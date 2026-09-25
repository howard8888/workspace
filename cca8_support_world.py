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

from cca8_motor_contracts import (
    MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, OralFeedbackV1, OralSealFeedbackV1, PlanarFeedbackV1, OralExtractionFeedbackV1,
    FeedingDeficitFeedbackV1,
)

__version__ = "0.8.0"
__all__ = [
    "MotorBodyStateV1", "FeedingConsequenceProfileV1", "FeedingConsequenceStateV1",
    "MotorWorldPerturbationV1",
    "MotorWorldProfileV1",
    "OralSealWorldStateV1", "OralSealWorldProfileV1", "OralClosurePerturbationV1",
    "OralExtractionWorldStateV1", "OralExtractionWorldProfileV1",
    "MotorWorldV1", "OralWorldStateV1", "OralWorldProfileV1", "OralWorldPerturbationV1",
    "PlanarObjectV1", "PlanarDetailObjectV1", "PlanarPerturbationV1", "PlanarWorldProfileV1", "PlanarWorldStateV1",
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


@dataclass(frozen=True, slots=True)
class PlanarObjectV1:
    """One fixed point/disk in the external horizontal scene, not a task target.

    Region IDs are opaque sensor handles. A positive radius denotes an obstacle;
    radius zero is a noncolliding landmark. The body is represented by a point
    for translation collision, not anatomical hooves or a contact polygon.
    """

    region_id: str
    position: tuple[float, float]
    radius: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.region_id, str) or not 1 <= len(self.region_id) <= 80:
            raise ValueError("object region_id must be bounded text")
        if any(not (char.isascii() and (char.isalnum() or char in "_:.-/")) for char in self.region_id):
            raise ValueError("object handle contains unsupported characters")
        PlanarFeedbackV1("scene_xy:validation", self.position, 0.0, False)
        object.__setattr__(self, "radius", _motor_number(self.radius, "obstacle radius", 0.0, 100.0))


@dataclass(frozen=True, slots=True)
class PlanarDetailObjectV1(PlanarObjectV1):
    """Opt-in visual detail on the same fixed-scene physical object interface.

    Inherited position/radius retain their ordinary point/disk meaning. The
    category and finite visual sensing radius affect only the existing sensory
    surface, never collision or movement. A feeding category is lower-provider
    recognition scaffolding, not learned nipple identity, part-of evidence,
    contact, latch, milk or a task milestone. Original PlanarObjectV1 instances
    keep their exact schema and unlimited-visibility behavior.
    """

    descriptor: str = "feeding"
    visibility_radius: float = 0.4

    def __post_init__(self) -> None:
        PlanarObjectV1.__post_init__(self)
        if not isinstance(self.descriptor, str) or self.descriptor not in {"object", "landmark", "hazard", "social", "feeding"}:
            raise ValueError("detail descriptor must belong to the existing surface recognition scaffold")
        radius = _motor_number(self.visibility_radius, "visibility radius", 0.0, 100.0)
        if radius <= 0.0:
            raise ValueError("a finite visibility radius must be positive")
        object.__setattr__(self, "visibility_radius", radius)


@dataclass(frozen=True, slots=True)
class PlanarPerturbationV1:
    """Fixed-time exogenous velocity/yaw, invisible to the motor controller.

    Velocity is scene-relative metres/second and can displace a neutral or
    blocked body. Heading rate is degrees/second. Neither is a commanded target,
    an action index, a task script or a sensory success flag.
    """

    start_tick: int
    stop_tick: int
    velocity: tuple[float, float] = (0.0, 0.0)
    heading_rate: float = 0.0

    def __post_init__(self) -> None:
        _motor_integer(self.start_tick, "planar perturbation start")
        _motor_integer(self.stop_tick, "planar perturbation stop")
        if self.stop_tick <= self.start_tick:
            raise ValueError("perturbation stop must follow start")
        if not isinstance(self.velocity, tuple) or len(self.velocity) != 2:
            raise TypeError("external velocity must be an immutable pair")
        for value in self.velocity:
            _motor_number(value, "external velocity", -2.0, 2.0)
        object.__setattr__(self, "heading_rate", _motor_number(self.heading_rate, "external heading rate", -180.0, 180.0))


@dataclass(frozen=True, slots=True)
class PlanarWorldProfileV1:
    """Opt-in horizontal extension of the SAME motor plant and sensor clock.

    Nominal speed is one metre/second times the normalized body-relative drive,
    conditional on actual contact/load and a near-upright body. Zero drive has
    no self-propulsion but external forcing still acts. Swept point/disk collision
    clips displacement at first contact without selecting a route or sliding
    around the obstacle. Localization and fixed object categories are explicit
    idealized sensory scaffolds; this is not a gait or vision simulator.
    """

    frame_id: str = "scene_xy:lab"
    initial_position: tuple[float, float] = (0.0, 0.0)
    initial_heading: float = 0.0
    objects: tuple[PlanarObjectV1, ...] = ()
    motor_enabled: bool = True
    position_available: bool = True
    heading_available: bool = True
    contact_available: bool = True
    vision_available: bool = True
    perturbations: tuple[PlanarPerturbationV1, ...] = ()

    def __post_init__(self) -> None:
        PlanarFeedbackV1(self.frame_id, self.initial_position, self.initial_heading, False)
        for flag in (self.motor_enabled, self.position_available, self.heading_available, self.contact_available, self.vision_available):
            if not isinstance(flag, bool):
                raise TypeError("planar profile switches must be Boolean")
        if not isinstance(self.objects, tuple) or len(self.objects) > 8 or any(not isinstance(item, PlanarObjectV1) for item in self.objects):
            raise ValueError("supply at most eight immutable physical objects")
        if len({item.region_id for item in self.objects}) != len(self.objects):
            raise ValueError("physical region handles must be unique")
        if any(item.radius > 0 and math.hypot(self.initial_position[0] - item.position[0],
                                             self.initial_position[1] - item.position[1]) < item.radius - 1e-12 for item in self.objects):
            raise ValueError("initial point body cannot lie inside a solid obstacle")
        if not isinstance(self.perturbations, tuple) or len(self.perturbations) > 8:
            raise ValueError("supply at most eight external planar perturbations")
        previous = 0
        for item in self.perturbations:
            if not isinstance(item, PlanarPerturbationV1) or item.start_tick < previous:
                raise ValueError("planar perturbations must be typed, ordered and nonoverlapping")
            previous = item.stop_tick


