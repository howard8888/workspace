# tests/test_phase8_mask_and_pred_err.py
from __future__ import annotations

import cca8_run
import cca8_world_graph
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment


def _ctx_for_mask_only() -> cca8_run.Ctx:
    """Small ctx for masking tests: avoid WorkingMap and long-term writes to keep tests tiny."""
    ctx = cca8_run.Ctx()
    ctx.working_enabled = False
    ctx.longterm_obs_enabled = False
    ctx.obs_mask_verbose = False
    ctx.obs_mask_last_cfg_sig = None
    return ctx


def test_obs_mask_prob_zero_is_noop() -> None:
    ctx = _ctx_for_mask_only()
    ctx.obs_mask_prob = 0.0
    ctx.obs_mask_seed = 123

    obs = EnvObservation(
        predicates=["posture:fallen", "proximity:mom:far", "nipple:hidden", "hazard:cliff:far"],
        cues=["vision:silhouette:mom"],
        env_meta={"step_index": 7, "scenario_stage": "birth", "time_since_birth": 0.0},
    )
    preds0 = list(obs.predicates)
    cues0 = list(obs.cues)

    world = cca8_world_graph.WorldGraph()
    cca8_run.inject_obs_into_world(world, ctx, obs)

    assert obs.predicates == preds0
    assert obs.cues == cues0


def test_obs_mask_prob_one_drops_unprotected_but_keeps_protected() -> None:
    ctx = _ctx_for_mask_only()
    ctx.obs_mask_prob = 1.0
    ctx.obs_mask_seed = 7

    # Protected families in runner: posture:*, hazard:cliff:*, proximity:shelter:*.
    obs = EnvObservation(
        predicates=[
            "posture:fallen",              # protected
            "hazard:cliff:near",           # protected
            "proximity:shelter:far",       # protected
            "proximity:mom:far",           # unprotected (should drop at p=1.0)
            "nipple:hidden",               # unprotected (should drop at p=1.0)
        ],
        cues=["vision:silhouette:mom"],     # cues are droppable at p=1.0
        env_meta={"step_index": 3, "scenario_stage": "birth", "time_since_birth": 0.0},
    )

    world = cca8_world_graph.WorldGraph()
    cca8_run.inject_obs_into_world(world, ctx, obs)

    assert "posture:fallen" in obs.predicates
    assert "hazard:cliff:near" in obs.predicates
    assert "proximity:shelter:far" in obs.predicates
    assert "proximity:mom:far" not in obs.predicates
    assert "nipple:hidden" not in obs.predicates
    assert obs.cues == []


def test_obs_mask_seeded_is_reproducible_for_same_step_ref() -> None:
    ctx = _ctx_for_mask_only()
    ctx.obs_mask_prob = 0.35
    ctx.obs_mask_seed = 123

    def run_once() -> tuple[list[str], list[str]]:
        obs = EnvObservation(
            predicates=["posture:fallen", "proximity:mom:far", "nipple:hidden", "hazard:cliff:far"],
            cues=["vision:silhouette:mom", "scent:milk"],
            env_meta={"step_index": 11, "scenario_stage": "birth", "time_since_birth": 0.0},
        )
        world = cca8_world_graph.WorldGraph()
        cca8_run.inject_obs_into_world(world, ctx, obs)
        return (list(obs.predicates), list(obs.cues))

    p1, c1 = run_once()
    p2, c2 = run_once()
    assert p1 == p2
    assert c1 == c2


def test_pred_err_v0_match_on_reset() -> None:
    env = HybridEnvironment()
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    ctx = cca8_run.Ctx()
    ctx.working_enabled = False  # keep output small; avoids WM tables at end
    ctx.pred_next_posture = "fallen"
    ctx.pred_next_policy = "policy:test"

    policy_rt = cca8_run.PolicyRuntime(cca8_run.CATALOG_GATES)
    policy_rt.refresh_loaded(ctx)

    cca8_run.run_env_closed_loop_steps(env, world, Drives(), ctx, policy_rt, 1)

    assert ctx.pred_err_v0_last == {"posture": 0}


def test_pred_err_v0_mismatch_on_reset() -> None:
    env = HybridEnvironment()
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    ctx = cca8_run.Ctx()
    ctx.working_enabled = False
    ctx.pred_next_posture = "standing"
    ctx.pred_next_policy = "policy:test"

    policy_rt = cca8_run.PolicyRuntime(cca8_run.CATALOG_GATES)
    policy_rt.refresh_loaded(ctx)

    cca8_run.run_env_closed_loop_steps(env, world, Drives(), ctx, policy_rt, 1)

    assert ctx.pred_err_v0_last == {"posture": 1}
