#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Environment-observation ingestion and BodyMap runtime integration for CCA8.

Purpose
-------
This module owns the runner-facing observation-ingestion path that was
historically embedded in ``cca8_run.py``. It provides:

- tiny BodyMap construction and EnvObservation-to-BodyMap updates
- short-window sequential/error diagnostics
- partial-observability masking
- short-lived SurfaceGrid, MapSurface, WorkingMap, and NavMap handoffs
- keyframe detection and sparse long-term WorldGraph writes
- optional spatial/valence observation sugar
- bounded per-cycle JSON/JSONL trace storage

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. The large ingestion function receives
an explicit :class:`ObservationRuntime` callback bundle. ``cca8_run`` constructs
that bundle from its compatibility surface so existing tests, monkeypatch seams,
and downstream imports continue to resolve at call time.

Behavior boundary
-----------------
This is a structural extraction. The order of masking, BodyMap updates,
sequential/error processing, WorkingMap/NavMap handoffs, keyframe detection, and
WorldGraph writes is preserved. In particular, the historical second BodyMap
update inside ``inject_obs_into_world`` remains unchanged pending a separate,
behavior-focused audit.
"""

from __future__ import annotations

# The extracted path intentionally preserves the defensive style of the runner.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-statements

import json
import logging
import os
import random
from dataclasses import dataclass
from typing import Any, Callable, Dict, Optional

import cca8_world_graph
from cca8_context import Ctx
from cca8_env import EnvObservation


__version__ = "0.1.0"

__all__ = [
    "ObservationRuntime",
    "init_body_world",
    "update_body_world_from_obs",
    "seqerr_update_from_obs",
    "append_cycle_json_record",
    "inject_obs_into_world",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class ObservationRuntime:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Callbacks required by the extracted EnvObservation ingestion pipeline.

    The runner supplies these operations at call time. Keeping the bridge
    explicit prevents a circular import and preserves historical monkeypatch
    seams while this module owns the ingestion algorithm itself.
    """

    newborn_stress_profile_from_ctx: Callable[..., Any]
    newborn_conflicted_repair_status: Callable[..., Any]
    update_body_world_from_obs: Callable[..., Any]
    seqerr_update_from_obs: Callable[..., Any]
    update_surface_grid_from_obs: Callable[..., Any]
    update_map_surface_from_obs: Callable[..., Any]
    predcode_update_from_obs: Callable[..., Any]
    navpatch_predictive_match_loop: Callable[..., Any]
    inject_obs_into_working_world: Callable[..., Any]
    navmap_ctx_observation_update_step: Callable[..., Any]
    write_spatial_scene_edges: Callable[..., Any]
    inject_simple_valence_like_mom: Callable[..., Any]


def init_body_world() -> tuple[cca8_world_graph.WorldGraph, dict[str, str]]:
    """
    Initialize a tiny BodyMap as a separate WorldGraph instance.

    Nodes (v1.1):
      - ROOT      (anchor:BODY_ROOT) — body as a whole
      - POSTURE   (pred:posture:*)   — overall posture
      - MOM       (pred:proximity:mom:*)      — mom distance relative to body
      - NIPPLE    (pred:nipple:* / pred:milk:drinking) — nipple/latch state
      - SHELTER   (pred:proximity:shelter:*)  — shelter distance relative to body
      - CLIFF     (pred:hazard:cliff:*)       — dangerous drop proximity

    Edges (v1.1):
      BODY_ROOT --body_state-->     POSTURE
      BODY_ROOT --body_relation-->  MOM
      BODY_ROOT --body_relation-->  SHELTER
      BODY_ROOT --body_danger-->    CLIFF
      MOM       --body_part-->      NIPPLE

    Returns:
        (body_world, body_ids) where body_ids maps "root"/"posture"/"mom"/"nipple" → binding ids.
    """
    body_world = cca8_world_graph.WorldGraph()
    # We may add non-lexicon tokens later; keep tag policy permissive here.
    body_world.set_tag_policy("allow")
    body_world.set_stage("neonate")

    # Root / self node
    root_bid = body_world.ensure_anchor("BODY_ROOT")

    # Posture slot: default fallen at birth
    posture_bid = body_world.add_predicate(
        "posture:fallen",
        attach="none",
        meta={"body_slot": "posture", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        posture_bid,
        "body_state",
        meta={"created_by": "body_map_init"},
    )

    # Mom distance slot: default far
    mom_bid = body_world.add_predicate(
        "proximity:mom:far",
        attach="none",
        meta={"body_slot": "mom", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        mom_bid,
        "body_relation",
        meta={"created_by": "body_map_init"},
    )

    # Shelter distance slot: default far
    shelter_bid = body_world.add_predicate(
        "proximity:shelter:far",
        attach="none",
        meta={"body_slot": "shelter", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        shelter_bid,
        "body_relation",
        meta={"created_by": "body_map_init"},
    )

    # Cliff / dangerous drop slot: default far (no immediate hazard)
    cliff_bid = body_world.add_predicate(
        "hazard:cliff:far",
        attach="none",
        meta={"body_slot": "cliff", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        root_bid,
        cliff_bid,
        "body_danger",
        meta={"created_by": "body_map_init"},
    )

    # Nipple slot: default hidden
    nipple_bid = body_world.add_predicate(
        "nipple:hidden",
        attach="none",
        meta={"body_slot": "nipple", "created_by": "body_map_init"},
    )
    body_world.add_edge(
        mom_bid,
        nipple_bid,
        "body_part",
        meta={"created_by": "body_map_init"},
    )

    body_ids = {
        "root": root_bid,
        "posture": posture_bid,
        "mom": mom_bid,
        "nipple": nipple_bid,
        "shelter": shelter_bid,
        "cliff": cliff_bid,
    }

    return body_world, body_ids


def update_body_world_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    """
    Update the tiny BodyMap (ctx.body_world) from an EnvObservation.

    We treat BodyMap as a structured register:
      - posture slot reflects posture:* / resting predicates
      - mom slot reflects proximity:mom:* predicates
      - nipple slot reflects nipple:* / milk:drinking predicates

    EnvObservation is observation-space; we mirror its discrete predicates here.
    """
    body_world = getattr(ctx, "body_world", None)
    body_ids = getattr(ctx, "body_ids", {}) or {}
    if body_world is None or not body_ids:
        return

    preds = set(getattr(env_obs, "predicates", []) or [])

    # --- posture slot ---
    posture_bid = body_ids.get("posture")
    if posture_bid and posture_bid in body_world._bindings:
        b = body_world._bindings[posture_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Strip old posture-like tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and (
                    t.startswith("pred:posture:")
                    or t == "pred:resting"
                    or t == "resting"
                )
            )
        }

        new_posture: str | None = None
        if "posture:standing" in preds:
            new_posture = "standing"
        elif "posture:fallen" in preds:
            new_posture = "fallen"
        elif "resting" in preds:
            new_posture = "resting"

        if new_posture == "resting":
            tags.add("pred:resting")
        elif new_posture in ("standing", "fallen"):
            tags.add(f"pred:posture:{new_posture}")

        b.tags = tags

    # --- mom-distance slot ---
    mom_bid = body_ids.get("mom")
    if mom_bid and mom_bid in body_world._bindings:
        b = body_world._bindings[mom_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old proximity tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:proximity:mom:")
            )
        }

        if "proximity:mom:close" in preds:
            tags.add("pred:proximity:mom:close")
        elif "proximity:mom:far" in preds:
            tags.add("pred:proximity:mom:far")

        b.tags = tags

    # --- shelter-distance slot ---
    shelter_bid = body_ids.get("shelter")
    if shelter_bid and shelter_bid in body_world._bindings:
        b = body_world._bindings[shelter_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old shelter proximity tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:proximity:shelter:")
            )
        }

        # Only update if the observation actually carries shelter proximity.
        if "proximity:shelter:near" in preds:
            tags.add("pred:proximity:shelter:near")
        elif "proximity:shelter:far" in preds:
            tags.add("pred:proximity:shelter:far")

        b.tags = tags

    # --- cliff / dangerous drop slot ---
    cliff_bid = body_ids.get("cliff")
    if cliff_bid and cliff_bid in body_world._bindings:
        b = body_world._bindings[cliff_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old cliff hazard tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and t.startswith("pred:hazard:cliff:")
            )
        }

        # Hazard semantics: near vs far; if not present we leave previous value.
        if "hazard:cliff:near" in preds:
            tags.add("pred:hazard:cliff:near")
        elif "hazard:cliff:far" in preds:
            tags.add("pred:hazard:cliff:far")

        b.tags = tags

    # --- nipple/latch slot ---
    nipple_bid = body_ids.get("nipple")
    if nipple_bid and nipple_bid in body_world._bindings:
        b = body_world._bindings[nipple_bid]
        tags = set(getattr(b, "tags", []) or [])

        # Remove old nipple/milk tags
        tags = {
            t for t in tags
            if not (
                isinstance(t, str)
                and (
                    t.startswith("pred:nipple:")
                    or t == "pred:milk:drinking"
                )
            )
        }

        # Infer a simple nipple state from observation predicates
        if "nipple:latched" in preds:
            tags.add("pred:nipple:latched")
            if "milk:drinking" in preds:
                tags.add("pred:milk:drinking")
        elif "nipple:found" in preds:
            tags.add("pred:nipple:found")
        elif "nipple:hidden" in preds or not bool(
            getattr(ctx, "experiment_newborn_explicit_missingness", False)
        ):
            # Preserve legacy non-publication behavior. Only the corrected
            # publication benchmark treats an absent nipple token as an
            # explicit unknown state rather than the positive state ``hidden``.
            tags.add("pred:nipple:hidden")
        # In explicit-missingness mode, absence of a nipple token leaves the
        # slot empty/unknown so Guarded Merge can perform a genuine repair.

        b.tags = tags

    # --- recency marker ---
    # We treat controller_steps as our integer "clock" for BodyMap staleness.
    try:
        # If controller_steps is not yet initialized, fall back to 0.
        steps = int(getattr(ctx, "controller_steps", 0))
        # Only set the attribute if it exists (Ctx defines bodymap_last_update_step).
        if hasattr(ctx, "bodymap_last_update_step"):
            ctx.bodymap_last_update_step = steps
    except Exception:
        # BodyMap bookkeeping must never break the env→body bridge.
        pass


