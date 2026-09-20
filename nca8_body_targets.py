#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Body-dependent target calculation and bounded reservations for P18-H3.

A supplied task requirement states a desired planar orientation and/or aggregate
extension. BodyMap subtracts its current measured body coordinate, limits the
requested change to the declared capability, and binds the resulting H1 target
to that capability. A 1e-12 absolute comparison allowance absorbs subtraction
roundoff at capability endpoints; it is not a task tolerance or sensor repair.
The requirement is not selected here. No world, motor
command, SMP executor, WNM, PNM or learning system is called by this module.

``BodyTargetMapperV1`` is the small local helper owned by ``Nca8BodyRuntimeV1``
when explicitly configured. It keeps one immutable sensor acquisition, one
pending proposal and at most two body-side target reservations. These are not
another cortical source or a generic task scheduler. Reservations prevent
conflicting requests and test cancellation/refinement/expiry before H4 adds
actual execution. They do not install a motor controller or replace the later
accepted-handoff check. All time is supplied by the caller; no clock runs here.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1,
    CommittedBodyTargetV1,
    SensorimotorTargetKindV1,
    TargetOriginV1,
)

__version__ = "0.1.0"
__all__ = [
    "BodyAxisCapabilityV1",
    "BodyMovementRequestV1",
    "BodyTargetBindingV1",
    "BodyTargetMapperV1",
    "BodyTargetProposalV1",
    "BodyTargetReservationV1",
    "nominal_body_capabilities_v1",
    "__version__",
]

_MAX_INDEX = 2**63 - 1
_EPSILON = 1e-12


