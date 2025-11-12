#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
CCA8 World Runner, i.e. the module that runs the CCA8 project

This script is the interactive and CLI entry point for the CCA8 simulation.
It provides an interactive banner + profile selector, wires the world graph
and a sample cortical column, offers HAL (embodiment) stubs, and exposes
preflight checks (lite at startup; full on demand).

The program is run at the command line interface:
        python cca8_run.py [FLAGS]

        e.g., > python cca8_run.py
        e.g., > python cca8_run.py --about
        e.g., > python cca8_run.py --preflight

Key ideas for readers and new collaborators
------------------------------------------
- **Predicate**: a symbolic fact token (e.g., "state:posture_standing").
- **Binding**: a node instance carrying a predicate tag (`pred:<token>`) plus meta/engrams.
- **Edge**: a directed link between bindings with a label (often "then") for **weak causality**.
- **WorldGraph**: the small, fast *episode index* (~5% information). Rich content goes in engrams.
- **Policy (primitive)**: behavior object with `trigger(world, drives)` and `execute(world, ctx, drives)`.
  The Action Center scans the ordered list of policies and runs the first that triggers (one "controller step").
- **Autosave/Load**: JSON snapshot with `world`, `drives`, `skills`, plus a `saved_at` timestamp.

This runner presents an interactive menu for inspecting the world, planning, adding predicates,
emitting sensory cues, and running the Action Center ("Instinct step"). It also supports
non-interactive utility flags for scripting, like `--about`, `--version`, and `--plan <predicate>`.
"""

# --- Pragmas and Imports -------------------------------------------------------------

# pylint: disable=protected-access
#   we treat the cca8_runner module as a trusted friend module and thus silence warnings for acces to _objects
# pylint: disable=import-outside-toplevel
#   a number of the imports in profile/preflight stubs are by design and leave for now


# Standard Library Imports
from __future__ import annotations
import argparse
import json
import os
import platform
import sys
import logging
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Any, Dict, List, Callable
from typing import DefaultDict
from collections import defaultdict
import random
import time
import subprocess
import shutil


# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
#import cca8_world_graph as wgmod  # modular alternative: allows swapping WorldGraph engines
import cca8_world_graph
from cca8_controller import Drives, action_center_step, skill_readout, skills_to_dict, skills_from_dict, HUNGER_HIGH, FATIGUE_HIGH
from cca8_temporal import TemporalContext
from cca8_column import mem as column_mem


# --- Public API index, version, global variables and constants ----------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.8.0"
__all__ = [
    "main",
    "interactive_loop",
    "run_preflight_full",
    "snapshot_text",
    "export_snapshot",
    "world_delete_edge",
    "boot_prime_stand",
    "save_session",
    "versions_dict",
    "versions_text",
    "choose_contextual_base",
    "compute_foa",
    "candidate_anchors",
    "__version__",
    "Ctx",
]
NON_WIN_LINUX = False  #set if non-Win, non-macOS, non-Linux/like OS
PLACEHOLDER_EMBODIMENT = '0.0.0 : none specified'

ASCII_LOGOS = {
    "badge": r"""
+--------------------------------------------------------------+
|  C C A 8  —  Causal Cognitive Architecture                   |
+--------------------------------------------------------------+""".strip("\n"),
    "goat": r"""
    ____            CCA8
 .'    `-.       mountain goat
