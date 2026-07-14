# -*- coding: utf-8 -*-
"""Compatibility tests for the extracted CCA8 preflight subsystem."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any, Callable

import pytest

# pylint: disable=protected-access

import cca8_preflight
import cca8_run


def test_runner_full_preflight_delegates_with_explicit_runtime(monkeypatch: pytest.MonkeyPatch) -> None:
    """The legacy runner entry point should delegate with the complete runtime bridge."""
    captured: dict[str, Any] = {}

    def fake_run(args: Any, runtime: cca8_preflight.PreflightRuntime) -> int:
        captured["args"] = args
        captured["runtime"] = runtime
        return 17

    monkeypatch.setattr(cca8_preflight, "run_preflight_full", fake_run)

    args = SimpleNamespace(hal=False, body="")
    result = cca8_run.run_preflight_full(args)

    assert result == 17
    assert captured["args"] is args

    runtime = captured["runtime"]
    assert isinstance(runtime, cca8_preflight.PreflightRuntime)
    assert runtime.anchor_id is cca8_run._anchor_id
    assert runtime.init_body_world is cca8_run.init_body_world
    assert runtime.print_ascii_logo is cca8_run.print_ascii_logo
    assert runtime.llm_operational_check is cca8_run.run_llm_operational_preflight_check


def test_runner_lite_preflight_delegates(monkeypatch: pytest.MonkeyPatch) -> None:
    """The startup compatibility entry point should delegate to the new module."""
    calls: list[str] = []

    def fake_lite() -> None:
        calls.append("called")

    monkeypatch.setattr(cca8_preflight, "run_preflight_lite_maybe", fake_lite)

    cca8_run.run_preflight_lite_maybe()

    assert calls == ["called"]


def test_runner_llm_preflight_wrapper_passes_runner_helpers(monkeypatch: pytest.MonkeyPatch) -> None:
    """Runner-level OpenAI helper replacement should remain available after extraction."""
    captured: dict[str, Any] = {}

    monkeypatch.setattr(cca8_run, "_openai_default_model_name", lambda: "model-from-runner")
    monkeypatch.setattr(cca8_run, "_openai_response_request_options_v1", lambda: {"temperature": 0.0})
    monkeypatch.setattr(cca8_run, "_openai_response_text_best_effort", lambda _response: "text-from-runner")

    def fake_llm_check(
        timeout_seconds: float,
        *,
        default_model_name: Callable[[], str],
        response_request_options: Callable[[], dict[str, Any]],
        response_text: Callable[[Any], str],
    ) -> dict[str, Any]:
        captured["timeout"] = timeout_seconds
        captured["model"] = default_model_name()
        captured["options"] = response_request_options()
        captured["text"] = response_text(object())
        return {"status": "pass"}

    monkeypatch.setattr(cca8_preflight, "run_llm_operational_preflight_check", fake_llm_check)

    result = cca8_run.run_llm_operational_preflight_check(timeout_seconds=0.25)

    assert result == {"status": "pass"}
    assert captured == {
        "timeout": 0.25,
        "model": "model-from-runner",
        "options": {"temperature": 0.0},
        "text": "text-from-runner",
    }
