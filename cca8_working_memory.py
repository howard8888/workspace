#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 WorkingMap, NavPatch, SurfaceGrid, and MapSurface subsystem.

Purpose
-------
This module owns Phases 1 through 3 of the CCA8 working-memory extraction.
Phase 1 contains WorkingMap construction/reset, MapSurface serialization,
Column storage, candidate ranking, and conservative merge/replace loading.
Phase 2 contains NavPatch matching, ambiguity Scratch records, zoom/probe
bookkeeping, salience focus, SurfaceGrid composition, grid-derived predicates,
and NavSummary calculation. Phase 3 contains live observation injection,
stateful MapSurface updates, pruning, retrieval gating, contextual map switching,
and short-lived retrieved-state hints.

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. It depends only on stable CCA8 modules
and data structures. ``cca8_run`` retains historical names through aliases and
small wrappers where call-time dependency replacement must remain possible. The
runner retains compatibility names and supplies replaceable dependencies through
small callback wrappers; the implementation remains one-way and import-safe.

WorldGraph boundary
-------------------
WorkingMap is implemented with ``WorldGraph`` objects, and this module is the
narrow owner of the internal mutations needed for short-lived working-memory
graphs. Long-term WorldGraph writes continue to use public methods. Future
WorldGraph APIs can replace these localized internal accesses without touching
the runner or experiment subsystem.
"""

from __future__ import annotations

# The extracted pipeline intentionally preserves the defensive implementation
# that was previously inside cca8_run.py.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-positional-arguments
# pylint: disable=too-many-boolean-expressions
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements
# pylint: disable=multiple-statements

import hashlib
import json
from math import log as _math_log, sqrt as _math_sqrt
import time
from typing import Any, Callable, Optional, cast

import cca8_navpatch
import cca8_world_graph
from cca8_column import mem as column_mem
from cca8_context import Ctx
from cca8_env import EnvObservation
from cca8_controller import (
    body_cliff_distance,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_shelter_distance,
    body_space_zone,
    bodymap_is_stale,
)
from cca8_features import FactMeta
from cca8_navpatch import (
    CELL_GOAL,
    CELL_HAZARD,
    CELL_TRAVERSABLE,
    CELL_UNKNOWN,
    SurfaceGridV1,
    compose_surfacegrid_v1,
    derive_grid_slot_families_v1,
    grid_overlap_fraction_v1,
)

__version__ = "0.3.0"

__all__ = [
    "init_working_world",
    "reset_working_world",
    "init_map_surface_world",
    "update_surface_grid_from_obs",
    "update_map_surface_from_obs",
    "predcode_update_from_obs",
    "should_autoretrieve_mapsurface",
    "maybe_autoretrieve_mapsurface_on_keyframe",
    "maybe_goat04_context_mapswitch_on_keyframe_v1",
    "maybe_newborn_b2_mapswitch_on_keyframe_v1",
    "inject_obs_into_working_world",
    "serialize_mapsurface_v1",
    "mapsurface_payload_sig_v1",
    "mapsurface_salience_v1",
    "current_mapsurface_salience_v1",
    "store_mapsurface_snapshot_v1",
    "pick_best_wm_mapsurface_rec",
    "load_mapsurface_payload_v1_into_workingmap",
    "merge_mapsurface_payload_v1_into_workingmap",
    "format_mapswitch_event_line_v1",
    "load_wm_mapsurface_engram_into_workingmap_mode",
    "load_wm_mapsurface_engram_into_workingmap",
    "navpatch_payload_sig_v1",
    "store_navpatch_engram_v1",
    "navpatch_similarity_v1",
    "navpatch_priors_bundle_v1",
    "navpatch_candidate_prior_bias_v1",
    "navpatch_predictive_match_loop_v1",
    "wm_apply_grid_slot_families_to_mapsurface_v1",
    "compute_navsummary_v1",
    "format_navsummary_line_v1",
    "render_surfacegrid_ascii_with_salience_v1",
    "format_surfacegrid_ascii_map_v1",
    "format_surfacegrid_snapshot_v1",
    "wm_salience_force_focus_entity_v1",
    "wm_salience_force_focus_token_v1",
    "wm_salience_tick_v1",
    "update_working_navpatch_refs_v1",
    "update_working_navpatch_scratch_zoom_v1",
    "update_working_salience_surfacegrid_v1",
    "__version__",
]


def init_working_world() -> cca8_world_graph.WorldGraph:
    """Initialize a short-term WorkingMap (working memory) as a separate WorldGraph.

    Design intent:
      - WorkingMap holds the full episodic trace.
      - Long-term WorldGraph can later be run in 'semantic' mode to reduce clutter.
      - Consolidation policy (what gets copied from WorkingMap into WorldGraph) can evolve
        without losing the ability to record raw per-tick structure.
    """
    ww = cca8_world_graph.WorldGraph(memory_mode="episodic")
    ww.set_tag_policy("allow")
    ww.set_stage("neonate")
    ww.ensure_anchor("NOW")
    ww.ensure_anchor("NOW_ORIGIN")
    return ww


def reset_working_world(ctx) -> None:
    """Reset ctx.working_world to a fresh WorkingMap instance (and clear MapSurface caches).
    """
    try:
        ctx.working_world = init_working_world()
        # MapSurface caches live on ctx (slots=True → must be explicit)
        ctx.wm_entities.clear()
        ctx.wm_last_env_cues.clear()
        # Creative layer state is also WorkingMap-local (ephemeral); clearing WM clears this too.
        try:
            ctx.wm_creative_candidates.clear()
            ctx.wm_creative_last_pick = None
        except Exception:
            pass
    except Exception:
        # If ctx is not writable for some reason, fail silently.
        pass


def serialize_mapsurface_v1(ctx: Ctx, *, include_internal_ids: bool = False) -> dict[str, Any]:
    """Serialize the WorkingMap MapSurface into a JSON-safe dict (MapEngram payload v1).

    Purpose / intent
    ----------------
    Option B (memory pipeline) will store WorkingMap snapshots as **Column engrams**. This function provides the
    *heavy payload* for such an engram: a stable, explicit, inspectable representation of the current MapSurface.

    Design constraints
    ------------------
    - Must be JSON-safe: only dict/list/str/int/float/bool/None.
    - Must be robust: never raise (best-effort snapshot).
    - Must NOT mutate WorkingMap: read-only.

    Included content (v1)
    ---------------------
    - header:
        schema tag, controller_steps/ticks/boundary/run-step, temporal fingerprint, and a tiny BodyMap readout if available.
    - entities:
        one record per WM entity (eid/kind/pos/dist/seen + preds + cues).
    - relations:
        distance_to edges from SELF → other entities, including edge meta (meters/class/frame) when present.

    Args:
        ctx:
            Runtime context (holds working_world and wm_entities).
        include_internal_ids:
            If True, include internal WorkingMap binding ids (e.g., "b17") in entity and relation records.
            Keep False for stable payloads; turn on only for debugging.

    Returns:
        A dict payload suitable for storing as a Column engram.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        return {
            "schema": "wm_mapsurface_v1",
            "header": {"error": "no_working_world"},
            "entities": [],
            "relations": [],
        }

    ent_map = getattr(ctx, "wm_entities", None)
    if not isinstance(ent_map, dict):
        ent_map = {}

    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    root_bid = anchors.get("WM_ROOT") or anchors.get("NOW")
    self_bid = ent_map.get("self") or anchors.get("WM_SELF")

    # ---- header (best-effort) ----
    header: dict[str, Any] = {
        "schema": "wm_mapsurface_v1",
        "profile": getattr(ctx, "profile", None),
        "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
        "ticks": int(getattr(ctx, "ticks", 0) or 0),
        "boundary_no": int(getattr(ctx, "boundary_no", 0) or 0),
        "boundary_vhash64": getattr(ctx, "boundary_vhash64", None),
        "tvec64": (ctx.tvec64() if hasattr(ctx, "tvec64") else None),
        "run_last_env_step": getattr(ctx, "run_last_env_step", None),
    }
    if isinstance(root_bid, str) and include_internal_ids:
        header["wm_root_bid"] = root_bid
    if isinstance(self_bid, str) and include_internal_ids:
        header["wm_self_bid"] = self_bid

    # Tiny BodyMap readout (helps indexing/debug; does not affect MapSurface content)
    body: dict[str, Any] = {"stale": True}
    try:
        stale = bool(bodymap_is_stale(ctx))
        body["stale"] = stale
        if not stale:
            try:
                body["posture"] = body_posture(ctx)
            except Exception:
                pass
            try:
                body["mom_distance"] = body_mom_distance(ctx)
            except Exception:
                pass
            try:
                body["nipple_state"] = body_nipple_state(ctx)
            except Exception:
                pass
            try:
                body["zone"] = body_space_zone(ctx)
            except Exception:
                pass
    except Exception:
        body = {"stale": True}
    header["body"] = body

    # ---- helpers ----
    def _as_float(x) -> float | None:
        try:
            return float(x)
        except Exception:
            return None

    def _as_int(x) -> int | None:
        try:
            return int(x)
        except Exception:
            return None

    # reverse map for relation decoding (bid -> eid)
    bid_to_eid: dict[str, str] = {}
    for eid, bid in ent_map.items():
        if isinstance(eid, str) and isinstance(bid, str):
            bid_to_eid[bid] = eid

    def _entity_record(eid: str, bid: str) -> dict[str, Any]:
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            out = {"eid": eid}
            if include_internal_ids:
                out["bid"] = bid
            return out

        tags_raw = getattr(b, "tags", None)
        if tags_raw is None:
            tags: list[str] = []
        elif isinstance(tags_raw, (set, list, tuple)):
            tags = [t for t in tags_raw if isinstance(t, str)]
        else:
            try:
                tags = [t for t in list(tags_raw) if isinstance(t, str)]
            except Exception:
                tags = []

        kind = None
        for t in tags:
            if t.startswith("wm:kind:"):
                kind = t.split(":", 2)[2]
                break

        preds = sorted(t[5:] for t in tags if t.startswith("pred:"))
        cues = sorted(t[4:] for t in tags if t.startswith("cue:"))

        meta = getattr(b, "meta", None)
        wmm = meta.get("wm", {}) if isinstance(meta, dict) else {}
        pos = wmm.get("pos", {}) if isinstance(wmm, dict) else {}

        x = pos.get("x") if isinstance(pos, dict) else None
        y = pos.get("y") if isinstance(pos, dict) else None
        frame = pos.get("frame") if isinstance(pos, dict) else None

        dist_m = wmm.get("dist_m") if isinstance(wmm, dict) else None
        dist_class = wmm.get("dist_class") if isinstance(wmm, dict) else None
        last_seen = wmm.get("last_seen_step") if isinstance(wmm, dict) else None
        patch_refs = wmm.get("patch_refs") if isinstance(wmm, dict) else None

        rec: dict[str, Any] = {
            "eid": eid,
            "kind": kind,
            "pos": {
                "x": _as_float(x),
                "y": _as_float(y),
                "frame": str(frame) if isinstance(frame, str) else None,
            },
            "dist_m": _as_float(dist_m),
            "dist_class": str(dist_class) if isinstance(dist_class, str) else None,
            "last_seen_step": _as_int(last_seen),
            "preds": preds,
            "cues": cues,
        }

        if isinstance(patch_refs, list):
            # patch_refs are JSON-safe dicts (sig/engram_id/role/frame/tags).
            rec["patch_refs"] = patch_refs

        if include_internal_ids:
            rec["bid"] = bid
        return rec

    # ---- entities ----
    entities: list[dict[str, Any]] = []
    try:
        # stable order: self first, then alphabetical by eid
        eids = sorted([e for e in ent_map.keys() if isinstance(e, str)])
        if "self" in eids:
            eids.remove("self")
            eids = ["self"] + eids

        for eid in eids:
            bid = ent_map.get(eid)
            if not isinstance(bid, str):
                continue
            entities.append(_entity_record(eid, bid))
    except Exception:
        entities = []

    # ---- relations (distance_to edges) ----
    relations: list[dict[str, Any]] = []
    try:
        if isinstance(self_bid, str) and self_bid in getattr(ww, "_bindings", {}):  # pylint: disable=protected-access
            bself = ww._bindings.get(self_bid)  # pylint: disable=protected-access
            edges = getattr(bself, "edges", []) or []
            if isinstance(edges, list):
                for e in edges:
                    if not isinstance(e, dict):
                        continue
                    lab = e.get("label") or e.get("rel") or e.get("relation")
                    if lab != "distance_to":
                        continue

                    dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    if not isinstance(dst, str):
                        continue

                    em = e.get("meta")
                    em = em if isinstance(em, dict) else {}
                    meters = em.get("meters")
                    cls = em.get("class")
                    frame = em.get("frame")

                    dst_eid = bid_to_eid.get(dst) or "(unknown)"
                    rel_rec: dict[str, Any] = {
                        "rel": "distance_to",
                        "src": "self",
                        "dst": dst_eid,
                        "meters": _as_float(meters),
                        "class": str(cls) if isinstance(cls, str) else None,
                        "frame": str(frame) if isinstance(frame, str) else None,
                    }
                    if include_internal_ids:
                        rel_rec["src_bid"] = self_bid
                        rel_rec["dst_bid"] = dst
                    relations.append(rel_rec)
    except Exception:
        relations = []

    return {
        "schema": "wm_mapsurface_v1",
        "header": header,
        "entities": entities,
        "relations": relations,
    }


def mapsurface_payload_sig_v1(payload: dict[str, Any], *, stage: Optional[str] = None, zone: Optional[str] = None) -> str:
    """Stable content signature for MapSurface snapshots (used for dedup vs last).

    Important:
      - excludes volatile header fields (steps/ticks/tvec/etc)
      - excludes volatile per-entity recency (last_seen_step)
      - includes stage/zone *if provided* (so you can choose whether those differentiate snapshots)

    Rationale:
      - In closed-loop runs, entities get "seen again" every tick. If we include last_seen_step, the
        signature changes every step even when the scene is otherwise identical, defeating dedup.
    """
    ents_in = payload.get("entities", []) or []
    ents_norm: list[dict[str, Any]] = []
    for ent in ents_in:
        if isinstance(ent, dict):
            d = dict(ent)
            d.pop("last_seen_step", None)  # volatile per-tick recency
            ents_norm.append(d)
        else:
            # Extremely defensive fallback; should not happen in normal paths.
            ents_norm.append({"_raw": str(ent)})

    core = {
        "schema": payload.get("schema"),
        "stage": stage,
        "zone": zone,
        "entities": ents_norm,
        "relations": payload.get("relations", []),
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_SALIENT_PRED_PREFIXES = (
    "posture:",
    "proximity:mom:",
    "proximity:shelter:",
    "hazard:cliff:",
    "nipple:",
    "milk:",
)


_SALIENT_PRED_EXACT = {
    "resting",
    "alert",
    "seeking_mom",
}


def mapsurface_salience_v1(payload: dict[str, Any], *, max_preds: int = 32, max_cues: int = 32) -> dict[str, Any]:
    """Extract a compact salience signature from a wm_mapsurface_v1 payload.

    Purpose:
      - Give us a small, robust descriptor we can store in Column meta for retrieval scoring.
      - This is NOT an embedding; it's a tiny "bag of salient symbols" for overlap scoring.

    Returns:
      {
        "sig": <hex16>,
        "preds": [<salient pred tokens>],
        "cues":  [<salient cue tokens>],
      }
    """
    preds_set: set[str] = set()
    cues_set: set[str] = set()

    ents = payload.get("entities", [])
    if isinstance(ents, list):
        for ent in ents:
            if not isinstance(ent, dict):
                continue

            preds = ent.get("preds")
            if isinstance(preds, list):
                for p in preds:
                    if not isinstance(p, str) or not p:
                        continue
                    if (p in _SALIENT_PRED_EXACT) or any(p.startswith(pref) for pref in _SALIENT_PRED_PREFIXES):
                        preds_set.add(p)

            cues = ent.get("cues")
            if isinstance(cues, list):
                for c in cues:
                    if isinstance(c, str) and c:
                        cues_set.add(c)

    # Full (uncapped) lists used for signature stability
    preds_full = sorted(preds_set)
    cues_full = sorted(cues_set)

    blob = json.dumps({"preds": preds_full, "cues": cues_full}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig16 = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    # Capped lists stored in meta for readability
    preds_out = preds_full[: max(1, int(max_preds))]
    cues_out = cues_full[: max(1, int(max_cues))]

    return {"sig": sig16, "preds": preds_out, "cues": cues_out}


def current_mapsurface_salience_v1(ctx: Ctx) -> dict[str, Any]:
    """Compute the current salience signature from the live WorkingMap.MapSurface."""
    try:
        payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return mapsurface_salience_v1(payload)


def store_mapsurface_snapshot_v1(world, ctx: Ctx, *, reason: str, attach: str = "now",
                                force: bool = False, quiet: bool = False) -> dict[str, Any]:
    """Store the current WorkingMap.MapSurface snapshot into Column memory and index it in WorldGraph.

    What gets written:
      1) Column engram payload: serialize_mapsurface_v1(ctx) (JSON-safe dict)
      2) WorldGraph binding: a thin pointer node tagged cue:wm:mapsurface_snapshot + index tags
         with engram pointer attached under binding.engrams["column01"]["id"].

    Dedup:
      - If the content signature matches ctx.wm_mapsurface_last_sig, we skip storing unless force=True.
    """
    payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)

    # Index attributes (best-effort)
    stage = getattr(ctx, "lt_obs_last_stage", None)
    if not isinstance(stage, str):
        stage = None

    try:
        zone = body_space_zone(ctx)
    except Exception:
        zone = None
    if not isinstance(zone, str):
        zone = None

    sig = mapsurface_payload_sig_v1(payload, stage=stage, zone=zone)
    sal = mapsurface_salience_v1(payload)
    sal_sig = sal.get("sig")
    sal_preds = sal.get("preds", []) if isinstance(sal.get("preds"), list) else []
    sal_cues  = sal.get("cues", []) if isinstance(sal.get("cues"), list) else []
    last_sig = getattr(ctx, "wm_mapsurface_last_sig", None)

    if (not force) and (sig == last_sig):
        return {"stored": False, "why": "dedup_same_as_last", "sig": sig, "stage": stage, "zone": zone}

    # Create a thin WorldGraph index binding (always new; no semantic reuse)
    tags = {"cue:wm:mapsurface_snapshot"}
    if stage:
        tags.add(f"idx:stage:{stage}")
    if zone:
        tags.add(f"idx:zone:{zone}")

    meta = {
        "wm": {
            "kind": "mapsurface_snapshot",
            "schema": payload.get("schema"),
            "sig": sig,
            "stage": stage,
            "zone": zone,
            "reason": reason,
            "salience_sig": sal_sig,
            "salient_pred_n": len(sal_preds),
            "salient_cue_n": len(sal_cues),
        }
    }

    bid = world.add_binding(set(tags), meta=meta)

    att = (attach or "").strip().lower() or None
    if att in (None, "none"):
        pass
    elif att == "now":
        src = world.ensure_anchor("NOW")
        world.add_edge(src, bid, label="then", meta={"kind": "wm_mapsurface_snapshot", "reason": reason})
    else:
        raise ValueError("attach must be None|'now'|'none'")

    # Store engram in Column + attach pointer to the WorldGraph binding

    attrs = {
        "schema": payload.get("schema"),
        "sig": sig,
        "stage": stage,
        "zone": zone,
        "reason": reason,
        "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
        "ticks": int(getattr(ctx, "ticks", 0) or 0),
        "boundary_no": int(getattr(ctx, "boundary_no", 0) or 0),
        "boundary_vhash64": getattr(ctx, "boundary_vhash64", None),
        "salience_sig": sal_sig,
        "salient_preds": list(sal_preds),
        "salient_cues": list(sal_cues),
    }
    fm = FactMeta(name="wm_mapsurface", links=[bid], attrs=attrs)

    engram_id = column_mem.assert_fact("wm_mapsurface", cast(Any, payload), fm)
    world.attach_engram(bid, column="column01", engram_id=engram_id, act=1.0)

    # Update ctx "last"
    ctx.wm_mapsurface_last_sig = sig
    ctx.wm_mapsurface_last_engram_id = engram_id
    ctx.wm_mapsurface_last_world_bid = bid

    if not quiet:
        print(f"[wm->column] stored wm_mapsurface: sig={sig[:16]} bid={bid} engram_id={engram_id[:16]}... stage={stage} zone={zone}")

    return {"stored": True, "sig": sig, "bid": bid, "engram_id": engram_id, "stage": stage, "zone": zone}


def _wm_entity_anchor_name(entity_id: str) -> str:
    """Return the WorkingMap anchor name for an entity id (must match the MapSurface naming scheme)."""
    eid = (entity_id or "unknown").strip().lower()
    if eid == "self":
        return "WM_SELF"

    # Match inject_obs_into_working_world._sanitize_entity_anchor semantics:
    s = eid.strip().upper()
    out: list[str] = []
    for ch in s:
        out.append(ch if ch.isalnum() else "_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    s = s.strip("_") or "UNKNOWN"
    return f"WM_ENT_{s}"


def _wm_tagset_of(world, bid: str) -> set[str]:
    """Return a mutable tag set for a binding (robust to legacy list tags)."""
    b = getattr(world, "_bindings", {}).get(bid)
    if not b:
        return set()
    ts = getattr(b, "tags", None)
    if ts is None:
        b.tags = set()
        return b.tags
    if isinstance(ts, set):
        return ts
    if isinstance(ts, list):
        s = set(ts)
        b.tags = s
        return s
    try:
        s = set(ts)
        b.tags = s
        return s
    except Exception:
        b.tags = set()
        return b.tags


def _wm_upsert_edge(world, src: str, dst: str, label: str, meta: dict | None = None) -> None:
    """Upsert an edge in a WorldGraph-like object (used for WorkingMap structural edges)."""
    b = getattr(world, "_bindings", {}).get(src)
    if not b:
        return
    edges = getattr(b, "edges", None)
    if not isinstance(edges, list):
        b.edges = []
        edges = b.edges

    for e in edges:
        if not isinstance(e, dict):
            continue
        to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
        lab = e.get("label") or e.get("rel") or e.get("relation")
        if to_ == dst and lab == label:
            if isinstance(meta, dict) and meta:
                em = e.get("meta")
                if isinstance(em, dict):
                    em.update(meta)
                else:
                    e["meta"] = dict(meta)
            return

    edges.append({"to": dst, "label": label, "meta": dict(meta or {})})


def _rec_stage_zone(rec: dict) -> tuple[str | None, str | None]:
    """Extract (stage, zone) from a Column record dict."""
    meta = rec.get("meta", {})
    meta = meta if isinstance(meta, dict) else {}
    attrs = meta.get("attrs", {})
    attrs = attrs if isinstance(attrs, dict) else {}
    stage = attrs.get("stage")
    zone = attrs.get("zone")
    stage = stage if isinstance(stage, str) else None
    zone = zone if isinstance(zone, str) else None
    return stage, zone


def _wm_snapshot_pointer_bids(long_world, *, max_scan: int = 500) -> list[str]:
    """Return newest-first WorldGraph binding ids that act as MapSurface snapshot pointers.

    Pointer node definition (Option B):
      - binding tags contain: 'cue:wm:mapsurface_snapshot'
      - binding.engrams contains a column pointer to the stored engram id
    """
    if long_world is None:
        return []

    # Collect pointer bindings
    out: list[str] = []
    try:
        for bid, b in getattr(long_world, "_bindings", {}).items():
            tags = getattr(b, "tags", None) or []
            if isinstance(tags, set):
                ok = "cue:wm:mapsurface_snapshot" in tags
            else:
                ok = any(isinstance(t, str) and t == "cue:wm:mapsurface_snapshot" for t in tags)
            if ok:
                out.append(bid)
    except Exception:
        return []

    # Sort newest-first by numeric bN (unknown ids at end)
    def _bid_key_desc(bid: str) -> tuple[int, int]:
        if isinstance(bid, str) and bid.startswith("b") and bid[1:].isdigit():
            return (0, -int(bid[1:]))
        return (1, 0)

    out.sort(key=_bid_key_desc)
    return out[: max(1, int(max_scan))]


def _wm_pointer_engram_id(long_world, pointer_bid: str) -> str | None:
    """Extract the engram id from a WorldGraph pointer binding (best-effort)."""
    try:
        b = getattr(long_world, "_bindings", {}).get(pointer_bid)
        if b is None:
            return None
        eng = getattr(b, "engrams", None)
        if not isinstance(eng, dict) or not eng:
            return None

        # Prefer the canonical slot name, else fall back to the first slot.
        v = eng.get("column01")
        if not isinstance(v, dict):
            try:
                v = next(iter(eng.values()))
            except Exception:
                v = None
        if isinstance(v, dict):
            eid = v.get("id")
            return eid if isinstance(eid, str) and eid else None
    except Exception:
        return None
    return None


def _iter_newest_wm_mapsurface_recs(*, long_world=None, limit: int = 500) -> tuple[list[dict], str]:
    """Return newest-first wm_mapsurface Column records, preferably via WorldGraph pointers.

    Returns (recs, source) where source ∈ {"world_pointers","column_scan"}.
    """
    lim = max(1, int(limit))

    # Prefer WorldGraph pointer nodes (fast index)
    if long_world is not None:
        seen: set[str] = set()
        recs: list[dict] = []
        for pbid in _wm_snapshot_pointer_bids(long_world, max_scan=lim * 2):
            eid = _wm_pointer_engram_id(long_world, pbid)
            if not isinstance(eid, str) or not eid or eid in seen:
                continue
            seen.add(eid)
            rec = column_mem.try_get(eid)
            if isinstance(rec, dict) and rec.get("name") == "wm_mapsurface":
                recs.append(rec)
                if len(recs) >= lim:
                    return recs, "world_pointers"
        if recs:
            return recs, "world_pointers"

    # no resolvable pointer engrams -> fallback to column scan
    # Fallback: scan column ids newest-first
    out: list[dict] = []
    try:
        ids = list(column_mem.list_ids())
        for eid in reversed(ids):
            rec = column_mem.try_get(eid)
            if not isinstance(rec, dict):
                continue
            if rec.get("name") != "wm_mapsurface":
                continue
            out.append(rec)
            if len(out) >= lim:
                break
    except Exception:
        out = []
    return out, "column_scan"


def pick_best_wm_mapsurface_rec(*, stage: str | None, zone: str | None, ctx: Ctx | None = None,
                               long_world=None, allow_fallback: bool = True, max_scan: int = 500,
                               top_k: int = 5) -> dict[str, Any]:
    """Pick the best wm_mapsurface record for (stage, zone), using WorldGraph pointers + salience overlap.

    Changes in B6:
      - Candidate source prefers WorldGraph pointer bindings (cue:wm:mapsurface_snapshot), then loads Column records.
      - Returns ranked top-K candidates (not just the winner) for inspection.

    Returns:
      {
        "ok": bool,
        "source": "world_pointers"|"column_scan",
        "match": "stage+zone"|"stage"|"zone"|"any"|"none",
        "rec": dict|None,
        "score": float,
        "overlap_preds": int,
        "overlap_cues": int,
        "want_pred_n": int,
        "want_cue_n": int,
        "want_salience_sig": str|None,
        "cand_salience_sig": str|None,
        "ranked": [ {candidate summary dicts...} ],
        "want_stage":..., "want_zone":...
      }
    """
    recs, source = _iter_newest_wm_mapsurface_recs(long_world=long_world, limit=max(1, int(max_scan)))

    if not recs:
        return {
            "ok": False,
            "source": source,
            "match": "none",
            "rec": None,
            "want_stage": stage,
            "want_zone": zone,
            "ranked": [],
        }

    # --- Current salience (from ctx WorkingMap MapSurface) ---
    want_preds: set[str] = set()
    want_cues: set[str] = set()
    want_sig: str | None = None
    if ctx is not None:
        try:
            want = current_mapsurface_salience_v1(ctx)
            want_sig = want.get("sig") if isinstance(want.get("sig"), str) else None
            wp = want.get("preds", [])
            wc = want.get("cues", [])
            if isinstance(wp, list):
                want_preds = {p for p in wp if isinstance(p, str) and p}
            if isinstance(wc, list):
                want_cues = {c for c in wc if isinstance(c, str) and c}
        except Exception:
            pass

    def _rec_salience_sets(rec: dict) -> tuple[set[str], set[str], str | None]:
        meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
        attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}

        sp = attrs.get("salient_preds")
        sc = attrs.get("salient_cues")
        ss = attrs.get("salience_sig")
        sig = ss if isinstance(ss, str) else None

        preds_set: set[str] = set()
        cues_set: set[str] = set()

        if isinstance(sp, list):
            preds_set = {p for p in sp if isinstance(p, str) and p}
        if isinstance(sc, list):
            cues_set = {c for c in sc if isinstance(c, str) and c}

        # Back-compat: older engrams may not have salience attrs; compute from payload
        if (not preds_set and not cues_set) and isinstance(rec.get("payload"), dict):
            sal = mapsurface_salience_v1(rec["payload"])
            sig = sig or (sal.get("sig") if isinstance(sal.get("sig"), str) else None)
            preds = sal.get("preds", [])
            cues = sal.get("cues", [])
            if isinstance(preds, list):
                preds_set = {p for p in preds if isinstance(p, str) and p}
            if isinstance(cues, list):
                cues_set = {c for c in cues if isinstance(c, str) and c}

        return preds_set, cues_set, sig

    def _score_candidate(rec: dict) -> tuple[float, int, int, str | None]:
        preds_set, cues_set, cand_sig = _rec_salience_sets(rec)
        op = len(want_preds & preds_set) if want_preds else 0
        oc = len(want_cues & cues_set) if want_cues else 0
        score = float(op) * 10.0 + float(oc) * 3.0
        return score, op, oc, cand_sig

    # Candidate filtering tiers
    def _filter_stage_zone(match_kind: str) -> list[dict]:
        if match_kind == "stage+zone" and stage and zone:
            return [r for r in recs if _rec_stage_zone(r) == (stage, zone)]
        if match_kind == "stage" and stage:
            return [r for r in recs if _rec_stage_zone(r)[0] == stage]
        if match_kind == "zone" and zone:
            return [r for r in recs if _rec_stage_zone(r)[1] == zone]
        if match_kind == "any":
            return list(recs)
        return []

    def _candidate_summary(rec: dict, *, score: float, op: int, oc: int, cand_sig: str | None) -> dict[str, Any]:
        meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
        attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}
        created_at = meta.get("created_at") or "(n/a)"

        links = meta.get("links")
        src = links[0] if isinstance(links, list) and links else None

        return {
            "engram_id": str(rec.get("id", "")),
            "created_at": created_at,
            "stage": attrs.get("stage"),
            "zone": attrs.get("zone"),
            "sig": attrs.get("sig"),
            "salience_sig": attrs.get("salience_sig"),
            "src": src,
            "score": float(score),
            "overlap_preds": int(op),
            "overlap_cues": int(oc),
            "cand_salience_sig": cand_sig,
        }

    k = max(1, min(10, int(top_k)))  # keep terminal readable
    tier_order = ["stage+zone", "stage", "zone", "any"] if allow_fallback else ["stage+zone"]

    for tier in tier_order:
        cands = _filter_stage_zone(tier)
        if not cands:
            continue

        scored: list[tuple[float, int, int, str | None, int, dict]] = []
        # preserve recency tie-break: cands is newest-first, so lower idx = newer
        for idx, rec in enumerate(cands):
            score, op, oc, cand_sig = _score_candidate(rec)
            scored.append((score, op, oc, cand_sig, idx, rec))

        scored.sort(key=lambda t: (-t[0], t[4]))  # high score first, then newest
        top = scored[:k]

        best = top[0]
        best_score, best_op, best_oc, best_csig, _best_idx, best_rec = best

        ranked = [_candidate_summary(r, score=s, op=op, oc=oc, cand_sig=csig) for (s, op, oc, csig, _i, r) in top]

        return {
            "ok": True,
            "source": source,
            "match": tier,
            "rec": best_rec,
            "score": float(best_score),
            "overlap_preds": int(best_op),
            "overlap_cues": int(best_oc),
            "want_pred_n": len(want_preds),
            "want_cue_n": len(want_cues),
            "want_salience_sig": want_sig,
            "cand_salience_sig": best_csig,
            "ranked": ranked,
            "want_stage": stage,
            "want_zone": zone,
        }

    return {"ok": False, "source": source, "match": "none", "rec": None, "want_stage": stage, "want_zone": zone, "ranked": []}


