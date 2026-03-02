import cca8_world_graph
from cca8_env import EnvState, PerceptionAdapter
from cca8_run import Ctx, init_body_world, inject_obs_into_world


def test_surface_grid_and_map_surface_update():
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.working_enabled = False
    ctx.longterm_obs_enabled = False  # keep test output quiet

    world = cca8_world_graph.WorldGraph()
    world.ensure_anchor("NOW")

    st = EnvState()
    st.mom_distance = "near"
    st.shelter_distance = "far"
    st.cliff_distance = "near"
    st.position = "cliff_edge"
    st.zone = "unsafe"

    obs = PerceptionAdapter().observe(st, ctx=ctx)

    inject_obs_into_world(world, ctx, obs)

    assert isinstance(ctx.surface_grid, dict)
    assert ctx.surface_grid.get("affordances", {}).get("cliff_near") is True

    ms = ctx.map_surface_world
    assert ms is not None
    self_bid = ctx.map_surface_ids.get("SELF")
    assert self_bid in ms._bindings
    tags = ms._bindings[self_bid].tags
    assert "pred:hazard:near" in tags