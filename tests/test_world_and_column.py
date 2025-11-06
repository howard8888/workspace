from cca8_world_graph import WorldGraph
from cca8_features import TensorPayload

def test_set_now_and_delete_edge():
    w = WorldGraph()
    now = w.ensure_anchor("NOW")
    a = w.add_predicate("pred:test:A", attach="now")
    b = w.add_predicate("pred:test:B", attach="latest")
    # move NOW and keep tags tidy
    prev = w.set_now(bid=a, tag=True, clean_previous=True)
    assert prev == now
    assert "anchor:NOW" in w._bindings[a].tags
    assert "anchor:NOW" not in w._bindings[now].tags
    # delete edge a->b (label 'then')
    removed = w.delete_edge(a, b, "then")
    assert removed >= 1

def test_capture_scene_attaches_column_pointer_and_retrievable_record():
    w = WorldGraph(); w.ensure_anchor("NOW")
    vec = [0.1, 0.2, 0.3]
    bid, eid = w.capture_scene("vision", "silhouette:mom", vec, attach="now", family="cue")
    # pointer on the binding
    eng = w._bindings[bid].engrams
    assert isinstance(eng, dict) and "column01" in eng and eng["column01"]["id"] == eid
    # column record round-trips
    rec = w.get_engram(engram_id=eid)
    assert rec.get("id") == eid
    pl = rec.get("payload")
    # TensorPayload object or dict (depending on import path), but shape must be 3
    if hasattr(pl, "meta"):
        assert pl.meta().get("shape") == (3,)
    else:
        assert (pl.get("shape") == (3,)) or (rec.get("shape") == (3,))

def test_action_metrics_and_list_actions():
    w = WorldGraph()
    w.ensure_anchor("NOW")
    s = w.add_predicate("pred:src", attach="now")
    d = w.add_predicate("pred:dst", attach="none")
    w.add_edge(s, d, label="run", meta={"meters": 10.0, "duration_s": 4.0})
    w.add_edge(s, d, label="run", meta={"meters": 6.0})
    met = w.action_metrics("run")
    assert met["count"] == 2
    assert met["keys"]["meters"]["sum"] == 16.0
    labs = w.list_actions()
    assert "run" in labs
