# -*- coding: utf-8 -*-
"""
Focused tests for experiment_prepare_logging_v1(...).

These tests cover the logging/output seam added for the long-horizon
experiment harness. They intentionally avoid running any experiment
episodes; they only verify protocol normalization, output-path prep,
and cycle-JSON arming behavior.
"""

from __future__ import annotations

import os

import cca8_run


def test_experiment_prepare_logging_v1_arms_paths_and_summary(tmp_path, monkeypatch) -> None:
    """Prepare logging, normalize config, and expose stable output paths on ctx.

    Coverage goals for this focused test:
      - ctx.experiment_cfg is normalized in-place
      - cycle JSON logging is armed when enabled
      - ctx.cycle_json_path is set from the prepared run id
      - ctx.experiment_last_summary contains run_id and episode_json_path
      - output directory is created, but JSONL files are not written yet
      - reset_buffers=True clears the in-memory cycle ring buffer
    """
    monkeypatch.setattr(
        cca8_run,
        "experiment_make_run_id_v1",
        lambda ctx, cfg=None: "exp_run_001",
    )

    out_dir = tmp_path / "experiment output"

    ctx = cca8_run.Ctx()
    ctx.cycle_json_records = [{"old": True}]
    ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="newborn_long_horizon",
        condition_ids=["a", "E", "a", "bogus"],
        seed_list=[101, "101", 202, "bad"],
        episodes_per_seed=2,
        max_cycles=25,
        obs_mask_prob=0.2,
        llm_model="  gpt-test-mini  ",
        run_label=" paper run / AE ",
        output_dir=str(out_dir),
        jsonl_write_cycle_records=True,
        jsonl_write_episode_records=True,
    )

    info = cca8_run.experiment_prepare_logging_v1(ctx, reset_buffers=True)

    expected_output_dir = os.path.normpath(str(out_dir))
    expected_cycle_path = os.path.join(expected_output_dir, "exp_run_001__cycle.jsonl")
    expected_episode_path = os.path.join(expected_output_dir, "exp_run_001__episode.jsonl")

    assert info["ok"] is True
    assert info["schema"] == "experiment_logging_prep_v1"
    assert info["run_id"] == "exp_run_001"
    assert info["output_dir"] == expected_output_dir
    assert info["cycle_json_path"] == expected_cycle_path
    assert info["episode_json_path"] == expected_episode_path

    assert ctx.experiment_cfg.benchmark_id == "newborn_long_horizon"
    assert ctx.experiment_cfg.condition_ids == ["A", "E"]
    assert ctx.experiment_cfg.seed_list == [101, 202]
    assert ctx.experiment_cfg.episodes_per_seed == 2
    assert ctx.experiment_cfg.max_cycles == 25
    assert ctx.experiment_cfg.obs_mask_prob == 0.2
    assert ctx.experiment_cfg.llm_model == "gpt-test-mini"
    assert ctx.experiment_cfg.run_label == "paper_run_AE"
    assert ctx.experiment_cfg.output_dir == expected_output_dir

    assert ctx.cycle_json_enabled is True
    assert ctx.cycle_json_path == expected_cycle_path
    assert ctx.cycle_json_records == []

    assert ctx.experiment_last_summary["ok"] is True
    assert ctx.experiment_last_summary["run_id"] == "exp_run_001"
    assert ctx.experiment_last_summary["benchmark_id"] == "newborn_long_horizon"
    assert ctx.experiment_last_summary["condition_ids"] == ["A", "E"]
    assert ctx.experiment_last_summary["seed_list"] == [101, 202]
    assert ctx.experiment_last_summary["episodes_per_seed"] == 2
    assert ctx.experiment_last_summary["max_cycles"] == 25
    assert ctx.experiment_last_summary["obs_mask_prob"] == 0.2
    assert ctx.experiment_last_summary["run_label"] == "paper_run_AE"
    assert ctx.experiment_last_summary["output_dir"] == expected_output_dir
    assert ctx.experiment_last_summary["cycle_json_enabled"] is True
    assert ctx.experiment_last_summary["cycle_json_path"] == expected_cycle_path
    assert ctx.experiment_last_summary["episode_json_enabled"] is True
    assert ctx.experiment_last_summary["episode_json_path"] == expected_episode_path

    assert os.path.isdir(expected_output_dir)
    assert not os.path.exists(expected_cycle_path)
    assert not os.path.exists(expected_episode_path)