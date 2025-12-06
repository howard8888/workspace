import cca8_world_graph
from cca8_run import Ctx, init_body_world, inject_obs_into_world, neighbors_near_self, resting_scenes_in_shelter
from cca8_env import EnvObservation


def _make_world_and_ctx():
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return world, ctx


def test_neighbors_near_self_and_resting_scene():
    world, ctx = _make_world_and_ctx()

    # Fake a "resting in shelter" observation
    obs = EnvObservation(
        raw_sensors={},
        predicates=[
            "resting",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
            "nipple:latched",
        ],
        cues=[],
        env_meta={},
    )

    inject_obs_into_world(world, ctx, obs)

    near_ids = neighbors_near_self(world)
    assert near_ids, "expected NOW to have near neighbors after resting scene"

    # At least one neighbor should be shelter-near
    shelter_ids = [
        bid for bid in near_ids
        if "pred:proximity:shelter:near" in getattr(world._bindings[bid], "tags", set())
    ]
    assert shelter_ids, "expected a shelter-near binding among neighbors_near_self"

    summary = resting_scenes_in_shelter(world)
    assert summary["rest_near_now"] is True
    assert summary["shelter_near_now"] is True
    assert summary["hazard_cliff_far_near_now"] is True
