import pytest

W = pytest.importorskip("cca8_world_graph", reason="cca8_world_graph module not found")
R = pytest.importorskip("cca8_run", reason="cca8_run module not found")


def _quiet(world):
    if hasattr(world, "set_tag_policy"):
        world.set_tag_policy("allow")


def test_parse_vector_mixed_separators_and_garbage():
    """
    _parse_vector should accept commas and spaces, ignore bad tokens,
    and default missing to [0,0,0].
    """
    assert R._parse_vector("") == [0.0, 0.0, 0.0]
    assert R._parse_vector("1, 2  3") == [1.0, 2.0, 3.0]
    # Ignore non-numeric junk gracefully
    assert R._parse_vector("  4.5, hmm,  6  ") == [4.5, 6.0]


def test_world_delete_edge_removes_per_binding_edges():
    """
    world_delete_edge() should remove exactly the matching (src->dst [rel]) edges
    from the per-binding adjacency list.
    """
    g = W.WorldGraph()
    _quiet(g)
    now = g.ensure_anchor("NOW")
    a = g.add_predicate("A", attach="now")
    b = g.add_predicate("B", attach="latest")

    # Sanity: NOW->A and A->B exist (label 'then')
    assert any(e.get("to") == a for e in g._bindings[now].edges)
    assert any(e.get("to") == b for e in g._bindings[a].edges)

    # Remove A->B only
    removed = R.world_delete_edge(g, a, b, "then")
    assert removed == 1
    assert not any(e.get("to") == b for e in g._bindings[a].edges)

    # Removing again does nothing
    removed_again = R.world_delete_edge(g, a, b, "then")
    assert removed_again == 0
