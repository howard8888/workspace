# -*- coding: utf-8 -*-
"""
Focused tests for the paper-aligned B2 newborn_long_horizon scoring helper.

These tests check that:
- the six milestone ladder is enforced in order,
- unsafe rest does not count as the final milestone,
- the episode stub exposes the new B2 fields,
- and the experiment summary lines show the new B2 metrics.
"""

from cca8_run import (
    Ctx,
    _experiment_summarize_newborn_b2_v1,
    experiment_build_episode_record_stub_v1,
    render_experiment_episode_summary_lines_v1,
)


def _ordered_success_records() -> list[dict]:
    """Return a minimal raw-record sequence that satisfies the paper-frozen B2 ladder."""
    return [
        {
            "env_step": 0,
            "posture": "fallen",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "zone": "unsafe",
            "obs": {"predicates": ["posture:fallen"]},
        },
        {
            "env_step": 1,
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "zone": "neutral",
            "obs": {"predicates": ["posture:standing"]},
        },
        {
            "env_step": 2,
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "hidden",
            "zone": "neutral",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close"]},
        },
        {
            "env_step": 3,
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "reachable",
            "zone": "neutral",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:found"]},
        },
        {
            "env_step": 4,
            "posture": "latched",
            "mom_distance": "touching",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:latched", "milk:drinking"]},
        },
        {
            "env_step": 5,
            "posture": "resting",
            "mom_distance": "touching",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["resting", "proximity:mom:close", "nipple:latched", "milk:drinking"]},
        },
    ]


def test_newborn_b2_ordered_success() -> None:
    """All six ordered milestones should produce success, score 1.0, and recovery latency at first stand."""
    summary = _experiment_summarize_newborn_b2_v1(_ordered_success_records())

    assert summary["success"] is True
    assert summary["milestone_score"] == 1.0
    assert summary["recovery_latency"] == 1.0
    assert summary["milestone_vector"] == {
        "stood_up": True,
        "reached_mom": True,
        "found_nipple": True,
        "latched_nipple": True,
        "milk_drinking": True,
        "rested": True,
    }


def test_newborn_b2_out_of_order_stays_incomplete() -> None:
    """Later milestones appearing before earlier ones should not be counted out of order."""
    raw_records = [
        {
            "env_step": 0,
            "posture": "fallen",
            "mom_distance": "far",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["posture:fallen", "nipple:latched", "milk:drinking"]},
        },
        {
            "env_step": 1,
            "posture": "resting",
            "mom_distance": "far",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["resting", "nipple:latched", "milk:drinking"]},
        },
    ]

    summary = _experiment_summarize_newborn_b2_v1(raw_records)

    assert summary["success"] is False
    assert summary["milestone_vector"]["stood_up"] is True
    assert summary["milestone_vector"]["reached_mom"] is False
    assert summary["milestone_vector"]["latched_nipple"] is False
    assert summary["milestone_vector"]["milk_drinking"] is False
    assert summary["milestone_vector"]["rested"] is False
    assert summary["milestone_score"] == 1.0 / 6.0


def test_newborn_b2_rest_requires_safe_zone() -> None:
    """Resting does not count as the final milestone unless the zone is safe."""
    raw_records = _ordered_success_records()
    raw_records[-1]["zone"] = "unsafe"

    summary = _experiment_summarize_newborn_b2_v1(raw_records)

    assert summary["success"] is False
    assert summary["milestone_vector"]["milk_drinking"] is True
    assert summary["milestone_vector"]["rested"] is False
    assert summary["milestone_score"] == 5.0 / 6.0


def test_episode_summary_lines_show_new_b2_metrics() -> None:
    """The experiment menu summary should expose milestone_score and recovery_latency for B2."""
    result = {
        "run_id": "demo",
        "benchmark_id": "newborn_long_horizon",
        "condition_id": "A",
        "condition_label": "Full CCA8 (merge retrieval)",
        "seed": 11,
        "episode_record": {
            "cycles_to_end": 6,
            "success": True,
            "milestone_vector": {"rested": True},
            "milestone_score": 1.0,
            "recovery_latency": 1.0,
            "repeated_action_loop_count": 2,
            "cumulative_prediction_error": 0.0,
            "latency_ms_total": 5.0,
        },
    }

    lines = render_experiment_episode_summary_lines_v1(result)
    joined = "\n".join(lines)

    assert "milestone_score" in joined
    assert "recovery_latency" in joined


def test_episode_record_stub_includes_newborn_b2_fields() -> None:
    """The episode stub should carry the new B2 fields so JSONL schema and writers stay aligned."""
    ctx = Ctx()
    record = experiment_build_episode_record_stub_v1(ctx, experiment_id="demo", condition_id="A", seed=11, episode_index=0)

    assert "milestone_score" in record
    assert "recovery_latency" in record
    assert record["milestone_score"] is None
    assert record["recovery_latency"] is None