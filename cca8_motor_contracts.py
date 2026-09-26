#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Neutral motor-command and sensed-feedback contracts for Planning-v18 H1.

These immutable records describe one command interval and one physical sensor
acquisition. They neither move a body nor create a clock, task, target, NavMap or
live permission. The future external provider and NCA8 may share these types
without importing one another's implementation. The existing support v1 packet
and binary stand-up provider are deliberately not changed.

The enhanced frame represents signed planar tilt from upright, in degrees, and
one normalized aggregate support-extension coordinate. Extension is an actuator
coordinate, not useful loading. Optional measurements preserve missingness;
valid ``support_contact=False`` is different from no report or an absent channel.
Event ticks and availability ticks use one external simulation timebase. A
consumer must check its own stream, generation, clock and previously used IDs.

Boundary decoders reject unknown keys and malformed values rather than copying
privileged or unspecified data. Exported dictionaries are detached and JSON-safe;
decoding a dictionary does not restore an installed execution or an old receipt.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass, field, replace

__version__ = "0.8.0"
__all__ = [
    "BodyBearingFeedbackV1",
    "MOTOR_COMMAND_SCHEMA_V1",
    "MOTOR_FEEDBACK_SCHEMA_V1",
    "MOTOR_FRAME_V1",
    "PlanarDriveV1", "PlanarFeedbackV1", "OralFeedbackV1", "OralSealFeedbackV1", "OralExtractionFeedbackV1",
    "FeedingDeficitFeedbackV1",
    "MotorCommandV1",
    "MotorFeedbackV1",
    "MotorStreamRefV1",
    "admit_motor_feedback_batch_v1",
    "__version__",
]

MOTOR_COMMAND_SCHEMA_V1 = "body_motor_command_v1"
MOTOR_FEEDBACK_SCHEMA_V1 = "body_motor_feedback_v1"
MOTOR_FRAME_V1 = "gravity_surface_planar_v1"
_MAX_INTEGER = 2**63 - 1


def _integer(value: object, name: str, *, minimum: int = 0) -> int:
    """Validate a bounded non-Boolean counter, without coercing floats or text."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} must be a non-Boolean integer")
    if not minimum <= value <= _MAX_INTEGER:
        raise ValueError(f"{name} must be between {minimum} and {_MAX_INTEGER}")
    return value


def _identifier(value: object, name: str) -> str:
    """Normalize a short nonempty identifier; reject embedded control characters."""
    if not isinstance(value, str):
        raise TypeError(f"{name} must be a string")
    normalized = value.strip()
    if not normalized or len(normalized) > 120 or any(ord(char) < 32 for char in normalized):
        raise ValueError(f"{name} must contain 1-120 non-control characters")
    return normalized


def _number(value: object, name: str, lower: float, upper: float) -> float:
    """Accept finite Python numeric values in range, but not Boolean substitutes."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} must be a non-Boolean number")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} must be finite") from exc
    if not math.isfinite(result) or not lower <= result <= upper:
        raise ValueError(f"{name} must be finite and between {lower} and {upper}")
    return result


def _optional_number(value: object, name: str, lower: float, upper: float) -> float | None:
    """Preserve a missing measured channel instead of replacing it with zero."""
    return None if value is None else _number(value, name, lower, upper)


def _fields(value: object, expected: frozenset[str]) -> dict[str, object]:
    """Detach a small exact-schema mapping without accepting additional fields."""
    if not isinstance(value, Mapping):
        raise TypeError("motor packet must be a mapping")
    if len(value) != len(expected):
        raise ValueError("motor packet fields do not match the exact schema")
    result: dict[str, object] = {}
    for key, item in value.items():
        if not isinstance(key, str) or key not in expected:
            raise ValueError("motor packet contains an unknown field")
        result[key] = item
    if set(result) != expected:
        raise ValueError("motor packet is missing a required field")
    return result


@dataclass(frozen=True, slots=True)
class MotorStreamRefV1:
    """Identify one body/sensor stream in one reset generation.

    ``stream_id`` is supplied by the owning session/provider, not generated here.
    Separate live instances must use separate stream IDs; resetting an instance
    increments its generation. A matching description is still not an ownership
    token, and it cannot authorize installation or replay of an execution.
    """

    stream_id: str
    generation: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "stream_id", _identifier(self.stream_id, "stream_id"))
        _integer(self.generation, "generation", minimum=1)

    def as_dict(self) -> dict[str, object]:
        """Return a detached identity description, not a live session handle."""
        return {"stream_id": self.stream_id, "generation": self.generation}

    @classmethod
    def from_dict(cls, value: object) -> MotorStreamRefV1:
        """Decode exactly the two identity fields, raising on invalid input."""
        packet = _fields(value, frozenset({"stream_id", "generation"}))
        return cls(_identifier(packet["stream_id"], "stream_id"), _integer(packet["generation"], "generation", minimum=1))