@dataclass(frozen=True, slots=True)
class PlanarWorldStateV1:
    """Actual horizontal pose and contact for external inspection only."""

    position: tuple[float, float]
    heading_degrees: float
    obstacle_contact: bool = False

    def __post_init__(self) -> None:
        PlanarFeedbackV1("scene_xy:validation", self.position, self.heading_degrees, self.obstacle_contact)

    def as_dict(self) -> dict[str, object]:
        """Export physical truth, never a substitute for an admitted sensor sample."""
        return {"position": list(self.position), "heading_degrees": self.heading_degrees, "obstacle_contact": self.obstacle_contact}


def _swept_planar_step(
    start: tuple[float, float], delta: tuple[float, float], objects: tuple[PlanarObjectV1, ...],
) -> tuple[tuple[float, float], bool]:
    """Clip one continuous point trajectory at its first disk intersection.

    This prevents tunnelling even when both unbounded endpoints are outside a
    disk. A tangent start may move away; an inward drive from contact stays put.
    The measured contact is a geometric consequence, not a copied expectation.
    """
    dx, dy = delta
    length_squared = dx * dx + dy * dy
    fraction = 1.0
    for item in objects:
        if item.radius <= 0.0 or length_squared == 0.0:
            continue
        px, py = start[0] - item.position[0], start[1] - item.position[1]
        radial = px * dx + py * dy
        c = px * px + py * py - item.radius * item.radius
        if c <= 1e-12 and radial < 0.0:
            fraction = 0.0
            continue
        discriminant = radial * radial - length_squared * c
        if discriminant < 0.0:
            continue
        entry = (-radial - math.sqrt(max(0.0, discriminant))) / length_squared
        if 0.0 < entry <= fraction:
            fraction = entry
    position = start[0] + fraction * dx, start[1] + fraction * dy
    contact = any(item.radius > 0.0 and math.hypot(position[0] - item.position[0], position[1] - item.position[1])
                  <= item.radius + 1e-10 for item in objects)
    return position, contact


@dataclass(frozen=True, slots=True)
class OralWorldStateV1:
    """Actual single-axis reach and touch, for external inspection only.

    Contact is recomputed from the current tip and independent scene surfaces.
    This is a functional point/disk sensing surrogate, not an anatomical mouth,
    force/collision solver, latch constraint or source of nourishment.
    """

    extension_metres: float = 0.0
    contact: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "extension_metres", _motor_number(self.extension_metres, "oral extension", 0.0, 0.35))
        if not isinstance(self.contact, bool):
            raise TypeError("physical oral contact must be Boolean")

    def as_dict(self) -> dict[str, object]:
        """Export actual geometry without substituting it for admitted sensing."""
        return {"extension_metres": self.extension_metres, "contact": self.contact}


@dataclass(frozen=True, slots=True)
class OralWorldPerturbationV1:
    """Fixed-time external reach forcing, independent of command or task count.

    The rate in metres/second acts over [start_tick, stop_tick) even with neutral
    drive. Its label/rate never enters local control; only later sensed effects
    do. This models a disturbance for a causal test, not neural noise or learning.
    """

    start_tick: int
    stop_tick: int
    rate_metres_s: float

    def __post_init__(self) -> None:
        _motor_integer(self.start_tick, "oral perturbation start")
        _motor_integer(self.stop_tick, "oral perturbation stop")
        if self.stop_tick <= self.start_tick:
            raise ValueError("oral perturbation stop must follow start")
        object.__setattr__(self, "rate_metres_s", _motor_number(self.rate_metres_s, "oral forcing", -1.0, 1.0))


@dataclass(frozen=True, slots=True)
class OralWorldProfileV1:
    """Opt-in body-forward reach in the existing plant, not a feeding programme.

    Full drive gives 0.5 metres/second within 0..0.35 metres. Motion requires
    actual supported posture; zero drive retains the reach coordinate, but body
    motion and independently scheduled forcing still change the tip or contact.
    Surfaces use the existing point/disk geometry independently of visual region
    categories. Any such surface can produce touch; contact conveys no identity.
    The tip may enter the sensor disk: no rigid collision, seal or latch is modeled.

    Sensing shares the existing motor acquisition and delayed delivery. Missing
    reach or touch channels remain unknown. Old profiles never enable this facet.
    """

    initial_extension_metres: float = 0.0
    surfaces: tuple[PlanarObjectV1, ...] = ()
    motor_enabled: bool = True
    extension_available: bool = True
    contact_available: bool = True
    perturbations: tuple[OralWorldPerturbationV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_extension_metres",
                           _motor_number(self.initial_extension_metres, "initial oral reach", 0.0, 0.35))
        if not all(isinstance(flag, bool) for flag in (self.motor_enabled, self.extension_available, self.contact_available)):
            raise TypeError("oral profile switches must be Boolean")
        if not isinstance(self.surfaces, tuple) or len(self.surfaces) > 8:
            raise ValueError("oral surfaces require at most eight immutable disks")
        for surface in self.surfaces:
            if not isinstance(surface, PlanarObjectV1) or not 0.0 < surface.radius <= 0.05:
                raise ValueError("oral sensing surfaces require physical disks with radius in (0, 0.05] metres")
        if len({surface.region_id for surface in self.surfaces}) != len(self.surfaces):
            raise ValueError("oral surface handles must be unique")
        if not isinstance(self.perturbations, tuple) or len(self.perturbations) > 8:
            raise ValueError("supply at most eight oral forcing intervals")
        previous = 0
        for event in self.perturbations:
            if not isinstance(event, OralWorldPerturbationV1) or event.start_tick < previous:
                raise ValueError("oral forcing must be typed, ordered and nonoverlapping")
            previous = event.stop_tick


