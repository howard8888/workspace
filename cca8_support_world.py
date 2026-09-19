#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""World-side support simulation: retained P16-1E-B and additive P18-H2 motor mode.

This is an opt-in physical *surrogate*, not a NavMap, learned motor skill,
validated goat biomechanical model, or second environment framework.
``HybridEnvironment`` owns the body snapshot and calls these pure functions.
The default newborn and legacy scenarios never enable this provider.

A received ``policy:stand_up`` token recruits load-bearing limb support and
lifts the body. Without that token there is no lifting drive. An external
surface disturbance removes useful loading and increases unwanted sliding;
it can overwhelm exactly the same received command. No phase, milestone,
attempt count, PNM, desired configuration, reward or cognitive context is read.

The packet uses the existing ``posture_support_v1`` schema. Its numerical
measurements come from the simulated body, not from decoding the old binary
posture label. The old A0 label is instead derived from body orientation for
compatibility, and remains a disclosed coarse perception scaffold. The richer
packet still has only read-only authority in NCA8 until later planned slices.

The separate opt-in ``MotorWorldV1`` below uses signed orientation/extension
drives and the existing H1 motor messages. It does not use the binary task
token or alter any v1 function. Its equations, delayed sensing and fixed-time
perturbations model physical response only, not BodyMap mapping, target
following, task prediction or learning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1

__version__ = "0.2.0"
__all__ = [
    "MotorBodyStateV1",
    "MotorWorldPerturbationV1",
    "MotorWorldProfileV1",
    "MotorWorldV1",
    "SupportWorldStateV1",
    "SupportWorldProfileV1",
    "support_profile_for_scenario_v1",
    "advance_support_world_v1",
    "support_observation_packet_v1",
    "validate_support_dt_v1",
    "__version__",
]


def _bounded_number(value: float, name: str, upper: float) -> float:
    """Validate a finite non-Boolean physical quantity without silently clamping input."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be numeric")
    number = float(value)
    if not math.isfinite(number) or not 0.0 <= number <= upper:
        raise ValueError(f"{name} must be finite and in [0, {upper}]")
    return number


def _clamp(value: float, upper: float = 1.0) -> float:
    """Apply the declared physical model's contact/range saturation, not an input repair."""
    return max(0.0, min(upper, value))


def validate_support_dt_v1(dt: float) -> float:
    """Return the supported physical integration interval in seconds, 0 < dt <= 1.

    The fixed-rate surrogate is qualified only over this interval. Reject an
    invalid interval before changing body state, time or sample counters. No
    silent subdivision, time scaling, default replacement or neural timing
    interpretation is provided by this slice.
    """
    interval = _bounded_number(dt, "support dt", 1.0)
    if interval == 0.0:
        raise ValueError("support dt must be greater than zero")
    return interval


@dataclass(frozen=True, slots=True)
class SupportWorldStateV1:
    """One immutable physical body snapshot; all values are actual simulated quantities.

    ``body_ground_angle_degrees`` is the undirected body-axis/ground angle:
    0 is horizontal and 90 upright. ``useful_loading`` is the modeled fraction
    of body weight borne usefully by limbs, in [0, 1]; lateral ground contact
    alone is not limb loading. ``destabilization`` is unwanted sliding/collapse
    speed as a fraction of the profile's reference maximum, in [0, 1]. It is
    not prediction error, action progress, task success or learned confidence.

    Partial limb loading can coexist with lateral contact during recovery.
    The Boolean lateral-contact sensor uses an angle threshold; this is a
    disclosed contact approximation, not a measured continuous contact area.
    There are no task IDs, timestamps, buffers or cognitive references here.
    """

    body_ground_angle_degrees: float = 10.0
    useful_loading: float = 0.45
    destabilization: float = 0.40

    def __post_init__(self) -> None:
        for name, upper in (("body_ground_angle_degrees", 90.0), ("useful_loading", 1.0), ("destabilization", 1.0)):
            object.__setattr__(self, name, _bounded_number(getattr(self, name), name, upper))

    @property
    def lateral_contact(self) -> bool:
        """Report the profile's coarse side-contact sensor: body angle <= 20 degrees."""
        return self.body_ground_angle_degrees <= 20.0

    @property
    def posture_label(self) -> str:
        """Supply the old A0 orientation label, not an activity-relative support verdict.

        Angle >= 75 degrees is reported as standing; all lower orientations
        are fallen/recovering in this two-label approximation. This direction
        of derivation is important: the measurements are never generated from
        the label. A0's later interpretation of standing as stable remains
        its old limitation; this property establishes no supported dwell.
        """
        return "standing" if self.body_ground_angle_degrees >= 75.0 else "fallen"


