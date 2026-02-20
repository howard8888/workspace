# -*- coding: utf-8 -*-
"""
Phase X: NavPatch v1 tests.

These are deliberately small and deterministic:
- signature stability (order-insensitive tags; ignores volatile fields)
- per-run dedup when storing patches into Column memory
"""

from __future__ import annotations

from typing import Any

from cca8_column import ColumnMemory
import cca8_run


def _mk_patch(*, tags: list[str] | None = None, x0: float = -2.0) -> dict[str, Any]:
    tag_list = tags if tags is not None else ["zone:unsafe", "position:cliff_edge", "stage:birth"]
    return {
        "schema": "navpatch_v1",
        "local_id": "p_scene",
        "entity_id": "scene",
        "role": "scene",
        "frame": "ego_schematic_v1",
        "extent": {"type": "aabb", "x0": x0, "y0": -2.0, "x1": 2.0, "y1": 2.0},
        "tags": list(tag_list),
        "layers": {},
        # Volatile/debug-only fields (should NOT affect signature):
        "obs": {"source": "unit_test"},
        "match": {"decision": "new_no_candidates"},
    }


def test_navpatch_payload_sig_v1_deterministic_and_ignores_volatiles() -> None:
    p1 = _mk_patch(tags=["zone:unsafe", "position:cliff_edge", "stage:birth"])
    s1 = cca8_run.navpatch_payload_sig_v1(p1)
    assert isinstance(s1, str) and len(s1) >= 16

    # Same core, different tag order + different volatile fields => same signature
    p2 = _mk_patch(tags=["stage:birth", "position:cliff_edge", "zone:unsafe"])
    p2["obs"] = {"source": "different_sensor"}  # should not matter
    p2["match"] = {"decision": "reuse_exact", "best": {"score": 1.0}}  # should not matter
    s2 = cca8_run.navpatch_payload_sig_v1(p2)
    assert s2 == s1

    # Core geometry change => signature should change
    p3 = _mk_patch(tags=["zone:unsafe", "position:cliff_edge", "stage:birth"], x0=-2.5)
    s3 = cca8_run.navpatch_payload_sig_v1(p3)
    assert s3 != s1


def test_store_navpatch_engram_v1_dedup_cache(monkeypatch) -> None:
    # Isolate Column memory so this test doesn't share global state with other tests/runs.
    fresh_col = ColumnMemory(name="column_test")
    monkeypatch.setattr(cca8_run, "column_mem", fresh_col)

    ctx = cca8_run.Ctx()
    ctx.navpatch_sig_to_eid = {}

    patch = _mk_patch()

    first = cca8_run.store_navpatch_engram_v1(ctx, patch, reason="unit_test")
    assert first.get("stored") is True
    eid1 = first.get("engram_id")
    sig1 = first.get("sig")
    assert isinstance(eid1, str) and eid1
    assert isinstance(sig1, str) and sig1

    second = cca8_run.store_navpatch_engram_v1(ctx, patch, reason="unit_test")
    assert second.get("stored") is False
    assert second.get("reason") == "dedup_cache"
    assert second.get("engram_id") == eid1
    assert second.get("sig") == sig1

    # Only one record should exist in this isolated column.
    assert fresh_col.count() == 1
    assert ctx.navpatch_sig_to_eid.get(sig1) == eid1
