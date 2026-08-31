#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""End-to-end StandUp Gate-A acceptance and ablation tests."""

from __future__ import annotations

from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1


def test_fresh_hard_session_stands_through_new_cognitive_path() -> None:
    """The first vertical goat should reach standing from later current body evidence."""
    session = Nca8SessionV1()

    summary = session.run_gate_a()

    assert summary.achieved_standing is True
    assert 2 <= summary.stand_up_actions <= summary.cycles_run
    assert summary.final_posture == "standing"
    assert summary.final_support == "stable"
    assert summary.last_outcome_status == "success"
    assert summary.successful_application_id is not None
    assert session.status().current_posture == "standing"
    assert session.status().current_pnm_id is None


def test_gate_a_success_closes_the_correct_last_standup_application() -> None:
    """Standing evidence should close the PNM created by the preceding applied task."""
    session = Nca8SessionV1()

    summary = session.run_gate_a()
    outcomes = session._prediction.outcome_history()  # pylint: disable=protected-access
    successes = [outcome for outcome in outcomes if outcome.status.value == "success"]

    assert len(successes) == 1
    assert successes[0].application_id == summary.successful_application_id
    assert successes[0].pnm_id == f"pnm:{summary.successful_application_id}"
    assert successes[0].evaluated_cycle == summary.cycles_run


def test_hard_environment_does_not_passively_stand_when_attention_is_ablated() -> None:
    """Without focal selection, passive time must not complete the hard StandUp task."""
    session = Nca8SessionV1(Nca8SessionConfigV1(attention_enabled=False, gate_a_max_cycles=10))

    summary = session.run_gate_a()

    assert summary.achieved_standing is False
    assert summary.stand_up_actions == 0
    assert summary.final_posture == "fallen"
    assert summary.reason == "bounded_gate_a_cycle_limit_reached_without_success"


def test_fresh_gate_a_runs_are_byte_deterministic() -> None:
    """Identical isolated sessions should produce identical Gate-A summaries and traces."""
    first = Nca8SessionV1(Nca8SessionConfigV1(seed=31))
    second = Nca8SessionV1(Nca8SessionConfigV1(seed=31))

    summary_first = first.run_gate_a()
    summary_second = second.run_gate_a()

    assert summary_first.as_dict() == summary_second.as_dict()
    assert first.trace_canonical_bytes() == second.trace_canonical_bytes()
