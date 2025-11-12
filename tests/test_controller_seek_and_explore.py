import cca8_world_graph as wg
from cca8_controller import Drives, SeekNipple, ExploreCheck

def test_seeknipple_trigger_and_execute():
    w = wg.WorldGraph()
    w.ensure_anchor("NOW")
    # upright & hungry → eligible
    w.add_predicate("posture:standing", attach="now")
    d = Drives(hunger=0.8, fatigue=0.1, warmth=0.6)

    p = SeekNipple()
    assert p.trigger(w, d) is True
    res = p.execute(w, ctx=type("C", (), {"ticks":0, "tvec64":lambda self: None})(), drives=d)
    assert res["status"] == "ok"
    # canonical seeking-mom fact present
    assert any("pred:state:seeking_mom" in (b.tags or set()) for b in w._bindings.values())

def test_explorecheck_is_noop_success():
    w = wg.WorldGraph(); w.ensure_anchor("NOW")
    d = Drives()
    p = ExploreCheck()
    assert p.trigger(w, d) is False
    before = len(w._bindings)
    res = p.execute(w, ctx=None, drives=d)
    assert res["status"] == "ok" and res["notes"] == "checked"
    assert len(w._bindings) == before
