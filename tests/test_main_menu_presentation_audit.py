#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused presentation checks for the reorganized CCA8 Main Menu."""

from __future__ import annotations

import builtins
import os

import pytest

import cca8_cli
import cca8_run


def test_menu_selection_banner_preserves_displayed_number() -> None:
    """Long menu responses should have an easy-to-find displayed-number marker."""
    assert cca8_cli.menu_selection_banner("1") == (
        f"{cca8_cli.MENU_RESPONSE_DIVIDER}\n"
        "MENU SELECTION #1\n"
    )


def test_main_menu_has_thirteen_clear_top_level_choices() -> None:
    """The visible front page should be compact, stable, and intent-oriented."""
    prompt = cca8_cli.MAIN_MENU_PROMPT

    for heading in ("RUN / UNDERSTAND", "OPERATE / CONFIGURE", "MEMORY / PLANNING", "RESEARCH / INTEGRATION"):
        assert prompt.count(heading) == 1

    for number in range(1, 14):
        assert f"{number})" in prompt

    assert "1) Watch Cognition Run" in prompt
    assert "2) Cognitive Storage Oscilloscope / System Inspector" in prompt
    assert "3) Architecture, Documentation & Tutorial" in prompt
    assert "13) Quit" in prompt
    assert "49) Experiments / Benchmarks" not in prompt
    assert "50) SimRobotGoat RCOS sandbox" not in prompt
    assert "51) Autonomous newborn survival demo" not in prompt
    assert "SCROLL UP TO SEE ALL" not in prompt


@pytest.mark.parametrize(
    ("pick", "expected_handler"),
    (("1", "35"), ("2", "37"), ("3", "51"), ("4", "nca8-runtime"), ("", None)),
)
def test_watch_cognition_submenu_routes_to_existing_cycle_handlers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pick: str,
    expected_handler: str | None,
) -> None:
    """Main Menu #1 should preserve legacy handlers and expose the explicit NCA8 route."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pick)

    result = cca8_run._watch_cognition_menu_v1()  # pylint: disable=protected-access

    output = capsys.readouterr().out
    assert "Selection: Watch Cognition Run" in output
    assert "one cognitive cycle slowly" in output
    assert "several cognitive cycles" in output
    assert "complete autonomous newborn survival episode" in output
    assert "new Architecture experimental runtime" in output
    assert "NCA8 Phase 1D / Gate A" in output
    assert result == expected_handler


def test_architecture_submenu_displays_current_map_first_overview(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Main Menu #3 option 1 should display the current architecture overview."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "1")
    monkeypatch.setattr(
        cca8_run,
        "print_architecture_overview_v1",
        lambda _policy_rt: print("ARCHITECTURE_OVERVIEW_SENTINEL"),
    )

    cca8_run._architecture_explanation_menu_v1(object())  # pylint: disable=protected-access

    output = capsys.readouterr().out
    assert "Architecture explanation options:" in output
    assert "Concise map-first architecture overview" in output
    assert "Selection: Explanation of the Architecture" in output
    assert "ARCHITECTURE_OVERVIEW_SENTINEL" in output


def test_readme_compendium_path_tracks_runner_location() -> None:
    """Main Menu #3 should find README.md beside the runner, independent of the process working directory."""
    expected = os.path.join(os.path.dirname(os.path.abspath(cca8_run.__file__)), "README.md")

    assert cca8_run._readme_compendium_path_v1() == expected  # pylint: disable=protected-access


def test_scope_submenu_owns_explicit_timekeeping_inspection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Main Menu #2 should expose timekeeping through its current-state panel."""
    responses = iter(("2", "6", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        cca8_run.cca8_cognitive_scope,
        "cognitive_scope_trace_summary_v1",
        lambda _ctx: {"retained_count": 0, "capacity": 128, "total_capture_count": 0},
    )
    monkeypatch.setattr(
        cca8_run,
        "_show_timekeeping_status_v1",
        lambda _env, _ctx: print("TIMEKEEPING_INSPECTOR_SENTINEL"),
    )

    result = cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "Current Cognition & Control State" in output
    assert "Explicit timekeeping / ordering" in output
    assert "TIMEKEEPING_INSPECTOR_SENTINEL" in output
    assert "Sandbox Signal Injection" in output
    assert result is None


def test_scope_submenu_routes_dp01_sandbox_injection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Main Menu #2 category 5 should invoke the bounded sandbox controller."""
    responses = iter(("5", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        cca8_run.cca8_cognitive_scope,
        "cognitive_scope_trace_summary_v1",
        lambda _ctx: {"retained_count": 0, "capacity": 128, "total_capture_count": 0},
    )
    monkeypatch.setattr(
        cca8_run,
        "_cognitive_scope_injection_flow_v1",
        lambda _ctx: print("DP01_INJECTION_SENTINEL"),
    )

    result = cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "Sandbox Signal Injection" in output
    assert "DP01_INJECTION_SENTINEL" in output
    assert result is None


def test_scope_submenu_preserves_runner_legacy_snapshot_seam(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The visualization panel should still resolve the runner-visible snapshot helper."""
    responses = iter(("4", "1", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        cca8_run.cca8_cognitive_scope,
        "cognitive_scope_trace_summary_v1",
        lambda _ctx: {"retained_count": 0, "capacity": 128, "total_capture_count": 0},
    )
    monkeypatch.setattr(
        cca8_run,
        "snapshot_text",
        lambda _world, **_kwargs: "LEGACY_SNAPSHOT_SENTINEL",
    )

    result = cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "Visualizations & Diagnostic Exports" in output
    assert "LEGACY DETAILED SNAPSHOT" in output
    assert "LEGACY_SNAPSHOT_SENTINEL" in output
    assert result is None


def test_scope_submenu_returns_existing_read_only_handler(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A legacy read-only view should return its established handler rather than duplicate code."""
    responses = iter(("2", "2"))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    monkeypatch.setattr(
        cca8_run.cca8_cognitive_scope,
        "cognitive_scope_trace_summary_v1",
        lambda _ctx: {"retained_count": 0, "capacity": 128, "total_capture_count": 0},
    )

    result = cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    assert result == "38"