def _pair(value: object, name: str, bound: float) -> tuple[float, float]:
    """Validate an immutable finite XY pair, not a mutable alias or a Boolean."""
    if not isinstance(value, tuple) or len(value) != 2:
        raise TypeError(f"{name} must be an immutable pair")
    return (_number(value[0], name, -bound, bound), _number(value[1], name, -bound, bound))


@dataclass(frozen=True, slots=True)
class PlanarDriveV1:
    """Optional horizontal drive in the body's current forward/left frame.

    The vector's Euclidean norm is at most one. The fixed translation provider
    interprets norm one as one metre/second under its stated traction conditions.
    This is an increment request, not an environmental destination, heading
    command, entity handle or target. The original two support drives remain
    independent. No heading is fabricated from gravity-relative tilt.
    """

    forward: float
    left: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "forward", _number(self.forward, "forward drive", -1.0, 1.0))
        object.__setattr__(self, "left", _number(self.left, "left drive", -1.0, 1.0))
        if math.hypot(self.forward, self.left) > 1.0 + 1e-12:
            raise ValueError("translation drive magnitude exceeds one")

    def as_dict(self) -> dict[str, object]:
        """Return the two motor channels, without a destination or task label."""
        return {"forward": self.forward, "left": self.left}

    @classmethod
    def from_dict(cls, value: object) -> PlanarDriveV1:
        """Decode the exact drive pair; reject additional or missing fields."""
        packet = _fields(value, frozenset({"forward", "left"}))
        return cls(_number(packet["forward"], "forward drive", -1, 1), _number(packet["left"], "left drive", -1, 1))


@dataclass(frozen=True, slots=True)
class PlanarFeedbackV1:
    """Optional horizontal measurements inside the SAME motor sensor acquisition.

    The enclosing MotorFeedbackV1 supplies the only stream/sample/event/arrival
    header. Position is an immutable XY metre pair; yaw is counterclockwise from
    the named scene's +X axis. Obstacle contact is distinct from ground support.
    Each channel may be unknown. These fields cannot grant actuator permission,
    identify the desired object, infer a maternal relation or report success.
    """

    frame_id: str
    position: tuple[float, float] | None
    heading_degrees: float | None
    obstacle_contact: bool | None

    def __post_init__(self) -> None:
        frame = _identifier(self.frame_id, "planar frame")
        if frame != self.frame_id or not frame.startswith("scene_xy:") or len(frame) <= len("scene_xy:"):
            raise ValueError("planar feedback needs an explicit unpadded scene_xy: metre frame")
        if any(not (char.isascii() and (char.isalnum() or char in "_:.-/")) for char in frame) or len(frame) > 80:
            raise ValueError("unsupported planar frame characters or length")
        if self.position is not None:
            object.__setattr__(self, "position", _pair(self.position, "planar position", 10000.0))
        object.__setattr__(self, "heading_degrees", _optional_number(self.heading_degrees, "heading", -180.0, 180.0))
        if self.obstacle_contact is not None and not isinstance(self.obstacle_contact, bool):
            raise TypeError("obstacle contact must be Boolean or unknown")

    def as_dict(self) -> dict[str, object]:
        """Export measured geometry; the enclosing record retains acquisition time."""
        return {"frame_id": self.frame_id, "position": None if self.position is None else list(self.position),
                "heading_degrees": self.heading_degrees, "obstacle_contact": self.obstacle_contact}

    @classmethod
    def from_dict(cls, value: object) -> PlanarFeedbackV1:
        """Decode the exact optional geometry; never repair missing localization."""
        packet = _fields(value, frozenset({"frame_id", "position", "heading_degrees", "obstacle_contact"}))
        raw = packet["position"]
        position = None
        if raw is not None:
            if not isinstance(raw, (list, tuple)) or len(raw) != 2:
                raise TypeError("wire position needs two coordinates")
            position = _pair(tuple(raw), "wire position", 10000.0)
        contact = packet["obstacle_contact"]
        if contact is not None and not isinstance(contact, bool):
            raise TypeError("wire obstacle contact must be Boolean or unknown")
        return cls(_identifier(packet["frame_id"], "frame_id"), position,
                   _optional_number(packet["heading_degrees"], "heading", -180, 180), contact)


