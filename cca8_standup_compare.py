# -*- coding: utf-8 -*-
"""Phase 3A StandUp map-native compare transaction.

Purpose
-------
Phase 3A moves the ``StandUp`` domain from authority level 2 (shadow) to
level 3 (compare/dual-run). The maintained NavMapV2 SELF-ground shadow now
independently answers a narrow task-level question:

    "Does the maintained body-ground geometry make StandUp applicable?"

When the map path recommends StandUp, it also constructs an authority-neutral
expected standing successor map. The existing BodyMap/PolicyRuntime path still
performs all gating, selection, and execution. The two paths are compared and
recorded, but the map path cannot change the selected behavioral primitive,
BodyMap, WorldGraph, environment, or lower-controller behavior.

Transaction timing
------------------
One closed-loop cycle has two Phase 3A moments:

1. Observation step
   Finalize any expected successor armed by the previous StandUp selection,
   then independently query the newly maintained SELF-ground shadow.
2. Selection step
   Record the actual legacy StandUp gate result and selected policy. If the
   legacy controller selected StandUp and the map path independently produced
   an expected successor, arm that expected map for comparison with the next
   observation.

The expected successor represents the task-level result of the behavioral
primitive: an upright SELF-ground configuration. It does not model hoof paths,
joint trajectories, balance corrections, or other lower motor details.

Authority boundary
------------------
This module is compare-only. ``legacy_executes`` is always true and
``map_can_override`` is always false. All public trace records state that
boundary explicitly.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Optional

from cca8_navmap_kernel import (
    NavActivationV1,
    NavBodyStateEvidenceV1,
    NavBodyStateInterpretationV1,
    NavElementV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapRefV1,
    NavMapV2,
    NavMatchStatusV1,
    NavPointV1,
    NavProvenanceV1,
    NavSourceClassV1,
    NavStructuredResidualV1,
    body_state_evidence,
    get_element,
    match_navmaps,
    structured_residual,
)
from cca8_navmap_shadow import (
    NavMapV2ShadowStateV2,
    navmap_v2_shadow_body_thresholds_v1,
    navmap_v2_shadow_match_thresholds_v1,
)

__version__ = "0.1.0"

__all__ = [
    "StandUpMapRecommendationV1",
    "StandUpCompareTransactionV1",
    "StandUpExpectedPendingV1",
    "StandUpObservedOutcomeV1",
    "standup_expected_successor_map_v1",
    "standup_compare_observation_step_v1",
    "standup_compare_selection_step_v1",
    "standup_compare_summary_v1",
    "render_standup_compare_lines_v1",
    "__version__",
]

_STANDUP_POLICY = "policy:stand_up"
_EXPECTED_MAP_ID_PREFIX = "goat_self_ground_expected_standup_v2"
_EXPECTED_SOURCE_REF_PREFIX = "behavioral_primitive:stand_up:phase3a_compare"
_ACTIONABLE_SUPPORT = frozenset({"fresh", "aging"})
_DEFAULT_HISTORY_LIMIT = 25


class StandUpMapRecommendationV1(str, Enum):
    """Map-native Phase 3A recommendation for the StandUp domain."""

    STAND_UP = "stand_up"
    DO_NOT_STAND = "do_not_stand"
    DEFER = "defer"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Validate one positive integer without accepting bool as an integer."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Validate one non-negative integer without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Validate one non-empty string field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the stable reference of one immutable map revision."""
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return a JSON-safe optional map reference."""
    return ref.as_dict() if ref is not None else None


def _body_state(navmap: NavMapV2) -> NavBodyStateEvidenceV1:
    """Derive the standard SELF-ground body-state readout from one map."""
    return body_state_evidence(
        navmap,
        body_element_id="self_body",
        head_element_id="self_head",
        foot_element_id="self_foot",
        ground_element_id="ground_surface",
        thresholds=navmap_v2_shadow_body_thresholds_v1(),
    )


def _point(x: float, y: float) -> NavPointV1:
    """Create one concise immutable point."""
    return NavPointV1(x=x, y=y)


def _geometry(kind: NavGeometryKindV1, *points: NavPointV1) -> NavGeometryV1:
    """Create one immutable geometry record."""
    return NavGeometryV1(kind=kind, points=tuple(points))


def _expected_provenance(transaction_no: int) -> NavProvenanceV1:
    """Return explicit EXPECTED provenance for one compare transaction."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.EXPECTED,
        source_ref=f"{_EXPECTED_SOURCE_REF_PREFIX}:{transaction_no}",
        quality=0.75,
    )


