# -*- coding: utf-8 -*-
"""
Focused tests for the benchmark-aware submenu 17 summary helper.

These tests verify that the menu summary now shows the oracle-scored goat04
metrics directly, while still rendering the newborn benchmark in a compact
behavioral form.
"""

from __future__ import annotations

import cca8_run


def test_render_experiment_episode_summary_lines_v1_goat04_shows_oracle_metrics() -> None:
    """goat04 summaries should surface oracle-scored B1 metrics directly."""
    result = {
        "run_id": "run_goat04_001",
        "benchmark_id": "goat04_context",
        "condition_id": "A",
        "condition_label": "Full CCA8 (merge retrieval)",
        "seed": 11,
        "episode_record": {
            "cycles_to_end": 40,
            "success": True,
            "context_switch_accuracy": 0.75,
            "oracle_action_accuracy": 0.75,
            "oracle_retrieval_precision": 1.0,
            "internal_retrieval_event_ratio": 0.5,
            "stabilization_latency": 1.0,
            "retrieval_action_dissociation_count": 1,
            "false_retrieval_count": 0,
            "cue_leakage_violations": 0,
            "repeated_action_loop_count": 2,
            "cumulative_prediction_error": 1.25,
            "latency_ms_total": 12.5,
        },
    }

    lines = cca8_run.render_experiment_episode_summary_lines_v1(result)
    text = "\n".join(lines)

    assert "[experiments] benchmark         : goat04_context" in text
    assert "[experiments] context_switch_acc: 0.750" in text
    assert "[experiments] oracle_action_acc : 0.750" in text
    assert "[experiments] oracle_retr_prec  : 1.000" in text
    assert "[experiments] internal_retr_rt  : 0.500" in text
    assert "[experiments] stabilize_lat     : 1.000" in text
    assert "[experiments] retr_act_dissoc   : 1" in text
    assert "[experiments] false_retrievals  : 0" in text
    assert "[experiments] cue_leakage       : 0" in text
    assert "[experiments] milestones        :" not in text


def test_render_experiment_episode_summary_lines_v1_newborn_shows_milestones() -> None:
    """newborn benchmark summaries should stay behavioral and milestone-centered."""
    result = {
        "run_id": "run_newborn_001",
        "benchmark_id": "newborn_long_horizon",
        "condition_id": "B",
        "condition_label": "CCA8 without episodic readback",
        "seed": 23,
        "episode_record": {
            "cycles_to_end": 75,
            "success": False,
            "milestone_vector": {
                "stood_up": True,
                "reached_mom": False,
                "found_nipple": False,
                "latched": False,
                "rested": False,
            },
            "repeated_action_loop_count": 14,
            "cumulative_prediction_error": 2.5,
            "latency_ms_total": 8.0,
        },
    }

    lines = cca8_run.render_experiment_episode_summary_lines_v1(result)
    text = "\n".join(lines)

    assert "[experiments] benchmark         : newborn_long_horizon" in text
    assert "[experiments] milestones        :" in text
    assert '"stood_up": true' in text
    assert "[experiments] repeated_loops    : 14" in text
    assert "[experiments] cumulative_pred_e : 2.500" in text
    assert "[experiments] oracle_action_acc :" not in text
    assert "[experiments] oracle_retr_prec  :" not in text