import re
import cca8_world_graph as wg
from cca8_run import snapshot_text, Ctx
from cca8_temporal import TemporalContext

def _ctx() -> Ctx:
    c = Ctx()
    c.temporal = TemporalContext(dim=16, sigma=0.01, jump=0.2)
    c.tvec_last_boundary = c.temporal.vector()
    return c

def test_snapshot_shows_legend_temporal_and_short_engram_id():
    world = wg.WorldGraph()
    world.ensure_anchor("NOW")
    ctx = _ctx()

    # Create an engram via the engine bridge (not interactive menu)
    bid, eid = world.capture_scene("vision", "silhouette:mom", [0.1, 0.2, 0.3], attach="now", family="cue")
    txt = snapshot_text(world, drives=None, ctx=ctx, policy_rt=None)

    # Legend present
    assert "LEGEND (temporal terms):" in txt

    # TEMPORAL keys (regex-tolerant to your friendlier wording)
    assert re.search(r"cos[_ ]?to[_ ]?last[_ ]?boundary", txt)
    assert "last_boundary_vhash64" in txt or "context vector vhash64" in txt

    # BINDINGS line should include short id form: engrams=[column01:xxxxxxxx…]
    # use only the slot name; the shortid is optional if printed
    assert re.search(r"\bb\d+:\s*\[.*\]\s*engrams=\[(?:column01(?::[0-9a-f]{8}…)?)]", txt)

    # "Policies eligible" header present (not execution list)
    assert "POLICIES ELIGIBLE" in txt
