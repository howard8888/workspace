# -*- coding: utf-8 -*-
"""Phase 4D FollowMom map-native compare transaction for CCA8.

Purpose
-------
Phase 4D moves the maternal domain from authority level 2 (shadow-only
geometry, temporal compression, and continuity) to authority level 3
(compare/dual-run) for one narrow behavioral question:

    "Does the current SELF-maternal relation make FollowMom applicable?"

The map path independently combines:

* Phase 4A current common-frame SELF-maternal geometry;
* Phase 4B bounded temporal meaning such as approaching or receding; and
* Phase 4C identity continuity, observability, localization, uncertainty, and
  active-track status.

The result is compared with the existing FollowMom gate, effective candidate
set, and selected policy.  The legacy BodyMap/PolicyRuntime/controller path
continues to select and execute every action.  The map result cannot trigger,
suppress, advise, select, or execute FollowMom in this phase.

Expected successor
------------------
When the map path recommends FollowMom, it creates a compact EXPECTED relation
rather than a complete future-world NavMap.  The expectation is deliberately
modest:

* when separation is far, the next supported relation should show a meaningful
  reduction in SELF-maternal distance or entry into the near range; or
* when Mom is near but receding, the next relation should keep separation near
  or prevent a material increase.

The expected relation is armed only when PolicyRuntime actually selects
``policy:follow_mom``. Phase 4D initially annotates that selection as legacy;
later guarded/default authority may reuse the same pending/outcome seam while
recording the cognitive source that supplied the gate. The next observation
then closes the transaction as ``success``, ``failure``, ``unknown``, or
``not_applied``. Prediction never becomes current truth, and issuing an action
never fabricates its outcome.

Continuity boundary
-------------------
A current exact identity-matched location may support a recommendation.  One
short coasting interval may also support a recommendation when Phase 4C exposes
an explicitly non-authoritative predicted region whose uncertainty is bounded
and whose entire extent is clearly near or far.  Ambiguous correspondence,
identity mismatch, reliable negative evidence, an unlocalized/lost track, or a
region crossing the near/far boundary returns DEFER.  The module never chases a
stale exact coordinate.

Safety and authority boundary
-----------------------------
This comparison intentionally does not duplicate terrain, cliff, posture,
feeding-stage, or other legacy safety gates.  Such disagreements are useful
migration evidence: a map-only FollowMom trigger that the legacy path blocks is
recorded as potentially harmful if it were granted authority, while a map
DO_NOT_FOLLOW result against the permissive legacy fallback is recorded as a
potentially useful over-trigger finding.  These labels are review signals, not
behavioral commands or ground-truth judgments.

The Phase 4D compare transaction itself always states
``authority=compare_only`` and cannot change selection. Its authority-neutral
pending/outcome records may later identify a guarded/default FollowMom source;
that annotation does not grant authority inside this module. BodyMap,
PolicyRuntime execution, protected safety, WorldGraph, environment dynamics,
and lower motor execution remain unchanged.
"""

from __future__ import annotations

# The module keeps the complete Phase 4D transaction, compact expectation,
# bounded histories, outcome comparison, summaries, and renderer together so
# the source/authority boundary remains easy to inspect.
# pylint: disable=duplicate-code
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Optional

from cca8_maternal_continuity import (
    MaternalContinuityShadowStateV1,
    MaternalIdentitySupportV1,
    MaternalLocalizationStatusV1,
    MaternalObservabilityV1,
    MaternalTrackStatusV1,
)
from cca8_maternal_geometry import (
    MaternalGeometryShadowStateV1,
    MaternalProximityV1,
)
from cca8_maternal_temporal import (
    MaternalTemporalShadowStateV1,
    MaternalTemporalTrendV1,
)
from cca8_navmap_kernel import NavMapRefV1, NavProvenanceV1, NavSourceClassV1

__version__ = "0.2.0"

__all__ = [
    "FollowMomMapRecommendationV1",
    "FollowMomExpectationKindV1",
    "FollowMomDisagreementAssessmentV1",
    "FollowMomCompareThresholdsV1",
    "FollowMomExpectedSuccessorV1",
    "FollowMomCompareTransactionV1",
    "FollowMomExpectedPendingV1",
    "FollowMomObservedOutcomeV1",
    "followmom_compare_thresholds_from_ctx_v1",
    "followmom_compare_observation_step_v1",
    "followmom_compare_selection_step_v1",
    "followmom_compare_summary_v1",
    "render_followmom_compare_lines_v1",
    "__version__",
]

_FOLLOW_MOM_POLICY = "policy:follow_mom"
_EXPECTED_RELATION_TYPE = "self_maternal_separation"
_EXPECTED_SOURCE_REF_PREFIX = "behavioral_primitive:follow_mom:phase4d_compare"
_DEFAULT_MINIMUM_DISTANCE_REDUCTION = 0.05
_DEFAULT_MAXIMUM_ALLOWED_DISTANCE_INCREASE = 0.10
_DEFAULT_MAXIMUM_PREDICTED_REGION_RADIUS = 1.00
_DEFAULT_HISTORY_LIMIT = 25


class FollowMomMapRecommendationV1(str, Enum):
    """Map-native Phase 4D applicability result for FollowMom."""

    FOLLOW_MOM = "follow_mom"
    DO_NOT_FOLLOW = "do_not_follow"
    DEFER = "defer"


class FollowMomExpectationKindV1(str, Enum):
    """Compact task-level relation expected after FollowMom is applied."""

    REDUCE_SEPARATION = "reduce_separation"
    REGULATE_NEAR_SEPARATION = "regulate_near_separation"


