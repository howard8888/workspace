# -*- coding: utf-8 -*-
"""Tests for the extracted CCA8 terminal presentation and menu routing."""

from __future__ import annotations

from typing import Any

import pytest

import cca8_cli
import cca8_run


def test_runner_preserves_cli_compatibility_names() -> None:
    """Legacy runner-level CLI names should still resolve after extraction."""
    assert cca8_run.print_ascii_logo is cca8_cli.print_ascii_logo
    assert cca8_run.ASCII_LOGOS is cca8_cli.ASCII_LOGOS
    assert cca8_run.TECH_MANUAL == cca8_cli.TECH_MANUAL


def test_runner_header_wrapper_supplies_runner_owned_values(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner wrapper should delegate with its version and visible logo callback."""
    captured: dict[str, Any] = {}

    def fake_header(*args: Any, **kwargs: Any) -> None:
        captured["args"] = args
        captured["kwargs"] = kwargs

    monkeypatch.setattr(cca8_cli, "print_header", fake_header)

    cca8_run.print_header("HAL TEST", "BODY TEST")

    assert captured["args"] == ("HAL TEST", "BODY TEST")
    assert captured["kwargs"]["runner_version"] == cca8_run.__version__
    assert captured["kwargs"]["technical_manual"] == cca8_cli.TECH_MANUAL
    assert captured["kwargs"]["logo_printer"] is cca8_run.print_ascii_logo


def test_exact_alias_and_unique_prefix_routing() -> None:
    """Exact aliases and unique prefixes should preserve the current displayed routes."""
    assert cca8_cli.route_menu_alias(" watch ") == ("1", [])
    assert cca8_cli.route_menu_alias("VER") == ("1", ["verbose"])
    assert cca8_cli.route_menu_alias(" snapshot ") == ("2", [])
    assert cca8_cli.route_menu_alias("SNAP") == ("2", ["snapshot"])
    assert cca8_cli.route_menu_alias("understanding") == ("3", [])
    assert cca8_cli.route_menu_alias("overview") == ("3", [])
    assert cca8_cli.route_menu_alias("timekeeping") == ("2", [])
    assert cca8_cli.route_menu_alias("robotg") == ("9", ["robotgoat"])
    assert cca8_cli.route_menu_alias("memory") == ("6", [])
    assert cca8_cli.route_menu_alias("developer") == ("12", [])


def test_ambiguous_and_too_short_aliases_are_not_routed() -> None:
    """Ambiguous prefixes should provide candidates; short prefixes should not route."""
    routed, matches = cca8_cli.route_menu_alias("eng")

    assert routed is None
    assert len(matches) > 1
    assert "engram" in matches
    assert "engrams" in matches
    assert cca8_cli.route_menu_alias("sn") == (None, [])


def test_menu_number_compatibility_preserves_handler_keys() -> None:
    """Canonical numbers should route to workbenches; hidden 14-51 routes should remain stable."""
    expected_top_level = {
        "1": "watch",
        "2": "scope",
        "3": "architecture",
        "4": "manual",
        "5": "config",
        "6": "memory",
        "7": "graph-menu",
        "8": "experiments-menu",
        "9": "rcos",
        "10": "llm",
        "11": "session",
        "12": "developer",
        "13": "quit",
    }
    for displayed, handler in expected_top_level.items():
        assert cca8_cli.route_menu_number(displayed) == handler

    assert cca8_cli.route_menu_number("14") == "6"
    assert cca8_cli.route_menu_number("31") == "9"
    assert cca8_cli.route_menu_number("51") == "51"
    assert cca8_cli.route_menu_number("S") == "s"
    assert cca8_cli.route_menu_number("999") == "999"


def test_main_menu_contains_thirteen_stable_intent_oriented_entries() -> None:
    """The visible Main Menu should contain only the stable 1-13 front-page choices."""
    expected_entries = (
        "1) Watch Cognition Run",
        "2) Cognitive Storage Oscilloscope / System Inspector",
        "3) Architecture, Documentation & Tutorial",
        "4) Manual Inputs & One-Step Controls",
        "5) Runtime / Episode Configuration",
        "6) Memory Operations: WorkingMap, Columns & Engrams",
        "7) WorldGraph Editing & Planning",
        "8) Experiments & Benchmarks",
        "9) RCOS / Robotics",
        "10) LLM / External Model Integration",
        "11) Session Save / Load / Reset",
        "12) Validation & Developer Utilities",
        "13) Quit",
    )
    for expected in expected_entries:
        assert expected in cca8_cli.MAIN_MENU_PROMPT

    for hidden_entry in (
        "14) Resolve engrams",
        "35) Run 1 Cognitive Cycle",
        "49) Experiments / Benchmarks",
        "50) SimRobotGoat RCOS sandbox",
        "51) Autonomous newborn survival demo",
        "SCROLL UP TO SEE ALL OF THE MENU CHOICES",
    ):
        assert hidden_entry not in cca8_cli.MAIN_MENU_PROMPT

    assert "Historical direct choices 14-51 remain accepted" not in cca8_cli.MAIN_MENU_PROMPT

    expected_spacing = (
        "commands.\n\n    RUN / UNDERSTAND",
        "[architecture]\n\n    OPERATE / CONFIGURE",
        "[config]\n\n    MEMORY / PLANNING",
        "[graph]\n\n    RESEARCH / INTEGRATION",
        "[llm]\n\n    SESSION / DEVELOPMENT",
        "13) Quit [quit]\n\n    New users: 1 -> 2 -> 3",
    )
    for expected in expected_spacing:
        assert expected in cca8_cli.MAIN_MENU_PROMPT

    rendered_menu = cca8_cli.MAIN_MENU_HEADER + cca8_cli.MAIN_MENU_PROMPT
    lines = rendered_menu.splitlines()
    assert len(lines) <= 30
    assert max(len(line) for line in lines) <= 80


def test_header_renderer_uses_current_environment(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The extracted header should render deterministically from supplied process state."""
    logo_calls: list[dict[str, Any]] = []

    def fake_logo(**kwargs: Any) -> None:
        logo_calls.append(dict(kwargs))

    monkeypatch.setattr(cca8_cli.os.path, "abspath", lambda _path: "entry:test")
    monkeypatch.setattr(cca8_cli.sys, "platform", "test-platform")

    cca8_cli.print_header(
        "HAL TEST",
        "BODY TEST",
        runner_version="9.9.9",
        technical_manual="manual:test",
        logo_printer=fake_logo,
    )

    output = capsys.readouterr().out
    assert "cca8_run.py v9.9.9" in output
    assert "entry:test" in output
    assert "OS: test-platform" in output
    assert "HAL TEST" in output
    assert "BODY TEST" in output
    assert "manual:test" in output
    assert logo_calls == [{"style": "goat", "color": True}]


def test_logo_off_environment_suppresses_output(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """CCA8_LOGO=off should continue to suppress the startup logo."""
    monkeypatch.setenv("CCA8_LOGO", "off")

    cca8_cli.print_ascii_logo()

    assert capsys.readouterr().out == ""


def test_read_menu_input_v1_strips_text_and_preserves_blank(monkeypatch: pytest.MonkeyPatch) -> None:
    """The shared CLI input boundary should normalize text without inventing cancel semantics."""
    responses = iter(("  12  ", ""))
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(responses))

    assert cca8_cli.read_menu_input_v1() == "12"
    assert cca8_cli.read_menu_input_v1() == ""


def test_read_menu_input_v1_returns_none_on_terminal_interrupt(monkeypatch: pytest.MonkeyPatch) -> None:
    """EOF/keyboard interruption should terminate a submenu cleanly rather than propagate."""

    def interrupt(_prompt: str = "") -> str:
        raise KeyboardInterrupt

    monkeypatch.setattr("builtins.input", interrupt)

    assert cca8_cli.read_menu_input_v1() is None


def test_wait_for_main_menu_continue_v1_uses_one_standard_prompt(monkeypatch: pytest.MonkeyPatch) -> None:
    """Main-menu continuation should use the shared safe-input boundary exactly once."""
    prompts: list[str] = []

    def fake_input(prompt: str = "") -> str:
        prompts.append(prompt)
        return ""

    monkeypatch.setattr("builtins.input", fake_input)

    assert cca8_cli.wait_for_main_menu_continue_v1() is True
    assert prompts == ["Please press ENTER to continue..."]


def test_wait_for_main_menu_continue_v1_reports_interruption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Terminal interruption should tell the runner not to redraw the Main Menu."""
    def interrupted_input(_prompt: str = "") -> str:
        raise EOFError

    monkeypatch.setattr("builtins.input", interrupted_input)

    assert cca8_cli.wait_for_main_menu_continue_v1() is False