def seqerr_update_from_obs(ctx: Ctx, env_obs: EnvObservation) -> None:
    # pylint: disable=too-many-locals, too-many-branches, too-many-statements
    """
    Sequential/error v1 (stub): compute short-window temporal deltas + prediction error.

    Intent
    ------
    In CCA7, a cerebellum-inspired unit processes how sensory signals evolve over time and
    computes mismatch signals (prediction error). For CCA8 we implement a minimal, transparent
    version that:

      1) Tracks a short history window (default 4) of:
         - raw numeric channels (EnvObservation.raw_sensors)
         - discrete predicate slots (EnvObservation.predicates)

      2) Computes:
         - raw_delta: per-channel curr - prev
         - raw_err  : constant-velocity extrapolation error when we have >=3 frames:
                      pred_next = prev + (prev - prev_prev)
                      raw_err   = curr - pred_next
         - slot_changes: list of discrete slot transitions (e.g., proximity:mom:far -> close)
         - slot_stability: how many consecutive frames each slot token has remained unchanged

    Outputs (stored on ctx)
    -----------------------
      - ctx.seqerr_last: latest JSON-safe bundle
      - ctx.seqerr_history: ring buffer of last seqerr_window frames

    Optional predictive-coding seam (OFF by default)
    ------------------------------------------------
    If ctx.seqerr_attention_enabled is True, set ctx.seqerr_attention_request when a channel
    error magnitude exceeds ctx.seqerr_attention_threshold and no request is pending.

    Safety
    ------
    Must never raise exceptions to callers.
    """
    if ctx is None or env_obs is None:
        return
    if not bool(getattr(ctx, "seqerr_enabled", True)):
        return

    def _as_int(x: Any) -> int:
        try:
            return int(x)
        except Exception:
            return 0

    def _as_float(x: Any) -> float | None:
        # bool is an int subclass; treat it as non-numeric for our purposes.
        if isinstance(x, bool):
            return None
        if isinstance(x, (int, float)):
            return float(x)
        try:
            return float(x)
        except Exception:
            return None

    def _slot_key(tok: str) -> str:
        tok = str(tok)
        return tok.rsplit(":", 1)[0] if ":" in tok else tok

    # ---- time/step reference (best-effort) ----
    env_meta = getattr(env_obs, "env_meta", None)
    env_meta = env_meta if isinstance(env_meta, dict) else {}
    t_now = _as_float(env_meta.get("time_since_birth"))
    step_ref = env_meta.get("step_index")
    if step_ref is None:
        step_ref = getattr(ctx, "controller_steps", 0)
    step_now = _as_int(step_ref)

    # ---- raw sensors (numeric only; JSON-safe) ----
    raw_in = getattr(env_obs, "raw_sensors", None)
    raw: dict[str, float] = {}
    if isinstance(raw_in, dict):
        for k, v in raw_in.items():
            if not isinstance(k, str) or not k:
                continue
            fv = _as_float(v)
            if fv is None:
                continue
            raw[k] = fv

    # ---- discrete slot snapshot (one token per slot family) ----
    preds_in = getattr(env_obs, "predicates", None)
    slots: dict[str, str] = {}
    if isinstance(preds_in, list):
        for p in preds_in:
            if p is None:
                continue
            tok = str(p).replace("pred:", "", 1)
            slots[_slot_key(tok)] = tok

    # ---- history ring buffer ----
    hist = getattr(ctx, "seqerr_history", None)
    if not isinstance(hist, list):
        hist = []
        try:
            ctx.seqerr_history = hist
        except Exception:
            hist = []

    frame = {"step": step_now, "t": t_now, "raw": dict(raw), "slots": dict(slots)}
    hist.append(frame)

    try:
        win = int(getattr(ctx, "seqerr_window", 4) or 4)
    except Exception:
        win = 4
    win = max(2, min(25, win))
    if len(hist) > win:
        del hist[: len(hist) - win]

    # ---- dt estimate ----
    dt = 1.0
    if len(hist) >= 2:
        t0 = hist[-2].get("t")
        t1 = hist[-1].get("t")
        if isinstance(t0, (int, float)) and isinstance(t1, (int, float)):
            d = float(t1) - float(t0)
            if d > 1e-9:
                dt = float(d)

    # ---- deltas + errors ----
    raw_delta: dict[str, float] = {}
    raw_err: dict[str, float] = {}
    slot_changes: list[dict[str, str]] = []
    slot_stability: dict[str, int] = {}

    if len(hist) >= 2:
        prev_raw = hist[-2].get("raw")
        prev_raw = prev_raw if isinstance(prev_raw, dict) else {}
        for k, v1 in raw.items():
            v0 = prev_raw.get(k)
            if isinstance(v0, (int, float)):
                raw_delta[k] = float(v1) - float(v0)

        prev_slots = hist[-2].get("slots")
        prev_slots = prev_slots if isinstance(prev_slots, dict) else {}
        for slot, tok in slots.items():
            prev_tok = prev_slots.get(slot)
            if isinstance(prev_tok, str) and prev_tok != tok:
                slot_changes.append({"slot": slot, "prev": prev_tok, "now": tok})

    if len(hist) >= 3:
        prev_raw = hist[-2].get("raw")
        prev_prev_raw = hist[-3].get("raw")
        if isinstance(prev_raw, dict) and isinstance(prev_prev_raw, dict):
            for k, v1 in raw.items():
                v0 = prev_raw.get(k)
                v_1 = prev_prev_raw.get(k)
                if isinstance(v0, (int, float)) and isinstance(v_1, (int, float)):
                    pred_next = float(v0) + (float(v0) - float(v_1))
                    raw_err[k] = float(v1) - pred_next

    for slot, tok in slots.items():
        n = 1
        for i in range(len(hist) - 2, -1, -1):
            slots_i = hist[i].get("slots")
            if not isinstance(slots_i, dict):
                break
            if slots_i.get(slot) == tok:
                n += 1
            else:
                break
        slot_stability[slot] = n

    # ---- attention suggestion (stored always; applied only when enabled) ----
    best_key: str | None = None
    best_mag = 0.0
    best_src = ""

    for k, e in raw_err.items():
        mag = abs(float(e))
        if mag > best_mag:
            best_mag = mag
            best_key = k
            best_src = "raw_err"

    if best_key is None:
        for k, d in raw_delta.items():
            mag = abs(float(d))
            if mag > best_mag:
                best_mag = mag
                best_key = k
                best_src = "raw_delta"

    attention_suggest: str | None = None
    if best_key is not None:
        if "mom" in best_key:
            attention_suggest = "mom"
        elif "temperature" in best_key:
            attention_suggest = "self:temperature"
        else:
            attention_suggest = best_key

    try:
        ctx.seqerr_last = {
            "step": int(step_now),
            "t": t_now,
            "dt": float(dt),
            "raw": dict(raw),
            "raw_delta": dict(raw_delta),
            "raw_err": dict(raw_err),
            "slots": dict(slots),
            "slot_changes": list(slot_changes),
            "slot_stability": dict(slot_stability),
            "attention_suggest": attention_suggest,
            "attention_src": best_src,
            "attention_mag": float(best_mag),
        }
    except Exception:
        pass

    try:
        if bool(getattr(ctx, "seqerr_attention_enabled", False)) and attention_suggest:
            thresh = float(getattr(ctx, "seqerr_attention_threshold", 0.25) or 0.25)
            if float(best_mag) >= thresh and getattr(ctx, "seqerr_attention_request", None) is None:
                ctx.seqerr_attention_request = attention_suggest
    except Exception:
        pass

    try:
        if bool(getattr(ctx, "seqerr_verbose", False)) and slot_changes:
            parts = []
            for c in slot_changes[:4]:
                if isinstance(c, dict):
                    parts.append(f"{c.get('slot')}:{c.get('prev')}→{c.get('now')}")
            more = " …" if len(slot_changes) > 4 else ""
            print(f"[seqerr] step={step_now} slot_changes={len(slot_changes)} [{', '.join(parts)}]{more}")
    except Exception:
        pass


