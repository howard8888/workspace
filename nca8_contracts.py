#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Immutable timing and commitment contracts for the new CCA8 runtime.

Phase 1B purpose
----------------
The Architecture-v09.3 runtime represents differently paced biological
processes with a deterministic logical cycle.  A result records when its
evidence was sampled, when the result becomes logically available, whether it
remains valid, and when an owning consumer applied it.  These fields prevent a
late result from silently influencing an earlier focal commitment merely
because one Python function happened to run first.

The records in this module have no cognitive authority.  They describe timing,
result payloads, and the final immutable commitment boundary of one cycle.  The
payload contract is intentionally small and JSON-safe; rich map or sensory
state belongs to later owning modules rather than these engineering records.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace
from enum import Enum, IntEnum
from typing import Mapping, TypeAlias

# pylint: disable=duplicate-code

__version__ = "0.1.0"
__all__ = [
    "CircuitResultV1",
    "CircuitTimingV1",
    "CircuitValidityV1",
    "ContractScalarV1",
    "CycleCommitmentV1",
    "CyclePhase",
    "LogicalAvailabilityV1",
    "__version__",
]

ContractScalarV1: TypeAlias = str | int | float | bool | None

_MAX_IDENTIFIER_LENGTH = 120
_MAX_PAYLOAD_ITEMS = 16
_MAX_PAYLOAD_KEY_LENGTH = 60
_MAX_PAYLOAD_TEXT_LENGTH = 200


class CyclePhase(IntEnum):
    """The six ordered causal phases of one deterministic cognitive cycle."""

    POLL_STAGE = 1
    FREEZE_ELIGIBLE = 2
    UPDATE_OUTCOMES = 3
    FOCAL_COMMITMENT = 4
    PROJECT_DISPATCH = 5
    LEARNING_SCHEDULE = 6

    @property
    def letter(self) -> str:
        """Return the stable human-facing phase letter ``A`` through ``F``."""
        return chr(ord("A") + int(self) - 1)

    @property
    def display_name(self) -> str:
        """Return a compact terminal label such as ``Phase_A POLL_STAGE``."""
        return f"Phase_{self.letter} {self.name}"


class LogicalAvailabilityV1(str, Enum):
    """Coarse deterministic latency choices used by the first scheduler."""

    THIS_CYCLE = "THIS_CYCLE"
    NEXT_CYCLE = "NEXT_CYCLE"


class CircuitValidityV1(str, Enum):
    """Explicit validity state carried by a staged circuit result."""

    VALID = "VALID"
    STALE = "STALE"
    INVALIDATED = "INVALIDATED"
    SUPERSEDED = "SUPERSEDED"
    EXPIRED = "EXPIRED"


def _positive_cycle(value: int, *, field_name: str) -> int:
    """Validate and return one positive non-Boolean logical cycle number."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_identifier(value: str, *, field_name: str) -> str:
    """Validate and return one non-empty bounded identifier."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > _MAX_IDENTIFIER_LENGTH:
        raise ValueError(f"{field_name} exceeds the {_MAX_IDENTIFIER_LENGTH}-character limit")
    return normalized


