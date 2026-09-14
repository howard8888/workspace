#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase-1C representation, null commitment, buffering, trace, and replay tests."""

from __future__ import annotations

import json

from nca8_contracts import CyclePhase
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionConfigV1, Nca8SessionV1


def test_null_cycle_has_no_focal_operation_pnm_or_task_action() -> None:
    """Attention ablation should preserve representation but prevent focal action."""
    session = Nca8SessionV1(Nca8SessionConfigV1(attention_enabled=False))

    result = session.run_cognitive_cycle()

    assert result.output == NCA8_NO_ACTION
    assert result.environment_action is None
    assert result.commitment.is_null is True
    assert result.commitment.focal_operation_id is None
    assert result.commitment.pnm_id is None
    assert result.commitment.task_action is None
    assert result.pnm_created is False
    assert result.commitment.committed_phase is CyclePhase.PROJECT_DISPATCH
    assert result.posture_support_state.posture.value == "fallen"
    assert result.body_map_state.posture.value == "fallen"
    assert result.posture_support_candidate is not None


def test_body_candidate_is_published_before_phase_d_but_not_selected() -> None:
    """BodyMap may publish a map-state candidate without becoming Attention or WNM."""
    session = Nca8SessionV1(Nca8SessionConfigV1(attention_enabled=False))

    result = session.run_cognitive_cycle()
    lines = session.trace_lines()

    candidate_index = next(index for index, line in enumerate(lines) if "candidate published" in line)
    attention_index = next(index for index, line in enumerate(lines) if "Attention released" in line)
    assert candidate_index < attention_index
    assert result.posture_support_candidate is not None
    assert result.posture_support_candidate.authority == "attention_candidate_only"
    assert result.attention_selection.disposition.value == "release"
    assert result.wnm is None
    assert result.body_map_state.as_dict()["is_wnm"] is False


def test_next_observation_is_buffered_but_not_applied_in_the_same_cycle() -> None:
    """Observation_(n+1) must wait until CognitiveCycle_(n+1)."""
    session = Nca8SessionV1()

    first = session.run_cognitive_cycle()

    assert first.next_observation_number == 2
    assert session.status().pending_observation_number == 2
    assert session._cognitive_runtime.last_applied_observation_number == 1  # pylint: disable=protected-access

    second = session.run_cognitive_cycle()

    assert second.observation_number == 2
    assert session._cognitive_runtime.last_applied_observation_number == 2  # pylint: disable=protected-access
    assert session.status().pending_observation_number == 3


def test_internal_handoff_and_close_precede_null_world_and_input_boundaries() -> None:
    """A null advances time once, after the closed core; no future evidence enters it."""
    session = Nca8SessionV1(Nca8SessionConfigV1(attention_enabled=False))
    session.run_cognitive_cycle()
    events = session.trace_snapshot()
    phase_e = next(event.sequence for event in events if "Phase_E PROJECT_DISPATCH" in event.message)
    handoff = next(event.sequence for event in events if event.channel == "handoff")
    phase_f = next(event.sequence for event in events if "Phase_F LEARNING_SCHEDULE" in event.message)
    close = next(event.sequence for event in events if event.message == "CognitiveCycle_1 closed")
    world = next(event.sequence for event in events if event.channel == "dispatch")
    admitted = next(event.sequence for event in events if event.channel == "input")
    buffered = next(event.sequence for event in events if "Observation_2 buffered" in event.message)
    assert phase_e < handoff < phase_f < close < world < admitted < buffered


def test_identical_input_and_schedule_produce_byte_equivalent_trace_snapshots() -> None:
    """Fresh deterministic sessions should produce byte-identical canonical traces."""
    first = Nca8SessionV1(Nca8SessionConfigV1(seed=23))
    second = Nca8SessionV1(Nca8SessionConfigV1(seed=23))

    first.run_cognitive_cycle()
    second.run_cognitive_cycle()

    assert first.trace_canonical_bytes() == second.trace_canonical_bytes()


def test_canonical_trace_snapshot_is_json_safe_and_phase_explicit() -> None:
    """Canonical bytes should decode cleanly and expose cycle/phase fields."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()

    decoded = json.loads(session.trace_canonical_bytes().decode("utf-8"))
    phase_events = [event for event in decoded if event["phase"] is not None]

    assert phase_events
    assert {event["phase"] for event in phase_events} == {phase.name for phase in CyclePhase}
    assert all(event["cycle_id"] == 1 for event in phase_events)


def test_trace_retention_remains_bounded_across_multiple_cycles() -> None:
    """Detailed phase tracing must not grow without an explicit memory bound."""
    session = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=16))

    for _ in range(4):
        session.run_cognitive_cycle()

    assert len(session.trace_snapshot()) == 16
    assert session.status().trace_retained == 16
