# -*- coding: utf-8 -*-
"""Focused tests for newborn B2 hint-bridge and debug/metric instrumentation."""

import cca8_run as runmod


def test_follow_mom_bridge_state_strict_uses_retrieved_hint_when_bodymap_sparse(monkeypatch):
    """Strict newborn mode should use the retrieved hint when BodyMap is sparse."""
    ctx = runmod.Ctx()
    ctx.controller_steps = 10
    ctx.experiment_newborn_require_current_state = True
    ctx.experiment_newborn_retrieved_hint = {
        "posture": "standing",
        "mom_distance": "near",
        "nipple_state": "hidden",
        "zone": "safe",
    }
    ctx.experiment_newborn_retrieved_hint_until_step = 12

    monkeypatch.setattr(runmod, "bodymap_is_stale", lambda _ctx: True)
    monkeypatch.setattr(runmod, "body_posture", lambda _ctx: None)
    monkeypatch.setattr(runmod, "body_mom_distance", lambda _ctx: None)
    monkeypatch.setattr(runmod, "body_nipple_state", lambda _ctx: None)
    monkeypatch.setattr(runmod, "body_space_zone", lambda _ctx: "unknown")

    state = runmod._follow_mom_bridge_state_v1(None, ctx)

    assert state["posture"] == "standing"
    assert state["mom_distance"] == "near"
    assert state["nipple_state"] == "hidden"
    assert state["zone"] == "safe"


def test_gate_seek_nipple_trigger_uses_retrieved_hint_for_mom_distance(monkeypatch):
    """Strict newborn seek gate should accept a retrieved mom-distance hint when current distance is missing."""
    ctx = runmod.Ctx()
    ctx.controller_steps = 10
    ctx.experiment_newborn_require_current_state = True
    ctx.experiment_newborn_retrieved_hint = {
        "mom_distance": "near",
        "nipple_state": "hidden",
    }
    ctx.experiment_newborn_retrieved_hint_until_step = 12

    monkeypatch.setattr(runmod, "bodymap_is_stale", lambda _ctx: False)
    monkeypatch.setattr(runmod, "body_posture", lambda _ctx: "standing")
    monkeypatch.setattr(runmod, "body_mom_distance", lambda _ctx: None)
    monkeypatch.setattr(runmod, "body_nipple_state", lambda _ctx: None)
    monkeypatch.setattr(runmod, "has_pred_near_now", lambda *args, **kwargs: False)

    drives = runmod.Drives(hunger=0.50, fatigue=0.30, warmth=0.60)

    assert runmod._gate_seek_nipple_trigger_body_first(None, drives, ctx) is True


def test_newborn_summary_reports_late_phase_latencies():
    """The newborn summary should expose the later milestone timing that batch success hides."""
    raw_records = [
        {
            "env_step": 5,
            "posture": "standing",
            "mom_distance": "far",
            "nipple_state": "hidden",
            "zone": "unknown",
            "obs": {"predicates": ["posture:standing"]},
        },
        {
            "env_step": 12,
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "hidden",
            "zone": "safe",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close"]},
        },
        {
            "env_step": 17,
            "posture": "standing",
            "mom_distance": "near",
            "nipple_state": "reachable",
            "zone": "safe",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:found"]},
        },
        {
            "env_step": 23,
            "posture": "latched",
            "mom_distance": "near",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:latched"]},
        },
        {
            "env_step": 24,
            "posture": "latched",
            "mom_distance": "near",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["posture:standing", "proximity:mom:close", "nipple:latched", "milk:drinking"]},
        },
        {
            "env_step": 26,
            "posture": "resting",
            "mom_distance": "touching",
            "nipple_state": "latched",
            "zone": "safe",
            "obs": {"predicates": ["resting", "proximity:mom:close", "nipple:latched", "milk:drinking"]},
        },
    ]

    summary = runmod._experiment_summarize_newborn_b2_v1(raw_records)

    assert summary["success"] is True
    assert summary["milestone_steps"]["stood_up"] == 5
    assert summary["milestone_steps"]["reached_mom"] == 12
    assert summary["milestone_steps"]["found_nipple"] == 17
    assert summary["milestone_steps"]["latched_nipple"] == 23
    assert summary["milestone_steps"]["rested"] == 26

    assert summary["recovery_latency"] == 5.0
    assert summary["time_to_rested"] == 26.0
    assert summary["mom_approach_latency"] == 7.0
    assert summary["nipple_find_latency"] == 5.0
    assert summary["latch_latency"] == 6.0
    assert summary["rest_completion_latency"] == 3.0


def test_newborn_retrieval_debug_counts_noop_and_non_noop():
    """Retrieval debug should distinguish merge no-ops from retrievals that actually changed WorkingMap."""
    raw_records = [
        {
            "env_step": 9,
            "wm": {
                "mapswitch": {
                    "events": [
                        {
                            "reason": "newborn_b2:first_stand:boundary",
                            "ok": True,
                            "load": {
                                "mode": "merge",
                                "added_entities": 0,
                                "filled_slots": 0,
                                "added_edges": 0,
                                "stored_prior_cues": 0,
                            },
                        }
                    ]
                }
            },
        },
        {
            "env_step": 11,
            "wm": {
                "mapswitch": {
                    "events": [
                        {
                            "reason": "newborn_b2:first_stand:boundary",
                            "ok": True,
                            "load": {
                                "mode": "replace",
                                "entities": 5,
                                "relations": 4,
                            },
                        }
                    ]
                }
            },
        },
    ]

    dbg = runmod._newborn_retrieval_debug_from_raw_records_v1(raw_records)

    assert dbg["retrieval_event_count"] == 2
    assert dbg["retrieval_ok_count"] == 2
    assert dbg["retrieval_non_noop_count"] == 1
    assert dbg["retrieval_merge_noop_count"] == 1
    assert dbg["retrieval_replace_count"] == 1
    assert dbg["retrieval_steps"] == [9, 11]


def test_condition_b_disables_newborn_autoretrieve_and_c_uses_replace():
    """The experiment condition application should keep B=no retrieval and C=replace retrieval."""
    runtime = runmod.experiment_make_sandbox_runtime_v1()
    world = runtime["world"]
    drives = runtime["drives"]
    ctx = runtime["ctx"]
    env = runtime["env"]

    cfg = runmod.ExperimentProtocolConfig(benchmark_id="newborn_long_horizon")

    info = runmod.experiment_configure_benchmark_runtime_v1(world, drives, ctx, env, "newborn_long_horizon")
    assert info["ok"] is True

    result_b = runmod.experiment_apply_condition_runtime_v1(world, drives, ctx, env, condition_id="B", cfg=cfg)
    assert result_b["ok"] is True
    assert ctx.wm_mapsurface_autoretrieve_enabled is False
    assert ctx.wm_mapsurface_autoretrieve_mode == "merge"

    result_c = runmod.experiment_apply_condition_runtime_v1(world, drives, ctx, env, condition_id="C", cfg=cfg)
    assert result_c["ok"] is True
    assert ctx.wm_mapsurface_autoretrieve_enabled is True
    assert ctx.wm_mapsurface_autoretrieve_mode == "replace"