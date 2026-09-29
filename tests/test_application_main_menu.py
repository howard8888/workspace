#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Preservation tests for the two-choice front door and real runner integration.

The menu helper controls navigation only. These tests also exercise the actual
runner and NCA8 entry point together, keeping legacy state and the retained NCA8
session separate. Simulated keyboard input belongs only in tests, never in the
production shortcut implementation.
"""

from __future__ import annotations

import argparse
import builtins
from pathlib import Path
from typing import Any

import pytest

import cca8_cli
import cca8_controller
import cca8_main_menu
import cca8_run
import nca8_menu
from nca8_runtime import Nca8SessionV1


def _input_sequence(monkeypatch: pytest.MonkeyPatch, replies: tuple[str, ...]) -> list[str]:
    """Install a finite terminal script and retain every requested prompt."""
    pending = iter(replies)
    prompts: list[str] = []

    def read(prompt: str = "") -> str:
        prompts.append(prompt)
        return next(pending)

    monkeypatch.setattr(builtins, "input", read)
    return prompts


def _runner_args(**overrides: Any) -> argparse.Namespace:
    """Supply the established interactive arguments without changing CLI parsing."""
    values = {
        "load": None, "autosave": None, "save": None, "profile": "goat",
        "no_intro": True, "hal": False, "body": None,
        "hal_status_str": "off", "body_status_str": "none",
    }
    values.update(overrides)
    return argparse.Namespace(**values)


def _watch_nca8_calls(monkeypatch: pytest.MonkeyPatch) -> list[tuple[bool, Nca8SessionV1 | None, Nca8SessionV1 | None]]:
    """Observe the real menu's input/output handles without replacing its work."""
    original = nca8_menu.run_nca8_experimental_menu_v1
    calls: list[tuple[bool, Nca8SessionV1 | None, Nca8SessionV1 | None]] = []

    def run(session: Nca8SessionV1 | None, *, run_one_cycle_with_trace: bool = False) -> Nca8SessionV1 | None:
        result = original(session, run_one_cycle_with_trace=run_one_cycle_with_trace)
        calls.append((run_one_cycle_with_trace, session, result))
        return result

    monkeypatch.setattr(nca8_menu, "run_nca8_experimental_menu_v1", run)
    return calls


def test_front_page_has_legacy_first_and_cycle_second(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """The new numbering must not inherit Planning's superseded opposite order."""
    prompts = _input_sequence(monkeypatch, ("2",))
    assert cca8_main_menu.read_application_menu_choice_v1(False) == ("nca8-cycle", False)
    output = capsys.readouterr().out
    assert output.index("1) Legacy Main Menu") < output.index("2) Run a NCA8 Cognitive Cycle")
    assert "3)" not in output
    assert "Q) Quit" in output
    assert prompts == ["Enter Menu Choice: "]


@pytest.mark.parametrize("selection", tuple(str(i) for i in range(1, 14)) + ("14", "35", "51", "watch", "scope", "s", "quit"))
def test_legacy_numbers_and_commands_are_returned_unchanged(monkeypatch: pytest.MonkeyPatch, selection: str) -> None:
    """The extra page cannot renumber or reinterpret any old command after Legacy is selected."""
    prompts = _input_sequence(monkeypatch, ("1", selection))
    assert cca8_main_menu.read_application_menu_choice_v1(False) == (selection, True)
    assert prompts[-1] == cca8_cli.MAIN_MENU_PROMPT


def test_legacy_mode_stays_active_between_operations(monkeypatch: pytest.MonkeyPatch) -> None:
    """A completed legacy operation returns to the legacy page, not another startup."""
    prompts = _input_sequence(monkeypatch, ("12",))
    assert cca8_main_menu.read_application_menu_choice_v1(True) == ("12", True)
    assert prompts == [cca8_cli.MAIN_MENU_PROMPT]


@pytest.mark.parametrize("back", ("b", "B", "Back", " back "))
def test_back_returns_to_front_without_dispatching_an_operation(monkeypatch: pytest.MonkeyPatch, back: str) -> None:
    """Only the eventual front-page selection is returned to the runner."""
    prompts = _input_sequence(monkeypatch, (back, "2"))
    assert cca8_main_menu.read_application_menu_choice_v1(True) == ("nca8-cycle", False)
    assert prompts == [cca8_cli.MAIN_MENU_PROMPT, "Enter Menu Choice: "]


def test_blank_invalid_and_old_numbers_do_not_select_front_page_runtime(
    monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str],
) -> None:
    """Old hidden commands are available through Legacy, not accidental front-page defaults."""
    _input_sequence(monkeypatch, ("", "99", "35", "scope", "nca8-cycle", "Q"))
    assert cca8_main_menu.read_application_menu_choice_v1(False) == ("quit", False)
    assert capsys.readouterr().out.count("Please choose 1, 2, or Q to quit.") == 5


