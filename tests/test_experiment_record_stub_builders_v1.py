# -*- coding: utf-8 -*-
"""
Focused tests for the experiment JSON stub-record builders.

These tests intentionally stay at the helper layer. They do not run any experiment
batch. They only verify that the stub builders produce stable, JSON-serializable
records from the current protocol/context seam.
"""

from __future__ import annotations

import json

import cca8_run


def test_experiment_build_cycle_record_stub_v1_is_json_serializable(monkeypatch) -> None:
    """Build a cycle stub from live ctx state and verify JSON-safe fields.

    Coverage goals:
      - uses the prepared run_id from ctx.experiment_last_summary when present
      - reflects benchmark/condition/seed/episode/cycle fields
      - carries stage, zone, obs-mask info, prediction error, and retrieval event
      - round-trips through json.dumps/json.loads without type surprises
    """
    monkeypatch.setattr(cca8_run, "body_space_zone", lambda _ctx: "unsafe_cliff_near")

    ctx = cca8_run.Ctx()
    ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="newborn_long_horizon",
        condition_ids=["A", "E"],
        seed_list=[17, 19],
        episodes_per_seed=2,
        max_cycles=45,
        obs_mask_prob=0.35,
    )
    ctx.experiment_last_summary = {"run_id": "prepared_run_001"}
    ctx.lt_obs_last_stage = "struggle"
    ctx.controller_steps = 7
    ctx.obs_mask_seed = 1234
    ctx.pred_err_v0_last = {"posture": 1, "mom_distance": 0}
    ctx.env_last_action = "policy:follow_mom"
    ctx.wm_mapswitch_last_events = [
        {
            "schema": "wm_mapswitch_event_v1",
            "ok": True,
            "mode": "merge",
            "candidate_count": 2,
            "chosen_seed": {"engram_id": "ENG001"},
        }
    ]

    record = cca8_run.experiment_build_cycle_record_stub_v1(
        ctx,
        condition_id="E",
        seed=19,
        episode_index=3,
        cycle_index=11,
    )

    assert record["schema"] == "experiment_cycle_record_v1"
    assert record["record_type"] == "cycle"
    assert record["experiment_id"] == "prepared_run_001"
    assert record["benchmark"] == "newborn_long_horizon"
    assert record["condition"] == "E"
    assert record["seed"] == 19
    assert record["episode_index"] == 3
    assert record["cycle_index"] == 11
    assert record["env_step"] == 7
    assert record["stage"] == "struggle"
    assert record["zone"] == "unsafe_cliff_near"
    assert record["obs_mask_stats"] == {"prob": 0.35, "seed": 1234}
    assert record["retrieval_event"] == ctx.wm_mapswitch_last_events[-1]
    assert record["pred_err"] == {"posture": 1, "mom_distance": 0}
    assert record["selected_policy"] is None
    assert record["llm_advice_summary"] is None
    assert record["executed_action"] == "policy:follow_mom"
    assert record["milestones"] == []
    assert record["done"] is False
    assert record["termination_reason"] is None

    encoded = json.dumps(record, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded == record


def test_experiment_build_episode_record_stub_v1_is_json_serializable(monkeypatch) -> None:
    """Build episode-summary stubs and verify fallback/override run-id behavior.

    Coverage goals:
      - falls back to experiment_make_run_id_v1(...) when no prepared summary exists
      - explicit experiment_id overrides the fallback run id
      - emits the expected placeholder metrics and counters
      - round-trips through json.dumps/json.loads without type surprises
    """
    monkeypatch.setattr(cca8_run, "experiment_make_run_id_v1", lambda _ctx, _cfg=None: "fallback_run_002")

    ctx = cca8_run.Ctx()
    ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="goat04_context",
        condition_ids=["A", "B", "C"],
        seed_list=[11, 23, 37],
    )
    ctx.experiment_last_summary = {}

    record = cca8_run.experiment_build_episode_record_stub_v1(
        ctx,
        condition_id="B",
        seed=23,
        episode_index=5,
    )

    assert record["schema"] == "experiment_episode_record_v1"
    assert record["record_type"] == "episode_summary"
    assert record["experiment_id"] == "fallback_run_002"
    assert record["benchmark"] == "goat04_context"
    assert record["condition"] == "B"
    assert record["seed"] == 23
    assert record["episode_index"] == 5
    assert record["success"] is None
    assert record["cycles_to_end"] is None
    assert record["milestone_vector"] == {}
    assert record["context_switch_accuracy"] is None
    assert record["false_retrieval_count"] == 0
    assert record["cue_leakage_violations"] == 0
    assert record["cumulative_prediction_error"] is None
    assert record["repeated_action_loop_count"] == 0
    assert record["llm_call_count"] == 0
    assert record["latency_ms_total"] is None

    encoded = json.dumps(record, sort_keys=True)
    decoded = json.loads(encoded)
    assert decoded == record

    override_record = cca8_run.experiment_build_episode_record_stub_v1(
        ctx,
        experiment_id="manual_run_777",
        condition_id="C",
        seed=37,
        episode_index=8,
    )

    assert override_record["experiment_id"] == "manual_run_777"
    assert override_record["condition"] == "C"
    assert override_record["seed"] == 37
    assert override_record["episode_index"] == 8

    override_encoded = json.dumps(override_record, sort_keys=True)
    override_decoded = json.loads(override_encoded)
    assert override_decoded == override_record