# -*- coding: utf-8 -*-
"""Phase 7 general temporal binding, live dynamics, and dynamic envelopes.

Purpose
-------
Phase 4B proved one narrow bounded temporal overlay for the SELF-maternal
relation.  Phase 7 generalizes that contract across several current map-linked
relations without creating a movie of immutable Navigation Maps.  The runtime
attaches compact typed samples to the existing bounded ``ctx.seqerr_history``
window and decodes current temporal overlays for:

* SELF-maternal relative motion and object-specific motion;
* SELF motion through the active terrain/route domain;
* harmless route-vegetation motion;
* nipple-mouth contact and contact duration;
* body support, support duration, and slip; and
* lower-controller progress, completion, interruption, and error.

Self-motion compensation
------------------------
Relative distance can shrink because Mom moved toward SELF, because SELF moved
toward Mom, or because both moved.  When current world-frame SELF and maternal
points are available, Phase 7 explicitly computes::

    object_velocity = relative_velocity + self_velocity

This keeps object-specific maternal motion separate from the already useful
SELF-maternal approach/recession relation.  A stationary mother therefore
remains stationary even while SELF successfully approaches her.

Dynamic envelopes and residuals
-------------------------------
Each supported current overlay may create one compact one-observation dynamic
envelope.  The next observation is compared with that envelope through a
structured residual carrying direction, rate, contact, support, slip, phase,
progress, and lower-controller-error fields as applicable.  Expected content
never becomes current evidence.  Ordinary rate variation, contact maintenance,
and periodic vegetation motion remain live state.  Event boundaries are
recorded sparsely, while a material-change candidate requires either an
explicit structural/affordance event or a persistent residual outside the
configured uncertainty envelope.

Authority and memory boundary
-----------------------------
Phase 7 is a source-linked live-dynamics layer.  It does not select or execute a
behavioral primitive, mutate BodyMap, weaken protected safety, write WorldGraph
or Columns, create episodic memory, or model detailed movement trajectories.
The shared rolling window is bounded, typed on reconstruction, identity- and
frame-consistent, and stores no complete NavMaps.  Lower motor systems expose
only compact progress/error/support/slip products needed by cognition.
"""

from __future__ import annotations

# The first generalized temporal vertical slice intentionally keeps its typed
# records, shared-window codec, envelope comparison, and renderer together so
# the source and no-movie boundaries remain inspectable.
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-boolean-expressions
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass
from enum import Enum
import math
from statistics import fmean
from typing import Any, Optional, Sequence

from cca8_env import EnvObservation
from cca8_feeding import FeedingRelationOverlayV1
from cca8_maternal_continuity import (
    MaternalContinuityShadowStateV1,
    MaternalIdentitySupportV1,
    MaternalLocalizationStatusV1,
    MaternalObservabilityV1,
    MaternalTrackStatusV1,
)
from cca8_maternal_geometry import MaternalGeometryShadowStateV1
from cca8_maternal_temporal import MaternalTemporalShadowStateV1, MaternalTemporalTrendV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1
from cca8_terrain import TerrainDynamicOverlayV1, TerrainWnmStateV1
from cca8_wnm_runtime import wnm_operative_map_v1

__version__ = "0.1.0"

__all__ = [
    "TemporalRelationV1",
    "TemporalMotionDirectionV1",
    "TemporalDistanceTrendV1",
    "TemporalPhaseV1",
    "TemporalExpectedContinuationV1",
    "TemporalEnvelopeStatusV1",
    "TemporalBindingSampleV1",
    "TemporalBindingOverlayV1",
    "TemporalDynamicEnvelopeV1",
    "TemporalStructuredResidualV1",
    "TemporalMaterialityDecisionV1",
    "TemporalBindingStateV1",
    "live_dynamics_reset_v1",
    "live_dynamics_observation_step_v1",
    "live_dynamics_overlay_v1",
    "live_dynamics_summary_v1",
    "render_live_dynamics_lines_v1",
    "__version__",
]

_BUCKET_KEY = "live_dynamics_v1"
_SELF_IDENTITY = "self_individual"
_MATERNAL_IDENTITY_FALLBACK = "maternal_individual"
_ROUTE_VEGETATION_IDENTITY = "route_vegetation_branch_v1"
_BODY_SUPPORT_IDENTITY = "self_body_support"
_LOWER_MOTOR_IDENTITY = "self_lower_motor_controller"
_DEFAULT_HISTORY_LIMIT = 25
_DEFAULT_SPEED_TOLERANCE = 0.05
_DEFAULT_RELATIVE_RATE_TOLERANCE = 0.05
_DEFAULT_ENVELOPE_SPEED_TOLERANCE = 0.15
_DEFAULT_ENVELOPE_RATE_TOLERANCE = 0.10
_DEFAULT_PROGRESS_TOLERANCE = 0.05
_DEFAULT_PERSISTENT_RESIDUAL_OBSERVATIONS = 2
_MINIMUM_DT = 1.0e-9


class TemporalRelationV1(str, Enum):
    """Bounded Phase 7 live relations decoded from current map-linked evidence."""

    SELF_MATERNAL = "self_maternal"
    SELF_ROUTE = "self_route"
    ROUTE_VEGETATION = "route_vegetation"
    FEEDING_CONTACT = "feeding_contact"
    BODY_SUPPORT = "body_support"
    LOWER_MOTOR = "lower_motor"


class TemporalMotionDirectionV1(str, Enum):
    """Current 2-D motion direction after explicit frame-consistent decoding."""

    STILL = "still"
    NORTH = "north"
    NORTH_EAST = "north_east"
    EAST = "east"
    SOUTH_EAST = "south_east"
    SOUTH = "south"
    SOUTH_WEST = "south_west"
    WEST = "west"
    NORTH_WEST = "north_west"
    UNKNOWN = "unknown"


class TemporalDistanceTrendV1(str, Enum):
    """Current change in a subject-object scalar separation."""

    APPROACHING = "approaching"
    STABLE = "stable"
    RECEDING = "receding"
    UNKNOWN = "unknown"


class TemporalPhaseV1(str, Enum):
    """Generic task/live-dynamics phase without detailed motor choreography."""

    IDLE = "idle"
    STARTING = "starting"
    ACTIVE = "active"
    MAINTAINING = "maintaining"
    INTERRUPTED = "interrupted"
    COMPLETED = "completed"
    UNKNOWN = "unknown"


class TemporalExpectedContinuationV1(str, Enum):
    """Compact one-step continuation expectations derived from current overlays."""

    CONTINUE_MOTION = "continue_motion"
    CONTINUE_APPROACH = "continue_approach"
    CONTINUE_RECESSION = "continue_recession"
    MAINTAIN_CONTACT = "maintain_contact"
    MAINTAIN_SUPPORT = "maintain_support"
    PROGRESS_NONDECREASING = "progress_nondecreasing"
    AVOID_NEW_ERROR = "avoid_new_error"
    HOLD_POSITION = "hold_position"
    UNKNOWN = "unknown"


class TemporalEnvelopeStatusV1(str, Enum):
    """Result of comparing one prior dynamic envelope with current evidence."""

    NOT_PREDICTED = "not_predicted"
    WITHIN_ENVELOPE = "within_envelope"
    OUTSIDE_ENVELOPE = "outside_envelope"
    UNKNOWN = "unknown"


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


