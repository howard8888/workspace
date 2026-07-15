# -*- coding: utf-8 -*-
"""Compatibility tests for the Phase-2 CCA8 experiment-runtime extraction."""

# This compatibility test intentionally exercises runner-private aliases and bridge factories.
# pylint: disable=protected-access

from __future__ import annotations

from typing import Any

import pytest

import cca8_experiments
import cca8_run


def test_runner_preserves_phase2_pure_helper_aliases() -> None:
    """Runner-visible pure helpers should resolve directly to the extracted module."""
    assert cca8_run._experiment_summarize_newborn_b2_v1 is cca8_experiments._experiment_summarize_newborn_b2_v1
    assert cca8_run._goat04_context_hint_active_v1 is cca8_experiments._goat04_context_hint_active_v1
    assert cca8_run.render_experiment_episode_summary_lines_v1 is cca8_experiments.render_experiment_episode_summary_lines_v1
    assert cca8_run.experiment_apply_condition_runtime_v1 is cca8_experiments.experiment_apply_condition_runtime_v1


def test_runtime_bridge_resolves_runner_callbacks_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The bridge should capture current runner callables so monkeypatch seams remain useful."""
    def fake_closed_loop(*_args: Any, **_kwargs: Any) -> None:
        return None

    def fake_run_id(_ctx: Any, _cfg: Any = None) -> str:
        return "phase2_runtime_test"

    monkeypatch.setattr(cca8_run, "run_env_closed_loop_steps", fake_closed_loop)
    monkeypatch.setattr(cca8_run, "experiment_make_run_id_v1", fake_run_id)

    runtime = cca8_run._experiment_runtime_v1()

    assert runtime.run_closed_loop is fake_closed_loop
    assert runtime.run_id_factory is fake_run_id


def test_menu_operations_resolve_runner_entry_points_at_call_time(monkeypatch: pytest.MonkeyPatch) -> None:
    """The extracted Menu 49 flow should receive runner-visible compatibility functions."""
    def fake_one_episode(*_args: Any, **_kwargs: Any) -> dict[str, Any]:
        return {"ok": True}

    monkeypatch.setattr(cca8_run, "experiment_run_one_episode_v1", fake_one_episode)

    operations = cca8_run._experiment_menu_operations_v1()

    assert operations.run_one_episode is fake_one_episode


def test_phase2_implementation_lives_outside_runner() -> None:
    """Execution, scoring, repeat analysis, and Menu 49 should now be module-owned."""
    assert cca8_experiments.experiment_make_sandbox_runtime_v1.__module__ == "cca8_experiments"
    assert cca8_experiments.experiment_run_one_episode_v1.__module__ == "cca8_experiments"
    assert cca8_experiments.experiment_run_condition_batch_v1.__module__ == "cca8_experiments"
    assert cca8_experiments.experiments_menu_49_interactive.__module__ == "cca8_experiments"
    assert "cca8_run" not in cca8_experiments.__dict__


def test_runner_menu_wrapper_returns_from_extracted_menu(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    """Entering zero should leave the extracted experiment menu without altering the runner API."""
    monkeypatch.setattr("builtins.input", lambda _prompt="": "0")

    cca8_run.experiments_menu_49_interactive(cca8_run.Ctx())

    assert "Experiments / Benchmarks" in capsys.readouterr().out
