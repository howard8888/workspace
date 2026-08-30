#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Phase-1C representation, null commitment, buffering, trace, and replay tests."""

from __future__ import annotations

import json

from nca8_contracts import CyclePhase
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionConfigV1, Nca8SessionV1


def test_null_cycle_has_no_focal_operation_pnm_or_task_action() -> None:
    """Body representation must not fabricate executive cognition or an action."""
    session = Nca8SessionV1()

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
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()
    lines = session.trace_lines()

    candidate_index = next(index for index, line in enumerate(lines) if "candidate published" in line)
    phase_d_index = next(index for index, line in enumerate(lines) if "Phase_D FOCAL_COMMITMENT" in line)
    assert candidate_index < phase_d_index
    assert result.posture_support_candidate is not None
    assert result.posture_support_candidate.authority == "attention_candidate_only"
    assert result.posture_support_candidate.as_dict()["attention_selected"] is False
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


def test_phase_e_boundary_precedes_phase_f_and_next_observation_buffering() -> None:
    """The world boundary occurs after commitment and new evidence is not applied retroactively."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    lines = session.trace_lines()

    phase_e = next(index for index, line in enumerate(lines) if "Phase_E PROJECT_DISPATCH" in line)
    environment = next(index for index, line in enumerate(lines) if "Action_1:NO_ACTION advanced" in line)
    phase_f = next(index for index, line in enumerate(lines) if "Phase_F LEARNING_SCHEDULE" in line)
    buffered = next(index for index, line in enumerate(lines) if "Observation_2 buffered" in line)

    assert phase_e < environment < phase_f < buffered


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
