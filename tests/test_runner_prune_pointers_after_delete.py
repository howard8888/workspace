import cca8_world_graph as wg
from cca8_column import mem as column_mem

def test_delete_engram_and_prune_pointers_like_menu30():
    world = wg.WorldGraph()
    world.ensure_anchor("NOW")
    bid, eid = world.capture_scene("vision", "silhouette:mom", [0.1, 0.2, 0.3], attach="now", family="cue")
    b = world._bindings[bid]
    assert "column01" in (b.engrams or {})

    # Simulate menu 30: delete from Column and prune pointers in the graph
    ok = column_mem.delete(eid)
    assert ok is True

    pruned = 0
    for _bid, _b in world._bindings.items():
        eng = getattr(_b, "engrams", None)
        if not isinstance(eng, dict):
            continue
        for slot, val in list(eng.items()):
            if isinstance(val, dict) and val.get("id") == eid:
                del eng[slot]
                pruned += 1

    assert pruned >= 1
    assert "column01" not in (b.engrams or {})
