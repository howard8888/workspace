# -*- coding: utf-8 -*-
"""
Focused tests for the first real experiment execution helper.

These tests verify that experiment_run_one_episode_v1(...) uses an isolated
sandbox runtime, emits experiment-schema JSONL rows, and rejects the not-yet-
wired LLM-only condition cleanly.
"""

from __future__ import annotations

import json

import cca8_run


def test_experiment_run_one_episode_v1_uses_sandbox_and_writes_records(tmp_path, monkeypatch) -> None:
    """Run one stubbed goat04 episode and verify transformed JSONL output.

    Coverage goals:
      - the live protocol ctx is not used as the runtime ctx
      - one prepared run id is used for both cycle and episode JSONL outputs
      - generic cycle rows are transformed into experiment cycle-record rows
      - the episode summary record is written and copied back into protocol_ctx.experiment_last_summary

    Important for the goat04 oracle patch:
      - the fake raw cycle records must now include the hidden oracle payload
      - a correct benchmark action must occur inside the oracle response window
      - retrieval grading needs a chosen_seed.engram_id that maps back to the true context
    """
    def fake_run_env_closed_loop_steps(env, world, drives, ctx, policy_rt, n_steps) -> None:
        _ = env, world, drives, policy_rt, n_steps

        ctx.wm_goat04_seed_engram_by_context = {
            "fox": "ENGFOX",
            "hawk": "ENGHAWK",
        }

        ctx.cycle_json_records.append(
            {
                "controller_steps": 1,
                "env_step": 1,
                "scenario_stage": "goat_foraging_04_scan",
                "posture": "standing",
                "mom_distance": "far",
                "nipple_state": "hidden",
                "zone": "unknown",
                "action_applied": None,
                "policy_fired": "policy:explore_check",
                "obs": {"env_meta": {"milestones": ["context:fox"]}},
                "oracle": {
                    "goat04": {
                        "true_context": "fox",
                        "expected_policy": "policy:follow_mom",
                        "switch_step": 1,
                        "response_deadline_step": 4,
                        "switch_event": True,
                        "response_window_open": True,
                    }
                },
                "wm": {
                    "mapswitch": {
                        "events": [
                            {
                                "reason": "goat04_context:fox",
                                "ok": True,
                                "chosen_seed": {"engram_id": "ENGFOX"},
                                "load": {"merge_guardrail_ok": True},
                            }
                        ]
                    }
                },
                "pred_err_v0": {"posture": 1},
            }
        )
        ctx.cycle_json_records.append(
            {
                "controller_steps": 2,
                "env_step": 2,
                "scenario_stage": "goat_foraging_04_scan",
                "posture": "standing",
                "mom_distance": "far",
                "nipple_state": "hidden",
                "zone": "unknown",
                "action_applied": "policy:follow_mom",
                "policy_fired": "policy:follow_mom",
                "obs": {"env_meta": {}},
                "oracle": {
                    "goat04": {
                        "true_context": "fox",
                        "expected_policy": "policy:follow_mom",
                        "switch_step": 1,
                        "response_deadline_step": 4,
                        "switch_event": False,
                        "response_window_open": True,
                    }
                },
                "wm": {"mapswitch": {"events": []}},
                "pred_err_v0": {"posture": 0},
            }
        )

    monkeypatch.setattr(cca8_run, "run_env_closed_loop_steps", fake_run_env_closed_loop_steps)
    monkeypatch.setattr(cca8_run, "experiment_make_run_id_v1", lambda ctx, cfg=None: "sandbox_run_001")

    protocol_ctx = cca8_run.Ctx()
    protocol_ctx.controller_steps = 99
    protocol_ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="goat04_context",
        condition_ids=["A"],
        seed_list=[23],
        max_cycles=12,
        output_dir=str(tmp_path),
    )

    result = cca8_run.experiment_run_one_episode_v1(protocol_ctx, condition_id="A", seed=23, suppress_output=True)

    assert result["ok"] is True
    assert result["run_id"] == "sandbox_run_001"
    assert result["cycle_record_count"] == 2
    assert result["seed"] == 23
    assert protocol_ctx.controller_steps == 99
    assert protocol_ctx.experiment_last_summary["last_run_condition_id"] == "A"
    assert protocol_ctx.experiment_last_summary["last_run_seed"] == 23

    episode_record = result["episode_record"]
    assert episode_record["benchmark"] == "goat04_context"
    assert episode_record["context_switch_accuracy"] == 1.0
    assert episode_record["oracle_action_accuracy"] == 1.0
    assert episode_record["oracle_retrieval_precision"] == 1.0
    assert episode_record["internal_retrieval_event_ratio"] == 1.0
    assert episode_record["stabilization_latency"] == 1.0
    assert episode_record["false_retrieval_count"] == 0
    assert episode_record["cue_leakage_violations"] == 0
    assert episode_record["cumulative_prediction_error"] == 1.0

    cycle_path = tmp_path / "sandbox_run_001__cycle.jsonl"
    episode_path = tmp_path / "sandbox_run_001__episode.jsonl"
    assert cycle_path.exists()
    assert episode_path.exists()

    cycle_lines = cycle_path.read_text(encoding="utf-8").strip().splitlines()
    episode_lines = episode_path.read_text(encoding="utf-8").strip().splitlines()
    assert len(cycle_lines) == 2
    assert len(episode_lines) == 1

    cycle_record = json.loads(cycle_lines[0])
    saved_episode = json.loads(episode_lines[0])
    assert cycle_record["schema"] == "experiment_cycle_record_v1"
    assert cycle_record["condition"] == "A"
    assert cycle_record["oracle"]["goat04"]["true_context"] == "fox"
    assert saved_episode["schema"] == "experiment_episode_record_v1"
    assert saved_episode["context_switch_accuracy"] == 1.0


def test_experiment_run_one_episode_v1_rejects_llm_only_conditions(tmp_path) -> None:
    """Condition D should fail clearly until the later LLM control hook exists."""
    protocol_ctx = cca8_run.Ctx()
    protocol_ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="goat04_context",
        condition_ids=["D"],
        seed_list=[11],
        max_cycles=5,
        output_dir=str(tmp_path),
    )

    result = cca8_run.experiment_run_one_episode_v1(protocol_ctx, condition_id="D", seed=11, suppress_output=True)

    assert result["ok"] is False
    assert result["why"] == "condition_not_yet_supported"
    assert result["condition_id"] == "D"
    assert result["agent_mode"] == "llm_only"
    assert result["llm_role"] == "controller"