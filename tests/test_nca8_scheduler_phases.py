#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase-order and deterministic-polling tests for the NCA8 scheduler."""

from __future__ import annotations

import pytest

from nca8_adapters import Nca8ObservationV1, create_environment_bridge_v1
from nca8_contracts import CircuitResultV1, CircuitTimingV1, CyclePhase, LogicalAvailabilityV1
from nca8_runtime import Nca8CognitiveRuntimeV1, Nca8SessionV1
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1


def _initial_observation_v1() -> Nca8ObservationV1:
    """Return one real whitelisted initial observation for scheduler tests."""
    bridge = create_environment_bridge_v1()
    return bridge.reset(seed=0).observation


def _current_result_v1(source: str, sequence: int, cycle_id: int) -> CircuitResultV1:
    """Build one deterministic result eligible at the current Phase-B freeze."""
    return CircuitResultV1.from_mapping(
        result_id=f"{source}:{sequence}",
        source_circuit=source,
        source_sequence=sequence,
        timing=CircuitTimingV1.for_availability(
            sampled_event_cycle=cycle_id,
            availability=LogicalAvailabilityV1.THIS_CYCLE,
            expires_after_cycle=cycle_id,
        ),
        payload={"value": sequence},
    )


def test_session_cycle_executes_all_six_phases_in_order() -> None:
    """One real NCA8 cycle should complete the exact A-to-F phase sequence."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()

    assert result.scheduler.phases == tuple(CyclePhase)
    assert result.scheduler.frozen_result_ids == (
        "body_sensory:1",
        "observation_ingress:1",
    )
    assert result.scheduler.applied_result_ids == (
        "body_sensory:1",
        "observation_ingress:1",
    )
    assert result.commitment.committed_phase is CyclePhase.PROJECT_DISPATCH


def test_scheduler_rejects_skipping_the_phase_b_freeze() -> None:
    """Runtime code cannot jump from Phase A directly to focal commitment."""
    scheduler = Nca8DeterministicSchedulerV1()
    trace = Nca8TraceBufferV1()
    source = CircuitPollSourceV1(
        circuit_id="alpha",
        poll=lambda cycle_id: (_current_result_v1("alpha", 1, cycle_id),),
    )

    scheduler.phase_a_poll_and_stage(1, (source,), trace)

    with pytest.raises(RuntimeError, match="expected Phase_B FREEZE_ELIGIBLE"):
        scheduler.enter_runtime_phase(1, CyclePhase.FOCAL_COMMITMENT)


def test_reordering_phase_a_poll_sources_preserves_commitment_and_trace_bytes() -> None:
    """Caller poll-list order must not alter the frozen set or canonical trace."""
    observation = _initial_observation_v1()

    alpha = CircuitPollSourceV1(
        circuit_id="alpha",
        poll=lambda cycle_id: (_current_result_v1("alpha", 1, cycle_id),),
    )
    beta = CircuitPollSourceV1(
        circuit_id="beta",
        poll=lambda cycle_id: (_current_result_v1("beta", 1, cycle_id),),
    )

    trace_one = Nca8TraceBufferV1(capacity=64)
    runtime_one = Nca8CognitiveRuntimeV1(
        trace=trace_one,
        scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(beta, alpha),
    )
    result_one = runtime_one.run_cycle(observation, observation_number=1)

    trace_two = Nca8TraceBufferV1(capacity=64)
    runtime_two = Nca8CognitiveRuntimeV1(
        trace=trace_two,
        scheduler=Nca8DeterministicSchedulerV1(),
        poll_sources=(alpha, beta),
    )
    result_two = runtime_two.run_cycle(observation, observation_number=1)

    assert result_one.commitment.as_dict() == result_two.commitment.as_dict()
    assert result_one.scheduler.as_dict() == result_two.scheduler.as_dict()
    assert trace_one.as_canonical_json_bytes() == trace_two.as_canonical_json_bytes()

def test_phase_a_orders_source_local_sequences_independently_of_poll_return_order() -> None:
    """One source's stable sequence, not tuple order, should determine Phase-A staging."""
    scheduler = Nca8DeterministicSchedulerV1()
    trace = Nca8TraceBufferV1()
    source = CircuitPollSourceV1(
        circuit_id="alpha",
        poll=lambda cycle_id: (
            _current_result_v1("alpha", 2, cycle_id),
            _current_result_v1("alpha", 1, cycle_id),
        ),
    )

    staged = scheduler.phase_a_poll_and_stage(1, (source,), trace)

    assert tuple(result.result_id for result in staged) == ("alpha:1", "alpha:2")


def test_phase_a_rejects_reused_source_sequence_on_a_later_cycle() -> None:
    """A circuit cannot publish a second result with an already-used local sequence number."""
    scheduler = Nca8DeterministicSchedulerV1()
    trace = Nca8TraceBufferV1()
    first_source = CircuitPollSourceV1(
        circuit_id="alpha",
        poll=lambda cycle_id: (_current_result_v1("alpha", 1, cycle_id),),
    )

    scheduler.phase_a_poll_and_stage(1, (first_source,), trace)
    scheduler.phase_b_freeze_eligible(1, trace)
    scheduler.phase_c_apply_frozen(1, trace)
    scheduler.enter_runtime_phase(1, CyclePhase.FOCAL_COMMITMENT)
    scheduler.enter_runtime_phase(1, CyclePhase.PROJECT_DISPATCH)
    scheduler.phase_f_finish(1, trace)

    reused_source = CircuitPollSourceV1(
        circuit_id="alpha",
        poll=lambda cycle_id: (_current_result_v1("alpha", 1, cycle_id),),
    )
    with pytest.raises(ValueError, match="source_sequence.*increase beyond 1"):
        scheduler.phase_a_poll_and_stage(2, (reused_source,), trace)
