# -*- coding: utf-8 -*-
"""Phase 3A/3B StandUp map-native compare and advisory transactions.

Purpose
-------
Phase 3A moved the ``StandUp`` domain from authority level 2 (shadow) to
level 3 (compare/dual-run). The maintained NavMapV2 SELF-ground shadow now
independently answers a narrow task-level question:

    "Does the maintained body-ground geometry make StandUp applicable?"

When the map path recommends StandUp, it also constructs an authority-neutral
expected standing successor map. The existing BodyMap/PolicyRuntime path still
performs all gating, selection, and execution. The two paths are compared and
recorded, but the map path cannot change the selected behavioral primitive,
BodyMap, WorldGraph, environment, or lower-controller behavior.

Phase 3B adds the authority-level-4 advisory surface. It converts bounded
compare results into explicit notices for unsupported/UNKNOWN posture, stale
support, expected-transform failure, map/legacy disagreement, and failed or
unresolved StandUp outcomes. An advisory can recommend resampling, review, or
continued BodyMap fallback, but it remains telemetry only: it cannot alter the
legacy StandUp gate, selected policy, safety path, or applied action.

Phase 3C added one feature-flagged guarded-authority decision for the StandUp
trigger. When enabled, fresh or aging maintained SELF-ground geometry can
supply the cognitive trigger. Stale, invalidated, UNKNOWN, ambiguous, missing,
or transform-incomplete map state falls back to the existing BodyMap/legacy
gate. A fresh BodyMap fallen signal remains a protected rapid safety override.

Phase 3D promotes that same bounded and validated path to default authority.
New contexts therefore use the maintained WNM/NavMap as the normal cognitive
source for StandUp without requiring an enabling flag. Explicit ``legacy`` and
``guarded`` modes remain available for experiments, differential diagnosis,
and rollback. BodyMap is not retired: fresh fallen evidence remains protected,
and unsupported map content still invokes the complete legacy fallback chain.
The existing Python behavioral primitive and lower controller continue to
execute the action; map authority remains limited to this one trigger and its
expected successor.

Transaction timing
------------------
One closed-loop cycle has two compare/advisory moments:

1. Observation step
   Finalize any expected successor armed by the previous StandUp selection,
   query the newly maintained SELF-ground shadow, and form a provisional
   advisory from the current map support and prior outcome.
2. Selection step
   Record the actual legacy StandUp gate result and selected policy, arm any
   expected successor, and finalize the current advisory with the legacy
   differential.

The expected successor represents the task-level result of the behavioral
primitive: an upright SELF-ground configuration. It does not model hoof paths,
joint trajectories, balance corrections, or other lower motor details.

Authority boundary
------------------
Phase 3A is compare-only and Phase 3B is advisory-only. Phase 3C remains an
explicit guarded mode, while Phase 3D makes the same validated map query the
default cognitive source. Neither mode can override a fresh BodyMap fallen
safety signal, mutate BodyMap, alter other behavioral-primitive domains, retire
the legacy fallback, or replace the PolicyRuntime/controller execution
substrate. All public trace records state the active boundary explicitly.
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

__version__ = "0.4.0"

__all__ = [
    "StandUpMapRecommendationV1",
    "StandUpAdvisoryKindV1",
    "StandUpAdvisorySeverityV1",
    "StandUpAuthorityModeV1",
    "StandUpGuardedAuthoritySourceV1",
    "StandUpCompareTransactionV1",
    "StandUpExpectedPendingV1",
    "StandUpObservedOutcomeV1",
    "StandUpAdvisoryV1",
    "StandUpGuardedDecisionV1",
    "standup_expected_successor_map_v1",
    "standup_compare_observation_step_v1",
    "standup_compare_selection_step_v1",
    "standup_compare_summary_v1",
    "render_standup_compare_lines_v1",
    "standup_advisory_observation_step_v1",
    "standup_advisory_selection_step_v1",
    "standup_advisory_summary_v1",
    "render_standup_advisory_lines_v1",
    "standup_authority_mode_v1",
    "standup_guarded_trigger_value_v1",
    "standup_guarded_safety_active_v1",
    "standup_guarded_explain_v1",
    "standup_guarded_selection_step_v1",
    "standup_guarded_summary_v1",
    "render_standup_guarded_lines_v1",
    "standup_authority_summary_v1",
    "render_standup_authority_lines_v1",
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


class StandUpAuthorityModeV1(str, Enum):
    """Configured StandUp authority mode across Phase 3C and Phase 3D."""

    LEGACY = "legacy"
    GUARDED = "guarded"
    DEFAULT = "default"


class StandUpAdvisoryKindV1(str, Enum):
    """Bounded Phase 3B advisory classifications."""

    CLEAR = "clear"
    SUPPORT_AGING = "support_aging"
    POSTURE_UNSUPPORTED = "posture_unsupported"
    EXPECTED_TRANSFORM_FAILURE = "expected_transform_failure"
    MAP_LEGACY_DISAGREEMENT = "map_legacy_disagreement"
    STANDUP_OUTCOME_FAILURE = "standup_outcome_failure"
    STANDUP_OUTCOME_UNKNOWN = "standup_outcome_unknown"
    ACTION_HANDOFF_MISMATCH = "action_handoff_mismatch"


class StandUpAdvisorySeverityV1(str, Enum):
    """Human-readable advisory severity without behavioral authority."""

    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"


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



@dataclass(frozen=True, slots=True)
class StandUpAdvisoryV1:
    """One bounded Phase 3B advisory derived from compare-only records.

    The record can request review, resampling, or continued BodyMap fallback,
    but it cannot change a gate, selected behavioral primitive, applied action,
    BodyMap content, or protected safety behavior.
    """

    transaction_no: int
    observation_no: int
    source_stage: str
    kind: StandUpAdvisoryKindV1
    severity: StandUpAdvisorySeverityV1
    active: bool
    reason: str
    recommended_response: str
    map_recommendation: StandUpMapRecommendationV1
    map_reason: str
    map_body_interpretation: NavBodyStateInterpretationV1
    support_status: str
    legacy_bodymap_posture: Optional[str]
    legacy_gate_triggered: Optional[bool]
    selected_policy: Optional[str]
    gate_comparison: str
    selection_comparison: str
    prior_outcome_transaction_no: Optional[int]
    prior_outcome: Optional[str]
    fallback_required: bool
    resample_recommended: bool
    transform_review_recommended: bool
    disagreement_review_recommended: bool
    outcome_review_recommended: bool

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.source_stage not in {"observation", "selection"}:
            raise ValueError("source_stage must be 'observation' or 'selection'")
        if not isinstance(self.kind, StandUpAdvisoryKindV1):
            raise TypeError("kind must be StandUpAdvisoryKindV1")
        if not isinstance(self.severity, StandUpAdvisorySeverityV1):
            raise TypeError("severity must be StandUpAdvisorySeverityV1")
        if not isinstance(self.active, bool):
            raise TypeError("active must be bool")
        _require_nonempty_text(self.reason, field_name="reason")
        _require_nonempty_text(self.recommended_response, field_name="recommended_response")
        if not isinstance(self.map_recommendation, StandUpMapRecommendationV1):
            raise TypeError("map_recommendation must be StandUpMapRecommendationV1")
        _require_nonempty_text(self.map_reason, field_name="map_reason")
        if not isinstance(self.map_body_interpretation, NavBodyStateInterpretationV1):
            raise TypeError("map_body_interpretation must be NavBodyStateInterpretationV1")
        _require_nonempty_text(self.support_status, field_name="support_status")
        if self.legacy_bodymap_posture is not None and not isinstance(self.legacy_bodymap_posture, str):
            raise TypeError("legacy_bodymap_posture must be str or None")
        if self.legacy_gate_triggered is not None and not isinstance(self.legacy_gate_triggered, bool):
            raise TypeError("legacy_gate_triggered must be bool or None")
        if self.selected_policy is not None and not isinstance(self.selected_policy, str):
            raise TypeError("selected_policy must be str or None")
        _require_nonempty_text(self.gate_comparison, field_name="gate_comparison")
        _require_nonempty_text(self.selection_comparison, field_name="selection_comparison")
        if self.prior_outcome_transaction_no is not None:
            _require_positive_int(
                self.prior_outcome_transaction_no,
                field_name="prior_outcome_transaction_no",
            )
        if self.prior_outcome is not None and not isinstance(self.prior_outcome, str):
            raise TypeError("prior_outcome must be str or None")
        for field_name in (
            "fallback_required",
            "resample_recommended",
            "transform_review_recommended",
            "disagreement_review_recommended",
            "outcome_review_recommended",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")

        if self.kind is StandUpAdvisoryKindV1.CLEAR:
            if self.active:
                raise ValueError("CLEAR advisory must not be active")
            if self.severity is not StandUpAdvisorySeverityV1.INFO:
                raise ValueError("CLEAR advisory must use INFO severity")
        elif not self.active:
            raise ValueError("non-CLEAR advisory must be active")

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe advisory and immutable authority contract."""
        return {
            "schema": "standup_advisory_v1",
            "phase": "3B",
            "authority_level": "advisory",
            "authority": "advisory_only",
            "legacy_authority": "bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
            "bodymap_mutation_allowed": False,
            "policy_selection_mutation_allowed": False,
            "requested_followup_is_behavioral_command": False,
            "behavioral_primitive": "stand_up",
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "source_stage": self.source_stage,
            "active": self.active,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "reason": self.reason,
            "recommended_response": self.recommended_response,
            "map_recommendation": self.map_recommendation.value,
            "map_reason": self.map_reason,
            "map_body_interpretation": self.map_body_interpretation.value,
            "support_status": self.support_status,
            "legacy_bodymap_posture": self.legacy_bodymap_posture,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "selected_policy": self.selected_policy,
            "selected_policy_before_advisory": self.selected_policy,
            "selected_policy_after_advisory": self.selected_policy,
            "legacy_action_unchanged": True,
            "gate_comparison": self.gate_comparison,
            "selection_comparison": self.selection_comparison,
            "prior_outcome_transaction_no": self.prior_outcome_transaction_no,
            "prior_outcome": self.prior_outcome,
            "fallback_required": self.fallback_required,
            "fallback_source": "bodymap_policy_runtime" if self.fallback_required else None,
            "resample_recommended": self.resample_recommended,
            "transform_review_recommended": self.transform_review_recommended,
            "disagreement_review_recommended": self.disagreement_review_recommended,
            "outcome_review_recommended": self.outcome_review_recommended,
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


def _relevant_prior_outcome(
    ctx: Any,
    transaction: StandUpCompareTransactionV1,
) -> Optional[StandUpObservedOutcomeV1]:
    """Return the outcome finalized immediately before the current transaction.

    ``navmap_standup_compare_last_outcome`` is intentionally retained for
    inspection. Restricting it to ``current transaction - 1`` prevents one old
    failure from producing an advisory on every later cognitive cycle.
    """
    outcome = getattr(ctx, "navmap_standup_compare_last_outcome", None)
    if not isinstance(outcome, StandUpObservedOutcomeV1):
        return None
    if outcome.transaction_no != transaction.transaction_no - 1:
        return None
    return outcome


def _transaction_has_disagreement(transaction: StandUpCompareTransactionV1) -> bool:
    """Return True when the actionable map and legacy StandUp paths diverge."""
    if transaction.gate_comparison.startswith("disagree_"):
        return True
    return transaction.selection_comparison in {
        "map_standup_not_selected",
        "disagree_standup_selected",
    }


def _advisory_decision(
    transaction: StandUpCompareTransactionV1,
    prior_outcome: Optional[StandUpObservedOutcomeV1],
) -> dict[str, Any]:
    """Return the bounded Phase 3B advisory classification and follow-up flags."""
    base: dict[str, Any] = {
        "kind": StandUpAdvisoryKindV1.CLEAR,
        "severity": StandUpAdvisorySeverityV1.INFO,
        "active": False,
        "reason": "no_advisory_condition_detected",
        "recommended_response": "continue_legacy_execution",
        "fallback_required": False,
        "resample_recommended": False,
        "transform_review_recommended": False,
        "disagreement_review_recommended": False,
        "outcome_review_recommended": False,
    }

    if prior_outcome is not None and prior_outcome.outcome == "failure":
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.STANDUP_OUTCOME_FAILURE,
                "severity": StandUpAdvisorySeverityV1.WARNING,
                "active": True,
                "reason": prior_outcome.reason,
                "recommended_response": "retain_legacy_recovery_and_review_standup_failure",
                "fallback_required": True,
                "outcome_review_recommended": True,
            }
        )
        return base

    if prior_outcome is not None and prior_outcome.outcome == "unknown":
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.STANDUP_OUTCOME_UNKNOWN,
                "severity": StandUpAdvisorySeverityV1.CAUTION,
                "active": True,
                "reason": prior_outcome.reason,
                "recommended_response": "retain_legacy_safety_and_resample_posture",
                "fallback_required": True,
                "resample_recommended": True,
                "outcome_review_recommended": True,
            }
        )
        return base

    if prior_outcome is not None and prior_outcome.outcome == "not_applied":
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.ACTION_HANDOFF_MISMATCH,
                "severity": StandUpAdvisorySeverityV1.WARNING,
                "active": True,
                "reason": prior_outcome.reason,
                "recommended_response": "retain_legacy_action_and_review_action_handoff",
                "fallback_required": True,
                "outcome_review_recommended": True,
            }
        )
        return base

    if transaction.map_reason.startswith("expected_successor_unavailable:"):
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.EXPECTED_TRANSFORM_FAILURE,
                "severity": StandUpAdvisorySeverityV1.WARNING,
                "active": True,
                "reason": transaction.map_reason,
                "recommended_response": "use_bodymap_fallback_and_review_expected_transform",
                "fallback_required": True,
                "transform_review_recommended": True,
            }
        )
        return base

    if transaction.map_recommendation is StandUpMapRecommendationV1.DEFER:
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.POSTURE_UNSUPPORTED,
                "severity": StandUpAdvisorySeverityV1.CAUTION,
                "active": True,
                "reason": transaction.map_reason,
                "recommended_response": "use_bodymap_fallback_and_resample_posture",
                "fallback_required": True,
                "resample_recommended": True,
            }
        )
        return base

    if _transaction_has_disagreement(transaction):
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.MAP_LEGACY_DISAGREEMENT,
                "severity": StandUpAdvisorySeverityV1.WARNING,
                "active": True,
                "reason": (
                    f"gate={transaction.gate_comparison};"
                    f"selection={transaction.selection_comparison}"
                ),
                "recommended_response": "retain_legacy_action_and_review_map_bodymap_disagreement",
                "fallback_required": True,
                "disagreement_review_recommended": True,
            }
        )
        return base

    if transaction.support_status == "aging":
        base.update(
            {
                "kind": StandUpAdvisoryKindV1.SUPPORT_AGING,
                "severity": StandUpAdvisorySeverityV1.CAUTION,
                "active": True,
                "reason": "maintained_posture_support_aging",
                "recommended_response": "monitor_support_and_resample_if_missing_continues",
                "resample_recommended": True,
            }
        )
    return base