@dataclass(frozen=True, slots=True)
class SupportWorldProfileV1:
    """Immutable initial conditions and external disturbance for one support experiment.

    Both built-in scenarios use the same ``support_dynamics_v1`` equations and
    initial body. Their only difference is the imposed surface disturbance:
    0 for recovery, 0.85 for the adverse condition. This is an experimental
    forcing parameter, not a difficulty label read by cognition. Tests can
    supply another initial body or bounded disturbance through EnvConfig.
    No policy or learned gain is supplied by the profile.
    """

    initial_body: SupportWorldStateV1 = field(default_factory=SupportWorldStateV1)
    surface_disturbance: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.initial_body, SupportWorldStateV1):
            raise TypeError("initial_body must be SupportWorldStateV1")
        object.__setattr__(self, "surface_disturbance", _bounded_number(self.surface_disturbance, "surface_disturbance", 1.0))

    @property
    def profile_id(self) -> str:
        """Identify the fixed equations for external experiment provenance, not packet authority."""
        return "support_dynamics_v1"


def support_profile_for_scenario_v1(scenario_name: str) -> SupportWorldProfileV1 | None:
    """Select the two explicitly opt-in support scenarios without altering old defaults.

    Ordinary scenario names return None and retain the existing FSM path.
    A misspelled name in the reserved ``posture_support_`` namespace fails
    rather than silently running an unrelated newborn storyboard.
    """
    if scenario_name == "posture_support_recovery_v1":
        return SupportWorldProfileV1()
    if scenario_name == "posture_support_disturbed_v1":
        return SupportWorldProfileV1(surface_disturbance=0.85)
    if scenario_name.startswith("posture_support_"):
        raise ValueError(f"unknown support scenario: {scenario_name}")
    return None


def advance_support_world_v1(
    body: SupportWorldStateV1,
    *,
    action: str | None,
    profile: SupportWorldProfileV1,
    dt: float,
) -> SupportWorldStateV1:
    """Advance one physical snapshot using the received command and external forcing.

    Fixed ``support_dynamics_v1`` engineering equations, evaluated in this order:

    * L' = clip(L + dt * (0.60 * effort * (1 - L) - (0.10 + disturbance) * L)).
    * S_target = clip(0.45 * (1 - L') + disturbance).
    * S' = clip(S + dt * 0.50 * (S_target - S)).
    * angle' = clip(angle + dt * (35 * effort * L' * (1 - disturbance)
      - 18 * S' * (1 - L') - 45 * disturbance), 0, 90).

    L is limb-supported weight fraction; S is normalized unwanted sliding.
    The loading terms approximate actuator recruitment, passive loss of
    purchase and disturbance-induced unloading. Sliding relaxes toward an
    equilibrium set by loading and surface forcing. The angular terms are
    lift minus sliding/collapse and external disturbance, in degrees/second.
    Coefficients are test-profile choices, not measured mammalian constants.

    Effort is 1 only for the received ``policy:stand_up`` token; None is 0.
    There is no automatic lift on a null step and no hidden lower controller.
    No attempt count or elapsed-step index enters these equations. Repeated
    commands can have different effects as the physical state changes.
    Unsupported actions and invalid intervals fail before any caller mutation.
    The function returns a new immutable body; it owns neither clock nor RNG.
    """
    if not isinstance(body, SupportWorldStateV1) or not isinstance(profile, SupportWorldProfileV1):
        raise TypeError("support step requires a physical body and profile")
    interval = validate_support_dt_v1(dt)
    if action is not None and action != "policy:stand_up":
        raise ValueError("support profile accepts only policy:stand_up or None")
    effort = 1.0 if action == "policy:stand_up" else 0.0
    disturbance = profile.surface_disturbance
    loading = _clamp(body.useful_loading + interval * (
        0.60 * effort * (1.0 - body.useful_loading) - (0.10 + disturbance) * body.useful_loading
    ))
    sliding_target = _clamp(0.45 * (1.0 - loading) + disturbance)
    sliding = _clamp(body.destabilization + interval * 0.50 * (sliding_target - body.destabilization))
    angular_rate = 35.0 * effort * loading * (1.0 - disturbance) - 18.0 * sliding * (1.0 - loading) - 45.0 * disturbance
    angle = _clamp(body.body_ground_angle_degrees + interval * angular_rate, 90.0)
    return SupportWorldStateV1(angle, loading, sliding)


