import pytest

W = pytest.importorskip("cca8_world_graph", reason="world graph not found")


def _quiet(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")


def test_plan_to_predicate_no_path_returns_none():
    w = W.WorldGraph(); _quiet(w)
    start = w.ensure_anchor("NOW")
    # no 'goal' anywhere
    assert w.plan_to_predicate(start, "goal") is None


def test_check_invariants_raises_on_broken_anchor():
    w = W.WorldGraph(); _quiet(w)
    w.ensure_anchor("NOW")
    # break invariant: NOW points to unknown id
    w._anchors["NOW"] = "b9999"
    with pytest.raises(AssertionError):
        w.check_invariants(raise_on_error=True)


def test_delete_edge_raises_keyerror_for_unknown_src():
    w = W.WorldGraph(); _quiet(w)
    w.ensure_anchor("NOW")
    with pytest.raises(KeyError):
        w.delete_edge("b9999", "b1", "then")


def test_dijkstra_uses_distance_and_duration_fallbacks():
    w = W.WorldGraph(); _quiet(w)
    start = w.ensure_anchor("NOW")
    goal = w.add_predicate("goal", attach=None)
    # two alternatives start->X->goal with different meta fallbacks
    d = w.add_predicate("D", attach=None)  # meta uses 'distance'
    e = w.add_predicate("E", attach=None)  # meta uses 'duration_s'
    w.add_edge(start, d, "then", meta={"distance": 4})
    w.add_edge(d, goal, "then")
    w.add_edge(start, e, "then", meta={"duration_s": 2})
    w.add_edge(e, goal, "then")
    if not hasattr(w, "set_planner"):
        pytest.skip("Dijkstra not integrated")
    w.set_planner("dijkstra")
    path = w.plan_to_predicate(start, "goal")
    assert path is not None and path[1] == e  # prefers lower total via duration_s=2
