import pytest

W = pytest.importorskip("cca8_world_graph")
F = pytest.importorskip("cca8_features")
C = pytest.importorskip("cca8_column")

def _quiet(w):
    if hasattr(w, "set_tag_policy"): w.set_tag_policy("allow")

def test_capture_scene_attaches_engram_for_cue_and_pred():
    w = W.WorldGraph(); _quiet(w)
    w.ensure_anchor("NOW")

    # cue family
    bid1, eid1 = w.capture_scene(
        "vision", "silhouette:mom", [0.1, 0.2, 0.3], family="cue", attach="now"
    )
    rec1 = C.mem.get(eid1)
    assert rec1["payload"].shape == (3,)

    # pred family
    bid2, eid2 = w.capture_scene(
        "vision", "edge:rock", [0.4, 0.5], family="pred", attach="latest"
    )
    rec2 = C.mem.get(eid2)
    assert rec2["payload"].shape == (2,)
