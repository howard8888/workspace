#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused presentation checks for the incremental Main Menu audit."""

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


def test_main_menu_uses_one_quick_start_overview_section() -> None:
    """The former tutorial and overview groups should occupy one compact section."""
    assert "# Quick Start & Tutorial" not in cca8_cli.MAIN_MENU_PROMPT
    assert cca8_cli.MAIN_MENU_PROMPT.count("# Quick Start / Overview") == 1
    assert "1) Brief Overview of Key Concepts" not in cca8_cli.MAIN_MENU_PROMPT
    assert "2) Help: Docs / Brief Overview / Tutorial" in cca8_cli.MAIN_MENU_PROMPT


def test_help_submenu_contains_former_brief_overview(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Help option 2 should render the overview removed from the top-level menu."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "2")
    monkeypatch.setattr(
        cca8_run,
        "print_tagging_and_policies_help",
        lambda _policy_rt: print("BRIEF_OVERVIEW_SENTINEL"),
    )

    cca8_run._help_menu_v1(object())  # pylint: disable=protected-access

    output = capsys.readouterr().out
    assert "Help options:" in output
    assert "2) Brief Overview of Key Concepts" in output
    assert "Selection: Brief Overview of Key Concepts" in output
    assert "BRIEF_OVERVIEW_SENTINEL" in output


def test_readme_compendium_path_tracks_runner_location() -> None:
    """Menu 2 should find README.md beside the runner, independent of the process working directory."""
    expected = os.path.join(os.path.dirname(os.path.abspath(cca8_run.__file__)), "README.md")

    assert cca8_run._readme_compendium_path_v1() == expected  # pylint: disable=protected-access
