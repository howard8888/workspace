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
from dataclasses import dataclass, field, replace

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1
from nca8_visual import VisualNavMapStateV1
from nca8_maternal import MaternalNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1, BodyTranslationTargetV1,
    CommittedBodyTargetV1,
    SensorimotorTargetKindV1,
    TargetOriginV1, oral_basis_compatible_v1, scalar_motor_coordinate_v1,
)

__version__ = "0.8.0"
__all__ = [
    "PlanarBodyObservationV1", "VisualApproachRequestV1", "VisualBodyPreviewV1",
    "BodyAxisCapabilityV1", "BodyTranslationCapabilityV1",
    "BodyMovementRequestV1",
    "BodyTargetBindingV1",
    "BodyTargetMapperV1",
    "BodyTargetProposalV1",
    "BodyTargetReservationV1",
    "nominal_body_capabilities_v1", "oral_body_capability_v1", "OralReachRequestV1", "OralReachPreviewV1",
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
    if kind is SensorimotorTargetKindV1.PLANAR_TRANSLATION:
        raise ValueError("vector translation is not a scalar axis")
    if kind is SensorimotorTargetKindV1.ORAL_REACH:
        return 0.0, 0.35, 0.5
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


def oral_body_capability_v1() -> BodyAxisCapabilityV1:
    """Supply optional single-axis oral competence, never enable it by default.

    This is a body-forward reach motor with a 0.15-metre contribution, 0.20-metre
    excursion, 0.5 metres/second rate and 0.0025-metre coordinate tolerance.
    It is not a nipple finder, head-orientation strategy, latch or suckling skill.
    The ordinary eight-tick lease and body protection still apply independently.
    """
    return BodyAxisCapabilityV1(SensorimotorTargetKindV1.ORAL_REACH, "smp:oral_reach:v1", 0.0, 0.35, 0.15, 0.20, 0.5, 0.0025)


@dataclass(frozen=True, slots=True)
class BodyTranslationCapabilityV1:
    """Fixed supplied vector competence; not learned calibration or task choice.

    Limits are deliberately small: a 0.25-metre target, 0.35-metre radial
    excursion, at most one metre/second, and a 0.01-metre local tolerance.
    Narrower supplied limits are permitted. The original eight-tick lease and
    two anomalous corrections remain independent of the task lifetime.
    """

    capability_id: str = "smp:planar_translation:v1"
    maximum_step: float = 0.25
    maximum_excursion: float = 0.35
    maximum_rate: float = 1.0
    tolerance: float = 0.01

    def __post_init__(self) -> None:
        _name(self.capability_id, "translation capability")
        for name in ("maximum_step", "maximum_excursion", "tolerance"):
            object.__setattr__(self, name, _scalar(getattr(self, name), name, 0.0, 0.5))
        object.__setattr__(self, "maximum_rate", _scalar(self.maximum_rate, "translation rate", 0.0, 1.0))
        if not 0.0 < self.tolerance <= self.maximum_step <= self.maximum_excursion or self.maximum_rate <= 0.0:
            raise ValueError("translation capability requires positive, ordered motion limits")

    @property
    def kind(self) -> SensorimotorTargetKindV1:
        """Return the vector resource family, not two separate focal operations."""
        return SensorimotorTargetKindV1.PLANAR_TRANSLATION

    def as_dict(self) -> dict[str, object]:
        """Describe assumed competence without claiming a successful movement."""
        return {"kind": self.kind.value, "capability_id": self.capability_id, "maximum_step": self.maximum_step,
                "maximum_excursion": self.maximum_excursion, "maximum_rate": self.maximum_rate, "tolerance": self.tolerance}


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
class OralReachRequestV1:
    """Identify a feeding-source region for one externally supplied reach fixture.

    The request selects no task and carries no desired success or hidden physical
    destination. BodyMap resolves the current represented point into its actual
    body-forward axis. The first experiment supplies this requirement explicitly;
    it does not claim Navigation selected SeekNipple or acquired a learned LP.
    """

    origin: TargetOriginV1
    source_map_ref: NavMapRefV1
    region_id: str
    lease_ticks: int = 8

    def __post_init__(self) -> None:
        if not isinstance(self.origin, TargetOriginV1) or not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("oral request requires the shared origin and a source reference")
        _name(self.region_id, "oral region handle")
        _index(self.lease_ticks, "oral lease", 1, 8)

    def as_dict(self) -> dict[str, object]:
        """Describe a supplied relation requirement, without live actuator rights."""
        return {"origin": self.origin.as_dict(), "source_map_ref": self.source_map_ref.as_dict(),
                "region_id": self.region_id, "lease_ticks": self.lease_ticks, "origin_status": "supplied_requirement_fixture"}


@dataclass(frozen=True, slots=True)
class OralReachPreviewV1:
    """Immutable record of source-to-body mapping before reservation/installation.

    Forward/left are calculated from independent current scene and body evidence.
    Off-axis or out-of-reach geometry remains visible as a refusal: the first
    one-axis motor cannot invent a head turn or body approach. This preview is
    not a task PNM and cannot establish physical contact or a found milestone.
    """

    request: OralReachRequestV1
    source: FeedingDetailNavMapStateV1 | None
    body: MotorFeedbackV1 | None
    forward_metres: float | None
    left_metres: float | None
    status: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, OralReachRequestV1):
            raise TypeError("oral mapping requires its original typed request")
        if self.source is not None and (not isinstance(self.source, FeedingDetailNavMapStateV1)
                                      or self.source.stream != self.request.origin.stream):
            raise ValueError("oral mapping source is invalid or foreign")
        if self.body is not None and (not isinstance(self.body, MotorFeedbackV1) or self.body.stream != self.request.origin.stream):
            raise ValueError("oral mapping body acquisition is invalid or foreign")
        if (self.forward_metres is None) != (self.left_metres is None):
            raise ValueError("oral mapping needs both coordinates or neither")
        for name in ("forward_metres", "left_metres"):
            value = getattr(self, name)
            if value is not None:
                _scalar(value, name, -30000.0, 30000.0)
        _name(self.status, "oral mapping status")

    def as_dict(self) -> dict[str, object]:
        """Keep represented position, mapped axis and unobserved contact distinct."""
        return {"request": self.request.as_dict(), "source": None if self.source is None else self.source.as_dict(),
                "body": None if self.body is None else self.body.as_dict(), "forward_metres": self.forward_metres,
                "left_metres": self.left_metres, "lateral_tolerance_metres": 0.005, "status": self.status,
                "is_task_pnm": False, "establishes_contact": False}


