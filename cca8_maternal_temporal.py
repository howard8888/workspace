# -*- coding: utf-8 -*-
"""Phase 4B maternal Sequential/Temporal compression shadow for CCA8.

Purpose
-------
Phase 4B consumes the geometry-derived SELF-maternal distance and bearing
produced by :mod:`cca8_maternal_geometry` and compresses a short changing
sequence into compact static temporal readouts:

* ``approaching`` / ``stable`` / ``receding`` from distance change;
* relative distance rate;
* clockwise / stable / counterclockwise bearing change where bearing exists;
* bounded support, freshness, and rate-uncertainty diagnostics; and
* explicit ``UNKNOWN`` or insufficient-history outcomes.

The module reuses the existing bounded Sequential/Error ring buffer on
``ctx.seqerr_history``.  It adds one compact JSON-safe sample under the
``navmap_temporal.self_maternal`` key of each participating frame.  It never
stores a complete :class:`~cca8_navmap_kernel.NavMapV2` in the temporal window,
creates no second unbounded history or clock, and does not create immutable
NavMap revisions for ordinary motion.

Scope boundary
--------------
This slice is shadow-only.  It does not implement maternal object permanence,
occlusion prediction, lost-track handling, FollowMom applicability, expected
FollowMom successors, or behavioral authority.  Those remain later Phase 4
subphases.  The existing Phase 4A geometry path remains unchanged.

Authority boundary
------------------
All public traces state ``authority=shadow_only`` and
``map_can_trigger_follow_mom=False``.  BodyMap, PolicyRuntime, protected safety,
and FollowMom selection/execution remain unchanged.
"""

from __future__ import annotations

# This module keeps the first bounded maternal temporal records, shared-window
# integration, derivation, summaries, and renderer together so the shadow and
# no-movie boundaries remain easy to inspect.
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional, Sequence

from cca8_env import EnvObservation
from cca8_maternal_geometry import MaternalGeometryShadowStateV1
from cca8_navmap_kernel import NavMapRefV1

__version__ = "0.1.0"

__all__ = [
    "MaternalTemporalTrendV1",
    "MaternalBearingTrendV1",
    "MaternalTemporalThresholdsV1",
    "MaternalTemporalSampleV1",
    "MaternalTemporalReadoutV1",
    "MaternalTemporalShadowStateV1",
    "maternal_temporal_thresholds_from_ctx_v1",
    "maternal_temporal_sample_from_geometry_state_v1",
    "maternal_temporal_readout_from_samples_v1",
    "maternal_temporal_shadow_observation_step_v1",
    "maternal_temporal_shadow_summary_v1",
    "render_maternal_temporal_shadow_lines_v1",
    "__version__",
]

_RELATION_KEY = "self_maternal"
_DEFAULT_MINIMUM_VALID_SAMPLES = 3
_DEFAULT_STABLE_RATE_TOLERANCE = 0.05
_DEFAULT_HYSTERESIS_RATE = 0.02
_DEFAULT_STABLE_BEARING_RATE_TOLERANCE = 2.0
_DEFAULT_BEARING_HYSTERESIS_RATE = 1.0
_DEFAULT_MINIMUM_ELAPSED_TIME = 1e-9
_DEFAULT_HISTORY_LIMIT = 25
_DEFAULT_SEQERR_WINDOW = 4
_MAX_SEQERR_WINDOW = 25


class MaternalTemporalTrendV1(str, Enum):
    """Static temporal relation derived from recent SELF-maternal distance."""

    APPROACHING = "approaching"
    STABLE = "stable"
    RECEDING = "receding"
    UNKNOWN = "unknown"


class MaternalBearingTrendV1(str, Enum):
    """Static angular relation derived from recent SELF-maternal bearing."""

    CLOCKWISE = "clockwise"
    STABLE = "stable"
    COUNTERCLOCKWISE = "counterclockwise"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MaternalTemporalThresholdsV1:
    """Explicit deterministic thresholds for the first maternal temporal decoder.

    The values are inspectable software parameters rather than biological
    constants.  ``stable_rate_tolerance`` is the entry boundary around zero.
    ``hysteresis_rate`` is the smaller exit boundary that lets an existing
    directional interpretation persist through mild slowing without chatter.
    Exact ties at the entry boundary resolve to ``stable`` unless hysteresis is
    already preserving the preceding directional state.
    """

    minimum_valid_samples: int
    stable_rate_tolerance: float
    hysteresis_rate: float
    stable_bearing_rate_tolerance: float
    bearing_hysteresis_rate: float
    minimum_elapsed_time: float

    def __post_init__(self) -> None:
        _require_int_at_least(self.minimum_valid_samples, minimum=2, field_name="minimum_valid_samples")
        stable_rate = _finite_non_negative_float(self.stable_rate_tolerance, field_name="stable_rate_tolerance")
        hysteresis = _finite_non_negative_float(self.hysteresis_rate, field_name="hysteresis_rate")
        stable_bearing = _finite_non_negative_float(
            self.stable_bearing_rate_tolerance,
            field_name="stable_bearing_rate_tolerance",
        )
        bearing_hysteresis = _finite_non_negative_float(
            self.bearing_hysteresis_rate,
            field_name="bearing_hysteresis_rate",
        )
        minimum_elapsed = _finite_positive_float(self.minimum_elapsed_time, field_name="minimum_elapsed_time")
        if hysteresis > stable_rate:
            raise ValueError("hysteresis_rate cannot exceed stable_rate_tolerance")
        if bearing_hysteresis > stable_bearing:
            raise ValueError("bearing_hysteresis_rate cannot exceed stable_bearing_rate_tolerance")
        object.__setattr__(self, "stable_rate_tolerance", stable_rate)
        object.__setattr__(self, "hysteresis_rate", hysteresis)
        object.__setattr__(self, "stable_bearing_rate_tolerance", stable_bearing)
        object.__setattr__(self, "bearing_hysteresis_rate", bearing_hysteresis)
        object.__setattr__(self, "minimum_elapsed_time", minimum_elapsed)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe threshold record."""
        return {
            "minimum_valid_samples": self.minimum_valid_samples,
            "stable_rate_tolerance": self.stable_rate_tolerance,
            "hysteresis_rate": self.hysteresis_rate,
            "stable_bearing_rate_tolerance": self.stable_bearing_rate_tolerance,
            "bearing_hysteresis_rate": self.bearing_hysteresis_rate,
            "minimum_elapsed_time": self.minimum_elapsed_time,
        }


@dataclass(frozen=True, slots=True)
class MaternalTemporalSampleV1:
    """One compact Phase 4B sample derived from the Phase 4A evidence map.

    The sample stores references and scalar readouts only.  It deliberately
    excludes complete NavMap elements, relations, links, serialized bytes, and
    policy state.
    """

    observation_no: int
    source_evidence_map_ref: NavMapRefV1
    maintained_map_ref: Optional[NavMapRefV1]
    frame_id: str
    units: str
    identity_handle: str
    self_element_id: str
    maternal_element_id: str
    step_index: Optional[int]
    controller_steps: int
    time_since_birth: Optional[float]
    distance: Optional[float]
    bearing_degrees: Optional[float]
    valid: bool
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        if not isinstance(self.source_evidence_map_ref, NavMapRefV1):
            raise TypeError("source_evidence_map_ref must be NavMapRefV1")
        if self.maintained_map_ref is not None and not isinstance(self.maintained_map_ref, NavMapRefV1):
            raise TypeError("maintained_map_ref must be NavMapRefV1 or None")
        for field_name in ("frame_id", "units", "identity_handle", "self_element_id", "maternal_element_id", "reason"):
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
        if self.distance is not None:
            object.__setattr__(self, "distance", _finite_non_negative_float(self.distance, field_name="distance"))
        if self.bearing_degrees is not None:
            bearing = _finite_float(self.bearing_degrees, field_name="bearing_degrees") % 360.0
            object.__setattr__(self, "bearing_degrees", bearing)
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be bool")
        if self.valid and self.distance is None:
            raise ValueError("valid temporal sample requires distance")
        if not self.valid and (self.distance is not None or self.bearing_degrees is not None):
            raise ValueError("invalid temporal sample cannot carry distance or bearing")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe compact sample."""
        return {
            "schema": "maternal_temporal_sample_v1",
            "observation_no": self.observation_no,
            "source_evidence_map_ref": self.source_evidence_map_ref.as_dict(),
            "maintained_map_ref": self.maintained_map_ref.as_dict() if self.maintained_map_ref is not None else None,
            "frame_id": self.frame_id,
            "units": self.units,
            "identity_handle": self.identity_handle,
            "self_element_id": self.self_element_id,
            "maternal_element_id": self.maternal_element_id,
            "step_index": self.step_index,
            "controller_steps": self.controller_steps,
            "time_since_birth": self.time_since_birth,
            "distance": self.distance,
            "bearing_degrees": self.bearing_degrees,
            "valid": self.valid,
            "reason": self.reason,
            "contains_full_navmap": False,
        }


