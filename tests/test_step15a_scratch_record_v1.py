from __future__ import annotations

from cca8_env import EnvObservation
from cca8_run import Ctx, init_working_world, inject_obs_into_working_world


def _scratch_root_bid(ww) -> str | None:
    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    scratch_bid = anchors.get("WM_SCRATCH")
    return scratch_bid if isinstance(scratch_bid, str) else None


def _scratch_item_bids(ww) -> list[str]:
    scratch_bid = _scratch_root_bid(ww)
    if not isinstance(scratch_bid, str):
        return []

    b = getattr(ww, "_bindings", {}).get(scratch_bid)
    if b is None:
        return []

    edges = getattr(b, "edges", None)
    if not isinstance(edges, list):
        return []

    out: list[str] = []
    for e in edges:
        if not isinstance(e, dict):
            continue
        lab = e.get("label") or e.get("rel") or e.get("relation")
        dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
        if lab == "wm_scratch_item" and isinstance(dst, str):
            out.append(dst)
    return out


def _count_scratch_edge(ww, dst_bid: str) -> int:
    scratch_bid = _scratch_root_bid(ww)
    if not isinstance(scratch_bid, str):
        return 0

    b = getattr(ww, "_bindings", {}).get(scratch_bid)
    if b is None:
        return 0

    edges = getattr(b, "edges", None)
    if not isinstance(edges, list):
        return 0

    n = 0
    for e in edges:
        if not isinstance(e, dict):
            continue
        lab = e.get("label") or e.get("rel") or e.get("relation")
        dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
        if lab == "wm_scratch_item" and dst == dst_bid:
            n += 1
    return n


def _mk_patch(*, commit: str, entity_id: str, local_id: str, sig16: str) -> dict:
    # Minimal patch that looks like a real NavPatch, with a match attached.
    return {
        "schema": "navpatch_v1",
        "local_id": local_id,
        "entity_id": entity_id,
        "role": "scene" if entity_id == "scene" else "hazard",
        "frame": "ego_schematic_v1",
        "extent": {"type": "aabb", "x0": -2.0, "y0": -2.0, "x1": 2.0, "y1": 2.0},
        "tags": ["zone:safe", "stage:birth"],
        "grid_encoding_v": "grid_v1",
        "grid_w": 3,
        "grid_h": 3,
        "grid_cells": [0] * 9,
        "sig16": sig16,
        "match": {
            "decision": "new_near_match",
            "decision_note": "test ambiguity",
            "commit": commit,
            "margin": 0.01,
            "best": {"engram_id": "E1", "score": 0.90, "err": 0.10},
            "top_k": [
                {"engram_id": "E1", "score": 0.90, "err": 0.10},
                {"engram_id": "E2", "score": 0.89, "err": 0.11},
            ],
        },
    }