def _build_advisory(
    ctx: Any,
    *,
    source_stage: str,
) -> Optional[StandUpAdvisoryV1]:
    """Build one advisory from the latest compare transaction without side effects."""
    transaction = getattr(ctx, "navmap_standup_compare_transaction", None)
    if not isinstance(transaction, StandUpCompareTransactionV1):
        return None

    prior_outcome = _relevant_prior_outcome(ctx, transaction)
    decision = _advisory_decision(transaction, prior_outcome)
    return StandUpAdvisoryV1(
        transaction_no=transaction.transaction_no,
        observation_no=transaction.observation_no,
        source_stage=source_stage,
        kind=decision["kind"],
        severity=decision["severity"],
        active=decision["active"],
        reason=decision["reason"],
        recommended_response=decision["recommended_response"],
        map_recommendation=transaction.map_recommendation,
        map_reason=transaction.map_reason,
        map_body_interpretation=transaction.map_body_interpretation,
        support_status=transaction.support_status,
        legacy_bodymap_posture=transaction.legacy_bodymap_posture,
        legacy_gate_triggered=transaction.legacy_gate_triggered,
        selected_policy=transaction.selected_policy,
        gate_comparison=transaction.gate_comparison,
        selection_comparison=transaction.selection_comparison,
        prior_outcome_transaction_no=(prior_outcome.transaction_no if prior_outcome is not None else None),
        prior_outcome=(prior_outcome.outcome if prior_outcome is not None else None),
        fallback_required=decision["fallback_required"],
        resample_recommended=decision["resample_recommended"],
        transform_review_recommended=decision["transform_review_recommended"],
        disagreement_review_recommended=decision["disagreement_review_recommended"],
        outcome_review_recommended=decision["outcome_review_recommended"],
    )


