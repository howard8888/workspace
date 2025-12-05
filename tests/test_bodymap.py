import cca8_world_graph
from cca8_run import Ctx, init_body_world, update_body_world_from_obs, _gate_seek_nipple_trigger_body_first
from cca8_env import EnvObservation
from cca8_controller import (
    Drives,
    HUNGER_HIGH,
    body_posture,
    body_mom_distance,
    body_nipple_state,
    bodymap_is_stale,
)


def _make_ctx_with_bodymap() -> Ctx:
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.controller_steps = 0
    return ctx


def test_bodymap_from_env_observation_posture():
    """
    EnvObservation -> BodyMap:
      posture:standing, proximity:mom:close, nipple:latched, milk:drinking
      should map to:
        body_posture == 'standing'
        body_mom_distance == 'near'
        body_nipple_state == 'latched'
      and record a fresh bodymap_last_update_step.
    """
    ctx = _make_ctx_with_bodymap()
    obs = EnvObservation(
        raw_sensors={},
        predicates=[
            "posture:standing",
            "proximity:mom:close",
            "nipple:latched",
            "milk:drinking",
        ],
        cues=[],
        env_meta={},
    )

    # Pretend we are at controller step 5 when this observation arrives.
    ctx.controller_steps = 5
    update_body_world_from_obs(ctx, obs)

    assert body_posture(ctx) == "standing"
    assert body_mom_distance(ctx) == "near"
    assert body_nipple_state(ctx) == "latched"

    # BodyMap should be marked as updated at the current controller_step.
    assert ctx.bodymap_last_update_step == ctx.controller_steps

    # Immediately after an update, BodyMap should not be stale.
    assert bodymap_is_stale(ctx, max_steps=10) is False

    # After many controller steps with no further updates, it should be stale.
    ctx.controller_steps += 11
    assert bodymap_is_stale(ctx, max_steps=10) is True


def test_seek_nipple_gate_uses_bodymap():
    """
    If BodyMap says:
      posture == 'standing' and nipple == 'latched'
    then the SeekNipple gate should return False even when hunger is high.

    When we later change BodyMap nipple state to 'hidden' *and* mom is near,
    the gate should be free to consider seeking (and in this simple setup we
    expect it to return True).
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    drives = Drives()
    drives.hunger = float(HUNGER_HIGH) + 0.1  # definitely "hungry"

    ctx = _make_ctx_with_bodymap()

    # Directly set BodyMap slots:
    bw = ctx.body_world
    posture_bid = ctx.body_ids["posture"]
    mom_bid = ctx.body_ids["mom"]
    nipple_bid = ctx.body_ids["nipple"]

    # Posture: standing
    bw._bindings[posture_bid].tags = {"pred:posture:standing"}  # pylint: disable=protected-access

    # Mom: near (so distance does not block SeekNipple in this test)
    bw._bindings[mom_bid].tags = {"pred:proximity:mom:close"}  # pylint: disable=protected-access

    # Nipple: latched + drinking
    bw._bindings[nipple_bid].tags = {"pred:nipple:latched", "pred:milk:drinking"}  # pylint: disable=protected-access

    # Mark BodyMap as freshly updated at the current controller_step.
    ctx.bodymap_last_update_step = ctx.controller_steps

    # Gate should refuse to seek because BodyMap says we are already latched.
    assert _gate_seek_nipple_trigger_body_first(world, drives, ctx) is False

    # If we change BodyMap nipple state to 'hidden', the gate should be free
    # to consider seeking; in this simple setup (standing, mom near, hungry),
    # we expect it to return True.
    bw._bindings[nipple_bid].tags = {"pred:nipple:hidden"}  # pylint: disable=protected-access
    ctx.bodymap_last_update_step = ctx.controller_steps
    assert _gate_seek_nipple_trigger_body_first(world, drives, ctx) is True


def test_bodymap_has_shelter_and_cliff_slots():
    """
    BodyMap init should create shelter and cliff slots and register their
    binding ids in ctx.body_ids. The bindings should exist in body_world.
    We do not assert on the exact tags here, only that the structure is wired.
    """
    ctx = _make_ctx_with_bodymap()
    bw = ctx.body_world
    body_ids = ctx.body_ids

    # Keys must be present in body_ids
    assert "shelter" in body_ids
    assert "cliff" in body_ids

    for slot in ("shelter", "cliff"):
        bid = body_ids[slot]
        # Must be a string id and present in the BodyMap WorldGraph
        assert isinstance(bid, str)
        assert bw is not None
        assert bid in bw._bindings  # binding exists

        # Binding must have a tags attribute (may be empty or pre-populated)
        b = bw._bindings[bid]
        assert hasattr(b, "tags")