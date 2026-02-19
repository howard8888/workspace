import sys
sys.path.insert(0, ".")  # repo root

import cca8_run
from cca8_column import mem as column_mem


def test_navpatch_sig_ignores_obs_meta():
    p1 = {
        "schema": "navpatch_v1",
        "local_id": "p_test",
        "entity_id": "cliff",
        "role": "hazard",
        "frame": "ego_schematic_v1",
        "extent": {"type": "aabb", "x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
        "tags": ["hazard:cliff:near"],
        "layers": {},
        "obs": {"source": "A", "time": 1},
    }
    p2 = dict(p1)
    p2["obs"] = {"source": "B", "time": 999}

    s1 = cca8_run.navpatch_payload_sig_v1(p1)
    s2 = cca8_run.navpatch_payload_sig_v1(p2)
    assert s1 == s2


def test_store_navpatch_dedups_in_ctx_cache():
    # Clear column for this test (in-memory only)
    try:
        column_mem._store.clear()  # pylint: disable=protected-access
    except Exception:
        pass

    ctx = cca8_run.Ctx()
    ctx.navpatch_sig_to_eid.clear()

    patch = {
        "schema": "navpatch_v1",
        "local_id": "p_test",
        "entity_id": "mom",
        "role": "agent",
        "frame": "ego_schematic_v1",
        "extent": {"type": "aabb", "x0": -1.0, "y0": -1.0, "x1": 1.0, "y1": 1.0},
        "tags": ["proximity:mom:near"],
        "layers": {},
    }

    r1 = cca8_run.store_navpatch_engram_v1(ctx, patch, reason="test")
    r2 = cca8_run.store_navpatch_engram_v1(ctx, patch, reason="test")

    assert r1["engram_id"] == r2["engram_id"]
    assert r1["stored"] is True
    assert r2["stored"] is False