def _store_advisory(ctx: Any, advisory: StandUpAdvisoryV1) -> dict[str, Any]:
    """Store one ctx-local advisory and one bounded row per compare transaction."""
    row = advisory.as_dict()
    ctx.navmap_standup_advisory = advisory
    ctx.navmap_standup_advisory_last_update = dict(row)

    history = getattr(ctx, "navmap_standup_advisory_history", [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    if clean and clean[-1].get("transaction_no") == advisory.transaction_no:
        clean[-1] = dict(row)
    else:
        clean.append(dict(row))
    limit = _history_limit(ctx, "navmap_standup_advisory_history_limit")
    ctx.navmap_standup_advisory_history = clean[-limit:]
    return standup_advisory_summary_v1(ctx)


def _advisory_step(ctx: Any, *, source_stage: str) -> dict[str, Any]:
    """Run one Phase 3B advisory refresh after observation or legacy selection."""
    if ctx is None:
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "ctx_unavailable",
            "authority": "advisory_only",
        }
    if not bool(getattr(ctx, "navmap_standup_advisory_enabled", True)):
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "disabled",
            "authority": "advisory_only",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
        }
    if not bool(getattr(ctx, "navmap_standup_compare_enabled", True)):
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "compare_disabled",
            "authority": "advisory_only",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
        }

    advisory = _build_advisory(ctx, source_stage=source_stage)
    if advisory is None:
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "idle",
            "authority": "advisory_only",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
            "history_count": len(getattr(ctx, "navmap_standup_advisory_history", []) or []),
        }
    return _store_advisory(ctx, advisory)


