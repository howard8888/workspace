# -*- coding: utf-8 -*-
"""Phase 4E-A non-binding FollowMom advisory for CCA8.

Purpose
-------
Phase 4D established an independent map-native FollowMom comparison from
maternal geometry, bounded temporal meaning, and identity/localization
continuity. Phase 4E-A converts that evidence into an inspectable advisory
surface while preserving the complete legacy PolicyRuntime/controller action.

The advisory may recommend that CCA8:

* recruit FollowMom from current supported maternal relations;
* avoid recruiting a new FollowMom trajectory;
* continue an already applied FollowMom trajectory when its immediately prior
  expected relation succeeded and the current ``far + approaching`` trend is
  therefore compatible with successful following;
* defer to legacy execution and request more evidence; or
* review a protected legacy block, arbitration difference, failed expectation,
  unknown outcome, or action-handoff mismatch.

Start versus continuation
-------------------------
Phase 4B measures relative SELF-maternal separation. A decreasing distance does
not identify whether Mom moved toward SELF or SELF moved toward Mom. Therefore,
Phase 4D's experimental ``far + approaching -> do_not_follow`` recommendation
must not automatically terminate an already successful FollowMom trajectory.
This module treats it as ``do_not_recruit`` for initial applicability unless the
immediately prior Phase 4D expected outcome proves that FollowMom was applied
and reduced separation. In that narrow case the advisory records
``continue_supported``. This is advisory evidence only; it is not persistence,
hysteresis, suppression, or execution authority.

Authority boundary
------------------
Every public record states ``authority=advisory_only``,
``legacy_executes=True``, and ``map_can_override=False``. The selected policy
before and after advisory processing is identical. The module cannot alter
BodyMap, PolicyRuntime gates, candidate filtering, arbitration, environment
actions, protected posture/safety behavior, NavMap revisions, or lower motor
execution.
"""

from __future__ import annotations

# The public record intentionally carries the complete authority and review
# contract, which is more important here than minimizing field count.
# pylint: disable=duplicate-code
# pylint: disable=too-many-instance-attributes

from dataclasses import dataclass
from enum import Enum
from typing import Any, Optional

from cca8_followmom_compare import (
    FollowMomCompareTransactionV1,
    FollowMomDisagreementAssessmentV1,
    FollowMomMapRecommendationV1,
    FollowMomObservedOutcomeV1,
)
from cca8_maternal_continuity import (
    MaternalIdentitySupportV1,
    MaternalLocalizationStatusV1,
    MaternalObservabilityV1,
    MaternalTrackStatusV1,
)
from cca8_maternal_geometry import MaternalProximityV1
from cca8_maternal_temporal import MaternalTemporalTrendV1

__version__ = "0.1.0"

__all__ = [
    "FollowMomAdvisoryKindV1",
    "FollowMomAdvisoryScopeV1",
    "FollowMomAdvisorySeverityV1",
    "FollowMomAdvisoryV1",
    "followmom_advisory_observation_step_v1",
    "followmom_advisory_selection_step_v1",
    "followmom_advisory_summary_v1",
    "render_followmom_advisory_lines_v1",
    "__version__",
]

_FOLLOW_MOM_POLICY = "policy:follow_mom"
_FAR_APPROACHING_REASON = "far_but_separation_already_approaching"
_DEFAULT_HISTORY_LIMIT = 25


class FollowMomAdvisoryKindV1(str, Enum):
    """Bounded Phase 4E-A advisory classifications."""

    FOLLOW_SUPPORTED = "follow_supported"
    DO_NOT_RECRUIT = "do_not_recruit"
    CONTINUE_SUPPORTED = "continue_supported"
    MAP_DEFERRED = "map_deferred"
    LEGACY_BLOCK_PRESERVED = "legacy_block_preserved"
    ARBITRATION_REVIEW = "arbitration_review"
    FOLLOWMOM_OUTCOME_FAILURE = "followmom_outcome_failure"
    FOLLOWMOM_OUTCOME_UNKNOWN = "followmom_outcome_unknown"
    ACTION_HANDOFF_MISMATCH = "action_handoff_mismatch"


