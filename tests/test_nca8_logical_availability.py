#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logical-availability, expiry, supersession, and event-latch tests."""

from __future__ import annotations

from nca8_adapters import Nca8ObservationV1, create_environment_bridge_v1
from nca8_contracts import (
    CircuitResultV1,
    CircuitTimingV1,
    CyclePhase,
    LogicalAvailabilityV1,
)
from nca8_runtime import Nca8CognitiveRuntimeV1
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1


def _initial_observation_v1() -> Nca8ObservationV1:
    bridge = create_environment_bridge_v1()
    return bridge.reset(seed=0).observation


def _result_v1(
    *,
    result_id: str,
    source: str,
    sequence: int,
    sampled_cycle: int,
    available_cycle: int,
    available_phase: CyclePhase = CyclePhase.FREEZE_ELIGIBLE,
    expires_after_cycle: int | None = None,
    event_latch: bool = False,
) -> CircuitResultV1:
    """Build one result with explicit timing for scheduler-boundary tests."""
    return CircuitResultV1.from_mapping(
        result_id=result_id,
        source_circuit=source,
        source_sequence=sequence,
        timing=CircuitTimingV1(
            sampled_event_cycle=sampled_cycle,
            available_cycle=available_cycle,
            available_phase=available_phase,
            expires_after_cycle=expires_after_cycle,
        ),
        payload={"token": result_id},
        event_latch=event_latch,
    )


def test_next_cycle_result_cannot_influence_current_phase_d_commitment() -> None:
    """A declared NEXT_CYCLE result must remain pending until the next freeze."""
    observation = _initial_observation_v1()

    def poll_latency(cycle_id: int) -> tuple[CircuitResultV1, ...]:
        if cycle_id != 1:
            return ()
        return (
            _result_v1(
                result_id="latency:this",
                source="latency",
                sequence=1,
                sampled_cycle=1,
                available_cycle=1,
                expires_after_cycle=1,
            ),
            _result_v1(
                result_id="latency:next",
                source="latency",
                sequence=2,
                sampled_cycle=1,
                available_cycle=2,
                expires_after_cycle=2,
            ),
        )

    runtime = Nca8CognitiveRuntimeV1(
        trace=Nca8TraceBufferV1(),
        scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(CircuitPollSourceV1("latency", poll_latency),),
    )

    cycle_one = runtime.run_cycle(observation, observation_number=1)
    cycle_two = runtime.run_cycle(observation, observation_number=2)

    assert "latency:this" in cycle_one.commitment.eligible_result_ids
    assert "latency:next" not in cycle_one.commitment.eligible_result_ids
    assert cycle_one.scheduler.pending_result_ids == ("latency:next",)
    assert "latency:next" in cycle_two.commitment.eligible_result_ids
    assert cycle_two.scheduler.pending_result_ids == ()


def test_result_available_in_phase_c_misses_the_current_phase_b_freeze() -> None:
    """Availability later than Phase B cannot be retroactively moved into Cycle 1."""
    observation = _initial_observation_v1()

    def poll_late(cycle_id: int) -> tuple[CircuitResultV1, ...]:
        if cycle_id != 1:
            return ()
        return (
            _result_v1(
                result_id="late_phase:1",
                source="late_phase",
                sequence=1,
                sampled_cycle=1,
                available_cycle=1,
                available_phase=CyclePhase.UPDATE_OUTCOMES,
                expires_after_cycle=2,
            ),
        )

    runtime = Nca8CognitiveRuntimeV1(
        trace=Nca8TraceBufferV1(),
        scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(CircuitPollSourceV1("late_phase", poll_late),),
    )

    cycle_one = runtime.run_cycle(observation, observation_number=1)
    cycle_two = runtime.run_cycle(observation, observation_number=2)

    assert "late_phase:1" not in cycle_one.commitment.eligible_result_ids
    assert cycle_one.scheduler.pending_result_ids == ("late_phase:1",)
    assert "late_phase:1" in cycle_two.commitment.eligible_result_ids


