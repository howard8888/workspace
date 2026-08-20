# -*- coding: utf-8 -*-
"""Phase 4C maternal identity-continuity and localization shadow for CCA8.

Purpose
-------
Phase 4C separates the continuing maternal individual and learned maternal role
from current observability, exact localization, motion support, and active-track
status.  The first bounded external continuity record proves that:

* a missing maternal position does not delete maternal identity or role;
* an exact current coordinate is never fabricated from a last-known point;
* a short unsupported interval may retain a widening, explicitly predicted
  region, after which the active localization track becomes unlocalized/lost;
* compatible reappearance reacquires the same identity rather than creating a
  new maternal individual;
* a different or ambiguous identity does not inherit the maternal role, prior
  localization track, or prior temporal trajectory; and
* reliable negative evidence at an expected visible location is stronger than
  an ordinary missing packet while still not deleting identity or role.

Representation boundary
-----------------------
The record is an external live continuity/localization overlay.  It is not a
new immutable NavMap revision, a second world model, a full Bayesian tracker, a
physics engine, or long-term identity memory.  It consumes the existing Phase
4A SELF-maternal geometry state and, when supported, the compact Phase 4B
Sequential/Temporal readout.  A predicted region is a bounded diagnostic prior,
not current sensory truth.

Current environment limitation
------------------------------
The ordinary CCA8 environment currently exposes current maternal position or a
generic unavailable/blackout condition.  It does not yet provide native visual
occluder geometry, field-of-view semantics, or explicit inspection of an empty
expected location.  This module therefore maps the current blackout metadata to
``sensor_dropout`` and accepts optional deterministic inspection metadata for
``occluded``, ``out_of_field``, identity substitution/ambiguity, and reliable
negative evidence.  Those optional fields make the architectural distinctions
testable without claiming that the current environment already senses them.

Authority boundary
------------------
All public traces state ``authority=shadow_only`` and
``map_can_trigger_follow_mom=False``.  BodyMap, PolicyRuntime, protected safety,
and FollowMom selection/execution remain unchanged.
"""

from __future__ import annotations

# This self-contained migration slice intentionally keeps its immutable record,
# bounded update transaction, projection helper, summaries, and renderer in one
# focused module so the identity/localization and authority boundaries remain
# inspectable.
# pylint: disable=duplicate-code
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional

from cca8_env import EnvObservation
from cca8_maternal_geometry import MaternalGeometryShadowStateV1
from cca8_maternal_temporal import MaternalTemporalShadowStateV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1, element_centroid

__version__ = "0.1.0"

__all__ = [
    "MaternalObservabilityV1",
    "MaternalIdentitySupportV1",
    "MaternalExistenceStatusV1",
    "MaternalLocalizationStatusV1",
    "MaternalTrackStatusV1",
    "MaternalReacquisitionV1",
    "MaternalContinuityThresholdsV1",
    "MaternalPredictedRegionV1",
    "MaternalContinuityShadowStateV1",
    "maternal_continuity_thresholds_from_ctx_v1",
    "maternal_continuity_shadow_observation_step_v1",
    "maternal_continuity_shadow_summary_v1",
    "render_maternal_continuity_shadow_lines_v1",
    "__version__",
]

_MATERNAL_ROLE_RELATION = "maternal_caregiver_of"
_DEFAULT_MAX_COAST_MISSING_OBSERVATIONS = 1
_DEFAULT_MAX_UNLOCALIZED_MISSING_OBSERVATIONS = 2
_DEFAULT_INITIAL_UNCERTAINTY_RADIUS = 0.25
_DEFAULT_UNCERTAINTY_GROWTH_PER_TIME = 0.50
_DEFAULT_MAXIMUM_UNCERTAINTY_RADIUS = 5.0
_DEFAULT_HISTORY_LIMIT = 25
_MINIMUM_TIME_DELTA = 1.0e-9


class MaternalObservabilityV1(str, Enum):
    """Why current maternal localization evidence is or is not available."""

    OBSERVED = "observed"
    SENSOR_DROPOUT = "sensor_dropout"
    OCCLUDED = "occluded"
    OUT_OF_FIELD = "out_of_field"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"
    NEGATIVE_EXPECTED_LOCATION = "negative_expected_location"


class MaternalIdentitySupportV1(str, Enum):
    """Current support for correspondence with the tracked maternal identity."""

    SUPPORTED = "supported"
    RETAINED = "retained"
    MISMATCH = "mismatch"
    AMBIGUOUS = "ambiguous"
    UNINITIALIZED = "uninitialized"


class MaternalExistenceStatusV1(str, Enum):
    """Bounded continued-existence hypothesis for the tracked individual."""

    OBSERVED = "observed"
    PRESUMED_CONTINUING = "presumed_continuing"
    UNCERTAIN = "uncertain"
    UNKNOWN = "unknown"


class MaternalLocalizationStatusV1(str, Enum):
    """Current status of the tracked maternal individual's localization."""

    CURRENT_EXACT = "current_exact"
    PREDICTED_REGION = "predicted_region"
    UNLOCALIZED = "unlocalized"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class MaternalTrackStatusV1(str, Enum):
    """Bounded active-track lifecycle independent of identity persistence."""

    ACTIVE = "active"
    COASTING = "coasting"
    UNLOCALIZED = "unlocalized"
    LOST = "lost"
    IDENTITY_MISMATCH = "identity_mismatch"
    AMBIGUOUS = "ambiguous"
    UNINITIALIZED = "uninitialized"


class MaternalReacquisitionV1(str, Enum):
    """How the current observation relates to the prior maternal track."""

    INITIAL_ACQUISITION = "initial_acquisition"
    CONTINUING_TRACK = "continuing_track"
    REACQUIRED = "reacquired"
    NOT_OBSERVED = "not_observed"
    IDENTITY_MISMATCH = "identity_mismatch"
    AMBIGUOUS = "ambiguous"