class FollowMomAdvisoryScopeV1(str, Enum):
    """Question addressed by one advisory without granting execution authority."""

    START = "start"
    CONTINUE = "continue"
    FALLBACK = "fallback"
    SELECTION_REVIEW = "selection_review"
    OUTCOME_REVIEW = "outcome_review"


class FollowMomAdvisorySeverityV1(str, Enum):
    """Human-readable advisory severity without behavioral authority."""

    INFO = "info"
    CAUTION = "caution"
    WARNING = "warning"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


@dataclass(frozen=True, slots=True)
class _FollowMomAdvisoryDecisionV1:
    """Internal typed decision used to construct the public advisory record."""

    kind: FollowMomAdvisoryKindV1
    severity: FollowMomAdvisorySeverityV1
    scope: FollowMomAdvisoryScopeV1
    reason: str
    recommended_response: str
    fallback_required: bool = False
    resample_recommended: bool = False
    legacy_filter_preserved: bool = False
    disagreement_review_recommended: bool = False
    outcome_review_recommended: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.kind, FollowMomAdvisoryKindV1):
            raise TypeError("kind must be FollowMomAdvisoryKindV1")
        if not isinstance(self.severity, FollowMomAdvisorySeverityV1):
            raise TypeError("severity must be FollowMomAdvisorySeverityV1")
        if not isinstance(self.scope, FollowMomAdvisoryScopeV1):
            raise TypeError("scope must be FollowMomAdvisoryScopeV1")
        _require_nonempty_text(self.reason, field_name="reason")
        _require_nonempty_text(self.recommended_response, field_name="recommended_response")
        for field_name in (
            "fallback_required",
            "resample_recommended",
            "legacy_filter_preserved",
            "disagreement_review_recommended",
            "outcome_review_recommended",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")


@dataclass(frozen=True, slots=True)
class FollowMomAdvisoryV1:
    """One non-binding Phase 4E-A advisory derived from Phase 4D evidence.

    The record deliberately separates initial recruitment from continuation.
    It may request resampling or review, but it cannot mutate a gate, candidate
    set, selected primitive, action, BodyMap, NavMap, or protected safety path.
    """

    transaction_no: int
    observation_no: int
    source_stage: str
    kind: FollowMomAdvisoryKindV1
    severity: FollowMomAdvisorySeverityV1
    scope: FollowMomAdvisoryScopeV1
    reason: str
    recommended_response: str
    map_recommendation: FollowMomMapRecommendationV1
    map_reason: str
    source_mode: str
    identity_support: MaternalIdentitySupportV1
    role_retained: bool
    observability: MaternalObservabilityV1
    localization_status: MaternalLocalizationStatusV1
    track_status: MaternalTrackStatusV1
    proximity: MaternalProximityV1
    temporal_trend: MaternalTemporalTrendV1
    temporal_valid: bool
    legacy_gate_triggered: Optional[bool]
    legacy_effective_candidate: Optional[bool]
    selected_policy: Optional[str]
    gate_comparison: str
    candidate_comparison: str
    selection_comparison: str
    disagreement_assessment: FollowMomDisagreementAssessmentV1
    prior_outcome_transaction_no: Optional[int]
    prior_outcome: Optional[str]
    prior_action_applied: Optional[str]
    prior_outcome_reason: Optional[str]
    fallback_required: bool
    resample_recommended: bool
    legacy_filter_preserved: bool
    disagreement_review_recommended: bool
    outcome_review_recommended: bool

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.source_stage not in {"observation", "selection"}:
            raise ValueError("source_stage must be 'observation' or 'selection'")
        if not isinstance(self.kind, FollowMomAdvisoryKindV1):
            raise TypeError("kind must be FollowMomAdvisoryKindV1")
        if not isinstance(self.severity, FollowMomAdvisorySeverityV1):
            raise TypeError("severity must be FollowMomAdvisorySeverityV1")
        if not isinstance(self.scope, FollowMomAdvisoryScopeV1):
            raise TypeError("scope must be FollowMomAdvisoryScopeV1")
        _require_nonempty_text(self.reason, field_name="reason")
        _require_nonempty_text(self.recommended_response, field_name="recommended_response")
        if not isinstance(self.map_recommendation, FollowMomMapRecommendationV1):
            raise TypeError("map_recommendation must be FollowMomMapRecommendationV1")
        _require_nonempty_text(self.map_reason, field_name="map_reason")
        _require_nonempty_text(self.source_mode, field_name="source_mode")
        if not isinstance(self.identity_support, MaternalIdentitySupportV1):
            raise TypeError("identity_support must be MaternalIdentitySupportV1")
        if not isinstance(self.role_retained, bool):
            raise TypeError("role_retained must be bool")
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
        if not isinstance(self.temporal_valid, bool):
            raise TypeError("temporal_valid must be bool")
        for field_name in ("legacy_gate_triggered", "legacy_effective_candidate"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        if self.selected_policy is not None and not isinstance(self.selected_policy, str):
            raise TypeError("selected_policy must be str or None")
        for field_name in ("gate_comparison", "candidate_comparison", "selection_comparison"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.disagreement_assessment, FollowMomDisagreementAssessmentV1):
            raise TypeError("disagreement_assessment must be FollowMomDisagreementAssessmentV1")
        if self.prior_outcome_transaction_no is not None:
            _require_positive_int(self.prior_outcome_transaction_no, field_name="prior_outcome_transaction_no")
        for field_name in ("prior_outcome", "prior_action_applied", "prior_outcome_reason"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, str):
                raise TypeError(f"{field_name} must be str or None")
        for field_name in (
            "fallback_required",
            "resample_recommended",
            "legacy_filter_preserved",
            "disagreement_review_recommended",
            "outcome_review_recommended",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe advisory and immutable authority contract."""
        return {
            "schema": "followmom_advisory_v1",
            "phase": "4E-A",
            "authority_level": "advisory",
            "authority": "advisory_only",
            "legacy_authority": "bodymap_policy_runtime",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
            "map_can_trigger_follow_mom": False,
            "map_can_suppress_follow_mom": False,
            "protected_safety_can_be_overridden": False,
            "bodymap_mutation_allowed": False,
            "navmap_revision_allowed": False,
            "policy_selection_mutation_allowed": False,
            "advice_is_behavioral_command": False,
            "behavioral_primitive": "follow_mom",
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "source_stage": self.source_stage,
            "active": True,
            "kind": self.kind.value,
            "severity": self.severity.value,
            "scope": self.scope.value,
            "reason": self.reason,
            "recommended_response": self.recommended_response,
            "map_recommendation": self.map_recommendation.value,
            "map_reason": self.map_reason,
            "source_mode": self.source_mode,
            "identity_support": self.identity_support.value,
            "role_retained": self.role_retained,
            "observability": self.observability.value,
            "localization_status": self.localization_status.value,
            "track_status": self.track_status.value,
            "proximity": self.proximity.value,
            "temporal_trend": self.temporal_trend.value,
            "temporal_valid": self.temporal_valid,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "legacy_effective_candidate": self.legacy_effective_candidate,
            "selected_policy": self.selected_policy,
            "selected_policy_before_advisory": self.selected_policy,
            "selected_policy_after_advisory": self.selected_policy,
            "legacy_action_unchanged": True,
            "gate_comparison": self.gate_comparison,
            "candidate_comparison": self.candidate_comparison,
            "selection_comparison": self.selection_comparison,
            "disagreement_assessment": self.disagreement_assessment.value,
            "prior_outcome_transaction_no": self.prior_outcome_transaction_no,
            "prior_outcome": self.prior_outcome,
            "prior_action_applied": self.prior_action_applied,
            "prior_outcome_reason": self.prior_outcome_reason,
            "fallback_required": self.fallback_required,
            "fallback_source": "legacy_bodymap_policy_runtime" if self.fallback_required else None,
            "resample_recommended": self.resample_recommended,
            "legacy_filter_preserved": self.legacy_filter_preserved,
            "disagreement_review_recommended": self.disagreement_review_recommended,
            "outcome_review_recommended": self.outcome_review_recommended,
        }


def _history_limit(ctx: Any) -> int:
    """Return the configured positive bounded advisory history size."""
    try:
        value = int(getattr(ctx, "navmap_followmom_advisory_history_limit", _DEFAULT_HISTORY_LIMIT) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _relevant_prior_outcome(
    ctx: Any,
    transaction: FollowMomCompareTransactionV1,
) -> Optional[FollowMomObservedOutcomeV1]:
    """Return only the Phase 4D outcome immediately preceding this transaction.

    The latest outcome remains available for inspection, but an older failure or
    success must not keep shaping every future advisory after its causal window.
    """
    outcome = getattr(ctx, "navmap_followmom_compare_last_outcome", None)
    if not isinstance(outcome, FollowMomObservedOutcomeV1):
        return None
    if outcome.transaction_no != transaction.transaction_no - 1:
        return None
    return outcome


def _continuation_success(
    transaction: FollowMomCompareTransactionV1,
    prior_outcome: Optional[FollowMomObservedOutcomeV1],
) -> bool:
    """Return True for the narrow successful-following continuation evidence.

    This requires the immediately prior expected relation to have succeeded
    after the environment actually received FollowMom. The current map must be
    the experimental far-but-approaching case. A different current winner or an
    effective legacy block prevents the advisory from preferring continuation.
    """
    return bool(
        prior_outcome is not None
        and prior_outcome.outcome == "success"
        and prior_outcome.action_applied == _FOLLOW_MOM_POLICY
        and transaction.map_reason == _FAR_APPROACHING_REASON
        and transaction.legacy_effective_candidate is not False
        and transaction.selected_policy in {None, _FOLLOW_MOM_POLICY}
    )


def _map_legacy_disagreement(transaction: FollowMomCompareTransactionV1) -> bool:
    """Return True when the current advisory-worthy map and legacy paths diverge."""
    if transaction.gate_comparison.startswith("disagree_"):
        return True
    if transaction.candidate_comparison.startswith("disagree_"):
        return True
    return transaction.selection_comparison in {
        "map_follow_not_selected",
        "disagree_follow_selected",
    }


def _advisory_decision(
    transaction: FollowMomCompareTransactionV1,
    prior_outcome: Optional[FollowMomObservedOutcomeV1],
) -> _FollowMomAdvisoryDecisionV1:
    """Return one typed, conservative Phase 4E-A advisory decision."""
    if prior_outcome is not None and prior_outcome.outcome == "failure":
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.FOLLOWMOM_OUTCOME_FAILURE,
            severity=FollowMomAdvisorySeverityV1.WARNING,
            scope=FollowMomAdvisoryScopeV1.OUTCOME_REVIEW,
            reason=prior_outcome.reason,
            recommended_response="retain_legacy_execution_and_review_followmom_failure",
            fallback_required=True,
            outcome_review_recommended=True,
        )

    if prior_outcome is not None and prior_outcome.outcome == "unknown":
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.FOLLOWMOM_OUTCOME_UNKNOWN,
            severity=FollowMomAdvisorySeverityV1.CAUTION,
            scope=FollowMomAdvisoryScopeV1.OUTCOME_REVIEW,
            reason=prior_outcome.reason,
            recommended_response="retain_legacy_execution_and_resample_maternal_relation",
            fallback_required=True,
            resample_recommended=True,
            outcome_review_recommended=True,
        )

    if prior_outcome is not None and prior_outcome.outcome == "not_applied":
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.ACTION_HANDOFF_MISMATCH,
            severity=FollowMomAdvisorySeverityV1.WARNING,
            scope=FollowMomAdvisoryScopeV1.OUTCOME_REVIEW,
            reason=prior_outcome.reason,
            recommended_response="retain_legacy_action_and_review_action_handoff",
            fallback_required=True,
            outcome_review_recommended=True,
        )

    if transaction.map_recommendation is FollowMomMapRecommendationV1.DEFER:
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.MAP_DEFERRED,
            severity=FollowMomAdvisorySeverityV1.CAUTION,
            scope=FollowMomAdvisoryScopeV1.FALLBACK,
            reason=transaction.map_reason,
            recommended_response="use_legacy_fallback_and_resample_maternal_relation",
            fallback_required=True,
            resample_recommended=True,
        )

    if transaction.map_recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM:
        if transaction.legacy_effective_candidate is False:
            return _FollowMomAdvisoryDecisionV1(
                kind=FollowMomAdvisoryKindV1.LEGACY_BLOCK_PRESERVED,
                severity=FollowMomAdvisorySeverityV1.WARNING,
                scope=FollowMomAdvisoryScopeV1.SELECTION_REVIEW,
                reason=(
                    f"candidate={transaction.candidate_comparison};"
                    f"selection={transaction.selection_comparison}"
                ),
                recommended_response="preserve_legacy_filter_and_review_map_overtrigger",
                fallback_required=True,
                legacy_filter_preserved=True,
                disagreement_review_recommended=True,
            )
        if transaction.selected_policy not in {None, _FOLLOW_MOM_POLICY}:
            return _FollowMomAdvisoryDecisionV1(
                kind=FollowMomAdvisoryKindV1.ARBITRATION_REVIEW,
                severity=FollowMomAdvisorySeverityV1.INFO,
                scope=FollowMomAdvisoryScopeV1.SELECTION_REVIEW,
                reason=transaction.selection_comparison,
                recommended_response="preserve_legacy_winner_and_record_followmom_arbitration_difference",
                disagreement_review_recommended=True,
            )
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED,
            severity=FollowMomAdvisorySeverityV1.INFO,
            scope=FollowMomAdvisoryScopeV1.START,
            reason=transaction.map_reason,
            recommended_response="advise_followmom_recruitment_without_changing_legacy_execution",
        )

    if _continuation_success(transaction, prior_outcome):
        return _FollowMomAdvisoryDecisionV1(
            kind=FollowMomAdvisoryKindV1.CONTINUE_SUPPORTED,
            severity=FollowMomAdvisorySeverityV1.INFO,
            scope=FollowMomAdvisoryScopeV1.CONTINUE,
            reason="far_approaching_after_immediately_prior_followmom_success",
            recommended_response="advise_continuation_while_progress_remains_supported",
        )

    disagreement = _map_legacy_disagreement(transaction)
    legacy_following = bool(
        transaction.legacy_effective_candidate is True
        or transaction.selected_policy == _FOLLOW_MOM_POLICY
    )
    return _FollowMomAdvisoryDecisionV1(
        kind=FollowMomAdvisoryKindV1.DO_NOT_RECRUIT,
        severity=(FollowMomAdvisorySeverityV1.WARNING if legacy_following else FollowMomAdvisorySeverityV1.INFO),
        scope=FollowMomAdvisoryScopeV1.START,
        reason=transaction.map_reason,
        recommended_response=(
            "do_not_recruit_new_followmom_and_review_legacy_continuation"
            if legacy_following
            else "do_not_recruit_new_followmom_trajectory"
        ),
        fallback_required=legacy_following,
        disagreement_review_recommended=disagreement,
    )


def _build_advisory(
    ctx: Any,
    *,
    source_stage: str,
) -> Optional[FollowMomAdvisoryV1]:
    """Build one advisory from the latest complete or provisional transaction."""
    transaction = getattr(ctx, "navmap_followmom_compare_transaction", None)
    if not isinstance(transaction, FollowMomCompareTransactionV1):
        return None

    prior_outcome = _relevant_prior_outcome(ctx, transaction)
    decision = _advisory_decision(transaction, prior_outcome)
    return FollowMomAdvisoryV1(
        transaction_no=transaction.transaction_no,
        observation_no=transaction.observation_no,
        source_stage=source_stage,
        kind=decision.kind,
        severity=decision.severity,
        scope=decision.scope,
        reason=decision.reason,
        recommended_response=decision.recommended_response,
        map_recommendation=transaction.map_recommendation,
        map_reason=transaction.map_reason,
        source_mode=transaction.source_mode,
        identity_support=transaction.identity_support,
        role_retained=transaction.role_retained,
        observability=transaction.observability,
        localization_status=transaction.localization_status,
        track_status=transaction.track_status,
        proximity=transaction.proximity,
        temporal_trend=transaction.temporal_trend,
        temporal_valid=transaction.temporal_valid,
        legacy_gate_triggered=transaction.legacy_gate_triggered,
        legacy_effective_candidate=transaction.legacy_effective_candidate,
        selected_policy=transaction.selected_policy,
        gate_comparison=transaction.gate_comparison,
        candidate_comparison=transaction.candidate_comparison,
        selection_comparison=transaction.selection_comparison,
        disagreement_assessment=transaction.disagreement_assessment,
        prior_outcome_transaction_no=(prior_outcome.transaction_no if prior_outcome is not None else None),
        prior_outcome=(prior_outcome.outcome if prior_outcome is not None else None),
        prior_action_applied=(prior_outcome.action_applied if prior_outcome is not None else None),
        prior_outcome_reason=(prior_outcome.reason if prior_outcome is not None else None),
        fallback_required=decision.fallback_required,
        resample_recommended=decision.resample_recommended,
        legacy_filter_preserved=decision.legacy_filter_preserved,
        disagreement_review_recommended=decision.disagreement_review_recommended,
        outcome_review_recommended=decision.outcome_review_recommended,
    )


def _store_advisory(ctx: Any, advisory: FollowMomAdvisoryV1) -> dict[str, Any]:
    """Store one ctx-local advisory and one bounded row per compare transaction."""
    row = advisory.as_dict()
    ctx.navmap_followmom_advisory = advisory
    ctx.navmap_followmom_advisory_last_update = dict(row)

    history = getattr(ctx, "navmap_followmom_advisory_history", [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    if clean and clean[-1].get("transaction_no") == advisory.transaction_no:
        clean[-1] = dict(row)
    else:
        clean.append(dict(row))
    ctx.navmap_followmom_advisory_history = clean[-_history_limit(ctx):]
    return followmom_advisory_summary_v1(ctx)


def _store_status(ctx: Any, row: dict[str, Any]) -> dict[str, Any]:
    """Store one non-active advisory status so disabled/error states cannot look stale."""
    ctx.navmap_followmom_advisory = None
    ctx.navmap_followmom_advisory_last_update = dict(row)
    return dict(row)


def _advisory_step(ctx: Any, *, source_stage: str) -> dict[str, Any]:
    """Refresh Phase 4E-A advice after observation or completed selection."""
    if ctx is None:
        return {
            "schema": "followmom_advisory_summary_v1",
            "phase": "4E-A",
            "status": "ctx_unavailable",
            "authority": "advisory_only",
        }
    if not bool(getattr(ctx, "navmap_followmom_advisory_enabled", True)):
        return _store_status(
            ctx,
            {
                "schema": "followmom_advisory_summary_v1",
                "phase": "4E-A",
                "status": "disabled",
                "authority": "advisory_only",
                "follow_mom_authority": "legacy_bodymap_policy_runtime",
                "legacy_executes": True,
                "map_can_override": False,
                "protected_safety_can_be_overridden": False,
            },
        )
    if not bool(getattr(ctx, "navmap_followmom_compare_enabled", True)):
        return _store_status(
            ctx,
            {
                "schema": "followmom_advisory_summary_v1",
                "phase": "4E-A",
                "status": "compare_disabled",
                "authority": "advisory_only",
                "follow_mom_authority": "legacy_bodymap_policy_runtime",
                "legacy_executes": True,
                "map_can_override": False,
                "protected_safety_can_be_overridden": False,
            },
        )

    advisory = _build_advisory(ctx, source_stage=source_stage)
    if advisory is None:
        return _store_status(
            ctx,
            {
                "schema": "followmom_advisory_summary_v1",
                "phase": "4E-A",
                "status": "idle",
                "authority": "advisory_only",
                "follow_mom_authority": "legacy_bodymap_policy_runtime",
                "legacy_executes": True,
                "map_can_override": False,
                "protected_safety_can_be_overridden": False,
                "history_count": len(getattr(ctx, "navmap_followmom_advisory_history", []) or []),
            },
        )
    return _store_advisory(ctx, advisory)


def followmom_advisory_observation_step_v1(ctx: Any) -> dict[str, Any]:
    """Create provisional Phase 4E-A advice after Phase 4D observation work."""
    return _advisory_step(ctx, source_stage="observation")


def followmom_advisory_selection_step_v1(ctx: Any) -> dict[str, Any]:
    """Finalize Phase 4E-A advice after the legacy candidate set and winner exist."""
    return _advisory_step(ctx, source_stage="selection")


def followmom_advisory_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 4E-A advice."""
    if ctx is None:
        return {
            "schema": "followmom_advisory_summary_v1",
            "phase": "4E-A",
            "status": "ctx_unavailable",
        }

    row = getattr(ctx, "navmap_followmom_advisory_last_update", None)
    history_count = len(getattr(ctx, "navmap_followmom_advisory_history", []) or [])
    if not isinstance(row, dict):
        return {
            "schema": "followmom_advisory_summary_v1",
            "phase": "4E-A",
            "status": "idle",
            "authority": "advisory_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
            "protected_safety_can_be_overridden": False,
            "history_count": history_count,
        }
    if isinstance(row.get("status"), str):
        out = dict(row)
        out["history_count"] = history_count
        return out

    return {
        "schema": "followmom_advisory_summary_v1",
        "phase": "4E-A",
        "status": "active",
        "authority": "advisory_only",
        "follow_mom_authority": "legacy_bodymap_policy_runtime",
        "legacy_executes": True,
        "map_can_override": False,
        "map_can_trigger_follow_mom": False,
        "map_can_suppress_follow_mom": False,
        "protected_safety_can_be_overridden": False,
        "advisory": dict(row),
        "history_count": history_count,
    }


def render_followmom_advisory_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 4E-A advisory lines."""
    summary = followmom_advisory_summary_v1(ctx)
    lines = ["FOLLOWMOM PHASE 4E-A ADVISORY:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle", "disabled", "compare_disabled", "dependency_error", "error"}:
        lines.append(
            "  "
            f"status={status} authority=advisory_only legacy_executes=True "
            "follow_mom_authority=legacy_bodymap_policy_runtime map_can_override=False "
            "protected_safety_can_be_overridden=False"
        )
        if status == "error":
            lines.append(f"  error_type={summary.get('error_type')} error={summary.get('error')}")
        return lines

    advisory = summary.get("advisory")
    advisory = advisory if isinstance(advisory, dict) else {}
    lines.append(
        "  "
        f"tx={advisory.get('transaction_no')} stage={advisory.get('source_stage')} status={status} "
        "authority=advisory_only legacy_executes=True map_can_override=False"
    )
    lines.append(
        "  "
        f"advisory={advisory.get('kind')} severity={advisory.get('severity')} "
        f"scope={advisory.get('scope')} reason={advisory.get('reason')}"
    )
    lines.append(
        "  "
        f"response={advisory.get('recommended_response')} "
        f"fallback_required={advisory.get('fallback_required')} "
        f"fallback_source={advisory.get('fallback_source')}"
    )
    lines.append(
        "  "
        f"map recommendation={advisory.get('map_recommendation')} "
        f"map_reason={advisory.get('map_reason')} source={advisory.get('source_mode')} "
        f"identity={advisory.get('identity_support')} localization={advisory.get('localization_status')}"
    )
    lines.append(
        "  "
        f"relation proximity={advisory.get('proximity')} temporal={advisory.get('temporal_trend')} "
        f"temporal_valid={advisory.get('temporal_valid')} track={advisory.get('track_status')}"
    )
    lines.append(
        "  "
        f"legacy gate={advisory.get('legacy_gate_triggered')} "
        f"candidate={advisory.get('legacy_effective_candidate')} selected={advisory.get('selected_policy')} "
        f"selection_unchanged={advisory.get('legacy_action_unchanged')}"
    )
    lines.append(
        "  "
        f"comparisons gate={advisory.get('gate_comparison')} "
        f"candidate={advisory.get('candidate_comparison')} "
        f"selection={advisory.get('selection_comparison')} "
        f"assessment={advisory.get('disagreement_assessment')}"
    )
    lines.append(
        "  "
        f"flags resample={advisory.get('resample_recommended')} "
        f"legacy_filter_preserved={advisory.get('legacy_filter_preserved')} "
        f"disagreement_review={advisory.get('disagreement_review_recommended')} "
        f"outcome_review={advisory.get('outcome_review_recommended')}"
    )
    if advisory.get("prior_outcome") is not None:
        lines.append(
            "  "
            f"prior_outcome tx={advisory.get('prior_outcome_transaction_no')} "
            f"action={advisory.get('prior_action_applied')} outcome={advisory.get('prior_outcome')} "
            f"reason={advisory.get('prior_outcome_reason')}"
        )
    return lines