def load_mapsurface_payload_v1_into_workingmap(ctx: Ctx, payload: dict[str, Any], *, replace: bool = True, reason: str = "manual_load") -> dict[str, Any]:
    """Load a wm_mapsurface_v1 payload into WorkingMap MapSurface.

    Semantics (Option B4 v1):
      - replace=True: clear WorkingMap, then rebuild MapSurface exactly from payload.
      - This is a *prior/seed*; the next EnvObservation tick may overwrite parts of it.

    Returns: {"ok": bool, "entities": int, "relations": int}.
    """
    if replace:
        reset_working_world(ctx)

    if getattr(ctx, "working_world", None) is None:
        ctx.working_world = init_working_world()
    ww = ctx.working_world
    if ww is None:
        return {"ok": False, "entities": 0, "relations": 0}

    # Ensure MapSurface roots exist
    root_bid = ww.ensure_anchor("WM_ROOT")
    try:
        ww.set_now(root_bid, tag=True, clean_previous=True)
    except Exception:
        try:
            ww._anchors["NOW"] = root_bid
            _wm_tagset_of(ww, root_bid).add("anchor:NOW")
        except Exception:
            pass

    # Keep NOW_ORIGIN aligned (same pattern as inject_obs_into_working_world)
    try:
        ww._anchors["NOW_ORIGIN"] = root_bid
        _wm_tagset_of(ww, root_bid).add("anchor:NOW_ORIGIN")
    except Exception:
        pass

    # Scratch + Creative anchors and links
    scratch_bid = ww.ensure_anchor("WM_SCRATCH")
    _wm_tagset_of(ww, scratch_bid).add("wm:scratch")
    _wm_upsert_edge(ww, root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_load", "reason": reason})

    creative_bid = ww.ensure_anchor("WM_CREATIVE")
    _wm_tagset_of(ww, creative_bid).add("wm:creative")
    _wm_upsert_edge(ww, root_bid, creative_bid, "wm_creative", {"created_by": "wm_load", "reason": reason})

    # Reset MapSurface caches
    try:
        ctx.wm_entities.clear()
        ctx.wm_last_env_cues.clear()
    except Exception:
        pass

    # Entities
    ents = payload.get("entities", [])
    if not isinstance(ents, list):
        ents = []

    n_ent = 0
    for ent in ents:
        if not isinstance(ent, dict):
            continue
        eid_raw = ent.get("eid")
        if not isinstance(eid_raw, str) or not eid_raw.strip():
            continue
        eid = eid_raw.strip().lower()
        kind = ent.get("kind")
        kind = kind if isinstance(kind, str) else None

        anchor_name = _wm_entity_anchor_name(eid)
        bid = ww.ensure_anchor(anchor_name)

        # cache mapping
        try:
            ctx.wm_entities[eid] = bid
        except Exception:
            pass

        tags = _wm_tagset_of(ww, bid)

        # remove old MapSurface tags (keep anchor:* tags)
        for t in list(tags):
            if isinstance(t, str) and (t.startswith("wm:") or t.startswith("pred:") or t.startswith("cue:")):
                tags.discard(t)

        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")
        if kind:
            tags.add(f"wm:kind:{kind}")

        preds = ent.get("preds")
        if isinstance(preds, list):
            for p in preds:
                if isinstance(p, str) and p:
                    tags.add(f"pred:{p}")

        cues = ent.get("cues")
        cue_full_tags: set[str] = set()
        if isinstance(cues, list):
            for c in cues:
                if isinstance(c, str) and c:
                    tags.add(f"cue:{c}")
                    cue_full_tags.add(f"cue:{c}")

        # meta.wm
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is not None:
            if not isinstance(getattr(b, "meta", None), dict):
                b.meta = {}
            wmm = b.meta.setdefault("wm", {})
            if isinstance(wmm, dict):
                pos = ent.get("pos")
                if isinstance(pos, dict):
                    x = pos.get("x")
                    y = pos.get("y")
                    frame = pos.get("frame")
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                        wmm["pos"] = {
                            "x": float(x),
                            "y": float(y),
                            "frame": frame if isinstance(frame, str) and frame else "wm_schematic_v1",
                        }

                dist_m = ent.get("dist_m")
                if isinstance(dist_m, (int, float)):
                    wmm["dist_m"] = float(dist_m)

                dist_class = ent.get("dist_class")
                if isinstance(dist_class, str) and dist_class:
                    wmm["dist_class"] = dist_class

                # Mark as fresh "seen" now (avoid confusing recency across sessions)
                wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)
                wmm["loaded_from"] = "wm_mapsurface_v1"
                wmm["load_reason"] = reason

        # root membership
        _wm_upsert_edge(ww, root_bid, bid, "wm_entity", {"created_by": "wm_load", "reason": reason})

        # cue cache for next env injection
        if cue_full_tags:
            try:
                ctx.wm_last_env_cues[eid] = set(cue_full_tags)
            except Exception:
                pass

        n_ent += 1

    # Relations (distance_to)
    rels = payload.get("relations", [])
    if not isinstance(rels, list):
        rels = []

    n_rel = 0
    self_bid = (getattr(ctx, "wm_entities", {}) or {}).get("self")
    for r in rels:
        if not isinstance(r, dict):
            continue
        if r.get("rel") != "distance_to":
            continue
        if r.get("src") != "self":
            continue
        dst = r.get("dst")
        if not isinstance(dst, str) or not dst.strip():
            continue
        dst_eid = dst.strip().lower()
        dst_bid = (getattr(ctx, "wm_entities", {}) or {}).get(dst_eid)

        if not (isinstance(self_bid, str) and isinstance(dst_bid, str)):
            continue

        em: dict[str, Any] = {"created_by": "wm_load", "reason": reason}
        meters = r.get("meters")
        if isinstance(meters, (int, float)):
            em["meters"] = float(meters)
        cls = r.get("class")
        if isinstance(cls, str) and cls:
            em["class"] = cls
        frame = r.get("frame")
        if isinstance(frame, str) and frame:
            em["frame"] = frame

        _wm_upsert_edge(ww, self_bid, dst_bid, "distance_to", em)
        n_rel += 1

    return {"ok": True, "entities": n_ent, "relations": n_rel}


def merge_mapsurface_payload_v1_into_workingmap(ctx: Ctx, payload: dict[str, Any], *, reason: str = "manual_merge") -> dict[str, Any]:
    """Merge/seed a wm_mapsurface_v1 payload into the current WorkingMap.MapSurface (conservative prior).

    Design intent:
      - Do NOT clear WorkingMap.
      - Do NOT delete or overwrite existing observed slot families.
      - Do NOT add cue:* tags (cues mean 'present now'); store cues in meta as 'prior_cues' instead.

    Returns:
      {"ok": bool, "added_entities": int, "filled_slots": int, "added_edges": int, "stored_prior_cues": int}
    """
    if getattr(ctx, "working_world", None) is None:
        ctx.working_world = init_working_world()
    ww = ctx.working_world
    if ww is None:
        return {"ok": False, "added_entities": 0, "filled_slots": 0, "added_edges": 0, "stored_prior_cues": 0}

    # Ensure MapSurface roots exist (do not clear anything)
    root_bid = ww.ensure_anchor("WM_ROOT")
    try:
        ww.set_now(root_bid, tag=True, clean_previous=True)
    except Exception:
        pass

    # Ensure Scratch + Creative exist (structural)
    scratch_bid = ww.ensure_anchor("WM_SCRATCH")
    _wm_tagset_of(ww, scratch_bid).add("wm:scratch")
    _wm_upsert_edge(ww, root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_merge", "reason": reason})

    creative_bid = ww.ensure_anchor("WM_CREATIVE")
    _wm_tagset_of(ww, creative_bid).add("wm:creative")
    _wm_upsert_edge(ww, root_bid, creative_bid, "wm_creative", {"created_by": "wm_merge", "reason": reason})

    # Rebuild ctx.wm_entities cache if empty (best-effort scan)
    try:
        if not getattr(ctx, "wm_entities", {}):
            for bid, b in getattr(ww, "_bindings", {}).items():
                tags = getattr(b, "tags", []) or []
                for t in tags:
                    if isinstance(t, str) and t.startswith("wm:eid:"):
                        eid = t.split(":", 2)[2].strip().lower()
                        if eid:
                            ctx.wm_entities[eid] = bid
    except Exception:
        pass


    def _pred_family(tok: str) -> str:
        if not isinstance(tok, str) or not tok:
            return ""
        return tok.rsplit(":", 1)[0] if ":" in tok else tok


    def _has_slot_family(tags: set[str], family: str) -> bool:
        """Return True if tags already contain any pred:* token in this slot family.

        Examples:
          family="posture"        matches pred:posture:standing, pred:posture:fallen
          family="proximity:mom"  matches pred:proximity:mom:close, pred:proximity:mom:far
          family="resting"        matches pred:resting (exact token)
        """
        if not family:
            return False

        # Exact token case (e.g., pred:resting)
        if f"pred:{family}" in tags:
            return True

        # Family-prefix case (e.g., pred:posture:*)
        pref = f"pred:{family}:"
        return any(isinstance(t, str) and t.startswith(pref) for t in tags)


    def _has_edge(src: str, dst: str, label: str) -> bool:
        b = getattr(ww, "_bindings", {}).get(src)
        if not b:
            return False
        edges = getattr(b, "edges", []) or []
        if not isinstance(edges, list):
            return False
        for e in edges:
            if not isinstance(e, dict):
                continue
            to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            lab = e.get("label") or e.get("rel") or e.get("relation")
            if to_ == dst and lab == label:
                return True
        return False

    ents = payload.get("entities", [])
    if not isinstance(ents, list):
        ents = []

    added_entities = 0
    filled_slots = 0
    stored_prior_cues = 0

    # Entities: create if missing; else fill missing slot families only.
    for ent in ents:
        if not isinstance(ent, dict):
            continue
        eid_raw = ent.get("eid")
        if not isinstance(eid_raw, str) or not eid_raw.strip():
            continue
        eid = eid_raw.strip().lower()

        kind = ent.get("kind")
        kind = kind if isinstance(kind, str) else None

        bid = (getattr(ctx, "wm_entities", {}) or {}).get(eid)
        if not (isinstance(bid, str) and bid in getattr(ww, "_bindings", {})):
            # Create / ensure anchor
            bid = ww.ensure_anchor(_wm_entity_anchor_name(eid))
            ctx.wm_entities[eid] = bid
            added_entities += 1

        tags = _wm_tagset_of(ww, bid)
        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")

        # Only set kind if missing (do not fight existing kind tags)
        if kind and not any(isinstance(t, str) and t.startswith("wm:kind:") for t in tags):
            tags.add(f"wm:kind:{kind}")

        # Ensure membership under WM_ROOT
        _wm_upsert_edge(ww, root_bid, bid, "wm_entity", {"created_by": "wm_merge", "reason": reason})

        # meta.wm fill (only if missing)
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is not None:
            if not isinstance(getattr(b, "meta", None), dict):
                b.meta = {}
            wmm = b.meta.setdefault("wm", {})
            if isinstance(wmm, dict):
                pos = ent.get("pos")
                if "pos" not in wmm and isinstance(pos, dict):
                    x = pos.get("x"); y = pos.get("y"); frame = pos.get("frame")
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                        wmm["pos"] = {"x": float(x), "y": float(y), "frame": frame if isinstance(frame, str) and frame else "wm_schematic_v1"}

                if "dist_m" not in wmm:
                    dist_m = ent.get("dist_m")
                    if isinstance(dist_m, (int, float)):
                        wmm["dist_m"] = float(dist_m)

                if "dist_class" not in wmm:
                    dist_class = ent.get("dist_class")
                    if isinstance(dist_class, str) and dist_class:
                        wmm["dist_class"] = dist_class

                # recency marker always refreshed
                wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)
                wmm["loaded_from"] = "wm_mapsurface_v1"
                wmm["load_reason"] = reason

                # Store cues as "prior_cues" (do NOT add cue:* tags in merge mode)
                cues = ent.get("cues")
                if isinstance(cues, list) and cues:
                    prior = wmm.setdefault("prior_cues", [])
                    if isinstance(prior, list):
                        for c in cues:
                            if isinstance(c, str) and c and c not in prior:
                                prior.append(c)
                                stored_prior_cues += 1

        # Predicates: only fill slot families that are missing
        preds = ent.get("preds")
        if isinstance(preds, list):
            for p in preds:
                if not isinstance(p, str) or not p:
                    continue
                fam = _pred_family(p)
                if _has_slot_family(tags, fam):
                    continue
                tags.add(f"pred:{p}")
                filled_slots += 1

    # Relations: add missing distance_to edges only
    rels = payload.get("relations", [])
    if not isinstance(rels, list):
        rels = []

    added_edges = 0
    self_bid = (getattr(ctx, "wm_entities", {}) or {}).get("self")
    for r in rels:
        if not isinstance(r, dict):
            continue
        if r.get("rel") != "distance_to" or r.get("src") != "self":
            continue
        dst = r.get("dst")
        if not isinstance(dst, str) or not dst.strip():
            continue
        dst_eid = dst.strip().lower()
        dst_bid = (getattr(ctx, "wm_entities", {}) or {}).get(dst_eid)
        if not (isinstance(self_bid, str) and isinstance(dst_bid, str)):
            continue

        if _has_edge(self_bid, dst_bid, "distance_to"):
            continue

        em: dict[str, Any] = {"created_by": "wm_merge", "reason": reason}
        meters = r.get("meters")
        if isinstance(meters, (int, float)):
            em["meters"] = float(meters)
        cls = r.get("class")
        if isinstance(cls, str) and cls:
            em["class"] = cls
        frame = r.get("frame")
        if isinstance(frame, str) and frame:
            em["frame"] = frame

        _wm_upsert_edge(ww, self_bid, dst_bid, "distance_to", em)
        added_edges += 1

    return {
        "ok": True,
        "added_entities": added_entities,
        "filled_slots": filled_slots,
        "added_edges": added_edges,
        "stored_prior_cues": stored_prior_cues,
    }


def _wm_count_cue_tags_v1(world) -> int:
    """Count cue:* tags currently present in a WorldGraph.

    This is used as a lightweight guardrail check for merge/seed mode:
    merge should preserve prior cues in metadata, but should not leak them
    back into live cue:* tags as if they were observed "now".
    """
    if world is None:
        return 0

    n = 0
    try:
        bindings = getattr(world, "_bindings", {})
        if isinstance(bindings, dict):
            for b in bindings.values():
                tags = getattr(b, "tags", None)
                if not isinstance(tags, list):
                    continue
                for t in tags:
                    if isinstance(t, str) and t.startswith("cue:"):
                        n += 1
    except Exception:
        return 0

    return int(n)


def _wm_mapswitch_candidate_view_v1(cand: dict[str, Any]) -> dict[str, Any]:
    """Return a small JSON-safe candidate summary for map-switch logs."""
    if not isinstance(cand, dict):
        return {}

    out: dict[str, Any] = {}

    eid = cand.get("engram_id")
    if isinstance(eid, str) and eid:
        out["engram_id"] = eid

    for key in ("stage", "zone", "sig", "salience_sig", "src", "cand_salience_sig"):
        val = cand.get(key)
        if isinstance(val, str) and val:
            out[key] = val

    for key in ("score",):
        val = cand.get(key)
        if isinstance(val, (int, float)):
            out[key] = float(val)

    for key in ("overlap_preds", "overlap_cues"):
        val = cand.get(key)
        if isinstance(val, int):
            out[key] = int(val)

    return out


def _wm_mapswitch_ranked_view_v1(ranked: list[dict[str, Any]], *, limit: int = 5) -> list[dict[str, Any]]:
    """Return a bounded list of candidate summaries for event logs."""
    out: list[dict[str, Any]] = []
    if not isinstance(ranked, list):
        return out

    lim = max(1, min(10, int(limit)))
    for cand in ranked[:lim]:
        if isinstance(cand, dict):
            row = _wm_mapswitch_candidate_view_v1(cand)
            if row:
                out.append(row)
    return out