def standup_advisory_observation_step_v1(ctx: Any) -> dict[str, Any]:
    """Create the provisional Phase 3B advisory after map observation work."""
    return _advisory_step(ctx, source_stage="observation")


def standup_advisory_selection_step_v1(ctx: Any) -> dict[str, Any]:
    """Finalize the Phase 3B advisory after the legacy gate and winner exist."""
    return _advisory_step(ctx, source_stage="selection")


def standup_advisory_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 3B advisory."""
    if ctx is None:
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "ctx_unavailable",
        }

    row = getattr(ctx, "navmap_standup_advisory_last_update", None)
    history_count = len(getattr(ctx, "navmap_standup_advisory_history", []) or [])
    if not isinstance(row, dict):
        return {
            "schema": "standup_advisory_summary_v1",
            "phase": "3B",
            "status": "idle",
            "authority": "advisory_only",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
            "history_count": history_count,
        }
    if row.get("status") == "error":
        out = dict(row)
        out["history_count"] = history_count
        return out

    return {
        "schema": "standup_advisory_summary_v1",
        "phase": "3B",
        "status": "active" if row.get("active") is True else "clear",
        "authority": "advisory_only",
        "legacy_executes": True,
        "map_can_override": False,
        "protected_safety_can_be_overridden": False,
        "advisory": dict(row),
        "history_count": history_count,
    }


def render_standup_advisory_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 3B advisory lines."""
    summary = standup_advisory_summary_v1(ctx)
    lines = ["STANDUP PHASE 3B ADVISORY:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle", "disabled", "compare_disabled", "error"}:
        lines.append(
            "  "
            f"status={status} authority=advisory_only legacy_executes=True "
            "map_can_override=False protected_safety_can_be_overridden=False"
        )
        if status == "error":
            lines.append(
                "  "
                f"error_type={summary.get('error_type')} error={summary.get('error')}"
            )
        return lines

    advisory = summary.get("advisory")
    advisory = advisory if isinstance(advisory, dict) else {}
    lines.append(
        "  "
        f"tx={advisory.get('transaction_no')} status={status} "
        "authority=advisory_only legacy_executes=True map_can_override=False "
        "protected_safety_can_be_overridden=False"
    )
    lines.append(
        "  "
        f"advisory={advisory.get('kind')} severity={advisory.get('severity')} "
        f"active={advisory.get('active')} reason={advisory.get('reason')}"
    )
    lines.append(
        "  "
        f"response={advisory.get('recommended_response')} "
        f"fallback_required={advisory.get('fallback_required')} "
        f"fallback_source={advisory.get('fallback_source')}"
    )
    lines.append(
        "  "
        f"map derived={advisory.get('map_body_interpretation')} "
        f"support={advisory.get('support_status')} "
        f"recommendation={advisory.get('map_recommendation')} "
        f"reason={advisory.get('map_reason')}"
    )
    lines.append(
        "  "
        f"legacy posture={advisory.get('legacy_bodymap_posture')} "
        f"gate={advisory.get('legacy_gate_triggered')} "
        f"selected={advisory.get('selected_policy')} "
        f"gate_comparison={advisory.get('gate_comparison')} "
        f"selection_comparison={advisory.get('selection_comparison')}"
    )
    lines.append(
        "  "
        f"flags resample={advisory.get('resample_recommended')} "
        f"transform_review={advisory.get('transform_review_recommended')} "
        f"disagreement_review={advisory.get('disagreement_review_recommended')} "
        f"outcome_review={advisory.get('outcome_review_recommended')}"
    )
    if advisory.get("prior_outcome") is not None:
        lines.append(
            "  "
            f"prior_outcome tx={advisory.get('prior_outcome_transaction_no')} "
            f"outcome={advisory.get('prior_outcome')}"
        )
    return lines

def standup_authority_mode_v1(ctx: Any) -> StandUpAuthorityModeV1:
    """Return the active StandUp authority mode with legacy compatibility.

    New contexts use ``ctx.navmap_standup_authority_mode`` and therefore start
    in Phase 3D ``default`` mode. The historical
    ``ctx.navmap_standup_guarded_enabled`` flag remains a temporary compatibility
    override: True selects Phase 3C guarded mode and False selects legacy mode.
    Invalid values fail safely to legacy authority.
    """
    if ctx is None:
        return StandUpAuthorityModeV1.LEGACY

    compatibility_flag = getattr(ctx, "navmap_standup_guarded_enabled", None)
    if isinstance(compatibility_flag, bool):
        return (
            StandUpAuthorityModeV1.GUARDED
            if compatibility_flag
            else StandUpAuthorityModeV1.LEGACY
        )

    raw_mode = getattr(ctx, "navmap_standup_authority_mode", StandUpAuthorityModeV1.DEFAULT.value)
    try:
        return StandUpAuthorityModeV1(str(raw_mode).strip().lower())
    except ValueError:
        return StandUpAuthorityModeV1.LEGACY


class StandUpGuardedAuthoritySourceV1(str, Enum):
    """Trigger-authority source for the bounded Phase 3C/3D StandUp domain."""

    WNM_NAVMAP = "wnm_navmap"
    BODYMAP_FALLBACK = "bodymap_fallback"
    PROTECTED_BODYMAP_SAFETY = "protected_bodymap_safety"