@dataclass(frozen=True, slots=True)
class BodyTargetBindingV1:
    """One proposed H1 target associated with one available family capability."""

    target: BodyRelativeTargetV1 | BodyTranslationTargetV1
    capability: BodyAxisCapabilityV1 | BodyTranslationCapabilityV1

    def __post_init__(self) -> None:
        if isinstance(self.target, BodyTranslationTargetV1):
            if not isinstance(self.capability, BodyTranslationCapabilityV1):
                raise TypeError("translation binding needs vector competence")
            if (math.hypot(*self.target.offset) > self.capability.maximum_step + _EPSILON
                    or self.target.max_displacement > self.capability.maximum_excursion
                    or self.target.max_rate > self.capability.maximum_rate or self.target.tolerance > self.capability.tolerance):
                raise ValueError("translation exceeds its supplied capability")
            return
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

    request: BodyMovementRequestV1 | VisualApproachRequestV1 | OralReachRequestV1
    created_tick: int
    bindings: tuple[BodyTargetBindingV1, ...]
    withheld: tuple[tuple[SensorimotorTargetKindV1, str], ...]
    replaces: tuple[BodyTargetReservationV1, ...] = ()
    visual_preview: VisualBodyPreviewV1 | None = None
    oral_preview: OralReachPreviewV1 | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.request, (BodyMovementRequestV1, VisualApproachRequestV1, OralReachRequestV1)):
            raise TypeError("proposal requires BodyMovementRequestV1")
        _index(self.created_tick, "created_tick")
        if not isinstance(self.replaces, tuple) or len(self.replaces) > 2:
            raise ValueError("replacement must name at most two original reservations")
        if any(not isinstance(item, BodyTargetReservationV1) for item in self.replaces):
            raise TypeError("replacement entries must be BodyMap reservations")
        if len({item.current.target.kind for item in self.replaces}) != len(self.replaces):
            raise ValueError("replacement resources must be distinct")
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
            if not isinstance(kind, SensorimotorTargetKindV1):
                raise TypeError("withheld kind must name a target family")
            _name(reason, "withheld reason")
            kinds.append(kind)
        expected = set()
        if self.oral_preview is not None and not isinstance(self.request, OralReachRequestV1):
            raise ValueError("only an oral request can carry its mapping preview")
        if isinstance(self.request, OralReachRequestV1):
            expected.add(SensorimotorTargetKindV1.ORAL_REACH)
            if self.visual_preview is not None or self.oral_preview is None or self.oral_preview.request is not self.request:
                raise ValueError("oral proposal needs its original independent source/body mapping")
        elif isinstance(self.request, VisualApproachRequestV1):
            expected.add(SensorimotorTargetKindV1.PLANAR_TRANSLATION)
            if self.visual_preview is None or self.visual_preview.request is not self.request:
                raise ValueError("translation proposal needs the original geometric calculation")
        else:
            if self.visual_preview is not None:
                raise ValueError("support proposal cannot carry a visual preview")
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
            **({"visual_mapping": self.visual_preview.as_dict()} if self.visual_preview is not None else {}),
            **({"oral_mapping": self.oral_preview.as_dict()} if self.oral_preview is not None else {}),
            **({"replaces": [item.current.as_dict() for item in self.replaces]} if self.replaces else {}),
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
    capability: BodyAxisCapabilityV1 | BodyTranslationCapabilityV1
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
        if isinstance(before, BodyTranslationTargetV1):
            if not isinstance(after, BodyTranslationTargetV1) or after != before:
                raise ValueError("this translation profile requires a new authorization for target changes")
        elif before.kind is SensorimotorTargetKindV1.ORAL_REACH and after != before:
            raise ValueError("oral target changes require new authorization")
        elif isinstance(after, BodyTranslationTargetV1) or abs(after.endpoint - before.endpoint) > before.tolerance + _EPSILON:
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