def _oral_state(extension: float, planar: PlanarWorldStateV1, profile: OralWorldProfileV1) -> OralWorldStateV1:
    """Calculate touch from actual tip geometry, without a target or visual label."""
    radians = math.radians(planar.heading_degrees)
    tip = (planar.position[0] + extension * math.cos(radians), planar.position[1] + extension * math.sin(radians))
    contact = any(math.hypot(tip[0] - surface.position[0], tip[1] - surface.position[1]) <= surface.radius + 1e-12
                  for surface in profile.surfaces)
    return OralWorldStateV1(extension, contact)


@dataclass(frozen=True, slots=True)
class OralSealWorldStateV1:
    """Actual aggregate closure and seal for the external observer, not cognition.

    A seal is a functional geometric relation indicator, not a fluid/force
    calculation, maternal identity, latch task verdict, or nourishment signal.
    """

    closure: float = 0.0
    sealed: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "closure", _motor_number(self.closure, "physical closure", 0.0, 1.0))
        if not isinstance(self.sealed, bool):
            raise TypeError("physical seal must be Boolean")

    def as_dict(self) -> dict[str, object]:
        """Expose external physical state separately from the delivered acquisition."""
        return {"closure": self.closure, "sealed": self.sealed}


@dataclass(frozen=True, slots=True)
class OralClosurePerturbationV1:
    """Apply a fixed external closure rate over [start, stop), not per task attempt."""

    start_tick: int
    stop_tick: int
    rate_units_s: float

    def __post_init__(self) -> None:
        _motor_integer(self.start_tick, "closure perturbation start")
        _motor_integer(self.stop_tick, "closure perturbation stop")
        if self.stop_tick <= self.start_tick:
            raise ValueError("closure perturbation stop must follow start")
        object.__setattr__(self, "rate_units_s", _motor_number(self.rate_units_s, "closure forcing", -4.0, 4.0))


@dataclass(frozen=True, slots=True)
class OralSealWorldProfileV1:
    """Opt-in closure actuator and sealable disks within the existing motor plant.

    Signed drive changes closure at 2 normalized units/second. Neutral drive
    retains that coordinate, not a guaranteed seal. Generic touch AND actual
    tip membership in an independently supplied sealable disk AND closure at
    least 0.5 are required for a seal. Body/reach motion can break it without
    a release command. No visual descriptor or task identity is read here.

    This is a functional lower-provider approximation, not oral biomechanics.
    It models neither suction nor milk. A surface can be tactile yet nonsealable.
    Channel dropout changes delivered knowledge, not the underlying physics.
    """

    initial_closure: float = 0.0
    sealable_surfaces: tuple[PlanarObjectV1, ...] = ()
    motor_enabled: bool = True
    closure_available: bool = True
    seal_available: bool = True
    perturbations: tuple[OralClosurePerturbationV1, ...] = ()

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_closure", _motor_number(self.initial_closure, "initial closure", 0.0, 1.0))
        if not all(isinstance(flag, bool) for flag in (self.motor_enabled, self.closure_available, self.seal_available)):
            raise TypeError("seal profile switches must be Boolean")
        # Reuse the existing geometric surface validator, not its reach dynamics.
        OralWorldProfileV1(surfaces=self.sealable_surfaces)
        if not isinstance(self.perturbations, tuple) or len(self.perturbations) > 8:
            raise ValueError("supply at most eight closure forcing intervals")
        previous = 0
        for event in self.perturbations:
            if not isinstance(event, OralClosurePerturbationV1) or event.start_tick < previous:
                raise ValueError("closure forcing must be typed, ordered and nonoverlapping")
            previous = event.stop_tick


def _oral_seal_state(
    closure: float, planar: PlanarWorldStateV1, oral: OralWorldStateV1, profile: OralSealWorldProfileV1,
) -> OralSealWorldStateV1:
    """Compute seal from actual closure/contact/geometry, never requested success."""
    angle = math.radians(planar.heading_degrees)
    tip = (planar.position[0] + oral.extension_metres * math.cos(angle),
           planar.position[1] + oral.extension_metres * math.sin(angle))
    compatible = any(math.hypot(tip[0] - disk.position[0], tip[1] - disk.position[1]) <= disk.radius + 1e-12
                     for disk in profile.sealable_surfaces)
    return OralSealWorldStateV1(closure, closure >= 0.5 - 1e-12 and oral.contact and compatible)


_EXTRACTION_RATE_UNITS_S = 2.0
_MILK_UNITS_PER_STROKE = 1.0
_MAX_MILK_SUPPLY_UNITS = 1_000_000.0