class FollowMomDisagreementAssessmentV1(str, Enum):
    """Review-oriented interpretation of map versus legacy differences.

    These values describe migration evidence only.  They do not change policy
    selection and do not claim that either path is globally correct.
    """

    AGREEMENT = "agreement"
    POTENTIALLY_USEFUL_LEGACY_OVERTRIGGER = "potentially_useful_legacy_overtrigger"
    POTENTIALLY_HARMFUL_MAP_OVERTRIGGER = "potentially_harmful_map_overtrigger_if_authoritative"
    MAP_DEFERRED_LEGACY_FALLBACK = "map_deferred_legacy_fallback"
    ARBITRATION_DIFFERENCE = "arbitration_difference"
    NOT_COMPARABLE = "not_comparable"


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


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float while rejecting bool and unsupported values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _finite_non_negative_float(value: Any, *, field_name: str) -> float:
    """Return one finite non-negative float."""
    number = _finite_float(value, field_name=field_name)
    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _finite_positive_float(value: Any, *, field_name: str) -> float:
    """Return one finite positive float."""
    number = _finite_float(value, field_name=field_name)
    if number <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return number


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return a JSON-safe optional map reference."""
    return ref.as_dict() if ref is not None else None


@dataclass(frozen=True, slots=True)
class FollowMomCompareThresholdsV1:
    """Explicit deterministic engineering parameters for Phase 4D.

    ``minimum_distance_reduction`` is the smallest exact distance decrease that
    counts as progress after one applied FollowMom step.  A near-regulation
    expectation tolerates at most ``maximum_allowed_distance_increase``.
    Predicted-region recommendations are accepted only while their uncertainty
    radius does not exceed ``maximum_predicted_region_radius``.

    These are inspectable software parameters, not biological constants.
    """

    minimum_distance_reduction: float
    maximum_allowed_distance_increase: float
    maximum_predicted_region_radius: float

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "minimum_distance_reduction",
            _finite_positive_float(
                self.minimum_distance_reduction,
                field_name="minimum_distance_reduction",
            ),
        )
        object.__setattr__(
            self,
            "maximum_allowed_distance_increase",
            _finite_non_negative_float(
                self.maximum_allowed_distance_increase,
                field_name="maximum_allowed_distance_increase",
            ),
        )
        object.__setattr__(
            self,
            "maximum_predicted_region_radius",
            _finite_positive_float(
                self.maximum_predicted_region_radius,
                field_name="maximum_predicted_region_radius",
            ),
        )

    def as_dict(self) -> dict[str, float]:
        """Return a JSON-safe threshold record."""
        return {
            "minimum_distance_reduction": self.minimum_distance_reduction,
            "maximum_allowed_distance_increase": self.maximum_allowed_distance_increase,
            "maximum_predicted_region_radius": self.maximum_predicted_region_radius,
        }


@dataclass(frozen=True, slots=True)
class _FollowMomMapInputV1:
    """Internal source-linked map input used to form one recommendation."""

    observation_no: int
    evidence_map_ref: NavMapRefV1
    stable_map_ref: Optional[NavMapRefV1]
    identity_handle: str
    identity_support: MaternalIdentitySupportV1
    role_retained: bool
    observability: MaternalObservabilityV1
    localization_status: MaternalLocalizationStatusV1
    track_status: MaternalTrackStatusV1
    source_mode: str
    frame_id: str
    units: str
    distance: Optional[float]
    uncertainty_radius: Optional[float]
    proximity: MaternalProximityV1
    near_distance: float
    temporal_trend: MaternalTemporalTrendV1
    temporal_valid: bool
    temporal_support_status: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        if not isinstance(self.evidence_map_ref, NavMapRefV1):
            raise TypeError("evidence_map_ref must be NavMapRefV1")
        if self.stable_map_ref is not None and not isinstance(self.stable_map_ref, NavMapRefV1):
            raise TypeError("stable_map_ref must be NavMapRefV1 or None")
        _require_nonempty_text(self.identity_handle, field_name="identity_handle")
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
        for field_name in ("source_mode", "frame_id", "units", "temporal_support_status"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if self.distance is not None:
            object.__setattr__(self, "distance", _finite_non_negative_float(self.distance, field_name="distance"))
        if self.uncertainty_radius is not None:
            object.__setattr__(
                self,
                "uncertainty_radius",
                _finite_non_negative_float(self.uncertainty_radius, field_name="uncertainty_radius"),
            )
        if not isinstance(self.proximity, MaternalProximityV1):
            raise TypeError("proximity must be MaternalProximityV1")
        object.__setattr__(self, "near_distance", _finite_positive_float(self.near_distance, field_name="near_distance"))
        if not isinstance(self.temporal_trend, MaternalTemporalTrendV1):
            raise TypeError("temporal_trend must be MaternalTemporalTrendV1")
        if not isinstance(self.temporal_valid, bool):
            raise TypeError("temporal_valid must be bool")


@dataclass(frozen=True, slots=True)
class FollowMomExpectedSuccessorV1:
    """One compact EXPECTED SELF-maternal relation after FollowMom.

    The record is not a current observation, accepted WNM, or immutable NavMap
    revision.  It carries the exact source map reference, identity, frame,
    baseline relation, uncertainty, explicit thresholds, and expected source
    provenance needed for later outcome comparison.
    """

    transaction_no: int
    source_observation_no: int
    source_geometry_map_ref: NavMapRefV1
    tracked_identity_handle: str
    frame_id: str
    units: str
    source_mode: str
    source_localization_status: MaternalLocalizationStatusV1
    source_track_status: MaternalTrackStatusV1
    source_distance: float
    source_uncertainty_radius: float
    source_proximity: MaternalProximityV1
    source_temporal_trend: MaternalTemporalTrendV1
    expectation_kind: FollowMomExpectationKindV1
    relation_type: str
    provenance: NavProvenanceV1
    near_distance: float
    thresholds: FollowMomCompareThresholdsV1

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.source_observation_no, field_name="source_observation_no")
        if not isinstance(self.source_geometry_map_ref, NavMapRefV1):
            raise TypeError("source_geometry_map_ref must be NavMapRefV1")
        for field_name in ("tracked_identity_handle", "frame_id", "units", "source_mode", "relation_type"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.source_localization_status, MaternalLocalizationStatusV1):
            raise TypeError("source_localization_status must be MaternalLocalizationStatusV1")
        if not isinstance(self.source_track_status, MaternalTrackStatusV1):
            raise TypeError("source_track_status must be MaternalTrackStatusV1")
        object.__setattr__(self, "source_distance", _finite_non_negative_float(self.source_distance, field_name="source_distance"))
        object.__setattr__(
            self,
            "source_uncertainty_radius",
            _finite_non_negative_float(self.source_uncertainty_radius, field_name="source_uncertainty_radius"),
        )
        if not isinstance(self.source_proximity, MaternalProximityV1):
            raise TypeError("source_proximity must be MaternalProximityV1")
        if not isinstance(self.source_temporal_trend, MaternalTemporalTrendV1):
            raise TypeError("source_temporal_trend must be MaternalTemporalTrendV1")
        if not isinstance(self.expectation_kind, FollowMomExpectationKindV1):
            raise TypeError("expectation_kind must be FollowMomExpectationKindV1")
        if not isinstance(self.provenance, NavProvenanceV1):
            raise TypeError("provenance must be NavProvenanceV1")
        if self.provenance.source_class is not NavSourceClassV1.EXPECTED:
            raise ValueError("FollowMom expected successor requires EXPECTED provenance")
        object.__setattr__(self, "near_distance", _finite_positive_float(self.near_distance, field_name="near_distance"))
        if not isinstance(self.thresholds, FollowMomCompareThresholdsV1):
            raise TypeError("thresholds must be FollowMomCompareThresholdsV1")

    @property
    def source_lower_distance(self) -> float:
        """Return the non-negative lower edge of the source uncertainty band."""
        return max(0.0, self.source_distance - self.source_uncertainty_radius)

    @property
    def source_upper_distance(self) -> float:
        """Return the upper edge of the source uncertainty band."""
        return self.source_distance + self.source_uncertainty_radius

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe, authority-explicit expected relation."""
        return {
            "schema": "followmom_expected_successor_v1",
            "phase": "4D",
            "source_class": "expected",
            "current_truth": False,
            "creates_navmap_revision": False,
            "transaction_no": self.transaction_no,
            "source_observation_no": self.source_observation_no,
            "source_geometry_map_ref": self.source_geometry_map_ref.as_dict(),
            "tracked_identity_handle": self.tracked_identity_handle,
            "frame_id": self.frame_id,
            "units": self.units,
            "source_mode": self.source_mode,
            "source_localization_status": self.source_localization_status.value,
            "source_track_status": self.source_track_status.value,
            "source_distance": self.source_distance,
            "source_uncertainty_radius": self.source_uncertainty_radius,
            "source_lower_distance": self.source_lower_distance,
            "source_upper_distance": self.source_upper_distance,
            "source_proximity": self.source_proximity.value,
            "source_temporal_trend": self.source_temporal_trend.value,
            "expectation_kind": self.expectation_kind.value,
            "relation_type": self.relation_type,
            "provenance": self.provenance.as_dict(),
            "near_distance": self.near_distance,
            "thresholds": self.thresholds.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class FollowMomCompareTransactionV1:
    """One Phase 4D map recommendation plus later legacy comparison."""

    transaction_no: int
    observation_no: int
    evidence_map_ref: NavMapRefV1
    stable_map_ref: Optional[NavMapRefV1]
    tracked_identity_handle: str
    identity_support: MaternalIdentitySupportV1
    role_retained: bool
    observability: MaternalObservabilityV1
    localization_status: MaternalLocalizationStatusV1
    track_status: MaternalTrackStatusV1
    source_mode: str
    distance: Optional[float]
    uncertainty_radius: Optional[float]
    proximity: MaternalProximityV1
    temporal_trend: MaternalTemporalTrendV1
    temporal_valid: bool
    temporal_support_status: str
    map_recommendation: FollowMomMapRecommendationV1
    map_reason: str
    expected_successor: Optional[FollowMomExpectedSuccessorV1]
    legacy_gate_triggered: Optional[bool] = None
    legacy_effective_candidate: Optional[bool] = None
    selected_policy: Optional[str] = None
    gate_comparison: str = "pending"
    candidate_comparison: str = "pending"
    selection_comparison: str = "pending"
    disagreement_assessment: FollowMomDisagreementAssessmentV1 = FollowMomDisagreementAssessmentV1.NOT_COMPARABLE
    pending_expected_armed: bool = False

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if not isinstance(self.evidence_map_ref, NavMapRefV1):
            raise TypeError("evidence_map_ref must be NavMapRefV1")
        if self.stable_map_ref is not None and not isinstance(self.stable_map_ref, NavMapRefV1):
            raise TypeError("stable_map_ref must be NavMapRefV1 or None")
        _require_nonempty_text(self.tracked_identity_handle, field_name="tracked_identity_handle")
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
        for field_name in ("source_mode", "temporal_support_status", "map_reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if self.distance is not None:
            object.__setattr__(self, "distance", _finite_non_negative_float(self.distance, field_name="distance"))
        if self.uncertainty_radius is not None:
            object.__setattr__(
                self,
                "uncertainty_radius",
                _finite_non_negative_float(self.uncertainty_radius, field_name="uncertainty_radius"),
            )
        if not isinstance(self.proximity, MaternalProximityV1):
            raise TypeError("proximity must be MaternalProximityV1")
        if not isinstance(self.temporal_trend, MaternalTemporalTrendV1):
            raise TypeError("temporal_trend must be MaternalTemporalTrendV1")
        if not isinstance(self.temporal_valid, bool):
            raise TypeError("temporal_valid must be bool")
        if not isinstance(self.map_recommendation, FollowMomMapRecommendationV1):
            raise TypeError("map_recommendation must be FollowMomMapRecommendationV1")
        if self.expected_successor is not None and not isinstance(self.expected_successor, FollowMomExpectedSuccessorV1):
            raise TypeError("expected_successor must be FollowMomExpectedSuccessorV1 or None")
        if self.map_recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM:
            if self.expected_successor is None:
                raise ValueError("FOLLOW_MOM recommendation requires expected_successor")
        elif self.expected_successor is not None:
            raise ValueError("only FOLLOW_MOM recommendation may carry expected_successor")
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
        if not isinstance(self.pending_expected_armed, bool):
            raise TypeError("pending_expected_armed must be bool")
        if self.pending_expected_armed:
            if self.selected_policy != _FOLLOW_MOM_POLICY or self.expected_successor is None:
                raise ValueError("pending expectation requires selected FollowMom and an expected successor")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit Phase 4D compare trace."""
        fallback_required = self.map_recommendation is FollowMomMapRecommendationV1.DEFER
        return {
            "schema": "followmom_compare_transaction_v1",
            "phase": "4D",
            "authority_level": "compare_dual_run",
            "authority": "compare_only",
            "legacy_authority": "bodymap_policy_runtime",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
            "map_can_trigger_follow_mom": False,
            "map_can_suppress_follow_mom": False,
            "protected_safety_can_be_overridden": False,
            "execution_source": "legacy_bodymap_policy_runtime",
            "fallback_required": fallback_required,
            "fallback_source": "legacy_bodymap_policy_runtime" if fallback_required else None,
            "behavioral_primitive": "follow_mom",
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "evidence_map_ref": self.evidence_map_ref.as_dict(),
            "stable_map_ref": _optional_ref_dict(self.stable_map_ref),
            "tracked_identity_handle": self.tracked_identity_handle,
            "identity_support": self.identity_support.value,
            "role_retained": self.role_retained,
            "observability": self.observability.value,
            "localization_status": self.localization_status.value,
            "track_status": self.track_status.value,
            "source_mode": self.source_mode,
            "distance": self.distance,
            "uncertainty_radius": self.uncertainty_radius,
            "proximity": self.proximity.value,
            "temporal_trend": self.temporal_trend.value,
            "temporal_valid": self.temporal_valid,
            "temporal_support_status": self.temporal_support_status,
            "map_recommendation": self.map_recommendation.value,
            "map_reason": self.map_reason,
            "expected_successor": self.expected_successor.as_dict() if self.expected_successor is not None else None,
            "legacy_gate_triggered": self.legacy_gate_triggered,
            "legacy_effective_candidate": self.legacy_effective_candidate,
            "selected_policy": self.selected_policy,
            "legacy_selected_follow_mom": self.selected_policy == _FOLLOW_MOM_POLICY,
            "gate_comparison": self.gate_comparison,
            "candidate_comparison": self.candidate_comparison,
            "selection_comparison": self.selection_comparison,
            "disagreement_assessment": self.disagreement_assessment.value,
            "pending_expected_armed": self.pending_expected_armed,
            "creates_navmap_revision": False,
        }


@dataclass(frozen=True, slots=True)
class FollowMomExpectedPendingV1:
    """One compact expected relation armed after selected FollowMom.

    The pending relation is authority-neutral. Phase 4D legacy selection keeps
    the default metadata, while Phase 4F may record WNM/NavMap selection without
    creating a second prediction/outcome mechanism.
    """

    transaction_no: int
    expected_successor: FollowMomExpectedSuccessorV1
    selected_policy: str
    selected_controller_step: int
    selection_phase: str = "4D"
    selection_authority: str = "legacy_bodymap_policy_runtime"
    cognitive_source: str = "legacy_bodymap_policy_runtime"

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor, FollowMomExpectedSuccessorV1):
            raise TypeError("expected_successor must be FollowMomExpectedSuccessorV1")
        if self.selected_policy != _FOLLOW_MOM_POLICY:
            raise ValueError("FollowMom pending expectation requires policy:follow_mom")
        _require_non_negative_int(self.selected_controller_step, field_name="selected_controller_step")
        for field_name in ("selection_phase", "selection_authority", "cognitive_source"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)


@dataclass(frozen=True, slots=True)
class FollowMomObservedOutcomeV1:
    """Observed current relation compared with one applied FollowMom expectation."""

    transaction_no: int
    expected_successor: FollowMomExpectedSuccessorV1
    evidence_map_ref: Optional[NavMapRefV1]
    action_applied: Optional[str]
    outcome: str
    observed_identity_support: MaternalIdentitySupportV1
    observed_observability: MaternalObservabilityV1
    observed_localization_status: MaternalLocalizationStatusV1
    observed_track_status: MaternalTrackStatusV1
    observed_distance: Optional[float]
    observed_proximity: MaternalProximityV1
    observed_temporal_trend: MaternalTemporalTrendV1
    reason: str
    selection_phase: str = "4D"
    selection_authority: str = "legacy_bodymap_policy_runtime"
    cognitive_source: str = "legacy_bodymap_policy_runtime"

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        if not isinstance(self.expected_successor, FollowMomExpectedSuccessorV1):
            raise TypeError("expected_successor must be FollowMomExpectedSuccessorV1")
        if self.evidence_map_ref is not None and not isinstance(self.evidence_map_ref, NavMapRefV1):
            raise TypeError("evidence_map_ref must be NavMapRefV1 or None")
        if self.action_applied is not None and not isinstance(self.action_applied, str):
            raise TypeError("action_applied must be str or None")
        _require_nonempty_text(self.outcome, field_name="outcome")
        if not isinstance(self.observed_identity_support, MaternalIdentitySupportV1):
            raise TypeError("observed_identity_support must be MaternalIdentitySupportV1")
        if not isinstance(self.observed_observability, MaternalObservabilityV1):
            raise TypeError("observed_observability must be MaternalObservabilityV1")
        if not isinstance(self.observed_localization_status, MaternalLocalizationStatusV1):
            raise TypeError("observed_localization_status must be MaternalLocalizationStatusV1")
        if not isinstance(self.observed_track_status, MaternalTrackStatusV1):
            raise TypeError("observed_track_status must be MaternalTrackStatusV1")
        if self.observed_distance is not None:
            object.__setattr__(
                self,
                "observed_distance",
                _finite_non_negative_float(self.observed_distance, field_name="observed_distance"),
            )
        if not isinstance(self.observed_proximity, MaternalProximityV1):
            raise TypeError("observed_proximity must be MaternalProximityV1")
        if not isinstance(self.observed_temporal_trend, MaternalTemporalTrendV1):
            raise TypeError("observed_temporal_trend must be MaternalTemporalTrendV1")
        _require_nonempty_text(self.reason, field_name="reason")
        for field_name in ("selection_phase", "selection_authority", "cognitive_source"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe expected-versus-observed relation outcome."""
        expected = self.expected_successor
        legacy_gate_authoritative = self.cognitive_source in {
            "legacy_bodymap_policy_runtime",
            "legacy_fallback",
            "protected_legacy_veto",
            "legacy_compatibility",
        }
        distance_delta = (
            self.observed_distance - expected.source_distance
            if self.observed_distance is not None
            else None
        )
        residual = {
            "relation_type": expected.relation_type,
            "expectation_kind": expected.expectation_kind.value,
            "source_distance": expected.source_distance,
            "source_uncertainty_radius": expected.source_uncertainty_radius,
            "source_lower_distance": expected.source_lower_distance,
            "source_upper_distance": expected.source_upper_distance,
            "observed_distance": self.observed_distance,
            "distance_delta": distance_delta,
            "near_distance": expected.near_distance,
            "minimum_distance_reduction": expected.thresholds.minimum_distance_reduction,
            "maximum_allowed_distance_increase": expected.thresholds.maximum_allowed_distance_increase,
        }
        return {
            "schema": "followmom_observed_outcome_v1",
            "phase": "4D",
            "authority": "compare_only",
            "comparison_authority": "compare_only",
            "selection_phase": self.selection_phase,
            "follow_mom_authority": self.selection_authority,
            "legacy_gate_authoritative": legacy_gate_authoritative,
            "legacy_executes": True,
            "policy_runtime_executes": True,
            "legacy_primitive_executor_unchanged": True,
            "map_can_override": False,
            "map_can_trigger_follow_mom": False,
            "comparison_module_can_trigger_follow_mom": False,
            "selection_map_can_supply_followmom_gate": self.cognitive_source == "wnm_navmap",
            "selection_map_authority_used": self.cognitive_source == "wnm_navmap",
            "cognitive_source": self.cognitive_source,
            "execution_source": "policy_runtime_action_center",
            "behavioral_primitive": "follow_mom",
            "transaction_no": self.transaction_no,
            "expected_successor": expected.as_dict(),
            "evidence_map_ref": _optional_ref_dict(self.evidence_map_ref),
            "action_applied": self.action_applied,
            "outcome": self.outcome,
            "observed_identity_support": self.observed_identity_support.value,
            "observed_observability": self.observed_observability.value,
            "observed_localization_status": self.observed_localization_status.value,
            "observed_track_status": self.observed_track_status.value,
            "observed_distance": self.observed_distance,
            "observed_proximity": self.observed_proximity.value,
            "observed_temporal_trend": self.observed_temporal_trend.value,
            "relation_residual": residual,
            "reason": self.reason,
            "creates_navmap_revision": False,
        }


def _ctx_float(ctx: Any, name: str, default: float) -> float:
    """Return one finite context float or a deterministic default."""
    value = getattr(ctx, name, default)
    try:
        return _finite_float(value, field_name=name)
    except (TypeError, ValueError):
        return default


def followmom_compare_thresholds_from_ctx_v1(ctx: Any) -> FollowMomCompareThresholdsV1:
    """Return validated Phase 4D thresholds from the runtime context."""
    minimum_reduction = _ctx_float(
        ctx,
        "navmap_followmom_compare_minimum_distance_reduction",
        _DEFAULT_MINIMUM_DISTANCE_REDUCTION,
    )
    maximum_increase = _ctx_float(
        ctx,
        "navmap_followmom_compare_maximum_allowed_distance_increase",
        _DEFAULT_MAXIMUM_ALLOWED_DISTANCE_INCREASE,
    )
    maximum_radius = _ctx_float(
        ctx,
        "navmap_followmom_compare_maximum_predicted_region_radius",
        _DEFAULT_MAXIMUM_PREDICTED_REGION_RADIUS,
    )
    if minimum_reduction <= 0.0:
        minimum_reduction = _DEFAULT_MINIMUM_DISTANCE_REDUCTION
    if maximum_increase < 0.0:
        maximum_increase = _DEFAULT_MAXIMUM_ALLOWED_DISTANCE_INCREASE
    if maximum_radius <= 0.0:
        maximum_radius = _DEFAULT_MAXIMUM_PREDICTED_REGION_RADIUS
    return FollowMomCompareThresholdsV1(
        minimum_distance_reduction=minimum_reduction,
        maximum_allowed_distance_increase=maximum_increase,
        maximum_predicted_region_radius=maximum_radius,
    )


def _next_transaction_no(ctx: Any) -> int:
    """Advance and return the deterministic Phase 4D transaction counter."""
    try:
        current = int(getattr(ctx, "navmap_followmom_compare_transaction_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    transaction_no = max(0, current) + 1
    ctx.navmap_followmom_compare_transaction_no = transaction_no
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


def _temporal_values(
    ctx: Any,
    *,
    observation_no: int,
) -> tuple[MaternalTemporalTrendV1, bool, str]:
    """Return current contiguous Phase 4B trend support for this observation."""
    state = getattr(ctx, "navmap_maternal_temporal_state", None)
    if not isinstance(state, MaternalTemporalShadowStateV1):
        return MaternalTemporalTrendV1.UNKNOWN, False, "unavailable"
    readout = state.readout
    current = readout.window_end_observation_no == observation_no
    if readout.valid and current:
        return readout.trend, True, readout.support_status
    return MaternalTemporalTrendV1.UNKNOWN, False, readout.support_status


def _map_input_from_ctx(ctx: Any) -> tuple[Optional[_FollowMomMapInputV1], str]:
    """Return one source-linked map input or a dependency reason."""
    geometry_state = getattr(ctx, "navmap_maternal_state", None)
    continuity_state = getattr(ctx, "navmap_maternal_continuity_state", None)
    if not isinstance(geometry_state, MaternalGeometryShadowStateV1):
        return None, "phase4a_geometry_state_unavailable"
    if not isinstance(continuity_state, MaternalContinuityShadowStateV1):
        return None, "phase4c_continuity_state_unavailable"
    if continuity_state.observation_no != geometry_state.observation_no:
        return None, "maternal_dependency_observation_mismatch"

    observation_no = geometry_state.observation_no
    trend, temporal_valid, temporal_support = _temporal_values(ctx, observation_no=observation_no)
    readout = geometry_state.evidence_readout
    near_distance = readout.thresholds.near_distance
    evidence_ref = geometry_state.evidence_ref
    stable_ref = geometry_state.stable_ref

    distance: Optional[float] = None
    uncertainty_radius: Optional[float] = None
    proximity = MaternalProximityV1.UNKNOWN
    source_mode = "unavailable"

    distance_readout = readout.distance
    exact_supported = bool(  # pylint: disable=too-many-boolean-expressions
        continuity_state.identity_support is MaternalIdentitySupportV1.SUPPORTED
        and continuity_state.role_retained
        and continuity_state.observability is MaternalObservabilityV1.OBSERVED
        and continuity_state.localization_status is MaternalLocalizationStatusV1.CURRENT_EXACT
        and continuity_state.track_status is MaternalTrackStatusV1.ACTIVE
        and continuity_state.localization_authoritative
        and continuity_state.current_location is not None
        and readout.valid
        and distance_readout is not None
    )
    if exact_supported and distance_readout is not None:
        source_mode = "current_exact"
        distance = distance_readout.value
        uncertainty_radius = 0.0
        proximity = readout.proximity
    else:
        region = continuity_state.predicted_region
        predicted_supported = bool(
            continuity_state.identity_support is MaternalIdentitySupportV1.RETAINED
            and continuity_state.role_retained
            and continuity_state.localization_status is MaternalLocalizationStatusV1.PREDICTED_REGION
            and continuity_state.track_status is MaternalTrackStatusV1.COASTING
            and region is not None
        )
        if predicted_supported and region is not None:
            source_mode = "predicted_region"
            distance = math.hypot(region.center.x, region.center.y)
            uncertainty_radius = region.radius
            lower = max(0.0, distance - region.radius)
            upper = distance + region.radius
            if lower > near_distance:
                proximity = MaternalProximityV1.FAR
            elif upper <= near_distance:
                proximity = MaternalProximityV1.NEAR

    return (
        _FollowMomMapInputV1(
            observation_no=observation_no,
            evidence_map_ref=evidence_ref,
            stable_map_ref=stable_ref,
            identity_handle=continuity_state.tracked_identity_handle,
            identity_support=continuity_state.identity_support,
            role_retained=continuity_state.role_retained,
            observability=continuity_state.observability,
            localization_status=continuity_state.localization_status,
            track_status=continuity_state.track_status,
            source_mode=source_mode,
            frame_id=continuity_state.frame_id,
            units=continuity_state.units,
            distance=distance,
            uncertainty_radius=uncertainty_radius,
            proximity=proximity,
            near_distance=near_distance,
            temporal_trend=trend,
            temporal_valid=temporal_valid,
            temporal_support_status=temporal_support,
        ),
        "available",
    )


def _map_recommendation(
    map_input: _FollowMomMapInputV1,
    *,
    thresholds: FollowMomCompareThresholdsV1,
) -> tuple[FollowMomMapRecommendationV1, str, Optional[FollowMomExpectationKindV1]]:
    """Return the narrow geometry/temporal/continuity FollowMom result."""
    if not map_input.role_retained:
        return FollowMomMapRecommendationV1.DEFER, "maternal_role_not_retained", None
    if map_input.identity_support in {
        MaternalIdentitySupportV1.MISMATCH,
        MaternalIdentitySupportV1.AMBIGUOUS,
        MaternalIdentitySupportV1.UNINITIALIZED,
    }:
        return FollowMomMapRecommendationV1.DEFER, f"identity_{map_input.identity_support.value}", None
    if map_input.observability is MaternalObservabilityV1.NEGATIVE_EXPECTED_LOCATION:
        return FollowMomMapRecommendationV1.DEFER, "reliable_negative_location_evidence", None
    if map_input.track_status in {
        MaternalTrackStatusV1.LOST,
        MaternalTrackStatusV1.UNLOCALIZED,
        MaternalTrackStatusV1.IDENTITY_MISMATCH,
        MaternalTrackStatusV1.AMBIGUOUS,
        MaternalTrackStatusV1.UNINITIALIZED,
    }:
        return FollowMomMapRecommendationV1.DEFER, f"track_{map_input.track_status.value}", None
    if map_input.distance is None:
        return FollowMomMapRecommendationV1.DEFER, "localization_distance_unavailable", None

    if map_input.source_mode == "predicted_region":
        if map_input.observability is not MaternalObservabilityV1.OCCLUDED:
            return (
                FollowMomMapRecommendationV1.DEFER,
                f"predicted_region_requires_explicit_occlusion_{map_input.observability.value}",
                None,
            )
        radius = map_input.uncertainty_radius
        if radius is None:
            return FollowMomMapRecommendationV1.DEFER, "predicted_region_uncertainty_unavailable", None
        if radius > thresholds.maximum_predicted_region_radius:
            return FollowMomMapRecommendationV1.DEFER, "predicted_region_uncertainty_exceeds_limit", None
        lower = max(0.0, map_input.distance - radius)
        upper = map_input.distance + radius
        if lower > map_input.near_distance:
            return (
                FollowMomMapRecommendationV1.FOLLOW_MOM,
                "bounded_coasting_region_entirely_far",
                FollowMomExpectationKindV1.REDUCE_SEPARATION,
            )
        if upper <= map_input.near_distance:
            return FollowMomMapRecommendationV1.DO_NOT_FOLLOW, "bounded_coasting_region_entirely_near", None
        return FollowMomMapRecommendationV1.DEFER, "predicted_region_crosses_near_far_boundary", None

    if map_input.source_mode != "current_exact":
        return FollowMomMapRecommendationV1.DEFER, "current_or_bounded_predicted_localization_unavailable", None

    if map_input.proximity is MaternalProximityV1.FAR:
        if map_input.temporal_valid and map_input.temporal_trend is MaternalTemporalTrendV1.APPROACHING:
            return FollowMomMapRecommendationV1.DO_NOT_FOLLOW, "far_but_separation_already_approaching", None
        return (
            FollowMomMapRecommendationV1.FOLLOW_MOM,
            "current_exact_far_without_supported_approach",
            FollowMomExpectationKindV1.REDUCE_SEPARATION,
        )

    if map_input.proximity in {MaternalProximityV1.NEAR, MaternalProximityV1.TOUCHING}:
        if map_input.temporal_valid and map_input.temporal_trend is MaternalTemporalTrendV1.RECEDING:
            return (
                FollowMomMapRecommendationV1.FOLLOW_MOM,
                "near_but_separation_receding",
                FollowMomExpectationKindV1.REGULATE_NEAR_SEPARATION,
            )
        return FollowMomMapRecommendationV1.DO_NOT_FOLLOW, "near_separation_not_receding", None

    return FollowMomMapRecommendationV1.DEFER, "geometry_proximity_unknown", None


def _expected_provenance(transaction_no: int) -> NavProvenanceV1:
    """Return explicit EXPECTED provenance for one Phase 4D transaction."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.EXPECTED,
        source_ref=f"{_EXPECTED_SOURCE_REF_PREFIX}:{transaction_no}",
        quality=0.70,
    )


def _expected_successor(
    map_input: _FollowMomMapInputV1,
    *,
    transaction_no: int,
    expectation_kind: FollowMomExpectationKindV1,
    thresholds: FollowMomCompareThresholdsV1,
) -> FollowMomExpectedSuccessorV1:
    """Build one compact expected relation from an actionable map input."""
    if map_input.distance is None:
        raise ValueError("expected successor requires source distance")
    return FollowMomExpectedSuccessorV1(
        transaction_no=transaction_no,
        source_observation_no=map_input.observation_no,
        source_geometry_map_ref=map_input.evidence_map_ref,
        tracked_identity_handle=map_input.identity_handle,
        frame_id=map_input.frame_id,
        units=map_input.units,
        source_mode=map_input.source_mode,
        source_localization_status=map_input.localization_status,
        source_track_status=map_input.track_status,
        source_distance=map_input.distance,
        source_uncertainty_radius=map_input.uncertainty_radius or 0.0,
        source_proximity=map_input.proximity,
        source_temporal_trend=map_input.temporal_trend,
        expectation_kind=expectation_kind,
        relation_type=_EXPECTED_RELATION_TYPE,
        provenance=_expected_provenance(transaction_no),
        near_distance=map_input.near_distance,
        thresholds=thresholds,
    )


def _gate_comparison(
    recommendation: FollowMomMapRecommendationV1,
    legacy_gate_triggered: Optional[bool],
) -> str:
    """Compare the map query with the original FollowMom gate result."""
    if legacy_gate_triggered is None:
        return "legacy_gate_unavailable"
    if recommendation is FollowMomMapRecommendationV1.DEFER:
        return "map_deferred_legacy_trigger" if legacy_gate_triggered else "map_deferred_legacy_no"
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM:
        return "agree_follow_trigger" if legacy_gate_triggered else "disagree_map_follow_legacy_no_trigger"
    return "agree_do_not_follow" if not legacy_gate_triggered else "disagree_map_do_not_follow_legacy_trigger"


def _candidate_comparison(
    recommendation: FollowMomMapRecommendationV1,
    legacy_effective_candidate: Optional[bool],
) -> str:
    """Compare the map query with the effective post-filter legacy candidate set."""
    if legacy_effective_candidate is None:
        return "legacy_candidate_unavailable"
    if recommendation is FollowMomMapRecommendationV1.DEFER:
        return "map_deferred_legacy_candidate" if legacy_effective_candidate else "map_deferred_legacy_not_candidate"
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM:
        return "agree_follow_candidate" if legacy_effective_candidate else "disagree_map_follow_legacy_blocked"
    return (
        "agree_do_not_follow_not_candidate"
        if not legacy_effective_candidate
        else "disagree_map_do_not_follow_legacy_candidate"
    )


def _selection_comparison(
    recommendation: FollowMomMapRecommendationV1,
    selected_policy: Optional[str],
) -> str:
    """Compare the map recommendation with the legacy controller winner."""
    selected_follow = selected_policy == _FOLLOW_MOM_POLICY
    if recommendation is FollowMomMapRecommendationV1.DEFER:
        return "map_deferred_follow_selected" if selected_follow else "map_deferred"
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM:
        return "agree_follow_selected" if selected_follow else "map_follow_not_selected"
    return "disagree_follow_selected" if selected_follow else "agree_do_not_follow_not_selected"


def _disagreement_assessment(
    recommendation: FollowMomMapRecommendationV1,
    legacy_effective_candidate: Optional[bool],
    selected_policy: Optional[str],
) -> FollowMomDisagreementAssessmentV1:
    """Return a conservative review label for map/legacy differences."""
    if legacy_effective_candidate is None:
        return FollowMomDisagreementAssessmentV1.NOT_COMPARABLE
    if recommendation is FollowMomMapRecommendationV1.DEFER:
        if legacy_effective_candidate or selected_policy == _FOLLOW_MOM_POLICY:
            return FollowMomDisagreementAssessmentV1.MAP_DEFERRED_LEGACY_FALLBACK
        return FollowMomDisagreementAssessmentV1.NOT_COMPARABLE
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM and not legacy_effective_candidate:
        return FollowMomDisagreementAssessmentV1.POTENTIALLY_HARMFUL_MAP_OVERTRIGGER
    if recommendation is FollowMomMapRecommendationV1.DO_NOT_FOLLOW and legacy_effective_candidate:
        return FollowMomDisagreementAssessmentV1.POTENTIALLY_USEFUL_LEGACY_OVERTRIGGER
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM and selected_policy not in {None, _FOLLOW_MOM_POLICY}:
        return FollowMomDisagreementAssessmentV1.ARBITRATION_DIFFERENCE
    return FollowMomDisagreementAssessmentV1.AGREEMENT


def _evaluate_expected_outcome(
    expected: FollowMomExpectedSuccessorV1,
    map_input: _FollowMomMapInputV1,
) -> tuple[str, str]:
    """Compare one expected relation with current exact identity-matched evidence."""
    exact_current = bool(
        map_input.source_mode == "current_exact"
        and map_input.identity_support is MaternalIdentitySupportV1.SUPPORTED
        and map_input.localization_status is MaternalLocalizationStatusV1.CURRENT_EXACT
        and map_input.track_status is MaternalTrackStatusV1.ACTIVE
        and map_input.distance is not None
    )
    if not exact_current or map_input.distance is None:
        return "unknown", "current_exact_identity_matched_localization_unavailable"

    observed_distance = map_input.distance
    if expected.expectation_kind is FollowMomExpectationKindV1.REDUCE_SEPARATION:
        if observed_distance <= expected.near_distance:
            return "success", "observed_relation_entered_near_range"
        if expected.source_uncertainty_radius > 0.0:
            success_limit = max(
                0.0,
                expected.source_lower_distance - expected.thresholds.minimum_distance_reduction,
            )
            failure_limit = (
                expected.source_upper_distance + expected.thresholds.maximum_allowed_distance_increase
            )
            if observed_distance <= success_limit:
                return "success", "observed_separation_reduced_beyond_predicted_uncertainty_band"
            if observed_distance > failure_limit:
                return "failure", "observed_separation_increased_beyond_predicted_uncertainty_band"
            return "unknown", "observed_distance_remains_within_source_uncertainty_band"

        reduction = expected.source_distance - observed_distance
        if reduction >= expected.thresholds.minimum_distance_reduction:
            return "success", "observed_separation_reduced"
        return "failure", "observed_separation_not_reduced"

    allowed = expected.source_distance + expected.thresholds.maximum_allowed_distance_increase
    if observed_distance <= expected.near_distance:
        return "success", "observed_relation_remains_near"
    if observed_distance <= allowed:
        return "success", "observed_separation_regulated_within_allowed_increase"
    return "failure", "observed_near_separation_increased_beyond_allowed_limit"


def _finalize_pending_expectation(
    ctx: Any,
    *,
    applied_policy: Optional[str],
    map_input: Optional[_FollowMomMapInputV1],
) -> Optional[FollowMomObservedOutcomeV1]:
    """Close one armed expected relation against the current observation."""
    pending = getattr(ctx, "navmap_followmom_compare_pending", None)
    if not isinstance(pending, FollowMomExpectedPendingV1):
        return None

    expected = pending.expected_successor
    outcome: str
    reason: str
    evidence_ref: Optional[NavMapRefV1]
    identity_support: MaternalIdentitySupportV1
    observability: MaternalObservabilityV1
    localization_status: MaternalLocalizationStatusV1
    track_status: MaternalTrackStatusV1
    observed_distance: Optional[float]
    observed_proximity: MaternalProximityV1
    observed_trend: MaternalTemporalTrendV1

    if applied_policy != _FOLLOW_MOM_POLICY:
        outcome = "not_applied"
        reason = "armed_followmom_was_not_the_applied_action"
    elif map_input is None:
        outcome = "unknown"
        reason = "maternal_map_dependencies_unavailable"
    elif map_input.identity_handle != expected.tracked_identity_handle:
        outcome = "unknown"
        reason = "tracked_maternal_identity_changed"
    else:
        outcome, reason = _evaluate_expected_outcome(expected, map_input)

    if map_input is None:
        evidence_ref = None
        identity_support = MaternalIdentitySupportV1.UNINITIALIZED
        observability = MaternalObservabilityV1.UNAVAILABLE
        localization_status = MaternalLocalizationStatusV1.UNKNOWN
        track_status = MaternalTrackStatusV1.UNINITIALIZED
        observed_distance = None
        observed_proximity = MaternalProximityV1.UNKNOWN
        observed_trend = MaternalTemporalTrendV1.UNKNOWN
    else:
        evidence_ref = map_input.evidence_map_ref
        identity_support = map_input.identity_support
        observability = map_input.observability
        localization_status = map_input.localization_status
        track_status = map_input.track_status
        observed_distance = map_input.distance if map_input.source_mode == "current_exact" else None
        observed_proximity = map_input.proximity if observed_distance is not None else MaternalProximityV1.UNKNOWN
        observed_trend = map_input.temporal_trend

    result = FollowMomObservedOutcomeV1(
        transaction_no=pending.transaction_no,
        expected_successor=expected,
        evidence_map_ref=evidence_ref,
        action_applied=applied_policy,
        outcome=outcome,
        observed_identity_support=identity_support,
        observed_observability=observability,
        observed_localization_status=localization_status,
        observed_track_status=track_status,
        observed_distance=observed_distance,
        observed_proximity=observed_proximity,
        observed_temporal_trend=observed_trend,
        reason=reason,
        selection_phase=pending.selection_phase,
        selection_authority=pending.selection_authority,
        cognitive_source=pending.cognitive_source,
    )
    ctx.navmap_followmom_compare_pending = None
    ctx.navmap_followmom_compare_last_outcome = result
    row = result.as_dict()
    ctx.navmap_followmom_compare_last_outcome_update = dict(row)
    _append_dict_history(
        ctx,
        field_name="navmap_followmom_compare_outcome_history",
        limit_field_name="navmap_followmom_compare_outcome_history_limit",
        row=row,
    )
    return result


def _update_summary(ctx: Any) -> dict[str, Any]:
    """Refresh and return the combined latest Phase 4D summary."""
    transaction = getattr(ctx, "navmap_followmom_compare_transaction", None)
    outcome = getattr(ctx, "navmap_followmom_compare_last_outcome", None)
    summary = {
        "schema": "followmom_compare_summary_v1",
        "phase": "4D",
        "authority_level": "compare_dual_run",
        "authority": "compare_only",
        "legacy_authority": "bodymap_policy_runtime",
        "follow_mom_authority": "legacy_bodymap_policy_runtime",
        "legacy_executes": True,
        "map_can_override": False,
        "map_can_trigger_follow_mom": False,
        "map_can_suppress_follow_mom": False,
        "execution_source": "legacy_bodymap_policy_runtime",
        "status": "active" if isinstance(transaction, FollowMomCompareTransactionV1) else "idle",
        "transaction": transaction.as_dict() if isinstance(transaction, FollowMomCompareTransactionV1) else None,
        "observed_outcome": outcome.as_dict() if isinstance(outcome, FollowMomObservedOutcomeV1) else None,
        "pending_expected": isinstance(getattr(ctx, "navmap_followmom_compare_pending", None), FollowMomExpectedPendingV1),
        "transaction_history_count": len(getattr(ctx, "navmap_followmom_compare_history", []) or []),
        "outcome_history_count": len(getattr(ctx, "navmap_followmom_compare_outcome_history", []) or []),
    }
    ctx.navmap_followmom_compare_last_update = dict(summary)
    return summary


def followmom_compare_observation_step_v1(
    ctx: Any,
    *,
    applied_policy: Optional[str] = None,
) -> dict[str, Any]:
    """Finalize a prior expectation and create the current Phase 4D query.

    This function must run after Phase 4A, 4B, and 4C have processed the current
    observation.  It reads only ctx-local map/temporal/continuity records.  It
    never writes BodyMap, WorldGraph, PolicyRuntime, environment, or selection
    state.
    """
    if ctx is None:
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "ctx_unavailable",
            "authority": "compare_only",
        }
    if not bool(getattr(ctx, "navmap_followmom_compare_enabled", True)):
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "disabled",
            "authority": "compare_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
        }

    map_input, dependency_reason = _map_input_from_ctx(ctx)
    _finalize_pending_expectation(
        ctx,
        applied_policy=applied_policy if isinstance(applied_policy, str) else None,
        map_input=map_input,
    )

    if map_input is None:
        ctx.navmap_followmom_compare_transaction = None
        summary = _update_summary(ctx)
        summary["dependency_reason"] = dependency_reason
        ctx.navmap_followmom_compare_last_update = dict(summary)
        return summary

    thresholds = followmom_compare_thresholds_from_ctx_v1(ctx)
    transaction_no = _next_transaction_no(ctx)
    recommendation, reason, expectation_kind = _map_recommendation(
        map_input,
        thresholds=thresholds,
    )
    expected: Optional[FollowMomExpectedSuccessorV1] = None
    if recommendation is FollowMomMapRecommendationV1.FOLLOW_MOM and expectation_kind is not None:
        expected = _expected_successor(
            map_input,
            transaction_no=transaction_no,
            expectation_kind=expectation_kind,
            thresholds=thresholds,
        )

    transaction = FollowMomCompareTransactionV1(
        transaction_no=transaction_no,
        observation_no=map_input.observation_no,
        evidence_map_ref=map_input.evidence_map_ref,
        stable_map_ref=map_input.stable_map_ref,
        tracked_identity_handle=map_input.identity_handle,
        identity_support=map_input.identity_support,
        role_retained=map_input.role_retained,
        observability=map_input.observability,
        localization_status=map_input.localization_status,
        track_status=map_input.track_status,
        source_mode=map_input.source_mode,
        distance=map_input.distance,
        uncertainty_radius=map_input.uncertainty_radius,
        proximity=map_input.proximity,
        temporal_trend=map_input.temporal_trend,
        temporal_valid=map_input.temporal_valid,
        temporal_support_status=map_input.temporal_support_status,
        map_recommendation=recommendation,
        map_reason=reason,
        expected_successor=expected,
    )
    ctx.navmap_followmom_compare_transaction = transaction
    return _update_summary(ctx)


def followmom_compare_selection_step_v1(
    ctx: Any,
    *,
    legacy_gate_triggered: Optional[bool],
    legacy_effective_candidate: Optional[bool],
    selected_policy: Optional[str],
) -> dict[str, Any]:
    """Record the legacy FollowMom gate/candidate/winner without changing it."""
    if ctx is None:
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "ctx_unavailable",
            "authority": "compare_only",
        }
    if not bool(getattr(ctx, "navmap_followmom_compare_enabled", True)):
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "disabled",
            "authority": "compare_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
        }

    transaction = getattr(ctx, "navmap_followmom_compare_transaction", None)
    if not isinstance(transaction, FollowMomCompareTransactionV1):
        return _update_summary(ctx)

    gate_value = legacy_gate_triggered if isinstance(legacy_gate_triggered, bool) else None
    candidate_value = legacy_effective_candidate if isinstance(legacy_effective_candidate, bool) else None
    policy_value = selected_policy if isinstance(selected_policy, str) and selected_policy else None
    arm_pending = policy_value == _FOLLOW_MOM_POLICY and transaction.expected_successor is not None
    updated = replace(
        transaction,
        legacy_gate_triggered=gate_value,
        legacy_effective_candidate=candidate_value,
        selected_policy=policy_value,
        gate_comparison=_gate_comparison(transaction.map_recommendation, gate_value),
        candidate_comparison=_candidate_comparison(transaction.map_recommendation, candidate_value),
        selection_comparison=_selection_comparison(transaction.map_recommendation, policy_value),
        disagreement_assessment=_disagreement_assessment(
            transaction.map_recommendation,
            candidate_value,
            policy_value,
        ),
        pending_expected_armed=arm_pending,
    )
    ctx.navmap_followmom_compare_transaction = updated

    if arm_pending and updated.expected_successor is not None:
        try:
            controller_step = int(getattr(ctx, "controller_steps", 0) or 0)
        except (TypeError, ValueError):
            controller_step = 0
        ctx.navmap_followmom_compare_pending = FollowMomExpectedPendingV1(
            transaction_no=updated.transaction_no,
            expected_successor=updated.expected_successor,
            selected_policy=_FOLLOW_MOM_POLICY,
            selected_controller_step=max(0, controller_step),
        )

    row = updated.as_dict()
    _append_dict_history(
        ctx,
        field_name="navmap_followmom_compare_history",
        limit_field_name="navmap_followmom_compare_history_limit",
        row=row,
    )
    return _update_summary(ctx)


def followmom_compare_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 4D state."""
    if ctx is None:
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_followmom_compare_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "followmom_compare_summary_v1",
            "phase": "4D",
            "status": "idle",
            "authority": "compare_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "legacy_executes": True,
            "map_can_override": False,
        }
    return dict(row)


def _ref_text(value: Any) -> str:
    """Render one optional JSON map reference."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id', '?')}@r{value.get('revision', '?')}"


def _float_text(value: Any, *, digits: int = 3) -> str:
    """Return one compact finite float string or ``unknown``."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    number = float(value)
    if not math.isfinite(number):
        return "unknown"
    return f"{number:.{digits}f}"


def render_followmom_compare_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 4D compare lines."""
    summary = followmom_compare_summary_v1(ctx)
    lines = ["FOLLOWMOM PHASE 4D COMPARE:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle", "disabled", "error"}:
        lines.append(
            "  "
            f"status={status} authority=compare_only legacy_executes=True "
            "follow_mom_authority=legacy_bodymap_policy_runtime "
            "map_can_override=False map_can_trigger_follow_mom=False"
        )
        if status == "error":
            lines.append(f"  error_type={summary.get('error_type')} error={summary.get('error')}")
        return lines

    transaction = summary.get("transaction")
    transaction = transaction if isinstance(transaction, dict) else {}
    lines.append(
        "  "
        f"tx={transaction.get('transaction_no')} authority=compare_only legacy_executes=True "
        "follow_mom_authority=legacy_bodymap_policy_runtime "
        "map_can_override=False map_can_trigger_follow_mom=False"
    )
    lines.append(
        "  "
        f"source={transaction.get('source_mode')} evidence={_ref_text(transaction.get('evidence_map_ref'))} "
        f"identity={transaction.get('identity_support')} role_retained={transaction.get('role_retained')} "
        f"observability={transaction.get('observability')} track={transaction.get('track_status')}"
    )
    lines.append(
        "  "
        f"distance={_float_text(transaction.get('distance'))} "
        f"uncertainty={_float_text(transaction.get('uncertainty_radius'))} "
        f"proximity={transaction.get('proximity')} temporal={transaction.get('temporal_trend')} "
        f"temporal_valid={transaction.get('temporal_valid')}"
    )
    lines.append(
        "  "
        f"recommendation={transaction.get('map_recommendation')} reason={transaction.get('map_reason')} "
        f"fallback_required={transaction.get('fallback_required')}"
    )
    expected = transaction.get("expected_successor")
    expected = expected if isinstance(expected, dict) else {}
    lines.append(
        "  "
        f"expected={expected.get('expectation_kind', 'none')} relation={expected.get('relation_type', 'none')} "
        f"source_distance={_float_text(expected.get('source_distance'))} current_truth=False"
    )
    lines.append(
        "  "
        f"legacy gate={transaction.get('legacy_gate_triggered')} "
        f"candidate={transaction.get('legacy_effective_candidate')} selected={transaction.get('selected_policy')} "
        f"gate_comparison={transaction.get('gate_comparison')} "
        f"candidate_comparison={transaction.get('candidate_comparison')}"
    )
    lines.append(
        "  "
        f"selection_comparison={transaction.get('selection_comparison')} "
        f"assessment={transaction.get('disagreement_assessment')} "
        f"pending_expected={summary.get('pending_expected')}"
    )

    outcome = summary.get("observed_outcome")
    if isinstance(outcome, dict):
        residual = outcome.get("relation_residual")
        residual = residual if isinstance(residual, dict) else {}
        lines.append(
            "  "
            f"observed tx={outcome.get('transaction_no')} action={outcome.get('action_applied')} "
            f"outcome={outcome.get('outcome')} observed_distance={_float_text(outcome.get('observed_distance'))} "
            f"delta={_float_text(residual.get('distance_delta'))} reason={outcome.get('reason')}"
        )
    return lines