def _expected_activations(
    element: NavElementV1,
    provenance: NavProvenanceV1,
) -> tuple[NavActivationV1, ...]:
    """Copy activation names/strengths while marking expected provenance."""
    return tuple(
        NavActivationV1(
            name=activation.name,
            strength=activation.strength,
            provenance=provenance,
        )
        for activation in element.activations
    )


def _expected_upright_geometry(element_id: str) -> NavGeometryV1:
    """Return the canonical task-level upright geometry for one SELF element."""
    if element_id == "self_body":
        return _geometry(NavGeometryKindV1.SEGMENT, _point(0.0, 0.2), _point(0.0, 2.0))
    if element_id == "self_head":
        return _geometry(NavGeometryKindV1.POINT, _point(0.0, 2.2))
    if element_id == "self_foot":
        return _geometry(NavGeometryKindV1.POINT, _point(0.0, 0.0))
    raise KeyError(f"no StandUp expected geometry for element {element_id!r}")


def standup_expected_successor_map_v1(
    body_ground_map: NavMapV2,
    *,
    transaction_no: int,
) -> NavMapV2:
    """Build an authority-neutral expected standing successor map.

    The current maintained SELF-ground map supplies the declared frame,
    unchanged ground/support content, sparse relations, and links. The three
    SELF geometry elements are replaced by the canonical upright task outcome
    and receive ``EXPECTED`` provenance. The result uses a separate map family
    so it cannot be mistaken for an accepted or maintained content revision.

    This is a task-level expectation for the behavioral primitive, not a motor
    trajectory. It intentionally does not specify how the lower controller
    achieves the upright configuration.
    """
    if not isinstance(body_ground_map, NavMapV2):
        raise TypeError("body_ground_map must be NavMapV2")
    _require_positive_int(transaction_no, field_name="transaction_no")

    required_ids = ("self_body", "self_head", "self_foot", "ground_surface")
    for element_id in required_ids:
        get_element(body_ground_map, element_id)

    provenance = _expected_provenance(transaction_no)
    expected_elements: list[NavElementV1] = []
    for element in body_ground_map.elements:
        if element.element_id in {"self_body", "self_head", "self_foot"}:
            expected_elements.append(
                replace(
                    element,
                    geometry=_expected_upright_geometry(element.element_id),
                    activations=_expected_activations(element, provenance),
                    provenance=provenance,
                )
            )
        else:
            expected_elements.append(element)

    expected_map = NavMapV2(
        map_id=f"{_EXPECTED_MAP_ID_PREFIX}_t{transaction_no:06d}",
        revision=1,
        parent_ref=None,
        role=body_ground_map.role,
        frame=body_ground_map.frame,
        provenance=provenance,
        elements=tuple(expected_elements),
        relations=body_ground_map.relations,
        links=body_ground_map.links,
        schema=body_ground_map.schema,
    )
    expected_state = _body_state(expected_map)
    if expected_state.interpretation is not NavBodyStateInterpretationV1.STANDING_LIKE:
        raise ValueError("StandUp expected successor must derive STANDING_LIKE")
    return expected_map


