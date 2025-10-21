import pytest

R = pytest.importorskip("cca8_run")
W = pytest.importorskip("cca8_world_graph")

def test_versions_text_contains_core_sections():
    txt = R.versions_text()
    for key in ("runner", "world_graph", "controller", "column", "features", "temporal"):
        assert key in txt.lower()

def test_bindings_with_pred_helpers_hit_goal_path():
    w = W.WorldGraph()
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")
    now = w.ensure_anchor("NOW")
    a = w.add_predicate("A", attach="now")
    goal = w.add_predicate("goal", attach="latest")

    # exercise both helper spellings if present
    if hasattr(R, "bindings_with_pred"):
        out = R.bindings_with_pred(w, "goal")
        assert goal in out
    if hasattr(R, "_bindings_with_pred"):
        out2 = R._bindings_with_pred(w, "goal")
        assert goal in out2
