import pytest

F = pytest.importorskip("cca8_features")
W = pytest.importorskip("cca8_world_graph")
COL = pytest.importorskip("cca8_column")


def _quiet(w):
    if hasattr(w, "set_tag_policy"):
        w.set_tag_policy("allow")


def test_attach_engram_and_get_roundtrip():
    w = W.WorldGraph(); _quiet(w); w.ensure_anchor("NOW")
    b = w.add_predicate("scene:demo", attach="now")
    tp = F.TensorPayload([0.1, 0.2, 0.3], shape=(3,), kind="scene", fmt="tensor/list-f32")
    eid = COL.mem.assert_fact("scene:demo", tp)
    w.attach_engram(b, engram_id=eid, column="column01", act=0.9, extra_meta={"note": "t"})
    rec = w.get_engram(engram_id=eid)
    assert rec["id"] == eid and rec["payload"].shape == (3,)