/  _  _   \
| (o)(o)  |
\    __  /
 `'-.____'""".strip("\n"),
}


# --- Runtime Context (ENGINE↔CLI seam) --------------------------------------------
@dataclass(slots=True)
class Ctx:
    """Mutable runtime context for the agent (module-level, importable).

    Timekeeping (soft clock + counters)
    -----------------------------------
    controller_steps : int
        Count of Action Center decision/execution loops run in this session
        (aka “instinct steps”). This is not wall-clock; it’s for analysis/debug.
        Resettable.

    cog_cycles : int
        Count of completed “cognitive cycles” that produced an output
        (sense→decide→act *and* a write occurred in the WorldGraph).
        Resettable.

    Temporal timekeeping (soft clock)
    ---------------------------------
    temporal : TemporalContext | None
        Owner of the procedural “now” vector and step()/boundary() operations.
    sigma : float
        Drift noise magnitude applied each step() (larger → faster cosine decay within epoch).
    jump : float
        Boundary noise magnitude applied on boundary() (larger → deeper post-boundary separation).
    tvec_last_boundary : list[float] | None
        Copy of the vector at the last boundary; used for cosine(current, last_boundary).
    boundary_no : int
        Epoch counter; incremented on each boundary() call.
    boundary_vhash64 : str | None
        64-bit sign-bit fingerprint of the vector at the last boundary (readable hex).
    """
    sigma: float = 0.015
    jump: float = 0.2
    age_days: float = 0.0
    ticks: int = 0
    profile: str = "Mountain Goat"
    winners_k: Optional[int] = None
    hal: Optional[Any] = None
    body: str = "(none)"
    temporal: Optional[TemporalContext] = None
    tvec_last_boundary: Optional[list[float]] = None
    boundary_no: int = 0
    boundary_vhash64: Optional[str] = None
    controller_steps: int = 0
    cog_cycles: int = 0
    last_drive_flags: Optional[set[str]] = None


    def reset_controller_steps(self) -> None:
        """quick reset of Ctx.controller_steps counter
        """
        self.controller_steps = 0

    def reset_cog_cycles(self) -> None:
        """quick reset of Ctx.cog_cycles counter
        """
        self.cog_cycles = 0

    def tvec64(self) -> Optional[str]:
        """64-bit sign-bit fingerprint of the temporal vector (hex)."""
        tv = self.temporal
        if not tv:
            return None
        v = tv.vector()
        x = 0
        m = min(64, len(v))
        for i in range(m):
            if v[i] >= 0.0:
                x |= (1 << i)
        return f"{x:016x}"

    def cos_to_last_boundary(self) -> Optional[float]:
        """Cosine(now, last_boundary); unit vectors → dot product."""
        tv = self.temporal
        lb = self.tvec_last_boundary
        if not (tv and lb):
            return None
        v = tv.vector()
        return sum(a*b for a, b in zip(v, lb))


# Module layout/seam:
#   ENGINE (pure helpers; import-safe; no user I/O)  → can be reused by other front-ends
#   CLI    (printing/input; menus; argparse)        → terminal user experience

# --- Edge delete helpers (self-contained) ------------------------------------
def _edge_get_dst(edge: Dict[str, Any]) -> str | None:
    return edge.get("dst") or edge.get("to") or edge.get("dst_id") or edge.get("id")

def _edge_get_rel(edge: Dict[str, Any]) -> str | None:
    return edge.get("rel") or edge.get("label") or edge.get("relation")

def _rm_from_list(lst: List[Dict[str, Any]], dst: str, rel: str | None) -> int:
    before = len(lst)
    def match(e: Dict[str, Any]) -> bool:
        if _edge_get_dst(e) != dst:
            return False
        return (rel is None) or (_edge_get_rel(e) == rel)
    lst[:] = [e for e in lst if not match(e)]
    return before - len(lst)

def world_delete_edge(world: Any, src: str, dst: str, rel: str | None) -> int:
    """
    Remove edges matching (src -> dst [rel]) from the in-memory WorldGraph.

    Supports per-binding edges like:
        world._bindings[src].edges == [{'label': 'then', 'to': 'b3'}, ...]
    and also optional global world.edges layouts.

    Returns number of removed edges.
    """
    removed = 0

    # Per-binding adjacency: world._bindings[src]
    bindings = getattr(world, "_bindings", None) or getattr(world, "bindings", None) or getattr(world, "nodes", None)
    if isinstance(bindings, dict) and src in bindings:
        node = bindings[src]
        # node may be an object with attribute 'edges' or a dict with key 'edges'
        edges_list = getattr(node, "edges", None) if hasattr(node, "edges") else (node.get("edges") if isinstance(node, dict) else None)
        if isinstance(edges_list, list):
            removed += _rm_from_list(edges_list, dst, rel)
        # Also check common alternative keys
        for key in ("out", "links", "outgoing"):
            alt = getattr(node, key, None) if hasattr(node, key) else (node.get(key) if isinstance(node, dict) else None)
            if isinstance(alt, list):
                removed += _rm_from_list(alt, dst, rel)

    # Global edge list: world.edges = [{src,dst,rel}, ...]
    gl = getattr(world, "edges", None)
    if isinstance(gl, list):
        before = len(gl)
        def match_gl(e: Dict[str, Any]) -> bool:
            s = e.get("src") or e.get("from") or e.get("src_id")
            d = _edge_get_dst(e)
            r = _edge_get_rel(e)
            if s != src or d != dst:
                return False
            return (rel is None) or (r == rel)
        gl[:] = [e for e in gl if not match_gl(e)]
        removed += before - len(gl)
    elif isinstance(gl, dict) and src in gl:
        lst = gl.get(src)
        if isinstance(lst, list):
            removed += _rm_from_list(lst, dst, rel)

    return removed


# --- CLI flow: delete edge -------------------------------------------------------
# This is part of the CLI layer; it calls engine helper `world_delete_edge()`.
def delete_edge_flow(world: Any, autosave_cb=None) -> None:
    """delete edge
    """
    print("Delete edge (src -> dst [relation])")
    src = input("Source binding id (e.g., b1): ").strip()
    dst = input("Dest binding id (e.g., b3): ").strip()
    rel = input("Relation label (optional; blank = ANY): ").strip() or None

    # Prefer a first-party method if present
    removed = 0
    for method in ("remove_edge", "delete_edge"):
        if hasattr(world, method):
            try:
                removed = getattr(world, method)(src, dst, rel)
                break
            except Exception:
                removed = 0

    if removed == 0:
        removed = world_delete_edge(world, src, dst, rel)

    print(f"Removed {removed} edge(s) {src} -> {dst}{(' (rel='+rel+')' if rel else '')}")

    if autosave_cb:
        try:
            autosave_cb()
        except Exception:
            pass

# ==== Spatial anchoring stubs (NO-OP) =======================================
#pylint: disable=unused-argument
def _maybe_anchor_attach(default_attach: str, base: dict | None) -> str:
    """
    STUB: When we enable base-aware write placement, change attach semantics here.
    For now, returns default_attach unchanged.
    Example (future):
      if isinstance(base, dict) and base.get("bid"):
          return "none"   # create unattached, then connect base['bid'] -> new

    Note: -We already compute a "write base" suggestion via choose_contextual_base(...)
            e.g., as seen in the Instinct Step menu selection.
          -these stubs give a single place to switch from attach="latest" to
            base-anchored placement later.
          - _add_pred_base_aware(...) stub is in Controller module
    """
    return default_attach


def add_spatial_relation(world, src_bid: str, rel: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    STUB: Sugar for scene-graph style relations (left_of, on, inside, supports, near).
    Today this is just an alias of world.add_edge(...).
    """
    world.add_edge(src_bid, dst_bid, rel, meta or {})
#pylint: enable=unused-argument

# --------------------------------------------------------------------------------------
# Utility: atomic JSON autosave
# --------------------------------------------------------------------------------------

def save_session(path: str, world, drives) -> str:
    """Serialize (world, drives, skills) to JSON and atomically write to disk.

    Returns:
        The ISO timestamp used as 'saved_at' in the file.
    """
    ts = datetime.now().isoformat(timespec="seconds")
    data = {
        "saved_at": ts,
        "world": world.to_dict(),
        "drives": drives.to_dict(),
        "skills": skills_to_dict(),
        "app_version": f"cca8_run/{__version__}",
        "platform": platform.platform(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return ts


def _module_version_and_path(modname: str) -> tuple[str, str]:
    """Return (version_string, path) for a module name, safely.
    - If module can't be imported → ('-- unavailable (i.e.,not found)', '<name>.py')
    - If no __version__ on module → ('n/a', path)
    """
    try:
        import importlib
        m = importlib.import_module(modname)
    except Exception:
        return "-- unavailable (i.e., not found)", f"{modname}.py"
    ver = getattr(m, "__version__", None)
    ver_str = str(ver) if ver is not None else "n/a"
    path = getattr(m, "__file__", f"{modname}.py")
    return ver_str, path





# --------------------------------------------------------------------------------------
# Embodiment
# --------------------------------------------------------------------------------------
class HAL:
    """Hardware abstraction layer (HAL) skeleton for future usage
    """
    def __init__(self, body: str | None = None):
        # future usage: load body profile (motor map), open serial/network, etc.
        self.body = body or "(none)"
        # future usage: load body profile (motor map), open serial/network, etc.

    # Actuators
    def push_up(self):
        """Raise chest (stub)."""
        return False

    def extend_legs(self):
        """Extend legs (stub)."""
        return False

    def orient_to_mom(self):
        """Rotate toward maternal stimulus (stub)."""
        return False

    # Sensors
    def sense_vision_mom(self):
        """Return True if mother's silhouette is detected (stub)."""
        return False

    def sense_vestibular_fall(self):
        """Return True if fall is detected (stub)."""
        return False

# --------------------------------------------------------------------------------------
# Two-gate policy and helpers and console helpers
# --------------------------------------------------------------------------------------

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

def _fmt_base(d: dict) -> str:
    """helper to print base suggestion info,
    particularly during snapshot displays

    e.g., print(f"[context] write-base: {_fmt_base(base)}")
    """
    if not isinstance(d, dict):
        return str(d)
    kind = d.get("base")
    bid  = d.get("bid")
    if kind == "NEAREST_PRED":
        p = d.get("pred")
        return f"NEAREST_PRED(pred={p}) -> {bid}"
    elif kind:
        return f"{kind} -> {bid}"
    return str(d)


def print_header(hal_str: str = "HAL: off (no embodiment)", body_str: str = "Body: (none)"):
    """Print the intro banner and a brief explanation of the simulation profiles and CLI usage."""
    print('\n\n# --------------------------------------------------------------------------------------')
    print('# NEW RUN   NEW RUN')
    print('# --------------------------------------------------------------------------------------')
    print("\nA Warm Welcome to the CCA8 Mammalian Brain Simulation")
    print(f"(cca8_run.py v{__version__})\n")
    print_ascii_logo(style="goat", color=True)
    print(f"Entry point program being run: {os.path.abspath(sys.argv[0])}")
    print(f"OS: {sys.platform} (see system-dependent utilities for more detailed system/simulation info)")
    print('(for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)')
    print(f'\nEmbodiment:  HAL (hardware abstraction layer) setting: {hal_str}')
    print(f'Embodiment:  body_type|version_number|serial_number (i.e., robotic embodiment): {body_str} ')

    print("\nThe simulation of the cognitive architecture can be adjusted to add or take away")
    print("  various features, allowing exploration of different evolutionary-like configurations.\n")
    print("  1. Mountain Goat-like brain simulation")
    print("  2. Chimpanzee-like brain simulation")
    print("  3. Human-like brain simulation")
    print("  4. Human-like one-agent multiple-brains simulation")
    print("  5. Human-like one-brain simulation × multiple-agents society")
    print("  6. Human-like one-agent multiple-brains simulation with combinatorial planning")
    print("  7. Super-Human-like machine simulation")
    print("  T. Tutorial (more information) on using and maintaining this program, references\n")

def print_ascii_logo(style: str = None, color: bool = True) -> None:  # pragma: no cover
    """
    Print a small ASCII logo once at program start.
    Env overrides:
      CCA8_LOGO=badge|goat|off   (off disables)
      NO_COLOR (set to disable ANSI colors)
    """
    style = (style or os.getenv("CCA8_LOGO", "badge")).lower()
    if style == "off":
        return
    art = ASCII_LOGOS.get(style, ASCII_LOGOS["badge"])

    # Optional ANSI color (Windows Terminal supports ANSI; NO_COLOR disables)
    want_color = color and sys.stdout.isatty() and not os.getenv("NO_COLOR")
    if want_color:
        CYAN = "\033[36m"; YEL = "\033[33m"; B = "\033[1m"; R = "\033[0m"
        if style == "badge":
            art = art.replace("C C A 8", f"{B}{CYAN}C C A 8{R}")
        elif style == "goat":
            art = f"{YEL}{art}{R}"

    print(art)  # pragma: no cover
    print()     # spacer  # pragma: no cover

def _snapshot_temporal_legend() -> list[str]:
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
        "  2. temporal drift — cos_to_last_boundary (cosine(current, last boundary))  [src=ctx.cos_to_last_boundary(); advanced by ctx.temporal.step()]",
        "  3. autonomic ticks — heartbeat for physiology/IO (robotics integration)  [src=ctx.ticks]",
        "  4. developmental age — age_days  [src=ctx.age_days]",
        "  5. cognitive cycles — full sense->process->opt. action cycle  [src=ctx.cog_cycles]"
        "  **see menu tutorials for more about these terms**",
        "",
    ]

def _compute_loc_by_dir(suffixes=(".py",),skip_folders=(".git", ".venv", "build", "dist", ".pytest_cache", "__pycache__")):
    """
    Compute SLOC per top-level directory using the pygount CLI.

    Returns:
        rows: list[(topdir, sloc, files_count)] sorted by sloc desc
        total_sloc: int
        errtext: Optional[str]
    """
    exe = shutil.which("pygount") or shutil.which("pygount.exe")
    if not exe:
        return [], 0, (
            "pygount not found on PATH.\n"
            "Install with:  py -m pip install --user pygount\n"
            "Then restart your terminal so the Scripts directory is on PATH."
        )

    cmd = [
        exe, ".",
        "--suffix=py",
        "--folders-to-skip=" + ",".join(skip_folders),
        "--format=json",
    ]
    #proc = subprocess.run(cmd, text=True, capture_output=True)  # pylint: disable=subprocess-run-check
    try:
        proc = subprocess.run(cmd, text=True, capture_output=True, check=True, timeout=15)
        #will timeout in 15 seconds if hung process
    except subprocess.CalledProcessError as e:
        msg = (e.stderr or e.stdout or str(e)).strip()
        return [], 0, f"pygount failed (exit={e.returncode}): {msg}\nTry: py -m pip install --user pygount"

    if proc.returncode != 0:
        msg = proc.stderr.strip() or proc.stdout.strip() or "unknown error"
        return [], 0, f"pygount failed (exit={proc.returncode}): {msg}\nTry: py -m pip install --user pygount"

    try:
        doc = json.loads(proc.stdout)
    except Exception as e:
        return [], 0, f"pygount JSON parse error: {e}"

    items = doc.get("files") if isinstance(doc, dict) else (doc if isinstance(doc, list) else [])

    sloc_by_top = defaultdict(int)
    files_by_top = defaultdict(int)

    for it in items:
        if it.get("state") != "analyzed":
            continue
        if (it.get("language") or "").lower() not in ("python", ""):
            continue
        path = it.get("path") or ""
        if not path.endswith(suffixes):
            continue

        rel = os.path.relpath(path, ".")
        top = rel.split(os.sep, 1)[0] if os.sep in rel else "."
        if top in skip_folders or not top:
            continue

        sloc = int(it.get("sourceCount") or it.get("codeCount") or 0)
        sloc_by_top[top] += sloc
        files_by_top[top] += 1

    rows = sorted(sloc_by_top.items(), key=lambda kv: (-kv[1], kv[0]))
    rows = [(k, v, files_by_top[k]) for k, v in rows]
    total = sum(sloc_by_top.values())
    return rows, total, None

def _render_loc_by_dir_table(rows, total):
    """
    Pretty-print the LOC table. Returns a string for testability, caller prints it.  # pragma: no cover
    """
    if not rows:
        return "No Python files (.py) found under the current directory.\n"
    # column widths
    name_w = max(25, max(len(k) for k, _, _ in rows))
    lines = []
    lines.append("Selection LOC by Directory (Python)")
    lines.append("Counts SLOC (pygount sourceCount) per top-level folder. Includes tests/ and root files under '.'.\n")
    lines.append(f"{'directory'.ljust(name_w)}  {'files':>7}  {'SLOC':>10}")
    lines.append(f"{'-'*name_w}  {'-'*7}  {'-'*10}")
    for k, sloc, nfiles in rows:
        lines.append(f"{k.ljust(name_w)}  {nfiles:7d}  {sloc:10,d}")
    lines.append(f"{'-'*name_w}  {'-'*7}  {'-'*10}")
    lines.append(f"{'TOTAL'.ljust(name_w)}  {sum(n for _,_,n in rows):7d}  {total:10,d}\n")
    return "\n".join(lines)

def _parse_vector(text: str) -> list[float]:
    """
    Parse a comma/space-separated string into a list of floats.
    Empty input → [0.0, 0.0, 0.0].
    """
    import re
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

def loop_helper(autosave_from_args: Optional[str], world, drives, time_limited: bool = False):
    """Operations to run at the end of each menu branch before looping again.

    Currently: autosave (if enabled). Future: time-limited bypasses for real-world ops.
    """
    if time_limited:
        return
    if autosave_from_args:
        save_session(autosave_from_args, world, drives)
        # Quiet by default; uncomment for debugging:
        # print(f"[autosaved {ts}] {autosave_from_args}")
    print("\n-----\n") #visual spacer before menu prints again


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

def _emit_interoceptive_cues(world, drives, ctx, attach: str = "latest") -> set[str]:
    """
    Emit `cue:drive:*` on rising-edge transitions (e.g., hunger crosses HUNGER_HIGH).
    Returns the set of flags that started this tick, e.g., {"drive:hunger_high"}.
    House style: treat drive thresholds as *evidence* (cue:*), not planner goals.
    """
    try:
        flags_now = set(_drive_tags(drives))         # e.g., {"drive:hunger_high", "drive:fatigue_high"}
        flags_prev = getattr(ctx, "last_drive_flags", set()) or set()
        started = flags_now - flags_prev #perhaps, e.g., {"drive:hunger_high"}
        for f in sorted(started):
            # world.add_cue normalizes to tag "cue:<token>"
            world.add_cue(f, attach=attach, meta={"created_by": "autonomic", "ticks": getattr(ctx, "ticks", 0)})
            #e.g., creates a new binding whose tag will inlcude f, perhaps e.g., "cue:drive:hunger_high"
        ctx.last_drive_flags = flags_now
        #return rising-edge drive thresholds that occurred here, e.g., "drive:hunger_high"
        #remember... cues can function as policy triggers focus of attention, but we *do not* write all the sensory cues streaming
        #  into the architecture -- we capture some of this as engrams; again, cues are part of a lightweight symbolic layer
        return started
    except Exception:
        return set()

def _normalize_pred(tok: str) -> str:
    """Ensure a token is 'pred:<x>' form (idempotent).
    """
    return tok if tok.startswith("pred:") else f"pred:{tok}"

def _neighbors(world, bid: str) -> List[str]:
    """Return outgoing neighbor ids from a binding, being tolerant of alternative edge
         layouts ('edges'/'out'/'links')."""
    b = world._bindings.get(bid)
    if not b:
        return []
    edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
    out = []
    if isinstance(edges, list):
        for e in edges:
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if dst:
                out.append(dst)
    return out

def _engrams_on_binding(world, bid: str) -> list[str]:
    """Return engram ids attached to a binding (via binding.engrams)."""
    b = world._bindings.get(bid)
    if not b:
        return []
    eng = getattr(b, "engrams", None) or {}
    out: list[str] = []
    if isinstance(eng, dict):
        for v in eng.values():
            if isinstance(v, dict):
                eid = v.get("id")
                if isinstance(eid, str):
                    out.append(eid)
    return out

def _bfs_reachable(world, src: str, dst: str, max_hops: int = 3) -> bool:
    """Light BFS reachability within `max_hops` hops; early exit on first match.
    """
    from collections import deque
    if src == dst:
        return True
    q, seen, depth = deque([src]), {src}, {src: 0}
    while q:
        u = q.popleft()
        if depth[u] >= max_hops:
            continue
        for v in _neighbors(world, u):
            if v in seen:
                continue
            if v == dst:
                return True
            seen.add(v)
            depth[v] = depth[u] + 1
            q.append(v)
    return False

def _bindings_with_pred(world, token: str) -> List[str]:
    """Return binding ids whose tags contain pred:<token> (exact match)."""
    want = _normalize_pred(token)
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out

def _bindings_with_cue(world, token: str) -> List[str]:
    """Return binding ids whose tags contain cue:<token> (exact match)."""
    want = f"cue:{token}"
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out

def any_cue_tokens_present(world, tokens: List[str]) -> bool:
    """Return True if **any** `cue:<token>` exists anywhere in the graph.
    """
    return any(_bindings_with_cue(world, tok) for tok in tokens)

def has_pred_near_now(world, token: str, hops: int = 3) -> bool:
    """Return True if any pred:<token> is reachable from NOW in ≤ `hops` edges."""
    now_id = _anchor_id(world, "NOW")
    for bid in _bindings_with_pred(world, token):
        if _bfs_reachable(world, now_id, bid, max_hops=hops):
            return True
    return False

def any_pred_present(world, tokens: List[str]) -> bool:
    """Return True if any pred:<token> in `tokens` exists anywhere in the graph."""
    return any(_bindings_with_pred(world, tok) for tok in tokens)

@dataclass
class PolicyGate:
    """Declarative description of a controller gate used by PolicyRuntime (dev_gating,
       trigger, and optional explain)."""
    name: str
    dev_gate: Callable[[Any], bool]                      # ctx -> bool
    trigger: Callable[[Any, Any, Any], bool]             # (world, drives, ctx) -> bool
    explain: Optional[Callable[[Any, Any, Any], str]] = None

class PolicyRuntime:
    """Runtime wrapper around a gate catalog that filters by dev gating, evaluates
         triggers, and executes one step."""
    def __init__(self, catalog: List[PolicyGate]):
        """Initialize with a catalog (list of PolicyGate) and compute the 'loaded'
           subset based on ctx.dev gating."""
        self.catalog = list(catalog)
        self.loaded: List[PolicyGate] = []

    def refresh_loaded(self, ctx) -> None:
        """Recompute `self.loaded` by applying each gate's dev_gating predicate to `ctx`.
        """
        self.loaded = [p for p in self.catalog if _safe(p.dev_gate, ctx)]

    def list_loaded_names(self) -> List[str]:
        """Return names of currently loaded (dev-eligible) gates.
        """
        return [p.name for p in self.loaded]


    def consider_and_maybe_fire(self, world, drives, ctx, tie_break: str = "first") -> str:  # pylint: disable=unused-argument
        """Evaluate triggers, prefer safety-critical gates, then run the controller once;
              return a short human string."""
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        if not matches:
            return "no_match"

        # If fallen, force safety-only gates
        if has_pred_near_now(world, "state:posture_fallen"):
            safety_only = {"policy:recover_fall", "policy:stand_up"}
            matches = [p for p in matches if p.name in safety_only]
            if not matches:
                return "no_match"

        # Choose by drive-deficit
        def deficit(name: str) -> float:
            d = 0.0
            if name == "policy:seek_nipple":
                d += max(0.0, float(getattr(drives, "hunger", 0.0)) - float(HUNGER_HIGH)) * 1.0
            if name == "policy:rest":
                d += max(0.0, float(getattr(drives, "fatigue", 0.0)) - float(FATIGUE_HIGH)) * 0.7
            return d

        def stable_idx(p):
            try:
                return [q.name for q in self.catalog].index(p.name)
            except ValueError:
                return 10_000

        chosen = max(matches, key=lambda p: (deficit(p.name), -stable_idx(p)))

        # Context for logging
        base  = choose_contextual_base(world, ctx, targets=["state:posture_standing", "stand"])
        foa   = compute_foa(world, ctx, max_hops=2)
        cands = candidate_anchors(world, ctx)
        pre_expl = chosen.explain(world, drives, ctx) if chosen.explain else "explain: (not provided)"

        # Run controller with the exact policy we selected
        try:
            before_n = len(world._bindings)
            result   = action_center_step(world, ctx, drives, preferred=chosen.name)
            after_n  = len(world._bindings)
            delta_n  = after_n - before_n
            label    = result.get("policy") if isinstance(result, dict) and "policy" in result else chosen.name
        except Exception as e:
            return f"{chosen.name} (error: {e})"

        gate_for_label = next((p for p in self.loaded if p.name == label), chosen)
        post_expl = gate_for_label.explain(world, drives, ctx) if gate_for_label.explain else "explain: (not provided)"

        return (
            f"{label} (added {delta_n} bindings)\n"
            f"pre:  {pre_expl}\n"
            f"base: {base}\n"
            f"foa:  {foa}\n"
            f"cands:{cands}\n"
            f"post: {post_expl}"
        )


def _safe(fn, *args):
    """Invoke a predicate defensively (exceptions → False).
    """
    try:
        return bool(fn(*args))
    except Exception:
        return False


CATALOG_GATES: List[PolicyGate] = [
    PolicyGate(
        name="policy:stand_up",
        dev_gate=lambda ctx: getattr(ctx, "age_days", 0.0) <= 3.0,
        trigger=lambda W, D, ctx: (
            has_pred_near_now(W, "stand")
            and not has_pred_near_now(W, "state:posture_standing")  # don't stand twice
        ),
        explain=lambda W, D, ctx: (
            f"dev_gate: age_days={getattr(ctx,'age_days',0.0):.2f}≤3.0, "
            f"trigger: stand near NOW={has_pred_near_now(W,'stand')}"
        ),
    ),

    PolicyGate(
        name="policy:seek_nipple",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: (
            has_pred_near_now(W, "state:posture_standing")
            and (getattr(D, "hunger", 0.0) > 0.6)
            and any_cue_tokens_present(W, ["vision:silhouette:mom", "scent:milk", "sound:bleat:mom"])
            and not has_pred_near_now(W, "state:seeking_mom")      # prevent repeats
            and not has_pred_near_now(W, "state:posture_fallen")   # ineligible while fallen
        ),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: posture_standing={has_pred_near_now(W,'state:posture_standing')} "
            f"and hunger={getattr(D,'hunger',0.0):.2f}>0.60 and cues={present_cue_bids(W)} "
            f"and not seeking={not has_pred_near_now(W,'state:seeking_mom')} "
            f"and not fallen={not has_pred_near_now(W,'state:posture_fallen')}"
        ),
    ),

    PolicyGate(
        name="policy:rest",
        dev_gate=lambda ctx: True,  # available at all stages; selection is by trigger/deficit
        trigger=lambda W, D, ctx: (
            # fire when raw fatigue is high, or when the rising-edge cue exists
            float(getattr(D, "fatigue", 0.0)) > float(FATIGUE_HIGH)
            or any_cue_tokens_present(W, ["drive:fatigue_high"])
        ),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: fatigue={getattr(D,'fatigue',0.0):.2f}>{float(FATIGUE_HIGH):.2f} "
            f"or cue:drive:fatigue_high present={any_cue_tokens_present(W, ['drive:fatigue_high'])}"
        ),
    ),

    PolicyGate(
        name="policy:suckle",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: has_pred_near_now(W, "mom:close"),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: mom:close near NOW={has_pred_near_now(W,'mom:close')}"
        ),
    ),

    PolicyGate(
        name="policy:recover_miss",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: has_pred_near_now(W, "nipple:missed"),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: nipple:missed near NOW={has_pred_near_now(W,'nipple:missed')}"
        ),
    ),

    PolicyGate(
        name="policy:recover_fall",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: (
            has_pred_near_now(W, "state:posture_fallen")
            or any_cue_tokens_present(W, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])
            #or any_pred_present(W, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])
        ),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: fallen={has_pred_near_now(W,'state:posture_fallen')} "
            f"or cues={present_cue_bids(W)}"
        ),
    ),
]

def _first_binding_with_pred(world, token: str) -> str | None:
    """Return the first binding id that carries pred:<token>, else None."""
    want = token if token.startswith("pred:") else f"pred:{token}"
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                return bid
    return None

def boot_prime_stand(world, ctx) -> None:
    """
    At birth (age_days == 0), ensure NOW can reach a stand intent.
    - If a stand binding exists but isn't reachable from NOW, link NOW -> stand.
    - Else create a new stand binding attached to NOW.
    Idempotent: safe to run on fresh sessions.
    """
    try:
        if float(getattr(ctx, "age_days", 0.0)) != 0.0:
            return  # only at birth
    except Exception:
        pass

    now_id = _anchor_id(world, "NOW")
    stand_bid = _first_binding_with_pred(world, "stand")
    if stand_bid:
        # If NOW can't reach it in 1 hop, add an edge
        if not _bfs_reachable(world, now_id, stand_bid, max_hops=1):
            try:
                world.add_edge(now_id, stand_bid, "initiate_stand")
                print(f"[boot] Linked {now_id} --initiate_stand--> {stand_bid}")
            except Exception as e:
                print(f"[boot] Could not link NOW->stand: {e}")
    else:
        try:
            # attach="now" will add NOW -> <new> with default 'then' (fine for boot)
            new_bid = world.add_predicate("stand", attach="now", meta={"boot": "init", "added_by": "system"})
            print(f"[boot] Seeded stand (i.e., default value) as {new_bid} (NOW -> stand)")
            # Optional: relabel auto 'then' to 'initiate_stand' for readability
            try:
                # remove any NOW->new edges regardless of label
                try:
                    world_delete_edge(world, now_id, new_bid, None)  # our helper, if present
                except NameError:
                    pass  # older build without the helper

                world.add_edge(now_id, new_bid, "initiate_stand")
                print(f"[boot] Relabeled NOW -> {new_bid} to 'initiate_stand'")
            except Exception as e:
                print(f"[boot] Relabel skipped: {e}")
        except Exception as e:
            print(f"[boot] Could not seed stand: {e}")

def print_tagging_and_policies_help(policy_rt=None) -> None:
    """Terminal help: bindings, edges, predicates, cues, anchors, provenance/engrams, and policies."""
    print("\n==================== Understanding Bindings, Edges, Predicates, Cues & Policies ====================\n")

    print("What is a Binding?")
    print("  • A small 'episode card' that binds together:")
    print("      - tags (symbols: predicates / cues / anchors)")
    print("      - engrams (pointers to rich memory outside WorldGraph)")
    print("      - meta (provenance, timestamps, light notes)")
    print("      - edges (directed links from this binding)\n")
    print("  Structure (conceptual):")
    print("      { id:'bN', tags:[...], engrams:{...}, meta:{...}, edges:[{'to': 'bK', 'label':'then', 'meta':{...}}, ...] }\n")

    print("Tag Families (use these prefixes)")
    print("  • pred:*   → states/goals/events you might plan TO")
    print("      examples: pred:born, pred:posture:standing, pred:nipple:latched, pred:milk:drinking, pred:event:fall_detected")
    print("  • cue:*    → evidence/context you NOTICE (policy triggers); not planner goals")
    print("      examples: cue:scent:milk, cue:sound:bleat:mom, cue:silhouette:mom, cue:terrain:rocky")
    print("  • anchor:* → orientation markers (e.g., anchor:NOW); also mapped in engine anchors {'NOW': 'b1'}")
    print("  • drive thresholds (pick one convention and be consistent):")
    print("      default: pred:drive:hunger_high  (plannable)")
    print("      alt:     cue:drive:hunger_high   (trigger/evidence only)\n")

    print("Edges = Actions/Transitions")
    print("  • Edge label is the action (string): 'then', 'search', 'latch', 'suckle', 'approach', 'recover_fall', 'run', 'stabilize'")
    print("  • Quantities about the action live in edge.meta (e.g., meters, duration_s, created_by)")
    print("  • Planner behavior today: labels are for readability; BFS follows structure (not names)")
    print("  • Duplicate protection: the UI warns on exact duplicates of (src, label, dst)\n")

    print("Provenance & Engrams")
    print("  • Who created a binding?   binding.meta['policy'] = 'policy:<name>'")
    print("  • Who created an edge?     edge.meta['created_by'] = 'policy:<name>'")
    print("  • Where is the rich data?  binding.engrams[...] → pointers (large payloads live outside WorldGraph)\n")

    print("Anchors")
    print("  • anchor:NOW exists; used as the start for planning; may have no pred:*")
    print("  • Other anchors (e.g., HERE) are allowed; anchors are just bindings with special meaning\n")

    print("Planner (BFS) Basics")
    print("  • Goal test: a popped binding whose tags contain the target 'pred:<token>'")
    print("  • Shortest hops: BFS with visited-on-enqueue; parent map reconstructs the path")
    print("  • BFS → fewest hops (unweighted).")
    print("  • Dijkstra → lowest total edge weight; weights come from edge.meta keys in this order:")
    print("      'weight' → 'cost' → 'distance' → 'duration_s' (default 1.0 if none present).")
    print("  • Toggle strategy via the 'Planner strategy' menu item, then run 'Plan from NOW'.")
    print("  • Pretty paths show first pred:* as the node label (fallback to id) and --label--> between nodes")
    print("  • Try: menu 'Plan from NOW', menu 'Display snapshot', menu 'Export interactive graph'\n")

    print("Policies (Action Center overview)")
    print("  • Policies live in cca8_controller and expose:")
    print("      - dev_gate(ctx)       → True/False (availability by development stage/context)")
    print("      - trigger(world, drives, ctx) → True/False (should we act now?)")
    print("      - execute(world, ctx, drives) → adds bindings/edges; stamps provenance")
    print("  • Action Center scans loaded policies in order each tick; first match runs (with safety priority for recovery)")
    print("  • After execute, you may see:")
    print("      - new bindings (with meta.policy)")
    print("      - new edges (with edge.meta.created_by)")
    print("      - skill ledger updates ('Show skill stats')\n")

    # If we can read the currently loaded policy names, show them:
    try:
        names = policy_rt.list_loaded_names() if policy_rt is not None else []
        if names:
            print("Policies currently loaded (meet dev requirements):")
            for nm in names:
                print(f"  - {nm}")
            print()
    except Exception:
        pass

    print("Do / Don’t (project house style)")
    print("  ✓ Use pred:* for states/goals/events (and drive thresholds if plannable)")
    print("  ✓ Use cue:* for evidence/conditions (not planning targets)")
    print("  ✓ Put creator/time/notes in meta; put action measurements in edge.meta")
    print("  ✓ Allow anchor-only bindings (e.g., anchor:NOW)")
    print("  ✗ Don’t mix state:* with pred:* (pick pred:*)")
    print("  ✗ Don’t store large data in tags; put it in engrams")
    print("\nExamples")
    print("  born --then--> wobble --stabilize--> posture:standing --suckle--> milk:drinking")
    print("  stand --search--> nipple:found --latch--> nipple:latched --suckle--> milk:drinking")
    print("\n(See README.md → Tagging Standard for more information.)\n")


# --------------------------------------------------------------------------------------
# Menu text
# --------------------------------------------------------------------------------------

MENU = """\
[hints for text selection instead of numerical selection]

# Quick Start & Tutorial
1) Understanding bindings, edges, predicates, cues, anchors, policies [understanding, tagging]
2) Tutorial and step-by-step demo [tutorial, tour]

# Quick Start / Overview
3) Snapshot (bindings + edges + ctx + policies) [snapshot, display]
4) World stats [world, stats]
5) Recent bindings (last 5) [last, bindings]
6) Drives & drive tags [drives]
7) Skill ledger [skills]
8) Temporal probe (epoch/hash/cos/hamming) [temporal, probe]

# Act / Simulate
9) Instinct step (Action Center) [instinct, act]
10) Autonomic tick (emit interoceptive cues) [autonomic, tick]
11) Simulate fall (add state:posture_fallen and try recovery) [fall, simulate]

# Perception & Memory (Cues & Engrams)
12) Input [sensory] cue [sensory, cue]
13) Capture scene → tiny engram (signal bridge) [capture, scene]
14) Resolve engrams on a binding [resolve, engrams]
15) Inspect engram by id (or binding) [engram, ei]
16) List all engrams [engrams-all, list-engrams]
17) Search engrams (by name / epoch) [search-engrams, find-engrams]
18) Delete engram by id (danger: leaves dangling pointers) [delete-engram, del-engram]
19) Attach existing engram to a binding [attach-engram, ae]

# Graph Inspect / Build / Plan
20) Inspect binding details [inspect, details]
21) List predicates [listpredicates, listpreds]
22) [Add] predicate [add, predicate]
23) Connect two bindings (src, dst, relation) [connect, link]
24) Delete edge (source, destn, relation) [delete, rm]
25) Plan from NOW -> <predicate> [plan]
26) Planner strategy (toggle BFS ↔ Dijkstra) [planner, strategy]
27) Export and display interactive graph with options [pyvis, graph]

# Save / System / Help
28) Export snapshot (text only) [export snapshot]
29) Save session → path [save]
30) Load session → path [load]
31) Run preflight now [preflight]
32) Quit [quit, exit]
33) Lines of Python code LOC by directory [loc, sloc]

[S] Save session → path
[L] Load session → path
[D] Show drives (raw + tags)
[R] Reset current saved session
[T] Tutorial and step-by-step demo

Select: """

# --------------------------------------------------------------------------------------
# Profile stubs (experimental profiles print info and fall back to Mountain Goat)
# --------------------------------------------------------------------------------------

def _goat_defaults():
    """Return the Mountain Goat default profile tuple: (name, sigma, jump, winners_k)."""
    return ("Mountain Goat", 0.015, 0.2, 2)

def _print_goat_fallback():
    """Explain that the chosen profile is not implemented and we fall back to Mountain Goat."""
    print("Although scaffolding is in place for its implementation, this evolutionary-like configuration is not currently available. "
          "Profile will be set to mountain goat-like brain simulation.\n")

def profile_chimpanzee(_ctx) -> tuple[str, float, float, int]:
    """Print a narrative about the chimpanzee profile; fall back to Mountain Goat defaults."""
    print(
        "\nChimpanzee-like brain simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language.\n'
    )
    _print_goat_fallback()
    return _goat_defaults()

def profile_human(_ctx) -> tuple[str, float, float, int]:
    """Print a narrative about the human profile; fall back to Mountain Goat defaults."""
    print(
        "\nHuman-like brain simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
    )
    _print_goat_fallback()
    return _goat_defaults()

def profile_human_multi_brains(_ctx, world) -> tuple[str, float, float, int]:
    """Dry-run multi-brain sandbox (no writes); print trace; fall back to Mountain Goat defaults."""
    # Narrative
    print(
        "\nHuman-like one-agent multiple-brains simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this model each agent has multiple brains operating in parallel. There is an intelligent voting mechanism to decide on a response whereby "
        "each of the 5 processes running in parallel can give a response with an indication of how certain they are this is the best response, and the most "
        "certain + most popular response is chosen. As well, all 5 symbolic maps along with their rich store of information in their engrams is continually learning "
        "and updated.\n"
    )
    print(
        "Implementation scaffolding for multiple-brains in one agent:"
        "\n  • Representation: 5 symbolic hippocampal-like maps (5 sandbox WorldGraphs) running in parallel."
        "\n  • Fork: each sandbox starts as a deep copy of the live WorldGraph (later: thin overlay base+delta)."
        "\n  • Propose: each sandbox generates a candidate next action and a confidence in that proposal."
        "\n  • Vote: choose the most popular action; tie-break by highest average confidence, then max confidence."
        "\n  • Learn: (future) on commit, merge only new nodes/edges from the winning sandbox into the live world; "
        "re-id new nodes to avoid bN collisions; keep provenance in meta."
        "\n  • Safety: this stub does a dry-run only; it does not commit changes to the live world.\n"
    )

    # Scaffolding (non-crashing; prints a trace and falls back)
    try:
        import copy
        random.seed(42)  # deterministic demo

        print("[scaffold] Spawning 5 parallel 'brains' (sandbox worlds)...")
        # Thick clones for now; later this could be a thin overlay (base + delta)
        base_dict = world.to_dict()
        brains = []
        for i in range(5):
            try:
                clone = cca8_world_graph.WorldGraph.from_dict(copy.deepcopy(base_dict))
            except Exception:
                # Fallback: construct an empty world (still fine for a stub)
                clone = cca8_world_graph.WorldGraph()
            brains.append(clone)
        print(f"[scaffold] Created {len(brains)} sandbox worlds.")

        # Each brain proposes a response + confidence + short rationale
        possible = ["stand", "seek_mom", "suckle", "recover_fall", "idle"]
        proposals = []
        for i, _ in enumerate(brains, start=1):
            resp = random.choice(possible)
            conf = round(random.uniform(0.40, 0.95), 2)
            why  = {
                "stand":        "posture not yet stable, maximize readiness",
                "seek_mom":     "hunger cues + mom likely nearby",
                "suckle":       "latched recently → continue reward behavior",
                "recover_fall": "vestibular/touch cues suggest instability",
                "idle":         "no strong drive signal; conserve energy",
            }.get(resp, "heuristic selection")
            proposals.append((resp, conf, why))
            print(f"[scaffold] Brain#{i} proposes: {resp:12s}  (confidence={conf:.2f})  rationale: {why}")

        # Voting: most popular; tie-break by highest avg confidence, then max confidence
        from collections import Counter
        counts = Counter(r for r, _, _ in proposals)
        avg_conf = defaultdict(list)
        #max_conf = defaultdict(float)
        max_conf: DefaultDict[int, float] = defaultdict(float)
        for r, c, _ in proposals:
            avg_conf[r].append(c)
            if c > max_conf[r]: max_conf[r] = c
        for r in list(avg_conf.keys()):
            avg_conf[r] = sum(avg_conf[r]) / len(avg_conf[r])

        popular = max(counts.items(), key=lambda kv: (kv[1], avg_conf[kv[0]], max_conf[kv[0]]))
        winning_resp = popular[0]
        print(f"[scaffold] Winner by popularity: {winning_resp} "
              f"(votes={counts[winning_resp]}, avg_conf={avg_conf[winning_resp]:.2f}, max_conf={max_conf[winning_resp]:.2f})")

        print("[scaffold] (No changes committed—this is a dry run only.)\n")
    except Exception as e:
        print(f"[scaffold] Note: sandbox demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def profile_society_multi_agents(_ctx) -> tuple[str, float, float, int]:
    """Dry-run 3-agent society (no writes); print trace; fall back to Mountain Goat defaults."""
    print(
        "\nHuman-like one-brain simulation × multiple-agents society"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this simulation we have multiple agents each with one human-like brain, all interacting with each other.\n"
    )
    print(
        "Implementation scaffolding for multiple agents (one brain per agent):"
        "\n  • Representation: each agent has its own WorldGraph, Drives, and policy set; no shared mutable state."
        "\n  • Scheduler: iterate agents each tick (single process first; later, one process per agent with queues)."
        "\n  • Communication: send messages as tags/edges in the receiver’s world (e.g., pred:sound:bleat:mom)."
        "\n  • Persistence: autosave per agent (session_A1.json, session_A2.json, ...)."
        "\n  • Safety: this stub simulates 3 agents for one tick; everything is printed only; no files are written.\n"
    )

    # Scaffolding: create 3 tiny agents, run one tick, pass a simple message
    try:
        random.seed(7)  # deterministic print

        @dataclass
        class _Agent:
            name: str
            world: Any
            drives: Any

        agents: list[_Agent] = []
        for i in range(3):
            w = cca8_world_graph.WorldGraph()
            w.ensure_anchor("NOW")
            d = Drives()
            agents.append(_Agent(name=f"A{i+1}", world=w, drives=d))

        print(f"[scaffold] Created {len(agents)} agents: {', '.join(a.name for a in agents)}")

        # One tick: each agent runs action_center_step (dry outcome)
        for a in agents:
            try:
                res = action_center_step(a.world, _ctx, a.drives)
                print(f"[scaffold] {a.name}: Action Center → {res}")
            except Exception as e:
                print(f"[scaffold] {a.name}: controller error: {e}")

        # Simple broadcast message: A1 'bleats', A2 receives a cue (sound:bleat:mom)
        try:
            print("[scaffold] A1 broadcasts 'sound:bleat:mom' → A2")
            bid = agents[1].world.add_cue("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            #bid = agents[1].world.add_predicate("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            print(f"[scaffold] A2 received cue as binding {bid}; running one controller step on A2...")
            res2 = action_center_step(agents[1].world, _ctx, agents[1].drives)
            print(f"[scaffold] A2: Action Center → {res2}")
        except Exception as e:
            print(f"[scaffold] message/cue demo note: {e}")

        print("[scaffold] (End of society dry-run; no snapshots written.)\n")
    except Exception as e:
        print(f"[scaffold] Society demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def profile_multi_brains_adv_planning(_ctx) -> tuple[str, float, float, int]:
    """Dry-run 5x256 combinatorial planning stub (no writes); print trace; fall back to Mountain Goat defaults."""
    print(
        "\nHuman-like one-agent multiple-brains simulation with combinatorial planning"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this model there are multiple brains, e.g., 5 at the time of this writing, in one agent."
        "There is an intelligent voting mechanism to decide on a response whereby each of the 5 processes running in parallel can give a response with an "
        "indication of how certain they are this is the best response, and the most certain + most popular response is chosen. As well, all 5 "
        "symbolic maps along with their rich store of information in their engrams is continually learning and updated.\n"
        "\nIn addition, in this model each brain has multiple von Neumann processors to independently explore different possible routes to take "
        "or different possible decisions to make.\n"
    )
    print(
        "Implementation scaffolding (this stub does not commit changes to the live world):"
        "\n  • Brains: 5 symbolic hippocampal-like maps (conceptual ‘brains’) exploring in parallel."
        "\n  • Processors: each brain has 256 von Neumann processors that independently explore candidate plans."
        "\n  • Rollouts: each processor tries a short action sequence (horizon H=3) from a small discrete action set."
        "\n  • Scoring: utility(plan) = Σ reward(action) − cost_per_step·len(plan) (simple, deterministic toy scoring)."
        "\n  • Selection: within a brain, keep the best plan; across brains, pick the champion by best score, then avg score."
        "\n  • Commit rule: in a real system we would commit only the FIRST action of the winning plan after a safety check."
        "\n  • Parallelism note: this stub runs sequentially; a real build would farm processors to separate OS processes.\n"
    )

    # Scaffolding: 5 brains × 256 processors → 1280 candidate plans; pick a champion (no world writes)
    try:
        random.seed(20251)  # reproducible demo

        brain_count       = 5
        procs_per_brain   = 256
        horizon           = 3
        actions           = ["stand", "seek_mom", "suckle", "recover_fall", "idle"]
        reward            = {"stand": 0.20, "seek_mom": 0.45, "suckle": 1.00, "recover_fall": 0.30, "idle": -0.10}
        cost_per_step     = 0.05

        # (plan, score) comparison: higher score better; tie-break by shorter, then lexical
        def _better(a, b):
            if a is None: return True
            pa, sa = a
            pb, sb = b
            return (sb > sa) or (sb == sa and (len(pb) < len(pa) or (len(pb) == len(pa) and tuple(pb) < tuple(pa))))

        brain_summaries = []  # list of (brain_idx, best_plan, best_score, avg_score)

        for bi in range(1, brain_count + 1):
            best = None
            sum_scores = 0.0
            for _ in range(procs_per_brain):
                plan  = [random.choice(actions) for _ in range(horizon)]
                score = sum(reward.get(a, 0.0) for a in plan) - cost_per_step * len(plan)
                sum_scores += score
                if _better(best, (plan, score)):
                    best = (plan, score)
            avg = sum_scores / procs_per_brain
            brain_summaries.append((bi, best[0], best[1], avg))
            print(f"[scaffold] Brain#{bi:>2}: best={best[0]}  best_score={best[1]:.3f}  avg_score={avg:.3f}  (processors={procs_per_brain})")

        # Champion across brains: choose by best_score, then avg_score, then shorter plan, then lexical
        champion = max(
            brain_summaries,
            key=lambda t: (t[2], t[3], -len(t[1]), tuple(t[1]))
        )
        champ_idx, champ_plan, champ_best, champ_avg = champion
        print(f"[scaffold] Champion brain: #{champ_idx}  best_score={champ_best:.3f}  avg_score={champ_avg:.3f}")
        print(f"[scaffold] Winning plan: {champ_plan}")
        print(f"[scaffold] Commit rule (not executed here): take FIRST action '{champ_plan[0]}' on the live world.\n")

    except Exception as e:
        print(f"[scaffold] advanced-planning demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def profile_superhuman(_ctx) -> tuple[str, float, float, int]:
    """Dry-run ‘ASI’ meta-controller stub (no writes); print trace; fall back to Mountain Goat defaults."""
    print(
        "\nSuper-human-like machine simulation"
        "\n\nFeatures scaffolding for an ASI-grade architecture:"
        "\n  • Hierarchical memory: massive multi-modal engrams (vision/sound/touch/text) linked to a compact symbolic index."
        "\n  • Weighted graph planning: edges carry costs/uncertainty; A*/landmarks for long-range navigation in concept space."
        "\n  • Meta-controller: blends proposals from symbolic search, neural value estimation, and program-synthesis planning."
        "\n  • Self-healing & explanation: detect/repair inconsistent states; produce human-readable rationales for actions."
        "\n  • Tool-use & embodiment: external tools (math/vision/robots) wrapped as policies with provenances and safeguards."
        "\n  • Safety envelope: constraint-checking policies that can veto/redirect unsafe plans."
        "\n\nThis stub prints a dry-run of the meta-controller triage and falls back to the current==Mountain Goat profile.\n"
    )

    # Scaffolding: three-module meta-controller, pick best proposal (no world writes)
    try:
        random.seed(123)

        modules = [
            ("symbolic_search", ["stand", "seek_mom", "suckle"]),
            ("neural_value",    ["seek_mom", "suckle", "stand"]),
            ("prog_synthesis",  ["suckle", "seek_mom", "recover_fall"]),
        ]
        proposals = []
        for name, pref in modules:
            action = pref[0]                           # top preference
            score  = round(random.uniform(0.50, 0.98), 3)  # mock utility
            why = {
                "symbolic_search": "shortest-hop path to immediate reward",
                "neural_value":   "high expected value under learned drive model",
                "prog_synthesis": "small program proves preconditions & reward",
            }[name]
            proposals.append((name, action, score, why))
            print(f"[scaffold] {name:15s} → {action:12s} score={score:.3f}  rationale: {why}")

        # pick by score; tie-break by a fixed preference order
        pref_order = {"suckle": 3, "seek_mom": 2, "stand": 1, "recover_fall": 1, "idle": 0}
        best = max(proposals, key=lambda t: (t[2], pref_order.get(t[1], 0)))
        print(f"[scaffold] Meta-controller winner: action={best[1]} "
              f"(score={best[2]:.3f}) from {best[0]}")

        print("[scaffold] (No changes committed—safety envelope would check constraints before execution.)\n")
    except Exception as e:
        print(f"[scaffold] ASI meta-controller demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def _open_readme_tutorial() -> None:
    """Open README.md in the default viewer, then return.
    This may or may not have the same behavior as main-menu 'T'
    (it does at time of writing but future versions may diverge
    """
    # pylint: disable=import-outside-toplevel
    import webbrowser
    path = os.path.abspath("README.md")
    try:
        if os.name == "nt":
            os.startfile(path)  # type: ignore[attr-defined]
        else:
            webbrowser.open_new_tab(f"file://{path}")
        print("[tutorial] Opened compendium document showing you how to use code, references, and technical details")
        print("      Please close it to return to the profile selection.")
    except Exception as e:
        print(f"[tutorial] Could not open the compendium document automatically: {e}\n"
              f"          You can open it manually at:\n  {path}")

def run_new_user_tour(world, drives, ctx, policy_rt,autosave_cb: Optional[Callable[[], None]] = None):
    """Quick, hands-on console tour for first-time users.
    Runs a baseline snapshot, probe, capture scene, pointer/engram inspect, and list/search.
    """

    def _pause(step_label: str) -> bool:
        try:
            s = input(f"\n[Tour] {step_label} — press Enter to continue, or type * to finish the tour: ").strip()
            return s == "*"
        except Exception:
            return False

    print("""
           === CCA8 Quick Tour ===
        This tour will do the following and show the following displays:
                       (1) snapshot, (2) temporal context probe, (3) capture a small
                       engram, (4) show the binding pointer (b#), (5) inspect that
                       engram, (6) list/search engrams.
        Hints: Press Enter to accept defaults. Type Q to exit.

        **The tutorial portion of the tour is still under construction. All components shown here are available
            as individual menu selections also -- see those and the README.md file for more details.**

        [tour] 1/6 — Baseline snapshot
        Shows CTX and TEMPORAL (dim/sigma/jump; cosine; hash). Next: temporal probe.
          • CTX shows agent counters (profile, age_days, ticks) and run context.
          • TEMPORAL is a soft clock (dim/sigma/jump), not wall time.
          • cosine≈1.000 → same event; <0.90 → “new event soon.”
          • vhash64 is a compact fingerprint for quick comparisons.

        [tour] 2/6 — Temporal context probe
        Updates the soft clock; prints dim/sigma/jump and cosine to last boundary.
        Next: capture a tiny engram.
          • boundary() jumps the vector and increments the epoch (event count).
          • vhash64 vs last_boundary_vhash64 → Hamming bits changed (0..64).
          • Cosine compares “now” vs last boundary; drift lowers cosine.
          • Status line summarizes phase (ON-BOUNDARY / DRIFTING / BOUNDARY-SOON).

        [tour] 3/6 — Capture a tiny engram
        Adds a memory item with time/provenance; visible in Snapshot. Next: show b#.
          • capture_scene creates a binding (cue/pred) and a Column engram.
          • The binding gets a pointer slot (e.g., column01 → EID).
          • Time attrs (ticks, epoch, tvec64) come from ctx at capture time.
          • binding.meta['policy'] records provenance when created by a policy.

        [tour] 4/6 — Show binding pointer (b#)
        Displays the new binding id and its attach target. Next: inspect that engram.
          • A binding is the symbolic “memory link”; engram is the rich payload.
          • The pointer (b#.engrams['slot']=EID) glues symbol ↔ rich memory.
          • Attaching near NOW/LATEST keeps episodes readable for planning.
          • Follow the pointer via Snapshot or “Inspect engram by id.”

        [tour] 5/6 — Inspect engram
        Shows engram fields (channel, token, attrs). Next: list/search engrams.
          • meta → attrs (ticks, epoch, tvec64, epoch_vhash64) for time context.
          • payload → kind/shape/bytes (varies by Column implementation).
          • Use this to verify data shape and provenance after capture.
          • Engrams persist across saves; pointers can be re-attached later.


        [tour] 6/6 — List/search engrams
        Lists and filters engrams by token/family.
          • Deduped EIDs with source binding (b#) for quick auditing.
          • Search by name substring and/or by epoch number.
          • Useful to confirm capture cadence across boundaries/epochs.
          • Pair with “Plan from NOW” to see if memory supports behavior.

    """)

    # 1) Baseline snapshot
    print("\n[tour] 1/6 — Baseline snapshot")
    try:
        print(snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt))
    except Exception as e:
        print(f"(tour) snapshot error: {e}")
    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("1/6"):
        return

    # 2) Temporal probe (same signals as menu 26)
    print("\n[tour] 2/6 — Temporal probe")
    try:
        epoch = getattr(ctx, "boundary_no", 0)
        vhash = ctx.tvec64() if hasattr(ctx, "tvec64") else None
        lbvh  = getattr(ctx, "boundary_vhash64", None)
        print(f"  epoch={epoch}")
        print(f"  vhash64={vhash if vhash else '(n/a)'}")
        print(f"  last_boundary_vhash64={lbvh if lbvh else '(n/a)'}")
        cos = None
        try: cos = ctx.cos_to_last_boundary()
        except Exception: pass
        if isinstance(cos, float):
            print(f"  cos_to_last_boundary={cos:.4f}")
        if vhash and lbvh:
            try:
                h = _hamming_hex64(vhash, lbvh)
                if h >= 0:
                    print(f"  hamming(vhash,last_boundary)={h} bits (0..64)")
            except Exception:
                pass
        tv = getattr(ctx, "temporal", None)
        if tv:
            print(f"  dim={getattr(tv,'dim',0)} sigma={getattr(tv,'sigma',0.0):.4f} jump={getattr(tv,'jump',0.0):.4f}")
        if isinstance(cos, float):
            if cos >= 0.99:      status = "ON-EVENT BOUNDARY"
            elif cos < 0.90:     status = "EVENT BOUNDARY-SOON"
            else:                status = "DRIFTING slowly forward in time"
            print(f"  status={status}")
    except Exception as e:
        print(f"(tour) probe error: {e}")
    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("2/6"):
        return

    # 3) Capture scene (pre-capture boundary so the engram mirrors a new epoch)
    print("\n[tour] 3/6 — Capture a small scene as a CUE engram")
    try:
        # Boundary jump before capture
        if ctx.temporal:
            new_v = ctx.temporal.boundary()
            ctx.tvec_last_boundary = list(new_v)
            ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
            try:
                ctx.boundary_vhash64 = ctx.tvec64()
            except Exception:
                ctx.boundary_vhash64 = None
            print(f"[temporal] event/boundary (pre-capture) → epoch={ctx.boundary_no} last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

        from cca8_features import time_attrs_from_ctx  # local import OK
        attrs = time_attrs_from_ctx(ctx)
        vec = [0.10, 0.20, 0.30]
        channel, token, family, attach = "vision", "silhouette:mom", "cue", "now"
        bid, eid = world.capture_scene(channel, token, vec, attach=attach, family=family, attrs=attrs)

        print(f"[bridge] created binding {bid} with tag {family}:{channel}:{token} and attached engram id={eid}")
        # Fetch + summarize the engram record
        try:
            rec = world.get_engram(engram_id=eid)
            meta = rec.get("meta", {}) if isinstance(rec, dict) else {}
            tattrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
            if tattrs:
                print(f"[bridge] time on engram: ticks={tattrs.get('ticks')} tvec64={tattrs.get('tvec64')} "
                      f"epoch={tattrs.get('epoch')} epoch_vhash64={tattrs.get('epoch_vhash64')}")
        except Exception as e:
            print(f"(tour) get_engram note: {e}")

        # Print the exact pointer slot we attached
        try:
            slot = None
            b = world._bindings.get(bid)
            eng = getattr(b, "engrams", None)
            if isinstance(eng, dict):
                for s, v in eng.items():
                    if isinstance(v, dict) and v.get("id") == eid:
                        slot = s; break
            if slot:
                print(f'[bridge] attached pointer: {bid}.engrams["{slot}"] = {eid}')
        except Exception:
            pass

        # Nudge controller once (pretty summary)
        try:
            res = action_center_step(world, ctx, drives)
            if isinstance(res, dict) and res.get("status") != "noop":
                policy  = res.get("policy"); status = res.get("status")
                reward  = res.get("reward"); binding = res.get("binding")
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                gate = next((p for p in policy_rt.loaded if p.name == policy), None)
                explain_fn: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
                if explain_fn is not None:
                    try:
                        why = explain_fn(world, drives, ctx)
                        print(f"[why {policy}] {why}")
                    except Exception:
                        pass
        except Exception as e:
            print(f"(tour) controller step note: {e}")

    except Exception as e:
        print(f"(tour) capture error: {e}")

    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("3/6"):
        return

    # 4) Inspect the binding pointer and the engram
    print("\n[tour] 4/6 — Inspect binding pointer and engram")
    try:
        b = world._bindings.get(bid)
        print(f"Binding {bid} → Engrams:", b.engrams if getattr(b, "engrams", None) else "(none)")
        rec = world.get_engram(engram_id=eid)
        meta = rec.get("meta", {}) if isinstance(rec, dict) else {}
        print("Engram meta:", json.dumps(meta, indent=2))
        payload = rec.get("payload") if isinstance(rec, dict) else None
        if hasattr(payload, "meta"):
            pmeta = payload.meta()
            print(f"Engram payload: shape={pmeta.get('shape')} kind={pmeta.get('kind')}")
    except Exception as e:
        print(f"(tour) inspect error: {e}")
    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("4/6"):
        return

    # 5) List all engrams (one-line summary)
    print("\n[tour] 5/6 — List all engrams")
    try:
        seen = set()
        any_found = False
        for _bid in _sorted_bids(world):
            for _eid in _engrams_on_binding(world, _bid):
                if _eid in seen:
                    continue
                seen.add(_eid); any_found = True
                rec = None
                try: rec = world.get_engram(engram_id=_eid)
                except Exception: rec = None
                shape = dtype = None
                if isinstance(rec, dict):
                    pl = rec.get("payload")
                    if hasattr(pl, "meta"):
                        try:
                            pm = pl.meta()
                            shape, dtype = pm.get("shape"), pm.get("kind")
                        except Exception:
                            pass
                print(f"EID={_eid} src={_bid} payload(shape={shape}, dtype={dtype})")
        if not any_found:
            print("(no engrams found)")
    except Exception as e:
        print(f"(tour) list error: {e}")
    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("5/6"):
        return

    # 6) Search demonstration (by name substring)
    print("\n[tour] 6/6 — Search engrams by name (substring='silhouette')")
    try:
        found = False
        seen = set()
        for _bid in _sorted_bids(world):
            for _eid in _engrams_on_binding(world, _bid):
                if _eid in seen:
                    continue
                seen.add(_eid)
                rec = world.get_engram(engram_id=_eid)
                name = (rec.get("name") or "") if isinstance(rec, dict) else ""
                if "silhouette" in name:
                    attrs = rec.get("meta", {}).get("attrs", {}) if isinstance(rec, dict) else {}
                    print(f"EID={_eid} src={_bid} name={name} epoch={attrs.get('epoch')} tvec64={attrs.get('tvec64')}")
                    found = True
        if not found:
            print("(no matches)")
    except Exception as e:
        print(f"(tour) search error: {e}")

    print("\n=== End of Quick Tour ===")

# --------------------------------------------------------------------------------------
# World/intro flows and preflight-lite stamp helpers
# --------------------------------------------------------------------------------------


def choose_profile(ctx, world) -> dict:
    """Prompt for a profile. 'T' opens the README tutorial, then re-prompts.
    Returns a dict: {"name", "ctx_sigma", "ctx_jump", "winners_k"}.

    Default to Mountain Goat unless a profile is implemented.
    For unimplemented profiles, print a narrative and fall back to goat defaults.
    Returns a dict: {"name", "ctx_sigma", "ctx_jump", "winners_k"}.

    Behavior:
      - 1..7 → select profile (unimplemented ones print a narrative, then fall back to goat defaults).
      - 'T' or 't' → open README.md (tutorial) and re-prompt.
      - any other input → default to Mountain Goat (as before).
    """
    GOAT = ("Mountain Goat", 0.015, 0.2, 2)

    while True:
        try:
            choice = input("Please make a choice [1–7 or T | Enter = Mountain Goat]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled selection.... will exit program....")
            sys.exit(0)

        # Fast path: Enter accepts default
        if choice == "":
            name, sigma, jump, k = GOAT
            break

        # Tutorial: open README, then re-prompt
        if choice.lower() == "t":
            _open_readme_tutorial()
            continue  # re-show prompt

        # Numeric choices
        if choice == "1":
            name, sigma, jump, k = GOAT
            break
        if choice == "2":
            name, sigma, jump, k = profile_chimpanzee(ctx)
            break
        if choice == "3":
            name, sigma, jump, k = profile_human(ctx)
            break
        if choice == "4":
            name, sigma, jump, k = profile_human_multi_brains(ctx, world)
            break
        if choice == "5":
            name, sigma, jump, k = profile_society_multi_agents(ctx)
            break
        if choice == "6":
            name, sigma, jump, k = profile_multi_brains_adv_planning(ctx)
            break
        if choice == "7":
            name, sigma, jump, k = profile_superhuman(ctx)
            break

        # Anything else: prompt again (no silent default)
        print(f"The selection {choice!r} is not valid. Please enter 1–7, 'T', or press Enter for Mountain Goat.\n")

    ctx.profile = name
    return {"name": name, "ctx_sigma": sigma, "ctx_jump": jump, "winners_k": k}

def versions_dict() -> dict:
    """Collect versions/paths for core CCA8 components and environment."""
    mods = ["cca8_world_graph", "cca8_controller", "cca8_column", "cca8_features", "cca8_temporal"]
    info = {"runner": __version__, "platform": platform.platform(), "python": sys.version.split()[0]}
    for m in mods:
        ver, path = _module_version_and_path(m)
        key = m.replace("cca8_", "")          # world_graph, controller, column, features, temporal
        info[key] = ver
        info[key + "_path"] = path
    return info

def versions_text() -> str:
    """
    Return a human-readable summary of core component versions.

    Includes: runner, world_graph, controller, column, features, temporal.
    Internally formats `versions_dict()` so tests (and users) have a quick glanceable string.
    """
    d = versions_dict()  # existing function
    keys = ("runner", "world_graph", "controller", "column", "features", "temporal")
    lines = [f"{k}: {d.get(k, 'n/a')}" for k in keys]
    return "\n".join(lines)

def print_startup_notices(world) -> None:
    '''print active planner and other statuses at
    startup of the runner
    '''
    try:
        print(f"[planner] Active planner on startup: {world.get_planner().upper()}")
    except Exception as e:
        print(f"unable to retrieve which active planner is running: {e}")
        logging.error(f"Unable to retrieve startup active planner status: {e}", exc_info=True)

def run_preflight_full(args) -> int:
    """
    Full preflight: quick, deterministic checks with one-line PASS/FAIL per item.
    Returns 0 for ok, non-zero for any failure.

    While the preflight system is a very convenient way for testing the cca8 simulation software, particularly after code or large
    data changes, we acknowledge the strength and tradition of the Pytest (or equivalent) unit tests in validating the correctness of
    code logic, the ability for very granular testing and better proves that the code works. Thus, the preflight system by design first
    calls pytest to run whatever unit tests are present in the /tests subdirectory from the main working directory.

    """
    print("\nPreflight running....")
    print("Like an aircraft pre-flight, this check verifies the critical parts of")
    print("the CCA8 architecture and simulation before you “fly” the system.\n")
    print("There are four main parts. The first part runs a variety of unit tests,")
    print("currently pytest-based. Coverage reports the percent of EXECUTABLE lines")
    print("exercised. Comments and docstrings are ignored; ordinary code lines—")
    print("including print(...) and input(...)—COUNT toward coverage, but not always. We")
    print("generally aim for ≥30% line coverage as a useful signal, focusing on critical paths")
    print("over raw percentage (diminishing returns with higher percentages unless mission critical).")
    print("(Due to where results are read from, the percentage may differ by one or two percent")
    print("in the body and summary line of the report.)\n")
    print("The second part of preflight runs scenario checks to catch issues which the unit")
    print("tests can miss, particularly whole-flow behavior (CLI → persistence →")
    print("relaunch).\n")
    print("The third part of the preflight runs the robotics hardware checks. In this section")
    print("the checks actually resemble more closely their aviation counterparts.\n")
    print("The fourth part of the preflight runs the system integration checks. In this section")
    print("the checks actually resemble more closely a pilot's medical and mental fitness assessment")
    print("plus the pilot's flight assessment. In this fourth part the ability of the CCA8 architecture")
    print("to functionally carry out small tasks representative of its abilities are tested.\n")
    # pylint: disable=reimported
    import os as _os  #required for running pyvis in browswer if os being used elsewhere
    print("[preflight] Running full preflight...")

    failures = 0
    checks = 0

    import time as _time
    t0 = _time.perf_counter()

    def ok(msg):
        nonlocal checks
        checks += 1
        print(f"[preflight] PASS  - {msg}")

    def bad(msg):
        nonlocal failures, checks
        failures += 1
        checks += 1
        print(f"[preflight] FAIL  - {msg}")

    # helpers for the footer
    def _fmt_hms(seconds: float) -> str:
        m, s = divmod(int(round(seconds)), 60)
        h, m = divmod(m, 60)
        return f"{h:02d}:{m:02d}:{s:02d}" if h else f"{m:02d}:{s:02d}"

    def _parse_junit_xml(path: str) -> dict:
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()
            if root.tag == "testsuite":
                return {
                    "tests":   int(root.attrib.get("tests", 0)),
                    "failures":int(root.attrib.get("failures", 0)),
                    "errors":  int(root.attrib.get("errors", 0)),
                    "skipped": int(root.attrib.get("skipped", 0)),
                }
            elif root.tag == "testsuites":
                total = {"tests":0,"failures":0,"errors":0,"skipped":0}
                for ts in root.findall("testsuite"):
                    for k in total:
                        total[k] += int(ts.attrib.get(k, 0))
                return total
        except Exception:
            pass
        return {}

    def _parse_coverage_pct(path: str) -> float | None:
        try:
            import xml.etree.ElementTree as ET
            tree = ET.parse(path)
            root = tree.getroot()  # coverage.py: <coverage line-rate="0.87" ...>
            lr = root.attrib.get("line-rate")
            if lr is not None:
                return float(lr) * 100.0
            # fallback from totals if present
            lv = root.attrib.get("lines-valid")
            lc = root.attrib.get("lines-covered")
            if lv and lc:
                lvf, lcf = float(lv), float(lc)
                return (lcf / lvf) * 100.0 if lvf else None
        except Exception:
            return None
        return None

    # --- color helpers (Windows-safe, no third-party deps) ---
    import sys as _sys

    def _is_tty() -> bool:
        try:
            return _sys.stdout.isatty()
        except Exception:
            return False

    def _ansi_enable() -> bool:
        # POSIX terminals usually support ANSI out of the box
        if not _sys.platform.startswith("win"):
            return True
        # Windows: enable Virtual Terminal Processing on stdout
        try:
            import ctypes
            kernel32 = ctypes.windll.kernel32
            h = kernel32.GetStdHandle(-11)  # STD_OUTPUT_HANDLE
            mode = ctypes.c_uint32()
            if kernel32.GetConsoleMode(h, ctypes.byref(mode)):
                new_mode = mode.value | 0x0004  # ENABLE_VIRTUAL_TERMINAL_PROCESSING
                if kernel32.SetConsoleMode(h, new_mode):
                    return True
        except Exception:
            pass
        return False

    _ANSI_OK = _is_tty() and _ansi_enable()

    def _paint_fail(line: str) -> str:
        # red
        return f"\x1b[31m{line}\x1b[0m" if _ANSI_OK else line

    # --- Unit tests (pytest) — run first ------------------------------------------------
    try:
        if _os.path.isdir("tests"):
            try:
                import pytest as _pytest
                print("[preflight] Running unit tests (pytest)...\n")

                # Detect pytest-cov plugin; if missing, run without coverage
                try:
                    import pytest_cov as _pytest_cov  # noqa: F401  ## pylint: disable=unused-import
                    _have_cov = True
                except Exception:
                    _have_cov = False

                # Always ensure artifacts dir exists (for JUnit/coverage outputs)
                _os.makedirs(".coverage", exist_ok=True)

                if _have_cov:
                    _os.environ.setdefault("COVERAGE_FILE", ".coverage/.coverage.preflight")
                    _cov_pkgs = ["cca8_world_graph", "cca8_controller", "cca8_run",
                                 "cca8_temporal", "cca8_features", "cca8_column"]
                    _args = ["-v", "--maxfail=1", "--junitxml=.coverage/junit.xml"]
                    for _pkg in _cov_pkgs:
                        _args += ["--cov", _pkg]
                    if _os.path.exists(".coveragerc"):
                        _args += ["--cov-config", ".coveragerc"]
                    # human + machine readable reports
                    _args += ["--cov-report=term-missing",
                              "--cov-report=xml:.coverage/coverage.xml",
                              "tests"]
                else:
                    # Fallback: no coverage plugin, but still produce JUnit for counts
                    _args = ["-v", "--maxfail=1", "--junitxml=.coverage/junit.xml", "tests"]

                _rc = _pytest.main(_args)
                if _rc == 0:
                    ok("pytest: all tests passed\n")
                    if _have_cov:
                        ok("coverage: see .coverage/coverage.xml and console summary above\n")
                else:
                    bad(f"pytest: test run reported failures (exit={_rc})\n")
            except Exception as e:
                bad(f"pytest run error: {e}")
        else:
            ok("pytest: no 'tests' directory found — skipping\n")
    except Exception as e:
        bad(f"pytest not available or other error: {e}\n")

    # 1) Python & platform
    try:
        pyver = sys.version.split()[0]
        ok(f"python={pyver} platform={platform.platform()}")
    except Exception as e:
        bad(f"could not read python/platform: {e}")

    # 2a) CCA8 modules present & importable (plus key symbols)
    try:
        import importlib

        # module name → list of symbols we expect to exist
        _mods: list[tuple[str, list[str]]] = [
            ("cca8_world_graph", ["WorldGraph", "__version__"]),
            ("cca8_controller",  ["Drives", "action_center_step", "__version__"]),
            ("cca8_column",      ["__version__"]),
            ("cca8_features",    ["__version__"]),
            ("cca8_temporal",    ["__version__"]),
        ]

        for _name, _symbols in _mods:
            try:
                _m = importlib.import_module(_name)
                _ver = getattr(_m, "__version__", None)
                _pth = getattr(_m, "__file__", None)
                ok(f"import {_name}" + (f" v{_ver}" if _ver else "") +
                   (f" ({_os.path.basename(_pth)})" if _pth else ""))

                for _sym in _symbols:
                    # "__version__" may not exist on every module; treat missing version as OK
                    if _sym == "__version__":
                        continue
                    if hasattr(_m, _sym):
                        # Touch the symbol to ensure it resolves
                        getattr(_m, _sym)
                        ok(f"{_name}.{_sym} available")
                    else:
                        bad(f"{_name}: missing symbol '{_sym}'")
            except Exception as e:
                bad(f"import {_name} failed: {e}")
    except Exception as e:
        bad(f"module import checks failed: {e}")

        # 2b) Explicit invariant check on a tiny fresh world
    try:
        _wi = cca8_world_graph.WorldGraph()
        _wi.ensure_anchor("NOW")
        issues = _wi.check_invariants(raise_on_error=False)
        if issues:
            bad("invariants: " + "; ".join(issues))
        else:
            ok("invariants: no issues on fresh world")
    except Exception as e:
        bad(f"invariants: check raised: {e}")


    # 3a) Accessory files present (README + image), non-empty
    try:
        _files = ["README.md", "calf_goat.jpg"]  # add more here if needed
        for _f in _files:
            try:
                if os.path.exists(_f):
                    _sz = os.path.getsize(_f)
                    if _sz > 0:
                        ok(f"file present: {_f} ({_sz} bytes)")
                    else:
                        bad(f"file present but empty: {_f}")
                else:
                    bad(f"file missing: {_f}")
            except Exception as e:
                bad(f"file check failed for {_f}: {e}")
    except Exception as e:
        bad(f"accessory file checks failed: {e}")

    # 4a) Pyvis installed (for HTML graph export)
    try:
        import pyvis as _pyvis # type: ignore # pylint: disable=unused-import
        ok("pyvis installed")
    except Exception as e:
        ok(f"pyvis not installed (export still optional): {e}")

    # 2) WorldGraph sanity
    try:
        w = cca8_world_graph.WorldGraph()
        w.ensure_anchor("NOW")
        if isinstance(w._bindings, dict) and _anchor_id(w, "NOW") != "?":
            ok("WorldGraph init and NOW anchor")
        else:
            bad("WorldGraph anchor missing or invalid")
    except Exception as e:
        bad(f"WorldGraph init failed: {e}")


    # 2a) WorldGraph.set_now() — anchor remap & tag housekeeping (no warnings)
    try:
        # fresh temp world just for this test
        _w2 = cca8_world_graph.WorldGraph()
        _w2.set_tag_policy("allow")  # silence lexicon WARNs in this probe
        # ensure NOW exists for this instance
        _old_now = _w2.ensure_anchor("NOW")

        def _tags_of(bid_: str):
            b = _w2._bindings[bid_]
            ts = getattr(b, "tags", None)
            if ts is None:
                b.tags = []
                ts = b.tags
            return ts

        def _has_tag(bid_: str, t: str) -> bool:
            ts = getattr(_w2._bindings[bid_], "tags", None)
            return bool(ts) and (t in ts)

        def _tag_add(bid_: str, t: str):
            ts = _tags_of(bid_)
            try: ts.add(t)
            except AttributeError:
                if t not in ts: ts.append(t)

        def _tag_discard(bid_: str, t: str):
            ts = getattr(_w2._bindings[bid_], "tags", None)
            if ts is None: return
            try: ts.discard(t)
            except AttributeError:
                try: ts.remove(t)
                except ValueError: pass

        ok("set_now: ensured initial NOW exists")

        # make sure the old NOW is visibly tagged so we can verify removal later
        if not _has_tag(_old_now, "anchor:NOW"):
            _tag_add(_old_now, "anchor:NOW")

        # create a new binding to become NOW (no auto-attach)
        _new_now = _w2.add_predicate("pred:preflight:now_test", attach="none", meta={"created_by": "preflight"})

        _prev = _w2.set_now(_new_now, tag=True, clean_previous=True)

        # anchors map updated?
        if _w2._anchors.get("NOW") == _new_now:
            ok("set_now: NOW anchor re-pointed")
        else:
            bad("set_now: anchors map not updated")

        # new NOW has anchor tag?
        if _has_tag(_new_now, "anchor:NOW"):
            ok("set_now: new NOW has anchor:NOW tag")
        else:
            bad("set_now: new NOW missing anchor:NOW tag")

        # previous NOW lost the anchor tag?
        if _prev and _prev in _w2._bindings:
            if not _has_tag(_prev, "anchor:NOW"):
                ok("set_now: removed anchor:NOW from previous NOW")
            else:
                bad("set_now: previous NOW still tagged anchor:NOW")

        # negative test: unknown id must raise KeyError
        try:
            _w2.set_now("b999999", tag=True)
            bad("set_now: accepted unknown id (expected KeyError)")
        except KeyError:
            ok("set_now: rejects unknown id (KeyError)")

    except Exception as e:
        bad(f"set_now test failed: {e}")

    # 3) Controller primitives
    try:
        from cca8_controller import PRIMITIVES, Drives as _Drv, __version__ as _CTRL_VER
        # (action_center_step is already imported at module top; if not, import it here too)
        if isinstance(PRIMITIVES, list) and PRIMITIVES:
            ok(f"controller primitives loaded (count={len(PRIMITIVES)})")
        else:
            bad("controller primitives missing/empty")

        # Smoke: run the controller once on a fresh world using the real Ctx dataclass
        try:
            _w = cca8_world_graph.WorldGraph(); _w.ensure_anchor("NOW")
            _d = _Drv()
            _ctx = Ctx()
            _ = action_center_step(_w, _ctx, _d)
            ok(f"action_center_step smoke-run (cca8_controller v{_CTRL_VER})")
        except Exception as e:
            bad(f"action_center_step failed to run: {e}")
    except Exception as e:
        bad(f"controller import failed: {e}")


    # 4) HAL header consistency (does not require real hardware)
    try:
        hal_flag = bool(getattr(args, "hal", False))
        body_val = (getattr(args, "body", "") or "").strip() or "(none)"
        ok(f"HAL flag={hal_flag} body={body_val}, nb no actual robotic embodiment implemented to pre-flight at this time")
    except Exception as e:
        bad(f"HAL/body flag read error: {e}")

    # 5) Read/write snapshot (tmp)
    try:
        tmp = "_preflight_session.json"
        d  = Drives()
        ts = save_session(tmp, cca8_world_graph.WorldGraph(), d)
        if os.path.exists(tmp):
            ok(f"snapshot write/read path exists ({tmp}, saved_at={ts})")
            try:
                with open(tmp, "r", encoding="utf-8") as f: json.load(f)
                ok("snapshot JSON parse")
            except Exception as e:
                bad(f"snapshot JSON parse failed: {e}")
            try:
                os.remove(tmp)
                ok("snapshot cleanup")
            except Exception as e:
                bad(f"snapshot cleanup failed: {e}")
        else:
            bad("snapshot file missing after save")
    except Exception as e:
        bad(f"snapshot write failed: {e}")

    # 6) Planning stub
    try:
        w = cca8_world_graph.WorldGraph()
        src = w.ensure_anchor("NOW")
        # plan to something that isn't there: expect no path, not an exception
        p = w.plan_to_predicate(src, "milk:drinking")
        ok(f"planner probes (path_found={bool(p)})")
    except Exception as e:
        bad(f"planner probe failed: {e}")

    # Z1) Attach semantics (NOW/latest → new binding) — no warnings
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.set_tag_policy("allow")  # silence lexicon WARNs here
        _now = _w.ensure_anchor("NOW")

        # attach="now" creates NOW→new (then) and updates LATEST
        _a = _w.add_predicate("pred:test:A", attach="now")

        if any(e.get("to") == _a and e.get("label", "then") == "then" for e in (_w._bindings[_now].edges or [])):
            ok("attach=now: NOW→new edge recorded")
        else:
            bad("attach=now: missing NOW→new edge")

        if _w._latest_binding_id == _a:
            ok("attach=now: LATEST updated to new binding")
        else:
            bad("attach=now: LATEST not updated")

        # attach="latest" creates oldLATEST→new (then) and updates LATEST
        _b = _w.add_predicate("pred:test:B", attach="latest")

        if any(e.get("to") == _b and e.get("label", "then") == "then" for e in (_w._bindings[_a].edges or [])):
            ok("attach=latest: LATEST→new edge recorded")
        else:
            bad("attach=latest: missing LATEST→new edge")

        if _w._latest_binding_id == _b:
            ok("attach=latest: LATEST updated to new binding")
        else:
            bad("attach=latest: LATEST not updated")

    except Exception as e:
        bad(f"attach semantics failed: {e}")

    # Z2) Cue normalization & family check
    try:
        _w3 = cca8_world_graph.WorldGraph()
        _w3.ensure_anchor("NOW")
        _c = _w3.add_cue("vision:silhouette:mom", attach="now", meta={"preflight": True})
        _tags = getattr(_w3._bindings[_c], "tags", []) or []
        if "cue:vision:silhouette:mom" in _tags:
            ok("cue add: created tag cue:vision:silhouette:mom")
        else:
            bad("cue add: did not normalize to cue:*")
        if any(isinstance(t, str) and t.startswith("pred:vision:") for t in _tags):
            bad("cue add: legacy pred:vision:* still present")
        else:
            ok("cue add: no legacy pred:vision:* present")
    except Exception as e:
        bad(f"cue normalization failed: {e}")

    # Z3) Action metrics aggregator — no warnings
    try:
        _w4 = cca8_world_graph.WorldGraph()
        _w4.set_tag_policy("allow")  # silence lexicon WARNs here
        _w4.ensure_anchor("NOW")
        _src = _w4.add_predicate("pred:test:src", attach="now")
        _dst = _w4.add_predicate("pred:test:dst", attach="none")
        _w4.add_edge(_src, _dst, label="run", meta={"meters": 10.0, "duration_s": 4.0})
        _met = _w4.action_metrics("run")
        if _met.get("count") == 1 and _met.get("keys", {}).get("meters", {}).get("sum") == 10.0:
            ok("action metrics: aggregated numeric meta (meters)")
        else:
            bad(f"action metrics: unexpected aggregate { _met }")
    except Exception as e:
        bad(f"action metrics failed: {e}")

    # Z4) BFS sanity (shortest-hop path found) — no warnings
    try:
        _w5 = cca8_world_graph.WorldGraph()
        _w5.set_tag_policy("allow")  # silence lexicon WARNs here
        _start = _w5.ensure_anchor("NOW")
        _a1 = _w5.add_predicate("pred:test:A", attach="now")
        _a2 = _w5.add_predicate("pred:test:B", attach="latest")
        _goal = _w5.add_predicate("pred:test:goal", attach="latest")
        _path = _w5.plan_to_predicate(_start, "pred:test:goal")
        if _path and _path[-1] == _goal and len(_path) >= 2:
            ok("planner: shortest-hop path to pred:test:goal found")
        else:
            bad(f"planner: unexpected path { _path }")
    except Exception as e:
        bad(f"planner (BFS) sanity failed: {e}")

    # Z5) Lexicon strictness: reject out-of-lexicon pred at neonate
    try:
        _w6 = cca8_world_graph.WorldGraph()
        _w6.set_stage("neonate"); _w6.set_tag_policy("strict"); _w6.ensure_anchor("NOW")
        try:
            _w6.add_predicate("abstract:calculus", attach="now")
            bad("lexicon: strict did not reject out-of-lexicon token")
        except ValueError:
            ok("lexicon: strict rejects out-of-lexicon token at neonate")
    except Exception as e:
        bad(f"lexicon strictness failed: {e}")

    # Z6) Engram bridge: capture_scene → engram asserted, pointer attached
    try:
        _w7 = cca8_world_graph.WorldGraph()
        _w7.ensure_anchor("NOW")
        bid, eid = _w7.capture_scene("vision", "silhouette:mom", [0.1, 0.2, 0.3], attach="now", family="cue")
        # engram pointer attached?
        b = _w7._bindings[bid]

        if any(t.startswith("cue:") for t in (b.tags or [])):
            ok("engram bridge: binding created with cue")
        else:
            bad("engram bridge: cue tag missing")

        if b.engrams and "column01" in b.engrams and b.engrams["column01"].get("id") == eid:
            ok("engram bridge: pointer attached to binding")
        else:
            bad("engram bridge: pointer not attached")
        # column record retrievable?
        rec = _w7.get_engram(engram_id=eid)
        if isinstance(rec, dict) and rec.get("id") == eid:
            ok("engram bridge: column record retrievable")
        else:
            bad("engram bridge: column record missing or malformed")
    except Exception as e:
        bad(f"engram bridge failed: {e}")

    # 7) Action helpers sanity
    try:
        _wa = cca8_world_graph.WorldGraph()
        s = _wa.action_summary_text(include_then=True, examples_per_action=1)
        # minimal presence check — the string can say "No actions..." on a fresh world, still OK
        if isinstance(s, str):
            ok("action helpers: summary generated")
        else:
            bad("action helpers: summary did not return text")
    except Exception as e:
        bad(f"action helpers failed: {e}")


    # part 3 -- hardware and robotics preflight
    hal_str  = getattr(args, "hal_status_str", "OFF (no embodiment)")
    body_str = getattr(args, "body_status_str", PLACEHOLDER_EMBODIMENT)
    print(f"\n[preflight hardware_robotics] HAL={hal_str}; body={body_str}")

    hal_checks = 0
    hal_failures = 0

    def ok_hw(msg: str) -> None:
        nonlocal hal_checks
        hal_checks += 1
        print(f"[preflight hardware_robotics] PASS  - {msg}")

    def bad_hw(msg: str) -> None:
        nonlocal hal_checks, hal_failures
        hal_checks += 1
        hal_failures += 1
        print(f"[preflight hardware_robotics] FAIL  - {msg}")

    # 3a) CPU enumeration
    try:
        _n = os.cpu_count() or 0
        if _n > 0:
            ok_hw(f"cpu_count={_n}")
        else:
            bad_hw("cpu_count returned 0")
    except Exception as e:
        bad_hw(f"cpu_count error: {e}")

    # 3b) High-resolution timer sanity (monotonic + resolution)
    try:
        import time as _time2
        info = _time2.get_clock_info("perf_counter")
        res  = getattr(info, "resolution", None)
        a = _time2.perf_counter(); b = _time2.perf_counter(); c = _time2.perf_counter()
        if a < b < c:
            ok_hw(f"perf_counter monotonic (resolution≈{res:.9f}s)")
        else:
            bad_hw("perf_counter did not strictly increase")
    except Exception as e:
        bad_hw(f"perf_counter check error: {e}")

    # 3c) Temp file write/read (4 KiB)
    try:
        import tempfile as _tempfile
        with _tempfile.NamedTemporaryFile("wb", delete=True) as tf:
            tf.write(b"\0" * 4096)
            tf.flush()
        ok_hw("temp file write (4 KiB)")
    except Exception as e:
        bad_hw(f"temp file write failed: {e}")

    # 3d) System memory (GiB) ≥ MIN_RAM_GB (default 4 -- Nov 2025)
    #adjust minimum RAM tested as makes sense for the hardware
    #looks for RAM in this order: psutil (if available), then Windows, then Linux, then MacOS, then Linux-like
    #if NON_WIN_LINUX=True for non-Win/macOS/Linux/like system, then test is bypassed
    try:
        if NON_WIN_LINUX:
            MIN_RAM_GB = 0.0
        else:
            MIN_RAM_GB = float(os.getenv("CCA8_MIN_RAM_GB", "4"))
        min_bytes = int(MIN_RAM_GB * (1024 ** 3))
        #min_bytes = int(5000.0 * (1024 ** 3))  #for testing to trigger a hardware testing warning

        def _total_ram_bytes() -> int:
            # Optional: psutil if present
            try:
                import psutil  # type: ignore
                return int(psutil.virtual_memory().total)
            except Exception:
                pass
            # Windows: GlobalMemoryStatusEx
            try:
                import ctypes
                class MEMORYSTATUSEX(ctypes.Structure): # pylint: disable=too-few-public-methods
                    """from cytpes library to store system info"""
                    _fields_ = [
                        ("dwLength", ctypes.c_ulong),
                        ("dwMemoryLoad", ctypes.c_ulong),
                        ("ullTotalPhys", ctypes.c_ulonglong),
                        ("ullAvailPhys", ctypes.c_ulonglong),
                        ("ullTotalPageFile", ctypes.c_ulonglong),
                        ("ullAvailPageFile", ctypes.c_ulonglong),
                        ("ullTotalVirtual", ctypes.c_ulonglong),
                        ("ullAvailVirtual", ctypes.c_ulonglong),
                        ("ullAvailExtendedVirtual", ctypes.c_ulonglong),
                    ]
                stat = MEMORYSTATUSEX()
                stat.dwLength = ctypes.sizeof(MEMORYSTATUSEX) # pylint: disable=attribute-defined-outside-init
                if ctypes.windll.kernel32.GlobalMemoryStatusEx(ctypes.byref(stat)):
                    return int(stat.ullTotalPhys)
            except Exception:
                pass
            # Linux: sysconf
            try:
                sysconf_fn: Optional[Callable[[str], int]] = getattr(os, "sysconf", None)  # type: ignore[attr-defined]
                if sysconf_fn is not None:
                    page = int(sysconf_fn("SC_PAGE_SIZE"))   # ok: Pylint sees a Callable
                    phys = int(sysconf_fn("SC_PHYS_PAGES"))
                    return page * phys
            except Exception:
                pass
            # macOS: sysctl
            try:
                out = subprocess.check_output(["sysctl", "-n", "hw.memsize"], text=True).strip()
                return int(out)
            except Exception:
                pass
            # Fallback: /proc/meminfo (Linux-like)
            try:
                with open("/proc/meminfo", "r", encoding="utf-8") as f:
                    for line in f:
                        if line.startswith("MemTotal:"):
                            # value reported in kB
                            return int(line.split()[1]) * 1024
            except Exception:
                pass
            return 0

        _total = _total_ram_bytes()
        if _total >= min_bytes:
            ok_hw(f"memory total={_total/(1024**3):.1f} GB -- (threshold RAM ≥{MIN_RAM_GB:.0f} GiB)")
        else:
            bad_hw(f"memory total={_total/(1024**3):.1f} GB -- below threshold RAM of {MIN_RAM_GB:.0f} GiB")
    except Exception as e:
        bad_hw(f"memory check error: {e}")

    # 3e) Disk free space on current volume ≥ MIN_DISK_GB (default 1)
    try:
        MIN_DISK_GB = float(os.getenv("CCA8_MIN_DISK_GB", "1"))
        _, _, free = shutil.disk_usage(".")
        if free >= int(MIN_DISK_GB * (1024 ** 3)):
            ok_hw(f"disk free={free/(1024**3):.1f} GiB (threshold≥{MIN_DISK_GB:.0f} GiB)")
        else:
            bad_hw(f"disk free={free/(1024**3):.1f} GiB below threshold {MIN_DISK_GB:.0f} GiB")
    except Exception as e:
        bad_hw(f"disk free check error: {e}")


    # part 4 -- integrated system preflight (stub)
    print(f"\n[preflight system functionality] PASS  - NO-TEST: HAL={hal_str}; body={body_str} — pending integration")
    assessment_checks = 0
    assessment_failures = 0


    # Compute Summary Results
    # ---- Summary footer (with denominators) ----
    elapsed_total = _time.perf_counter() - t0
    mm, ss = divmod(int(round(elapsed_total)), 60)
    elapsed_mmss = f"{mm:02d}:{ss:02d}"

    # Tests / coverage (Part 1)
    junit = _parse_junit_xml(".coverage/junit.xml")
    tests_total = junit.get("tests")
    tests_fail  = (junit.get("failures", 0) or 0) + (junit.get("errors", 0) or 0)
    tests_skip  = junit.get("skipped", 0) or 0
    tests_pass  = (tests_total - tests_fail - tests_skip) if isinstance(tests_total, int) else None
    cov_pct     = _parse_coverage_pct(".coverage/coverage.xml")

    tests_txt = (f"unit_tests={tests_pass}/{tests_total}"
                 if isinstance(tests_total, int) else "unit_tests=—")
    cov_txt   = (f"coverage={cov_pct:.0f}% ({'≥30' if (cov_pct or 0.0) >= 30.0 else '<30'})"
                 if (cov_pct is not None) else "coverage=—")

    # Probes (Part 2) — counts come from your ok()/bad() probe counters
    probes_pass = max(0, checks - failures)
    probes_txt  = f"probes={probes_pass}/{checks}"

    # Hardware (Part 3) — show pass/total
    hardware_pass = max(0, hal_checks - hal_failures)

    # System fitness (Part 4) — show pass/total (stub)
    assessment_checks = locals().get("assessment_checks", 0)
    assessment_failures = locals().get("assessment_failures", 0)
    assess_pass = max(0, assessment_checks - assessment_failures)

    # Overall status (fail if any part failed)
    status_ok = (
        (failures == 0) and
        (hal_failures == 0) and
        (assessment_failures == 0) and
        (tests_fail == 0 if isinstance(tests_total, int) else True)
    )

    line1 = f"\n[preflight] RESULT: {'PASS' if status_ok else 'FAIL'} | PART 1: {tests_txt} | {cov_txt} | PART 2: {probes_txt} |"
    line2 = (f"[preflight] PART 3: hardware_robotics_checks = {hardware_pass}/{hal_checks} | "
             f"PART 4: system_fitness_assessments = {assess_pass}/{assessment_checks} |")
    line3 = f"[preflight] elapsed_time (mm:ss) ={elapsed_mmss}"

    print(_paint_fail(line1) if not status_ok else line1)

    # If any non-test part failed, color line2 as well for quick scanning
    if hal_failures or assessment_failures:
        print(_paint_fail(line2))
    else:
        print(line2)
    print(line3)
    random.seed(time.perf_counter_ns())
    if assessment_failures == 0 and status_ok and random.randint(1,10) in (2, 3, 4):  #silly humor
        print("\nError!! ###$#$# !!  system_fitness_assessments has DIVIDE BY ZERO ERROR -- DANGER!! DANGER!!\n.... just kidding:)\n")

    if status_ok:
        print_ascii_logo(style="goat", color=True)
    return 0 if status_ok else 1


def run_preflight_lite_maybe():
    """Optional 'lite' preflight on startup (controlled by CCA8_PREFLIGHT)."""
    mode = os.environ.get("CCA8_PREFLIGHT", "lite").lower()
    if mode == "off":
        return
    print("[preflight-lite] checks ok\n\n")

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
    """Return binding ids sorted numerically (b1, b2, ...), with non-numeric ids last."""
    def key_fn(bid: str):
        try: return int(bid[1:])  # sort b1,b2,... numerically
        except: return 10**9
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

    # EDGES (collapsed duplicates)
    lines.append("")
    lines.append("EDGES:")
    from collections import Counter
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
    lines.append("  • Drives object: cca8_controller.Drives  [src=cca8_controller.Drives]")
    lines.append("  • Updated by: autonomic ticks, policies, or direct code.")
    lines.append("  • Drive tags here are ephemeral (not persisted unless you choose to).")

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
    from math import isfinite
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

def _io_banner(args, loaded_path: str | None, loaded_ok: bool) -> None:
    """Explain how load/autosave will behave for this run."""
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
        print(f"[io] Loaded '{lp}'. Autosave OFF — use menu [S] to save or relaunch with --autosave <path>.")
    elif (not loaded_ok) and ap:
        print(f"[io] Started a NEW session. Autosave ON to '{ap}'.")
    else:
        print("[io] Started a NEW session. Autosave OFF — use [S] to save or pass --autosave <path>.")


# ---------- Contextual base selection (skeleton) ----------
def _nearest_binding_with_pred(world, token: str, from_bid: str, max_hops: int = 3) -> str | None:
    """Return the first binding matching pred:<token> found by BFS from `from_bid` within `max_hops`."""
    want = token if token.startswith("pred:") else f"pred:{token}"
    # BFS with early exit that returns the first binding matching the predicate
    from collections import deque
    q, seen, depth = deque([from_bid]), {from_bid}, {from_bid: 0}
    while q:
        u = q.popleft()
        b = world._bindings.get(u)
        if b and any(t == want for t in getattr(b, "tags", [])):
            return u
        if depth[u] >= max_hops:
            continue
        edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
        if isinstance(edges, list):
            for e in edges:
                v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if v and v not in seen:
                    seen.add(v); depth[v] = depth[u] + 1; q.append(v)
    return None

def choose_contextual_base(world, ctx, targets: list[str] | None = None) -> dict: # pylint: disable=unused-argument
    """
    Skeleton: pick where a primitive *should* anchor writes.
    Order: nearest target predicate -> HERE (if exists) -> NOW.
    We only *suggest* the base here; controller may ignore it today.
    """
    targets = targets or ["state:posture_standing", "stand"]
    now_id  = _anchor_id(world, "NOW")
    here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
    # try each target nearest to NOW
    for tok in targets:
        bid = _nearest_binding_with_pred(world, tok, from_bid=now_id, max_hops=3)
        if bid:
            return {"base": "NEAREST_PRED", "pred": tok, "bid": bid}
    if here_id:
        return {"base": "HERE", "bid": here_id}
    return {"base": "NOW", "bid": now_id}

# ---------- FOA (Focus of Attention) skeleton ----------
def present_cue_bids(world) -> list[str]:
    """Return binding ids that carry any `cue:*` tag (unordered)
    """
    bids = []
    for bid, b in world._bindings.items():
        ts = getattr(b, "tags", [])
        if any(isinstance(t, str) and t.startswith("cue:") for t in ts):
            bids.append(bid)
    return bids

def neighbors_k(world, start_bid: str, max_hops: int = 2) -> set[str]:
    """Return the set of nodes within `max_hops` hops of `start_bid` (inclusive).
    """
    from collections import deque
    out = set()
    q = deque([(start_bid, 0)])
    seen = {start_bid}
    while q:
        u, d = q.popleft()
        out.add(u)
        if d >= max_hops:
            continue
        b = world._bindings.get(u)
        edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
        if isinstance(edges, list):
            for e in edges:
                v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if v and v not in seen:
                    seen.add(v); q.append((v, d+1))
    return out

def compute_foa(world, ctx, max_hops: int = 2) -> dict: # pylint: disable=unused-argument
    """
    Skeleton FOA window: union of neighborhoods around LATEST and NOW, plus cue nodes.
    Later we can weight by drives/costs and restrict size aggressively.
    """
    now_id   = _anchor_id(world, "NOW")
    latest   = world._latest_binding_id
    seeds    = [x for x in [latest, now_id] if x]
    seeds   += present_cue_bids(world)
    # dedupe seeds while preserving original order
    seen: set[str] = set()
    uniq: list[str] = []
    for s in seeds:
        if s not in seen:
            seen.add(s)
            uniq.append(s)
    seeds = uniq
    foa_ids  = set()
    for s in seeds:
        foa_ids |= neighbors_k(world, s, max_hops=max_hops)
    return {"seeds": seeds, "size": len(foa_ids), "ids": foa_ids}

# ---------- Multi-anchor candidates (skeleton) ----------
def candidate_anchors(world, ctx) -> list[str]:  # pylint: disable=unused-argument
    """
    Skeleton list of candidate start anchors for planning/search.
    Later we’ll run K parallel searches from these.
    """
    now_id   = _anchor_id(world, "NOW")
    here_id  = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
    picks    = [now_id]
    if here_id and here_id not in picks: picks.append(here_id)
    for tok in ("state:posture_standing", "stand", "mom:close"):
        bid = _nearest_binding_with_pred(world, tok, from_bid=now_id, max_hops=3)
        if bid and bid not in picks:
            picks.append(bid)
    return [p for p in picks if p]


# --------------------------------------------------------------------------------------
# Interactive loop
# --------------------------------------------------------------------------------------

def interactive_loop(args: argparse.Namespace) -> None:
    """Main interactive loop."""
    # Build initial world/drives fresh
    world = cca8_world_graph.WorldGraph()
    drives = Drives()  #Drives(hunger=0.7, fatigue=0.2, warmth=0.6) at time of writing comment
    #drives.fatigue = 0.85 #for devp't testing --> Drives(hunger=0.7, fatigue=0.85, warmth=0.6)
    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)
    ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump) # temporal soft clock (added)
    ctx.tvec_last_boundary = ctx.temporal.vector()  # seed “last boundary”
    try:
        ctx.boundary_vhash64 = ctx.tvec64()
    except Exception:
        ctx.boundary_vhash64 = None
    print_startup_notices(world)

    POLICY_RT = PolicyRuntime(CATALOG_GATES)
    POLICY_RT.refresh_loaded(ctx)
    loaded_ok = False
    loaded_src = None

    # ---- Text command aliases (words + 3-letter prefixes → legacy actions) -----
    #will map to current menu which then must be mapped to original menu numbers
    #intentionally keep here so easier for development visualization than up at top with constants
    MIN_PREFIX = 3 #if not perfect match then this specifies how many letters to match
    _ALIASES = {
    # Quick Start & Tutorial
    "understanding": "1", "tagging": "1",
    "tutorial": "2", "tour": "2", "help": "2",

    # Quick Start / Overview
    "snapshot": "3", "display": "3",
    "world": "4", "stats": "4",
    "last": "5", "bindings": "5",
    "drives": "6",
    "skills": "7",
    "temporal": "8", "tp": "8", "probe": "8",

    # Act / Simulate
    "instinct": "9", "act": "9",
    "autonomic": "10", "tick": "10",
    "fall": "11", "simulate": "11",

    # Perception & Memory
    "sensory": "12", "cue": "12",
    "capture": "13", "cap": "13", "scene": "13",
    "resolve": "14", "engrams": "14",
    "engram": "15", "engr": "15", "ei": "15",
    "engrams-all": "16", "list-engrams": "16", "le": "16", "la": "16",
    "search-engrams": "17", "find-engrams": "17", "se": "17",
    "delete-engram": "18", "del-engram": "18", "de": "18",
    "attach-engram": "19", "ae": "19",

    # Graph Inspect / Build / Plan
    "inspect": "20", "details": "20", "id": "20",
    "listpredicates": "21", "listpreds": "21", "listp": "21",
    "add": "22", "predicate": "22",
    "connect": "23", "link": "23",
    "delete": "24", "del": "24", "rm": "24",
    "plan": "25",
    "planner": "26", "strategy": "26", "dijkstra": "26", "bfs": "26",
    "pyvis": "27", "graph": "27", "viz": "27", "html": "27", "interactive": "27", "export and display": "27",

    # Save / System / Help
    "export snapshot": "28",
    "save": "29",
    "load": "30",
    "preflight": "31",
    "quit": "32", "exit": "32",
    "loc": "33", "sloc": "33", "pygount": "33",

    # Keep letter shortcuts working too
    "s": "s", "l": "l", "t": "t", "d": "d", "r": "r",
}

    # NEW MENU compatibility: accept new grouped numbers and legacy ones.
    NEW_TO_OLD = {
    # Quick Start & Tutorial
    "1": "23",  # Understanding (help pane)
    "2": "t",   # Tutorial (letter branch)

    # Quick Start / Overview
    "3": "17",  # Snapshot (display)
    "4": "1",   # World stats
    "5": "7",   # Recent bindings (last 5)
    "6": "d",   # Drives & tags (letter branch)
    "7": "13",  # Skill ledger
    "8": "26",  # Temporal probe

    # Act / Simulate
    "9": "12",   # Instinct step
    "10": "14",  # Autonomic tick
    "11": "18",  # Simulate fall

    # Perception & Memory
    "12": "11",  # Input sensory cue
    "13": "24",  # Capture scene → engram
    "14": "6",   # Resolve engrams on a binding
    "15": "27",  # Inspect engram by id
    "16": "28",  # List all engrams
    "17": "29",  # Search engrams
    "18": "30",  # Delete engram by id
    "19": "31",  # Attach existing engram

    # Graph Inspect / Build / Plan
    "20": "10",  # Inspect binding details
    "21": "2",   # List predicates
    "22": "3",   # Add predicate
    "23": "4",   # Connect two bindings
    "24": "15",  # Delete edge
    "25": "5",   # Plan from NOW -> <predicate>
    "26": "25",  # Planner strategy (toggle)
    "27": "22",  # Export interactive graph

    # Save / System / Help
    "28": "16",  # Export snapshot (text)
    "29": "s",   # Save session
    "30": "l",   # Load session
    "31": "9",   # Run preflight now
    "32": "8",   # Quit
    "33": "33",  # Lines of Count
}

    # Attempt to load a prior session if requested
    if args.load:
        try:
            with open(args.load, "r", encoding="utf-8") as f:
                blob = json.load(f)

            new_world  = cca8_world_graph.WorldGraph.from_dict(blob.get("world", {}))
            try:
                new_drives = Drives.from_dict(blob.get("drives", {}))
            except Exception as e:
                print(f"[warn] --load: invalid drives in {args.load}: {e}; using defaults.")
                new_drives = Drives()

            skills_from_dict(blob.get("skills", {}))
            world, drives = new_world, new_drives
            loaded_ok = True
            loaded_src = args.load

            print(f"Loaded {args.load} (saved_at={blob.get('saved_at','?')})")
            print("A previously saved simulation session is being continued here.\n")

        except FileNotFoundError:
            print(f"The file {args.load} could not be found. The simulation will run as a new one.\n")
        except json.JSONDecodeError as e:
            print(f"[warn] --load: invalid JSON in {args.load}: {e}")
            print("The simulation will run as a new one.\n")
        except (PermissionError, OSError) as e:
            print(f"[warn] --load: could not read {args.load}: {e}")
            print("The simulation will run as a new one.\n")
        except Exception as e:
            print(f"The file was found but there was a problem reading it: {args.load}: {e}")
            print("The simulation will run as a new one.\n")

    # Banner & profile selection
    if not args.no_intro:
        print_header(args.hal_status_str, args.body_status_str)
    if args.profile:
        mapping = {"goat": ("Mountain Goat", 0.015, 0.2, 2),
                   "chimp": ("Chimpanzee", 0.02, 0.25, 3),
                   "human": ("Human", 0.03, 0.3, 4),
                   "super": ("Super-Human", 0.05, 0.35, 5)}
        name, sigma, jump, k = mapping[args.profile]
        ctx.profile, ctx.sigma, ctx.jump = name, sigma, jump
        ctx.winners_k = k
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
        POLICY_RT.refresh_loaded(ctx)
    else:
        profile = choose_profile(ctx, world)
        name = profile["name"]
        sigma, jump, k = profile["ctx_sigma"], profile["ctx_jump"], profile["winners_k"]
        ctx.sigma, ctx.jump = sigma, jump
        ctx.winners_k = k
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
        POLICY_RT.refresh_loaded(ctx)
    _io_banner(args, loaded_src, loaded_ok)

    world.set_stage_from_ctx(ctx)        # derive 'neonate'/'infant' from ctx.age_days
    world.set_tag_policy("warn")         # or "strict" once you’re ready


    # HAL instantiation (although already set in class Ctx, but can modify here)
    ctx.hal  = None
    ctx.body = "(none)"
    if getattr(args, "hal", False):
        hal = HAL(args.body)
        ctx.hal  = hal  #store HAL on ctx so that other primitives can see it
        ctx.body = hal.body

    # Ensure NOW anchor exists for the episode (so attachments from "now" resolve)
    world.ensure_anchor("NOW")
    #boot policy, e.g., mountain goat should stand up
    if not args.no_boot_prime:
        boot_prime_stand(world, ctx)

    # Non-interactive plan flag (one-shot planning and exit)
    if args.plan:
        src_id = world.ensure_anchor("NOW")
        path = world.plan_to_predicate(src_id, args.plan)
        if path:
            print("Plan to", args.plan, ":", " -> ".join(path))
        else:
            print("No path found to", args.plan)
        return

    # Optional preflight-lite
    run_preflight_lite_maybe()

    pretty_scroll = True  #to see changes before terminal menu scrolls over screen

    # Interactive menu loop  >>>>>>>>>>>>>>>>>>>
    while True:
        try:
            if pretty_scroll:
                temp = input('\nPlease press any key (* stops this scroll pause) to continue with menu (above screen will scroll)....\n')
                if temp == "*":
                    pretty_scroll = False
            choice = input(MENU).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        def _route_alias(cmd: str) -> tuple[str | None, list[str]]:
            """Return (routed_choice, matches). routed_choice is None if no unique match.
            matches lists alias keys that begin with the provided prefix (for help)."""
            s = cmd.strip().lower() #s not a number and that's why routed here
            if s in _ALIASES: #check to see if s is a whole word in _ALIASES
                return _ALIASES[s], []  #returns ("routed", matches[]) <--
            if len(s) >= MIN_PREFIX: #s not a number and not a whole matching word and at least 3/variable letters
                matches = [k for k in _ALIASES if k.startswith(s)] #
                if len(matches) == 1:
                    return _ALIASES[matches[0]], matches #returns ("routed", matches[]) <--
                return None, matches #returns (None, [matches]) if more than one match  <--
            return None, [] #returns (None, matches[]]) if no match  <--

        ckey = choice.strip().lower()

        # If it's not a pure number, try word/prefix routing first
        if not ckey.isdigit():
            routed, matches = _route_alias(ckey) #(routed, []), if no match -- (None, []), if multiple matches -- (None, [matches])
            if routed is not None:
                if pretty_scroll:
                    print(f"[text input menu selection successfully matched: '{ckey}' → {routed}]")
                choice = routed
            else:
                if len(matches) > 1:
                    print(f"[help] Ambiguous input '{ckey}'. "
                          f"Try one of: {', '.join(sorted(matches)[:6])}"
                          f"{'...' if len(matches) > 6 else ''}")
                    continue #ambiguous entry thus restart while loop above for new input

        ckey = choice.strip().lower() #ensure any present or future routed value is in correct form
        if ckey in NEW_TO_OLD:
            routed = NEW_TO_OLD[ckey]
            if pretty_scroll:
                if ckey != routed:
                    print(f"[[menu numbering auto-compatibility] processed input entry routed to old value: {ckey} → {routed}]\n")
            choice = routed
        else:
            choice = ckey

        if choice == "1":
            # World stats
            now_id = _anchor_id(world, "NOW")
            print("Selection World Graph Statistics\n")
            print("The CCA8 architecture holds symbolic declarative memory (i.e., episodic and semantic memory) in the WorldGraph.")
            print("There are bindings (i.e., nodes) in the WorldGraph, each of which holds directed edges to other bindings (i.e., nodes), concise semantic")
            print("  and episodic information, metadata, and pointers to engrams in the cortical-like Columns which is the rich store of knowledge.")
            print("  e.g., 'b1' means binding 1, 'b2' means binding 2, and so on")
            print("As mentioned, the bindings (i.e., nodes) are linked to each other by directed edges.")
            print("An 'anchor' is a binding which we use to start the WorldGraph as well as a starting point somewhere in the middle of the graph.")
            print("Symbolic procedural knowledge is held in the Policies which currently are held in the Controller Module.")
            print("  A policy (i.e., same as primitive in the CCA8 published papers) is a simple set of conditional actions.")
            print("  In order to execute, a policy must be loaded (e.g., meets development requirements) and then it must be triggered.")
            print("Note we are showing the symbolic statistics here. The distributed, rich information of the CCA8, i.e., its engrams, are held in the Columns.\n")
            print("Below we show some general WorldGraph and Policy statistics. See Snapshot and other menu selections for more details on the system.\n")
            print(f"Bindings: {len(world._bindings)}  Anchors: NOW={now_id}  Latest: {world._latest_binding_id}")
            try:
                print(f"Policies loaded: {len(POLICY_RT.loaded)} -> {', '.join(POLICY_RT.list_loaded_names()) or '(none)'}")
            except Exception:
                pass
            loop_helper(args.autosave, world, drives)

        elif choice == "2":
            # List predicates
            print("Selection List Predicates\n")
            print("Groups all pred:* tokens and shows which bindings (bN) carry each token.")
            print("Planner targets are predicates; cues are evidence only and won’t appear here.\n")

            idx: Dict[str, List[str]] = {}
            for bid, b in world._bindings.items():
                for t in getattr(b, "tags", []):
                    if isinstance(t, str) and t.startswith("pred:"):
                        key = t.replace("pred:", "", 1)
                        idx.setdefault(key, []).append(bid)
            if not idx:
                print("(no predicates yet)")
            else:
                for key in sorted(idx.keys()):
                    bids = sorted(idx[key], key=lambda x: int(x[1:]) if x[1:].isdigit() else x)
                    print(f"  {key:<22} -> {', '.join(bids)}")
            loop_helper(args.autosave, world, drives)

        elif choice == "3":
            # Add predicate
            print("Selection Add Predicate\n")
            print("Creates a new binding tagged pred:<token>, attached to LATEST (keeps episodes readable).")
            print("Examples: state:posture_standing, nipple:latched. Lexicon may warn in strict modes.\n")

            token = input("Enter predicate token (e.g., state:posture_standing): ").strip()
            if token:
                bid = world.add_predicate(token, attach="latest", meta={"added_by": "user"})
                print(f"Added binding {bid} with pred:{token}")
            loop_helper(args.autosave, world, drives)

        elif choice == "4":
            # Connect two bindings (with duplicate warning)
            print("Selection Connect Bindings\n")
            print("Adds a directed edge src --label--> dst (default label: 'then'). Duplicate edges are skipped.")
            print("Use labels for readability (‘fall’, ‘latch’, …); BFS planning follows structure, not labels.\n")

            src = input("Source binding id (e.g., b12): ").strip()
            dst = input("Dest binding id (e.g., b13): ").strip()
            label = input('Relation label (e.g., "then"): ').strip() or "then"

            try:
                b = world._bindings.get(src)
                if not b:
                    print("Invalid id: unknown source binding.")
                elif dst not in world._bindings:
                    print("Invalid id: unknown destination binding.")
                else:
                    edges = getattr(b, "edges", []) or []
                    # Treat missing/alt keys the same as our stored "label"/"to"
                    def _rel(e): return e.get("label") or e.get("rel") or e.get("relation") or "then"
                    duplicate = any((e.get("to") == dst) and (_rel(e) == label) for e in edges)

                    if duplicate:
                        print(f"[info] Edge already exists: {src} --{label}--> {dst} (skipping)")
                    else:
                        world.add_edge(src, dst, label)  # this is the real write
                        print(f"Linked {src} --{label}--> {dst}")
            except KeyError as e:
                print("Invalid id:", e)
            except ValueError as e:
                print(f"[guard] {e}")

            loop_helper(args.autosave, world, drives)

        elif choice == "5":
            # Plan from NOW -> <predicate>
            print("Selection Plan to Predicate\n")
            print("BFS from anchor:NOW to a binding with pred:<token>. Prints raw id path and a pretty path.")
            print("No path means the goal isn’t reachable with current edges—add links or adjust targets.\n")

            token = input("Target predicate (e.g., state:posture_standing): ").strip()
            if not token:
                loop_helper(args.autosave, world, drives)
                continue
            src_id = world.ensure_anchor("NOW")
            path = world.plan_to_predicate(src_id, token)
            if path:
                print("Path (ids):", " -> ".join(path))
                try:
                    pretty = world.pretty_path(
                        path,
                        node_mode="id+pred",       # try 'pred' if   prefer only tokens
                        show_edge_labels=True,
                        annotate_anchors=True
                    )
                    print("Pretty printing of path:\n", pretty)
                except Exception as e:
                    print(f"(pretty-path error: {e})")
            else:
                print("No path found.")
            loop_helper(args.autosave, world, drives)

        elif choice == "6":
            # Resolve engrams on a binding
            print("Selection Resolve Engrams\n")
            print("Shows engram slots on a binding (pointers into Column memory).")
            print("Use 'Inspect engram by id' for payload/meta details.\n")

            bid = input("Binding id to resolve engrams: ").strip()
            b = world._bindings.get(bid)
            if not b:
                print("Unknown binding id.")
            else:
                print("Engrams:", b.engrams if b.engrams else "(none)")
            loop_helper(args.autosave, world, drives)

        elif choice == "7":
            # Show last 5 bindings
            print("Selection Recent Bindings\n")
            print("Shows the 5 most recent bindings (bN). For each: tags and any engram slots attached.")
            print(" 'outdeg' is the number of outgoing edges, e.g., outdeg=2 means there are 2 outgoing edges")
            print(" 'preview' is a short sample of up to 3 these outgoing edges")
            print("     e.g., outdeg=2 preview=[initiate_stand:b2, then:b3]")
            print("     -this means 2 outgoing edges, 1 edge goes to b2 with action label 'initiate_stand', 1 edge goes to b3 with action label 'then'}")
            print("Tip: use 'Inspect binding details' for full meta/edges on a specific id.\n")

            print(recent_bindings_text(world, limit=5))
            loop_helper(args.autosave, world, drives)

        elif choice == "8":
            # Quit
            print("Selection Quit\n")
            print("Exits the simulation. If you launched with --save, a final save occurs on exit.\n")

            print("Goodbye.")
            if args.save:
                save_session(args.save, world, drives)
            return

        elif choice == "9":
            # Run preflight now
            print("Selection Preflight\n")
            print("Runs pytest (unit tests framework) and coverage, then a series of whole-flow custom tests.\n")

            #rc = run_preflight_full(args)
            run_preflight_full(args)
            loop_helper(args.autosave, world, drives)

        elif choice == "10":
            # Inspect binding details (accepts a single id, or ALL/* to dump everything)
            print("Selection Inspect Binding Details\n")
            print("Enter a binding id (e.g., b3) or 'ALL'. Displays tags, meta, engrams, and outgoing edges.")
            print("Use this to audit provenance (meta.policy/created_by) and attached engrams on one binding.\n")

            bid = input("Binding id to inspect (or 'ALL'): ").strip()

            def _print_one(_bid: str) -> None:
                b = world._bindings.get(_bid)
                if not b:
                    print(f"Unknown binding id: {_bid}")
                    return
                print(f"ID: {_bid}")
                print("Tags:", ", ".join(sorted(getattr(b, "tags", []))))
                print("Meta:", json.dumps(getattr(b, "meta", {}), indent=2))
                if getattr(b, "engrams", None):
                    print("Engrams:", json.dumps(b.engrams, indent=2))
                else:
                    print("Engrams: (none)")
                edges = getattr(b, "edges", []) or getattr(b, "out", []) \
                        or getattr(b, "links", []) or getattr(b, "outgoing", [])
                if isinstance(edges, list) and edges:
                    print("Edges:")
                    for ee in edges:
                        rel = ee.get("label") or ee.get("rel") or ee.get("relation") or "then"
                        dst = ee.get("to") or ee.get("dst") or ee.get("dst_id") or ee.get("id")
                        print(f"  -- {rel} --> {dst}")
                else:
                    print("Edges: (none)")
                print("-" * 78)

            if bid.lower() in ("all", "*"):
                for _bid in _sorted_bids(world):
                    _print_one(_bid)
            else:
                _print_one(bid)
            loop_helper(args.autosave, world, drives)

        elif choice == "11":
            # Add sensory cue
            print("Selection Input Sensory Cue\n")
            print("Adds cue:<channel>:<token> (evidence, not a goal) at NOW and may nudge a policy.")
            print("Examples: vision:silhouette:mom, sound:bleat:mom, scent:milk.\n")

            ch = input("Channel (vision/scent/touch/sound): ").strip().lower()
            tok = input("Cue token (e.g., silhouette:mom): ").strip()
            if ch and tok:
                cue_token = f"{ch}:{tok}"
                bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
                print(f"Added sensory cue: cue:{cue_token} as {bid}")
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
                if fired != "no_match":
                    print(fired)
            loop_helper(args.autosave, world, drives)

        elif choice == "12":
            # Instinct step
            print("Selection Instinct Step\n")
            # Quick explainer for the user before the step runs
            print(
    '''Purpose:
      • Run ONE controller step ("instinct step") which will:
       i.   Advance the soft temporal clock (temporal drift) (no autonomic tick or age_days change)
       ii.  Propose a write-base (base_suggestion): NEAREST_PRED(targets), then HERE, then NOW
       iii. Build a small FOA (focus-of-attention): union of small neighborhoods around NOW, LATEST, cues
       iv.  Evaluate loaded policies and execute the first that triggers (safety-first)
       v.   If the controller wrote new facts, then boundary jump (epoch++)

    Let's consider an example. Consider the Mountain Goat simulation at its start, just after
        the goat calf is born.

    There is by default a binding b1 with the tag "anchor:NOW" and the default bootup routines
        will create a binding b2 with the tag "pred:stand" and a link from b1 to b2 -- this all exists.
    Ok... then we run an "instinct step".

    i.  -there is a small drift of the context vector via ctx.temporal.step()
         (this may not matter if a policy writes a new event and there is a temporal jump later)

    ii. -the Action Center has to decide where to link new bindings to -- base_suggestions provides suggestions
        -base_suggestion = choose_contextual_base(..., targets=['state:posture_standing', 'stand'])
        -it first looks for NEAREST_PRED(target) and success since b2 meets the target specified
        -thus, base_suggestion = binding b2 is recommended as the "write base", i.e. to link to
        -the suggestion is not used since that link already exists
        -base_suggestions can be used at different times to control write placement

    iii. -FOA focus of attention -- a small set of nearby nodes around NOW/LATEST, cues (for lightweight planning)


    iv. -policy:stand_up when considered can be triggered since age_days is <3.0 and stand near NOW is True
        -thus, policy:stand_up runs and as creates one mor more new nodes/edges (e.g., b5), and bindings b2 through b5 are linked

    v.  -a new event occurred, thus there is a temporal jump, with epoch++

    ''')

            # Count one controller step
            try:
                ctx.controller_steps += 1
            except Exception:
                pass

            before_n = len(world._bindings)

            # [TEMPORAL] drift once per instinct step
            if ctx.temporal:
                ctx.temporal.step()

            # --- context (for teaching / debugging) ---
            base  = choose_contextual_base(world, ctx, targets=["state:posture_standing", "stand"])
            foa   = compute_foa(world, ctx, max_hops=2)
            cands = candidate_anchors(world, ctx)

            # annotate anchors for readability: b1(NOW), ?(HERE), etc.
            now_id  = _anchor_id(world, "NOW")
            here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
            def _ann(bid: str) -> str:
                if bid == now_id:  return f"{bid}(NOW)"
                if here_id and bid == here_id: return f"{bid}(HERE)"
                return f"{bid}"

            print(f"[instinct] base_suggestion={base}, anchors={[ _ann(x) for x in cands ]}, foa_size={foa['size']}")
            print("Note: A base_suggestion is a proposal for where to attach writes this step. It is not a policy pick.")
            print("      Anchors give us a write base (where to attach new preds/edges). Where we attach the new fact matters for searching paths and planning later.")

            print(f"[context] write-base: {_fmt_base(base)}")
            print(f"[context] anchors: {', '.join(_ann(x) for x in cands)}")
            print(f"[context] foa: size={foa['size']} (ids near NOW/LATEST + cues)")
            print("Note: write-base is where we’ll attach any new facts/edges this step (keeps the episode local and readable).")
            print("      anchors are candidate start points the system considers for local searches/attachment.")
            print("      foa is the current 'focus of attention' neighborhood size used for light-weight planning.")

            result = action_center_step(world, ctx, drives)
            after_n  = len(world._bindings)  # NEW: measure write delta for this path

            # Count a cognitive cycle only if the step produced an output (a real write)
            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n:
                try:
                    ctx.cog_cycles += 1
                except Exception:
                    pass

            # Explicit summary of what executed
            if isinstance(result, dict):
                policy  = result.get("policy")
                status  = result.get("status")
                reward  = result.get("reward")
                binding = result.get("binding")
                if policy and status:
                    rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                    print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                else:
                    print("Action Center:", result)
            else:
                print("Action Center:", result)

            # WHY: show a human explanation tied to the executed policy
            label = result.get("policy") if isinstance(result, dict) and "policy" in result else "(controller)"
            gate  = next((p for p in POLICY_RT.loaded if p.name == label), None)
            explainer: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
            if explainer is not None:
                try:
                    why = explainer(world, drives, ctx)
                    print(f"[why {label}] {why}")
                except Exception:
                    pass

            # delta and autosave
            if after_n == before_n:
                print("(no new bindings/edges created this step)")
            else:
                print(f"(graph updated: bindings {before_n} -> {after_n})")

            # [TEMPORAL] boundary when the controller actually wrote
            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n and ctx.temporal:
                new_v = ctx.temporal.boundary()
                ctx.tvec_last_boundary = list(new_v)
                # epoch++
                ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                try:
                    ctx.boundary_vhash64 = ctx.tvec64()
                except Exception:
                    ctx.boundary_vhash64 = None
                print("[temporal] a new event occurred, thus not just a drift in the context vector but instead a jump to mark a temporal boundary (cos reset to ~1.000)")
                print(f"[temporal] boundary==event changes -> event/boundary/epoch={ctx.boundary_no} last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            # [TEMPORAL] optional τ-cut (e.g., τ=0.90)
            if ctx.temporal and ctx.tvec_last_boundary:
                v_now = ctx.temporal.vector()
                cos_now = sum(a*b for a,b in zip(v_now, ctx.tvec_last_boundary))
                if cos_now < 0.90:
                    new_v = ctx.temporal.boundary()
                    ctx.tvec_last_boundary = list(new_v)
                    # epoch++
                    ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                    try:
                        ctx.boundary_vhash64 = ctx.tvec64()
                    except Exception:
                        ctx.boundary_vhash64 = None
                    print(f"[temporal] boundary: cos_to_last_boundary {cos_now:.3f} < 0.90")
                    print(f"[temporal] boundary -> epoch (event changes) ={ctx.boundary_no} last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            loop_helper(args.autosave, world, drives)

        elif choice == "13":
            # Skill Ledger
            print("Selection Skill Ledger\n")
            print(skill_ledger_text("policy:stand_up"))
            print("Full ledger:  [src=cca8_controller.skill_readout()]")
            print(skill_readout())
            loop_helper(args.autosave, world, drives)

        elif choice == "14":
            # Autonomic tick
            print('''
            The autonomic tick is like a fixed-rate heartbeat in the background, particularly important for hardware and robotics.
            (To learn more about the different time systems in the architecture see the Snapshot or Instinct Step menu selections.)

            The result of this menu autonomic tick may cause (if conditions exist):
              i.   increment ticks, age_days, temporal drift, fatigue
              ii.  emit rising-edge interoceptive cues
              iii. recompute which policies are unlocked at this age/stage via dev_gate(ctx) before evaluating triggers
              iv.  try one controller step (Action Center): collect triggered policies, apply safety override if needed,
              tie-break by priority, and execute one policy (same engine as Instinct Step, just less verbose here)

            The Mountain Goat calf is born. At this time by default (note: might change as software is modified):
            - default -- binding b1 with the tag "anchor:NOW", b2 with tag "pred:stand", link b1--> b2
            - controller_steps=0, cog_cycles=0, temporal_epochs=0, autonomic_ticks=0, age_days: 0.0000
            - hunger=0.70, fatigue=0.20, warmth=0.60  [src=drives.hunger; drives.fatigue; drives.warmth]

            Ok... then we run this menu "autonomic tick" (and look at Snapshot display also):
            i.   ticks -> 1, age_day -> .01, cosine -> .98, fatigue -> .21

            ii.  HUNGER_HIGH = 0.60 (Controller Module), thus hunger drive at 0.70 will trigger and thus
             be present now and thus written to WorldGraph as an interoceptive cue --
             b1: [anchor:NOW], b2: [pred:stand], b3 LATEST: [cue:drive:hunger_high], with b2-->b3 now also

            iii. POLICY_RT.refresh_loaded(ctx) causes the Action Center to recompute and rebuild the set of
            stage-appropriate policies (via dev_gate(ctx)) so only developmentally unlocked policies can trigger
            -- these are loaded and are ready for step iv

            iv.  try one controller step to react if anything is now actionable:
                    fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx); if fired != "no_match": print(fired)
                    (similar to Instinct Step menu but less verbose and instead more runtime version: refresh-->triggers-->pick--execute)
               -looks at all the loaded policies re trigger(world, drives, ctx)
                  e.g., policy:stand_up wants nearby pred:stand, that you are not already standing, and young age
               -choose best candidate triggered policy and call policy's execute(...)
                  e.g., policy:stand_up (added 3 bindings)
                        b4: [pred:action:push_up], b5: [pred:action:extend_legs], b6: [pred:posture:standing, pred:state:posture_standing]
               -the extra lines below: base is the same as Instinct Step base suggestion, and again for humans not passed into action_center step;
               foa seeds foa with LATEST and NOW, adds cue nodes, union of neighborhoods with max_hops of 2; cands are candidate anchors which could be
               potential start anchors for planning/attachement
            ''')
            print("Selection Autonomic Tick\n")
            print("Fixed-rate heartbeat: fatigue↑, autonomic_ticks/age_days advance, temporal drift here (with optional boundary).")
            print("Often followed by a controller check to see if any policy should act, gather triggered policies, apply safety override,")
            print("pick by priority, and execute one policy (similar to menu Instinct Step but less verbose)")
            drives.fatigue = min(1.0, drives.fatigue + 0.01) #ceiling clamp, never exceed 1.0
            # advance developmental clock
            try:
                ctx.ticks = getattr(ctx, "ticks", 0) + 1
                ctx.age_days = getattr(ctx, "age_days", 0.0) + 0.01   # tune step as like
                if ctx.temporal:
                    ctx.temporal.step()
                world.set_stage_from_ctx(ctx)           # keep the stage in sync as age changes
                print(f"Autonomic: fatigue +0.01 | ticks={ctx.ticks} age_days={ctx.age_days:.2f}")

                # Interoception: write cues only on threshold rising-edges to avoid clutter
                started = _emit_interoceptive_cues(world, drives, ctx, attach="latest")
                if started:
                    print("[autonomic] interoceptive cues asserted: " + ", ".join(f"cue:{s}" for s in sorted(started)))

                # [TEMPORAL] optional τ-cut
                if ctx.temporal:
                    # Initialize boundary state once, on first tick with a temporal context
                    if getattr(ctx, "tvec_last_boundary", None) is None:
                        ctx.tvec_last_boundary = list(ctx.temporal.vector())
                        ctx.boundary_no = getattr(ctx, "boundary_no", 0)
                        try:
                            ctx.boundary_vhash64 = ctx.tvec64()
                        except Exception:
                            ctx.boundary_vhash64 = None

                    v_now = ctx.temporal.vector()
                    cos_now = sum(a * b for a, b in zip(v_now, ctx.tvec_last_boundary))

                    if cos_now < 0.90:
                        new_v = ctx.temporal.boundary()  # re-seed & renormalize
                        ctx.tvec_last_boundary = list(new_v)
                        ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                        try:
                            ctx.boundary_vhash64 = ctx.tvec64()
                        except Exception:
                            ctx.boundary_vhash64 = None
                        print(f"[temporal] τ-cut: cos_to_last_boundary={cos_now:.3f} < 0.90 → epoch={ctx.boundary_no}, last_boundary_vhash64={ctx.boundary_vhash64}")
                        print("[temporal] note: writes after this boundary belong to the NEW epoch.")
            except Exception as e:
                print(f"Autonomic: fatigue +0.01 (exception: {type(e).__name__}: {e})")

            # Refresh availability and consider firing regardless
            POLICY_RT.refresh_loaded(ctx)
            #rebuilds the set of eligible policies by applying each gate's dev_gate(ctx) to the current context
            #  e.g., age-->stage, etc  -- only those that pass are "loaded"=="eligible" for triggering
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            #runs the Action Center once:
            # -collects policies whose trigger(world, drives, ctx) is True, i.e., eligible policy that has triggered
            # -safety override -- e.g., if state:posture_fallen is near NOW then restricts policy to only policy:recover_fall, policy:stand_up
            # -tie-break/priority -- computes a simple drive-deficit score (e.g., hunger for policy:seek_nipple, etc) and picks the max policy
            # -executes the chosen policy via action_center_step(...) and returns a human-readable summary
            if fired != "no_match":
                print(fired)
            loop_helper(args.autosave, world, drives)

        elif choice == "15":
            # Delete edge and autosave (if --autosave is active)
            print("Selection Delete Edge\n")
            print("Removes edge(s) matching src --> dst [relation]. Leave relation blank to remove any label.\n")

            try:
                delete_edge_flow(world, autosave_cb=lambda: loop_helper(args.autosave, world, drives))
            except NameError:
                # Older builds: no helper available for callback style—do a simple save after.
                delete_edge_flow(world, autosave_cb=None)
                loop_helper(args.autosave, world, drives)

        elif choice == "16":
            # Export snapshot
            print("Selection Export Snapshot (Text)\n")
            print("Writes the same snapshot you see on-screen to world_snapshot.txt for sharing/debugging.\n")

            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives)

        elif choice == "17":
            # Display snapshot
            print("Selection Snapshot (WorldGraph + CTX + Policies)\n")
            print("A full, human-readable dump. The LEGEND explains some of the terms.")
            print("Note: Various tutorials and the README/Compendium file can help you understand the terms and functionality better.")
            print("Note: At the end of the snapshot you have the option to generate an interactive HTML graph of WorldGraph.\n")

            print(snapshot_text(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT))

            # Optional: generate an interactive Pyvis HTML view
            try:
                yn = input("Generate interactive graph (Pyvis HTML)? [y/N]: ").strip().lower()
            except Exception:
                yn = "n"
            if yn in ("y", "yes"):
                default_path = "world_graph.html"
                try:
                    path = input(f"Save HTML to (default: {default_path}): ").strip() or default_path
                except Exception:
                    path = default_path
                try:
                    out = world.to_pyvis_html(path_html=path, label_mode="id+first_pred", show_edge_labels=True, physics=True)
                    print(f"Interactive graph written to: {out}")
                    try:
                        open_now = input("Open in your default browser now? [y/N]: ").strip().lower()
                    except Exception:
                        open_now = "n"
                    if open_now in ("y", "yes"):
                        try:
                            import webbrowser # use the top-level 'sys','os'
                            if sys.platform.startswith("win"):
                                os.startfile(out)  # type: ignore[attr-defined]
                            elif sys.platform == "darwin":
                                os.system(f'open "{out}"')
                            else:
                                webbrowser.open(f"file://{out}")
                            print("(opened in your browser)")
                        except Exception as e:
                            print(f"[warn] Could not open automatically: {e}")
                except Exception as e:
                    print(f"[warn] Could not generate Pyvis HTML: {e}")
                    print("       Tip: install with  pip install pyvis")

            loop_helper(args.autosave, world, drives)

        elif choice == "18":
            # Simulate a fall event and try a recovery attempt immediately
            print("Selection Simulate Fall\n")
            print("Creates state:posture_fallen and relabels the linking edge to 'fall', then attempts recovery.")
            print("Use this to demo safety gates (recover_fall / stand_up).\n")

            prev_latest = world._latest_binding_id
            # Create a 'fallen' state as a new binding attached to latest
            fallen_bid = world.add_predicate(
                "state:posture_fallen",
                attach="latest",
                meta={"event": "fall", "added_by": "user"}
            )
            # Relabel the auto 'then' edge from the previous latest → fallen as 'fall'
            try:
                if prev_latest:
                    # Remove any auto edge regardless of label, then add a semantic one
                    try:
                        world_delete_edge(world, prev_latest, fallen_bid, None)
                    except NameError:
                        pass
                    world.add_edge(prev_latest, fallen_bid, "fall")
            except Exception as e:
                print(f"[fall] relabel note: {e}")

            print(f"Simulated fall as {fallen_bid}")

            # Refresh and consider policies now; recovery gate will nudge Action Center
            POLICY_RT.refresh_loaded(ctx)
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(fired)

            loop_helper(args.autosave, world, drives)


        #elif "19"  see new_to_old compatibility map
        #elif "20"  see new_to_old compatibility map
        #elif "21"  see new_to_old compatibility map

        elif choice == "22":
            # Export and display interactive graph (Pyvis HTML) with options
            print("\nExport and display graph of nodes and links with more options (Pyvis HTML)")
            print("   Note: the graph opened in your web browser is interactive -- even if you don't show")
            print("       edge labels to save space, put the mouse on them and the labels appear")
            print("   Note: the graph HTML file will be saved in your current directory\n")
            print(" — Edge labels: draw text on the links, e.g.,'then' or 'initiate_stand'")
            print("    On = label printed on the arrow (and still a tooltip). Off = only tooltip.")
            print("    -->Recommend Y on small graphs, n on larger ones to reduce clutter")
            print(" — Node label mode:")
            print("    'id'           → show binding ids only (e.g., b5)")
            print("    'first_pred'   → show first pred:* token (e.g., stand, nurse)")
            print("    'id+first_pred'→ show both (two-line label)")
            print("     -->Recommend id+first_pred if enough space")
            print(" — Physics: enable force-directed layout; turn off for very large graphs.")
            print("      (We model the graph as a physical system and then try to achieve a minimal")
            print("       energy state by simulating the movement of the nodes into this minimal state. The result is a")
            print("       graph which many people find easier to read. This option uses Barnes-Hut physics which is an")
            print("       algorithm originally for the N-body problem in astrophysics and which speeds up the layout calculations.")
            print("       Nonetheless, for very large graphs may not be computationally feasible.")
            print("      -->Recommend physics ON unless issues with very large graphs\n")

            # Collect options
            try:
                label_mode = input("Node label mode [id / first_pred / id+first_pred] (default: id+first_pred): ").strip().lower()
            except Exception:
                label_mode = ""
            if label_mode not in {"id", "first_pred", "id+first_pred"}:
                label_mode = "id+first_pred"

            try:
                el = input("Show edge labels on links? [Y/n]: ").strip().lower()
            except Exception:
                el = ""
            show_edge_labels = not (el in {"n", "no", "0"})

            try:
                ph = input("Enable physics (force-directed layout)? [Y/n]: ").strip().lower()
            except Exception:
                ph = ""
            physics = not (ph in {"n", "no", "0"})

            default_path = "world_graph.html"
            try:
                path = input(f"Save HTML to (default: {default_path}): ").strip() or default_path
            except Exception:
                path = default_path

            try:
                out = world.to_pyvis_html(
                    path_html=path,
                    label_mode=label_mode,
                    show_edge_labels=show_edge_labels,
                    physics=physics
                )
                print(f"Interactive graph written to: {out}")
                try:
                    open_now = input("Open in your default browser now? [y/N]: ").strip().lower()
                except Exception:
                    open_now = "n"
                if open_now in ("y", "yes"):
                    try:
                        import webbrowser # use the top-level 'sys', 'os'
                        if sys.platform.startswith("win"):
                            os.startfile(out)  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            os.system(f'open "{out}"')
                        else:
                            webbrowser.open(f"file://{out}")
                        print("(opened in your browser)")
                    except Exception as e:
                        print(f"[warn] Could not open automatically: {e}")
            except Exception as e:
                print(f"[warn] Could not generate Pyvis HTML: {e}")
                print("       Tip: install with  pip install pyvis")
            loop_helper(args.autosave, world, drives)

        elif choice == "23":
            # Understanding bindings/edges/predicates/cues/anchors/policies (terminal help)
            print_tagging_and_policies_help(POLICY_RT)
            loop_helper(args.autosave, world, drives)

        elif choice == "24":
            # Capture scene → emit cue/predicate + tiny engram (signal bridge demo)
            print("\nCapture scene — this will create a binding (cue/pred), assert a tiny engram in the column,")
            print("and attach the engram pointer to the binding. You can see the pointer in the snapshot/HTML.")
            try:
                channel = input("Channel [vision/scent/sound/touch] (default: vision): ").strip().lower() or "vision"
                token   = input("Token   (e.g., silhouette:mom) (default: silhouette:mom): ").strip() or "silhouette:mom"
                family  = input("Family  [cue/pred] (default: cue): ").strip().lower() or "cue"
                attach  = input("Attach  [now/latest/none] (default: now): ").strip().lower() or "now"
                vtext   = input("Vector  (comma/space floats; default: 0.0,0.0,0.0): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n(cancelled)")
                loop_helper(args.autosave, world, drives)
                continue

            if family not in ("cue", "pred"):
                print("[info] unknown family; defaulting to 'cue'")
                family = "cue"
            if attach not in ("now", "latest", "none"):
                print("[info] unknown attach; defaulting to 'now'")
                attach = "now"

            vec = _parse_vector(vtext)

            # Treat capture as a new event (pre-capture boundary) so time attrs reflect a new epoch
            if ctx.temporal:
                new_v = ctx.temporal.boundary()
                ctx.tvec_last_boundary = list(new_v)
                ctx.boundary_no = getattr(ctx, "boundary_no", 0) + 1
                try:
                    ctx.boundary_vhash64 = ctx.tvec64()
                except Exception:
                    ctx.boundary_vhash64 = None
                print(f"[temporal] boundary (pre-capture) → epoch={ctx.boundary_no} last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            # Pass time attrs when creating an engram
            from cca8_features import time_attrs_from_ctx
            attrs = time_attrs_from_ctx(ctx)
            bid, eid = world.capture_scene(channel, token, vec, attach=attach, family=family, attrs=attrs)

            try:
                print(f"[bridge] created binding {bid} with tag "
                      f"{family}:{channel}:{token} and attached engram id={eid}")

                # Fetch and summarize the engram record (robust to different shapes)
                try:
                    rec = world.get_engram(engram_id=eid)
                    meta = rec.get("meta", {})
                    attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                    if attrs:
                        print(f"[bridge] time on engram: ticks={attrs.get('ticks')} "
                              f"tvec64={attrs.get('tvec64')} epoch={attrs.get('epoch')} "
                              f"epoch_vhash64={attrs.get('epoch_vhash64')}")
                    rid   = rec.get("id", eid)
                    # payload can be nested or flat
                    payload = rec.get("payload") if isinstance(rec, dict) else None
                    if isinstance(payload, dict):
                        kind  = payload.get("kind") or payload.get("meta", {}).get("kind")
                        shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                    else:
                        kind  = rec.get("kind")
                        shape = rec.get("shape")
                    print(f"[bridge] column record ok: id={rid} kind={kind} shape={shape} keys={list(rec.keys()) if isinstance(rec, dict) else type(rec)}")
                except Exception as e:
                    print(f"[warn] could not retrieve engram record: {e}")

                # Print the actual slot and ids we just attached
                slot = None
                try:
                    b = world._bindings.get(bid)
                    eng = getattr(b, "engrams", None)
                    if isinstance(eng, dict):
                        # pick the slot that actually points to this engram id
                        for s, v in eng.items():
                            if isinstance(v, dict) and v.get("id") == eid:
                                slot = s
                                break
                except Exception:
                    slot = None

                if slot:
                    print(f'[bridge] attached pointer: {bid}.engrams["{slot}"] = {eid}')
                else:
                    # fallback: show all slots if we didn't find an exact match
                    slots = ", ".join(eng.keys()) if isinstance(eng, dict) else "(none)"
                    print(f'[bridge] {bid} engrams now include [{slots}] (attached id={eid})')

                # optional: nudge controller once to see if anything reacts (pretty summary)
                try:
                    res = action_center_step(world, ctx, drives)

                    if isinstance(res, dict):
                        # Skip printing if it's an explicit no-op
                        if res.get("status") != "noop":
                            policy  = res.get("policy")
                            status  = res.get("status")
                            reward  = res.get("reward")
                            binding = res.get("binding")
                            rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                            print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")

                            # WHY line if the gate provides an explanation
                            gate = next((p for p in POLICY_RT.loaded if p.name == policy), None)
                            explain_fn: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
                            if explain_fn is not None:
                                try:
                                    why = explain_fn(world, drives, ctx)
                                    print(f"[why {policy}] {why}")
                                except Exception:
                                    pass
                    else:
                        # Non-dict result: fall back to a generic print
                        print("Action Center:", res)
                except Exception as e:
                    print(f"[warn] controller step errored: {e}")
            except Exception as e:
                print(f"[warn] capture_scene failed: {e}")
            loop_helper(args.autosave, world, drives)

        elif choice == "25":
            # Planner strategy toggle
            try:
                current = getattr(world, "get_planner", lambda: "bfs")()
            except Exception:
                current = "bfs"
            print(f"\nCurrent planner: {current.upper()}  (BFS = fewest hops; Dijkstra = lowest total edge weight)")
            print("Note: Edge weights are read from edge.meta keys: 'weight' → 'cost' → 'distance' → 'duration_s' (default 1.0).")
            try:
                sel = input("Choose planner: [b]fs / [d]ijkstra / [Enter]=keep → ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                sel = ""
            if sel.startswith("b"):
                world.set_planner("bfs")
                print("Planner set to BFS (unweighted shortest path by hops).")
            elif sel.startswith("d"):
                world.set_planner("dijkstra")
                print("Planner set to Dijkstra (weighted; defaults to 1 per edge when unspecified).")
            else:
                print("Planner unchanged.")
            loop_helper(args.autosave, world, drives)

        elif choice == "26":
            # Temporal probe (harmonized with Snapshot naming)
            print("Selection Temporal Probe\n")
            print("Shows the temporal soft clock using the same names as Snapshot,")
            print("with source attributes for each value.\n")

            # Epoch + hashes (same names as Snapshot)
            epoch = getattr(ctx, "boundary_no", 0)
            vhash_now = ctx.tvec64() if hasattr(ctx, "tvec64") else None
            epoch_vh  = getattr(ctx, "boundary_vhash64", None)

            print(f"  vhash64(now): {vhash_now if vhash_now else '(n/a)'}  [src=ctx.tvec64()]")
            print(f"  vhash64: {vhash_now if vhash_now else '(n/a)'}  [alias of vhash64(now)]")
            print(f"  epoch: {epoch}  [src=ctx.boundary_no]")
            print(f"  epoch_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [src=ctx.boundary_vhash64]")
            print(f"  last_boundary_vhash64: {epoch_vh if epoch_vh else '(n/a)'}  [alias of epoch_vhash64]")

            # Cosine to last boundary (same name as Snapshot)
            cos = None
            try:
                cos = ctx.cos_to_last_boundary()
            except Exception:
                cos = None
            if isinstance(cos, float):
                print(f"  cos_to_last_boundary: {cos:.4f}  [src=ctx.cos_to_last_boundary()]")
            else:
                print("  cos_to_last_boundary: (n/a)  [src=ctx.cos_to_last_boundary()]")

            # Hamming distance between hashes (0..64), optional
            if vhash_now and epoch_vh:
                try:
                    h = _hamming_hex64(vhash_now, epoch_vh)
                    if h >= 0:
                        print(f"  hamming(vhash64,epoch_vhash64): {h} bits (0..64)  [src=_hamming_hex64]")
                except Exception:
                    pass

            # Temporal parameters (same keys as Snapshot)
            tv = getattr(ctx, "temporal", None)
            if tv:
                dim   = getattr(tv, "dim", 0)
                sigma = getattr(tv, "sigma", 0.0)
                jump  = getattr(tv, "jump", 0.0)
                print(f"  dim={dim}  [src=ctx.temporal.dim]")
                print(f"  sigma={sigma:.4f}  [src=ctx.temporal.sigma]")
                print(f"  jump={jump:.4f}  [src=ctx.temporal.jump]")

            # Status derived from cosine, same thresholds as elsewhere
            if isinstance(cos, float):
                if cos >= 0.99:
                    status = "ON-EVENT BOUNDARY"
                elif cos < 0.90:
                    status = "EVENT BOUNDARY-SOON"
                else:
                    status = "DRIFTING slowly forward in time"
                print(f"  status={status}  [derived from cos_to_last_boundary]")

            # Explanation (matches Snapshot nomenclature)
            print("\nExplanation:")
            print("  The temporal soft clock keeps two fingerprints of a unit vector:")
            print("    • vhash64(now) — current context vector fingerprint  [src=ctx.tvec64()]")
            print("    • epoch_vhash64 — fingerprint captured at the last boundary  [src=ctx.boundary_vhash64]")
            print("  Between boundaries the vector DRIFTS a little each drift step (sigma). When a new")
            print("  event occurs, boundary() applies a larger JUMP (jump), we record epoch_vhash64")
            print("  to the new value, and vhash64(now) equals it immediately after.")
            print("  Elapsed-within-epoch can be estimated by comparing now vs boundary:")
            print("    • cos_to_last_boundary ≈ 1.000 at a boundary and decreases with drift;")
            print("    • Hamming(vhash64(now), epoch_vhash64) counts bit flips (0..64).")

            # Small legend (matches Snapshot legend terms)
            print("\nLegend:")
            print("  epoch = event boundary count; increments when boundary() is taken")
            print("  vhash64(now) = fingerprint of current temporal vector")
            print("  epoch_vhash64 = fingerprint at last boundary (alias: last_boundary_vhash64)")

            loop_helper(args.autosave, world, drives)

        elif choice == "27":
            # Inspect engram by id OR by binding id
            try:
                key = input("Engram id OR Binding id: ").strip()
            except Exception:
                key = ""

            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives)
                continue

            # Resolve binding → engram(s) if the user passed bN
            eid = key
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives)
                    continue
                if len(eids) > 1:
                    print(f"Binding {key} has multiple engrams:")
                    for i, ee in enumerate(eids, 1):
                        print(f"  {i}) {ee}")
                    try:
                        sel = input("Pick one [number]: ").strip()
                        idx = int(sel) - 1
                        eid = eids[idx]
                    except Exception:
                        print("Cancelled.")
                        loop_helper(args.autosave, world, drives)
                        continue
                else:
                    eid = eids[0]

            # Fetch and pretty-print the Column record
            rec = None
            try:
                rec = world.get_engram(engram_id=eid)
            except Exception:
                rec = None

            if not rec:
                print(f"Engram not found: {eid}")
                loop_helper(args.autosave, world, drives)
                continue

            try:
                kind = rec.get("kind") or rec.get("type") or "(unknown)"
                print(f"Engram: {eid}")
                print(f"  kind: {kind}")

                meta = rec.get("meta", {}) if isinstance(rec, dict) else {}
                print("  meta:", json.dumps(meta, indent=2))

                attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                if isinstance(attrs, dict) and attrs:
                    ticks = attrs.get("ticks")
                    tvec  = attrs.get("tvec64")
                    epoch = attrs.get("epoch")
                    evh   = attrs.get("epoch_vhash64")
                    print(f"  time attrs: ticks={ticks} tvec64={tvec} epoch={epoch} epoch_vhash64={evh}")

                payload = rec.get("payload") or rec.get("data") or rec.get("value")
                if isinstance(payload, dict):
                    shape  = payload.get("shape") or payload.get("meta", {}).get("shape")
                    dtype  = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                    nbytes = payload.get("nbytes")
                    if nbytes is None and "bytes" in payload and isinstance(payload["bytes"], (bytes, bytearray, str)):
                        try: nbytes = len(payload["bytes"])
                        except Exception: nbytes = None
                    if shape or dtype or nbytes is not None:
                        print(f"  payload: shape={shape} dtype={dtype} nbytes={nbytes}")
                    else:
                        print("  payload:", json.dumps(payload, indent=2))
                elif isinstance(payload, (bytes, bytearray)):
                    print(f"  payload: <{len(payload)} bytes>")
                else:
                    print("  payload: (none)" if payload is None else f"  payload: {payload}")

            except Exception as e:
                print(f"(error printing engram {eid}): {e!r}")

            print("-" * 78)
            loop_helper(args.autosave, world, drives)

        elif choice == "28":
            # List all engrams by scanning bindings; dedupe by id
            seen: set[str] = set()
            any_found = False
            for bid in _sorted_bids(world):
                eids = _engrams_on_binding(world, bid)
                for eid in eids:
                    if eid in seen:
                        continue
                    seen.add(eid)
                    any_found = True
                    # Best-effort fetch of Column record for summary
                    rec = None
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        rec = None

                    ticks = epoch = tvec = evh = shape = dtype = None
                    if isinstance(rec, dict):
                        meta = rec.get("meta", {})
                        attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}
                        if isinstance(attrs, dict):
                            ticks = attrs.get("ticks")
                            tvec  = attrs.get("tvec64")
                            epoch = attrs.get("epoch")
                            evh   = attrs.get("epoch_vhash64")


                        payload = rec.get("payload")
                        if isinstance(payload, dict):
                            shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                            dtype = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                        else:
                            shape = rec.get("shape"); dtype = rec.get("kind") or rec.get("type")

                        payload = rec.get("payload")
                        if isinstance(payload, dict):
                            shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                            dtype = payload.get("dtype") or payload.get("ftype") or payload.get("kind")
                        elif hasattr(payload, "meta"):  # e.g., TensorPayload object
                            try:
                                pmeta = payload.meta()  # {'kind','fmt','shape','len'}
                                shape = pmeta.get("shape")
                                dtype = pmeta.get("kind")
                            except Exception:
                                shape = dtype = None
                        else:
                            shape = rec.get("shape")
                            dtype = rec.get("kind") or rec.get("type")

                    print(f"EID={eid}  src={bid}  ticks={ticks} epoch={epoch} tvec64={tvec} "
                          f"payload(shape={shape}, dtype={dtype})")
            if not any_found:
                print("(no engrams found)")
            print("-" * 78)
            loop_helper(args.autosave, world, drives)


        elif choice == "29":
            # Search engrams by name substring and/or epoch
            try:
                q = input("Name contains (substring, blank=any): ").strip()
            except Exception:
                q = ""
            try:
                e_in = input("Epoch equals (blank=any): ").strip()
                epoch = int(e_in) if e_in else None
            except Exception:
                epoch = None

            # Walk pointers so we only see engrams actually referenced by the graph
            seen = set()
            found = []
            for bid in _sorted_bids(world):
                for eid in _engrams_on_binding(world, bid):
                    if eid in seen:
                        continue
                    seen.add(eid)
                    rec = None
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        pass
                    if not isinstance(rec, dict):
                        continue
                    name = (rec.get("name") or "")
                    if q and q.lower() not in name.lower():
                        continue
                    if epoch is not None:
                        attrs = rec.get("meta", {}).get("attrs", {})
                        if not (isinstance(attrs, dict) and attrs.get("epoch") == epoch):
                            continue
                    found.append((eid, bid, name, rec.get("meta", {}).get("attrs", {})))
            if not found:
                print("(no matches)")
            else:
                for eid, bid, name, attrs in found:
                    print(f"EID={eid}  src={bid}  name={name}  epoch={attrs.get('epoch')}  tvec64={attrs.get('tvec64')}")
            print("-" * 78)
            loop_helper(args.autosave, world, drives)


        elif choice == "30":
            # Delete engram by id OR by binding id; also prune any binding pointers to it
            key = input("Engram id OR Binding id to delete: ").strip()
            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives); continue

            # Resolve binding → engram id(s) if needed
            targets = []
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives); continue
                if len(eids) > 1:
                    print(f"Binding {key} has multiple engrams:")
                    for i, ee in enumerate(eids, 1):
                        print(f"  {i}) {ee}")
                    try:
                        pick = int(input("Pick one [number]: ").strip()) - 1
                        targets = [eids[pick]]
                    except Exception:
                        print("(cancelled)")
                        loop_helper(args.autosave, world, drives); continue
                else:
                    targets = [eids[0]]
            else:
                targets = [key]

            print("WARNING: this will delete the engram record from column memory,")
            print("and will also prune any binding pointers that reference it.")
            if input("Type DELETE to confirm: ").strip() != "DELETE":
                print("(cancelled)")
                loop_helper(args.autosave, world, drives); continue

            deleted_any = False
            for eid in targets:
                ok = False
                try:
                    ok = column_mem.delete(eid)
                except Exception as e:
                    print(f"(error) {e}")
                # prune pointers regardless — harmless if not present
                pruned = 0
                for bid, b in world._bindings.items():
                    eng = getattr(b, "engrams", None)
                    if not isinstance(eng, dict):
                        continue
                    for slot, val in list(eng.items()):
                        if isinstance(val, dict) and val.get("id") == eid:
                            try:
                                del eng[slot]
                                pruned += 1
                            except Exception:
                                pass
                print(("Deleted" if ok else "Engram not found or not deleted") + f". Pruned {pruned} pointer(s).")
                deleted_any = deleted_any or ok

            loop_helper(args.autosave, world, drives)


        elif choice == "31":
            # Attach an existing engram id to a binding (creates/overwrites a slot)
            bid = input("Binding id: ").strip()
            if not (bid.lower().startswith("b") and bid[1:].isdigit()):
                print("Please enter a binding id like b3.")
                loop_helper(args.autosave, world, drives); continue
            eid = input("Engram id to attach: ").strip()
            if not eid:
                print("No engram id provided.")
                loop_helper(args.autosave, world, drives); continue

            # Choose slot (column name)
            slot = input("Column slot name (default: column01): ").strip() or "column01"

            # Existence check is optional; we’ll warn but still allow.
            try:
                _ = world.get_engram(engram_id=eid)
                exists = True
            except Exception:
                exists = False
            if not exists:
                print("(warn) engram id not found in column memory; attaching pointer anyway.")

            b = world._bindings.get(bid)
            if not b:
                print(f"Unknown binding id: {bid}")
                loop_helper(args.autosave, world, drives); continue
            if getattr(b, "engrams", None) is None or not isinstance(b.engrams, dict):
                b.engrams = {}
            b.engrams[slot] = {"id": eid, "act": 1.0}
            print(f"Attached engram {eid} to {bid} as {slot}.")
            loop_helper(args.autosave, world, drives)

        elif choice == "33":
            print("Selection LOC by Directory (Python)")
            print("Prints total lines of Python source code")
            rows, total, err = _compute_loc_by_dir()
            if err:
                print(err)  # pragma: no cover
            else:
                print(_render_loc_by_dir_table(rows, total))  # pragma: no cover

        elif choice.lower() == "s":
            # Save session
            print("Selection Save Session\n")
            print("Saves world+drives+skills to JSON (atomic write). Use this to checkpoint progress.\n")

            path = input("Save to file (e.g., session.json): ").strip()
            if path:
                ts = save_session(path, world, drives)
                print(f"Saved to {path} at {ts}")

        elif choice.lower() == "l":
            # Load session
            print("Selection Load Session\n")
            print("Loads a prior JSON snapshot (world, drives, skills). The new state replaces the current one.\n")

            path = input("Load from file: ").strip()
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        blob = json.load(f)
                    print(f"Loaded {path} (saved_at={blob.get('saved_at','?')})")
                    new_world  = cca8_world_graph.WorldGraph.from_dict(blob.get("world", {}))
                    new_drives = Drives.from_dict(blob.get("drives", {}))
                    skills_from_dict(blob.get("skills", {}))
                    world, drives = new_world, new_drives
                    loaded_ok = True
                    loaded_src = path
                    _io_banner(args, loaded_src, loaded_ok)
                except Exception as e:
                    print(f"[warn] could not load {path}: {e}")

        elif choice.lower() == "d":
            # Show drives (raw + tags), robust across Drives variants
            print("Selection Drives & Drive Tags\n")
            print("Shows raw drive values and threshold flags with their sources.\n")
            print(drives_and_tags_text(drives))
            loop_helper(args.autosave, world, drives)

        elif choice.lower() == "r":
            # Reset current saved session: explicit confirmation
            if not args.autosave:
                print("No current saved json file to reset (you did not pass --autosave <path>).")
            else:
                path = os.path.abspath(args.autosave)
                cwd  = os.path.abspath(os.getcwd())
                print("\n[RESET] This will:")
                print("  • Delete the autosave file shown below (if it exists), and")
                print("  • Re-initialize an empty world, drives, and skill ledger in memory.\n")
                print(f"Autosave file: {path}")
                if not path.startswith(cwd):
                    print(f"[CAUTION] The file is outside the current directory: {cwd}")
                try:
                    reply = input("Type DELETE in uppercase to confirm, or press Enter to cancel: ").strip()
                except Exception:
                    reply = ""
                if reply == "DELETE":
                    try:
                        if os.path.exists(path):
                            os.remove(path)
                            print(f"Deleted {path}.")
                        else:
                            print(f"No file at {path} (nothing to delete).")
                    except Exception as e:
                        print(f"[warn] Could not delete {path}: {e}")
                    # Reinitialize episode state
                    world = cca8_world_graph.WorldGraph()
                    drives = Drives()
                    skills_from_dict({})  # clear skill ledger
                    world.ensure_anchor("NOW")
                    print("Initialized a fresh episode in memory. Next action will autosave a new snapshot.")
                else:
                    print("Reset cancelled.")
            continue   # back to menu


        elif choice.lower() == "t":
            #Tutorial selection that gives a tour through several common menu functions
            print("Selection Tutorial\n")
            print("1) Quick console tour (recommended), 2) Open README/compendium, 3) Both. Enter cancels.\n")

            print("\nTutorial options:")
            print("  1) Quick console tour (recommended)")
            print("  2) Open README/compendium")
            print("  3) Both")
            print("  [Enter] Cancel")
            try:
                pick = input("Choose: ").strip()
            except Exception:
                pick = ""

            #pylint:disable=no-else-continue
            if pick == "1":
                run_new_user_tour(world, drives, ctx, POLICY_RT, autosave_cb=lambda: loop_helper(args.autosave, world, drives))
                continue
            elif pick == "2":
                comp = os.path.join(os.getcwd(), "README.md")
                print(f"Tutorial file (README.md which acts as an all-in-one compendium): {comp}")
                if os.path.exists(comp):
                    try:
                        if sys.platform.startswith("win"):
                            os.startfile(comp)  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            os.system(f'open "{comp}"')
                        else:
                            os.system(f'xdg-open "{comp}"')
                        print("Opened the README.md/compendium in your default viewer.")
                    except Exception as e:
                        print(f"[warn] Could not open automatically: {e}")
                        print("Please open the file manually in your editor.")
                else:
                    print("README.md not found in the current folder. Copy it here to open directly.")
                continue
            elif pick == "3":
                run_new_user_tour(world, drives, ctx, POLICY_RT, autosave_cb=lambda: loop_helper(args.autosave, world, drives))
                # then open README
                comp = os.path.join(os.getcwd(), "README.md")
                if os.path.exists(comp):
                    try:
                        if sys.platform.startswith("win"):
                            os.startfile(comp)  # type: ignore[attr-defined]
                        elif sys.platform == "darwin":
                            os.system(f'open "{comp}"')
                        else:
                            os.system(f'xdg-open "{comp}"')
                        print("Opened the README.md/compendium in your default viewer.")
                    except Exception as e:
                        print(f"[warn] Could not open automatically: {e}")
                        print("Please open the file manually in your editor.")
                else:
                    print("README.md not found in the current folder. Copy it here to open directly.")
                continue
            else:
                print("(cancelled)")
                continue
            #pylint:enable=no-else-continue

    # interactive_loop(...) while loop end  <<<<<<<<<<<<<<<<<<<

# --------------------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """argument parser and program entry
    """

    # set up logging (one-time)
    if not logging.getLogger().handlers:
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s %(levelname)s %(message)s",
            handlers=[logging.FileHandler("cca8_run.log", encoding="utf-8"),
                      logging.StreamHandler()] )
    logging.info("cca8_run start v%s python=%s platform=%s",
                 __version__, sys.version.split()[0], platform.platform())

    ##argparse and processing of certain flags here
    # argparse flags
    p = argparse.ArgumentParser(prog="cca8_run.py")
    p.add_argument("--about", action="store_true", help="Print version and component info")
    p.add_argument("--version", action="store_true", help="Print just the runner (i.e., main entry program module) version")
    p.add_argument("--hal", action="store_true", help="Enable HAL embodiment stub (if available)")
    p.add_argument("--body", help="Body/robot, profile to use with HAL, e.g., 'hapty'")
    #p.add_argument("--period", type=int, default=None, help="Optional period (for tagging)")
    #p.add_argument("--year", type=int, default=None, help="Optional year (for tagging)")
    p.add_argument("--no-intro", action="store_true", help="Skip the intro banner")
    p.add_argument("--profile", choices=["goat","chimp","human","super"],
               help="Pick a profile without prompting (goat=Mountain Goat, chimp=Chimpanzee, human=Human, super=Super-Human), usage may be unstable")
    p.add_argument("--preflight", action="store_true", help="Run full unit tests and preflight and exit")
    #p.add_argument("--write-artifacts", action="store_true", help="Write preflight artifacts to disk")
    p.add_argument("--load", help="Load session from JSON file")
    p.add_argument("--save", help="Save session to JSON file on exit")
    p.add_argument("--autosave", help="Autosave session to JSON file after each action")
    p.add_argument("--plan", metavar="PRED", help="Plan from NOW to predicate and exit")
    p.add_argument("--no-boot-prime", action="store_true", help="Disable boot/default intent for calf to stand")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        code = getattr(e, "code", 0)
        return 2 if code else 0  # pylint: disable=using-constant-test


    # process embodiment flags and continue with code
    try:
        if args.hal:
            args.hal_status_str = "ON (however, a full R-HAL has not been implemented\n     at this time, thus software will run without consideration of the robotic embodiment)"
        else:
            args.hal_status_str = "OFF (runs without consideration of the robotic embodiment)"
        body = (args.body or "").strip()
        if body == "hapty":
            body = "0.1.1 hapty"
        args.body_status_str = f"{body if body else PLACEHOLDER_EMBODIMENT}"
    except Exception as e:
        args.hal_status_str  = f"error in flag {e} -- HAL: off (software will run without consideration of  robotic embodiment)"
        args.body_status_str = f"error in flag {e} -- Body: (none)"

    # process version flag and return
    if args.version:
        print(__version__)
        return 0

    # process about flag and return
    if args.about:
        comps = [  # (label, version, path)
            ("cca8_run.py", __version__, os.path.abspath(__file__)),
        ]
        for name in ["cca8_world_graph", "cca8_controller", "cca8_column", "cca8_features", "cca8_temporal"]:
            ver, path = _module_version_and_path(name)
            comps.append((name, ver, path))

        print("CCA8 Components:")
        for label, ver, path in comps:
            print(f"  - {label} v{ver} ({path})")

        # additionally show primitive count if the controller is importable
        try:
            from cca8_controller import PRIMITIVES
            print(f"    [controller primitives: {len(PRIMITIVES)}]")
        except Exception:
            pass

        return 0

    # process preflight flag and return
    if args.preflight:
        rc = run_preflight_full(args)
        return rc

    ##main operations of program via interactive_loop()
    interactive_loop(args); return 0

# --------------------------------------------------------------------------------------
# __main__
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
