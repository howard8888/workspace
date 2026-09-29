#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NCA8 menu wording, read-only inspection, routing, and noninterference tests."""

from __future__ import annotations

import builtins

import pytest

import cca8_cli
import nca8_menu
from nca8_runtime import Nca8SessionConfigV1, Nca8SessionV1
from nca8_trace import render_flow_trace_lines_v1


def test_opening_and_leaving_nca8_menu_does_not_construct_a_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The second brain should remain lazy until a concrete operation needs it."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    result = nca8_menu.run_nca8_experimental_menu_v1(None)

    output = capsys.readouterr().out
    assert result is None
    assert "NCA8 -- EXPERIMENTAL RUNTIME / HIERARCHICAL MOTOR REVIEW" in output
    assert "Current checkpoint: retained Gate A plus isolated reviews through P16-2C-N." in output
    assert "Terminology follows Architecture v10.2; compatibility identifiers and runtime routing are unchanged." in output
    assert "controller does not choose, replace, or rescue the NCA8 action" in output
    assert "not a complete geometric coordinate transformation" in output


def test_status_is_read_only_and_does_not_construct_a_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The status screen should honestly report an absent lazy session."""
    responses = iter(("1", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = nca8_menu.run_nca8_experimental_menu_v1(None)

    output = capsys.readouterr().out
    assert result is None
    assert "No NCA8 session has been created yet." in output
    assert "TERM KEY" in output
    assert "Environment run" in output
    assert "Session generation:" not in output


def test_cognitive_cycle_choice_lazily_creates_and_returns_the_isolated_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first executable operation should run the complete StandUp commitment path."""
    responses = iter(("3", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = nca8_menu.run_nca8_experimental_menu_v1(None)

    output = capsys.readouterr().out
    assert isinstance(result, Nca8SessionV1)
    assert result.status().cognitive_cycles == 1
    assert "input=Observation_1 output=Action_1:STAND_UP next_input=Observation_2" in output
    assert "[nca8:focal]" in output
    assert "primitive=ip:stand_up" in output
    assert "task_action=STAND_UP" in output
    assert "env_action='policy:stand_up'" in output


def test_nca8_menu_does_not_consume_the_shared_main_menu_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the established Main Menu should own the common return pause."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    def _unexpected_pause() -> bool:
        raise AssertionError("NCA8 submenu must not invoke the Main Menu pause")

    monkeypatch.setattr(cca8_cli, "wait_for_main_menu_continue_v1", _unexpected_pause)

    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None


def test_all_five_menu_labels_explain_their_scope(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Users must be able to distinguish inspection, one-cycle stepping, and a fresh run."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    output = capsys.readouterr().out

    for label in (
        "1) Show session status for the current isolated NCA8 session",
        "2) Create or reset the current isolated NCA8 session",
        "3) Advance the current NCA8 session by exactly one cognitive cycle",
        "4) Show the explanatory trace for the current NCA8 session (text + flowchart)",
        "5) Start fresh and automatically run the complete Gate-A StandUp demonstration",
        "[Enter] Return to Main Menu",
    ):
        assert label in output
    assert "conscious-like" not in output


@pytest.mark.parametrize("enabled", (False, True))
def test_status_explains_real_settings_without_mutating_session(
    enabled: bool,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The key accompanies real configuration values; inspecting cannot create body evidence."""
    config = Nca8SessionConfigV1(
        seed=31,
        trace_capacity=17,
        attention_enabled=enabled,
        navigation_enabled=enabled,
        body_action_handoff_enabled=enabled,
        support_observation_enabled=enabled,
    )
    session = Nca8SessionV1(config)
    before = session.status()
    trace_before = session.trace_canonical_bytes()
    pending_before = session.pending_observation
    responses = iter(("1", "1", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out

    assert "Session generation: 1" in output
    assert "Environment run: 1" in output
    assert "Reproducibility seed: 31" in output
    assert "Cognitive cycles completed: 0" in output
    assert "Next sensory input waiting to be processed: Observation_1" in output
    assert "Current posture: (not yet processed)" in output
    assert "Current physical support: (not yet processed)" in output
    assert "Trace entries retained: 2 / 17" in output
    label = "enabled" if enabled else "disabled"
    for heading in ("Attention", "ExecNav", "Body-to-environment action handoff", "Read-only support measurements"):
        assert f"{heading}: {label}" in output
    assert "not a cognitive episode" in output
    assert "environment-run counter starts at 1 again" in output
    assert "@r1 means durable revision 1" in output
    assert "episode=" not in output
    assert "environment_episode_index" not in output
    assert "conscious-like" not in output
    assert session.status() == before
    assert session.trace_canonical_bytes() == trace_before
    assert session.pending_observation is pending_before
    assert session.posture_support_state is None
    assert session.body_map_state is None
    assert session.support_configuration is None
    assert session.config is config


def test_status_after_gate_a_reports_current_values_not_the_startup_example(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An explanatory panel must not turn illustrative startup numbers into hard-coded status."""
    session = Nca8SessionV1()
    session.run_gate_a(reset_first=False)
    before = session.status()
    trace_before = session.trace_canonical_bytes()
    responses = iter(("1", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out

    assert "Cognitive cycles completed: 6" in output
    assert "Next sensory input waiting to be processed: Observation_7" in output
    assert "Current posture: standing" in output
    assert "Current physical support: stable" in output
    assert "Last Attention decision: release" in output
    assert "Current WNM: (none)" in output
    assert "Selected procedure: (none)" in output
    assert "Current PNM: (none)" in output
    assert "Last StandUp prediction assessment: success" in output
    assert "Trace entries retained: 158 / 256" in output
    assert session.status() == before
    assert session.trace_canonical_bytes() == trace_before


def test_create_then_reset_explains_isolation_and_preserves_lifecycle_rules(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Option 2 creates Session Generation one, then resets that same session without running a cycle."""
    responses = iter(("2", "2", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    session = nca8_menu.run_nca8_experimental_menu_v1(None)
    output = capsys.readouterr().out

    assert isinstance(session, Nca8SessionV1)
    assert session.status().lifecycle_generation == 2
    assert session.status().environment_episode_index == 1
    assert session.status().cognitive_cycles == 0
    assert session.status().pending_observation_number == 1
    assert session.status().trace_retained == 2
    assert "Session generation: 1" in output
    assert "Session generation: 2" in output
    assert "Environment run: 1" in output
    assert "Environment run: 2" not in output
    assert "does not share or alter the cognitive state" in output
    assert "clears its previous trace" in output
    assert "This reset is not a new cognitive episode" in output
    assert "TERM KEY" not in output


def test_menu_reset_matches_direct_reset_and_leaves_other_session_unchanged(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Reset explanations cannot add steps, alter settings, or reach another session's state."""
    config = Nca8SessionConfigV1(seed=11)
    session = Nca8SessionV1(config)
    direct = Nca8SessionV1(config)
    untouched = Nca8SessionV1()
    untouched.run_cognitive_cycle()
    untouched_status = untouched.status()
    untouched_trace = untouched.trace_canonical_bytes()
    session.run_cognitive_cycle()
    direct.run_cognitive_cycle()
    direct.reset()
    responses = iter(("2", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    capsys.readouterr()
    assert session.status() == direct.status()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert session.config is config
    assert untouched.status() == untouched_status
    assert untouched.trace_canonical_bytes() == untouched_trace


def test_two_step_choices_then_trace_show_both_cycles_and_do_not_reset(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Option 3 accumulates cycles in one session; option 4 renders both without adding a third."""
    direct = Nca8SessionV1()
    direct.run_cognitive_cycle()
    direct.run_cognitive_cycle()
    responses = iter(("3", "3", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    session = nca8_menu.run_nca8_experimental_menu_v1(None)
    output = capsys.readouterr().out

    assert isinstance(session, Nca8SessionV1)
    assert session.status() == direct.status()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert session.status().lifecycle_generation == 1
    assert session.status().cognitive_cycles == 2
    assert "Only one cognitive cycle is run" in output
    assert "Close CognitiveCycle_1" in output
    assert "committed output: Action_1:STAND_UP" in output
    assert "Close CognitiveCycle_2" in output
    assert "committed output: Action_2:STAND_UP" in output
    assert "Open CognitiveCycle_3" not in output
    assert "not just the last cycle" in output
    assert "sparse task-linked PNM for the selected operation" in output


def test_trace_without_session_explains_absence_without_creating_one(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Requesting a trace cannot create a session just to have something to display."""
    responses = iter(("4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    output = capsys.readouterr().out
    assert "No NCA8 session has been created, so there is no trace to show." in output
    assert "Showing the trace is read-only" in output
    assert "Trace entries retained:" not in output


def test_trace_panel_reports_actual_capacity_and_keeps_only_retained_entries(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The panel must not promise full session history once early events have been discarded."""
    session = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=5))
    session.run_cognitive_cycle()
    session.run_cognitive_cycle()
    before = session.status()
    trace_before = session.trace_canonical_bytes()
    expected_text = "\n".join(render_flow_trace_lines_v1(session.trace_snapshot(), reader_guidance=True))
    responses = iter(("4", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    output = capsys.readouterr().out

    assert "Trace entries retained: 5 / 5" in output
    assert "oldest entries are discarded" in output.lower() or "oldest entries\nare discarded" in output.lower()
    assert output.count(expected_text) == 2
    assert "EARLIER RECORDS NOT RETAINED" in output
    assert "PARTIAL VIEW" in output
    assert "Session generation 1 initialized" not in output
    assert "Open CognitiveCycle_1" not in output
    assert session.status() == before
    assert session.trace_canonical_bytes() == trace_before


def test_gate_a_menu_replaces_previous_session_and_matches_direct_trace(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """New headings cannot change the six-cycle/five-action result or its canonical trace."""
    config = Nca8SessionConfigV1(seed=23)
    prior = Nca8SessionV1(config)
    prior.run_cognitive_cycle()
    prior_status = prior.status()
    prior_trace = prior.trace_canonical_bytes()
    direct = Nca8SessionV1(config)
    direct.run_gate_a(reset_first=False)
    responses = iter(("5", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    session = nca8_menu.run_nca8_experimental_menu_v1(prior)
    output = capsys.readouterr().out

    assert isinstance(session, Nca8SessionV1)
    assert session is not prior
    assert session.config is config
    assert session.status() == direct.status()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert prior.status() == prior_status
    assert prior.trace_canonical_bytes() == prior_trace
    assert "Maximum cognitive cycles for this demonstration: 10" in output
    assert "standing=True cycles=6 stand_up_actions=5" in output
    assert "final_posture=standing final_support=stable outcome=success" in output
    assert "[nca8:support_observation]" not in output
    for cycle in range(1, 7):
        assert f"Open CognitiveCycle_{cycle} with Observation_{cycle}" in output


def test_gate_a_limit_display_uses_existing_configuration_without_changing_it(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A shorter configured limit must be shown and enforced, not replaced by the help example."""
    config = Nca8SessionConfigV1(gate_a_max_cycles=2)
    prior = Nca8SessionV1(config)
    direct = Nca8SessionV1(config)
    direct.run_gate_a(reset_first=False)
    responses = iter(("5", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    session = nca8_menu.run_nca8_experimental_menu_v1(prior)
    output = capsys.readouterr().out

    assert isinstance(session, Nca8SessionV1)
    assert session.config is config
    assert session.status() == direct.status()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert "Maximum cognitive cycles for this demonstration: 2" in output
    assert "standing=False cycles=2 stand_up_actions=2" in output


@pytest.mark.parametrize("operation", ("3", "5"))
def test_menu_explanations_do_not_enable_disabled_cognitive_controls(
    operation: str,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Presentation changes must not defeat the existing Attention-disabled negative control."""
    config = Nca8SessionConfigV1(attention_enabled=False, gate_a_max_cycles=2)
    session = Nca8SessionV1(config)
    direct = Nca8SessionV1(config)
    if operation == "3":
        direct.run_cognitive_cycle()
    else:
        direct.run_gate_a(reset_first=False)
    responses = iter((operation, ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = nca8_menu.run_nca8_experimental_menu_v1(session)
    capsys.readouterr()

    assert isinstance(result, Nca8SessionV1)
    assert result.status() == direct.status()
    assert result.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert result.status().current_posture == "fallen"
    assert result.status().last_task_action is None
    assert result.config is config


def test_unknown_choice_still_returns_to_menu_without_constructing_a_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """An unsupported choice remains inert with the separate continuous stand-follow review."""
    responses = iter(("99", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    assert "Please choose 1-15, or press Enter to return." in capsys.readouterr().out


def test_v102_introduction_keeps_gate_a_and_post_n_review_scopes_distinct(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A terminology update must neither invent missing learning nor describe accepted Rest as still absent."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")
    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
    output = " ".join(capsys.readouterr().out.split())
    assert "The same Selected NM serves in the WNM role" in output
    assert "Gate A serializes that content in a source-linked sample" in output
    assert "P16-2C is accepted at its bounded experimental scope" in output
    assert "hard-newborn B99 and default promotion remain open" in output
    assert "15) Feeding and safe Rest: retained P16-2C reviews (A-N)" in output
    assert "latch, milk, rest and B99 remain open" not in output
    assert "The Rest review is the P16-2C closure candidate" not in output


def test_shortcut_matches_manual_cycle_then_trace_without_nested_input(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """The convenience entry must use precisely the manual option-3/option-4 machinery."""
    responses = iter(("3", "4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    manual = nca8_menu.run_nca8_experimental_menu_v1(None)
    capsys.readouterr()
    assert manual is not None

    def unexpected_input(_prompt: str = "") -> str:
        raise AssertionError("The shortcut must not ask for nested choices")

    monkeypatch.setattr(builtins, "input", unexpected_input)
    shortcut = nca8_menu.run_nca8_experimental_menu_v1(None, run_one_cycle_with_trace=True)
    output = capsys.readouterr().out
    assert shortcut is not None
    assert "[nca8:error]" not in output
    assert shortcut.status() == manual.status()
    assert shortcut.trace_canonical_bytes() == manual.trace_canonical_bytes()
    expected = "\n".join(render_flow_trace_lines_v1(shortcut.trace_snapshot(), reader_guidance=True))
    assert output.count(expected) == 1
    assert "EXPERIMENTAL RUNTIME / HIERARCHICAL MOTOR REVIEW" not in output


def test_shortcut_initializes_once_calls_one_cycle_and_renders_afterward(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Count actual construction, cycle, external step and renderer calls, not only menu labels."""
    original_init = Nca8SessionV1.__init__
    original_cycle = Nca8SessionV1.run_cognitive_cycle
    original_render = nca8_menu.render_flow_trace_lines_v1
    operations: list[str] = []
    created: list[Nca8SessionV1] = []

    def initialize(self: Nca8SessionV1, config: Nca8SessionConfigV1 | None = None) -> None:
        operations.append("initialize")
        original_init(self, config)
        created.append(self)

    def cycle(self: Nca8SessionV1):
        operations.append("cycle")
        result = original_cycle(self)
        assert result.cycle_id == 1 and result.environment_step == 1
        return result

    def render(events, **kwargs):
        operations.append("render")
        assert kwargs == {"reader_guidance": True}
        assert events == created[0].trace_snapshot()
        assert created[0].status().cognitive_cycles == 1
        return original_render(events, **kwargs)

    monkeypatch.setattr(Nca8SessionV1, "__init__", initialize)
    monkeypatch.setattr(Nca8SessionV1, "run_cognitive_cycle", cycle)
    monkeypatch.setattr(nca8_menu, "render_flow_trace_lines_v1", render)
    result = nca8_menu.run_nca8_experimental_menu_v1(None, run_one_cycle_with_trace=True)
    assert operations == ["initialize", "cycle", "render"]
    assert created == [result]
    assert result is not None and result.status().lifecycle_generation == 1
    assert "[nca8:error]" not in capsys.readouterr().out


def test_shortcut_preserves_config_and_session_on_repeated_selection(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Repeated selections continue the retained session; they cannot reset to Cycle 1."""
    config = Nca8SessionConfigV1(seed=27, trace_capacity=120)
    session = Nca8SessionV1(config)
    direct = Nca8SessionV1(config)
    for count in range(1, 4):
        direct.run_cognitive_cycle()
        assert nca8_menu.run_nca8_experimental_menu_v1(session, run_one_cycle_with_trace=True) is session
        assert session.status() == direct.status()
        assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
        assert session.status().cognitive_cycles == count
        assert session.config is config
    assert "[nca8:error]" not in capsys.readouterr().out


@pytest.mark.parametrize("disabled", ("attention_enabled", "navigation_enabled", "body_action_handoff_enabled"))
def test_shortcut_preserves_each_disabled_cognitive_control(
    disabled: str, capsys: pytest.CaptureFixture[str],
) -> None:
    """A convenience menu must not turn a disabled control on to manufacture movement."""
    config = Nca8SessionConfigV1(**{disabled: False})
    session = Nca8SessionV1(config)
    direct = Nca8SessionV1(config)
    expected = direct.run_cognitive_cycle()
    assert nca8_menu.run_nca8_experimental_menu_v1(session, run_one_cycle_with_trace=True) is session
    assert session.status() == direct.status()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    assert expected.environment_step == 1
    assert expected.environment_action is None
    assert "[nca8:error]" not in capsys.readouterr().out


def test_shared_trace_helper_is_neutral_and_preserves_next_cycle(capsys: pytest.CaptureFixture[str]) -> None:
    """Repeated display must not change input identity, RNG, trace bytes or the next real result."""
    session = Nca8SessionV1()
    direct = Nca8SessionV1()
    session.run_cognitive_cycle()
    direct.run_cognitive_cycle()
    pending = session.pending_observation
    before = session.status()
    trace = session.trace_canonical_bytes()
    rng = session._rng.getstate()  # pylint: disable=protected-access
    for _ in range(2):
        nca8_menu._print_session_trace_v1(session)  # pylint: disable=protected-access
    assert session.status() == before
    assert session.trace_canonical_bytes() == trace
    assert session.pending_observation is pending
    assert session._rng.getstate() == rng  # pylint: disable=protected-access
    assert session.run_cognitive_cycle() == direct.run_cognitive_cycle()
    assert session.trace_canonical_bytes() == direct.trace_canonical_bytes()
    capsys.readouterr()


def test_shortcut_keeps_bounded_trace_history(capsys: pytest.CaptureFixture[str]) -> None:
    """The shortcut reuses real retained history rather than regenerating discarded cycles."""
    session = Nca8SessionV1(Nca8SessionConfigV1(trace_capacity=5))
    session.run_cognitive_cycle()
    assert nca8_menu.run_nca8_experimental_menu_v1(session, run_one_cycle_with_trace=True) is session
    output = capsys.readouterr().out
    assert session.status().cognitive_cycles == 2
    assert "Trace entries retained: 5 / 5" in output
    assert "EARLIER RECORDS NOT RETAINED" in output
    assert "Open CognitiveCycle_1" not in output


def test_shortcut_initialization_failure_returns_none_without_retry(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Failed initialization must be reported, not repeated or replaced by a legacy run."""
    calls: list[str] = []

    def fail_init(_self: Nca8SessionV1, _config: Nca8SessionConfigV1 | None = None) -> None:
        calls.append("initialize")
        raise RuntimeError("initialization fault")

    monkeypatch.setattr(Nca8SessionV1, "__init__", fail_init)
    assert nca8_menu.run_nca8_experimental_menu_v1(None, run_one_cycle_with_trace=True) is None
    assert calls == ["initialize"]
    output = capsys.readouterr().out
    assert "initialization fault" in output and "No automatic retry" in output


@pytest.mark.parametrize("fault", (RuntimeError, KeyboardInterrupt))
def test_shortcut_retains_new_stopped_session_after_world_failure(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str], fault: type[BaseException],
) -> None:
    """A first-call failure after construction cannot lose the session or replay its consumed handoff."""
    from nca8_adapters import Nca8EnvironmentBridgeV1  # pylint: disable=import-outside-toplevel

    calls: list[object] = []

    def fail_world(_self: Nca8EnvironmentBridgeV1, action: object):
        calls.append(action)
        raise fault("external step fault")

    monkeypatch.setattr(Nca8EnvironmentBridgeV1, "advance_task_action", fail_world)
    session = nca8_menu.run_nca8_experimental_menu_v1(None, run_one_cycle_with_trace=True)
    assert session is not None
    assert len(calls) == 1 and session.status().reset_required
    before = session.status()
    trace = session.trace_canonical_bytes()
    assert nca8_menu.run_nca8_experimental_menu_v1(session, run_one_cycle_with_trace=True) is session
    assert len(calls) == 1
    assert session.status() == before and session.trace_canonical_bytes() == trace
    output = capsys.readouterr().out
    assert "Explicit reset is required" in output
    assert "No automatic retry" in output


def test_shortcut_trace_failure_does_not_rerun_completed_cycle(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Rendering failure leaves the successfully advanced session ready for its next explicit selection."""
    calls: list[str] = []

    def fail_render(*_args, **_kwargs):
        calls.append("render")
        raise RuntimeError("display fault")

    monkeypatch.setattr(nca8_menu, "render_flow_trace_lines_v1", fail_render)
    session = nca8_menu.run_nca8_experimental_menu_v1(None, run_one_cycle_with_trace=True)
    assert session is not None
    assert calls == ["render"]
    assert session.status().cognitive_cycles == 1
    assert session.status().pending_observation_number == 2
    assert session.status().pending_input_available and not session.status().reset_required
    output = capsys.readouterr().out
    assert "display fault" in output and "No automatic retry" in output
    monkeypatch.setattr(nca8_menu, "render_flow_trace_lines_v1", render_flow_trace_lines_v1)
    assert nca8_menu.run_nca8_experimental_menu_v1(session, run_one_cycle_with_trace=True) is session
    assert session.status().cognitive_cycles == 2
    assert "[nca8:error]" not in capsys.readouterr().out
