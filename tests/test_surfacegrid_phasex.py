from __future__ import annotations

from types import SimpleNamespace

import pytest

import cca8_env
import cca8_run


def _make_surfacegrid_observation(*, focus: str | None = None) -> cca8_env.EnvObservation:
    """Build one deterministic observation rich enough to exercise the new SurfaceGrid/salience path.

    The state intentionally includes:
      - mom near,
      - shelter near,
      - cliff near,
      - nipple reachable,
      - a symbolic position in the shelter area.

    That gives the adapter enough structure to emit landmarks, affordances, and NavPatch tags in one shot.
    """
    state = cca8_env.EnvState(
        kid_posture="standing",
        mom_distance="near",
        shelter_distance="near",
        cliff_distance="near",
        nipple_state="reachable",
        scenario_stage="first_stand",
        position="shelter_area",
        kid_position=(1.6, 0.0),
        mom_position=(1.95, 0.0),
    )
    state.update_zone_from_position()

    adapter = cca8_env.PerceptionAdapter()
    if focus is None:
        return adapter.observe(state)
    return adapter.observe(state, ctx=SimpleNamespace(percept_focus=focus))


def test_fsm_reset_initializes_open_field_geometry() -> None:
    """The reset path should seed a neutral/open-field anchor with synchronized coarse coordinates.

    This protects the new bridge between symbolic position labels and the continuous-ish coordinates
    used later by SurfaceGrid, raw distance summaries, and salience overlays.
    """
    backend = cca8_env.FsmBackend()
    config = cca8_env.EnvConfig(scenario_name="newborn_goat_first_hour")
    state = cca8_env.EnvState()

    backend.reset(state, config)

    assert state.position == "open_field"
    assert state.zone == "neutral"
    assert state.kid_position == pytest.approx((0.8, 0.0))
    assert state.mom_position == pytest.approx((1.7, 0.0))
    assert state.cliff_distance == "far"
    assert state.shelter_distance == "far"


def test_fsm_follow_mom_moves_symbolic_and_numeric_geometry_together() -> None:
    """Following mom should move both the symbolic location and the coarse numeric anchor.

    The important regression here is that WorkingMap/SurfaceGrid should be able to see that SELF
    really moved when the storyboard says the goat moved from cliff edge -> open field -> shelter.
    """
    backend = cca8_env.FsmBackend()
    state = cca8_env.EnvState(
        scenario_stage="struggle",
        position="cliff_edge",
        zone="unsafe",
        mom_distance="near",
        shelter_distance="far",
        cliff_distance="near",
        kid_position=(0.0, 0.0),
        mom_position=(0.35, 0.0),
        step_index=6,
    )

    backend.step(state, "policy:follow_mom", ctx=None)
    assert state.position == "open_field"
    assert state.zone == "neutral"
    assert state.kid_position == pytest.approx((0.8, 0.0))
    assert state.mom_position == pytest.approx((1.15, 0.0))
    assert state.cliff_distance == "far"
    assert state.shelter_distance == "far"

    backend.step(state, "policy:follow_mom", ctx=None)
    assert state.position == "shelter_area"
    assert state.zone == "safe"
    assert state.kid_position == pytest.approx((1.6, 0.0))
    assert state.mom_position == pytest.approx((1.95, 0.0))
    assert state.cliff_distance == "far"
    assert state.shelter_distance == "near"


def test_perception_adapter_emits_surfacegrid_landmarks_focus_and_navpatch_tags() -> None:
    """The observation packet should now carry richer SurfaceGrid-facing metadata.

    This test covers three new seams together:
      1) focused raw channels (mom_dx/mom_dy),
      2) landmark/salience metadata on surface_grid/env_meta,
      3) richer NavPatch tags used later by the runner.
    """
    obs = _make_surfacegrid_observation(focus="mom")

    assert obs.raw_sensors["mom_dx"] == pytest.approx(0.35)
    assert obs.raw_sensors["mom_dy"] == pytest.approx(0.0)
    assert obs.env_meta["percept_focus"] == "mom"
    assert obs.env_meta["surface_anchor_xy"] == {"x": 1.6, "y": 0.0}
    assert obs.env_meta["surface_affordances"] == {
        "cliff_near": True,
        "shelter_near": True,
        "mom_near": True,
    }
    assert obs.env_meta["salience_candidates"] == ["mom", "cliff", "shelter", "nipple"]

    assert obs.surface_grid["attention"] == {"focus": "mom"}
    landmarks = {item["token"]: item for item in obs.surface_grid["landmarks"]}
    assert set(landmarks) == {"self", "mom", "cliff", "shelter", "nipple"}
    assert landmarks["mom"]["focused"] is True
    assert landmarks["self"]["kind"] == "ego_anchor"
    assert landmarks["cliff"]["kind"] == "hazard"
    assert landmarks["shelter"]["kind"] == "goal"
    assert landmarks["nipple"]["kind"] == "feeding"

    assert len(obs.nav_patches) == 1
    tags = set(obs.nav_patches[0]["tags"])
    assert {"hazard:cliff", "goal:shelter", "landmark:mom", "goal:nipple", "focus:mom"}.issubset(tags)


def test_working_surfacegrid_cache_and_snapshot_are_updated_from_observation() -> None:
    """WorkingMap injection should compose one SurfaceGrid, then reuse it on a cache hit.

    This locks in the current cache semantics and also checks that salience/snapshot output is
    populated enough for terminal inspection.
    """
    ctx = cca8_run.Ctx()
    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()

    obs = _make_surfacegrid_observation()

    cca8_run.update_body_world_from_obs(ctx, obs)
    first = cca8_run.inject_obs_into_working_world(ctx, obs)

    assert first["predicates"]
    assert ctx.wm_surfacegrid is not None
    assert isinstance(ctx.wm_surfacegrid_sig16, str) and len(ctx.wm_surfacegrid_sig16) == 16
    assert ctx.wm_surfacegrid_dirty_reasons == ["patches_changed", "grid_missing"]
    assert ctx.wm_surfacegrid_compose_ms > 0.0
    assert ctx.wm_salience_focus_entities == ["self", "cliff", "shelter", "mom"]
    assert isinstance(ctx.wm_surfacegrid_last_ascii, str)
    assert "@" in ctx.wm_surfacegrid_last_ascii

    cliff_bid = ctx.wm_entities["cliff"]
    cliff_binding = ctx.working_world._bindings[cliff_bid]
    assert cliff_binding.meta["wm"]["salience_ttl"] == ctx.wm_salience_promote_ttl

    cca8_run.update_body_world_from_obs(ctx, obs)
    cca8_run.inject_obs_into_working_world(ctx, obs)

    assert ctx.wm_surfacegrid_dirty_reasons == ["cache_hit"]
    assert ctx.wm_surfacegrid_compose_ms == pytest.approx(0.0)

    snapshot = cca8_run.format_surfacegrid_snapshot_v1(ctx)
    assert "[surfacegrid]" in snapshot
    assert "WM.SurfaceGrid" in snapshot
    assert "focus=self, cliff, shelter, mom" in snapshot