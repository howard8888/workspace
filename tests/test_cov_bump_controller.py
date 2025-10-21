import pytest

C = pytest.importorskip("cca8_controller")
W = pytest.importorskip("cca8_world_graph")


def _quiet(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")


def test_rest_trigger_and_execute_reduces_fatigue():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    d = C.Drives(hunger=0.2, fatigue=0.9, warmth=0.6)
    p = C.Rest()
    assert p.trigger(w, d) is True
    fatigue_before = d.fatigue
    res = p.execute(w, ctx=None, drives=d)
    assert res["status"] == "ok" and d.fatigue < fatigue_before


def test_tag_helpers_any_tag_has_any_cue_present():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    b_pred = w.add_predicate("state:alert", attach="now")
    b_cue = w.add_cue("vision:silhouette:mom", attach="now")

    assert C._any_tag(w, "pred:state:alert") is True   # internal helper
    assert C._has(w, "state:alert") is True
    assert C._any_cue_present(w) is True