def support_observation_packet_v1(body: SupportWorldStateV1, *, step_index: int) -> dict[str, str | int | float | bool]:
    """Measure the physical body through the existing support packet, without changing it.

    The serialized test harness maps world step 0 (reset) to sample/event 1;
    after world step n its observation belongs to cycle n+1. ``step_index + 1``
    is this explicit clock-domain mapping, not evidence of progress or a
    runtime phase read. Re-observing a body at the same step returns the same
    identity and values. A world reset restarts the stream; NCA8 separately
    resets its owning consumer/generation. No stale sample is retimestamped.

    All four sensors are available in this deterministic provider. The
    existing admission/consumer path still handles absent or malformed data
    when a transport test or a future provider supplies it; no missing value
    is silently replaced here. Packet keys exactly match posture_support_v1:
    no profile, scenario, outcome, source-map, owner or action-answer fields.
    """
    if not isinstance(body, SupportWorldStateV1):
        raise TypeError("support measurement requires SupportWorldStateV1")
    if isinstance(step_index, bool) or not isinstance(step_index, int) or not 0 <= step_index < 2**63 - 1:
        raise ValueError("support world step must permit a positive signed-64-bit sample identity")
    return {
        "schema": "posture_support_v1",
        "sample_id": step_index + 1,
        "event_cycle": step_index + 1,
        "frame_id": "body_ground_v1",
        "body_ground_angle_degrees": body.body_ground_angle_degrees,
        "useful_loading": body.useful_loading,
        "destabilization": body.destabilization,
        "lateral_contact": body.lateral_contact,
    }


# ---------------------------------------------------------------------------
# P18-H2: an independent, command-driven physical profile in the same module.
# The retained v1 functions above are intentionally unchanged.
# ---------------------------------------------------------------------------

_MOTOR_COUNTER_LIMIT = 2**63 - 1
_MOTOR_PENDING_LIMIT = 16
_MOTOR_CHANNELS = (
    "body_tilt_degrees", "support_extension", "support_contact", "useful_loading", "destabilization",
)


def _motor_number(value: object, name: str, lower: float, upper: float) -> float:
    """Check external physical parameters before mutating a body or its time."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a non-Boolean number")
    # All callers supply finite bounds. Check before conversion so huge integers,
    # NaN and infinities are rejected without overflow or silent input repair.
    if not lower <= value <= upper:
        raise ValueError(f"{name} must be finite and in [{lower}, {upper}]")
    return float(value)


def _motor_integer(value: object, name: str, upper: int = _MOTOR_COUNTER_LIMIT) -> int:
    """Check a nonnegative integral physical tick/count, without Boolean coercion."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-Boolean integer")
    if not 0 <= value <= upper:
        raise ValueError(f"{name} must be in [0, {upper}]")
    return value


@dataclass(frozen=True, slots=True)
class MotorBodyStateV1:
    """Two actual simulated coordinates, not a target or a cortical representation.

    Tilt is signed from upright (zero), with lateral limits at -90/+90 degrees.
    Extension is one aggregate actuator coordinate in [0, 1], not a particular
    limb or useful loading. Gravity, contact and loading are calculated by the
    provider. Replacing this small immutable snapshot advances no clock itself.
    """

    body_tilt_degrees: float = 30.0
    support_extension: float = 0.40

    def __post_init__(self) -> None:
        object.__setattr__(self, "body_tilt_degrees", _motor_number(self.body_tilt_degrees, "body_tilt_degrees", -90.0, 90.0))
        object.__setattr__(self, "support_extension", _motor_number(self.support_extension, "support_extension", 0.0, 1.0))


