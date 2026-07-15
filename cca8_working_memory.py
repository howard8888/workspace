#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 WorkingMap MapSurface storage and retrieval subsystem.

Purpose
-------
This module owns Phase 1 of the CCA8 working-memory extraction: WorkingMap
construction/reset, MapSurface serialization, content signatures and salience,
Column storage plus WorldGraph pointer indexing, candidate ranking, conservative
merge/replace loading, and map-switch event records.

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. It depends only on stable CCA8 modules
and data structures. ``cca8_run`` retains its historical function names as
compatibility aliases, while live per-cycle observation injection, NavPatch and
SurfaceGrid orchestration, and contextual auto-retrieval policy remain runner-
owned for later extraction phases.

WorldGraph boundary
-------------------
WorkingMap is implemented with ``WorldGraph`` objects, and this module is the
narrow owner of the internal mutations needed to reconstruct and merge those
short-lived graphs. Long-term WorldGraph writes continue to use its public
methods. Future WorldGraph APIs can replace these localized internal accesses
without touching the runner or experiment subsystem.
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
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements
# pylint: disable=multiple-statements

import hashlib
import json
from typing import Any, Optional, cast

import cca8_world_graph
from cca8_column import mem as column_mem
from cca8_context import Ctx
from cca8_controller import (
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_space_zone,
    bodymap_is_stale,
)
from cca8_features import FactMeta

__version__ = "0.1.0"

__all__ = [
    "init_working_world",
    "reset_working_world",
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
