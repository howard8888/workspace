# -*- coding: utf-8 -*-
"""Regression tests for CCA8 long-horizon benchmark features.

These tests target the benchmark scaffolding added around long-horizon state
integrity rather than the ordinary interactive runner. They are intentionally
small and mostly use synthetic records so they stay fast under pytest and safe
to run as part of the normal ``--preflight`` path.
"""

from __future__ import annotations

import pytest

from cca8_env import EnvObservation
from cca8_run import (
    Ctx,
    ExperimentProtocolConfig,
    apply_newborn_experiment_stress_v1,
    experiment_apply_condition_runtime_v1,
    experiment_normalize_protocol_v1,
)
from cca8_state_integrity import summarize_newborn_state_integrity_v1
from cca8_rcos_experiments import rcos_robotic_run_episode_v1


def _lhsi_record(
    *,
    env_step: int,
    stage: str,
    posture: str,
    mom: str,
    nipple: str,
    zone: str,
    policy: str,
    predicates: list[str],
    mapswitch_events: list[dict] | None = None,
    pred_err: dict[str, int] | None = None,
) -> dict:
    """Return one compact raw cycle record for LHSI unit tests."""
    return {
        "env_step": int(env_step),
        "scenario_stage": stage,
        "posture": posture,
        "mom_distance": mom,
        "nipple_state": nipple,
        "zone": zone,
        "policy_fired": policy,
        "action_applied": policy,
        "obs": {"predicates": list(predicates)},
        "wm": {"mapswitch": {"events": list(mapswitch_events or [])}},
        "pred_err_v0": dict(pred_err or {}),
    }


def test_route_loss_masks_external_task_context_but_preserves_body_state() -> None:
    """Route loss should remove route/task evidence, not proprioceptive state."""
    ctx = Ctx()
    ctx.experiment_cfg = ExperimentProtocolConfig(
        newborn_stress_profile="route_loss",
        newborn_blackout_length=8,
    )
    ctx.experiment_newborn_require_resume_memory = True
    ctx.controller_steps = 5
    ctx.experiment_newborn_blackout_start_step = 3
    ctx.experiment_newborn_blackout_until_step = 8
    ctx.experiment_newborn_blackout_reason = "after_stood_up"

    obs = EnvObservation(
        raw_sensors={
            "imu_pitch": 0.12,
            "mom_distance_m": 0.4,
            "route_bearing_deg": 45,
            "battery": 0.9,
        },
        predicates=[
            "posture:standing",
            "proximity:mom:close",
            "nipple:found",
            "milk:drinking",
            "hazard:cliff:near",
            "resting",
            "alert",
        ],
        cues=[
            "vestibular:fall",
            "balance:lost",
            "vision:silhouette:mom",
            "touch:nipple",
            "nav:route_hint",
        ],
        nav_patches=[{"role": "route", "tags": ["goal:dir:east"]}],
        surface_grid={"encoding": "grid_encoding_v1", "cells": [0, 1, 2]},
        env_meta={
            "scenario_stage": "first_stand",
            "milestones": ["reached_mom"],
            "mom_position": [1.0, 0.0],
            "bearing_to_mom": 90,
        },
    )

    out = apply_newborn_experiment_stress_v1(ctx, obs)

    # Body / proprioceptive facts survive route loss.
    assert "posture:standing" in out.predicates
    assert "resting" in out.predicates
    assert "alert" in out.predicates
    assert "vestibular:fall" in out.cues
    assert "balance:lost" in out.cues
    assert out.raw_sensors["imu_pitch"] == pytest.approx(0.12)
    assert out.raw_sensors["battery"] == pytest.approx(0.9)

    # External route/task facts are suppressed.
    assert "proximity:mom:close" not in out.predicates
    assert "nipple:found" not in out.predicates
    assert "milk:drinking" not in out.predicates
    assert "hazard:cliff:near" not in out.predicates
    assert "vision:silhouette:mom" not in out.cues
    assert "touch:nipple" not in out.cues
    assert "nav:route_hint" not in out.cues
    assert "mom_distance_m" not in out.raw_sensors
    assert "route_bearing_deg" not in out.raw_sensors
    assert out.nav_patches == []
    assert out.surface_grid == {}

    # Metadata should preserve scoring/protocol fields while removing direct route hints.
    assert out.env_meta["scenario_stage"] == "first_stand"
    assert out.env_meta["milestones"] == ["reached_mom"]
    assert "mom_position" not in out.env_meta
    assert "bearing_to_mom" not in out.env_meta
    assert out.env_meta["newborn_blackout_active"] is True
    assert out.env_meta["newborn_route_loss_active"] is True
    assert out.env_meta["newborn_force_keyframe"] is True
    assert out.env_meta["newborn_blackout_dropped_preds"] >= 4
    assert out.env_meta["newborn_blackout_dropped_cues"] >= 3
    assert out.env_meta["newborn_route_loss_dropped_nav_patches"] == 1
    assert out.env_meta["newborn_route_loss_dropped_surface_grid"] == 1

    # A route-loss milestone should schedule or extend the next blackout window.
    assert ctx.experiment_newborn_blackout_start_step <= 6
    assert ctx.experiment_newborn_blackout_until_step >= 12
    assert ctx.experiment_newborn_blackout_reason == "after_reached_mom"