@dataclass(frozen=True, slots=True)
class StandUpCompareTransactionV1:
    """One Phase 3A map decision plus later legacy-selection comparison."""

    transaction_no: int
    observation_no: int
    shadow_body_ground_ref: Optional[NavMapRefV1]
    map_body_interpretation: NavBodyStateInterpretationV1
    map_maintained: bool
    support_status: str
    map_recommendation: StandUpMapRecommendationV1
    map_reason: str
    expected_successor_map: Optional[NavMapV2]
    legacy_bodymap_posture: Optional[str]
    legacy_gate_triggered: Optional[bool] = None
    selected_policy: Optional[str] = None
    gate_comparison: str = "pending"
    selection_comparison: str = "pending"
    pending_expected_armed: bool = False

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.shadow_body_ground_ref is not None and not isinstance(self.shadow_body_ground_ref, NavMapRefV1):
            raise TypeError("shadow_body_ground_ref must be NavMapRefV1 or None")
        if not isinstance(self.map_body_interpretation, NavBodyStateInterpretationV1):
            raise TypeError("map_body_interpretation must be NavBodyStateInterpretationV1")
        if not isinstance(self.map_maintained, bool):
            raise TypeError("map_maintained must be bool")
        _require_nonempty_text(self.support_status, field_name="support_status")
        if not isinstance(self.map_recommendation, StandUpMapRecommendationV1):
            raise TypeError("map_recommendation must be StandUpMapRecommendationV1")
        _require_nonempty_text(self.map_reason, field_name="map_reason")
        if self.expected_successor_map is not None:
            if not isinstance(self.expected_successor_map, NavMapV2):
                raise TypeError("expected_successor_map must be NavMapV2 or None")
            expected_state = _body_state(self.expected_successor_map)
            if expected_state.interpretation is not NavBodyStateInterpretationV1.STANDING_LIKE:
                raise ValueError("expected_successor_map must derive STANDING_LIKE")
        if self.map_recommendation is StandUpMapRecommendationV1.STAND_UP:
            if self.expected_successor_map is None:
                raise ValueError("STAND_UP recommendation requires expected_successor_map")
        elif self.expected_successor_map is not None:
            raise ValueError("only STAND_UP recommendation may carry expected_successor_map")
        if self.legacy_bodymap_posture is not None and not isinstance(self.legacy_bodymap_posture, str):
            raise TypeError("legacy_bodymap_posture must be str or None")
        if self.legacy_gate_triggered is not None and not isinstance(self.legacy_gate_triggered, bool):
            raise TypeError("legacy_gate_triggered must be bool or None")
        if self.selected_policy is not None and not isinstance(self.selected_policy, str):
            raise TypeError("selected_policy must be str or None")
        _require_nonempty_text(self.gate_comparison, field_name="gate_comparison")
        _require_nonempty_text(self.selection_comparison, field_name="selection_comparison")
        if not isinstance(self.pending_expected_armed, bool):
            raise TypeError("pending_expected_armed must be bool")
        if self.pending_expected_armed:
            if self.selected_policy != _STANDUP_POLICY or self.expected_successor_map is None:
                raise ValueError("pending expectation requires selected StandUp and an expected successor")

    @property
    def expected_successor_ref(self) -> Optional[NavMapRefV1]:
        """Return the optional expected successor reference."""
        if self.expected_successor_map is None:
            return None
        return _map_ref(self.expected_successor_map)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit compare trace."""
        expected_state = _body_state(self.expected_successor_map) if self.expected_successor_map is not None else None
        return {
            "schema": "standup_compare_transaction_v1",
            "phase": "3A",
            "authority_level": "compare_dual_run",
            "authority": "compare_only",
            "legacy_authority": "bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
            "execution_source": "legacy_bodymap_policy_runtime",
            "fallback_status": "not_applicable_compare_only",
            "behavioral_primitive": "stand_up",
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "shadow_body_ground_ref": _optional_ref_dict(self.shadow_body_ground_ref),
            "map_body_interpretation": self.map_body_interpretation.value,
            "map_maintained": self.map_maintained,
            "support_status": self.support_status,
            "map_recommendation": self.map_recommendation.value,
            "map_reason": self.map_reason,
            "expected_successor_ref": _optional_ref_dict(self.expected_successor_ref),
            "expected_successor_content_signature": (
                self.expected_successor_map.content_signature() if self.expected_successor_map is not None else None
            ),
            "expected_successor_body_state": expected_state.as_dict() if expected_state is not None else None,
            "legacy_bodymap_posture": self.legacy_bodymap_posture,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "selected_policy": self.selected_policy,
            "legacy_selected_standup": self.selected_policy == _STANDUP_POLICY,
            "gate_comparison": self.gate_comparison,
            "selection_comparison": self.selection_comparison,
            "pending_expected_armed": self.pending_expected_armed,
        }


@dataclass(frozen=True, slots=True)
class StandUpExpectedPendingV1:
    """Expected successor armed after the legacy controller selects StandUp."""

    transaction_no: int
    expected_successor_map: NavMapV2
    selected_policy: str
    selected_controller_step: int

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor_map, NavMapV2):
            raise TypeError("expected_successor_map must be NavMapV2")
        if self.selected_policy != _STANDUP_POLICY:
            raise ValueError("StandUp pending expectation requires policy:stand_up")
        _require_non_negative_int(self.selected_controller_step, field_name="selected_controller_step")


@dataclass(frozen=True, slots=True)
class StandUpObservedOutcomeV1:
    """Observed evidence compared with one applied StandUp expectation."""

    transaction_no: int
    expected_successor_map: NavMapV2
    evidence_map: NavMapV2
    action_applied: Optional[str]
    outcome: str
    observed_interpretation: NavBodyStateInterpretationV1
    match_status: Optional[NavMatchStatusV1]
    residual: Optional[NavStructuredResidualV1]
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor_map, NavMapV2):
            raise TypeError("expected_successor_map must be NavMapV2")
        if not isinstance(self.evidence_map, NavMapV2):
            raise TypeError("evidence_map must be NavMapV2")
        if self.action_applied is not None and not isinstance(self.action_applied, str):
            raise TypeError("action_applied must be str or None")
        _require_nonempty_text(self.outcome, field_name="outcome")
        if not isinstance(self.observed_interpretation, NavBodyStateInterpretationV1):
            raise TypeError("observed_interpretation must be NavBodyStateInterpretationV1")
        if self.match_status is not None and not isinstance(self.match_status, NavMatchStatusV1):
            raise TypeError("match_status must be NavMatchStatusV1 or None")
        if self.residual is not None and not isinstance(self.residual, NavStructuredResidualV1):
            raise TypeError("residual must be NavStructuredResidualV1 or None")
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe expected-versus-observed trace."""
        residual_dict = self.residual.as_dict() if self.residual is not None else None
        changed_id_set: set[str] = set()
        if self.residual is not None:
            for item in self.residual.element_residuals:
                expected_element_id = item.expected_element_id
                if item.content_difference and isinstance(expected_element_id, str):
                    changed_id_set.add(expected_element_id)
        changed_ids = sorted(changed_id_set)
        return {
            "schema": "standup_observed_outcome_v1",
            "phase": "3A",
            "authority": "compare_only",
            "legacy_executes": True,
            "map_can_override": False,
            "execution_source": "legacy_bodymap_policy_runtime",
            "fallback_status": "not_applicable_compare_only",
            "behavioral_primitive": "stand_up",
            "transaction_no": self.transaction_no,
            "expected_successor_ref": _map_ref(self.expected_successor_map).as_dict(),
            "expected_successor_content_signature": self.expected_successor_map.content_signature(),
            "evidence_map_ref": _map_ref(self.evidence_map).as_dict(),
            "evidence_content_signature": self.evidence_map.content_signature(),
            "action_applied": self.action_applied,
            "outcome": self.outcome,
            "observed_interpretation": self.observed_interpretation.value,
            "match_status": self.match_status.value if self.match_status is not None else None,
            "structured_residual": residual_dict,
            "changed_element_ids": changed_ids,
            "reason": self.reason,
        }


