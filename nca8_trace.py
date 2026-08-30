#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Independent bounded trace support for the new CCA8 runtime.

Purpose
-------
The ``nca8_*`` modules implement the experimental Architecture-v09.3 runtime
beside the established ``cca8_*`` runtime.  This module provides the new
runtime's first diagnostic boundary: deterministic, bounded, immutable trace
events that can be rendered for a human or exported as JSON-safe dictionaries.

Authority boundary
------------------
Trace records are observations about execution.  They are never read back as
cognitive evidence, never select an action, and never mutate the environment.
The trace uses logical sequence numbers rather than wall-clock timestamps so a
fresh session with the same inputs produces directly comparable output.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Mapping
from dataclasses import dataclass
from typing import TypeAlias

#pylint: disable=unnecessary-comprehension

__version__ = "0.1.0"
__all__ = [
    "Nca8TraceBufferV1",
    "Nca8TraceEventV1",
    "TraceScalarV1",
    "__version__",
]

TraceScalarV1: TypeAlias = str | int | float | bool | None

_MAX_CHANNEL_LENGTH = 40
_MAX_MESSAGE_LENGTH = 240
_MAX_DETAIL_COUNT = 16
_MAX_DETAIL_KEY_LENGTH = 60
_MAX_DETAIL_STRING_LENGTH = 200


def _bounded_text(value: str, *, maximum: int, field_name: str) -> str:
    """Return one non-empty bounded string or raise ``ValueError``.

    Trace text is deliberately bounded because a trace event should summarize a
    causal boundary rather than become an unbounded dump of cognitive state.
    """
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character trace limit")
    return normalized


def _normalize_trace_scalar(value: TraceScalarV1) -> TraceScalarV1:
    """Return a JSON-safe scalar suitable for deterministic trace details."""
    if value is None or isinstance(value, (bool, int, float)):
        return value
    if isinstance(value, str):
        if len(value) > _MAX_DETAIL_STRING_LENGTH:
            raise ValueError(
                f"trace detail string exceeds the {_MAX_DETAIL_STRING_LENGTH}-character limit"
            )
        return value
    raise TypeError(f"trace details accept JSON-safe scalar values, not {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class Nca8TraceEventV1:
    """One immutable engineering trace event from the new runtime.

    Attributes
    ----------
    sequence:
        Monotonic logical sequence inside one trace-buffer lifetime.
    channel:
        Small subsystem label such as ``session``, ``smoke``, or
        ``environment``.
    message:
        Human-readable event description.
    details:
        Deterministically ordered scalar key/value details.  Rich observations
        and mutable runtime objects are intentionally excluded.
    """

    sequence: int
    channel: str
    message: str
    details: tuple[tuple[str, TraceScalarV1], ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Return a JSON-safe dictionary without exposing mutable trace state."""
        return {
            "sequence": self.sequence,
            "channel": self.channel,
            "message": self.message,
            "details": {key: value for key, value in self.details},
        }

    def render(self) -> str:
        """Return one compact deterministic terminal line."""
        prefix = f"[nca8:{self.channel}]"
        if not self.details:
            return f"{prefix} {self.message}"
        detail_text = " ".join(f"{key}={value!r}" for key, value in self.details)
        return f"{prefix} {self.message} | {detail_text}"


class Nca8TraceBufferV1:
    """Own a bounded sequence of immutable new-runtime trace events.

    This service is mutable only in the engineering sense that it appends and
    evicts trace events.  It has no cognitive authority.  ``capacity`` bounds
    retained history, while ``total_appended`` records how many events were
    emitted since the last clear even when old events have been evicted.
    """

    def __init__(self, capacity: int = 64) -> None:
        if isinstance(capacity, bool) or not isinstance(capacity, int) or capacity <= 0:
            raise ValueError("trace capacity must be a positive integer")
        self._capacity = capacity
        self._events: deque[Nca8TraceEventV1] = deque(maxlen=capacity)
        self._next_sequence = 1
        self._total_appended = 0

    @property
    def capacity(self) -> int:
        """Return the maximum number of retained events."""
        return self._capacity

    @property
    def retained_count(self) -> int:
        """Return the number of events currently retained."""
        return len(self._events)

    @property
    def total_appended(self) -> int:
        """Return the number of events appended since the last clear."""
        return self._total_appended

    def clear(self) -> None:
        """Remove all events and restart logical sequence numbering at one."""
        self._events.clear()
        self._next_sequence = 1
        self._total_appended = 0

    def append(
        self,
        channel: str,
        message: str,
        *,
        details: Mapping[str, TraceScalarV1] | None = None,
    ) -> Nca8TraceEventV1:
        """Create, retain, and return one validated immutable trace event.

        Detail keys are sorted so caller dictionary insertion order cannot alter
        rendered output or JSON export.  The method rejects non-scalar values;
        callers should summarize rich state instead of placing it in the trace.
        """
        normalized_channel = _bounded_text(
            channel,
            maximum=_MAX_CHANNEL_LENGTH,
            field_name="trace channel",
        )
        normalized_message = _bounded_text(
            message,
            maximum=_MAX_MESSAGE_LENGTH,
            field_name="trace message",
        )

        raw_details = details or {}
        if len(raw_details) > _MAX_DETAIL_COUNT:
            raise ValueError(f"one trace event may contain at most {_MAX_DETAIL_COUNT} details")

        normalized_details: list[tuple[str, TraceScalarV1]] = []
        for key in sorted(raw_details):
            normalized_key = _bounded_text(
                str(key),
                maximum=_MAX_DETAIL_KEY_LENGTH,
                field_name="trace detail key",
            )
            normalized_details.append((normalized_key, _normalize_trace_scalar(raw_details[key])))

        event = Nca8TraceEventV1(
            sequence=self._next_sequence,
            channel=normalized_channel,
            message=normalized_message,
            details=tuple(normalized_details),
        )
        self._next_sequence += 1
        self._total_appended += 1
        self._events.append(event)
        return event

    def snapshot(self) -> tuple[Nca8TraceEventV1, ...]:
        """Return an immutable snapshot of retained events in causal order."""
        return tuple(self._events)

    def render_lines(self) -> tuple[str, ...]:
        """Return all retained events as immutable terminal lines."""
        return tuple(event.render() for event in self._events)

    def as_json_safe(self) -> list[dict[str, object]]:
        """Return retained events as newly allocated JSON-safe dictionaries."""
        return [event.as_dict() for event in self._events]