@dataclass(frozen=True, slots=True)
class OralFeedbackV1:
    """Measured body-forward reach and independent touch in the same acquisition.

    This optional v3 facet has no sample clock of its own. The enclosing motor
    record supplies event, availability and generation. Reach is metres along
    the body's forward axis, not body translation or a selected destination.
    Contact is sensed proximity in the declared physical surrogate; it does not
    identify a nipple, imply a latch, or establish milk transfer. Each channel
    can be unknown. Missing contact must never be substituted with False.
    """

    extension_metres: float | None
    contact: bool | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "extension_metres", _optional_number(self.extension_metres, "oral extension", 0.0, 0.35))
        if self.contact is not None and not isinstance(self.contact, bool):
            raise TypeError("oral contact must be Boolean or unknown")

    def as_dict(self) -> dict[str, object]:
        """Describe two measured channels, without task or feeding-success fields."""
        return {"frame_id": "body_forward_oral_v1", "units": "metres",
                "extension_metres": self.extension_metres, "contact": self.contact}

    @classmethod
    def from_dict(cls, value: object) -> OralFeedbackV1:
        """Decode the exact body-forward facet; reject wrong units or added answers."""
        packet = _fields(value, frozenset({"frame_id", "units", "extension_metres", "contact"}))
        if packet["frame_id"] != "body_forward_oral_v1" or packet["units"] != "metres":
            raise ValueError("unsupported oral frame or units")
        contact = packet["contact"]
        if contact is not None and not isinstance(contact, bool):
            raise TypeError("oral contact must be Boolean or unknown")
        return cls(_optional_number(packet["extension_metres"], "oral extension", 0.0, 0.35), contact)


@dataclass(frozen=True, slots=True)
class OralSealFeedbackV1:
    """Measured aggregate closure and seal, never a selected feeding milestone.

    Closure is a normalized actuator coordinate in [0, 1]; sealed is a separate
    sensed physical relation. Neither channel supplies nipple identity, milk or
    nourishment. The enclosing v4 acquisition supplies time and stream identity.
    Missing channels remain None, and potentially inconsistent measurements are
    not silently repaired by this transport contract.
    """

    closure: float | None
    sealed: bool | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "closure", _optional_number(self.closure, "oral closure", 0.0, 1.0))
        if self.sealed is not None and not isinstance(self.sealed, bool):
            raise TypeError("oral seal must be Boolean or unknown")

    def as_dict(self) -> dict[str, object]:
        """Export actual channels, with no action rights or inferred task success."""
        return {"frame_id": "aggregate_oral_closure_v1", "units": "normalized", "closure": self.closure, "sealed": self.sealed}

    @classmethod
    def from_dict(cls, value: object) -> OralSealFeedbackV1:
        """Decode only the stated facet; refuse extra identity or success answers."""
        packet = _fields(value, frozenset({"frame_id", "units", "closure", "sealed"}))
        if packet["frame_id"] != "aggregate_oral_closure_v1" or packet["units"] != "normalized":
            raise ValueError("unsupported oral closure frame or units")
        sealed = packet["sealed"]
        if sealed is not None and not isinstance(sealed, bool):
            raise TypeError("oral seal must be Boolean or unknown")
        return cls(_optional_number(packet["closure"], "oral closure", 0.0, 1.0), sealed)


@dataclass(frozen=True, slots=True)
class OralExtractionFeedbackV1:
    """Optional v5 aggregate stroke and milk measured over one physical interval.

    Stroke is a normalized physical coordinate, not a requested motor target.
    ``milk_transferred_units`` is volume entering the mouth during the named
    interval, in explicitly uncalibrated model units; it is not supply, cumulative
    consumption, swallowing, nourishment or a task verdict. A known zero is
    distinct from None. The enclosing MotorFeedbackV1 supplies the sole stream,
    sample, event and availability header and checks that this interval ends at
    that event. An acquisition at reset has no prior interval: its start and
    measured milk are both None, even when the stroke coordinate is observable.

    This immutable transport record does not repair contradictory channels,
    create a clock, resample experience, authorize extraction or assign credit.
    """

    stroke: float | None
    milk_transferred_units: float | None
    interval_start_tick: int | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "stroke", _optional_number(self.stroke, "extraction stroke", 0.0, 1.0))
        object.__setattr__(self, "milk_transferred_units",
                           _optional_number(self.milk_transferred_units, "interval milk", 0.0, 1.0))
        if self.interval_start_tick is None:
            if self.milk_transferred_units is not None:
                raise ValueError("no prior interval cannot contain measured transfer")
        elif _integer(self.interval_start_tick, "extraction interval start") == _MAX_INTEGER:
            raise ValueError("extraction interval must leave room for its endpoint")

    def as_dict(self) -> dict[str, object]:
        """Describe the measured interval without exposing reservoir or task data."""
        return {"frame_id": "aggregate_oral_extraction_v1", "stroke_units": "normalized",
                "milk_units": "model_volume_units", "stroke": self.stroke,
                "milk_transferred_units": self.milk_transferred_units, "interval_start_tick": self.interval_start_tick}

    @classmethod
    def from_dict(cls, value: object) -> OralExtractionFeedbackV1:
        """Decode the exact facet; missing values require explicit None channels."""
        packet = _fields(value, frozenset({"frame_id", "stroke_units", "milk_units", "stroke",
                                          "milk_transferred_units", "interval_start_tick"}))
        if (packet["frame_id"] != "aggregate_oral_extraction_v1" or packet["stroke_units"] != "normalized"
                or packet["milk_units"] != "model_volume_units"):
            raise ValueError("unsupported extraction frame or units")
        start = packet["interval_start_tick"]
        return cls(_optional_number(packet["stroke"], "extraction stroke", 0.0, 1.0),
                   _optional_number(packet["milk_transferred_units"], "interval milk", 0.0, 1.0),
                   None if start is None else _integer(start, "extraction interval start"))