@pytest.mark.parametrize("selection", ("q", "Q", "quit", " Quit "))
def test_front_quit_returns_existing_semantic_quit(monkeypatch: pytest.MonkeyPatch, selection: str) -> None:
    """The runner, not the new helper, remains responsible for final save and exit."""
    _input_sequence(monkeypatch, (selection,))
    assert cca8_main_menu.read_application_menu_choice_v1(False) == ("quit", False)


@pytest.mark.parametrize("error_type", (EOFError, KeyboardInterrupt))
@pytest.mark.parametrize("legacy", (False, True))
def test_navigation_interrupts_reach_existing_runner_boundary(
    monkeypatch: pytest.MonkeyPatch, error_type: type[BaseException], legacy: bool,
) -> None:
    """Menu input must not swallow an interruption into a default cycle choice."""
    def interrupt(_prompt: str = "") -> str:
        raise error_type()

    monkeypatch.setattr(builtins, "input", interrupt)
    with pytest.raises(error_type):
        cca8_main_menu.read_application_menu_choice_v1(legacy)


def test_real_runner_keeps_startup_profile_and_boot_before_front_page(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path,
) -> None:
    """The new menu is reached only after the existing banner, profile and boot sequence."""
    monkeypatch.chdir(tmp_path)
    order: list[str] = []
    original_boot = cca8_run.boot_prime_stand
    original_read = cca8_main_menu.read_application_menu_choice_v1

    def header(*_args: Any, **_kwargs: Any) -> None:
        order.append("banner")

    def profile(_ctx: Any, _world: Any) -> dict[str, Any]:
        order.append("profile")
        return {"name": "Mountain Goat", "winners_k": 2}

    def boot(world: Any, ctx: Any) -> Any:
        order.append("boot")
        return original_boot(world, ctx)

    def read(legacy: bool) -> tuple[str, bool]:
        order.append("menu")
        return original_read(legacy)

    monkeypatch.setattr(cca8_run, "print_header", header)
    monkeypatch.setattr(cca8_run, "choose_profile", profile)
    monkeypatch.setattr(cca8_run, "boot_prime_stand", boot)
    monkeypatch.setattr(cca8_main_menu, "read_application_menu_choice_v1", read)
    _input_sequence(monkeypatch, ("q",))
    cca8_run.interactive_loop(_runner_args(no_intro=False, profile=None))
    assert order == ["banner", "profile", "boot", "menu"]