@dataclass(frozen=True, slots=True)
class PlanarBodyObservationV1:
    """Independent horizontal body localization for the visual mapping preview.

    Position is metres in an explicit scene_xy: frame. Heading is counterclockwise
    degrees from that frame's +X axis, with body +Y to the left. This is horizontal
    yaw, NOT the existing signed gravity-relative body tilt. Neither is inferred
    from the other. The current fixture supplies localization as a declared sensor
    scaffold; no locomotor provider exists in 2A-A. Unknown position/heading stays
    unknown. The original acquisition/time/generation is immutable.
    """

    stream: MotorStreamRefV1
    sample_id: int
    event_tick: int
    available_tick: int
    frame_id: str
    position: NavPointV1 | None
    heading_degrees: float | None

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("planar body observation needs MotorStreamRefV1")
        _index(self.sample_id, "sample_id", 1)
        _index(self.event_tick, "event_tick")
        _index(self.available_tick, "available_tick", self.event_tick)
        _name(self.frame_id, "frame_id")
        if not self.frame_id.startswith("scene_xy:") or self.frame_id == "scene_xy:":
            raise ValueError("planar body observation needs an explicit horizontal scene_xy: metre frame")
        if self.position is not None:
            if not isinstance(self.position, NavPointV1):
                raise TypeError("body position must be NavPointV1 or None")
            _scalar(self.position.x, "body x", -10000, 10000)
            _scalar(self.position.y, "body y", -10000, 10000)
        if self.heading_degrees is not None:
            object.__setattr__(self, "heading_degrees", _scalar(self.heading_degrees, "heading", -180, 180))

    def as_dict(self) -> dict[str, object]:
        """Export current localization without implying target or motor permission."""
        return {"stream": self.stream.as_dict(), "sample_id": self.sample_id, "event_tick": self.event_tick,
                "available_tick": self.available_tick, "frame_id": self.frame_id, "units": "metres",
                "position": None if self.position is None else self.position.as_dict(),
                "heading_degrees": self.heading_degrees, "heading_is_gravity_tilt": False}


@dataclass(frozen=True, slots=True)
class VisualApproachRequestV1:
    """A bounded source-relative requirement with an explicitly identified origin.

    The retained visual fixtures supply their requirement without claiming task
    selection. The maternal profile instead records a selected Follow-Mom
    application. Neither a record nor its origin label grants a motor lease:
    BodyMap proposal, reservation and the closed handoff still establish that
    boundary. BodyMap never chooses the represented region. The intermediate
    displacement stops short of the selected point by stand_off_metres.
    """

    origin: TargetOriginV1
    source_map_ref: NavMapRefV1
    region_id: str
    stand_off_metres: float = 0.5
    maximum_step_metres: float = 0.25
    origin_status: str = "supplied_requirement_fixture"

    def __post_init__(self) -> None:
        if not isinstance(self.origin, TargetOriginV1) or not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("visual request needs the existing origin and source-reference contracts")
        _name(self.region_id, "region_id")
        if self.origin_status not in {"supplied_requirement_fixture", "selected_follow_mom"}:
            raise ValueError("unsupported approach requirement origin")
        object.__setattr__(self, "stand_off_metres", _scalar(self.stand_off_metres, "stand off", 0, 100))
        step = _scalar(self.maximum_step_metres, "maximum step", 0, 1)
        if step == 0:
            raise ValueError("maximum step must be positive")
        object.__setattr__(self, "maximum_step_metres", step)

    def as_dict(self) -> dict[str, object]:
        """Declare the supplied, unselected requirement rather than a task decision."""
        return {"origin": self.origin.as_dict(), "source_map_ref": self.source_map_ref.as_dict(),
                "region_id": self.region_id, "stand_off_metres": self.stand_off_metres,
                "maximum_step_metres": self.maximum_step_metres, "source": self.origin_status}