def _write_spatial_scene_edges(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    token_to_bid: Dict[str, str],
    *,
    anchor_id_fn: Callable[[Any, str], str],
    add_spatial_relation_fn: Callable[..., None],
) -> None:
    """
    Write minimal scene-graph style edges for this observation.

    Today we keep this extremely conservative:

      • Only when 'resting' is present in env_obs.predicates (kid is in a relatively
        stable configuration).

      • Treat the NOW anchor as "SELF".

      • For any bindings created this step with tokens:
            proximity:mom:close
            proximity:shelter:near
            hazard:cliff:near
        we add a single edge:

            NOW --near--> <that binding>

        if such an edge does not already exist.

    The destination binding's predicate tags carry the semantics (mom vs shelter vs cliff);
    the edge label 'near' is intentionally generic to avoid label explosion.
    """
    _ = ctx  # retained for the historical observation-runtime callback signature
    preds = set(getattr(env_obs, "predicates", []) or [])
    # Only annotate a tiny scene when resting is present in this observation
    if "resting" not in preds:
        return

    try:
        now_id = anchor_id_fn(world, "NOW")
        if not now_id or now_id == "?":
            return
        src = world._bindings.get(now_id)
        if not src:
            return

        # Collect existing 'near' edges out of NOW so we don't duplicate them.
        existing: set[str] = set()
        edges_raw = (
            getattr(src, "edges", []) or
            getattr(src, "out", []) or
            getattr(src, "links", []) or
            getattr(src, "outgoing", [])
        )
        if isinstance(edges_raw, list):
            for e in edges_raw:
                if not isinstance(e, dict):
                    continue
                if e.get("label") == "near":
                    dst = (
                        e.get("to")
                        or e.get("dst")
                        or e.get("dst_id")
                        or e.get("id")
                    )
                    if isinstance(dst, str):
                        existing.add(dst)

        # Candidate tokens we know how to represent.
        candidates = [
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:near",
        ]

        for tok in candidates:
            bid = token_to_bid.get(tok)
            if not isinstance(bid, str):
                continue
            if bid in existing:
                continue  # already have NOW --near--> bid

            try:
                add_spatial_relation_fn(
                    world,
                    src_bid=now_id,
                    rel="near",
                    dst_bid=bid,
                    meta={
                        "created_by": "scene_graph",
                        "source": "env_step",
                        "kind": "near",
                    },
                )
                existing.add(bid)
            except Exception:
                # Scene-graph sugar must never break env injection.
                continue
    except Exception:
        # Fully defensive: if anything goes wrong, just skip spatial labels.
        return


def _inject_simple_valence_like_mom(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    token_to_bid: Dict[str, str],
) -> None:
    """
    Minimal valence stub: when the kid is latched and mom is close in the SAME EnvObservation,
    tag the mom-proximity binding with pred:valence:like.

    Condition:
      • 'nipple:latched' ∈ env_obs.predicates
      • 'proximity:mom:close' ∈ env_obs.predicates

    Effect:
      • Find the binding we just created for 'proximity:mom:close' (via token_to_bid)
      • Add 'pred:valence:like' to its tags if not already present.

    This encodes "like mom (when close and feeding)" directly on the mom-near binding,
    ready for future planning/gating logic to read.
    """
    _ = ctx  # retained for the historical observation-runtime callback signature
    preds = set(getattr(env_obs, "predicates", []) or [])
    if "nipple:latched" not in preds:
        return
    if "proximity:mom:close" not in preds:
        return

    mom_bid = token_to_bid.get("proximity:mom:close")
    if not isinstance(mom_bid, str):
        return

    b = world._bindings.get(mom_bid)
    if not b:
        return

    tags = getattr(b, "tags", None)

    # Ensure tags is a mutable set
    if tags is None:
        b.tags = {"pred:valence:like"}
        return
    if isinstance(tags, list):
        tags = set(tags)
        b.tags = tags

    if "pred:valence:like" not in tags:
        tags.add("pred:valence:like")


