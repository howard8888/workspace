# -*- coding: utf-8 -*-
"""
Focused tests for the A/B/C experiment batch helper.

These tests check that:
- the batch helper loops over A/B/C and the configured seeds,
- the benchmark-aware newborn summary aggregates the expected means,
- and the batch summary renderer exposes the new B2 metrics clearly.
"""

import cca8_run as runmod


def test_experiment_run_condition_batch_v1_aggregates_newborn(monkeypatch) -> None:
    """Batch helper should aggregate A/B/C newborn runs over the selected seeds."""
    ctx = runmod.Ctx()
    ctx.experiment_cfg = runmod.ExperimentProtocolConfig(
        benchmark_id="newborn_long_horizon",
        condition_ids=["A", "B", "C"],
        seed_list=[11, 23],
        episodes_per_seed=1,
    )

    def fake_run(protocol_ctx, *, condition_id=None, seed=None, episode_index=0, suppress_output=True):
        _ = protocol_ctx
        _ = suppress_output

        cid = str(condition_id)
        score_map = {"A": 1.0, "B": 0.5, "C": 0.25}
        loop_map = {"A": 0, "B": 2, "C": 4}
        pred_map = {"A": 1.0, "B": 3.0, "C": 5.0}
        success_map = {"A": True, "B": False, "C": False}

        return {
            "ok": True,
            "run_id": f"{cid}_{seed}_{episode_index}",
            "benchmark_id": "newborn_long_horizon",
            "condition_id": cid,
            "condition_label": runmod.experiment_condition_catalog_v1()[cid].label,
            "seed": int(seed),
            "episode_index": int(episode_index),
            "cycle_record_count": 10,
            "episode_record": {
                "success": success_map[cid],
                "milestone_score": score_map[cid],
                "recovery_latency": float(seed),
                "repeated_action_loop_count": loop_map[cid],
                "cumulative_prediction_error": pred_map[cid],
            },
            "cycle_json_path": f"{cid}_{seed}_{episode_index}.cycle.jsonl",
            "episode_json_path": f"{cid}_{seed}_{episode_index}.episode.jsonl",
            "suppressed_output": True,
            "captured_output_lines": 0,
        }

    monkeypatch.setattr(runmod, "experiment_run_one_episode_v1", fake_run)

    batch = runmod.experiment_run_condition_batch_v1(
        ctx,
        condition_ids=["A", "B", "C"],
        seed_list=[11, 23],
        episodes_per_seed=1,
        suppress_output=True,
    )

    assert batch["ok"] is True
    assert batch["benchmark_id"] == "newborn_long_horizon"
    assert batch["run_count"] == 6
    assert batch["ok_count"] == 6
    assert batch["fail_count"] == 0

    by_id = {row["condition_id"]: row for row in batch["condition_summaries"]}

    assert by_id["A"]["success_rate"] == 1.0
    assert by_id["B"]["success_rate"] == 0.0
    assert by_id["C"]["success_rate"] == 0.0

    assert by_id["A"]["mean_milestone_score"] == 1.0
    assert by_id["B"]["mean_milestone_score"] == 0.5
    assert by_id["C"]["mean_milestone_score"] == 0.25

    assert by_id["A"]["mean_recovery_latency"] == 17.0
    assert by_id["B"]["mean_repeated_loops"] == 2.0
    assert by_id["C"]["mean_cumulative_prediction_error"] == 5.0


def test_render_experiment_batch_summary_lines_v1_shows_b2_metrics() -> None:
    """Renderer should expose milestone_score and recovery_lat for newborn B2 batches."""
    batch = {
        "ok": True,
        "benchmark_id": "newborn_long_horizon",
        "condition_ids": ["A", "B", "C"],
        "seed_list": [11, 23],
        "episodes_per_seed": 1,
        "run_count": 6,
        "ok_count": 6,
        "fail_count": 0,
        "condition_summaries": [
            {
                "condition_id": "A",
                "condition_label": "Full CCA8 (merge retrieval)",
                "n_ok": 2,
                "n_fail": 0,
                "success_rate": 1.0,
                "mean_milestone_score": 1.0,
                "mean_recovery_latency": 4.0,
                "mean_repeated_loops": 0.0,
                "mean_cumulative_prediction_error": 2.0,
            }
        ],
    }

    lines = runmod.render_experiment_batch_summary_lines_v1(batch)
    joined = "\n".join(lines)

    assert "milestone_score" in joined
    assert "recovery_lat" in joined
    assert "Full CCA8" in joined