@dataclass(frozen=True, slots=True)
class VisualBodyPreviewV1:
    """A non-actuating BodyMap result with immutable source and body anchors.

    A body_relative_target is the whole target displacement, while body_step is
    the bounded intermediate proposal. hypothetical_self is a geometric preview
    under perfect translation, not a PNM generated by a selected IP or an observed
    outcome. This type is deliberately incompatible with live H1 reservations,
    H6 handoffs and H4 installation. No translation capability is claimed yet.
    """

    request: VisualApproachRequestV1
    source: VisualNavMapStateV1 | MaternalNavMapStateV1
    body: PlanarBodyObservationV1 | None
    cutoff_tick: int
    status: str
    scene_target: NavPointV1 | None = None
    body_relative_target: NavPointV1 | None = None
    body_step: NavPointV1 | None = None
    hypothetical_self: NavPointV1 | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.request, VisualApproachRequestV1) or not isinstance(self.source, (VisualNavMapStateV1, MaternalNavMapStateV1)):
            raise TypeError("preview requires its typed original request and visual source")
        _index(self.cutoff_tick, "cutoff_tick", self.source.cutoff_tick)
        if self.status not in {"geometry_only_not_authorized", "mapping_disabled", "visual_unavailable", "visual_stale",
                               "spatial_stream_disabled", "target_unlocalized", "body_pose_unavailable",
                               "body_geometry_unknown", "frame_incompatible"}:
            raise ValueError("unknown visual mapping disposition")
        if self.body is not None and not isinstance(self.body, PlanarBodyObservationV1):
            raise TypeError("preview body must be a typed localization or None")
        if self.request.origin.stream != self.source.stream or self.request.source_map_ref != self.source.source_map_ref:
            raise ValueError("preview request and source have different origins")
        points = (self.scene_target, self.body_relative_target, self.body_step, self.hypothetical_self)
        if self.status == "geometry_only_not_authorized":
            if self.body is None or any(not isinstance(point, NavPointV1) for point in points):
                raise ValueError("computed visual preview requires all geometric fields and its body basis")
            if self.body_step is not None and math.hypot(self.body_step.x, self.body_step.y) > self.request.maximum_step_metres + _EPSILON:
                raise ValueError("preview exceeds the requested intermediate step bound")
        elif any(point is not None for point in points):
            raise ValueError("a withheld preview cannot expose a fabricated target")

    def as_dict(self) -> dict[str, object]:
        """Export actual/hypothetical fields separately; no reader acquires authority."""
        return {"request": self.request.as_dict(), "source": self.source.as_dict(),
                "body": None if self.body is None else self.body.as_dict(), "cutoff_tick": self.cutoff_tick,
                "status": self.status, "scene_target": None if self.scene_target is None else self.scene_target.as_dict(),
                "body_relative_target": None if self.body_relative_target is None else self.body_relative_target.as_dict(),
                "body_step": None if self.body_step is None else self.body_step.as_dict(),
                "hypothetical_self": None if self.hypothetical_self is None else self.hypothetical_self.as_dict(),
                "prediction_model": "perfect_translation_geometry_fixture_only",
                "motor_authority": False, "capability_bound": False, "task_selected": False, "task_pnm_created": False}


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

    orientation_mapping_sign defaults to +1. The explicit -1 qualification
    setting reverses only the mapped orientation increment, not the sensed pose,
    task request, extension, capability or motor sign. It is a calibration-fault
    control, not a learned parameter or a normal recovery policy. Original
    coordinate, excursion, rate, resource and lease checks remain in force.
    """

    def __init__(
        self, stream: MotorStreamRefV1, capabilities: tuple[BodyAxisCapabilityV1, ...], *,
        tick_seconds: float = 0.05, maximum_feedback_age: int = 2, enabled: bool = True, orientation_mapping_sign: int = 1,
        visual_preview_enabled: bool = False, translation_capability: BodyTranslationCapabilityV1 | None = None,
        translation_mapping_sign: int = 1,
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
        if isinstance(orientation_mapping_sign, bool) or not isinstance(orientation_mapping_sign, int):
            raise TypeError("orientation_mapping_sign must be +1 or -1, not Boolean")
        if orientation_mapping_sign not in (-1, 1):
            raise ValueError("orientation_mapping_sign must be +1 or -1")
        if not isinstance(visual_preview_enabled, bool):
            raise TypeError("visual_preview_enabled must be Boolean")
        if translation_capability is not None and not isinstance(translation_capability, BodyTranslationCapabilityV1):
            raise TypeError("translation capability must be typed or absent")
        if translation_capability is not None and not visual_preview_enabled:
            raise ValueError("translation requires the visual/body geometry path")
        if isinstance(translation_mapping_sign, bool) or not isinstance(translation_mapping_sign, int) or translation_mapping_sign not in (-1, 1):
            raise ValueError("translation mapping sign must be +1 or -1")
        self._translation_capability = translation_capability
        self._translation_mapping_sign = translation_mapping_sign
        self._visual_preview_enabled = visual_preview_enabled
        self._planar_observation: PlanarBodyObservationV1 | None = None
        self._planar_available = False
        self._orientation_mapping_sign = orientation_mapping_sign
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
        self._executor_owner: object | None = None

    def observe_planar_body(self, observation: PlanarBodyObservationV1 | None, *, at_tick: int) -> None:
        """Maintain one optional body-local spatial reading without updating vision.

        This opt-in preview channel shares the mapper's existing stream and clock.
        It grants no resource, target or motor permission. Bad/future/reversed or
        changed-duplicate packets reject before mutation. An explicit gap cannot
        be repaired with an old duplicate; a distinct acquisition is required.
        """
        if not self._visual_preview_enabled:
            raise RuntimeError("planar body input requires the explicit visual-preview profile")
        tick = self._check_tick(at_tick)
        retained = self._planar_observation
        available = False
        if observation is not None:
            if not isinstance(observation, PlanarBodyObservationV1):
                raise TypeError("planar body input requires a typed observation or None")
            if observation.stream != self._stream or observation.available_tick > tick:
                raise ValueError("planar body input is foreign or not yet available")
            duplicate = retained is not None and observation.sample_id == retained.sample_id
            if retained is not None:
                if duplicate and observation != retained:
                    raise ValueError("planar body acquisition identity changed")
                if not duplicate and (observation.sample_id <= retained.sample_id or observation.event_tick <= retained.event_tick):
                    raise ValueError("planar body samples and events must advance")
            available = self._planar_available if duplicate else True
            retained = observation
        self._planar_observation, self._planar_available, self._last_tick = retained, available, tick

    def preview_visual_approach(
        self, request: VisualApproachRequestV1, source: VisualNavMapStateV1 | MaternalNavMapStateV1, *, at_tick: int,
    ) -> VisualBodyPreviewV1:
        """Compute the explicit scene-to-body transform with no reservation or drive.

        R(-heading) maps target minus current body position to forward/left metres.
        A bounded intermediate step is re-expressed in the scene solely to display
        its hypothetical geometric effect. Current source/body data are unchanged.
        There is no collision solver, movement guarantee, task choice or learned
        calibration. Execution requires the separate proposal/reservation/handoff path.
        """
        if not self._visual_preview_enabled:
            raise RuntimeError("visual mapping requires the explicit preview profile")
        tick = self._check_tick(at_tick)
        if not isinstance(request, VisualApproachRequestV1) or not isinstance(source, (VisualNavMapStateV1, MaternalNavMapStateV1)):
            raise TypeError("mapping needs a typed supplied request and visual source")
        if request.origin.stream != self._stream or source.stream != self._stream or request.source_map_ref != source.source_map_ref:
            raise ValueError("visual mapping cannot borrow a different source or generation")
        if source.cutoff_tick > tick:
            raise ValueError("visual source was applied after this mapping opportunity")
        body = self._planar_observation if self._planar_available else None
        if body is not None and tick - body.event_tick > self._maximum_feedback_age:
            body = None
        status = "geometry_only_not_authorized"
        region = next((item for item in source.guidance if item.region_id == request.region_id), None)
        if not self._enabled:
            status = "mapping_disabled"
        elif not source.evidence_current:
            status = "visual_unavailable"
        elif source.event_tick is None or tick - source.event_tick > 2:
            status = "visual_stale"
        elif not source.spatial_enabled:
            status = "spatial_stream_disabled"
        elif region is None:
            status = "target_unlocalized"
        elif body is None:
            status = "body_pose_unavailable"
        elif body.position is None or body.heading_degrees is None:
            status = "body_geometry_unknown"
        elif body.frame_id != source.frame_id:
            status = "frame_incompatible"
        if status != "geometry_only_not_authorized":
            return VisualBodyPreviewV1(request, source, body, tick, status)
        if region is None or body is None or body.position is None or body.heading_degrees is None:
            raise RuntimeError("validated visual mapping lost its geometry")
        dx, dy = region.position.x - body.position.x, region.position.y - body.position.y
        heading = math.radians(body.heading_degrees)
        cosine, sine = math.cos(heading), math.sin(heading)
        forward, left = cosine * dx + sine * dy, -sine * dx + cosine * dy
        distance = math.hypot(dx, dy)
        extent = min(request.maximum_step_metres, max(0.0, distance - request.stand_off_metres))
        ratio = extent / distance if distance > 0.0 else 0.0
        step = NavPointV1(forward * ratio, left * ratio)
        hypothetical = NavPointV1(body.position.x + dx * ratio, body.position.y + dy * ratio)
        return VisualBodyPreviewV1(request, source, body, tick, status, region.position,
                                   NavPointV1(forward, left), step, hypothetical)

    def retained_counts(self) -> dict[str, int]:
        """Count owned records without expiring, refreshing or granting any right.

        These diagnostic counts include an old sensor record and reserved records
        awaiting normal expiry processing. They measure storage, not currentness.
        The fixed limits are one sensor, one unreserved proposal and two resources.
        """
        return {"body_sensor_records": int(self._feedback is not None),
                "body_pending_proposals": int(self._pending is not None), "body_reserved_records": len(self._reservations),
                **({"planar_body_records": int(self._planar_observation is not None)} if self._visual_preview_enabled else {})}

    @property
    def stream(self) -> MotorStreamRefV1:
        """Return the fixed body stream; resetting requires a fresh helper/generation."""
        return self._stream

    @property
    def capabilities(self) -> tuple[BodyAxisCapabilityV1, ...]:
        """Return the fixed capability declarations in canonical family order."""
        return tuple(self._capabilities[kind] for kind in SensorimotorTargetKindV1 if kind in self._capabilities)

    @property
    def tick_seconds(self) -> float:
        """Return the declared local interval; this property runs no clock."""
        return self._tick_seconds

    def claim_executor_slot(self, owner: object) -> None:
        """Attach one local executor owner to this body generation, without movement.

        H4 supplies a private owner token, not a serialized ID or target record.
        A second executor cannot attach to the same mapper and independently
        dispatch its reservations. This is one local ownership slot, not a
        global registry or cognitive handoff. Reset uses a fresh mapper.
        """
        if owner is None:
            raise TypeError("executor owner cannot be None")
        if self._executor_owner is not None:
            raise ValueError("this BodyMap already has a local executor owner")
        self._executor_owner = owner

    def current_feedback(self, *, at_tick: int) -> MotorFeedbackV1 | None:
        """Return the eligible immutable local reading, never a prediction or new event.

        This is the typed H4 reader for the existing H3 currentness calculation.
        It does not refresh a timestamp, alter the focal source, or backfill an
        unavailable channel. A returned reading may be a still-valid reread.
        """
        return self._current_feedback(self._check_tick(at_tick))

    def execution_refusal(self, reservation: BodyTargetReservationV1, *, at_tick: int) -> str | None:
        """Check current ownership plus the existing per-axis evidence constraints.

        H4 calls this before pursuit. Revocation/revision/expiry raises through
        validate_reservation; an unavailable coordinate, support or capability
        returns the same reason used by H3. No command or target change occurs.
        """
        self.validate_reservation(reservation, at_tick=at_tick)
        feedback = self.current_feedback(at_tick=at_tick)
        if isinstance(reservation.current.target, BodyTranslationTargetV1) and feedback is not None and feedback.planar is not None:
            original = reservation.current.target.basis.planar
            if original is None or original.frame_id != feedback.planar.frame_id:
                return "translation_frame_changed"
        refusal = self._axis_refusal(reservation.current.target.kind, feedback)
        if refusal is None and reservation.current.target.kind is SensorimotorTargetKindV1.ORAL_REACH and feedback is not None:
            target = reservation.current.target
            if not oral_basis_compatible_v1(target.basis, feedback):
                return "oral_body_anchor_changed"
            oral = feedback.oral
            if not isinstance(target, BodyRelativeTargetV1) or oral is None or oral.extension_metres is None:
                raise RuntimeError("oral permission lacks its scalar target or measured reach")
            if oral.contact is True and abs(oral.extension_metres - target.endpoint) > target.tolerance + _EPSILON:
                return "oral_contact_before_target"
        return refusal

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
            if self._translation_capability is not None:
                self._planar_available = False
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
        if self._visual_preview_enabled and feedback.planar is not None:
            planar = feedback.planar
            self.observe_planar_body(PlanarBodyObservationV1(
                feedback.stream, feedback.sample_id, feedback.event_tick, feedback.available_tick, planar.frame_id,
                None if planar.position is None else NavPointV1(*planar.position), planar.heading_degrees,
            ), at_tick=tick)
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
        if kind is SensorimotorTargetKindV1.PLANAR_TRANSLATION:
            return self._translation_refusal(feedback)
        if not self._enabled:
            return "bodymap_disabled"
        if kind not in self._capabilities:
            return "capability_unavailable"
        if feedback is None:
            return "current_body_feedback_unavailable"
        coordinate = scalar_motor_coordinate_v1(feedback, kind)
        if coordinate is None:
            return "required_coordinate_missing"
        capability = self._capabilities[kind]
        if not capability.minimum_coordinate - _EPSILON <= coordinate <= capability.maximum_coordinate + _EPSILON:
            return "body_outside_capability_range"
        if kind is SensorimotorTargetKindV1.ORAL_REACH:
            planar, oral = feedback.planar, feedback.oral
            if planar is None or planar.position is None or planar.heading_degrees is None:
                return "required_coordinate_missing"
            if oral is None or oral.contact is None:
                return "required_contact_evidence_missing"
            if (feedback.support_contact is None or feedback.useful_loading is None
                    or feedback.body_tilt_degrees is None or feedback.destabilization is None):
                return "required_support_evidence_missing"
            if (not feedback.support_contact or feedback.useful_loading < 0.75
                    or abs(feedback.body_tilt_degrees) > 12.0 or feedback.destabilization > 0.25):
                return "oral_support_unavailable"
        if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
            if feedback.support_contact is False and feedback.useful_loading is not None and feedback.useful_loading > 0.0:
                return "inconsistent_support_evidence"
            if feedback.support_contact is None or feedback.useful_loading is None:
                return "required_support_evidence_missing"
            if not feedback.support_contact or feedback.useful_loading <= 0.0:
                return "loaded_support_unavailable"
        return None

    def _translation_refusal(self, feedback: MotorFeedbackV1 | None) -> str | None:
        """Apply evidence-limited translation protection, never choose a new task.

        The initial capability needs mobility-quality support (tilt <=12 degrees,
        load >=0.75 and destabilization <=0.15) plus known obstacle contact. These
        are fixed engineering constraints, not a theorem of biological balance.
        Incompatibility with posture manipulation is checked at reservation time.
        """
        if not self._enabled:
            return "bodymap_disabled"
        if self._translation_capability is None:
            return "capability_unavailable"
        if feedback is None:
            return "current_body_feedback_unavailable"
        planar = feedback.planar
        if planar is None or planar.position is None or planar.heading_degrees is None:
            return "required_coordinate_missing"
        if (feedback.support_contact is None or feedback.body_tilt_degrees is None or feedback.useful_loading is None
                or feedback.destabilization is None or planar.obstacle_contact is None):
            return "required_support_evidence_missing"
        if planar.obstacle_contact:
            return "observed_obstacle_contact"
        if (not feedback.support_contact or feedback.useful_loading < 0.75
                or abs(feedback.body_tilt_degrees) > 12.0 or feedback.destabilization > 0.15):
            return "translation_support_unavailable"
        return None

    def propose_translation(
        self, request: VisualApproachRequestV1, source: VisualNavMapStateV1 | MaternalNavMapStateV1, *, at_tick: int,
        lease_ticks: int = 8, replace_existing: bool = False,
    ) -> BodyTargetProposalV1:
        """Map the supplied visual requirement into a real finite vector target.

        The accepted 2A-A calculation supplies geometry only. This method checks
        current independent body sensing and declared capability, narrows the
        bounded step, then proposes a vector target anchored to that acquisition.
        Reserving and installing still require the original proposal and a later
        single-use handoff. Mapping reversal is a named calibration-fault control;
        it alters neither sensing, requested object nor the physical motor signs.
        """
        tick = self._check_tick(at_tick)
        _index(lease_ticks, "translation lease", 1, 8)
        if tick > _MAX_INDEX - lease_ticks:
            raise ValueError("translation expiry exceeds the supported time range")
        if not isinstance(replace_existing, bool):
            raise TypeError("replace_existing must be Boolean")
        preview = self.preview_visual_approach(request, source, at_tick=tick)
        number = _index(self._proposal_number + 1, "proposal number", 1)
        feedback = self._current_feedback(tick)
        live = self.reservations(at_tick=tick)
        replacing = live if replace_existing else ()
        reason = None if preview.status == "geometry_only_not_authorized" else preview.status
        if reason is None:
            reason = self._translation_refusal(feedback)
        if reason is None and live and not replace_existing:
            reason = "incompatible_body_resource_reserved"
        bindings: tuple[BodyTargetBindingV1, ...] = ()
        capability = self._translation_capability
        if reason is None:
            if feedback is None or capability is None or preview.body_step is None or preview.body is None:
                raise RuntimeError("permitted translation lost its original geometry")
            planar = feedback.planar
            if planar is None or planar.position is None or planar.heading_degrees is None:
                raise RuntimeError("permitted translation has no current independent body basis")
            if (preview.body.sample_id, preview.body.event_tick, preview.body.frame_id, preview.body.heading_degrees) != (
                feedback.sample_id, feedback.event_tick, planar.frame_id, planar.heading_degrees,
            ) or preview.body.position != NavPointV1(*planar.position):
                raise ValueError("preview and authorization must use the same independent body acquisition")
            length = math.hypot(preview.body_step.x, preview.body_step.y)
            permitted = min(capability.maximum_step, capability.maximum_rate * self._tick_seconds * lease_ticks)
            if length > capability.tolerance and permitted <= capability.tolerance:
                reason = "insufficient_motion_budget"
            else:
                ratio = min(1.0, permitted / length) if length > 0.0 else 1.0
                sign = self._translation_mapping_sign
                offset = (preview.body_step.x * ratio * sign, preview.body_step.y * ratio * sign)
                target = BodyTranslationTargetV1(
                    f"body_target:planar_translation:{number}", 1, request.origin, feedback, offset,
                    capability.tolerance, capability.maximum_excursion, capability.maximum_rate, lease_ticks,
                )
                bindings = (BodyTargetBindingV1(target, capability),)
        withheld = () if reason is None else ((SensorimotorTargetKindV1.PLANAR_TRANSLATION, reason),)
        proposal = BodyTargetProposalV1(request, tick, bindings, withheld, replacing, preview)
        self._pending, self._proposal_number, self._last_tick = proposal, number, tick
        return proposal

    def propose_oral_reach(
        self, request: OralReachRequestV1, source: FeedingDetailNavMapStateV1 | None, *, at_tick: int,
    ) -> BodyTargetProposalV1:
        """Map one supplied feeding relation to the bounded existing scalar target path.

        The independently represented detail must be current and correspond to
        this body acquisition. A body-forward projection is calculated; lateral
        error or unavailable reach/heading is not silently repaired by a head
        turn, translation or world lookup. No target is reserved or installed.
        The source remains unchanged, and this geometric preview is not PNM.

        One optional oral capability is exclusive with all other movement in
        this first profile. A longer reachable distance may yield one bounded
        intermediate target; attaining that coordinate does not prove contact.
        New task authority is required for subsequent contributions.
        """
        tick = self._check_tick(at_tick)
        if not isinstance(request, OralReachRequestV1) or request.origin.stream != self._stream:
            raise ValueError("oral mapping requires its own typed request and generation")
        if tick > _MAX_INDEX - request.lease_ticks:
            raise ValueError("oral target expiry exceeds the finite clock")
        if source is not None:
            if not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self._stream or source.cutoff_tick != tick:
                raise ValueError("oral mapping requires the current generation/cutoff feeding source")
            if source.source_map_ref != request.source_map_ref or source.seed.detail_region_id != request.region_id:
                raise ValueError("oral request and source identify different represented regions")
        feedback = self._current_feedback(tick)
        number = _index(self._proposal_number + 1, "proposal number", 1)
        reason = None if source is not None and source.focal_accessible else "current_feeding_detail_unavailable"
        forward: float | None = None
        left: float | None = None
        if reason is None:
            reason = self._axis_refusal(SensorimotorTargetKindV1.ORAL_REACH, feedback)
        capability = self._capabilities.get(SensorimotorTargetKindV1.ORAL_REACH)
        bindings: tuple[BodyTargetBindingV1, ...] = ()
        if reason is None:
            if source is None or source.detail_position is None or feedback is None or capability is None:
                raise RuntimeError("oral mapping lost its admitted source/body/capability")
            planar, oral = feedback.planar, feedback.oral
            if planar is None or planar.position is None or planar.heading_degrees is None or oral is None or oral.extension_metres is None:
                raise RuntimeError("oral mapping lacks its independent measured axis")
            if source.frame_id != planar.frame_id:
                reason = "oral_source_frame_mismatch"
            elif (source.maternal.visual.sample_id, source.maternal.visual.event_tick) != (feedback.sample_id, feedback.event_tick):
                reason = "oral_source_body_acquisition_mismatch"
            else:
                dx, dy = source.detail_position.x - planar.position[0], source.detail_position.y - planar.position[1]
                angle = math.radians(planar.heading_degrees)
                forward, left = math.cos(angle) * dx + math.sin(angle) * dy, -math.sin(angle) * dx + math.cos(angle) * dy
                if abs(left) > 0.005 + _EPSILON:
                    reason = "oral_target_off_axis"
                elif not capability.minimum_coordinate - _EPSILON <= forward <= capability.maximum_coordinate + _EPSILON:
                    reason = "oral_target_out_of_reach"
                elif oral.contact is True and abs(forward - oral.extension_metres) > capability.tolerance + _EPSILON:
                    reason = "oral_contact_before_target"
                elif self.reservations(at_tick=tick):
                    reason = "incompatible_body_resource_reserved"
                else:
                    goal = max(capability.minimum_coordinate, min(capability.maximum_coordinate, forward))
                    step = min(capability.maximum_step, capability.maximum_rate * self._tick_seconds * request.lease_ticks)
                    if abs(goal - oral.extension_metres) > capability.tolerance and step <= capability.tolerance:
                        reason = "insufficient_motion_budget"
                    else:
                        offset = max(-step, min(step, goal - oral.extension_metres))
                        target = BodyRelativeTargetV1(f"body_target:oral_reach:{number}", 1, request.origin,
                                                     SensorimotorTargetKindV1.ORAL_REACH, feedback, offset,
                                                     capability.tolerance, capability.maximum_excursion,
                                                     capability.maximum_rate, request.lease_ticks)
                        bindings = (BodyTargetBindingV1(target, capability),)
        preview = OralReachPreviewV1(request, source, feedback, forward, left, reason or "geometry_only_not_authorized")
        withheld = () if reason is None else ((SensorimotorTargetKindV1.ORAL_REACH, reason),)
        proposal = BodyTargetProposalV1(request, tick, bindings, withheld, oral_preview=preview)
        self._pending, self._proposal_number, self._last_tick = proposal, number, tick
        return proposal

    def _make_binding(
        self, request: BodyMovementRequestV1, kind: SensorimotorTargetKindV1,
        goal: float, *, feedback: MotorFeedbackV1, number: int,
    ) -> BodyTargetBindingV1:
        """Calculate an anchored bounded increment, not a low-level drive command."""
        capability = self._capabilities[kind]
        coordinate = scalar_motor_coordinate_v1(feedback, kind)
        if coordinate is None:
            raise ValueError("required body coordinate is missing")
        bounded_goal = max(capability.minimum_coordinate, min(capability.maximum_coordinate, goal))
        travel_budget = capability.maximum_rate * self._tick_seconds * request.lease_ticks
        maximum_step = min(capability.maximum_step, travel_budget)
        offset = max(-maximum_step, min(maximum_step, bounded_goal - coordinate))
        if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST and self._orientation_mapping_sign == -1:
            # Explicit H6-B mapping fault: preserve the request and sensor basis,
            # reverse only the computed orientation adjustment inside normal limits.
            endpoint = max(capability.minimum_coordinate, min(capability.maximum_coordinate, coordinate - offset))
            offset = endpoint - coordinate
        target = BodyRelativeTargetV1(
            target_id=f"body_target:{kind.value}:{number}", revision=1, origin=request.origin, kind=kind,
            basis=feedback, offset=offset, tolerance=capability.tolerance,
            max_displacement=capability.maximum_excursion, max_rate=capability.maximum_rate,
            lease_ticks=request.lease_ticks,
        )
        return BodyTargetBindingV1(target, capability)

    def propose(
        self, request: BodyMovementRequestV1, *, at_tick: int, replace_existing: bool = False,
    ) -> BodyTargetProposalV1:
        """Map the supplied requirement; keep one pending proposal, occupy no resource.

        Refusal is per axis: missing tilt need not suppress a usable extension.
        A live reservation from another origin blocks both resources; BodyMap
        does not arbitrate between tasks. Each accepted target retains the same
        supplied origin. Narrowing is visible by comparing request and endpoint.
        A new proposal invalidates only the earlier unreserved proposal.
        H6 can explicitly propose replacement of the whole current envelope.
        The old resources stay reserved until reserve() atomically accepts usable
        new targets against that exact captured set. A refusal never cancels it.
        This parameter is not task selection or motor installation permission.
        """
        tick = self._check_tick(at_tick)
        if not isinstance(request, BodyMovementRequestV1):
            raise TypeError("request must be BodyMovementRequestV1")
        if request.origin.stream != self._stream:
            raise ValueError("task request has the wrong body stream or generation")
        if tick > _MAX_INDEX - request.lease_ticks:
            raise ValueError("insufficient tick range for this target lease")
        if not isinstance(replace_existing, bool):
            raise TypeError("replace_existing must be Boolean")
        number = _index(self._proposal_number + 1, "proposal number", 1)
        feedback = self._current_feedback(tick)
        live = self.reservations(at_tick=tick)
        replacing = live if replace_existing else ()
        continuing = () if replace_existing else live
        occupied = {item.current.target.kind for item in continuing}
        foreign_origin = any(item.current.target.origin != request.origin for item in continuing)
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
            if reason is None and occupied.intersection({SensorimotorTargetKindV1.PLANAR_TRANSLATION, SensorimotorTargetKindV1.ORAL_REACH}):
                reason = "incompatible_body_resource_reserved"
            if reason is None and kind in occupied:
                reason = "resource_already_reserved"
            if reason is not None:
                withheld.append((kind, reason))
            else:
                if feedback is None:
                    raise RuntimeError("accepted mapping lost its current feedback")
                bindings.append(self._make_binding(request, kind, goal, feedback=feedback, number=number))
        proposal = BodyTargetProposalV1(request, tick, tuple(bindings), tuple(withheld), replacing)
        self._pending = proposal
        self._proposal_number = number
        self._last_tick = tick
        return proposal

    def reserve(
        self, proposal: BodyTargetProposalV1, *, execution_id: str, at_tick: int,
    ) -> tuple[BodyTargetReservationV1, ...]:
        """Reserve proposed body resources for the separately authorized execution path.

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
        if (proposal.visual_preview is not None or proposal.oral_preview is not None) and tick != proposal.created_tick:
            raise ValueError("scene-directed target must commit at its original reviewed visual cutoff")
        feedback = self._current_feedback(tick)
        live = self.reservations(at_tick=tick)
        if proposal.replaces:
            if len(live) != len(proposal.replaces) or any(old is not current for old, current in zip(proposal.replaces, live)):
                raise ValueError("replacement no longer names the exact current reservation set")
            if tick != proposal.created_tick:
                raise ValueError("replacement must be committed at its reviewed boundary")
            live = ()
        if any(item.current.target.origin != proposal.request.origin or item.current.execution_id != execution for item in live):
            raise ValueError("resources belong to another task, envelope or execution")
        occupied = {item.current.target.kind for item in live}
        proposed_kinds = {binding.target.kind for binding in proposal.bindings}
        if SensorimotorTargetKindV1.ORAL_REACH in occupied | proposed_kinds and len(live) + len(proposal.bindings) != 1:
            raise ValueError("oral reach excludes simultaneous support or locomotor targets")
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
        if current.kind is SensorimotorTargetKindV1.ORAL_REACH:
            raise ValueError("oral target changes require a new source mapping and authorization")
        if not isinstance(initial, BodyRelativeTargetV1) or not isinstance(current, BodyRelativeTargetV1):
            raise ValueError("translation changes require a new task authorization, not scalar refinement")
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
        if not isinstance(capability, BodyAxisCapabilityV1):
            raise TypeError("scalar refinement requires scalar capability")
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
