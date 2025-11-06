from cca8_run import _hamming_hex64, snapshot_text, Ctx
from cca8_world_graph import WorldGraph

def test_hamming_hex64_and_snapshot_text_smoke():
    assert _hamming_hex64("0001", "0000") == 1
    w = WorldGraph(); w.ensure_anchor("NOW")
    ctx = Ctx()
    txt = snapshot_text(w, drives=None, ctx=ctx)
    assert "WorldGraph snapshot" in txt
    assert "LEGEND (temporal terms):" in txt
    #assert "TEMPORAL:" in txt  # has temporal probe block
