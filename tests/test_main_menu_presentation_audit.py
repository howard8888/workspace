#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused presentation checks for the incremental Main Menu audit."""

import os

import cca8_cli
import cca8_run


def test_menu_selection_banner_preserves_displayed_number() -> None:
    """Long menu responses should have an easy-to-find displayed-number marker."""
    assert cca8_cli.menu_selection_banner("1") == (
        f"{cca8_cli.MENU_RESPONSE_DIVIDER}\n"
        "MENU SELECTION #1\n"
    )


def test_main_menu_item_one_uses_interim_key_concepts_title() -> None:
    """Menu 1 should advertise its temporary high-level purpose during the NavMap migration."""
    assert "1) Brief Overview of Key Concepts [understanding, tagging]" in cca8_cli.MAIN_MENU_PROMPT


def test_readme_compendium_path_tracks_runner_location() -> None:
    """Menu 2 should find README.md beside the runner, independent of the process working directory."""
    expected = os.path.join(os.path.dirname(os.path.abspath(cca8_run.__file__)), "README.md")

    assert cca8_run._readme_compendium_path_v1() == expected  # pylint: disable=protected-access