def test_bounded_event_latch_evicts_oldest_and_preserves_newer_brief_events() -> None:
    """A per-source event latch should retain only its deterministic capacity."""
    observation = _initial_observation_v1()

    def poll_events(cycle_id: int) -> tuple[CircuitResultV1, ...]:
        if cycle_id != 1:
            return ()
        return tuple(
            _result_v1(
                result_id=f"brief:{sequence}",
                source="brief",
                sequence=sequence,
                sampled_cycle=1,
                available_cycle=2,
                expires_after_cycle=2,
                event_latch=True,
            )
            for sequence in (1, 2, 3)
        )

    runtime = Nca8CognitiveRuntimeV1(
        trace=Nca8TraceBufferV1(),
        scheduler=Nca8DeterministicSchedulerV1(event_latch_capacity_per_source=2),
        poll_sources=(CircuitPollSourceV1("brief", poll_events),),
    )

    cycle_one = runtime.run_cycle(observation, observation_number=1)
    cycle_two = runtime.run_cycle(observation, observation_number=2)

    assert cycle_one.scheduler.evicted_latch_result_ids == ("brief:1",)
    assert cycle_one.scheduler.latched_result_ids == ("brief:2", "brief:3")
    assert cycle_one.scheduler.pending_result_ids == ("brief:2", "brief:3")
    assert "brief:1" not in cycle_two.commitment.eligible_result_ids
    assert "brief:2" in cycle_two.commitment.eligible_result_ids
    assert "brief:3" in cycle_two.commitment.eligible_result_ids
    assert cycle_two.scheduler.latched_result_ids == ()


def test_unconsumed_event_expiring_after_current_cycle_is_retired_in_phase_f() -> None:
    """A brief event that misses Phase B may expire rather than becoming false current truth."""
    observation = _initial_observation_v1()

    def poll_expiring(cycle_id: int) -> tuple[CircuitResultV1, ...]:
        if cycle_id != 1:
            return ()
        return (
            _result_v1(
                result_id="brief:expires",
                source="brief_expiry",
                sequence=1,
                sampled_cycle=1,
                available_cycle=1,
                available_phase=CyclePhase.UPDATE_OUTCOMES,
                expires_after_cycle=1,
                event_latch=True,
            ),
        )

    runtime = Nca8CognitiveRuntimeV1(
        trace=Nca8TraceBufferV1(),
        scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(CircuitPollSourceV1("brief_expiry", poll_expiring),),
    )

    cycle_one = runtime.run_cycle(observation, observation_number=1)

    assert "brief:expires" not in cycle_one.commitment.eligible_result_ids
    assert cycle_one.scheduler.retired_result_ids == ("brief:expires",)
    assert cycle_one.scheduler.pending_result_ids == ()
    assert cycle_one.scheduler.latched_result_ids == ()


def test_superseded_pending_result_never_crosses_a_later_freeze() -> None:
    """Explicit supersession should block stale pending information from commitment."""
    trace = Nca8TraceBufferV1()
    scheduler = Nca8DeterministicSchedulerV1()
    old_result = _result_v1(
        result_id="visual:old",
        source="visual",
        sequence=1,
        sampled_cycle=1,
        available_cycle=2,
        expires_after_cycle=2,
    )
    source = CircuitPollSourceV1("visual", lambda _cycle_id: (old_result,))

    scheduler.phase_a_poll_and_stage(1, (source,), trace)
    updated = scheduler.supersede_result("visual:old", "visual:new")
    frozen = scheduler.phase_b_freeze_eligible(1, trace)
    scheduler.phase_c_apply_frozen(1, trace)
    scheduler.enter_runtime_phase(1, CyclePhase.FOCAL_COMMITMENT)
    scheduler.enter_runtime_phase(1, CyclePhase.PROJECT_DISPATCH)
    snapshot = scheduler.phase_f_finish(1, trace)

    assert updated.timing.superseded_by_result_id == "visual:new"
    assert frozen == ()
    assert snapshot.retired_result_ids == ("visual:old",)
