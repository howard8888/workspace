import pytest

W = pytest.importorskip("cca8_world_graph", reason="world_graph not found")


def _quiet(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")


def test_actions_counts_metrics_and_list_actions_variants():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    a = w.add_predicate("A", attach="now")     # NOW -> A (then)
    b = w.add_predicate("B", attach="latest")  # A   -> B (then)
    w.add_edge(a, b, "run", meta={"meters": 5.0, "duration_s": 2.0})

    # list_actions includes 'then' by default, can hide it
    labs_all = w.list_actions(include_then=True)
    labs_no_then = w.list_actions(include_then=False)
    assert "run" in labs_all
    assert "then" in labs_all and "then" not in labs_no_then

    # counts and numeric metrics aggregation
    counts = w.action_counts(include_then=True)
    assert counts.get("run") == 1 and counts.get("then", 0) >= 2
    met = w.action_metrics("run")
    assert met["count"] == 1 and met["keys"]["meters"]["avg"] == 5.0


def test_pretty_path_modes_and_anchor_annotations():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    goal = w.add_predicate("goal", attach="now")  # NOW -> goal

    path = [now, goal]
    # id mode
    s_id = w.pretty_path(path, node_mode="id", show_edge_labels=True, annotate_anchors=True)
    assert "b" in s_id and "(NOW)" in s_id
    # pred mode
    s_pred = w.pretty_path(path, node_mode="pred", show_edge_labels=False, annotate_anchors=True)
    assert "goal" in s_pred
    # id+pred mode
    s_both = w.pretty_path(path, node_mode="id+pred", show_edge_labels=True, annotate_anchors=True)
    assert "[goal]" in s_both and "--then-->" in s_both


def test_remove_edge_alias_points_to_delete_edge():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    a = w.add_predicate("A", attach="now")
    b = w.add_predicate("B", attach="latest")
    w.add_edge(a, b, "run")
    w.add_edge(a, b, "run")  # duplicate label to be sure only exact matches are removed

    # remove by alias (back-compat)
    removed = w.remove_edge(a, b, "run")
    assert removed >= 1
