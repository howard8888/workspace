from __future__ import annotations

import cca8_env
import cca8_run
import cca8_world_graph
from cca8_controller import Drives


def test_goat_foraging_04_env_emits_context_switches_and_keyframe_hints() -> None:
    """The contextual evaluation scenario should alternate fox/hawk under stable coarse geometry.

    This is the key environment-side contract for the evaluation:
      - same coarse scene scaffold,
      - changing context labels/cues,
      - milestone + sparse-observation hints on context transitions.
    """
    env = cca8_env.HybridEnvironment(config=cca8_env.EnvConfig(scenario_name="goat_foraging_04"))

    obs0, info0 = env.reset()
    assert info0["scenario_name"] == "goat_foraging_04"
    assert env.state.scenario_stage == "goat_foraging_04_scan"
    assert env.state.position == "open_field"
    assert env.state.context_label == "fox"
    assert "terrain:forage_patch" in obs0.cues
    assert "vision:silhouette:fox" in obs0.cues

    saw_hawk = False
    saw_context_milestone = False
    labels = [env.state.context_label]

    for _ in range(10):
        obs, _reward, _done, _info = env.step(action=None, ctx=None)
        labels.append(env.state.context_label)

        if "vision:silhouette:hawk" in (obs.cues or []):
            saw_hawk = True

        milestones = obs.env_meta.get("milestones") if isinstance(obs.env_meta, dict) else None
        if isinstance(milestones, list) and milestones:
            saw_context_milestone = True
            assert any(m in ("context:fox", "context:hawk") for m in milestones)
            assert int(obs.env_meta.get("obs_mask_dropped_cues", 0) or 0) >= 1

        # Coarse geometry should remain intentionally simple.
        assert env.state.position == "open_field"
        assert env.state.shelter_distance == "far"
        assert env.state.cliff_distance == "far"

    assert "fox" in labels
    assert "hawk" in labels
    assert saw_hawk is True
    assert saw_context_milestone is True


def test_configure_goat_foraging_04_eval_v1_sets_runner_knobs() -> None:
    """The runner-side helper should enable the intended evaluation configuration."""
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    drives = Drives()
    ctx = cca8_run.Ctx()
    env = cca8_env.HybridEnvironment()

    cca8_run.configure_goat_foraging_04_eval_v1(world, drives, ctx, env)

    assert env.config.scenario_name == "goat_foraging_04"
    assert ctx.env_episode_started is False
    assert ctx.env_last_action is None

    assert ctx.phase7_working_first is True
    assert ctx.phase7_run_compress is True

    assert ctx.longterm_obs_keyframe_on_stage_change is False
    assert ctx.longterm_obs_keyframe_on_zone_change is False
    assert ctx.longterm_obs_keyframe_on_milestone is True

    assert ctx.wm_mapsurface_autoretrieve_enabled is True
    assert ctx.wm_mapsurface_autoretrieve_mode == "merge"
    assert ctx.wm_mapsurface_autoretrieve_top_k == 5

    assert drives.hunger == 0.30
    assert drives.fatigue == 0.20
    assert drives.warmth == 0.60