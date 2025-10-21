import pytest
W = pytest.importorskip("cca8_world_graph")
R = pytest.importorskip("cca8_run")

def _quiet(w):
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")

def test_choose_contextual_base_prefers_nearest_predicate():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    stand = w.add_predicate("stand", attach="now")
    ctx = R.Ctx()
    base = R.choose_contextual_base(w, ctx, targets=["stand"])
    assert base["base"] == "NEAREST_PRED" and base["bid"] in (now, stand)

def test_compute_foa_includes_now_and_latest():
    w = W.WorldGraph(); _quiet(w)
    now = w.ensure_anchor("NOW")
    a = w.add_predicate("A", attach="now")     # becomes latest
    ctx = R.Ctx()
    foa = R.compute_foa(w, ctx, max_hops=1)
    assert now in foa["seeds"] and a in foa["seeds"]
    assert foa["size"] >= 1