def _index(value: object, label: str, minimum: int = 0, maximum: int = _MAX_INDEX) -> int:
    """Validate a finite logical index or budget; bool is not a numeric index."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if not minimum <= value <= maximum:
        raise ValueError(f"{label} must be in [{minimum}, {maximum}]")
    return value


def _scalar(value: object, label: str, lower: float, upper: float) -> float:
    """Return a finite measured/requested scalar without coercing strings or bools."""
    if isinstance(value, bool) or not isinstance(value, (float, int)):
        raise TypeError(f"{label} must be numeric, not Boolean or text")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{label} cannot be represented as a finite float") from exc
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError(f"{label} must be finite and in [{lower}, {upper}]")
    return result


def _name(value: object, label: str) -> str:
    """Validate a bounded reference used by this helper, not a registry key."""
    if not isinstance(value, str):
        raise TypeError(f"{label} must be text")
    text = value.strip()
    if not text or len(text) > 120 or any(ord(char) < 32 for char in text):
        raise ValueError(f"{label} must contain 1-120 printable single-line characters")
    return text


def _axis_limits(kind: SensorimotorTargetKindV1) -> tuple[float, float, float]:
    """Return H1 coordinate/rate limits, without reading physical provider state."""
    if not isinstance(kind, SensorimotorTargetKindV1):
        raise TypeError("kind must be SensorimotorTargetKindV1")
    if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
        return -90.0, 90.0, 90.0
    return 0.0, 1.0, 1.0


@dataclass(frozen=True, slots=True)
class BodyAxisCapabilityV1:
    """One explicitly supplied movement capability and its fixed calibration.

    The H3 harness declares these values. Presence means that the caller offers
    this target family, not that an H4 executor is already installed. Omitting a
    family makes it unavailable. ``maximum_step`` limits a new target's offset;
    ``maximum_excursion`` is the separate bound on subsequent pursuit. Both are
    in the family's coordinate units. ``maximum_rate`` uses simulation seconds.
    Capability calibration is fixed, not a learned or sensed success result.
    """

    kind: SensorimotorTargetKindV1
    capability_id: str
    minimum_coordinate: float
    maximum_coordinate: float
    maximum_step: float
    maximum_excursion: float
    maximum_rate: float
    tolerance: float

    def __post_init__(self) -> None:
        lower, upper, rate = _axis_limits(self.kind)
        object.__setattr__(self, "capability_id", _name(self.capability_id, "capability_id"))
        for field in ("minimum_coordinate", "maximum_coordinate"):
            object.__setattr__(self, field, _scalar(getattr(self, field), field, lower, upper))
        if self.minimum_coordinate >= self.maximum_coordinate:
            raise ValueError("capability coordinate interval must have positive width")
        for field in ("maximum_step", "maximum_excursion", "tolerance"):
            object.__setattr__(self, field, _scalar(getattr(self, field), field, 0.0, upper - lower))
        object.__setattr__(self, "maximum_rate", _scalar(self.maximum_rate, "maximum_rate", 0.0, rate))
        if not 0.0 < self.tolerance <= self.maximum_step <= self.maximum_excursion:
            raise ValueError("require 0 < tolerance <= maximum_step <= maximum_excursion")
        if self.tolerance > self.maximum_coordinate - self.minimum_coordinate:
            raise ValueError("tolerance exceeds the capability coordinate interval")
        if self.maximum_rate <= 0.0:
            raise ValueError("capability maximum_rate must be positive")

    def as_dict(self) -> dict[str, object]:
        """Describe a supplied capability without creating an executor."""
        return {
            "kind": self.kind.value,
            "capability_id": self.capability_id,
            "minimum_coordinate": self.minimum_coordinate,
            "maximum_coordinate": self.maximum_coordinate,
            "maximum_step": self.maximum_step,
            "maximum_excursion": self.maximum_excursion,
            "maximum_rate": self.maximum_rate,
            "tolerance": self.tolerance,
        }


def nominal_body_capabilities_v1() -> tuple[BodyAxisCapabilityV1, ...]:
    """Return the two declared H1/H3 fixture capabilities, without installing them.

    These values retain the H1 design: orientation step 12 degrees, excursion
    18 degrees, rate 60 degrees/s and tolerance 1 degree; extension step 0.20,
    excursion 0.25, rate 1 unit/s and tolerance 0.01. Callers may supply narrower
    capabilities or omit one. This is not an inventory of inherited goat muscles.
    """
    return (
        BodyAxisCapabilityV1(
            SensorimotorTargetKindV1.ORIENTATION_ADJUST, "smp:orientation_adjust:v1", -90.0, 90.0, 12.0, 18.0, 60.0, 1.0,
        ),
        BodyAxisCapabilityV1(
            SensorimotorTargetKindV1.SUPPORT_EXTENSION, "smp:support_extension:v1", 0.0, 1.0, 0.20, 0.25, 1.0, 0.01,
        ),
    )


@dataclass(frozen=True, slots=True)
class BodyMovementRequestV1:
    """A supplied task contribution in the declared gravity/surface frame.

    ``desired_tilt_degrees`` is an absolute signed orientation relative to the
    H1 gravity reference, not a motor drive or a standing predicate. Extension
    is the declared aggregate actuator coordinate, never desired useful loading.
    None omits that axis. H3 calculates bounded intermediate targets toward these
    supplied coordinates; it neither chooses their task nor constructs a route.
    The original request remains visible when a capability narrows the result.
    """

    origin: TargetOriginV1
    desired_tilt_degrees: float | None = None
    desired_extension: float | None = None
    lease_ticks: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.origin, TargetOriginV1):
            raise TypeError("origin must be TargetOriginV1")
        if self.desired_tilt_degrees is None and self.desired_extension is None:
            raise ValueError("a movement request must name at least one coordinate")
        if self.desired_tilt_degrees is not None:
            object.__setattr__(self, "desired_tilt_degrees", _scalar(self.desired_tilt_degrees, "desired tilt", -90.0, 90.0))
        if self.desired_extension is not None:
            object.__setattr__(self, "desired_extension", _scalar(self.desired_extension, "desired extension", 0.0, 1.0))
        _index(self.lease_ticks, "lease_ticks", 1, 8)

    def as_dict(self) -> dict[str, object]:
        """Keep task requirements distinguishable from the resulting body targets."""
        return {
            "origin": self.origin.as_dict(),
            "desired_tilt_degrees": self.desired_tilt_degrees,
            "desired_extension": self.desired_extension,
            "lease_ticks": self.lease_ticks,
        }


@dataclass(frozen=True, slots=True)
class BodyTargetBindingV1:
    """One proposed H1 target associated with one available family capability."""

    target: BodyRelativeTargetV1
    capability: BodyAxisCapabilityV1

    def __post_init__(self) -> None:
        if not isinstance(self.target, BodyRelativeTargetV1) or not isinstance(self.capability, BodyAxisCapabilityV1):
            raise TypeError("a binding requires a body target and an axis capability")
        if self.target.kind is not self.capability.kind:
            raise ValueError("target family does not match capability")
        if not self.capability.minimum_coordinate - _EPSILON <= self.target.endpoint <= self.capability.maximum_coordinate + _EPSILON:
            raise ValueError("target endpoint exceeds capability coordinate range")
        if self.target.max_rate > self.capability.maximum_rate or self.target.max_displacement > self.capability.maximum_excursion:
            raise ValueError("target pursuit bounds exceed capability")

    def as_dict(self) -> dict[str, object]:
        """Export the binding; this does not start the named sensorimotor primitive."""
        return {"target": self.target.as_dict(), "capability": self.capability.as_dict()}


@dataclass(frozen=True, slots=True)
class BodyTargetProposalV1:
    """A bounded proposal with separate accepted axes and explicit refusal reasons.

    Only the mapper's most recent original proposal may be reserved. Constructing
    an equivalent record, decoding its diagnostic dictionary or retaining an old
    proposal cannot authorize a body request. Creating a proposal does not occupy
    any resource. It also does not replace an already reserved target.
    """

    request: BodyMovementRequestV1
    created_tick: int
    bindings: tuple[BodyTargetBindingV1, ...]
    withheld: tuple[tuple[SensorimotorTargetKindV1, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, BodyMovementRequestV1):
            raise TypeError("proposal requires BodyMovementRequestV1")
        _index(self.created_tick, "created_tick")
        if not isinstance(self.bindings, tuple) or not isinstance(self.withheld, tuple):
            raise TypeError("proposal entries must be immutable tuples")
        kinds: list[SensorimotorTargetKindV1] = []
        for binding in self.bindings:
            if not isinstance(binding, BodyTargetBindingV1) or binding.target.origin != self.request.origin:
                raise ValueError("proposal binding belongs to a different origin or is invalid")
            kinds.append(binding.target.kind)
        for item in self.withheld:
            if not isinstance(item, tuple) or len(item) != 2:
                raise TypeError("withheld entry must contain family and reason")
            kind, reason = item
            _axis_limits(kind)
            _name(reason, "withheld reason")
            kinds.append(kind)
        expected = set()
        if self.request.desired_tilt_degrees is not None:
            expected.add(SensorimotorTargetKindV1.ORIENTATION_ADJUST)
        if self.request.desired_extension is not None:
            expected.add(SensorimotorTargetKindV1.SUPPORT_EXTENSION)
        if len(kinds) != len(set(kinds)) or set(kinds) != expected:
            raise ValueError("each requested axis needs exactly one binding or refusal")

    def as_dict(self) -> dict[str, object]:
        """Return detached diagnostics; no motor permission accompanies the export."""
        return {
            "request": self.request.as_dict(), "created_tick": self.created_tick,
            "bindings": [binding.as_dict() for binding in self.bindings],
            "withheld": [{"kind": kind.value, "reason": reason} for kind, reason in self.withheld],
            "status": "proposed", "motor_execution": False,
        }


@dataclass(frozen=True, slots=True)
class BodyTargetReservationV1:
    """BodyMap's immutable resource reservation, not an installed motor execution.

    ``initial`` retains the original bounds and lease. ``current`` can describe
    a strictly bounded local refinement. Its committed tick continues to name
    the original lease origin, while ``updated_tick`` names the latest reservation
    change (revision, cancellation or expiry). For a live reservation it is the
    revision event. Never backdate a later revision to the lease origin.
    Local refinement cannot move beyond the original endpoint tolerance band,
    enlarge any bound, or extend expiry. Cancelled/expired copies remain merely
    historical descriptions and cannot be restored through diagnostic replay.
    """

    initial: CommittedBodyTargetV1
    current: CommittedBodyTargetV1
    capability: BodyAxisCapabilityV1
    updated_tick: int
    status: str = "reserved"

    def __post_init__(self) -> None:
        if not isinstance(self.initial, CommittedBodyTargetV1) or not isinstance(self.current, CommittedBodyTargetV1):
            raise TypeError("reservation requires committed-target descriptions")
        BodyTargetBindingV1(self.initial.target, self.capability)
        BodyTargetBindingV1(self.current.target, self.capability)
        _index(self.updated_tick, "updated_tick", self.initial.committed_tick)
        if self.status not in {"reserved", "cancelled", "expired"}:
            raise ValueError("unknown body reservation status")
        before, after = self.initial.target, self.current.target
        if (before.origin, before.target_id, before.kind, before.basis) != (after.origin, after.target_id, after.kind, after.basis):
            raise ValueError("reservation refinement changed its origin, identity, family or body basis")
        if (self.initial.execution_id, self.initial.committed_tick) != (self.current.execution_id, self.current.committed_tick):
            raise ValueError("refinement changed execution or lease origin")
        if after.revision < before.revision or after.lease_ticks != before.lease_ticks:
            raise ValueError("refinement reversed revision or changed the lease")
        if after.revision == before.revision and after != before:
            raise ValueError("changed target content requires a new revision")
        if after.revision - before.revision > self.updated_tick - self.initial.committed_tick:
            raise ValueError("target revisions require distinct later local ticks")
        if (after.max_rate, after.max_displacement, after.tolerance, after.max_corrections) != (
            before.max_rate, before.max_displacement, before.tolerance, before.max_corrections,
        ):
            raise ValueError("refinement changed the original pursuit bounds")
        if abs(after.endpoint - before.endpoint) > before.tolerance + _EPSILON:
            raise ValueError("refinement exceeds original endpoint tolerance band")
        if self.status == "reserved" and self.updated_tick >= self.initial.expires_at_tick:
            raise ValueError("a reserved revision cannot start at or after expiry")
        if self.status == "expired" and self.updated_tick < self.initial.expires_at_tick:
            raise ValueError("reservation has not yet expired")

    def as_dict(self) -> dict[str, object]:
        """Describe reservation, original permission and revision time without actuating."""
        return {
            "initial": self.initial.as_dict(), "current": self.current.as_dict(),
            "capability": self.capability.as_dict(), "updated_tick": self.updated_tick,
            "status": self.status, "motor_executor_installed": False,
        }


class BodyTargetMapperV1:
    """Own one local body view and at most two nonexecuting target reservations.

    Callers supply an explicit body stream, capabilities and logical ticks.
    Sensor input is already the canonical immutable H1 record, not a simulator
    object. Missing data never becomes zero; identical rereads retain their old
    event time. The default maximum age is two local ticks from acquisition,
    not two ticks since this helper last read the sample.

    Orientation mapping requires known contact and positive measured loading.
    Extension can be attempted without known contact because establishing
    contact is different from already having it. This is a disclosed H3 mapping
    precondition, not a stability theorem. H4 must check ongoing permission and
    protection before issuing each motor command. H3 itself issues none.
    """

    def __init__(
        self, stream: MotorStreamRefV1, capabilities: tuple[BodyAxisCapabilityV1, ...], *,
        tick_seconds: float = 0.05, maximum_feedback_age: int = 2, enabled: bool = True,
    ) -> None:
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        if not isinstance(capabilities, tuple) or len(capabilities) > 2:
            raise ValueError("supply an immutable tuple of at most two axis capabilities")
        axes: dict[SensorimotorTargetKindV1, BodyAxisCapabilityV1] = {}
        names: set[str] = set()
        for capability in capabilities:
            if not isinstance(capability, BodyAxisCapabilityV1):
                raise TypeError("capability must be BodyAxisCapabilityV1")
            if capability.kind in axes or capability.capability_id in names:
                raise ValueError("duplicate capability family or identity")
            axes[capability.kind] = capability
            names.add(capability.capability_id)
        interval = _scalar(tick_seconds, "tick_seconds", 0.0, 0.05)
        if interval == 0.0:
            raise ValueError("tick_seconds must be positive")
        _index(maximum_feedback_age, "maximum_feedback_age", 0, 2)
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be Boolean")
        self._stream = stream
        self._capabilities = axes
        self._tick_seconds = interval
        self._maximum_feedback_age = maximum_feedback_age
        self._enabled = enabled
        self._feedback: MotorFeedbackV1 | None = None
        self._feedback_available = False
        self._last_tick = 0
        self._proposal_number = 0
        self._pending: BodyTargetProposalV1 | None = None
        self._reservations: dict[SensorimotorTargetKindV1, BodyTargetReservationV1] = {}

    @property
    def stream(self) -> MotorStreamRefV1:
        """Return the fixed body stream; resetting requires a fresh helper/generation."""
        return self._stream

    @property
    def capabilities(self) -> tuple[BodyAxisCapabilityV1, ...]:
        """Return the fixed capability declarations in canonical family order."""
        return tuple(self._capabilities[kind] for kind in SensorimotorTargetKindV1 if kind in self._capabilities)

    def _check_tick(self, at_tick: int) -> int:
        """Reject time reversal without advancing an external or internal clock."""
        return _index(at_tick, "at_tick", self._last_tick)

    def update_feedback(self, feedback: MotorFeedbackV1 | None, *, at_tick: int) -> str:
        """Admit a sensor reading without updating cortical maps or old targets.

        A duplicate is a reread, not a new event. A strictly older identity/time
        is ignored without overwriting newer current content. Inconsistent reuse
        or ordering raises before mutation. Explicit None makes the local view
        unavailable while retaining only the last record for ordering/diagnostics.
        Malformed/wrong-stream/future input raises before mutation; a caller must
        not catch such a fault and continue issuing commands as though it passed.
        """
        tick = self._check_tick(at_tick)
        if feedback is None:
            self._feedback_available = False
            self._pending = None
            self._last_tick = tick
            return "unavailable"
        if not isinstance(feedback, MotorFeedbackV1):
            raise TypeError("feedback must be MotorFeedbackV1 or None")
        feedback.validate_available(stream=self._stream, at_tick=tick)
        previous = self._feedback
        result = "accepted"
        if previous is not None:
            if feedback.sample_id == previous.sample_id:
                if feedback != previous:
                    raise ValueError("one sensor identity cannot have changed content or time")
                result = "reread"
            elif feedback.sample_id < previous.sample_id and feedback.event_tick < previous.event_tick:
                self._last_tick = tick
                return "older_ignored"
            elif feedback.sample_id <= previous.sample_id or feedback.event_tick <= previous.event_tick:
                raise ValueError("sensor identity and physical event order disagree")
        if feedback != previous or not self._feedback_available:
            self._pending = None
        self._feedback = feedback
        self._feedback_available = True
        self._last_tick = tick
        return result

    def _current_feedback(self, tick: int) -> MotorFeedbackV1 | None:
        """Read only genuinely available, sufficiently recent body evidence."""
        feedback = self._feedback
        if not self._feedback_available or feedback is None:
            return None
        if tick - feedback.event_tick > self._maximum_feedback_age:
            return None
        return feedback

    def body_view(self, *, at_tick: int) -> dict[str, object]:
        """Export currentness and the original reading; this never refreshes its age."""
        tick = self._check_tick(at_tick)
        current = self._current_feedback(tick)
        status = "current" if current is not None else "unavailable"
        if self._feedback_available and self._feedback is not None and current is None:
            status = "stale"
        return {
            "stream": self._stream.as_dict(), "checked_tick": tick, "status": status,
            "feedback": self._feedback.as_dict() if self._feedback is not None else None,
            "age_ticks": tick - self._feedback.event_tick if self._feedback is not None else None,
            "maximum_feedback_age": self._maximum_feedback_age,
            "is_wnm": False,
        }

    def reservations(self, *, at_tick: int) -> tuple[BodyTargetReservationV1, ...]:
        """Return only live body-side reservations without renewing or deleting them."""
        tick = self._check_tick(at_tick)
        return tuple(
            self._reservations[kind] for kind in SensorimotorTargetKindV1
            if kind in self._reservations and tick < self._reservations[kind].current.expires_at_tick
        )

    def _axis_refusal(self, kind: SensorimotorTargetKindV1, feedback: MotorFeedbackV1 | None) -> str | None:
        """Check only the evidence and capability required by the requested family."""
        if not self._enabled:
            return "bodymap_disabled"
        if kind not in self._capabilities:
            return "capability_unavailable"
        if feedback is None:
            return "current_body_feedback_unavailable"
        coordinate = feedback.body_tilt_degrees if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST else feedback.support_extension
        if coordinate is None:
            return "required_coordinate_missing"
        capability = self._capabilities[kind]
        if not capability.minimum_coordinate - _EPSILON <= coordinate <= capability.maximum_coordinate + _EPSILON:
            return "body_outside_capability_range"
        if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
            if feedback.support_contact is False and feedback.useful_loading is not None and feedback.useful_loading > 0.0:
                return "inconsistent_support_evidence"
            if feedback.support_contact is None or feedback.useful_loading is None:
                return "required_support_evidence_missing"
            if not feedback.support_contact or feedback.useful_loading <= 0.0:
                return "loaded_support_unavailable"
        return None

    def _make_binding(
        self, request: BodyMovementRequestV1, kind: SensorimotorTargetKindV1,
        goal: float, *, feedback: MotorFeedbackV1, number: int,
    ) -> BodyTargetBindingV1:
        """Calculate an anchored bounded increment, not a low-level drive command."""
        capability = self._capabilities[kind]
        coordinate = feedback.body_tilt_degrees if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST else feedback.support_extension
        if coordinate is None:
            raise ValueError("required body coordinate is missing")
        bounded_goal = max(capability.minimum_coordinate, min(capability.maximum_coordinate, goal))
        travel_budget = capability.maximum_rate * self._tick_seconds * request.lease_ticks
        maximum_step = min(capability.maximum_step, travel_budget)
        offset = max(-maximum_step, min(maximum_step, bounded_goal - coordinate))
        target = BodyRelativeTargetV1(
            target_id=f"body_target:{kind.value}:{number}", revision=1, origin=request.origin, kind=kind,
            basis=feedback, offset=offset, tolerance=capability.tolerance,
            max_displacement=capability.maximum_excursion, max_rate=capability.maximum_rate,
            lease_ticks=request.lease_ticks,
        )
        return BodyTargetBindingV1(target, capability)

    def propose(self, request: BodyMovementRequestV1, *, at_tick: int) -> BodyTargetProposalV1:
        """Map the supplied requirement; keep one pending proposal, occupy no resource.

        Refusal is per axis: missing tilt need not suppress a usable extension.
        A live reservation from another origin blocks both resources; BodyMap
        does not arbitrate between tasks. Each accepted target retains the same
        supplied origin. Narrowing is visible by comparing request and endpoint.
        A new proposal invalidates only the earlier unreserved proposal.
        """
        tick = self._check_tick(at_tick)
        if not isinstance(request, BodyMovementRequestV1):
            raise TypeError("request must be BodyMovementRequestV1")
        if request.origin.stream != self._stream:
            raise ValueError("task request has the wrong body stream or generation")
        if tick > _MAX_INDEX - request.lease_ticks:
            raise ValueError("insufficient tick range for this target lease")
        number = _index(self._proposal_number + 1, "proposal number", 1)
        feedback = self._current_feedback(tick)
        live = self.reservations(at_tick=tick)
        occupied = {item.current.target.kind for item in live}
        foreign_origin = any(item.current.target.origin != request.origin for item in live)
        bindings: list[BodyTargetBindingV1] = []
        withheld: list[tuple[SensorimotorTargetKindV1, str]] = []
        for kind, goal in (
            (SensorimotorTargetKindV1.ORIENTATION_ADJUST, request.desired_tilt_degrees),
            (SensorimotorTargetKindV1.SUPPORT_EXTENSION, request.desired_extension),
        ):
            if goal is None:
                continue
            reason = self._axis_refusal(kind, feedback)
            if reason is None and feedback is not None:
                capability = self._capabilities[kind]
                coordinate = (
                    feedback.body_tilt_degrees
                    if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST else feedback.support_extension
                )
                bounded_goal = max(capability.minimum_coordinate, min(capability.maximum_coordinate, goal))
                travel_budget = capability.maximum_rate * self._tick_seconds * request.lease_ticks
                if coordinate is not None and abs(bounded_goal - coordinate) > capability.tolerance:
                    if travel_budget <= capability.tolerance:
                        reason = "insufficient_motion_budget"
            if reason is None and foreign_origin:
                reason = "different_task_envelope_reserved"
            if reason is None and kind in occupied:
                reason = "resource_already_reserved"
            if reason is not None:
                withheld.append((kind, reason))
            else:
                if feedback is None:
                    raise RuntimeError("accepted mapping lost its current feedback")
                bindings.append(self._make_binding(request, kind, goal, feedback=feedback, number=number))
        proposal = BodyTargetProposalV1(request, tick, tuple(bindings), tuple(withheld))
        self._pending = proposal
        self._proposal_number = number
        self._last_tick = tick
        return proposal

    def reserve(
        self, proposal: BodyTargetProposalV1, *, execution_id: str, at_tick: int,
    ) -> tuple[BodyTargetReservationV1, ...]:
        """Reserve proposed body resources for an explicitly supplied execution fixture.

        This is a BodyMap-side association, not motor installation or proof of
        task authorization. H4/H6 must separately validate the real handoff.
        Reject stale/foreign/copied proposals, occupied axes, mismatched owners
        and changed sensing before mutation. A valid subset can be reserved
        when another requested axis was withheld; that refusal remains visible.
        """
        tick = self._check_tick(at_tick)
        execution = _name(execution_id, "execution_id")
        if not isinstance(proposal, BodyTargetProposalV1) or proposal is not self._pending:
            raise ValueError("proposal is not the mapper's current original proposal")
        if not proposal.bindings:
            raise ValueError("proposal has no usable target to reserve")
        feedback = self._current_feedback(tick)
        live = self.reservations(at_tick=tick)
        if any(item.current.target.origin != proposal.request.origin or item.current.execution_id != execution for item in live):
            raise ValueError("resources belong to another task, envelope or execution")
        occupied = {item.current.target.kind for item in live}
        added: list[BodyTargetReservationV1] = []
        for binding in proposal.bindings:
            kind = binding.target.kind
            if kind in occupied:
                raise ValueError("resource already has a reserved target")
            if feedback != binding.target.basis or self._axis_refusal(kind, feedback) is not None:
                raise ValueError("target proposal no longer has a valid current body basis")
            committed = CommittedBodyTargetV1(binding.target, execution, tick)
            added.append(BodyTargetReservationV1(committed, committed, binding.capability, tick))
        self._reservations = {item.current.target.kind: item for item in (*live, *added)}
        self._pending = None
        self._last_tick = tick
        return tuple(added)

    def validate_reservation(self, reservation: BodyTargetReservationV1, *, at_tick: int) -> None:
        """Check current body-side ownership and lease, not actuator permission.

        Retained, cancelled, refined-away and reconstructed descriptions cannot
        pass as the currently owned record. This does not check live motor state
        or promise safety; later execution must additionally use current feedback.
        """
        tick = self._check_tick(at_tick)
        if not isinstance(reservation, BodyTargetReservationV1):
            raise TypeError("reservation must be BodyTargetReservationV1")
        current = self._reservations.get(reservation.current.target.kind)
        if current is not reservation:
            raise ValueError("reservation is not the currently owned body request")
        target = reservation.current.target
        reservation.current.validate_current(
            stream=self._stream, execution_id=reservation.current.execution_id,
            envelope_id=target.origin.envelope_id, target_id=target.target_id,
            target_revision=target.revision, now_tick=tick,
        )

    def refine(
        self, reservation: BodyTargetReservationV1, *, endpoint: float, at_tick: int,
    ) -> BodyTargetReservationV1:
        """Refine within the original tolerance band and lease using current evidence.

        At most one change per later local tick is allowed. The fixed initial
        anchor, maximum excursion/rate, original endpoint tolerance band and
        original expiry survive every revision. This cannot ratchet a target
        across successive bands, extend a task, or consume an H4 anomaly budget.
        A larger movement needs cancellation and a new legitimately authorized
        task contribution. No motor action or new PNM occurs here.
        """
        tick = self._check_tick(at_tick)
        self.validate_reservation(reservation, at_tick=tick)
        if tick <= reservation.updated_tick:
            raise ValueError("refinement requires a later local tick")
        initial, current = reservation.initial.target, reservation.current.target
        lower, upper, _ = _axis_limits(current.kind)
        value = _scalar(endpoint, "endpoint", lower, upper)
        feedback = self._current_feedback(tick)
        if self._axis_refusal(current.kind, feedback) is not None or feedback is None:
            raise ValueError("refinement requires current usable body evidence")
        coordinate = (
            feedback.body_tilt_degrees
            if current.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST else feedback.support_extension
        )
        if coordinate is None or abs(coordinate - initial.basis_coordinate) > initial.max_displacement + _EPSILON:
            raise ValueError("current body has left the original permitted excursion")
        if abs(value - initial.endpoint) > initial.tolerance + _EPSILON:
            raise ValueError("refinement exceeds the original endpoint tolerance band")
        capability = reservation.capability
        if not capability.minimum_coordinate - _EPSILON <= value <= capability.maximum_coordinate + _EPSILON:
            raise ValueError("refined endpoint exceeds capability coordinate range")
        remaining_travel = current.max_rate * self._tick_seconds * (reservation.current.expires_at_tick - tick)
        if abs(value - coordinate) > remaining_travel + current.tolerance:
            raise ValueError("refined target exceeds the remaining nominal travel budget")
        if value == current.endpoint:
            self._last_tick = tick
            return reservation
        revision = _index(current.revision + 1, "target revision", 1)
        target = replace(current, revision=revision, offset=value - initial.basis_coordinate)
        committed = CommittedBodyTargetV1(target, reservation.current.execution_id, reservation.initial.committed_tick)
        updated = BodyTargetReservationV1(reservation.initial, committed, capability, tick)
        self._reservations[current.kind] = updated
        self._pending = None
        self._last_tick = tick
        return updated

    def cancel(self, reservation: BodyTargetReservationV1, *, at_tick: int) -> BodyTargetReservationV1:
        """Release a named current resource; never undo or assert a physical effect."""
        tick = self._check_tick(at_tick)
        self.validate_reservation(reservation, at_tick=tick)
        cancelled = replace(reservation, updated_tick=tick, status="cancelled")
        del self._reservations[reservation.current.target.kind]
        self._pending = None
        self._last_tick = tick
        return cancelled

    def expire(self, *, at_tick: int) -> tuple[BodyTargetReservationV1, ...]:
        """Retire due reservations under their original leases, with no renewal.

        Passing time does not issue a command. H4 must query/check the lease
        before pursuit even if this housekeeping method has not yet been called.
        The returned records are historical expiry reports, not failed movement
        verdicts. At most two entries are examined; no history is accumulated.
        """
        tick = self._check_tick(at_tick)
        expired = tuple(
            replace(item, updated_tick=tick, status="expired")
            for item in self._reservations.values() if tick >= item.current.expires_at_tick
        )
        for item in expired:
            del self._reservations[item.current.target.kind]
        if self._pending is not None and self._current_feedback(tick) is None:
            self._pending = None
        self._last_tick = tick
        return expired
