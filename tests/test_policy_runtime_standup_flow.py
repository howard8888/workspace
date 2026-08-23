import cca8_world_graph as wg
from cca8_controller import Drives
from cca8_run import CATALOG_GATES, Ctx, PolicyRuntime

def test_policy_runtime_standup_flow() -> None:
    w = wg.WorldGraph()
    w.ensure_anchor("NOW")
    w.add_predicate("stand", attach="now")   # gate for stand_up
    d = Drives()
    ctx = Ctx()

    rt = PolicyRuntime(CATALOG_GATES)
    rt.refresh_loaded(ctx)
    out = rt.consider_and_maybe_fire(w, d, ctx)
    assert out.startswith("policy:stand_up")