def append_cycle_json_record(ctx: Ctx, record: dict[str, Any]) -> None:
    """Append a per-cycle JSON-safe record to ctx and optionally write it as JSONL.

    Design:
      - Always appends to an in-memory ring buffer (ctx.cycle_json_records).
      - If ctx.cycle_json_path is a non-empty string, appends a single JSON object per line (JSONL).
      - Never raises: logging-only on failure so the runner stays interactive.

    Notes:
      - File path is interpreted relative to the process working directory unless absolute.
      - The file is created on first successful open(..., "a", ...).
    """
    if ctx is None or not bool(getattr(ctx, "cycle_json_enabled", False)):
        return

    max_n = int(getattr(ctx, "cycle_json_max_records", 0) or 0)
    if max_n <= 0:
        max_n = 2000

    buf = getattr(ctx, "cycle_json_records", None)
    if not isinstance(buf, list):
        ctx.cycle_json_records = []
        buf = ctx.cycle_json_records
    buf.append(record)
    if len(buf) > max_n:
        del buf[:-max_n]

    path = getattr(ctx, "cycle_json_path", None)
    if not isinstance(path, str) or not path.strip():
        return

    abs_path = os.path.abspath(path)
    try:
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False)
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logging.error("[cycle_json] write failed path=%r: %s", abs_path, e, exc_info=True)
        return