@dataclass(frozen=True, slots=True)
class MaternalTemporalReadoutV1:
    """Static temporal features decoded from one bounded maternal sample window."""

    source_evidence_map_ref: NavMapRefV1
    maintained_map_ref: Optional[NavMapRefV1]
    target_element_id: str
    frame_id: str
    units: str
    trend: MaternalTemporalTrendV1
    bearing_trend: MaternalBearingTrendV1
    window_capacity: int
    window_sample_count: int
    valid_sample_count: int
    bearing_valid_sample_count: int
    window_start_observation_no: Optional[int]
    window_end_observation_no: int
    interval_source: Optional[str]
    elapsed_time: Optional[float]
    distance_start: Optional[float]
    distance_end: Optional[float]
    distance_delta: Optional[float]
    relative_rate: Optional[float]
    rate_uncertainty: Optional[float]
    bearing_start_degrees: Optional[float]
    bearing_end_degrees: Optional[float]
    bearing_delta_degrees: Optional[float]
    bearing_rate_degrees: Optional[float]
    bearing_rate_uncertainty: Optional[float]
    support_status: str
    support_fraction: float
    freshness: str
    valid: bool
    reason: str
    thresholds: MaternalTemporalThresholdsV1

    def __post_init__(self) -> None:
        if not isinstance(self.source_evidence_map_ref, NavMapRefV1):
            raise TypeError("source_evidence_map_ref must be NavMapRefV1")
        if self.maintained_map_ref is not None and not isinstance(self.maintained_map_ref, NavMapRefV1):
            raise TypeError("maintained_map_ref must be NavMapRefV1 or None")
        for field_name in ("target_element_id", "frame_id", "units", "support_status", "freshness", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.trend, MaternalTemporalTrendV1):
            raise TypeError("trend must be MaternalTemporalTrendV1")
        if not isinstance(self.bearing_trend, MaternalBearingTrendV1):
            raise TypeError("bearing_trend must be MaternalBearingTrendV1")
        if not isinstance(self.thresholds, MaternalTemporalThresholdsV1):
            raise TypeError("thresholds must be MaternalTemporalThresholdsV1")
        _require_positive_int(self.window_capacity, field_name="window_capacity")
        _require_non_negative_int(self.window_sample_count, field_name="window_sample_count")
        _require_non_negative_int(self.valid_sample_count, field_name="valid_sample_count")
        _require_non_negative_int(self.bearing_valid_sample_count, field_name="bearing_valid_sample_count")
        _require_positive_int(self.window_end_observation_no, field_name="window_end_observation_no")
        if self.window_start_observation_no is not None:
            _require_positive_int(self.window_start_observation_no, field_name="window_start_observation_no")
            if self.window_start_observation_no > self.window_end_observation_no:
                raise ValueError("window_start_observation_no cannot exceed window_end_observation_no")
        if self.interval_source is not None:
            _require_nonempty_text(self.interval_source, field_name="interval_source")
        for field_name in (
            "elapsed_time",
            "distance_start",
            "distance_end",
            "distance_delta",
            "relative_rate",
            "rate_uncertainty",
            "bearing_start_degrees",
            "bearing_end_degrees",
            "bearing_delta_degrees",
            "bearing_rate_degrees",
            "bearing_rate_uncertainty",
        ):
            value = getattr(self, field_name)
            if value is not None:
                number = _finite_float(value, field_name=field_name)
                if field_name in {"elapsed_time", "distance_start", "distance_end", "rate_uncertainty", "bearing_rate_uncertainty"}:
                    if number < 0.0:
                        raise ValueError(f"{field_name} must be non-negative")
                object.__setattr__(self, field_name, number)
        support_fraction = _finite_non_negative_float(self.support_fraction, field_name="support_fraction")
        if support_fraction > 1.0:
            raise ValueError("support_fraction cannot exceed 1.0")
        object.__setattr__(self, "support_fraction", support_fraction)
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be bool")
        if self.valid:
            if self.trend is MaternalTemporalTrendV1.UNKNOWN:
                raise ValueError("valid temporal readout cannot have UNKNOWN trend")
            if self.elapsed_time is None or self.relative_rate is None:
                raise ValueError("valid temporal readout requires elapsed_time and relative_rate")
        elif self.trend is not MaternalTemporalTrendV1.UNKNOWN:
            raise ValueError("invalid temporal readout must preserve UNKNOWN trend")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe static temporal readout."""
        return {
            "schema": "maternal_temporal_readout_v1",
            "source_evidence_map_ref": self.source_evidence_map_ref.as_dict(),
            "maintained_map_ref": self.maintained_map_ref.as_dict() if self.maintained_map_ref is not None else None,
            "target_element_id": self.target_element_id,
            "frame_id": self.frame_id,
            "units": self.units,
            "trend": self.trend.value,
            "bearing_trend": self.bearing_trend.value,
            "window_capacity": self.window_capacity,
            "window_sample_count": self.window_sample_count,
            "valid_sample_count": self.valid_sample_count,
            "bearing_valid_sample_count": self.bearing_valid_sample_count,
            "window_start_observation_no": self.window_start_observation_no,
            "window_end_observation_no": self.window_end_observation_no,
            "interval_source": self.interval_source,
            "elapsed_time": self.elapsed_time,
            "distance_start": self.distance_start,
            "distance_end": self.distance_end,
            "distance_delta": self.distance_delta,
            "relative_rate": self.relative_rate,
            "rate_uncertainty": self.rate_uncertainty,
            "bearing_start_degrees": self.bearing_start_degrees,
            "bearing_end_degrees": self.bearing_end_degrees,
            "bearing_delta_degrees": self.bearing_delta_degrees,
            "bearing_rate_degrees": self.bearing_rate_degrees,
            "bearing_rate_uncertainty": self.bearing_rate_uncertainty,
            "support_status": self.support_status,
            "support_fraction": self.support_fraction,
            "freshness": self.freshness,
            "valid": self.valid,
            "reason": self.reason,
            "thresholds": self.thresholds.as_dict(),
        }


@dataclass(frozen=True, slots=True)
class MaternalTemporalShadowStateV1:
    """One immutable Phase 4B shared-window sample and decoded readout."""

    sample: MaternalTemporalSampleV1
    readout: MaternalTemporalReadoutV1
    previous_trend: MaternalTemporalTrendV1
    previous_bearing_trend: MaternalBearingTrendV1

    def __post_init__(self) -> None:
        if not isinstance(self.sample, MaternalTemporalSampleV1):
            raise TypeError("sample must be MaternalTemporalSampleV1")
        if not isinstance(self.readout, MaternalTemporalReadoutV1):
            raise TypeError("readout must be MaternalTemporalReadoutV1")
        if self.sample.source_evidence_map_ref != self.readout.source_evidence_map_ref:
            raise ValueError("readout must describe the latest temporal sample")
        if not isinstance(self.previous_trend, MaternalTemporalTrendV1):
            raise TypeError("previous_trend must be MaternalTemporalTrendV1")
        if not isinstance(self.previous_bearing_trend, MaternalBearingTrendV1):
            raise TypeError("previous_bearing_trend must be MaternalBearingTrendV1")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit Phase 4B state record."""
        return {
            "schema": "maternal_temporal_shadow_state_v1",
            "phase": "4B",
            "authority_level": "shadow",
            "authority": "shadow_only",
            "legacy_authority": "bodymap_policy_runtime",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
            "map_can_advise_follow_mom": False,
            "sample_window": "ctx.seqerr_history.navmap_temporal.self_maternal",
            "window_shared_with_seqerr": True,
            "stores_full_navmaps": False,
            "creates_immutable_navmap_revision": False,
            "sample": self.sample.as_dict(),
            "readout": self.readout.as_dict(),
            "previous_trend": self.previous_trend.value,
            "previous_bearing_trend": self.previous_bearing_trend.value,
            "deferred_phase4_capabilities": [
                "maternal_continuity_and_occlusion",
                "follow_mom_compare_transaction",
                "expected_follow_mom_successor",
                "follow_mom_trigger_authority",
            ],
        }


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Validate one non-empty text value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Validate one positive integer without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Validate one non-negative integer without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_int_at_least(value: int, *, minimum: int, field_name: str) -> None:
    """Validate one integer lower bound without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value < minimum:
        raise ValueError(f"{field_name} must be an integer >= {minimum}")


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float without accepting bool."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a finite number") from exc
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _finite_non_negative_float(value: Any, *, field_name: str) -> float:
    """Return one finite non-negative float without accepting bool."""
    number = _finite_float(value, field_name=field_name)
    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _finite_positive_float(value: Any, *, field_name: str) -> float:
    """Return one finite positive float without accepting bool."""
    number = _finite_float(value, field_name=field_name)
    if number <= 0.0:
        raise ValueError(f"{field_name} must be positive")
    return number


def _optional_finite_float(value: Any) -> Optional[float]:
    """Return a finite float or ``None`` for unavailable values."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _optional_non_negative_int(value: Any) -> Optional[int]:
    """Return a non-negative int or ``None`` without accepting bool."""
    if isinstance(value, bool) or value is None:
        return None
    try:
        number = int(value)
    except (TypeError, ValueError):
        return None
    return number if number >= 0 else None


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
    """Read one context float with a deterministic fallback."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _seqerr_window_capacity(ctx: Any) -> int:
    """Return the existing bounded Sequential/Error window capacity."""
    value = _ctx_int(ctx, "seqerr_window", _DEFAULT_SEQERR_WINDOW)
    return max(2, min(_MAX_SEQERR_WINDOW, value))


def maternal_temporal_thresholds_from_ctx_v1(ctx: Any) -> MaternalTemporalThresholdsV1:
    """Return explicit Phase 4B thresholds from the runtime context."""
    minimum_valid_samples = _ctx_int(
        ctx,
        "navmap_maternal_temporal_minimum_valid_samples",
        _DEFAULT_MINIMUM_VALID_SAMPLES,
    )
    if minimum_valid_samples < 2:
        minimum_valid_samples = _DEFAULT_MINIMUM_VALID_SAMPLES
    stable_rate_tolerance = _ctx_float(
        ctx,
        "navmap_maternal_temporal_stable_rate_tolerance",
        _DEFAULT_STABLE_RATE_TOLERANCE,
    )
    hysteresis_rate = _ctx_float(
        ctx,
        "navmap_maternal_temporal_hysteresis_rate",
        _DEFAULT_HYSTERESIS_RATE,
    )
    stable_bearing_rate_tolerance = _ctx_float(
        ctx,
        "navmap_maternal_temporal_stable_bearing_rate_tolerance",
        _DEFAULT_STABLE_BEARING_RATE_TOLERANCE,
    )
    bearing_hysteresis_rate = _ctx_float(
        ctx,
        "navmap_maternal_temporal_bearing_hysteresis_rate",
        _DEFAULT_BEARING_HYSTERESIS_RATE,
    )
    minimum_elapsed_time = _ctx_float(
        ctx,
        "navmap_maternal_temporal_minimum_elapsed_time",
        _DEFAULT_MINIMUM_ELAPSED_TIME,
    )
    if stable_rate_tolerance < 0.0:
        stable_rate_tolerance = _DEFAULT_STABLE_RATE_TOLERANCE
    if hysteresis_rate < 0.0 or hysteresis_rate > stable_rate_tolerance:
        hysteresis_rate = min(_DEFAULT_HYSTERESIS_RATE, stable_rate_tolerance)
    if stable_bearing_rate_tolerance < 0.0:
        stable_bearing_rate_tolerance = _DEFAULT_STABLE_BEARING_RATE_TOLERANCE
    if bearing_hysteresis_rate < 0.0 or bearing_hysteresis_rate > stable_bearing_rate_tolerance:
        bearing_hysteresis_rate = min(_DEFAULT_BEARING_HYSTERESIS_RATE, stable_bearing_rate_tolerance)
    if minimum_elapsed_time <= 0.0:
        minimum_elapsed_time = _DEFAULT_MINIMUM_ELAPSED_TIME
    return MaternalTemporalThresholdsV1(
        minimum_valid_samples=minimum_valid_samples,
        stable_rate_tolerance=stable_rate_tolerance,
        hysteresis_rate=hysteresis_rate,
        stable_bearing_rate_tolerance=stable_bearing_rate_tolerance,
        bearing_hysteresis_rate=bearing_hysteresis_rate,
        minimum_elapsed_time=minimum_elapsed_time,
    )


def _env_timing(ctx: Any, env_obs: EnvObservation) -> tuple[Optional[int], int, Optional[float]]:
    """Return existing step/controller/time values without creating another clock."""
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}
    controller_steps = max(0, _ctx_int(ctx, "controller_steps", 0))
    step_index = _optional_non_negative_int(meta.get("step_index"))
    if step_index is None:
        step_index = controller_steps
    time_since_birth = _optional_finite_float(meta.get("time_since_birth"))
    if time_since_birth is not None and time_since_birth < 0.0:
        time_since_birth = None
    return step_index, controller_steps, time_since_birth


def maternal_temporal_sample_from_geometry_state_v1(
    state: MaternalGeometryShadowStateV1,
    env_obs: EnvObservation,
    *,
    controller_ctx: Any,
) -> MaternalTemporalSampleV1:
    """Build one compact sample from the current Phase 4A evidence readout.

    The function consumes only geometry-derived Phase 4A results.  It never
    reads ``raw_sensors['distance_to_mom']`` or ``proximity:mom:*`` predicates.
    """
    if not isinstance(state, MaternalGeometryShadowStateV1):
        raise TypeError("state must be MaternalGeometryShadowStateV1")
    if not isinstance(env_obs, EnvObservation):
        raise TypeError("env_obs must be EnvObservation")
    step_index, controller_steps, time_since_birth = _env_timing(controller_ctx, env_obs)
    readout = state.evidence_readout
    distance = readout.distance.value if readout.valid and readout.distance is not None else None
    bearing = readout.bearing.value if readout.valid and readout.bearing is not None else None
    valid = bool(readout.valid and distance is not None)
    maintained_ref = state.stable_ref
    return MaternalTemporalSampleV1(
        observation_no=state.observation_no,
        source_evidence_map_ref=state.evidence_ref,
        maintained_map_ref=maintained_ref,
        frame_id=state.evidence_map.frame.frame_id,
        units=state.evidence_map.frame.units,
        identity_handle=readout.maternal_element_id,
        self_element_id=readout.self_element_id,
        maternal_element_id=readout.maternal_element_id,
        step_index=step_index,
        controller_steps=controller_steps,
        time_since_birth=time_since_birth,
        distance=float(distance) if distance is not None else None,
        bearing_degrees=float(bearing) if bearing is not None else None,
        valid=valid,
        reason=readout.reason,
    )


def _ref_from_dict(value: Any) -> Optional[NavMapRefV1]:
    """Decode one map reference from a JSON-safe dict."""
    if not isinstance(value, dict):
        return None
    map_id = value.get("map_id")
    revision = value.get("revision")
    if not isinstance(map_id, str) or not map_id.strip():
        return None
    if not isinstance(revision, int) or isinstance(revision, bool):
        return None
    try:
        return NavMapRefV1(map_id=map_id, revision=revision)
    except (TypeError, ValueError):
        return None


def _sample_from_dict(value: Any) -> Optional[MaternalTemporalSampleV1]:
    """Decode one compact sample from the shared Sequential/Error window."""
    if not isinstance(value, dict):
        return None
    source_ref = _ref_from_dict(value.get("source_evidence_map_ref"))
    if source_ref is None:
        return None
    maintained_value = value.get("maintained_map_ref")
    maintained_ref = _ref_from_dict(maintained_value)
    if maintained_value is not None and maintained_ref is None:
        return None

    observation_no = value.get("observation_no")
    controller_steps = value.get("controller_steps")
    valid = value.get("valid")
    frame_id = value.get("frame_id")
    units = value.get("units")
    identity_handle = value.get("identity_handle")
    self_element_id = value.get("self_element_id")
    maternal_element_id = value.get("maternal_element_id")
    reason = value.get("reason")
    if not isinstance(observation_no, int) or isinstance(observation_no, bool):
        return None
    if not isinstance(controller_steps, int) or isinstance(controller_steps, bool):
        return None
    if not isinstance(valid, bool):
        return None
    if not isinstance(frame_id, str):
        return None
    if not isinstance(units, str):
        return None
    if not isinstance(identity_handle, str):
        return None
    if not isinstance(self_element_id, str):
        return None
    if not isinstance(maternal_element_id, str):
        return None
    if not isinstance(reason, str):
        return None

    try:
        return MaternalTemporalSampleV1(
            observation_no=observation_no,
            source_evidence_map_ref=source_ref,
            maintained_map_ref=maintained_ref,
            frame_id=frame_id,
            units=units,
            identity_handle=identity_handle,
            self_element_id=self_element_id,
            maternal_element_id=maternal_element_id,
            step_index=_optional_non_negative_int(value.get("step_index")),
            controller_steps=controller_steps,
            time_since_birth=_optional_finite_float(value.get("time_since_birth")),
            distance=_optional_finite_float(value.get("distance")),
            bearing_degrees=_optional_finite_float(value.get("bearing_degrees")),
            valid=valid,
            reason=reason,
        )
    except (TypeError, ValueError):
        return None


def _frame_matches_sample(frame: dict[str, Any], sample: MaternalTemporalSampleV1) -> bool:
    """Return whether the latest generic seqerr frame belongs to this sample."""
    frame_step = _optional_non_negative_int(frame.get("step"))
    if sample.step_index is not None and frame_step is not None and sample.step_index == frame_step:
        frame_t = _optional_finite_float(frame.get("t"))
        if sample.time_since_birth is None or frame_t is None:
            return True
        return math.isclose(sample.time_since_birth, frame_t, rel_tol=0.0, abs_tol=1e-9)
    frame_t = _optional_finite_float(frame.get("t"))
    if sample.time_since_birth is not None and frame_t is not None:
        return math.isclose(sample.time_since_birth, frame_t, rel_tol=0.0, abs_tol=1e-9)
    return False


def _attach_sample_to_seqerr_window(
    ctx: Any,
    sample: MaternalTemporalSampleV1,
) -> tuple[list[dict[str, Any]], int]:
    """Attach one compact sample to the existing bounded seqerr ring buffer."""
    capacity = _seqerr_window_capacity(ctx)
    raw_history = getattr(ctx, "seqerr_history", None)
    history = [dict(item) for item in raw_history if isinstance(item, dict)] if isinstance(raw_history, list) else []

    frame: dict[str, Any]
    use_latest = False
    if history:
        latest = history[-1]
        temporal_bucket = latest.get("navmap_temporal")
        temporal_bucket = temporal_bucket if isinstance(temporal_bucket, dict) else {}
        existing = temporal_bucket.get(_RELATION_KEY)
        use_latest = existing is None and _frame_matches_sample(latest, sample)
    if use_latest:
        frame = history[-1]
    else:
        frame = {
            "step": sample.step_index if sample.step_index is not None else sample.controller_steps,
            "t": sample.time_since_birth,
            "raw": {},
            "slots": {},
        }
        history.append(frame)

    temporal_bucket = frame.get("navmap_temporal")
    temporal_bucket = dict(temporal_bucket) if isinstance(temporal_bucket, dict) else {}
    temporal_bucket[_RELATION_KEY] = sample.as_dict()
    frame["navmap_temporal"] = temporal_bucket

    if len(history) > capacity:
        del history[: len(history) - capacity]
    ctx.seqerr_history = history
    return history, capacity


def _samples_from_seqerr_window(history: Sequence[dict[str, Any]]) -> list[MaternalTemporalSampleV1]:
    """Return maternal temporal samples stored in the shared bounded window."""
    samples: list[MaternalTemporalSampleV1] = []
    for frame in history:
        if not isinstance(frame, dict):
            continue
        bucket = frame.get("navmap_temporal")
        if not isinstance(bucket, dict):
            continue
        sample = _sample_from_dict(bucket.get(_RELATION_KEY))
        if sample is not None:
            samples.append(sample)
    return samples


def _compatible_valid_suffix(samples: Sequence[MaternalTemporalSampleV1]) -> list[MaternalTemporalSampleV1]:
    """Return the contiguous valid suffix for one identity and frame."""
    if not samples or not samples[-1].valid:
        return []
    latest = samples[-1]
    suffix: list[MaternalTemporalSampleV1] = []
    for sample in reversed(samples):
        if not sample.valid:
            break
        if sample.identity_handle != latest.identity_handle or sample.frame_id != latest.frame_id or sample.units != latest.units:
            break
        suffix.append(sample)
    suffix.reverse()
    return suffix


def _strictly_increasing(values: Sequence[float], *, minimum_delta: float) -> bool:
    """Return whether each adjacent value increases by more than the declared minimum."""
    return all((right - left) > minimum_delta for left, right in zip(values, values[1:]))


def _time_axis(
    samples: Sequence[MaternalTemporalSampleV1],
    *,
    minimum_elapsed_time: float,
) -> tuple[str, list[float]]:
    """Choose existing observation timing without creating another clock."""
    times = [sample.time_since_birth for sample in samples]
    if all(value is not None for value in times):
        time_values = [float(value) for value in times if value is not None]
        if _strictly_increasing(time_values, minimum_delta=minimum_elapsed_time):
            return "time_since_birth", time_values

    steps = [sample.step_index for sample in samples]
    if all(value is not None for value in steps):
        step_values = [float(value) for value in steps if value is not None]
        if _strictly_increasing(step_values, minimum_delta=minimum_elapsed_time):
            return "step_index", step_values

    observation_values = [float(sample.observation_no) for sample in samples]
    return "observation_no", observation_values


def _interval_rates(values: Sequence[float], axis: Sequence[float]) -> list[float]:
    """Return deterministic adjacent rates for equal-length value/time sequences."""
    rates: list[float] = []
    for left_value, right_value, left_time, right_time in zip(values, values[1:], axis, axis[1:]):
        dt = right_time - left_time
        if dt > 0.0:
            rates.append((right_value - left_value) / dt)
    return rates


def _rate_uncertainty(interval_rates: Sequence[float], overall_rate: float) -> float:
    """Return the maximum interval-rate deviation from the overall rate."""
    if not interval_rates:
        return 0.0
    return max(abs(rate - overall_rate) for rate in interval_rates)


def _shortest_signed_angle_delta(start_degrees: float, end_degrees: float) -> float:
    """Return the signed shortest angular displacement in ``[-180, 180)``."""
    return ((end_degrees - start_degrees + 180.0) % 360.0) - 180.0


def _unwrapped_bearing_values(samples: Sequence[MaternalTemporalSampleV1]) -> Optional[list[float]]:
    """Return a locally unwrapped bearing series, or ``None`` if any bearing is absent."""
    bearings = [sample.bearing_degrees for sample in samples]
    if any(value is None for value in bearings):
        return None
    numeric = [float(value) for value in bearings if value is not None]
    if not numeric:
        return None
    unwrapped = [numeric[0]]
    for previous, current in zip(numeric, numeric[1:]):
        unwrapped.append(unwrapped[-1] + _shortest_signed_angle_delta(previous, current))
    return unwrapped


def _distance_trend(
    rate: float,
    *,
    previous: MaternalTemporalTrendV1,
    thresholds: MaternalTemporalThresholdsV1,
) -> MaternalTemporalTrendV1:
    """Classify one relative distance rate with explicit hysteresis and ties."""
    if previous is MaternalTemporalTrendV1.APPROACHING and rate < -thresholds.hysteresis_rate:
        return MaternalTemporalTrendV1.APPROACHING
    if previous is MaternalTemporalTrendV1.RECEDING and rate > thresholds.hysteresis_rate:
        return MaternalTemporalTrendV1.RECEDING
    if rate < -thresholds.stable_rate_tolerance:
        return MaternalTemporalTrendV1.APPROACHING
    if rate > thresholds.stable_rate_tolerance:
        return MaternalTemporalTrendV1.RECEDING
    return MaternalTemporalTrendV1.STABLE


def _bearing_trend(
    rate: float,
    *,
    previous: MaternalBearingTrendV1,
    thresholds: MaternalTemporalThresholdsV1,
) -> MaternalBearingTrendV1:
    """Classify one bearing rate with explicit hysteresis and deterministic ties."""
    if previous is MaternalBearingTrendV1.CLOCKWISE and rate < -thresholds.bearing_hysteresis_rate:
        return MaternalBearingTrendV1.CLOCKWISE
    if previous is MaternalBearingTrendV1.COUNTERCLOCKWISE and rate > thresholds.bearing_hysteresis_rate:
        return MaternalBearingTrendV1.COUNTERCLOCKWISE
    if rate < -thresholds.stable_bearing_rate_tolerance:
        return MaternalBearingTrendV1.CLOCKWISE
    if rate > thresholds.stable_bearing_rate_tolerance:
        return MaternalBearingTrendV1.COUNTERCLOCKWISE
    return MaternalBearingTrendV1.STABLE


def _invalid_readout(
    sample: MaternalTemporalSampleV1,
    *,
    thresholds: MaternalTemporalThresholdsV1,
    window_capacity: int,
    window_sample_count: int,
    valid_sample_count: int,
    support_status: str,
    freshness: str,
    reason: str,
) -> MaternalTemporalReadoutV1:
    """Return one explicit UNKNOWN temporal readout."""
    support_fraction = min(1.0, valid_sample_count / float(window_capacity))
    return MaternalTemporalReadoutV1(
        source_evidence_map_ref=sample.source_evidence_map_ref,
        maintained_map_ref=sample.maintained_map_ref,
        target_element_id=sample.maternal_element_id,
        frame_id=sample.frame_id,
        units=sample.units,
        trend=MaternalTemporalTrendV1.UNKNOWN,
        bearing_trend=MaternalBearingTrendV1.UNKNOWN,
        window_capacity=window_capacity,
        window_sample_count=window_sample_count,
        valid_sample_count=valid_sample_count,
        bearing_valid_sample_count=0,
        window_start_observation_no=None,
        window_end_observation_no=sample.observation_no,
        interval_source=None,
        elapsed_time=None,
        distance_start=None,
        distance_end=sample.distance,
        distance_delta=None,
        relative_rate=None,
        rate_uncertainty=None,
        bearing_start_degrees=None,
        bearing_end_degrees=sample.bearing_degrees,
        bearing_delta_degrees=None,
        bearing_rate_degrees=None,
        bearing_rate_uncertainty=None,
        support_status=support_status,
        support_fraction=support_fraction,
        freshness=freshness,
        valid=False,
        reason=reason,
        thresholds=thresholds,
    )


def maternal_temporal_readout_from_samples_v1(
    samples: Sequence[MaternalTemporalSampleV1],
    *,
    thresholds: MaternalTemporalThresholdsV1,
    window_capacity: int,
    previous_trend: MaternalTemporalTrendV1 = MaternalTemporalTrendV1.UNKNOWN,
    previous_bearing_trend: MaternalBearingTrendV1 = MaternalBearingTrendV1.UNKNOWN,
) -> MaternalTemporalReadoutV1:
    """Decode static temporal features from a bounded compact sample sequence."""
    if not samples:
        raise ValueError("samples must contain the current maternal temporal sample")
    if not isinstance(thresholds, MaternalTemporalThresholdsV1):
        raise TypeError("thresholds must be MaternalTemporalThresholdsV1")
    _require_positive_int(window_capacity, field_name="window_capacity")
    if not isinstance(previous_trend, MaternalTemporalTrendV1):
        raise TypeError("previous_trend must be MaternalTemporalTrendV1")
    if not isinstance(previous_bearing_trend, MaternalBearingTrendV1):
        raise TypeError("previous_bearing_trend must be MaternalBearingTrendV1")
    for sample in samples:
        if not isinstance(sample, MaternalTemporalSampleV1):
            raise TypeError("samples must contain MaternalTemporalSampleV1 values")

    current = samples[-1]
    suffix = _compatible_valid_suffix(samples)
    if not current.valid:
        return _invalid_readout(
            current,
            thresholds=thresholds,
            window_capacity=window_capacity,
            window_sample_count=len(samples),
            valid_sample_count=0,
            support_status="current_geometry_unknown",
            freshness="unavailable",
            reason=f"current_geometry_unknown:{current.reason}",
        )
    if window_capacity < thresholds.minimum_valid_samples:
        return _invalid_readout(
            current,
            thresholds=thresholds,
            window_capacity=window_capacity,
            window_sample_count=len(samples),
            valid_sample_count=len(suffix),
            support_status="insufficient_window_capacity",
            freshness="fresh",
            reason=(
                f"insufficient_window_capacity:{window_capacity}/"
                f"{thresholds.minimum_valid_samples}"
            ),
        )
    if len(suffix) < thresholds.minimum_valid_samples:
        return _invalid_readout(
            current,
            thresholds=thresholds,
            window_capacity=window_capacity,
            window_sample_count=len(samples),
            valid_sample_count=len(suffix),
            support_status="insufficient_history",
            freshness="fresh",
            reason=f"insufficient_history:{len(suffix)}/{thresholds.minimum_valid_samples}",
        )

    interval_source, axis = _time_axis(suffix, minimum_elapsed_time=thresholds.minimum_elapsed_time)
    elapsed_time = axis[-1] - axis[0]
    if elapsed_time <= thresholds.minimum_elapsed_time:
        return _invalid_readout(
            current,
            thresholds=thresholds,
            window_capacity=window_capacity,
            window_sample_count=len(samples),
            valid_sample_count=len(suffix),
            support_status="invalid_elapsed_time",
            freshness="fresh",
            reason="invalid_elapsed_time",
        )

    distances = [float(sample.distance) for sample in suffix if sample.distance is not None]
    distance_start = distances[0]
    distance_end = distances[-1]
    distance_delta = distance_end - distance_start
    relative_rate = distance_delta / elapsed_time
    interval_distance_rates = _interval_rates(distances, axis)
    rate_uncertainty = _rate_uncertainty(interval_distance_rates, relative_rate)
    trend = _distance_trend(relative_rate, previous=previous_trend, thresholds=thresholds)

    unwrapped_bearings = _unwrapped_bearing_values(suffix)
    bearing_valid_sample_count = sum(sample.bearing_degrees is not None for sample in suffix)
    bearing_start: Optional[float] = None
    bearing_end: Optional[float] = None
    bearing_delta: Optional[float] = None
    bearing_rate: Optional[float] = None
    bearing_rate_uncertainty: Optional[float] = None
    bearing_trend = MaternalBearingTrendV1.UNKNOWN
    if unwrapped_bearings is not None and len(unwrapped_bearings) >= thresholds.minimum_valid_samples:
        bearing_start = suffix[0].bearing_degrees
        bearing_end = suffix[-1].bearing_degrees
        bearing_delta = unwrapped_bearings[-1] - unwrapped_bearings[0]
        bearing_rate = bearing_delta / elapsed_time
        interval_bearing_rates = _interval_rates(unwrapped_bearings, axis)
        bearing_rate_uncertainty = _rate_uncertainty(interval_bearing_rates, bearing_rate)
        bearing_trend = _bearing_trend(
            bearing_rate,
            previous=previous_bearing_trend,
            thresholds=thresholds,
        )

    return MaternalTemporalReadoutV1(
        source_evidence_map_ref=current.source_evidence_map_ref,
        maintained_map_ref=current.maintained_map_ref,
        target_element_id=current.maternal_element_id,
        frame_id=current.frame_id,
        units=current.units,
        trend=trend,
        bearing_trend=bearing_trend,
        window_capacity=window_capacity,
        window_sample_count=len(samples),
        valid_sample_count=len(suffix),
        bearing_valid_sample_count=bearing_valid_sample_count,
        window_start_observation_no=suffix[0].observation_no,
        window_end_observation_no=current.observation_no,
        interval_source=interval_source,
        elapsed_time=elapsed_time,
        distance_start=distance_start,
        distance_end=distance_end,
        distance_delta=distance_delta,
        relative_rate=relative_rate,
        rate_uncertainty=rate_uncertainty,
        bearing_start_degrees=bearing_start,
        bearing_end_degrees=bearing_end,
        bearing_delta_degrees=bearing_delta,
        bearing_rate_degrees=bearing_rate,
        bearing_rate_uncertainty=bearing_rate_uncertainty,
        support_status="supported",
        support_fraction=min(1.0, len(suffix) / float(window_capacity)),
        freshness="fresh",
        valid=True,
        reason="bounded_temporal_relation_supported",
        thresholds=thresholds,
    )


def _previous_state(ctx: Any) -> Optional[MaternalTemporalShadowStateV1]:
    """Return the preceding Phase 4B state when available."""
    value = getattr(ctx, "navmap_maternal_temporal_state", None)
    return value if isinstance(value, MaternalTemporalShadowStateV1) else None


def _history_limit(ctx: Any) -> int:
    """Return one bounded positive Phase 4B trace-history limit."""
    value = _ctx_int(ctx, "navmap_maternal_temporal_history_limit", _DEFAULT_HISTORY_LIMIT)
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_trace_history(ctx: Any, row: dict[str, Any]) -> None:
    """Append one bounded JSON-safe Phase 4B diagnostic trace."""
    raw_history = getattr(ctx, "navmap_maternal_temporal_history", None)
    history = [dict(item) for item in raw_history if isinstance(item, dict)] if isinstance(raw_history, list) else []
    history.append(dict(row))
    ctx.navmap_maternal_temporal_history = history[-_history_limit(ctx):]


def _update_seqerr_last(ctx: Any, sample: MaternalTemporalSampleV1, readout: MaternalTemporalReadoutV1) -> None:
    """Expose the map-derived temporal result through the existing seqerr surface."""
    raw_last = getattr(ctx, "seqerr_last", None)
    last = dict(raw_last) if isinstance(raw_last, dict) else {}
    bucket = last.get("navmap_temporal")
    bucket = dict(bucket) if isinstance(bucket, dict) else {}
    bucket[_RELATION_KEY] = {
        "sample": sample.as_dict(),
        "readout": readout.as_dict(),
    }
    last["navmap_temporal"] = bucket
    ctx.seqerr_last = last


def maternal_temporal_shadow_observation_step_v1(ctx: Any, env_obs: EnvObservation) -> dict[str, Any]:
    """Process one Phase 4A geometry result through the Phase 4B shadow.

    The function attaches one compact sample to the existing bounded seqerr
    window, decodes a static temporal readout, and stores only diagnostic state.
    It cannot change BodyMap, FollowMom applicability, policy selection, or any
    immutable NavMap revision.
    """
    if ctx is None or env_obs is None:
        return {}
    if not bool(getattr(ctx, "navmap_maternal_temporal_shadow_enabled", True)):
        return {
            "schema": "maternal_temporal_shadow_update_v1",
            "phase": "4B",
            "status": "disabled",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
        }
    if not bool(getattr(ctx, "seqerr_enabled", True)):
        return {
            "schema": "maternal_temporal_shadow_update_v1",
            "phase": "4B",
            "status": "sequential_unit_disabled",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
        }
    geometry_state = getattr(ctx, "navmap_maternal_state", None)
    if not isinstance(geometry_state, MaternalGeometryShadowStateV1):
        return {
            "schema": "maternal_temporal_shadow_update_v1",
            "phase": "4B",
            "status": "geometry_unavailable",
            "authority": "shadow_only",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
            "reason": "phase4a_geometry_state_unavailable",
        }

    sample = maternal_temporal_sample_from_geometry_state_v1(
        geometry_state,
        env_obs,
        controller_ctx=ctx,
    )
    shared_history, window_capacity = _attach_sample_to_seqerr_window(ctx, sample)
    window_samples = _samples_from_seqerr_window(shared_history)
    previous_state = _previous_state(ctx)
    previous_trend = (
        previous_state.readout.trend if previous_state is not None else MaternalTemporalTrendV1.UNKNOWN
    )
    previous_bearing_trend = (
        previous_state.readout.bearing_trend
        if previous_state is not None
        else MaternalBearingTrendV1.UNKNOWN
    )
    thresholds = maternal_temporal_thresholds_from_ctx_v1(ctx)
    readout = maternal_temporal_readout_from_samples_v1(
        window_samples,
        thresholds=thresholds,
        window_capacity=window_capacity,
        previous_trend=previous_trend,
        previous_bearing_trend=previous_bearing_trend,
    )
    state = MaternalTemporalShadowStateV1(
        sample=sample,
        readout=readout,
        previous_trend=previous_trend,
        previous_bearing_trend=previous_bearing_trend,
    )
    row = state.as_dict()
    if readout.valid:
        status = "supported"
    elif readout.support_status == "current_geometry_unknown":
        status = "unknown"
    else:
        status = readout.support_status
    row.update(
        {
            "schema": "maternal_temporal_shadow_update_v1",
            "status": status,
            "controller_steps": getattr(ctx, "controller_steps", None),
            "ticks": getattr(ctx, "ticks", None),
            "phase4a_observation_no": geometry_state.observation_no,
        }
    )

    ctx.navmap_maternal_temporal_state = state
    ctx.navmap_maternal_temporal_last_update = dict(row)
    _append_trace_history(ctx, row)
    _update_seqerr_last(ctx, sample, readout)
    return row


def maternal_temporal_shadow_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 4B update."""
    if ctx is None:
        return {
            "schema": "maternal_temporal_shadow_summary_v1",
            "phase": "4B",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_maternal_temporal_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "maternal_temporal_shadow_summary_v1",
            "phase": "4B",
            "status": "idle",
            "authority": "shadow_only",
            "history_count": len(getattr(ctx, "navmap_maternal_temporal_history", []) or []),
        }
    out = dict(row)
    out["schema"] = "maternal_temporal_shadow_summary_v1"
    out["history_count"] = len(getattr(ctx, "navmap_maternal_temporal_history", []) or [])
    return out


