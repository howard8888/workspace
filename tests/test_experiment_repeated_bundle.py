# -*- coding: utf-8 -*-
"""
Focused pytest for repeated experiment bundle writing.

This test exercises the paper-facing archival helper that writes:
- episode_rows JSONL
- repeat_rows JSONL
- stats JSON

I intentionally use a very small fake repeated_result payload so the test stays
fast, deterministic, and independent of the full experiment runner.
"""

from __future__ import annotations

import json
from pathlib import Path

from cca8_run import (
    Ctx,
    ExperimentProtocolConfig,
    _experiment_write_repeated_result_bundle_v1,
)


def test_experiment_write_repeated_result_bundle_creates_files_and_stats(tmp_path: Path) -> None:
    """
    The repeated bundle helper should materialize the three archival files and the
    stats JSON should explicitly contain repeat_metric_rows.

    This is the key provenance contract for paper-facing experiment statistics.
    """
    ctx = Ctx()
    ctx.experiment_cfg = ExperimentProtocolConfig(
        benchmark_id="newborn_long_horizon",
        obs_mask_prob=0.70,
        output_dir=str(tmp_path),
        run_label="pytest_bundle",
    )

    repeated_result = {
        "ok": True,
        "benchmark_id": "newborn_long_horizon",
        "condition_ids": ["A", "B", "C"],
        "compare_condition_ids": ["B", "C"],
        "repeats": 1,
        "seeds_per_repeat": 2,
        "metric_keys": [
            "success_rate",
            "mean_milestone_score",
        ],
        "repeat_batches": [
            {
                "repeat_index": 1,
                "seed_list": [101, 202],
                "batch": {
                    "benchmark_id": "newborn_long_horizon",
                    "results": [
                        {
                            "ok": True,
                            "run_id": "run_a_1",
                            "condition_label": "Full CCA8 (merge retrieval)",
                            "effective_obs_mask_prob": 0.70,
                            "episode_record": {
                                "benchmark": "newborn_long_horizon",
                                "condition": "A",
                                "seed": 101,
                                "episode_index": 0,
                                "success": True,
                                "cycles_to_end": 48,
                                "milestone_vector": {
                                    "stood_up": True,
                                    "reached_mom": True,
                                    "found_nipple": True,
                                    "latched_nipple": True,
                                    "milk_drinking": True,
                                    "rested": True,
                                },
                                "milestone_score": 1.0,
                                "cumulative_prediction_error": 12.0,
                                "llm_call_count": 0,
                            },
                        },
                        {
                            "ok": True,
                            "run_id": "run_b_1",
                            "condition_label": "CCA8 without episodic readback",
                            "effective_obs_mask_prob": 0.70,
                            "episode_record": {
                                "benchmark": "newborn_long_horizon",
                                "condition": "B",
                                "seed": 101,
                                "episode_index": 0,
                                "success": False,
                                "cycles_to_end": 60,
                                "milestone_vector": {
                                    "stood_up": True,
                                    "reached_mom": True,
                                    "found_nipple": True,
                                    "latched_nipple": False,
                                    "milk_drinking": False,
                                    "rested": False,
                                },
                                "milestone_score": 0.5,
                                "cumulative_prediction_error": 7.0,
                                "llm_call_count": 0,
                            },
                        },
                        {
                            "ok": True,
                            "run_id": "run_c_1",
                            "condition_label": "CCA8 with replace-mode prior injection",
                            "effective_obs_mask_prob": 0.70,
                            "episode_record": {
                                "benchmark": "newborn_long_horizon",
                                "condition": "C",
                                "seed": 101,
                                "episode_index": 0,
                                "success": False,
                                "cycles_to_end": 60,
                                "milestone_vector": {
                                    "stood_up": True,
                                    "reached_mom": True,
                                    "found_nipple": False,
                                    "latched_nipple": False,
                                    "milk_drinking": False,
                                    "rested": False,
                                },
                                "milestone_score": 0.3333333333333333,
                                "cumulative_prediction_error": 9.0,
                                "llm_call_count": 0,
                            },
                        },
                    ],
                    "condition_summaries": [
                        {
                            "condition_id": "A",
                            "condition_label": "Full CCA8 (merge retrieval)",
                            "n_ok": 1,
                            "n_fail": 0,
                            "success_rate": 1.0,
                            "mean_milestone_score": 1.0,
                        },
                        {
                            "condition_id": "B",
                            "condition_label": "CCA8 without episodic readback",
                            "n_ok": 1,
                            "n_fail": 0,
                            "success_rate": 0.0,
                            "mean_milestone_score": 0.5,
                        },
                        {
                            "condition_id": "C",
                            "condition_label": "CCA8 with replace-mode prior injection",
                            "n_ok": 1,
                            "n_fail": 0,
                            "success_rate": 0.0,
                            "mean_milestone_score": 0.3333333333333333,
                        },
                    ],
                },
            }
        ],
        "repeat_metric_rows": [
            {
                "A": {
                    "success_rate": 1.0,
                    "mean_milestone_score": 1.0,
                },
                "B": {
                    "success_rate": 0.0,
                    "mean_milestone_score": 0.5,
                },
                "C": {
                    "success_rate": 0.0,
                    "mean_milestone_score": 0.3333333333333333,
                },
            }
        ],
        "averages_by_condition": {
            "A": {
                "condition_id": "A",
                "success_rate": 1.0,
                "mean_milestone_score": 1.0,
            },
            "B": {
                "condition_id": "B",
                "success_rate": 0.0,
                "mean_milestone_score": 0.5,
            },
            "C": {
                "condition_id": "C",
                "success_rate": 0.0,
                "mean_milestone_score": 0.3333333333333333,
            },
        },
        "condition_metric_stats_by_condition": {
            "A": {
                "success_rate": {"n": 1, "mean": 1.0, "sd": None, "ci_low": 1.0, "ci_high": 1.0, "confidence": 0.95},
                "mean_milestone_score": {"n": 1, "mean": 1.0, "sd": None, "ci_low": 1.0, "ci_high": 1.0, "confidence": 0.95},
            },
            "B": {
                "success_rate": {"n": 1, "mean": 0.0, "sd": None, "ci_low": 0.0, "ci_high": 0.0, "confidence": 0.95},
                "mean_milestone_score": {"n": 1, "mean": 0.5, "sd": None, "ci_low": 0.5, "ci_high": 0.5, "confidence": 0.95},
            },
            "C": {
                "success_rate": {"n": 1, "mean": 0.0, "sd": None, "ci_low": 0.0, "ci_high": 0.0, "confidence": 0.95},
                "mean_milestone_score": {"n": 1, "mean": 0.3333333333333333, "sd": None, "ci_low": 0.3333333333333333, "ci_high": 0.3333333333333333, "confidence": 0.95},
            },
        },
        "paired_stats_vs_a": {
            "B": {
                "success_rate": {
                    "n": 1,
                    "mean_ref": 1.0,
                    "mean_cmp": 0.0,
                    "mean_diff": -1.0,
                    "sd_diff": None,
                    "ci_low": -1.0,
                    "ci_high": -1.0,
                    "t_stat": None,
                    "p_value": None,
                    "confidence": 0.95,
                }
            },
            "C": {
                "success_rate": {
                    "n": 1,
                    "mean_ref": 1.0,
                    "mean_cmp": 0.0,
                    "mean_diff": -1.0,
                    "sd_diff": None,
                    "ci_low": -1.0,
                    "ci_high": -1.0,
                    "t_stat": None,
                    "p_value": None,
                    "confidence": 0.95,
                }
            },
        },
    }

    bundle = _experiment_write_repeated_result_bundle_v1(
        ctx,
        repeated_result,
        bundle_label="pytest_bundle",
    )

    assert bundle["ok"] is True

    episode_rows_path = Path(bundle["episode_rows_jsonl_path"])
    repeat_rows_path = Path(bundle["repeat_rows_jsonl_path"])
    stats_json_path = Path(bundle["stats_json_path"])

    assert episode_rows_path.exists()
    assert repeat_rows_path.exists()
    assert stats_json_path.exists()

    stats_payload = json.loads(stats_json_path.read_text(encoding="utf-8"))
    assert "repeat_metric_rows" in stats_payload
    assert stats_payload["repeat_metric_rows"] == repeated_result["repeat_metric_rows"]
    assert stats_payload["protocol"]["benchmark_id"] == "newborn_long_horizon"

    episode_lines = [line for line in episode_rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]
    repeat_lines = [line for line in repeat_rows_path.read_text(encoding="utf-8").splitlines() if line.strip()]

    assert len(episode_lines) == 3
    assert len(repeat_lines) == 3