@dataclass(frozen=True, slots=True)
class MotorWorldPerturbationV1:
    """An external intervention over physical intervals [start_tick, stop_tick).

    A tick identifies an integration interval, not a cognitive call or command
    number. The angular rate is added in degrees/s; support removal and sensor
    dropout are distinct interventions. Dropout discards acquisitions from the
    affected intervals, never previously acquired reports already in transit.
    At the interval end, the nominal surface/sensor configuration resumes.
    These experiment settings are never included in agent-visible feedback.
    """

    start_tick: int
    stop_tick: int
    angular_rate_degrees_s: float = 0.0
    remove_support: bool = False
    drop_feedback: bool = False

    def __post_init__(self) -> None:
        start = _motor_integer(self.start_tick, "start_tick")
        stop = _motor_integer(self.stop_tick, "stop_tick")
        if stop <= start:
            raise ValueError("perturbation stop_tick must follow start_tick")
        object.__setattr__(self, "angular_rate_degrees_s", _motor_number(
            self.angular_rate_degrees_s, "angular_rate_degrees_s", -180.0, 180.0,
        ))
        if not isinstance(self.remove_support, bool) or not isinstance(self.drop_feedback, bool):
            raise TypeError("perturbation flags must be Boolean")


@dataclass(frozen=True, slots=True)
class MotorWorldProfileV1:
    """Fixed physical and sensor settings for one isolated P18-H2 experiment.

    The frozen H1 design supplies the nominal equations: 90 degrees/s at full
    orientation drive, 1 extension unit/s, and passive angular drift
    12*sin(tilt)*(1-loading). Required surface reach defaults to 0.25. This is
    a functional surrogate, not fitted goat biomechanics or learned competence.

    ``dt_seconds`` is fixed for the instance: nominal 0.05, with explicitly
    selected smaller positive steps allowed for resolution tests. Blocking a
    motor suppresses its drive, not gravity or external forcing. Extension is
    retained at zero drive; this does not guarantee useful support.

    Post-step sensing has a constant 0-16 tick delivery delay (nominal 1).
    Missing channels are explicitly named; missing whole acquisitions are
    scheduled separately. Up to sixteen ordered, nonoverlapping interventions
    avoid a general event framework and ambiguous simultaneous overrides.
    """

    initial_body: MotorBodyStateV1 = field(default_factory=MotorBodyStateV1)
    dt_seconds: float = 0.05
    surface_reach: float = 0.25
    surface_present: bool = True
    orientation_motor_enabled: bool = True
    extension_motor_enabled: bool = True
    sensor_delay_ticks: int = 1
    unavailable_channels: tuple[str, ...] = ()
    perturbations: tuple[MotorWorldPerturbationV1, ...] = ()
    profile_id: str = field(default="planar_motor_world_v1", init=False)

    def __post_init__(self) -> None:
        if not isinstance(self.initial_body, MotorBodyStateV1):
            raise TypeError("initial_body must be MotorBodyStateV1")
        interval = _motor_number(self.dt_seconds, "dt_seconds", 0.0, 0.05)
        reach = _motor_number(self.surface_reach, "surface_reach", 0.0, 1.0)
        if interval == 0.0 or reach == 1.0:
            raise ValueError("dt_seconds must be positive and surface_reach must be less than 1")
        object.__setattr__(self, "dt_seconds", interval)
        object.__setattr__(self, "surface_reach", reach)
        for name in ("surface_present", "orientation_motor_enabled", "extension_motor_enabled"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be Boolean")
        _motor_integer(self.sensor_delay_ticks, "sensor_delay_ticks", _MOTOR_PENDING_LIMIT)
        if not isinstance(self.unavailable_channels, tuple) or len(self.unavailable_channels) > len(_MOTOR_CHANNELS):
            raise ValueError("unavailable_channels must be a bounded tuple of measurement names")
        if any(not isinstance(name, str) or name not in _MOTOR_CHANNELS for name in self.unavailable_channels):
            raise ValueError("unknown unavailable motor measurement")
        if len(set(self.unavailable_channels)) != len(self.unavailable_channels):
            raise ValueError("unavailable motor measurements must be distinct")
        if not isinstance(self.perturbations, tuple) or len(self.perturbations) > 16:
            raise ValueError("perturbations must be a tuple of at most sixteen intervals")
        previous_stop = 0
        for event in self.perturbations:
            if not isinstance(event, MotorWorldPerturbationV1):
                raise TypeError("each perturbation must be MotorWorldPerturbationV1")
            if event.start_tick < previous_stop:
                raise ValueError("perturbations must be ordered and nonoverlapping")
            previous_stop = event.stop_tick


def _motor_support(body: MotorBodyStateV1, profile: MotorWorldProfileV1, surface_present: bool) -> tuple[bool, float]:
    """Derive contact/load from actual aggregate reach, not requested extension."""
    reach = body.support_extension * math.cos(math.radians(body.body_tilt_degrees))
    contact = surface_present and reach >= profile.surface_reach
    loading = _clamp((reach - profile.surface_reach) / (1.0 - profile.surface_reach)) if contact else 0.0
    return contact, loading


class MotorWorldV1:
    """A small deterministic body simulator with explicit command and sensing time.

    Construct only for an explicitly requested physical experiment. ``step``
    consumes a MotorCommandV1 (or neutral None), integrates one fixed interval,
    and returns only newly due MotorFeedbackV1 records. It chooses no task or
    target and performs no feedback correction. Future H4 code supplies that
    control. There are no threads, random draws or callbacks into cognition.

    Boundary tick k has time k*dt; a command at k integrates [k,k+1). The new
    acquisition is event k+1, sample k+2, available at event+sensor_delay_ticks.
    Reset sample 1 at tick 0 is immediately available. Polling ``observe`` merely
    rereads the latest delivered record, preserving its original identity/time.

    Validation and next-state calculations finish before any owned state changes.
    Thus a rejected command or calculation failure has no effect in this pure
    simulator. This is not an exactly-once physical robot-delivery guarantee.
    Only the latest body, latest delivered reading and up to sixteen in-transit
    readings are retained; a diagnostic trace never drives the physical model.
    """

    def __init__(self, stream: MotorStreamRefV1, profile: MotorWorldProfileV1 | None = None) -> None:
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        if profile is not None and not isinstance(profile, MotorWorldProfileV1):
            raise TypeError("profile must be MotorWorldProfileV1 or None")
        self._stream = stream
        self._profile = profile if profile is not None else MotorWorldProfileV1()
        self._body = self._profile.initial_body
        self._tick = 0
        self._last_command_id = 0
        self._pending: tuple[MotorFeedbackV1, ...] = ()
        self._latest_feedback = self._measure(self._body, 0.0, self._profile.surface_present, event_tick=0, delay=0)

    @property
    def stream(self) -> MotorStreamRefV1:
        """Return the current sensor/command identity, not actuator permission."""
        return self._stream

    @property
    def profile(self) -> MotorWorldProfileV1:
        """Return immutable external experiment settings; never pass them to cognition."""
        return self._profile

    @property
    def tick(self) -> int:
        """Return the physical boundary index; no focal cycle is implied."""
        return self._tick

    @property
    def elapsed_seconds(self) -> float:
        """Derive simulation time from the single integer clock and fixed interval."""
        return self._tick * self._profile.dt_seconds

    @property
    def body(self) -> MotorBodyStateV1:
        """Expose the immutable actual body for external tests, not agent sensing."""
        return self._body

    @property
    def pending_feedback_count(self) -> int:
        """Report bounded sensor deliveries in transit, without revealing future values."""
        return len(self._pending)

    def observe(self) -> MotorFeedbackV1:
        """Read the latest delivered sensor event without resampling or refreshing time.

        A dropout or delayed delivery can leave this record older than the body.
        Consumers must inspect its original time; a repeated read is not evidence
        of continuing contact or another independent observation.
        """
        return self._latest_feedback

    def reset(self) -> MotorFeedbackV1:
        """Reset this simulator to its initial body in a new stream generation.

        Pending deliveries and command ordering are discarded; old commands are
        rejected after reset. No active cognitive target or lease is restored.
        Generation overflow is rejected before replacing any owned value.
        """
        fresh = MotorWorldV1(MotorStreamRefV1(self._stream.stream_id, self._stream.generation + 1), self._profile)
        self._stream = fresh.stream
        self._body = fresh.body
        self._tick = 0
        self._last_command_id = 0
        self._pending = ()
        self._latest_feedback = fresh.observe()
        return self._latest_feedback

    def _measure(
        self, body: MotorBodyStateV1, angular_rate: float, surface_present: bool, *, event_tick: int, delay: int,
    ) -> MotorFeedbackV1:
        """Sense actual geometry; omit declared channels without repairing them.

        Destabilization follows the declared engineering readout using the
        pre-saturation angular rate, including external forcing. It is not a
        measured joint velocity, prediction error or task-completion flag.
        """
        contact, loading = _motor_support(body, self._profile, surface_present)
        instability = _clamp(abs(math.sin(math.radians(body.body_tilt_degrees))) * (1.0 - loading) + abs(angular_rate) / 180.0)
        missing = self._profile.unavailable_channels
        return MotorFeedbackV1(
            stream=self._stream, sample_id=event_tick + 1, event_tick=event_tick, available_tick=event_tick + delay,
            body_tilt_degrees=None if "body_tilt_degrees" in missing else body.body_tilt_degrees,
            support_extension=None if "support_extension" in missing else body.support_extension,
            support_contact=None if "support_contact" in missing else contact,
            useful_loading=None if "useful_loading" in missing else loading,
            destabilization=None if "destabilization" in missing else instability,
        )

    def step(self, command: MotorCommandV1 | None = None) -> tuple[MotorFeedbackV1, ...]:
        """Advance once and return newly available sensor reports in acquisition order.

        Unsupported inputs, wrong streams/generations/ticks, reused command IDs
        and exhausted counters fail before state/time changes. None applies zero
        drives for one interval; it does not repeat the previous command, cancel
        a cognitive target, freeze gravity or manufacture support.

        A scheduled intervention acts during its declared physical interval.
        Surface loss changes actual loading before the drift calculation; sensed
        consequences are acquired at the interval end. A dropped acquisition
        leaves a gap in sample IDs and does not erase earlier in-flight evidence.
        At constant delay, returned reports retain physical event order.
        """
        if command is not None and not isinstance(command, MotorCommandV1):
            raise TypeError("motor mode accepts MotorCommandV1 or None, not a task token or target")
        if self._tick >= _MOTOR_COUNTER_LIMIT - max(1, self._profile.sensor_delay_ticks) - 1:
            raise OverflowError("motor time/sample identity exhausted; reset required")
        if command is not None:
            command.validate_for_update(stream=self._stream, now_tick=self._tick, previous_command_id=self._last_command_id)
        orientation_drive = 0.0 if command is None or not self._profile.orientation_motor_enabled else command.orientation_drive
        extension_drive = 0.0 if command is None or not self._profile.extension_motor_enabled else command.extension_drive
        surface_present = self._profile.surface_present
        external_rate = 0.0
        dropout = False
        for event in self._profile.perturbations:
            if event.start_tick <= self._tick < event.stop_tick:
                external_rate = event.angular_rate_degrees_s
                surface_present = surface_present and not event.remove_support
                dropout = event.drop_feedback
                break
        _, previous_loading = _motor_support(self._body, self._profile, surface_present)
        angular_rate = (90.0 * orientation_drive
                        + 12.0 * math.sin(math.radians(self._body.body_tilt_degrees)) * (1.0 - previous_loading)
                        + external_rate)
        dt = self._profile.dt_seconds
        next_body = MotorBodyStateV1(
            body_tilt_degrees=max(-90.0, min(90.0, self._body.body_tilt_degrees + dt * angular_rate)),
            support_extension=_clamp(self._body.support_extension + dt * extension_drive),
        )
        next_tick = self._tick + 1
        pending = self._pending
        if not dropout:
            measurement = self._measure(next_body, angular_rate, surface_present,
                                        event_tick=next_tick, delay=self._profile.sensor_delay_ticks)
            pending += (measurement,)
        delivered = tuple(item for item in pending if item.available_tick <= next_tick)
        future = tuple(item for item in pending if item.available_tick > next_tick)
        if len(future) > _MOTOR_PENDING_LIMIT:
            raise OverflowError("motor feedback staging capacity exceeded")
        # All remaining work is replacement of already computed local values.
        if command is not None:
            self._last_command_id = command.command_id
        self._body = next_body
        self._tick = next_tick
        self._pending = future
        if delivered:
            self._latest_feedback = delivered[-1]
        return delivered
