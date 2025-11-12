import cca8_world_graph as wg
from cca8_controller import Drives
from cca8_run import Ctx, PolicyRuntime, CATALOG_GATES, _hamming_hex64

def test_policy_runtime_standup_flow_and_hamming():
    w = wg.WorldGraph()
    w.ensure_anchor("NOW")
    w.add_predicate("stand", attach="now")   # gate for stand_up
    d = Drives()
    ctx = Ctx()

    rt = PolicyRuntime(CATALOG_GATES)
    rt.refresh_loaded(ctx)
    out = rt.consider_and_maybe_fire(w, d, ctx)
    assert out.startswith("policy:stand_up")
    # small runner util sanity
    assert _hamming_hex64("00ff", "0f0f") == 8
