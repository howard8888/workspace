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
from dataclasses import dataclass

__version__ = "0.1.0"
__all__ = [
    "MOTOR_COMMAND_SCHEMA_V1",
    "MOTOR_FEEDBACK_SCHEMA_V1",
    "MOTOR_FRAME_V1",
    "MotorCommandV1",
    "MotorFeedbackV1",
    "MotorStreamRefV1",
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


@dataclass(frozen=True, slots=True)
class MotorCommandV1:
    """Two signed normalized drives for one external interval [tick, tick+1).

    ``issued_tick`` names the beginning of that interval. A future provider
    validates it against its actual clock before advancing the body once.
    Command numbers increase within a stream generation; gaps are permissible,
    duplicate/reversed numbers are not. Neither a task label nor a desired body
    endpoint belongs in this motor record. Zero drives are neutral input, not a
    promise that passive physics stops or that support is safe.
    """

    stream: MotorStreamRefV1
    command_id: int
    issued_tick: int
    orientation_drive: float = 0.0
    extension_drive: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        _integer(self.command_id, "command_id", minimum=1)
        tick = _integer(self.issued_tick, "issued_tick")
        if tick == _MAX_INTEGER:
            raise ValueError("issued_tick must leave room for the interval endpoint")
        object.__setattr__(self, "orientation_drive", _number(self.orientation_drive, "orientation_drive", -1.0, 1.0))
        object.__setattr__(self, "extension_drive", _number(self.extension_drive, "extension_drive", -1.0, 1.0))

    @property
    def is_neutral(self) -> bool:
        """Return whether both commanded drives are zero, without implying safety."""
        return self.orientation_drive == 0.0 and self.extension_drive == 0.0

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
            "schema": MOTOR_COMMAND_SCHEMA_V1,
            "stream": self.stream.as_dict(),
            "command_id": self.command_id,
            "issued_tick": self.issued_tick,
            "orientation_drive": self.orientation_drive,
            "extension_drive": self.extension_drive,
        }

    @classmethod
    def from_dict(cls, value: object) -> MotorCommandV1:
        """Strictly decode a command description; do not execute or authorize it."""
        packet = _fields(value, frozenset({
            "schema", "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive",
        }))
        if packet["schema"] != MOTOR_COMMAND_SCHEMA_V1:
            raise ValueError("unsupported motor command schema")
        return cls(
            stream=MotorStreamRefV1.from_dict(packet["stream"]),
            command_id=_integer(packet["command_id"], "command_id", minimum=1),
            issued_tick=_integer(packet["issued_tick"], "issued_tick"),
            orientation_drive=_number(packet["orientation_drive"], "orientation_drive", -1.0, 1.0),
            extension_drive=_number(packet["extension_drive"], "extension_drive", -1.0, 1.0),
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

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("stream must be MotorStreamRefV1")
        _integer(self.sample_id, "sample_id", minimum=1)
        event = _integer(self.event_tick, "event_tick")
        available = _integer(self.available_tick, "available_tick")
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
        return {
            "schema": MOTOR_FEEDBACK_SCHEMA_V1,
            "stream": self.stream.as_dict(),
            "sample_id": self.sample_id,
            "event_tick": self.event_tick,
            "available_tick": self.available_tick,
            "frame_id": self.frame_id,
            "angle_units": "degrees",
            "extension_units": "normalized",
            "body_tilt_degrees": self.body_tilt_degrees,
            "support_extension": self.support_extension,
            "support_contact": self.support_contact,
            "useful_loading": self.useful_loading,
            "destabilization": self.destabilization,
        }

    @classmethod
    def from_dict(cls, value: object) -> MotorFeedbackV1:
        """Decode only the declared enhanced schema; never infer missing fields.

        All keys must be present, although measured channel values may be None.
        This distinguishes an explicitly unavailable measurement from an invalid
        packet shape. Unknown task, policy, outcome and scenario keys are errors.
        No raw mapping is retained, and changing it later cannot mutate a record.
        """
        packet = _fields(value, frozenset({
            "schema", "stream", "sample_id", "event_tick", "available_tick", "frame_id", "angle_units", "extension_units",
            "body_tilt_degrees", "support_extension", "support_contact", "useful_loading", "destabilization",
        }))
        if packet["schema"] != MOTOR_FEEDBACK_SCHEMA_V1:
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
            body_tilt_degrees=_optional_number(packet["body_tilt_degrees"], "body_tilt_degrees", -90.0, 90.0),
            support_extension=_optional_number(packet["support_extension"], "support_extension", 0.0, 1.0),
            support_contact=contact,
            useful_loading=_optional_number(packet["useful_loading"], "useful_loading", 0.0, 1.0),
            destabilization=_optional_number(packet["destabilization"], "destabilization", 0.0, 1.0),
        )