def test_real_runner_shortcut_runs_once_then_returns_to_front(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The real runner must dispatch the shortcut without asking for any nested NCA8 choices."""
    monkeypatch.chdir(tmp_path)
    calls = _watch_nca8_calls(monkeypatch)
    prompts = _input_sequence(monkeypatch, ("2", "", "q"))
    cca8_run.interactive_loop(_runner_args())
    assert len(calls) == 1
    flag, prior, session = calls[0]
    assert flag is True and prior is None and session is not None
    assert session.status().cognitive_cycles == 1
    assert prompts == ["Enter Menu Choice: ", "Please press ENTER to continue...", "Enter Menu Choice: "]
    output = capsys.readouterr().out
    assert "Close CognitiveCycle_1" in output
    assert "Open CognitiveCycle_2" not in output
    assert output.index("[nca8:cycle]") < output.index("EXPLANATORY TRACE FOR THE CURRENT NCA8 SESSION")


def test_repeated_shortcuts_and_legacy_manual_route_share_one_handle(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Two shortcuts, a manual NCA8 step, and a final shortcut continue the same session."""
    monkeypatch.chdir(tmp_path)
    calls = _watch_nca8_calls(monkeypatch)
    _input_sequence(monkeypatch, ("2", "", "2", "", "1", "1", "4", "3", "4", "", "", "b", "2", "", "q"))
    cca8_run.interactive_loop(_runner_args())
    assert [row[0] for row in calls] == [True, True, False, True]
    session = calls[0][2]
    assert session is not None and calls[0][1] is None
    assert all(row[1] is session and row[2] is session for row in calls[1:])
    assert session.status().lifecycle_generation == 1
    assert session.status().cognitive_cycles == 4
    assert session.status().pending_observation_number == 5


def test_manual_reset_remains_effective_for_next_shortcut(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """An explicit reset from the legacy NCA8 menu resets the same retained handle only once."""
    monkeypatch.chdir(tmp_path)
    calls = _watch_nca8_calls(monkeypatch)
    _input_sequence(monkeypatch, ("2", "", "1", "1", "4", "2", "", "", "b", "2", "", "q"))
    cca8_run.interactive_loop(_runner_args())
    session = calls[-1][2]
    assert session is not None
    assert all(row[2] is session for row in calls)
    assert session.status().lifecycle_generation == 2
    assert session.status().cognitive_cycles == 1
    assert session.status().pending_observation_number == 2


def test_legacy_nca8_open_and_back_stay_lazy(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Merely navigating through the full old NCA8 menu must not construct its session."""
    monkeypatch.chdir(tmp_path)
    calls = _watch_nca8_calls(monkeypatch)
    _input_sequence(monkeypatch, ("1", "1", "4", "", "", "b", "q"))
    cca8_run.interactive_loop(_runner_args())
    assert calls == [(False, None, None)]


@pytest.mark.parametrize("path", (("q",), ("1", "13")))
def test_both_explicit_quit_routes_retain_exit_save(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, path: tuple[str, ...],
) -> None:
    """The added front menu and legacy Quit both reach the original save implementation."""
    monkeypatch.chdir(tmp_path)
    destination = tmp_path / "exit.json"
    calls = _watch_nca8_calls(monkeypatch)
    _input_sequence(monkeypatch, path)
    cca8_run.interactive_loop(_runner_args(save=str(destination)))
    assert destination.is_file()
    assert '"world"' in destination.read_text(encoding="utf-8")
    assert calls == []


def test_shortcut_does_not_change_legacy_objects_or_autosave(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    """Snapshot legacy state after normal boot and compare it after the shortcut completes."""
    monkeypatch.chdir(tmp_path)
    captured: dict[str, Any] = {}
    original_profile = cca8_run.apply_hardwired_profile_phase7
    original_cycle = nca8_menu.run_nca8_experimental_menu_v1

    def capture(ctx: Any, world: Any) -> None:
        original_profile(ctx, world)
        captured["ctx"] = ctx
        captured["world"] = world
        captured["world_before"] = world.to_dict()
        captured["body_before"] = ctx.body_world.to_dict()
        captured["working_before"] = ctx.working_world.to_dict()
        captured["counts_before"] = (ctx.controller_steps, ctx.cog_cycles, ctx.ticks)
        captured["skills_before"] = cca8_controller.skills_to_dict()

    def run(session: Nca8SessionV1 | None, *, run_one_cycle_with_trace: bool = False) -> Nca8SessionV1 | None:
        result = original_cycle(session, run_one_cycle_with_trace=run_one_cycle_with_trace)
        ctx = captured["ctx"]
        assert captured["world"].to_dict() == captured["world_before"]
        assert ctx.body_world.to_dict() == captured["body_before"]
        assert ctx.working_world.to_dict() == captured["working_before"]
        assert (ctx.controller_steps, ctx.cog_cycles, ctx.ticks) == captured["counts_before"]
        assert cca8_controller.skills_to_dict() == captured["skills_before"]
        return result

    monkeypatch.setattr(cca8_run, "apply_hardwired_profile_phase7", capture)
    monkeypatch.setattr(nca8_menu, "run_nca8_experimental_menu_v1", run)
    _input_sequence(monkeypatch, ("2", "", "q"))
    autosave = tmp_path / "legacy-autosave.json"
    cca8_run.interactive_loop(_runner_args(autosave=str(autosave)))
    assert not autosave.exists()


def test_existing_legacy_operation_is_functional_and_returns_to_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str],
) -> None:
    """The actual configuration workbench still toggles legacy state through its existing handler."""
    monkeypatch.chdir(tmp_path)
    original = cca8_run.cca8_session_menu.runtime_configuration_menu_v1
    changes: list[tuple[bool, bool]] = []

    def configure(drives: Any, ctx: Any) -> None:
        before = ctx.mini_snapshot
        original(drives, ctx)
        changes.append((before, ctx.mini_snapshot))

    monkeypatch.setattr(cca8_run.cca8_session_menu, "runtime_configuration_menu_v1", configure)
    prompts = _input_sequence(monkeypatch, ("1", "5", "4", "", "", "13"))
    cca8_run.interactive_loop(_runner_args())
    assert len(changes) == 1 and changes[0][0] is not changes[0][1]
    assert prompts.count(cca8_cli.MAIN_MENU_PROMPT) == 2
    assert capsys.readouterr().out.count("1) Legacy Main Menu") == 1
