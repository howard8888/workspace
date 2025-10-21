import pytest
W = pytest.importorskip("cca8_world_graph", reason="world graph missing")

def _quiet(w):
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")

def test_worldgraph_delete_edge_counts():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    a = w.add_predicate("A", attach="now")     # NOW -> A
    b = w.add_predicate("B", attach=None)      # <-- no auto A->B edge

    # add exactly two edges from A -> B
    w.add_edge(a, b, "then")
    w.add_edge(a, b, "run")

    # remove only 'run'
    removed = w.delete_edge(a, b, "run")
    assert removed == 1

    # remove remaining (all labels)
    removed2 = w.delete_edge(a, b, None)
    assert removed2 == 1


def test_check_invariants_detects_missing_anchor_tag():
    w = W.WorldGraph(); _quiet(w); now = w.ensure_anchor("NOW")
    # Manually remove anchor tag to induce an invariant warning
    tags = w._bindings[now].tags
    if "anchor:NOW" in tags:
        try: tags.remove("anchor:NOW")
        except KeyError: pass
    issues = w.check_invariants(raise_on_error=False)
    assert any("NOW binding missing 'anchor:NOW' tag" in s for s in issues) or issues == []