@dataclass(frozen=True, slots=True)
class StandUpGuardedDecisionV1:
    """One bounded StandUp trigger and selection record.

    In guarded mode this record describes the feature-flagged Phase 3C path. In
    default mode it describes the promoted Phase 3D path in which the maintained
    WNM/NavMap is the normal cognitive source. The existing PolicyRuntime and
    controller remain the executor, unsupported maps fall back to legacy logic,
    and fresh BodyMap fallen evidence remains a protected safety override.
    """

    decision_no: int
    transaction_no: Optional[int]
    observation_no: Optional[int]
    controller_step: int
    source_stage: str
    authority_mode: StandUpAuthorityModeV1
    triggered: bool
    authority_source: StandUpGuardedAuthoritySourceV1
    reason: str
    fallback_used: bool
    fallback_reason: Optional[str]
    protected_bodymap_fallen: bool
    legacy_gate_triggered: bool
    legacy_bodymap_posture: Optional[str]
    map_recommendation: Optional[StandUpMapRecommendationV1]
    map_body_interpretation: NavBodyStateInterpretationV1
    map_maintained: bool
    support_status: str
    expected_successor_available: bool
    selected_policy: Optional[str] = None
    selection_result: str = "pending"
    expected_pending_armed: bool = False

    def __post_init__(self) -> None:
        _require_positive_int(self.decision_no, field_name="decision_no")
        if self.transaction_no is not None:
            _require_positive_int(self.transaction_no, field_name="transaction_no")
        if self.observation_no is not None:
            _require_positive_int(self.observation_no, field_name="observation_no")
        _require_non_negative_int(self.controller_step, field_name="controller_step")
        if self.source_stage not in {"gate", "selection"}:
            raise ValueError("source_stage must be 'gate' or 'selection'")
        if self.authority_mode not in {
            StandUpAuthorityModeV1.GUARDED,
            StandUpAuthorityModeV1.DEFAULT,
        }:
            raise ValueError("decision authority_mode must be guarded or default")
        if not isinstance(self.triggered, bool):
            raise TypeError("triggered must be bool")
        if not isinstance(self.authority_source, StandUpGuardedAuthoritySourceV1):
            raise TypeError("authority_source must be StandUpGuardedAuthoritySourceV1")
        _require_nonempty_text(self.reason, field_name="reason")
        if not isinstance(self.fallback_used, bool):
            raise TypeError("fallback_used must be bool")
        if self.fallback_reason is not None and not isinstance(self.fallback_reason, str):
            raise TypeError("fallback_reason must be str or None")
        if not isinstance(self.protected_bodymap_fallen, bool):
            raise TypeError("protected_bodymap_fallen must be bool")
        if not isinstance(self.legacy_gate_triggered, bool):
            raise TypeError("legacy_gate_triggered must be bool")
        if self.legacy_bodymap_posture is not None and not isinstance(self.legacy_bodymap_posture, str):
            raise TypeError("legacy_bodymap_posture must be str or None")
        if self.map_recommendation is not None and not isinstance(
            self.map_recommendation,
            StandUpMapRecommendationV1,
        ):
            raise TypeError("map_recommendation must be StandUpMapRecommendationV1 or None")
        if not isinstance(self.map_body_interpretation, NavBodyStateInterpretationV1):
            raise TypeError("map_body_interpretation must be NavBodyStateInterpretationV1")
        if not isinstance(self.map_maintained, bool):
            raise TypeError("map_maintained must be bool")
        _require_nonempty_text(self.support_status, field_name="support_status")
        if not isinstance(self.expected_successor_available, bool):
            raise TypeError("expected_successor_available must be bool")
        if self.selected_policy is not None and not isinstance(self.selected_policy, str):
            raise TypeError("selected_policy must be str or None")
        _require_nonempty_text(self.selection_result, field_name="selection_result")
        if not isinstance(self.expected_pending_armed, bool):
            raise TypeError("expected_pending_armed must be bool")

        if self.authority_source is StandUpGuardedAuthoritySourceV1.WNM_NAVMAP:
            if self.fallback_used:
                raise ValueError("WNM_NAVMAP authority cannot also be a fallback")
            if not self.map_maintained or self.support_status not in _ACTIONABLE_SUPPORT:
                raise ValueError("WNM_NAVMAP authority requires actionable maintained support")
            if self.map_recommendation not in {
                StandUpMapRecommendationV1.STAND_UP,
                StandUpMapRecommendationV1.DO_NOT_STAND,
            }:
                raise ValueError("WNM_NAVMAP authority requires an actionable recommendation")
        elif not self.fallback_used:
            raise ValueError("non-WNM source must be recorded as fallback/safety use")

        if self.protected_bodymap_fallen:
            if self.authority_source is not StandUpGuardedAuthoritySourceV1.PROTECTED_BODYMAP_SAFETY:
                raise ValueError("protected BodyMap fallen must own the decision")
            if not self.triggered:
                raise ValueError("protected BodyMap fallen must trigger StandUp")

    @property
    def phase(self) -> str:
        """Return the phase label corresponding to the configured authority mode."""
        return "3D" if self.authority_mode is StandUpAuthorityModeV1.DEFAULT else "3C"

    @property
    def authority_level(self) -> str:
        """Return ``default`` or ``guarded`` for trace output."""
        return self.authority_mode.value

    @property
    def authority_label(self) -> str:
        """Return the bounded authority label used in trace output."""
        return (
            "default_standup"
            if self.authority_mode is StandUpAuthorityModeV1.DEFAULT
            else "guarded_standup"
        )

    @property
    def map_authority_used(self) -> bool:
        """Return True when the maintained WNM supplied the trigger result."""
        return self.authority_source is StandUpGuardedAuthoritySourceV1.WNM_NAVMAP

    @property
    def guarded_map_fallen_active(self) -> bool:
        """Compatibility readout: True when active map authority requires StandUp."""
        return (
            self.map_authority_used
            and self.triggered
            and self.map_recommendation is StandUpMapRecommendationV1.STAND_UP
            and self.map_body_interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit Phase 3C/3D trace."""
        default_mode = self.authority_mode is StandUpAuthorityModeV1.DEFAULT
        return {
            "schema": "standup_guarded_decision_v1",
            "phase": self.phase,
            "authority_level": self.authority_level,
            "authority": self.authority_label,
            "authority_mode": self.authority_mode.value,
            "default_authority_active": default_mode,
            "normal_cognitive_source": "wnm_navmap" if default_mode else "feature_flagged_wnm_navmap",
            "bounded_domain": "stand_up_trigger_and_expectation",
            "feature_flag": (
                "ctx.navmap_standup_guarded_enabled"
                if self.authority_mode is StandUpAuthorityModeV1.GUARDED
                else None
            ),
            "feature_flag_enabled": self.authority_mode is StandUpAuthorityModeV1.GUARDED,
            "canonical_mode_field": "ctx.navmap_standup_authority_mode",
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "bodymap_protected_safety_fallback": True,
            "controller_executor": "policy_runtime_action_center",
            "lower_controller_unchanged": True,
            "bodymap_mutation_allowed": False,
            "other_policy_authority_allowed": False,
            "protected_safety_can_be_overridden": False,
            "map_can_override_legacy_trigger": self.map_authority_used,
            "map_can_override_protected_safety": False,
            "decision_no": self.decision_no,
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "controller_step": self.controller_step,
            "source_stage": self.source_stage,
            "triggered": self.triggered,
            "trigger_authority_source": self.authority_source.value,
            "map_authority_used": self.map_authority_used,
            "guarded_map_fallen_active": self.guarded_map_fallen_active,
            "reason": self.reason,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "fallback_source": "bodymap_policy_runtime" if self.fallback_used else None,
            "protected_bodymap_fallen": self.protected_bodymap_fallen,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "legacy_bodymap_posture": self.legacy_bodymap_posture,
            "map_recommendation": (
                self.map_recommendation.value if self.map_recommendation is not None else None
            ),
            "map_body_interpretation": self.map_body_interpretation.value,
            "map_maintained": self.map_maintained,
            "support_status": self.support_status,
            "expected_successor_available": self.expected_successor_available,
            "selected_policy": self.selected_policy,
            "selected_standup": self.selected_policy == _STANDUP_POLICY,
            "selection_result": self.selection_result,
            "expected_pending_armed": self.expected_pending_armed,
        }


def _next_guarded_decision_no(ctx: Any) -> int:
    """Advance and return the deterministic Phase 3C decision counter."""
    try:
        current = int(getattr(ctx, "navmap_standup_guarded_decision_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    decision_no = max(0, current) + 1
    ctx.navmap_standup_guarded_decision_no = decision_no
    return decision_no


def _guarded_controller_step(ctx: Any) -> int:
    """Return a defensive non-negative controller-step number."""
    try:
        return max(0, int(getattr(ctx, "controller_steps", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _store_guarded_decision(ctx: Any, decision: StandUpGuardedDecisionV1) -> dict[str, Any]:
    """Store one ctx-local guarded decision and bounded one-row lifecycle."""
    row = decision.as_dict()
    ctx.navmap_standup_guarded_decision = decision
    ctx.navmap_standup_guarded_last_update = dict(row)

    history = getattr(ctx, "navmap_standup_guarded_history", [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    if clean and clean[-1].get("decision_no") == decision.decision_no:
        clean[-1] = dict(row)
    else:
        clean.append(dict(row))
    limit = _history_limit(ctx, "navmap_standup_guarded_history_limit")
    ctx.navmap_standup_guarded_history = clean[-limit:]
    return standup_guarded_summary_v1(ctx)


def _guarded_transaction(ctx: Any) -> Optional[StandUpCompareTransactionV1]:
    """Return the current compare transaction only while the compare path is enabled."""
    if not bool(getattr(ctx, "navmap_standup_compare_enabled", True)):
        return None
    value = getattr(ctx, "navmap_standup_compare_transaction", None)
    return value if isinstance(value, StandUpCompareTransactionV1) else None


def _guarded_decision_from_current_state(
    ctx: Any,
    *,
    authority_mode: StandUpAuthorityModeV1,
    legacy_gate_triggered: bool,
    protected_bodymap_fallen: bool,
) -> StandUpGuardedDecisionV1:
    """Build one bounded Phase 3C/3D trigger decision from current state."""
    transaction = _guarded_transaction(ctx)
    transaction_no = transaction.transaction_no if transaction is not None else None
    observation_no = transaction.observation_no if transaction is not None else None
    legacy_posture = transaction.legacy_bodymap_posture if transaction is not None else None
    recommendation = transaction.map_recommendation if transaction is not None else None
    interpretation = (
        transaction.map_body_interpretation
        if transaction is not None
        else NavBodyStateInterpretationV1.UNKNOWN
    )
    maintained = transaction.map_maintained if transaction is not None else False
    support_status = transaction.support_status if transaction is not None else "unavailable"
    expected_available = bool(
        transaction is not None and transaction.expected_successor_map is not None
    )

    if protected_bodymap_fallen:
        source = StandUpGuardedAuthoritySourceV1.PROTECTED_BODYMAP_SAFETY
        triggered = True
        reason = "fresh_bodymap_fallen_protected_safety_override"
        fallback_used = True
        fallback_reason = "protected_bodymap_fallen"
    elif (
        transaction is not None #pylint: disable=too-many-boolean-expressions
        and maintained
        and support_status in _ACTIONABLE_SUPPORT
        and recommendation is StandUpMapRecommendationV1.STAND_UP
        and interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE
        and expected_available
    ):
        source = StandUpGuardedAuthoritySourceV1.WNM_NAVMAP
        triggered = True
        reason = "maintained_wnm_geometry_fallen_like"
        fallback_used = False
        fallback_reason = None
    elif (
        transaction is not None
        and maintained
        and support_status in _ACTIONABLE_SUPPORT
        and recommendation is StandUpMapRecommendationV1.DO_NOT_STAND
        and interpretation is NavBodyStateInterpretationV1.STANDING_LIKE
    ):
        source = StandUpGuardedAuthoritySourceV1.WNM_NAVMAP
        triggered = False
        reason = "maintained_wnm_geometry_standing_like"
        fallback_used = False
        fallback_reason = None
    else:
        source = StandUpGuardedAuthoritySourceV1.BODYMAP_FALLBACK
        triggered = bool(legacy_gate_triggered)
        fallback_used = True
        if transaction is None:
            fallback_reason = "compare_transaction_unavailable"
        elif not maintained:
            fallback_reason = "map_not_maintained"
        elif support_status not in _ACTIONABLE_SUPPORT:
            fallback_reason = f"support_{support_status}"
        elif recommendation is StandUpMapRecommendationV1.DEFER:
            fallback_reason = transaction.map_reason
        elif interpretation in {
            NavBodyStateInterpretationV1.UNKNOWN,
            NavBodyStateInterpretationV1.AMBIGUOUS,
        }:
            fallback_reason = f"map_{interpretation.value}"
        elif recommendation is StandUpMapRecommendationV1.STAND_UP and not expected_available:
            fallback_reason = "expected_successor_unavailable"
        else:
            fallback_reason = "map_guard_conditions_not_satisfied"
        reason = f"legacy_bodymap_fallback:{fallback_reason}"

    return StandUpGuardedDecisionV1(
        decision_no=_next_guarded_decision_no(ctx),
        transaction_no=transaction_no,
        observation_no=observation_no,
        controller_step=_guarded_controller_step(ctx),
        source_stage="gate",
        authority_mode=authority_mode,
        triggered=triggered,
        authority_source=source,
        reason=reason,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        protected_bodymap_fallen=bool(protected_bodymap_fallen),
        legacy_gate_triggered=bool(legacy_gate_triggered),
        legacy_bodymap_posture=legacy_posture,
        map_recommendation=recommendation,
        map_body_interpretation=interpretation,
        map_maintained=maintained,
        support_status=support_status,
        expected_successor_available=expected_available,
    )


def standup_guarded_trigger_value_v1(
    ctx: Any,
    *,
    legacy_gate_triggered: bool,
    protected_bodymap_fallen: bool,
) -> bool:
    """Return the active StandUp trigger while storing authority telemetry.

    Legacy mode is an exact pass-through. Explicit guarded mode preserves the
    Phase 3C experiment. Promoted default mode makes actionable maintained WNM
    geometry the normal cognitive source. Unsupported map content falls back to
    the supplied legacy result and fresh BodyMap fallen remains protected.
    """
    legacy_value = bool(legacy_gate_triggered)
    authority_mode = standup_authority_mode_v1(ctx)
    if authority_mode is StandUpAuthorityModeV1.LEGACY:
        return legacy_value

    decision = _guarded_decision_from_current_state(
        ctx,
        authority_mode=authority_mode,
        legacy_gate_triggered=legacy_value,
        protected_bodymap_fallen=bool(protected_bodymap_fallen),
    )
    _store_guarded_decision(ctx, decision)
    return decision.triggered


def standup_guarded_safety_active_v1(ctx: Any) -> bool:
    """Return True when guarded WNM authority currently requires StandUp."""
    if standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.LEGACY:
        return False
    decision = getattr(ctx, "navmap_standup_guarded_decision", None)
    return bool(
        isinstance(decision, StandUpGuardedDecisionV1)
        and decision.source_stage == "gate"
        and decision.guarded_map_fallen_active
    )


def standup_guarded_explain_v1(ctx: Any) -> str:
    """Return one concise gate explanation without recomputing the decision."""
    authority_mode = standup_authority_mode_v1(ctx)
    if authority_mode is StandUpAuthorityModeV1.LEGACY:
        return "standup_authority=legacy source=legacy_bodymap_policy_runtime"
    decision = getattr(ctx, "navmap_standup_guarded_decision", None)
    phase_label = "phase3d_default" if authority_mode is StandUpAuthorityModeV1.DEFAULT else "phase3c_guarded"
    if not isinstance(decision, StandUpGuardedDecisionV1):
        return f"{phase_label}=on source=bodymap_fallback reason=decision_unavailable"
    return (
        f"{phase_label}=on "
        f"source={decision.authority_source.value} trigger={decision.triggered} "
        f"map={decision.map_body_interpretation.value}/{decision.support_status} "
        f"legacy={decision.legacy_gate_triggered} fallback={decision.fallback_used}"
    )


def _guarded_selection_result(
    decision: StandUpGuardedDecisionV1,
    selected_policy: Optional[str],
) -> str:
    """Return a deterministic selection label for guarded or default authority."""
    selected_standup = selected_policy == _STANDUP_POLICY
    if decision.authority_source is StandUpGuardedAuthoritySourceV1.WNM_NAVMAP:
        prefix = (
            "default"
            if decision.authority_mode is StandUpAuthorityModeV1.DEFAULT
            else "guarded"
        )
        if decision.triggered:
            return f"{prefix}_standup_selected" if selected_standup else f"{prefix}_standup_not_selected"
        return (
            f"{prefix}_do_not_stand_overridden"
            if selected_standup
            else f"{prefix}_do_not_stand_respected"
        )
    if decision.authority_source is StandUpGuardedAuthoritySourceV1.PROTECTED_BODYMAP_SAFETY:
        return "protected_safety_standup_selected" if selected_standup else "protected_safety_standup_not_selected"
    return "fallback_standup_selected" if selected_standup else "fallback_non_standup_selected"


def standup_guarded_selection_step_v1(
    ctx: Any,
    *,
    selected_policy: Optional[str],
) -> dict[str, Any]:
    """Finalize the current Phase 3C/3D record after policy selection.

    This function only observes the already-completed selection. It does not
    change the selected behavioral primitive, action, BodyMap, or safety path.
    """
    if ctx is None:
        return {
            "schema": "standup_guarded_summary_v1",
            "phase": "3D",
            "status": "ctx_unavailable",
            "authority": "default_standup",
        }
    if standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.LEGACY:
        return standup_guarded_summary_v1(ctx)

    decision = getattr(ctx, "navmap_standup_guarded_decision", None)
    if not isinstance(decision, StandUpGuardedDecisionV1):
        return standup_guarded_summary_v1(ctx)

    policy_value = selected_policy if isinstance(selected_policy, str) and selected_policy else None
    pending = getattr(ctx, "navmap_standup_compare_pending", None)
    expected_armed = bool(
        isinstance(pending, StandUpExpectedPendingV1)
        and decision.transaction_no is not None
        and pending.transaction_no == decision.transaction_no
        and policy_value == _STANDUP_POLICY
    )
    updated = replace(
        decision,
        source_stage="selection",
        selected_policy=policy_value,
        selection_result=_guarded_selection_result(decision, policy_value),
        expected_pending_armed=expected_armed,
    )
    return _store_guarded_decision(ctx, updated)


def standup_guarded_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe Phase 3C/3D authority summary."""
    if ctx is None:
        return {
            "schema": "standup_guarded_summary_v1",
            "phase": "3D",
            "status": "ctx_unavailable",
        }

    history_count = len(getattr(ctx, "navmap_standup_guarded_history", []) or [])
    mode = standup_authority_mode_v1(ctx)
    if mode is StandUpAuthorityModeV1.LEGACY:
        compatibility = getattr(ctx, "navmap_standup_guarded_enabled", None)
        return {
            "schema": "standup_guarded_summary_v1",
            "phase": "3D",
            "status": "disabled" if compatibility is False else "legacy_override",
            "authority": "legacy_bodymap_policy_runtime",
            "authority_level": "legacy",
            "authority_mode": "legacy",
            "default_authority_active": False,
            "feature_flag_enabled": False,
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "history_count": history_count,
        }

    phase = "3D" if mode is StandUpAuthorityModeV1.DEFAULT else "3C"
    authority = "default_standup" if mode is StandUpAuthorityModeV1.DEFAULT else "guarded_standup"
    row = getattr(ctx, "navmap_standup_guarded_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "standup_guarded_summary_v1",
            "phase": phase,
            "status": "idle",
            "authority": authority,
            "authority_level": mode.value,
            "authority_mode": mode.value,
            "default_authority_active": mode is StandUpAuthorityModeV1.DEFAULT,
            "feature_flag_enabled": mode is StandUpAuthorityModeV1.GUARDED,
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "history_count": history_count,
        }
    if row.get("status") == "error":
        out = dict(row)
        out["history_count"] = history_count
        return out

    source = row.get("trigger_authority_source")
    if source == StandUpGuardedAuthoritySourceV1.WNM_NAVMAP.value:
        status = (
            "default_map_authority"
            if mode is StandUpAuthorityModeV1.DEFAULT
            else "guarded_map_authority"
        )
    elif source == StandUpGuardedAuthoritySourceV1.PROTECTED_BODYMAP_SAFETY.value:
        status = "protected_safety_fallback"
    else:
        status = "bodymap_fallback"
    return {
        "schema": "standup_guarded_summary_v1",
        "phase": phase,
        "status": status,
        "authority": authority,
        "authority_level": mode.value,
        "authority_mode": mode.value,
        "default_authority_active": mode is StandUpAuthorityModeV1.DEFAULT,
        "feature_flag_enabled": mode is StandUpAuthorityModeV1.GUARDED,
        "legacy_debug_mode_available": True,
        "legacy_retired": False,
        "decision": dict(row),
        "history_count": history_count,
    }


def standup_authority_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return the canonical Phase 3C/3D StandUp authority summary.

    The historical guarded-summary function preserves its Phase 3C schema and
    disabled-status compatibility. This wrapper provides the mode-neutral Phase
    3D public contract used by new traces and tests while retaining the complete
    guarded/default decision payload.
    """
    summary = dict(standup_guarded_summary_v1(ctx))
    mode = standup_authority_mode_v1(ctx)
    summary["schema"] = "standup_authority_summary_v1"
    summary["authority_mode"] = mode.value
    summary["legacy_debug_mode_available"] = True
    summary["legacy_retired"] = False
    summary["bodymap_protected_safety_fallback"] = True

    if mode is StandUpAuthorityModeV1.LEGACY:
        summary["status"] = "legacy_mode"
        summary["normal_cognitive_source"] = "legacy_bodymap_policy_runtime"
        summary["default_authority_active"] = False
        return summary

    summary["normal_cognitive_source"] = (
        "wnm_navmap"
        if mode is StandUpAuthorityModeV1.DEFAULT
        else "feature_flagged_wnm_navmap"
    )
    summary["default_authority_active"] = mode is StandUpAuthorityModeV1.DEFAULT
    return summary


def render_standup_authority_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 3C/3D authority lines."""
    summary = standup_authority_summary_v1(ctx)
    phase = summary.get("phase") or "3D"
    mode = summary.get("authority_mode") or "legacy"
    if phase == "3D" and mode == "default":
        title = "STANDUP PHASE 3D DEFAULT AUTHORITY:"
    elif mode == "guarded":
        title = "STANDUP PHASE 3C GUARDED AUTHORITY:"
    else:
        title = "STANDUP AUTHORITY LEGACY MODE:"
    lines = [title]
    status = summary.get("status")
    if status in {"ctx_unavailable", "disabled", "legacy_mode", "idle", "error"}:
        lines.append(
            "  "
            f"status={status} mode={mode} feature_flag={summary.get('feature_flag_enabled')} "
            f"authority={summary.get('authority')} "
            f"normal_cognitive_source={summary.get('normal_cognitive_source')} "
            f"legacy_retired={summary.get('legacy_retired')}"
        )
        if status == "error":
            lines.append(
                "  "
                f"error_type={summary.get('error_type')} error={summary.get('error')}"
            )
        return lines

    decision = summary.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    lines.append(
        "  "
        f"decision={decision.get('decision_no')} tx={decision.get('transaction_no')} "
        f"status={status} authority={decision.get('authority')} "
        f"mode={decision.get('authority_mode')} bounded_domain=stand_up"
    )
    lines.append(
        "  "
        f"mode={summary.get('authority_mode')} "
        f"normal_cognitive_source={summary.get('normal_cognitive_source')} "
        f"legacy_retired={summary.get('legacy_retired')}"
    )
    lines.append(
        "  "
        f"source={decision.get('trigger_authority_source')} trigger={decision.get('triggered')} "
        f"reason={decision.get('reason')}"
    )
    lines.append(
        "  "
        f"map derived={decision.get('map_body_interpretation')} "
        f"support={decision.get('support_status')} "
        f"maintained={decision.get('map_maintained')} "
        f"recommendation={decision.get('map_recommendation')} "
        f"expected_available={decision.get('expected_successor_available')}"
    )
    lines.append(
        "  "
        f"legacy posture={decision.get('legacy_bodymap_posture')} "
        f"legacy_gate={decision.get('legacy_gate_triggered')} "
        f"protected_bodymap_fallen={decision.get('protected_bodymap_fallen')}"
    )
    lines.append(
        "  "
        f"fallback_used={decision.get('fallback_used')} "
        f"fallback_reason={decision.get('fallback_reason')} "
        "protected_safety_can_be_overridden=False legacy_retired=False"
    )
    lines.append(
        "  "
        f"selected={decision.get('selected_policy')} "
        f"selection_result={decision.get('selection_result')} "
        f"expected_pending_armed={decision.get('expected_pending_armed')}"
    )
    return lines


def render_standup_guarded_lines_v1(ctx: Any) -> list[str]:
    """Compatibility wrapper for the canonical authority renderer."""
    return render_standup_authority_lines_v1(ctx)
