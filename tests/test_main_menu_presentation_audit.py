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


def test_main_menu_has_three_clear_top_level_orientation_choices() -> None:
    """Watching, inspecting, and explaining should be the first three menu choices."""
    prompt = cca8_cli.MAIN_MENU_PROMPT

    assert prompt.count("# Quick Start / Overview") == 1
    assert "1) Watch Cognition Run" in prompt
    assert "2) Cognitive Storage Oscilloscope / System Inspector" in prompt
    assert "3) Explanation of the Architecture" in prompt
    assert "4) World stats" not in prompt
    assert "5) Recent bindings" not in prompt
    assert "6) Drives & drive tags" not in prompt
    assert "7) Skill ledger" not in prompt
    assert "8) Timekeeping status" not in prompt
    assert "35) Run 1 Cognitive Cycle" not in prompt
    assert "37) Run n Cognitive Cycles" not in prompt


@pytest.mark.parametrize(
    ("pick", "expected_handler"),
    (("1", "35"), ("2", "37"), ("", None)),
)
def test_watch_cognition_submenu_routes_to_existing_cycle_handlers(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
    pick: str,
    expected_handler: str | None,
) -> None:
    """Main Menu #1 should reuse, rather than duplicate, the established cycle handlers."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pick)

    result = cca8_run._watch_cognition_menu_v1()  # pylint: disable=protected-access

    output = capsys.readouterr().out
    assert "Selection: Watch Cognition Run" in output
    assert "one cognitive cycle slowly" in output
    assert "several cognitive cycles" in output
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
    """Main Menu #2 should expose the full time-domain panel rather than a separate visible top-level item."""
    responses = iter(("9", ""))
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

    cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "Explicit timekeeping / ordering" in output
    assert "TIMEKEEPING_INSPECTOR_SENTINEL" in output
    assert "13) Inject one preset synthetic EnvObservation at DP01" in output
    assert "14) Clear retained oscilloscope snapshots" in output


def test_scope_submenu_routes_dp01_sandbox_injection(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Main Menu #2 option 13 should invoke the bounded sandbox controller."""
    responses = iter(("13", ""))
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

    cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "SANDBOX SIGNAL INJECTION" in output
    assert "DP01_INJECTION_SENTINEL" in output
    assert "14) Clear retained oscilloscope snapshots" in output


def test_scope_submenu_preserves_runner_legacy_snapshot_seam(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Menu #2 option 11 should still resolve the runner-visible snapshot helper."""
    responses = iter(("11", ""))
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

    cca8_run._cognitive_scope_menu_v1(  # pylint: disable=protected-access
        object(),
        object(),
        object(),
        cca8_run.Ctx(),
        object(),
    )

    output = capsys.readouterr().out
    assert "LEGACY DETAILED SNAPSHOT" in output
    assert "LEGACY_SNAPSHOT_SENTINEL" in output