def test_experiment_conditions_apply_memory_governance_modes_without_llm_calls() -> None:
    """A/B/C should map directly to merge, no-readback, and replace retrieval modes."""
    cfg = ExperimentProtocolConfig(obs_mask_prob=0.5, llm_model="gpt-test")
    ctx = Ctx()

    cond_a = experiment_apply_condition_runtime_v1(None, None, ctx, None, condition_id="A", cfg=cfg)
    assert cond_a["ok"] is True
    assert cond_a["retrieval_enabled"] is True
    assert cond_a["retrieval_mode"] == "merge"
    assert ctx.wm_mapsurface_autoretrieve_enabled is True
    assert ctx.wm_mapsurface_autoretrieve_mode == "merge"
    assert ctx.experiment_llm_adviser_enabled is False
    assert ctx.experiment_llm_call_count == 0

    cond_b = experiment_apply_condition_runtime_v1(None, None, ctx, None, condition_id="B", cfg=cfg)
    assert cond_b["ok"] is True
    assert cond_b["retrieval_enabled"] is False
    assert ctx.wm_mapsurface_autoretrieve_enabled is False
    assert ctx.experiment_llm_adviser_enabled is False
    assert ctx.experiment_llm_call_count == 0

    cond_c = experiment_apply_condition_runtime_v1(None, None, ctx, None, condition_id="C", cfg=cfg)
    assert cond_c["ok"] is True
    assert cond_c["retrieval_enabled"] is True
    assert cond_c["retrieval_mode"] == "replace"
    assert ctx.wm_mapsurface_autoretrieve_enabled is True
    assert ctx.wm_mapsurface_autoretrieve_mode == "replace"
    assert ctx.experiment_llm_adviser_enabled is False
    assert ctx.experiment_llm_call_count == 0

    # D is still deliberately not a runnable native CCA8 condition.
    cond_d = experiment_apply_condition_runtime_v1(None, None, ctx, None, condition_id="D", cfg=cfg)
    assert cond_d["ok"] is False
    assert cond_d["why"] == "condition_not_yet_supported"
    assert cond_d["agent_mode"] == "llm_only"


def test_protocol_normalization_keeps_route_loss_configuration_reproducible() -> None:
    """Invalid menu inputs should normalize to safe benchmark defaults."""
    raw = ExperimentProtocolConfig(
        benchmark_id="bad_benchmark",
        condition_ids=["C", "A", "C", "Z", "B"],
        seed_list=[101, "bad", 101, 202],  # type: ignore[list-item]
        episodes_per_seed=0,
        max_cycles=-10,
        obs_mask_prob=1.7,
        newborn_stress_profile="route_loss",
        newborn_blackout_length=3,
        llm_adviser_ambiguity_delta=99.0,
        llm_adviser_max_candidates=99,
        run_label="my run: route/loss",
        output_dir="",
    )

    cfg = experiment_normalize_protocol_v1(raw)

    assert cfg.benchmark_id == "newborn_long_horizon"
    assert cfg.condition_ids == ["C", "A", "B"]
    assert cfg.seed_list == [101, 202]
    assert cfg.episodes_per_seed == 1
    assert cfg.max_cycles == 1
    assert cfg.obs_mask_prob == 1.0
    assert cfg.newborn_stress_profile == "route_loss"
    # The raw stored value is clamped to [1, 20]; the effective route-loss
    # minimum is checked by the stress/runtime helpers, not by this field.
    assert cfg.newborn_blackout_length == 3
    assert cfg.llm_adviser_ambiguity_delta == 1.0
    assert cfg.llm_adviser_max_candidates == 8
    assert cfg.run_label == "my_run_route_loss"
    assert cfg.output_dir == "testvalues"


