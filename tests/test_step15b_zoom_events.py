import pytest

from cca8_env import EnvObservation
from cca8_run import Ctx, init_working_world, inject_obs_into_working_world


def _mk_patch(*, commit: str, entity_id: str = "cliff", local_id: str = "p_cliff") -> dict:
    """Build a minimal NavPatch dict that Step 15A/15B can read safely.

    Notes:
      - We set match.commit explicitly (ambiguous vs commit) so this stays a unit test
        of the WM.Scratch + WM.Zoom logic, not a test of the NavPatch match loop.
      - Keep the payload JSON-safe and small.
    """
    return {
        "schema": "navpatch_v1",
        "local_id": local_id,
        "entity_id": entity_id,
        "role": "hazard",
        "frame": "wm_grid_v1",
        "grid_encoding_v": "cells_v1",
        "grid_w": 4,
        "grid_h": 4,
        "grid_origin": [0.0, 0.0],
        "grid_resolution": 1.0,
        "grid_cells": [0] * 16,
        "extent": {"x0": 0.0, "y0": 0.0, "x1": 1.0, "y1": 1.0},
        "tags": ["hazard:cliff:near"],
        "layers": {},
        "match": {
            "commit": commit,
            "decision": "new_near_match",
            "decision_note": None,
            "margin": 0.01,
            "best": {"engram_id": "x", "score": 0.90, "err": 0.10},
            "top_k": [],
        },
        "sig16": "deadbeefdeadbeef",
    }


def _mk_obs(patches: list[dict]) -> EnvObservation:
    return EnvObservation(raw_sensors={}, predicates=[], cues=[], nav_patches=patches, env_meta={})


def _edge_exists(world, src: str, label: str, dst: str) -> bool:
    """Small helper to check WorkingMap internal adjacency without relying on ordering."""
    try:
        b = getattr(world, "_bindings", {}).get(src)
        if b is None:
            return False
        edges = getattr(b, "edges", None) or []
        if not isinstance(edges, list):
            return False
        for e in edges:
            if not isinstance(e, dict):
                continue
            lab = e.get("label") or e.get("rel") or e.get("relation")
            to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if lab == label and to_ == dst:
                return True
    except Exception:
        return False
    return False