@dataclass(frozen=True, slots=True)
class FeedingDeficitFeedbackV1:
    """One measured synthetic body-deficit channel, not a task-completion flag.

    The enclosing MotorFeedbackV1 supplies acquisition identity and timing. None
    explicitly means unavailable, never zero need. Units are a declared physical
    surrogate, not calories, biological hunger, reward, or permission to Rest.
    No private intake pool, supply reservoir or evaluator result is transported.
    """

    deficit_units: float | None

    def __post_init__(self) -> None:
        object.__setattr__(self, "deficit_units", _optional_number(self.deficit_units, "feeding deficit", 0.0, 8.0))

    def as_dict(self) -> dict[str, object]:
        """Detach the single measured channel, retaining explicit unknown evidence."""
        return {"deficit_units": self.deficit_units, "units": "synthetic_feeding_deficit"}

    @classmethod
    def from_dict(cls, value: object) -> FeedingDeficitFeedbackV1:
        """Reject undeclared fields and units rather than accept a supplied fed flag."""
        packet = _fields(value, frozenset({"deficit_units", "units"}))
        if packet["units"] != "synthetic_feeding_deficit":
            raise ValueError("unsupported feeding-deficit units")
        return cls(_optional_number(packet["deficit_units"], "feeding deficit", 0.0, 8.0))


@dataclass(frozen=True, slots=True)
class BodyBearingFeedbackV1:
    """Measured body-ground contact and normalized bearing, not limb competence.

    This independent optional body facet supplies neither a resting label nor
    task success. Both measurements may be unavailable. Contradictions remain
    visible to the body/source owner rather than being repaired at transport.
    The enclosing MotorFeedbackV1 supplies original stream and acquisition time.
    """

    contact: bool | None
    bearing: float | None

    def __post_init__(self) -> None:
        if self.contact is not None and not isinstance(self.contact, bool):
            raise TypeError("body contact requires Boolean or unavailable")
        object.__setattr__(self, "bearing", _optional_number(self.bearing, "body bearing", 0.0, 1.0))

    def as_dict(self) -> dict[str, object]:
        """Export measurements only; this value cannot authorize any action."""
        return {"contact": self.contact, "bearing": self.bearing, "units": "normalized_body_bearing"}

    @classmethod
    def from_dict(cls, value: object) -> BodyBearingFeedbackV1:
        """Decode the exact body-bearing seam without accepting evaluator fields."""
        packet = _fields(value, frozenset({"contact", "bearing", "units"}))
        if packet["units"] != "normalized_body_bearing":
            raise ValueError("unsupported body-bearing units")
        contact = packet["contact"]
        if contact is not None and not isinstance(contact, bool):
            raise TypeError("body contact requires Boolean or unavailable")
        return cls(contact, _optional_number(packet["bearing"], "body bearing", 0.0, 1.0))