@dataclass(frozen=True, slots=True)
class OralExtractionWorldStateV1:
    """Actual extraction and conserved transfer for external observation only.

    ``stroke`` is independent of reach and closure. Supply and accumulated
    transfer are bounded provider quantities, never privileged cognitive input.
    ``interval_milk_units`` describes only the latest completed physical step;
    it is zero at construction/reset and on a step without transfer. Reset's
    sensed facet instead reports no prior interval, not measured zero. Transfer
    means entry into the mouth, not swallowing, absorption or nourishment.
    """

    stroke: float = 0.0
    remaining_supply_units: float = 0.0
    transferred_milk_units: float = 0.0
    interval_milk_units: float = 0.0

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke", _motor_number(self.stroke, "physical extraction stroke", 0.0, 1.0))
        for name in ("remaining_supply_units", "transferred_milk_units"):
            object.__setattr__(self, name, _motor_number(getattr(self, name), name, 0.0, _MAX_MILK_SUPPLY_UNITS))
        object.__setattr__(self, "interval_milk_units",
                           _motor_number(self.interval_milk_units, "physical interval milk", 0.0, _MILK_UNITS_PER_STROKE))
        if self.interval_milk_units > self.transferred_milk_units:
            raise ValueError("interval transfer cannot exceed accumulated transfer")
        if self.remaining_supply_units + self.transferred_milk_units > _MAX_MILK_SUPPLY_UNITS:
            raise ValueError("total physical supply exceeds the provider bound")

    def as_dict(self) -> dict[str, object]:
        """Return detached observer state; reservoir/total are not sensor channels."""
        return {"stroke": self.stroke, "remaining_supply_units": self.remaining_supply_units,
                "transferred_milk_units": self.transferred_milk_units, "interval_milk_units": self.interval_milk_units}


@dataclass(frozen=True, slots=True)
class OralExtractionWorldProfileV1:
    """L-A opt-in physical extraction surrogate, not an automatic feeding routine.

    A signed motor drive advances a separate [0,1] stroke at 2 units/second.
    Positive ACTUAL displacement can draw one uncalibrated model volume unit
    per full stroke from one fixed disk's finite supply. Return, neutral and
    saturation do not transfer milk. There is no refill within a generation.
    Touch, seal and supply are distinct physical conditions; a dry seal is valid.

    Transfer needs support and closure throughout the interval, plus a conservative
    tip-path certificate inside tactile, sealable and supplying disks. Uncertain
    boundary-crossing intervals transfer zero, rather than crediting contact
    first attained at their endpoint. This may undercount at coarse resolution;
    it is not a continuous fluid model or physiological rate. The provider's
    existing step, clock, delayed/dropout sensing and reset are reused. Channel
    availability changes observations only, not the actual physical trajectory.
    No Navigation/BodyMap/SMP extraction path is installed by this profile.
    """

    initial_stroke: float = 0.0
    initial_supply_units: float = 0.0
    supplying_surface: PlanarObjectV1 | None = None
    motor_enabled: bool = True
    stroke_available: bool = True
    milk_available: bool = True

    def __post_init__(self) -> None:
        object.__setattr__(self, "initial_stroke", _motor_number(self.initial_stroke, "initial stroke", 0.0, 1.0))
        object.__setattr__(self, "initial_supply_units",
                           _motor_number(self.initial_supply_units, "initial milk supply", 0.0, _MAX_MILK_SUPPLY_UNITS))
        if not all(isinstance(flag, bool) for flag in (self.motor_enabled, self.stroke_available, self.milk_available)):
            raise TypeError("extraction profile switches must be Boolean")
        if self.supplying_surface is not None:
            # Reuse disk validation only; supplying does not imply touch or seal.
            OralWorldProfileV1(surfaces=(self.supplying_surface,))
        elif self.initial_supply_units != 0.0:
            raise ValueError("positive physical supply requires its supplying surface")


def _extraction_path_inside_disk(
    disk: PlanarObjectV1, tip: tuple[float, float], travel_bound: float,
) -> bool:
    """Certify the whole tip path inside a convex disk, not endpoint contact alone."""
    return math.hypot(tip[0] - disk.position[0], tip[1] - disk.position[1]) + travel_bound <= disk.radius + 1e-12


@dataclass(frozen=True, slots=True)
class FeedingConsequenceProfileV1:
    """Optional deterministic downstream intake/uptake competence, not cognition.

    Previous intake is processed before new interval milk is added. The assumed
    conversion is one model-volume unit to one synthetic deficit unit. These are
    not mL, calories, learned parameters or a swallow controller. Sensor controls
    affect measurement only. Fixed unavailable ticks are external test conditions,
    never task instructions. The profile supplies no fed/reward/Rest label.
    """

    initial_deficit_units: float = 0.50
    uptake_units_per_second: float = 0.50
    initial_pending_units: float = 0.0
    sensor_available: bool = True
    unavailable_ticks: tuple[int, ...] = ()

    def __post_init__(self) -> None:
        for name in ("initial_deficit_units", "uptake_units_per_second", "initial_pending_units"):
            object.__setattr__(self, name, _motor_number(getattr(self, name), name, 0.0, 8.0))
        if not isinstance(self.sensor_available, bool):
            raise TypeError("feeding-deficit sensing switch must be Boolean")
        if (not isinstance(self.unavailable_ticks, tuple) or len(self.unavailable_ticks) > 160
                or any(isinstance(t, bool) or not isinstance(t, int) or not 0 <= t <= 160 for t in self.unavailable_ticks)
                or tuple(sorted(set(self.unavailable_ticks))) != self.unavailable_ticks):
            raise ValueError("feeding-deficit dropout ticks must be distinct ordered physical ticks in [0,160]")


