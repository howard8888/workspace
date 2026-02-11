import io
from contextlib import redirect_stdout

import cca8_run
import cca8_world_graph
from cca8_controller import Drives
from cca8_env import HybridEnvironment
from cca8_temporal import TemporalContext


def test_phase7_autostore_respects_stage_zone_keyframe_flags() -> None:
    # Arrange: minimal Phase VII world + ctx
    world = cca8_world_graph.WorldGraph()
    world.set_tag_policy("allow")
    world.set_stage("neonate")
    world.ensure_anchor("NOW")

    ctx = cca8_run.Ctx()

    # TemporalContext is expected by the closed-loop runner.
    if ctx.temporal is None:
        ctx.temporal = TemporalContext(dim=16, sigma=ctx.sigma, jump=ctx.jump)
        ctx.tvec_last_boundary = ctx.temporal.vector()
        try:
            ctx.boundary_vhash64 = ctx.tvec64()
        except Exception:
            ctx.boundary_vhash64 = None

    ctx.body_world, ctx.body_ids = cca8_run.init_body_world()
    ctx.working_world = cca8_run.init_working_world()

    # Enable Phase VII "daily driver" settings (auto-store machinery is active).
    cca8_run.apply_hardwired_profile_phase7(ctx, world)

    # Critical: disable stage/zone boundary storage.
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False

    # Keep this test narrow: disable other keyframe triggers (env_reset keyframe is fine).
    ctx.longterm_obs_keyframe_period_steps = 0
    ctx.longterm_obs_keyframe_on_pred_err = False
    ctx.longterm_obs_keyframe_on_milestone = False
    ctx.longterm_obs_keyframe_on_emotion = False

    policy_rt = cca8_run.PolicyRuntime(cca8_run.CATALOG_GATES)
    policy_rt.refresh_loaded(ctx)

    env = HybridEnvironment()
    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)

    # Act
    buf = io.StringIO()
    with redirect_stdout(buf):
        cca8_run.run_env_closed_loop_steps(env, world, drives, ctx, policy_rt, n_steps=6)
    out = buf.getvalue()

    # Assert: confirm we actually left the birth stage (otherwise the test is meaningless)
    assert getattr(env.state, "scenario_stage", None) != "birth"

    # Assert: stage/zone transitions must NOT force auto-boundary WM↔Column store when disabled
    assert "auto_boundary_stage:" not in out
    assert "auto_boundary_zone:" not in out