def _wm_log_mapswitch_event_v1(
    ctx: Ctx,
    *,
    ok: bool,
    why: str,
    reason: str | None,
    stage: str | None,
    zone: str | None,
    mode: str,
    source: str | None,
    match: str | None,
    top_k: int,
    exclude_engram_id: str | None = None,
    ranked: list[dict[str, Any]] | None = None,
    chosen: dict[str, Any] | None = None,
    load: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Append one structured map-switch event to ctx.

    Event semantics
    ---------------
    - `candidates`: the ranked candidates that were considered
    - `chosen_seed`: the candidate actually chosen (if any)
    - `drop_reason`: why the top/default candidate was skipped or why no-op occurred
    - `load`: compact summary of the merge/replace application and cue-leakage guardrail

    The event is JSON-safe and intentionally small enough to store in per-cycle traces.
    """
    ranked_rows = _wm_mapswitch_ranked_view_v1(ranked or [], limit=max(1, min(10, int(top_k))))
    chosen_row = _wm_mapswitch_candidate_view_v1(chosen) if isinstance(chosen, dict) else None
    if not chosen_row:
        chosen_row = None

    chosen_rank: int | None = None
    if isinstance(chosen_row, dict):
        chosen_id = chosen_row.get("engram_id")
        if isinstance(chosen_id, str):
            for idx, row in enumerate(ranked_rows, start=1):
                if row.get("engram_id") == chosen_id:
                    chosen_rank = idx
                    break

    drop_reason: str | None = None
    top_id = None
    if ranked_rows:
        raw_top = ranked_rows[0].get("engram_id")
        top_id = raw_top if isinstance(raw_top, str) and raw_top else None

    if isinstance(exclude_engram_id, str) and exclude_engram_id and top_id == exclude_engram_id:
        drop_reason = "excluded_current_snapshot"

    if (not ok) and not drop_reason:
        drop_reason = why if isinstance(why, str) and why else None

    load_view: dict[str, Any] = {}
    if isinstance(load, dict):
        for key in (
            "mode",
            "added_entities",
            "filled_slots",
            "added_edges",
            "stored_prior_cues",
            "entities",
            "relations",
            "cue_tags_before",
            "cue_tags_after",
            "cue_tag_delta",
            "merge_guardrail_ok",
        ):
            if key in load:
                load_view[key] = load.get(key)

    event = {
        "schema": "wm_mapswitch_event_v1",
        "step": int(getattr(ctx, "controller_steps", 0) or 0),
        "ok": bool(ok),
        "why": str(why or ""),
        "reason": reason if isinstance(reason, str) and reason else None,
        "stage": stage if isinstance(stage, str) and stage else None,
        "zone": zone if isinstance(zone, str) and zone else None,
        "mode": str(mode or "merge"),
        "source": source if isinstance(source, str) and source else None,
        "match": match if isinstance(match, str) and match else None,
        "top_k": int(top_k),
        "exclude_engram_id": exclude_engram_id if isinstance(exclude_engram_id, str) and exclude_engram_id else None,
        "candidate_count": int(len(ranked_rows)),
        "candidates": ranked_rows,
        "chosen_seed": chosen_row,
        "chosen_rank": int(chosen_rank) if isinstance(chosen_rank, int) else None,
        "drop_reason": drop_reason,
        "load": load_view,
    }

    try:
        ctx.wm_mapswitch_last_events = [event]
    except Exception:
        pass

    try:
        hist = getattr(ctx, "wm_mapswitch_history", None)
        if not isinstance(hist, list):
            hist = []
        hist.append(event)

        lim = int(getattr(ctx, "wm_mapswitch_history_limit", 50) or 50)
        lim = max(1, min(500, lim))
        if len(hist) > lim:
            del hist[:-lim]

        ctx.wm_mapswitch_history = hist
    except Exception:
        pass

    return event


def format_mapswitch_event_line_v1(event: dict[str, Any]) -> str:
    """Render a compact one-line map-switch event for terminal logs."""
    if not isinstance(event, dict) or not event:
        return "(none)"

    ok = bool(event.get("ok"))
    mode = event.get("mode")
    mode_txt = mode if isinstance(mode, str) and mode else "merge"

    match = event.get("match")
    match_txt = match if isinstance(match, str) and match else "(none)"

    try:
        cand_n = int(event.get("candidate_count", 0) or 0)
    except Exception:
        cand_n = 0

    if ok:
        chosen = event.get("chosen_seed")
        chosen_txt = "(none)"
        if isinstance(chosen, dict):
            raw = chosen.get("engram_id")
            if isinstance(raw, str) and raw:
                chosen_txt = raw[:8] + "…"

        try:
            chosen_rank = event.get("chosen_rank")
            rank_txt = str(int(chosen_rank)) if chosen_rank is not None else "n/a"
        except Exception:
            rank_txt = "n/a"

        drop = event.get("drop_reason")
        drop_txt = f" drop={drop}" if isinstance(drop, str) and drop else ""

        load = event.get("load")
        guard_txt = ""
        if isinstance(load, dict):
            guard = load.get("merge_guardrail_ok")
            delta = load.get("cue_tag_delta")
            if guard is True:
                guard_txt = " cue_guard=ok"
            elif guard is False:
                try:
                    delta_i = int(delta) if delta is not None else None
                except Exception:
                    delta_i = None
                if isinstance(delta_i, int):
                    guard_txt = f" cue_guard=leak(+{delta_i})"
                else:
                    guard_txt = " cue_guard=leak"

        return (
            f"ok mode={mode_txt} match={match_txt} cand_n={cand_n} "
            f"chosen={chosen_txt} rank={rank_txt}{drop_txt}{guard_txt}"
        )

    why = event.get("why")
    why_txt = why if isinstance(why, str) and why else "no-op"
    drop = event.get("drop_reason")
    drop_txt = f" drop={drop}" if isinstance(drop, str) and drop else ""
    return f"skip why={why_txt} mode={mode_txt} match={match_txt} cand_n={cand_n}{drop_txt}"


def load_wm_mapsurface_engram_into_workingmap_mode(ctx: Ctx, engram_id: str, *, mode: str = "replace") -> dict[str, Any]:
    """Load a Column engram (wm_mapsurface) into WorkingMap using replace or merge/seed mode.

    Extra traceability
    ------------------
    We also measure cue-tag counts before/after the load so merge/seed mode can
    prove that it did not leak cue:* tags back into the live WorkingMap.
    """
    rec = column_mem.try_get(engram_id)
    if not isinstance(rec, dict):
        return {"ok": False, "why": "no_such_engram"}

    if rec.get("name") != "wm_mapsurface":
        return {"ok": False, "why": "wrong_name"}

    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "why": "payload_not_dict"}

    cue_before = _wm_count_cue_tags_v1(getattr(ctx, "working_world", None))

    m = (mode or "replace").strip().lower()
    if m in ("merge", "seed", "merge_seed", "merge/seed"):
        out = merge_mapsurface_payload_v1_into_workingmap(ctx, payload, reason=f"engram_merge:{engram_id[:8]}")
        out["mode"] = "merge"
    else:
        out = load_mapsurface_payload_v1_into_workingmap(ctx, payload, replace=True, reason=f"engram_replace:{engram_id[:8]}")
        out["mode"] = "replace"

    cue_after = _wm_count_cue_tags_v1(getattr(ctx, "working_world", None))

    out["ok"] = True
    out["engram_id"] = engram_id
    out["cue_tags_before"] = int(cue_before)
    out["cue_tags_after"] = int(cue_after)
    out["cue_tag_delta"] = int(cue_after - cue_before)

    if out.get("mode") == "merge":
        out["merge_guardrail_ok"] = int(out.get("cue_tag_delta", 0) or 0) == 0
    else:
        out["merge_guardrail_ok"] = None

    return out


def load_wm_mapsurface_engram_into_workingmap(ctx: Ctx, engram_id: str, *, replace: bool = True) -> dict[str, Any]:
    """Load a Column engram (wm_mapsurface) into WorkingMap MapSurface."""
    rec = column_mem.try_get(engram_id)
    if not isinstance(rec, dict):
        return {"ok": False, "why": "no_such_engram", "entities": 0, "relations": 0}

    if rec.get("name") != "wm_mapsurface":
        return {"ok": False, "why": "wrong_name", "entities": 0, "relations": 0}

    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "why": "payload_not_dict", "entities": 0, "relations": 0}

    out = load_mapsurface_payload_v1_into_workingmap(ctx, payload, replace=replace, reason=f"engram:{engram_id[:8]}")
    out["engram_id"] = engram_id
    return out


# -----------------------------------------------------------------------------
# Working Memory refactor Phase 2: NavPatch, salience, SurfaceGrid, NavSummary
# -----------------------------------------------------------------------------

def _navpatch_core_v1(patch: dict[str, Any]) -> dict[str, Any]:
    """Return the stable core of a NavPatch payload for signatures/dedup.

    A NavPatch is a compact, local navigation map fragment intended to be:
      - JSON-safe (dict/list/str/int/float/bool/None only)
      - stable under repeated observation of the same structure
      - composable (map-of-maps) via links/transforms in later phases

    This helper strips volatile fields (timestamps, match traces, etc.) so the
    same structural patch yields the same signature across cycles.

    Parameters
    ----------
    patch:
        JSON-safe dict produced by PerceptionAdapter (env-side) or by later
        agent-side processing.

    Returns
    -------
    dict
        Canonicalized core dict used for hashing.
    """
    if not isinstance(patch, dict):
        return {"schema": "navpatch_v1", "error": "not_dict"}

    schema = patch.get("schema") if isinstance(patch.get("schema"), str) else "navpatch_v1"

    core: dict[str, Any] = {
        "schema": schema,
        "local_id": patch.get("local_id") if isinstance(patch.get("local_id"), str) else None,
        "entity_id": patch.get("entity_id") if isinstance(patch.get("entity_id"), str) else None,
        "role": patch.get("role") if isinstance(patch.get("role"), str) else None,
        "frame": patch.get("frame") if isinstance(patch.get("frame"), str) else None,
    }

    # Grid payload (Phase X v5.9): include topology core in the signature.
    # Signature rules: include grid_encoding_v, grid_w, grid_h, and grid_cells (or a stable digest).
    ge = patch.get("grid_encoding_v")
    if isinstance(ge, str) and ge:
        core["grid_encoding_v"] = ge

    gw = patch.get("grid_w")
    gh = patch.get("grid_h")
    if isinstance(gw, int) and isinstance(gh, int) and gw > 0 and gh > 0:
        core["grid_w"] = int(gw)
        core["grid_h"] = int(gh)

        cells = patch.get("grid_cells")
        if isinstance(cells, list) and len(cells) == int(gw) * int(gh):
            norm: list[int] = []
            ok = True
            for c in cells:
                if isinstance(c, int):
                    norm.append(int(c))
                else:
                    ok = False
                    break
            if ok:
                core["grid_cells"] = norm
            else:
                # Fallback: keep a stable digest so the signature still changes with topology.
                try:
                    blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                    core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
                except Exception:
                    pass
        elif isinstance(cells, list) and cells:
            try:
                blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            except Exception:
                pass

    # Optional (v1): origin/resolution are stable geometry parameters.
    go = patch.get("grid_origin")
    if isinstance(go, list) and len(go) == 2 and all(isinstance(v, (int, float)) for v in go):
        core["grid_origin"] = [float(go[0]), float(go[1])]
    gr = patch.get("grid_resolution")
    if isinstance(gr, (int, float)):
        core["grid_resolution"] = float(gr)

    extent = patch.get("extent")
    if isinstance(extent, dict):
        core["extent"] = {
            k: extent.get(k)
            for k in sorted(extent)
            if isinstance(k, str) and isinstance(extent.get(k), (str, int, float, bool, type(None)))
        }

    tags = patch.get("tags")
    if isinstance(tags, list):
        core["tags"] = sorted({t for t in tags if isinstance(t, str) and t})

    # --- Grid payload core (Phase X Step 11) ---
    ge = patch.get("grid_encoding_v")
    if isinstance(ge, str) and ge:
        core["grid_encoding_v"] = ge

    gw = patch.get("grid_w")
    gh = patch.get("grid_h")
    if isinstance(gw, int) and isinstance(gh, int) and gw > 0 and gh > 0:
        core["grid_w"] = int(gw)
        core["grid_h"] = int(gh)

        cells = patch.get("grid_cells")
        if isinstance(cells, list) and len(cells) == int(gw) * int(gh) and all(isinstance(c, int) for c in cells):
            # Keep explicit cells for small grids so 1-cell changes affect sig directly.
            if len(cells) <= 1024:
                core["grid_cells"] = [int(c) for c in cells]
            else:
                blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        elif isinstance(cells, list) and cells:
            blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
            core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    go = patch.get("grid_origin")
    if isinstance(go, list) and len(go) == 2 and all(isinstance(v, (int, float)) for v in go):
        core["grid_origin"] = [float(go[0]), float(go[1])]

    gr = patch.get("grid_resolution")
    if isinstance(gr, (int, float)):
        core["grid_resolution"] = float(gr)

    layers = patch.get("layers")
    if isinstance(layers, dict):
        core["layers"] = {
            k: layers.get(k)
            for k in sorted(layers)
            if isinstance(k, str) and isinstance(layers.get(k), (str, int, float, bool, type(None)))
        }

    links = patch.get("links")
    if isinstance(links, list):
        core["links"] = [x for x in links if isinstance(x, (str, int, float, bool, type(None), dict, list))]

    return core


def navpatch_payload_sig_v1(patch: dict[str, Any]) -> str:
    """Stable content signature for a NavPatch payload."""
    core = _navpatch_core_v1(patch)
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def store_navpatch_engram_v1(
    ctx: Ctx,
    patch: dict[str, Any],
    *,
    reason: str,
    column_memory: Any | None = None,
) -> dict[str, Any]:
    """Store a NavPatch payload into Column memory, with per-run dedup by content signature.

    Dedup strategy (v0):
      - Deduplicate within a single run using ctx.navpatch_sig_to_eid.
      - Later we can replace this with a Column-side signature index if/when Column is persisted.
    """
    active_column = column_memory if column_memory is not None else column_mem

    sig = navpatch_payload_sig_v1(patch)
    sig16 = sig[:16]

    cache = getattr(ctx, "navpatch_sig_to_eid", None)
    if isinstance(cache, dict):
        existing = cache.get(sig)
        if isinstance(existing, str) and existing:
            return {"stored": False, "sig": sig, "sig16": sig16, "engram_id": existing, "reason": "dedup_cache"}

    attrs: dict[str, Any] = {
        "schema": patch.get("schema") if isinstance(patch.get("schema"), str) else "navpatch_v1",
        "sig": sig,
        "sig16": sig16,
        "reason": reason,
    }

    for k in ("entity_id", "role", "frame", "local_id"):
        v = patch.get(k)
        if isinstance(v, str) and v:
            attrs[k] = v

    tags = patch.get("tags")
    if isinstance(tags, list):
        attrs["tags"] = [t for t in tags if isinstance(t, str) and t][:12]

    fm = FactMeta(name="navpatch", links=[], attrs=attrs).with_time(ctx)
    engram_id = active_column.assert_fact("navpatch", cast(Any, patch), fm)

    if isinstance(cache, dict):
        cache[sig] = engram_id
    else:
        try:
            ctx.navpatch_sig_to_eid = {sig: engram_id}
        except Exception:
            pass

    return {"stored": True, "sig": sig, "sig16": sig16, "engram_id": engram_id, "reason": reason}


def _wm_surfacegrid_priority_v1(token: str) -> int:
    """Return a stable display priority for salience tokens.

    Higher numbers are displayed first when we need to trim the salience set.
    The ordering intentionally favors direct hazards, then goals/attachment cues,
    then lower-risk landmarks. This keeps the overlay conservative and easy to
    read in the terminal while the full MapSurface entity system is still under
    construction.
    """
    tok = str(token or "").strip().lower()
    if tok == "cliff":
        return 100
    if tok == "shelter":
        return 80
    if tok == "mom":
        return 70
    if tok == "nipple":
        return 60
    if tok == "self":
        return 50
    return 10


def _wm_focus_token_from_obs_token_v1(token: str) -> Optional[str]:
    """Map a predicate/cue token to a small focus-token vocabulary.

    We intentionally keep the salience vocabulary tiny in v1 because the current
    environment exposes only a few stable scene entities. A future MapSurface
    layer can replace this with entity ids and richer focus semantics.
    """
    tok = str(token or "").strip().lower()
    if not tok:
        return None
    if tok.startswith("vision:silhouette:mom") or tok.startswith("proximity:mom:"):
        return "mom"
    if tok.startswith("proximity:shelter:"):
        return "shelter"
    if tok.startswith("hazard:cliff:"):
        return "cliff"
    if tok.startswith("nipple:") or tok.startswith("milk:"):
        return "nipple"
    return None


def wm_salience_force_focus_token_v1(ctx: Ctx, token: str, *, ttl: Optional[int] = None, reason: str = "manual") -> None:
    """Force a focus token into the salience set for a short time.

    This is the token-level counterpart of a later entity-level focus API. It is
    intentionally simple so probe/inspect policies can request a focus target
    without depending on a full MapSurface entity layer yet.
    """
    if ctx is None:
        return

    tok = str(token or "").strip().lower()
    if not tok:
        return

    ttl_steps = int(ttl if ttl is not None else getattr(ctx, "wm_salience_promote_ttl", 5) or 5)
    ttl_steps = max(1, ttl_steps)

    try:
        ctx.wm_salience_forced_focus[tok] = ttl_steps
        ctx.wm_salience_forced_reason[tok] = str(reason or "manual")
    except Exception:
        pass


def _wm_salience_candidate_tokens_v1(env_obs: EnvObservation) -> list[tuple[str, str]]:
    """Extract focus candidates from a single observation.

    Returns a list of ``(focus_token, reason)`` pairs in deterministic order. The
    reason strings are small trace labels, useful for debugging promotion/decay.
    """
    preds = [str(x) for x in (getattr(env_obs, "predicates", None) or []) if x is not None]
    cues = [str(x) for x in (getattr(env_obs, "cues", None) or []) if x is not None]

    out: list[tuple[str, str]] = []
    seen: set[str] = set()

    def add_token(tok: Optional[str], reason: str) -> None:
        if tok is None or tok in seen:
            return
        seen.add(tok)
        out.append((tok, reason))

    for tok in preds:
        focus = _wm_focus_token_from_obs_token_v1(tok)
        if focus == "cliff" and tok.endswith(":near"):
            add_token(focus, "hazard")
    for tok in cues:
        focus = _wm_focus_token_from_obs_token_v1(tok)
        if focus is not None:
            add_token(focus, "cue")
    for tok in preds:
        focus = _wm_focus_token_from_obs_token_v1(tok)
        if focus is not None:
            add_token(focus, "present")

    return out


def _wm_blank_grid_cells_v1(grid_w: int, grid_h: int, fill: int = cca8_navpatch.CELL_UNKNOWN) -> list[int]:
    """Return a flat grid cell list with a uniform fill value."""
    return [int(fill)] * (int(grid_w) * int(grid_h))


def _wm_set_grid_cell_v1(cells: list[int], grid_w: int, grid_h: int, x: int, y: int, value: int) -> None:
    """Safely set one flat-grid cell if the coordinates are in bounds."""
    if not (0 <= x < grid_w and 0 <= y < grid_h):
        return
    cells[(y * grid_w) + x] = int(value)


def _wm_paint_diamond_v1(cells: list[int], grid_w: int, grid_h: int, cx: int, cy: int, radius: int, value: int) -> None:
    """Paint a tiny Manhattan-diamond into a flat grid list."""
    radius = max(0, int(radius))
    for y in range(max(0, cy - radius), min(grid_h, cy + radius + 1)):
        for x in range(max(0, cx - radius), min(grid_w, cx + radius + 1)):
            if abs(x - cx) + abs(y - cy) <= radius:
                _wm_set_grid_cell_v1(cells, grid_w, grid_h, x, y, value)


def _wm_env_position_v1(env_obs: EnvObservation, key: str) -> Optional[tuple[float, float]]:
    """Read a numeric 2D position from ``env_obs.env_meta`` if available."""
    meta = getattr(env_obs, "env_meta", None) or {}
    pos = meta.get(key)
    if not (isinstance(pos, (tuple, list)) and len(pos) == 2):
        return None
    try:
        return float(pos[0]), float(pos[1])
    except Exception:
        return None


def _wm_relative_direction_cell_v1(env_obs: EnvObservation, grid_w: int, grid_h: int, *, default_xy: tuple[int, int]) -> tuple[int, int]:
    """Project mom_position relative to kid_position into a coarse SELF-local cell.

    The current environment only needs a tiny directional hint, not metric map
    accuracy. If positions are unavailable, we fall back to a deterministic
    canonical cell.
    """
    kid_pos = _wm_env_position_v1(env_obs, "kid_position")
    mom_pos = _wm_env_position_v1(env_obs, "mom_position")
    if kid_pos is None or mom_pos is None:
        return default_xy

    dx = mom_pos[0] - kid_pos[0]
    dy = mom_pos[1] - kid_pos[1]
    cx = grid_w // 2
    cy = grid_h // 2

    step_x = 0
    step_y = 0
    if dx > 0.15:
        step_x = 1
    elif dx < -0.15:
        step_x = -1
    if dy > 0.15:
        step_y = 1
    elif dy < -0.15:
        step_y = -1

    x = max(0, min(grid_w - 1, cx + (2 * step_x)))
    y = max(0, min(grid_h - 1, cy + (2 * step_y)))
    return x, y


def _wm_default_navpatches_from_obs_v1(env_obs: EnvObservation, *, grid_w: int, grid_h: int, zoom_level: int = 0) -> list[dict[str, Any]]:
    """Synthesize a tiny deterministic patch set from a basic EnvObservation.

    Why this exists
    ---------------
    The current repo version already has a general ``cca8_navpatch`` module, but
    the environment does not yet emit full patch payloads. This helper provides a
    small bridge so the WorkingMap can still maintain one current SurfaceGrid per
    cycle and the terminal can display salience-aware topology diagnostics.
    """
    preds = {str(x) for x in (getattr(env_obs, "predicates", None) or []) if x is not None}
    patches: list[dict[str, Any]] = []
    cx = int(grid_w) // 2
    cy = int(grid_h) // 2

    terrain_cells = _wm_blank_grid_cells_v1(grid_w, grid_h)
    terrain_radius = 2 if int(zoom_level) <= 0 else 1
    _wm_paint_diamond_v1(terrain_cells, grid_w, grid_h, cx, cy, terrain_radius, cca8_navpatch.CELL_TRAVERSABLE)
    patches.append({
        "schema": "navpatch_v1",
        "role": "terrain",
        "frame": "self_local",
        "entity_id": "self",
        "extent": {"center_xy": [cx, cy], "radius": terrain_radius},
        "grid_encoding_v": cca8_navpatch.GRID_ENCODING_V1,
        "grid_w": int(grid_w),
        "grid_h": int(grid_h),
        "grid_cells": terrain_cells,
    })

    cliff_cells = _wm_blank_grid_cells_v1(grid_w, grid_h)
    if "hazard:cliff:near" in preds:
        cliff_y = max(0, cy - 2)
    else:
        cliff_y = 0
    for x in range(max(0, cx - 1), min(grid_w, cx + 2)):
        _wm_set_grid_cell_v1(cliff_cells, grid_w, grid_h, x, cliff_y, cca8_navpatch.CELL_HAZARD)
    patches.append({
        "schema": "navpatch_v1",
        "role": "hazard",
        "frame": "self_local",
        "entity_id": "cliff",
        "extent": {"center_xy": [cx, cliff_y]},
        "grid_encoding_v": cca8_navpatch.GRID_ENCODING_V1,
        "grid_w": int(grid_w),
        "grid_h": int(grid_h),
        "grid_cells": cliff_cells,
    })

    if "proximity:shelter:near" in preds or "proximity:shelter:close" in preds or "proximity:shelter:touching" in preds:
        shelter_x = min(grid_w - 1, cx + 2)
    else:
        shelter_x = min(grid_w - 1, cx + 3)
    shelter_cells = _wm_blank_grid_cells_v1(grid_w, grid_h)
    _wm_set_grid_cell_v1(shelter_cells, grid_w, grid_h, shelter_x, cy, cca8_navpatch.CELL_GOAL)
    patches.append({
        "schema": "navpatch_v1",
        "role": "goal",
        "frame": "self_local",
        "entity_id": "shelter",
        "extent": {"center_xy": [shelter_x, cy]},
        "grid_encoding_v": cca8_navpatch.GRID_ENCODING_V1,
        "grid_w": int(grid_w),
        "grid_h": int(grid_h),
        "grid_cells": shelter_cells,
    })

    mom_x, mom_y = _wm_relative_direction_cell_v1(
        env_obs,
        grid_w,
        grid_h,
        default_xy=(max(0, cx - 2), cy),
    )
    mom_cells = _wm_blank_grid_cells_v1(grid_w, grid_h)
    patches.append({
        "schema": "navpatch_v1",
        "role": "landmark",
        "frame": "self_local",
        "entity_id": "mom",
        "extent": {"center_xy": [mom_x, mom_y]},
        "grid_encoding_v": cca8_navpatch.GRID_ENCODING_V1,
        "grid_w": int(grid_w),
        "grid_h": int(grid_h),
        "grid_cells": mom_cells,
        "tags": ["mom"],
    })

    return patches


def _wm_patch_center_xy_v1(patch: dict[str, Any], *, grid_w: int, grid_h: int) -> Optional[tuple[int, int]]:
    """Return a coarse display center for one navpatch payload."""
    extent = patch.get("extent")
    if isinstance(extent, dict):
        center_xy = extent.get("center_xy")
        if isinstance(center_xy, (tuple, list)) and len(center_xy) == 2:
            try:
                x = max(0, min(grid_w - 1, int(center_xy[0])))
                y = max(0, min(grid_h - 1, int(center_xy[1])))
                return x, y
            except Exception:
                return None
    return None


def _wm_patch_index_v1(patches: list[dict[str, Any]], *, grid_w: int, grid_h: int) -> dict[str, tuple[int, int]]:
    """Index navpatch display centers by entity id / role."""
    out: dict[str, tuple[int, int]] = {}
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        center = _wm_patch_center_xy_v1(patch, grid_w=grid_w, grid_h=grid_h)
        if center is None:
            continue
        raw_key = patch.get("entity_id") or patch.get("role")
        if not isinstance(raw_key, str) or not raw_key.strip():
            continue
        out[raw_key.strip().lower()] = center
    return out


def _wm_surfacegrid_mark_char_v1(token: str) -> str:
    """Return the ASCII overlay glyph for one focus token."""
    tok = str(token or "").strip().lower()
    if tok == "mom":
        return "M"
    if tok == "shelter":
        return "S"
    if tok == "cliff":
        return "C"
    if tok == "nipple":
        return "N"
    return "*"


def _wm_place_overlay_char_v1(grid: list[list[str]], char: str, *, preferred_xy: tuple[int, int], center_xy: tuple[int, int]) -> None:
    """Place one overlay character while avoiding obvious collisions.

    Hazard/goal-aligned markers (``C`` and ``S``) may overwrite the underlying
    semantic cell because they are effectively a relabeling of that terrain.
    Other markers prefer nearby blank cells so they do not erase more important
    topology cues already present on the map.
    """
    grid_h = len(grid)
    grid_w = len(grid[0]) if grid else 0
    if grid_w <= 0 or grid_h <= 0:
        return

    px, py = preferred_xy
    cx, cy = center_xy
    candidates: list[tuple[int, int]] = [(px, py)]
    for radius in (1, 2):
        for dy in range(-radius, radius + 1):
            for dx in range(-radius, radius + 1):
                if dx == 0 and dy == 0:
                    continue
                if max(abs(dx), abs(dy)) != radius:
                    continue
                candidates.append((px + dx, py + dy))

    for x, y in candidates:
        if not (0 <= x < grid_w and 0 <= y < grid_h):
            continue
        if x == cx and y == cy:
            continue
        existing = grid[y][x]
        if existing in "@MSCN*":
            continue
        if char in ("C", "S"):
            grid[y][x] = char
            return
        if existing == " ":
            grid[y][x] = char
            return


def _navpatch_tag_jaccard(tags_a: Any, tags_b: Any) -> float:
    a: set[str] = set()
    b: set[str] = set()

    if isinstance(tags_a, list):
        for t in tags_a:
            if isinstance(t, str) and t:
                a.add(t)

    if isinstance(tags_b, list):
        for t in tags_b:
            if isinstance(t, str) and t:
                b.add(t)

    u = a | b
    return (len(a & b) / float(len(u))) if u else 1.0


def _navpatch_extent_sim(ext_a: Any, ext_b: Any) -> float:
    # If we don't have numeric extents on both sides, do not penalize.
    if not (isinstance(ext_a, dict) and isinstance(ext_b, dict)):
        return 1.0

    keys = ("x0", "y0", "x1", "y1")
    a_vals: dict[str, float] = {}
    b_vals: dict[str, float] = {}

    for k in keys:
        av = ext_a.get(k)
        bv = ext_b.get(k)
        if not isinstance(av, (int, float)) or not isinstance(bv, (int, float)):
            return 1.0
        a_vals[k] = float(av)
        b_vals[k] = float(bv)

    # Normalize by the larger span so the score is scale-insensitive.
    span_a = max(abs(a_vals["x1"] - a_vals["x0"]), abs(a_vals["y1"] - a_vals["y0"]), 1.0)
    span_b = max(abs(b_vals["x1"] - b_vals["x0"]), abs(b_vals["y1"] - b_vals["y0"]), 1.0)
    denom = max(span_a, span_b, 1.0)

    diff_sum = 0.0
    for k in keys:
        diff_sum += abs(a_vals[k] - b_vals[k]) / denom

    # diff_sum in [0..~4]; convert to similarity in [0..1]
    sim = 1.0 - min(1.0, diff_sum / 4.0)
    return float(max(0.0, min(1.0, sim)))


def navpatch_similarity_v1(patch_a: dict[str, Any], patch_b: dict[str, Any]) -> float:
    """Similarity score in [0,1] based on tag overlap + (optional) extent overlap.

    This is intentionally simple (priors OFF baseline). It is only for debugging/top-K traces now.
    """
    a = _navpatch_core_v1(patch_a)
    b = _navpatch_core_v1(patch_b)

    role_a = a.get("role")
    role_b = b.get("role")
    if isinstance(role_a, str) and isinstance(role_b, str) and role_a and role_b and role_a != role_b:
        return 0.0

    tag_sim = _navpatch_tag_jaccard(a.get("tags"), b.get("tags"))
    ext_sim = _navpatch_extent_sim(a.get("extent"), b.get("extent"))

    score = 0.75 * tag_sim + 0.25 * ext_sim
    return float(max(0.0, min(1.0, score)))


def navpatch_priors_bundle_v1(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    body_space_zone_fn: Callable[[Ctx], Any] = body_space_zone,
) -> dict[str, Any]:
    """Compute a lightweight top-down priors bundle for NavPatch matching (v1.1).

    Purpose
    -------
    This bundle is the “top-down context” for the patch matching loop. It is:
      - JSON-safe (so we can store it in cycle_log.jsonl),
      - traceable (sig16 stable fingerprint),
      - intentionally small (no heavy payload).

    v1.1 additions
    -------------
    Adds a minimal precision vector so we can weight evidence vs priors in a stable way.

    Precision is not “Friston math” here; it is simply a tunable reliability weight:
      - tags precision  : how much we trust symbolic tag overlap (salience/texture-like channel)
      - extent precision: how much we trust geometric overlap (schematic geometry channel)
      - grid precision
      code:
        tags_prec = max(0.0, min(1.0, float(tags_prec)))
        ext_prec = max(0.0, min(1.0, float(ext_prec)))
        grid_prec = max(0.0, min(1.0, float(grid_prec)))
        precision = {"tags": tags_prec, "extent": ext_prec, "grid": grid_prec}

    We make tags precision stage-sensitive:
      - birth/struggle → lower tags precision (more ambiguity)
      - later stages   → default tags precision

    Fields (v1.1)
    ------------
    v:
        Schema label: "navpatch_priors_v1".
    enabled:
        True when priors were requested by ctx.navpatch_priors_enabled.
    sig16:
        Stable 16-hex signature of the bundle contents (for traceability).
    stage:
        Env meta stage string when present (e.g., "birth", "struggle").
    zone:
        BodyMap coarse zone label when available (e.g., "unsafe_cliff_near", "safe", "unknown").
    hazard_bias:
        Positive bias applied to hazard-like candidates when the zone is unsafe.
    err_guard:
        Evidence-first guardrail: if evidence error > err_guard, priors must not force a confident match.
    precision:
        Per-layer evidence reliability weights (v1.1: {"tags": f, "extent": f}).
    """
    stage: str | None = None
    try:
        meta = getattr(env_obs, "env_meta", None)
        if isinstance(meta, dict):
            s = meta.get("scenario_stage")
            stage = s if isinstance(s, str) and s else None
    except Exception:
        stage = None

    zone: str | None = None
    try:
        z = body_space_zone_fn(ctx)
        zone = z if isinstance(z, str) and z else None
    except Exception:
        zone = None

    # ---- hazard prior (v1) ----
    hazard_bias = 0.0
    try:
        hb = float(getattr(ctx, "navpatch_priors_hazard_bias", 0.0) or 0.0)
    except Exception:
        hb = 0.0
    if zone == "unsafe_cliff_near":
        hazard_bias = hb

    # ---- evidence-first guard (v1) ----
    try:
        guard = float(getattr(ctx, "navpatch_priors_error_guard", 0.45) or 0.45)
    except Exception:
        guard = 0.45
    guard = max(0.0, min(1.0, float(guard)))

    # ---- precision vector (v1.1) ----
    try:
        tags_prec = float(getattr(ctx, "navpatch_precision_tags", 0.75) or 0.75)
    except Exception:
        tags_prec = 0.75
    try:
        ext_prec = float(getattr(ctx, "navpatch_precision_extent", 0.25) or 0.25)
    except Exception:
        ext_prec = 0.25

    if stage == "birth":
        try:
            tags_prec = min(tags_prec, float(getattr(ctx, "navpatch_precision_tags_birth", tags_prec) or tags_prec))
        except Exception:
            pass
    elif stage == "struggle":
        try:
            tags_prec = min(tags_prec, float(getattr(ctx, "navpatch_precision_tags_struggle", tags_prec) or tags_prec))
        except Exception:
            pass

    try:
        grid_prec = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
    except Exception:
        grid_prec = 0.0

    tags_prec = max(0.0, min(1.0, float(tags_prec)))
    ext_prec = max(0.0, min(1.0, float(ext_prec)))
    grid_prec = max(0.0, min(1.0, float(grid_prec)))
    precision = {"tags": tags_prec, "extent": ext_prec, "grid": grid_prec}

    core = {
        "v": "navpatch_priors_v1",
        "enabled": True,
        "stage": stage,
        "zone": zone,
        "hazard_bias": float(hazard_bias),
        "err_guard": float(guard),
        "precision": precision,
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig16 = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    out = dict(core)
    out["sig16"] = sig16
    return out


def navpatch_candidate_prior_bias_v1(priors: dict[str, Any], cand_payload: dict[str, Any], cand_attrs: dict[str, Any]) -> float:
    """Return the additive prior bias term for a candidate NavPatch prototype (v1).

    v1 semantics:
      - If priors carries a positive hazard_bias and the candidate looks "hazard-like"
        (role == "hazard" OR any tag starts with "hazard:"), return hazard_bias.
      - Otherwise return 0.0.
    """
    if not isinstance(priors, dict) or not priors.get("enabled", False):
        return 0.0

    try:
        hazard_bias = float(priors.get("hazard_bias", 0.0) or 0.0)
    except Exception:
        hazard_bias = 0.0
    if hazard_bias == 0.0:
        return 0.0

    role = None
    try:
        r = cand_attrs.get("role") if isinstance(cand_attrs, dict) else None
        if isinstance(r, str) and r:
            role = r
        else:
            r2 = cand_payload.get("role") if isinstance(cand_payload, dict) else None
            role = r2 if isinstance(r2, str) and r2 else None
    except Exception:
        role = None

    tags: list[str] = []
    try:
        t = cand_payload.get("tags") if isinstance(cand_payload, dict) else None
        if isinstance(t, list):
            tags = [x for x in t if isinstance(x, str) and x]
        else:
            t2 = cand_attrs.get("tags") if isinstance(cand_attrs, dict) else None
            if isinstance(t2, list):
                tags = [x for x in t2 if isinstance(x, str) and x]
    except Exception:
        tags = []

    hazard_like = (role == "hazard") or any(isinstance(t, str) and t.startswith("hazard:") for t in tags)
    return float(hazard_bias) if hazard_like else 0.0


def navpatch_predictive_match_loop_v1(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    column_memory: Any | None = None,
    store_navpatch_fn: Callable[..., dict[str, Any]] | None = None,
    body_space_zone_fn: Callable[[Ctx], Any] = body_space_zone,
) -> list[dict[str, Any]]:
    """Compute a top-K candidate match trace for EnvObservation.nav_patches.

    This implements Phase X “predictive matching” (v1.1):
      - store observed patches as navpatch engrams (deduped by signature),
      - rank other stored prototypes as candidate interpretations (top-K),
      - apply priors as a *small bias term* (hazard_bias),
      - weight evidence by a tiny precision vector (tags vs extent),
      - classify match confidence as commit vs ambiguous vs unknown.

    Self-exclusion
    --------------
    If we stored (or dedup-reused) the current patch engram this tick, the Column scan will contain it.
    We must exclude that engram_id from candidate ranking so we do not trivially match the patch to itself.
    """
    if ctx is None:
        return []

    active_column = column_memory if column_memory is not None else column_mem

    if store_navpatch_fn is None:
        def active_store_navpatch(
            active_ctx: Ctx,
            active_patch: dict[str, Any],
            *,
            reason: str,
        ) -> dict[str, Any]:
            return store_navpatch_engram_v1(
                active_ctx,
                active_patch,
                reason=reason,
                column_memory=active_column,
            )
    else:
        active_store_navpatch = store_navpatch_fn

    # --- Step 15C support: auto-restore probe precision boosts ----------------------------
    # The probe policy can temporarily raise ctx.navpatch_precision_grid to help disambiguate
    # competing prototypes. We restore the previous value once the probe window expires so
    # the system returns to its default evidence weighting.
    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    try:
        restore_step = getattr(ctx, "wm_probe_restore_step", None)
        if isinstance(restore_step, int) and step_now >= int(restore_step):
            prev = getattr(ctx, "wm_probe_prev_navpatch_precision_grid", None)
            if isinstance(prev, (int, float)):
                ctx.navpatch_precision_grid = float(prev)

            # Clear probe restore bookkeeping (best-effort).
            ctx.wm_probe_restore_step = None
            ctx.wm_probe_prev_navpatch_precision_grid = None
    except Exception:
        pass

    if ctx is None or not bool(getattr(ctx, "navpatch_enabled", False)):
        return []

    patches = getattr(env_obs, "nav_patches", None) or []
    if not isinstance(patches, list) or not patches:
        try:
            ctx.navpatch_last_matches = []
        except Exception:
            pass
        return []

    # Config (keep terminal readable; clamp)
    try:
        top_k = int(getattr(ctx, "navpatch_match_top_k", 3) or 3)
    except Exception:
        top_k = 3
    top_k = max(1, min(10, top_k))

    try:
        accept = float(getattr(ctx, "navpatch_match_accept_score", 0.85) or 0.85)
    except Exception:
        accept = 0.85
    accept = max(0.0, min(1.0, accept))

    try:
        amb_margin = float(getattr(ctx, "navpatch_match_ambiguous_margin", 0.05) or 0.05)
    except Exception:
        amb_margin = 0.05
    amb_margin = max(0.0, min(1.0, amb_margin))

    # --- Demo knob: forced ambiguity (temporary) ---------------------------------------
    # This exists purely to demo Step 15B (zoom) + Step 15C (probe) in short runs.
    # Default is OFF (steps==0).
    try:
        demo_steps_left = int(getattr(ctx, "wm_demo_force_ambiguity_steps", 0) or 0)
    except Exception:
        demo_steps_left = 0

    demo_entity = str(getattr(ctx, "wm_demo_force_ambiguity_entity", "cliff") or "cliff").strip().lower()
    try:
        demo_margin = float(getattr(ctx, "wm_demo_force_ambiguity_margin", 0.0) or 0.0)
    except Exception:
        demo_margin = 0.0
    demo_margin = max(0.0, min(1.0, demo_margin))

    # Priors bundle (Phase X 2.2a): OFF by default.
    priors_enabled = bool(getattr(ctx, "navpatch_priors_enabled", False))
    priors: dict[str, Any] = {"v": "navpatch_priors_v1", "enabled": False, "sig16": None}

    if priors_enabled:
        priors = navpatch_priors_bundle_v1(ctx, env_obs, body_space_zone_fn=body_space_zone_fn)

    try:
        ctx.navpatch_last_priors = dict(priors)
    except Exception:
        pass

    # Precision weights (Phase X 2.2b): used even when priors are off (as stable knobs).
    prec_tags = None
    prec_ext = None
    prec_grid = None

    if isinstance(priors, dict) and isinstance(priors.get("precision"), dict):
        p = priors.get("precision")  # type: ignore[assignment]
        try:
            prec_tags = float(p.get("tags"))  # type: ignore[union-attr]
        except Exception:
            prec_tags = None
        try:
            prec_ext = float(p.get("extent"))  # type: ignore[union-attr]
        except Exception:
            prec_ext = None
        try:
            prec_grid = float(p.get("grid"))  # type: ignore[union-attr]
        except Exception:
            prec_grid = None

    if prec_tags is None:
        try:
            prec_tags = float(getattr(ctx, "navpatch_precision_tags", 0.75) or 0.75)
        except Exception:
            prec_tags = 0.75
    if prec_ext is None:
        try:
            prec_ext = float(getattr(ctx, "navpatch_precision_extent", 0.25) or 0.25)
        except Exception:
            prec_ext = 0.25
    if prec_grid is None:
        try:
            prec_grid = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
        except Exception:
            prec_grid = 0.0

    prec_tags = max(0.0, min(1.0, float(prec_tags)))
    prec_ext = max(0.0, min(1.0, float(prec_ext)))
    prec_grid = max(0.0, min(1.0, float(prec_grid)))

    # Candidate prototype records (best-effort; Column is RAM-local)
    try:
        proto_recs = active_column.find(name_contains="navpatch", has_attr="sig", limit=500)
    except Exception:
        proto_recs = []

    out: list[dict[str, Any]] = []

    for p in patches:
        if not isinstance(p, dict):
            continue

        sig = navpatch_payload_sig_v1(p)
        sig16 = sig[:16]

        # Ensure an engram exists (or reuse cached) if storage is enabled.
        stored_flag: bool | None = None
        engram_id: str | None = None
        if bool(getattr(ctx, "navpatch_store_to_column", False)):
            try:
                st = active_store_navpatch(ctx, p, reason="env_obs")
                if isinstance(st, dict):
                    stored_flag = bool(st.get("stored")) if "stored" in st else None
                    eid = st.get("engram_id")
                    if isinstance(eid, str) and eid:
                        engram_id = eid
            except Exception:
                pass

        # Precompute observed patch core once (stable keys only).
        obs_core = _navpatch_core_v1(p)

        # Score top-K prototypes.
        # Tuple: (score_post, score_evidence, score_unweighted, prior_bias, tag_sim, ext_sim, grid_sim, engram_id)
        scored: list[tuple[float, float, float, float, float, float, float | None, str]] = []
        role_p = p.get("role")

        for rec in proto_recs:
            if not isinstance(rec, dict):
                continue
            eid = rec.get("id")
            if not isinstance(eid, str) or not eid:
                continue
            # Self-exclusion
            if isinstance(engram_id, str) and engram_id and eid == engram_id:
                continue
            payload = rec.get("payload")
            if not isinstance(payload, dict):
                continue
            meta_raw = rec.get("meta")
            meta: dict[str, Any] = meta_raw if isinstance(meta_raw, dict) else {}
            attrs_raw = meta.get("attrs")
            attrs: dict[str, Any] = attrs_raw if isinstance(attrs_raw, dict) else {}
            role_r = attrs.get("role")
            if (
                isinstance(role_p, str) and role_p
                and isinstance(role_r, str) and role_r
                and role_p != role_r
            ):
                continue

            proto_core = _navpatch_core_v1(payload)
            # Evidence channels (v1.1): tags vs extent vs grid
            tag_sim = float(_navpatch_tag_jaccard(obs_core.get("tags"), proto_core.get("tags")))
            ext_sim = float(_navpatch_extent_sim(obs_core.get("extent"), proto_core.get("extent")))
            tag_sim = max(0.0, min(1.0, tag_sim))
            ext_sim = max(0.0, min(1.0, ext_sim))
            grid_sim: float | None = None
            try:
                obs_cells = p.get("grid_cells")
                cand_cells = payload.get("grid_cells")
                if (
                    isinstance(obs_cells, list)
                    and isinstance(cand_cells, list)
                    and len(obs_cells) == len(cand_cells)
                    and bool(obs_cells)
                ):
                    grid_sim = float(grid_overlap_fraction_v1(obs_cells, cand_cells))
            except Exception:
                grid_sim = None
            if grid_sim is not None:
                grid_sim = max(0.0, min(1.0, float(grid_sim)))
            # Unweighted evidence score (diagnostic only)
            if grid_sim is None:
                score_unw = 0.5 * tag_sim + 0.5 * ext_sim
            else:
                score_unw = (tag_sim + ext_sim + float(grid_sim)) / 3.0
            # Precision-weighted evidence score
            err_tags = 1.0 - tag_sim
            err_ext = 1.0 - ext_sim
            err_grid = (1.0 - float(grid_sim)) if grid_sim is not None else 0.0
            w_tags = float(prec_tags)
            w_ext = float(prec_ext)
            w_grid = float(prec_grid) if grid_sim is not None else 0.0
            denom = float(w_tags + w_ext + w_grid)
            if denom > 0.0:
                err_weighted = (w_tags * err_tags + w_ext * err_ext + w_grid * err_grid) / denom
            else:
                # Fallback: average over available channels
                if grid_sim is None:
                    err_weighted = 0.5 * (err_tags + err_ext)
                else:
                    err_weighted = (err_tags + err_ext + err_grid) / 3.0
            score_evidence = 1.0 - err_weighted
            score_evidence = max(0.0, min(1.0, float(score_evidence)))
            prior_bias = float(navpatch_candidate_prior_bias_v1(priors, payload, attrs)) if priors_enabled else 0.0
            score_post = max(0.0, min(1.0, float(score_evidence + prior_bias)))
            scored.append((score_post, score_evidence, score_unw, float(prior_bias), tag_sim, ext_sim, grid_sim, eid))

        scored.sort(key=lambda t: (-t[0], t[-1]))
        top_list: list[dict[str, Any]] = [
            {
                "engram_id": eid,
                "score": float(score_post),
                "score_raw": float(score_evidence),
                "score_unweighted": float(score_unw),
                "prior_bias": float(prior_bias),
                "err": float(1.0 - score_post),
                "err_raw": float(1.0 - score_evidence),
                "err_unweighted": float(1.0 - score_unw),
                "tag_sim": float(tag_sim),
                "ext_sim": float(ext_sim),
                "grid_sim": float(grid_sim) if isinstance(grid_sim, (int, float)) else None,
            }
            for (score_post, score_evidence, score_unw, prior_bias, tag_sim, ext_sim, grid_sim, eid) in scored[:top_k]
        ]

        # Add normalized weights (posterior proxy) for future graded belief work.
        if top_list:
            s_post = 0.0
            s_raw = 0.0
            for c in top_list:
                try:
                    s_post += float(c.get("score", 0.0) or 0.0)
                except Exception:
                    pass
                try:
                    s_raw += float(c.get("score_raw", 0.0) or 0.0)
                except Exception:
                    pass

            n = float(len(top_list))
            for c in top_list:
                try:
                    v = float(c.get("score", 0.0) or 0.0)
                except Exception:
                    v = 0.0
                c["w"] = (v / s_post) if s_post > 0.0 else (1.0 / n)

                try:
                    v = float(c.get("score_raw", 0.0) or 0.0)
                except Exception:
                    v = 0.0
                c["w_raw"] = (v / s_raw) if s_raw > 0.0 else (1.0 / n)

        def _candidate_float(candidate: dict[str, Any] | None, key: str) -> float:
            """Return one numeric candidate field without leaking broad JSON types to Mypy."""
            if not isinstance(candidate, dict):
                return 0.0
            value = candidate.get(key, 0.0)
            return float(value) if isinstance(value, (int, float, str)) else 0.0

        best = top_list[0] if top_list else None
        best_score = _candidate_float(best, "score")
        best_score_raw = _candidate_float(best, "score_raw")
        best_err_raw = float(1.0 - best_score_raw)

        second = top_list[1] if len(top_list) > 1 else None
        margin = (best_score - _candidate_float(second, "score")) if isinstance(second, dict) else None
        margin_raw = (best_score_raw - _candidate_float(second, "score_raw")) if isinstance(second, dict) else None

        # Decision labels are for logs/JSON traces, not control logic yet.
        decision: str | None = None
        decision_note: str | None = None

        if stored_flag is False:
            decision = "reuse_exact"
        else:
            if best is None:
                decision = "new_no_candidates"
            else:
                if priors_enabled:
                    try:
                        guard = float(priors.get("err_guard", 0.45) or 0.45)
                    except Exception:
                        guard = 0.45
                    guard = max(0.0, min(1.0, float(guard)))

                    if best_err_raw > guard:
                        decision = "new_novel"
                        decision_note = "guard_high_err"
                    else:
                        decision = "new_near_match" if best_score >= accept else "new_novel"
                else:
                    decision = "new_near_match" if best_score >= accept else "new_novel"

        # Commit classification (Phase X 2.2c-style semantics, without changing control yet).
        commit = "unknown"
        if decision == "reuse_exact":
            commit = "commit"
        elif decision_note == "guard_high_err":
            commit = "unknown"
        elif best is None:
            commit = "unknown"
        else:
            if best_score >= accept:
                if isinstance(margin, float) and margin < amb_margin:
                    commit = "ambiguous"
                    if decision_note is None:
                        decision_note = "ambiguous_low_margin"
                else:
                    commit = "commit"
            else:
                commit = "unknown"

        # --- Demo: force an ambiguous commit for a chosen entity for N steps -------------
        if demo_steps_left > 0 and demo_entity:
            ent0 = p.get("entity_id")
            ent = ent0.strip().lower() if isinstance(ent0, str) else ""
            if ent == demo_entity:
                commit = "ambiguous"
                if decision_note is None:
                    decision_note = "demo_force_ambiguity"
                margin = float(demo_margin)
                margin_raw = float(demo_margin)

        rec_out = {
            "sig": sig,
            "sig16": sig16,
            "priors_sig16": (priors.get("sig16") if isinstance(priors, dict) else None),
            "local_id": p.get("local_id"),
            "entity_id": p.get("entity_id"),
            "role": p.get("role"),
            "stored": stored_flag,
            "engram_id": engram_id,
            "decision": decision,
            "decision_note": decision_note,
            "commit": commit,
            "margin": float(margin) if isinstance(margin, float) else None,
            "margin_raw": float(margin_raw) if isinstance(margin_raw, float) else None,
            "best": best,
            "top_k": top_list,
        }
        out.append(rec_out)

        # Attach trace back onto the patch itself (JSON-safe).
        try:
            p["sig"] = sig
            p["sig16"] = sig16
            p["match"] = {
                "decision": decision,
                "decision_note": decision_note,
                "commit": commit,
                "margin": rec_out.get("margin"),
                "priors_sig16": rec_out.get("priors_sig16"),
                "best": best,
                "top_k": top_list,
            }
        except Exception:
            pass

    try:
        ctx.navpatch_last_matches = out
    except Exception:
        pass

    # Decrement demo knob once per navpatch loop call (one per env step).
    if demo_steps_left > 0:
        try:
            ctx.wm_demo_force_ambiguity_steps = max(0, int(demo_steps_left) - 1)
        except Exception:
            pass
    return out


def wm_apply_grid_slot_families_to_mapsurface_v1(working_world, self_bid: str, slots: dict[str, Any]) -> list[str]:
    """Apply Step-13 grid-derived slot-families onto WM.MapSurface (SELF), deterministically.

    Intent
    ------
    SurfaceGrid is the topological substrate; MapSurface is the action-ready sketch.
    This helper writes a *very small*, stable set of pred:* tags onto the existing
    MapSurface SELF binding using overwrite-by-slot-family semantics.

    Design constraints
    ------------------
    - Must NOT create new bindings or edges (no uncontrolled growth).
    - Must NOT emit cue:* (no cue leakage).
    - Must be deterministic: same `slots` -> same written tags.
    - Overwrite-by-family: each derived family replaces its previous value each tick.

    Slot mapping (v1)
    -----------------
    - slots["hazard:near"] == True        -> "pred:hazard:near"     (otherwise absent)
    - slots["terrain:traversable_near"]   -> "pred:terrain:traversable_near" (otherwise absent)
    - slots["goal:dir"] == "NE"/"E"/...   -> "pred:goal:dir:<dir8>" (otherwise absent)

    Parameters
    ----------
    working_world
        The WorkingMap WorldGraph instance (ctx.working_world).
    self_bid
        Binding id of the MapSurface SELF node in the working_world.
    slots
        Dict produced by derive_grid_slot_families_v1(...).

    Returns
    -------
    list[str]
        The pred:* tags written this tick (for logging / JSON traces / debugging).
    """
    if working_world is None or not isinstance(self_bid, str) or not self_bid:
        return []

    bindings = getattr(working_world, "_bindings", None)
    if not isinstance(bindings, dict) or self_bid not in bindings:
        return []

    b = bindings.get(self_bid)
    if b is None:
        return []
    raw = getattr(b, "tags", None)

    # Normalize to a set for editing (keep other tags intact).
    if isinstance(raw, set):
        tset = set(t for t in raw if isinstance(t, str))
        out_kind = "set"
    elif isinstance(raw, list):
        tset = set(t for t in raw if isinstance(t, str))
        out_kind = "list"
    else:
        tset = set()
        out_kind = "list"

    # Overwrite-by-family: remove prior derived tags (only our tiny namespace).
    def _drop_prefix(prefix: str) -> None:
        nonlocal tset
        tset = set(t for t in tset if not (isinstance(t, str) and t.startswith(prefix)))

    _drop_prefix("pred:goal:dir:")
    if "pred:hazard:near" in tset:
        tset.discard("pred:hazard:near")
    if "pred:terrain:traversable_near" in tset:
        tset.discard("pred:terrain:traversable_near")

    written: list[str] = []

    if bool(slots.get("hazard:near", False)):
        tset.add("pred:hazard:near")
        written.append("pred:hazard:near")

    if bool(slots.get("terrain:traversable_near", False)):
        tset.add("pred:terrain:traversable_near")
        written.append("pred:terrain:traversable_near")

    gd = slots.get("goal:dir")
    if isinstance(gd, str) and gd:
        tag = f"pred:goal:dir:{gd}"
        tset.add(tag)
        written.append(tag)

    # Write back, preserving the original container kind where possible.
    if out_kind == "set":
        b.tags = set(tset)
    else:
        b.tags = sorted(tset)

    return written


def _wm_dir8_v1(dx: int, dy: int) -> str:
    """Return a compact 8-way direction code from an integer delta.

    The goal here is readability, not geometry perfection. This matches the spirit
    of the simple directional summaries already used elsewhere in the CCA8 codebase.
    """
    sx = 0 if dx == 0 else (1 if dx > 0 else -1)
    sy = 0 if dy == 0 else (1 if dy > 0 else -1)

    if sx == 0 and sy == 0:
        return "C"
    if sx == 0 and sy < 0:
        return "N"
    if sx == 0 and sy > 0:
        return "S"
    if sx > 0 and sy == 0:
        return "E"
    if sx < 0 and sy == 0:
        return "W"
    if sx > 0 and sy < 0:  #pylint: disable=chained-comparison
        return "NE"
    if sx > 0 and sy > 0:
        return "SE"
    if sx < 0 and sy < 0:
        return "NW"
    return "SW"


def _wm_surfacegrid_local_points_v1(grid_w: int, grid_h: int, cx: int, cy: int, radius: int) -> list[tuple[int, int]]:
    """Return Euclidean-disk local points around SELF for NavSummary v1.

    This intentionally mirrors the "near-self local neighborhood" idea already
    used for small grid-derived slot families. The result is small, deterministic,
    and cheap to scan every cycle.
    """
    w = max(1, int(grid_w))
    h = max(1, int(grid_h))
    r = max(0, int(radius))

    pts: list[tuple[int, int]] = []
    r2 = r * r
    for y in range(max(0, cy - r), min(h, cy + r + 1)):
        dy = y - cy
        for x in range(max(0, cx - r), min(w, cx + r + 1)):
            dx = x - cx
            if (dx * dx + dy * dy) <= r2:
                pts.append((x, y))
    return pts


def _wm_surfacegrid_corridor_count_v1(sg: SurfaceGridV1, *, self_xy: tuple[int, int], local_radius: int) -> int:
    """Count connected traversable components near SELF.

    v1 definition:
      - local neighborhood = Euclidean disk around SELF
      - safe/traversable cells = CELL_TRAVERSABLE or CELL_GOAL
      - connectivity = 4-neighbor

    This is a deliberately simple proxy for "how many local traversable branches
    or corridors do I have right now?"
    """
    w = int(getattr(sg, "grid_w", 0) or 0)
    h = int(getattr(sg, "grid_h", 0) or 0)
    cells = getattr(sg, "grid_cells", None)
    if not isinstance(cells, list) or len(cells) != (w * h) or w <= 0 or h <= 0:
        return 0

    cx, cy = int(self_xy[0]), int(self_xy[1])
    pts = _wm_surfacegrid_local_points_v1(w, h, cx, cy, local_radius)
    local = set(pts)
    safe_codes = {CELL_TRAVERSABLE, CELL_GOAL}

    walkable: set[tuple[int, int]] = set()
    for x, y in pts:
        try:
            c = int(cells[y * w + x])
        except Exception:
            continue
        if c in safe_codes:
            walkable.add((x, y))

    if not walkable:
        return 0

    seen: set[tuple[int, int]] = set()
    comps = 0

    for pt in sorted(walkable):
        if pt in seen:
            continue
        comps += 1
        stack = [pt]
        seen.add(pt)

        while stack:
            x, y = stack.pop()
            for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
                np = (nx, ny)
                if np not in local or np not in walkable or np in seen:
                    continue
                seen.add(np)
                stack.append(np)

    return comps


def _wm_surfacegrid_shortest_safe_path_cost_v1(sg: SurfaceGridV1, *, self_xy: tuple[int, int]) -> int | None:
    """Return the shortest safe path length from SELF to any goal cell.

    v1 safety rule:
      - passable = CELL_TRAVERSABLE or CELL_GOAL
      - impassable = unknown / hazard / blocked
      - connectivity = 4-neighbor

    This is intentionally conservative. Unknown cells are not treated as safe.
    """
    w = int(getattr(sg, "grid_w", 0) or 0)
    h = int(getattr(sg, "grid_h", 0) or 0)
    cells = getattr(sg, "grid_cells", None)
    if not isinstance(cells, list) or len(cells) != (w * h) or w <= 0 or h <= 0:
        return None

    cx, cy = int(self_xy[0]), int(self_xy[1])
    if not (0 <= cx < w and 0 <= cy < h):
        return None

    safe_codes = {CELL_TRAVERSABLE, CELL_GOAL}
    goals: set[tuple[int, int]] = set()

    for y in range(h):
        base = y * w
        for x in range(w):
            try:
                c = int(cells[base + x])
            except Exception:
                continue
            if c == CELL_GOAL:
                goals.add((x, y))

    if not goals:
        return None

    try:
        start_cell = int(cells[cy * w + cx])
    except Exception:
        return None

    if start_cell == CELL_GOAL:
        return 0
    if start_cell not in safe_codes:
        return None

    queue: list[tuple[int, int, int]] = [(cx, cy, 0)]
    seen: set[tuple[int, int]] = {(cx, cy)}
    head = 0

    while head < len(queue):
        x, y, dist = queue[head]
        head += 1

        if (x, y) in goals:
            return int(dist)

        for nx, ny in ((x + 1, y), (x - 1, y), (x, y + 1), (x, y - 1)):
            if not (0 <= nx < w and 0 <= ny < h):
                continue
            if (nx, ny) in seen:
                continue
            try:
                c = int(cells[ny * w + nx])
            except Exception:
                continue
            if c not in safe_codes:
                continue
            seen.add((nx, ny))
            queue.append((nx, ny, dist + 1))

    return None


def compute_navsummary_v1(
    sg: SurfaceGridV1,
    *,
    slots: dict[str, Any] | None = None,
    self_xy: tuple[int, int] | None = None,
    local_radius: int = 2,
) -> dict[str, Any]:
    """Compute a compact numeric summary from the current SurfaceGrid.

    Purpose
    -------
    NavSummary is the "cheap scan once" layer that sits between raw topology and
    later policy logic. It is intentionally small and JSON-safe, and it avoids
    exploding the number of derived pred:* tags on MapSurface.

    v1 outputs
    ----------
    - hazard_near / hazard_density
    - traversable_near / traversable_density
    - corridor_count
    - goal_present / goal_dir / goal_distance_l1
    - shortest_safe_path_cost

    Notes
    -----
    - Densities are LOCAL to a small SELF-centered disk (radius=local_radius),
      not whole-grid fractions.
    - goal_dir is first taken from `slots["goal:dir"]` if already computed by
      the grid→slot-family path; otherwise we derive it from the nearest goal.
    - shortest_safe_path_cost is conservative and may be None when no safe route
      is visible from the current grid.
    """
    w = int(getattr(sg, "grid_w", 0) or 0)
    h = int(getattr(sg, "grid_h", 0) or 0)
    cells = getattr(sg, "grid_cells", None)
    if not isinstance(cells, list) or len(cells) != (w * h) or w <= 0 or h <= 0:
        return {}

    if self_xy is None:
        cx = w // 2
        cy = h // 2
    else:
        cx = max(0, min(w - 1, int(self_xy[0])))
        cy = max(0, min(h - 1, int(self_xy[1])))

    r = max(1, int(local_radius))
    pts = _wm_surfacegrid_local_points_v1(w, h, cx, cy, r)

    blocked_code = int(getattr(cca8_navpatch, "CELL_BLOCKED", 4) or 4)

    total_local_n = len(pts)
    unknown_n = 0
    traversable_n = 0
    hazard_n = 0
    goal_n = 0
    blocked_n = 0

    for x, y in pts:
        try:
            c = int(cells[y * w + x])
        except Exception:
            continue

        if c == CELL_UNKNOWN:
            unknown_n += 1
        elif c == CELL_TRAVERSABLE:
            traversable_n += 1
        elif c == CELL_HAZARD:
            hazard_n += 1
        elif c == CELL_GOAL:
            goal_n += 1
        elif c == blocked_code:
            blocked_n += 1

    known_n = max(0, total_local_n - unknown_n)
    safe_local_n = traversable_n + goal_n

    if isinstance(slots, dict):
        hazard_near = bool(slots.get("hazard:near", False))
        traversable_near = bool(slots.get("terrain:traversable_near", False))
        slot_goal_dir = slots.get("goal:dir")
        goal_dir = slot_goal_dir if isinstance(slot_goal_dir, str) and slot_goal_dir else None
    else:
        hazard_near = (hazard_n + blocked_n) > 0
        traversable_near = safe_local_n > 0
        goal_dir = None

    hazard_density = float(hazard_n + blocked_n) / float(known_n) if known_n > 0 else 0.0
    traversable_density = float(safe_local_n) / float(known_n) if known_n > 0 else 0.0

    goal_pts: list[tuple[int, int]] = []
    for y in range(h):
        base = y * w
        for x in range(w):
            try:
                if int(cells[base + x]) == CELL_GOAL:
                    goal_pts.append((x, y))
            except Exception:
                continue

    goal_present = bool(goal_pts)
    goal_distance_l1: int | None = None

    if goal_pts:
        nearest = min(goal_pts, key=lambda p: (abs(p[0] - cx) + abs(p[1] - cy), p[1], p[0]))
        goal_distance_l1 = int(abs(nearest[0] - cx) + abs(nearest[1] - cy))
        if goal_dir is None:
            goal_dir = _wm_dir8_v1(nearest[0] - cx, nearest[1] - cy)

    shortest_safe_path_cost = _wm_surfacegrid_shortest_safe_path_cost_v1(sg, self_xy=(cx, cy))
    corridor_count = _wm_surfacegrid_corridor_count_v1(sg, self_xy=(cx, cy), local_radius=r)

    try:
        grid_sig16 = sg.sig16_v1()
    except Exception:
        grid_sig16 = None

    return {
        "schema": "wm_navsummary_v1",
        "grid_sig16": grid_sig16 if isinstance(grid_sig16, str) and grid_sig16 else None,
        "grid_w": int(w),
        "grid_h": int(h),
        "self_xy": [int(cx), int(cy)],
        "local_radius": int(r),
        "hazard_near": bool(hazard_near),
        "hazard_density": float(hazard_density),
        "traversable_near": bool(traversable_near),
        "traversable_density": float(traversable_density),
        "corridor_count": int(corridor_count),
        "goal_present": bool(goal_present),
        "goal_dir": goal_dir if isinstance(goal_dir, str) and goal_dir else None,
        "goal_distance_l1": int(goal_distance_l1) if isinstance(goal_distance_l1, int) else None,
        "shortest_safe_path_cost": (
            int(shortest_safe_path_cost) if isinstance(shortest_safe_path_cost, int) else None
        ),
        "local_counts": {
            "total": int(total_local_n),
            "known": int(known_n),
            "unknown": int(unknown_n),
            "traversable": int(traversable_n),
            "goal": int(goal_n),
            "hazard": int(hazard_n),
            "blocked": int(blocked_n),
        },
    }


def format_navsummary_line_v1(summary: dict[str, Any]) -> str:
    """Render a compact one-line NavSummary for terminal logs."""
    if not isinstance(summary, dict) or not summary:
        return "(none)"

    hazard_near = 1 if bool(summary.get("hazard_near", False)) else 0
    traversable_near = 1 if bool(summary.get("traversable_near", False)) else 0

    try:
        hazard_density = float(summary.get("hazard_density", 0.0) or 0.0)
    except Exception:
        hazard_density = 0.0

    try:
        traversable_density = float(summary.get("traversable_density", 0.0) or 0.0)
    except Exception:
        traversable_density = 0.0

    try:
        corridors = int(summary.get("corridor_count", 0) or 0)
    except Exception:
        corridors = 0

    goal_dir = summary.get("goal_dir")
    goal_dir_txt = goal_dir if isinstance(goal_dir, str) and goal_dir else "(none)"

    goal_l1 = summary.get("goal_distance_l1")
    goal_l1_txt = str(int(goal_l1)) if isinstance(goal_l1, int) else "n/a"

    safe_cost = summary.get("shortest_safe_path_cost")
    safe_cost_txt = str(int(safe_cost)) if isinstance(safe_cost, int) else "n/a"

    return (
        f"hazard_near={hazard_near} hazard_density={hazard_density:.2f} "
        f"traversable_near={traversable_near} traversable_density={traversable_density:.2f} "
        f"corridors={corridors} goal_dir={goal_dir_txt} goal_l1={goal_l1_txt} safe_cost={safe_cost_txt}"
    )


def _wm_entity_pos_xy_v1(ww, bid: str) -> tuple[float, float] | None:
    """Best-effort read of WM schematic position from binding.meta['wm']['pos'].

    Returns:
        (x, y) floats in the WM schematic frame, or None if missing.
    """
    try:
        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            return None
        meta = getattr(b, "meta", None)
        if not isinstance(meta, dict):
            return None
        wmm = meta.get("wm")
        if not isinstance(wmm, dict):
            return None
        pos = wmm.get("pos")
        if not isinstance(pos, dict):
            return None
        x = pos.get("x")
        y = pos.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return (float(x), float(y))
    except Exception:
        return None
    return None


def _wm_entity_kind_v1(ww, bid: str) -> str | None:
    """Return WM kind tag value (e.g., 'hazard', 'shelter', 'agent') if present."""
    try:
        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            return None
        tags = getattr(b, "tags", []) or []
        for t in tags:
            if isinstance(t, str) and t.startswith("wm:kind:"):
                return t.split(":", 2)[2]
    except Exception:
        return None
    return None


def _wm_entity_dist_class_v1(ww, bid: str) -> str | None:
    """Return the WM distance-class metadata (e.g., touching / near / far) when present.

    We use this only for terminal presentation. In particular, if mom is marked
    as "touching", the SurfaceGrid can render a combined SELF+MOM symbol even if
    the schematic coordinate projection would otherwise place mom in a nearby cell.
    """
    try:
        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            return None
        meta = getattr(b, "meta", None)
        if not isinstance(meta, dict):
            return None
        wmm = meta.get("wm")
        if not isinstance(wmm, dict):
            return None
        dc = wmm.get("dist_class")
        if isinstance(dc, str) and dc:
            return dc
    except Exception:
        return None
    return None


def _wm_pos_to_grid_cell_v1(x: float, y: float, grid_w: int, grid_h: int) -> tuple[int, int] | None:
    """Map WM schematic (x,y) to a SurfaceGrid cell, assuming SELF is centered."""
    try:
        w = int(grid_w)
        h = int(grid_h)
        if w <= 0 or h <= 0:
            return None
        cx = w // 2
        cy = h // 2
        gx = cx + int(round(float(x)))
        gy = cy + int(round(float(y)))
        if 0 <= gx < w and 0 <= gy < h:
            return (gx, gy)
    except Exception:
        return None
    return None


def _wm_surfacegrid_window_anchor_v2(env_obs: EnvObservation, *, zoom_level: int = 0) -> tuple[int, int]:
    """Compute a coarse SELF-local window anchor for dirty-cache v2.

    We do not yet have a fully explicit scrolling local-window object, so we use
    env_meta['kid_position'] as a pragmatic proxy for whether the current local
    view should be considered shifted enough to warrant recomposition.

    The bucket size is zoom-sensitive: higher zoom means the effective local
    footprint is smaller, so smaller motion should trigger a window shift.
    """
    env_meta = getattr(env_obs, "env_meta", None) or {}
    kid_pos = env_meta.get("kid_position")
    if not (isinstance(kid_pos, (tuple, list)) and len(kid_pos) == 2):
        return (0, 0)

    try:
        x = float(kid_pos[0])
        y = float(kid_pos[1])
    except Exception:
        return (0, 0)

    bucket = 1.0 / max(1, int(zoom_level) + 1)
    return (int(round(x / bucket)), int(round(y / bucket)))


def _wm_surfacegrid_scene_fingerprint_v2(
    env_obs: EnvObservation,
    patches: list[dict[str, Any]],
    *,
    grid_w: int,
    grid_h: int,
    zoom_level: int,
    focus_entities: list[str],
) -> dict[str, Any]:
    """Build the v2 dirty-cache fingerprint for the current SurfaceGrid scene.

    This fingerprints the *incoming evidence* (patch payload sigs) plus a few
    semantically important display/context fields. That lets us distinguish a
    true cache hit from cases where the underlying scene changed even if the old
    v1 patch-sig cache would have missed it.
    """
    sig16s: list[str] = []
    for patch in patches:
        if not isinstance(patch, dict):
            continue
        try:
            sig16s.append(navpatch_payload_sig_v1(patch)[:16])
        except Exception:
            continue
    sig16s.sort()

    preds = {str(x) for x in (getattr(env_obs, "predicates", None) or []) if x is not None}
    hazard_sig = sorted(tok for tok in preds if tok.startswith("hazard:"))

    focus = [str(x).strip().lower() for x in (focus_entities or []) if isinstance(x, str) and x.strip()]

    return {
        "input_sig16": sig16s,
        "grid_wh": [int(grid_w), int(grid_h)],
        "window_anchor": list(_wm_surfacegrid_window_anchor_v2(env_obs, zoom_level=zoom_level)),
        "zoom_level": int(zoom_level),
        "focus_entities": focus,
        "hazard_sig": hazard_sig,
    }


def _wm_surfacegrid_dirty_reasons_v2(ctx: Ctx, fingerprint: dict[str, Any]) -> list[str]:
    """Compare the current scene fingerprint to the previous one.

    Cleanup intent
    --------------
    We want the dirty reasons to describe *why the scene changed*, not to over-report
    grid-shape changes when the composed map dimensions are actually stable.

    v2 rule:
      - grid_shape_changed is based on previous vs current fingerprinted grid_wh
      - the current SurfaceGrid object's grid_w/grid_h are used only as a sanity check
      - semantic reasons (patches/focus/window/hazard/zoom) still come from the fingerprint
    """
    reasons: list[str] = []

    prev = getattr(ctx, "wm_surfacegrid_last_scene_fingerprint", None)
    if not isinstance(prev, dict):
        prev = {}

    sg = getattr(ctx, "wm_surfacegrid", None)

    def _fp_grid_wh(fp: dict[str, Any]) -> tuple[int, int] | None:
        raw = fp.get("grid_wh")
        if not (isinstance(raw, (list, tuple)) and len(raw) == 2):
            return None
        try:
            return (int(raw[0]), int(raw[1]))
        except Exception:
            return None
    prev_wh = _fp_grid_wh(prev)
    cur_wh = _fp_grid_wh(fingerprint)
    has_prev_fingerprint = bool(prev)

    # Bootstrap / structural checks first.
    if sg is None:
        reasons.append("grid_missing")
    else:
        # Shape change is an explanation about the requested scene fingerprint changing
        # across ticks, not about the already-composed previous grid object merely existing.
        if prev_wh is not None and cur_wh is not None and prev_wh != cur_wh:
            reasons.append("grid_shape_changed")
        else:
            # Keep a light sanity check on the existing SurfaceGrid object.
            try:
                sg_w = int(getattr(sg, "grid_w", 0) or 0)
                sg_h = int(getattr(sg, "grid_h", 0) or 0)
                if sg_w <= 0 or sg_h <= 0:
                    reasons.append("grid_check_error")
            except Exception:
                reasons.append("grid_check_error")

    # Fingerprint-driven semantic reasons.
    #
    # Bootstrap policy:
    # - On the very first compose, report scene-content reasons such as patches_changed
    #   and hazard_changed.
    # - Do NOT report transition-style reasons like self_window_shift / zoom_changed /
    #   focus_changed until there is an actual previous fingerprint to compare against.
    if list(prev.get("input_sig16", [])) != list(fingerprint.get("input_sig16", [])):
        reasons.append("patches_changed")
    if has_prev_fingerprint and list(prev.get("window_anchor", [])) != list(fingerprint.get("window_anchor", [])):
        reasons.append("self_window_shift")
    if has_prev_fingerprint and int(prev.get("zoom_level", 0) or 0) != int(fingerprint.get("zoom_level", 0) or 0):
        reasons.append("zoom_changed")
    if has_prev_fingerprint and list(prev.get("focus_entities", [])) != list(fingerprint.get("focus_entities", [])):
        reasons.append("focus_changed")
    if list(prev.get("hazard_sig", [])) != list(fingerprint.get("hazard_sig", [])):
        reasons.append("hazard_changed")
    return reasons or ["cache_hit"]


def _surfacegrid_ascii_lines_v1(grid_w: int, grid_h: int, cells: list[int], *, sparse: bool) -> list[str]:
    """Render grid cells to ASCII lines (v1). Display-only: does not mutate the grid.

    Mapping (v1):
        unknown -> ' '
        traversable -> '.' (or ' ' if sparse=True)
        hazard -> '#'
        goal -> 'G'
        4 (blocked/reserved) -> 'X'
        other -> '?'
    """
    w = int(grid_w); h = int(grid_h)
    if w <= 0 or h <= 0 or len(cells) != w * h:
        return ["(surfacegrid: invalid dims/cells)"]

    def _ch(v: int) -> str:
        if v == CELL_UNKNOWN:
            return " "
        if v == CELL_TRAVERSABLE:
            return " " if sparse else "."
        if v == CELL_HAZARD:
            return "#"
        if v == CELL_GOAL:
            return "G"
        if v == 4:
            return "X"
        return "?"

    out: list[str] = []
    for y in range(h):
        base = y * w
        out.append("".join(_ch(int(cells[base + x])) for x in range(w)))
    return out


def _wm_entity_mark_char_v1(entity_id: str, kind: str | None) -> str:
    """Choose a single-character mark for an entity in SurfaceGrid ASCII."""
    eid = (entity_id or "").strip().lower()
    if eid == "self":
        return "@"
    if eid in ("mom", "mother"):
        return "M"
    if eid == "shelter":
        return "S"
    if eid in ("cliff", "drop", "danger") or (kind == "hazard"):
        return "C"
    return "*"


def _wm_display_focus_entities_v1(focus_entities: list[str]) -> list[str]:
    """Normalize the salience focus list for terminal display.

    Why this helper exists
    ----------------------
    The internal salience machinery can occasionally include meta-entities such as
    "scene" that are useful for bookkeeping but are not meaningful landmarks for a
    human reading the SurfaceGrid printout.

    This helper keeps the printed focus list stable and readable by:
      - dropping known non-spatial/meta ids,
      - de-duplicating entries,
      - presenting common landmarks in a fixed user-facing order.
    """
    raw: list[str] = []
    for item in (focus_entities or []):
        if isinstance(item, str) and item.strip():
            raw.append(item.strip().lower())

    skip = {"scene", "wm_root", "root", "now"}

    seen: set[str] = set()
    kept: list[str] = []
    for ent in raw:
        if ent in skip:
            continue
        if ent in seen:
            continue
        seen.add(ent)
        kept.append(ent)

    ordered: list[str] = []
    preferred = ("self", "cliff", "shelter", "mom", "nipple")
    for ent in preferred:
        if ent in seen:
            ordered.append(ent)

    for ent in sorted(kept):
        if ent not in preferred:
            ordered.append(ent)

    return ordered


def render_surfacegrid_ascii_with_salience_v1(ctx: Ctx, ww, sg: SurfaceGridV1, *, focus_entities: list[str]) -> str:
    """Render a sparse SurfaceGrid ASCII string and overlay salient entity marks.

    This is display-only: it never changes sg.cells, so Step 13 grid->predicates remains unchanged.

    Overlay rules
    -------------
      - SELF is normally rendered as '@' at the center cell.
      - If mom is effectively co-located with SELF (same grid cell, or dist_class='touching'),
        render '&' at the center cell to mean SELF+MOM.
      - Other focus entities are rendered in their own cells using one-letter marks.
    """
    w = int(getattr(sg, "grid_w", 0) or 0)
    h = int(getattr(sg, "grid_h", 0) or 0)

    cells = getattr(sg, "grid_cells", None)
    if not isinstance(cells, list):
        # Back-compat: some earlier drafts used sg.cells
        cells = getattr(sg, "cells", None)
    if not isinstance(cells, list):
        cells = []

    sparse = bool(getattr(ctx, "wm_surfacegrid_ascii_sparse", True))

    try:
        cells_i = [int(x) for x in cells]
    except Exception:
        cells_i = []

    lines = _surfacegrid_ascii_lines_v1(w, h, cells_i, sparse=sparse)

    if w <= 0 or h <= 0 or len(lines) != h:
        return "\n".join(lines)

    grid: list[list[str]] = []
    for row in lines:
        rr = list(row)
        if len(rr) < w:
            rr.extend([" "] * (w - len(rr)))
        grid.append(rr[:w])

    cx = w // 2
    cy = h // 2

    # Start with SELF at center; we may later upgrade this to '&' if mom is touching/co-located.
    try:
        grid[cy][cx] = "@"
    except Exception:
        pass

    show_entities = bool(getattr(ctx, "wm_surfacegrid_ascii_show_entities", True))
    if not show_entities:
        return "\n".join("".join(r) for r in grid)

    for eid in _wm_display_focus_entities_v1(focus_entities):
        if not isinstance(eid, str):
            continue

        ent = eid.strip().lower()
        if not ent or ent == "self":
            continue

        bid = (getattr(ctx, "wm_entities", {}) or {}).get(ent)
        if not isinstance(bid, str):
            continue

        pos = _wm_entity_pos_xy_v1(ww, bid)
        if pos is None:
            continue
        x, y = pos

        cell = _wm_pos_to_grid_cell_v1(x, y, w, h)
        if cell is None:
            continue
        gx, gy = cell

        kind = _wm_entity_kind_v1(ww, bid)
        dist_class = _wm_entity_dist_class_v1(ww, bid)
        mark = _wm_entity_mark_char_v1(ent, kind)

        try:
            # Presentation rule: when mom is physically with SELF, show a combined symbol.
            if ent in ("mom", "mother") and (dist_class == "touching" or (gx == cx and gy == cy)):
                grid[cy][cx] = "&"
            else:
                grid[gy][gx] = mark
        except Exception:
            pass

    # Re-assert SELF only when we are NOT intentionally showing the combined SELF+MOM symbol.
    try:
        if grid[cy][cx] != "&":
            grid[cy][cx] = "@"
    except Exception:
        pass

    return "\n".join("".join(r) for r in grid)


def format_surfacegrid_ascii_map_v1(
    ascii_txt: str,
    *,
    title: str | None = None,
    legend: str | None = None,
    show_axes: bool = True,
) -> str:
    """
    Wrap a raw ASCII SurfaceGrid dump in a terminal-friendly "map frame".

    Intent
    ------
    The SurfaceGrid renderer (render_surfacegrid_ascii_with_salience_v1) returns a raw block of rows,
    where each character is a cell symbol (optionally with entity overlays like '@', 'M', 'C', 'S').
    This helper adds:

      - a border (top/bottom),
      - optional x-axis labels (0..w-1, with tens row when w >= 10),
      - optional y-axis labels (0..h-1),
      - optional title and legend lines.

    This is deliberately pure string formatting:
      - No third-party libraries.
      - No assumptions about semantic meanings of characters beyond what the renderer already decided.

    Parameters
    ----------
    ascii_txt:
        The raw ASCII grid text. May contain uneven line lengths; we pad rows to the max width
        so the frame aligns cleanly.
    title:
        Optional header line shown above the axes/border. Use to include sig16, etc.
    legend:
        Optional legend line shown below the framed map.
    show_axes:
        If True, show x-axis (top) and y-axis (left). If False, draws only a border with no indices.

    Returns
    -------
    str
        Framed map text with no trailing newline.
    """
    s = (ascii_txt or "").rstrip("\n")
    if not s:
        return "(surfacegrid ascii: empty)"

    rows = s.splitlines()
    # Preserve intentional leading/trailing spaces in rows; only pad to a uniform width.
    w = max((len(r) for r in rows), default=0)
    h = len(rows)
    padded = [r.ljust(w) for r in rows]

    if show_axes:
        y_w = max(2, len(str(max(0, h - 1))))
        indent_border = " " * (y_w + 1)   # spaces before the '+-----+' border
        indent_cells = " " * (y_w + 2)    # spaces before the first cell (after '|')
    else:
        y_w = 0
        indent_border = ""
        indent_cells = ""

    out: list[str] = []
    if title:
        out.append(str(title))

    if show_axes and w > 0:
        tens = "".join(str((i // 10) % 10) if i >= 10 else " " for i in range(w))
        ones = "".join(str(i % 10) for i in range(w))
        if any(ch != " " for ch in tens):
            out.append(indent_cells + tens)
        out.append(indent_cells + ones)

    border = indent_border + "+" + ("-" * w) + "+"
    out.append(border)

    for y, row in enumerate(padded):
        if show_axes:
            out.append(f"{y:>{y_w}d} |{row}|")
        else:
            out.append(f"|{row}|")

    out.append(border)

    if legend:
        out.append(str(legend))

    return "\n".join(out)


def _surfacegrid_ascii_text_v1(ctx: Ctx, sg) -> Optional[str]:
    """Return the best available raw ASCII SurfaceGrid text for the current tick.

    Preference order
    ----------------
    1. Reuse ctx.wm_surfacegrid_last_ascii when it is already available.
    2. Fall back to the renderer helper if the current code path has a SurfaceGrid
       object but the cached ASCII text has not yet been populated.

    This helper is read-mostly. It may refresh ctx.wm_surfacegrid_last_ascii when
    the fallback renderer succeeds.
    """
    ascii_txt = getattr(ctx, "wm_surfacegrid_last_ascii", None)
    if isinstance(ascii_txt, str) and ascii_txt:
        return ascii_txt

    render_fn = globals().get("render_surfacegrid_ascii_with_salience_v1")
    if not callable(render_fn) or sg is None:
        return None

    ww = getattr(ctx, "working_world", None)
    focus_entities = getattr(ctx, "wm_salience_focus_entities", None)
    if not isinstance(focus_entities, list):
        focus_entities = []
    try:
        focus_entities = _wm_display_focus_entities_v1(focus_entities)
    except Exception:
        focus_entities = list(focus_entities)

    try:
        ascii_txt = render_fn(ctx, ww, sg, focus_entities=focus_entities)
    except Exception:
        return None

    if isinstance(ascii_txt, str) and ascii_txt:
        try:
            ctx.wm_surfacegrid_last_ascii = ascii_txt
        except Exception:
            pass
        return ascii_txt

    return None


def _surfacegrid_terminal_block_key_v1(map_txt: str) -> str:
    """Return a normalized comparison key for the framed SurfaceGrid terminal block.

    Why this helper exists
    ----------------------
    The terminal UX should suppress repeat prints when the *visible* SurfaceGrid
    block is unchanged. Comparing the raw cached ascii snapshot alone can be too
    strict, because upstream recomposition may produce harmless whitespace-only
    differences while the framed terminal block the user sees is identical.

    Normalization
    -------------
    - split into lines
    - strip trailing whitespace per line
    - drop only blank lines at the very start/end
    - preserve internal spaces and line order
    """
    if not isinstance(map_txt, str) or not map_txt:
        return ""

    lines = [line.rstrip() for line in map_txt.splitlines()]

    while lines and not lines[0]:
        lines.pop(0)
    while lines and not lines[-1]:
        lines.pop()

    return "\n".join(lines)


def _surfacegrid_ascii_terminal_block_v1(
    ctx: Ctx,
    sg,
    *,
    sig16: str,
    line_prefix: str = "",
    title: Optional[str] = None,
    legend: Optional[str] = None,
    ascii_text_fn: Callable[[Ctx, Any], str | None] | None = None,
    format_map_fn: Callable[..., str] | None = None,
) -> str:
    """Return the terminal block for a SurfaceGrid map using change detection.

    Behavior
    --------
    - First time a map is printed in this run: print the full framed map.
    - If the visible framed map changes later: print the full framed map again.
    - If the visible framed map is unchanged: print a short unchanged marker instead.

    Why the comparison uses the framed block
    ----------------------------------------
    The raw cached ascii snapshot can differ across ticks for non-visual reasons,
    while the formatted terminal block the user sees is identical. For terminal UX,
    I therefore compare a normalized key derived from the formatted map block.
    """
    _ = sig16  # kept for call-site compatibility; helper no longer needs sig16 directly

    active_ascii_text = ascii_text_fn or _surfacegrid_ascii_text_v1
    active_format_map = format_map_fn or format_surfacegrid_ascii_map_v1

    ascii_txt = active_ascii_text(ctx, sg)
    if not isinstance(ascii_txt, str) or not ascii_txt:
        try:
            ctx.wm_surfacegrid_last_printed_ascii = None
            ctx.wm_surfacegrid_last_printed_block = None
        except Exception:
            pass
        return f"{line_prefix}map: (no ascii available)"

    map_txt = active_format_map(
        ascii_txt,
        title=title,
        legend=legend,
        show_axes=True,
    )
    block_key = _surfacegrid_terminal_block_key_v1(map_txt)

    show_each = bool(getattr(ctx, "wm_surfacegrid_ascii_each_tick", False))
    last_block = getattr(ctx, "wm_surfacegrid_last_printed_block", None)
    changed = bool(show_each or block_key != last_block)

    if not changed:
        try:
            ctx.wm_surfacegrid_last_printed_ascii = ascii_txt
        except Exception:
            pass

        if str(line_prefix).startswith("[cycle] SG"):
            return f"{line_prefix}ASCII map already printed above; no second dump needed"

        return f"{line_prefix}++SurfaceGrid ASCII Map is unchanged++"

    try:
        ctx.wm_surfacegrid_last_printed_ascii = ascii_txt
        ctx.wm_surfacegrid_last_printed_block = block_key
    except Exception:
        pass

    return f"{line_prefix}map:\n{map_txt}"


def format_surfacegrid_snapshot_v1(ctx: Ctx) -> str:
    """Format the current WM.SurfaceGrid stored on ctx using shared change detection.

    Why this helper exists
    ----------------------
    Older call sites still want a single "give me the current SurfaceGrid as a
    printable string" API. We now route those call sites through the same
    changed-vs-unchanged logic used by the cycle footer, so the full ASCII map
    is printed only when it actually changes.
    """
    sg = getattr(ctx, "wm_surfacegrid", None)
    if sg is None:
        return "[surfacegrid] (none)"

    sig16 = getattr(ctx, "wm_surfacegrid_sig16", None)
    if not isinstance(sig16, str) or not sig16:
        try:
            sig16 = sg.sig16_v1()
        except Exception:
            sig16 = "unknown"

    try:
        compose_ms = float(getattr(ctx, "wm_surfacegrid_compose_ms", 0.0) or 0.0)
    except Exception:
        compose_ms = 0.0

    reasons = getattr(ctx, "wm_surfacegrid_dirty_reasons", None)
    if not isinstance(reasons, list):
        reasons = []

    reason_items = [str(r) for r in reasons if isinstance(r, str) and r]
    if reason_items == ["cache_hit"]:
        reason_txt = ""
    else:
        reason_txt = ", ".join(reason_items)

    focus_entities = getattr(ctx, "wm_salience_focus_entities", None)
    if not isinstance(focus_entities, list):
        focus_entities = []
    try:
        focus_entities = _wm_display_focus_entities_v1(focus_entities)
    except Exception:
        focus_entities = list(focus_entities)

    focus_txt = ", ".join(focus_entities) or "(none)"

    header = f"[surfacegrid] sig16={sig16} compose_ms={compose_ms:.2f} focus={focus_txt}"
    if reason_txt:
        header += f" reasons={reason_txt}"

    legend_txt = (
        "@=self &=self+mom M=mom S=shelter C=cliff G=goal "
        "#=hazard X=blocked *=other  (dense: .=traversable; sparse: space=unknown/trav)"
    )

    block = _surfacegrid_ascii_terminal_block_v1(
        ctx,
        sg,
        sig16=sig16,
        line_prefix="",
        title=f"WM.SurfaceGrid (sig16={sig16})",
        legend=legend_txt,
    )

    return header + "\n" + block


def wm_salience_force_focus_entity_v1(ctx: Ctx, entity_id: str, *, ttl: int | None = None, reason: str = "inspect") -> None:
    """Force an entity into the Step-14 salience focus set for a few ticks.

    This is *attention/display* only:
      - It affects ctx.wm_salience_focus_entities (what we render as landmarks),
      - It does NOT change MapSurface beliefs or WorldGraph state.

    The TTL is decremented once per call to wm_salience_tick_v1(...).
    """
    if ctx is None or not isinstance(entity_id, str) or not entity_id.strip():
        return

    eid = entity_id.strip().lower()
    try:
        t = int(ttl) if ttl is not None else int(getattr(ctx, "wm_salience_inspect_focus_ttl", 4) or 4)
    except Exception:
        t = 4
    t = max(1, min(50, int(t)))  # keep bounded

    m = getattr(ctx, "wm_salience_forced_focus", None)
    if not isinstance(m, dict):
        ctx.wm_salience_forced_focus = {}
        m = ctx.wm_salience_forced_focus

    try:
        prev = int(m.get(eid, 0) or 0)
    except Exception:
        prev = 0
    if t > prev:
        m[eid] = int(t)

    rmap = getattr(ctx, "wm_salience_forced_reason", None)
    if not isinstance(rmap, dict):
        ctx.wm_salience_forced_reason = {}
        rmap = ctx.wm_salience_forced_reason
    if isinstance(reason, str) and reason:
        rmap[eid] = reason


def _wm_guess_inspected_entity_v1(
    ctx: Ctx,
    *,
    body_cliff_distance_fn: Callable[[Ctx], Any] = body_cliff_distance,
    body_mom_distance_fn: Callable[[Ctx], Any] = body_mom_distance,
) -> str | None:
    """Best-effort guess of a probe/inspect target when a policy doesn't specify one.

    Priority order:
      1) Any NavPatch matches whose commit != 'commit' (ambiguous/unknown). Prefer cliff if present.
      2) If BodyMap says cliff is near, use cliff.
      3) If BodyMap has mom distance info, use mom.
      4) Otherwise None.
    """
    # 1) Ambiguous/unknown NavPatch entities (from ctx.navpatch_last_matches)
    ent_ids: list[str] = []
    try:
        matches = getattr(ctx, "navpatch_last_matches", None)
        if isinstance(matches, list):
            for rec in matches:
                if not isinstance(rec, dict):
                    continue
                commit = rec.get("commit")
                if not isinstance(commit, str) or not commit or commit == "commit":
                    continue
                eid = rec.get("entity_id")
                if isinstance(eid, str) and eid.strip():
                    ent_ids.append(eid.strip().lower())
    except Exception:
        ent_ids = []

    if ent_ids:
        # Prefer high-safety relevance if present.
        for pref in ("cliff", "shelter", "mom"):
            if pref in ent_ids:
                return pref
        return sorted(set(ent_ids))[0]

    # 2) BodyMap hazard
    try:
        if body_cliff_distance_fn(ctx) == "near":
            return "cliff"
    except Exception:
        pass

    # 3) BodyMap mom proximity
    try:
        md = body_mom_distance_fn(ctx)
        if isinstance(md, str) and md:
            return "mom"
    except Exception:
        pass

    return None


def _wm_salience_ambiguous_entities_v1(env_obs: EnvObservation) -> set[str]:
    """Extract entities with ambiguous patch matches (commit != 'commit') from env_obs.nav_patches."""
    out: set[str] = set()
    patches = getattr(env_obs, "nav_patches", None) or []
    if not isinstance(patches, list):
        return out
    for p in patches:
        if not isinstance(p, dict):
            continue
        m = p.get("match")
        if not isinstance(m, dict):
            continue
        commit = m.get("commit")
        if isinstance(commit, str) and commit and commit != "commit":
            eid = p.get("entity_id")
            if isinstance(eid, str) and eid.strip():
                out.add(eid.strip().lower())
    return out


def wm_salience_tick_v1(
    ctx: Ctx,
    ww,
    *,
    changed_entities: set[str],
    new_cue_entities: set[str],
    ambiguous_entities: set[str],
    body_cliff_distance_fn: Callable[[Ctx], Any] = body_cliff_distance,
    body_mom_distance_fn: Callable[[Ctx], Any] = body_mom_distance,
    body_shelter_distance_fn: Callable[[Ctx], Any] = body_shelter_distance,
) -> dict[str, Any]:
    """One-tick salience update (Phase X Step 14, minimal v1).

    Signals:
      - changed_entities: any entity whose MapSurface slot-family was overwritten this tick.
      - new_cue_entities: any entity that gained a new cue this tick.
      - ambiguous_entities: any entity whose NavPatch match is not committed (commit != 'commit').

    Storage:
      - Writes per-entity fields under binding.meta['wm']:
          salience_ttl: int
          salience_reason: short string (best-effort)
      - Returns a small dict for traces/printing:
          {"focus_entities": [...], "events": [...]}  (JSON-safe)

    TTL rules (v1):
      - Novelty burst: changed or new cue → ttl=max(ttl, novelty_ttl)
      - Promotion: hazard-relevant or ambiguous → ttl=max(ttl, promote_ttl)
      - Decay: any entity not refreshed this tick decrements ttl by 1 down to 0
    """
    novelty_ttl = max(0, int(getattr(ctx, "wm_salience_novelty_ttl", 3) or 3))
    promote_ttl = max(novelty_ttl, int(getattr(ctx, "wm_salience_promote_ttl", 8) or 8))
    k_max = max(0, int(getattr(ctx, "wm_salience_max_items", 3) or 3))

    changed = {e.strip().lower() for e in (changed_entities or set()) if isinstance(e, str) and e.strip()}
    newc = {e.strip().lower() for e in (new_cue_entities or set()) if isinstance(e, str) and e.strip()}
    amb = {e.strip().lower() for e in (ambiguous_entities or set()) if isinstance(e, str) and e.strip()}

    # Mandatory baseline: SELF always.
    focus: list[str] = ["self"]

    # Hazard/goal relevance from BodyMap-first signals (cheap and robust).
    try:
        if body_cliff_distance_fn(ctx) == "near":
            focus.append("cliff")
    except Exception:
        pass
    try:
        if body_shelter_distance_fn(ctx) in ("near", "touching"):
            focus.append("shelter")
    except Exception:
        pass
    try:
        if body_mom_distance_fn(ctx) == "near":
            focus.append("mom")
    except Exception:
        pass

    # Novelty/focus candidates (excluding already forced ones).
    forced = set(focus)

    # Forced focus (inspect/probe): keep these entities in focus for a few ticks even if they stop being "top-K" now.
    forced_map = getattr(ctx, "wm_salience_forced_focus", None)
    forced_list: list[tuple[int, str]] = []
    if isinstance(forced_map, dict) and forced_map:
        for k, v in forced_map.items():
            if not isinstance(k, str) or not k.strip():
                continue
            try:
                ttl = int(v)
            except Exception:
                continue
            if ttl > 0:
                forced_list.append((ttl, k.strip().lower()))
    # Deterministic order: higher TTL first, then lexical.
    forced_list.sort(key=lambda t: (-t[0], t[1]))
    # Keep bounded so focus doesn't explode.
    for _ttl, e in forced_list[:8]:
        if e and e not in forced:
            focus.append(e)
            forced.add(e)

    cand: list[tuple[int, str, str]] = []
    for e in amb:
        if e not in forced and e != "self":
            cand.append((3, e, "ambiguous"))
    for e in changed:
        if e not in forced and e != "self":
            cand.append((2, e, "changed"))
    for e in newc:
        if e not in forced and e != "self":
            cand.append((1, e, "new_cue"))

    # Deterministic pick: higher priority first, then lexicographic.
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    for _prio, e, _why in cand[:k_max]:
        if e not in forced:
            focus.append(e)
            forced.add(e)

    # Apply TTL updates into WM entity meta
    events: list[dict[str, Any]] = []
    ent_map = getattr(ctx, "wm_entities", {}) or {}
    for eid, bid in ent_map.items():
        if not isinstance(eid, str) or not isinstance(bid, str):
            continue
        e = eid.strip().lower()
        if not e:
            continue

        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            continue
        if not isinstance(getattr(b, "meta", None), dict):
            b.meta = {}
        wmm = b.meta.setdefault("wm", {})
        if not isinstance(wmm, dict):
            continue

        prev_ttl = int(wmm.get("salience_ttl", 0) or 0)
        prev_reason = wmm.get("salience_reason")
        if not isinstance(prev_reason, str):
            prev_reason = ""

        refreshed = e in forced
        reason = ""

        # Choose the strongest reason we have (best-effort)
        if e in amb:
            reason = "ambiguous"
        elif e in changed:
            reason = "changed"
        elif e in newc:
            reason = "new_cue"
        elif e in ("cliff", "shelter", "mom"):
            # forced-by-goal/hazard, but no novelty signal this tick
            reason = "goal/hazard"

        if refreshed:
            ttl_target = promote_ttl if (e in amb or e == "cliff") else novelty_ttl
            ttl_new = max(prev_ttl, ttl_target)
        else:
            ttl_new = max(0, prev_ttl - 1)

        if ttl_new != prev_ttl or (refreshed and reason and reason != prev_reason):
            events.append(
                {
                    "entity": e,
                    "ttl_prev": int(prev_ttl),
                    "ttl_new": int(ttl_new),
                    "refreshed": bool(refreshed),
                    "reason": reason,
                }
            )

        wmm["salience_ttl"] = int(ttl_new)
        if reason:
            wmm["salience_reason"] = reason
        else:
            # keep old reason if we are only decaying; drop when ttl hits 0
            if ttl_new <= 0:
                wmm.pop("salience_reason", None)

    # Decrement forced-focus TTL counters once per tick.
    try:
        ff = getattr(ctx, "wm_salience_forced_focus", None)
        if isinstance(ff, dict) and ff:
            new_ff: dict[str, int] = {}
            for e, ttl in ff.items():
                if not isinstance(e, str) or not e.strip():
                    continue
                try:
                    t = int(ttl)
                except Exception:
                    continue
                t2 = t - 1
                if t2 > 0:
                    new_ff[e.strip().lower()] = int(t2)
            ctx.wm_salience_forced_focus = new_ff

            fr = getattr(ctx, "wm_salience_forced_reason", None)
            if isinstance(fr, dict) and fr:
                ctx.wm_salience_forced_reason = {e: str(fr.get(e, "")) for e in new_ff if e in fr}
    except Exception:
        pass

    return {"focus_entities": list(focus), "events": events}




# -----------------------------------------------------------------------------
# Phase-2 orchestration helpers called by the still-runner-owned observation path
# -----------------------------------------------------------------------------

def update_working_navpatch_refs_v1(
    ctx: Ctx,
    env_obs: EnvObservation,
    working_world: Any,
    *,
    ensure_entity_fn: Callable[..., str],
    display_id_fn: Callable[[str], str] | None = None,
    store_navpatch_fn: Callable[..., dict[str, Any]] | None = None,
) -> None:
    """Attach this observation's NavPatch references to WorkingMap entities.

    The helper preserves the historical per-tick replacement semantics: active
    entities receive the current reference list, while entities whose patches
    disappeared have their ``patch_refs`` metadata removed. Heavy payloads may
    be stored in Column memory through the supplied callback.
    """
    if ctx is None or env_obs is None or working_world is None:
        return
    if not bool(getattr(ctx, "navpatch_enabled", False)):
        return

    active_store = store_navpatch_fn or store_navpatch_engram_v1
    active_display: Callable[[str], str] = display_id_fn or str
    ww = working_world

    patches_in = getattr(env_obs, "nav_patches", None) or []
    refs_by_ent: dict[str, list[dict[str, Any]]] = {}
    sigs_by_ent: dict[str, set[str]] = {}

    if isinstance(patches_in, list):
        for patch in patches_in:
            if not isinstance(patch, dict):
                continue

            ent_raw = patch.get("entity_id") or patch.get("entity") or "self"
            try:
                ent = str(ent_raw).strip().lower() or "self"
            except Exception:
                ent = "self"

            sig = navpatch_payload_sig_v1(patch)
            sig16 = sig[:16]

            engram_id: str | None = None
            if bool(getattr(ctx, "navpatch_store_to_column", False)):
                try:
                    stored = active_store(ctx, patch, reason="env_obs")
                    engram_id = stored.get("engram_id") if isinstance(stored, dict) else None
                except Exception:
                    engram_id = None

            ref: dict[str, Any] = {
                "sig16": sig16,
                "sig": sig,
                "engram_id": engram_id,
                "local_id": patch.get("local_id"),
                "role": patch.get("role"),
                "frame": patch.get("frame"),
            }

            tags = patch.get("tags")
            if isinstance(tags, list):
                ref["tags"] = [tag for tag in tags if isinstance(tag, str) and tag][:8]

            refs_by_ent.setdefault(ent, []).append(ref)
            sigs_by_ent.setdefault(ent, set()).add(sig16)

    bindings = getattr(ww, "_bindings", {})

    for ent, refs in refs_by_ent.items():
        kind = None
        try:
            roles = {ref.get("role") for ref in refs if isinstance(ref, dict)}
            if "hazard" in roles or ent in ("cliff", "drop", "danger"):
                kind = "hazard"
            elif "shelter" in roles or ent == "shelter":
                kind = "shelter"
            elif ent in ("mom", "mother", "self"):
                kind = "agent"
        except Exception:
            kind = None

        bid = ensure_entity_fn(ent, kind_hint=kind)
        binding = bindings.get(bid) if isinstance(bindings, dict) else None
        if binding is not None:
            if not isinstance(getattr(binding, "meta", None), dict):
                binding.meta = {}
            wm_meta = binding.meta.setdefault("wm", {})
            if isinstance(wm_meta, dict):
                wm_meta["patch_refs"] = list(refs)
                try:
                    first_ref = refs[0] if refs else None
                    frame = first_ref.get("frame") if isinstance(first_ref, dict) else None
                    if isinstance(frame, str) and frame:
                        wm_meta["patch_frame"] = frame
                except Exception:
                    pass

        try:
            ctx.wm_last_navpatch_sigs[ent] = set(sigs_by_ent.get(ent, set()))
        except Exception:
            pass

        if bool(getattr(ctx, "navpatch_verbose", False)):
            try:
                display = f"{active_display(bid)} ({bid})"
                print(f"[env→working] PATCH x{len(refs)} → {display} (entity={ent})")
            except Exception:
                pass

    try:
        last_sig_map = getattr(ctx, "wm_last_navpatch_sigs", {}) or {}
        for ent in list(last_sig_map.keys()):
            if ent in refs_by_ent:
                continue
            existing_bid = (getattr(ctx, "wm_entities", {}) or {}).get(ent)
            if isinstance(existing_bid, str) and isinstance(bindings, dict) and existing_bid in bindings:
                binding = bindings.get(existing_bid)
                if binding is not None and isinstance(getattr(binding, "meta", None), dict):
                    wm_meta = binding.meta.get("wm")
                    if isinstance(wm_meta, dict):
                        wm_meta.pop("patch_refs", None)
            ctx.wm_last_navpatch_sigs.pop(ent, None)
    except Exception:
        pass


def update_working_navpatch_scratch_zoom_v1(
    ctx: Ctx,
    env_obs: EnvObservation,
    working_world: Any,
    *,
    tagset_fn: Callable[[str], set[str]] | None = None,
    upsert_edge_fn: Callable[[str, str, str, dict[str, Any] | None], None] | None = None,
    body_cliff_distance_fn: Callable[[Ctx], Any] = body_cliff_distance,
) -> None:
    """Update ambiguity Scratch records and emit zoom transition events.

    Ambiguous NavPatch commits are represented by stable WM_SCRATCH items so
    later probe logic can inspect them without unbounded graph growth. A change
    between an empty and non-empty ambiguity set emits one ``zoom_down`` or
    ``zoom_up`` event, preserving the historical diagnostic behavior.
    """
    if ctx is None or env_obs is None or working_world is None:
        return
    if not bool(getattr(ctx, "navpatch_enabled", False)):
        return
    if not bool(getattr(ctx, "wm_scratch_navpatch_enabled", True)):
        return

    ww = working_world
    def default_tagset(binding_id: str) -> set[str]:
        """Return a mutable tag set from the active WorkingMap."""
        return _wm_tagset_of(ww, binding_id)

    def default_upsert(
        src: str,
        dst: str,
        label: str,
        meta: dict[str, Any] | None = None,
    ) -> None:
        """Upsert one structural edge in the active WorkingMap."""
        _wm_upsert_edge(ww, src, dst, label, meta)

    active_tagset: Callable[[str], set[str]] = tagset_fn or default_tagset
    active_upsert: Callable[[str, str, str, dict[str, Any] | None], None] = upsert_edge_fn or default_upsert

    try:
        scratch_bid = ww.ensure_anchor("WM_SCRATCH")

        key_to_bid = getattr(ctx, "wm_scratch_navpatch_key_to_bid", None)
        if not isinstance(key_to_bid, dict):
            key_to_bid = {}
            ctx.wm_scratch_navpatch_key_to_bid = key_to_bid

        prev_keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
        if not isinstance(prev_keys, set):
            prev_keys = set()
            ctx.wm_scratch_navpatch_last_keys = prev_keys

        def sanitize_anchor_token(text: str) -> str:
            normalized = (text or "").strip().upper()
            chars = [char if char.isalnum() else "_" for char in normalized]
            normalized = "".join(chars)
            while "__" in normalized:
                normalized = normalized.replace("__", "_")
            return normalized.strip("_") or "X"

        def scratch_key(entity_id: str, local_id: str) -> str:
            return f"{(entity_id or '').strip().lower()}|{(local_id or '').strip().lower()}"

        nav_patches = getattr(env_obs, "nav_patches", None)
        cur_keys: set[str] = set()
        bindings = getattr(ww, "_bindings", {})

        if isinstance(nav_patches, list):
            for patch in nav_patches:
                if not isinstance(patch, dict):
                    continue

                match = patch.get("match")
                if not isinstance(match, dict) or (match.get("commit") or "") != "ambiguous":
                    continue

                entity_raw = patch.get("entity_id")
                local_raw = patch.get("local_id")
                entity_id = (
                    entity_raw.strip().lower()
                    if isinstance(entity_raw, str) and entity_raw.strip()
                    else "unknown"
                )
                local_id = (
                    local_raw.strip().lower()
                    if isinstance(local_raw, str) and local_raw.strip()
                    else "p"
                )

                key = scratch_key(entity_id, local_id)
                cur_keys.add(key)

                anchor_name = (
                    f"WM_SCRATCH_NVP_{sanitize_anchor_token(entity_id)}_"
                    f"{sanitize_anchor_token(local_id)}"
                )
                scratch_item_bid = ww.ensure_anchor(anchor_name)
                key_to_bid[key] = scratch_item_bid

                active_upsert(
                    scratch_bid,
                    scratch_item_bid,
                    "wm_scratch_item",
                    {"created_by": "wm_scratch", "kind": "navpatch_ambiguous"},
                )

                tags = active_tagset(scratch_item_bid)
                tags.add("wm:scratch_item")
                tags.add("wm:scratch:navpatch_match")
                tags.add(f"wm:eid:{entity_id}")
                tags.add(f"wm:patch_local:{local_id}")

                binding = bindings.get(scratch_item_bid) if isinstance(bindings, dict) else None
                if binding is not None:
                    if not isinstance(getattr(binding, "meta", None), dict):
                        binding.meta = {}
                    wm_meta = binding.meta.setdefault("wm", {})
                    if isinstance(wm_meta, dict):
                        wm_meta["kind"] = "navpatch_match_ambiguous"
                        wm_meta["schema"] = "wm_scratch_navpatch_match_v1"
                        wm_meta["controller_steps"] = int(getattr(ctx, "controller_steps", 0) or 0)
                        wm_meta["entity_id"] = entity_id
                        wm_meta["local_id"] = local_id
                        wm_meta["patch_sig16"] = (
                            patch.get("sig16") if isinstance(patch.get("sig16"), str) else None
                        )
                        wm_meta["commit"] = "ambiguous"
                        wm_meta["decision"] = match.get("decision")
                        wm_meta["decision_note"] = match.get("decision_note")
                        wm_meta["margin"] = match.get("margin")
                        wm_meta["best"] = match.get("best") if isinstance(match.get("best"), dict) else None
                        wm_meta["top_k"] = match.get("top_k") if isinstance(match.get("top_k"), list) else []

        stale_keys = set(prev_keys) - set(cur_keys)
        if stale_keys and isinstance(bindings, dict):
            scratch_root = bindings.get(scratch_bid)
            edges = getattr(scratch_root, "edges", None) if scratch_root is not None else None
            if isinstance(edges, list):
                for key in stale_keys:
                    scratch_item_bid = key_to_bid.get(key)
                    if not isinstance(scratch_item_bid, str):
                        continue
                    edges[:] = [
                        edge
                        for edge in edges
                        if not (
                            isinstance(edge, dict)
                            and (edge.get("label") or edge.get("rel") or edge.get("relation"))
                            == "wm_scratch_item"
                            and (edge.get("to") or edge.get("dst") or edge.get("dst_id") or edge.get("id"))
                            == scratch_item_bid
                        )
                    ]
                    key_to_bid.pop(key, None)

        ctx.wm_scratch_navpatch_last_keys = set(cur_keys)

        if bool(getattr(ctx, "wm_zoom_enabled", True)):
            now_down = bool(cur_keys)
            prev_down = bool(prev_keys)

            def entities_from_keys(keys: set[str]) -> set[str]:
                entities: set[str] = set()
                for key in keys:
                    if not isinstance(key, str) or "|" not in key:
                        continue
                    entities.add(key.split("|", 1)[0].strip().lower())
                return entities

            events: list[dict[str, Any]] = []
            if now_down != prev_down:
                kind = "zoom_down" if now_down else "zoom_up"
                keys_for_event = set(cur_keys) if now_down else set(prev_keys)
                entities = entities_from_keys(keys_for_event)

                try:
                    hazard_near = body_cliff_distance_fn(ctx) == "near"
                except Exception:
                    hazard_near = False

                hazard_ambiguous = "cliff" in entities
                if now_down:
                    reason = "hazard+ambiguity" if (hazard_near or hazard_ambiguous) else "ambiguity"
                else:
                    reason = "resolved"

                event = {
                    "kind": kind,
                    "reason": reason,
                    "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
                    "ambiguous_n": int(len(keys_for_event)),
                    "ambiguous_keys": sorted(keys_for_event),
                    "ambiguous_entities": sorted(entities),
                    "hazard_near": bool(hazard_near),
                    "hazard_ambiguous": bool(hazard_ambiguous),
                }
                events.append(event)

                if bool(getattr(ctx, "wm_zoom_verbose", False)):
                    try:
                        entity_text = ",".join(sorted(entities)[:4])
                        more = "..." if len(entities) > 4 else ""
                        print(
                            f"[wm-zoom] {kind} reason={reason} "
                            f"amb={len(keys_for_event)} ents={entity_text}{more}"
                        )
                    except Exception:
                        pass

                try:
                    ctx.wm_zoom_last_reason = reason
                    ctx.wm_zoom_last_event_step = int(getattr(ctx, "controller_steps", 0) or 0)
                except Exception:
                    pass

            try:
                ctx.wm_zoom_state = "down" if now_down else "up"
                ctx.wm_zoom_last_events = list(events)
            except Exception:
                pass
    except Exception:
        pass


def update_working_salience_surfacegrid_v1(
    ctx: Ctx,
    env_obs: EnvObservation,
    working_world: Any,
    *,
    changed_entities: set[str],
    new_cue_entities: set[str],
    salience_tick_fn: Callable[..., dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Update salience, SurfaceGrid cache, grid predicates, and NavSummary.

    This is the Phase-2 sub-pipeline extracted from the live WorkingMap
    observation injector. It deliberately mutates only the current ``Ctx`` and
    short-lived WorkingMap graph and returns a compact diagnostic summary.
    """
    if ctx is None or env_obs is None or working_world is None:
        return {}

    ww = working_world
    active_salience_tick = salience_tick_fn or wm_salience_tick_v1

    ambiguous_entities: set[str] = set()
    if bool(getattr(ctx, "wm_salience_enabled", False)):
        try:
            ambiguous_entities = _wm_salience_ambiguous_entities_v1(env_obs)
        except Exception:
            ambiguous_entities = set()

        salience = active_salience_tick(
            ctx,
            ww,
            changed_entities=changed_entities,
            new_cue_entities=new_cue_entities,
            ambiguous_entities=ambiguous_entities,
        )
        try:
            ctx.wm_salience_focus_entities = list(salience.get("focus_entities", []) or [])
            ctx.wm_salience_last_events = list(salience.get("events", []) or [])
        except Exception:
            pass
    else:
        try:
            ctx.wm_salience_focus_entities = []
            ctx.wm_salience_last_events = []
        except Exception:
            pass

    if bool(getattr(ctx, "wm_surfacegrid_enabled", False)):
        try:
            grid_w = int(getattr(ctx, "wm_surfacegrid_w", 16) or 16)
        except Exception:
            grid_w = 16
        try:
            grid_h = int(getattr(ctx, "wm_surfacegrid_h", 16) or 16)
        except Exception:
            grid_h = 16
        if grid_w <= 0:
            grid_w = 16
        if grid_h <= 0:
            grid_h = 16

        patches_raw = getattr(env_obs, "nav_patches", None) or []
        patches_in = (
            [patch for patch in patches_raw if isinstance(patch, dict)]
            if isinstance(patches_raw, list)
            else []
        )

        try:
            zoom_level = int(getattr(ctx, "wm_zoom_level", 0) or 0)
        except Exception:
            zoom_level = 0
        focus_entities = [
            str(entity).strip().lower()
            for entity in (getattr(ctx, "wm_salience_focus_entities", []) or [])
            if isinstance(entity, str) and entity.strip()
        ]
        fingerprint = _wm_surfacegrid_scene_fingerprint_v2(
            env_obs,
            patches_in,
            grid_w=grid_w,
            grid_h=grid_h,
            zoom_level=zoom_level,
            focus_entities=focus_entities,
        )
        reasons = _wm_surfacegrid_dirty_reasons_v2(ctx, fingerprint)
        dirty = any(reason != "cache_hit" for reason in reasons)

        previous_sig16 = getattr(ctx, "wm_surfacegrid_sig16", None)
        if not isinstance(previous_sig16, str) or not previous_sig16:
            previous_sig16 = None

        if dirty:
            started = time.perf_counter()
            try:
                surfacegrid = compose_surfacegrid_v1(patches_in, grid_w=grid_w, grid_h=grid_h)
            except Exception:
                surfacegrid = compose_surfacegrid_v1([], grid_w=grid_w, grid_h=grid_h)
                reasons = list(reasons) + ["compose_error"]

            elapsed_ms = (time.perf_counter() - started) * 1000.0
            ctx.wm_surfacegrid = surfacegrid
            try:
                ctx.wm_surfacegrid_sig16 = surfacegrid.sig16_v1()
            except Exception:
                ctx.wm_surfacegrid_sig16 = None

            new_sig16 = ctx.wm_surfacegrid_sig16 if isinstance(ctx.wm_surfacegrid_sig16, str) else None
            if (
                "patches_changed" in reasons
                and previous_sig16 is not None
                and new_sig16 is not None
                and new_sig16 == previous_sig16
                and "grid_missing" not in reasons
                and "grid_shape_changed" not in reasons
                and "self_window_shift" not in reasons
                and "zoom_changed" not in reasons
                and "focus_changed" not in reasons
                and "hazard_changed" not in reasons
                and "compose_error" not in reasons
            ):
                reasons = ["patch_payload_changed"] + [
                    reason for reason in reasons if reason != "patches_changed"
                ]

            ctx.wm_surfacegrid_last_input_sig16 = list(fingerprint.get("input_sig16", []) or [])
            ctx.wm_surfacegrid_compose_ms = float(elapsed_ms)
            ctx.wm_surfacegrid_dirty = False
            ctx.wm_surfacegrid_dirty_reasons = list(reasons) if reasons else ["dirty"]
            ctx.wm_surfacegrid_last_scene_fingerprint = dict(fingerprint)

            if bool(getattr(ctx, "wm_surfacegrid_verbose", False)):
                try:
                    ctx.wm_surfacegrid_last_ascii = surfacegrid.ascii_v1()
                except Exception:
                    ctx.wm_surfacegrid_last_ascii = None
            else:
                ctx.wm_surfacegrid_last_ascii = None
        else:
            ctx.wm_surfacegrid_last_input_sig16 = list(fingerprint.get("input_sig16", []) or [])
            ctx.wm_surfacegrid_compose_ms = 0.0
            ctx.wm_surfacegrid_dirty = False
            ctx.wm_surfacegrid_dirty_reasons = ["cache_hit"]
            ctx.wm_surfacegrid_last_scene_fingerprint = dict(fingerprint)

    try:
        current_surfacegrid = getattr(ctx, "wm_surfacegrid", None)
        if current_surfacegrid is not None:
            ctx.wm_surfacegrid_last_ascii = render_surfacegrid_ascii_with_salience_v1(
                ctx,
                ww,
                current_surfacegrid,
                focus_entities=list(getattr(ctx, "wm_salience_focus_entities", []) or []),
            )
    except Exception:
        pass

    if bool(getattr(ctx, "wm_grid_to_preds_enabled", False)):
        current_surfacegrid = getattr(ctx, "wm_surfacegrid", None)
        if current_surfacegrid is not None:
            try:
                slots = derive_grid_slot_families_v1(
                    current_surfacegrid,
                    self_xy=None,
                    r=2,
                    include_goal_dir=True,
                )
            except Exception:
                slots = {}
            ctx.wm_grid_slot_families = dict(slots) if isinstance(slots, dict) else {}

            try:
                entities = getattr(ctx, "wm_entities", {}) or {}
                self_bid = entities.get("self") if isinstance(entities, dict) else None
                if isinstance(self_bid, str) and self_bid:
                    ctx.wm_grid_pred_tags = wm_apply_grid_slot_families_to_mapsurface_v1(
                        ww,
                        self_bid,
                        ctx.wm_grid_slot_families,
                    )
                else:
                    ctx.wm_grid_pred_tags = []
            except Exception:
                ctx.wm_grid_pred_tags = []
        else:
            ctx.wm_grid_slot_families = {}
            ctx.wm_grid_pred_tags = []
    else:
        ctx.wm_grid_slot_families = {}
        ctx.wm_grid_pred_tags = []

    if bool(getattr(ctx, "wm_navsummary_enabled", True)):
        current_surfacegrid = getattr(ctx, "wm_surfacegrid", None)
        if current_surfacegrid is not None:
            try:
                local_radius = int(getattr(ctx, "wm_navsummary_local_radius", 2) or 2)
            except Exception:
                local_radius = 2
            local_radius = max(1, min(6, local_radius))

            try:
                ctx.wm_navsummary = compute_navsummary_v1(
                    current_surfacegrid,
                    slots=getattr(ctx, "wm_grid_slot_families", {}) or {},
                    self_xy=None,
                    local_radius=local_radius,
                )
            except Exception:
                ctx.wm_navsummary = {}
        else:
            ctx.wm_navsummary = {}
    else:
        ctx.wm_navsummary = {}

    return {
        "focus_entities": list(getattr(ctx, "wm_salience_focus_entities", []) or []),
        "surfacegrid_sig16": getattr(ctx, "wm_surfacegrid_sig16", None),
        "dirty_reasons": list(getattr(ctx, "wm_surfacegrid_dirty_reasons", []) or []),
        "grid_pred_tags": list(getattr(ctx, "wm_grid_pred_tags", []) or []),
        "navsummary": dict(getattr(ctx, "wm_navsummary", {}) or {}),
    }

