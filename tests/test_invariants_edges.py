import pytest
W = pytest.importorskip("cca8_world_graph", reason="world_graph not found")

def _q(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")

def test_add_edge_rejects_unknown_ids_and_self_loops():
    g = W.WorldGraph(); _q(g)
    a = g.ensure_anchor("NOW")
    b = g.add_predicate("A", attach=None)

    # unknown ids
    with pytest.raises(KeyError):
        g.add_edge(a, "b9999", "then")
    with pytest.raises(KeyError):
        g.add_edge("b9998", b, "then")

    # self-loop default rejection
    with pytest.raises(ValueError):
        g.add_edge(b, b, "then")

    # explicit self-loop allowed
    g.add_edge(b, b, "then", allow_self_loop=True)

def test_check_invariants_ok_on_fresh_world():
    g = W.WorldGraph(); _q(g)
    now = g.ensure_anchor("NOW")
    # NOW anchor must have the tag
    assert "anchor:NOW" in g._bindings[now].tags
    # no issues in a brand-new world
    assert g.check_invariants(raise_on_error=False) == []
