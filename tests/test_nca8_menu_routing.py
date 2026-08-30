#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Focused routing and terminal-boundary tests for NCA8 Phase 1A."""

from __future__ import annotations

import builtins

import pytest

import cca8_cli
import nca8_menu
from nca8_runtime import NCA8_NO_ACTION, Nca8SessionV1


def test_opening_and_leaving_nca8_menu_does_not_construct_a_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The second brain should remain lazy until a concrete operation needs it."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    result = nca8_menu.run_nca8_experimental_menu_v1(None)

    output = capsys.readouterr().out
    assert result is None
    assert "NCA8 -- NEW ARCHITECTURE-v09.3 EXPERIMENTAL RUNTIME" in output
    assert "not yet a cognitive implementation" in output


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
    assert "[nca8:status] session=not-created" in output


def test_null_smoke_choice_lazily_creates_and_returns_the_isolated_session(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The first executable menu operation should emit an explicit null output."""
    responses = iter(("3", ""))
    monkeypatch.setattr(builtins, "input", lambda _prompt="": next(responses))

    result = nca8_menu.run_nca8_experimental_menu_v1(None)

    output = capsys.readouterr().out
    assert isinstance(result, Nca8SessionV1)
    assert result.status().null_smoke_cycles == 1
    assert f"output={NCA8_NO_ACTION}" in output
    assert "no cognition was simulated" in output


def test_nca8_menu_does_not_consume_the_shared_main_menu_pause(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the established Main Menu should own the common return pause."""
    monkeypatch.setattr(builtins, "input", lambda _prompt="": "")

    def _unexpected_pause() -> bool:
        raise AssertionError("NCA8 submenu must not invoke the Main Menu pause")

    monkeypatch.setattr(cca8_cli, "wait_for_main_menu_continue_v1", _unexpected_pause)

    assert nca8_menu.run_nca8_experimental_menu_v1(None) is None
