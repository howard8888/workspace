# -*- coding: utf-8 -*-
"""Phase 4F default FollowMom NavMap authority for CCA8.

Purpose
-------
Phase 4D created an independent map-native FollowMom transaction and compact
expected successor. Phase 4E-A converted that transaction into explicit start,
continuation, defer, and review advice. This module promotes the validated
maternal path into one bounded FollowMom authority domain while retaining the
legacy gate as a protected veto, compatibility path, fallback, and debug mode.

The canonical mode for new contexts is ``default``. The same implementation
also preserves explicit ``guarded`` and ``legacy`` modes so the migration ladder
remains inspectable and reversible:

``legacy``
    The complete historical BodyMap/PolicyRuntime FollowMom gate passes through.

``guarded``
    Current-exact identity-supported maternal evidence may control the FollowMom
    gate behind explicit guards; otherwise the complete legacy result is used.

``default``
    The same guarded map decision becomes the normal cognitive source for the
    bounded FollowMom applicability domain. Unsupported, ambiguous, stale, or
    outcome-review states still fall back to the historical gate.

Safety and compatibility boundary
---------------------------------
The map path is intentionally unable to add FollowMom against any current
legacy veto. This preserves posture/fall protection, post-latch sequence locks,
route/topology safety, benchmark-specific compatibility gates, and sparse-state
fallback discipline. A small number of explicit legacy compatibility forces
remain authoritative until their consumers migrate. Within an ordinary
legacy-permissive FollowMom opportunity, the map path may authorize or suppress
the candidate.

Authority is currently restricted to exact current localization with supported
maternal identity, retained role, observed evidence, and an active track.
Phase 4D predicted-region/occlusion reasoning remains available for comparison
and advisory traces but is not authoritative in this first default slice.

Start versus continuation
-------------------------
A current ``far + approaching`` relation does not identify whether Mom moved
toward SELF or SELF moved toward Mom. Initial recruitment is therefore
suppressed unless the immediately preceding applied FollowMom expectation
succeeded. In that narrow continuation case, this module constructs a fresh
compact expected successor from the current exact relation and arms it only if
PolicyRuntime actually selects FollowMom. Motor issuance never counts as
success; the next observation still determines success, failure, or uncertainty.

The module changes only the FollowMom gate value supplied to PolicyRuntime and
records bounded telemetry. It does not mutate BodyMap, maternal NavMaps,
WorldGraph truth, drives, lower motor execution, other policy gates, global
single-winner arbitration, or environment dynamics.
"""

from __future__ import annotations

# The public authority decision intentionally carries the complete source,
# fallback, safety, and expected-successor contract.
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments
# pylint: disable=too-many-boolean-expressions
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Optional

from cca8_followmom_advisory import (
    FollowMomAdvisoryKindV1,
    FollowMomAdvisoryScopeV1,
    FollowMomAdvisoryV1,
)
from cca8_followmom_compare import (
    FollowMomCompareTransactionV1,
    FollowMomExpectedPendingV1,
    FollowMomExpectedSuccessorV1,
    FollowMomExpectationKindV1,
    FollowMomMapRecommendationV1,
    FollowMomObservedOutcomeV1,
)
from cca8_maternal_continuity import (
    MaternalContinuityShadowStateV1,
    MaternalIdentitySupportV1,
    MaternalLocalizationStatusV1,
    MaternalObservabilityV1,
    MaternalTrackStatusV1,
)
from cca8_maternal_geometry import MaternalProximityV1
from cca8_maternal_temporal import MaternalTemporalTrendV1
from cca8_navmap_kernel import NavProvenanceV1, NavSourceClassV1

__version__ = "0.1.0"

__all__ = [
    "FollowMomAuthorityModeV1",
    "FollowMomAuthoritySourceV1",
    "FollowMomAuthorityDecisionV1",
    "followmom_authority_mode_v1",
    "followmom_authority_trigger_value_v1",
    "followmom_authority_legacy_bridge_allowed_v1",
    "followmom_authority_selection_step_v1",
    "followmom_authority_summary_v1",
    "followmom_authority_explain_v1",
    "render_followmom_authority_lines_v1",
    "__version__",
]

_FOLLOW_MOM_POLICY = "policy:follow_mom"
_FAR_APPROACHING_REASON = "far_but_separation_already_approaching"
_DEFAULT_HISTORY_LIMIT = 25
_AUTHORITY_EXPECTED_SOURCE_PREFIX = "behavioral_primitive:follow_mom:phase4f_authority"


class FollowMomAuthorityModeV1(str, Enum):
    """Supported FollowMom authority modes during and after migration."""

    LEGACY = "legacy"
    GUARDED = "guarded"
    DEFAULT = "default"


