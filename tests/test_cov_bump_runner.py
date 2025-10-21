import types
import pytest

R = pytest.importorskip("cca8_run")
W = pytest.importorskip("cca8_world_graph")


def _quiet(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")


def test_drive_tags_fallback_without_predicates_method():
    dummy = types.SimpleNamespace(hunger=0.61, fatigue=0.71, warmth=0.25)
    tags = R._drive_tags(dummy)
    assert "drive:hunger_high" in tags
    assert "drive:fatigue_high" in tags
    assert "drive:cold" in tags


def test_bindings_with_pred_and_has_pred_near_now():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    # NOW -> A -> goal
    a = w.add_predicate("A", attach="now")
    goal = w.add_predicate("goal", attach="latest")
    assert R.has_pred_near_now(w, "goal", hops=3)


def test_world_delete_edge_alt_layouts_global_edges_only():
    # World stub with ONLY a global edge list (no _bindings)
    world = types.SimpleNamespace(
        edges=[
            {"src": "b1", "to": "b2", "label": "run"},
            {"src": "b1", "to": "b3", "label": "then"},
        ]
    )
    removed = R.world_delete_edge(world, "b1", "b2", "run")
    assert removed == 1
    # removing remaining to b3 with None (any label) should work too
    removed2 = R.world_delete_edge(world, "b1", "b3", None)
    assert removed2 == 1


def test_snapshot_text_contains_core_sections():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    ctx = R.Ctx()
    text = R.snapshot_text(w, drives=None, ctx=ctx, policy_rt=None)
    # Sanity: sections we expect in the snapshot
    assert "WorldGraph snapshot" in text and "BINDINGS:" in text and "EDGES:" in text
