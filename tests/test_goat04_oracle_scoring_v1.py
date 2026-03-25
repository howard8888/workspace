# -*- coding: utf-8 -*-
"""
Focused tests for the first goat04 external-oracle patch.

These tests ensure that:
  1) goat04 hidden context truth is not leaked through the public observation metadata
  2) experiment episode scoring uses the hidden oracle/action window rather than
     trusting the retrieval layer's own self-reported ok=True flag
"""

from __future__ import annotations

from cca8_env import EnvConfig, HybridEnvironment
import cca8_run


def test_goat04_observation_hides_context_label_but_keeps_contextual_cues() -> None:
    """goat04 should keep hidden context truth private while still exposing ambiguous cues."""
    env = HybridEnvironment(config=EnvConfig(scenario_name="goat_foraging_04"))
    obs, _info = env.reset()

    assert obs.env_meta.get("scenario_stage") == "goat_foraging_04_scan"
    assert "context_label" not in obs.env_meta
    assert "terrain:forage_patch" in obs.cues
    assert "vision:silhouette:fox" in obs.cues


def test_experiment_summarize_generic_episode_v1_uses_external_goat04_oracle() -> None:
    """A wrong retrieval but correct later action should be scored by the external oracle window."""
    ctx = cca8_run.Ctx()
    ctx.experiment_cfg = cca8_run.ExperimentProtocolConfig(
        benchmark_id="goat04_context",
        condition_ids=["A"],
        seed_list=[11],
        max_cycles=40,
    )
    ctx.wm_goat04_seed_engram_by_context = {
        "fox": "ENGFOX",
        "hawk": "ENGHAWK",
    }

    raw_records = [
        {
            "env_step": 4,
            "scenario_stage": "goat_foraging_04_scan",
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "policy_fired": "policy:follow_mom",
            "action_applied": "policy:follow_mom",
            "pred_err_v0": {},
            "obs": {"env_meta": {"milestones": ["context:hawk"]}},
            "oracle": {
                "goat04": {
                    "true_context": "hawk",
                    "expected_policy": "policy:rest",
                    "switch_step": 4,
                    "response_deadline_step": 7,
                    "switch_event": True,
                    "response_window_open": True,
                }
            },
            "wm": {
                "mapswitch": {
                    "events": [
                        {
                            "reason": "goat04_context:hawk",
                            "ok": True,
                            "chosen_seed": {"engram_id": "ENGFOX"},
                            "load": {"merge_guardrail_ok": True},
                        }
                    ]
                }
            },
        },
        {
            "env_step": 5,
            "scenario_stage": "goat_foraging_04_scan",
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "policy_fired": "policy:rest",
            "action_applied": "policy:rest",
            "pred_err_v0": {},
            "obs": {"env_meta": {}},
            "oracle": {
                "goat04": {
                    "true_context": "hawk",
                    "expected_policy": "policy:rest",
                    "switch_step": 4,
                    "response_deadline_step": 7,
                    "switch_event": False,
                    "response_window_open": True,
                }
            },
            "wm": {"mapswitch": {"events": []}},
        },
    ]

    rec = cca8_run._experiment_summarize_generic_episode_v1(
        ctx,
        experiment_id="run_goat04_oracle_001",
        condition_id="A",
        seed=11,
        episode_index=0,
        raw_records=raw_records,
        latency_ms_total=12.5,
    )

    # New external-oracle behavior: action accuracy is judged over the hidden response window.
    assert rec["context_switch_accuracy"] == 1.0
    assert rec["oracle_action_accuracy"] == 1.0
    assert rec["stabilization_latency"] == 1.0

    # The retrieval layer graded itself ok=True, but the external oracle sees the wrong retrieved seed/context.
    assert rec["internal_retrieval_event_ratio"] == 1.0
    assert rec["oracle_retrieval_precision"] == 0.0
    assert rec["false_retrieval_count"] == 1

    # This case is not a retrieval/action dissociation: the action was corrected inside the response window.
    assert rec["retrieval_action_dissociation_count"] == 0
    assert rec["cue_leakage_violations"] == 0