class FollowMomAuthoritySourceV1(str, Enum):
    """Source that supplied one bounded FollowMom gate value."""

    WNM_NAVMAP = "wnm_navmap"
    LEGACY_FALLBACK = "legacy_fallback"
    PROTECTED_LEGACY_VETO = "protected_legacy_veto"
    LEGACY_COMPATIBILITY = "legacy_compatibility"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class FollowMomAuthorityDecisionV1:
    """One guarded/default FollowMom gate and selection lifecycle.

    A gate-stage decision may use current WNM/NavMap evidence or one explicit
    legacy route. Selection finalization records the actual controller winner
    and arms a compact expected successor only when FollowMom was selected.
    """

    decision_no: int
    transaction_no: Optional[int]
    observation_no: Optional[int]
    controller_step: int
    source_stage: str
    authority_mode: FollowMomAuthorityModeV1
    triggered: bool
    authority_source: FollowMomAuthoritySourceV1
    reason: str
    fallback_used: bool
    fallback_reason: Optional[str]
    legacy_gate_triggered: bool
    legacy_gate_reason: str
    protected_legacy_veto: bool
    legacy_compatibility_force: bool
    map_recommendation: Optional[FollowMomMapRecommendationV1]
    map_reason: Optional[str]
    advisory_kind: Optional[FollowMomAdvisoryKindV1]
    advisory_scope: Optional[FollowMomAdvisoryScopeV1]
    source_mode: str
    identity_support: MaternalIdentitySupportV1
    role_retained: bool
    observability: MaternalObservabilityV1
    localization_status: MaternalLocalizationStatusV1
    track_status: MaternalTrackStatusV1
    proximity: MaternalProximityV1
    temporal_trend: MaternalTemporalTrendV1
    temporal_valid: bool
    temporal_support_status: str
    reliable_negative_evidence: bool
    expected_successor: Optional[FollowMomExpectedSuccessorV1]
    prior_outcome_transaction_no: Optional[int]
    prior_outcome: Optional[str]
    prior_action_applied: Optional[str]
    active_effective_candidate: Optional[bool] = None
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
            FollowMomAuthorityModeV1.GUARDED,
            FollowMomAuthorityModeV1.DEFAULT,
        }:
            raise ValueError("decision authority_mode must be guarded or default")
        if not isinstance(self.triggered, bool):
            raise TypeError("triggered must be bool")
        if not isinstance(self.authority_source, FollowMomAuthoritySourceV1):
            raise TypeError("authority_source must be FollowMomAuthoritySourceV1")
        _require_nonempty_text(self.reason, field_name="reason")
        if not isinstance(self.fallback_used, bool):
            raise TypeError("fallback_used must be bool")
        if self.fallback_reason is not None:
            _require_nonempty_text(self.fallback_reason, field_name="fallback_reason")
        if not isinstance(self.legacy_gate_triggered, bool):
            raise TypeError("legacy_gate_triggered must be bool")
        _require_nonempty_text(self.legacy_gate_reason, field_name="legacy_gate_reason")
        for field_name in (
            "protected_legacy_veto",
            "legacy_compatibility_force",
            "role_retained",
            "temporal_valid",
            "reliable_negative_evidence",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if self.map_recommendation is not None and not isinstance(
            self.map_recommendation,
            FollowMomMapRecommendationV1,
        ):
            raise TypeError("map_recommendation must be FollowMomMapRecommendationV1 or None")
        if self.map_reason is not None:
            _require_nonempty_text(self.map_reason, field_name="map_reason")
        if self.advisory_kind is not None and not isinstance(self.advisory_kind, FollowMomAdvisoryKindV1):
            raise TypeError("advisory_kind must be FollowMomAdvisoryKindV1 or None")
        if self.advisory_scope is not None and not isinstance(self.advisory_scope, FollowMomAdvisoryScopeV1):
            raise TypeError("advisory_scope must be FollowMomAdvisoryScopeV1 or None")
        _require_nonempty_text(self.source_mode, field_name="source_mode")
        if not isinstance(self.identity_support, MaternalIdentitySupportV1):
            raise TypeError("identity_support must be MaternalIdentitySupportV1")
        if not isinstance(self.observability, MaternalObservabilityV1):
            raise TypeError("observability must be MaternalObservabilityV1")
        if not isinstance(self.localization_status, MaternalLocalizationStatusV1):
            raise TypeError("localization_status must be MaternalLocalizationStatusV1")
        if not isinstance(self.track_status, MaternalTrackStatusV1):
            raise TypeError("track_status must be MaternalTrackStatusV1")
        if not isinstance(self.proximity, MaternalProximityV1):
            raise TypeError("proximity must be MaternalProximityV1")
        if not isinstance(self.temporal_trend, MaternalTemporalTrendV1):
            raise TypeError("temporal_trend must be MaternalTemporalTrendV1")
        _require_nonempty_text(self.temporal_support_status, field_name="temporal_support_status")
        if self.expected_successor is not None and not isinstance(
            self.expected_successor,
            FollowMomExpectedSuccessorV1,
        ):
            raise TypeError("expected_successor must be FollowMomExpectedSuccessorV1 or None")
        if self.prior_outcome_transaction_no is not None:
            _require_positive_int(self.prior_outcome_transaction_no, field_name="prior_outcome_transaction_no")
        if self.active_effective_candidate is not None and not isinstance(self.active_effective_candidate, bool):
            raise TypeError("active_effective_candidate must be bool or None")
        for field_name in ("prior_outcome", "prior_action_applied", "selected_policy"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field_name} must be str or None")
        _require_nonempty_text(self.selection_result, field_name="selection_result")
        if not isinstance(self.expected_pending_armed, bool):
            raise TypeError("expected_pending_armed must be bool")

        if self.protected_legacy_veto and self.legacy_compatibility_force:
            raise ValueError("protected veto and compatibility force cannot both be active")

        if self.authority_source is FollowMomAuthoritySourceV1.WNM_NAVMAP:
            if self.fallback_used:
                raise ValueError("WNM_NAVMAP authority cannot also be fallback")
            if self.protected_legacy_veto or self.legacy_compatibility_force:
                raise ValueError("WNM_NAVMAP authority cannot override a protected legacy route")
            if not self.legacy_gate_triggered:
                raise ValueError("current Phase 4F map authority cannot add against a legacy veto")
            if not self._current_exact_guards_pass:
                raise ValueError("WNM_NAVMAP authority requires exact current identity-supported localization")
            if self.advisory_kind not in {
                FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED,
                FollowMomAdvisoryKindV1.DO_NOT_RECRUIT,
                FollowMomAdvisoryKindV1.CONTINUE_SUPPORTED,
            }:
                raise ValueError("WNM_NAVMAP authority requires one actionable advisory kind")
            if self.triggered and self.expected_successor is None:
                raise ValueError("authoritative FollowMom trigger requires an expected successor")
            if not self.triggered and self.expected_successor is not None:
                raise ValueError("authoritative do-not-follow cannot carry an expected successor")
        elif self.authority_source is FollowMomAuthoritySourceV1.PROTECTED_LEGACY_VETO:
            if not self.protected_legacy_veto or self.legacy_gate_triggered or self.triggered:
                raise ValueError("protected legacy veto must preserve a false legacy gate")
            if not self.fallback_used:
                raise ValueError("protected legacy veto must be recorded as fallback/protection")
        elif self.authority_source is FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY:
            if not self.legacy_compatibility_force or not self.legacy_gate_triggered or not self.triggered:
                raise ValueError("legacy compatibility source requires a true compatibility force")
            if not self.fallback_used:
                raise ValueError("legacy compatibility source must be recorded as fallback/compatibility")
        elif not self.fallback_used:
            raise ValueError("legacy fallback source requires fallback_used")

    @property
    def phase(self) -> str:
        """Return the phase corresponding to guarded or default mode."""
        return "4F" if self.authority_mode is FollowMomAuthorityModeV1.DEFAULT else "4E-B"

    @property
    def authority_label(self) -> str:
        """Return the bounded authority label used in traces."""
        return "default_followmom" if self.authority_mode is FollowMomAuthorityModeV1.DEFAULT else "guarded_followmom"

    @property
    def map_authority_used(self) -> bool:
        """Return True when current WNM/NavMap evidence supplied the gate."""
        return self.authority_source is FollowMomAuthoritySourceV1.WNM_NAVMAP

    @property
    def map_suppressed_legacy_candidate(self) -> bool:
        """Return True when the map suppressed an otherwise permissive legacy candidate."""
        return self.map_authority_used and self.legacy_gate_triggered and not self.triggered

    @property
    def map_authorized_followmom(self) -> bool:
        """Return True when the map supplied an affirmative FollowMom gate."""
        return self.map_authority_used and self.triggered

    @property
    def _current_exact_guards_pass(self) -> bool:
        """Return True for the deliberately narrow first authoritative evidence class."""
        return bool(
            self.source_mode == "current_exact"
            and self.identity_support is MaternalIdentitySupportV1.SUPPORTED
            and self.role_retained
            and self.observability is MaternalObservabilityV1.OBSERVED
            and self.localization_status is MaternalLocalizationStatusV1.CURRENT_EXACT
            and self.track_status is MaternalTrackStatusV1.ACTIVE
            and not self.reliable_negative_evidence
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority, fallback, and outcome contract."""
        default_mode = self.authority_mode is FollowMomAuthorityModeV1.DEFAULT
        return {
            "schema": "followmom_authority_decision_v1",
            "phase": self.phase,
            "authority_level": self.authority_mode.value,
            "authority": self.authority_label,
            "authority_mode": self.authority_mode.value,
            "default_authority_active": default_mode,
            "normal_cognitive_source": "wnm_navmap" if default_mode else "feature_flagged_wnm_navmap",
            "bounded_domain": "follow_mom_applicability_and_expected_relation",
            "canonical_mode_field": "ctx.navmap_followmom_authority_mode",
            "compatibility_flag": (
                "ctx.navmap_followmom_guarded_enabled"
                if self.authority_mode is FollowMomAuthorityModeV1.GUARDED
                else None
            ),
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "legacy_fallback_available": True,
            "current_exact_authority_only": True,
            "predicted_region_authority_allowed": False,
            "controller_executor": "policy_runtime_action_center",
            "lower_controller_unchanged": True,
            "global_single_winner_unchanged": True,
            "bodymap_mutation_allowed": False,
            "navmap_revision_allowed": False,
            "other_policy_authority_allowed": False,
            "protected_safety_can_be_overridden": False,
            "map_can_supply_followmom_gate": self.map_authority_used,
            "map_can_add_against_legacy_veto": False,
            "map_can_suppress_legacy_candidate": self.map_authority_used,
            "decision_no": self.decision_no,
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "controller_step": self.controller_step,
            "source_stage": self.source_stage,
            "triggered": self.triggered,
            "trigger_authority_source": self.authority_source.value,
            "map_authority_used": self.map_authority_used,
            "map_authorized_followmom": self.map_authorized_followmom,
            "map_suppressed_legacy_candidate": self.map_suppressed_legacy_candidate,
            "reason": self.reason,
            "fallback_used": self.fallback_used,
            "fallback_reason": self.fallback_reason,
            "fallback_source": "legacy_bodymap_policy_runtime" if self.fallback_used else None,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "legacy_gate_reason": self.legacy_gate_reason,
            "protected_legacy_veto": self.protected_legacy_veto,
            "legacy_compatibility_force": self.legacy_compatibility_force,
            "map_recommendation": self.map_recommendation.value if self.map_recommendation is not None else None,
            "map_reason": self.map_reason,
            "advisory_kind": self.advisory_kind.value if self.advisory_kind is not None else None,
            "advisory_scope": self.advisory_scope.value if self.advisory_scope is not None else None,
            "source_mode": self.source_mode,
            "identity_support": self.identity_support.value,
            "role_retained": self.role_retained,
            "observability": self.observability.value,
            "localization_status": self.localization_status.value,
            "track_status": self.track_status.value,
            "proximity": self.proximity.value,
            "temporal_trend": self.temporal_trend.value,
            "temporal_valid": self.temporal_valid,
            "temporal_support_status": self.temporal_support_status,
            "reliable_negative_evidence": self.reliable_negative_evidence,
            "expected_successor": self.expected_successor.as_dict() if self.expected_successor is not None else None,
            "prior_outcome_transaction_no": self.prior_outcome_transaction_no,
            "prior_outcome": self.prior_outcome,
            "prior_action_applied": self.prior_action_applied,
            "active_effective_candidate": self.active_effective_candidate,
            "selected_policy": self.selected_policy,
            "selected_followmom": self.selected_policy == _FOLLOW_MOM_POLICY,
            "selection_result": self.selection_result,
            "expected_pending_armed": self.expected_pending_armed,
        }


def followmom_authority_mode_v1(ctx: Any) -> FollowMomAuthorityModeV1:
    """Return the active FollowMom authority mode with compatibility handling.

    ``ctx.navmap_followmom_guarded_enabled`` is a temporary compatibility
    override. ``True`` selects guarded mode, ``False`` selects legacy mode, and
    ``None`` uses the canonical ``ctx.navmap_followmom_authority_mode`` value.
    Invalid values fail safely to legacy authority.
    """
    if ctx is None:
        return FollowMomAuthorityModeV1.LEGACY

    compatibility_flag = getattr(ctx, "navmap_followmom_guarded_enabled", None)
    if isinstance(compatibility_flag, bool):
        return FollowMomAuthorityModeV1.GUARDED if compatibility_flag else FollowMomAuthorityModeV1.LEGACY

    raw_mode = getattr(ctx, "navmap_followmom_authority_mode", FollowMomAuthorityModeV1.DEFAULT.value)
    try:
        return FollowMomAuthorityModeV1(str(raw_mode).strip().lower())
    except ValueError:
        return FollowMomAuthorityModeV1.LEGACY


def _next_decision_no(ctx: Any) -> int:
    """Advance and return the deterministic authority-decision counter."""
    try:
        current = int(getattr(ctx, "navmap_followmom_authority_decision_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    decision_no = max(0, current) + 1
    ctx.navmap_followmom_authority_decision_no = decision_no
    return decision_no


def _controller_step(ctx: Any) -> int:
    """Return a defensive non-negative controller-step value."""
    try:
        return max(0, int(getattr(ctx, "controller_steps", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _history_limit(ctx: Any) -> int:
    """Return the configured positive bounded authority-history size."""
    try:
        value = int(getattr(ctx, "navmap_followmom_authority_history_limit", _DEFAULT_HISTORY_LIMIT) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _store_decision(ctx: Any, decision: FollowMomAuthorityDecisionV1) -> dict[str, Any]:
    """Store one ctx-local authority decision and one bounded lifecycle row."""
    row = decision.as_dict()
    ctx.navmap_followmom_authority_decision = decision
    ctx.navmap_followmom_authority_last_update = dict(row)

    history = getattr(ctx, "navmap_followmom_authority_history", [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    if clean and clean[-1].get("decision_no") == decision.decision_no:
        clean[-1] = dict(row)
    else:
        clean.append(dict(row))
    ctx.navmap_followmom_authority_history = clean[-_history_limit(ctx):]
    return followmom_authority_summary_v1(ctx)


def _current_transaction(ctx: Any) -> Optional[FollowMomCompareTransactionV1]:
    """Return the current Phase 4D transaction when its path is enabled."""
    if not bool(getattr(ctx, "navmap_followmom_compare_enabled", True)):
        return None
    value = getattr(ctx, "navmap_followmom_compare_transaction", None)
    return value if isinstance(value, FollowMomCompareTransactionV1) else None


def _current_advisory(
    ctx: Any,
    transaction: Optional[FollowMomCompareTransactionV1],
) -> Optional[FollowMomAdvisoryV1]:
    """Return current matching Phase 4E advice or ``None`` when unavailable."""
    if transaction is None or not bool(getattr(ctx, "navmap_followmom_advisory_enabled", True)):
        return None
    advisory = getattr(ctx, "navmap_followmom_advisory", None)
    if not isinstance(advisory, FollowMomAdvisoryV1):
        return None
    if advisory.transaction_no != transaction.transaction_no:
        return None
    if advisory.observation_no != transaction.observation_no:
        return None
    return advisory


def _prior_outcome(
    ctx: Any,
    transaction: Optional[FollowMomCompareTransactionV1],
) -> Optional[FollowMomObservedOutcomeV1]:
    """Return only the immediately preceding expected-versus-observed outcome."""
    if transaction is None:
        return None
    outcome = getattr(ctx, "navmap_followmom_compare_last_outcome", None)
    if not isinstance(outcome, FollowMomObservedOutcomeV1):
        return None
    if outcome.transaction_no != transaction.transaction_no - 1:
        return None
    return outcome


def _reliable_negative_evidence(
    ctx: Any,
    transaction: Optional[FollowMomCompareTransactionV1],
) -> bool:
    """Return current reliable maternal negative evidence for this transaction.

    Phase 4D normally converts reliable negative evidence into a non-exact or
    deferred map input before authority runs. The explicit check is retained so
    the Phase 4F guard and trace remain correct even if a future adapter exposes
    an otherwise exact-looking relation beside reliable contradictory evidence.
    """
    if transaction is None:
        return False
    state = getattr(ctx, "navmap_maternal_continuity_state", None)
    return bool(
        isinstance(state, MaternalContinuityShadowStateV1)
        and state.observation_no == transaction.observation_no
        and state.negative_evidence_reliable
    )


def _current_exact_guard_failure(
    ctx: Any,
    transaction: Optional[FollowMomCompareTransactionV1],
) -> Optional[str]:
    """Return why the first authoritative evidence guard does not pass."""
    if transaction is None:
        return "compare_transaction_unavailable"
    if transaction.source_mode != "current_exact":
        return f"source_mode_{transaction.source_mode}_not_authoritative"
    if transaction.identity_support is not MaternalIdentitySupportV1.SUPPORTED:
        return f"identity_{transaction.identity_support.value}"
    if not transaction.role_retained:
        return "maternal_role_not_retained"
    if transaction.observability is not MaternalObservabilityV1.OBSERVED:
        return f"observability_{transaction.observability.value}"
    if transaction.localization_status is not MaternalLocalizationStatusV1.CURRENT_EXACT:
        return f"localization_{transaction.localization_status.value}"
    if transaction.track_status is not MaternalTrackStatusV1.ACTIVE:
        return f"track_{transaction.track_status.value}"
    if _reliable_negative_evidence(ctx, transaction):
        return "reliable_negative_evidence"
    if transaction.distance is None:
        return "current_distance_unavailable"
    return None


def _advisory_guard_failure(
    transaction: FollowMomCompareTransactionV1,
    advisory: Optional[FollowMomAdvisoryV1],
) -> Optional[str]:
    """Return why current advisory evidence is not authority-actionable."""
    if advisory is None:
        return "matching_advisory_unavailable"
    if advisory.kind not in {
        FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED,
        FollowMomAdvisoryKindV1.DO_NOT_RECRUIT,
        FollowMomAdvisoryKindV1.CONTINUE_SUPPORTED,
    }:
        return f"advisory_{advisory.kind.value}_requires_legacy_fallback"
    if advisory.kind is FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED:
        if transaction.map_recommendation is not FollowMomMapRecommendationV1.FOLLOW_MOM:
            return "follow_supported_without_follow_recommendation"
        if transaction.expected_successor is None:
            return "follow_supported_expected_successor_unavailable"
        if transaction.map_reason == "near_but_separation_receding":
            if not transaction.temporal_valid or transaction.temporal_trend is not MaternalTemporalTrendV1.RECEDING:
                return "near_receding_follow_requires_supported_receding_trend"
        return None
    if advisory.kind is FollowMomAdvisoryKindV1.CONTINUE_SUPPORTED:
        if transaction.map_recommendation is not FollowMomMapRecommendationV1.DO_NOT_FOLLOW:
            return "continuation_requires_do_not_follow_start_recommendation"
        if transaction.map_reason != _FAR_APPROACHING_REASON:
            return "continuation_requires_far_approaching_relation"
        if not transaction.temporal_valid or transaction.temporal_trend is not MaternalTemporalTrendV1.APPROACHING:
            return "continuation_requires_supported_approaching_trend"
        if advisory.prior_outcome != "success" or advisory.prior_action_applied != _FOLLOW_MOM_POLICY:
            return "continuation_requires_immediately_prior_followmom_success"
        return None
    if transaction.map_recommendation is not FollowMomMapRecommendationV1.DO_NOT_FOLLOW:
        return "do_not_recruit_without_do_not_follow_recommendation"
    if transaction.map_reason == _FAR_APPROACHING_REASON:
        if not transaction.temporal_valid or transaction.temporal_trend is not MaternalTemporalTrendV1.APPROACHING:
            return "far_approaching_suppression_requires_supported_approaching_trend"
    return None


def _continuation_expected_successor(
    transaction: FollowMomCompareTransactionV1,
    prior_outcome: Optional[FollowMomObservedOutcomeV1],
) -> Optional[FollowMomExpectedSuccessorV1]:
    """Build a fresh compact expectation for one supported continuation step.

    The immediately preceding successful outcome supplies stable frame, units,
    near threshold, and explicit residual thresholds. Current exact transaction
    evidence supplies the new source map, identity, distance, proximity, and
    temporal relation. No complete future NavMap is created.
    """
    if prior_outcome is None or prior_outcome.outcome != "success":
        return None
    if prior_outcome.action_applied != _FOLLOW_MOM_POLICY or transaction.distance is None:
        return None
    previous = prior_outcome.expected_successor
    if previous.tracked_identity_handle != transaction.tracked_identity_handle:
        return None
    provenance = NavProvenanceV1(
        source_class=NavSourceClassV1.EXPECTED,
        source_ref=f"{_AUTHORITY_EXPECTED_SOURCE_PREFIX}:{transaction.transaction_no}",
        quality=0.75,
    )
    return replace(
        previous,
        transaction_no=transaction.transaction_no,
        source_observation_no=transaction.observation_no,
        source_geometry_map_ref=transaction.evidence_map_ref,
        tracked_identity_handle=transaction.tracked_identity_handle,
        source_mode=transaction.source_mode,
        source_localization_status=transaction.localization_status,
        source_track_status=transaction.track_status,
        source_distance=transaction.distance,
        source_uncertainty_radius=float(transaction.uncertainty_radius or 0.0),
        source_proximity=transaction.proximity,
        source_temporal_trend=transaction.temporal_trend,
        expectation_kind=FollowMomExpectationKindV1.REDUCE_SEPARATION,
        provenance=provenance,
    )


def _map_gate_value_and_expected(
    transaction: FollowMomCompareTransactionV1,
    advisory: FollowMomAdvisoryV1,
    prior_outcome: Optional[FollowMomObservedOutcomeV1],
) -> tuple[bool, str, Optional[FollowMomExpectedSuccessorV1]]:
    """Return the authoritative gate value, reason, and expected successor."""
    if advisory.kind is FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED:
        return True, advisory.reason, transaction.expected_successor
    if advisory.kind is FollowMomAdvisoryKindV1.CONTINUE_SUPPORTED:
        expected = _continuation_expected_successor(transaction, prior_outcome)
        if expected is None:
            raise ValueError("continuation expected successor could not be constructed")
        return True, advisory.reason, expected
    return False, advisory.reason, None


def _decision_from_current_state(
    ctx: Any,
    *,
    authority_mode: FollowMomAuthorityModeV1,
    legacy_gate_triggered: bool,
    legacy_gate_reason: str,
    protected_legacy_veto: bool,
    legacy_compatibility_force: bool,
) -> FollowMomAuthorityDecisionV1:
    """Build one bounded guarded/default FollowMom gate decision."""
    transaction = _current_transaction(ctx)
    advisory = _current_advisory(ctx, transaction)
    prior_outcome = _prior_outcome(ctx, transaction)

    transaction_no = transaction.transaction_no if transaction is not None else None
    observation_no = transaction.observation_no if transaction is not None else None
    recommendation = transaction.map_recommendation if transaction is not None else None
    map_reason = transaction.map_reason if transaction is not None else None
    source_mode = transaction.source_mode if transaction is not None else "unavailable"
    identity_support = (
        transaction.identity_support if transaction is not None else MaternalIdentitySupportV1.UNINITIALIZED
    )
    role_retained = transaction.role_retained if transaction is not None else False
    observability = transaction.observability if transaction is not None else MaternalObservabilityV1.UNAVAILABLE
    localization_status = (
        transaction.localization_status if transaction is not None else MaternalLocalizationStatusV1.UNKNOWN
    )
    track_status = transaction.track_status if transaction is not None else MaternalTrackStatusV1.UNINITIALIZED
    proximity = transaction.proximity if transaction is not None else MaternalProximityV1.UNKNOWN
    temporal_trend = (
        transaction.temporal_trend if transaction is not None else MaternalTemporalTrendV1.UNKNOWN
    )
    temporal_valid = transaction.temporal_valid if transaction is not None else False
    temporal_support_status = transaction.temporal_support_status if transaction is not None else "unavailable"
    reliable_negative_evidence = _reliable_negative_evidence(ctx, transaction)

    fallback_used = True
    source = FollowMomAuthoritySourceV1.LEGACY_FALLBACK
    triggered = bool(legacy_gate_triggered)
    reason = f"legacy_bodymap_fallback:{legacy_gate_reason}"
    fallback_reason: Optional[str] = legacy_gate_reason
    expected: Optional[FollowMomExpectedSuccessorV1] = None

    if protected_legacy_veto:
        source = FollowMomAuthoritySourceV1.PROTECTED_LEGACY_VETO
        triggered = False
        reason = f"protected_legacy_veto:{legacy_gate_reason}"
        fallback_reason = legacy_gate_reason
    elif legacy_compatibility_force:
        source = FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY
        triggered = True
        reason = f"legacy_compatibility_force:{legacy_gate_reason}"
        fallback_reason = legacy_gate_reason
    elif not legacy_gate_triggered:
        source = FollowMomAuthoritySourceV1.LEGACY_FALLBACK
        triggered = False
        reason = f"legacy_false_preserved:{legacy_gate_reason}"
        fallback_reason = legacy_gate_reason
    else:
        outcome_review_kinds = {
            FollowMomAdvisoryKindV1.FOLLOWMOM_OUTCOME_FAILURE,
            FollowMomAdvisoryKindV1.FOLLOWMOM_OUTCOME_UNKNOWN,
            FollowMomAdvisoryKindV1.ACTION_HANDOFF_MISMATCH,
        }
        if transaction is not None and advisory is not None and advisory.kind in outcome_review_kinds:
            guard_failure = _advisory_guard_failure(transaction, advisory)
        else:
            guard_failure = _current_exact_guard_failure(ctx, transaction)
            if guard_failure is None and transaction is not None:
                guard_failure = _advisory_guard_failure(transaction, advisory)
        if guard_failure is None and transaction is not None and advisory is not None:
            try:
                triggered, reason, expected = _map_gate_value_and_expected(transaction, advisory, prior_outcome)
            except ValueError as exc:
                guard_failure = str(exc)
            else:
                source = FollowMomAuthoritySourceV1.WNM_NAVMAP
                fallback_used = False
                fallback_reason = None
        if guard_failure is not None:
            source = FollowMomAuthoritySourceV1.LEGACY_FALLBACK
            triggered = bool(legacy_gate_triggered)
            reason = f"legacy_bodymap_fallback:{guard_failure}"
            fallback_reason = guard_failure

    return FollowMomAuthorityDecisionV1(
        decision_no=_next_decision_no(ctx),
        transaction_no=transaction_no,
        observation_no=observation_no,
        controller_step=_controller_step(ctx),
        source_stage="gate",
        authority_mode=authority_mode,
        triggered=triggered,
        authority_source=source,
        reason=reason,
        fallback_used=fallback_used,
        fallback_reason=fallback_reason,
        legacy_gate_triggered=bool(legacy_gate_triggered),
        legacy_gate_reason=legacy_gate_reason,
        protected_legacy_veto=bool(protected_legacy_veto),
        legacy_compatibility_force=bool(legacy_compatibility_force),
        map_recommendation=recommendation,
        map_reason=map_reason,
        advisory_kind=advisory.kind if advisory is not None else None,
        advisory_scope=advisory.scope if advisory is not None else None,
        source_mode=source_mode,
        identity_support=identity_support,
        role_retained=role_retained,
        observability=observability,
        localization_status=localization_status,
        track_status=track_status,
        proximity=proximity,
        temporal_trend=temporal_trend,
        temporal_valid=temporal_valid,
        temporal_support_status=temporal_support_status,
        reliable_negative_evidence=reliable_negative_evidence,
        expected_successor=expected,
        prior_outcome_transaction_no=(prior_outcome.transaction_no if prior_outcome is not None else None),
        prior_outcome=(prior_outcome.outcome if prior_outcome is not None else None),
        prior_action_applied=(prior_outcome.action_applied if prior_outcome is not None else None),
    )


def _error_fallback_decision(
    ctx: Any,
    *,
    authority_mode: FollowMomAuthorityModeV1,
    legacy_gate_triggered: bool,
    legacy_gate_reason: str,
    protected_legacy_veto: bool,
    legacy_compatibility_force: bool,
    error: Exception,
) -> FollowMomAuthorityDecisionV1:
    """Return a minimal typed legacy fallback after an authority-path error.

    Default authority must fail toward the complete historical gate, never
    toward an accidental suppression. The error record intentionally avoids
    reading the transaction/advisory path that just failed. Explicit protected
    veto and compatibility ownership are preserved when their supplied legacy
    values are internally consistent.
    """
    protected = bool(protected_legacy_veto and not legacy_gate_triggered)
    compatibility = bool(legacy_compatibility_force and legacy_gate_triggered and not protected)
    if protected:
        source = FollowMomAuthoritySourceV1.PROTECTED_LEGACY_VETO
        triggered = False
    elif compatibility:
        source = FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY
        triggered = True
    else:
        source = FollowMomAuthoritySourceV1.LEGACY_FALLBACK
        triggered = bool(legacy_gate_triggered)

    error_reason = f"authority_error_{type(error).__name__}"
    return FollowMomAuthorityDecisionV1(
        decision_no=_next_decision_no(ctx),
        transaction_no=None,
        observation_no=None,
        controller_step=_controller_step(ctx),
        source_stage="gate",
        authority_mode=authority_mode,
        triggered=triggered,
        authority_source=source,
        reason=f"legacy_bodymap_fallback:{error_reason}",
        fallback_used=True,
        fallback_reason=error_reason,
        legacy_gate_triggered=bool(legacy_gate_triggered),
        legacy_gate_reason=legacy_gate_reason,
        protected_legacy_veto=protected,
        legacy_compatibility_force=compatibility,
        map_recommendation=None,
        map_reason=None,
        advisory_kind=None,
        advisory_scope=None,
        source_mode="authority_error",
        identity_support=MaternalIdentitySupportV1.UNINITIALIZED,
        role_retained=False,
        observability=MaternalObservabilityV1.UNAVAILABLE,
        localization_status=MaternalLocalizationStatusV1.UNKNOWN,
        track_status=MaternalTrackStatusV1.UNINITIALIZED,
        proximity=MaternalProximityV1.UNKNOWN,
        temporal_trend=MaternalTemporalTrendV1.UNKNOWN,
        temporal_valid=False,
        temporal_support_status="authority_error",
        reliable_negative_evidence=False,
        expected_successor=None,
        prior_outcome_transaction_no=None,
        prior_outcome=None,
        prior_action_applied=None,
    )


def _reusable_gate_decision(
    ctx: Any,
    *,
    authority_mode: FollowMomAuthorityModeV1,
    legacy_gate_triggered: bool,
    legacy_gate_reason: str,
    protected_legacy_veto: bool,
    legacy_compatibility_force: bool,
) -> Optional[FollowMomAuthorityDecisionV1]:
    """Return the current same-cycle gate decision when evaluation repeats.

    Policy gates may be inspected more than once before execution, including by
    the WorkingMap Creative diagnostic and then by the real selector. Reusing an
    identical gate-stage decision keeps one decision number and one bounded
    lifecycle row for the controller step. Selection-stage records are never
    reused as gates, and any changed legacy input forces a fresh decision.
    """
    decision = getattr(ctx, "navmap_followmom_authority_decision", None)
    if not isinstance(decision, FollowMomAuthorityDecisionV1):
        return None
    transaction = _current_transaction(ctx)
    transaction_no = transaction.transaction_no if transaction is not None else None
    if decision.source_stage != "gate":
        return None
    if decision.controller_step != _controller_step(ctx):
        return None
    if decision.authority_mode is not authority_mode:
        return None
    if decision.transaction_no != transaction_no:
        return None
    if decision.legacy_gate_triggered != bool(legacy_gate_triggered):
        return None
    if decision.legacy_gate_reason != legacy_gate_reason:
        return None
    if decision.protected_legacy_veto != bool(protected_legacy_veto):
        return None
    if decision.legacy_compatibility_force != bool(legacy_compatibility_force):
        return None
    return decision


def followmom_authority_trigger_value_v1(
    ctx: Any,
    *,
    legacy_gate_triggered: bool,
    legacy_gate_reason: str,
    protected_legacy_veto: bool,
    legacy_compatibility_force: bool,
) -> bool:
    """Return the active FollowMom gate while storing authority telemetry.

    Legacy mode is an exact pass-through. Guarded/default modes preserve every
    supplied legacy veto and compatibility force. Only an ordinary permissive
    legacy opportunity may be controlled by exact current WNM/NavMap evidence.
    """
    legacy_value = bool(legacy_gate_triggered)
    _require_nonempty_text(legacy_gate_reason, field_name="legacy_gate_reason")
    mode = followmom_authority_mode_v1(ctx)
    if mode is FollowMomAuthorityModeV1.LEGACY:
        return legacy_value

    reusable = _reusable_gate_decision(
        ctx,
        authority_mode=mode,
        legacy_gate_triggered=legacy_value,
        legacy_gate_reason=legacy_gate_reason,
        protected_legacy_veto=bool(protected_legacy_veto),
        legacy_compatibility_force=bool(legacy_compatibility_force),
    )
    if reusable is not None:
        return reusable.triggered

    try:
        decision = _decision_from_current_state(
            ctx,
            authority_mode=mode,
            legacy_gate_triggered=legacy_value,
            legacy_gate_reason=legacy_gate_reason,
            protected_legacy_veto=bool(protected_legacy_veto),
            legacy_compatibility_force=bool(legacy_compatibility_force),
        )
    except Exception as exc:  # defensive default-authority fallback boundary
        decision = _error_fallback_decision(
            ctx,
            authority_mode=mode,
            legacy_gate_triggered=legacy_value,
            legacy_gate_reason=legacy_gate_reason,
            protected_legacy_veto=bool(protected_legacy_veto),
            legacy_compatibility_force=bool(legacy_compatibility_force),
            error=exc,
        )
    _store_decision(ctx, decision)
    return decision.triggered


def followmom_authority_legacy_bridge_allowed_v1(ctx: Any) -> bool:
    """Return whether PolicyRuntime may apply its historical FollowMom force bridge.

    The bridge is part of the retained legacy fallback and benchmark-compatibility
    surface. It must remain available in explicit legacy mode, when the guarded
    path fell back, or when a compatibility force owns the decision. It must not
    re-add FollowMom after an actionable WNM/NavMap ``DO_NOT_RECRUIT`` decision,
    and it must not convert a protected veto into a candidate.

    Returning False for a missing decision in guarded/default mode is the safer
    failure behavior: the active FollowMom gate has already had its opportunity
    to use the complete legacy fallback, so a later force should not silently
    bypass an unavailable authority record.
    """
    mode = followmom_authority_mode_v1(ctx)
    if mode is FollowMomAuthorityModeV1.LEGACY:
        return True

    decision = getattr(ctx, "navmap_followmom_authority_decision", None)
    if not isinstance(decision, FollowMomAuthorityDecisionV1):
        return False
    if decision.source_stage != "gate":
        return False
    return decision.authority_source in {
        FollowMomAuthoritySourceV1.LEGACY_FALLBACK,
        FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY,
    }


def _selection_result(decision: FollowMomAuthorityDecisionV1, selected_policy: Optional[str]) -> str:
    """Return one deterministic selection label for the authority lifecycle."""
    selected_follow = selected_policy == _FOLLOW_MOM_POLICY
    if decision.authority_source is FollowMomAuthoritySourceV1.WNM_NAVMAP:
        prefix = "default" if decision.authority_mode is FollowMomAuthorityModeV1.DEFAULT else "guarded"
        if decision.triggered:
            return f"{prefix}_followmom_selected" if selected_follow else f"{prefix}_followmom_not_selected"
        return f"{prefix}_do_not_follow_overridden" if selected_follow else f"{prefix}_do_not_follow_respected"
    if decision.authority_source is FollowMomAuthoritySourceV1.PROTECTED_LEGACY_VETO:
        return "protected_veto_overridden" if selected_follow else "protected_veto_respected"
    if decision.authority_source is FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY:
        return "compatibility_followmom_selected" if selected_follow else "compatibility_followmom_not_selected"
    return "fallback_followmom_selected" if selected_follow else "fallback_non_followmom_selected"


def _arm_expected_pending(
    ctx: Any,
    decision: FollowMomAuthorityDecisionV1,
    selected_policy: Optional[str],
) -> bool:
    """Arm or re-tag one compact expectation after actual FollowMom selection.

    Phase 4D may already have armed the transaction's ordinary start
    expectation. Phase 4F reuses that exact object but records the authority
    source that supplied the gate. A successful-continuation decision carries a
    fresh authority-created expected relation because the raw Phase 4D start
    recommendation is ``DO_NOT_FOLLOW`` in the ``far + approaching`` case.
    """
    if selected_policy != _FOLLOW_MOM_POLICY:
        return False

    expected = decision.expected_successor
    pending = getattr(ctx, "navmap_followmom_compare_pending", None)
    if expected is None and isinstance(pending, FollowMomExpectedPendingV1):
        if decision.transaction_no is not None and pending.transaction_no == decision.transaction_no:
            expected = pending.expected_successor
    if expected is None:
        return False

    ctx.navmap_followmom_compare_pending = FollowMomExpectedPendingV1(
        transaction_no=expected.transaction_no,
        expected_successor=expected,
        selected_policy=_FOLLOW_MOM_POLICY,
        selected_controller_step=_controller_step(ctx),
        selection_phase=decision.phase,
        selection_authority=decision.authority_label,
        cognitive_source=decision.authority_source.value,
    )
    _mark_compare_transaction_pending(ctx, expected.transaction_no)
    return True


def _mark_compare_transaction_pending(ctx: Any, transaction_no: int) -> None:
    """Keep the Phase 4D transaction/history consistent with authority arming."""
    transaction = getattr(ctx, "navmap_followmom_compare_transaction", None)
    if not isinstance(transaction, FollowMomCompareTransactionV1):
        return
    if transaction.transaction_no != transaction_no or transaction.pending_expected_armed:
        return

    # A Phase 4F continuation expectation is intentionally absent from the raw
    # Phase 4D transaction because that transaction's initial-applicability
    # recommendation remains DO_NOT_FOLLOW. The ctx pending register and Phase
    # 4F decision are authoritative for that continuation expectation; do not
    # violate the Phase 4D dataclass invariant by pretending it owned one.
    if transaction.expected_successor is None:
        summary = getattr(ctx, "navmap_followmom_compare_last_update", None)
        if isinstance(summary, dict):
            refreshed = dict(summary)
            refreshed["pending_expected"] = True
            refreshed["pending_expected_source"] = "phase4f_followmom_authority"
            ctx.navmap_followmom_compare_last_update = refreshed
        return

    updated = replace(transaction, pending_expected_armed=True)
    ctx.navmap_followmom_compare_transaction = updated

    history = getattr(ctx, "navmap_followmom_compare_history", None)
    if isinstance(history, list) and history:
        row = history[-1]
        if isinstance(row, dict) and row.get("transaction_no") == transaction_no:
            history[-1] = updated.as_dict()

    summary = getattr(ctx, "navmap_followmom_compare_last_update", None)
    if isinstance(summary, dict):
        refreshed = dict(summary)
        refreshed["transaction"] = updated.as_dict()
        refreshed["pending_expected"] = True
        ctx.navmap_followmom_compare_last_update = refreshed


def followmom_authority_selection_step_v1(
    ctx: Any,
    *,
    active_effective_candidate: Optional[bool] = None,
    selected_policy: Optional[str],
) -> dict[str, Any]:
    """Finalize the current authority record after PolicyRuntime selection.

    The function observes the completed global arbitration. It cannot change the
    selected primitive. It may only attach the decision's compact expected
    relation to the existing Phase 4D pending-outcome seam when FollowMom was
    actually selected.
    """
    if ctx is None:
        return {
            "schema": "followmom_authority_summary_v1",
            "phase": "4F",
            "status": "ctx_unavailable",
            "authority": "default_followmom",
        }
    if followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.LEGACY:
        return followmom_authority_summary_v1(ctx)

    decision = getattr(ctx, "navmap_followmom_authority_decision", None)
    if not isinstance(decision, FollowMomAuthorityDecisionV1):
        return followmom_authority_summary_v1(ctx)
    if decision.source_stage != "gate" or decision.controller_step != _controller_step(ctx):
        return followmom_authority_summary_v1(ctx)

    candidate_value = active_effective_candidate if isinstance(active_effective_candidate, bool) else None
    policy_value = selected_policy if isinstance(selected_policy, str) and selected_policy else None
    expected_armed = _arm_expected_pending(ctx, decision, policy_value)
    updated = replace(
        decision,
        source_stage="selection",
        active_effective_candidate=candidate_value,
        selected_policy=policy_value,
        selection_result=_selection_result(decision, policy_value),
        expected_pending_armed=expected_armed,
    )
    return _store_decision(ctx, updated)


def followmom_authority_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe guarded/default authority summary."""
    if ctx is None:
        return {
            "schema": "followmom_authority_summary_v1",
            "phase": "4F",
            "status": "ctx_unavailable",
        }

    history_count = len(getattr(ctx, "navmap_followmom_authority_history", []) or [])
    mode = followmom_authority_mode_v1(ctx)
    if mode is FollowMomAuthorityModeV1.LEGACY:
        compatibility = getattr(ctx, "navmap_followmom_guarded_enabled", None)
        return {
            "schema": "followmom_authority_summary_v1",
            "phase": "4F",
            "status": "legacy_override" if compatibility is False else "legacy_mode",
            "authority": "legacy_bodymap_policy_runtime",
            "authority_level": "legacy",
            "authority_mode": "legacy",
            "default_authority_active": False,
            "normal_cognitive_source": "legacy_bodymap_policy_runtime",
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "protected_safety_can_be_overridden": False,
            "history_count": history_count,
        }

    phase = "4F" if mode is FollowMomAuthorityModeV1.DEFAULT else "4E-B"
    authority = "default_followmom" if mode is FollowMomAuthorityModeV1.DEFAULT else "guarded_followmom"
    row = getattr(ctx, "navmap_followmom_authority_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "followmom_authority_summary_v1",
            "phase": phase,
            "status": "idle",
            "authority": authority,
            "authority_level": mode.value,
            "authority_mode": mode.value,
            "default_authority_active": mode is FollowMomAuthorityModeV1.DEFAULT,
            "normal_cognitive_source": (
                "wnm_navmap" if mode is FollowMomAuthorityModeV1.DEFAULT else "feature_flagged_wnm_navmap"
            ),
            "legacy_debug_mode_available": True,
            "legacy_retired": False,
            "protected_safety_can_be_overridden": False,
            "history_count": history_count,
        }

    if row.get("status") in {"error", "dependency_error"}:
        out = dict(row)
        out["history_count"] = history_count
        out.setdefault("legacy_debug_mode_available", True)
        out.setdefault("legacy_retired", False)
        out.setdefault("protected_safety_can_be_overridden", False)
        return out

    source = row.get("trigger_authority_source")
    if source == FollowMomAuthoritySourceV1.WNM_NAVMAP.value:
        status = "default_map_authority" if mode is FollowMomAuthorityModeV1.DEFAULT else "guarded_map_authority"
    elif source == FollowMomAuthoritySourceV1.PROTECTED_LEGACY_VETO.value:
        status = "protected_legacy_veto"
    elif source == FollowMomAuthoritySourceV1.LEGACY_COMPATIBILITY.value:
        status = "legacy_compatibility"
    else:
        status = "legacy_fallback"
    return {
        "schema": "followmom_authority_summary_v1",
        "phase": phase,
        "status": status,
        "authority": authority,
        "authority_level": mode.value,
        "authority_mode": mode.value,
        "default_authority_active": mode is FollowMomAuthorityModeV1.DEFAULT,
        "normal_cognitive_source": (
            "wnm_navmap" if mode is FollowMomAuthorityModeV1.DEFAULT else "feature_flagged_wnm_navmap"
        ),
        "legacy_debug_mode_available": True,
        "legacy_retired": False,
        "protected_safety_can_be_overridden": False,
        "decision": dict(row),
        "history_count": history_count,
    }


def followmom_authority_explain_v1(ctx: Any) -> str:
    """Return one concise FollowMom authority explanation without recomputation."""
    mode = followmom_authority_mode_v1(ctx)
    if mode is FollowMomAuthorityModeV1.LEGACY:
        return "followmom_authority=legacy source=legacy_bodymap_policy_runtime"
    decision = getattr(ctx, "navmap_followmom_authority_decision", None)
    phase_label = "phase4f_default" if mode is FollowMomAuthorityModeV1.DEFAULT else "phase4e_guarded"
    if not isinstance(decision, FollowMomAuthorityDecisionV1):
        return f"{phase_label}=on source=legacy_fallback reason=decision_unavailable"
    return (
        f"{phase_label}=on source={decision.authority_source.value} trigger={decision.triggered} "
        f"map={decision.map_recommendation.value if decision.map_recommendation is not None else 'unavailable'} "
        f"advisory={decision.advisory_kind.value if decision.advisory_kind is not None else 'unavailable'} "
        f"legacy={decision.legacy_gate_triggered} fallback={decision.fallback_used}"
    )


def render_followmom_authority_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable guarded/default FollowMom authority lines."""
    summary = followmom_authority_summary_v1(ctx)
    mode = summary.get("authority_mode") or "legacy"
    if mode == "default":
        title = "FOLLOWMOM PHASE 4F DEFAULT AUTHORITY:"
    elif mode == "guarded":
        title = "FOLLOWMOM PHASE 4E-B GUARDED AUTHORITY:"
    else:
        title = "FOLLOWMOM AUTHORITY LEGACY MODE:"
    lines = [title]
    status = summary.get("status")
    if status in {"ctx_unavailable", "legacy_mode", "legacy_override", "idle", "error", "dependency_error"}:
        lines.append(
            "  "
            f"status={status} mode={mode} authority={summary.get('authority')} "
            f"normal_cognitive_source={summary.get('normal_cognitive_source')} "
            f"legacy_retired={summary.get('legacy_retired')}"
        )
        if status == "error":
            lines.append(f"  error_type={summary.get('error_type')} error={summary.get('error')}")
        elif status == "dependency_error":
            lines.append(f"  reason={summary.get('reason')}")
        return lines

    decision = summary.get("decision")
    decision = decision if isinstance(decision, dict) else {}
    lines.append(
        "  "
        f"status={status} mode={mode} source={decision.get('trigger_authority_source')} "
        f"trigger={decision.get('triggered')} fallback={decision.get('fallback_used')} "
        "protected_safety_can_be_overridden=False"
    )
    lines.append(
        "  "
        f"tx={decision.get('transaction_no')} observation={decision.get('observation_no')} "
        f"map={decision.get('map_recommendation')} advisory={decision.get('advisory_kind')} "
        f"scope={decision.get('advisory_scope')} reason={decision.get('reason')}"
    )
    lines.append(
        "  "
        f"identity={decision.get('identity_support')} role_retained={decision.get('role_retained')} "
        f"localization={decision.get('localization_status')}/{decision.get('source_mode')} "
        f"track={decision.get('track_status')} temporal={decision.get('temporal_trend')} "
        f"support={decision.get('temporal_support_status')}"
    )
    lines.append(
        "  "
        f"legacy gate={decision.get('legacy_gate_triggered')} reason={decision.get('legacy_gate_reason')} "
        f"protected_veto={decision.get('protected_legacy_veto')} "
        f"compatibility_force={decision.get('legacy_compatibility_force')}"
    )
    if decision.get("source_stage") == "selection":
        lines.append(
            "  "
            f"selected={decision.get('selected_policy')} result={decision.get('selection_result')} "
            f"expected_pending_armed={decision.get('expected_pending_armed')}"
        )
    return lines
