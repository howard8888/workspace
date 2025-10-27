# tests/test_controller_rest.py
from cca8_world_graph import WorldGraph
from cca8_controller import Drives, action_center_step

def test_rest_fires_and_reduces_fatigue():
    g = WorldGraph()
    g.set_tag_policy("allow")
    now = g.ensure_anchor("NOW")

    d = Drives(hunger=0.2, fatigue=0.9, warmth=0.6)  # fatigue high
    res = action_center_step(g, ctx=None, drives=d)
    assert res["policy"] == "policy:rest"
    assert d.fatigue < 0.9  # reduced
    assert g.plan_to_predicate(now, "state:resting") is not None