# -----------------------------------------------------------------------------
# Working Memory refactor Phase 3: live observation injection and retrieval
# -----------------------------------------------------------------------------



def init_map_surface_world() -> tuple[cca8_world_graph.WorldGraph, dict[str, str]]:
    """Initialize a stateful MapSurface as a separate WorldGraph instance.

    Concept
    -------
    - WorkingMap (ctx.working_world) is episodic: we append bindings each tick to preserve a
      high-bandwidth trace.
    - MapSurface (ctx.map_surface_world) is stateful: it holds a small set of entity nodes
      (starting with SELF) whose pred:* tags are overwritten each tick by slot-family.

    Implementation detail
    ---------------------
    We treat the "NOW" anchor binding as the SELF node for MapSurface.
    """
    ms = cca8_world_graph.WorldGraph(memory_mode="semantic")
    ms.set_tag_policy("allow")
    ms.set_stage("neonate")
    self_bid = ms.ensure_anchor("NOW")
    ms.ensure_anchor("NOW_ORIGIN")
    ids = {"SELF": self_bid, "NOW": self_bid}
    return ms, ids


def _slot_key_from_token(tok: str) -> str:
    """Return a stable slot-family key for a token."""
    tok = str(tok)
    return tok.rsplit(":", 1)[0] if ":" in tok else tok


