#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Runtime reporting, snapshots, terminal diagnostics, and transcript helpers for CCA8.

Purpose
-------
This module owns the stateful terminal-reporting code that was historically
embedded in ``cca8_run.py``. It provides:

- WorkingMap layer, entity-table, and tail snapshots
- temporal, drive, skill, and component-facing runtime readouts
- full WorldGraph snapshots and compact mini-snapshots
- closed-loop cognitive-cycle footer reporting
- terminal transcript tee support
- small developer-facing LOC and vector-parsing utilities

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. It reads stable CCA8 runtime objects
and imports established controller, predictive, NavMap-runtime, and WorkingMap
rendering helpers directly. ``cca8_run`` re-exports the historical names so
existing menu code, tests, and downstream imports remain compatible.

Behavior boundary
-----------------
Reporting remains read-only. Phase 5 adds operative-WNM and feeding close-up
lines to full and mini snapshots, but formatting does not commit a transition,
change policy selection, write memory, or grant map authority. The compact
mini-snapshot still maintains the legacy posture-discrepancy history because the
current controller uses that history as a diagnostic signal for persistent
StandUp failure.
"""

from __future__ import annotations

# The extracted reporting code intentionally preserves the defensive style that
# previously lived in cca8_run.py.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-statements

import atexit
import logging
import os
import re
import sys
from collections import Counter, defaultdict
from datetime import datetime
from math import atan2, degrees, isfinite
from typing import Any, List, Optional

import cca8_working_memory
from cca8_context import Ctx
from cca8_feeding import feeding_operative_readout_v1, render_feeding_lines_v1
from cca8_controller import (
    FATIGUE_HIGH,
    HUNGER_HIGH,
    body_cliff_distance,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_shelter_distance,
    body_space_zone,
    skill_readout,
    skills_to_dict,
)
from cca8_navmap_runtime import (
    NAVMAP_SCOPE_MARKER_V1,
    navmap_accepted_current_mini_line_v1,
    navmap_expected_current_mini_line_v1,
    navmap_observation_update_mini_line_v1,
    navmap_scope_mini_line_v1,
    navmap_transition_mini_line_v1,
    render_navmap_accepted_current_lines_v1,
    render_navmap_expected_current_lines_v1,
    render_navmap_observation_update_lines_v1,
    render_navmap_scope_frame_lines_v1,
    render_navmap_transition_lines_v1,
    render_working_navmap_surface_lines_v1,
    working_navmap_surface_mini_line_v1,
)
from cca8_predictive import (
    latest_posture_binding_v1 as _latest_posture_binding,
    prediction_feedback_mini_line_v1,
    render_prediction_feedback_lines_v1,
)
from cca8_wnm_runtime import render_wnm_lines_v1, wnm_summary_v1

__version__ = "0.2.0"

__all__ = [
    "TeeTextIO",
    "install_terminal_tee",
    "print_startup_notices",
    "print_working_map_snapshot",
    "print_working_map_layers",
    "print_working_map_entity_table",
    "timekeeping_line",
    "print_timekeeping_line",
    "snapshot_text",
    "export_snapshot",
    "recent_bindings_text",
    "print_env_loop_tag_legend_once",
    "mini_snapshot_text",
    "print_mini_snapshot",
    "drives_and_tags_text",
    "skill_ledger_text",
    "skills_hud_text",
    "__version__",
]

# Stable WorkingMap display helpers used by the extracted renderers.
_wm_display_id = cca8_working_memory._wm_display_id
format_surfacegrid_snapshot_v1 = cca8_working_memory.format_surfacegrid_snapshot_v1
navpatch_payload_sig_v1 = cca8_working_memory.navpatch_payload_sig_v1
format_mapswitch_event_line_v1 = cca8_working_memory.format_mapswitch_event_line_v1
format_navsummary_line_v1 = cca8_working_memory.format_navsummary_line_v1
_surfacegrid_ascii_text_v1 = cca8_working_memory._surfacegrid_ascii_text_v1
format_surfacegrid_ascii_map_v1 = cca8_working_memory.format_surfacegrid_ascii_map_v1

def _surfacegrid_ascii_terminal_block_v1(
    ctx: Ctx,
    sg,
    *,
    sig16: str,
    line_prefix: str = "",
    title: Optional[str] = None,
    legend: Optional[str] = None,
) -> str:
    """Render a SurfaceGrid block through runner-visible formatting hooks."""
    return cca8_working_memory._surfacegrid_ascii_terminal_block_v1(
        ctx,
        sg,
        sig16=sig16,
        line_prefix=line_prefix,
        title=title,
        legend=legend,
        ascii_text_fn=_surfacegrid_ascii_text_v1,
        format_map_fn=format_surfacegrid_ascii_map_v1,
    )


def print_working_map_snapshot(ctx, *, n: int = 15, title: str = "[workingmap] snapshot") -> None:
    """Print a tail snapshot of the WorkingMap graph, showing tags + a small edge preview."""
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    def _bid_key(bid: str) -> int:
        try:
            return int(bid[1:]) if isinstance(bid, str) and bid.startswith("b") else 10**9
        except Exception:
            return 10**9

    all_ids = sorted(getattr(ww, "_bindings", {}).keys(), key=_bid_key)  # pylint: disable=protected-access
    tail = all_ids[-max(1, int(n)) :]
    print(f"{title}: last {len(tail)} binding(s) of {len(all_ids)} total")
    print(
        "  Legend: edges=wm_entity(root→entity), wm_scratch(root→scratch), wm_creative(root→creative), "
        "distance_to(self→entity), then(action chain)"
    )
    print("          tags=wm:* entity markers; pred:* belief-now; cue:* cues-now; meta.wm.pos={x,y,frame}")



    for bid in tail:
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue
        tags = ", ".join(sorted(getattr(b, "tags", []) or []))
        edges_raw = getattr(b, "edges", []) or []
        edges = [e for e in edges_raw if isinstance(e, dict)]

        preview = []
        for e in edges[:6]:
            rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if not isinstance(dst, str):
                continue
            extra = ""
            em = e.get("meta") if isinstance(e, dict) else None
            if rel == "distance_to" and isinstance(em, dict):
                meters = em.get("meters")
                dclass = em.get("class")
                if isinstance(meters, (int, float)):
                    extra += f" meters={float(meters):.2f}"
                if isinstance(dclass, str) and dclass:
                    extra += f" class={dclass}"
            preview.append(f"{rel}:{_wm_display_id(dst)} ({dst}){extra}")

        if preview:
            pv = ", ".join(preview)
            if len(edges) > 6:
                pv += f" (+{len(edges) - 6} more)"
        else:
            pv = "(none)"
        print(f"  {_wm_display_id(bid)} ({bid}): [{tags}] out={len(edges)} edges={pv}")

    try:
        if getattr(ctx, "wm_surfacegrid", None) is not None:
            print(format_surfacegrid_snapshot_v1(ctx))
    except Exception:
        pass


def print_working_map_layers(ctx, *, title: str = "[workingmap] layers") -> None:
    """Print a compact HUD of WorkingMap layers (MapSurface / Scratch / Creative).

    This is intentionally a *structural* view:
      - Which roots exist?
      - Is Creative enabled?
      - How many candidates are currently staged?

    It does not print the full graph; use print_working_map_snapshot(...) for that.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    root_bid = (anchors.get("WM_ROOT") or anchors.get("NOW"))
    scratch_bid = anchors.get("WM_SCRATCH")
    creative_bid = anchors.get("WM_CREATIVE")

    ent_map = getattr(ctx, "wm_entities", {}) or {}
    enabled = bool(getattr(ctx, "wm_creative_enabled", False))
    cands = getattr(ctx, "wm_creative_candidates", []) or []

    print(title)
    if isinstance(root_bid, str):
        print(f"  MapSurface: root={_wm_display_id(root_bid)} ({root_bid}) entities={len(ent_map)}")
    else:
        print(f"  MapSurface: root=(none) entities={len(ent_map)}")

    if isinstance(scratch_bid, str):
        print(f"  Scratch  : root={_wm_display_id(scratch_bid)} ({scratch_bid})")
    else:
        print("  Scratch  : root=(none)")

    if isinstance(creative_bid, str):
        print(f"  Creative : root={_wm_display_id(creative_bid)} ({creative_bid}) enabled={enabled} candidates={len(cands)}")
    else:
        print(f"  Creative : root=(none) enabled={enabled} candidates={len(cands)}")

    # Optional: show candidate summaries if present
    if cands:
        print("  Creative candidates: trig=Y/N (trigger satisfied or blocked); score is a display heuristic (not deficit or RL q).")
        try:
            ordered = sorted(cands, key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)
        except Exception:
            ordered = list(cands)

        for i, c in enumerate(ordered[:8], 1):
            try:
                pol = getattr(c, "policy", "(unknown)")
                score = float(getattr(c, "score", 0.0))
                notes = str(getattr(c, "notes", "") or "")

                pred = getattr(c, "predicted", None)
                trig = bool(pred.get("triggerable", False)) if isinstance(pred, dict) else False
                trig_txt = "Y" if trig else "N"

                # If the candidate is blocked, normalize the old note prefix so output is cleaner.
                if (not trig) and notes.startswith("blocked(not_triggered)"):
                    rest = notes[len("blocked(not_triggered)"):]
                    rest = rest.lstrip(" ;")
                    notes = "not_triggered" + (f"; {rest}" if rest else "")

                print(f"    {i:>2}) {pol:<18} trig={trig_txt} score={score:>6.2f}  {notes}")
            except Exception:
                print(f"    {i:>2}) {c}")