def _ref_text(value: Any) -> str:
    """Render one optional JSON map reference."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id', '?')}@r{value.get('revision', '?')}"


def _float_text(value: Any, *, digits: int = 3, suffix: str = "") -> str:
    """Render one optional finite numeric value."""
    number = _optional_finite_float(value)
    if number is None:
        return "unknown"
    return f"{number:.{digits}f}{suffix}"


def render_maternal_temporal_shadow_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 4B maternal temporal lines."""
    summary = maternal_temporal_shadow_summary_v1(ctx)
    lines = ["MATERNAL TEMPORAL PHASE 4B SHADOW:"]
    status = summary.get("status")
    if status in {
        "ctx_unavailable",
        "idle",
        "disabled",
        "sequential_unit_disabled",
        "geometry_unavailable",
        "dependency_error",
        "error",
    }:
        lines.append(
            "  "
            f"status={status} authority=shadow_only follow_mom_authority=legacy_bodymap_policy_runtime "
            "map_can_trigger_follow_mom=False"
        )
        if summary.get("reason") is not None:
            lines.append(f"  reason={summary.get('reason')}")
        if status == "error":
            lines.append(f"  error_type={summary.get('error_type')} error={summary.get('error')}")
        return lines

    sample = summary.get("sample")
    sample = sample if isinstance(sample, dict) else {}
    readout = summary.get("readout")
    readout = readout if isinstance(readout, dict) else {}
    thresholds = readout.get("thresholds")
    thresholds = thresholds if isinstance(thresholds, dict) else {}

    lines.append(
        "  "
        f"status={status} authority=shadow_only follow_mom_authority=legacy_bodymap_policy_runtime "
        "map_can_trigger_follow_mom=False"
    )
    lines.append(
        "  "
        f"sample observation={sample.get('observation_no')} source={_ref_text(sample.get('source_evidence_map_ref'))} "
        f"distance={_float_text(sample.get('distance'))} bearing={_float_text(sample.get('bearing_degrees'), digits=1, suffix='deg')} "
        f"frame={sample.get('frame_id')} valid={sample.get('valid')}"
    )
    lines.append(
        "  "
        f"window samples={readout.get('window_sample_count')}/{readout.get('window_capacity')} "
        f"valid={readout.get('valid_sample_count')} interval={_float_text(readout.get('elapsed_time'))} "
        f"source={readout.get('interval_source')} support={readout.get('support_status')} "
        f"fraction={_float_text(readout.get('support_fraction'))} freshness={readout.get('freshness')}"
    )
    lines.append(
        "  "
        f"trend={readout.get('trend')} rate={_float_text(readout.get('relative_rate'))} "
        f"uncertainty={_float_text(readout.get('rate_uncertainty'))} reason={readout.get('reason')}"
    )
    lines.append(
        "  "
        f"bearing_trend={readout.get('bearing_trend')} "
        f"bearing_rate={_float_text(readout.get('bearing_rate_degrees'), digits=2, suffix='deg/t')} "
        f"bearing_uncertainty={_float_text(readout.get('bearing_rate_uncertainty'), digits=2, suffix='deg/t')}"
    )
    lines.append(
        "  "
        f"threshold stable={thresholds.get('stable_rate_tolerance')} hysteresis={thresholds.get('hysteresis_rate')} "
        f"min_history={thresholds.get('minimum_valid_samples')} shared_seqerr_window=True "
        "stores_full_navmaps=False creates_navmap_revision=False"
    )
    return lines