@dataclass(frozen=True, slots=True)
class MaternalContinuityThresholdsV1:
    """Explicit bounded engineering parameters for Phase 4C.

    The thresholds are transparent simulation settings, not biological
    constants.  ``max_coast_missing_observations`` defines the brief interval in
    which the active track is coasting.  The track then becomes unlocalized and
    finally lost after ``max_unlocalized_missing_observations``.  Region radii
    widen monotonically and are capped independently of identity persistence.
    """

    max_coast_missing_observations: int
    max_unlocalized_missing_observations: int
    initial_uncertainty_radius: float
    uncertainty_growth_per_time: float
    maximum_uncertainty_radius: float

    def __post_init__(self) -> None:
        _require_non_negative_int(
            self.max_coast_missing_observations,
            field_name="max_coast_missing_observations",
        )
        _require_positive_int(
            self.max_unlocalized_missing_observations,
            field_name="max_unlocalized_missing_observations",
        )
        if self.max_unlocalized_missing_observations < self.max_coast_missing_observations:
            raise ValueError("max_unlocalized_missing_observations cannot be smaller than max_coast_missing_observations")
        initial = _finite_non_negative_float(self.initial_uncertainty_radius, field_name="initial_uncertainty_radius")
        growth = _finite_non_negative_float(self.uncertainty_growth_per_time, field_name="uncertainty_growth_per_time")
        maximum = _finite_positive_float(self.maximum_uncertainty_radius, field_name="maximum_uncertainty_radius")
        if maximum < initial:
            raise ValueError("maximum_uncertainty_radius cannot be smaller than initial_uncertainty_radius")
        object.__setattr__(self, "initial_uncertainty_radius", initial)
        object.__setattr__(self, "uncertainty_growth_per_time", growth)
        object.__setattr__(self, "maximum_uncertainty_radius", maximum)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe threshold record."""
        return {
            "max_coast_missing_observations": self.max_coast_missing_observations,
            "max_unlocalized_missing_observations": self.max_unlocalized_missing_observations,
            "initial_uncertainty_radius": self.initial_uncertainty_radius,
            "uncertainty_growth_per_time": self.uncertainty_growth_per_time,
            "maximum_uncertainty_radius": self.maximum_uncertainty_radius,
        }


@dataclass(frozen=True, slots=True)
class MaternalPredictedRegionV1:
    """One bounded circular prior for current maternal location.

    The region is explicitly non-authoritative.  Its center may shift using the
    most recent valid Phase 4B relative-distance/bearing rates; otherwise it
    remains centered on the last supported point while its radius widens.
    """

    center: NavPointV1
    radius: float
    frame_id: str
    units: str
    source_observation_no: int
    elapsed_since_support: float
    method: str
    motion_applied: bool

    def __post_init__(self) -> None:
        if not isinstance(self.center, NavPointV1):
            raise TypeError("center must be NavPointV1")
        object.__setattr__(self, "radius", _finite_non_negative_float(self.radius, field_name="radius"))
        _require_nonempty_text(self.frame_id, field_name="frame_id")
        _require_nonempty_text(self.units, field_name="units")
        _require_positive_int(self.source_observation_no, field_name="source_observation_no")
        object.__setattr__(
            self,
            "elapsed_since_support",
            _finite_non_negative_float(self.elapsed_since_support, field_name="elapsed_since_support"),
        )
        _require_nonempty_text(self.method, field_name="method")
        if not isinstance(self.motion_applied, bool):
            raise TypeError("motion_applied must be bool")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe predicted-region record."""
        return {
            "schema": "maternal_predicted_region_v1",
            "center": self.center.as_dict(),
            "radius": self.radius,
            "frame_id": self.frame_id,
            "units": self.units,
            "source_observation_no": self.source_observation_no,
            "elapsed_since_support": self.elapsed_since_support,
            "method": self.method,
            "motion_applied": self.motion_applied,
            "authoritative_current_location": False,
        }