def _normalize_scalar(value: ContractScalarV1) -> ContractScalarV1:
    """Return one bounded JSON-safe scalar or raise a clear validation error."""
    if value is None or isinstance(value, (bool, int)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError("circuit-result payload floats must be finite")
        return value
    if isinstance(value, str):
        if len(value) > _MAX_PAYLOAD_TEXT_LENGTH:
            raise ValueError(
                f"circuit-result payload text exceeds the {_MAX_PAYLOAD_TEXT_LENGTH}-character limit"
            )
        return value
    raise TypeError(f"circuit-result payload values must be JSON-safe scalars, not {type(value).__name__}")


@dataclass(frozen=True, slots=True)
class CircuitTimingV1:
    """Logical timing, validity, expiry, and application status for one result.

    ``sampled_event_cycle`` identifies the event described by the evidence.
    ``available_cycle`` and ``available_phase`` identify when the processed
    result may first cross the scheduler's Phase-B freeze.  A result can be
    sampled in an earlier cycle and become available later without being
    reinterpreted as evidence about the later event.

    ``expires_after_cycle`` is inclusive: the result may be used during that
    cycle but is removed during its Phase F if still unconsumed.  Supersession
    is explicit and names the newer result that displaced this one.
    """

    sampled_event_cycle: int
    available_cycle: int
    available_phase: CyclePhase = CyclePhase.FREEZE_ELIGIBLE
    applied_cycle: int | None = None
    last_supported_cycle: int | None = None
    expires_after_cycle: int | None = None
    validity: CircuitValidityV1 = CircuitValidityV1.VALID
    superseded_by_result_id: str | None = None

    def __post_init__(self) -> None:
        sampled = _positive_cycle(self.sampled_event_cycle, field_name="sampled_event_cycle")
        available = _positive_cycle(self.available_cycle, field_name="available_cycle")
        if available < sampled:
            raise ValueError("available_cycle cannot precede sampled_event_cycle")
        if not isinstance(self.available_phase, CyclePhase):
            raise TypeError("available_phase must be a CyclePhase")

        if self.applied_cycle is not None:
            applied = _positive_cycle(self.applied_cycle, field_name="applied_cycle")
            if applied < available:
                raise ValueError("applied_cycle cannot precede available_cycle")

        if self.last_supported_cycle is not None:
            supported = _positive_cycle(self.last_supported_cycle, field_name="last_supported_cycle")
            if supported < sampled:
                raise ValueError("last_supported_cycle cannot precede sampled_event_cycle")

        if self.expires_after_cycle is not None:
            expiry = _positive_cycle(self.expires_after_cycle, field_name="expires_after_cycle")
            if expiry < available:
                raise ValueError("expires_after_cycle cannot precede available_cycle")

        if not isinstance(self.validity, CircuitValidityV1):
            raise TypeError("validity must be a CircuitValidityV1")

        superseding_id = self.superseded_by_result_id
        if superseding_id is not None:
            normalized = _bounded_identifier(superseding_id, field_name="superseded_by_result_id")
            object.__setattr__(self, "superseded_by_result_id", normalized)
        if self.validity is CircuitValidityV1.SUPERSEDED and superseding_id is None:
            raise ValueError("SUPERSEDED timing requires superseded_by_result_id")
        if self.validity is not CircuitValidityV1.SUPERSEDED and superseding_id is not None:
            raise ValueError("superseded_by_result_id is valid only for SUPERSEDED timing")
        if self.validity is CircuitValidityV1.EXPIRED and self.expires_after_cycle is None:
            raise ValueError("EXPIRED timing requires expires_after_cycle")

    @classmethod
    def for_availability(
        cls,
        *,
        sampled_event_cycle: int,
        availability: LogicalAvailabilityV1,
        available_phase: CyclePhase = CyclePhase.FREEZE_ELIGIBLE,
        last_supported_cycle: int | None = None,
        expires_after_cycle: int | None = None,
    ) -> "CircuitTimingV1":
        """Build timing using the initial ``THIS_CYCLE``/``NEXT_CYCLE`` model."""
        if not isinstance(availability, LogicalAvailabilityV1):
            raise TypeError("availability must be a LogicalAvailabilityV1")
        available_cycle = sampled_event_cycle
        if availability is LogicalAvailabilityV1.NEXT_CYCLE:
            available_cycle += 1
        return cls(
            sampled_event_cycle=sampled_event_cycle,
            available_cycle=available_cycle,
            available_phase=available_phase,
            last_supported_cycle=last_supported_cycle,
            expires_after_cycle=expires_after_cycle,
        )

    def effective_validity(self, cycle_id: int) -> CircuitValidityV1:
        """Return explicit validity, treating passed expiry as ``EXPIRED``."""
        cycle = _positive_cycle(cycle_id, field_name="cycle_id")
        if self.expires_after_cycle is not None and cycle > self.expires_after_cycle:
            return CircuitValidityV1.EXPIRED
        return self.validity

    def is_eligible_for_freeze(self, cycle_id: int) -> bool:
        """Return whether this result may enter the current Phase-B frozen set."""
        cycle = _positive_cycle(cycle_id, field_name="cycle_id")
        if self.effective_validity(cycle) is not CircuitValidityV1.VALID:
            return False
        if self.available_cycle < cycle:
            return True
        return self.available_cycle == cycle and self.available_phase <= CyclePhase.FREEZE_ELIGIBLE

    def mark_applied(self, cycle_id: int) -> "CircuitTimingV1":
        """Return a copy recording the cycle in which an owning consumer applied it."""
        cycle = _positive_cycle(cycle_id, field_name="cycle_id")
        if cycle < self.available_cycle:
            raise ValueError("a circuit result cannot be applied before it becomes available")
        return replace(self, applied_cycle=cycle)

    def mark_superseded(self, superseding_result_id: str) -> "CircuitTimingV1":
        """Return a copy explicitly displaced by a newer result."""
        result_id = _bounded_identifier(superseding_result_id, field_name="superseding_result_id")
        return replace(
            self,
            validity=CircuitValidityV1.SUPERSEDED,
            superseded_by_result_id=result_id,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe diagnostic representation."""
        return {
            "sampled_event_cycle": self.sampled_event_cycle,
            "available_cycle": self.available_cycle,
            "available_phase": self.available_phase.name,
            "applied_cycle": self.applied_cycle,
            "last_supported_cycle": self.last_supported_cycle,
            "expires_after_cycle": self.expires_after_cycle,
            "validity": self.validity.value,
            "superseded_by_result_id": self.superseded_by_result_id,
        }


@dataclass(frozen=True, slots=True)
class CircuitResultV1:
    """One bounded, immutable result published by an owning circuit.

    ``source_sequence`` is monotonically increasing within ``source_circuit``.
    The scheduler combines that local sequence with the source and result ID to
    obtain an order independent of Python polling order.  ``event_latch`` marks
    a brief event that must remain in a bounded per-source latch until consumed,
    superseded, invalidated, expired, or deterministically evicted.
    """

    result_id: str
    source_circuit: str
    source_sequence: int
    timing: CircuitTimingV1
    payload: tuple[tuple[str, ContractScalarV1], ...] = ()
    event_latch: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "result_id", _bounded_identifier(self.result_id, field_name="result_id"))
        object.__setattr__(
            self,
            "source_circuit",
            _bounded_identifier(self.source_circuit, field_name="source_circuit"),
        )
        if isinstance(self.source_sequence, bool) or not isinstance(self.source_sequence, int) or self.source_sequence <= 0:
            raise ValueError("source_sequence must be a positive integer")
        if not isinstance(self.timing, CircuitTimingV1):
            raise TypeError("timing must be a CircuitTimingV1")
        if not isinstance(self.event_latch, bool):
            raise TypeError("event_latch must be Boolean")
        if len(self.payload) > _MAX_PAYLOAD_ITEMS:
            raise ValueError(f"circuit-result payload may contain at most {_MAX_PAYLOAD_ITEMS} items")

        normalized: list[tuple[str, ContractScalarV1]] = []
        seen: set[str] = set()
        for raw_key, raw_value in self.payload:
            key = _bounded_identifier(str(raw_key), field_name="payload key")
            if len(key) > _MAX_PAYLOAD_KEY_LENGTH:
                raise ValueError(f"payload key exceeds the {_MAX_PAYLOAD_KEY_LENGTH}-character limit")
            if key in seen:
                raise ValueError(f"duplicate circuit-result payload key: {key!r}")
            seen.add(key)
            normalized.append((key, _normalize_scalar(raw_value)))
        normalized.sort(key=lambda item: item[0])
        object.__setattr__(self, "payload", tuple(normalized))

    @classmethod
    def from_mapping(
        cls,
        *,
        result_id: str,
        source_circuit: str,
        source_sequence: int,
        timing: CircuitTimingV1,
        payload: Mapping[str, ContractScalarV1] | None = None,
        event_latch: bool = False,
    ) -> "CircuitResultV1":
        """Build one result from a mapping while preserving immutable storage."""
        return cls(
            result_id=result_id,
            source_circuit=source_circuit,
            source_sequence=source_sequence,
            timing=timing,
            payload=tuple((str(key), value) for key, value in (payload or {}).items()),
            event_latch=event_latch,
        )

    @property
    def stable_sort_key(self) -> tuple[int, int, str, int, str]:
        """Return the order used after Phase-A polling, independent of call order."""
        return (
            self.timing.available_cycle,
            int(self.timing.available_phase),
            self.source_circuit,
            self.source_sequence,
            self.result_id,
        )

    def mark_applied(self, cycle_id: int) -> "CircuitResultV1":
        """Return a copy whose timing records application by the owning consumer."""
        return replace(self, timing=self.timing.mark_applied(cycle_id))

    def mark_superseded(self, superseding_result_id: str) -> "CircuitResultV1":
        """Return a copy explicitly superseded by another result."""
        return replace(self, timing=self.timing.mark_superseded(superseding_result_id))

    def payload_dict(self) -> dict[str, ContractScalarV1]:
        """Return a newly allocated scalar payload dictionary."""
        return dict(self.payload)
        #return {key: value for key, value in self.payload}

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe representation."""
        return {
            "result_id": self.result_id,
            "source_circuit": self.source_circuit,
            "source_sequence": self.source_sequence,
            "timing": self.timing.as_dict(),
            "payload": self.payload_dict(),
            "event_latch": self.event_latch,
        }


@dataclass(frozen=True, slots=True)
class CycleCommitmentV1:
    """Immutable Phase-E commitment record for one logical cognitive cycle.

    Phase 1B creates a real commitment boundary but no focal operation.  The
    current record therefore honestly contains ``None`` for focal operation,
    PNM, and task action.  Later phases may populate those fields only when the
    corresponding subsystem exists and has causal authority.
    """

    cycle_id: int
    observation_number: int
    eligible_result_ids: tuple[str, ...]
    applied_result_ids: tuple[str, ...]
    focal_operation_id: str | None = None
    pnm_id: str | None = None
    task_action: str | None = None
    committed_phase: CyclePhase = CyclePhase.PROJECT_DISPATCH

    def __post_init__(self) -> None:
        cycle = _positive_cycle(self.cycle_id, field_name="cycle_id")
        observation = _positive_cycle(self.observation_number, field_name="observation_number")
        if cycle != observation:
            raise ValueError("Cycle_n must consume Observation_n at the commitment boundary")
        if self.committed_phase is not CyclePhase.PROJECT_DISPATCH:
            raise ValueError("CycleCommitmentV1 becomes immutable at Phase E")

        eligible = tuple(_bounded_identifier(item, field_name="eligible result id") for item in self.eligible_result_ids)
        applied = tuple(_bounded_identifier(item, field_name="applied result id") for item in self.applied_result_ids)
        if len(set(eligible)) != len(eligible):
            raise ValueError("eligible_result_ids must not contain duplicates")
        if len(set(applied)) != len(applied):
            raise ValueError("applied_result_ids must not contain duplicates")
        if not set(applied).issubset(set(eligible)):
            raise ValueError("applied results must come from the Phase-B frozen eligible set")
        object.__setattr__(self, "eligible_result_ids", eligible)
        object.__setattr__(self, "applied_result_ids", applied)

        for field_name in ("focal_operation_id", "pnm_id", "task_action"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(self, field_name, _bounded_identifier(value, field_name=field_name))
        if self.focal_operation_id is None and (self.pnm_id is not None or self.task_action is not None):
            raise ValueError("PNM or task action requires a focal operation")
        if self.pnm_id is not None and self.focal_operation_id is None:
            raise ValueError("PNM requires a focal operation")

    @property
    def is_null(self) -> bool:
        """Return ``True`` when the cycle committed no focal operation or task action."""
        return self.focal_operation_id is None and self.pnm_id is None and self.task_action is None

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe commitment snapshot."""
        return {
            "cycle_id": self.cycle_id,
            "observation_number": self.observation_number,
            "eligible_result_ids": list(self.eligible_result_ids),
            "applied_result_ids": list(self.applied_result_ids),
            "focal_operation_id": self.focal_operation_id,
            "pnm_id": self.pnm_id,
            "task_action": self.task_action,
            "committed_phase": self.committed_phase.name,
            "is_null": self.is_null,
        }
