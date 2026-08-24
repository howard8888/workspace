#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused routing tests for the stable 13-choice CCA8 Main Menu."""

from __future__ import annotations

import builtins
from typing import Any

import pytest

import cca8_main_menu
import cca8_session_menu
from cca8_context import Ctx
from cca8_controller import Drives


@pytest.mark.parametrize(
    ("pick", "expected"),
    (("1", "12"), ("2", "14"), ("3", "18"), ("4", "11"), ("", None)),
)
def test_manual_controls_submenu_reuses_existing_handlers(
    monkeypatch: pytest.MonkeyPatch,
    pick: str,
    expected: str | None,
) -> None:
    """Manual controls should be a routing shell over established runner handlers."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pick)

    assert cca8_main_menu.manual_controls_menu_v1() == expected


@pytest.mark.parametrize(
    ("pick", "expected"),
    (("1", "24"), ("2", "44"), ("3", "47"), ("4", "31"), ("5", "30"), ("6", "clear-working-map")),
)
def test_memory_operations_submenu_separates_mutating_actions(
    monkeypatch: pytest.MonkeyPatch,
    pick: str,
    expected: str,
) -> None:
    """Memory mutation should remain separate from Main Menu #2 read-only inspection."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pick)

    assert cca8_main_menu.memory_operations_menu_v1() == expected


@pytest.mark.parametrize(
    ("pick", "expected"),
    (("1", "3"), ("2", "4"), ("3", "15"), ("4", "5"), ("5", "25")),
)
def test_worldgraph_workbench_reuses_editing_and_planning_handlers(
    monkeypatch: pytest.MonkeyPatch,
    pick: str,
    expected: str,
) -> None:
    """WorldGraph editing/planning should remain single-source in the runner."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": pick)

    assert cca8_main_menu.worldgraph_workbench_menu_v1() == expected


def test_experiments_submenu_includes_protocol_and_goat04(monkeypatch: pytest.MonkeyPatch) -> None:
    """The experiment workbench should include the contextual map-switch configuration."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "2")

    assert cca8_main_menu.experiments_menu_v1() == "42"


def test_session_submenu_status_is_read_only_then_can_route_save(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Session status should remain in the submenu without duplicating save logic."""
    responses = iter(("4", "1"))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = cca8_main_menu.session_management_menu_v1(
        loaded_path="loaded.json",
        autosave_path="autosave.json",
        exit_save_path="exit.json",
    )

    output = capsys.readouterr().out
    assert "loaded.json" in output
    assert "autosave.json" in output
    assert "exit.json" in output
    assert result == "s"


def test_clear_working_map_requires_exact_confirmation(monkeypatch: pytest.MonkeyPatch) -> None:
    """The mutating clear operation should require an explicit uppercase token."""
    calls: list[Any] = []
    ctx = object()
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "CLEAR")

    cleared = cca8_main_menu.clear_working_map_interactive_v1(
        ctx,
        reset_working_map=lambda value: calls.append(value),
    )

    assert cleared is True
    assert calls == [ctx]


def test_new_observation_mask_menu_keeps_verbose_on_blank(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main Menu #5 should not alter verbose masking merely because Enter was pressed."""
    responses = iter(("", "", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    ctx = Ctx()
    ctx.obs_mask_verbose = True

    cca8_session_menu.configure_observation_masking_v1(ctx)

    assert ctx.obs_mask_verbose is True


def test_runtime_configuration_menu_exposes_independent_settings(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Main Menu #5 should let the user change one settings family at a time."""
    responses = iter(("4", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))
    drives = Drives()
    ctx = Ctx()
    original = ctx.mini_snapshot

    cca8_session_menu.runtime_configuration_menu_v1(drives, ctx)

    assert ctx.mini_snapshot is (not original)


def test_top_level_router_passes_through_hidden_historical_handler() -> None:
    """Non-semantic hidden compatibility handlers should pass through unchanged."""
    runtime = cca8_main_menu.MainMenuRuntimeV1(
        watch_menu=lambda: None,
        scope_menu=lambda: None,
        architecture_menu=lambda: None,
        versions_text=lambda: "versions",
    )

    result = cca8_main_menu.resolve_top_level_choice_v1(
        "44",
        runtime=runtime,
        loaded_path=None,
        autosave_path=None,
        exit_save_path=None,
    )

    assert result == "44"
