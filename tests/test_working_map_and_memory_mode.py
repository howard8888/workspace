import cca8_world_graph as W
import cca8_run as runmod
from cca8_env import EnvObservation


def _allow_tags(world: W.WorldGraph) -> None:
    if hasattr(world, "set_tag_policy"):
        world.set_tag_policy("allow")


def test_worldgraph_memory_mode_episodic_creates_new_bindings_for_same_predicate():
    w = W.WorldGraph(memory_mode="episodic")
    _allow_tags(w)

    a = w.add_predicate("posture:standing", attach="now")
    b = w.add_predicate("posture:standing", attach="latest")

    assert a != b


def test_worldgraph_memory_mode_semantic_reuses_identical_predicate():
    w = W.WorldGraph(memory_mode="semantic")
    _allow_tags(w)

    a = w.add_predicate("posture:standing", attach="now")
    b = w.add_predicate("posture:standing", attach="latest")

    assert a == b


def test_inject_obs_into_working_world_creates_ctx_working_world_and_writes_tags():
    ctx = runmod.Ctx()
    ctx.working_world = None
    ctx.working_enabled = True

    obs = EnvObservation(
        predicates=["pred:posture:standing", "pred:proximity:mom:far"],
        cues=["cue:vision:silhouette:mom"],
        env_meta={},
    )

    out = runmod.inject_obs_into_working_world(ctx, obs)
    assert ctx.working_world is not None
    assert out["predicates"]
    assert any("pred:posture:standing" in b.tags for b in ctx.working_world._bindings.values())  # pylint: disable=protected-access


def test_inject_obs_into_world_mirrors_to_working_map_when_enabled():
    ctx = runmod.Ctx()
    ctx.working_world = None
    ctx.working_enabled = True

    world = W.WorldGraph()
    _allow_tags(world)

    obs = EnvObservation(
        predicates=["pred:posture:fallen"],
        cues=[],
        env_meta={},
    )

    runmod.inject_obs_into_world(world, ctx, obs)
    assert ctx.working_world is not None
    assert any("pred:posture:fallen" in b.tags for b in ctx.working_world._bindings.values())  # pylint: disable=protected-access