def update_surface_grid_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Update ctx.surface_grid from EnvObservation."""
    if ctx is None or env_obs is None:
        return
    sg = getattr(env_obs, "surface_grid", None)
    if isinstance(sg, dict):
        ctx.surface_grid = sg


def update_map_surface_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Update the stateful MapSurface SELF node from EnvObservation (overwrite-by-slot)."""
    if ctx is None or env_obs is None:
        return

    if getattr(ctx, "map_surface_world", None) is None:
        try:
            ctx.map_surface_world, ctx.map_surface_ids = init_map_surface_world()
        except Exception:
            return

    ms = ctx.map_surface_world
    if ms is None:
        return

    self_bid = (getattr(ctx, "map_surface_ids", {}) or {}).get("SELF")
    if not isinstance(self_bid, str):
        try:
            self_bid = ms.ensure_anchor("NOW")
            ctx.map_surface_ids = {"SELF": self_bid, "NOW": self_bid}
        except Exception:
            return

    b = ms._bindings.get(self_bid)
    if b is None:
        return

    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]

    keep: list[str] = []
    for tok in pred_tokens:
        if tok.startswith("proximity:") or tok.startswith("hazard:"):
            keep.append(tok)

    hazard_tok: str | None = None
    if any(t.startswith("hazard:") and t.endswith(":near") for t in keep):
        hazard_tok = "hazard:near"
    elif any(t.startswith("hazard:") and t.endswith(":far") for t in keep):
        hazard_tok = "hazard:far"
    if hazard_tok is not None:
        keep.append(hazard_tok)

    slots_to_write = {_slot_key_from_token(t) for t in keep}

    tags = set(getattr(b, "tags", []) or [])
    cleaned: set[str] = set()
    for t in tags:
        if not isinstance(t, str) or not t.startswith("pred:"):
            cleaned.add(t)
            continue
        tok = t.replace("pred:", "", 1)
        if _slot_key_from_token(tok) in slots_to_write:
            continue
        cleaned.add(t)

    for tok in keep:
        cleaned.add(f"pred:{tok}")

    b.tags = cleaned


