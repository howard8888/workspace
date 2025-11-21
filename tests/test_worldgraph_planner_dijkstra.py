import pytest

from cca8_world_graph import WorldGraph

def test_plan_to_predicate_dijkstra_uses_edge_weights():
    w = WorldGraph()
    src = w.ensure_anchor("NOW")
    goal = w.add_predicate("goal", attach="none")
    mid1 = w.add_predicate("mid1", attach="none")
    mid2 = w.add_predicate("mid2", attach="none")

    # Direct but expensive path: src -> goal
    w.add_edge(src, goal, "direct", meta={"weight": 10.0})
    # Cheaper multi-step path: src -> mid1 -> mid2 -> goal
    w.add_edge(src, mid1, "step1", meta={"weight": 1.0})
    w.add_edge(mid1, mid2, "step2", meta={"weight": 1.0})
    w.add_edge(mid2, goal, "step3", meta={"weight": 1.0})

    # BFS (default) chooses fewest hops: src -> goal
    path_bfs = w.plan_to_predicate(src, "goal")
    assert path_bfs == [src, goal]

    # Dijkstra chooses lowest total cost path via mid1/mid2
    w.set_planner("dijkstra")
    path_dijk = w.plan_to_predicate(src, "goal")
    assert path_dijk[0] == src
    assert path_dijk[-1] == goal
    assert len(path_dijk) == 4
    assert mid1 in path_dijk and mid2 in path_dijk

def test_set_planner_rejects_invalid_strategy():
    w = WorldGraph()
    with pytest.raises(ValueError):
        w.set_planner("astar")

def test_pretty_path_id_and_pred_modes():
    w = WorldGraph()
    now = w.ensure_anchor("NOW")
    goal = w.add_predicate("state:resting", attach="now")

    path = [now, goal]

    txt_id = w.pretty_path(path, node_mode="id", show_edge_labels=False, annotate_anchors=False)
    assert now in txt_id and goal in txt_id

    txt_pred = w.pretty_path(path, node_mode="pred", show_edge_labels=False, annotate_anchors=False)
    # The canonical stored tag is pred:state:resting, so 'state:resting' should appear
    assert "state:resting" in txt_pred