@dataclass(frozen=True, slots=True)
class MaternalContinuityShadowStateV1:
    """One immutable Phase 4C identity/continuity/localization transaction."""

    observation_no: int
    tracked_identity_handle: str
    observed_identity_handle: Optional[str]
    identity_support: MaternalIdentitySupportV1
    maternal_role_relation: str
    role_retained: bool
    observed_entity_inherits_maternal_role: bool
    existence_status: MaternalExistenceStatusV1
    observability: MaternalObservabilityV1
    observability_reason: str
    frame_id: str
    units: str
    source_geometry_map_ref: NavMapRefV1
    source_stable_map_ref: Optional[NavMapRefV1]
    observed_candidate_location: Optional[NavPointV1]
    current_location: Optional[NavPointV1]
    last_supported_location: Optional[NavPointV1]
    last_supported_map_ref: Optional[NavMapRefV1]
    predicted_region: Optional[MaternalPredictedRegionV1]
    localization_status: MaternalLocalizationStatusV1
    localization_authoritative: bool
    track_status: MaternalTrackStatusV1
    missing_age_observations: int
    last_supported_observation_no: Optional[int]
    last_supported_step_index: Optional[int]
    last_supported_time_since_birth: Optional[float]
    motion_source_map_ref: Optional[NavMapRefV1]
    motion_source_observation_no: Optional[int]
    motion_interval_source: Optional[str]
    motion_reference_value: Optional[float]
    motion_relative_rate: Optional[float]
    motion_bearing_rate_degrees: Optional[float]
    motion_rate_uncertainty: Optional[float]
    negative_evidence_present: bool
    negative_evidence_reliable: bool
    negative_evidence_reason: Optional[str]
    reliable_negative_evidence_count: int
    reacquisition: MaternalReacquisitionV1
    reason: str
    thresholds: MaternalContinuityThresholdsV1

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        _require_nonempty_text(self.tracked_identity_handle, field_name="tracked_identity_handle")
        if self.observed_identity_handle is not None:
            _require_nonempty_text(self.observed_identity_handle, field_name="observed_identity_handle")
        if not isinstance(self.identity_support, MaternalIdentitySupportV1):
            raise TypeError("identity_support must be MaternalIdentitySupportV1")
        _require_nonempty_text(self.maternal_role_relation, field_name="maternal_role_relation")
        for field_name in (
            "role_retained",
            "observed_entity_inherits_maternal_role",
            "localization_authoritative",
            "negative_evidence_present",
            "negative_evidence_reliable",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if not isinstance(self.existence_status, MaternalExistenceStatusV1):
            raise TypeError("existence_status must be MaternalExistenceStatusV1")
        if not isinstance(self.observability, MaternalObservabilityV1):
            raise TypeError("observability must be MaternalObservabilityV1")
        _require_nonempty_text(self.observability_reason, field_name="observability_reason")
        _require_nonempty_text(self.frame_id, field_name="frame_id")
        _require_nonempty_text(self.units, field_name="units")
        if not isinstance(self.source_geometry_map_ref, NavMapRefV1):
            raise TypeError("source_geometry_map_ref must be NavMapRefV1")
        if self.source_stable_map_ref is not None and not isinstance(self.source_stable_map_ref, NavMapRefV1):
            raise TypeError("source_stable_map_ref must be NavMapRefV1 or None")
        for field_name in ("observed_candidate_location", "current_location", "last_supported_location"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        if self.last_supported_map_ref is not None and not isinstance(self.last_supported_map_ref, NavMapRefV1):
            raise TypeError("last_supported_map_ref must be NavMapRefV1 or None")
        if self.predicted_region is not None and not isinstance(self.predicted_region, MaternalPredictedRegionV1):
            raise TypeError("predicted_region must be MaternalPredictedRegionV1 or None")
        if not isinstance(self.localization_status, MaternalLocalizationStatusV1):
            raise TypeError("localization_status must be MaternalLocalizationStatusV1")
        if not isinstance(self.track_status, MaternalTrackStatusV1):
            raise TypeError("track_status must be MaternalTrackStatusV1")
        _require_non_negative_int(self.missing_age_observations, field_name="missing_age_observations")
        if self.last_supported_observation_no is not None:
            _require_positive_int(self.last_supported_observation_no, field_name="last_supported_observation_no")
            if self.last_supported_observation_no > self.observation_no:
                raise ValueError("last_supported_observation_no cannot exceed observation_no")
        if self.last_supported_step_index is not None:
            _require_non_negative_int(self.last_supported_step_index, field_name="last_supported_step_index")
        if self.last_supported_time_since_birth is not None:
            object.__setattr__(
                self,
                "last_supported_time_since_birth",
                _finite_non_negative_float(
                    self.last_supported_time_since_birth,
                    field_name="last_supported_time_since_birth",
                ),
            )
        if self.motion_source_map_ref is not None and not isinstance(self.motion_source_map_ref, NavMapRefV1):
            raise TypeError("motion_source_map_ref must be NavMapRefV1 or None")
        if self.motion_source_observation_no is not None:
            _require_positive_int(self.motion_source_observation_no, field_name="motion_source_observation_no")
        if self.motion_interval_source is not None:
            _require_nonempty_text(self.motion_interval_source, field_name="motion_interval_source")
        for field_name in (
            "motion_reference_value",
            "motion_relative_rate",
            "motion_bearing_rate_degrees",
            "motion_rate_uncertainty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite_float(value, field_name=field_name)
                if field_name == "motion_rate_uncertainty" and number < 0.0:
                    raise ValueError("motion_rate_uncertainty must be non-negative")
                object.__setattr__(self, field_name, number)
        if self.negative_evidence_reason is not None:
            _require_nonempty_text(self.negative_evidence_reason, field_name="negative_evidence_reason")
        _require_non_negative_int(self.reliable_negative_evidence_count, field_name="reliable_negative_evidence_count")
        if not isinstance(self.reacquisition, MaternalReacquisitionV1):
            raise TypeError("reacquisition must be MaternalReacquisitionV1")
        _require_nonempty_text(self.reason, field_name="reason")
        if not isinstance(self.thresholds, MaternalContinuityThresholdsV1):
            raise TypeError("thresholds must be MaternalContinuityThresholdsV1")

        if self.localization_authoritative:
            if self.current_location is None:
                raise ValueError("authoritative current localization requires current_location")
            if self.localization_status is not MaternalLocalizationStatusV1.CURRENT_EXACT:
                raise ValueError("authoritative current localization must be CURRENT_EXACT")
            if self.track_status is not MaternalTrackStatusV1.ACTIVE:
                raise ValueError("authoritative current localization requires an ACTIVE track")
            if self.identity_support is not MaternalIdentitySupportV1.SUPPORTED:
                raise ValueError("authoritative current localization requires supported identity")
            if self.observability is not MaternalObservabilityV1.OBSERVED:
                raise ValueError("authoritative current localization requires observed evidence")
        elif self.current_location is not None:
            raise ValueError("non-authoritative continuity state cannot expose a current exact location")

        if self.predicted_region is not None and self.localization_status is not MaternalLocalizationStatusV1.PREDICTED_REGION:
            raise ValueError("predicted_region requires PREDICTED_REGION localization status")
        if self.localization_status is MaternalLocalizationStatusV1.PREDICTED_REGION and self.predicted_region is None:
            raise ValueError("PREDICTED_REGION localization status requires predicted_region")
        if self.observed_entity_inherits_maternal_role:
            if not self.role_retained or self.identity_support is not MaternalIdentitySupportV1.SUPPORTED:
                raise ValueError("maternal role can apply to the observed entity only with supported identity")
            if self.observed_identity_handle != self.tracked_identity_handle:
                raise ValueError("observed entity can inherit maternal role only when identity handles match")
        if self.negative_evidence_reliable and not self.negative_evidence_present:
            raise ValueError("reliable negative evidence requires negative_evidence_present")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit Phase 4C trace record."""
        identity_persists_without_localization = bool(
            self.role_retained and not self.localization_authoritative
        )
        return {
            "schema": "maternal_continuity_shadow_state_v1",
            "phase": "4C",
            "authority_level": "shadow",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
            "observation_no": self.observation_no,
            "tracked_identity_handle": self.tracked_identity_handle,
            "observed_identity_handle": self.observed_identity_handle,
            "identity_support": self.identity_support.value,
            "maternal_role_relation": self.maternal_role_relation,
            "role_retained": self.role_retained,
            "observed_entity_inherits_maternal_role": self.observed_entity_inherits_maternal_role,
            "identity_persists_without_localization": identity_persists_without_localization,
            "lost_track_deletes_identity": False,
            "lost_track_deletes_role": False,
            "existence_status": self.existence_status.value,
            "observability": self.observability.value,
            "observability_reason": self.observability_reason,
            "frame_id": self.frame_id,
            "units": self.units,
            "source_geometry_map_ref": self.source_geometry_map_ref.as_dict(),
            "source_stable_map_ref": (
                self.source_stable_map_ref.as_dict() if self.source_stable_map_ref is not None else None
            ),
            "observed_candidate_location": _point_dict(self.observed_candidate_location),
            "current_location": _point_dict(self.current_location),
            "last_supported_location": _point_dict(self.last_supported_location),
            "last_supported_map_ref": (
                self.last_supported_map_ref.as_dict() if self.last_supported_map_ref is not None else None
            ),
            "predicted_region": self.predicted_region.as_dict() if self.predicted_region is not None else None,
            "localization_status": self.localization_status.value,
            "localization_authoritative": self.localization_authoritative,
            "current_exact_coordinate_fabricated": False,
            "last_supported_location_is_current_observation": self.localization_authoritative,
            "predicted_region_is_current_observation": False,
            "track_status": self.track_status.value,
            "missing_age_observations": self.missing_age_observations,
            "last_supported_observation_no": self.last_supported_observation_no,
            "last_supported_step_index": self.last_supported_step_index,
            "last_supported_time_since_birth": self.last_supported_time_since_birth,
            "motion_estimate": {
                "source_map_ref": (
                    self.motion_source_map_ref.as_dict() if self.motion_source_map_ref is not None else None
                ),
                "source_observation_no": self.motion_source_observation_no,
                "interval_source": self.motion_interval_source,
                "reference_value": self.motion_reference_value,
                "relative_rate": self.motion_relative_rate,
                "bearing_rate_degrees": self.motion_bearing_rate_degrees,
                "rate_uncertainty": self.motion_rate_uncertainty,
                "supported": self.motion_relative_rate is not None,
            },
            "negative_evidence": {
                "present": self.negative_evidence_present,
                "reliable": self.negative_evidence_reliable,
                "reason": self.negative_evidence_reason,
                "reliable_count": self.reliable_negative_evidence_count,
            },
            "reacquisition": self.reacquisition.value,
            "reason": self.reason,
            "thresholds": self.thresholds.as_dict(),
            "creates_navmap_revision": False,
            "adapter_limitation": "native_runtime_observed_position_or_generic_unavailable_blackout_only",
            "optional_inspection_metadata": [
                "maternal_identity_handle",
                "maternal_identity_status",
                "maternal_identity_candidates",
                "maternal_observability",
                "maternal_observability_reason",
                "maternal_negative_evidence",
            ],
        }


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer excluding bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer excluding bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float excluding bool."""
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


def _optional_finite_float(value: Any) -> Optional[float]:
    """Return a finite float or None for unsupported input."""
    try:
        return _finite_float(value, field_name="value")
    except (TypeError, ValueError):
        return None


def _optional_non_negative_int(value: Any) -> Optional[int]:
    """Return a non-negative integer or None for unsupported input."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        return None
    return value


def _ctx_int(ctx: Any, name: str, default: int) -> int:
    """Return one context integer or a deterministic default."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ctx_float(ctx: Any, name: str, default: float) -> float:
    """Return one finite context float or a deterministic default."""
    value = getattr(ctx, name, default)
    try:
        return _finite_float(value, field_name=name)
    except (TypeError, ValueError):
        return default


def _point_dict(point: Optional[NavPointV1]) -> Optional[dict[str, float]]:
    """Return a JSON-safe point or None."""
    return point.as_dict() if point is not None else None


def _env_meta(env_obs: EnvObservation) -> dict[str, Any]:
    """Return one defensive observation-metadata dictionary."""
    raw = getattr(env_obs, "env_meta", None)
    return dict(raw) if isinstance(raw, dict) else {}


def maternal_continuity_thresholds_from_ctx_v1(ctx: Any) -> MaternalContinuityThresholdsV1:
    """Return validated bounded Phase 4C parameters from the runtime context."""
    max_coast = _ctx_int(
        ctx,
        "navmap_maternal_continuity_max_coast_missing_observations",
        _DEFAULT_MAX_COAST_MISSING_OBSERVATIONS,
    )
    max_unlocalized = _ctx_int(
        ctx,
        "navmap_maternal_continuity_max_unlocalized_missing_observations",
        _DEFAULT_MAX_UNLOCALIZED_MISSING_OBSERVATIONS,
    )
    initial = _ctx_float(
        ctx,
        "navmap_maternal_continuity_initial_uncertainty_radius",
        _DEFAULT_INITIAL_UNCERTAINTY_RADIUS,
    )
    growth = _ctx_float(
        ctx,
        "navmap_maternal_continuity_uncertainty_growth_per_time",
        _DEFAULT_UNCERTAINTY_GROWTH_PER_TIME,
    )
    maximum = _ctx_float(
        ctx,
        "navmap_maternal_continuity_maximum_uncertainty_radius",
        _DEFAULT_MAXIMUM_UNCERTAINTY_RADIUS,
    )
    if max_coast < 0:
        max_coast = _DEFAULT_MAX_COAST_MISSING_OBSERVATIONS
    if max_unlocalized <= 0 or max_unlocalized < max_coast:
        max_unlocalized = max(_DEFAULT_MAX_UNLOCALIZED_MISSING_OBSERVATIONS, max_coast)
    if initial < 0.0:
        initial = _DEFAULT_INITIAL_UNCERTAINTY_RADIUS
    if growth < 0.0:
        growth = _DEFAULT_UNCERTAINTY_GROWTH_PER_TIME
    if maximum <= 0.0 or maximum < initial:
        maximum = max(_DEFAULT_MAXIMUM_UNCERTAINTY_RADIUS, initial)
    return MaternalContinuityThresholdsV1(
        max_coast_missing_observations=max_coast,
        max_unlocalized_missing_observations=max_unlocalized,
        initial_uncertainty_radius=initial,
        uncertainty_growth_per_time=growth,
        maximum_uncertainty_radius=maximum,
    )


def _previous_state(ctx: Any) -> Optional[MaternalContinuityShadowStateV1]:
    """Return the preceding Phase 4C state when available."""
    value = getattr(ctx, "navmap_maternal_continuity_state", None)
    return value if isinstance(value, MaternalContinuityShadowStateV1) else None


def _relative_observation_candidate(env_obs: EnvObservation) -> Optional[NavPointV1]:
    """Return one raw SELF-relative candidate point for mismatch inspection only."""
    meta = _env_meta(env_obs)
    self_raw = meta.get("kid_position")
    candidate_raw = meta.get("mom_position")
    if not isinstance(self_raw, dict) or not isinstance(candidate_raw, dict):
        return None
    self_x = _optional_finite_float(self_raw.get("x"))
    self_y = _optional_finite_float(self_raw.get("y"))
    candidate_x = _optional_finite_float(candidate_raw.get("x"))
    candidate_y = _optional_finite_float(candidate_raw.get("y"))
    if self_x is None or self_y is None or candidate_x is None or candidate_y is None:
        return None
    try:
        return NavPointV1(x=candidate_x - self_x, y=candidate_y - self_y)
    except (TypeError, ValueError):
        return None


def _candidate_location(
    state: MaternalGeometryShadowStateV1,
    env_obs: EnvObservation,
) -> Optional[NavPointV1]:
    """Return the current maternal point or a non-maternal candidate for inspection.

    Normal matched evidence remains map-derived. If Phase 4A deliberately
    excluded a mismatched/ambiguous identity, the raw candidate coordinate may
    still be exposed as ``observed_candidate_location`` for diagnosis, but it
    can never become ``current_location`` without identity support.
    """
    if state.evidence_readout.valid:
        try:
            result = element_centroid(state.evidence_map, state.evidence_readout.maternal_element_id)
        except (KeyError, TypeError, ValueError):
            return None
        return result.point
    return _relative_observation_candidate(env_obs)


def _identity_evidence(
    meta: dict[str, Any],
    *,
    expected_identity: str,
    candidate_visible: bool,
) -> tuple[Optional[str], MaternalIdentitySupportV1, str]:
    """Classify deterministic identity/correspondence inspection evidence.

    No candidate is selected from an ambiguous list.  Candidate order therefore
    cannot silently determine maternal identity.
    """
    status_raw = meta.get("maternal_identity_status")
    status = str(status_raw).strip().lower() if isinstance(status_raw, str) else ""
    if status in {"ambiguous", "unknown", "uncertain"}:
        return None, MaternalIdentitySupportV1.AMBIGUOUS, "explicit_identity_ambiguous"

    observed: Optional[str]
    candidates_raw = meta.get("maternal_identity_candidates")
    if isinstance(candidates_raw, (list, tuple)):
        candidates = sorted(
            {
                item.strip()
                for item in candidates_raw
                if isinstance(item, str) and item.strip()
            }
        )
        if len(candidates) != 1:
            return None, MaternalIdentitySupportV1.AMBIGUOUS, "identity_candidate_set_ambiguous"
        observed = candidates[0]
    else:
        handle_raw = meta.get("maternal_identity_handle")
        observed = handle_raw.strip() if isinstance(handle_raw, str) and handle_raw.strip() else None

    if observed is None:
        if candidate_visible:
            observed = expected_identity
            return observed, MaternalIdentitySupportV1.SUPPORTED, "phase4a_known_maternal_scaffold"
        return None, MaternalIdentitySupportV1.RETAINED, "identity_not_currently_observed"
    if observed != expected_identity:
        return observed, MaternalIdentitySupportV1.MISMATCH, "observed_identity_differs_from_tracked_maternal"
    return observed, MaternalIdentitySupportV1.SUPPORTED, "observed_identity_matches_tracked_maternal"


def _negative_evidence(meta: dict[str, Any]) -> tuple[bool, bool, Optional[str]]:
    """Decode optional explicit negative-evidence inspection metadata."""
    raw = meta.get("maternal_negative_evidence")
    if isinstance(raw, dict):
        present = bool(raw.get("present", False))
        reliable = bool(raw.get("reliable", False)) if present else False
        reason_raw = raw.get("reason")
        reason = reason_raw.strip() if isinstance(reason_raw, str) and reason_raw.strip() else None
        return present, reliable, reason
    if isinstance(raw, bool):
        return raw, raw, "explicit_expected_location_empty" if raw else None
    return False, False, None


def _observability(
    meta: dict[str, Any],
    *,
    candidate_visible: bool,
    negative_present: bool,
    negative_reason: Optional[str],
) -> tuple[MaternalObservabilityV1, str]:
    """Classify current observability without inventing native occlusion semantics."""
    if negative_present and not candidate_visible:
        return (
            MaternalObservabilityV1.NEGATIVE_EXPECTED_LOCATION,
            negative_reason or "explicit_expected_visible_location_empty",
        )

    explicit_raw = meta.get("maternal_observability")
    explicit = str(explicit_raw).strip().lower() if isinstance(explicit_raw, str) else ""
    aliases = {
        "visible": MaternalObservabilityV1.OBSERVED,
        "observed": MaternalObservabilityV1.OBSERVED,
        "sensor_dropout": MaternalObservabilityV1.SENSOR_DROPOUT,
        "blackout": MaternalObservabilityV1.SENSOR_DROPOUT,
        "occluded": MaternalObservabilityV1.OCCLUDED,
        "out_of_field": MaternalObservabilityV1.OUT_OF_FIELD,
        "outside_field": MaternalObservabilityV1.OUT_OF_FIELD,
        "unavailable": MaternalObservabilityV1.UNAVAILABLE,
        "missing": MaternalObservabilityV1.UNAVAILABLE,
        "ambiguous": MaternalObservabilityV1.AMBIGUOUS,
    }
    if explicit in aliases:
        classified = aliases[explicit]
        conflict = candidate_visible != (classified is MaternalObservabilityV1.OBSERVED)
        if conflict:
            return MaternalObservabilityV1.AMBIGUOUS, "observability_metadata_conflicts_with_position_evidence"
        reason_raw = meta.get("maternal_observability_reason")
        if isinstance(reason_raw, str) and reason_raw.strip():
            return classified, reason_raw.strip()
        return classified, f"explicit_{classified.value}"

    if candidate_visible:
        return MaternalObservabilityV1.OBSERVED, "current_phase4a_position_evidence"
    if bool(meta.get("newborn_obs_blackout", False)):
        kind_raw = meta.get("newborn_obs_blackout_kind")
        kind = kind_raw.strip() if isinstance(kind_raw, str) and kind_raw.strip() else "generic"
        return MaternalObservabilityV1.SENSOR_DROPOUT, f"newborn_observation_blackout:{kind}"
    return MaternalObservabilityV1.UNAVAILABLE, "maternal_position_unavailable_no_native_occlusion_semantics"


def _timing_values(env_obs: EnvObservation) -> tuple[Optional[int], Optional[float]]:
    """Return current step/time metadata without creating another clock."""
    meta = _env_meta(env_obs)
    step_index = _optional_non_negative_int(meta.get("step_index"))
    time_since_birth = _optional_finite_float(meta.get("time_since_birth"))
    if time_since_birth is not None and time_since_birth < 0.0:
        time_since_birth = None
    return step_index, time_since_birth


def _axis_value(
    env_obs: EnvObservation,
    *,
    observation_no: int,
    interval_source: Optional[str],
) -> Optional[float]:
    """Return the current value for a previously selected Phase 4B time axis."""
    step_index, time_since_birth = _timing_values(env_obs)
    if interval_source == "time_since_birth":
        return time_since_birth
    if interval_source == "step_index":
        return float(step_index) if step_index is not None else None
    if interval_source == "observation_no":
        return float(observation_no)
    return None


def _current_motion(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    observation_no: int,
) -> tuple[
    Optional[NavMapRefV1],
    Optional[int],
    Optional[str],
    Optional[float],
    Optional[float],
    Optional[float],
    Optional[float],
]:
    """Return the current valid Phase 4B motion estimate or an empty tuple."""
    value = getattr(ctx, "navmap_maternal_temporal_state", None)
    if not isinstance(value, MaternalTemporalShadowStateV1):
        return None, None, None, None, None, None, None
    readout = value.readout
    if not readout.valid or readout.window_end_observation_no != observation_no:
        return None, None, None, None, None, None, None
    reference = _axis_value(
        env_obs,
        observation_no=observation_no,
        interval_source=readout.interval_source,
    )
    return (
        readout.source_evidence_map_ref,
        observation_no,
        readout.interval_source,
        reference,
        readout.relative_rate,
        readout.bearing_rate_degrees,
        readout.rate_uncertainty,
    )


def _missing_age(
    previous: Optional[MaternalContinuityShadowStateV1],
    *,
    observation_no: int,
) -> int:
    """Return unsupported observation age since the last exact localization."""
    if previous is None or previous.last_supported_observation_no is None:
        return 0
    return max(1, observation_no - previous.last_supported_observation_no)


def _elapsed_since_support(
    previous: MaternalContinuityShadowStateV1,
    env_obs: EnvObservation,
    *,
    observation_no: int,
    missing_age: int,
) -> float:
    """Return elapsed time on the preserved motion axis, with bounded fallback."""
    current = _axis_value(
        env_obs,
        observation_no=observation_no,
        interval_source=previous.motion_interval_source,
    )
    reference = previous.motion_reference_value
    if current is not None and reference is not None and current - reference > _MINIMUM_TIME_DELTA:
        return current - reference
    return float(max(1, missing_age))


def _predicted_region(
    previous: MaternalContinuityShadowStateV1,
    env_obs: EnvObservation,
    *,
    observation_no: int,
    missing_age: int,
    thresholds: MaternalContinuityThresholdsV1,
) -> Optional[MaternalPredictedRegionV1]:
    """Project a bounded shifting/widening region from the last supported point."""
    last = previous.last_supported_location
    source_observation_no = previous.last_supported_observation_no
    if last is None or source_observation_no is None:
        return None

    elapsed = _elapsed_since_support(
        previous,
        env_obs,
        observation_no=observation_no,
        missing_age=missing_age,
    )
    center = last
    method = "last_supported_center_widening"
    motion_applied = False
    rate = previous.motion_relative_rate
    if rate is not None:
        distance = math.hypot(last.x, last.y)
        bearing = math.degrees(math.atan2(last.y, last.x)) % 360.0 if distance > _MINIMUM_TIME_DELTA else None
        if bearing is not None:
            projected_distance = max(0.0, distance + rate * elapsed)
            bearing_rate = previous.motion_bearing_rate_degrees or 0.0
            projected_bearing = (bearing + bearing_rate * elapsed) % 360.0
            radians = math.radians(projected_bearing)
            center = NavPointV1(
                x=projected_distance * math.cos(radians),
                y=projected_distance * math.sin(radians),
            )
            method = "phase4b_polar_rate_projection"
            motion_applied = True

    uncertainty_bonus = 0.0
    if previous.motion_rate_uncertainty is not None:
        uncertainty_bonus = previous.motion_rate_uncertainty * elapsed
    radius = min(
        thresholds.maximum_uncertainty_radius,
        thresholds.initial_uncertainty_radius
        + thresholds.uncertainty_growth_per_time * max(1.0, elapsed)
        + uncertainty_bonus,
    )
    return MaternalPredictedRegionV1(
        center=center,
        radius=radius,
        frame_id=previous.frame_id,
        units=previous.units,
        source_observation_no=source_observation_no,
        elapsed_since_support=elapsed,
        method=method,
        motion_applied=motion_applied,
    )


def _history_limit(ctx: Any) -> int:
    """Return one bounded positive Phase 4C trace-history limit."""
    value = _ctx_int(ctx, "navmap_maternal_continuity_history_limit", _DEFAULT_HISTORY_LIMIT)
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_history(ctx: Any, row: dict[str, Any]) -> None:
    """Append one bounded JSON-safe Phase 4C trace."""
    raw = getattr(ctx, "navmap_maternal_continuity_history", None)
    history = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    history.append(dict(row))
    ctx.navmap_maternal_continuity_history = history[-_history_limit(ctx):]


def _status_from_state(state: MaternalContinuityShadowStateV1) -> str:
    """Return one compact top-level transaction status."""
    if state.negative_evidence_reliable:
        return "negative_evidence"
    if state.track_status is MaternalTrackStatusV1.ACTIVE:
        if state.reacquisition is MaternalReacquisitionV1.INITIAL_ACQUISITION:
            return "acquired"
        if state.reacquisition is MaternalReacquisitionV1.REACQUIRED:
            return "reacquired"
        return "active"
    return state.track_status.value


def maternal_continuity_shadow_observation_step_v1(ctx: Any, env_obs: EnvObservation) -> dict[str, Any]:
    """Process one Phase 4A/4B result through the Phase 4C shadow.

    The transaction never writes BodyMap, WorldGraph, PolicyRuntime, FollowMom,
    or an immutable NavMap.  It updates only bounded context-local continuity
    records and trace history.
    """
    if ctx is None or env_obs is None:
        return {}
    if not bool(getattr(ctx, "navmap_maternal_continuity_shadow_enabled", True)):
        return {
            "schema": "maternal_continuity_shadow_update_v1",
            "phase": "4C",
            "status": "disabled",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
        }

    geometry_state = getattr(ctx, "navmap_maternal_state", None)
    if not isinstance(geometry_state, MaternalGeometryShadowStateV1):
        return {
            "schema": "maternal_continuity_shadow_update_v1",
            "phase": "4C",
            "status": "geometry_unavailable",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
            "reason": "phase4a_geometry_state_unavailable",
        }

    observation_no = geometry_state.observation_no
    previous = _previous_state(ctx)
    expected_identity = (
        previous.tracked_identity_handle
        if previous is not None
        else geometry_state.evidence_readout.maternal_element_id
    )
    frame_id = geometry_state.evidence_map.frame.frame_id
    units = geometry_state.evidence_map.frame.units
    candidate = _candidate_location(geometry_state, env_obs)
    meta = _env_meta(env_obs)
    negative_present, negative_reliable, negative_reason = _negative_evidence(meta)
    observed_identity, identity_evidence, identity_reason = _identity_evidence(
        meta,
        expected_identity=expected_identity,
        candidate_visible=candidate is not None,
    )
    observability, observability_reason = _observability(
        meta,
        candidate_visible=candidate is not None,
        negative_present=negative_present,
        negative_reason=negative_reason,
    )
    thresholds = maternal_continuity_thresholds_from_ctx_v1(ctx)
    step_index, time_since_birth = _timing_values(env_obs)

    previously_known = bool(previous is not None and previous.role_retained)
    identity_supported_now = bool(
        candidate is not None
        and observability is MaternalObservabilityV1.OBSERVED
        and identity_evidence is MaternalIdentitySupportV1.SUPPORTED
        and observed_identity == expected_identity
        and not negative_present
    )

    last_location = previous.last_supported_location if previous is not None else None
    last_map_ref = previous.last_supported_map_ref if previous is not None else None
    last_observation_no = previous.last_supported_observation_no if previous is not None else None
    last_step_index = previous.last_supported_step_index if previous is not None else None
    last_time_since_birth = previous.last_supported_time_since_birth if previous is not None else None
    missing_age = _missing_age(previous, observation_no=observation_no)
    reliable_negative_count = (
        (previous.reliable_negative_evidence_count if previous is not None else 0) + 1
        if negative_present and negative_reliable
        else 0
    )

    motion_values: tuple[
        Optional[NavMapRefV1],
        Optional[int],
        Optional[str],
        Optional[float],
        Optional[float],
        Optional[float],
        Optional[float],
    ] = (None, None, None, None, None, None, None)

    current_location: Optional[NavPointV1] = None
    predicted: Optional[MaternalPredictedRegionV1] = None
    localization_authoritative = False
    role_retained = previously_known
    observed_inherits_role = False

    if negative_present and negative_reliable and candidate is None:
        identity_support = MaternalIdentitySupportV1.RETAINED if previously_known else MaternalIdentitySupportV1.UNINITIALIZED
        existence_status = MaternalExistenceStatusV1.UNCERTAIN if previously_known else MaternalExistenceStatusV1.UNKNOWN
        localization_status = (
            MaternalLocalizationStatusV1.UNLOCALIZED if previously_known else MaternalLocalizationStatusV1.UNKNOWN
        )
        track_status = MaternalTrackStatusV1.LOST if previously_known else MaternalTrackStatusV1.UNINITIALIZED
        reacquisition = MaternalReacquisitionV1.NOT_OBSERVED
        missing_age = max(1, missing_age) if previously_known else 0
        reason = "reliable_negative_evidence_withdraws_expected_location_track_not_identity_or_role"
    elif identity_supported_now:
        identity_support = MaternalIdentitySupportV1.SUPPORTED
        role_retained = True
        observed_inherits_role = True
        existence_status = MaternalExistenceStatusV1.OBSERVED
        current_location = candidate
        last_location = candidate
        last_map_ref = geometry_state.stable_ref or geometry_state.last_stable_ref
        last_observation_no = observation_no
        last_step_index = step_index
        last_time_since_birth = time_since_birth
        localization_status = MaternalLocalizationStatusV1.CURRENT_EXACT
        localization_authoritative = True
        track_status = MaternalTrackStatusV1.ACTIVE
        missing_age = 0
        reliable_negative_count = 0
        if not previously_known:
            reacquisition = MaternalReacquisitionV1.INITIAL_ACQUISITION
        elif previous is not None and previous.track_status is MaternalTrackStatusV1.ACTIVE:
            reacquisition = MaternalReacquisitionV1.CONTINUING_TRACK
        else:
            reacquisition = MaternalReacquisitionV1.REACQUIRED
        motion_values = _current_motion(
            ctx,
            env_obs,
            observation_no=observation_no,
        )
        reason = "current_exact_localization_supported_by_identity_matched_phase4a_geometry"
    elif candidate is not None and identity_evidence is MaternalIdentitySupportV1.MISMATCH:
        identity_support = MaternalIdentitySupportV1.MISMATCH
        existence_status = (
            MaternalExistenceStatusV1.PRESUMED_CONTINUING if previously_known else MaternalExistenceStatusV1.UNKNOWN
        )
        localization_status = MaternalLocalizationStatusV1.UNLOCALIZED
        track_status = MaternalTrackStatusV1.IDENTITY_MISMATCH
        reacquisition = MaternalReacquisitionV1.IDENTITY_MISMATCH
        missing_age = max(1, missing_age) if previously_known else 0
        reason = "different_observed_identity_does_not_inherit_maternal_role_or_track"
    elif (
        identity_evidence is MaternalIdentitySupportV1.AMBIGUOUS
        or observability is MaternalObservabilityV1.AMBIGUOUS
        or (candidate is not None and negative_present)
    ):
        identity_support = MaternalIdentitySupportV1.AMBIGUOUS
        existence_status = (
            MaternalExistenceStatusV1.PRESUMED_CONTINUING if previously_known else MaternalExistenceStatusV1.UNKNOWN
        )
        localization_status = MaternalLocalizationStatusV1.AMBIGUOUS
        track_status = MaternalTrackStatusV1.AMBIGUOUS
        reacquisition = MaternalReacquisitionV1.AMBIGUOUS
        missing_age = max(1, missing_age) if previously_known else 0
        reason = "ambiguous_identity_or_observability_preserves_unknown_without_arbitrary_assignment"
    elif previously_known and previous is not None:
        identity_support = MaternalIdentitySupportV1.RETAINED
        role_retained = True
        existence_status = MaternalExistenceStatusV1.PRESUMED_CONTINUING
        reacquisition = MaternalReacquisitionV1.NOT_OBSERVED
        missing_age = max(1, missing_age)
        if missing_age <= thresholds.max_coast_missing_observations:
            track_status = MaternalTrackStatusV1.COASTING
        elif missing_age <= thresholds.max_unlocalized_missing_observations:
            track_status = MaternalTrackStatusV1.UNLOCALIZED
        else:
            track_status = MaternalTrackStatusV1.LOST
        if track_status is MaternalTrackStatusV1.LOST:
            localization_status = MaternalLocalizationStatusV1.UNLOCALIZED
            reason = "bounded_missing_support_exhausted_active_track_lost_identity_and_role_retained"
        else:
            predicted = _predicted_region(
                previous,
                env_obs,
                observation_no=observation_no,
                missing_age=missing_age,
                thresholds=thresholds,
            )
            if predicted is not None:
                localization_status = MaternalLocalizationStatusV1.PREDICTED_REGION
                reason = "missing_position_retains_non_authoritative_widening_region"
            else:
                localization_status = MaternalLocalizationStatusV1.UNLOCALIZED
                reason = "missing_position_without_supported_region_identity_and_role_retained"
        motion_values = (
            previous.motion_source_map_ref,
            previous.motion_source_observation_no,
            previous.motion_interval_source,
            previous.motion_reference_value,
            previous.motion_relative_rate,
            previous.motion_bearing_rate_degrees,
            previous.motion_rate_uncertainty,
        )
    else:
        identity_support = MaternalIdentitySupportV1.UNINITIALIZED
        existence_status = MaternalExistenceStatusV1.UNKNOWN
        localization_status = MaternalLocalizationStatusV1.UNKNOWN
        track_status = MaternalTrackStatusV1.UNINITIALIZED
        reacquisition = MaternalReacquisitionV1.NOT_OBSERVED
        missing_age = 0
        reason = "maternal_track_not_initialized_without_identity_matched_position_evidence"

    (
        motion_source_map_ref,
        motion_source_observation_no,
        motion_interval_source,
        motion_reference_value,
        motion_relative_rate,
        motion_bearing_rate,
        motion_rate_uncertainty,
    ) = motion_values

    state = MaternalContinuityShadowStateV1(
        observation_no=observation_no,
        tracked_identity_handle=expected_identity,
        observed_identity_handle=observed_identity,
        identity_support=identity_support,
        maternal_role_relation=_MATERNAL_ROLE_RELATION,
        role_retained=role_retained,
        observed_entity_inherits_maternal_role=observed_inherits_role,
        existence_status=existence_status,
        observability=observability,
        observability_reason=(
            f"{observability_reason};{identity_reason}"
            if identity_reason and identity_evidence in {MaternalIdentitySupportV1.MISMATCH, MaternalIdentitySupportV1.AMBIGUOUS}
            else observability_reason
        ),
        frame_id=frame_id,
        units=units,
        source_geometry_map_ref=geometry_state.evidence_ref,
        source_stable_map_ref=geometry_state.stable_ref,
        observed_candidate_location=candidate,
        current_location=current_location,
        last_supported_location=last_location,
        last_supported_map_ref=last_map_ref,
        predicted_region=predicted,
        localization_status=localization_status,
        localization_authoritative=localization_authoritative,
        track_status=track_status,
        missing_age_observations=missing_age,
        last_supported_observation_no=last_observation_no,
        last_supported_step_index=last_step_index,
        last_supported_time_since_birth=last_time_since_birth,
        motion_source_map_ref=motion_source_map_ref,
        motion_source_observation_no=motion_source_observation_no,
        motion_interval_source=motion_interval_source,
        motion_reference_value=motion_reference_value,
        motion_relative_rate=motion_relative_rate,
        motion_bearing_rate_degrees=motion_bearing_rate,
        motion_rate_uncertainty=motion_rate_uncertainty,
        negative_evidence_present=negative_present,
        negative_evidence_reliable=negative_reliable,
        negative_evidence_reason=negative_reason,
        reliable_negative_evidence_count=reliable_negative_count,
        reacquisition=reacquisition,
        reason=reason,
        thresholds=thresholds,
    )
    row = state.as_dict()
    row.update(
        {
            "schema": "maternal_continuity_shadow_update_v1",
            "status": _status_from_state(state),
            "controller_steps": getattr(ctx, "controller_steps", None),
            "ticks": getattr(ctx, "ticks", None),
            "phase4a_observation_no": geometry_state.observation_no,
            "phase4b_status": (
                getattr(ctx, "navmap_maternal_temporal_last_update", {}).get("status")
                if isinstance(getattr(ctx, "navmap_maternal_temporal_last_update", None), dict)
                else None
            ),
        }
    )

    ctx.navmap_maternal_continuity_state = state
    ctx.navmap_maternal_continuity_last_update = dict(row)
    _append_history(ctx, row)
    return row


def maternal_continuity_shadow_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 4C update."""
    if ctx is None:
        return {
            "schema": "maternal_continuity_shadow_summary_v1",
            "phase": "4C",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_maternal_continuity_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "maternal_continuity_shadow_summary_v1",
            "phase": "4C",
            "status": "uninitialized",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
        }
    summary = dict(row)
    summary["schema"] = "maternal_continuity_shadow_summary_v1"
    return summary


def _point_text(value: Any) -> str:
    """Return one compact point string for terminal traces."""
    if not isinstance(value, dict):
        return "unknown"
    x = value.get("x")
    y = value.get("y")
    if not isinstance(x, (int, float)) or isinstance(x, bool):
        return "unknown"
    if not isinstance(y, (int, float)) or isinstance(y, bool):
        return "unknown"
    return f"({float(x):.3f},{float(y):.3f})"


def _region_text(value: Any) -> str:
    """Return one compact predicted-region string for terminal traces."""
    if not isinstance(value, dict):
        return "none"
    center = _point_text(value.get("center"))
    radius = value.get("radius")
    method = value.get("method")
    radius_text = f"{float(radius):.3f}" if isinstance(radius, (int, float)) and not isinstance(radius, bool) else "unknown"
    return f"center={center} radius={radius_text} method={method}"


def render_maternal_continuity_shadow_lines_v1(ctx: Any) -> list[str]:
    """Render the latest Phase 4C identity/localization shadow for inspection."""
    summary = maternal_continuity_shadow_summary_v1(ctx)
    lines = ["MATERNAL CONTINUITY PHASE 4C SHADOW:"]
    lines.append(
        "  "
        f"status={summary.get('status')} authority={summary.get('authority')} "
        f"follow_mom_authority={summary.get('follow_mom_authority')} "
        f"map_can_trigger_follow_mom={summary.get('map_can_trigger_follow_mom')}"
    )
    lines.append(
        "  "
        f"identity tracked={summary.get('tracked_identity_handle')} observed={summary.get('observed_identity_handle')} "
        f"support={summary.get('identity_support')} role={summary.get('maternal_role_relation')} "
        f"role_retained={summary.get('role_retained')} "
        f"observed_inherits_role={summary.get('observed_entity_inherits_maternal_role')}"
    )
    lines.append(
        "  "
        f"observability={summary.get('observability')} reason={summary.get('observability_reason')} "
        f"existence={summary.get('existence_status')}"
    )
    lines.append(
        "  "
        f"localization={summary.get('localization_status')} authoritative={summary.get('localization_authoritative')} "
        f"current={_point_text(summary.get('current_location'))} "
        f"last_supported={_point_text(summary.get('last_supported_location'))}"
    )
    lines.append(f"  predicted_region={_region_text(summary.get('predicted_region'))}")
    negative = summary.get("negative_evidence")
    negative = negative if isinstance(negative, dict) else {}
    lines.append(
        "  "
        f"track={summary.get('track_status')} missing_age={summary.get('missing_age_observations')} "
        f"reacquisition={summary.get('reacquisition')} "
        f"negative={negative.get('present')}/{negative.get('reliable')} reason={negative.get('reason')}"
    )
    motion = summary.get("motion_estimate")
    motion = motion if isinstance(motion, dict) else {}
    lines.append(
        "  "
        f"motion_supported={motion.get('supported')} interval={motion.get('interval_source')} "
        f"relative_rate={motion.get('relative_rate')} bearing_rate={motion.get('bearing_rate_degrees')} "
        "creates_navmap_revision=False current_exact_coordinate_fabricated=False"
    )
    lines.append(
        "  environment_limit=native observed position or generic unavailable/blackout; "
        "occlusion/out-of-field/negative evidence require explicit inspection metadata"
    )
    return lines