@dataclass(frozen=True, slots=True)
class MotorCommandV1:
    """Signed normalized drives for one external interval [tick, tick+1).

    ``issued_tick`` names the beginning of that interval. A future provider
    validates it against its actual clock before advancing the body once.
    Command numbers increase within a stream generation; gaps are permissible,
    duplicate/reversed numbers are not. Neither a task label nor a desired body
    endpoint belongs in this motor record. Zero drives are neutral input, not a
    promise that passive physics stops or that support is safe. The opt-in v3
    oral_drive is normalized body-forward reach velocity (0.5 metres/s at one),
    not a seek/latch/suckle command. The v4 oral_closure_drive independently
    changes normalized closure (2 units/s at one), without requesting a seal.
    The independent opt-in v5 oral_extraction_drive requests aggregate stroke
    velocity, not a seal, milk quantity or feeding goal. Its first provider uses
    2 normalized units/s at drive one. Old v1-v4 exports remain unchanged when
    the newer optional drives are absent. No drive confers execution permission.
    """

    stream: MotorStreamRefV1
    command_id: int
    issued_tick: int
    orientation_drive: float = 0.0
    extension_drive: float = 0.0
    translation: PlanarDriveV1 | None = field(default=None, kw_only=True)
    oral_drive: float | None = field(default=None, kw_only=True)
    oral_closure_drive: float | None = field(default=None, kw_only=True)
    oral_extraction_drive: float | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        object.__setattr__(self, "oral_extraction_drive",
                           _optional_number(self.oral_extraction_drive, "oral extraction drive", -1.0, 1.0))
        object.__setattr__(self, "oral_drive", _optional_number(self.oral_drive, "oral drive", -1.0, 1.0))
        object.__setattr__(self, "oral_closure_drive", _optional_number(self.oral_closure_drive, "oral closure drive", -1.0, 1.0))
        if self.translation is not None and not isinstance(self.translation, PlanarDriveV1):
            raise TypeError("translation must be PlanarDriveV1 or None")
        _integer(self.command_id, "command_id", minimum=1)
        tick = _integer(self.issued_tick, "issued_tick")
        if tick == _MAX_INTEGER:
            raise ValueError("issued_tick must leave room for the interval endpoint")
        object.__setattr__(self, "orientation_drive", _number(self.orientation_drive, "orientation_drive", -1.0, 1.0))
        object.__setattr__(self, "extension_drive", _number(self.extension_drive, "extension_drive", -1.0, 1.0))

    @property
    def is_neutral(self) -> bool:
        """Return whether every supplied drive is zero, without implying safety."""
        return (self.orientation_drive == 0.0 and self.extension_drive == 0.0
                and (self.translation is None or (self.translation.forward == 0.0 and self.translation.left == 0.0))
                and (self.oral_drive is None or self.oral_drive == 0.0)
                and (self.oral_closure_drive is None or self.oral_closure_drive == 0.0)
                and (self.oral_extraction_drive is None or self.oral_extraction_drive == 0.0))

    def validate_for_update(self, *, stream: MotorStreamRefV1, now_tick: int, previous_command_id: int) -> None:
        """Check caller-supplied ownership/time/ordering without applying anything.

        A provider must supply its own trusted current values, update its command
        watermark before a possible side effect, and handle ambiguous failures.
        This pure check cannot supply exactly-once delivery or prevent an owner
        from deliberately passing a false watermark. Every failure raises before
        a provider should alter physical state or advance time.
        """
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("expected stream must be MotorStreamRefV1")
        tick = _integer(now_tick, "now_tick")
        previous = _integer(previous_command_id, "previous_command_id")
        if self.stream != stream:
            raise ValueError("motor command has the wrong stream or generation")
        if self.issued_tick != tick:
            raise ValueError("motor command does not belong to the current interval")
        if self.command_id <= previous:
            raise ValueError("motor command is duplicate or out of order")

    def as_dict(self) -> dict[str, object]:
        """Return the exact detached wire schema with no cognitive task fields."""
        return {
            "schema": ("body_motor_command_v5" if self.oral_extraction_drive is not None else
                       "body_motor_command_v4" if self.oral_closure_drive is not None else
                       "body_motor_command_v3" if self.oral_drive is not None else
                       MOTOR_COMMAND_SCHEMA_V1 if self.translation is None else "body_motor_command_v2"),
            "stream": self.stream.as_dict(),
            "command_id": self.command_id,
            "issued_tick": self.issued_tick,
            "orientation_drive": self.orientation_drive,
            "extension_drive": self.extension_drive,
            **({"translation": None if self.translation is None else self.translation.as_dict(), "oral_drive": self.oral_drive}
               if self.oral_drive is not None or self.oral_closure_drive is not None or self.oral_extraction_drive is not None
               else {"translation": self.translation.as_dict()} if self.translation is not None else {}),
            **({"oral_closure_drive": self.oral_closure_drive}
               if self.oral_closure_drive is not None or self.oral_extraction_drive is not None else {}),
            **({"oral_extraction_drive": self.oral_extraction_drive} if self.oral_extraction_drive is not None else {}),
        }

    @classmethod
    def from_dict(cls, value: object) -> MotorCommandV1:
        """Strictly decode a command description; do not execute or authorize it."""
        extraction = isinstance(value, Mapping) and value.get("schema") == "body_motor_command_v5"
        closure = extraction or isinstance(value, Mapping) and value.get("schema") == "body_motor_command_v4"
        oral = closure or isinstance(value, Mapping) and value.get("schema") == "body_motor_command_v3"
        extended = oral or isinstance(value, Mapping) and value.get("schema") == "body_motor_command_v2"
        fields = {"schema", "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive"}
        packet = _fields(value, frozenset(fields | ({"translation"} if extended else set()) | ({"oral_drive"} if oral else set())
                                          | ({"oral_closure_drive"} if closure else set())
                                          | ({"oral_extraction_drive"} if extraction else set())))
        schema = "body_motor_command_v5" if extraction else "body_motor_command_v4" if closure else "body_motor_command_v3" if oral else (
            "body_motor_command_v2" if extended else MOTOR_COMMAND_SCHEMA_V1)
        if packet["schema"] != schema:
            raise ValueError("unsupported motor command schema")
        return cls(
            stream=MotorStreamRefV1.from_dict(packet["stream"]),
            command_id=_integer(packet["command_id"], "command_id", minimum=1),
            issued_tick=_integer(packet["issued_tick"], "issued_tick"),
            orientation_drive=_number(packet["orientation_drive"], "orientation_drive", -1.0, 1.0),
            extension_drive=_number(packet["extension_drive"], "extension_drive", -1.0, 1.0),
            translation=PlanarDriveV1.from_dict(packet["translation"]) if extended and (not oral or packet["translation"] is not None) else None,
            oral_drive=(_optional_number(packet["oral_drive"], "oral drive", -1.0, 1.0) if closure else
                        _number(packet["oral_drive"], "oral drive", -1.0, 1.0) if oral else None),
            oral_closure_drive=(_optional_number(packet["oral_closure_drive"], "oral closure drive", -1.0, 1.0) if extraction else
                                _number(packet["oral_closure_drive"], "oral closure drive", -1.0, 1.0) if closure else None),
            oral_extraction_drive=_number(packet["oral_extraction_drive"], "oral extraction drive", -1.0, 1.0) if extraction else None,
        )


