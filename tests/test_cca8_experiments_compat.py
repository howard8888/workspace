# -*- coding: utf-8 -*-
"""Compatibility tests for the extracted CCA8 experiment infrastructure."""

from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

import cca8_experiments
import cca8_run


def test_runner_preserves_experiment_types_and_pure_helpers() -> None:
    """Runner-level compatibility names should resolve to the extracted module."""
    assert cca8_run.ExperimentConditionDef is cca8_experiments.ExperimentConditionDef
    assert cca8_run.ExperimentBenchmarkDef is cca8_experiments.ExperimentBenchmarkDef
    assert cca8_run.experiment_normalize_protocol_v1 is cca8_experiments.experiment_normalize_protocol_v1
    assert cca8_run.apply_newborn_experiment_stress_v1 is cca8_experiments.apply_newborn_experiment_stress_v1


def test_experiment_module_does_not_import_runner() -> None:
    """The extracted module must stay independent of the large interactive runner."""
    assert "cca8_run" not in cca8_experiments.__dict__


def test_runner_prepare_logging_uses_visible_run_id_hook(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Runner monkeypatches should still control prepared experiment filenames."""
    monkeypatch.setattr(cca8_run, "experiment_make_run_id_v1", lambda _ctx, _cfg=None: "compat_run_001")

    ctx = cca8_run.Ctx()
    ctx.experiment_cfg.output_dir = str(tmp_path)

    info = cca8_run.experiment_prepare_logging_v1(ctx)

    assert info["run_id"] == "compat_run_001"
    assert info["cycle_json_path"] == str(tmp_path / "compat_run_001__cycle.jsonl")
    assert info["episode_json_path"] == str(tmp_path / "compat_run_001__episode.jsonl")


def test_runner_cycle_builder_uses_visible_body_zone_hook(monkeypatch: pytest.MonkeyPatch) -> None:
    """The runner wrapper should preserve its historical BodyMap monkeypatch seam."""
    monkeypatch.setattr(cca8_run, "body_space_zone", lambda _ctx: "compat-zone")

    record = cca8_run.experiment_build_cycle_record_stub_v1(cca8_run.Ctx())

    assert record["zone"] == "compat-zone"


def test_direct_module_protocol_helpers_remain_json_safe() -> None:
    """Direct users of cca8_experiments should receive the same normalized contract."""
    raw = cca8_run.ExperimentProtocolConfig(
        condition_ids=["b", "A", "bad", "b"],
        seed_list=[11, 11, 23],
        obs_mask_prob=2.0,
        run_label=" phase / one ",
    )

    normalized = cca8_experiments.experiment_normalize_protocol_v1(raw)
    paths: dict[str, Any] = cca8_experiments.experiment_jsonl_paths_v1(
        cca8_run.Ctx(experiment_cfg=normalized),
        run_id="direct_run_001",
    )

    assert normalized.condition_ids == ["B", "A"]
    assert normalized.seed_list == [11, 23]
    assert normalized.obs_mask_prob == 1.0
    assert normalized.run_label == "phase_one"
    assert paths["cycle_json_path"].endswith("direct_run_001__cycle.jsonl")
