# -*- coding: utf-8 -*-
"""Compatibility tests for the extracted CCA8 OpenAI/LLM subsystem."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

# This file intentionally verifies private runner aliases and bridge factories.
# pylint: disable=protected-access

import cca8_openai
import cca8_run


def test_runner_preserves_openai_helper_aliases() -> None:
    """Runner-visible pure helpers should resolve to the extracted module."""
    assert cca8_run._openai_default_model_name is cca8_openai._openai_default_model_name
    assert cca8_run._openai_response_request_options_v1 is cca8_openai._openai_response_request_options_v1
    assert cca8_run._openai_response_text_best_effort is cca8_openai._openai_response_text_best_effort
    assert cca8_run._openai_api_error_detail_v1 is cca8_openai._openai_api_error_detail_v1


def test_openai_module_has_no_runner_import() -> None:
    """The extracted implementation must not create an OpenAI-to-runner cycle."""
    assert "cca8_run" not in cca8_openai.__dict__
    assert cca8_openai.openai_menu_48_interactive.__module__ == "cca8_openai"
    assert cca8_openai.build_cca8_llm_state_summary_v1.__module__ == "cca8_openai"


def test_openai_runtime_resolves_runner_callbacks_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner bridge should capture current helper replacements."""
    def fake_timekeeping(_ctx: Any) -> str:
        return "fake-time"

    def fake_anchor(_world: Any, _name: str = "NOW") -> str:
        return "b-fake"

    def fake_sorted(_world: Any) -> list[str]:
        return ["b-fake"]

    monkeypatch.setattr(cca8_run, "timekeeping_line", fake_timekeeping)
    monkeypatch.setattr(cca8_run, "_anchor_id", fake_anchor)
    monkeypatch.setattr(cca8_run, "_sorted_bids", fake_sorted)

    runtime = cca8_run._openai_runtime_v1()

    assert runtime.timekeeping_line is fake_timekeeping
    assert runtime.anchor_id is fake_anchor
    assert runtime.sorted_bids is fake_sorted


def test_runner_state_summary_wrapper_uses_current_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """State-summary delegation should receive the current runner runtime."""
    captured: dict[str, Any] = {}

    def fake_summary(
        world: Any,
        drives: Any,
        ctx: Any,
        *,
        runtime: cca8_openai.OpenAIRuntime | None = None,
    ) -> dict[str, Any]:
        captured["world"] = world
        captured["drives"] = drives
        captured["ctx"] = ctx
        captured["runtime"] = runtime
        return {"ok": True}

    monkeypatch.setattr(cca8_openai, "build_cca8_llm_state_summary_v1", fake_summary)

    world = object()
    drives = object()
    ctx = object()
    result = cca8_run.build_cca8_llm_state_summary_v1(world, drives, ctx)

    assert result == {"ok": True}
    assert captured["world"] is world
    assert captured["drives"] is drives
    assert captured["ctx"] is ctx
    assert isinstance(captured["runtime"], cca8_openai.OpenAIRuntime)


def test_menu_operations_resolve_runner_entry_points_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """Menu 48 should receive current runner-visible callables."""
    def fake_smoke() -> None:
        return None

    def fake_temperature() -> None:
        return None

    monkeypatch.setattr(cca8_run, "run_openai_smoke_test_interactive", fake_smoke)
    monkeypatch.setattr(cca8_run, "configure_openai_temperature_interactive", fake_temperature)

    menu_operations = cca8_run._openai_menu_operations_v1()
    advanced_operations = cca8_run._openai_advanced_menu_operations_v1()

    assert menu_operations.run_smoke_test is fake_smoke
    assert advanced_operations.configure_temperature is fake_temperature


def test_runner_menu_wrapper_returns_from_extracted_menu(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Blank input should return from extracted Menu 48 through the runner API."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": "")

    cca8_run.openai_menu_48_interactive(object(), object(), SimpleNamespace())

    output = capsys.readouterr().out
    assert "OpenAI / LLM API setup" in output
    assert "Returning to main menu" in output


def test_response_text_fallback_reads_structured_content() -> None:
    """Response extraction should retain the historical structured fallback."""
    part_a = SimpleNamespace(text="CCA8 ")
    part_b = SimpleNamespace(text="ok")
    item = SimpleNamespace(content=[part_a, part_b])
    response = SimpleNamespace(output_text="", output=[item])

    assert cca8_openai._openai_response_text_best_effort(response) == "CCA8 ok"


def test_request_option_parsing_and_adviser_sanitizing(monkeypatch: pytest.MonkeyPatch) -> None:
    """Environment parsing should remain stable after extraction."""
    monkeypatch.setenv("CCA8_OPENAI_TEMPERATURE", "0.25")
    monkeypatch.setenv("CCA8_OPENAI_TOP_P", "0.80")
    monkeypatch.setenv("CCA8_OPENAI_MAX_OUTPUT_TOKENS", "123")
    monkeypatch.setenv("CCA8_OPENAI_REASONING_EFFORT", "low")

    options = cca8_openai._openai_response_request_options_v1()

    assert options == {
        "temperature": 0.25,
        "top_p": 0.8,
        "max_output_tokens": 123,
        "reasoning": {"effort": "low"},
    }
    assert cca8_openai._openai_sanitize_adviser_request_options_v1(options) == {
        "max_output_tokens": 123,
    }