def _unit_interval(value: Any, *, field_name: str) -> float:
    """Return one finite value in the closed unit interval."""
    number = _finite_float(value, field_name=field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _optional_float(value: Any) -> Optional[float]:
    """Return one finite float or ``None`` without accepting bool."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_non_negative_int(value: Any) -> Optional[int]:
    """Return one non-negative integer or ``None`` without accepting bool."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


def _optional_bool(value: Any) -> Optional[bool]:
    """Return a real bool or ``None`` without truthiness coercion."""
    return value if isinstance(value, bool) else None


def _optional_text(value: Any) -> Optional[str]:
    """Return non-empty text or ``None``."""
    return value if isinstance(value, str) and value.strip() else None


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return a JSON-safe optional map reference."""
    return ref.as_dict() if ref is not None else None


def _point_dict(point: Optional[NavPointV1]) -> Optional[dict[str, float]]:
    """Return a JSON-safe optional point."""
    return point.as_dict() if point is not None else None


@dataclass(frozen=True, slots=True)
class TemporalBindingSampleV1:
    """One compact relation sample stored in the shared bounded seqerr window.

    Complete NavMaps, map serializations, motor trajectories, and episodic
    records are deliberately excluded.  The sample carries only identities,
    frame, timing, source reference, selected point/scalar/control evidence,
    and explicit validity.
    """

    relation: TemporalRelationV1
    observation_no: int
    source_ref: str
    source_map_ref: Optional[NavMapRefV1]
    subject_identity_handle: str
    object_identity_handle: Optional[str]
    frame_id: str
    units: str
    step_index: Optional[int]
    controller_steps: int
    time_since_birth: Optional[float]
    subject_point: Optional[NavPointV1]
    object_point: Optional[NavPointV1]
    relative_distance: Optional[float]
    scalar_value: Optional[float]
    contact: Optional[bool]
    support: Optional[bool]
    slip: Optional[bool]
    phase_hint: Optional[str]
    lower_motor_action: Optional[str]
    lower_motor_progress: Optional[float]
    lower_motor_error: Optional[str]
    evidence_quality: float
    material_event: bool
    event_labels: tuple[str, ...]
    valid: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.relation, TemporalRelationV1):
            raise TypeError("relation must be TemporalRelationV1")
        _require_positive_int(self.observation_no, field_name="observation_no")
        _require_nonempty_text(self.source_ref, field_name="source_ref")
        if self.source_map_ref is not None and not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be NavMapRefV1 or None")
        _require_nonempty_text(self.subject_identity_handle, field_name="subject_identity_handle")
        if self.object_identity_handle is not None:
            _require_nonempty_text(self.object_identity_handle, field_name="object_identity_handle")
        for field_name in ("frame_id", "units", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if self.step_index is not None:
            _require_non_negative_int(self.step_index, field_name="step_index")
        _require_non_negative_int(self.controller_steps, field_name="controller_steps")
        if self.time_since_birth is not None:
            object.__setattr__(
                self,
                "time_since_birth",
                _finite_non_negative_float(self.time_since_birth, field_name="time_since_birth"),
            )
        for field_name in ("subject_point", "object_point"):
            point = getattr(self, field_name)
            if point is not None and not isinstance(point, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        if self.relative_distance is not None:
            object.__setattr__(
                self,
                "relative_distance",
                _finite_non_negative_float(self.relative_distance, field_name="relative_distance"),
            )
        if self.scalar_value is not None:
            object.__setattr__(self, "scalar_value", _finite_float(self.scalar_value, field_name="scalar_value"))
        for field_name in ("contact", "support", "slip"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        for field_name in ("phase_hint", "lower_motor_action", "lower_motor_error"):
            value = getattr(self, field_name)
            if value is not None:
                _require_nonempty_text(value, field_name=field_name)
        if self.lower_motor_progress is not None:
            object.__setattr__(
                self,
                "lower_motor_progress",
                _unit_interval(self.lower_motor_progress, field_name="lower_motor_progress"),
            )
        object.__setattr__(self, "evidence_quality", _unit_interval(self.evidence_quality, field_name="evidence_quality"))
        if not isinstance(self.material_event, bool):
            raise TypeError("material_event must be bool")
        if not isinstance(self.event_labels, tuple) or not all(isinstance(item, str) and item for item in self.event_labels):
            raise TypeError("event_labels must be a tuple of non-empty strings")
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be bool")

    def as_dict(self) -> dict[str, Any]:
        """Return one JSON-safe compact shared-window sample."""
        return {
            "schema": "temporal_binding_sample_v1",
            "phase": "7",
            "relation": self.relation.value,
            "observation_no": self.observation_no,
            "source_ref": self.source_ref,
            "source_map_ref": _optional_ref_dict(self.source_map_ref),
            "subject_identity_handle": self.subject_identity_handle,
            "object_identity_handle": self.object_identity_handle,
            "frame_id": self.frame_id,
            "units": self.units,
            "step_index": self.step_index,
            "controller_steps": self.controller_steps,
            "time_since_birth": self.time_since_birth,
            "subject_point": _point_dict(self.subject_point),
            "object_point": _point_dict(self.object_point),
            "relative_distance": self.relative_distance,
            "scalar_value": self.scalar_value,
            "contact": self.contact,
            "support": self.support,
            "slip": self.slip,
            "phase_hint": self.phase_hint,
            "lower_motor_action": self.lower_motor_action,
            "lower_motor_progress": self.lower_motor_progress,
            "lower_motor_error": self.lower_motor_error,
            "evidence_quality": self.evidence_quality,
            "material_event": self.material_event,
            "event_labels": list(self.event_labels),
            "valid": self.valid,
            "reason": self.reason,
            "contains_full_navmap": False,
            "contains_motor_trajectory": False,
            "episodic_memory_record": False,
        }


@dataclass(frozen=True, slots=True)
class TemporalBindingOverlayV1:
    """One current static temporal feature bundle decoded from a bounded suffix."""

    relation: TemporalRelationV1
    observation_no: int
    source_map_ref: Optional[NavMapRefV1]
    subject_identity_handle: str
    object_identity_handle: Optional[str]
    frame_id: str
    units: str
    window_capacity: int
    window_sample_count: int
    valid_sample_count: int
    interval_source: Optional[str]
    elapsed_time: Optional[float]
    motion_supported: bool
    motion_direction: TemporalMotionDirectionV1
    velocity_x: Optional[float]
    velocity_y: Optional[float]
    speed: Optional[float]
    self_velocity_x: Optional[float]
    self_velocity_y: Optional[float]
    object_velocity_x: Optional[float]
    object_velocity_y: Optional[float]
    object_speed: Optional[float]
    self_motion_compensated: bool
    relative_distance_start: Optional[float]
    relative_distance_end: Optional[float]
    relative_distance_rate: Optional[float]
    distance_trend: TemporalDistanceTrendV1
    scalar_rate: Optional[float]
    rate_uncertainty: Optional[float]
    contact: Optional[bool]
    support: Optional[bool]
    slip: Optional[bool]
    contact_duration_observations: Optional[int]
    support_duration_observations: Optional[int]
    phase: TemporalPhaseV1
    phase_detail: str
    expected_continuations: tuple[TemporalExpectedContinuationV1, ...]
    lower_motor_action: Optional[str]
    lower_motor_progress: Optional[float]
    lower_motor_error: Optional[str]
    evidence_quality: float
    freshness: str
    support_status: str
    material_event: bool
    event_labels: tuple[str, ...]
    valid: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.relation, TemporalRelationV1):
            raise TypeError("relation must be TemporalRelationV1")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.source_map_ref is not None and not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be NavMapRefV1 or None")
        _require_nonempty_text(self.subject_identity_handle, field_name="subject_identity_handle")
        if self.object_identity_handle is not None:
            _require_nonempty_text(self.object_identity_handle, field_name="object_identity_handle")
        for field_name in ("frame_id", "units", "phase_detail", "freshness", "support_status", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        _require_positive_int(self.window_capacity, field_name="window_capacity")
        _require_non_negative_int(self.window_sample_count, field_name="window_sample_count")
        _require_non_negative_int(self.valid_sample_count, field_name="valid_sample_count")
        if self.interval_source is not None:
            _require_nonempty_text(self.interval_source, field_name="interval_source")
        for field_name in (
            "elapsed_time",
            "velocity_x",
            "velocity_y",
            "speed",
            "self_velocity_x",
            "self_velocity_y",
            "object_velocity_x",
            "object_velocity_y",
            "object_speed",
            "relative_distance_start",
            "relative_distance_end",
            "relative_distance_rate",
            "scalar_rate",
            "rate_uncertainty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite_float(value, field_name=field_name)
                if field_name in {
                    "elapsed_time",
                    "speed",
                    "object_speed",
                    "relative_distance_start",
                    "relative_distance_end",
                    "rate_uncertainty",
                } and number < 0.0:
                    raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, number)
        for field_name in ("motion_supported", "self_motion_compensated", "material_event", "valid"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if not isinstance(self.motion_direction, TemporalMotionDirectionV1):
            raise TypeError("motion_direction must be TemporalMotionDirectionV1")
        if not isinstance(self.distance_trend, TemporalDistanceTrendV1):
            raise TypeError("distance_trend must be TemporalDistanceTrendV1")
        for field_name in ("contact", "support", "slip"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        for field_name in ("contact_duration_observations", "support_duration_observations"):
            value = getattr(self, field_name)
            if value is not None:
                _require_non_negative_int(value, field_name=field_name)
        if not isinstance(self.phase, TemporalPhaseV1):
            raise TypeError("phase must be TemporalPhaseV1")
        if not isinstance(self.expected_continuations, tuple) or not all(
            isinstance(item, TemporalExpectedContinuationV1) for item in self.expected_continuations
        ):
            raise TypeError("expected_continuations must contain TemporalExpectedContinuationV1 values")
        for field_name in ("lower_motor_action", "lower_motor_error"):
            value = getattr(self, field_name)
            if value is not None:
                _require_nonempty_text(value, field_name=field_name)
        if self.lower_motor_progress is not None:
            object.__setattr__(
                self,
                "lower_motor_progress",
                _unit_interval(self.lower_motor_progress, field_name="lower_motor_progress"),
            )
        object.__setattr__(self, "evidence_quality", _unit_interval(self.evidence_quality, field_name="evidence_quality"))
        if not isinstance(self.event_labels, tuple) or not all(isinstance(item, str) and item for item in self.event_labels):
            raise TypeError("event_labels must be a tuple of non-empty strings")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe source-linked live temporal overlay."""
        return {
            "schema": "temporal_binding_overlay_v1",
            "cca_phase": "7",
            "relation": self.relation.value,
            "observation_no": self.observation_no,
            "source_map_ref": _optional_ref_dict(self.source_map_ref),
            "subject_identity_handle": self.subject_identity_handle,
            "object_identity_handle": self.object_identity_handle,
            "frame_id": self.frame_id,
            "units": self.units,
            "window_capacity": self.window_capacity,
            "window_sample_count": self.window_sample_count,
            "valid_sample_count": self.valid_sample_count,
            "interval_source": self.interval_source,
            "elapsed_time": self.elapsed_time,
            "motion_supported": self.motion_supported,
            "motion_direction": self.motion_direction.value,
            "velocity": {"x": self.velocity_x, "y": self.velocity_y, "speed": self.speed},
            "self_velocity": {"x": self.self_velocity_x, "y": self.self_velocity_y},
            "object_specific_velocity": {
                "x": self.object_velocity_x,
                "y": self.object_velocity_y,
                "speed": self.object_speed,
                "self_motion_compensated": self.self_motion_compensated,
            },
            "relative_distance_start": self.relative_distance_start,
            "relative_distance_end": self.relative_distance_end,
            "relative_distance_rate": self.relative_distance_rate,
            "distance_trend": self.distance_trend.value,
            "scalar_rate": self.scalar_rate,
            "rate_uncertainty": self.rate_uncertainty,
            "contact": self.contact,
            "support": self.support,
            "slip": self.slip,
            "contact_duration_observations": self.contact_duration_observations,
            "support_duration_observations": self.support_duration_observations,
            "phase": self.phase.value,
            "phase_detail": self.phase_detail,
            "expected_continuations": [item.value for item in self.expected_continuations],
            "lower_motor_action": self.lower_motor_action,
            "lower_motor_progress": self.lower_motor_progress,
            "lower_motor_error": self.lower_motor_error,
            "evidence_quality": self.evidence_quality,
            "freshness": self.freshness,
            "support_status": self.support_status,
            "material_event": self.material_event,
            "event_labels": list(self.event_labels),
            "valid": self.valid,
            "reason": self.reason,
            "source_linked": True,
            "creates_navmap_revision": False,
            "stores_full_navmap_history": False,
            "lower_motor_trajectory_present": False,
        }


@dataclass(frozen=True, slots=True)
class TemporalDynamicEnvelopeV1:
    """One compact expected continuation for the next current observation."""

    relation: TemporalRelationV1
    source_observation_no: int
    source_map_ref: Optional[NavMapRefV1]
    frame_id: str
    units: str
    expected_motion_direction: TemporalMotionDirectionV1
    minimum_speed: Optional[float]
    maximum_speed: Optional[float]
    minimum_relative_rate: Optional[float]
    maximum_relative_rate: Optional[float]
    minimum_scalar_rate: Optional[float]
    maximum_scalar_rate: Optional[float]
    expected_contact: Optional[bool]
    expected_support: Optional[bool]
    slip_allowed: bool
    expected_phase: Optional[TemporalPhaseV1]
    minimum_progress: Optional[float]
    source_action: Optional[str]
    uncertainty: float
    horizon_observations: int
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.relation, TemporalRelationV1):
            raise TypeError("relation must be TemporalRelationV1")
        _require_positive_int(self.source_observation_no, field_name="source_observation_no")
        if self.source_map_ref is not None and not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be NavMapRefV1 or None")
        for field_name in ("frame_id", "units", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.expected_motion_direction, TemporalMotionDirectionV1):
            raise TypeError("expected_motion_direction must be TemporalMotionDirectionV1")
        for field_name in (
            "minimum_speed",
            "maximum_speed",
            "minimum_relative_rate",
            "maximum_relative_rate",
            "minimum_scalar_rate",
            "maximum_scalar_rate",
        ):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite_float(value, field_name=field_name)
                if field_name in {"minimum_speed", "maximum_speed"} and number < 0.0:
                    raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, number)
        for low_name, high_name in (
            ("minimum_speed", "maximum_speed"),
            ("minimum_relative_rate", "maximum_relative_rate"),
            ("minimum_scalar_rate", "maximum_scalar_rate"),
        ):
            low = getattr(self, low_name)
            high = getattr(self, high_name)
            if low is not None and high is not None and low > high:
                raise ValueError(f"{low_name} cannot exceed {high_name}")
        for field_name in ("expected_contact", "expected_support"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        if not isinstance(self.slip_allowed, bool):
            raise TypeError("slip_allowed must be bool")
        if self.expected_phase is not None and not isinstance(self.expected_phase, TemporalPhaseV1):
            raise TypeError("expected_phase must be TemporalPhaseV1 or None")
        if self.minimum_progress is not None:
            object.__setattr__(self, "minimum_progress", _unit_interval(self.minimum_progress, field_name="minimum_progress"))
        if self.source_action is not None:
            _require_nonempty_text(self.source_action, field_name="source_action")
        object.__setattr__(self, "uncertainty", _finite_non_negative_float(self.uncertainty, field_name="uncertainty"))
        _require_positive_int(self.horizon_observations, field_name="horizon_observations")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe expected dynamic envelope."""
        return {
            "schema": "temporal_dynamic_envelope_v1",
            "phase": "7",
            "source_class": "expected",
            "current_truth": False,
            "relation": self.relation.value,
            "source_observation_no": self.source_observation_no,
            "source_map_ref": _optional_ref_dict(self.source_map_ref),
            "frame_id": self.frame_id,
            "units": self.units,
            "expected_motion_direction": self.expected_motion_direction.value,
            "speed_range": {"minimum": self.minimum_speed, "maximum": self.maximum_speed},
            "relative_rate_range": {
                "minimum": self.minimum_relative_rate,
                "maximum": self.maximum_relative_rate,
            },
            "scalar_rate_range": {"minimum": self.minimum_scalar_rate, "maximum": self.maximum_scalar_rate},
            "expected_contact": self.expected_contact,
            "expected_support": self.expected_support,
            "slip_allowed": self.slip_allowed,
            "expected_phase": self.expected_phase.value if self.expected_phase is not None else None,
            "minimum_progress": self.minimum_progress,
            "source_action": self.source_action,
            "uncertainty": self.uncertainty,
            "horizon_observations": self.horizon_observations,
            "reason": self.reason,
            "creates_navmap_revision": False,
            "contains_motor_trajectory": False,
        }


@dataclass(frozen=True, slots=True)
class TemporalStructuredResidualV1:
    """Structured expected-envelope versus current-evidence comparison."""

    relation: TemporalRelationV1
    expected_source_observation_no: Optional[int]
    observed_observation_no: int
    status: TemporalEnvelopeStatusV1
    residual_fields: dict[str, dict[str, Any]]
    mismatch_count: int
    uncertainty: float
    event_boundary: bool
    material_change_candidate: bool
    persistent_residual_count: int
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.relation, TemporalRelationV1):
            raise TypeError("relation must be TemporalRelationV1")
        if self.expected_source_observation_no is not None:
            _require_positive_int(self.expected_source_observation_no, field_name="expected_source_observation_no")
        _require_positive_int(self.observed_observation_no, field_name="observed_observation_no")
        if not isinstance(self.status, TemporalEnvelopeStatusV1):
            raise TypeError("status must be TemporalEnvelopeStatusV1")
        if not isinstance(self.residual_fields, dict):
            raise TypeError("residual_fields must be dict")
        _require_non_negative_int(self.mismatch_count, field_name="mismatch_count")
        object.__setattr__(self, "uncertainty", _finite_non_negative_float(self.uncertainty, field_name="uncertainty"))
        for field_name in ("event_boundary", "material_change_candidate"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        _require_non_negative_int(self.persistent_residual_count, field_name="persistent_residual_count")
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe structured dynamic residual."""
        return {
            "schema": "temporal_structured_residual_v1",
            "phase": "7",
            "relation": self.relation.value,
            "expected_source_observation_no": self.expected_source_observation_no,
            "observed_observation_no": self.observed_observation_no,
            "status": self.status.value,
            "residual_fields": dict(self.residual_fields),
            "mismatch_count": self.mismatch_count,
            "uncertainty": self.uncertainty,
            "event_boundary": self.event_boundary,
            "material_change_candidate": self.material_change_candidate,
            "persistent_residual_count": self.persistent_residual_count,
            "reason": self.reason,
            "expected_did_not_become_observed": True,
            "creates_navmap_revision": False,
        }


@dataclass(frozen=True, slots=True)
class TemporalMaterialityDecisionV1:
    """Sparse Phase 7 event/materiality gate for current live dynamics."""

    observation_no: int
    event_labels: tuple[str, ...]
    material_change_relations: tuple[TemporalRelationV1, ...]
    persistent_residual_relations: tuple[TemporalRelationV1, ...]
    event_boundary: bool
    material_change_recommended: bool
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        if not isinstance(self.event_labels, tuple) or not all(isinstance(item, str) and item for item in self.event_labels):
            raise TypeError("event_labels must be a tuple of non-empty strings")
        for field_name in ("material_change_relations", "persistent_residual_relations"):
            value = getattr(self, field_name)
            if not isinstance(value, tuple) or not all(isinstance(item, TemporalRelationV1) for item in value):
                raise TypeError(f"{field_name} must contain TemporalRelationV1 values")
        for field_name in ("event_boundary", "material_change_recommended"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe event/material-change decision."""
        return {
            "schema": "temporal_materiality_decision_v1",
            "phase": "7",
            "observation_no": self.observation_no,
            "event_labels": list(self.event_labels),
            "material_change_relations": [item.value for item in self.material_change_relations],
            "persistent_residual_relations": [item.value for item in self.persistent_residual_relations],
            "event_boundary": self.event_boundary,
            "material_change_recommended": self.material_change_recommended,
            "phase7_creates_navmap_revision": False,
            "phase7_creates_episodic_memory": False,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TemporalBindingStateV1:
    """One current Phase 7 generalized temporal-binding transaction."""

    observation_no: int
    overlays: tuple[TemporalBindingOverlayV1, ...]
    residuals: tuple[TemporalStructuredResidualV1, ...]
    pending_envelopes: tuple[TemporalDynamicEnvelopeV1, ...]
    materiality: TemporalMaterialityDecisionV1
    phase4b_comparison: dict[str, Any]
    shared_window_capacity: int
    shared_window_frame_count: int

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        if not isinstance(self.overlays, tuple) or not all(isinstance(item, TemporalBindingOverlayV1) for item in self.overlays):
            raise TypeError("overlays must contain TemporalBindingOverlayV1 values")
        if not isinstance(self.residuals, tuple) or not all(isinstance(item, TemporalStructuredResidualV1) for item in self.residuals):
            raise TypeError("residuals must contain TemporalStructuredResidualV1 values")
        if not isinstance(self.pending_envelopes, tuple) or not all(
            isinstance(item, TemporalDynamicEnvelopeV1) for item in self.pending_envelopes
        ):
            raise TypeError("pending_envelopes must contain TemporalDynamicEnvelopeV1 values")
        if not isinstance(self.materiality, TemporalMaterialityDecisionV1):
            raise TypeError("materiality must be TemporalMaterialityDecisionV1")
        if not isinstance(self.phase4b_comparison, dict):
            raise TypeError("phase4b_comparison must be dict")
        _require_positive_int(self.shared_window_capacity, field_name="shared_window_capacity")
        _require_non_negative_int(self.shared_window_frame_count, field_name="shared_window_frame_count")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe Phase 7 state without full-map snapshots."""
        return {
            "schema": "temporal_binding_state_v1",
            "phase": "7",
            "authority": "source_linked_live_dynamics",
            "observation_no": self.observation_no,
            "overlays": {item.relation.value: item.as_dict() for item in self.overlays},
            "residuals": {item.relation.value: item.as_dict() for item in self.residuals},
            "pending_envelopes": {item.relation.value: item.as_dict() for item in self.pending_envelopes},
            "materiality": self.materiality.as_dict(),
            "phase4b_comparison": dict(self.phase4b_comparison),
            "shared_window": "ctx.seqerr_history.live_dynamics_v1",
            "shared_window_capacity": self.shared_window_capacity,
            "shared_window_frame_count": self.shared_window_frame_count,
            "rolling_history_bounded": True,
            "rolling_history_typed_on_reconstruction": True,
            "separate_from_episodic_memory": True,
            "stores_full_navmap_history": False,
            "creates_navmap_revision": False,
            "policy_selection_mutation_allowed": False,
            "protected_safety_can_be_overridden": False,
            "lower_motor_trajectory_present": False,
        }


def _ctx_int(ctx: Any, name: str, default: int) -> int:
    """Read one context integer with a deterministic fallback."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ctx_float(ctx: Any, name: str, default: float) -> float:
    """Read one finite context float with a deterministic fallback."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _window_capacity(ctx: Any) -> int:
    """Return the existing bounded seqerr window capacity."""
    return max(2, min(25, _ctx_int(ctx, "seqerr_window", 4)))


def _history_limit(ctx: Any) -> int:
    """Return the bounded sparse event-history limit."""
    value = _ctx_int(ctx, "live_dynamics_event_history_limit_v1", _DEFAULT_HISTORY_LIMIT)
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _next_observation_no(ctx: Any) -> int:
    """Advance the deterministic Phase 7 observation counter."""
    current = max(0, _ctx_int(ctx, "live_dynamics_observation_no_v1", 0))
    observation_no = current + 1
    ctx.live_dynamics_observation_no_v1 = observation_no
    return observation_no


def _meta(env_obs: EnvObservation) -> dict[str, Any]:
    """Return a defensive observation metadata dictionary."""
    raw = getattr(env_obs, "env_meta", None)
    return dict(raw) if isinstance(raw, dict) else {}


def _point_from_value(value: Any) -> Optional[NavPointV1]:
    """Decode one finite ``{x, y}`` point."""
    if not isinstance(value, dict):
        return None
    x = _optional_float(value.get("x"))
    y = _optional_float(value.get("y"))
    if x is None or y is None:
        return None
    try:
        return NavPointV1(x=x, y=y)
    except (TypeError, ValueError):
        return None


def _ref_from_dict(value: Any) -> Optional[NavMapRefV1]:
    """Decode one optional JSON map reference."""
    if not isinstance(value, dict):
        return None
    map_id = value.get("map_id")
    revision = value.get("revision")
    if not isinstance(map_id, str) or not map_id:
        return None
    if isinstance(revision, bool) or not isinstance(revision, int) or revision <= 0:
        return None
    try:
        return NavMapRefV1(map_id, revision)
    except (TypeError, ValueError):
        return None


def _sample_from_dict(value: Any) -> Optional[TemporalBindingSampleV1]:
    """Reconstruct one typed sample from the JSON-safe shared window."""
    if not isinstance(value, dict) or value.get("schema") != "temporal_binding_sample_v1":
        return None
    relation_raw = value.get("relation")
    try:
        relation = TemporalRelationV1(str(relation_raw))
    except ValueError:
        return None
    event_labels_raw = value.get("event_labels")
    event_labels = tuple(item for item in event_labels_raw if isinstance(item, str) and item) if isinstance(
        event_labels_raw, list
    ) else ()

    observation_no = _optional_non_negative_int(value.get("observation_no"))
    if observation_no is None or observation_no <= 0:
        return None

    try:
        return TemporalBindingSampleV1(
            relation=relation,
            observation_no=observation_no,
            source_ref=str(value.get("source_ref")),
            source_map_ref=_ref_from_dict(value.get("source_map_ref")),
            subject_identity_handle=str(value.get("subject_identity_handle")),
            object_identity_handle=_optional_text(value.get("object_identity_handle")),
            frame_id=str(value.get("frame_id")),
            units=str(value.get("units")),
            step_index=_optional_non_negative_int(value.get("step_index")),
            controller_steps=max(0, int(value.get("controller_steps", 0))),
            time_since_birth=_optional_float(value.get("time_since_birth")),
            subject_point=_point_from_value(value.get("subject_point")),
            object_point=_point_from_value(value.get("object_point")),
            relative_distance=_optional_float(value.get("relative_distance")),
            scalar_value=_optional_float(value.get("scalar_value")),
            contact=_optional_bool(value.get("contact")),
            support=_optional_bool(value.get("support")),
            slip=_optional_bool(value.get("slip")),
            phase_hint=_optional_text(value.get("phase_hint")),
            lower_motor_action=_optional_text(value.get("lower_motor_action")),
            lower_motor_progress=_optional_float(value.get("lower_motor_progress")),
            lower_motor_error=_optional_text(value.get("lower_motor_error")),
            evidence_quality=float(value.get("evidence_quality", 0.0)),
            material_event=bool(value.get("material_event", False)),
            event_labels=event_labels,
            valid=bool(value.get("valid", False)),
            reason=str(value.get("reason") or "sample_reconstructed"),
        )
    except (TypeError, ValueError):
        return None


def _frame_matches_current(frame: dict[str, Any], *, step_index: Optional[int], time_value: Optional[float]) -> bool:
    """Return whether a generic seqerr frame belongs to the current observation."""
    frame_step = _optional_non_negative_int(frame.get("step"))
    if step_index is not None and frame_step is not None and step_index == frame_step:
        frame_time = _optional_float(frame.get("t"))
        if time_value is None or frame_time is None:
            return True
        return math.isclose(time_value, frame_time, rel_tol=0.0, abs_tol=1.0e-9)
    frame_time = _optional_float(frame.get("t"))
    if time_value is not None and frame_time is not None:
        return math.isclose(time_value, frame_time, rel_tol=0.0, abs_tol=1.0e-9)
    return False


def _attach_samples_to_shared_window(
    ctx: Any,
    samples: Sequence[TemporalBindingSampleV1],
) -> tuple[list[dict[str, Any]], int]:
    """Attach compact relation samples to the existing bounded seqerr window."""
    capacity = _window_capacity(ctx)
    raw_history = getattr(ctx, "seqerr_history", None)
    history = [dict(item) for item in raw_history if isinstance(item, dict)] if isinstance(raw_history, list) else []
    first = samples[0]
    use_latest = bool(
        history
        and _frame_matches_current(
            history[-1],
            step_index=first.step_index,
            time_value=first.time_since_birth,
        )
    )
    if use_latest:
        frame = history[-1]
    else:
        frame = {
            "step": first.step_index if first.step_index is not None else first.controller_steps,
            "t": first.time_since_birth,
            "raw": {},
            "slots": {},
        }
        history.append(frame)

    bucket = frame.get(_BUCKET_KEY)
    bucket = dict(bucket) if isinstance(bucket, dict) else {}
    for sample in samples:
        bucket[sample.relation.value] = sample.as_dict()
    frame[_BUCKET_KEY] = bucket

    if len(history) > capacity:
        del history[: len(history) - capacity]
    ctx.seqerr_history = history
    return history, capacity


def _samples_for_relation(
    history: Sequence[dict[str, Any]],
    relation: TemporalRelationV1,
) -> list[TemporalBindingSampleV1]:
    """Return typed samples for one relation from the shared bounded window."""
    out: list[TemporalBindingSampleV1] = []
    for frame in history:
        if not isinstance(frame, dict):
            continue
        bucket = frame.get(_BUCKET_KEY)
        if not isinstance(bucket, dict):
            continue
        sample = _sample_from_dict(bucket.get(relation.value))
        if sample is not None:
            out.append(sample)
    return out


def _compatible_valid_suffix(samples: Sequence[TemporalBindingSampleV1]) -> list[TemporalBindingSampleV1]:
    """Return the contiguous valid suffix for one identity, object, frame, and units."""
    if not samples or not samples[-1].valid:
        return []
    latest = samples[-1]
    suffix: list[TemporalBindingSampleV1] = []
    for sample in reversed(samples):
        if not sample.valid:
            break
        if sample.relation is not latest.relation:
            break
        if sample.subject_identity_handle != latest.subject_identity_handle:
            break
        if sample.object_identity_handle != latest.object_identity_handle:
            break
        if sample.frame_id != latest.frame_id or sample.units != latest.units:
            break
        if (
            latest.relation is TemporalRelationV1.LOWER_MOTOR
            and sample.lower_motor_action != latest.lower_motor_action
        ):
            break
        suffix.append(sample)
    suffix.reverse()
    return suffix


def _strictly_increasing(values: Sequence[float]) -> bool:
    """Return whether every adjacent value increases by more than the minimum dt."""
    return all((right - left) > _MINIMUM_DT for left, right in zip(values, values[1:]))


def _time_axis(samples: Sequence[TemporalBindingSampleV1]) -> tuple[Optional[str], list[float]]:
    """Choose current observation timing without creating another clock."""
    times = [sample.time_since_birth for sample in samples]
    if all(value is not None for value in times):
        values = [float(value) for value in times if value is not None]
        if _strictly_increasing(values):
            return "time_since_birth", values
    steps = [sample.step_index for sample in samples]
    if all(value is not None for value in steps):
        values = [float(value) for value in steps if value is not None]
        if _strictly_increasing(values):
            return "step_index", values
    values = [float(sample.controller_steps) for sample in samples]
    if _strictly_increasing(values):
        return "controller_steps", values
    return None, []


def _pair_rates(values: Sequence[float], axis: Sequence[float]) -> list[float]:
    """Return finite adjacent rates for one scalar series."""
    rates: list[float] = []
    for left, right, t0, t1 in zip(values, values[1:], axis, axis[1:]):
        dt = t1 - t0
        if dt <= _MINIMUM_DT:
            continue
        rates.append((right - left) / dt)
    return rates


def _rate_uncertainty(*rate_groups: Sequence[float]) -> Optional[float]:
    """Return maximum absolute deviation across available adjacent-rate groups."""
    deviations: list[float] = []
    for rates in rate_groups:
        if not rates:
            continue
        mean = fmean(rates)
        deviations.extend(abs(value - mean) for value in rates)
    return max(deviations) if deviations else None


def _direction_from_velocity(vx: Optional[float], vy: Optional[float], *, tolerance: float) -> TemporalMotionDirectionV1:
    """Return one deterministic eight-way direction or STILL/UNKNOWN."""
    if vx is None or vy is None:
        return TemporalMotionDirectionV1.UNKNOWN
    speed = math.hypot(vx, vy)
    if speed <= tolerance:
        return TemporalMotionDirectionV1.STILL
    angle = math.degrees(math.atan2(vy, vx)) % 360.0
    if angle < 22.5 or angle >= 337.5:
        return TemporalMotionDirectionV1.EAST
    if angle < 67.5:
        return TemporalMotionDirectionV1.NORTH_EAST
    if angle < 112.5:
        return TemporalMotionDirectionV1.NORTH
    if angle < 157.5:
        return TemporalMotionDirectionV1.NORTH_WEST
    if angle < 202.5:
        return TemporalMotionDirectionV1.WEST
    if angle < 247.5:
        return TemporalMotionDirectionV1.SOUTH_WEST
    if angle < 292.5:
        return TemporalMotionDirectionV1.SOUTH
    return TemporalMotionDirectionV1.SOUTH_EAST


def _distance_trend(rate: Optional[float], *, tolerance: float) -> TemporalDistanceTrendV1:
    """Return approach/stable/recession from one signed separation rate."""
    if rate is None:
        return TemporalDistanceTrendV1.UNKNOWN
    if rate < -tolerance:
        return TemporalDistanceTrendV1.APPROACHING
    if rate > tolerance:
        return TemporalDistanceTrendV1.RECEDING
    return TemporalDistanceTrendV1.STABLE


def _phase_from_hint(
    sample: TemporalBindingSampleV1,
    *,
    motion_direction: TemporalMotionDirectionV1,
    previous: Optional[TemporalBindingOverlayV1],
) -> tuple[TemporalPhaseV1, str]:
    """Return one generic phase and preserved domain-specific detail label."""
    hint = str(sample.phase_hint or "unknown").strip().lower()
    if sample.lower_motor_error or sample.slip is True or sample.support is False:
        return TemporalPhaseV1.INTERRUPTED, hint if hint != "unknown" else "lower_controller_interruption"
    completed_hints = {"completed", "shelter_reached", "milk_obtained", "resting", "latched"}
    maintaining_hints = {"maintaining", "contact", "suckling", "supported", "stable", "holding"}
    idle_hints = {"idle", "none"}
    starting_hints = {"starting", "searching", "localizing"}
    active_hints = {"active", "reaching", "approaching", "receding", "moving"}
    if hint in completed_hints:
        return TemporalPhaseV1.COMPLETED, hint
    if hint in maintaining_hints:
        return TemporalPhaseV1.MAINTAINING, hint
    if hint in idle_hints:
        return TemporalPhaseV1.IDLE, hint
    if hint in starting_hints:
        return TemporalPhaseV1.STARTING, hint
    if hint in active_hints:
        return TemporalPhaseV1.ACTIVE, hint
    if sample.lower_motor_progress is not None:
        if sample.lower_motor_progress >= 1.0:
            return TemporalPhaseV1.COMPLETED, "progress_complete"
        if sample.lower_motor_progress <= 0.0:
            return TemporalPhaseV1.STARTING, "progress_starting"
        return TemporalPhaseV1.ACTIVE, "progress_active"
    if sample.contact is True or sample.support is True:
        return TemporalPhaseV1.MAINTAINING, "relation_maintained"
    if motion_direction not in {TemporalMotionDirectionV1.STILL, TemporalMotionDirectionV1.UNKNOWN}:
        return TemporalPhaseV1.ACTIVE, "motion_active"
    if previous is not None and previous.valid:
        return TemporalPhaseV1.MAINTAINING, "stable_live_relation"
    return TemporalPhaseV1.UNKNOWN, "unknown"


def _duration_value(
    current: Optional[bool],
    previous_value: Optional[bool],
    previous_duration: Optional[int],
    *,
    compatible_previous: bool,
) -> Optional[int]:
    """Return one compact live duration without storing an unbounded sequence."""
    if current is None:
        return None
    if not current:
        return 0
    if compatible_previous and previous_value is True:
        return int(previous_duration or 0) + 1
    return 1


def _expected_continuations(
    sample: TemporalBindingSampleV1,
    *,
    motion_direction: TemporalMotionDirectionV1,
    distance_trend: TemporalDistanceTrendV1,
    phase: TemporalPhaseV1,
) -> tuple[TemporalExpectedContinuationV1, ...]:
    """Return bounded one-step continuation semantics for one current overlay."""
    out: list[TemporalExpectedContinuationV1] = []
    if motion_direction not in {TemporalMotionDirectionV1.STILL, TemporalMotionDirectionV1.UNKNOWN}:
        out.append(TemporalExpectedContinuationV1.CONTINUE_MOTION)
    elif motion_direction is TemporalMotionDirectionV1.STILL and phase in {
        TemporalPhaseV1.MAINTAINING,
        TemporalPhaseV1.COMPLETED,
    }:
        out.append(TemporalExpectedContinuationV1.HOLD_POSITION)
    if distance_trend is TemporalDistanceTrendV1.APPROACHING:
        out.append(TemporalExpectedContinuationV1.CONTINUE_APPROACH)
    elif distance_trend is TemporalDistanceTrendV1.RECEDING:
        out.append(TemporalExpectedContinuationV1.CONTINUE_RECESSION)
    if sample.contact is True:
        out.append(TemporalExpectedContinuationV1.MAINTAIN_CONTACT)
    if sample.support is True:
        out.append(TemporalExpectedContinuationV1.MAINTAIN_SUPPORT)
    if sample.lower_motor_progress is not None and phase in {
        TemporalPhaseV1.STARTING,
        TemporalPhaseV1.ACTIVE,
        TemporalPhaseV1.MAINTAINING,
    }:
        out.append(TemporalExpectedContinuationV1.PROGRESS_NONDECREASING)
        out.append(TemporalExpectedContinuationV1.AVOID_NEW_ERROR)
    if not out:
        out.append(TemporalExpectedContinuationV1.UNKNOWN)
    return tuple(dict.fromkeys(out))


def _previous_overlay(
    previous_state: Optional[TemporalBindingStateV1],
    relation: TemporalRelationV1,
) -> Optional[TemporalBindingOverlayV1]:
    """Return the preceding overlay for one relation."""
    if previous_state is None:
        return None
    return next((item for item in previous_state.overlays if item.relation is relation), None)


def _decode_overlay(
    ctx: Any,
    relation_samples: Sequence[TemporalBindingSampleV1],
    *,
    previous: Optional[TemporalBindingOverlayV1],
    window_capacity: int,
) -> TemporalBindingOverlayV1:
    """Decode one current relation from its identity/frame-consistent suffix."""
    current = relation_samples[-1]
    suffix = _compatible_valid_suffix(relation_samples)
    speed_tolerance = max(0.0, _ctx_float(ctx, "live_dynamics_speed_tolerance_v1", _DEFAULT_SPEED_TOLERANCE))
    relative_tolerance = max(
        0.0,
        _ctx_float(ctx, "live_dynamics_relative_rate_tolerance_v1", _DEFAULT_RELATIVE_RATE_TOLERANCE),
    )

    interval_source: Optional[str] = None
    elapsed_time: Optional[float] = None
    velocity_x: Optional[float] = None
    velocity_y: Optional[float] = None
    speed: Optional[float] = None
    self_velocity_x: Optional[float] = None
    self_velocity_y: Optional[float] = None
    object_velocity_x: Optional[float] = None
    object_velocity_y: Optional[float] = None
    object_speed: Optional[float] = None
    self_motion_compensated = False
    relative_start: Optional[float] = None
    relative_end: Optional[float] = None
    relative_rate: Optional[float] = None
    scalar_rate: Optional[float] = None
    uncertainty: Optional[float] = None
    motion_supported = False

    axis_name, axis = _time_axis(suffix)
    if len(suffix) >= 2 and axis_name is not None and axis:
        elapsed = axis[-1] - axis[0]
        if elapsed > _MINIMUM_DT:
            interval_source = axis_name
            elapsed_time = elapsed

            subject_points = [sample.subject_point for sample in suffix]
            if all(point is not None for point in subject_points):
                points = [point for point in subject_points if point is not None]
                velocity_x = (points[-1].x - points[0].x) / elapsed
                velocity_y = (points[-1].y - points[0].y) / elapsed
                speed = math.hypot(velocity_x, velocity_y)
                motion_supported = True
                x_rates = _pair_rates([point.x for point in points], axis)
                y_rates = _pair_rates([point.y for point in points], axis)
            else:
                x_rates = []
                y_rates = []

            object_points = [sample.object_point for sample in suffix]
            if all(point is not None for point in object_points) and all(point is not None for point in subject_points):
                subjects = [point for point in subject_points if point is not None]
                objects = [point for point in object_points if point is not None]
                self_velocity_x = (subjects[-1].x - subjects[0].x) / elapsed
                self_velocity_y = (subjects[-1].y - subjects[0].y) / elapsed
                rel_x_start = objects[0].x - subjects[0].x
                rel_y_start = objects[0].y - subjects[0].y
                rel_x_end = objects[-1].x - subjects[-1].x
                rel_y_end = objects[-1].y - subjects[-1].y
                relative_velocity_x = (rel_x_end - rel_x_start) / elapsed
                relative_velocity_y = (rel_y_end - rel_y_start) / elapsed
                object_velocity_x = relative_velocity_x + self_velocity_x
                object_velocity_y = relative_velocity_y + self_velocity_y
                object_speed = math.hypot(object_velocity_x, object_velocity_y)
                self_motion_compensated = True
                object_x_rates = _pair_rates([point.x for point in objects], axis)
                object_y_rates = _pair_rates([point.y for point in objects], axis)
            else:
                object_x_rates = []
                object_y_rates = []

            distances = [sample.relative_distance for sample in suffix]
            if all(value is not None for value in distances):
                distance_values = [float(value) for value in distances if value is not None]
                relative_start = distance_values[0]
                relative_end = distance_values[-1]
                relative_rate = (relative_end - relative_start) / elapsed
                distance_rates = _pair_rates(distance_values, axis)
            else:
                distance_rates = []

            scalars = [sample.scalar_value for sample in suffix]
            if all(value is not None for value in scalars):
                scalar_values = [float(value) for value in scalars if value is not None]
                scalar_rate = (scalar_values[-1] - scalar_values[0]) / elapsed
                scalar_rates = _pair_rates(scalar_values, axis)
                if not motion_supported:
                    velocity_x = scalar_rate
                    velocity_y = 0.0
                    speed = abs(scalar_rate)
                    motion_supported = True
            else:
                scalar_rates = []

            uncertainty = _rate_uncertainty(
                x_rates,
                y_rates,
                object_x_rates,
                object_y_rates,
                distance_rates,
                scalar_rates,
            )

    primary_vx = object_velocity_x if current.relation is TemporalRelationV1.SELF_MATERNAL and self_motion_compensated else velocity_x
    primary_vy = object_velocity_y if current.relation is TemporalRelationV1.SELF_MATERNAL and self_motion_compensated else velocity_y
    motion_direction = _direction_from_velocity(primary_vx, primary_vy, tolerance=speed_tolerance)
    distance_trend = _distance_trend(relative_rate, tolerance=relative_tolerance)

    compatible_previous = bool(
        previous is not None
        and previous.observation_no == current.observation_no - 1
        and previous.subject_identity_handle == current.subject_identity_handle
        and previous.object_identity_handle == current.object_identity_handle
        and previous.frame_id == current.frame_id
        and previous.units == current.units
    )
    contact_duration = _duration_value(
        current.contact,
        previous.contact if previous is not None else None,
        previous.contact_duration_observations if previous is not None else None,
        compatible_previous=compatible_previous,
    )
    support_duration = _duration_value(
        current.support,
        previous.support if previous is not None else None,
        previous.support_duration_observations if previous is not None else None,
        compatible_previous=compatible_previous,
    )
    phase, phase_detail = _phase_from_hint(current, motion_direction=motion_direction, previous=previous)

    event_labels = list(current.event_labels)
    if previous is not None and compatible_previous:
        if current.contact is not None and previous.contact is not None and current.contact != previous.contact:
            event_labels.append("contact_acquired" if current.contact else "contact_lost")
        if current.support is not None and previous.support is not None and current.support != previous.support:
            event_labels.append("support_acquired" if current.support else "support_lost")
        if phase is not previous.phase:
            event_labels.append(f"phase_{previous.phase.value}_to_{phase.value}")
    elif previous is not None:
        event_labels.append("identity_or_frame_continuity_reset")
    if current.slip is True:
        event_labels.append("slip_detected")
    if current.lower_motor_error is not None:
        event_labels.append("lower_motor_error")

    valid = bool(current.valid)
    if not valid:
        support_status = "unsupported"
        freshness = "unknown"
        reason = current.reason
    elif len(suffix) < 2:
        support_status = "insufficient_history"
        freshness = "fresh"
        reason = "current_relation_supported_motion_history_insufficient"
    else:
        support_status = "supported"
        freshness = "fresh"
        reason = "bounded_general_temporal_relation_supported"

    expected = _expected_continuations(
        current,
        motion_direction=motion_direction,
        distance_trend=distance_trend,
        phase=phase,
    )
    return TemporalBindingOverlayV1(
        relation=current.relation,
        observation_no=current.observation_no,
        source_map_ref=current.source_map_ref,
        subject_identity_handle=current.subject_identity_handle,
        object_identity_handle=current.object_identity_handle,
        frame_id=current.frame_id,
        units=current.units,
        window_capacity=window_capacity,
        window_sample_count=len(relation_samples),
        valid_sample_count=len(suffix),
        interval_source=interval_source,
        elapsed_time=elapsed_time,
        motion_supported=motion_supported,
        motion_direction=motion_direction,
        velocity_x=velocity_x,
        velocity_y=velocity_y,
        speed=speed,
        self_velocity_x=self_velocity_x,
        self_velocity_y=self_velocity_y,
        object_velocity_x=object_velocity_x,
        object_velocity_y=object_velocity_y,
        object_speed=object_speed,
        self_motion_compensated=self_motion_compensated,
        relative_distance_start=relative_start,
        relative_distance_end=relative_end,
        relative_distance_rate=relative_rate,
        distance_trend=distance_trend,
        scalar_rate=scalar_rate,
        rate_uncertainty=uncertainty,
        contact=current.contact,
        support=current.support,
        slip=current.slip,
        contact_duration_observations=contact_duration,
        support_duration_observations=support_duration,
        phase=phase,
        phase_detail=phase_detail,
        expected_continuations=expected,
        lower_motor_action=current.lower_motor_action,
        lower_motor_progress=current.lower_motor_progress,
        lower_motor_error=current.lower_motor_error,
        evidence_quality=current.evidence_quality,
        freshness=freshness,
        support_status=support_status,
        material_event=current.material_event,
        event_labels=tuple(dict.fromkeys(event_labels)),
        valid=valid,
        reason=reason,
    )


def _map_ref_from_terrain_state(ctx: Any) -> Optional[NavMapRefV1]:
    """Return the current source-linked terrain route reference."""
    state = getattr(ctx, "terrain_state_v1", None)
    if isinstance(state, TerrainWnmStateV1) and state.operative_route_map_ref is not None:
        return state.operative_route_map_ref
    operative = wnm_operative_map_v1(ctx)
    if operative is not None and operative.role in {"terrain_route_west", "terrain_route_east"}:
        return NavMapRefV1(operative.map_id, operative.revision)
    return None


def _sample_common(
    ctx: Any,
    meta: dict[str, Any],
) -> tuple[Optional[int], int, Optional[float]]:
    """Return current step/controller/time values without introducing another clock."""
    step_index = _optional_non_negative_int(meta.get("step_index"))
    controller_steps = max(0, _ctx_int(ctx, "controller_steps", 0))
    time_value = _optional_float(meta.get("time_since_birth"))
    return step_index, controller_steps, time_value


def _maternal_sample(
    ctx: Any,
    meta: dict[str, Any],
    *,
    observation_no: int,
) -> TemporalBindingSampleV1:
    """Build current SELF-maternal world-frame evidence for compensation."""
    step_index, controller_steps, time_value = _sample_common(ctx, meta)
    geometry = getattr(ctx, "navmap_maternal_state", None)
    continuity = getattr(ctx, "navmap_maternal_continuity_state", None)
    source_map_ref = geometry.evidence_ref if isinstance(geometry, MaternalGeometryShadowStateV1) else None
    self_point = _point_from_value(meta.get("kid_position"))
    maternal_point = _point_from_value(meta.get("mom_position"))
    identity = (
        continuity.tracked_identity_handle
        if isinstance(continuity, MaternalContinuityShadowStateV1)
        else _MATERNAL_IDENTITY_FALLBACK
    )
    exact = bool(
        isinstance(continuity, MaternalContinuityShadowStateV1)
        and continuity.identity_support is MaternalIdentitySupportV1.SUPPORTED
        and continuity.observability is MaternalObservabilityV1.OBSERVED
        and continuity.localization_status is MaternalLocalizationStatusV1.CURRENT_EXACT
        and continuity.track_status is MaternalTrackStatusV1.ACTIVE
        and continuity.localization_authoritative
        and self_point is not None
        and maternal_point is not None
    )
    distance = (
        math.hypot(maternal_point.x - self_point.x, maternal_point.y - self_point.y)
        if exact and self_point is not None and maternal_point is not None
        else None
    )
    event_labels: list[str] = []
    if isinstance(continuity, MaternalContinuityShadowStateV1):
        if continuity.identity_support in {MaternalIdentitySupportV1.AMBIGUOUS, MaternalIdentitySupportV1.MISMATCH}:
            event_labels.append(f"maternal_identity_{continuity.identity_support.value}")
        if continuity.track_status in {MaternalTrackStatusV1.LOST, MaternalTrackStatusV1.UNLOCALIZED}:
            event_labels.append(f"maternal_track_{continuity.track_status.value}")
    return TemporalBindingSampleV1(
        relation=TemporalRelationV1.SELF_MATERNAL,
        observation_no=observation_no,
        source_ref="phase4_current_exact_self_maternal_world_points_v1",
        source_map_ref=source_map_ref,
        subject_identity_handle=_SELF_IDENTITY,
        object_identity_handle=identity,
        frame_id="goat_route_world_frame_v1",
        units="m",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=self_point if exact else None,
        object_point=maternal_point if exact else None,
        relative_distance=distance,
        scalar_value=None,
        contact=None,
        support=None,
        slip=None,
        phase_hint=None,
        lower_motor_action=None,
        lower_motor_progress=None,
        lower_motor_error=None,
        evidence_quality=0.85 if exact else 0.0,
        material_event=False,
        event_labels=tuple(event_labels),
        valid=exact,
        reason="current_exact_identity_supported_self_maternal_points" if exact else "current_exact_maternal_world_points_unavailable",
    )


def _route_samples(
    ctx: Any,
    meta: dict[str, Any],
    *,
    observation_no: int,
) -> tuple[TemporalBindingSampleV1, TemporalBindingSampleV1]:
    """Build SELF-route and harmless route-vegetation samples."""
    step_index, controller_steps, time_value = _sample_common(ctx, meta)
    overlay = getattr(ctx, "terrain_dynamic_overlay_v1", None)
    source_map_ref = _map_ref_from_terrain_state(ctx)
    valid = bool(
        isinstance(overlay, TerrainDynamicOverlayV1)
        and overlay.current_evidence_supported
        and overlay.self_world_point is not None
    )
    point = overlay.self_world_point if isinstance(overlay, TerrainDynamicOverlayV1) and valid else None
    position_label = overlay.position_label if isinstance(overlay, TerrainDynamicOverlayV1) else "unknown"
    if position_label == "shelter_area":
        phase_hint = "shelter_reached"
    elif position_label in {"cliff_edge", "open_field"}:
        phase_hint = "moving"
    else:
        phase_hint = "unknown"
    material_event = bool(
        isinstance(overlay, TerrainDynamicOverlayV1)
        and overlay.route_structure_materially_changed
    )
    route_events = ("terrain_structure_materially_changed",) if material_event else ()
    route_sample = TemporalBindingSampleV1(
        relation=TemporalRelationV1.SELF_ROUTE,
        observation_no=observation_no,
        source_ref=(overlay.source_packet_ref if isinstance(overlay, TerrainDynamicOverlayV1) else "phase6_terrain_unavailable"),
        source_map_ref=source_map_ref,
        subject_identity_handle=_SELF_IDENTITY,
        object_identity_handle=None,
        frame_id="goat_route_world_frame_v1",
        units="m",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=point,
        object_point=None,
        relative_distance=None,
        scalar_value=None,
        contact=None,
        support=None,
        slip=None,
        phase_hint=phase_hint,
        lower_motor_action=None,
        lower_motor_progress=None,
        lower_motor_error=None,
        evidence_quality=0.90 if valid else 0.0,
        material_event=material_event,
        event_labels=route_events,
        valid=valid,
        reason="current_self_route_point_supported" if valid else "current_self_route_point_unavailable",
    )
    branch_value = (
        overlay.vegetation_branch_offset
        if isinstance(overlay, TerrainDynamicOverlayV1) and overlay.current_evidence_supported
        else None
    )
    vegetation_valid = branch_value is not None
    vegetation_sample = TemporalBindingSampleV1(
        relation=TemporalRelationV1.ROUTE_VEGETATION,
        observation_no=observation_no,
        source_ref=(overlay.source_packet_ref if isinstance(overlay, TerrainDynamicOverlayV1) else "phase6_terrain_unavailable"),
        source_map_ref=source_map_ref,
        subject_identity_handle=_ROUTE_VEGETATION_IDENTITY,
        object_identity_handle=None,
        frame_id="goat_route_world_frame_v1",
        units="m",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=None,
        object_point=None,
        relative_distance=None,
        scalar_value=branch_value,
        contact=None,
        support=None,
        slip=None,
        phase_hint="active" if vegetation_valid else "unknown",
        lower_motor_action=None,
        lower_motor_progress=None,
        lower_motor_error=None,
        evidence_quality=0.75 if vegetation_valid else 0.0,
        material_event=False,
        event_labels=(),
        valid=vegetation_valid,
        reason="periodic_vegetation_live_offset_supported" if vegetation_valid else "vegetation_offset_unavailable",
    )
    return route_sample, vegetation_sample


def _feeding_sample(
    ctx: Any,
    meta: dict[str, Any],
    *,
    observation_no: int,
) -> TemporalBindingSampleV1:
    """Build one current feeding-contact sample from the Phase 5 overlay."""
    step_index, controller_steps, time_value = _sample_common(ctx, meta)
    overlay = getattr(ctx, "feeding_overlay_v1", None)
    if isinstance(overlay, FeedingRelationOverlayV1):
        valid = overlay.freshness == "fresh" and overlay.support_status not in {"unsupported", "unavailable"}
        if overlay.milk_evidence is True:
            phase_hint = "milk_obtained"
        elif overlay.contact is True and overlay.latch_evidence is True:
            phase_hint = "suckling"
        elif overlay.contact is True:
            phase_hint = "contact"
        elif overlay.target_localized is True and overlay.reachability.value == "reachable":
            phase_hint = "reaching"
        else:
            phase_hint = "searching"
        phase_events: tuple[str, ...] = ()
        if overlay.contact_event.value in {"acquired", "lost"}:
            phase_events = (f"feeding_contact_{overlay.contact_event.value}",)
        return TemporalBindingSampleV1(
            relation=TemporalRelationV1.FEEDING_CONTACT,
            observation_no=observation_no,
            source_ref="phase5_feeding_relation_overlay_v1",
            source_map_ref=overlay.source_evidence_map_ref or overlay.operative_map_ref,
            subject_identity_handle="self_muzzle",
            object_identity_handle=overlay.nipple_identity_handle,
            frame_id="maternal_body_feeding_frame_v1",
            units="m",
            step_index=step_index,
            controller_steps=controller_steps,
            time_since_birth=time_value,
            subject_point=None,
            object_point=None,
            relative_distance=overlay.mouth_nipple_distance,
            scalar_value=None,
            contact=overlay.contact,
            support=None,
            slip=None,
            phase_hint=phase_hint,
            lower_motor_action=None,
            lower_motor_progress=None,
            lower_motor_error=None,
            evidence_quality=0.90 if valid else 0.0,
            material_event=False,
            event_labels=phase_events,
            valid=valid,
            reason="current_phase5_feeding_overlay_supported" if valid else "current_feeding_overlay_unsupported",
        )
    return TemporalBindingSampleV1(
        relation=TemporalRelationV1.FEEDING_CONTACT,
        observation_no=observation_no,
        source_ref="phase5_feeding_relation_overlay_unavailable",
        source_map_ref=None,
        subject_identity_handle="self_muzzle",
        object_identity_handle="maternal_nipple",
        frame_id="maternal_body_feeding_frame_v1",
        units="m",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=None,
        object_point=None,
        relative_distance=None,
        scalar_value=None,
        contact=None,
        support=None,
        slip=None,
        phase_hint="unknown",
        lower_motor_action=None,
        lower_motor_progress=None,
        lower_motor_error=None,
        evidence_quality=0.0,
        material_event=False,
        event_labels=(),
        valid=False,
        reason="phase5_feeding_overlay_unavailable",
    )


def _lower_motor_samples(
    ctx: Any,
    meta: dict[str, Any],
    *,
    observation_no: int,
    applied_policy: Optional[str],
) -> tuple[TemporalBindingSampleV1, TemporalBindingSampleV1]:
    """Build compact body-support and lower-controller feedback samples."""
    step_index, controller_steps, time_value = _sample_common(ctx, meta)
    packet = meta.get("lower_motor_feedback_v1")
    packet = dict(packet) if isinstance(packet, dict) else {}
    action = _optional_text(packet.get("action_applied")) or applied_policy
    support = _optional_bool(packet.get("support_contact"))
    slip = _optional_bool(packet.get("slip_detected"))
    progress = _optional_float(packet.get("progress"))
    if progress is not None:
        progress = min(1.0, max(0.0, progress))
    error = _optional_text(packet.get("error_code"))
    phase_hint = _optional_text(packet.get("phase")) or "unknown"
    quality = _optional_float(packet.get("quality"))
    quality = min(1.0, max(0.0, quality)) if quality is not None else 0.0
    source_ref = _optional_text(packet.get("source_ref")) or "lower_motor_feedback_unavailable"
    packet_valid = bool(packet.get("schema") == "lower_motor_feedback_v1")
    support_sample = TemporalBindingSampleV1(
        relation=TemporalRelationV1.BODY_SUPPORT,
        observation_no=observation_no,
        source_ref=source_ref,
        source_map_ref=None,
        subject_identity_handle=_BODY_SUPPORT_IDENTITY,
        object_identity_handle="ground_support_surface",
        frame_id="body_support_frame_v1",
        units="boolean_contact",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=None,
        object_point=None,
        relative_distance=None,
        scalar_value=None,
        contact=None,
        support=support,
        slip=slip,
        phase_hint="supported" if support is True else ("interrupted" if support is False else "unknown"),
        lower_motor_action=action,
        lower_motor_progress=None,
        lower_motor_error=error,
        evidence_quality=quality,
        material_event=False,
        event_labels=("slip_detected",) if slip is True else (),
        valid=packet_valid and support is not None,
        reason="current_lower_motor_support_feedback" if packet_valid and support is not None else "lower_motor_support_unavailable",
    )
    motor_sample = TemporalBindingSampleV1(
        relation=TemporalRelationV1.LOWER_MOTOR,
        observation_no=observation_no,
        source_ref=source_ref,
        source_map_ref=None,
        subject_identity_handle=_LOWER_MOTOR_IDENTITY,
        object_identity_handle=None,
        frame_id="lower_motor_task_progress_frame_v1",
        units="normalized_progress",
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_value,
        subject_point=None,
        object_point=None,
        relative_distance=None,
        scalar_value=progress,
        contact=None,
        support=support,
        slip=slip,
        phase_hint=phase_hint,
        lower_motor_action=action,
        lower_motor_progress=progress,
        lower_motor_error=error,
        evidence_quality=quality,
        material_event=False,
        event_labels=tuple(
            label
            for label, active in (
                ("slip_detected", slip is True),
                ("lower_motor_error", error is not None),
            )
            if active
        ),
        valid=packet_valid,
        reason="current_lower_motor_progress_feedback" if packet_valid else "lower_motor_feedback_unavailable",
    )
    return support_sample, motor_sample


def _build_samples(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    observation_no: int,
    applied_policy: Optional[str],
) -> tuple[TemporalBindingSampleV1, ...]:
    """Build all current compact Phase 7 samples in deterministic relation order."""
    meta = _meta(env_obs)
    route_sample, vegetation_sample = _route_samples(ctx, meta, observation_no=observation_no)
    support_sample, motor_sample = _lower_motor_samples(
        ctx,
        meta,
        observation_no=observation_no,
        applied_policy=applied_policy,
    )
    return (
        _maternal_sample(ctx, meta, observation_no=observation_no),
        route_sample,
        vegetation_sample,
        _feeding_sample(ctx, meta, observation_no=observation_no),
        support_sample,
        motor_sample,
    )


def _make_envelope(ctx: Any, overlay: TemporalBindingOverlayV1) -> Optional[TemporalDynamicEnvelopeV1]:
    """Build one compact one-observation envelope when continuation is meaningful."""
    if not overlay.valid:
        return None
    continuations = set(overlay.expected_continuations)
    if continuations == {TemporalExpectedContinuationV1.UNKNOWN}:
        return None
    speed_tolerance = max(
        0.0,
        _ctx_float(ctx, "live_dynamics_envelope_speed_tolerance_v1", _DEFAULT_ENVELOPE_SPEED_TOLERANCE),
    )
    rate_tolerance = max(
        0.0,
        _ctx_float(ctx, "live_dynamics_envelope_rate_tolerance_v1", _DEFAULT_ENVELOPE_RATE_TOLERANCE),
    )
    uncertainty = float(overlay.rate_uncertainty or 0.0)
    speed_for_envelope = overlay.object_speed if overlay.self_motion_compensated else overlay.speed
    min_speed = max(0.0, speed_for_envelope - speed_tolerance - uncertainty) if speed_for_envelope is not None else None
    max_speed = speed_for_envelope + speed_tolerance + uncertainty if speed_for_envelope is not None else None
    min_relative = (
        overlay.relative_distance_rate - rate_tolerance - uncertainty
        if overlay.relative_distance_rate is not None
        else None
    )
    max_relative = (
        overlay.relative_distance_rate + rate_tolerance + uncertainty
        if overlay.relative_distance_rate is not None
        else None
    )
    min_scalar = overlay.scalar_rate - rate_tolerance - uncertainty if overlay.scalar_rate is not None else None
    max_scalar = overlay.scalar_rate + rate_tolerance + uncertainty if overlay.scalar_rate is not None else None
    expected_phase = overlay.phase if overlay.phase in {
        TemporalPhaseV1.ACTIVE,
        TemporalPhaseV1.MAINTAINING,
        TemporalPhaseV1.COMPLETED,
    } else None
    expected_contact = True if TemporalExpectedContinuationV1.MAINTAIN_CONTACT in continuations else None
    expected_support = True if TemporalExpectedContinuationV1.MAINTAIN_SUPPORT in continuations else None
    minimum_progress = (
        overlay.lower_motor_progress
        if TemporalExpectedContinuationV1.PROGRESS_NONDECREASING in continuations
        else None
    )
    return TemporalDynamicEnvelopeV1(
        relation=overlay.relation,
        source_observation_no=overlay.observation_no,
        source_map_ref=overlay.source_map_ref,
        frame_id=overlay.frame_id,
        units=overlay.units,
        expected_motion_direction=(
            overlay.motion_direction
            if TemporalExpectedContinuationV1.CONTINUE_MOTION in continuations
            or TemporalExpectedContinuationV1.HOLD_POSITION in continuations
            else TemporalMotionDirectionV1.UNKNOWN
        ),
        minimum_speed=min_speed,
        maximum_speed=max_speed,
        minimum_relative_rate=min_relative,
        maximum_relative_rate=max_relative,
        minimum_scalar_rate=min_scalar,
        maximum_scalar_rate=max_scalar,
        expected_contact=expected_contact,
        expected_support=expected_support,
        slip_allowed=False,
        expected_phase=expected_phase,
        minimum_progress=minimum_progress,
        source_action=overlay.lower_motor_action,
        uncertainty=uncertainty,
        horizon_observations=1,
        reason="one_observation_dynamic_continuation_from_current_overlay",
    )


def _residual_field(expected: Any, observed: Any, *, mismatch: bool, delta: Any = None) -> dict[str, Any]:
    """Return one JSON-safe structured residual field."""
    return {
        "expected": expected,
        "observed": observed,
        "delta": delta,
        "mismatch": bool(mismatch),
    }


def _range_mismatch(value: Optional[float], low: Optional[float], high: Optional[float]) -> tuple[bool, Optional[float]]:
    """Return whether one observed scalar falls outside an optional range."""
    if value is None or low is None or high is None:
        return False, None
    if value < low:
        return True, value - low
    if value > high:
        return True, value - high
    return False, 0.0


def _compare_envelope(
    ctx: Any,
    envelope: Optional[TemporalDynamicEnvelopeV1],
    overlay: TemporalBindingOverlayV1,
    *,
    previous_streak: int,
) -> TemporalStructuredResidualV1:
    """Compare one prior expected envelope with current evidence."""
    if envelope is None:
        return TemporalStructuredResidualV1(
            relation=overlay.relation,
            expected_source_observation_no=None,
            observed_observation_no=overlay.observation_no,
            status=TemporalEnvelopeStatusV1.NOT_PREDICTED,
            residual_fields={},
            mismatch_count=0,
            uncertainty=float(overlay.rate_uncertainty or 0.0),
            event_boundary=bool(overlay.event_labels),
            material_change_candidate=overlay.material_event,
            persistent_residual_count=0,
            reason="no_prior_dynamic_envelope",
        )
    if not overlay.valid or envelope.frame_id != overlay.frame_id or envelope.units != overlay.units:
        return TemporalStructuredResidualV1(
            relation=overlay.relation,
            expected_source_observation_no=envelope.source_observation_no,
            observed_observation_no=overlay.observation_no,
            status=TemporalEnvelopeStatusV1.UNKNOWN,
            residual_fields={
                "comparability": _residual_field(
                    {"frame_id": envelope.frame_id, "units": envelope.units},
                    {"frame_id": overlay.frame_id, "units": overlay.units, "valid": overlay.valid},
                    mismatch=True,
                )
            },
            mismatch_count=0,
            uncertainty=max(envelope.uncertainty, float(overlay.rate_uncertainty or 0.0)),
            event_boundary=bool(overlay.event_labels),
            material_change_candidate=overlay.material_event,
            persistent_residual_count=0,
            reason="current_evidence_not_comparable_with_dynamic_envelope",
        )

    fields: dict[str, dict[str, Any]] = {}
    mismatch_count = 0
    observed_speed = overlay.object_speed if overlay.self_motion_compensated else overlay.speed
    if envelope.expected_motion_direction is not TemporalMotionDirectionV1.UNKNOWN:
        direction_mismatch = overlay.motion_direction is not envelope.expected_motion_direction
        fields["motion_direction"] = _residual_field(
            envelope.expected_motion_direction.value,
            overlay.motion_direction.value,
            mismatch=direction_mismatch,
        )
        mismatch_count += int(direction_mismatch)
    speed_mismatch, speed_delta = _range_mismatch(observed_speed, envelope.minimum_speed, envelope.maximum_speed)
    if envelope.minimum_speed is not None and envelope.maximum_speed is not None:
        fields["speed"] = _residual_field(
            {"minimum": envelope.minimum_speed, "maximum": envelope.maximum_speed},
            observed_speed,
            mismatch=speed_mismatch,
            delta=speed_delta,
        )
        mismatch_count += int(speed_mismatch)
    relative_mismatch, relative_delta = _range_mismatch(
        overlay.relative_distance_rate,
        envelope.minimum_relative_rate,
        envelope.maximum_relative_rate,
    )
    if envelope.minimum_relative_rate is not None and envelope.maximum_relative_rate is not None:
        fields["relative_distance_rate"] = _residual_field(
            {"minimum": envelope.minimum_relative_rate, "maximum": envelope.maximum_relative_rate},
            overlay.relative_distance_rate,
            mismatch=relative_mismatch,
            delta=relative_delta,
        )
        mismatch_count += int(relative_mismatch)
    scalar_mismatch, scalar_delta = _range_mismatch(
        overlay.scalar_rate,
        envelope.minimum_scalar_rate,
        envelope.maximum_scalar_rate,
    )
    if envelope.minimum_scalar_rate is not None and envelope.maximum_scalar_rate is not None:
        fields["scalar_rate"] = _residual_field(
            {"minimum": envelope.minimum_scalar_rate, "maximum": envelope.maximum_scalar_rate},
            overlay.scalar_rate,
            mismatch=scalar_mismatch,
            delta=scalar_delta,
        )
        mismatch_count += int(scalar_mismatch)
    if envelope.expected_contact is not None:
        mismatch = overlay.contact is not envelope.expected_contact
        fields["contact"] = _residual_field(envelope.expected_contact, overlay.contact, mismatch=mismatch)
        mismatch_count += int(mismatch)
    if envelope.expected_support is not None:
        mismatch = overlay.support is not envelope.expected_support
        fields["support"] = _residual_field(envelope.expected_support, overlay.support, mismatch=mismatch)
        mismatch_count += int(mismatch)
    if not envelope.slip_allowed:
        mismatch = overlay.slip is True
        fields["slip"] = _residual_field(False, overlay.slip, mismatch=mismatch)
        mismatch_count += int(mismatch)
    if envelope.expected_phase is not None and overlay.phase is TemporalPhaseV1.INTERRUPTED:
        fields["phase"] = _residual_field(envelope.expected_phase.value, overlay.phase.value, mismatch=True)
        mismatch_count += 1
    progress_tolerance = max(
        0.0,
        _ctx_float(ctx, "live_dynamics_progress_tolerance_v1", _DEFAULT_PROGRESS_TOLERANCE),
    )
    if envelope.minimum_progress is not None:
        observed_progress = overlay.lower_motor_progress
        mismatch = bool(
            observed_progress is not None
            and observed_progress + progress_tolerance < envelope.minimum_progress
        )
        fields["lower_motor_progress"] = _residual_field(
            {"minimum": envelope.minimum_progress, "tolerance": progress_tolerance},
            observed_progress,
            mismatch=mismatch,
            delta=(observed_progress - envelope.minimum_progress if observed_progress is not None else None),
        )
        mismatch_count += int(mismatch)
    if overlay.lower_motor_error is not None:
        fields["lower_motor_error"] = _residual_field(None, overlay.lower_motor_error, mismatch=True)
        mismatch_count += 1

    status = TemporalEnvelopeStatusV1.OUTSIDE_ENVELOPE if mismatch_count else TemporalEnvelopeStatusV1.WITHIN_ENVELOPE
    streak = previous_streak + 1 if mismatch_count else 0
    persistent_threshold = max(
        1,
        _ctx_int(
            ctx,
            "live_dynamics_persistent_residual_observations_v1",
            _DEFAULT_PERSISTENT_RESIDUAL_OBSERVATIONS,
        ),
    )
    # Periodic vegetation is explicitly known live motion.  Direction reversals
    # can create event boundaries but cannot become a material route revision.
    persistent_material = bool(
        mismatch_count
        and streak >= persistent_threshold
        and overlay.relation is not TemporalRelationV1.ROUTE_VEGETATION
    )
    material_candidate = bool(overlay.material_event or persistent_material)
    event_boundary = bool(mismatch_count or overlay.event_labels)
    return TemporalStructuredResidualV1(
        relation=overlay.relation,
        expected_source_observation_no=envelope.source_observation_no,
        observed_observation_no=overlay.observation_no,
        status=status,
        residual_fields=fields,
        mismatch_count=mismatch_count,
        uncertainty=max(envelope.uncertainty, float(overlay.rate_uncertainty or 0.0)),
        event_boundary=event_boundary,
        material_change_candidate=material_candidate,
        persistent_residual_count=streak,
        reason=(
            "current_evidence_outside_dynamic_envelope"
            if mismatch_count
            else "current_evidence_within_dynamic_envelope"
        ),
    )


def _phase4b_comparison(ctx: Any, overlays: Sequence[TemporalBindingOverlayV1]) -> dict[str, Any]:
    """Compare the generalized maternal trend with the retained Phase 4B path."""
    generic = next((item for item in overlays if item.relation is TemporalRelationV1.SELF_MATERNAL), None)
    phase4b = getattr(ctx, "navmap_maternal_temporal_state", None)
    if not isinstance(generic, TemporalBindingOverlayV1) or not isinstance(phase4b, MaternalTemporalShadowStateV1):
        return {
            "status": "not_comparable",
            "phase4b_replaced": False,
            "reason": "generic_or_phase4b_temporal_state_unavailable",
        }
    readout = phase4b.readout
    if not readout.valid or readout.window_end_observation_no != phase4b.sample.observation_no:
        return {
            "status": "not_comparable",
            "phase4b_replaced": False,
            "generic_trend": generic.distance_trend.value,
            "phase4b_trend": readout.trend.value,
            "reason": "phase4b_temporal_readout_not_current_supported",
        }
    mapping = {
        MaternalTemporalTrendV1.APPROACHING: TemporalDistanceTrendV1.APPROACHING,
        MaternalTemporalTrendV1.STABLE: TemporalDistanceTrendV1.STABLE,
        MaternalTemporalTrendV1.RECEDING: TemporalDistanceTrendV1.RECEDING,
        MaternalTemporalTrendV1.UNKNOWN: TemporalDistanceTrendV1.UNKNOWN,
    }
    expected = mapping[readout.trend]
    status = "agreement" if generic.distance_trend is expected else "disagreement"
    return {
        "status": status,
        "agreement": status == "agreement",
        "phase4b_replaced": False,
        "generic_trend": generic.distance_trend.value,
        "generalized_trend": generic.distance_trend.value,
        "phase4b_trend": readout.trend.value,
        "generic_relative_rate": generic.relative_distance_rate,
        "phase4b_relative_rate": readout.relative_rate,
        "self_motion_compensation_added_by_phase7": generic.self_motion_compensated,
        "reason": "dual_run_generalized_temporal_contract",
    }


def _materiality_decision(
    observation_no: int,
    overlays: Sequence[TemporalBindingOverlayV1],
    residuals: Sequence[TemporalStructuredResidualV1],
) -> TemporalMaterialityDecisionV1:
    """Build one sparse event/materiality decision from current overlays/residuals."""
    labels: list[str] = []
    for overlay in overlays:
        labels.extend(f"{overlay.relation.value}:{label}" for label in overlay.event_labels)
    labels.extend(
        f"{residual.relation.value}:outside_dynamic_envelope"
        for residual in residuals
        if residual.status is TemporalEnvelopeStatusV1.OUTSIDE_ENVELOPE
    )
    material_relations = tuple(
        dict.fromkeys(
            overlay.relation
            for overlay in overlays
            if overlay.material_event
        )
    )
    persistent_relations = tuple(
        dict.fromkeys(
            residual.relation
            for residual in residuals
            if residual.material_change_candidate and residual.relation not in material_relations
        )
    )
    material_recommended = bool(material_relations or persistent_relations)
    event_boundary = bool(labels or material_recommended)
    if material_relations:
        reason = "explicit_structural_or_affordance_event_present"
    elif persistent_relations:
        reason = "persistent_dynamic_residual_exceeded_materiality_gate"
    elif event_boundary:
        reason = "live_dynamic_event_boundary_without_material_revision"
    else:
        reason = "ordinary_live_dynamics_no_event_boundary"
    return TemporalMaterialityDecisionV1(
        observation_no=observation_no,
        event_labels=tuple(dict.fromkeys(labels)),
        material_change_relations=material_relations,
        persistent_residual_relations=persistent_relations,
        event_boundary=event_boundary,
        material_change_recommended=material_recommended,
        reason=reason,
    )


def _store_sparse_event(ctx: Any, state: TemporalBindingStateV1) -> None:
    """Store only sparse event-boundary rows, never a per-cycle NavMap movie."""
    if not state.materiality.event_boundary:
        return
    raw = getattr(ctx, "live_dynamics_event_history_v1", None)
    history = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    history.append(
        {
            "schema": "live_dynamics_event_v1",
            "phase": "7",
            "observation_no": state.observation_no,
            "materiality": state.materiality.as_dict(),
            "residuals": {
                item.relation.value: item.as_dict()
                for item in state.residuals
                if item.event_boundary or item.material_change_candidate
            },
            "stores_full_navmap": False,
            "episodic_memory_record": False,
        }
    )
    ctx.live_dynamics_event_history_v1 = history[-_history_limit(ctx):]


def _update_seqerr_last(ctx: Any, state: TemporalBindingStateV1) -> None:
    """Expose the generalized result through the existing Sequential/Error surface."""
    raw = getattr(ctx, "seqerr_last", None)
    last = dict(raw) if isinstance(raw, dict) else {}
    last[_BUCKET_KEY] = {
        "overlays": {item.relation.value: item.as_dict() for item in state.overlays},
        "residuals": {item.relation.value: item.as_dict() for item in state.residuals},
        "materiality": state.materiality.as_dict(),
    }
    ctx.seqerr_last = last


def live_dynamics_reset_v1(ctx: Any) -> None:
    """Clear episode-local Phase 7 registers without touching shared WNM maps."""
    if ctx is None:
        return
    ctx.live_dynamics_observation_no_v1 = 0
    ctx.live_dynamics_state_v1 = None
    ctx.live_dynamics_last_update_v1 = {}
    ctx.live_dynamics_pending_envelopes_v1 = {}
    ctx.live_dynamics_residual_streak_v1 = {}
    ctx.live_dynamics_event_history_v1 = []


def live_dynamics_observation_step_v1(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    applied_policy: Optional[str] = None,
) -> dict[str, Any]:
    """Process one observation through the generalized bounded temporal layer.

    The function must run after Phase 4 maternal, Phase 5 feeding, and Phase 6
    terrain updates so it can consume their current source-linked overlays.  It
    observes the action already applied by the lower environment/controller
    path but cannot alter current or future policy selection.
    """
    if ctx is None or env_obs is None:
        return {
            "schema": "live_dynamics_summary_v1",
            "phase": "7",
            "status": "ctx_or_observation_unavailable",
        }
    if not bool(getattr(ctx, "live_dynamics_enabled_v1", True)):
        ctx.live_dynamics_state_v1 = None
        ctx.live_dynamics_last_update_v1 = {
            "schema": "live_dynamics_summary_v1",
            "phase": "7",
            "status": "disabled",
            "authority": "source_linked_live_dynamics",
            "policy_selection_mutation_allowed": False,
        }
        return dict(ctx.live_dynamics_last_update_v1)
    if not bool(getattr(ctx, "seqerr_enabled", True)):
        ctx.live_dynamics_state_v1 = None
        ctx.live_dynamics_last_update_v1 = {
            "schema": "live_dynamics_summary_v1",
            "phase": "7",
            "status": "dependency_error",
            "authority": "source_linked_live_dynamics",
            "reason": "shared_seqerr_window_disabled",
            "policy_selection_mutation_allowed": False,
        }
        return dict(ctx.live_dynamics_last_update_v1)

    observation_no = _next_observation_no(ctx)
    previous_state_raw = getattr(ctx, "live_dynamics_state_v1", None)
    previous_state = previous_state_raw if isinstance(previous_state_raw, TemporalBindingStateV1) else None
    samples = _build_samples(
        ctx,
        env_obs,
        observation_no=observation_no,
        applied_policy=applied_policy if isinstance(applied_policy, str) else None,
    )
    history, capacity = _attach_samples_to_shared_window(ctx, samples)
    overlays: list[TemporalBindingOverlayV1] = []
    for relation in TemporalRelationV1:
        relation_samples = _samples_for_relation(history, relation)
        if not relation_samples:
            continue
        overlays.append(
            _decode_overlay(
                ctx,
                relation_samples,
                previous=_previous_overlay(previous_state, relation),
                window_capacity=capacity,
            )
        )

    pending_raw = getattr(ctx, "live_dynamics_pending_envelopes_v1", None)
    pending = {
        key: value
        for key, value in pending_raw.items()
        if isinstance(key, str) and isinstance(value, TemporalDynamicEnvelopeV1)
    } if isinstance(pending_raw, dict) else {}
    streak_raw = getattr(ctx, "live_dynamics_residual_streak_v1", None)
    streaks = {
        key: max(0, int(value))
        for key, value in streak_raw.items()
        if isinstance(key, str) and isinstance(value, int) and not isinstance(value, bool)
    } if isinstance(streak_raw, dict) else {}
    residuals: list[TemporalStructuredResidualV1] = []
    next_streaks: dict[str, int] = {}
    for overlay in overlays:
        prior = pending.get(overlay.relation.value)
        residual = _compare_envelope(
            ctx,
            prior,
            overlay,
            previous_streak=streaks.get(overlay.relation.value, 0),
        )
        residuals.append(residual)
        next_streaks[overlay.relation.value] = residual.persistent_residual_count

    next_envelopes: dict[str, TemporalDynamicEnvelopeV1] = {}
    for overlay in overlays:
        envelope = _make_envelope(ctx, overlay)
        if envelope is not None:
            next_envelopes[overlay.relation.value] = envelope
    materiality = _materiality_decision(observation_no, overlays, residuals)
    state = TemporalBindingStateV1(
        observation_no=observation_no,
        overlays=tuple(overlays),
        residuals=tuple(residuals),
        pending_envelopes=tuple(next_envelopes[key] for key in sorted(next_envelopes)),
        materiality=materiality,
        phase4b_comparison=_phase4b_comparison(ctx, overlays),
        shared_window_capacity=capacity,
        shared_window_frame_count=len(history),
    )
    ctx.live_dynamics_state_v1 = state
    ctx.live_dynamics_pending_envelopes_v1 = next_envelopes
    ctx.live_dynamics_residual_streak_v1 = next_streaks
    row = state.as_dict()
    ctx.live_dynamics_last_update_v1 = dict(row)
    _store_sparse_event(ctx, state)
    _update_seqerr_last(ctx, state)
    return live_dynamics_summary_v1(ctx)


def live_dynamics_overlay_v1(
    ctx: Any,
    relation: TemporalRelationV1 | str,
) -> Optional[TemporalBindingOverlayV1]:
    """Return the current typed overlay for one relation."""
    if ctx is None:
        return None
    try:
        relation_value = relation if isinstance(relation, TemporalRelationV1) else TemporalRelationV1(str(relation))
    except ValueError:
        return None
    state = getattr(ctx, "live_dynamics_state_v1", None)
    if not isinstance(state, TemporalBindingStateV1):
        return None
    return next((item for item in state.overlays if item.relation is relation_value), None)


def live_dynamics_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe Phase 7 summary."""
    if ctx is None:
        return {"schema": "live_dynamics_summary_v1", "phase": "7", "status": "ctx_unavailable"}
    state = getattr(ctx, "live_dynamics_state_v1", None)
    last_update = getattr(ctx, "live_dynamics_last_update_v1", None)
    if not isinstance(state, TemporalBindingStateV1) and isinstance(last_update, dict):
        if last_update.get("status") in {"disabled", "dependency_error", "error"}:
            out = dict(last_update)
            out.setdefault("schema", "live_dynamics_summary_v1")
            out.setdefault("phase", "7")
            out["event_history_count"] = len(getattr(ctx, "live_dynamics_event_history_v1", []) or [])
            return out
    return {
        "schema": "live_dynamics_summary_v1",
        "phase": "7",
        "status": "active" if isinstance(state, TemporalBindingStateV1) else "idle",
        "authority": "source_linked_live_dynamics",
        "policy_selection_mutation_allowed": False,
        "protected_safety_can_be_overridden": False,
        "phase4b_temporal_replaced": False,
        "rolling_history": "ctx.seqerr_history.live_dynamics_v1",
        "rolling_history_bounded": True,
        "separate_from_episodic_memory": True,
        "stores_full_navmap_history": False,
        "lower_motor_trajectory_present": False,
        "state": state.as_dict() if isinstance(state, TemporalBindingStateV1) else None,
        "event_history_count": len(getattr(ctx, "live_dynamics_event_history_v1", []) or []),
        "event_history_limit": _history_limit(ctx),
    }


def _float_text(value: Any, *, digits: int = 3) -> str:
    """Return compact finite float text or ``unknown``."""
    number = _optional_float(value)
    return f"{number:.{digits}f}" if number is not None else "unknown"


def render_live_dynamics_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 7 temporal/dynamic lines."""
    summary = live_dynamics_summary_v1(ctx)
    lines = ["PHASE 7 GENERAL TEMPORAL BINDING / LIVE DYNAMICS:"]
    if summary.get("status") != "active":
        lines.append(
            "  "
            f"status={summary.get('status')} policy_selection_mutation_allowed=False "
            "stores_full_navmap_history=False"
        )
        return lines
    state = summary.get("state")
    state = state if isinstance(state, dict) else {}
    overlays = state.get("overlays")
    overlays = overlays if isinstance(overlays, dict) else {}
    lines.append(
        "  "
        f"status=active observation={state.get('observation_no')} "
        f"window={state.get('shared_window_frame_count')}/{state.get('shared_window_capacity')} "
        f"relations={len(overlays)} event_history={summary.get('event_history_count')} "
        "policy_selection_mutation_allowed=False"
    )
    for relation in (
        TemporalRelationV1.SELF_MATERNAL,
        TemporalRelationV1.SELF_ROUTE,
        TemporalRelationV1.FEEDING_CONTACT,
        TemporalRelationV1.BODY_SUPPORT,
        TemporalRelationV1.LOWER_MOTOR,
    ):
        row = overlays.get(relation.value)
        if not isinstance(row, dict):
            continue
        velocity = row.get("velocity")
        velocity = velocity if isinstance(velocity, dict) else {}
        object_velocity = row.get("object_specific_velocity")
        object_velocity = object_velocity if isinstance(object_velocity, dict) else {}
        lines.append(
            "  "
            f"{relation.value}: valid={row.get('valid')} phase={row.get('phase')}/{row.get('phase_detail')} "
            f"direction={row.get('motion_direction')} speed={_float_text(velocity.get('speed'))} "
            f"trend={row.get('distance_trend')} rate={_float_text(row.get('relative_distance_rate'))} "
            f"contact={row.get('contact')} support={row.get('support')} slip={row.get('slip')}"
        )
        if relation is TemporalRelationV1.SELF_MATERNAL:
            lines.append(
                "    "
                f"self_motion_compensated={object_velocity.get('self_motion_compensated')} "
                f"object_speed={_float_text(object_velocity.get('speed'))} "
                f"object_velocity=({_float_text(object_velocity.get('x'))},{_float_text(object_velocity.get('y'))})"
            )
    materiality = state.get("materiality")
    materiality = materiality if isinstance(materiality, dict) else {}
    lines.append(
        "  "
        f"event_boundary={materiality.get('event_boundary')} "
        f"material_change_recommended={materiality.get('material_change_recommended')} "
        f"phase7_creates_navmap_revision={materiality.get('phase7_creates_navmap_revision')} "
        f"reason={materiality.get('reason')}"
    )
    phase4b = state.get("phase4b_comparison")
    phase4b = phase4b if isinstance(phase4b, dict) else {}
    lines.append(
        "  "
        f"phase4b_dual_run={phase4b.get('status')} phase4b_replaced={phase4b.get('phase4b_replaced')} "
        f"generic_trend={phase4b.get('generic_trend')} phase4b_trend={phase4b.get('phase4b_trend')}"
    )
    return lines
