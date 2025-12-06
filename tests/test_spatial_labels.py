import cca8_world_graph
from cca8_env import EnvObservation
from cca8_run import Ctx, init_body_world, inject_obs_into_world, _anchor_id


def test_spatial_near_edges_written_when_resting():
    """
    When an EnvObservation includes:
      • resting
      • proximity:shelter:near
    the runner should write a 'near' edge from NOW to the shelter binding.
    """
    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()

    obs = EnvObservation(
        raw_sensors={},
        predicates=["resting", "proximity:shelter:near", "proximity:mom:close"],
        cues=[],
        env_meta={},
    )

    inject_obs_into_world(world, ctx, obs)

    now_id = _anchor_id(world, "NOW")
    assert now_id in world._bindings

    b_now = world._bindings[now_id]
    edges_raw = (
        getattr(b_now, "edges", []) or
        getattr(b_now, "out", []) or
        getattr(b_now, "links", []) or
        getattr(b_now, "outgoing", [])
    )

    near_targets = {
        (e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id"))
        for e in edges_raw
        if isinstance(e, dict) and e.get("label") == "near"
    }

    assert near_targets, "expected at least one 'near' spatial edge from NOW"

    # There should be at least one 'near' edge to a binding tagged pred:proximity:shelter:near
    shelter_bids = [
        bid for bid in near_targets
        if isinstance(bid, str)
        and "pred:proximity:shelter:near" in getattr(world._bindings[bid], "tags", set())
    ]
    assert shelter_bids, "expected NOW --near--> binding tagged pred:proximity:shelter:near"
