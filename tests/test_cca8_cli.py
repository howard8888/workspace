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
    """Exact aliases and unique prefixes should preserve the historical routes."""
    assert cca8_cli.route_menu_alias(" snapshot ") == ("3", [])
    assert cca8_cli.route_menu_alias("SNAP") == ("3", ["snapshot"])
    assert cca8_cli.route_menu_alias("robotg") == ("50", ["robotgoat"])


def test_ambiguous_and_too_short_aliases_are_not_routed() -> None:
    """Ambiguous prefixes should provide candidates; short prefixes should not route."""
    routed, matches = cca8_cli.route_menu_alias("eng")

    assert routed is None
    assert len(matches) > 1
    assert "engram" in matches
    assert "engrams" in matches
    assert cca8_cli.route_menu_alias("sn") == (None, [])


def test_menu_number_compatibility_preserves_handler_keys() -> None:
    """Displayed numbers should still resolve to the existing runner handler keys."""
    assert cca8_cli.route_menu_number(" 3 ") == "17"
    assert cca8_cli.route_menu_number("31") == "9"
    assert cca8_cli.route_menu_number("51") == "51"
    assert cca8_cli.route_menu_number("S") == "s"
    assert cca8_cli.route_menu_number("999") == "999"


def test_main_menu_contains_current_high_value_entries() -> None:
    """The extracted menu should retain the current cognitive-cycle and experiment entries."""
    for expected in (
        "35) Run 1 Cognitive Cycle",
        "37) Run n Cognitive Cycles",
        "49) Experiments / Benchmarks",
        "50) SimRobotGoat RCOS sandbox",
        "51) Autonomous newborn survival demo",
    ):
        assert expected in cca8_cli.MAIN_MENU_PROMPT


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
