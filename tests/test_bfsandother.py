import re
import os
import importlib
import pytest

# Skip the whole module if the world graph isn't importable
W = pytest.importorskip("cca8_world_graph", reason="cca8_world_graph module not found")


def _quiet_tags(world):
    """Silence lexicon warnings during tests, if supported."""
    if hasattr(world, "set_tag_policy"):
        try:
            world.set_tag_policy("allow")
        except Exception:
            pass


def _build_weighted_demo_world(force_env_planner: str | None = None):
    """
    Construct a tiny graph with two routes from NOW -> goal:

      Route 1 (2 hops, but heavy):
        NOW -[5]-> X -[1]-> goal     total cost = 6

      Route 2 (3 hops, cheap):
        NOW -[1]-> A -[1]-> B -[1]-> goal   total cost = 3

    Dijkstra should pick Route 2; BFS should pick Route 1.
    """
    if force_env_planner is not None:
        # If the implementation reads the planner strategy from an env var in __init__,
        # set it *before* constructing the world.
        os.environ["CCA8_PLANNER"] = force_env_planner

    world = W.WorldGraph()
    _quiet_tags(world)

    start = world.ensure_anchor("NOW")

    # Cheap 3-hop path via A -> B -> goal (each weight=1 by default)
    a = world.add_predicate("A", attach="now")       # NOW -> A (weight 1 default)
    b = world.add_predicate("B", attach="latest")    # A -> B
    goal = world.add_predicate("goal", attach="latest")  # B -> goal

    # Heavy 2-hop path via X: add X WITHOUT auto-link; then explicit heavy edge.
    x = world.add_predicate("X", attach=None)        # <-- no auto edge
    world.add_edge(start, x, "then", meta={"weight": 5})
    world.add_edge(x, goal, "then", meta={"weight": 1})

    return world, start, goal, {"A": a, "B": b, "X": x}


def _first_pred_token(world, binding_id) -> str | None:
    """Return the first pred:* token (without 'pred:') from a binding."""
    b = world._bindings[binding_id]  # project-internal structure; fine for tests
    for t in b.tags:
        if isinstance(t, str) and t.startswith("pred:"):
            return t[5:]
    return None


def _path_tokens(world, ids):
    """Map a path of ids to their first predicate tokens (NOW/HERE will be None)."""
    return [_first_pred_token(world, u) for u in ids]


def test_bfs_vs_dijkstra_weighted_routes():
    world, start, goal, ids = _build_weighted_demo_world()

    # If planner switching hasn't been integrated yet, skip cleanly.
    if not hasattr(world, "set_planner") or not hasattr(world, "get_planner"):
        pytest.skip("Planner switching API (set_planner/get_planner) not available yet.")

    # --- BFS (fewest hops: NOW -> X -> goal) ---
    world.set_planner("bfs")
    path_bfs = world.plan_to_predicate(start, "goal")
    assert path_bfs is not None, "BFS should find a path"
    toks_bfs = _path_tokens(world, path_bfs)

    # Expected 3 nodes: [NOW(None), X, goal]
    assert len(path_bfs) == 3, f"BFS should choose 2-hop route via X; got {len(path_bfs)-1} hops"
    assert toks_bfs[1] == "X" and toks_bfs[-1] == "goal"

    # --- Dijkstra (lowest total weight: NOW -> A -> B -> goal) ---
    world.set_planner("dijkstra")
    path_dij = world.plan_to_predicate(start, "goal")
    assert path_dij is not None, "Dijkstra should find a path"
    toks_dij = _path_tokens(world, path_dij)

    # Expected 4 nodes: [NOW(None), A, B, goal]
    assert len(path_dij) == 4, f"Dijkstra should choose 3-hop cheaper route; got {len(path_dij)-1} hops"
    assert toks_dij[1:3] == ["A", "B"] and toks_dij[-1] == "goal"
    assert toks_bfs != toks_dij, "Strategies should disagree on this weighted graph"


def test_env_var_planner_toggle(monkeypatch):
    """
    If your __init__ reads CCA8_PLANNER, this verifies that 'dijkstra'
    is respected without calling set_planner() explicitly.
    """
    monkeypatch.setenv("CCA8_PLANNER", "dijkstra")

    # Re-importing isn't necessary if the class reads the env var in __init__.
    # Just build a fresh world after setting the env var:
    world, start, goal, ids = _build_weighted_demo_world()

    # If there's no way to introspect the current planner, try to infer by behavior.
    if hasattr(world, "get_planner"):
        assert world.get_planner() == "dijkstra"
    else:
        # Infer via behavior (should pick A->B->goal)
        path = world.plan_to_predicate(start, "goal")
        assert path is not None
        toks = _path_tokens(world, path)
        assert toks[1:3] == ["A", "B"] and toks[-1] == "goal"


def test_dijkstra_falls_back_to_other_weight_keys():
    """
    Confirms the priority: weight -> cost -> distance -> duration_s -> 1.0
    Here we *don't* set 'weight' but use 'cost' instead.
    """
    world = W.WorldGraph()
    _quiet_tags(world)
    start = world.ensure_anchor("NOW")

    # Cheap 3-hop path via A->B->goal using defaults (=1)
    a = world.add_predicate("A", attach="now")
    b = world.add_predicate("B", attach="latest")
    goal = world.add_predicate("goal", attach="latest")

    # Heavy 2-hop path via X using 'cost' instead of 'weight'
    x = world.add_predicate("X", attach=None)
    world.add_edge(start, x, "then", meta={"cost": 5})
    world.add_edge(x, goal, "then", meta={"cost": 1})

    # If Dijkstra isn't wired, skip cleanly
    if not hasattr(world, "set_planner"):
        pytest.skip("Dijkstra not available (set_planner missing).")

    world.set_planner("dijkstra")
    path = world.plan_to_predicate(start, "goal")
    assert path is not None
    toks = _path_tokens(world, path)
    # Should prefer A->B->goal (3 total) over NOW->X->goal (6 total)
    assert toks[1:3] == ["A", "B"] and toks[-1] == "goal"


def test_unweighted_equivalence_when_no_weights():
    """
    With no explicit weights anywhere, Dijkstra and BFS should generally agree
    (all edges cost 1). We assert equal hop counts on a fresh tiny graph.
    """
    world = W.WorldGraph()
    _quiet_tags(world)
    start = world.ensure_anchor("NOW")

    # Two parallel 2-hop routes to 'goal' (no weights at all)
    a = world.add_predicate("A", attach="now")
    goal = world.add_predicate("goal", attach="latest")

    x = world.add_predicate("X", attach=None)
    world.add_edge(start, x, "then")
    world.add_edge(x, goal, "then")

    if not hasattr(world, "set_planner"):
        pytest.skip("Planner switching API not integrated yet.")

    world.set_planner("bfs")
    p_bfs = world.plan_to_predicate(start, "goal")
    assert p_bfs is not None

    world.set_planner("dijkstra")
    p_dij = world.plan_to_predicate(start, "goal")
    assert p_dij is not None

    assert len(p_bfs) == len(p_dij), "With all weights=1, hop counts should match"