def print_working_map_entity_table(ctx, *, title: str = "[workingmap] MapSurface entity table") -> None:
    """Print a compact table of WorkingMap entities with schematic coordinates and key WM meta.

    This is intentionally a *MapSurface* view (entities + geometry), not the full binding log.
    Coordinates are stored in binding.meta['wm']['pos'] as {x,y,frame}.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    ent_map = getattr(ctx, "wm_entities", None)
    if not isinstance(ent_map, dict) or not ent_map:
        print(f"{title}: (no wm_entities; MapSurface may not be initialized yet)")
        return

    def _sort_key(item) -> tuple[int, str]:
        eid = str(item[0])
        return (0, "") if eid == "self" else (1, eid)

    print(title)
    print("  ent      node        kind      pos(x,y)         dist_m  class     seen patches             preds (short)                cues (short)")
    print("  -------  ----------  --------  --------------  ------  --------  ---- ------------------  --------------------------  ----------------")

    # Footer summary counters (NavPatch visibility; keeps logs readable during long runs)
    ent_rows = 0
    ent_with_patches = 0
    patch_refs_total = 0
    uniq_sig16: set[str] = set()
    uniq_patch_eids: set[str] = set()

    skip_meta_entities = {"scene", "wm_root", "root", "now"}

    for eid, bid in sorted(ent_map.items(), key=_sort_key):
        if not isinstance(eid, str):
            continue
        if eid.strip().lower() in skip_meta_entities:
            continue
        if not isinstance(bid, str):
            continue
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue

        tags = list(getattr(b, "tags", []) or [])
        kind = ""
        for t in tags:
            if isinstance(t, str) and t.startswith("wm:kind:"):
                kind = t.split(":", 2)[2]
                break

        meta = getattr(b, "meta", None)
        wmm = meta.get("wm", {}) if isinstance(meta, dict) else {}
        pos = wmm.get("pos", {}) if isinstance(wmm, dict) else {}

        x = pos.get("x") if isinstance(pos, dict) else None
        y = pos.get("y") if isinstance(pos, dict) else None
        frame = pos.get("frame") if isinstance(pos, dict) else None

        dist_m = wmm.get("dist_m") if isinstance(wmm, dict) else None
        dist_class = wmm.get("dist_class") if isinstance(wmm, dict) else None
        last_seen = wmm.get("last_seen_step") if isinstance(wmm, dict) else None
        patch_refs_raw = wmm.get("patch_refs") if isinstance(wmm, dict) else None
        patch_refs: list[Any] = patch_refs_raw if isinstance(patch_refs_raw, list) else []

        # Summary bookkeeping (count only rows we actually render)
        ent_rows += 1
        if patch_refs:
            ent_with_patches += 1
            patch_refs_total += len(patch_refs)
            for ref in patch_refs:
                if not isinstance(ref, dict):
                    continue
                s16 = ref.get("sig16")
                if isinstance(s16, str) and s16:
                    uniq_sig16.add(s16)
                peid = ref.get("engram_id")
                if isinstance(peid, str) and peid:
                    uniq_patch_eids.add(peid)

        node_disp = f"{_wm_display_id(bid)} ({bid})"

        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pos_txt = f"({float(x):6.2f},{float(y):6.2f})"
        else:
            pos_txt = "(   n/a,   n/a)"

        dist_txt = f"{float(dist_m):6.2f}" if isinstance(dist_m, (int, float)) else "  n/a "
        cls_txt = str(dist_class) if isinstance(dist_class, str) else "n/a"
        seen_txt = f"{int(last_seen):4d}" if isinstance(last_seen, int) else " n/a"
        patch_n = len(patch_refs)
        patch_sig16: Optional[str] = None
        if patch_refs:
            first_patch_ref = patch_refs[0]
            if isinstance(first_patch_ref, dict):
                v = first_patch_ref.get("sig16")
                if isinstance(v, str) and v:
                    patch_sig16 = v
        patch_txt = f"{patch_n}:{patch_sig16}" if patch_n and patch_sig16 else ("0" if patch_n == 0 else str(patch_n))
        frame_txt = str(frame) if isinstance(frame, str) else ""
        #to clear pylint #0612: Unused variable "frame_txt" will append frame to pos_txt
        if isinstance(frame, str) and frame_txt:
            pos_txt += f" [{frame}]"

        # Optional: schematic bearing/heading (degrees) from SELF to entity, based on the distorted (x,y) WM coords.
        # This is not "true physics bearing" yet — it's a consistent directional cue for debugging/map intuition.
        try:
            if eid != "self" and isinstance(x, (int, float)) and isinstance(y, (int, float)) and (float(x) != 0.0 or float(y) != 0.0):
                brg = degrees(atan2(float(y), float(x)))
                pos_txt += f" brg={brg:+.0f}°"
        except Exception:
            pass

        # Short belief summaries
        preds = sorted(t[5:] for t in tags if isinstance(t, str) and t.startswith("pred:"))
        cues  = sorted(t[4:] for t in tags if isinstance(t, str) and t.startswith("cue:"))

        pred_txt = ", ".join(preds[:3]) + (" …" if len(preds) > 3 else "")
        cue_txt  = ", ".join(cues[:2]) + (" …" if len(cues) > 2 else "")

        print(
            f"  {eid:<7}  {node_disp:<10}  {kind:<8}  {pos_txt:<14}  {dist_txt:>6}  {cls_txt:<8}  {seen_txt:>4}  "
            f"{patch_txt:<18}  {pred_txt:<26}  {cue_txt}"
        )

    if ent_rows:
        print(
            f"  [patches] ent_with={ent_with_patches}/{ent_rows} refs_total={patch_refs_total} "
            f"uniq_sig16={len(uniq_sig16)} uniq_eid={len(uniq_patch_eids)}"
        )


def _hamming_hex64(a: str, b: str) -> int:
    """Hamming distance between two hex strings (intended for 64-bit vhashes).
    Returns -1 on parse error. Case-insensitive; extra whitespace ignored.
    -we use for analysis of the temporal context vector
    """
    try:
        xa = int(a.strip(), 16)
        xb = int(b.strip(), 16)
        return (xa ^ xb).bit_count()
    except Exception:
        return -1


def _snapshot_temporal_legend() -> list[str]:
    """info about temporal timekeeping in the CCA8
    """
    return [
        "LEGEND (temporal terms):",
        "  epoch: event boundary count; increments when boundary() is taken  [src=ctx.boundary_no]",
        "  vhash64(now): 64-bit sign-bit fingerprint of the current context vector  [src=ctx.tvec64()]",
        "  epoch_vhash64: 64-bit fingerprint of the vector at the last boundary  [src=ctx.boundary_vhash64]",
        "  last_boundary_vhash64: alias of epoch_vhash64 (kept for back-compat)  [alias of epoch_vhash64]",
        "  cos_to_last_boundary: cosine(current vector, last boundary vector)  [src=ctx.cos_to_last_boundary()]",
        "  binding (== node): holds tags, pointers to engrams, and directed edges",
        "",
        "Five measures of time in the CCA8 system:",
        "  1. controller steps — one Action Center decision/execution loop   [src=ctx.controller_steps]",
        "  2. temporal drift — cos_to_last_boundary (cosine(current, last boundary))  [src=ctx.cos_to_last_boundary();"
        "     advanced by ctx.temporal.step()]",
        "  3. autonomic ticks — heartbeat for physiology/IO (robotics integration)  [src=ctx.ticks]",
        "  4. developmental age — age_days  [src=ctx.age_days]",
        "  5. cognitive cycles — full sense->process->opt. action cycle  [src=ctx.cog_cycles]"
        "  **see menu tutorials for more about these terms**",
        "",
    ]


def timekeeping_line(ctx) -> str:
    """Compact summary of the 5 time measures + cosine (robust if any piece is missing).
    """
    cs = getattr(ctx, "controller_steps", 0)
    te = getattr(ctx, "boundary_no", 0)        # temporal epochs
    at = getattr(ctx, "ticks", 0)              # autonomic ticks
    ad = getattr(ctx, "age_days", 0.0)
    cc = getattr(ctx, "cog_cycles", 0)
    try:
        c = ctx.cos_to_last_boundary()
        cos_txt = f"{c:.4f}" if isinstance(c, float) else "(n/a)"
    except Exception:
        cos_txt = "(n/a)"
    return (f"controller_steps={cs}, cos_to_last_boundary={cos_txt}, "
            f"temporal_epochs={te}, autonomic_ticks={at}, age_days={ad:.4f}, cog_cycles={cc}")


def print_timekeeping_line(ctx, prefix: str = "[time] ") -> None:
    """Console helper for menus.
    """
    try:
        print(prefix + timekeeping_line(ctx))
    except Exception:
        pass


def _python_loc_counts_for_file(path: str) -> dict[str, int]:
    """Return simple physical/nonblank/code-like line counts for one Python file.

    This helper intentionally measures what a human usually means by "how large is this file?"
    rather than only formal SLOC. Physical LOC includes comments, docstrings, blank lines,
    long menu text, teaching text, and explanatory scaffolding. Code-like LOC is a simple
    approximation: nonblank lines minus full-line comments. It still counts docstrings and
    multiline strings because those are important in this repo's readable, teaching-oriented style.
    """
    try:
        with open(path, "r", encoding="utf-8", errors="replace") as handle:
            lines = handle.readlines()
    except Exception:
        return {"physical": 0, "nonblank": 0, "comment_only": 0, "code_like": 0}

    physical = len(lines)
    nonblank = 0
    comment_only = 0

    for line in lines:
        stripped = line.strip()
        if stripped:
            nonblank += 1
        if line.lstrip().startswith("#"):
            comment_only += 1

    code_like = max(0, nonblank - comment_only)

    return {
        "physical": int(physical),
        "nonblank": int(nonblank),
        "comment_only": int(comment_only),
        "code_like": int(code_like),
    }


def _compute_loc_by_dir(
    suffixes: tuple[str, ...] = (".py",),
    skip_folders: tuple[str, ...] = (
        ".git",
        ".venv",
        "build",
        "dist",
        ".pytest_cache",
        "__pycache__",
    ),
) -> tuple[
    list[tuple[str, int, int, int, int, int]],
    dict[str, int],
    str | None,
]:
    """Compute Python line counts per top-level directory using a dependency-free scanner.

    Returns:
        rows:
            list[(topdir, files_count, physical_loc, nonblank_loc, code_like_loc, comment_only_loc)]
            sorted by physical LOC descending.

        total:
            dict with aggregate counts for the same columns.

        errtext:
            None on success. A string only if the directory walk itself fails.

    Rationale:
        The old Menu 33 path used pygount SLOC, which intentionally excludes comments,
        docstrings, and blank lines. That is useful for one purpose, but it under-reports
        the actual size/readability burden of CCA8. This local scanner reports the project
        size a human sees in an editor.
    """
    skip_set = {str(x) for x in skip_folders}
    suffix_tuple = tuple(str(x) for x in suffixes)

    counts_by_top: dict[str, dict[str, int]] = defaultdict(
        lambda: {"files": 0, "physical": 0, "nonblank": 0, "code_like": 0, "comment_only": 0}
    )

    try:
        for root, dirs, files in os.walk("."):
            dirs[:] = [d for d in dirs if d not in skip_set and not d.startswith(".")]

            for name in files:
                if not name.endswith(suffix_tuple):
                    continue

                path = os.path.join(root, name)
                rel = os.path.relpath(path, ".")
                parts = rel.split(os.sep)
                top = "." if len(parts) == 1 else parts[0]

                if top in skip_set or not top:
                    continue

                item = _python_loc_counts_for_file(path)
                counts_by_top[top]["files"] += 1
                counts_by_top[top]["physical"] += item["physical"]
                counts_by_top[top]["nonblank"] += item["nonblank"]
                counts_by_top[top]["code_like"] += item["code_like"]
                counts_by_top[top]["comment_only"] += item["comment_only"]

    except Exception as e:
        return [], {}, f"LOC scan failed: {e}"

    rows = []
    for top, item in counts_by_top.items():
        rows.append(
            (
                top,
                int(item["files"]),
                int(item["physical"]),
                int(item["nonblank"]),
                int(item["code_like"]),
                int(item["comment_only"]),
            )
        )

    rows.sort(key=lambda row: (-row[2], row[0]))

    total = {
        "files": sum(row[1] for row in rows),
        "physical": sum(row[2] for row in rows),
        "nonblank": sum(row[3] for row in rows),
        "code_like": sum(row[4] for row in rows),
        "comment_only": sum(row[5] for row in rows),
    }

    return rows, total, None


def _render_loc_by_dir_table(rows, total):
    """Pretty-print the Python LOC table. Returns a string for testability; caller prints it."""
    if not rows:
        return "No Python files (.py) found under the current directory.\n"

    totals = total if isinstance(total, dict) else {}
    name_w = max(25, max(len(str(row[0])) for row in rows))

    lines = []
    lines.append("Selection:  LOC by Directory (Python)")
    lines.append("Counts Python files per top-level folder.")
    lines.append("physical_LOC includes comments, docstrings, menu text, teaching text, and blank lines.")
    lines.append("nonblank_LOC excludes blank lines.")
    lines.append("code_like_LOC excludes blank lines and full-line comments, but still includes docstrings/multiline strings.\n")
    lines.append(
        f"{'directory'.ljust(name_w)}  {'files':>7}  {'physical_LOC':>12}  "
        f"{'nonblank_LOC':>12}  {'code_like_LOC':>13}  {'comment_LOC':>11}"
    )
    lines.append(
        f"{'-' * name_w}  {'-' * 7}  {'-' * 12}  {'-' * 12}  {'-' * 13}  {'-' * 11}"
    )

    for top, files_n, physical, nonblank, code_like, comment_only in rows:
        lines.append(
            f"{str(top).ljust(name_w)}  {files_n:7d}  {physical:12,d}  "
            f"{nonblank:12,d}  {code_like:13,d}  {comment_only:11,d}"
        )

    lines.append(
        f"{'-' * name_w}  {'-' * 7}  {'-' * 12}  {'-' * 12}  {'-' * 13}  {'-' * 11}"
    )
    lines.append(
        f"{'TOTAL'.ljust(name_w)}  {int(totals.get('files', 0)):7d}  "
        f"{int(totals.get('physical', 0)):12,d}  {int(totals.get('nonblank', 0)):12,d}  "
        f"{int(totals.get('code_like', 0)):13,d}  {int(totals.get('comment_only', 0)):11,d}\n"
    )

    return "\n".join(lines)


def _parse_vector(text: str) -> list[float]:
    """
    Parse a comma/space-separated string into a list of floats.
    Empty input → [0.0, 0.0, 0.0].
    """
    s = (text or "").strip()
    if not s:
        return [0.0, 0.0, 0.0]
    vec = []
    for tok in re.split(r"[,\s]+", s):
        if not tok:
            continue
        try:
            vec.append(float(tok))
        except ValueError:
            pass
    return vec or [0.0, 0.0, 0.0]


def _drive_tags(drives) -> list[str]:
    """Robustly compute drive:* tags even if Drives.flags()/predicates() is missing.

    If the Drives class has .flags() use that; fallback to .predicates(); else derive
    by thresholds: hunger>0.6 → drive:hunger_high; fatigue>0.7 → drive:fatigue_high; warmth<0.3 → drive:cold.
    """
    # Prefer the new API
    if hasattr(drives, "flags") and callable(getattr(drives, "flags")):
        try:
            tags = list(drives.flags())
            return [t for t in tags if isinstance(t, str)]
        except Exception:
            pass

    # Back-compat
    if hasattr(drives, "predicates") and callable(getattr(drives, "predicates")):
        try:
            tags = list(drives.predicates())
            return [t for t in tags if isinstance(t, str)]
        except Exception:
            pass

    # Last-resort derived flags
    tags = []
    try:
        if getattr(drives, "hunger", 0.0) > 0.6:
            tags.append("drive:hunger_high")
        if getattr(drives, "fatigue", 0.0) > 0.7:
            tags.append("drive:fatigue_high")
        if getattr(drives, "warmth", 1.0) < 0.3:
            tags.append("drive:cold")
    except Exception:
        pass
    return tags


class TeeTextIO:
    """File-like stream that duplicates writes into multiple underlying streams.

    Purpose:
        - Keep interactive output visible in the terminal
        - Also persist the full transcript to a file (e.g., terminal.txt)
        - Avoid rewriting existing print(...) calls across the codebase

    Notes:
        - This affects *all* print() calls that ultimately write to sys.stdout/sys.stderr.
        - It is safe for interactive sessions (input() relies on stdout.flush()).
    """
    def __init__(self, *streams):
        self._streams = list(streams)

    def write(self, s: str) -> int:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self) -> None:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        try:
            return any(getattr(st, "isatty", lambda: False)() for st in self._streams)
        except Exception:
            return False

    @property
    def encoding(self) -> str:
        '''Keep downstream code happy if it queries sys.stdout.encoding
        '''
        try:
            return getattr(self._streams[0], "encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"


def install_terminal_tee(path: str = "terminal.txt", *, append: bool = True, also_stderr: bool = True) -> None:
    """Duplicate stdout (and optionally stderr) to a UTF-8 text file.

    Call this once near program start (inside main) to capture a full transcript
    of an interactive run without losing on-screen output.

    Args:
        path: Output file path (e.g., "terminal.txt").
        append: If True, append; if False, overwrite each run.
        also_stderr: If True, duplicate stderr too (tracebacks end up in the file).
    """
    if getattr(sys, "_cca8_terminal_tee_installed", False):
        return

    mode = "a" if append else "w"
    # NOTE:
    # We intentionally keep this file handle open for the full program lifetime so
    # stdout/stderr can be tee'd during interactive use. It is closed via atexit
    # in _cleanup() below. Using `with open(...)` here would close it immediately.
    f = open(path, mode, encoding="utf-8", errors="replace", buffering=1)  # pylint: disable=consider-using-with

    sys._cca8_terminal_tee_installed = True  # type: ignore[attr-defined]

    # Keep originals so we can restore them at exit.
    sys._cca8_stdout_orig = sys.stdout  # type: ignore[attr-defined]
    sys._cca8_stderr_orig = sys.stderr  # type: ignore[attr-defined]
    sys._cca8_terminal_tee_file = f     # type: ignore[attr-defined]

    sys.stdout = TeeTextIO(sys.stdout, f)
    if also_stderr:
        sys.stderr = TeeTextIO(sys.stderr, f)


    def _cleanup() -> None:
        # Flush tee streams first, then restore and close.
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        try:
            sys.stdout = sys._cca8_stdout_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            sys.stderr = sys._cca8_stderr_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass
    atexit.register(_cleanup)


def print_startup_notices(world) -> None:
    '''print active planner and other statuses at
    startup of the runner
    '''
    try:
        planner = str(world.get_planner()).upper()
        expl = {
            "BFS": "Breadth-First Search (unweighted shortest path by hop count)",
            "DIJKSTRA": "Dijkstra (lowest total edge weight; equals BFS when all weights=1)",
        }.get(planner)
        if expl:
            print(f"[planner] Active planner on startup: {planner} — {expl}")
        else:
            print(f"[planner] Active planner on startup: {planner}")


    except Exception as e:
        print(f"unable to retrieve which active planner is running: {e}")
        logging.error(f"Unable to retrieve startup active planner status: {e}", exc_info=True)


def _anchor_id(world, name="NOW") -> str:
    """Return the binding id for anchor:<name>, scanning internals or tags; '?' if not found."""
    # Try a direct lookup if available
    try:
        if hasattr(world, "_anchors") and isinstance(world._anchors, dict):
            bid = world._anchors.get(name)
            if bid:
                return bid
    except Exception:
        pass
    # Fallback: scan tags
    for bid, b in world._bindings.items():
        if any(t == f"anchor:{name}" for t in getattr(b, "tags", [])):
            return bid
    return "?"


def _sorted_bids(world) -> list[str]:
    """Return binding ids sorted numerically (b1, b2, ...), with non-numeric ids last.
    -in class World self._bindings={}, i.e., in the instance world, world_bindings.keys() is a
    dict_keys view of all the keys  e.g., dict_keys(['b1', 'b2', 'b3', 'b4'.....])
    nb. Python 3.7+ dicts preserve insertion order, so that is what will be obtained before sorting
    """

    def key_fn(bid: str):
        """
        -strip out the 'b' for sorting bindings, and alphabetical bindings, e.g., NOW,
            sort after the 'b' numerical ones
        -in Python the key= value can be any comparable object, including tuples
        -thus, (0,n) where 'n' is from bn will be sorted ahead of (1, abc) where abc is an alpha binding, e.g., "NOW"
        """
        if bid.startswith("b") and bid[1:].isdigit():
            return (0, int(bid[1:]))   # group 0: numeric, sorted by number
        return (1, bid)                # group 1: non-numeric, sorted by string
    return sorted(world._bindings.keys(), key=key_fn)


def snapshot_text(world, drives=None, ctx=None, policy_rt=None) -> str:
    """
    Render a human-readable snapshot of the runtime state.
    Each value also shows its source attribute for maintainers, e.g., "[src=ctx.ticks]".

    Sections:
    - Header/anchors: EMBODIMENT (ctx.body), NOW/LATEST from world anchors.
    - CTX (Context): agent state (profile, age_days, ticks, winners_k) +
      temporal breadcrumbs: vhash64(now)=ctx.tvec64(), epoch=ctx.boundary_no,
      epoch_vhash64=ctx.boundary_vhash64.
    - TEMPORAL: params from ctx.temporal (dim, sigma, jump), cos_to_last_boundary;
      repeats vhash64(now)/epoch/epoch_vhash64; prints a back-compat alias "vhash64:".
    - DRIVES: drives.hunger/fatigue/warmth.
    - POLICIES (executed this session): per-policy SkillStat telemetry (from skill_readout()).
    - ELIGIBLE NOW: policies with dev_gate(ctx) == True (policy_rt.list_loaded_names()).
    - BINDINGS/EDGES: symbolic nodes/links with their raw sources noted.
    - Footer: nodes/edges count summary.
    """

    def _safe(getter, default=None):
        try:
            return getter()
        except Exception:
            return default

    lines: List[str] = []
    lines.append("\n--------------------------------------------------------------------------------------")
    lines.append(f"WorldGraph snapshot at {datetime.now()}")
    lines.append("--------------------------------------------------------------------------------------")
    lines.extend(_snapshot_temporal_legend())

    # Header / anchors
    body = (getattr(ctx, "body", None)
            or getattr(getattr(ctx, "hal", None), "body", None)
            or "(none)")
    lines.append(f"EMBODIMENT: body={body}  [src=ctx.body or ctx.hal.body]")

    now_id = _anchor_id(world, "NOW")
    latest = getattr(world, "_latest_binding_id", "?")
    lines.append(f"NOW={now_id}  [src=_anchor_id('NOW')]  LATEST={latest}  [src=world._latest_binding_id]")
    origin_id = _anchor_id(world, "NOW_ORIGIN")
    lines.append(f"NOW_ORIGIN={origin_id}  [src=_anchor_id('NOW_ORIGIN')]")
    lines.append(f"NOW_LATEST={latest}  [alias for LATEST/world._latest_binding_id]")
    lines.append("")

    # CTX (Context)
    lines.append("CTX (Context):")
    lines.append("(runtime agent state (profile/age/ticks) + TemporalContext soft clock)")
    if ctx is not None:
        # Print scalar-ish fields explicitly so we can annotate their sources.
        def _add_ctx_scalar(name: str, src: str, fmt="{v}"):
            v = getattr(ctx, name, None)
            if isinstance(v, float):
                lines.append(f"  {name}: {v:.4f}  [src={src}]")
            elif v is not None:
                lines.append(f"  {name}: {fmt.format(v=v)}  [src={src}]")

        _add_ctx_scalar("age_days", "ctx.age_days", "{v:.4f}")
        _add_ctx_scalar("body", "ctx.body")
        _add_ctx_scalar("hal", "ctx.hal")
        _add_ctx_scalar("profile", "ctx.profile")
        lines.append(f"  autonomic_ticks: {getattr(ctx,'ticks',0)}  [src=ctx.ticks]")
        _add_ctx_scalar("winners_k", "ctx.winners_k")

        lines.append(
            "  counts: controller_steps="
            f"{getattr(ctx,'controller_steps',0)}, cog_cycles={getattr(ctx,'cog_cycles',0)}, "
            f"temporal_epochs={getattr(ctx,'boundary_no',0)}, autonomic_ticks={getattr(ctx,'ticks',0)}" )

        # Harmonized temporal breadcrumbs in CTX
        vhash_now = _safe(ctx.tvec64)
        lines.append(f"  vhash64(now): {vhash_now if vhash_now else '(n/a)'}  [src=ctx.tvec64()]")
        epoch_vh = getattr(ctx, "boundary_vhash64", None)
        lines.append(f"  epoch_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [src=ctx.boundary_vhash64]")
        epoch_no = getattr(ctx, "boundary_no", 0)
        lines.append(f"  epoch: {epoch_no}  [src=ctx.boundary_no]")
    else:
        lines.append("  (none)")
    lines.append("")

    # TEMPORAL
    tv = getattr(ctx, "temporal", None)
    if tv:
        lines.append("TEMPORAL:")
        dim   = getattr(tv, "dim", 0)
        sigma = getattr(tv, "sigma", 0.0)
        jump  = getattr(tv, "jump", 0.0)
        lines.append(f"  dim={dim}  [src=ctx.temporal.dim]")
        lines.append(f"  sigma={sigma:.4f}  [src=ctx.temporal.sigma]")
        lines.append(f"  jump={jump:.4f}  [src=ctx.temporal.jump]")

        c = _safe(ctx.cos_to_last_boundary)
        lines.append(
            f"  cos_to_last_boundary: {c:.4f}  [src=ctx.cos_to_last_boundary()]"
            if isinstance(c, float) else
            "  cos_to_last_boundary: (n/a)  [src=ctx.cos_to_last_boundary()]"
        )

        vhash_now = _safe(ctx.tvec64)
        if vhash_now:
            lines.append(f"  vhash64(now): {vhash_now}  [src=ctx.tvec64()]")
            # Back-compat alias for tests expecting plain 'vhash64:'
            lines.append(f"  vhash64: {vhash_now}  [alias of vhash64(now)]")
        else:
            lines.append("  vhash64(now): (n/a)  [src=ctx.tvec64()]")
            lines.append("  vhash64: (n/a)  [alias of vhash64(now)]")

        epoch_no = getattr(ctx, "boundary_no", 0)
        lines.append(f"  epoch: {epoch_no}  [src=ctx.boundary_no]")
        epoch_vh = getattr(ctx, "boundary_vhash64", None)
        if epoch_vh:
            lines.append(f"  epoch_vhash64: {epoch_vh}  [src=ctx.boundary_vhash64]")
            lines.append(f"  last_boundary_vhash64: {epoch_vh}  [alias of epoch_vhash64]")
        # One-line timekeeping summary (compact view)
        if ctx is not None:
            lines.append("TIMEKEEPING: " + timekeeping_line(ctx))

        lines.append("")
    else:
        lines.append("TEMPORAL: (none)")
        lines.append("")

    # DRIVES
    lines.append("DRIVES:")
    if drives is not None:
        try:
            lines.append(
                f"  hunger={drives.hunger:.2f}, fatigue={drives.fatigue:.2f}, warmth={drives.warmth:.2f}  "
                "[src=drives.hunger; drives.fatigue; drives.warmth]"
            )
        except Exception:
            lines.append("  (unavailable)")
    else:
        lines.append("  (none)")
    lines.append("")

    # BODY (BodyMap + near-world) one-line summary
    if ctx is not None:
        try:
            bp = body_posture(ctx)
            md = body_mom_distance(ctx)
            ns = body_nipple_state(ctx)
            # shelter/cliff may not be present on older runs; guard separately
            try:
                sd = body_shelter_distance(ctx)
            except Exception:
                sd = None
            try:
                cd = body_cliff_distance(ctx)
            except Exception:
                cd = None

            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None

            line = (
                "BODY: "
                f"posture={bp or '(n/a)'} "
                f"mom={md or '(n/a)'} "
                f"nipple={ns or '(n/a)'} "
                f"shelter={sd or '(n/a)'} "
                f"cliff={cd or '(n/a)'}"
            )
            if zone is not None:
                line += f" zone={zone}"
            lines.append(line)
        except Exception:
            # Snapshot must stay robust even if BodyMap is missing.
            lines.append("BODY: (unavailable)")
    else:
        lines.append("BODY: (ctx unavailable)")
    lines.append("")

    lines.extend(render_prediction_feedback_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_observation_update_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_expected_current_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_accepted_current_lines_v1(ctx))
    lines.append("")

    lines.extend(render_working_navmap_surface_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_transition_lines_v1(ctx))
    lines.append("")

    lines.extend(render_navmap_scope_frame_lines_v1(ctx))
    lines.append("")

    lines.extend(render_wnm_lines_v1(ctx))
    lines.append("")

    lines.extend(render_feeding_lines_v1(ctx))
    lines.append("")

    # POLICIES (skills readout)
    lines.append("POLICIES:\n (already run at least once, with their SkillStat statistics)  [src=skill_readout()]")
    try:
        sr = skill_readout()
        if sr.strip():
            for ln in sr.strip().splitlines():
                lines.append(f"  {ln}")
        else:
            lines.append("  (none)")
    except Exception:
        lines.append("  (unavailable)")
    lines.append("")

    # POLICY GATES (availability)
    lines.append("POLICIES ELIGIBLE (meet devpt requirements):  [src=policy_rt.list_loaded_names()]")
    try:
        names = policy_rt.list_loaded_names() if policy_rt is not None else []
        if names:
            for nm in names:
                lines.append(f"  - {nm}")
        else:
            lines.append("  (none)")
    except Exception:
        lines.append("  (unavailable)")
    lines.append("")

    # BINDINGS
    lines.append("BINDINGS:")
    for bid in _sorted_bids(world):
        b = world._bindings[bid]
        tags = ", ".join(sorted(getattr(b, "tags", [])))
        eng = getattr(b, "engrams", None)
        if isinstance(eng, dict) and eng:
            parts = []
            for slot, val in eng.items():
                eid = val.get("id") if isinstance(val, dict) else None
                parts.append(f"{slot}:{eid[:8]}…" if isinstance(eid, str) else slot)
            lines.append(f"{bid}: [{tags}] engrams=[{', '.join(parts)}]  [src=world._bindings['{bid}'].tags/engrams]")
        else:
            lines.append(f"{bid}: [{tags}]  [src=world._bindings['{bid}'].tags]")

    # PROMINENCE (top tags; runtime convenience)
    lines.append("")
    lines.append("PROMINENCE (top tags; obs>=2, sorted by act):")
    try:
        rows = world.prominence_top(n=12, sort_by="act", min_obs=2)
    except Exception:
        rows = []
    if not rows:
        lines.append("(none)")
    else:
        for tag, rec in rows:
            try:
                obs = int(rec.get("obs", 0))
            except Exception:
                obs = 0
            try:
                act = float(rec.get("act", 0.0))
            except Exception:
                act = 0.0
            last_step = rec.get("last_step")
            step_key = rec.get("step_key")
            lines.append(f"{tag}: obs={obs} act={act:.2f} last_step={last_step} [{step_key}]")

    # EDGES (collapsed duplicates)
    lines.append("")
    lines.append("EDGES:")
    def _edge_lines_for(bid: str) -> list[str]:
        b = world._bindings[bid]
        edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                 getattr(b, "links", []) or getattr(b, "outgoing", []))
        out: list[str] = []
        if isinstance(edges, list):
            for e in edges:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    out.append(f"{bid} --{rel}--> {dst}  [src=world._bindings['{bid}'].edges]")
        return out

    all_edge_lines: list[str] = []
    for bid in _sorted_bids(world):
        all_edge_lines.extend(_edge_lines_for(bid))

    if not all_edge_lines:
        lines.append("(none)")
    else:
        for line, n in Counter(all_edge_lines).items():
            lines.append(line if n == 1 else f"{line}  ×{n}")

    # Summary footer
    edges_total = len(all_edge_lines)
    lines.append(f"Summary: nodes={len(world._bindings)} edges={edges_total}")
    lines.append("--------------------------------------------------------------------------------------\n")
    return "\n".join(lines)


def export_snapshot(world, drives=None, ctx=None, policy_rt=None,
                    path_txt="world_snapshot.txt", _path_dot=None) -> None:
    """Write a complete snapshot of bindings + edges to a text file (no DOT).
    """
    text_blob = snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt)
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(text_blob + "\n")

    path_txt_abs = os.path.abspath(path_txt)
    out_dir = os.path.dirname(path_txt_abs)
    print("Exported snapshot (text only):")
    print(f"  {path_txt_abs}")
    print(f"Directory: {out_dir}")


def recent_bindings_text(world, limit: int = 5) -> str:
    """
    Build a short, source-annotated list of the last `limit` bindings.
    For each binding, show tags, engram slots, a tiny edge preview, and key meta.
    """
    lines = []
    last_ids = _sorted_bids(world)[-limit:]
    if not last_ids:
        return "(no bindings yet)\n"

    for bid in last_ids:
        b = world._bindings.get(bid)
        # tags
        tags = ", ".join(sorted(getattr(b, "tags", []))) if b else ""
        lines.append(f"  {bid}: tags=[{tags}]  [src=world._bindings['{bid}'].tags]")

        # engrams
        eng = getattr(b, "engrams", None) if b else None
        if isinstance(eng, dict) and eng:
            parts = []
            for slot, val in eng.items():
                eid = val.get("id") if isinstance(val, dict) else None
                parts.append(f"{slot}:{(eid[:8] + '…') if isinstance(eid, str) else '(id?)'}")
            lines.append(f"      engrams=[{', '.join(parts)}]  [src=world._bindings['{bid}'].engrams]")
        else:
            lines.append(f"      engrams=(none)  [src=world._bindings['{bid}'].engrams]")

        # edges (preview up to 3)
        edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                 getattr(b, "links", []) or getattr(b, "outgoing", [])) if b else []
        if isinstance(edges, list) and edges:
            preview = []
            for e in edges[:3]:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    preview.append(f"{rel}:{dst}")
            more = f" (+{len(edges)-3} more)" if len(edges) > 3 else ""
            lines.append(
                f"      outdeg={len(edges)} preview=[{', '.join(preview)}]{more}  "
                f"[src=world._bindings['{bid}'].edges]"
            )
        else:
            lines.append(f"      outdeg=0  [src=world._bindings['{bid}'].edges]")

        # meta highlights (best-effort)
        meta = getattr(b, "meta", {}) if b else {}
        if isinstance(meta, dict) and meta:
            pol = meta.get("policy") or meta.get("created_by")
            created = meta.get("created_at") or meta.get("time") or meta.get("ts")
            extras = []
            if pol:     extras.append(f"policy={pol}")
            if created: extras.append(f"created_at={created}")
            if extras:
                lines.append(f"      meta: {' '.join(extras)}  [src=world._bindings['{bid}'].meta]")

    return "\n".join(lines) + "\n"


def print_env_loop_tag_legend_once(ctx: Ctx) -> None:
    """Print a compact legend for console prefixes (once per session).

    We keep the run output readable for new users, but avoid re-printing the
    legend every time menu 35/37 is used.
    """
    if ctx is None:
        return
    if ctx.env_loop_legend_printed:
        return
    ctx.env_loop_legend_printed = True

    print("\nLegend (console tags):")
    print("  [env-loop]      closed-loop driver (one cognitive cycle = env update → policy select → policy act)")
    print("  [env]           environment events (reset/step; with HAL ON, this would be real sensor I/O)")
    print("  [env→working]   EnvObservation → WorkingMap (fast scratch / map surface)")
    print("  [env→world]     EnvObservation → WorldGraph (long-term episode index)")
    print("  [env→controller] Action Center output (policy selection + execution)")
    print("  [wm<->col]      WorkingMap ⇄ Column keyframe pipeline (store snapshot → retrieve candidates → apply/merge priors)")
    print("  [pred_err]      prediction error v0 (expected vs observed); gates auto-retrieve and shapes policy value via penalty on streaks")
    print("  [gate:<p>]      gating explanation for policy <p>")
    print("  [pick]          which policy was selected this cycle")
    print("  [executed]      policy execution result (effects show up in the NEXT cycle's observation)")
    print("  [maps]          selection_on=map used to score; execute_on=map used to run actions")
    print("  [obs-mask]      partial-observability masking (token drops) when enabled")
    print("")


def _quiet_solved_rest_tail_v1(
    curr_state,
    zone: str | None,
    action_applied_this_step: str | None,
    next_action_for_env: str | None,
) -> bool:
    """Return True when the newborn episode is already in a stable solved rest tail.

    This helper is intentionally cosmetic-only. It does not alter controller or
    environment behavior. It simply identifies the late solved state where
    repeating the same explanatory prose and the same SurfaceGrid ASCII map each
    cycle adds noise but little new information.

    We call the rest tail "quiet" only when all of these are already true:
      - scenario_stage == "rest"
      - kid_posture == "resting"
      - mom_distance == "touching"
      - nipple_state == "latched"
      - zone == "safe"
      - no action was applied this step
      - no next action is queued for the next environment step

    The first transition into rest is therefore still explained normally. Only
    the later steady-state tail becomes quieter.
    """
    if curr_state is None or zone != "safe":
        return False

    try:
        stage = getattr(curr_state, "scenario_stage", None)
        posture = getattr(curr_state, "kid_posture", None)
        mom_distance = getattr(curr_state, "mom_distance", None)
        nipple_state = getattr(curr_state, "nipple_state", None)
    except Exception:
        return False

    if stage != "rest":
        return False
    if posture != "resting":
        return False
    if mom_distance != "touching":
        return False
    if nipple_state != "latched":
        return False

    if isinstance(action_applied_this_step, str) and action_applied_this_step:
        return False
    if isinstance(next_action_for_env, str) and next_action_for_env:
        return False

    return True


def _print_cog_cycle_footer(*,
                            ctx: "Ctx",
                            drives,
                            env_obs,
                            prev_state,
                            curr_state,
                            env_step: int | None,
                            zone: str | None,
                            inj: dict[str, Any] | None,
                            fired_txt: str | None,
                            col_store_txt: str | None,
                            col_retrieve_txt: str | None,
                            col_apply_txt: str | None,
                            action_applied_this_step: str | None,
                            next_action_for_env: str | None,
                            cycle_no: int,
                            cycle_total: int) -> None:
    """
    Print a compact, end-of-cycle footer intended for fast human scanning.

    Intent
    ------
    Menu 37 (closed-loop env↔controller runs) produces many diagnostic lines. This footer is the
    "cheap digest" line-set that lets a maintainer quickly see what happened in *this* cognitive
    cycle in terms of the architecture:

      inputs → MapSurface deltas → Scratch writes → WorldGraph writes → Column ops → action

    The footer is intentionally pragmatic and will evolve as Phase IX/robotics/HAL integration evolves.
    Treat it as a reading aid, not a stable API.

    Notes
    -----
    - "MapSurface deltas" are derived from EnvState diffs (authoritative simulator truth). MapSurface is
      driven by EnvObservation, so EnvState changes correspond to slot-family changes (posture, proximity,
      hazard, nipple, etc.).
    - "Scratch writes" are summarized from the policy runtime's returned text (added bindings, executed line).
    - Column ops are summarized from the wm<->col store/retrieve/apply block when it ran this cycle.
    """
    if not bool(getattr(ctx, "env_loop_cycle_summary", True)):
        return

    try:
        max_items = int(getattr(ctx, "env_loop_cycle_summary_max_items", 6) or 6)
    except Exception:
        max_items = 6

    def _sf(x) -> str:
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "n/a"

    def _fmt_items(items, *, prefix: str = "", limit: int = 6) -> str:
        if not items:
            return "(none)"
        out = []
        for it in items:
            if isinstance(it, str) and it:
                out.append(f"{prefix}{it}")
        if not out:
            return "(none)"
        if len(out) <= limit:
            return ", ".join(out)
        head = ", ".join(out[:limit])
        return f"{head}, +{len(out) - limit} more"


    def _get_state_attr(st, name: str):
        try:
            return getattr(st, name, None)
        except Exception:
            return None


    def _obs_write_strings(raw: Any) -> list[str]:
        """Return non-empty strings from common JSON-safe obs-write shapes.

        The EnvObservation injection path has evolved over time. Most runs provide
        lists such as ["posture:fallen"], but some diagnostic paths may provide a
        dict such as token_to_bid. This helper keeps the footer defensive without
        changing the underlying memory write behavior.
        """
        if isinstance(raw, str):
            return [raw] if raw else []

        raw_iter: Any
        if isinstance(raw, dict):
            raw_iter = raw.keys()
        elif isinstance(raw, (list, tuple, set)):
            raw_iter = raw
        else:
            return []

        out: list[str] = []
        for item in raw_iter:
            if isinstance(item, str) and item:
                out.append(item)
            elif isinstance(item, dict):
                for key in ("token", "tag", "name"):
                    val = item.get(key)
                    if isinstance(val, str) and val:
                        out.append(val)
                        break
        return out


    def _clean_obs_family_token(tok: str, *, family: str) -> str | None:
        """Normalize one pred/cue token for footer display.

        Returned tokens are prefix-free because the footer later adds the display
        prefix itself via _fmt_items(..., prefix="pred:"/"cue:").
        """
        text = str(tok or "").strip()
        if not text:
            return None

        own_prefix = f"{family}:"
        if text.startswith(own_prefix):
            return text[len(own_prefix):]

        if text.startswith("pred:") or text.startswith("cue:"):
            return None

        return text


    def _dedup_obs_tokens(items: list[str]) -> list[str]:
        """De-duplicate footer tokens while preserving their original order."""
        out: list[str] = []
        seen: set[str] = set()

        for item in items:
            if item not in seen:
                seen.add(item)
                out.append(item)

        return out


    def _obs_write_family_values(src: dict[str, Any], keys: tuple[str, ...], *, family: str) -> list[str]:
        """Return obs-write values from the first matching schema key."""
        for key in keys:
            out: list[str] = []
            for item in _obs_write_strings(src.get(key)):
                tok = _clean_obs_family_token(item, family=family)
                if tok:
                    out.append(tok)

            if out:
                return _dedup_obs_tokens(out)

        return []


    def _looks_like_pred_token(tok: str) -> bool:
        """Classify unprefixed token_to_bid fallback keys that are clearly predicates."""
        text = str(tok or "").strip()
        return (
            text.startswith("posture:")
            or text.startswith("proximity:")
            or text.startswith("hazard:")
            or text.startswith("nipple:")
            or text.startswith("milk:")
            or text in ("resting", "alert", "seeking_mom")
        )


    def _surface_deltas(ps, cs) -> list[str]:
        # These correspond to the newborn-goat "big slots" that map cleanly onto MapSurface slot-families.
        fields = [
            ("posture", "kid_posture"),
            ("mom", "mom_distance"),
            ("shelter", "shelter_distance"),
            ("cliff", "cliff_distance"),
            ("nipple", "nipple_state"),
        ]
        out: list[str] = []
        for label, attr in fields:
            a = _get_state_attr(ps, attr) if ps is not None else None
            b = _get_state_attr(cs, attr) if cs is not None else None
            if ps is None:
                out.append(f"{label}={b}")
            else:
                if a != b:
                    out.append(f"{label} {a}→{b}")
        return out

    def _parse_fired(txt: str | None) -> dict[str, Any]:
        # fired text is produced by PolicyRuntime.consider_and_maybe_fire(...).
        out: dict[str, Any] = {"policy": None, "added": None, "reward": None, "sel_on": None, "exec_on": None}
        if not (isinstance(txt, str) and txt.strip()):
            return out
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if not lines:
            return out

        # First line: "policy:xyz (added N bindings)"
        first = lines[0]
        parts = first.split()
        if parts and parts[0].startswith("policy:"):
            out["policy"] = parts[0]
        m = re.search(r"added\s+(\d+)\s+bindings", first)
        if m:
            try:
                out["added"] = int(m.group(1))
            except Exception:
                out["added"] = None

        for ln in lines:
            if ln.startswith("[executed]"):
                # Example: [executed] policy:follow_mom (ok, reward=+0.10) binding=w38 (b38)
                m2 = re.search(r"reward=([+\-]?\d+(?:\.\d+)?)", ln)
                if m2:
                    try:
                        out["reward"] = float(m2.group(1))
                    except Exception:
                        out["reward"] = None
            if ln.startswith("[maps]"):
                # Example: [maps] selection_on=WG execute_on=WM
                if "selection_on=" in ln:
                    try:
                        out["sel_on"] = ln.split("selection_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
                if "execute_on=" in ln:
                    try:
                        out["exec_on"] = ln.split("execute_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
        return out

    # Keyframe indicator: best-effort. (Keyframe reasons still appear in the KEYFRAME log line above.)
    is_kf = False
    try:
        is_kf = (getattr(ctx, "lt_obs_last_keyframe_step", None) == getattr(ctx, "controller_steps", None))
    except Exception:
        is_kf = False

    st_stage = _get_state_attr(curr_state, "scenario_stage")
    st_post  = _get_state_attr(curr_state, "kid_posture")
    st_mom   = _get_state_attr(curr_state, "mom_distance")
    st_nip   = _get_state_attr(curr_state, "nipple_state")

    dr_h = _sf(getattr(drives, "hunger", None))
    dr_f = _sf(getattr(drives, "fatigue", None))
    dr_w = _sf(getattr(drives, "warmth", None))

    # WG write summary (env injection)
    wg_preds: list[str] = []
    wg_cues: list[str] = []
    wg_keyframe = False
    wg_reason_txt = ""

    if isinstance(inj, dict):
        wg_preds = _obs_write_family_values(
            inj,
            (
                "predicates",
                "preds",
                "created_preds",
                "created_predicates",
                "written_predicates",
                "predicates_written",
                "preds_written",
            ),
            family="pred",
        )
        wg_cues = _obs_write_family_values(
            inj,
            (
                "cues",
                "created_cues",
                "written_cues",
                "cues_written",
            ),
            family="cue",
        )

        # Fallback for obs_write schemas that expose only token_to_bid.
        # Unprefixed fallback keys are only treated as predicates when they are from
        # known state-slot families, so we do not accidentally label arbitrary cue text.
        if not (wg_preds or wg_cues):
            token_to_bid = inj.get("token_to_bid")
            if isinstance(token_to_bid, dict):
                pred_fallback: list[str] = []
                cue_fallback: list[str] = []

                for raw_key in token_to_bid.keys():
                    if not isinstance(raw_key, str) or not raw_key:
                        continue

                    key = raw_key.strip()
                    if key.startswith("cue:"):
                        tok = _clean_obs_family_token(key, family="cue")
                        if tok:
                            cue_fallback.append(tok)
                    elif key.startswith("pred:"):
                        tok = _clean_obs_family_token(key, family="pred")
                        if tok:
                            pred_fallback.append(tok)
                    elif _looks_like_pred_token(key):
                        pred_fallback.append(key)

                wg_preds = _dedup_obs_tokens(pred_fallback)
                wg_cues = _dedup_obs_tokens(cue_fallback)

        wg_keyframe = bool(inj.get("keyframe"))

        reason_items = _obs_write_strings(
            inj.get("keyframe_reasons")
            or inj.get("keyframe_reason")
            or inj.get("reasons")
        )
        reason_items = _dedup_obs_tokens(reason_items)
        if reason_items:
            wg_reason_txt = " reason=" + _fmt_items(reason_items, prefix="", limit=3)

    # EnvObservation input summary (what crossed the env→agent boundary this tick)
    obs_preds: list[str] = []
    obs_cues: list[str] = []
    obs_drop_p = 0
    obs_drop_c = 0
    if env_obs is not None:
        try:
            pr = getattr(env_obs, "predicates", None)
            if isinstance(pr, list):
                obs_preds = [str(x).replace("pred:", "", 1) for x in pr if isinstance(x, str) and x]
        except Exception:
            obs_preds = []

        try:
            cr = getattr(env_obs, "cues", None)
            if isinstance(cr, list):
                obs_cues = [str(x).replace("cue:", "", 1) for x in cr if isinstance(x, str) and x]
        except Exception:
            obs_cues = []

        try:
            em = getattr(env_obs, "env_meta", None)
            if isinstance(em, dict):
                obs_drop_p = int(em.get("obs_mask_dropped_preds", 0) or 0)
                obs_drop_c = int(em.get("obs_mask_dropped_cues", 0) or 0)
        except Exception:
            obs_drop_p = 0
            obs_drop_c = 0

    fired_info = _parse_fired(fired_txt)

    # ---- line 1: inputs
    kf_txt = "KF" if is_kf else "--"
    step_txt = str(env_step) if isinstance(env_step, int) else "?"
    zone_txt = zone if isinstance(zone, str) else "?"

    mask_txt = ""
    if (obs_drop_p or obs_drop_c) and (obs_drop_p >= 0 and obs_drop_c >= 0):
        mask_txt = f" mask_drop(p={obs_drop_p} c={obs_drop_c})"

    print(
        f"[cycle] IN   {kf_txt} cycle={cycle_no}/{cycle_total} env_step={step_txt} "
        f"stage={st_stage} posture={st_post} mom={st_mom} nipple={st_nip} zone={zone_txt} "
        f"drives(h={dr_h} f={dr_f} w={dr_w}) applied_action={action_applied_this_step!r} "
        f"obs(p={len(obs_preds)} c={len(obs_cues)}){mask_txt}"
    )

    # ---- line 1b: observation detail (preds/cues + navpatch summary)
    patches_in = getattr(env_obs, "nav_patches", None) or []
    patch_n = len(patches_in) if isinstance(patches_in, list) else 0
    uniq_sig16: set[str] = set()
    patch_ids: set[str] = set()

    if patch_n:
        for p in patches_in:
            if not isinstance(p, dict):
                continue

            try:
                uniq_sig16.add(navpatch_payload_sig_v1(p)[:16])
            except Exception:
                pass

            role = p.get("role") if isinstance(p.get("role"), str) else ""
            local_id = p.get("local_id") if isinstance(p.get("local_id"), str) else ""
            entity_id = p.get("entity_id") if isinstance(p.get("entity_id"), str) else ""

            key = ""
            if role and local_id:
                key = f"{role}|{local_id}"
            elif role and entity_id:
                key = f"{role}|{entity_id}"
            elif entity_id and local_id:
                key = f"{entity_id}|{local_id}"
            elif role:
                key = role
            elif local_id:
                key = local_id
            elif entity_id:
                key = entity_id

            if key:
                patch_ids.add(key)

    ids_txt = ""
    if patch_ids:
        ids = sorted(patch_ids)
        show_n = 4
        shown = ids[:show_n]
        more = len(ids) - len(shown)

        ids_body = ", ".join(shown)
        if more > 0:
            ids_body = ids_body + f", +{more} more"

        ids_txt = f" ids=[{ids_body}]"

    nav_txt = f"nav_patches={patch_n} uniq_sig16={len(uniq_sig16)}{ids_txt}"

    obs_note_txt = ""
    try:
        obs_pred_set = {str(x) for x in obs_preds if isinstance(x, str) and x}
        if (
            isinstance(st_post, str)
            and st_post == "latched"
            and "posture:standing" in obs_pred_set
            and "nipple:latched" in obs_pred_set
            and "milk:drinking" in obs_pred_set
        ):
            obs_note_txt = (
                " | note: in this early CCA8, env_posture='latched' is encoded perceptually as "
                "posture:standing + nipple:latched + milk:drinking"
            )
    except Exception:
        obs_note_txt = ""

    if obs_preds or obs_cues or patch_n:
        pred_txt = _fmt_items(obs_preds, prefix="", limit=max_items) if obs_preds else "(none)"
        cue_txt = _fmt_items(obs_cues, prefix="", limit=max_items) if obs_cues else "(none)"
        print(f"[cycle] OBS  preds: {pred_txt} | cues: {cue_txt} | {nav_txt}{obs_note_txt}")

    # ---- line 2: WorkingMap summary (surface deltas + scratch writes)
    deltas = _surface_deltas(prev_state, curr_state)
    delta_txt = _fmt_items(deltas, prefix="", limit=max_items) if deltas else "(no surface slot change)"
    pol = fired_info.get("policy") or next_action_for_env
    added = fired_info.get("added")
    exec_on = fired_info.get("exec_on")
    scratch_txt = "(no policy fired)"
    if isinstance(pol, str) and pol:
        if isinstance(added, int):
            scratch_txt = f"{pol} +{added} binding(s)"
        else:
            scratch_txt = f"{pol}"
        if exec_on:
            scratch_txt += f" (exec_on={exec_on})"
    print(f"[cycle] WM   surfaceΔ: {delta_txt} | scratch: {scratch_txt}")
    # [cycle] ZM — Zoom transitions (Phase X Step 15B)
    # We only print on transition ticks (zoom_down / zoom_up) so logs stay readable.
    try:
        z_events = getattr(ctx, "wm_zoom_last_events", None)
        if isinstance(z_events, list) and z_events:
            ev0 = z_events[0] if isinstance(z_events[0], dict) else {}
            kind = ev0.get("kind") if isinstance(ev0.get("kind"), str) else "zoom"
            reason = ev0.get("reason") if isinstance(ev0.get("reason"), str) else ""
            ents = ev0.get("ambiguous_entities") if isinstance(ev0.get("ambiguous_entities"), list) else []
            ent_txt = _fmt_items(ents, prefix="", limit=3) if ents else "(none)"
            amb_n = ev0.get("ambiguous_n")
            try:
                amb_n = int(amb_n) if amb_n is not None else None
            except Exception:
                amb_n = None
            amb_txt = f" amb={amb_n}" if isinstance(amb_n, int) else ""
            rz = f" reason={reason}" if reason else ""
            print(f"[cycle] ZM   {kind}{rz}{amb_txt} ents={ent_txt}")
    except Exception:
        pass

    # [cycle] MS — Map-switch events (P3.11)
    try:
        ms_events = getattr(ctx, "wm_mapswitch_last_events", None)
        if isinstance(ms_events, list) and ms_events:
            ev0 = ms_events[-1] if isinstance(ms_events[-1], dict) else {}
            line = format_mapswitch_event_line_v1(ev0)
            if line and line != "(none)":
                print(f"[cycle] MS   {line}")
    except Exception:
        pass


    # [cycle] SG — SurfaceGrid HUD (Phase X Step 12)
    if bool(getattr(ctx, "wm_surfacegrid_enabled", False)):
        sg_sig16 = getattr(ctx, "wm_surfacegrid_sig16", None)
        sg_sig16 = sg_sig16 if isinstance(sg_sig16, str) and sg_sig16 else "(none)"
        try:
            sg_ms = float(getattr(ctx, "wm_surfacegrid_compose_ms", 0.0) or 0.0)
        except Exception:
            sg_ms = 0.0

        reasons = getattr(ctx, "wm_surfacegrid_dirty_reasons", None)
        reasons = reasons if isinstance(reasons, list) else []

        reason_items = [str(r) for r in reasons[:3] if isinstance(r, str) and r]
        if reason_items == ["cache_hit"]:
            reason_txt = ""
        else:
            reason_txt = ",".join(reason_items)
            reason_txt = f" ({reason_txt})" if reason_txt else ""

        print(f"[cycle] SG   surfacegrid_sig16={sg_sig16} compose_ms={sg_ms:.2f}{reason_txt}")

        # ASCII map dump:
        # Optional ASCII map dump using the same changed-vs-unchanged logic as
        # the older [surfacegrid] snapshot path.
        if bool(getattr(ctx, "wm_surfacegrid_verbose", False)):
            legend_txt = (
                "@=self &=self+mom M=mom S=shelter C=cliff G=goal "
                "#=hazard X=blocked *=other  (dense: .=traversable; sparse: space=unknown/trav)"
            )
            sg = getattr(ctx, "wm_surfacegrid", None)
            print(
                _surfacegrid_ascii_terminal_block_v1(
                    ctx,
                    sg,
                    sig16=sg_sig16,
                    line_prefix="[cycle] SG   ",
                    title=f"WM.SurfaceGrid (sig16={sg_sig16})",
                    legend=legend_txt,
                )
            )

    # [cycle] NS — NavSummary HUD (Phase X P1.4)
    try:
        if bool(getattr(ctx, "wm_navsummary_enabled", False)):
            ns = getattr(ctx, "wm_navsummary", None)
            if isinstance(ns, dict) and ns:
                print(f"[cycle] NS   {format_navsummary_line_v1(ns)}")
    except Exception:
        pass

    # ---- line 3: WorldGraph writes this tick
    wg_txt = f"preds+{len(wg_preds)} cues+{len(wg_cues)}"
    if wg_keyframe:
        wg_txt += " keyframe=Y"

    wg_pred_txt = _fmt_items(wg_preds, prefix="pred:", limit=max_items)
    wg_cue_txt = _fmt_items(wg_cues, prefix="cue:", limit=max_items)
    print(f"[cycle] WG   wrote {wg_txt}{wg_reason_txt} | {wg_pred_txt} | {wg_cue_txt}")

    # ---- line 4: Column ops (only meaningful on keyframes)
    if col_store_txt or col_retrieve_txt or col_apply_txt:
        cs = col_store_txt or "store: (n/a)"
        cr = col_retrieve_txt or "retrieve: (n/a)"
        ca = col_apply_txt or "apply: (n/a)"
        print(f"[cycle] COL  {cs} | {cr} | {ca}")
    else:
        print("[cycle] COL  (no wm<->col ops this cycle)")

    # ---- line 5: action recap
    r = fired_info.get("reward")
    rtxt = f"{r:+.2f}" if isinstance(r, (int, float)) else "n/a"
    print(f"[cycle] ACT  executed={pol!r} reward={rtxt} next_action={next_action_for_env!r}")


def mini_snapshot_text(world, ctx=None, limit: int = 50) -> str:
    """
    Compact mini-snapshot: one timekeeping line + a short list of recent bindings
    with their outgoing edges.

    Intentionally omits [src=...] annotations so readers see only the conceptual
    structure (bindings/tags/edges) without internal implementation details.
    """
    lines: list[str] = []

    # Timekeeping line (if ctx is available)
    if ctx is not None:
        try:
            lines.append("[time] " + timekeeping_line(ctx))
        except Exception:
            lines.append("[time] (unavailable)")
    else:
        lines.append("[time] (ctx unavailable)")

    try:
        lines.append(prediction_feedback_mini_line_v1(ctx))
    except Exception:
        lines.append("[pred] (unavailable)")

    try:
        lines.append(navmap_observation_update_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap] (unavailable)")

    try:
        lines.append(navmap_expected_current_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-expected] (unavailable)")

    try:
        lines.append(navmap_accepted_current_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-accepted] (unavailable)")

    try:
        lines.append(working_navmap_surface_mini_line_v1(ctx))
    except Exception:
        lines.append("[working-navmap] (unavailable)")

    try:
        lines.append(navmap_transition_mini_line_v1(ctx))
    except Exception:
        lines.append("[navmap-transition] (unavailable)")

    try:
        lines.append(navmap_scope_mini_line_v1(ctx))
    except Exception:
        lines.append(f"{NAVMAP_SCOPE_MARKER_V1} [navmap-scope] (unavailable)")

    try:
        wnm = wnm_summary_v1(ctx)
        operative = wnm.get("operative_map")
        operative = operative if isinstance(operative, dict) else {}
        lines.append(
            "[wnm] "
            f"status={wnm.get('status')} operative={operative.get('role') or '(none)'} "
            f"ready={wnm.get('ready_count', 0)}/{wnm.get('ready_capacity', 0)}"
        )
    except Exception:
        lines.append("[wnm] (unavailable)")

    try:
        feeding = feeding_operative_readout_v1(ctx)
        lines.append(
            "[feeding] "
            f"detail={feeding.get('detail_level', 'unavailable')} "
            f"target={feeding.get('target_localized')} reach={feeding.get('reachability', 'unknown')} "
            f"contact={feeding.get('contact')} latch={feeding.get('latch_evidence')} "
            f"milk={feeding.get('milk_evidence')}"
        )
    except Exception:
        lines.append("[feeding] (unavailable)")

    # Compact world view: last `limit` bindings with their outgoing edges
    try:
        bids = _sorted_bids(world)
    except Exception:
        bids = []

    if not bids:
        lines.append("[world] no bindings yet")
        return "\n".join(lines)

    n = min(limit, len(bids))
    lines.append(f"[world] last {n} binding(s):")
    for bid in bids[-n:]:
        b = world._bindings.get(bid)
        tags = ", ".join(sorted(getattr(b, "tags", []))) if b else ""
        lines.append(f"  {bid}: [{tags}]")

        # Robust edge extraction with explicit typing (for mypy)
        edges: list[dict[str, Any]] = []
        if b is not None:
            edges_raw = (
                getattr(b, "edges", []) or
                getattr(b, "out", []) or
                getattr(b, "links", []) or
                getattr(b, "outgoing", [])
            )
            if isinstance(edges_raw, list):
                edges = [e for e in edges_raw if isinstance(e, dict)]

        if edges:
            parts: list[str] = []
            for e in edges:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    parts.append(f"{rel}:{dst}")
            if parts:
                lines.append(f"      edges: {', '.join(parts)}")
            else:
                lines.append("      edges: (none)")
        else:
            lines.append("      edges: (none)")

    # Optional posture discrepancy note (env vs policy-expected posture).
    # This is a *display-only* diagnostic: we do NOT create any bindings.
    history_entry: Optional[str] = None
    try:
        env_bid, env_posture, _ = _latest_posture_binding(
            world, source="HybridEnvironment"
        )
        pol_bid, pol_posture, pol_meta = _latest_posture_binding(
            world, require_policy=True
        )

        if env_bid and pol_bid and env_posture and pol_posture and env_posture != pol_posture:
            def _posture_suffix(tag: str) -> str:
                parts = tag.split(":", 2)
                return parts[-1] if parts else tag

            env_state = _posture_suffix(env_posture)
            pol_state = _posture_suffix(pol_posture)
            pol_name = pol_meta.get("policy") if isinstance(pol_meta, dict) else None

            if pol_name:
                msg_main = (
                    f"[discrepancy] env posture={env_state!r} at {env_bid} "
                    f"vs policy-expected posture={pol_state!r} from {pol_name} at {pol_bid}"
                )
            else:
                msg_main = (
                    f"[discrepancy] env posture={env_state!r} at {env_bid} "
                    f"vs policy-expected posture={pol_state!r} at {pol_bid}"
                )

            msg_hint = (
                "[discrepancy] note: a mismatch can be normal right after reset (env has not yet applied the last action); "
                "persistent mismatches across steps suggest failed execution or storyboard veto."
            )

            lines.append(msg_main)
            lines.append(msg_hint)
            history_entry = msg_main

    except Exception:
        # Snapshot must never crash the runner.
        pass

    # Maintain and print discrepancy history (last ~50 events), if ctx supports it.
    try:
        if ctx is not None and hasattr(ctx, "posture_discrepancy_history"):
            hist: list[str] = getattr(ctx, "posture_discrepancy_history", [])
            # Append the newest entry if it exists and is not a duplicate of the last one
            if history_entry:
                if not hist or hist[-1] != history_entry:
                    hist.append(history_entry)
                    if len(hist) > 50:
                        del hist[:-50]
                ctx.posture_discrepancy_history = hist  # in case it was missing before

            if hist:
                lines.append("")
                lines.append("[discrepancy history] recent posture discrepancies (most recent last):")
                for h in hist:
                    lines.append("  " + h)
    except Exception:
        # Again, history bookkeeping must never crash the runner.
        pass

    return "\n".join(lines)


def print_mini_snapshot(world, ctx=None, limit: int = 50) -> None:
    """Print the compact mini-snapshot (safe to call from menu flow).
    """
    try:
        print("Values of time measures, nodes and links at this point:")
        print(mini_snapshot_text(world, ctx, limit))
    except Exception:
        pass


def drives_and_tags_text(drives) -> str:
    """
    Human-readable drives panel with source annotations and a concise explainer.
    """
    lines = []
    lines.append("Raw drives (0..1). Policies can read raw values or threshold flags.")
    lines.append(
        f"  hunger={drives.hunger:.2f}  [src=drives.hunger]  "
        f"HUNGER_HIGH={HUNGER_HIGH:.2f}  [src=cca8_controller.HUNGER_HIGH]"
    )
    lines.append(
        f"  fatigue={drives.fatigue:.2f}  [src=drives.fatigue]  "
        f"FATIGUE_HIGH={FATIGUE_HIGH:.2f}  [src=cca8_controller.FATIGUE_HIGH]"
    )
    lines.append(
        f"  warmth={drives.warmth:.2f}  [src=drives.warmth]  "
        f"rule:cold if warmth<0.30  [src=_drive_tags (derived)]"
    )

    # Compute the tags + show where they came from (flags/predicates/derived)
    if hasattr(drives, "flags") and callable(getattr(drives, "flags")):
        tag_source = "drives.flags()"
    elif hasattr(drives, "predicates") and callable(getattr(drives, "predicates")):
        tag_source = "drives.predicates()"
    else:
        tag_source = "derived thresholds (hunger>0.60, fatigue>0.70, warmth<0.30)"

    tags = _drive_tags(drives)
    lines.append(
        "Drive tags: " +
        (", ".join(tags) if tags else "(none)") +
        f"  [src=_drive_tags → {tag_source}]"
    )

    lines.append("")
    lines.append("Where these live:")
    lines.append("  - Drives object: cca8_controller.Drives  [src=cca8_controller.Drives]")
    lines.append("  - Updated by: autonomic ticks, policies, or direct code.")
    lines.append("  - Drive tags here are ephemeral (not persisted unless you choose to).")

    # === Integrated ~10-line explainer ===
    lines.append("")
    lines.append("Drive flags = thresholds from raw drives (e.g., hunger>=HUNGER_HIGH")
    lines.append("  → drive:hunger_high). They are ephemeral and usually NOT written")
    lines.append("  to the graph; used to gate/weight policies.")
    lines.append("House style: use pred:drive:* only when you want a planner goal")
    lines.append("  (e.g., pred:drive:warm_enough). Otherwise treat thresholds as")
    lines.append("  evidence in triggers (conceptually cue:drive:*).")
    lines.append("Combine flags with sensory cues (e.g., cue:silhouette:mom) in")
    lines.append("  policy.trigger(...). Example: hunger>=HUNGER_HIGH AND cue:nipple:found.")
    lines.append("Priority variant: cues gate; hunger over threshold scales reward/urgency.")
    lines.append("We compute flags on-the-fly each controller step or autonomic tick; persist them only for demos/debug.")
    lines.append("Sources: raw=drives.*, thresholds=HUNGER_HIGH/FATIGUE_HIGH (controller).")

    return "\n".join(lines) + "\n"


def skill_ledger_text(example_policy: str = "policy:stand_up") -> str:
    """
    Human-readable explainer for the Skill Ledger with a concrete example and sources.
    """
    lines = []
    lines.append("The Skill Ledger is per-policy runtime telemetry (RL-flavored):")
    lines.append("  n=executions, succ=successes, rate=succ/n, q=mean reward, last=last reward.")
    lines.append("  Used as a quick controller health check and for tuning/diagnostics.")
    lines.append("Sources: live in-memory ledger → cca8_controller.SKILLS;")
    lines.append("         programmatic snapshot → cca8_controller.skills_to_dict();")
    lines.append("         human-readable lines  → cca8_controller.skill_readout().")
    lines.append("")

    # Example row (policy:stand_up) pulled from skills_to_dict(), with fallbacks
    try:
        d = skills_to_dict() or {}
    except Exception:
        d = {}
    row = d.get(example_policy, {}) if isinstance(d, dict) else {}

    def _get(dd, *keys, default=None):
        for k in keys:
            if isinstance(dd, dict) and k in dd:
                return dd[k]
        return default

    n     = _get(row, "n", "runs", "count", default=0) or 0
    succ  = _get(row, "succ", "successes", "ok", default=0) or 0
    rate  = _get(row, "rate", default=(succ / n if n else None))
    q     = _get(row, "q", "mean_reward", "avg", default=None)
    last  = _get(row, "last", "last_reward", default=None)

    def _fmt(x, nd=2, plus=False):
        if x is None:
            return "n/a"
        try:
            val = float(x)
            if not isfinite(val):
                return "n/a"
            s = f"{val:+.{nd}f}" if plus else f"{val:.{nd}f}"
            return s
        except Exception:
            return str(x)

    lines.append(f"Example ({example_policy}): "
                 f"n={n}, succ={succ}, rate={_fmt(rate)}, q={_fmt(q)}, last={_fmt(last, plus=True)}  "
                 f"[src=skills_to_dict()['{example_policy}']]")
    lines.append("")
    lines.append("Interpretation: higher n builds confidence; rate≈1.0 means it rarely fails;")
    lines.append("q tracks average reward quality; last is the most recent reward sample.")
    return "\n".join(lines) + "\n"


def skills_hud_text(ctx: Optional[Ctx] = None, *, top_n: int = 8) -> str:
    """
    Compact HUD for learned policy values (SkillStat.q).

    - Sorts policies by q (EMA reward) descending.
    - Shows basic counts: n, succ-rate, q, last_reward.
    - If ctx is provided, also prints RL settings + explore/exploit counters.

    This is intentionally a *read-only* helper (no world writes).
    """
    try:
        raw = skills_to_dict() or {}
    except Exception:
        raw = {}

    try:
        delta = float(getattr(ctx, "rl_delta", 0.0))
    except Exception:
        delta = 0.0
    delta = max(delta, 0.0)

    rows: list[tuple[str, int, int, float, float]] = []
    for name, stat in raw.items():
        if not isinstance(name, str) or not isinstance(stat, dict):
            continue
        try:
            n = int(stat.get("n", 0) or 0)
            succ = int(stat.get("succ", 0) or 0)
            q = float(stat.get("q", 0.0) or 0.0)
            last = float(stat.get("last_reward", 0.0) or 0.0)
        except Exception:
            continue
        if n <= 0:
            continue
        rows.append((name, n, succ, q, last))

    if not rows:
        return "(no skill stats yet)"

    # Sort: high q first, then higher n, then name for stability
    rows.sort(key=lambda t: (-t[3], -t[1], t[0]))

    lines: list[str] = []

    if ctx is not None:
        enabled = bool(getattr(ctx, "rl_enabled", False))
        eps_raw = getattr(ctx, "rl_epsilon", None)
        try:
            eff_eps = float(eps_raw) if eps_raw is not None else float(getattr(ctx, "jump", 0.0))
        except (TypeError, ValueError):
            eff_eps = float(getattr(ctx, "jump", 0.0))

        explore = int(getattr(ctx, "rl_explore_steps", 0) or 0)
        exploit = int(getattr(ctx, "rl_exploit_steps", 0) or 0)
        total = explore + exploit
        explore_rate = (explore / total) if total else 0.0

        lines.append(
            "RL: "
            f"enabled={enabled} "
            f"epsilon={eff_eps:.3f} "
            f"delta={delta:.3f} "
            f"(explore={explore}, exploit={exploit}, explore_rate={explore_rate:.2f})"
        )

    show_n = min(top_n, len(rows))
    lines.append(f"Skill HUD (top {show_n} by q=EMA reward):")

    for i, (name, n, succ, q, last) in enumerate(rows[:show_n], start=1):
        rate = (succ / n) if n else 0.0
        lines.append(
            f"  {i:2d}) {name:<18}  n={n:3d}  rate={rate:.2f}  q={q:+.2f}  last={last:+.2f}"
        )

    return "\n".join(lines)


def _io_banner(args, loaded_path: str | None, loaded_ok: bool) -> None:
    """Explain how load/autosave will behave for this run.
    """
    ap = (args.autosave or "").strip() if hasattr(args, "autosave") else ""
    lp = (loaded_path or "").strip() if loaded_path else ""
    def _same(a, b):  # robust path compare
        try: return os.path.abspath(a) == os.path.abspath(b)
        except Exception: return a == b

    if loaded_ok and ap and _same(ap, lp):
        print(f"[io] Loaded '{lp}'. Autosave ON to the same file — state will be saved in-place after each action. "
              f"(the file is fully rewritten on each autosave).")
    elif loaded_ok and ap and not _same(ap, lp):
        print(f"[io] Loaded '{lp}'. Autosave ON to '{ap}' — new steps will be written to the autosave file; "
              f"the original load file remains unchanged.")
    elif loaded_ok and not ap:
        print(f"[io] Loaded '{lp}'. Autosave OFF")
        print("[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>.")
    elif (not loaded_ok) and ap:
        print(f"[io] Started a NEW session. Autosave ON to '{ap}'.")
    else:
        print("[io] Started a NEW session. Autosave OFF — use menu selection Save Session or relaunch with --autosave <path>.")