@dataclass(frozen=True, slots=True)
class FeedingConsequenceStateV1:
    """Actual private body state; only measured deficit may cross into cognition.

    The pending pool is observer-only. Its bound accommodates the declared finite
    supply plus initial pending material; saturation of deficit is a body equation,
    not a declaration of task success. No learning or cognitive lifetime is stored.
    """

    pending_units: float
    deficit_units: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "pending_units", _motor_number(self.pending_units, "pending intake", 0.0,
                                                               _MAX_MILK_SUPPLY_UNITS + 8.0))
        object.__setattr__(self, "deficit_units", _motor_number(self.deficit_units, "feeding deficit", 0.0, 8.0))

    def as_dict(self) -> dict[str, object]:
        """Export observer quantities without handing them back to a source owner."""
        return {"pending_units": self.pending_units, "deficit_units": self.deficit_units,
                "units": "synthetic_feeding_deficit", "observer_only": True}


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

    def __init__(
        self, stream: MotorStreamRefV1, profile: MotorWorldProfileV1 | None = None, *, planar_profile: PlanarWorldProfileV1 | None = None,
        oral_profile: OralWorldProfileV1 | None = None,
        oral_seal_profile: OralSealWorldProfileV1 | None = None,
        oral_extraction_profile: OralExtractionWorldProfileV1 | None = None,
        feeding_consequence_profile: FeedingConsequenceProfileV1 | None = None,
    ) -> None:
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        if profile is not None and not isinstance(profile, MotorWorldProfileV1):
            raise TypeError("profile must be MotorWorldProfileV1 or None")
        if planar_profile is not None and not isinstance(planar_profile, PlanarWorldProfileV1):
            raise TypeError("planar_profile must be PlanarWorldProfileV1 or None")
        if oral_profile is not None and (not isinstance(oral_profile, OralWorldProfileV1) or planar_profile is None):
            raise TypeError("oral profile requires its typed settings and the existing planar body profile")
        if oral_seal_profile is not None and (not isinstance(oral_seal_profile, OralSealWorldProfileV1) or oral_profile is None):
            raise TypeError("oral seal profile requires the typed oral and planar physical profiles")
        if oral_extraction_profile is not None and (not isinstance(oral_extraction_profile, OralExtractionWorldProfileV1)
                                                    or oral_seal_profile is None):
            raise TypeError("extraction profile requires the typed seal, oral and planar physical profiles")
        if feeding_consequence_profile is not None and (not isinstance(feeding_consequence_profile, FeedingConsequenceProfileV1)
                                                        or oral_extraction_profile is None):
            raise TypeError("downstream consequence requires its explicit typed profile and extraction provider")
        self._feeding_consequence_profile = feeding_consequence_profile
        self._feeding_consequence = (None if feeding_consequence_profile is None else FeedingConsequenceStateV1(
            feeding_consequence_profile.initial_pending_units, feeding_consequence_profile.initial_deficit_units))
        self._oral_extraction_profile = oral_extraction_profile
        self._oral_extraction = (None if oral_extraction_profile is None else
                                 OralExtractionWorldStateV1(oral_extraction_profile.initial_stroke,
                                                           oral_extraction_profile.initial_supply_units))
        self._oral_seal_profile = oral_seal_profile
        self._oral_profile = oral_profile
        self._planar_profile = planar_profile
        self._planar = (None if planar_profile is None else
                        PlanarWorldStateV1(planar_profile.initial_position, planar_profile.initial_heading,
                                           _swept_planar_step(planar_profile.initial_position, (0.0, 0.0), planar_profile.objects)[1]))
        self._oral = (None if oral_profile is None or self._planar is None else
                      _oral_state(oral_profile.initial_extension_metres, self._planar, oral_profile))
        self._oral_seal = (None if oral_seal_profile is None or self._planar is None or self._oral is None else
                           _oral_seal_state(oral_seal_profile.initial_closure, self._planar, self._oral, oral_seal_profile))
        self._stream = stream
        self._profile = profile if profile is not None else MotorWorldProfileV1()
        self._body = self._profile.initial_body
        self._tick = 0
        self._last_command_id = 0
        self._pending: tuple[MotorFeedbackV1, ...] = ()
        self._latest_feedback = self._measure(self._body, 0.0, self._profile.surface_present,
                                             event_tick=0, delay=0, planar=self._planar, oral=self._oral, oral_seal=self._oral_seal,
                                             oral_extraction=self._oral_extraction, feeding_consequence=self._feeding_consequence)

    @property
    def feeding_consequence_body(self) -> FeedingConsequenceStateV1 | None:
        """Read private physical intake/deficit for observers, never cognitive decisions."""
        return self._feeding_consequence

    @property
    def oral_extraction_body(self) -> OralExtractionWorldStateV1 | None:
        """Inspect physical stroke/supply externally; consumers use delivered sensing."""
        return self._oral_extraction

    @property
    def oral_seal_body(self) -> OralSealWorldStateV1 | None:
        """Inspect physical closure/seal externally; cognition must use delivered feedback."""
        return self._oral_seal

    @property
    def oral_body(self) -> OralWorldStateV1 | None:
        """Read actual oral state for the external observer, never as cognitive input."""
        return self._oral

    @property
    def planar_body(self) -> PlanarWorldStateV1 | None:
        """Read actual horizontal state for external evaluation; cognition must not use it."""
        return self._planar

    def visual_surface(self, *, feedback: MotorFeedbackV1 | None = None) -> dict[str, object] | None:
        """Expose a fixed-scene sensory scaffold at the latest DELIVERED acquisition.

        Object locations are fixed for this slice. SELF comes from that same old
        sensor sample, never from the newer private body. Reading this surface
        neither advances nor resamples anything. The outer adapter supplies the
        matching original event/availability header and positive whitelist.
        Optional feedback supplies a previously delivered canonical acquisition
        for historical comparison. This does not change the provider's current
        sample or resample the body; it is valid only for this fixed-scene scaffold.
        """
        # The optional original sample supports delayed-claim routing, not new sensing.
        # Scene objects are fixed under this provider, so only the measured SELF basis varies.
        basis = self._latest_feedback if feedback is None else feedback
        if not isinstance(basis, MotorFeedbackV1):
            raise TypeError("visual surface requires a canonical original motor acquisition")
        basis.validate_available(stream=self._stream, at_tick=self._tick)
        if basis.sample_id > self._latest_feedback.sample_id or basis.event_tick > self._latest_feedback.event_tick:
            raise ValueError("visual surface cannot use an acquisition beyond the delivered boundary")
        profile, sensed = self._planar_profile, basis.planar
        if profile is None or sensed is None or not profile.vision_available:
            return None
        anchor: dict[str, object] = {"entity": "self"}
        if sensed.position is not None:
            anchor.update(x=sensed.position[0], y=sensed.position[1])
        # Visibility uses the ORIGINAL delivered body position, never newer private
        # coordinates or task progress. Missing position cannot reveal ranged detail.
        visible = tuple(item for item in profile.objects if not isinstance(item, PlanarDetailObjectV1) or
                        sensed.position is not None and math.hypot(item.position[0] - sensed.position[0],
                                                                  item.position[1] - sensed.position[1]) <= item.visibility_radius + 1e-12)
        return {"schema": "surface_grid_v1", "frame": profile.frame_id, "anchor": anchor,
                "objects": [{"entity": item.region_id, "kind": item.descriptor if isinstance(item, PlanarDetailObjectV1) else "object",
                             "x": item.position[0], "y": item.position[1]}
                            for item in visible], "landmarks": []}

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
        fresh = MotorWorldV1(MotorStreamRefV1(self._stream.stream_id, self._stream.generation + 1), self._profile,
                             planar_profile=self._planar_profile, oral_profile=self._oral_profile, oral_seal_profile=self._oral_seal_profile,
                             oral_extraction_profile=self._oral_extraction_profile,
                             feeding_consequence_profile=self._feeding_consequence_profile)
        self._stream = fresh.stream
        self._body = fresh.body
        self._planar = fresh.planar_body
        self._oral = fresh.oral_body
        self._oral_seal = fresh.oral_seal_body
        self._oral_extraction = fresh.oral_extraction_body
        self._feeding_consequence = fresh.feeding_consequence_body
        self._tick = 0
        self._last_command_id = 0
        self._pending = ()
        self._latest_feedback = fresh.observe()
        return self._latest_feedback

    def _measure(
        self, body: MotorBodyStateV1, angular_rate: float, surface_present: bool, *, event_tick: int, delay: int,
        planar: PlanarWorldStateV1 | None = None, oral: OralWorldStateV1 | None = None,
        oral_seal: OralSealWorldStateV1 | None = None,
        oral_extraction: OralExtractionWorldStateV1 | None = None,
        feeding_consequence: FeedingConsequenceStateV1 | None = None,
    ) -> MotorFeedbackV1:
        """Sense actual geometry; omit declared channels without repairing them.

        Destabilization follows the declared engineering readout using the
        pre-saturation angular rate, including external forcing. It is not a
        measured joint velocity, prediction error or task-completion flag.
        """
        contact, loading = _motor_support(body, self._profile, surface_present)
        instability = _clamp(abs(math.sin(math.radians(body.body_tilt_degrees))) * (1.0 - loading) + abs(angular_rate) / 180.0)
        missing = self._profile.unavailable_channels
        planar_feedback = None
        horizontal = self._planar_profile
        if planar is not None and horizontal is not None:
            planar_feedback = PlanarFeedbackV1(
                horizontal.frame_id, planar.position if horizontal.position_available else None,
                planar.heading_degrees if horizontal.heading_available else None,
                planar.obstacle_contact if horizontal.contact_available else None,
            )
        oral_feedback = None
        if oral is not None and self._oral_profile is not None:
            oral_feedback = OralFeedbackV1(oral.extension_metres if self._oral_profile.extension_available else None,
                                          oral.contact if self._oral_profile.contact_available else None)
        seal_feedback = None
        if oral_seal is not None and self._oral_seal_profile is not None:
            seal_feedback = OralSealFeedbackV1(oral_seal.closure if self._oral_seal_profile.closure_available else None,
                                               oral_seal.sealed if self._oral_seal_profile.seal_available else None)
        extraction_feedback = None
        extraction_profile = self._oral_extraction_profile
        if oral_extraction is not None and extraction_profile is not None:
            extraction_feedback = OralExtractionFeedbackV1(
                oral_extraction.stroke if extraction_profile.stroke_available else None,
                oral_extraction.interval_milk_units if event_tick > 0 and extraction_profile.milk_available else None,
                event_tick - 1 if event_tick > 0 else None,
            )
        deficit_feedback = None
        consequence_profile = self._feeding_consequence_profile
        if feeding_consequence is not None and consequence_profile is not None:
            visible = consequence_profile.sensor_available and event_tick not in consequence_profile.unavailable_ticks
            deficit_feedback = FeedingDeficitFeedbackV1(feeding_consequence.deficit_units if visible else None)
        return MotorFeedbackV1(
            feeding_deficit=deficit_feedback,
            planar=planar_feedback, oral=oral_feedback, oral_seal=seal_feedback, oral_extraction=extraction_feedback,
            stream=self._stream, sample_id=event_tick + 1, event_tick=event_tick, available_tick=event_tick + delay,
            body_tilt_degrees=None if "body_tilt_degrees" in missing else body.body_tilt_degrees,
            support_extension=None if "support_extension" in missing else body.support_extension,
            support_contact=None if "support_contact" in missing else contact,
            useful_loading=None if "useful_loading" in missing else loading,
            destabilization=None if "destabilization" in missing else instability,
        )

    def _advance_planar(self, command: MotorCommandV1 | None, surface_present: bool) -> PlanarWorldStateV1 | None:
        """Integrate actual bounded velocity/yaw without reading a cognitive target."""
        profile, body = self._planar_profile, self._planar
        if profile is None or body is None:
            return None
        drive = None if command is None else command.translation
        contact, load = _motor_support(self._body, self._profile, surface_present)
        forward, left = 0.0, 0.0
        if drive is not None and profile.motor_enabled and contact and load >= 0.75 and abs(self._body.body_tilt_degrees) <= 12.0:
            forward, left = drive.forward, drive.left
        cosine, sine = math.cos(math.radians(body.heading_degrees)), math.sin(math.radians(body.heading_degrees))
        vx, vy = cosine * forward - sine * left, sine * forward + cosine * left
        heading_rate = 0.0
        for event in profile.perturbations:
            if event.start_tick <= self._tick < event.stop_tick:
                vx, vy = vx + event.velocity[0], vy + event.velocity[1]
                heading_rate = event.heading_rate
                break
        interval = self._profile.dt_seconds
        position, obstacle_contact = _swept_planar_step(body.position, (vx * interval, vy * interval), profile.objects)
        heading = ((body.heading_degrees + heading_rate * interval + 180.0) % 360.0) - 180.0
        return PlanarWorldStateV1(position, heading, obstacle_contact)

    def _advance_oral(
        self, command: MotorCommandV1 | None, planar: PlanarWorldStateV1 | None, surface_present: bool,
    ) -> OralWorldStateV1 | None:
        """Integrate the sole reach motor and recompute independent physical touch.

        No task, requested endpoint, part identity, visual category or success
        counter is available here. Whole-body motion can move the tip even when
        its own reach drive is zero; cancelling a target is not freezing physics.
        """
        profile, state = self._oral_profile, self._oral
        if profile is None or state is None or planar is None:
            return None
        contact, load = _motor_support(self._body, self._profile, surface_present)
        drive = 0.0
        if (command is not None and command.oral_drive is not None and profile.motor_enabled
                and contact and load >= 0.75 and abs(self._body.body_tilt_degrees) <= 12.0):
            drive = command.oral_drive
        forcing = next((event.rate_metres_s for event in profile.perturbations
                        if event.start_tick <= self._tick < event.stop_tick), 0.0)
        extension = max(0.0, min(0.35, state.extension_metres + self._profile.dt_seconds * (0.5 * drive + forcing)))
        return _oral_state(extension, planar, profile)

    def _advance_oral_seal(
        self, command: MotorCommandV1 | None, planar: PlanarWorldStateV1 | None,
        oral: OralWorldStateV1 | None, surface_present: bool,
    ) -> OralSealWorldStateV1 | None:
        """Integrate independent closure and derive seal from the evolved geometry.

        A closing command may close in empty space; it still cannot make a seal.
        Actuation needs the same supported posture as the existing oral motor.
        Forcing is external and acts even with no command or disabled motor.
        """
        profile, state = self._oral_seal_profile, self._oral_seal
        if profile is None or state is None or planar is None or oral is None:
            return None
        contact, load = _motor_support(self._body, self._profile, surface_present)
        drive = 0.0
        if (command is not None and command.oral_closure_drive is not None and profile.motor_enabled
                and contact and load >= 0.75 and abs(self._body.body_tilt_degrees) <= 12.0):
            drive = command.oral_closure_drive
        forcing = next((event.rate_units_s for event in profile.perturbations
                        if event.start_tick <= self._tick < event.stop_tick), 0.0)
        closure = _clamp(state.closure + self._profile.dt_seconds * (2.0 * drive + forcing))
        return _oral_seal_state(closure, planar, oral, profile)

    def _advance_oral_extraction(
        self, command: MotorCommandV1 | None, *, body: MotorBodyStateV1, planar: PlanarWorldStateV1 | None,
        oral: OralWorldStateV1 | None, seal: OralSealWorldStateV1 | None, surface_present: bool,
    ) -> OralExtractionWorldStateV1 | None:
        """Compute stroke and transfer locally before the step's atomic replacement.

        Drive affects only extraction; the existing body/reach/closure equations
        are untouched. At start-of-step the old oral motor competence gates motion.
        Transfer additionally requires supported posture and closure throughout.
        Linear/clipped body displacement and reach plus bounded yaw give a safe
        upper bound on tip travel, including interior curved excursions. A disk
        containing that whole bound certifies contact without sampling a future
        endpoint as though it existed for the entire interval. This deliberately
        conservative geometry can withhold transfer on an uncertain interval.
        """
        profile, state = self._oral_extraction_profile, self._oral_extraction
        if profile is None or state is None:
            return None
        previous_planar, previous_oral, previous_seal = self._planar, self._oral, self._oral_seal
        oral_profile, seal_profile = self._oral_profile, self._oral_seal_profile
        if (planar is None or oral is None or seal is None or previous_planar is None or previous_oral is None
                or previous_seal is None or oral_profile is None or seal_profile is None):
            raise RuntimeError("extraction requires its complete physical context")
        contact, loading = _motor_support(self._body, self._profile, surface_present)
        drive = 0.0
        if (command is not None and command.oral_extraction_drive is not None and profile.motor_enabled
                and contact and loading >= 0.75 and abs(self._body.body_tilt_degrees) <= 12.0):
            drive = command.oral_extraction_drive
        stroke = _clamp(state.stroke + self._profile.dt_seconds * _EXTRACTION_RATE_UNITS_S * drive)
        displacement = max(0.0, stroke - state.stroke)
        transfer = 0.0
        conservative_body = MotorBodyStateV1(max(abs(body.body_tilt_degrees), abs(self._body.body_tilt_degrees)),
                                             min(body.support_extension, self._body.support_extension))
        _, minimum_load = _motor_support(conservative_body, self._profile, surface_present)
        supplier = profile.supplying_surface
        if (displacement > 0.0 and supplier is not None and minimum_load >= 0.75
                and conservative_body.body_tilt_degrees <= 12.0 and min(seal.closure, previous_seal.closure) >= 0.5 - 1e-12):
            angle = math.radians(previous_planar.heading_degrees)
            tip = (previous_planar.position[0] + previous_oral.extension_metres * math.cos(angle),
                   previous_planar.position[1] + previous_oral.extension_metres * math.sin(angle))
            yaw = abs((planar.heading_degrees - previous_planar.heading_degrees + 180.0) % 360.0 - 180.0)
            travel = (math.hypot(planar.position[0] - previous_planar.position[0], planar.position[1] - previous_planar.position[1])
                      + abs(oral.extension_metres - previous_oral.extension_metres)
                      + max(oral.extension_metres, previous_oral.extension_metres) * math.radians(yaw))
            if (_extraction_path_inside_disk(supplier, tip, travel)
                    and any(_extraction_path_inside_disk(disk, tip, travel) for disk in oral_profile.surfaces)
                    and any(_extraction_path_inside_disk(disk, tip, travel) for disk in seal_profile.sealable_surfaces)):
                transfer = min(state.remaining_supply_units, displacement * _MILK_UNITS_PER_STROKE)
        # Derive inventory from ONE accumulated total, rather than independently
        # subtracting tiny transfers from a large reservoir and adding them to
        # another accumulator. The latter can manufacture round-off stock.
        total = min(profile.initial_supply_units, state.transferred_milk_units + transfer)
        return OralExtractionWorldStateV1(stroke, profile.initial_supply_units - total, total, transfer)

    def _advance_feeding_consequence(self, extraction: OralExtractionWorldStateV1 | None) -> FeedingConsequenceStateV1 | None:
        """Compute delayed processing from previous intake and actual new transfer.

        No observer total, task, prediction, selection or success flag participates.
        This is computed within the existing atomic physical step. Neutral motor
        evolution still processes old intake; measurement availability does not
        change the body. Unsupported provider combinations fail before commit.
        """
        state, profile = self._feeding_consequence, self._feeding_consequence_profile
        if state is None or profile is None:
            return None
        if extraction is None:
            raise RuntimeError("feeding consequence lost its declared physical intake source")
        uptake = min(state.pending_units, profile.uptake_units_per_second * self._profile.dt_seconds)
        return FeedingConsequenceStateV1(state.pending_units - uptake + extraction.interval_milk_units,
                                         max(0.0, state.deficit_units - uptake))

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
        if command is not None and command.translation is not None and self._planar_profile is None:
            raise ValueError("translation requires the explicit planar physical profile")
        if command is not None and command.oral_drive is not None and self._oral_profile is None:
            raise ValueError("oral drive requires the explicit oral physical profile")
        if command is not None and command.oral_closure_drive is not None and self._oral_seal_profile is None:
            raise ValueError("closure drive requires the explicit oral seal physical profile")
        if command is not None and command.oral_extraction_drive is not None and self._oral_extraction_profile is None:
            raise ValueError("extraction drive requires the explicit extraction physical profile")
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
        next_planar = self._advance_planar(command, surface_present)
        next_oral = self._advance_oral(command, next_planar, surface_present)
        next_seal = self._advance_oral_seal(command, next_planar, next_oral, surface_present)
        next_extraction = self._advance_oral_extraction(
            command, body=next_body, planar=next_planar, oral=next_oral, seal=next_seal, surface_present=surface_present,
        )
        next_consequence = self._advance_feeding_consequence(next_extraction)
        next_tick = self._tick + 1
        pending = self._pending
        if not dropout:
            measurement = self._measure(next_body, angular_rate, surface_present,
                                        event_tick=next_tick, delay=self._profile.sensor_delay_ticks, planar=next_planar, oral=next_oral,
                                        oral_seal=next_seal, oral_extraction=next_extraction, feeding_consequence=next_consequence)
            pending += (measurement,)
        delivered = tuple(item for item in pending if item.available_tick <= next_tick)
        future = tuple(item for item in pending if item.available_tick > next_tick)
        if len(future) > _MOTOR_PENDING_LIMIT:
            raise OverflowError("motor feedback staging capacity exceeded")
        # All remaining work is replacement of already computed local values.
        if command is not None:
            self._last_command_id = command.command_id
        self._body = next_body
        self._planar = next_planar
        self._oral = next_oral
        self._oral_seal = next_seal
        self._oral_extraction = next_extraction
        self._feeding_consequence = next_consequence
        self._tick = next_tick
        self._pending = future
        if delivered:
            self._latest_feedback = delivered[-1]
        return delivered