def predcode_update_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Predictive coding v1: predict "no change" and compute which slots changed."""
    if ctx is None or env_obs is None:
        return
    if not bool(getattr(ctx, "predcode_enabled", True)):
        return

    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]

    observed_slots: dict[str, str] = {}
    for tok in pred_tokens:
        observed_slots[_slot_key_from_token(tok)] = tok

    predicted_slots = dict(getattr(ctx, "predcode_prev_slots", {}) or {})

    mismatches: list[dict[str, str]] = []
    for slot, pred_tok in predicted_slots.items():
        obs_tok = observed_slots.get(slot)
        if obs_tok is None:
            continue
        if obs_tok != pred_tok:
            mismatches.append({"slot": slot, "pred": str(pred_tok), "obs": str(obs_tok)})

    ctx.predcode_last_error = {
        "mismatch_count": len(mismatches),
        "mismatches": mismatches,
        "predicted_slots": len(predicted_slots),
        "observed_slots": len(observed_slots),
    }
    ctx.predcode_prev_slots = observed_slots

    if mismatches and getattr(ctx, "percept_focus", None) is None:
        slot0 = mismatches[0].get("slot")
        ctx.percept_focus = "proximity:mom" if isinstance(slot0, str) and slot0.startswith("proximity:mom") else slot0


def _wm_display_id(bid: str) -> str:
    """
    Display-only: show WorkingMap ids as wN while keeping real ids as bN.
    """
    try:
        if isinstance(bid, str) and bid.startswith("b") and bid[1:].isdigit():
            return "w" + bid[1:]
    except Exception:
        pass
    return f"w({bid})"


def _prune_working_world(ctx) -> None:
    """Keep the WorkingMap bounded so long runs do not explode memory.

    This only applies to ctx.working_world. It never touches the long-term `world`.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        return

    max_b = int(getattr(ctx, "working_max_bindings", 0) or 0)
    if max_b <= 0:
        return

    # Protect anchors + latest (so pruning doesn't sever the current frame completely)
    protected = set(getattr(ww, "_anchors", {}).values())  # pylint: disable=protected-access
    latest = getattr(ww, "_latest_binding_id", None)        # pylint: disable=protected-access
    if latest:
        protected.add(latest)

    def _bid_key(bid: str) -> int:
        try:
            return int(bid[1:]) if bid.startswith("b") else 10**9
        except Exception:
            return 10**9

    # Delete oldest non-protected bindings until within cap
    all_ids = sorted(list(getattr(ww, "_bindings", {}).keys()), key=_bid_key)  # pylint: disable=protected-access
    while len(getattr(ww, "_bindings", {})) > max_b:  # pylint: disable=protected-access
        binding_to_delete = None
        for bid in all_ids:
            if bid not in protected:
                binding_to_delete = bid
                break
        if binding_to_delete is None:
            break
        ww.delete_binding(binding_to_delete)
        all_ids.remove(binding_to_delete)


