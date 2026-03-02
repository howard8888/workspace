import cca8_world_graph
from cca8_env import EnvObservation
from cca8_run import Ctx, init_body_world, inject_obs_into_world


def test_seqerr_updates_raw_delta_and_slot_stability():
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()

    # Keep the test small/quiet: we only care about seqerr side-effects.
    ctx.working_enabled = False
    ctx.longterm_obs_enabled = False

    ctx.seqerr_enabled = True
    ctx.seqerr_window = 4

    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    obs1 = EnvObservation(
        raw_sensors={"distance_to_mom": 2.0, "kid_temperature": 0.6},
        predicates=["posture:fallen", "proximity:mom:far"],
        cues=[],
        env_meta={"time_since_birth": 0.0, "scenario_stage": "birth"},
    )
    inject_obs_into_world(world, ctx, obs1)

    assert isinstance(ctx.seqerr_last, dict)
    assert ctx.seqerr_last.get("raw_delta", {}) == {}
    assert isinstance(ctx.seqerr_history, list)
    assert len(ctx.seqerr_history) == 1

    obs2 = EnvObservation(
        raw_sensors={"distance_to_mom": 1.5, "kid_temperature": 0.6},
        predicates=["posture:fallen", "proximity:mom:close"],
        cues=[],
        env_meta={"time_since_birth": 1.0, "scenario_stage": "birth"},
    )
    inject_obs_into_world(world, ctx, obs2)

    last = ctx.seqerr_last
    assert last.get("raw_delta", {}).get("distance_to_mom") == -0.5

    stab = last.get("slot_stability", {})
    assert stab.get("posture") == 2
    assert stab.get("proximity:mom") == 1

    changes = last.get("slot_changes", [])
    assert any(isinstance(c, dict) and c.get("slot") == "proximity:mom" for c in changes)