def test_step15a_creates_keyed_scratch_record_with_expected_payload() -> None:
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.controller_steps = 123

    patch = _mk_patch(commit="ambiguous", entity_id="scene", local_id="p_scene", sig16="0123456789abcdef")
    env_obs = EnvObservation(predicates=[], cues=[], nav_patches=[patch], env_meta={})
    inject_obs_into_working_world(ctx, env_obs)

    ww = ctx.working_world
    assert ww is not None

    # Key bookkeeping (this is part of Step 15A's contract).
    key = "scene|p_scene"
    assert ctx.wm_scratch_navpatch_last_keys == {key}
    assert isinstance(ctx.wm_scratch_navpatch_key_to_bid, dict)
    assert key in ctx.wm_scratch_navpatch_key_to_bid

    sbid = ctx.wm_scratch_navpatch_key_to_bid[key]
    assert isinstance(sbid, str)

    # Scratch root exists and points to the item.
    items = _scratch_item_bids(ww)
    assert sbid in items

    # Item should be anchored (stable update-in-place).
    anchors = getattr(ww, "_anchors", {})
    assert any(isinstance(k, str) and k.startswith("WM_SCRATCH_NVP_") and v == sbid for k, v in anchors.items())

    b = getattr(ww, "_bindings", {}).get(sbid)
    assert b is not None

    # Tags (don’t require exact set type).
    tags = getattr(b, "tags", None) or set()
    if isinstance(tags, list):
        tags = set(tags)
    assert "wm:scratch_item" in tags
    assert "wm:scratch:navpatch_match" in tags
    assert "wm:eid:scene" in tags
    assert "wm:patch_local:p_scene" in tags

    # Payload integrity.
    meta = getattr(b, "meta", None)
    assert isinstance(meta, dict)

    wmm = meta.get("wm")
    assert isinstance(wmm, dict)
    assert wmm.get("schema") == "wm_scratch_navpatch_match_v1"
    assert wmm.get("commit") == "ambiguous"
    assert wmm.get("entity_id") == "scene"
    assert wmm.get("local_id") == "p_scene"
    assert wmm.get("patch_sig16") == "0123456789abcdef"
    assert wmm.get("controller_steps") == 123
    assert isinstance(wmm.get("best"), dict)
    assert isinstance(wmm.get("top_k"), list)


def test_step15a_upserts_without_duplicates_and_cleans_up_when_resolved() -> None:
    ctx = Ctx()
    ctx.working_world = init_working_world()

    patch_amb = _mk_patch(commit="ambiguous", entity_id="scene", local_id="p_scene", sig16="0123456789abcdef")
    patch_ok = _mk_patch(commit="commit", entity_id="scene", local_id="p_scene", sig16="0123456789abcdef")

    # Tick 10: become ambiguous -> item created
    ctx.controller_steps = 10
    inject_obs_into_working_world(ctx, EnvObservation(predicates=[], cues=[], nav_patches=[patch_amb], env_meta={}))
    ww = ctx.working_world
    assert ww is not None

    key = "scene|p_scene"
    sbid = ctx.wm_scratch_navpatch_key_to_bid[key]
    assert _count_scratch_edge(ww, sbid) == 1

    # Tick 11: still ambiguous -> should update in-place, not create duplicates
    ctx.controller_steps = 11
    inject_obs_into_working_world(ctx, EnvObservation(predicates=[], cues=[], nav_patches=[patch_amb], env_meta={}))
    assert ctx.wm_scratch_navpatch_key_to_bid[key] == sbid
    assert _count_scratch_edge(ww, sbid) == 1

    # Tick 12: resolved -> scratch edge removed, key mapping cleared, last_keys empty
    ctx.controller_steps = 12
    inject_obs_into_working_world(ctx, EnvObservation(predicates=[], cues=[], nav_patches=[patch_ok], env_meta={}))
    assert key not in ctx.wm_scratch_navpatch_key_to_bid
    assert ctx.wm_scratch_navpatch_last_keys == set()
    assert sbid not in _scratch_item_bids(ww)


def test_step15a_multiple_ambiguous_patches_create_multiple_items() -> None:
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.controller_steps = 200

    p1 = _mk_patch(commit="ambiguous", entity_id="scene", local_id="p_scene", sig16="1111111111111111")
    p2 = _mk_patch(commit="ambiguous", entity_id="cliff", local_id="p_cliff", sig16="2222222222222222")

    env_obs = EnvObservation(predicates=[], cues=[], nav_patches=[p1, p2], env_meta={})
    inject_obs_into_working_world(ctx, env_obs)

    ww = ctx.working_world
    assert ww is not None

    keys = ctx.wm_scratch_navpatch_last_keys
    assert keys == {"scene|p_scene", "cliff|p_cliff"}

    m = ctx.wm_scratch_navpatch_key_to_bid
    assert isinstance(m, dict)
    assert "scene|p_scene" in m and "cliff|p_cliff" in m

    items = set(_scratch_item_bids(ww))
    assert m["scene|p_scene"] in items
    assert m["cliff|p_cliff"] in items