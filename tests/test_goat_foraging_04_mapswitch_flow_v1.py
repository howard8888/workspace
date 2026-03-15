from __future__ import annotations

import cca8_env
import cca8_run
import cca8_world_graph
from cca8_column import mem as column_mem


def _cleanup_new_column_records(before_ids: set[str]) -> None:
    """Delete any new Column records created during this test."""
    try:
        after_ids = set(column_mem.list_ids())
    except Exception:
        return

    for eid in (after_ids - before_ids):
        try:
            column_mem.delete(eid)
        except Exception:
            pass


def _advance_until_context_milestone(env: cca8_env.HybridEnvironment, target: str, *, max_steps: int = 20):
    """Advance the environment until a specific context milestone appears."""
    for _ in range(max_steps):
        obs, _reward, _done, _info = env.step(action=None, ctx=None)
        meta = obs.env_meta if isinstance(obs.env_meta, dict) else {}
        ms = meta.get("milestones")
        if isinstance(ms, list) and f"context:{target}" in ms:
            return obs
    raise AssertionError(f"Did not reach context:{target} milestone within {max_steps} steps")


def test_goat04_context_mapswitch_stores_two_seeds_then_retrieves() -> None:
    """goat_foraging_04 should store fox/hawk seeds first, then attempt retrieve/apply later."""
    before_ids = set(column_mem.list_ids())

    try:
        world = cca8_world_graph.WorldGraph()
        world.set_tag_policy("allow")
        world.ensure_anchor("NOW")

        ctx = cca8_run.Ctx()
        ctx.body_world, ctx.body_ids = cca8_run.init_body_world()
        ctx.working_world = cca8_run.init_working_world()
        ctx.working_enabled = True
        ctx.working_mapsurface = True
        ctx.wm_mapsurface_autoretrieve_enabled = True
        ctx.wm_mapsurface_autoretrieve_mode = "merge"
        ctx.wm_mapsurface_autoretrieve_top_k = 5
        ctx.wm_mapsurface_autoretrieve_verbose = False

        env = cca8_env.HybridEnvironment(config=cca8_env.EnvConfig(scenario_name="goat_foraging_04"))
        obs0, _info0 = env.reset()

        # Initial reset observation: no context milestone yet.
        cca8_run.inject_obs_into_working_world(ctx, obs0)
        cca8_run.update_body_world_from_obs(ctx, obs0)
        inj0 = cca8_run.inject_obs_into_world(world, ctx, obs0)
        assert inj0["keyframe"] is True  # initial keyframe exists, but helper should ignore it
        out0 = cca8_run.maybe_goat04_context_mapswitch_on_keyframe_v1(world, ctx, obs0)
        assert out0["handled"] is False

        # First hawk milestone -> STORE hawk seed only
        obs_hawk_1 = _advance_until_context_milestone(env, "hawk")
        cca8_run.inject_obs_into_working_world(ctx, obs_hawk_1)
        cca8_run.update_body_world_from_obs(ctx, obs_hawk_1)
        cca8_run.inject_obs_into_world(world, ctx, obs_hawk_1)

        out_hawk_1 = cca8_run.maybe_goat04_context_mapswitch_on_keyframe_v1(world, ctx, obs_hawk_1)
        assert out_hawk_1["handled"] is True
        assert isinstance(out_hawk_1["store"], str) and "goat04:hawk" in out_hawk_1["store"]
        assert out_hawk_1["retrieve"] is None
        assert out_hawk_1["apply"] is None
        assert "hawk" in ctx.wm_goat04_seeded_contexts
        assert "hawk" in ctx.wm_goat04_seed_engram_by_context

        # First fox milestone -> STORE fox seed only
        obs_fox_1 = _advance_until_context_milestone(env, "fox")
        cca8_run.inject_obs_into_working_world(ctx, obs_fox_1)
        cca8_run.update_body_world_from_obs(ctx, obs_fox_1)
        cca8_run.inject_obs_into_world(world, ctx, obs_fox_1)

        out_fox_1 = cca8_run.maybe_goat04_context_mapswitch_on_keyframe_v1(world, ctx, obs_fox_1)
        assert out_fox_1["handled"] is True
        assert isinstance(out_fox_1["store"], str) and "goat04:fox" in out_fox_1["store"]
        assert out_fox_1["retrieve"] is None
        assert out_fox_1["apply"] is None
        assert "fox" in ctx.wm_goat04_seeded_contexts
        assert "fox" in ctx.wm_goat04_seed_engram_by_context

        # Later hawk milestone -> RETRIEVE/APPLY
        obs_hawk_2 = _advance_until_context_milestone(env, "hawk")
        cca8_run.inject_obs_into_working_world(ctx, obs_hawk_2)
        cca8_run.update_body_world_from_obs(ctx, obs_hawk_2)
        cca8_run.inject_obs_into_world(world, ctx, obs_hawk_2)

        out_hawk_2 = cca8_run.maybe_goat04_context_mapswitch_on_keyframe_v1(world, ctx, obs_hawk_2)
        assert out_hawk_2["handled"] is True
        assert out_hawk_2["store"] is None
        assert isinstance(out_hawk_2["retrieve"], str)
        assert isinstance(out_hawk_2["apply"], str)

        events = getattr(ctx, "wm_mapswitch_last_events", [])
        assert isinstance(events, list) and events
        ev0 = events[-1]
        assert ev0["schema"] == "wm_mapswitch_event_v1"
        assert ev0["reason"] == "goat04_context:hawk"
        assert ev0["candidate_count"] >= 2
        assert ev0["load"]
    finally:
        _cleanup_new_column_records(before_ids)