def inject_obs_into_world(
    world: Any,
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    runtime: ObservationRuntime,
) -> dict[str, Any]:
    """Write env observation tokens into the long-term WorldGraph with clear attach semantics.

    Modes (ctx.longterm_obs_mode):
      - "snapshot": old behavior; always write all observed predicates each tick
      - "changes" : write only when a state-slot changes, plus optional re-asserts/keyframes

    Slot definition:
      token "proximity:mom:far" -> slot "proximity:mom"
      token "resting"           -> slot "resting" (no ":")

    Keyframes (only in "changes" mode):
      - episode start (env_reset): time_since_birth <= 0.0
      - stage change (if enabled): env_meta["scenario_stage"] changed
      - zone change (if enabled): coarse safety zone flip derived from shelter/cliff predicates
      - periodic (optional): every N controller steps (period_steps > 0)
      - surprise (optional): pred_err v0 sustained mismatch (streak-based)
      - milestones (optional): env_meta milestone flags AND/OR derived predicate slot transitions
      - strong emotion/arousal (optional): env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy

    Even when we skip writing an unchanged token, token_to_bid will still map that token
    to the most recent binding id for its slot (so downstream helpers can still find it).
    """
    created_preds: list[str] = []
    created_cues: list[str] = []
    token_to_bid: dict[str, str] = {}

    # Pull env meta fields early (not masked; used for keyframe labels later).
    env_meta = getattr(env_obs, "env_meta", None) or {}
    stage = env_meta.get("scenario_stage")
    time_since_birth = env_meta.get("time_since_birth")

    # Partial observability (Phase VIII): optionally drop some observation facts before they enter memory.
    #
    # Notes:
    # - This is a PERCEPTION knob (what crosses the env→agent boundary), not a change to EnvState truth.
    # - Masking happens BEFORE BodyMap/WorkingMap/WorldGraph writes so it affects "belief-now".
    # - A small set of safety-critical predicate families is protected so zone classification remains stable.
    mask_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
    if mask_p <= 0.0:
        # If masking is off, clear the "config printed" sentinel so re-enabling prints a config line again.
        try:
            ctx.obs_mask_last_cfg_sig = None
        except Exception:
            pass
    else:
        mask_p = max(0.0, min(1.0, mask_p))
        protect_pred_prefixes: tuple[str, ...] = (
            "posture:",
            "hazard:cliff:",
            "proximity:shelter:",
        )

        # The integrated conflicted-repair challenge depends on two declared
        # information boundaries. The clean seed must store mom-distance and
        # route:clear. During the active challenge, the fresh route safety field
        # must remain visible while mom-distance is removed deliberately by the
        # stressor. Protect only those challenge-critical families from the
        # unrelated ordinary random mask. Other eligible observations continue
        # to use the configured partial-observability probability.
        try:
            challenge_profile = runtime.newborn_stress_profile_from_ctx(ctx) == "conflicted_repair"
            challenge_status = runtime.newborn_conflicted_repair_status(ctx)
        except Exception:
            challenge_profile = False
            challenge_status = "inactive"
        if challenge_profile and challenge_status in {"armed", "active"}:
            protect_pred_prefixes = protect_pred_prefixes + ("route:",)
            if (
                (
                    challenge_status == "armed"
                    and bool(
                        getattr(
                            ctx,
                            "experiment_conflicted_repair_memory_available",
                            True,
                        )
                    )
                )
                or bool(getattr(ctx, "experiment_conflicted_repair_reacquired", False))
            ):
                protect_pred_prefixes = protect_pred_prefixes + ("proximity:mom:",)

        preds_in = getattr(env_obs, "predicates", None)
        cues_in = getattr(env_obs, "cues", None)

        preds = [t for t in preds_in if isinstance(t, str) and t] if isinstance(preds_in, list) else []
        cues = [t for t in cues_in if isinstance(t, str) and t] if isinstance(cues_in, list) else []

        def _strip_pred_prefix(tok: str) -> str:
            return tok[5:] if tok.startswith("pred:") else tok

        # Reproducible masking (optional):
        # If ctx.obs_mask_seed is set, use a per-step deterministic RNG. This prevents unrelated random calls
        # (e.g., RL exploration) from perturbing the observation-masking pattern.
        rng: Any = random
        rng_mode = "global"
        seed_base = getattr(ctx, "obs_mask_seed", None)

        step_ref = env_meta.get("step_index")
        if step_ref is None:
            step_ref = getattr(ctx, "cog_cycles", None)
        if step_ref is None:
            step_ref = getattr(ctx, "controller_steps", 0)

        seed_eff: Optional[int] = None
        if seed_base is not None:
            try:
                seed_i = int(seed_base)
            except Exception:
                seed_i = None
            if seed_i is not None:
                try:
                    step_i = int(step_ref) if step_ref is not None else 0
                except Exception:
                    step_i = 0
                seed_eff = (seed_i * 1_000_003) ^ step_i
                rng = random.Random(seed_eff)
                rng_mode = "seeded"

        verbose = bool(getattr(ctx, "obs_mask_verbose", True))
        cfg_sig = f"{rng_mode}|{seed_base!r}|{mask_p:.3f}"
        if verbose and cfg_sig != getattr(ctx, "obs_mask_last_cfg_sig", None):
            try:
                ctx.obs_mask_last_cfg_sig = cfg_sig
            except Exception:
                pass
            print(
                f"[obs-mask] config mode={rng_mode} seed={seed_base!r} step_ref={step_ref!r} "
                f"p={mask_p:.2f} protected={len(protect_pred_prefixes)}"
            )

        dropped_pred_tokens: list[str] = []
        dropped_cue_tokens: list[str] = []

        preds_out: list[str] = []
        for tok in preds:
            tok_chk = _strip_pred_prefix(tok)
            if any(tok_chk.startswith(pfx) for pfx in protect_pred_prefixes):
                preds_out.append(tok)
                continue
            if rng.random() < mask_p:
                dropped_pred_tokens.append(tok)
                continue
            preds_out.append(tok)

        # Defensive: keep at least one predicate if we had any (avoid “empty observation block” surprises).
        if (not preds_out) and preds:
            preds_out = [preds[0]]
            dropped_pred_tokens = list(preds[1:])

        cues_out: list[str] = []
        for tok in cues:
            if rng.random() < mask_p:
                dropped_cue_tokens.append(tok)
                continue
            cues_out.append(tok)

        dropped_preds = len(dropped_pred_tokens)
        dropped_cues = len(dropped_cue_tokens)

        # Apply the masked lists back onto the observation packet.
        try:
            setattr(env_obs, "predicates", preds_out)
            setattr(env_obs, "cues", cues_out)
        except Exception:
            pass

        # In the stochastic conflicted-repair benchmark, an exogenous
        # mother-distance opportunity is only a true current-state reacquisition
        # when the token survives the ordinary observation mask. Once observed,
        # the cue remains trackable for the rest of the short challenge.
        try:
            exposed = bool(
                challenge_profile
                and challenge_status == "active"
                and getattr(
                    ctx,
                    "experiment_conflicted_repair_reacquisition_exposed_this_step",
                    False,
                )
            )
            if exposed:
                observed = any(
                    _strip_pred_prefix(token).startswith("proximity:mom:")
                    for token in preds_out
                    if isinstance(token, str)
                )
                if observed:
                    already = bool(
                        getattr(ctx, "experiment_conflicted_repair_reacquired", False)
                    )
                    ctx.experiment_conflicted_repair_reacquired = True
                    ctx.experiment_conflicted_repair_reacquisition_available = True
                    if not already:
                        try:
                            ctx.experiment_conflicted_repair_reacquire_step = (
                                int(step_ref)
                                if step_ref is not None
                                else None
                            )
                        except Exception:
                            ctx.experiment_conflicted_repair_reacquire_step = None
                        ctx.experiment_conflicted_repair_reacquisition_observed_count = int(
                            getattr(
                                ctx,
                                "experiment_conflicted_repair_reacquisition_observed_count",
                                0,
                            )
                            or 0
                        ) + 1
                    if isinstance(env_meta, dict):
                        env_meta["newborn_conflicted_repair_reacquired"] = True
                        env_meta["newborn_conflicted_repair_reacquisition_available"] = True
                        env_meta["newborn_conflicted_repair_reacquire_step"] = getattr(
                            ctx,
                            "experiment_conflicted_repair_reacquire_step",
                            None,
                        )
                        env_meta[
                            "newborn_conflicted_repair_reacquisition_observed_count"
                        ] = int(
                            getattr(
                                ctx,
                                "experiment_conflicted_repair_reacquisition_observed_count",
                                0,
                            )
                            or 0
                        )
            ctx.experiment_conflicted_repair_reacquisition_exposed_this_step = False
        except Exception:
            pass

        # Expose masking stats for downstream gating/diagnostics (e.g., keyframe auto-retrieve).
        # This lets the keyframe pipeline know whether *this* observation lost tokens.
        try:
            if isinstance(env_meta, dict):
                env_meta["obs_mask_dropped_preds"] = int(dropped_preds)
                env_meta["obs_mask_dropped_cues"] = int(dropped_cues)
                # Preserve the exact removed tokens so WorkingMap can represent
                # synthetic missingness explicitly instead of silently retaining
                # the preceding value as current state.
                env_meta["obs_mask_dropped_pred_tokens"] = list(dropped_pred_tokens[:32])
                env_meta["obs_mask_dropped_cue_tokens"] = list(dropped_cue_tokens[:32])
                env_meta["obs_mask_mode"] = str(rng_mode)
                env_meta["obs_mask_prob"] = float(mask_p)
        except Exception:
            pass

        if verbose and (dropped_preds or dropped_cues):
            seed_part = f" seed_eff={seed_eff}" if seed_eff is not None else ""
            print(
                f"[obs-mask] mode={rng_mode}{seed_part} step_ref={step_ref!r} "
                f"dropped preds={dropped_preds}/{len(preds)} cues={dropped_cues}/{len(cues)} p={mask_p:.2f}"
            )

    # Always keep BodyMap current (policies are BodyMap-first now).
    try:
        runtime.update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass

    # Sequential/error stub (CCA7-inspired): temporal deltas + prediction error on the sensory stream.
    # Diagnostic-first; does not affect policy selection unless you explicitly enable attention later.
    try:
        runtime.seqerr_update_from_obs(ctx, env_obs)
    except Exception:
        pass

    # Update the short-lived sensory surfaces (SurfaceGrid + MapSurface) and
    # compute a minimal prediction error signal (predictive coding v1).
    try:
        runtime.update_surface_grid_from_obs(ctx, env_obs)
    except Exception:
        pass
    try:
        runtime.update_map_surface_from_obs(ctx, env_obs)
    except Exception:
        pass
    try:
        runtime.predcode_update_from_obs(ctx, env_obs)
    except Exception:
        pass

    # NavPatch predictive matching loop (Phase X baseline; priors OFF).
    # This records traceability metadata and may store new patch engrams in Column.
    # IMPORTANT: run *before* WorkingMap injection so env_obs.nav_patches carries match/commit fields.
    # This must never break env stepping.
    try:
        runtime.navpatch_predictive_match_loop(ctx, env_obs)
    except Exception:
        # Matching is diagnostic; ignore failures and keep the env loop alive.
        pass

    # Mirror into WorkingMap when enabled.
    # Keep the returned dict so callers (e.g., env-loop footer) can summarize what happened.
    working_inj = None
    try:
        if getattr(ctx, "working_enabled", False):
            working_inj = runtime.inject_obs_into_working_world(ctx, env_obs)
    except Exception:
        working_inj = None

    # Always keep BodyMap current (policies are BodyMap-first now).
    try:
        runtime.update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass

    # Read-only NavMap diagnostic bridge. This updates ctx-local candidate/history fields only.
    try:
        runtime.navmap_ctx_observation_update_step(ctx, env_obs)
    except Exception:
        pass

    # Allow turning off long-term injection entirely (BodyMap/WorkingMap still update).
    if not getattr(ctx, "longterm_obs_enabled", True):
        return {
            "predicates": created_preds,
            "cues": created_cues,
            "token_to_bid": token_to_bid,
            "working": working_inj,
        }

    mode = (getattr(ctx, "longterm_obs_mode", "snapshot") or "snapshot").strip().lower()
    do_changes = mode in ("changes", "dedup", "delta", "state_changes")

    # Normalize (defensive: some probes may include prefixes already) AFTER masking.
    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "")
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    keyframe = False
    keyframe_reasons: list[str] = []
    # In "changes" mode: optionally force a one-tick snapshot at stage transitions/resets
    if do_changes:
        force_snapshot = False
        reasons: list[str] = []

        step_no = int(getattr(ctx, "controller_steps", 0) or 0)

        # ---- Coarse zone (derived from pred tokens; does NOT depend on BodyMap update ordering) ----
        zone_now = "unknown"
        shelter = None
        cliff = None
        for _tok in pred_tokens:
            if isinstance(_tok, str) and _tok.startswith("proximity:shelter:"):
                shelter = _tok.rsplit(":", 1)[-1]
            elif isinstance(_tok, str) and _tok.startswith("hazard:cliff:"):
                cliff = _tok.rsplit(":", 1)[-1]
        if cliff == "near" and shelter != "near":
            zone_now = "unsafe_cliff_near"
        elif shelter == "near" and cliff != "near":
            zone_now = "safe"

        last_zone = getattr(ctx, "lt_obs_last_zone", None)

        # Reset keyframe: env.reset() produces time_since_birth == 0.0
        if isinstance(time_since_birth, (int, float)) and float(time_since_birth) <= 0.0:
            force_snapshot = True
            reasons.append(f"env_reset(time_since_birth={float(time_since_birth):.2f})")

        # Stage-change keyframe (optional)
        last_stage = getattr(ctx, "lt_obs_last_stage", None)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True)):
            if stage is not None and last_stage is not None and stage != last_stage:
                force_snapshot = True
                reasons.append(f"stage_change {last_stage!r}→{stage!r}")

        # Zone-change keyframe (optional)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_zone_change", True)):
            if isinstance(last_zone, str) and zone_now != last_zone:
                force_snapshot = True
                reasons.append(f"zone_change {last_zone!r}→{zone_now!r}")

        # Benchmark-only newborn route-loss keyframe.
        # During route_loss, current route/task evidence is deliberately hidden,
        # so the experiment must create retrieval opportunities instead of
        # waiting for ordinary stage/zone changes.
        try:
            env_meta_for_stress = getattr(env_obs, "env_meta", None)
            env_meta_for_stress = env_meta_for_stress if isinstance(env_meta_for_stress, dict) else {}

            if bool(env_meta_for_stress.get("newborn_force_keyframe")):
                force_snapshot = True
                route_reason = env_meta_for_stress.get("newborn_blackout_reason")
                route_reason = route_reason if isinstance(route_reason, str) and route_reason else "route_loss"
                reasons.append(f"newborn_stress:{route_reason}")
        except Exception:
            pass

        # Periodic keyframe (optional; safe: evaluated only at this boundary hook)
        #
        # Two semantics:
        #   A) legacy absolute schedule: step_no % period == 0
        #   B) reset-on-any-keyframe: treat periodic as a max-gap since last keyframe
        #      (if any other keyframe happens, the periodic counter restarts).
        try:
            period = int(getattr(ctx, "longterm_obs_keyframe_period_steps", 0) or 0)
        except Exception:
            period = 0

        if period > 0 and step_no > 0:
            reset_on_any = bool(getattr(ctx, "longterm_obs_keyframe_period_reset_on_any_keyframe", False))

            hit = False
            if reset_on_any:
                last_kf = getattr(ctx, "lt_obs_last_keyframe_step", None)
                last_kf_step = int(last_kf) if isinstance(last_kf, int) else 0
                if last_kf_step > step_no:
                    # Defensive: controller_steps can be reset in some flows; treat that as a new epoch.
                    last_kf_step = 0
                hit = (step_no - last_kf_step) >= period
            else:
                hit = (step_no % period) == 0

            # Optional suppression: do not fire periodic keyframes while sleeping.
            #
            # We detect sleep state best-effort from either:
            #   A) env_meta: sleep_state/sleep_mode (str), or sleeping/dreaming (bool)
            #   B) predicate tokens: sleeping:non_dreaming / sleeping:dreaming (rem/nrem aliases allowed)
            if hit:
                sup_nd = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming", False))
                sup_dr = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_dreaming", False))

                if sup_nd or sup_dr:
                    sleep_kind: str | None = None

                    # A) env_meta string label
                    try:
                        sm = env_meta.get("sleep_state") or env_meta.get("sleep_mode") or env_meta.get("sleep")
                    except Exception:
                        sm = None

                    if isinstance(sm, str) and sm.strip():
                        s = sm.strip().lower().replace(" ", "_")
                        if s in ("dreaming", "rem", "rem_sleep", "sleep_rem"):
                            sleep_kind = "dreaming"
                        elif s in ("non_dreaming", "nondreaming", "nrem", "nrem_sleep", "sleep_nrem", "non_rem"):
                            sleep_kind = "non_dreaming"

                    # A2) env_meta boolean flags
                    if sleep_kind is None:
                        try:
                            sleeping_flag = env_meta.get("sleeping")
                            dreaming_flag = env_meta.get("dreaming")
                        except Exception:
                            sleeping_flag = None
                            dreaming_flag = None

                        if isinstance(sleeping_flag, bool) and sleeping_flag:
                            sleep_kind = "dreaming" if bool(dreaming_flag) else "non_dreaming"

                    # B) predicate tokens
                    if sleep_kind is None:
                        try:
                            toks = {t.strip().lower() for t in pred_tokens if isinstance(t, str) and t.strip()}
                        except Exception:
                            toks = set()

                        if (
                            "sleeping:dreaming" in toks
                            or "sleep:dreaming" in toks
                            or "sleeping:rem" in toks
                            or "sleep:rem" in toks
                        ):
                            sleep_kind = "dreaming"
                        elif (
                            "sleeping:non_dreaming" in toks
                            or "sleep:non_dreaming" in toks
                            or "sleeping:nrem" in toks
                            or "sleep:nrem" in toks
                        ):
                            sleep_kind = "non_dreaming"
                        elif ("sleeping" in toks) or ("sleep" in toks):
                            # If sleep is present but untyped, treat as non-dreaming by default.
                            sleep_kind = "non_dreaming"

                    if (sleep_kind == "non_dreaming") and sup_nd:
                        hit = False
                    elif (sleep_kind == "dreaming") and sup_dr:
                        hit = False

            if hit:
                # If another keyframe is already happening this tick, do NOT add a second "periodic" reason.
                # In reset-on-any-keyframe mode, the periodic counter will still be reset by that other keyframe.
                if not force_snapshot:
                    force_snapshot = True
                    reasons.append(f"periodic(step={step_no}, period={period})")

        # Surprise keyframe from pred_err v0 (optional; streak-based)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_pred_err", False)):
            pe = getattr(ctx, "pred_err_v0_last", None)
            pe_any = False
            if isinstance(pe, dict) and pe:
                try:
                    pe_any = any(int(v or 0) != 0 for v in pe.values())
                except Exception:
                    pe_any = False

            streak = int(getattr(ctx, "lt_obs_pred_err_streak", 0) or 0)
            streak = (streak + 1) if pe_any else 0
            ctx.lt_obs_pred_err_streak = streak

            try:
                min_streak = int(getattr(ctx, "longterm_obs_keyframe_pred_err_min_streak", 2) or 2)
            except Exception:
                min_streak = 2
            min_streak = max(1, min_streak)

            if pe_any and streak >= min_streak:
                force_snapshot = True
                reasons.append(f"pred_err_v0(streak={streak})")
        else:
            ctx.lt_obs_pred_err_streak = 0

        # Milestone keyframes (HAL + derived from predicate transitions). Off by default.
        #
        # Two sources:
        #   A) env_meta milestone flags (HAL/richer envs) — may be sticky and repeat across ticks → dedup.
        #   B) derived transition events from predicate slots (storyboard + early HAL) — event-based, no sticky dedup needed.
        #
        # Derived events currently recognized:
        #   - posture:fallen -> posture:standing              => stood_up
        #   - proximity:mom:* -> proximity:mom:close         => reached_mom
        #   - (first) nipple:found                           => found_nipple
        #   - (first) nipple:latched                         => latched_nipple
        #   - (first) milk:drinking                          => milk_drinking
        #   - (first) resting                                => rested
        if bool(getattr(ctx, "longterm_obs_keyframe_on_milestone", False)):
            ms_events: set[str] = set()

            # --- A) Env-supplied milestone flags (rising-edge, not episode-global sticky) ---
            #
            # Important semantic choice:
            #   We treat env-supplied milestones as "new" relative to the immediately
            #   previous observation, NOT as "seen once per episode forever".
            #
            # Why:
            #   Some scenarios intentionally reuse the same milestone label multiple times
            #   in one episode. goat_foraging_04 is the current example:
            #
            #       context:fox -> context:hawk -> context:fox -> ...
            #
            #   We want each alternation edge to be a fresh keyframe trigger, while still
            #   suppressing repeated identical labels on consecutive ticks:
            #
            #       fox, fox, fox     -> fire once on first fox tick
            #       fox -> hawk       -> fire on hawk
            #       hawk, hawk, hawk  -> fire once on first hawk tick
            #       hawk -> fox       -> fire on fox again
            #
            #   Therefore we compare CURRENT milestones against the PREVIOUS active set,
            #   then overwrite the remembered set with the current one.
            ms_raw = env_meta.get("milestones") or env_meta.get("milestone")
            ms_list: list[str] = []
            if isinstance(ms_raw, str) and ms_raw:
                ms_list = [ms_raw]
            elif isinstance(ms_raw, list):
                ms_list = [m for m in ms_raw if isinstance(m, str) and m]

            prev_raw = getattr(ctx, "lt_obs_last_milestones", None)
            prev_ms: set[str] = {x for x in prev_raw if isinstance(x, str) and x} if isinstance(prev_raw, set) else set()
            curr_ms: set[str] = {m for m in ms_list if isinstance(m, str) and m}

            new_ms = curr_ms - prev_ms
            if new_ms:
                ms_events |= new_ms

            try:
                ctx.lt_obs_last_milestones = curr_ms
            except Exception:
                pass

            # --- B) Derived milestone events (slot transitions) ---
            try:
                prev_slots = getattr(ctx, "lt_obs_slots", None)
                prev_slots = prev_slots if isinstance(prev_slots, dict) else {}

                # Build current slot->token mapping from this observation (pred_tokens has no "pred:" prefix).
                curr_by_slot: dict[str, str] = {}
                for tok in pred_tokens:
                    if not isinstance(tok, str) or not tok:
                        continue
                    slot = tok.rsplit(":", 1)[0] if ":" in tok else tok
                    if slot not in curr_by_slot:
                        curr_by_slot[slot] = tok

                def _prev_token(slot: str) -> str | None:
                    p = prev_slots.get(slot)
                    if isinstance(p, dict):
                        t = p.get("token")
                        return t if isinstance(t, str) else None
                    return None

                # posture transition
                prev_posture = _prev_token("posture")
                curr_posture = curr_by_slot.get("posture")
                if curr_posture == "posture:standing" and prev_posture != "posture:standing":
                    ms_events.add("stood_up")

                # mom proximity transition
                prev_mom = _prev_token("proximity:mom")
                curr_mom = curr_by_slot.get("proximity:mom")
                if curr_mom == "proximity:mom:close" and prev_mom != "proximity:mom:close":
                    ms_events.add("reached_mom")

                # nipple milestones
                prev_nipple = _prev_token("nipple")
                curr_nipple = curr_by_slot.get("nipple")
                if curr_nipple == "nipple:found" and prev_nipple != "nipple:found":
                    ms_events.add("found_nipple")
                if curr_nipple == "nipple:latched" and prev_nipple != "nipple:latched":
                    ms_events.add("latched_nipple")

                # milk milestone
                prev_milk = _prev_token("milk")
                curr_milk = curr_by_slot.get("milk")
                if curr_milk == "milk:drinking" and prev_milk != "milk:drinking":
                    ms_events.add("milk_drinking")

                # resting milestone
                prev_rest = _prev_token("resting")
                curr_rest = curr_by_slot.get("resting")
                if curr_rest == "resting" and prev_rest != "resting":
                    ms_events.add("rested")
            except Exception:
                # Derived milestones are strictly best-effort; never break env injection.
                pass

            if ms_events:
                force_snapshot = True
                reasons.append("milestone:" + ",".join(sorted(ms_events)))

        # Strong emotion keyframe stub (HAL / richer envs). Off by default.
        # Note: we treat hazard zone as a conservative proxy ("fear") only when env_meta doesn't supply emotion.
        if bool(getattr(ctx, "longterm_obs_keyframe_on_emotion", False)):
            label = None
            intensity = None

            emo_raw = env_meta.get("emotion") or env_meta.get("affect")
            if isinstance(emo_raw, dict):
                lab = emo_raw.get("label")
                inten = emo_raw.get("intensity")
                label = lab if isinstance(lab, str) and lab else None
                try:
                    intensity = float(inten) if inten is not None else None
                except Exception:
                    intensity = None
            elif isinstance(emo_raw, str) and emo_raw:
                label = emo_raw

            # Proxy if no explicit emotion: unsafe zone -> fear-high
            if intensity is None and label is None:
                if zone_now == "unsafe_cliff_near":
                    label = "fear"
                    intensity = 1.0

            try:
                thr = float(getattr(ctx, "longterm_obs_keyframe_emotion_threshold", 0.85) or 0.85)
            except Exception:
                thr = 0.85

            high = bool(isinstance(intensity, (int, float)) and float(intensity) >= thr)
            prev_label = getattr(ctx, "lt_obs_last_emotion_label", None)
            prev_high = bool(getattr(ctx, "lt_obs_last_emotion_high", False))

            # Rising edge: (not high) -> high, or label changes while high.
            if high and (label != prev_label or not prev_high):
                force_snapshot = True
                inten_txt = f"{float(intensity):.2f}" if isinstance(intensity, (int, float)) else "n/a"
                reasons.append(f"emotion:{label or 'n/a'}@{inten_txt}")

            try:
                ctx.lt_obs_last_emotion_label = label if isinstance(label, str) else None
                ctx.lt_obs_last_emotion_high = high
            except Exception:
                pass

        # [KEYFRAME HOOK + ORDERING INVARIANT]
        # This is the keyframe/boundary detection point for the env→memory injection path.
        # inject_obs_into_world(...) runs BEFORE policy selection (Action Center), so any keyframe-driven
        # WM↔Column pipeline that must influence *this same boundary cycle* belongs conceptually here.
        #
        # INVARIANT (keyframes):
        #   EnvObservation -> BodyMap/WorkingMap update -> (keyframe) store snapshot + pointer update ->
        #   (keyframe) optional retrieve+apply (replace or seed/merge) -> policy selection/execution.
        #
        # RESERVED FUTURE SLOT (consolidation/reconsolidation write-back):
        #   After policy selection+execution, a keyframe may also write new engrams (copy-on-write) and
        #   update WorldGraph pointers for future retrieval, without mutating the belief state already
        #   used for action selection in this cycle.  See README: "WM ⇄ Column engram pipeline".

        # REAL-EMBODIMENT KEYFRAMES (HAL / non-storyboard):
        #   In real robots there is no storyboard stage. We will therefore support additional keyframe triggers here,
        #   evaluated ONLY at this boundary hook (never mid-cycle):
        #
        #   - periodic: every N controller_steps (ctx.longterm_obs_keyframe_period_steps)
        #   - surprise: pred_err v0 sustained mismatch (ctx.pred_err_v0_last + min_streak)
        #   - context discontinuity: zone flips (zone_now derived here vs ctx.lt_obs_last_zone)
        #   - milestones: env_meta milestones and/or derived slot transitions (goal-relevant outcomes)
        #   - emotion/arousal: env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy
        #
        # TIME-BASED SAFETY:
        #   Even the periodic keyframe must be checked only at this boundary hook so we never split a cycle
        #   while intermediate planner/policy structures are half-written.

        if force_snapshot:
            old_pred_n = len(getattr(ctx, "lt_obs_slots", {}) or {})
            old_cue_n = len(getattr(ctx, "lt_obs_cues", {}) or {})

            ctx.lt_obs_slots.clear()
            try:
                ctx.lt_obs_cues.clear()
            except Exception:
                pass
            try:
                ctx.lt_obs_last_milestones = set()
            except Exception:
                pass
            if bool(getattr(ctx, "longterm_obs_keyframe_log", True)):
                why = ", ".join(reasons) if reasons else "keyframe"
                print(f"[env→world] KEYFRAME: {why} | cleared {old_pred_n} pred slot(s), {old_cue_n} cue slot(s)")
            try:
                ctx.lt_obs_last_keyframe_step = step_no
            except Exception:
                pass

        ctx.lt_obs_last_stage = stage
        ctx.lt_obs_last_zone = zone_now

        # For downstream callers (e.g., env-loop) that want a unified keyframe definition:
        keyframe = bool(force_snapshot)
        keyframe_reasons = list(reasons)


    def _slot_key(tok: str) -> str:
        return tok.rsplit(":", 1)[0] if ":" in tok else tok

    step_no = int(getattr(ctx, "controller_steps", 0) or 0)
    reassert_steps = int(getattr(ctx, "longterm_obs_reassert_steps", 0) or 0)
    verbose_skips = bool(getattr(ctx, "longterm_obs_verbose", False))

    wrote_any_pred_this_tick = False

    # Predicates: snapshot vs changes mode
    for tok in pred_tokens:
        meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}

        if not do_changes:
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
            continue

        slot = _slot_key(tok)
        prev = ctx.lt_obs_slots.get(slot)

        emit = False
        reason = ""
        if prev is None:
            emit = True
            reason = "first"
        elif prev.get("token") != tok:
            emit = True
            reason = "changed"
        else:
            # unchanged
            if 0 < reassert_steps <= (step_no - int(prev.get("last_emit_step", 0) or 0)):
                emit = True
                reason = "reassert"
            else:
                emit = False
                reason = "unchanged"
        if emit:
            meta2 = dict(meta)
            meta2["_dedup"] = reason
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta2)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            ctx.lt_obs_slots[slot] = {"token": tok, "bid": bid, "last_emit_step": step_no}
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
        else:
            prev_bid = prev.get("bid") if isinstance(prev, dict) else None
            if isinstance(prev_bid, str):
                token_to_bid[tok] = prev_bid
                try:
                    world.bump_prominence(prev_bid, tag=f"pred:{tok}", meta=meta, reason="observe")
                except Exception:
                    pass
            if verbose_skips:
                print(f"[env→world] pred:{tok} → {prev_bid} (reused; unchanged)")

    # If everything was unchanged, print one line so the user knows this is intentional.
    if do_changes and pred_tokens and not created_preds and not verbose_skips:
        print("[env→world] (long-term obs unchanged; no new pred:* bindings written)")

    # Cues:
    # Default: episodic (write each observed cue each tick).
    # Optional (changes-mode): rising-edge de-dup (emit only when absent→present), but still bump prominence every tick.
    cue_attach = "latest" if wrote_any_pred_this_tick else "now"
    dedup_cues = bool(do_changes) and bool(getattr(ctx, "longterm_obs_dedup_cues", False))
    if not dedup_cues:
        for tok in cue_tokens:
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            bid = world.add_cue(tok, attach=cue_attach, meta=meta)
            created_cues.append(tok)
            token_to_bid[tok] = bid
            print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
    else:
        cue_cache = getattr(ctx, "lt_obs_cues", None)
        if not isinstance(cue_cache, dict):
            cue_cache = {}
            try:
                ctx.lt_obs_cues = cue_cache
            except Exception:
                pass

        seen_this_step: set[str] = set()
        cues_now: set[str] = set()
        for tok in cue_tokens:
            if not isinstance(tok, str):
                continue
            if tok in seen_this_step:
                continue
            seen_this_step.add(tok)
            cues_now.add(tok)
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            prev = cue_cache.get(tok)
            was_present = bool(isinstance(prev, dict) and prev.get("present", False))
            emit = False
            reason = ""
            if not was_present:
                emit = True
                reason = "rising"
            else:
                if 0 < reassert_steps <= (step_no - int((prev or {}).get("last_emit_step", 0) or 0)):
                    emit = True
                    reason = "reassert"
                else:
                    emit = False
                    reason = "held"
            if emit:
                meta2 = dict(meta)
                meta2["_dedup"] = reason
                bid = world.add_cue(tok, attach=cue_attach, meta=meta2)
                created_cues.append(tok)
                token_to_bid[tok] = bid
                cue_cache[tok] = {"present": True, "bid": bid, "last_emit_step": step_no}
                print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
            else:
                prev_bid = prev.get("bid") if isinstance(prev, dict) else None
                if isinstance(prev_bid, str):
                    token_to_bid[tok] = prev_bid
                    try:
                        world.bump_prominence(prev_bid, tag=f"cue:{tok}", meta=meta, reason="observe")
                    except Exception:
                        pass
                if isinstance(prev, dict):
                    prev["present"] = True
                if verbose_skips:
                    print(f"[env→world] cue:{tok} → {prev_bid} (reused; held)")
        # Mark cues that were present but are absent now as not present.
        try:
            for tok, rec in list(cue_cache.items()):
                if not isinstance(rec, dict):
                    continue
                if rec.get("present", False) and tok not in cues_now:
                    rec["present"] = False
        except Exception:
            pass

    # Optional env sugar on top of tokens (must never break env stepping)
    try:
        runtime.write_spatial_scene_edges(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    try:
        runtime.inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    return {
        "predicates": created_preds,
        "cues": created_cues,
        "token_to_bid": token_to_bid,
        "working": working_inj,
        "keyframe": bool(keyframe),
        "keyframe_reasons": list(keyframe_reasons),
        "zone_now": getattr(ctx, "lt_obs_last_zone", None),
    }