@dataclass(frozen=True, slots=True)
class MotorFeedbackV1:
    """One canonical sensed body event, with explicit time and missing channels.

    Tilt is signed from upright in ``gravity_surface_planar_v1``. It cannot be
    recovered uniquely from the old unsigned support angle. The aggregate
    extension, useful loading and destabilization channels lie in [0, 1] but
    mean different things. Contact is strictly Boolean or missing; numeric zero
    is not a Boolean report. Contradictory measured channels are not silently
    repaired here, since this boundary is not a physics or task-success oracle.

    ``event_tick`` names when the described physical acquisition occurred;
    ``available_tick`` names its earliest usable time. Delays do not relabel the
    event. Equality is permitted for an explicitly immediate/reset acquisition;
    the H2 provider, not this general record, enforces its nominal sensor delay.
    Sample IDs must be tracked by each consuming owner to prevent duplicate
    confirmation. This class contains no mutable history and no probability.
    """

    stream: MotorStreamRefV1
    sample_id: int
    event_tick: int
    available_tick: int
    body_tilt_degrees: float | None
    support_extension: float | None
    support_contact: bool | None
    useful_loading: float | None
    destabilization: float | None
    frame_id: str = MOTOR_FRAME_V1
    planar: PlanarFeedbackV1 | None = field(default=None, kw_only=True)
    oral: OralFeedbackV1 | None = field(default=None, kw_only=True)
    oral_seal: OralSealFeedbackV1 | None = field(default=None, kw_only=True)
    oral_extraction: OralExtractionFeedbackV1 | None = field(default=None, kw_only=True)
    feeding_deficit: FeedingDeficitFeedbackV1 | None = field(default=None, kw_only=True)
    body_bearing: BodyBearingFeedbackV1 | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        if self.body_bearing is not None and not isinstance(self.body_bearing, BodyBearingFeedbackV1):
            raise TypeError("body bearing requires its independent typed measurement facet")
        if self.feeding_deficit is not None and (not isinstance(self.feeding_deficit, FeedingDeficitFeedbackV1)
                                                or self.oral_extraction is None):
            raise TypeError("feeding deficit requires its typed facet and declared extraction/body context")
        if self.oral_extraction is not None and (not isinstance(self.oral_extraction, OralExtractionFeedbackV1) or self.oral_seal is None):
            raise TypeError("extraction feedback requires its typed facet and the seal sensing context")
        if self.oral_seal is not None and (not isinstance(self.oral_seal, OralSealFeedbackV1) or self.oral is None):
            raise TypeError("seal feedback requires its typed facet and the oral sensing context")
        if self.oral is not None and (not isinstance(self.oral, OralFeedbackV1) or self.planar is None):
            raise TypeError("oral feedback requires its typed facet and a planar body frame")
        if self.planar is not None and not isinstance(self.planar, PlanarFeedbackV1):
            raise TypeError("planar must be PlanarFeedbackV1 or None")
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        _integer(self.sample_id, "sample_id", minimum=1)
        event = _integer(self.event_tick, "event_tick")
        available = _integer(self.available_tick, "available_tick")
        if self.oral_extraction is not None:
            expected_start = None if event == 0 else event - 1
            if self.oral_extraction.interval_start_tick != expected_start:
                raise ValueError("extraction measurement must describe the enclosing event's single preceding interval")
        if available < event:
            raise ValueError("feedback cannot be available before its physical event")
        if not isinstance(self.frame_id, str) or self.frame_id != MOTOR_FRAME_V1:
            raise ValueError("unsupported enhanced motor frame")
        object.__setattr__(self, "body_tilt_degrees", _optional_number(self.body_tilt_degrees, "body_tilt_degrees", -90.0, 90.0))
        for name in ("support_extension", "useful_loading", "destabilization"):
            object.__setattr__(self, name, _optional_number(getattr(self, name), name, 0.0, 1.0))
        if self.support_contact is not None and not isinstance(self.support_contact, bool):
            raise TypeError("support_contact must be Boolean or None")

    def validate_available(self, *, stream: MotorStreamRefV1, at_tick: int) -> None:
        """Reject wrong-generation or future feedback without making it current.

        Availability is necessary but not sufficient for a consumer's freshness,
        sample-order, capability or task-specific evidence policy. An old sample
        does not become new merely because this check is called again.
        """
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("expected stream must be MotorStreamRefV1")
        tick = _integer(at_tick, "at_tick")
        if self.stream != stream:
            raise ValueError("motor feedback has the wrong stream or generation")
        if self.available_tick > tick:
            raise ValueError("motor feedback is not yet available")

    def as_dict(self) -> dict[str, object]:
        """Return a detached JSON-safe sensor packet retaining original identity."""
        packet: dict[str, object] = {
            "schema": ("body_motor_feedback_v6" if self.feeding_deficit is not None else
                       "body_motor_feedback_v5" if self.oral_extraction is not None else
                       "body_motor_feedback_v4" if self.oral_seal is not None else
                       "body_motor_feedback_v3" if self.oral is not None else
                       MOTOR_FEEDBACK_SCHEMA_V1 if self.planar is None else "body_motor_feedback_v2"),
            "stream": self.stream.as_dict(),
            "sample_id": self.sample_id,
            "event_tick": self.event_tick,
            "available_tick": self.available_tick,
            "frame_id": self.frame_id,
            **({"planar": self.planar.as_dict()} if self.planar is not None else {}),
            **({"oral": self.oral.as_dict()} if self.oral is not None else {}),
            **({"oral_seal": self.oral_seal.as_dict()} if self.oral_seal is not None else {}),
            **({"oral_extraction": self.oral_extraction.as_dict()} if self.oral_extraction is not None else {}),
            **({"feeding_deficit": self.feeding_deficit.as_dict()} if self.feeding_deficit is not None else {}),
            "angle_units": "degrees",
            "extension_units": "normalized",
            "body_tilt_degrees": self.body_tilt_degrees,
            "support_extension": self.support_extension,
            "support_contact": self.support_contact,
            "useful_loading": self.useful_loading,
            "destabilization": self.destabilization,
        }
        if self.body_bearing is not None:
            packet.update(base_schema=packet["schema"], schema="body_motor_feedback_v7", body_bearing=self.body_bearing.as_dict())
        return packet

    @classmethod
    def from_dict(cls, value: object) -> MotorFeedbackV1:
        """Decode only the declared enhanced schema; never infer missing fields.

        All keys must be present, although measured channel values may be None.
        This distinguishes an explicitly unavailable measurement from an invalid
        packet shape. Unknown task, policy, outcome and scenario keys are errors.
        No raw mapping is retained, and changing it later cannot mutate a record.
        """
        if isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v7":
            base_schema = value.get("base_schema")
            if base_schema not in {MOTOR_FEEDBACK_SCHEMA_V1, *(f"body_motor_feedback_v{n}" for n in range(2, 7))}:
                raise ValueError("body-bearing packet requires a declared v1-v6 base schema")
            if "body_bearing" not in value:
                raise ValueError("body-bearing measurement is missing")
            base = {key: item for key, item in value.items() if key not in {"base_schema", "body_bearing"}}
            base["schema"] = base_schema
            original = cls.from_dict(base)
            return replace(original, body_bearing=BodyBearingFeedbackV1.from_dict(value["body_bearing"]))
        feeding = isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v6"
        extraction = feeding or isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v5"
        seal = extraction or isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v4"
        oral = seal or isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v3"
        extended = oral or isinstance(value, Mapping) and value.get("schema") == "body_motor_feedback_v2"
        packet = _fields(value, frozenset({
            "schema", "stream", "sample_id", "event_tick", "available_tick", "frame_id", "angle_units", "extension_units",
            "body_tilt_degrees", "support_extension", "support_contact", "useful_loading", "destabilization",
        } | ({"planar"} if extended else set()) | ({"oral"} if oral else set()) | ({"oral_seal"} if seal else set())
            | ({"oral_extraction"} if extraction else set()) | ({"feeding_deficit"} if feeding else set())))
        schema = "body_motor_feedback_v6" if feeding else "body_motor_feedback_v5" if extraction else "body_motor_feedback_v4" if seal else "body_motor_feedback_v3" if oral else (
            "body_motor_feedback_v2" if extended else MOTOR_FEEDBACK_SCHEMA_V1)
        if packet["schema"] != schema:
            raise ValueError("unsupported motor feedback schema")
        if packet["angle_units"] != "degrees" or packet["extension_units"] != "normalized":
            raise ValueError("unsupported enhanced motor units")
        frame = packet["frame_id"]
        if not isinstance(frame, str) or frame != MOTOR_FRAME_V1:
            raise ValueError("unsupported enhanced motor frame")
        contact = packet["support_contact"]
        if contact is not None and not isinstance(contact, bool):
            raise TypeError("support_contact must be Boolean or None")
        return cls(
            stream=MotorStreamRefV1.from_dict(packet["stream"]),
            sample_id=_integer(packet["sample_id"], "sample_id", minimum=1),
            event_tick=_integer(packet["event_tick"], "event_tick"),
            available_tick=_integer(packet["available_tick"], "available_tick"),
            frame_id=frame,
            planar=PlanarFeedbackV1.from_dict(packet["planar"]) if extended else None,
            oral=OralFeedbackV1.from_dict(packet["oral"]) if oral else None,
            oral_seal=OralSealFeedbackV1.from_dict(packet["oral_seal"]) if seal else None,
            oral_extraction=OralExtractionFeedbackV1.from_dict(packet["oral_extraction"]) if extraction else None,
            feeding_deficit=FeedingDeficitFeedbackV1.from_dict(packet["feeding_deficit"]) if feeding else None,
            body_tilt_degrees=_optional_number(packet["body_tilt_degrees"], "body_tilt_degrees", -90.0, 90.0),
            support_extension=_optional_number(packet["support_extension"], "support_extension", 0.0, 1.0),
            support_contact=contact,
            useful_loading=_optional_number(packet["useful_loading"], "useful_loading", 0.0, 1.0),
            destabilization=_optional_number(packet["destabilization"], "destabilization", 0.0, 1.0),
        )


