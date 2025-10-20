import pytest

W = pytest.importorskip("cca8_world_graph", reason="cca8_world_graph module not found")


def _quiet(world):
    """Silence lexicon warnings for test-only tokens."""
    if hasattr(world, "set_tag_policy"):
        world.set_tag_policy("allow")


def test_ensure_anchor_is_idempotent():
    """Calling ensure_anchor('NOW') twice returns the same binding id."""
    g = W.WorldGraph()
    _quiet(g)
    a1 = g.ensure_anchor("NOW")
    a2 = g.ensure_anchor("NOW")
    assert a1 == a2
    # Anchor shows up in anchors map
    assert g._anchors.get("NOW") == a1


def test_add_predicate_attach_now_autolinks_from_NOW():
    """attach='now' should create an edge NOW -> new_predicate."""
    g = W.WorldGraph()
    _quiet(g)
    now = g.ensure_anchor("NOW")
    p = g.add_predicate("posture:standing", attach="now")
    # Find edge NOW -> p
    eids = [e.get("to") for e in g._bindings[now].edges]
    assert p in eids
    assert "pred:posture:standing" in g._bindings[p].tags


def test_add_predicate_attach_latest_links_from_previous_latest():
    """
    attach='latest' should link <previous latest> -> new.

    Sequence:
      NOW -> A (attach=now)
      A   -> B (attach=latest)
    """
    g = W.WorldGraph()
    _quiet(g)
    now = g.ensure_anchor("NOW")
    a = g.add_predicate("action:push_up", attach="now")
    b = g.add_predicate("action:extend_legs", attach="latest")
    outs = [e.get("to") for e in g._bindings[a].edges]
    assert b in outs
    # Confirm NOW only links to first node
    now_outs = [e.get("to") for e in g._bindings[now].edges]
    assert a in now_outs and b not in now_outs


def test_tag_policy_strict_raises_on_unknown_predicate():
    """Out-of-lexicon tokens should raise under 'strict' policy."""
    g = W.WorldGraph()
    g.set_tag_policy("strict")
    g.ensure_anchor("NOW")
    with pytest.raises(ValueError):
        g.add_predicate("totally:unknown:token", attach="now")


def test_plan_to_predicate_bfs_and_pretty_path():
    """
    Build NOW -> A -> B -> goal and ensure BFS finds goal.
    Also assert pretty_path contains anchors/preds.
    """
    g = W.WorldGraph()
    _quiet(g)
    start = g.ensure_anchor("NOW")
    a = g.add_predicate("A", attach="now")
    b = g.add_predicate("B", attach="latest")
    goal = g.add_predicate("goal", attach="latest")

    path = g.plan_to_predicate(start, "goal")
    assert path is not None and path[0] == start and path[-1] == goal
    pretty = g.plan_pretty(start, "goal")
    # Examples look like: b1(NOW) --then--> b3[A] --then--> b4[B] --then--> b5[goal]
    assert "NOW" in pretty and "goal" in pretty and "--then-->" in pretty
