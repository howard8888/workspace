#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Deterministic bounded-quasi-asynchronous scheduler for the new CCA8 runtime.

The scheduler is single-threaded and nonblocking by design.  Phase A polls due
sources and stages completed results.  Phase B freezes the exact set eligible
for the current cycle.  Later Python execution cannot move another result into
that frozen set.  Brief events can be retained in bounded per-source latches,
while ordinary delayed results use a separate bounded staged-result store.

This module contains engineering timing machinery only.  It does not know what
a NavMap, Attention candidate, primitive, PNM, or action means and therefore
cannot become a hidden cognitive authority.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Callable, Sequence
from dataclasses import dataclass, replace
from typing import TypeAlias

from nca8_contracts import CircuitResultV1, CircuitValidityV1, CyclePhase
from nca8_trace import Nca8TraceBufferV1

# pylint: disable=duplicate-code

__version__ = "0.2.0"
__all__ = [
    "CircuitPollFunctionV1",
    "CircuitPollSourceV1",
    "Nca8DeterministicSchedulerV1",
    "SchedulerCycleSnapshotV1",
    "__version__",
]

CircuitPollFunctionV1: TypeAlias = Callable[[int], Sequence[CircuitResultV1]]

_MAX_POLL_SOURCES = 32
_MAX_RESULT_IDS_IN_TRACE = 8


def _positive_int(value: int, *, field_name: str) -> int:
    """Validate and return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_id(value: str, *, field_name: str) -> str:
    """Validate and return one compact identifier used by scheduler records."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > 120:
        raise ValueError(f"{field_name} exceeds the 120-character limit")
    return normalized


def _ids_text(result_ids: Sequence[str]) -> str:
    """Return a bounded deterministic ID summary for one trace event."""
    ordered = tuple(result_ids)
    visible = ordered[:_MAX_RESULT_IDS_IN_TRACE]
    text = ",".join(visible) if visible else "(none)"
    if len(ordered) > len(visible):
        text += f",...(+{len(ordered) - len(visible)})"
    return text[:200]


@dataclass(frozen=True, slots=True)
class CircuitPollSourceV1:
    """One named Phase-A poll function with a stable circuit identity."""

    circuit_id: str
    poll: CircuitPollFunctionV1

    def __post_init__(self) -> None:
        object.__setattr__(self, "circuit_id", _bounded_id(self.circuit_id, field_name="circuit_id"))
        if not callable(self.poll):
            raise TypeError("poll must be callable")