def admit_motor_feedback_batch_v1(
    delivered: tuple[MotorFeedbackV1, ...], previous: MotorFeedbackV1, *, stream: MotorStreamRefV1, at_tick: int,
) -> MotorFeedbackV1:
    """Validate/detach one bounded delivered batch without resampling a physical event.

    H4 and H6 share this input boundary. Delayed older acquisitions cannot replace
    newer current evidence. A repeated identity must have identical content;
    inconsistent identity/time ordering or future/foreign input raises before
    replacing anything. Empty delivery preserves the old record and its old age,
    not fresh support. The caller owns stop-on-fault policy after a physical call.
    This helper neither reads a world nor supplies missing channels from a PNM.
    """
    if not isinstance(previous, MotorFeedbackV1):
        raise TypeError("previous feedback must be MotorFeedbackV1")
    previous.validate_available(stream=stream, at_tick=at_tick)
    if not isinstance(delivered, tuple) or len(delivered) > 16:
        raise TypeError("physical provider must return a bounded sensor tuple")
    latest = previous
    for feedback in delivered:
        if not isinstance(feedback, MotorFeedbackV1):
            raise TypeError("physical provider returned a malformed sensor reading")
        feedback.validate_available(stream=stream, at_tick=at_tick)
        if feedback.sample_id == latest.sample_id:
            if feedback != latest:
                raise ValueError("a sensor identity was reused for changed content")
        elif feedback.sample_id < latest.sample_id and feedback.event_tick < latest.event_tick:
            continue
        elif feedback.sample_id <= latest.sample_id or feedback.event_tick <= latest.event_tick:
            raise ValueError("returned sensor identities and event times disagree")
        else:
            latest = feedback
    return MotorFeedbackV1.from_dict(latest.as_dict())