def test_step15b_zoom_transitions_payload_and_stability():
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.working_enabled = True

    # Keep this test focused on Scratch+Zoom (avoid unrelated per-tick work).
    ctx.wm_surfacegrid_enabled = False
    ctx.wm_salience_enabled = False
    ctx.wm_grid_to_preds_enabled = False

    # Step 15A/15B are under the navpatch-enabled path.
    ctx.navpatch_enabled = True
    ctx.navpatch_store_to_column = False

    ctx.wm_scratch_navpatch_enabled = True
    ctx.wm_zoom_enabled = True
    ctx.wm_zoom_verbose = False

    key = "cliff|p_cliff"

    # --- Tick 10: ambiguity appears -> zoom_down + scratch item created ---
    ctx.controller_steps = 10
    inject_obs_into_working_world(ctx, _mk_obs([_mk_patch(commit="ambiguous")]))

    assert ctx.wm_zoom_state == "down"
    assert isinstance(ctx.wm_zoom_last_events, list) and len(ctx.wm_zoom_last_events) == 1

    ev = ctx.wm_zoom_last_events[0]
    assert ev.get("kind") == "zoom_down"
    assert ev.get("reason") == "hazard+ambiguity"
    assert ev.get("controller_steps") == 10
    assert ev.get("ambiguous_n") == 1
    assert ev.get("ambiguous_keys") == [key]
    assert ev.get("ambiguous_entities") == ["cliff"]
    assert ev.get("hazard_ambiguous") is True

    # Step 15A: scratch key bookkeeping exists
    assert ctx.wm_scratch_navpatch_last_keys == {key}
    assert isinstance(ctx.wm_scratch_navpatch_key_to_bid, dict)
    assert key in ctx.wm_scratch_navpatch_key_to_bid

    ww = ctx.working_world
    assert ww is not None

    scratch_root = getattr(ww, "_anchors", {}).get("WM_SCRATCH")
    assert isinstance(scratch_root, str) and scratch_root in getattr(ww, "_bindings", {})

    sbid = ctx.wm_scratch_navpatch_key_to_bid[key]
    assert isinstance(sbid, str) and sbid in getattr(ww, "_bindings", {})

    # Scratch root points to the item
    assert _edge_exists(ww, scratch_root, "wm_scratch_item", sbid)

    # Scratch item has expected tags + meta payload marker
    sb = ww._bindings.get(sbid)  # pylint: disable=protected-access
    assert sb is not None
    tags = getattr(sb, "tags", None) or set()
    if isinstance(tags, list):
        tags = set(tags)
    assert "wm:scratch_item" in tags
    assert "wm:scratch:navpatch_match" in tags
    assert "wm:eid:cliff" in tags
    assert "wm:patch_local:p_cliff" in tags

    meta = getattr(sb, "meta", None)
    assert isinstance(meta, dict)
    wmm = meta.get("wm")
    assert isinstance(wmm, dict)
    assert wmm.get("schema") == "wm_scratch_navpatch_match_v1"
    assert wmm.get("commit") == "ambiguous"
    assert wmm.get("entity_id") == "cliff"
    assert wmm.get("local_id") == "p_cliff"

    # --- Tick 11: still ambiguous -> NO new zoom event (transition-only) ---
    ctx.controller_steps = 11
    inject_obs_into_working_world(ctx, _mk_obs([_mk_patch(commit="ambiguous")]))
    assert ctx.wm_zoom_state == "down"
    assert ctx.wm_zoom_last_events == []

    # --- Tick 12: ambiguity clears -> zoom_up, keys included from previous ambiguity ---
    ctx.controller_steps = 12
    inject_obs_into_working_world(ctx, _mk_obs([_mk_patch(commit="commit")]))
    assert ctx.wm_zoom_state == "up"
    assert isinstance(ctx.wm_zoom_last_events, list) and len(ctx.wm_zoom_last_events) == 1

    ev = ctx.wm_zoom_last_events[0]
    assert ev.get("kind") == "zoom_up"
    assert ev.get("reason") == "resolved"
    assert ev.get("controller_steps") == 12
    assert ev.get("ambiguous_n") == 1
    assert ev.get("ambiguous_keys") == [key]
    assert ev.get("ambiguous_entities") == ["cliff"]

    # Scratch keys cleared; mapping for this key removed
    assert ctx.wm_scratch_navpatch_last_keys == set()
    assert key not in ctx.wm_scratch_navpatch_key_to_bid

    # Edge from WM_SCRATCH to the item should be removed
    assert not _edge_exists(ww, scratch_root, "wm_scratch_item", sbid)

    # --- Tick 13: still clear -> NO new zoom event ---
    ctx.controller_steps = 13
    inject_obs_into_working_world(ctx, _mk_obs([_mk_patch(commit="commit")]))
    assert ctx.wm_zoom_state == "up"
    assert ctx.wm_zoom_last_events == []


def test_step15b_no_match_dict_no_zoom_and_no_scratch():
    ctx = Ctx()
    ctx.working_world = init_working_world()
    ctx.working_enabled = True

    # Focus the test.
    ctx.wm_surfacegrid_enabled = False
    ctx.wm_salience_enabled = False
    ctx.wm_grid_to_preds_enabled = False

    ctx.navpatch_enabled = True
    ctx.navpatch_store_to_column = False
    ctx.wm_scratch_navpatch_enabled = True
    ctx.wm_zoom_enabled = True

    # Patch missing "match" should not create scratch ambiguity or zoom transitions.
    patch = _mk_patch(commit="commit")
    patch.pop("match", None)

    ctx.controller_steps = 20
    inject_obs_into_working_world(ctx, _mk_obs([patch]))

    assert ctx.wm_zoom_state == "up"
    assert ctx.wm_zoom_last_events == []
    assert ctx.wm_scratch_navpatch_last_keys == set()