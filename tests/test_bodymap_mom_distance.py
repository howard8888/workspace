import cca8_world_graph
from cca8_run import Ctx, init_body_world, _gate_seek_nipple_trigger_body_first
from cca8_controller import Drives, HUNGER_HIGH


def _make_ctx_with_bodymap() -> Ctx:
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.controller_steps = 0
    ctx.bodymap_last_update_step = 0
    return ctx


def test_seek_nipple_gate_uses_bodymap_mom_distance():
    """
    When BodyMap says mom is 'far', SeekNipple dev gate should refuse to fire
    even if hunger and posture conditions are met. When BodyMap says 'near',
    it should allow firing (assuming no other blockers).
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    drives = Drives()
    drives.hunger = float(HUNGER_HIGH) + 0.1  # hungry enough

    ctx = _make_ctx_with_bodymap()
    bw = ctx.body_world
    posture_bid = ctx.body_ids["posture"]
    mom_bid = ctx.body_ids["mom"]
    nipple_bid = ctx.body_ids["nipple"]

    # BodyMap: standing, nipple hidden
    bw._bindings[posture_bid].tags = {"pred:posture:standing"}   # pylint: disable=protected-access
    bw._bindings[nipple_bid].tags = {"pred:nipple:hidden"}       # pylint: disable=protected-access

    # 1) Mom far → gate should be False
    bw._bindings[mom_bid].tags = {"pred:proximity:mom:far"}      # pylint: disable=protected-access
    assert _gate_seek_nipple_trigger_body_first(world, drives, ctx) is False

    # 2) Mom near → gate should be True
    bw._bindings[mom_bid].tags = {"pred:proximity:mom:close"}    # pylint: disable=protected-access
    assert _gate_seek_nipple_trigger_body_first(world, drives, ctx) is True
