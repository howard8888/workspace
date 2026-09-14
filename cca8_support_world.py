#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Bounded world-side support dynamics for Planning v16 P16-1E-B.

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
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math

__version__ = "0.1.0"
__all__ = [
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