def _newborn_controller_step_int_v1(ctx: Ctx | None) -> int:
    """Return the current controller step as an int for newborn instrumentation."""
    if ctx is None:
        return 0
    try:
        return int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        return 0


def _append_newborn_retrieved_hint_event_v1(ctx: Ctx | None, event: dict[str, Any]) -> None:
    """Append one bounded retrieved-hint instrumentation event."""
    if ctx is None or not isinstance(event, dict):
        return

    try:
        events = getattr(ctx, "experiment_newborn_retrieved_hint_events", None)
        if not isinstance(events, list):
            events = []
        events.append(dict(event))

        if len(events) > 64:
            del events[:-64]

        ctx.experiment_newborn_retrieved_hint_events = events
    except Exception:
        pass


def _note_newborn_retrieved_hint_returned_v1(ctx: Ctx | None, hint: dict[str, Any]) -> None:
    """Record that a retrieved hint was active and returned to control this cycle.

    This is a control-use proxy. The helper counts each controller step at most
    once, even if several gate helpers consult the hint during the same cycle.
    """
    if ctx is None or not isinstance(hint, dict) or not hint:
        return

    step_now = _newborn_controller_step_int_v1(ctx)

    try:
        last_active = int(getattr(ctx, "experiment_newborn_retrieved_hint_last_active_step_counted", -1) or -1)
    except Exception:
        last_active = -1

    if last_active != step_now:
        try:
            ctx.experiment_newborn_retrieved_hint_active_step_count += 1
            ctx.experiment_newborn_retrieved_hint_last_active_step_counted = step_now
        except Exception:
            pass

    try:
        last_used = int(getattr(ctx, "experiment_newborn_retrieved_hint_last_used_step_counted", -1) or -1)
    except Exception:
        last_used = -1

    if last_used != step_now:
        try:
            ctx.experiment_newborn_retrieved_hint_used_step_count += 1
            ctx.experiment_newborn_retrieved_hint_last_used_step_counted = step_now
        except Exception:
            pass

        _append_newborn_retrieved_hint_event_v1(
            ctx,
            {
                "kind": "returned_to_control",
                "step": int(step_now),
                "source": getattr(ctx, "experiment_newborn_retrieved_hint_source", None),
                "until_step": getattr(ctx, "experiment_newborn_retrieved_hint_until_step", None),
                "hint_keys": sorted(k for k in hint.keys() if isinstance(k, str)),
            },
        )


def _newborn_retrieved_hint_debug_from_ctx_v1(ctx: Ctx | None) -> dict[str, Any]:
    """Return episode-level retrieved-hint instrumentation counters."""
    if ctx is None:
        return {
            "newborn_retrieved_hint_set_count": 0,
            "newborn_retrieved_hint_active_step_count": 0,
            "newborn_retrieved_hint_used_step_count": 0,
            "newborn_retrieved_hint_events": [],
        }

    def int_attr(name: str) -> int:
        try:
            return int(getattr(ctx, name, 0) or 0)
        except Exception:
            return 0

    events = getattr(ctx, "experiment_newborn_retrieved_hint_events", [])
    events = [dict(item) for item in events if isinstance(item, dict)] if isinstance(events, list) else []

    return {
        "newborn_retrieved_hint_set_count": int_attr("experiment_newborn_retrieved_hint_set_count"),
        "newborn_retrieved_hint_active_step_count": int_attr("experiment_newborn_retrieved_hint_active_step_count"),
        "newborn_retrieved_hint_used_step_count": int_attr("experiment_newborn_retrieved_hint_used_step_count"),
        "newborn_retrieved_hint_events": events[:24],
    }


def _clear_newborn_retrieved_hint_v1(ctx: Ctx | None) -> None:
    """Clear the short-lived newborn B2 retrieved-state hint."""
    if ctx is None:
        return
    try:
        ctx.experiment_newborn_retrieved_hint = {}
        ctx.experiment_newborn_retrieved_hint_until_step = -1
        ctx.experiment_newborn_retrieved_hint_source = None
    except Exception:
        pass


def _newborn_active_retrieved_hint_v1(ctx: Ctx | None) -> dict[str, Any]:
    """Return the active retrieved-state hint for newborn B2, or {} when absent/expired."""
    if ctx is None:
        return {}

    hint = getattr(ctx, "experiment_newborn_retrieved_hint", None)
    if not isinstance(hint, dict) or not hint:
        return {}

    try:
        raw_step = getattr(ctx, "controller_steps", 0)
        raw_until = getattr(ctx, "experiment_newborn_retrieved_hint_until_step", -1)

        step_now = int(raw_step) if raw_step is not None else 0
        until_step = int(raw_until) if raw_until is not None else -1
    except Exception:
        return {}

    if step_now > until_step:
        _clear_newborn_retrieved_hint_v1(ctx)
        return {}

    _note_newborn_retrieved_hint_returned_v1(ctx, hint)
    return dict(hint)


def _decode_newborn_hint_from_mapsurface_record_v1(rec: dict[str, Any]) -> dict[str, Any]:
    """Decode a tiny control-relevant state hint from a wm_mapsurface Column record.

    The benchmark does not need the full retrieved map to influence control.
    It needs only a few values that matter at the newborn decision seam:

      - posture
      - mom_distance
      - nipple_state
      - zone

    We first prefer the payload header's BodyMap summary if present. If that is
    missing or incomplete, we fall back to parsing entity preds.
    """
    if not isinstance(rec, dict):
        return {}

    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {}

    hint: dict[str, Any] = {}

    header = payload.get("header")
    header = header if isinstance(header, dict) else {}
    body = header.get("body")
    body = body if isinstance(body, dict) else {}

    for key in ("posture", "mom_distance", "nipple_state", "zone"):
        val = body.get(key)
        if isinstance(val, str) and val:
            hint[key] = val

    ents = payload.get("entities")
    ents = ents if isinstance(ents, list) else []

    shelter_near = False
    cliff_near = False

    for ent in ents:
        if not isinstance(ent, dict):
            continue

        preds = ent.get("preds")
        preds = preds if isinstance(preds, list) else []

        for tok in preds:
            if not isinstance(tok, str) or not tok:
                continue

            if "posture" not in hint:
                if tok == "resting":
                    hint["posture"] = "resting"
                elif tok == "posture:standing":
                    hint["posture"] = "standing"
                elif tok == "posture:fallen":
                    hint["posture"] = "fallen"

            if "mom_distance" not in hint:
                if tok == "proximity:mom:close":
                    hint["mom_distance"] = "near"
                elif tok == "proximity:mom:far":
                    hint["mom_distance"] = "far"

            if tok == "milk:drinking":
                hint["milk_drinking"] = True

            if "nipple_state" not in hint:
                if tok in ("nipple:latched", "milk:drinking"):
                    hint["nipple_state"] = "latched"
                elif tok == "nipple:found":
                    hint["nipple_state"] = "reachable"
                elif tok == "nipple:hidden":
                    hint["nipple_state"] = "hidden"

            if tok == "proximity:shelter:near":
                shelter_near = True
            elif tok == "hazard:cliff:near":
                cliff_near = True

    if "zone" not in hint:
        if cliff_near and not shelter_near:
            hint["zone"] = "unsafe_cliff_near"
        elif shelter_near and not cliff_near:
            hint["zone"] = "safe"

    return hint


def _set_newborn_retrieved_hint_from_engram_v1(
    ctx: Ctx | None,
    engram_id: str,
    *,
    ttl_steps: int = 3,
    column_memory: Any | None = None,
) -> dict[str, Any]:
    """Decode and store a short-lived retrieved-state hint from a wm_mapsurface engram.

    This is benchmark-only glue. It does not replace BodyMap. It simply lets a
    successful newborn retrieval restore a few decision-relevant values for a
    short time when current evidence is sparse.
    """
    active_column = column_memory if column_memory is not None else column_mem

    if ctx is None:
        return {}
    if not isinstance(engram_id, str) or not engram_id:
        return {}

    rec = active_column.try_get(engram_id)
    if not isinstance(rec, dict):
        _clear_newborn_retrieved_hint_v1(ctx)
        return {}

    hint = _decode_newborn_hint_from_mapsurface_record_v1(rec)
    if not hint:
        _clear_newborn_retrieved_hint_v1(ctx)
        return {}

    try:
        raw_step = getattr(ctx, "controller_steps", 0)
        step_now = int(raw_step) if raw_step is not None else 0
    except Exception:
        step_now = 0

    ttl_i = max(1, int(ttl_steps))

    try:
        until_step = step_now + ttl_i
        ctx.experiment_newborn_retrieved_hint = dict(hint)
        ctx.experiment_newborn_retrieved_hint_until_step = until_step
        ctx.experiment_newborn_retrieved_hint_source = engram_id
        ctx.experiment_newborn_retrieved_hint_set_count += 1

        _append_newborn_retrieved_hint_event_v1(
            ctx,
            {
                "kind": "set",
                "step": int(step_now),
                "until_step": int(until_step),
                "source": engram_id,
                "hint": dict(hint),
            },
        )
    except Exception:
        pass

    return dict(hint)