def test_lhsi_active_horizon_ignores_post_completion_behavior() -> None:
    """Actions after final rest should not inflate active-horizon LHSI metrics."""
    records = [
        _lhsi_record(
            env_step=0,
            stage="birth",
            posture="standing",
            mom="far",
            nipple="hidden",
            zone="unsafe",
            policy="policy:stand_up",
            predicates=["posture:standing"],
        ),
        _lhsi_record(
            env_step=1,
            stage="first_stand",
            posture="standing",
            mom="near",
            nipple="hidden",
            zone="neutral",
            policy="policy:follow_mom",
            predicates=["posture:standing", "proximity:mom:close"],
        ),
        _lhsi_record(
            env_step=2,
            stage="first_stand",
            posture="standing",
            mom="near",
            nipple="visible",
            zone="neutral",
            policy="policy:seek_nipple",
            predicates=["posture:standing", "proximity:mom:close", "nipple:found"],
        ),
        _lhsi_record(
            env_step=3,
            stage="first_latch",
            posture="latched",
            mom="near",
            nipple="latched",
            zone="safe",
            policy="policy:seek_nipple",
            predicates=["posture:standing", "proximity:mom:close", "nipple:found", "nipple:latched"],
        ),
        _lhsi_record(
            env_step=4,
            stage="first_latch",
            posture="latched",
            mom="near",
            nipple="latched",
            zone="safe",
            policy="policy:suckle",
            predicates=[
                "posture:standing",
                "proximity:mom:close",
                "nipple:found",
                "nipple:latched",
                "milk:drinking",
            ],
        ),
        _lhsi_record(
            env_step=5,
            stage="rest",
            posture="resting",
            mom="near",
            nipple="latched",
            zone="safe",
            policy="policy:rest",
            predicates=[
                "posture:standing",
                "proximity:mom:close",
                "nipple:found",
                "nipple:latched",
                "milk:drinking",
                "resting",
            ],
        ),
        # This would be a wrong-stage action, but it occurs after task completion.
        _lhsi_record(
            env_step=6,
            stage="rest",
            posture="resting",
            mom="near",
            nipple="latched",
            zone="safe",
            policy="policy:follow_mom",
            predicates=["resting"],
        ),
    ]

    summary = summarize_newborn_state_integrity_v1(records)

    assert summary["success"] is True
    assert summary["milestone_score"] == pytest.approx(1.0)
    assert summary["raw_cycle_count"] == 7
    assert summary["active_cycle_count"] == 6
    assert summary["active_horizon_applied"] is True
    assert summary["completion_cutoff_cycle_index"] == 5
    assert summary["completion_cutoff_env_step"] == 5
    assert summary["wrong_stage_action_count"] == 0
    assert summary["provenance_complete_cycle_rate"] == pytest.approx(1.0)


def test_lhsi_counts_replace_retrieval_overwrite_and_followup_prediction_error() -> None:
    """Replace-mode retrieval should be visible in LHSI proxy metrics."""
    records = [
        _lhsi_record(
            env_step=0,
            stage="birth",
            posture="fallen",
            mom="far",
            nipple="hidden",
            zone="unsafe",
            policy="policy:stand_up",
            predicates=["posture:fallen"],
        ),
        _lhsi_record(
            env_step=1,
            stage="first_stand",
            posture="standing",
            mom="far",
            nipple="hidden",
            zone="unsafe",
            policy="policy:stand_up",
            predicates=["posture:standing"],
            mapswitch_events=[
                {
                    "reason": "newborn_b2:test_retrieve",
                    "ok": True,
                    "load": {"mode": "replace", "entities": 2, "relations": 1},
                }
            ],
            pred_err={"posture": 1},
        ),
        _lhsi_record(
            env_step=2,
            stage="first_stand",
            posture="standing",
            mom="far",
            nipple="hidden",
            zone="unsafe",
            policy="policy:follow_mom",
            predicates=["posture:standing"],
            pred_err={"posture": 1},
        ),
    ]

    summary = summarize_newborn_state_integrity_v1(records, followup_window=1)

    assert summary["retrieval_event_count"] == 1
    assert summary["retrieval_ok_count"] == 1
    assert summary["retrieval_replace_count"] == 1
    assert summary["retrieval_non_noop_count"] == 1
    assert summary["current_state_overwrite_proxy_count"] == 1
    assert summary["retrieval_followup_basis_count"] == 1
    assert summary["stale_memory_intrusion_proxy_count"] >= 1
    assert summary["cumulative_prediction_error_lhsi"] == pytest.approx(2.0)
    assert summary["state_integrity_score"] < summary["milestone_score"]


def test_rcos_negative_controls_do_not_get_false_long_horizon_success() -> None:
    """Partial task progress must not be scored as strict RCOS task completion."""
    incomplete = rcos_robotic_run_episode_v1(
        controller_id="incomplete_no_return_control",
        seed=123,
        max_steps=80,
        write_jsonl=False,
    )
    rec = incomplete["episode_record"]

    assert incomplete["ok"] is True
    assert rec["target_inspected"] is True
    assert rec["returned_to_dock"] is False
    assert rec["success"] is False
    assert rec["expected_outcome_met"] is True
    assert rec["milestone_score"] < 1.0
    assert incomplete["cycle_json_path"] is None
    assert incomplete["episode_json_path"] is None

    hazard = rcos_robotic_run_episode_v1(
        controller_id="hazard_negative_control",
        seed=123,
        max_steps=80,
        write_jsonl=False,
    )
    hazard_rec = hazard["episode_record"]

    assert hazard["ok"] is True
    assert hazard_rec["success"] is False
    assert hazard_rec["expected_outcome_met"] is True
    assert hazard_rec["falls"] > 0
    assert hazard_rec["safety_violations"] > 0