@dataclass(frozen=True, slots=True)
class SchedulerCycleSnapshotV1:
    """Immutable end-of-cycle scheduler state for diagnostics and replay tests."""

    cycle_id: int
    phases: tuple[CyclePhase, ...]
    staged_result_ids: tuple[str, ...]
    frozen_result_ids: tuple[str, ...]
    applied_result_ids: tuple[str, ...]
    evicted_latch_result_ids: tuple[str, ...]
    retired_result_ids: tuple[str, ...]
    pending_result_ids: tuple[str, ...]
    latched_result_ids: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe scheduler snapshot."""
        return {
            "cycle_id": self.cycle_id,
            "phases": [phase.name for phase in self.phases],
            "staged_result_ids": list(self.staged_result_ids),
            "frozen_result_ids": list(self.frozen_result_ids),
            "applied_result_ids": list(self.applied_result_ids),
            "evicted_latch_result_ids": list(self.evicted_latch_result_ids),
            "retired_result_ids": list(self.retired_result_ids),
            "pending_result_ids": list(self.pending_result_ids),
            "latched_result_ids": list(self.latched_result_ids),
        }


class _EventLatchStoreV1:
    """Retain brief events in bounded deterministic per-source queues."""

    def __init__(self, capacity_per_source: int) -> None:
        self._capacity_per_source = _positive_int(
            capacity_per_source,
            field_name="event_latch_capacity_per_source",
        )
        self._by_source: dict[str, deque[CircuitResultV1]] = {}

    def add(self, result: CircuitResultV1) -> CircuitResultV1 | None:
        """Latch one result and return a deterministically evicted oldest event."""
        queue = self._by_source.setdefault(result.source_circuit, deque())
        evicted = None
        if len(queue) >= self._capacity_per_source:
            evicted = queue.popleft()
        queue.append(result)
        return evicted

    def all_results(self) -> tuple[CircuitResultV1, ...]:
        """Return every latched event in stable result order."""
        results = [result for queue in self._by_source.values() for result in queue]
        return tuple(sorted(results, key=lambda item: item.stable_sort_key))

    def find(self, result_id: str) -> CircuitResultV1 | None:
        """Return one latched result by ID without exposing the queue."""
        for queue in self._by_source.values():
            for result in queue:
                if result.result_id == result_id:
                    return result
        return None

    def replace(self, updated: CircuitResultV1) -> bool:
        """Replace one latched result with an immutable updated copy."""
        queue = self._by_source.get(updated.source_circuit)
        if queue is None:
            return False
        for index, result in enumerate(queue):
            if result.result_id == updated.result_id:
                queue[index] = updated
                return True
        return False

    def remove_ids(self, result_ids: set[str]) -> None:
        """Remove consumed or retired results and delete empty source queues."""
        for source, queue in tuple(self._by_source.items()):
            retained = deque(result for result in queue if result.result_id not in result_ids)
            if retained:
                self._by_source[source] = retained
            else:
                del self._by_source[source]


class Nca8DeterministicSchedulerV1:
    """Execute the explicit Phase-A-to-F timing boundary for NCA8.

    The scheduler enforces consecutive cycle numbers and exact phase order.  It
    sorts poll sources by circuit ID and returned results by declared timing,
    source, source-local sequence, and result ID.  Consequently, changing the
    caller's Phase-A poll-function list order cannot alter the frozen Phase-B
    set or its trace representation.
    """

    def __init__(
        self,
        *,
        staged_result_capacity: int = 64,
        event_latch_capacity_per_source: int = 4,
    ) -> None:
        self._staged_result_capacity = _positive_int(
            staged_result_capacity,
            field_name="staged_result_capacity",
        )
        self._event_latches = _EventLatchStoreV1(event_latch_capacity_per_source)
        self._staged_results: dict[str, CircuitResultV1] = {}
        self._last_source_sequence: dict[str, int] = {}
        self._last_completed_cycle = 0
        self._active_cycle: int | None = None
        self._last_phase_value = 0
        self._cycle_staged_ids: tuple[str, ...] = ()
        self._cycle_frozen: tuple[CircuitResultV1, ...] = ()
        self._cycle_applied: tuple[CircuitResultV1, ...] = ()
        self._cycle_evicted_ids: tuple[str, ...] = ()
        self._cycle_retired_ids: tuple[str, ...] = ()

    @property
    def last_completed_cycle(self) -> int:
        """Return the most recent fully completed logical cycle."""
        return self._last_completed_cycle

    def _enter_phase(self, cycle_id: int, phase: CyclePhase) -> None:
        """Enforce consecutive cycles and exact A-to-F phase progression."""
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if not isinstance(phase, CyclePhase):
            raise TypeError("phase must be a CyclePhase")

        if self._active_cycle is None:
            if phase is not CyclePhase.POLL_STAGE:
                raise RuntimeError("a scheduler cycle must begin with Phase A")
            expected_cycle = self._last_completed_cycle + 1
            if cycle != expected_cycle:
                raise RuntimeError(f"expected CognitiveCycle_{expected_cycle}, received CognitiveCycle_{cycle}")
            self._active_cycle = cycle
            self._last_phase_value = 0
            self._cycle_staged_ids = ()
            self._cycle_frozen = ()
            self._cycle_applied = ()
            self._cycle_evicted_ids = ()
            self._cycle_retired_ids = ()
        elif cycle != self._active_cycle:
            raise RuntimeError(
                f"CognitiveCycle_{self._active_cycle} is still active; cannot enter CognitiveCycle_{cycle}"
            )

        expected_phase_value = self._last_phase_value + 1
        if int(phase) != expected_phase_value:
            expected = CyclePhase(expected_phase_value)
            raise RuntimeError(
                f"CognitiveCycle_{cycle} expected {expected.display_name}, received {phase.display_name}"
            )
        self._last_phase_value = int(phase)

    def phase_a_poll_and_stage(
        self,
        cycle_id: int,
        poll_sources: Sequence[CircuitPollSourceV1],
        trace: Nca8TraceBufferV1,
    ) -> tuple[CircuitResultV1, ...]:
        """Poll sources in stable order and stage all completed results."""
        self._enter_phase(cycle_id, CyclePhase.POLL_STAGE)
        if len(poll_sources) > _MAX_POLL_SOURCES:
            raise ValueError(f"Phase A supports at most {_MAX_POLL_SOURCES} poll sources")

        source_ids = [source.circuit_id for source in poll_sources]
        if len(set(source_ids)) != len(source_ids):
            raise ValueError("Phase-A poll source IDs must be unique")

        completed: list[CircuitResultV1] = []
        for source in sorted(poll_sources, key=lambda item: item.circuit_id):
            source_results = tuple(source.poll(cycle_id))
            for result in source_results:
                if not isinstance(result, CircuitResultV1):
                    raise TypeError(f"poll source {source.circuit_id!r} returned a non-CircuitResultV1 value")
                if result.source_circuit != source.circuit_id:
                    raise ValueError(
                        f"poll source {source.circuit_id!r} returned result owned by {result.source_circuit!r}"
                    )
                completed.append(result)

        ordered = tuple(
            sorted(
                completed,
                key=lambda item: (item.source_circuit, item.source_sequence, item.result_id),
            )
        )
        self._validate_new_results(ordered)

        evicted_ids: list[str] = []
        for result in ordered:
            previous_sequence = self._last_source_sequence.get(result.source_circuit, 0)
            self._last_source_sequence[result.source_circuit] = max(previous_sequence, result.source_sequence)
            if result.event_latch:
                evicted = self._event_latches.add(result)
                if evicted is not None:
                    evicted_ids.append(evicted.result_id)
            else:
                self._staged_results[result.result_id] = result

        self._cycle_staged_ids = tuple(result.result_id for result in ordered)
        self._cycle_evicted_ids = tuple(evicted_ids)
        trace.append(
            "scheduler",
            f"{CyclePhase.POLL_STAGE.display_name} completed",
            cycle_id=cycle_id,
            phase=CyclePhase.POLL_STAGE.name,
            details={
                "evicted_latch_count": len(evicted_ids),
                "poll_source_count": len(poll_sources),
                "result_ids": _ids_text(self._cycle_staged_ids),
                "staged_result_count": len(ordered),
            },
        )
        return ordered

    def _validate_new_results(self, ordered: Sequence[CircuitResultV1]) -> None:
        """Validate capacity, identity, and source-local monotonic sequence numbers."""
        new_ids = [result.result_id for result in ordered]
        if len(set(new_ids)) != len(new_ids):
            raise ValueError("Phase A returned duplicate circuit result IDs")

        existing_ids = set(self._staged_results)
        existing_ids.update(result.result_id for result in self._event_latches.all_results())
        duplicate_existing = existing_ids.intersection(new_ids)
        if duplicate_existing:
            raise ValueError(f"circuit result already staged: {sorted(duplicate_existing)[0]!r}")

        results_by_source: dict[str, list[CircuitResultV1]] = {}
        for result in ordered:
            results_by_source.setdefault(result.source_circuit, []).append(result)
        for source, source_results in results_by_source.items():
            previous = self._last_source_sequence.get(source, 0)
            for result in sorted(source_results, key=lambda item: item.source_sequence):
                if result.source_sequence <= previous:
                    raise ValueError(
                        f"source_sequence for {source!r} must increase beyond {previous}"
                    )
                previous = result.source_sequence

        non_latched_count = sum(not result.event_latch for result in ordered)
        if len(self._staged_results) + non_latched_count > self._staged_result_capacity:
            raise OverflowError("bounded staged-result capacity would be exceeded")

    def phase_b_freeze_eligible(
        self,
        cycle_id: int,
        trace: Nca8TraceBufferV1,
    ) -> tuple[CircuitResultV1, ...]:
        """Freeze the exact result set eligible before the current commitment."""
        self._enter_phase(cycle_id, CyclePhase.FREEZE_ELIGIBLE)
        all_results = list(self._staged_results.values())
        all_results.extend(self._event_latches.all_results())
        by_id = {result.result_id: result for result in all_results}
        eligible = tuple(
            sorted(
                (result for result in by_id.values() if result.timing.is_eligible_for_freeze(cycle_id)),
                key=lambda item: item.stable_sort_key,
            )
        )
        self._cycle_frozen = eligible
        trace.append(
            "scheduler",
            f"{CyclePhase.FREEZE_ELIGIBLE.display_name} froze the eligible set",
            cycle_id=cycle_id,
            phase=CyclePhase.FREEZE_ELIGIBLE.name,
            details={
                "eligible_result_count": len(eligible),
                "result_ids": _ids_text(tuple(result.result_id for result in eligible)),
            },
        )
        return eligible

    def phase_c_apply_frozen(
        self,
        cycle_id: int,
        trace: Nca8TraceBufferV1,
    ) -> tuple[CircuitResultV1, ...]:
        """Mark only the Phase-B frozen results as applied and consume them."""
        self._enter_phase(cycle_id, CyclePhase.UPDATE_OUTCOMES)
        applied = tuple(result.mark_applied(cycle_id) for result in self._cycle_frozen)
        consumed_ids = {result.result_id for result in self._cycle_frozen}
        for result_id in consumed_ids:
            self._staged_results.pop(result_id, None)
        self._event_latches.remove_ids(consumed_ids)
        self._cycle_applied = applied
        trace.append(
            "scheduler",
            f"{CyclePhase.UPDATE_OUTCOMES.display_name} applied frozen results",
            cycle_id=cycle_id,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={
                "applied_result_count": len(applied),
                "result_ids": _ids_text(tuple(result.result_id for result in applied)),
            },
        )
        return applied

    def enter_runtime_phase(self, cycle_id: int, phase: CyclePhase) -> None:
        """Advance through runtime-owned Phase D or E while preserving phase order."""
        if phase not in (CyclePhase.FOCAL_COMMITMENT, CyclePhase.PROJECT_DISPATCH):
            raise ValueError("enter_runtime_phase accepts only Phase D or Phase E")
        self._enter_phase(cycle_id, phase)

    def phase_f_finish(
        self,
        cycle_id: int,
        trace: Nca8TraceBufferV1,
        *,
        reconcile: Callable[[], None] | None = None,
    ) -> SchedulerCycleSnapshotV1:
        """Enter F, run optional due-owner reconciliation, then retire and close.

        The callback receives no new external input and supplies no task decision.
        The composing runtime owns its bounded work; the scheduler knows nothing
        about learner inventories or update rules. A callback failure leaves the
        cycle unclosed, so its owner must stop/reset rather than retry the callback.
        Existing callers without reconciliation retain identical phase and trace
        behavior. Invalid callbacks are rejected before entering F.
        """
        if reconcile is not None and not callable(reconcile):
            raise TypeError("F reconciliation must be callable or None")
        self._enter_phase(cycle_id, CyclePhase.LEARNING_SCHEDULE)
        if reconcile is not None:
            reconcile()
        retired_ids = self._retire_after_cycle(cycle_id)
        self._cycle_retired_ids = retired_ids
        pending = self.pending_results_snapshot()
        latched = self._event_latches.all_results()
        snapshot = SchedulerCycleSnapshotV1(
            cycle_id=cycle_id,
            phases=tuple(CyclePhase),
            staged_result_ids=self._cycle_staged_ids,
            frozen_result_ids=tuple(result.result_id for result in self._cycle_frozen),
            applied_result_ids=tuple(result.result_id for result in self._cycle_applied),
            evicted_latch_result_ids=self._cycle_evicted_ids,
            retired_result_ids=self._cycle_retired_ids,
            pending_result_ids=tuple(result.result_id for result in pending),
            latched_result_ids=tuple(result.result_id for result in latched),
        )
        trace.append(
            "scheduler",
            f"{CyclePhase.LEARNING_SCHEDULE.display_name} completed",
            cycle_id=cycle_id,
            phase=CyclePhase.LEARNING_SCHEDULE.name,
            details={
                "latched_result_count": len(latched),
                "pending_result_count": len(pending),
                "retired_result_count": len(retired_ids),
            },
        )
        self._last_completed_cycle = cycle_id
        self._active_cycle = None
        self._last_phase_value = 0
        return snapshot

    def _retire_after_cycle(self, cycle_id: int) -> tuple[str, ...]:
        """Remove pending results that cannot legally participate next cycle."""
        retired: set[str] = set()
        for result_id, result in tuple(self._staged_results.items()):
            if self._should_retire_after_cycle(result, cycle_id):
                retired.add(result_id)
                del self._staged_results[result_id]

        for result in self._event_latches.all_results():
            if self._should_retire_after_cycle(result, cycle_id):
                retired.add(result.result_id)
        self._event_latches.remove_ids(retired)
        return tuple(sorted(retired))

    @staticmethod
    def _should_retire_after_cycle(result: CircuitResultV1, cycle_id: int) -> bool:
        """Return whether a pending result is invalid or expires as this cycle closes."""
        if result.timing.validity is not CircuitValidityV1.VALID:
            return True
        expiry = result.timing.expires_after_cycle
        return expiry is not None and expiry <= cycle_id

    def pending_results_snapshot(self) -> tuple[CircuitResultV1, ...]:
        """Return all ordinary and latched pending results in stable order."""
        results = list(self._staged_results.values())
        results.extend(self._event_latches.all_results())
        by_id = {result.result_id: result for result in results}
        return tuple(sorted(by_id.values(), key=lambda item: item.stable_sort_key))

    def latched_results_snapshot(self) -> tuple[CircuitResultV1, ...]:
        """Return a read-only snapshot of bounded brief-event latches."""
        return self._event_latches.all_results()

    def supersede_result(self, result_id: str, superseding_result_id: str) -> CircuitResultV1:
        """Mark one pending result as explicitly superseded before Phase F retirement."""
        target_id = _bounded_id(result_id, field_name="result_id")
        replacement_id = _bounded_id(superseding_result_id, field_name="superseding_result_id")
        result = self._staged_results.get(target_id) or self._event_latches.find(target_id)
        if result is None:
            raise KeyError(f"unknown pending circuit result: {target_id!r}")
        updated = result.mark_superseded(replacement_id)
        if target_id in self._staged_results:
            self._staged_results[target_id] = updated
        else:
            self._event_latches.replace(updated)
        return updated

    def invalidate_result(self, result_id: str) -> CircuitResultV1:
        """Mark one pending result invalid so it cannot cross a later freeze."""
        target_id = _bounded_id(result_id, field_name="result_id")
        result = self._staged_results.get(target_id) or self._event_latches.find(target_id)
        if result is None:
            raise KeyError(f"unknown pending circuit result: {target_id!r}")
        timing = replace(result.timing, validity=CircuitValidityV1.INVALIDATED)
        updated = replace(result, timing=timing)
        if target_id in self._staged_results:
            self._staged_results[target_id] = updated
        else:
            self._event_latches.replace(updated)
        return updated