def should_autoretrieve_mapsurface(
    ctx: Ctx,
    env_obs: EnvObservation | None,
    *,
    stage: str | None,
    zone: str | None,
    stage_changed: bool,
    zone_changed: bool,
    forced_keyframe: bool = False,
    boundary_reason: str | None = None,
    bodymap_is_stale_fn: Callable[[Any], bool] = bodymap_is_stale,
) -> dict[str, Any]:
    """Guard hook: decide whether CCA8 should attempt MapSurface auto-retrieval *right now*.

    What this is (plain English)
    ----------------------------
    Auto-retrieve is the read-path side of the memory pipeline:

        Column engram (wm_mapsurface payload)  →  WorkingMap.MapSurface (as a prior)

    We consider it at keyframes so the system can "snap into" a previously seen scene configuration
    without bloating the long-term WorldGraph. WorldGraph stores only a thin pointer; the heavy
    MapSurface payload lives in Column memory.

    Minimal gating (Phase VIII)
    ---------------------------
    Historically this hook was a simple baseline: if enabled + boundary → attempt.
    We now add a conservative gating rule so *prediction error and partial observability matter*:

      Attempt auto-retrieve only when ALL are true:
        1) enabled, and
        2) this call is occurring on a keyframe boundary (stage/zone boundary), and
        3) we have evidence priors may help, i.e. at least one of:
             - missingness: this observation dropped tokens due to obs-mask (or obs packet is very sparse / None)
             - pred_err:   ctx.pred_err_v0_last has any non-zero component (v0 currently tracks posture mismatch)
             - stale:      BodyMap is stale (priors can stabilize belief when fast registers are unreliable)

    This is intentionally conservative: in rich-observation demos, retrieval often becomes a no-op anyway.
    The gating keeps the logs meaningful and prevents "always retrieve" behavior from dominating experiments.

    Returns
    -------
    dict with stable keys:
      ok:
        True if we should attempt auto-retrieval now.
      why:
        Short reason string for logs/tests.
      mode:
        Normalized retrieval mode to use ("merge" or "replace").
      top_k:
        Candidate budget (int, clamped to 2..10).
      verbose:
        Whether the caller should print diagnostic lines.
      diag:
        Small diagnostic dictionary (counts, flags, stage/zone) for optional logging.
    """
    enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False))
    verbose = bool(getattr(ctx, "wm_mapsurface_autoretrieve_verbose", False))

    # Normalize mode (keep conservative by default)
    mode_raw = (getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge")
    mode_eff = str(mode_raw).strip().lower()
    if mode_eff not in ("merge", "replace", "r"):
        mode_eff = "merge"
    if mode_eff == "r":
        mode_eff = "replace"

    # Clamp top_k so exclusion has room to choose a second candidate.
    try:
        top_raw = int(getattr(ctx, "wm_mapsurface_autoretrieve_top_k", 5) or 5)
    except Exception:
        top_raw = 5
    top_k = max(2, min(10, int(top_raw)))

    # Cheap diagnostic counts (do not depend on exact schema)
    pred_n = 0
    cue_n = 0
    try:
        preds = getattr(env_obs, "predicates", None) if env_obs is not None else None
        cues = getattr(env_obs, "cues", None) if env_obs is not None else None
        pred_n = len(preds) if isinstance(preds, list) else 0
        cue_n = len(cues) if isinstance(cues, list) else 0
    except Exception:
        pred_n = 0
        cue_n = 0

    boundary = bool(stage_changed) or bool(zone_changed) or bool(forced_keyframe)

    diag: dict[str, Any] = {
        "stage": stage,
        "zone": zone,
        "stage_changed": bool(stage_changed),
        "zone_changed": bool(zone_changed),
        "boundary_reason": boundary_reason,
        "pred_n": pred_n,
        "cue_n": cue_n,
    }

    if not enabled:
        diag["need_priors"] = False
        return {"ok": False, "why": "disabled", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    if not boundary:
        diag["need_priors"] = False
        return {"ok": False, "why": "not_boundary", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    # ---- Minimal gating signals (missingness + pred_err + BodyMap staleness) ----
    body_stale = True
    try:
        body_stale = bool(bodymap_is_stale_fn(ctx))
    except Exception:
        body_stale = True

    pred_err_any = False
    pred_err_posture = 0
    try:
        pe = getattr(ctx, "pred_err_v0_last", None)
        if isinstance(pe, dict) and pe:
            try:
                pred_err_posture = int(pe.get("posture", 0) or 0)
            except Exception:
                pred_err_posture = 0
            try:
                pred_err_any = any(int(v or 0) != 0 for v in pe.values())
            except Exception:
                pred_err_any = pred_err_posture != 0
    except Exception:
        pred_err_any = False
        pred_err_posture = 0

    mask_dropped_preds = 0
    mask_dropped_cues = 0
    try:
        meta = getattr(env_obs, "env_meta", None) if env_obs is not None else None
        if isinstance(meta, dict):
            mask_dropped_preds = int(meta.get("obs_mask_dropped_preds", 0) or 0)
            mask_dropped_cues = int(meta.get("obs_mask_dropped_cues", 0) or 0)
    except Exception:
        mask_dropped_preds = 0
        mask_dropped_cues = 0

    # Treat a missing/very-sparse obs packet as missingness (priors likely helpful).
    sparse_obs = (env_obs is None) or (pred_n <= 1 and cue_n <= 0)
    missingness = sparse_obs or ((mask_dropped_preds + mask_dropped_cues) > 0)

    need_priors = bool(pred_err_any) or bool(missingness) or bool(body_stale)

    diag.update(
        {
            "pred_err_any": bool(pred_err_any),
            "pred_err_posture": int(pred_err_posture),
            "mask_dropped_preds": int(mask_dropped_preds),
            "mask_dropped_cues": int(mask_dropped_cues),
            "bodymap_stale": bool(body_stale),
            "sparse_obs": bool(sparse_obs),
            "missingness": bool(missingness),
            "need_priors": bool(need_priors),
        }
    )

    if not need_priors:
        return {"ok": False, "why": "enabled_boundary_confident", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    if pred_err_any:
        why = "enabled_boundary_pred_err"
    elif missingness:
        why = "enabled_boundary_missing"
    else:
        why = "enabled_boundary_bodymap_stale"

    return {"ok": True, "why": why, "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}


def maybe_autoretrieve_mapsurface_on_keyframe(
    world,
    ctx: Ctx,
    *,
    stage: str | None,
    zone: str | None,
    exclude_engram_id: str | None = None,
    reason: str = "auto_keyframe",
    mode: str | None = None,
    top_k: int | None = None,
    max_scan: int = 500,
    log: bool | None = None,
    pick_best_fn: Callable[..., dict[str, Any]] = pick_best_wm_mapsurface_rec,
    load_engram_fn: Callable[..., dict[str, Any]] = load_wm_mapsurface_engram_into_workingmap_mode,
    log_event_fn: Callable[..., dict[str, Any]] = _wm_log_mapswitch_event_v1,
    format_event_fn: Callable[[dict[str, Any]], str] = format_mapswitch_event_line_v1,
) -> dict[str, Any]:
    """Try to seed WorkingMap from a prior wm_mapsurface engram on a keyframe boundary.

    This is the *read-path* complement to store_mapsurface_snapshot_v1(...).

    In addition to returning the load result, this function now records a structured
    map-switch event containing:
      - candidates considered,
      - chosen seed,
      - drop/no-op reason,
      - and cue-leakage guardrail outcome for merge mode.
    """
    if ctx is None or world is None:
        return {"ok": False, "why": "missing_ctx_or_world"}

    if not bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False)):
        return {"ok": False, "why": "disabled"}

    mode_eff = (mode or getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
    top_eff = top_k if isinstance(top_k, int) else int(getattr(ctx, "wm_mapsurface_autoretrieve_top_k", 5) or 5)
    top_eff = max(2, min(10, int(top_eff)))

    pick = pick_best_fn(
        stage=stage,
        zone=zone,
        ctx=ctx,
        long_world=world,
        allow_fallback=True,
        max_scan=max(1, int(max_scan)),
        top_k=top_eff,
    )

    source = pick.get("source") if isinstance(pick, dict) and isinstance(pick.get("source"), str) else None
    match = pick.get("match") if isinstance(pick, dict) and isinstance(pick.get("match"), str) else None
    ranked = pick.get("ranked") if isinstance(pick, dict) and isinstance(pick.get("ranked"), list) else []

    if not ranked:
        event = log_event_fn(
            ctx,
            ok=False,
            why="no_candidates",
            reason=reason,
            stage=stage,
            zone=zone,
            mode=mode_eff,
            source=source,
            match=match,
            top_k=top_eff,
            exclude_engram_id=exclude_engram_id,
            ranked=ranked,
            chosen=None,
            load=None,
        )
        return {"ok": False, "why": "no_candidates", "pick": pick, "event": event}

    chosen: dict[str, Any] | None = None
    for cand in ranked:
        if not isinstance(cand, dict):
            continue
        eid = cand.get("engram_id")
        if not isinstance(eid, str) or not eid:
            continue
        if isinstance(exclude_engram_id, str) and exclude_engram_id and eid == exclude_engram_id:
            continue
        chosen = cand
        break

    if chosen is None:
        event = log_event_fn(
            ctx,
            ok=False,
            why="only_excluded_candidate",
            reason=reason,
            stage=stage,
            zone=zone,
            mode=mode_eff,
            source=source,
            match=match,
            top_k=top_eff,
            exclude_engram_id=exclude_engram_id,
            ranked=ranked,
            chosen=None,
            load=None,
        )
        return {"ok": False, "why": "only_excluded_candidate", "pick": pick, "event": event}

    eid = chosen.get("engram_id")
    if not isinstance(eid, str) or not eid:
        event = log_event_fn(
            ctx,
            ok=False,
            why="bad_engram_id",
            reason=reason,
            stage=stage,
            zone=zone,
            mode=mode_eff,
            source=source,
            match=match,
            top_k=top_eff,
            exclude_engram_id=exclude_engram_id,
            ranked=ranked,
            chosen=chosen,
            load=None,
        )
        return {"ok": False, "why": "bad_engram_id", "pick": pick, "event": event}

    if mode_eff in ("replace", "r"):
        load = load_engram_fn(ctx, eid, mode="replace")
    else:
        load = load_engram_fn(ctx, eid, mode="merge")

    try:
        ctx.wm_mapsurface_last_autoretrieve_engram_id = eid
        ctx.wm_mapsurface_last_autoretrieve_reason = reason
    except Exception:
        pass

    event = log_event_fn(
        ctx,
        ok=True,
        why="ok",
        reason=reason,
        stage=stage,
        zone=zone,
        mode=mode_eff,
        source=source,
        match=match,
        top_k=top_eff,
        exclude_engram_id=exclude_engram_id,
        ranked=ranked,
        chosen=chosen,
        load=load if isinstance(load, dict) else None,
    )

    log_enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_verbose", False))
    if log is not None:
        log_enabled = bool(log)

    if log_enabled:
        try:
            print("[wm-mapswitch] " + format_event_fn(event))
        except Exception:
            pass

    return {
        "ok": True,
        "engram_id": eid,
        "chosen": chosen,
        "pick": pick,
        "load": load,
        "event": event,
    }


def _goat04_context_milestone_label_v1(env_obs: EnvObservation) -> str | None:
    """Return 'fox' or 'hawk' when this observation carries a goat_foraging_04 context milestone."""
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}

    stage = meta.get("scenario_stage")
    if stage != "goat_foraging_04_scan":
        return None

    raw = meta.get("milestones") or meta.get("milestone")
    items: list[str] = []
    if isinstance(raw, str) and raw:
        items = [raw]
    elif isinstance(raw, list):
        items = [m for m in raw if isinstance(m, str) and m]

    for m in items:
        if m == "context:fox":
            return "fox"
        if m == "context:hawk":
            return "hawk"
    return None


def maybe_goat04_context_mapswitch_on_keyframe_v1(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    body_space_zone_fn: Callable[[Any], Any] = body_space_zone,
    store_snapshot_fn: Callable[..., dict[str, Any]] = store_mapsurface_snapshot_v1,
    autoretrieve_fn: Callable[..., dict[str, Any]] = maybe_autoretrieve_mapsurface_on_keyframe,
) -> dict[str, Any]:
    """goat_foraging_04 evaluation harness:

    - first fox milestone  -> store a fox wm_mapsurface
    - first hawk milestone -> store a hawk wm_mapsurface
    - later alternating milestones -> attempt auto-retrieve/apply

    Returns a small dict for the cycle footer:
      {
        "handled": bool,
        "store": str|None,
        "retrieve": str|None,
        "apply": str|None,
      }
    """
    out: dict[str, Any] = {"handled": False, "store": None, "retrieve": None, "apply": None}

    if ctx is None or world is None or env_obs is None:
        return out

    label = _goat04_context_milestone_label_v1(env_obs)
    if label not in ("fox", "hawk"):
        return out

    out["handled"] = True

    seeded = getattr(ctx, "wm_goat04_seeded_contexts", None)
    if not isinstance(seeded, set):
        seeded = set()
        ctx.wm_goat04_seeded_contexts = seeded

    seed_map = getattr(ctx, "wm_goat04_seed_engram_by_context", None)
    if not isinstance(seed_map, dict):
        seed_map = {}
        ctx.wm_goat04_seed_engram_by_context = seed_map

    # Stage/zone for retrieval filtering
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}
    stage = meta.get("scenario_stage")
    stage = stage if isinstance(stage, str) and stage else None

    try:
        zone = body_space_zone_fn(ctx)
    except Exception:
        zone = None
    zone = zone if isinstance(zone, str) and zone else None

    # ------------------------------------------------------------------
    # First time we see a context milestone: STORE a seed snapshot.
    # ------------------------------------------------------------------
    if label not in seeded:
        info = store_snapshot_fn(
            world,
            ctx,
            reason=f"goat04_seed:{label}",
            attach="now",
            force=True,
            quiet=True,
        )

        sig16 = str(info.get("sig") or "")[:16]
        eid = info.get("engram_id")
        eid_txt = (eid[:8] + "…") if isinstance(eid, str) and eid else "(n/a)"

        if bool(info.get("stored")):
            seeded.add(label)
            if isinstance(eid, str) and eid:
                seed_map[label] = eid

            print(f"[wm<->col] store: goat04 seed context={label} sig={sig16} eid={eid_txt}")
            out["store"] = f"store goat04:{label} sig={sig16} eid={eid_txt}"
        else:
            why = info.get("why")
            if isinstance(eid, str) and eid:
                seeded.add(label)
                seed_map[label] = eid
            print(f"[wm<->col] store: goat04 seed context={label} skip={why} sig={sig16}")
            out["store"] = f"store goat04:{label} skip={why} sig={sig16}"

        return out

    # ------------------------------------------------------------------
    # Later alternating milestones: RETRIEVE/APPLY only after both seeds exist.
    # ------------------------------------------------------------------
    if not ("fox" in seed_map and "hawk" in seed_map):
        return out

    mode_txt = "merge"
    top_k = 5
    ret = autoretrieve_fn(
        world,
        ctx,
        stage=stage,
        zone=zone,
        exclude_engram_id=None,
        reason=f"goat04_context:{label}",
        mode=mode_txt,
        top_k=top_k,
        log=False,   # footer owns the compact standardized log line
    )

    # Build a compact event payload so [cycle] MS can show it even if the generic path was bypassed.
    pick_raw = ret.get("pick")
    pick: dict[str, Any] = pick_raw if isinstance(pick_raw, dict) else {}
    ranked_raw = pick.get("ranked")
    ranked: list[Any] = ranked_raw if isinstance(ranked_raw, list) else []
    chosen_raw = ret.get("chosen")
    chosen: dict[str, Any] = chosen_raw if isinstance(chosen_raw, dict) else {}
    load_raw = ret.get("load")
    load: dict[str, Any] = load_raw if isinstance(load_raw, dict) else {}

    chosen_rank = None
    chosen_eid = chosen.get("engram_id") if isinstance(chosen, dict) else None
    if isinstance(chosen_eid, str) and isinstance(ranked, list):
        for idx, cand in enumerate(ranked, start=1):
            if isinstance(cand, dict) and cand.get("engram_id") == chosen_eid:
                chosen_rank = idx
                break

    event = {
        "schema": "wm_mapswitch_event_v1",
        "ok": bool(isinstance(ret, dict) and ret.get("ok")),
        "why": str(ret.get("why") or ("ok" if ret.get("ok") else "no-op")) if isinstance(ret, dict) else "error",
        "mode": mode_txt,
        "reason": f"goat04_context:{label}",
        "stage": stage,
        "zone": zone,
        "match": pick.get("match") if isinstance(pick, dict) else None,
        "candidate_count": len(ranked) if isinstance(ranked, list) else 0,
        "chosen_seed": chosen if isinstance(chosen, dict) and chosen else None,
        "chosen_rank": chosen_rank,
        "drop_reason": None if bool(isinstance(ret, dict) and ret.get("ok")) else (ret.get("why") if isinstance(ret, dict) else "error"),
        "load": load if isinstance(load, dict) else {},
    }

    try:
        ctx.wm_mapswitch_last_events = [event]
    except Exception:
        pass
    try:
        hist = getattr(ctx, "wm_mapswitch_history", None)
        if not isinstance(hist, list):
            hist = []
        hist.append(event)
        lim = int(getattr(ctx, "wm_mapswitch_history_limit", 50) or 50)
        lim = max(1, min(500, lim))
        if len(hist) > lim:
            del hist[:-lim]
        ctx.wm_mapswitch_history = hist
    except Exception:
        pass

    if bool(ret.get("ok")):
        rid = ret.get("engram_id")
        rid_txt = (rid[:8] + "…") if isinstance(rid, str) and rid else "(n/a)"
        match = pick.get("match") if isinstance(pick, dict) else None
        cand_n = len(ranked) if isinstance(ranked, list) else 0

        print(f"[wm<->col] retrieve: goat04 context={label} ok mode={mode_txt} eid={rid_txt} match={match} cand_n={cand_n}")
        out["retrieve"] = f"retrieve goat04:{label} ok eid={rid_txt} match={match} cand_n={cand_n}"

        if load.get("mode") == "replace":
            ent_n = load.get("entities")
            rel_n = load.get("relations")
            print(f"[wm<->col] apply: replace entities={ent_n} relations={rel_n}")
            out["apply"] = f"apply replace ent={ent_n} rel={rel_n}"
        else:
            ae = load.get("added_entities")
            fs = load.get("filled_slots")
            ed = load.get("added_edges")
            pc = load.get("stored_prior_cues")

            guard_ok = load.get("merge_guardrail_ok")
            cue_delta = load.get("cue_tag_delta")
            if guard_ok is True:
                guard_txt = " cue_guard=ok"
            elif guard_ok is False:
                try:
                    d_i = int(cue_delta) if cue_delta is not None else None
                except Exception:
                    d_i = None
                if isinstance(d_i, int):
                    guard_txt = f" cue_guard=leak(+{d_i})"
                else:
                    guard_txt = " cue_guard=leak"
            else:
                guard_txt = ""

            print(
                f"[wm<->col] apply: merge added_entities={ae} filled_slots={fs} "
                f"added_edges={ed} prior_cues={pc}{guard_txt}"
            )
            out["apply"] = f"apply merge ent+{ae} slots+{fs} edges+{ed} prior_cues={pc}{guard_txt}"
    else:
        why = ret.get("why") if isinstance(ret, dict) else "error"
        print(f"[wm<->col] retrieve: goat04 context={label} skip why={why}")
        print(f"[wm<->col] apply: no-op ({why})")
        out["retrieve"] = f"retrieve goat04:{label} skip why={why}"
        out["apply"] = f"apply no-op ({why})"

    return out


def _newborn_b2_seed_label_v1(env_obs: EnvObservation) -> str | None:
    """Return the newborn B2 milestone label that should create a reusable seed snapshot.

    I keep this narrow and explicit. We only seed a few meaningful control states:
      - stood_up
      - reached_mom
      - latched_nipple
      - milk drinking
      - rested

    That gives the benchmark a small reusable memory library inside one episode
    without turning the newborn task into a generic snapshot dump.
    """
    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}

    raw = meta.get("milestones") or meta.get("milestone")
    items: list[str] = []

    if isinstance(raw, str) and raw:
        items = [raw]
    elif isinstance(raw, list):
        items = [m for m in raw if isinstance(m, str) and m]

    for label in ("stood_up", "reached_mom", "latched_nipple", "milk_drinking", "rested"):
        if label in items:
            return label
    return None


def maybe_newborn_b2_mapswitch_on_keyframe_v1(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    body_space_zone_fn: Callable[[Any], Any] = body_space_zone,
    store_snapshot_fn: Callable[..., dict[str, Any]] = store_mapsurface_snapshot_v1,
    autoretrieve_fn: Callable[..., dict[str, Any]] = maybe_autoretrieve_mapsurface_on_keyframe,
    set_retrieved_hint_fn: Callable[..., dict[str, Any]] = _set_newborn_retrieved_hint_from_engram_v1,
    clear_retrieved_hint_fn: Callable[[Ctx | None], None] = _clear_newborn_retrieved_hint_v1,
) -> dict[str, Any]:
    """newborn_long_horizon evaluation harness.

    What this does
    --------------
    - first meaningful newborn milestones store compact wm_mapsurface seeds
    - later newborn keyframes may retrieve/apply those seeds when auto-retrieve is enabled

    Why this exists
    ---------------
    goat04 already has an explicit benchmark-side store/retrieve seam.
    newborn_long_horizon did not. That meant A vs B differed in flags, but not in
    whether any real episodic readback event actually occurred.

    This helper gives B2 a real within-episode readback loop without changing
    ordinary interactive runs.
    """
    out: dict[str, Any] = {"handled": False, "store": None, "retrieve": None, "apply": None}

    if ctx is None or world is None or env_obs is None:
        return out
    if not bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)):
        return out

    meta = getattr(env_obs, "env_meta", None)
    meta = meta if isinstance(meta, dict) else {}
    stage = meta.get("scenario_stage")
    stage = stage if isinstance(stage, str) and stage else None

    if stage not in ("struggle", "first_stand", "first_latch", "rest"):
        return out

    out["handled"] = True

    seeded = getattr(ctx, "wm_newborn_b2_seeded_labels", None)
    if not isinstance(seeded, set):
        seeded = set()
        ctx.wm_newborn_b2_seeded_labels = seeded

    seed_map = getattr(ctx, "wm_newborn_b2_seed_engram_by_label", None)
    if not isinstance(seed_map, dict):
        seed_map = {}
        ctx.wm_newborn_b2_seed_engram_by_label = seed_map

    label = _newborn_b2_seed_label_v1(env_obs)

    # First time we hit a meaningful milestone, store a reusable seed.
    if label and label not in seeded:
        info = store_snapshot_fn(
            world,
            ctx,
            reason=f"newborn_b2_seed:{label}",
            attach="now",
            force=True,
            quiet=True,
        )

        sig16 = str(info.get("sig") or "")[:16]
        eid = info.get("engram_id")
        eid_txt = (eid[:8] + "…") if isinstance(eid, str) and eid else "(n/a)"

        if bool(info.get("stored")):
            seeded.add(label)
            if isinstance(eid, str) and eid:
                seed_map[label] = eid

            print(f"[wm<->col] store: newborn_b2 seed={label} sig={sig16} eid={eid_txt}")
            out["store"] = f"store newborn_b2:{label} sig={sig16} eid={eid_txt}"
        else:
            why = info.get("why")
            if isinstance(eid, str) and eid:
                seeded.add(label)
                seed_map[label] = eid

            print(f"[wm<->col] store: newborn_b2 seed={label} skip={why} sig={sig16}")
            out["store"] = f"store newborn_b2:{label} skip={why} sig={sig16}"

        return out

    # No stored seeds yet -> nothing to retrieve.
    if not seed_map:
        return out

    try:
        zone = body_space_zone_fn(ctx)
    except Exception:
        zone = None
    zone = zone if isinstance(zone, str) and zone else None

    mode_txt = str(getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
    try:
        top_k = int(getattr(ctx, "wm_mapsurface_autoretrieve_top_k", 5) or 5)
    except Exception:
        top_k = 5
    top_k = max(2, min(10, top_k))

    ret = autoretrieve_fn(
        world,
        ctx,
        stage=stage,
        zone=zone,
        exclude_engram_id=None,
        reason=f"newborn_b2:{stage}:{label or 'boundary'}",
        mode=mode_txt,
        top_k=top_k,
        log=False,
    )

    if bool(ret.get("ok")):
        rid = ret.get("engram_id")
        rid_txt = (rid[:8] + "…") if isinstance(rid, str) and rid else "(n/a)"

        try:
            if isinstance(rid, str) and rid:
                set_retrieved_hint_fn(ctx, rid, ttl_steps=3)
        except Exception:
            pass

        pick_raw = ret.get("pick")
        pick: dict[str, Any] = pick_raw if isinstance(pick_raw, dict) else {}
        match = pick.get("match")
        ranked_raw = pick.get("ranked")
        ranked: list[Any] = ranked_raw if isinstance(ranked_raw, list) else []
        cand_n = len(ranked)

        print(
            f"[wm<->col] retrieve: newborn_b2 stage={stage} ok mode={mode_txt} "
            f"eid={rid_txt} match={match} cand_n={cand_n}"
        )
        out["retrieve"] = f"retrieve newborn_b2:{stage} ok eid={rid_txt} match={match} cand_n={cand_n}"

        load_raw = ret.get("load")
        load: dict[str, Any] = load_raw if isinstance(load_raw, dict) else {}
        if load.get("mode") == "replace":
            ent_n = load.get("entities")
            rel_n = load.get("relations")
            print(f"[wm<->col] apply: replace entities={ent_n} relations={rel_n}")
            out["apply"] = f"apply replace ent={ent_n} rel={rel_n}"
        else:
            ae = load.get("added_entities")
            fs = load.get("filled_slots")
            ed = load.get("added_edges")
            pc = load.get("stored_prior_cues")

            guard_ok = load.get("merge_guardrail_ok")
            cue_delta = load.get("cue_tag_delta")
            if guard_ok is True:
                guard_txt = " cue_guard=ok"
            elif guard_ok is False:
                try:
                    delta_i = int(cue_delta) if cue_delta is not None else None
                except Exception:
                    delta_i = None
                if isinstance(delta_i, int):
                    guard_txt = f" cue_guard=leak(+{delta_i})"
                else:
                    guard_txt = " cue_guard=leak"
            else:
                guard_txt = ""

            print(
                f"[wm<->col] apply: merge added_entities={ae} filled_slots={fs} "
                f"added_edges={ed} prior_cues={pc}{guard_txt}"
            )
            out["apply"] = f"apply merge ent+{ae} slots+{fs} edges+{ed} prior_cues={pc}{guard_txt}"
    else:
        try:
            clear_retrieved_hint_fn(ctx)
        except Exception:
            pass

        why = ret.get("why") if isinstance(ret, dict) else "error"
        print(f"[wm<->col] retrieve: newborn_b2 stage={stage} skip why={why}")
        print(f"[wm<->col] apply: no-op ({why})")
        out["retrieve"] = f"retrieve newborn_b2:{stage} skip why={why}"
        out["apply"] = f"apply no-op ({why})"

    return out


def inject_obs_into_working_world(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    init_working_world_fn: Callable[[], cca8_world_graph.WorldGraph] = init_working_world,
    display_id_fn: Callable[[str], str] = _wm_display_id,
    store_navpatch_fn: Callable[..., dict[str, Any]] = store_navpatch_engram_v1,
    salience_tick_fn: Callable[..., dict[str, Any]] = wm_salience_tick_v1,
    body_cliff_distance_fn: Callable[[Any], Any] = body_cliff_distance,
    prune_working_world_fn: Callable[[Any], None] = _prune_working_world,
) -> dict[str, Any]:
    """
    Mirror EnvObservation into WorkingMap.

    Phase VII default: MapSurface (stable map)
    -----------------------------------------
    - We maintain *stable* entity bindings (SELF, MOM, SHELTER, CLIFF, ...).
    - We update pred:* and cue:* tags IN PLACE (so step 2 does NOT create new posture/mom/etc. nodes).
    - We store a 2D "schematic" coordinate frame in binding.meta["wm"]["pos"] (distorted, subway-map style).

    Optional debug: if ctx.working_trace=True, we also append a per-tick trace using add_predicate/add_cue
    (old behaviour) after updating the map.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        try:
            ctx.working_world = init_working_world_fn()
            ww = ctx.working_world
        except Exception:
            return {"predicates": [], "cues": []}

    if ww is None:
        return {"predicates": [], "cues": []}

    changed_entities: set[str] = set()
    new_cue_entities: set[str] = set()
    prev_cues_by_ent: dict[str, set[str]] = {}
    try:
        prev = getattr(ctx, "wm_last_env_cues", None)
        if isinstance(prev, dict):
            for k, v in prev.items():
                if isinstance(k, str) and isinstance(v, set):
                    prev_cues_by_ent[k] = set(v)
    except Exception:
        prev_cues_by_ent = {}

    meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
    created_preds: list[str] = []
    created_cues: list[str] = []

    # -------------------- small helpers (robust to tags=list vs tags=set) --------------------
    def _tagset_of(bid: str) -> set[str]:
        b = ww._bindings.get(bid)
        if b is None:
            return set()
        ts = getattr(b, "tags", None)
        if ts is None:
            b.tags = set()
            return b.tags
        if isinstance(ts, set):
            return ts
        if isinstance(ts, list):
            s = set(ts)
            b.tags = s
            return s
        try:
            s = set(ts)  # last resort
            b.tags = s
            return s
        except Exception:
            b.tags = set()
            return b.tags

    def _sanitize_entity_anchor(entity_id: str) -> str:
        s = (entity_id or "unknown").strip().upper()
        out: list[str] = []
        for ch in s:
            out.append(ch if ch.isalnum() else "_")
        s = "".join(out)
        while "__" in s:
            s = s.replace("__", "_")
        s = s.strip("_") or "UNKNOWN"
        return f"WM_ENT_{s}"

    def _upsert_edge(src: str, dst: str, label: str, meta2: dict | None = None) -> None:
        b = ww._bindings.get(src)
        if b is None:
            return
        edges = getattr(b, "edges", None)
        if edges is None or not isinstance(edges, list):
            b.edges = []
            edges = b.edges
        # update if exists
        for e in edges:
            try:
                to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                lab = e.get("label") or e.get("rel") or e.get("relation")
                # Treat wm_has as a legacy alias of wm_entity (cosmetic rename)
                if label == "wm_entity" and to_ == dst and lab in ("wm_entity", "wm_has"):
                    # migrate label in-place (prevents duplicate edges)
                    if lab != "wm_entity":
                        e["label"] = "wm_entity"
                    if isinstance(meta2, dict) and meta2:
                        em = e.get("meta")
                        if isinstance(em, dict):
                            em.update(meta2)
                        else:
                            e["meta"] = dict(meta2)
                    return

                if to_ == dst and lab == label:
                    if isinstance(meta2, dict) and meta2:
                        em = e.get("meta")
                        if isinstance(em, dict):
                            em.update(meta2)
                        else:
                            e["meta"] = dict(meta2)
                    return
            except Exception:
                continue
        edges.append({"to": dst, "label": label, "meta": dict(meta2 or {})})

    def _ensure_entity(entity_id: str, *, kind_hint: str | None = None) -> str:
        eid = (entity_id or "unknown").strip().lower()
        # cached?
        bid = (getattr(ctx, "wm_entities", {}) or {}).get(eid)
        if isinstance(bid, str) and bid in ww._bindings:
            # If we later learn a better kind hint, annotate the existing entity in-place.
            if isinstance(kind_hint, str) and kind_hint:
                try:
                    tags = _tagset_of(bid)
                    tags.add(f"wm:kind:{kind_hint}")
                except Exception:
                    pass
            return bid

        anchor_name = "WM_SELF" if eid == "self" else _sanitize_entity_anchor(eid)
        try:
            bid = ww.ensure_anchor(anchor_name)
        except Exception:
            # fallback: a plain node if anchors fail for any reason
            bid = ww.add_predicate(f"wm_entity:{eid}", attach="none", meta={"created_by": "wm_mapsurface"})

        # mark + cache
        try:
            ctx.wm_entities[eid] = bid
        except Exception:
            pass

        tags = _tagset_of(bid)
        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")
        if isinstance(kind_hint, str) and kind_hint:
            tags.add(f"wm:kind:{kind_hint}")

        # attach under WM_ROOT so predicates are reachable from NOW (we pin NOW to WM_ROOT each tick)
        try:
            _upsert_edge(root_bid, bid, "wm_entity", {"created_by": "wm_mapsurface"})
        except Exception:
            pass

        # init wm meta
        try:
            b = ww._bindings.get(bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                wmm = b.meta.setdefault("wm", {})
                if isinstance(wmm, dict):
                    wmm.setdefault("entity_id", eid)
        except Exception:
            pass

        return bid

    def _replace_pred_slot_on_entity(bid: str, slot_prefix: str, new_full_tag: str) -> bool:
        """
        Ensure entity has exactly one pred tag for this slot family, e.g.:
          slot_prefix='posture'         → pred:posture:*
          slot_prefix='proximity:mom'   → pred:proximity:mom:*
        Returns True if the stored tag actually changed.
        """
        tags = _tagset_of(bid)
        pref = f"pred:{slot_prefix}:"
        old = None
        for t in list(tags):
            if isinstance(t, str) and t.startswith(pref):
                old = t
                break
        if old == new_full_tag:
            return False
        # remove all in that family, then add the new one
        for t in list(tags):
            if isinstance(t, str) and t.startswith(pref):
                tags.discard(t)
        tags.add(new_full_tag)
        return True

    def _entity_from_pred(tok: str) -> tuple[str, str]:
        """
        Return (entity_id, slot_prefix) from a predicate token (no 'pred:' prefix).
        """
        parts = (tok or "").split(":")
        if not parts:
            return ("self", "unknown")

        head = parts[0]
        if head == "grid" and len(parts) >= 2:
            return ("self", f"grid:{parts[1]}")
        if head == "posture":
            return ("self", "posture")
        if head in ("nipple", "milk"):
            return ("self", head)
        if head == "proximity" and len(parts) >= 3:
            ent = parts[1]
            return (ent, f"proximity:{ent}")
        if head == "hazard" and len(parts) >= 3:
            ent = parts[1]
            return (ent, f"hazard:{ent}")

        # fallback: treat as SELF attribute family
        return ("self", head)

    def _entity_from_cue(tok: str) -> str:
        """
        Heuristic: for cues like 'vision:silhouette:mom', assume the last segment is an entity id.
        """
        parts = (tok or "").split(":")
        if len(parts) >= 2:
            tail = parts[-1].strip().lower()
            if tail:
                return tail
        return "self"

    def _set_pos(bid: str, x: float, y: float, dist_m: float | None, dist_class: str | None) -> None:
        b = ww._bindings.get(bid)
        if b is None:
            return
        if not isinstance(getattr(b, "meta", None), dict):
            b.meta = {}
        wmm = b.meta.setdefault("wm", {})
        if not isinstance(wmm, dict):
            wmm = {}
            b.meta["wm"] = wmm
        wmm["pos"] = {"x": float(x), "y": float(y), "frame": "wm_schematic_v1"}
        if dist_m is not None:
            wmm["dist_m"] = float(dist_m)
        if isinstance(dist_class, str) and dist_class:
            wmm["dist_class"] = dist_class
        wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)

    def _dist_value_from_class(dist_class: str | None) -> float:
        m = {
            "touching": 0.2,
            "close": 1.0,
            "near": 1.2,
            "reachable": 0.8,
            "far": 5.0,
        }
        if dist_class is None:
            return 3.0
        return float(m.get(dist_class, 3.0))

    def _raw_distance_guess(raw: dict, ent: str) -> float | None:
        if not isinstance(raw, dict):
            return None

        # common keys
        for k in (
            f"distance_to_{ent}",
            f"{ent}_distance",
            f"{ent}_distance_m",
            f"dist_{ent}",
        ):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                return float(v)

        # positions: (kid_position, mom_position, shelter_position, cliff_position, ...)
        kp = raw.get("kid_position") or raw.get("self_position")
        op = raw.get(f"{ent}_position")
        if isinstance(kp, (tuple, list)) and isinstance(op, (tuple, list)) and len(kp) == 2 and len(op) == 2:
            try:
                dx = float(op[0]) - float(kp[0])
                dy = float(op[1]) - float(kp[1])
                return _math_sqrt(dx * dx + dy * dy)
            except Exception:
                return None

        return None


    def _lane_y(ent: str, *, kind: str | None) -> float:
        ent_l = (ent or "").lower()
        if kind == "hazard" or ent_l in ("cliff", "drop", "danger"):
            return 1.0
        if ent_l in ("shelter", "den", "nest"):
            return -1.0
        if kind == "agent" or ent_l in ("mom", "mother"):
            return 0.0
        # deterministic lane based on characters (avoid python hash randomization)
        s = sum(ord(c) for c in ent_l)
        lane = (s % 5) - 2  # -2..+2
        return float(lane) * 0.5


    def _project(dist_m: float, ent: str, *, kind: str | None) -> tuple[float, float]:
        # subway-map distortion: compress far distances but keep ordering monotonic
        d = max(0.0, float(dist_m))
        x = 3.0 * _math_log(1.0 + d)
        y = _lane_y(ent, kind=kind)
        return (x, y)

    # -------------------- MapSurface path (default) --------------------
    if getattr(ctx, "working_mapsurface", True):
        # Ensure WM_ROOT exists, and pin NOW to it so has_pred_near_now(...) works against the map.
        try:
            root_bid = ww.ensure_anchor("WM_ROOT")
        except Exception:
            # fallback: keep whatever NOW is if WM_ROOT cannot be created
            root_bid = ww.ensure_anchor("NOW")

        try:
            ww.set_now(root_bid, tag=True, clean_previous=True)
        except Exception:
            try:
                ww._anchors["NOW"] = root_bid
                _tagset_of(root_bid).add("anchor:NOW")
            except Exception:
                pass

        # Optional: keep NOW_ORIGIN aligned with WM_ROOT in WorkingMap
        try:
            ww._anchors["NOW_ORIGIN"] = root_bid
            _tagset_of(root_bid).add("anchor:NOW_ORIGIN")
        except Exception:
            pass

        # Ensure WM_SCRATCH exists and is reachable from WM_ROOT.
        # This is where policy scratch chains will attach, so WM_ROOT stays a clean "map surface".
        try:
            scratch_bid = ww.ensure_anchor("WM_SCRATCH")
            try:
                _tagset_of(scratch_bid).add("wm:scratch")
            except Exception:
                pass
            try:
                _upsert_edge(root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_mapsurface"})
            except Exception:
                pass
        except Exception:
            pass

        # Ensure WM_CREATIVE exists and is reachable from WM_ROOT.
        # This is the "imagination" workspace: counterfactual rollouts should not contaminate MapSurface.
        try:
            creative_bid = ww.ensure_anchor("WM_CREATIVE")
            try:
                _tagset_of(creative_bid).add("wm:creative")
            except Exception:
                pass
            try:
                _upsert_edge(root_bid, creative_bid, "wm_creative", {"created_by": "wm_mapsurface"})
            except Exception:
                pass
        except Exception:
            pass

        # Ensure SELF entity exists and sits under WM_ROOT
        self_bid = _ensure_entity("self", kind_hint="agent")
        _upsert_edge(root_bid, self_bid, "wm_entity", {"created_by": "wm_mapsurface"})
        _set_pos(self_bid, 0.0, 0.0, dist_m=0.0, dist_class="self")

        # NOTE (Phase X):
        # SurfaceGrid composition + grid→predicate derivation happens later in this function:
        #   - Step 12: WM.SurfaceGrid compose + dirty-cache (ctx.wm_surfacegrid_*)
        #   - Step 13: Grid → slot-family predicates written onto MapSurface SELF
        # The older inline prototype block was removed to avoid double-compose and misleading cache-hit reporting.
        #
        # --- DELETED PREVIOUSLY: WM.SurfaceGrid (Phase X): compose once-per-tick and derive grid predicates ---
        # deleted this block of code

        # --- Predicates: update entity tags in place ---
        pred_tokens = [
            str(p).replace("pred:", "", 1)
            for p in (getattr(env_obs, "predicates", []) or [])
            if p is not None
        ]

        for tok in pred_tokens:
            ent, slot_prefix = _entity_from_pred(tok)
            kind = "hazard" if slot_prefix.startswith("hazard:") else None
            if ent == "self":
                kind = "agent"
            if ent in ("mom", "mother"):
                kind = "agent"
            if ent == "shelter":
                kind = "shelter"
            bid = _ensure_entity(ent, kind_hint=kind)
            full_tag = f"pred:{tok}"
            changed = _replace_pred_slot_on_entity(bid, slot_prefix, full_tag)

            # bump prominence (exposure signal) even if unchanged
            try:
                ww.bump_prominence(bid, tag=full_tag, meta=meta, reason="observe")
            except Exception:
                pass
            created_preds.append(tok)

            if changed:
                changed_entities.add(ent)

            if getattr(ctx, "working_verbose", False) or changed:
                try:
                    disp = f"{display_id_fn(bid)} ({bid})"
                    print(
                        f"[env→working] MAP pred:{tok} → {disp} (entity={ent}, slot={slot_prefix})"
                        + (" [changed]" if changed else ""))
                except Exception:
                    pass

        # --- Cues: attach to an entity and dedup/remove old env cues per entity ---
        cue_tokens = [
            str(c).replace("cue:", "", 1)
            for c in (getattr(env_obs, "cues", []) or [])
            if c is not None
        ]

        cues_by_ent: dict[str, set[str]] = {}
        for tok in cue_tokens:
            ent = _entity_from_cue(tok)
            cues_by_ent.setdefault(ent, set()).add(f"cue:{tok}")
            created_cues.append(tok)

        # update each entity that has cues this tick
        for ent, new_cue_tags in cues_by_ent.items():
            kind = "agent" if ent in ("mom", "mother") else None
            bid = _ensure_entity(ent, kind_hint=kind)
            tags = _tagset_of(bid)

            prev = (getattr(ctx, "wm_last_env_cues", {}) or {}).get(ent, set())
            # remove old env cues not present now
            for t in list(prev - new_cue_tags):
                try:
                    tags.discard(t)
                except Exception:
                    pass
            # add new env cues
            for t in list(new_cue_tags - prev):
                try:
                    tags.add(t)
                except Exception:
                    pass

            try:
                ctx.wm_last_env_cues[ent] = set(new_cue_tags)
            except Exception:
                pass

            for t in new_cue_tags:
                try:
                    ww.bump_prominence(bid, tag=t, meta=meta, reason="observe")
                except Exception:
                    pass

            if getattr(ctx, "working_verbose", False):
                try:
                    for t in sorted(new_cue_tags):
                        disp = f"{display_id_fn(bid)} ({bid})"
                        print(f"[env→working] MAP {t} → {disp} (entity={ent})")
                except Exception:
                    pass

        # Also clear env cues for entities that had cues last tick but none now
        try:
            for ent in list(ctx.wm_last_env_cues.keys()):
                if ent in cues_by_ent:
                    continue
                cue_bid = (ctx.wm_entities or {}).get(ent)
                if not (isinstance(cue_bid, str) and cue_bid in ww._bindings):
                    ctx.wm_last_env_cues.pop(ent, None)
                    continue
                tags = _tagset_of(cue_bid)
                for t in list(ctx.wm_last_env_cues.get(ent, set())):
                    tags.discard(t)
                ctx.wm_last_env_cues.pop(ent, None)
        except Exception:
            pass

        try:
            now_map = getattr(ctx, "wm_last_env_cues", None)
            if isinstance(now_map, dict):
                for ent, now_set in now_map.items():
                    if not isinstance(ent, str) or not isinstance(now_set, set):
                        continue
                    prev_set = prev_cues_by_ent.get(ent, set())
                    if now_set - prev_set:
                        new_cue_entities.add(ent)
        except Exception:
            pass

        # --- NavPatch / SurfaceGrid Phase-2 sub-pipeline -------------------------------
        # The live entity/predicate/cue injection and its Phase-2 helpers now share this module.
        # NavPatch references, ambiguity Scratch/zoom, salience, SurfaceGrid, grid-derived
        # predicates, and NavSummary are delegated to the focused helpers below.
        if bool(getattr(ctx, "navpatch_enabled", False)):
            try:
                update_working_navpatch_refs_v1(
                    ctx,
                    env_obs,
                    ww,
                    ensure_entity_fn=_ensure_entity,
                    display_id_fn=display_id_fn,
                    store_navpatch_fn=store_navpatch_fn,
                )
            except Exception:
                pass

            try:
                update_working_navpatch_scratch_zoom_v1(
                    ctx,
                    env_obs,
                    ww,
                    tagset_fn=_tagset_of,
                    upsert_edge_fn=_upsert_edge,
                    body_cliff_distance_fn=body_cliff_distance_fn,
                )
            except Exception:
                pass

        try:
            update_working_salience_surfacegrid_v1(
                ctx,
                env_obs,
                ww,
                changed_entities=changed_entities,
                new_cue_entities=new_cue_entities,
                salience_tick_fn=salience_tick_fn,
            )
        except Exception:
            pass

        # --- Coordinates + distance edges (schematic map) ---
        raw = getattr(env_obs, "raw_sensors", {}) or {}
        for ent, bid in (getattr(ctx, "wm_entities", {}) or {}).items():
            if ent in ("self",):
                continue
            if not isinstance(bid, str) or bid not in ww._bindings:
                continue

            tags = _tagset_of(bid)
            # infer a distance class from the current pred tags on this entity
            dist_class = None
            kind = None
            for t in tags:
                if not isinstance(t, str) or not t.startswith("pred:"):
                    continue
                if t.startswith(f"pred:proximity:{ent}:"):
                    dist_class = t.split(":")[-1]
                    break
                if t.startswith(f"pred:hazard:{ent}:"):
                    dist_class = t.split(":")[-1]
                    kind = "hazard"
                    break
            if ent == "shelter":
                kind = "shelter"
            if dist_class is None:
                dist_class = "unknown"

            dist_m = _raw_distance_guess(raw, ent)
            if dist_m is None:
                dist_m = _dist_value_from_class(dist_class)
            if kind is None:
                if any(isinstance(t, str) and t == "wm:kind:agent" for t in tags):
                    kind = "agent"
            x, y = _project(dist_m, ent, kind=kind)
            _set_pos(bid, x, y, dist_m=dist_m, dist_class=dist_class)

            # self -> entity distance edge (upsert)
            try:
                _upsert_edge(self_bid, bid, "distance_to", {"meters": float(dist_m), "class": dist_class, "frame": "wm_schematic_v1"})
            except Exception:
                pass

        # Keep working map bounded (mostly relevant if policies also write into WorkingMap)
        try:
            prune_working_world_fn(ctx)
        except Exception:
            pass

        # Optional: append raw trace nodes (debug only)
        if getattr(ctx, "working_trace", False):
            try:
                attach = "now"
                for tok in pred_tokens:
                    ww.add_predicate(tok, attach=attach, meta=meta)
                    attach = "latest"
                cue_attach = "latest" if pred_tokens else "now"
                for tok in cue_tokens:
                    ww.add_cue(tok, attach=cue_attach, meta=meta)
                prune_working_world_fn(ctx)
            except Exception:
                pass

        return {"predicates": created_preds, "cues": created_cues}

    # -------------------- Fallback: old episodic “tick log” behaviour --------------------
    # (kept so you can revert quickly if desired)
    pred_tokens = [
        str(p).replace("pred:", "", 1)
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "", 1)
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    attach = "now"
    for tok in pred_tokens:
        try:
            ww.add_predicate(tok, attach=attach, meta=meta)
            created_preds.append(tok)
            if getattr(ctx, "working_verbose", False):
                print(f"[env→working] pred:{tok} (attach={attach})")
        except Exception:
            pass
        attach = "latest"

    cue_attach = "latest" if created_preds else "now"
    for tok in cue_tokens:
        try:
            ww.add_cue(tok, attach=cue_attach, meta=meta)
            created_cues.append(tok)
            if getattr(ctx, "working_verbose", False):
                print(f"[env→working] cue:{tok} (attach={cue_attach})")
        except Exception:
            pass

    # Keep working map bounded
    try:
        prune_working_world_fn(ctx)
    except Exception:
        pass
    return {"predicates": created_preds, "cues": created_cues}
