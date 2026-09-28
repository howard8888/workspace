#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Regression tests for explanatory Gate-A trace rendering and lifecycle numbering."""

from __future__ import annotations

import builtins

import pytest

import nca8_menu
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import render_explanatory_trace_lines_v1


def test_explanatory_rendering_is_read_only_and_preserves_compact_trace() -> None:
    """Teaching prose must not change retained events, compact output, or canonical JSON."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    compact_before = session.trace_lines()
    canonical_before = session.trace_canonical_bytes()

    explanatory = render_explanatory_trace_lines_v1(session.trace_snapshot())

    assert len(explanatory) == len(compact_before)
    assert session.trace_lines() == compact_before
    assert session.trace_canonical_bytes() == canonical_before


def test_explanatory_trace_makes_gate_a_source_authority_and_timing_explicit() -> None:
    """The expanded trace should explain the causal distinctions found during manual review."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    text = "\n".join(render_explanatory_trace_lines_v1(session.trace_snapshot()))

    assert "observation-ingress bookkeeping result and one body-sensory interpretation result" in text
    assert "did not itself interpret sensory content or update a NavMap" in text
    assert "No new NavMap was created" in text
    assert "innate NM posture_support@r1 was not revised" in text
    assert "Attention selected the NM through its configuration reference; it did not choose StandUp" in text
    assert "source-linked WNM sample for Attention's Selected NM" in text
    assert "Attention did not make this action choice" in text
    assert "PNM is predicted information, not an observation or confirmed completion" in text
    assert "Outcome authority comes from later evidence" in text


def test_explanatory_no_action_dispatch_does_not_look_like_rejected_authorization() -> None:
    """NO_ACTION should say authorization was unnecessary, while compact telemetry stays unchanged."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    explanatory = render_explanatory_trace_lines_v1(session.trace_snapshot())

    expanded_line = next(line for line in explanatory if line.startswith("[nca8:dispatch]") and ":NO_ACTION" in line)
    compact_line = next(line for line in session.trace_lines() if line.startswith("[nca8:dispatch]") and ":NO_ACTION" in line)

    assert "No BodyMap authorization was required because there was no task to authorize" in expanded_line
    assert "body_authorized=False" not in expanded_line
    assert "body_authorized=False" in compact_line


def test_fresh_gate_a_menu_demonstration_always_starts_at_generation_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Menu 5 should replace any retained session rather than reset it into Session Generation two."""
    prior_session = Nca8SessionV1(Nca8SessionConfigV1(seed=31))
    prior_session.reset()
    assert prior_session.status().lifecycle_generation == 2

    responses = iter(("5", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = nca8_menu.run_nca8_experimental_menu_v1(prior_session)
    output = capsys.readouterr().out

    assert isinstance(result, Nca8SessionV1)
    assert result is not prior_session
    assert result.status().lifecycle_generation == 1
    assert result.config == prior_session.config
    assert result.status().seed == 31
    assert "Session generation: 1" in output
    assert "NCA8 GUIDED FLOW TRACE" in output
    assert "generation=1" in output
    assert "generation=2" not in output


def test_explicit_reset_still_increments_lifecycle_generation() -> None:
    """The Session Generation fix must not weaken ordinary explicit-reset bookkeeping."""
    session = Nca8SessionV1()

    assert session.status().lifecycle_generation == 1
    session.run_gate_a(reset_first=False)
    assert session.status().lifecycle_generation == 1

    status = session.reset()
    assert status.lifecycle_generation == 2


def test_explanatory_no_action_dispatch_distinguishes_rejected_body_handoff() -> None:
    """A body-authorization ablation must read as a rejected handoff, not as no proposed task."""
    session = Nca8SessionV1(Nca8SessionConfigV1(body_action_handoff_enabled=False))

    result = session.run_cognitive_cycle()
    explanatory = render_explanatory_trace_lines_v1(session.trace_snapshot())

    phase_e_line = next(
        line
        for line in explanatory
        if line.startswith("[nca8:runtime]") and "Phase_E PROJECT_DISPATCH committed Action_1:NO_ACTION" in line
    )
    dispatch_line = next(
        line for line in explanatory if line.startswith("[nca8:dispatch]") and "Action_1:NO_ACTION" in line
    )

    assert result.navigation.selected_primitive_id == "ip:stand_up"
    assert result.pnm is not None
    assert result.body_handoff is not None
    assert result.body_handoff.authorized is False
    assert "BodyMap did not authorize the task selected by ExecNav" in phase_e_line
    assert "BodyMap rejected the selected task's action envelope" in dispatch_line
    assert "blocked handoff" in dispatch_line
    assert "body_authorized=False" in dispatch_line
    assert "there was no task to authorize" not in dispatch_line


@pytest.mark.parametrize("settings", (
    {}, {"attention_enabled": False}, {"navigation_enabled": False},
    {"body_action_handoff_enabled": False},
    {"support_observation_enabled": True, "support_dynamics_enabled": True},
))
def test_v102_display_does_not_rewrite_protocol_or_affect_the_next_cycle(settings: dict[str, bool]) -> None:
    """Render every supported teaching view, preserving raw records and subsequent behavior under ablations."""
    from nca8_trace import render_flow_trace_lines_v1

    config = Nca8SessionConfigV1(**settings)
    session = Nca8SessionV1(config)
    control = Nca8SessionV1(config)
    session.run_cognitive_cycle()
    control.run_cognitive_cycle()
    events = session.trace_snapshot()
    raw_before = session.trace_canonical_bytes()
    compact_before = session.trace_lines()
    status_before = session.status()

    render_explanatory_trace_lines_v1(events)
    render_flow_trace_lines_v1(events)

    assert session.trace_snapshot() == events
    assert session.trace_canonical_bytes() == raw_before == control.trace_canonical_bytes()
    assert session.trace_lines() == compact_before == control.trace_lines()
    assert session.status() == status_before == control.status()
    session.run_cognitive_cycle()
    control.run_cognitive_cycle()
    assert session.trace_canonical_bytes() == control.trace_canonical_bytes()
    assert session.status() == control.status()


def test_v102_procedure_labels_leave_primitive_event_names_and_fields_exact() -> None:
    """The human label changes, not the event schema or the strings used to recognize old records."""
    session = Nca8SessionV1()
    session.run_cognitive_cycle()
    events = session.trace_snapshot()
    query = next(event for event in events if event.message == "primitive applicability evaluated from the WNM")
    commitment = next(event for event in events if event.message == "Navigation commitment completed")
    assert query.channel == commitment.channel == "navigation"
    assert query.as_dict()["details"]["primitive_id"] == "ip:stand_up"
    assert commitment.as_dict()["details"]["selected_primitive_id"] == "ip:stand_up"
    assert "selected_procedure_id" not in commitment.as_dict()["details"]
    assert "ExecNav asked procedure" in query.render_explanatory()
    assert "ExecNav selected and applied procedure" in commitment.render_explanatory()
    assert "primitive applicability evaluated from the WNM" in query.render()
    assert "Navigation commitment completed" in commitment.render()


@pytest.mark.parametrize("message", (
    "procedure applicability evaluated from the WNM", "ExecNav commitment completed",
))
def test_display_spelling_does_not_become_an_unapproved_raw_event_protocol(message: str) -> None:
    """A new-looking message in an old channel remains unknown; presentation cannot expand event recognition."""
    from nca8_trace import Nca8TraceEventV1

    event = Nca8TraceEventV1(1, "navigation", message, details=(("primitive_id", "ip:stand_up"),))
    assert event.render_explanatory() == event.render()