def _next_transaction_no(ctx: Any) -> int:
    """Advance and return the deterministic Phase 3A transaction counter."""
    try:
        current = int(getattr(ctx, "navmap_standup_compare_transaction_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    transaction_no = max(0, current) + 1
    ctx.navmap_standup_compare_transaction_no = transaction_no
    return transaction_no


def _history_limit(ctx: Any, field_name: str) -> int:
    """Return one bounded positive history limit from the context."""
    try:
        value = int(getattr(ctx, field_name, _DEFAULT_HISTORY_LIMIT) or _DEFAULT_HISTORY_LIMIT)
    except (TypeError, ValueError):
        return _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_dict_history(ctx: Any, *, field_name: str, limit_field_name: str, row: dict[str, Any]) -> None:
    """Append one defensive JSON-safe row to a bounded context history."""
    history = getattr(ctx, field_name, [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    clean.append(dict(row))
    limit = _history_limit(ctx, limit_field_name)
    setattr(ctx, field_name, clean[-limit:])


def _map_recommendation(
    shadow_state: NavMapV2ShadowStateV2,
) -> tuple[StandUpMapRecommendationV1, str]:
    """Return the narrow map-native StandUp applicability result."""
    if not shadow_state.maintained or shadow_state.body_ground_map is None:
        return StandUpMapRecommendationV1.DEFER, "shadow_not_maintained"
    if shadow_state.support_status not in _ACTIONABLE_SUPPORT:
        return StandUpMapRecommendationV1.DEFER, f"support_{shadow_state.support_status}"
    stable_state = shadow_state.stable_body_state
    if stable_state is None:
        return StandUpMapRecommendationV1.DEFER, "stable_body_state_unavailable"
    if stable_state.interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE:
        return StandUpMapRecommendationV1.STAND_UP, "maintained_geometry_fallen_like"
    if stable_state.interpretation is NavBodyStateInterpretationV1.STANDING_LIKE:
        return StandUpMapRecommendationV1.DO_NOT_STAND, "maintained_geometry_standing_like"
    return StandUpMapRecommendationV1.DEFER, f"maintained_geometry_{stable_state.interpretation.value}"


def _gate_comparison(
    recommendation: StandUpMapRecommendationV1,
    legacy_gate_triggered: Optional[bool],
) -> str:
    """Compare the map query with the existing StandUp trigger gate."""
    if legacy_gate_triggered is None:
        return "legacy_gate_unavailable"
    if recommendation is StandUpMapRecommendationV1.DEFER:
        return "map_deferred"
    if recommendation is StandUpMapRecommendationV1.STAND_UP:
        return "agree_trigger" if legacy_gate_triggered else "disagree_map_trigger_legacy_no"
    return "agree_no_trigger" if not legacy_gate_triggered else "disagree_map_no_legacy_trigger"


def _selection_comparison(
    recommendation: StandUpMapRecommendationV1,
    selected_policy: Optional[str],
) -> str:
    """Compare the map recommendation with the legacy controller's winner."""
    selected_standup = selected_policy == _STANDUP_POLICY
    if recommendation is StandUpMapRecommendationV1.DEFER:
        return "map_deferred_standup_selected" if selected_standup else "map_deferred"
    if recommendation is StandUpMapRecommendationV1.STAND_UP:
        return "agree_standup_selected" if selected_standup else "map_standup_not_selected"
    return "disagree_standup_selected" if selected_standup else "agree_standup_not_selected"


def _finalize_pending_expectation(
    ctx: Any,
    *,
    applied_policy: Optional[str],
    shadow_state: NavMapV2ShadowStateV2,
) -> Optional[StandUpObservedOutcomeV1]:
    """Compare one armed expected successor with the current evidence map."""
    pending = getattr(ctx, "navmap_standup_compare_pending", None)
    if not isinstance(pending, StandUpExpectedPendingV1):
        return None

    evidence_map = shadow_state.evidence_body_ground_map
    observed_state = shadow_state.evidence_body_state
    match_status: Optional[NavMatchStatusV1] = None
    residual: Optional[NavStructuredResidualV1] = None

    if applied_policy != _STANDUP_POLICY:
        outcome = "not_applied"
        reason = "armed_standup_was_not_the_applied_action"
    elif observed_state.interpretation is NavBodyStateInterpretationV1.STANDING_LIKE:
        match = match_navmaps(
            pending.expected_successor_map,
            evidence_map,
            thresholds=navmap_v2_shadow_match_thresholds_v1(),
        )
        residual = structured_residual(
            pending.expected_successor_map,
            evidence_map,
            match_result=match,
        )
        match_status = match.status
        outcome = "success"
        reason = "observed_geometry_standing_like"
    elif observed_state.interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE:
        match = match_navmaps(
            pending.expected_successor_map,
            evidence_map,
            thresholds=navmap_v2_shadow_match_thresholds_v1(),
        )
        residual = structured_residual(
            pending.expected_successor_map,
            evidence_map,
            match_result=match,
        )
        match_status = match.status
        outcome = "failure"
        reason = "observed_geometry_remains_fallen_like"
    else:
        outcome = "unknown"
        reason = f"observed_geometry_{observed_state.interpretation.value}"

    result = StandUpObservedOutcomeV1(
        transaction_no=pending.transaction_no,
        expected_successor_map=pending.expected_successor_map,
        evidence_map=evidence_map,
        action_applied=applied_policy,
        outcome=outcome,
        observed_interpretation=observed_state.interpretation,
        match_status=match_status,
        residual=residual,
        reason=reason,
    )
    ctx.navmap_standup_compare_pending = None
    ctx.navmap_standup_compare_last_outcome = result
    row = result.as_dict()
    ctx.navmap_standup_compare_last_outcome_update = dict(row)
    _append_dict_history(
        ctx,
        field_name="navmap_standup_compare_outcome_history",
        limit_field_name="navmap_standup_compare_outcome_history_limit",
        row=row,
    )
    return result


def _update_summary(ctx: Any) -> dict[str, Any]:
    """Refresh and return the combined latest Phase 3A summary."""
    transaction = getattr(ctx, "navmap_standup_compare_transaction", None)
    outcome = getattr(ctx, "navmap_standup_compare_last_outcome", None)
    summary = {
        "schema": "standup_compare_summary_v1",
        "phase": "3A",
        "authority_level": "compare_dual_run",
        "authority": "compare_only",
        "legacy_authority": "bodymap_policy_runtime",
        "legacy_executes": True,
        "map_can_override": False,
        "execution_source": "legacy_bodymap_policy_runtime",
        "fallback_status": "not_applicable_compare_only",
        "status": "active" if isinstance(transaction, StandUpCompareTransactionV1) else "idle",
        "transaction": transaction.as_dict() if isinstance(transaction, StandUpCompareTransactionV1) else None,
        "observed_outcome": outcome.as_dict() if isinstance(outcome, StandUpObservedOutcomeV1) else None,
        "pending_expected": isinstance(getattr(ctx, "navmap_standup_compare_pending", None), StandUpExpectedPendingV1),
        "transaction_history_count": len(getattr(ctx, "navmap_standup_compare_history", []) or []),
        "outcome_history_count": len(getattr(ctx, "navmap_standup_compare_outcome_history", []) or []),
    }
    ctx.navmap_standup_compare_last_update = dict(summary)
    return summary


def standup_compare_observation_step_v1(
    ctx: Any,
    *,
    applied_policy: Optional[str] = None,
) -> dict[str, Any]:
    """Finalize prior StandUp expectation and create the current map query.

    This function must run after the Phase 2B shadow has processed the current
    observation. It reads only the shadow transaction and context telemetry. It
    does not write BodyMap, WorldGraph, PolicyRuntime, environment, or action
    selection state.
    """
    if ctx is None:
        return {
            "schema": "standup_compare_summary_v1",
            "status": "ctx_unavailable",
            "authority": "compare_only",
        }
    if not bool(getattr(ctx, "navmap_standup_compare_enabled", True)):
        return {
            "schema": "standup_compare_summary_v1",
            "status": "disabled",
            "authority": "compare_only",
            "legacy_executes": True,
            "map_can_override": False,
        }

    shadow_state = getattr(ctx, "navmap_v2_shadow_state", None)
    if not isinstance(shadow_state, NavMapV2ShadowStateV2):
        ctx.navmap_standup_compare_transaction = None
        return _update_summary(ctx)

    _finalize_pending_expectation(
        ctx,
        applied_policy=applied_policy if isinstance(applied_policy, str) else None,
        shadow_state=shadow_state,
    )

    transaction_no = _next_transaction_no(ctx)
    recommendation, reason = _map_recommendation(shadow_state)
    expected_map: Optional[NavMapV2] = None
    if recommendation is StandUpMapRecommendationV1.STAND_UP and shadow_state.body_ground_map is not None:
        try:
            expected_map = standup_expected_successor_map_v1(
                shadow_state.body_ground_map,
                transaction_no=transaction_no,
            )
        except (KeyError, TypeError, ValueError) as exc:
            recommendation = StandUpMapRecommendationV1.DEFER
            reason = f"expected_successor_unavailable:{type(exc).__name__}"

    stable_state = shadow_state.stable_body_state
    interpretation = (
        stable_state.interpretation
        if shadow_state.maintained and stable_state is not None
        else NavBodyStateInterpretationV1.UNKNOWN
    )
    body_ref = shadow_state.body_ground_ref
    transaction = StandUpCompareTransactionV1(
        transaction_no=transaction_no,
        observation_no=shadow_state.observation_no,
        shadow_body_ground_ref=body_ref,
        map_body_interpretation=interpretation,
        map_maintained=shadow_state.maintained,
        support_status=shadow_state.support_status,
        map_recommendation=recommendation,
        map_reason=reason,
        expected_successor_map=expected_map,
        legacy_bodymap_posture=shadow_state.legacy_bodymap_posture,
    )
    ctx.navmap_standup_compare_transaction = transaction
    return _update_summary(ctx)


def standup_compare_selection_step_v1(
    ctx: Any,
    *,
    legacy_gate_triggered: Optional[bool],
    selected_policy: Optional[str],
) -> dict[str, Any]:
    """Record the legacy gate/winner and optionally arm expected comparison.

    The function observes the selection already made by the legacy controller.
    It never changes that winner and never writes ``ctx.env_last_action``.
    """
    if ctx is None:
        return {
            "schema": "standup_compare_summary_v1",
            "status": "ctx_unavailable",
            "authority": "compare_only",
        }
    if not bool(getattr(ctx, "navmap_standup_compare_enabled", True)):
        return {
            "schema": "standup_compare_summary_v1",
            "status": "disabled",
            "authority": "compare_only",
            "legacy_executes": True,
            "map_can_override": False,
        }

    transaction = getattr(ctx, "navmap_standup_compare_transaction", None)
    if not isinstance(transaction, StandUpCompareTransactionV1):
        return _update_summary(ctx)

    gate_value = legacy_gate_triggered if isinstance(legacy_gate_triggered, bool) else None
    policy_value = selected_policy if isinstance(selected_policy, str) and selected_policy else None
    arm_pending = policy_value == _STANDUP_POLICY and transaction.expected_successor_map is not None
    updated = replace(
        transaction,
        legacy_gate_triggered=gate_value,
        selected_policy=policy_value,
        gate_comparison=_gate_comparison(transaction.map_recommendation, gate_value),
        selection_comparison=_selection_comparison(transaction.map_recommendation, policy_value),
        pending_expected_armed=arm_pending,
    )
    ctx.navmap_standup_compare_transaction = updated

    if arm_pending and updated.expected_successor_map is not None:
        try:
            controller_step = int(getattr(ctx, "controller_steps", 0) or 0)
        except (TypeError, ValueError):
            controller_step = 0
        ctx.navmap_standup_compare_pending = StandUpExpectedPendingV1(
            transaction_no=updated.transaction_no,
            expected_successor_map=updated.expected_successor_map,
            selected_policy=_STANDUP_POLICY,
            selected_controller_step=max(0, controller_step),
        )

    row = updated.as_dict()
    _append_dict_history(
        ctx,
        field_name="navmap_standup_compare_history",
        limit_field_name="navmap_standup_compare_history_limit",
        row=row,
    )
    return _update_summary(ctx)


def standup_compare_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 3A state."""
    if ctx is None:
        return {
            "schema": "standup_compare_summary_v1",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_standup_compare_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "standup_compare_summary_v1",
            "status": "idle",
            "authority": "compare_only",
            "legacy_executes": True,
            "map_can_override": False,
        }
    return dict(row)


def _ref_text(value: Any) -> str:
    """Render one optional JSON map reference."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id', '?')}@r{value.get('revision', '?')}"


def render_standup_compare_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 3A compare lines."""
    summary = standup_compare_summary_v1(ctx)
    lines = ["STANDUP PHASE 3A COMPARE:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle", "disabled"}:
        lines.append(f"  status={status} authority=compare_only legacy_executes=True")
        return lines

    transaction = summary.get("transaction")
    transaction = transaction if isinstance(transaction, dict) else {}
    lines.append(
        "  "
        f"tx={transaction.get('transaction_no')} authority=compare_only "
        "legacy_executes=True map_can_override=False "
        "fallback=not_applicable_compare_only"
    )
    lines.append(
        "  "
        f"map body={_ref_text(transaction.get('shadow_body_ground_ref'))} "
        f"derived={transaction.get('map_body_interpretation')} "
        f"support={transaction.get('support_status')} "
        f"recommendation={transaction.get('map_recommendation')} "
        f"reason={transaction.get('map_reason')}"
    )
    expected_state = transaction.get("expected_successor_body_state")
    expected_state = expected_state if isinstance(expected_state, dict) else {}
    lines.append(
        "  "
        f"expected={_ref_text(transaction.get('expected_successor_ref'))} "
        f"derived={expected_state.get('interpretation', 'none')}"
    )
    lines.append(
        "  "
        f"legacy posture={transaction.get('legacy_bodymap_posture')} "
        f"gate={transaction.get('legacy_gate_triggered')} "
        f"selected={transaction.get('selected_policy')} "
        f"gate_comparison={transaction.get('gate_comparison')} "
        f"selection_comparison={transaction.get('selection_comparison')}"
    )
    lines.append(f"  pending_expected={summary.get('pending_expected')}")

    outcome = summary.get("observed_outcome")
    if isinstance(outcome, dict):
        residual = outcome.get("structured_residual")
        residual_reason = residual.get("reason") if isinstance(residual, dict) else None
        lines.append(
            "  "
            f"observed tx={outcome.get('transaction_no')} action={outcome.get('action_applied')} "
            f"outcome={outcome.get('outcome')} "
            f"evidence={_ref_text(outcome.get('evidence_map_ref'))} "
            f"derived={outcome.get('observed_interpretation')} "
            f"match={outcome.get('match_status')} residual={residual_reason}"
        )
    return lines
