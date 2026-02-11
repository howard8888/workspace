import cca8_world_graph
from cca8_run import Ctx, apply_hardwired_profile_phase7


def test_phase7_profile_respects_keyframe_triggers():
    world = cca8_world_graph.WorldGraph()
    ctx = Ctx()

    # User experiment settings (should be preserved)
    ctx.longterm_obs_keyframe_on_stage_change = False
    ctx.longterm_obs_keyframe_on_zone_change = False
    ctx.longterm_obs_keyframe_period_steps = 10
    ctx.longterm_obs_keyframe_on_milestone = True
    ctx.longterm_obs_keyframe_on_pred_err = True

    apply_hardwired_profile_phase7(ctx, world)

    assert ctx.longterm_obs_keyframe_on_stage_change is False
    assert ctx.longterm_obs_keyframe_on_zone_change is False
    assert ctx.longterm_obs_keyframe_period_steps == 10
    assert ctx.longterm_obs_keyframe_on_milestone is True
    assert ctx.longterm_obs_keyframe_on_pred_err is True

    # Sanity: Phase VII profile still enables longterm obs pipeline
    assert ctx.longterm_obs_enabled is True
    assert ctx.longterm_obs_mode == "changes"
