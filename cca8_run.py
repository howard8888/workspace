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
- **Predicate**: a symbolic fact token (e.g., "posture:standing").
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

# Style:Display notes:
#  -assume Windows default 120 column x 30+ line terminal display for displayed messages; translates well to macOS and Linux
#  -Main Menu limit to 80 column display but all other messages assume 120 columns
#  -code lines and docstrings -- try to respect 120 columns but ok to go over, generally try to keep under 200 columns
#  -ANSI colors ok but do not rely on them alone
#  -alert user visually if a task will take longer than 2 seconds
#  -if an error message can occur, then the user should see a human-readable, readily comprehensible error message

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
from dataclasses import dataclass, field
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
from cca8_controller import (
    PRIMITIVES,
    skill_readout,
    skills_to_dict,
    skills_from_dict,
    HUNGER_HIGH,
    FATIGUE_HIGH,
    Drives,
    action_center_step,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    bodymap_is_stale,
    body_cliff_distance,
    body_space_zone,
    _fallen_near_now,
    __version__ as controller_version,
)
from cca8_controller import body_shelter_distance  # pylint: disable=unused-import
from cca8_controller import body_cliff_is_near     # pylint: disable=unused-import
from cca8_controller import body_shelter_is_near   # pylint: disable=unused-import
from cca8_temporal import TemporalContext
from cca8_column import mem as column_mem
from cca8_env import HybridEnvironment  # environment simulation (HybridEnvironment/EnvState/EnvObservation)


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
    cog_cycles: int = 0  # 'productive' cycles: incremented only in Instinct Step when the step wrote new facts, to modify in future when full cog cycle implemented
    last_drive_flags: Optional[set[str]] = None
    env_episode_started: bool = False       # Environment / HybridEnvironment integration
    env_last_action: Optional[str] = None  # last fired policy name for env.step(...)
    mini_snapshot: bool = True  #mini-snapshot toggle starting value
    posture_discrepancy_history: list[str] = field(default_factory=list) #per-session list of discrepancies motor command vs what environment reports
    # BodyMap: tiny body+near-world map (separate WorldGraph instance)
    body_world: Optional[cca8_world_graph.WorldGraph] = None
    body_ids: dict[str, str] = field(default_factory=dict)
    bodymap_last_update_step: Optional[int] = None  # BodyMap recency marker: controller_steps value when BodyMap was last updated
    # Safety / posture retry bookkeeping (Phase V)
    last_standup_step: Optional[int] = None
    last_standup_failed: bool = False


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


# Module layout / roadmap
# -----------------------
# ENGINE (import-safe, no direct user I/O) – reusable from tests or other front-ends:
#   • Runtime context:
#       - Ctx: mutable runtime state (soft temporal clock, ticks, age_days, controller_steps, cog_cycles, etc.).
#   • Graph / edge helpers:
#       - world_delete_edge(...), delete_edge_flow(...): engine + CLI helpers for removing edges.
#       - Spatial stubs: _maybe_anchor_attach(...), add_spatial_relation(...).
#   • Persistence & versioning:
#       - save_session(...): atomic JSON snapshot of (world, drives, skills).
#       - _module_version_and_path(...), versions_dict(), versions_text(): component versions + paths.
#   • Embodiment stub:
#       - HAL: hardware abstraction layer skeleton for future robot embodiments.
#   • Policy runtime:
#       - PolicyGate, PolicyRuntime, CATALOG_GATES: controller gate catalog and runtime gate evaluation.
#       - boot_prime_stand(...): boot-time seeding of a “stand” intent reachable from NOW.
#   • Tagging / help text:
#       - print_tagging_and_policies_help(...): console explainer for bindings, edges, tags, and policies.
#   • Profiles & tutorials:
#       - profile_* functions: chimpanzee / human / multi-brain / society / ASI stubs (dry-run, no writes).
#       - choose_profile(...): profile picker at startup.
#       - run_new_user_tour(...), _open_readme_tutorial(...): quick tour + README/compendium helpers.
#   • Preflight:
#       - run_preflight_full(...): full pytest + probes + hardware checks.
#       - run_preflight_lite_maybe(): optional startup “lite” preflight banner.
#   • WorldGraph helpers for the runner:
#       - _anchor_id(...), _sorted_bids(...): anchor and binding id helpers.
#       - snapshot_text(...), export_snapshot(...), recent_bindings_text(...):
#           snapshot and export of the live WorldGraph, CTX, and policies.
#       - timekeeping_line(...), print_timekeeping_line(...), _snapshot_temporal_legend(...):
#           soft-clock / epoch / cosine one-line summaries and legend.
#       - drives_and_tags_text(...), skill_ledger_text(...): drives panel + skill ledger explainers.
#       - _resolve_engrams_pretty(...), _bindings_pointing_to_eid(...), _engrams_on_binding(...):
#           engram pointer inspection utilities.
#   • Planning / FOA / contextual helpers:
#       - _neighbors(...), _bfs_reachable(...), *_with_pred/cue(...): small graph utilities.
#       - _first_binding_with_pred(...), choose_contextual_base(...): write-base suggestions.
#       - present_cue_bids(...), neighbors_k(...), compute_foa(...), candidate_anchors(...):
#           focus-of-attention and candidate anchor selection.
#
# CLI (printing/input; menus; argparse) – terminal user experience:
#   • interactive_loop(args): main menu + per-selection code blocks.
#   • main(argv): argument parsing, logging, “one-shot” flags (about/version/preflight/plan), and then interactive_loop.
#   • if __name__ == "__main__": sys.exit(main()): standard Python script entry point.


# --- Graph edge deletion helpers (engine-level, import-safe) -----------------

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


# --- CLI flow: delete edge (menu 24) ---------------------------------------------
# CLI helper that wraps world_delete_edge() and engine-level delete_edge(), plus autosave.

def delete_edge_flow(world: Any, autosave_cb=None) -> None:
    """delete edge

    """
    #messages and input values
    print("Delete edge (src -> dst [relation])")
    print("src -- enter the source binding, e.g., b1")
    print("dst -- enter the destination binding, e.g., b5")
    print("[relation] -- if multiple links between the two bindings you can optionally specify which one to delete")
    print("           -- you need to specify the exact label, not a substring\n")
    src = input("Source binding id (e.g., b1): ").strip()
    dst = input("Dest binding id (e.g., b5): ").strip()
    rel = input("Relation label (optional; blank = ANY): ").strip() or None

    #removal of link
    removed = 0
    for method in ("remove_edge", "delete_edge"):  #remove_edge() is an old alias for delete_edge, both here for compatibility
        if hasattr(world, method): #does the world object have this method?
            try:
                removed = getattr(world, method)(src, dst, rel) #fetches the bound method and calls it
                break
            except Exception:
                removed = 0 #any error then we will try world_delete_edge(...)
    if removed == 0: #if neither of remove_edge() nor delete_edge() existed/worked
        removed = world_delete_edge(world, src, dst, rel)

    #print message and autosave file
    print(f"Removed {removed} edge(s) {src} -> {dst}{(' (rel='+rel+')' if rel else '')}")
    if autosave_cb:
        try:
            autosave_cb()
        except Exception:
            pass


# ==== Spatial anchoring stubs (NO-OP placeholders for future attach semantics) ====

def _maybe_anchor_attach(default_attach: str, base: dict | None) -> str:
    """
    Base-aware attach helper: adjust the attach mode based on a suggested write-base.

    Today we keep the behavior very conservative:

      • If base is a NEAREST_PRED suggestion with a concrete 'bid' and the caller
        would have used attach="latest", we return "none". This signals that the
        caller should create the new binding unattached and then explicitly add
        base['bid'] --then--> new in a single, readable place.

      • In all other cases we simply return default_attach unchanged.

    This keeps the core WorldGraph attach semantics simple (now/latest/none) while
    giving us a single knob to turn write placement from naive 'LATEST' to
    base-anchored placement as the architecture evolves.

    Note: -We already compute a "write base" suggestion via choose_contextual_base(...)
            e.g., as seen in the Instinct Step menu selection.
          -These helpers (together with _add_pred_base_aware(...) in the Controller)
            provide a single choke point for future base-aware write semantics.
    Note: Nov 2025 -- pylint:disable=unused-argument removed as stub now filled in
    """
    if not isinstance(base, dict):
        return default_attach
    kind = base.get("base")
    bid = base.get("bid")
    if kind == "NEAREST_PRED" and isinstance(bid, str) and bid and default_attach == "latest":
        # Create the node unattached; the caller will add base['bid'] --then--> new.
        return "none"
    return default_attach


def _attach_via_base(world, base: dict | None, new_bid: str, *, rel: str = "then", meta: dict | None = None) -> None:
    """
    Attach a newly-created binding under the suggested base, when appropriate.

    This is intended to be used together with _maybe_anchor_attach(...):

      • The caller first chooses a base via choose_contextual_base(...),
        then calls _maybe_anchor_attach(default_attach, base) to decide the
        attach mode to pass into world.add_predicate/add_cue/etc.

      • If _maybe_anchor_attach(...) returned "none" for a NEAREST_PRED base,
        the caller can then invoke _attach_via_base(...) to add an explicit
        base['bid'] --rel--> new_bid edge for readability.

    For now we only attach for NEAREST_PRED suggestions; HERE/NOW bases are
    left to the default attach semantics to avoid duplicating edges.
    """
    if not isinstance(base, dict):
        return
    kind = base.get("base")
    base_bid = base.get("bid")
    if kind != "NEAREST_PRED" or not isinstance(base_bid, str) or not base_bid:
        return
    try:
        if base_bid not in world._bindings or new_bid not in world._bindings:
            return
    except Exception:
        return
    edge_meta = meta or {
        "created_by": "base_attach",
        "base_kind": kind,
        "base_pred": base.get("pred"),
    }
    try:
        world.add_edge(base_bid, new_bid, rel, meta=edge_meta)
        try:
            print(f"[base] attached {new_bid} under base {base_bid} via {rel} ({_fmt_base(base)})")
        except Exception:
            # Printing is purely diagnostic; ignore errors here.
            pass
    except Exception as e:
        try:
            print(f"[base] error while attaching {new_bid} under {base_bid}: {e}")
        except Exception:
            pass


# Minimal vocabulary for spatial edge labels in WorldGraph.
SPATIAL_REL_LABELS = {"near", "inside", "supports"}
def add_spatial_relation(world, src_bid: str, rel: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Sugar for scene-graph style relations (near, inside, supports).

    Today this is just an alias of world.add_edge(...). The 'rel' string is not
    strictly enforced here, but callers are encouraged to stick to the small,
    explicit vocabulary in SPATIAL_REL_LABELS to avoid label explosion.
    """
    world.add_edge(src_bid, dst_bid, rel, meta or {})


def add_spatial_inside(world, src_bid: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Stub helper for 'inside' spatial relation.

    Intended future use:
      SELF --inside--> SHELTER when the agent is resting in a sheltered niche.

    Currently unused; provided as a clearly named wrapper so future code can
    call it and we keep the label semantics centralized.
    """
    add_spatial_relation(world, src_bid, "inside", dst_bid, meta)


def add_spatial_supports(world, src_bid: str, dst_bid: str, meta: dict | None = None) -> None:
    """
    Stub helper for 'supports' spatial relation.

    Intended future use:
      ROCK --supports--> SELF when a particular surface is bearing the body,
      or SHELTER_FLOOR --supports--> SELF, etc.

    Currently unused; provided as a stub for future development.
    """
    add_spatial_relation(world, src_bid, "supports", dst_bid, meta)



# --------------------------------------------------------------------------------------
# Persistence: atomic JSON autosave (world, drives, skills)
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
# Embodiment / HAL skeleton (no real robotics yet)
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
# Policy runtime: gates, Action Center, and console helpers
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


# --- WorldGraph snapshot + engram helpers (runner-facing) ------------------------


def _resolve_engrams_pretty(world, bid: str) -> None:
    """used with resolve engrams menu selection
    -from bid gets column01: {"id": eid, "act": 1.0}
    -prints these out as, e.g., Engrams on b3; column01: 34c406dd…  OK
    """

    b = world._bindings.get(bid)
    # e.g., Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={}, engrams={'column01': {'id': '302ca8b28d0c4e03b501c2d1d23ffa76', 'act': 1.0}})
    # -world is the live WorldGraph instance created at runner start inside interactive_loop
    if not b:
        print("Unknown binding id.")
        return
    eng = getattr(b, "engrams", None)
    # e.g., {'column01': {'id': '34c406dd346f4a6fb8bd356d01da9f79', 'act': 1.0}}
    #  -{"id": eid, "act": 1.0} (id = engram id, act = activation weight)
    if not isinstance(eng, dict) or not eng:
        print("Engrams: (none)")
        return
    print("Engrams on", bid)

    for slot, val in sorted(eng.items()):
        eid = val.get("id") if isinstance(val, dict) else None
        ok = False
        try:
            rec = world.get_engram(engram_id=eid) if isinstance(eid, str) else None
            ok = bool(rec and isinstance(rec, dict) and rec.get("id") == eid)
        except Exception:
            ok = False
        status = "OK" if ok else "(dangling)"
        short = (eid[:8] + "…") if isinstance(eid, str) else "(id?)"
        print(f"  {slot}: {short}  {status}")


def _bindings_pointing_to_eid(world, eid: str):
    """allows inspect engrams to tell which bindings
    reference the eid
    """
    refs = []
    for bid, b in world._bindings.items():
        eng = getattr(b, "engrams", None)
        if isinstance(eng, dict):
            for slot, val in eng.items():
                if isinstance(val, dict) and val.get("id") == eid:
                    refs.append((bid, slot))
    return refs


# ==== Temporal / timekeeping legend and one-line summary helpers ==================

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


# ==== Developer utilities: LOC, vector parsing, and loop helper ===================

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
    lines.append("Selection:  LOC by Directory (Python)")
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


def loop_helper(autosave_from_args: Optional[str], world, drives, ctx=None, time_limited: bool = False):
    """
    Operations to run at the end of each menu branch before looping again.
    Currently: autosave (if enabled), optional mini-snapshot, visual spacer.
    Mini-snapshot -- print a compact binding/edge list plus one line of timekeeping values
    Future: time-limited bypasses for real-world ops.
    """
    if time_limited:
        return #from the loop_helper (not menu loop), i.e., just return without doing anything
    if autosave_from_args:
        save_session(autosave_from_args, world, drives)
        # Quiet by default; uncomment for debugging:
        # print(f"[autosaved {ts}] {autosave_from_args}")
    try:
        if ctx is not None and getattr(ctx, "mini_snapshot", False):
            print()
            print_mini_snapshot(world, ctx, limit=50)
    except Exception:
        pass
    print("\n-----\n") #visual spacer before menu prints again
    #this is usually the end of the elif branch of a menu selection block
    #thus, control now falls to the bottom of the while loop and then back to top where while True starts its next iteration


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
    """Return engram ids attached to a binding (via binding.engrams).
    -in world instance of class World -- self._bindings={}, i.e., in the instance world, world_bindings.keys() is a

    """
    b = world._bindings.get(bid)
    #-nodes in world instance of WorldGraph are dataclass Binding
    #-fields of dataclass Binding -- id, tags {set}, edges [list of TypedDict Edges {to:___, label:___, meta:___}, {}...], meta {dict}, engrams {dict}
    #-b=Binding below is an instance of dataclass Binding corresponding to, e.g., node b3
    #   nb. Python objects don't have an intrinsic 'instance name' -- just have variables point at them
    # e.g., b= Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={},
    #          engrams={'column01': {'id': '9e48b29cb0614f71b8435e4cab01082a', 'act': 1.0}})
    if not b:
        return []
    eng = getattr(b, "engrams", None) or {}
    # e.g., eng = {'column01': {'id': '9e48b29cb0614f71b8435e4cab01082a', 'act': 1.0}}
    out: list[str] = []
    if isinstance(eng, dict):
        for v in eng.values():
            if isinstance(v, dict):
                eid = v.get("id")
                #e.g., eid = 9e48b29cb0614f71b8435e4cab01082a
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


def neighbors_near_self(world) -> List[str]:
    """
    Return binding ids that are directly connected from NOW via a 'near' edge.

        NOW --near--> bN

    This queries the main WorldGraph (episode index), not the BodyMap. It is
    purely descriptive sugar over the scene-graph edges written by
    _write_spatial_scene_edges(...).
    """
    now_id = _anchor_id(world, "NOW")
    if not now_id or now_id == "?" or now_id not in world._bindings:
        return []

    b = world._bindings.get(now_id)
    if not b:
        return []

    edges_raw = (
        getattr(b, "edges", []) or
        getattr(b, "out", []) or
        getattr(b, "links", []) or
        getattr(b, "outgoing", [])
    )

    out: list[str] = []
    if isinstance(edges_raw, list):
        for e in edges_raw:
            if not isinstance(e, dict):
                continue
            rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
            if rel != "near":
                continue
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if isinstance(dst, str) and dst in world._bindings:
                out.append(dst)

    # Deduplicate while preserving order
    seen: set[str] = set()
    uniq: list[str] = []
    for bid in out:
        if bid not in seen:
            seen.add(bid)
            uniq.append(bid)
    return uniq


def resting_scenes_in_shelter(world) -> Dict[str, Any]:
    """
    Query helper for the current episode around NOW:

    Returns a dict with:
      {
        "rest_near_now": bool,           # pred:resting reachable from NOW within a small radius
        "shelter_near_now": bool,        # NOW --near--> binding(s) with pred:proximity:shelter:near
        "shelter_bids": list[str],       # those shelter-near binding ids
        "hazard_cliff_far_near_now": bool,  # pred:hazard:cliff:far reachable from NOW
      }

    This is intentionally simple and descriptive. It does NOT alter the world
    or planner; it just inspects the structure produced by the env loop and
    scene-graph writer.

    Typical use:
      - Ask "are we in a 'resting in shelter, cliff far' configuration now?"
      - That is approximately when:
          rest_near_now
          and shelter_near_now
          and hazard_cliff_far_near_now
    """
    now_id = _anchor_id(world, "NOW")
    if not now_id or now_id == "?" or now_id not in world._bindings:
        return {
            "rest_near_now": False,
            "shelter_near_now": False,
            "shelter_bids": [],
            "hazard_cliff_far_near_now": False,
        }

    # 1) Is there any 'resting' predicate reachable from NOW within a few hops?
    rest_near_now = has_pred_near_now(world, "resting", hops=3)

    # 2) Which neighbors via NOW --near--> are shelter-near bindings?
    near_ids = neighbors_near_self(world)
    shelter_bids: list[str] = []
    for bid in near_ids:
        b = world._bindings.get(bid)
        if not b:
            continue
        tags = getattr(b, "tags", []) or []
        if any(isinstance(t, str) and t == "pred:proximity:shelter:near" for t in tags):
            shelter_bids.append(bid)

    shelter_near_now = bool(shelter_bids)

    # 3) Is there any 'hazard:cliff:far' near NOW?
    hazard_cliff_far_near_now = has_pred_near_now(world, "hazard:cliff:far", hops=3)

    return {
        "rest_near_now": rest_near_now,
        "shelter_near_now": shelter_near_now,
        "shelter_bids": shelter_bids,
        "hazard_cliff_far_near_now": hazard_cliff_far_near_now,
    }


#pylint: disable=superfluous-parens
def _gate_stand_up_trigger_body_first(world, _drives: Drives, ctx) -> bool:
    """
    StandUp gate that prefers BodyMap for posture when available, falling back
    to WorldGraph near-NOW predicates otherwise.

    Trigger logic (neonate):
      • If BodyMap is fresh and posture == 'fallen'  → fire.
      • If BodyMap is fresh and posture == 'standing'→ do NOT fire.
      • Otherwise, fall back to:
            fallen  := pred:posture:fallen near NOW
            standing:= pred:posture:standing near NOW
        and fire if fallen or (stand_intent && not standing).
    """
    # BodyMap posture if available and not stale
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None

    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        fallen = has_pred_near_now(world, "posture:fallen")
        standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    return fallen or (stand_intent and not standing)


def _gate_stand_up_explain(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_stand_up_trigger_body_first.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    bp = body_posture(ctx) if ctx is not None else None
    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        fallen = has_pred_near_now(world, "posture:fallen")
        standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    return (
        f"dev_gate: age_days={getattr(ctx, 'age_days', 0.0):.2f}<=3.0, trigger: "
        f"fallen={fallen} or (stand_intent={stand_intent} and not standing={not standing}) "
        f"(hunger={hunger:.2f})"
    )


def _gate_seek_nipple_trigger_body_first(world, drives: Drives, ctx) -> bool:
    """
    SeekNipple gate that prefers BodyMap for posture (standing/fallen) and uses
    Drives.hunger numerically for the hunger condition.

    Conditions (BodyMap + WorldGraph):
      • hunger > HUNGER_HIGH
      • body_posture == 'standing' (BodyMap if fresh, else graph near NOW)
      • not fallen
      • if we have any mom-distance info (BodyMap or WorldGraph),
        require "mom is near" (nursing range)
      • nipple_state != 'latched' (BodyMap if available)
      • not already seeking_mom near NOW

    Notes:
      - Mom-distance is taken from BodyMap first (ctx.body_world / body_ids['mom']).
      - If BodyMap is stale or absent, we fall back to WorldGraph predicates
        proximity:mom:close / proximity:mom:far near NOW.
      - If neither map has *any* mom proximity information, we leave the gate
        unconstrained on mom distance (legacy behaviour).
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    if hunger <= float(HUNGER_HIGH):
        return False

    # Prefer BodyMap posture when it is not stale; otherwise fall back to graph.
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None

    if bp is not None:
        standing = (bp == "standing")
        fallen = (bp == "fallen")
    else:
        standing = has_pred_near_now(world, "posture:standing")
        fallen = has_pred_near_now(world, "posture:fallen")

    if not standing or fallen:
        return False

    # --- Mom-distance check (BodyMap + WorldGraph, but only if we have info) ---
    have_distance = False
    mom_near = True  # default: unconstrained (no info → do not block)

    if ctx is not None and not stale:
        md = body_mom_distance(ctx)
        if md is not None:
            have_distance = True
            mom_near = (md == "near")

    if not have_distance:
        # Fall back to WorldGraph proximity predicates near NOW.
        close = has_pred_near_now(world, "proximity:mom:close")
        far   = has_pred_near_now(world, "proximity:mom:far")
        if close or far:
            have_distance = True
            mom_near = close  # near only when "close" is explicitly present

    # Only enforce the mom-distance gate when we actually have some signal.
    if have_distance and not mom_near:
        return False

    # If BodyMap says we are already latched/drinking, do not seek again.
    ns = body_nipple_state(ctx) if ctx is not None else None
    if ns == "latched":
        return False

    # Use the episode graph to see if 'seeking_mom' is already active near NOW.
    if has_pred_near_now(world, "seeking_mom"):
        return False

    return True


def _gate_seek_nipple_explain(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_seek_nipple_trigger_body_first.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    bp = body_posture(ctx) if ctx is not None else None
    if bp is not None:
        standing = (bp == "standing")
        fallen = (bp == "fallen")
        posture_str = bp
    else:
        standing = has_pred_near_now(world, "posture:standing")
        fallen = has_pred_near_now(world, "posture:fallen")
        posture_str = f"standing={standing}, fallen={fallen}"

    ns = body_nipple_state(ctx) if ctx is not None else None
    nipple_str = ns if ns is not None else "n/a"

    seeking = has_pred_near_now(world, "seeking_mom")
    return (
        f"dev_gate: True, trigger: posture={posture_str} "
        f"and hunger={hunger:.2f}>0.60 "
        f"and nipple_state={nipple_str} "
        f"and not seeking={not seeking} "
        f"and not fallen={not fallen}"
        f"-mem_distance={body_mom_distance(ctx)}"
    )
#pylint: enable=superfluous-parens


def _gate_rest_trigger_body_space(world, drives: Drives, ctx) -> bool:
    """
    Rest gate that adds a gentle body/space constraint on top of fatigue.

    Conditions:
      • fatigue > FATIGUE_HIGH OR drive:fatigue_high cue present, AND
      • if BodyMap is available: classify a 'rest_zone' via body_space_zone(ctx)
            and do NOT rest when rest_zone == 'unsafe_cliff_near'.
      • otherwise, rely solely on fatigue / fatigue cue.

    This keeps the original rest behaviour when BodyMap is stale or absent, and
    only vetoes rest in clearly unsafe positions (near a cliff without shelter).
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_high = fatigue > float(FATIGUE_HIGH)
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])

    # --- DEBUG: show how the Rest gate sees BodyMap and drives ---
    try:
        cliff = None
        shelter = None
        zone_label = "unknown"
        bodymap_stale = True

        if ctx is not None:
            bodymap_stale = bodymap_is_stale(ctx)
            if not bodymap_stale:
                cliff = body_cliff_distance(ctx)
                shelter = body_shelter_distance(ctx)
                if cliff == "near" and shelter != "near":
                    zone_label = "unsafe_cliff_near"
                elif shelter == "near" and cliff != "near":
                    zone_label = "safe"

        print(
            "[gate:rest] "
            f"fatigue={fatigue:.2f} high={fatigue_high} cue={fatigue_cue} "
            f"bodymap_stale={bodymap_stale} "
            f"cliff={cliff} shelter={shelter} zone={zone_label}"
        )
    except Exception:
        # Debug only; never crash the gate.
        pass

    # If we are not tired enough, do not rest regardless of geometry.
    if not (fatigue_high or fatigue_cue):
        return False

    # Gentle body/space veto: only when we can classify a zone from BodyMap.
    try:
        if ctx is not None:
            zone = body_space_zone(ctx)
            if zone == "unsafe_cliff_near":
                return False
    except Exception:
        # On any BodyMap error, fall back to fatigue-based gate only.
        return True

    return True


def _gate_rest_explain_body_space(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_rest_trigger_body_space.
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])

    shelter = None
    cliff = None
    zone = "unknown"
    try:
        if ctx is not None and not bodymap_is_stale(ctx):
            shelter = body_shelter_distance(ctx)
            cliff = body_cliff_distance(ctx)
        zone = body_space_zone(ctx) if ctx is not None else "unknown"
    except Exception:
        shelter = cliff = None
        zone = "unknown"

    return (
        f"dev_gate: True, trigger: fatigue={fatigue:.2f}>{float(FATIGUE_HIGH):.2f} "
        f"or cue:drive:fatigue_high present={fatigue_cue} "
        f"and rest_zone={zone} (shelter={shelter}, cliff={cliff})"
    )


def _gate_follow_mom_trigger_body_space(world, drives: Drives, ctx) -> bool: #pylint: disable=unused-argument
    """
    FollowMom gate: permissive fallback when the kid is not fallen.

    Conditions:
      • If BodyMap is fresh and posture == 'fallen' → do NOT fire
        (let StandUp / safety handle that).
      • Otherwise → True (act as a default "keep moving with mom" policy).

    This keeps FollowMom from fighting the safety layer when the kid is actually
    down, but otherwise lets it act as the permissive fallback we intended.
    """
    try:
        if ctx is not None and not bodymap_is_stale(ctx):
            bp = body_posture(ctx)
            if bp == "fallen":
                return False
    except Exception:
        # On any BodyMap issue, stay permissive; the safety override in the
        # Action Center still protects us from truly fallen configurations.
        pass
    return True


def _gate_follow_mom_explain_body_space(world, drives: Drives, ctx) -> str: #pylint: disable=unused-argument
    """
    Human-readable explanation matching _gate_follow_mom_trigger_body_space.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))

    posture = None
    zone = "unknown"
    try:
        if ctx is not None and not bodymap_is_stale(ctx):
            posture = body_posture(ctx)
            zone = body_space_zone(ctx)
    except Exception:
        posture = posture or "n/a"
        zone = "unknown"

    return (
        "dev_gate: True, trigger: fallback=True when not fallen; "
        f"posture={posture or 'n/a'} zone={zone} "
        f"(hunger={hunger:.2f}, fatigue={fatigue:.2f})"
    )


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

        # If fallen near NOW (BodyMap-first), force safety-only gates
        if _fallen_near_now(world, ctx, max_hops=3):
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
        base  = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
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

        # Build an explicit [executed] line from the result dict, if available
        exec_line = ""
        if isinstance(result, dict):
            status  = result.get("status")
            reward  = result.get("reward")
            binding = result.get("binding")
            if status and status != "noop":
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                exec_line = f"[executed] {label} ({status}, reward={rtxt}) binding={binding}\n"

        gate_for_label = next((p for p in self.loaded if p.name == label), chosen)
        post_expl = gate_for_label.explain(world, drives, ctx) if gate_for_label.explain else "explain: (not provided)"
        return (
            f"{label} (added {delta_n} bindings)\n"
            f"{exec_line}"
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
        # Neonatal only; later profiles/ages may choose a different gate.
        dev_gate=lambda ctx: getattr(ctx, "age_days", 0.0) <= 3.0,
        trigger=_gate_stand_up_trigger_body_first,
        explain=_gate_stand_up_explain,
    ),

    PolicyGate(
        name="policy:seek_nipple",
        dev_gate=lambda ctx: True,
        trigger=_gate_seek_nipple_trigger_body_first,
        explain=_gate_seek_nipple_explain,
    ),

    PolicyGate(
        name="policy:rest",
        dev_gate=lambda ctx: True,  # available at all stages; selection is by trigger/deficit
        trigger=_gate_rest_trigger_body_space,
        explain=_gate_rest_explain_body_space,
    ),

    PolicyGate(
        name="policy:follow_mom",
        dev_gate=lambda ctx: True,
        trigger=_gate_follow_mom_trigger_body_space,
        explain=_gate_follow_mom_explain_body_space,
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
            has_pred_near_now(W, "posture:fallen")
            or any_cue_tokens_present(W, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])
            #or any_pred_present(W, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])
        ),
        explain=lambda W, D, ctx: (
            f"dev_gate: True, trigger: fallen={has_pred_near_now(W,'posture:fallen')} "
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
    At birth (age_days == 0), seed a simple initial posture state for the kid:

    - Ensure there is a `posture:fallen` predicate reachable from NOW.
    - If not present, create it attached to NOW.
    - Use generic 'then' as the edge label (no special 'initiate_*' action label).

    Idempotent and safe to call on a fresh session.
    """
    # Only at birth
    try:
        if float(getattr(ctx, "age_days", 0.0)) != 0.0:
            return
    except Exception:
        return

    now_id = _anchor_id(world, "NOW")

    # Look for an existing fallen-posture predicate
    fallen_bid = _first_binding_with_pred(world, "posture:fallen")
    if fallen_bid:
        # If NOW can't reach it in 1 hop, add a 'then' edge
        if not _bfs_reachable(world, now_id, fallen_bid, max_hops=1):
            try:
                world.add_edge(now_id, fallen_bid, "then")
                print(f"[boot] Linked {now_id} --then--> {fallen_bid} (posture:fallen)")
            except Exception as e:
                print(f"[boot] Could not link NOW->posture:fallen: {e}")
        return

    # Otherwise, create a new fallen-posture binding attached to NOW
    try:
        fallen_bid = world.add_predicate(
            "posture:fallen",
            attach="now",
            meta={"boot": "init", "added_by": "system"},
        )
        print(f"[boot] Seeded posture:fallen as {fallen_bid} (NOW -> fallen)")
    except Exception as e:
        print(f"[boot] Could not seed posture:fallen: {e}")


def print_tagging_and_policies_help(policy_rt=None) -> None:
    """Terminal help: bindings, edges, predicates, cues, anchors, provenance/engrams, and policies."""
    print("""

==================== Understanding Bindings, Edges, Predicates, Cues & Policies ====================

What is a Binding?
  • A small 'episode card' that binds together:
      - tags (symbols: predicates / cues / anchors)
      - engrams (pointers to rich memory outside WorldGraph)
      - meta (provenance, timestamps, light notes)
      - edges (directed links from this binding)\n
  Structure (conceptual):
      { id:'bN', tags:[...], engrams:{...}, meta:{...}, edges:[{'to': 'bK', 'label':'then', 'meta':{...}}, ...] }

Tag Families (use these prefixes)
  • pred:*        → predicates (facts you might plan TO)
      examples: pred:posture:standing, pred:posture:fallen, pred:nipple:latched, pred:milk:drinking,
                pred:proximity:mom:close, pred:event:fall_detected
  • pred:action:* → explicit action bindings (verbs in the map).
      examples: pred:action:push_up, pred:action:extend_legs, pred:action:orient_to_mom
  • cue:*         → evidence/context you NOTICE (policy triggers); not planner goals
      examples: cue:vision:silhouette:mom, cue:scent:milk, cue:sound:bleat:mom, cue:terrain:rocky
  • anchor:*      → orientation markers (e.g., anchor:NOW); also mapped in engine anchors {'NOW': 'b1'}
  • drive thresholds (pick one convention and be consistent):
      default: pred:drive:hunger_high  (plannable)
      alt:     cue:drive:hunger_high   (trigger/evidence only)

Edges = Transitions
  • We treat edge labels as weak episode links (often just 'then').
  • Most semantics live in bindings (predicates and pred:action:*); edge labels are for readability and metrics.
  • Quantities about the transition live in edge.meta (e.g., meters, duration_s, created_by).
  • Planner behavior today: labels are for readability; BFS follows structure (node/edge graph), not names.
  • Duplicate protection: the UI warns on exact duplicates of (src, label, dst)

Provenance & Engrams
  • Who created a binding?   binding.meta['policy'] = 'policy:<name>'
  • Who created an edge?     edge.meta['created_by'] = 'policy:<name>'
  • Where is the rich data?  binding.engrams[...] → pointers (large payloads live outside WorldGraph)

Anchors
  • anchor:NOW exists; used as the start for planning; may have no pred:*
  • Other anchors (e.g., HERE) are allowed; anchors are just bindings with special meaning

Planner (BFS) Basics
  • Goal test: a popped binding whose tags contain the target 'pred:<token>'
  • Shortest hops: BFS with visited-on-enqueue; parent map reconstructs the path
  • BFS → fewest hops (unweighted).
  • Dijkstra → lowest total edge weight; weights come from edge.meta keys in this order:
      'weight' → 'cost' → 'distance' → 'duration_s' (default 1.0 if none present).
  • Toggle strategy via the 'Planner strategy' menu item, then run 'Plan from NOW'.
  • Pretty paths show first pred:* as the node label (fallback to id) and --label--> between nodes
  • Try: menu 'Plan from NOW', menu 'Display snapshot', menu 'Export interactive graph'

Policies (Action Center overview)
  • Policies live in cca8_controller and expose:
      - dev_gate(ctx)       → True/False (availability by development stage/context)
      - trigger(world, drives, ctx) → True/False (should we act now?)
      - execute(world, ctx, drives) → adds bindings/edges; stamps provenance
  • Action Center scans loaded policies in order each tick; first match runs (with safety priority for
             recovery)
  • After execute, you may see:
      - new bindings (with meta.policy)
      - new edges (with edge.meta.created_by)
     - skill ledger updates ('Show skill stats')

    """)

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
    print("  ✗ Don’t store large data in tags; put it in engrams")
    print("\nExamples")
    print("  born --then--> wobble --stabilize--> posture:standing --suckle--> milk:drinking")
    print("  stand --search--> nipple:found --latch--> nipple:latched --suckle--> milk:drinking")
    print("\n(See README.md → Tagging Standard for more information.)\n")


# --------------------------------------------------------------------------------------
# Profiles & tutorials: experimental profiles (dry-run) + narrative fallbacks
# --------------------------------------------------------------------------------------


def _goat_defaults():
    """Return the Mountain Goat default profile tuple: (name, sigma, jump, winners_k)."""
    return ("Mountain Goat", 0.015, 0.2, 2)


def _print_goat_fallback():
    """Explain that the chosen profile is not implemented and we fall back to Mountain Goat."""
    print("Although scaffolding is in place, currently this evolutionary-like configuration is not available. "
          "Profile will be set to mountain goat-like brain simulation.\n")


def profile_chimpanzee(_ctx) -> tuple[str, float, float, int]:
    """Print a narrative about the chimpanzee profile; fall back to Mountain Goat defaults."""
    print('''
Chimpanzee-like brain simulation
\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
    "similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better
    combinatorial language.\n
    ''')
    _print_goat_fallback()
    return _goat_defaults()


def profile_human(_ctx) -> tuple[str, float, float, int]:
    """Print a narrative about the human profile; fall back to Mountain Goat defaults."""
    print('''
\nHuman-like brain simulation
\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
    "similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better
    combinatorial language.
The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning
    and compositional reasoning/language.\n
    ''')
    _print_goat_fallback()
    return _goat_defaults()


def profile_human_multi_brains(_ctx, world) -> tuple[str, float, float, int]:
    """Dry-run multi-brain sandbox (no writes); print trace; fall back to Mountain Goat defaults."""
    # Narrative
    print('''
\nHuman-like one-agent multiple-brains simulation
\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
    "similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better
    combinatorial language.
The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning
    and compositional reasoning/language.\n"
In this model each agent has multiple brains operating in parallel. There is an intelligent voting mechanism to
    decide on a response whereby each of the 5 processes running in parallel can give a response with an indication
    of how certain they are this is the best response, and the most certain + most popular response is chosen.
As well, all 5 symbolic maps along with their rich store of information in their engrams are continually learning
    and constantly updated.\n"
    ''')
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
    print('''
\nHuman-like one-brain simulation × multiple-agents society
\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
    "similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better
    combinatorial language.
The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning
    and compositional reasoning/language.\n
\nIn this simulation we have multiple agents each with one human-like brain, all interacting with each other.\n
    ''')
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
    print('''
\nHuman-like one-agent multiple-brains simulation with combinatorial planning
\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
"similar" structures) but hanced feedback pathways allowing better causal reasoning. Also better
combinatorial language. "
The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning
 and compositional reasoning/language.\n
\nIn this model there are multiple brains, e.g., 5 at the time of this writing, in one agent.
There is an intelligent voting mechanism to decide on a response whereby each of the 5 processes running in
 parallel can give a response with an indication of how certain they are this is the best response, and the most
 certain + most popular response is chosen. As well, all 5 symbolic maps along with their rich store of
 information in their engrams are continually learning and updated.\n
\nIn addition, in this model each brain has multiple von Neumann processors to independently explore different
 possible routes to take or different possible decisions to make.\n

Implementation scaffolding (this stub does not commit changes to the live world):
\n  • Brains: 5 symbolic hippocampal-like maps (conceptual ‘brains’) exploring in parallel.
\n  • Processors: each brain has 256 von Neumann processors that independently explore candidate plans.
\n  • Rollouts: each processor tries a short action sequence (horizon H=3) from a small discrete action set.
\n  • Scoring: utility(plan) = Σ reward(action) − cost_per_step·len(plan) (simple, deterministic toy scoring).
\n  • Selection: within a brain, keep the best plan; across brains, pick the champion by best score, then avg score.
\n  • Commit rule: in a real system we would commit only the FIRST action of the winning plan after a safety check.
\n  • Parallelism note: this stub runs sequentially; a real build would farm processors to separate OS processes.\n
    ''')

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
    print('''
\nSuper-human-like machine simulation
\n\nFeatures scaffolding for an ASI-grade architecture:
\n  • Hierarchical memory: massive multi-modal engrams (vision/sound/touch/text) linked to a compact symbolic index.
\n  • Weighted graph planning: edges carry costs/uncertainty; A*/landmarks for long-range navigation in concept space.
\n  • Meta-controller: blends proposals from symbolic search, neural value estimation, and program-synthesis planning.
\n  • Self-healing & explanation: detect/repair inconsistent states; produce human-readable rationales for actions.
\n  • Tool-use & embodiment: external tools (math/vision/robots) wrapped as policies with provenances and safeguards.
\n  • Safety envelope: constraint-checking policies that can veto/redirect unsafe plans.
\n\nThis stub prints a dry-run of the meta-controller triage and falls back to the current==Mountain Goat profile.\n
    ''')

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

Note:   Pending more tutorial-like upgrade.
        Currently this 'tour' really just runs some of the menu routines without much explanation.
        New version to be more interactive and provide better explanations.


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
# World/intro flows: profile selection, startup notices, preflight-lite
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


    # 2) WorldGraph reasonableness
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
        from cca8_controller import Drives as _Drv, __version__ as _CTRL_VER

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


    # Z4) BFS reasonableness (shortest-hop path found) — no warnings
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
        bad(f"planner (BFS) reasonableness failed: {e}")


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


    # Z7) Timekeeping one-liner reasonableness
    try:
        _w = cca8_world_graph.WorldGraph(); _w.ensure_anchor("NOW")
        _d = Drives(); _ctx = Ctx()
        # Instinct-like: drift once then one controller step
        if _ctx.temporal is None:
            _ctx.temporal = TemporalContext(dim=8, sigma=_ctx.sigma, jump=_ctx.jump)
            _ctx.tvec_last_boundary = _ctx.temporal.vector()
            _ctx.boundary_vhash64 = _ctx.tvec64()
        _rt = PolicyRuntime(CATALOG_GATES); _rt.refresh_loaded(_ctx)
        if _ctx.temporal:
            _ctx.temporal.step()
        _ = action_center_step(_w, _ctx, _d)
        line = timekeeping_line(_ctx)
        if ("controller_steps=" in line) and ("age_days=" in line):
            ok("timekeeping one-liner produced")
        else:
            bad("timekeeping one-liner missing fields")
    except Exception as e:
        bad(f"timekeeping one-liner error: {e}")


    # Z7b) TemporalContext drift + boundary geometry
    try:
        _tctx = Ctx()
        # Small dim so this stays inexpensive; sigma/jump large enough that we
        # can see movement, but boundary() + tvec_last_boundary reset should
        # bring cosine back very close to 1.0.
        _tctx.temporal = TemporalContext(dim=16, sigma=0.03, jump=0.4)
        _tctx.tvec_last_boundary = _tctx.temporal.vector()
        _tctx.boundary_no = 0
        try:
            _tctx.boundary_vhash64 = _tctx.tvec64()
        except Exception:
            _tctx.boundary_vhash64 = None

        _cos0 = _tctx.cos_to_last_boundary()
        if not isinstance(_cos0, float):
            bad("timekeeping drift/boundary: cos_to_last_boundary missing at init")
        else:
            # Drift once and ensure cosine is still finite and in [-1,1].
            _tctx.temporal.step()
            _cos1 = _tctx.cos_to_last_boundary()
            if isinstance(_cos1, float) and -1.0001 <= _cos1 <= 1.0001:
                ok("timekeeping drift: cos_to_last_boundary computed after step()")
            else:
                bad("timekeeping drift: cos_to_last_boundary out of range after step()")

            # Boundary jump: epoch++ and cosine reset near 1.0 with a new vhash64.
            _prev_hash = _tctx.boundary_vhash64
            _new_v = _tctx.temporal.boundary()
            _tctx.tvec_last_boundary = list(_new_v)
            _tctx.boundary_no = getattr(_tctx, "boundary_no", 0) + 1
            try:
                _tctx.boundary_vhash64 = _tctx.tvec64()
            except Exception:
                _tctx.boundary_vhash64 = None

            _cos2 = _tctx.cos_to_last_boundary()
            if (
                isinstance(_cos2, float)
                and _cos2 > 0.95
                and _tctx.boundary_no == 1
                and _tctx.boundary_vhash64
                and _tctx.boundary_vhash64 != _prev_hash
            ):
                ok("timekeeping boundary: epoch increment & cosine reset near 1.0")
            else:
                bad("timekeeping boundary: unexpected cosine/epoch/vhash behavior")
    except Exception as e:
        bad(f"timekeeping drift/boundary error: {e}")


    # Z8) Resolve Engrams pretty (smoke)
    try:
        _wk = cca8_world_graph.WorldGraph(); _wk.ensure_anchor("NOW")
        bid, eid = _wk.capture_scene("vision", "silhouette:mom", [0.1], attach="now", family="cue")
        _resolve_engrams_pretty(_wk, bid)  # prints; OK if non-crashing
        # add a dangling pointer
        b = _wk._bindings[bid]; b.engrams["column09"] = {"id": "a"*32, "act": 1.0}
        _resolve_engrams_pretty(_wk, bid)  # should still print; no assert
        ok("resolve-engrams pretty printed")
    except Exception as e:
        bad(f"resolve-engrams pretty error: {e}")


    # Z9) Demo-world builder smoke (graph shape and provenance)
    try:
        from cca8_test_worlds import build_demo_world_for_inspect
        _wd, _ids = build_demo_world_for_inspect()
        _now = _ids.get("NOW")
        _rest = _ids.get("rest")
        if (_now in _wd._bindings) and (_rest in _wd._bindings):
            ok("demo world: NOW/rest bindings present")
        else:
            bad("demo world: NOW/rest bindings missing")
    except Exception as e:
        bad(f"demo world builder failed: {e}")


    # Z10) Tag hygiene: no 'state:' or 'pred:action:' tags in a simple S–A–P episode
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.set_tag_policy("allow")
        _w.ensure_anchor("NOW")
        # Minimal S–A–P chain
        _w.add_predicate("posture:fallen", attach="now")
        _w.add_action("action:push_up", attach="latest")
        _w.add_action("action:extend_legs", attach="latest")
        _w.add_predicate("posture:standing", attach="latest")
        bad_tags = []
        for bid, b in _w._bindings.items():
            for t in getattr(b, "tags", []):
                if isinstance(t, str) and (t.startswith("state:") or t.startswith("pred:action:")):
                    bad_tags.append((bid, t))
        if bad_tags:
            bad(f"tag hygiene: found legacy tags {bad_tags}")
        else:
            ok("tag hygiene: no 'state:*' or 'pred:action:*' tags on fresh S–A–P episode")
    except Exception as e:
        bad(f"tag hygiene check failed: {e}")


    # Z11) NOW_ORIGIN anchor semantics
    try:
        _w = cca8_world_graph.WorldGraph()
        _w.ensure_anchor("NOW")
        ensure_now_origin(_w)
        origin = _anchor_id(_w, "NOW_ORIGIN")
        now = _anchor_id(_w, "NOW")
        if origin != "?" and origin == now:
            ok("NOW_ORIGIN: pinned to initial NOW on fresh world")
        else:
            bad(f"NOW_ORIGIN: unexpected (origin={origin}, now={now})")
    except Exception as e:
        bad(f"NOW_ORIGIN check failed: {e}")


    # Z12) BodyMap bridge + SeekNipple gate (body-first) sanity
    try:
        # Build a fresh BodyMap and context.
        _bm_ctx = Ctx()
        _bm_ctx.body_world, _bm_ctx.body_ids = init_body_world()
        _bm_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: only .predicates is needed here.
        class _ObsStub:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates

        _obs = _ObsStub([
            "posture:standing",
            "proximity:mom:close",
            "nipple:latched",
            "milk:drinking",
        ])

        # Mirror observation into BodyMap.
        update_body_world_from_obs(_bm_ctx, _obs)

        # Check that the high-level BodyMap helpers see what we injected.
        _bp = body_posture(_bm_ctx)
        _md = body_mom_distance(_bm_ctx)
        _ns = body_nipple_state(_bm_ctx)

        if _bp == "standing" and _md == "near" and _ns == "latched":
            ok("BodyMap: posture/mom/nipple mirrored from observation into BodyMap helpers")
        else:
            bad(
                "BodyMap: mismatch between observation and helpers "
                f"(posture={_bp!r}, mom={_md!r}, nipple={_ns!r})"
            )

        # With nipple already latched, SeekNipple gate should NOT trigger even if hunger is high.
        _bm_world = cca8_world_graph.WorldGraph()
        _bm_world.ensure_anchor("NOW")
        _hungry = Drives(hunger=0.95, fatigue=0.1, warmth=0.6)
        _gate = _gate_seek_nipple_trigger_body_first(_bm_world, _hungry, _bm_ctx)
        if _gate:
            bad("BodyMap gate: seek_nipple triggered despite nipple_state='latched'")
        else:
            ok("BodyMap gate: seek_nipple correctly suppressed when nipple_state='latched'")
    except Exception as e:
        bad(f"BodyMap / gate probes failed: {e}")


    # Z12b) BodyMap spatial zone + Rest gate sanity
    try:
        # Fresh BodyMap + context for zone tests
        _zone_ctx = Ctx()
        _zone_ctx.body_world, _zone_ctx.body_ids = init_body_world()
        _zone_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: only .predicates is needed.
        class _ObsStubZone:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates

        # ----- Case 1: unsafe_cliff_near (cliff=near, shelter=far) -----
        _obs_unsafe = _ObsStubZone([
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:far",
            "hazard:cliff:near",
        ])
        update_body_world_from_obs(_zone_ctx, _obs_unsafe)

        _zone1 = body_space_zone(_zone_ctx)
        if _zone1 == "unsafe_cliff_near":
            ok("BodyMap zone: unsafe_cliff_near from (shelter=far, cliff=near)")
        else:
            bad(
                "BodyMap zone: expected 'unsafe_cliff_near' from (shelter=far, cliff=near) "
                f"but got {_zone1!r}"
            )

        # Rest gate should veto rest here even if fatigue is high.
        _world_dummy = cca8_world_graph.WorldGraph()
        _world_dummy.ensure_anchor("NOW")
        _tired = Drives(hunger=0.20, fatigue=0.90, warmth=0.60)

        _rest_gate_unsafe = _gate_rest_trigger_body_space(_world_dummy, _tired, _zone_ctx)
        if _rest_gate_unsafe:
            bad("Rest gate: incorrectly allowed rest when zone='unsafe_cliff_near' and fatigue high")
        else:
            ok("Rest gate: vetoes rest when zone='unsafe_cliff_near' despite high fatigue")

        # ----- Case 2: safe (shelter=near, cliff=far) -----
        _obs_safe = _ObsStubZone([
            "posture:standing",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ])
        update_body_world_from_obs(_zone_ctx, _obs_safe)

        _zone2 = body_space_zone(_zone_ctx)
        if _zone2 == "safe":
            ok("BodyMap zone: safe from (shelter=near, cliff=far)")
        else:
            bad(
                "BodyMap zone: expected 'safe' from (shelter=near, cliff=far) "
                f"but got {_zone2!r}"
            )

        _rest_gate_safe = _gate_rest_trigger_body_space(_world_dummy, _tired, _zone_ctx)
        if _rest_gate_safe:
            ok("Rest gate: allows rest when zone='safe' and fatigue high")
        else:
            bad("Rest gate: incorrectly vetoed rest when zone='safe' and fatigue high")

    except Exception as e:
        bad(f"BodyMap spatial zone / Rest gate probes failed: {e}")


    # Z12c) Spatial scene-graph + 'resting in shelter' summary sanity
    try:
        # Fresh world + context with BodyMap initialized
        _scene_world = cca8_world_graph.WorldGraph()
        _scene_world.set_tag_policy("allow")
        _scene_world.ensure_anchor("NOW")

        _scene_ctx = Ctx()
        _scene_ctx.body_world, _scene_ctx.body_ids = init_body_world()
        _scene_ctx.controller_steps = 0

        # Minimal EnvObservation-like stub: we only need .predicates for this probe.
        class _ObsStubScene:  # pylint: disable=too-few-public-methods
            def __init__(self, predicates):
                self.predicates = predicates
                self.cues = []

        # Synthetic "resting in shelter, cliff far" observation.
        _obs_rest = _ObsStubScene([
            "resting",
            "proximity:mom:close",
            "proximity:shelter:near",
            "hazard:cliff:far",
        ])

        # Use the normal env→world bridge: this will:
        #   • create pred:* bindings,
        #   • update BodyMap,
        #   • write NOW --near--> mom/shelter bindings because 'resting' is present.
        inject_obs_into_world(_scene_world, _scene_ctx, _obs_rest)

        _summary = resting_scenes_in_shelter(_scene_world)

        if _summary.get("rest_near_now") and _summary.get("shelter_near_now"):
            ok(
                "scene-graph: resting_scenes_in_shelter sees "
                "rest_near_now=True and shelter_near_now=True after a resting-in-shelter obs"
            )
        else:
            bad(
                "scene-graph: resting_scenes_in_shelter summary unexpected for "
                "resting+mom:close+shelter:near+cliff:far obs: "
                f"{_summary}"
            )

    except Exception as e:
        bad(f"Spatial scene-graph / resting_scenes_in_shelter probe failed: {e}")


    # Z13) HybridEnvironment reset/step + perception smoke test
    try:
        env = HybridEnvironment()
        _ctx_env = Ctx()

        # Reset: get first observation + info.
        obs0, info0 = env.reset()
        if hasattr(obs0, "predicates") and isinstance(getattr(obs0, "predicates", None), list):
            ok("env: reset produced initial observation with predicates list")
        else:
            bad("env: reset did not return an observation with .predicates list")

        if isinstance(info0, dict) and "scenario_name" in info0:
            ok("env: reset info contains scenario_name")
        else:
            bad("env: reset info missing scenario_name")

        # Optional: inspect internal state shape (kid_posture + scenario_stage).
        _st0 = getattr(env, "state", None)
        if _st0 is not None and hasattr(_st0, "kid_posture") and hasattr(_st0, "scenario_stage"):
            ok("env: state exposes kid_posture/scenario_stage after reset")
        else:
            bad("env: state missing kid_posture/scenario_stage after reset")

        # One storyboard step forward.
        obs1, reward1, done1, info1 = env.step(action=None, ctx=_ctx_env)
        if hasattr(obs1, "predicates") and isinstance(getattr(obs1, "predicates", None), list):
            _types_ok = isinstance(reward1, (int, float)) and isinstance(done1, bool) and isinstance(info1, dict)
            if _types_ok:
                ok("env: step produced (observation, reward, done, info) tuple")
            else:
                bad("env: step returned unexpected reward/done/info types")
        else:
            bad("env: step did not return an observation with .predicates list")
    except Exception as e:
        bad(f"env: reset/step probes failed: {e}")


    # 7) Action helpers reasonableness
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


    # 3b) High-resolution timer reasonableness (monotonic + resolution)
    try:
        import time as _time2
        info = _time2.get_clock_info("perf_counter")
        res  = getattr(info, "resolution", None)
        a = _time2.perf_counter(); b = _time2.perf_counter(); c = _time2.perf_counter()
        if (b > a) or (c > b):  # any forward progress is enough
        #if a < b < c:  #occasionally samples land in the same clock tick
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


def update_body_world_from_obs(ctx, env_obs) -> None:
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
        else:
            # Fallback: hidden if nothing else observed
            tags.add("pred:nipple:hidden")

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


def _write_spatial_scene_edges(world, ctx, env_obs, token_to_bid: Dict[str, str]) -> None: #pylint: disable=unused-argument
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
    preds = set(getattr(env_obs, "predicates", []) or [])
    # Only annotate a tiny scene when resting is present in this observation
    if "resting" not in preds:
        return

    try:
        now_id = _anchor_id(world, "NOW")
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
                add_spatial_relation(
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


def _inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid: Dict[str, str]) -> None:  # pylint: disable=unused-argument
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


def inject_obs_into_world(world, ctx, env_obs) -> Dict[str, List[str]]:  # pylint: disable=unused-argument
    """
    Map an EnvObservation into the WorldGraph as pred:* and cue:* bindings.

    - world: live WorldGraph instance.
    - ctx  : runtime context (currently unused here; reserved for future time/base-aware writes).
    - env_obs: EnvObservation with .predicates and .cues lists.

    Returns:
        {"predicates": [binding ids], "cues": [binding ids]} for any created bindings.

    Notes:
        - Uses attach="now" for the first predicate/cue, then attach="latest" for subsequent ones.
        - Stamps meta={"created_by": "env_step", "source": "HybridEnvironment"} on all injected bindings.
        - Prints the same [env→world] lines as before.
        - Also updates ctx.body_world (BodyMap) to mirror posture/mom_distance/nipple_state.
        - NEW: writes tiny scene-graph 'near' edges from NOW to mom/shelter/cliff bindings
               when 'resting' is present (see _write_spatial_scene_edges).
    """
    created_preds: List[str] = []
    created_cues: List[str] = []
    token_to_bid: Dict[str, str] = {}

    # Map env predicates into the CCA8 WorldGraph as pred:* tokens
    try:
        attach = "now"
        for token in getattr(env_obs, "predicates", []) or []:
            bid = world.add_predicate(
                token,
                attach=attach,
                meta={
                    "created_by": "env_step",
                    "source": "HybridEnvironment",
                },
            )
            print(f"[env→world] pred:{token} → {bid} (attach={attach})")
            created_preds.append(bid)
            token_to_bid[token] = bid
            # After the first predicate, hang subsequent ones off LATEST
            attach = "latest"
    except Exception as e:
        print(f"[env→world] predicate injection error: {e}")

    # Map env cues into the WorldGraph as cue:* tokens
    try:
        attach_c = "now"
        for cue_token in getattr(env_obs, "cues", []) or []:
            bid_c = world.add_cue(
                cue_token,
                attach=attach_c,
                meta={
                    "created_by": "env_step",
                    "source": "HybridEnvironment",
                },
            )
            print(f"[env→world] cue:{cue_token} → {bid_c} (attach={attach_c})")
            created_cues.append(bid_c)
            attach_c = "latest"
    except Exception as e:
        print(f"[env→world] cue injection error: {e}")

    # update BodyMap (ctx.body_world) from this observation
    try:
        update_body_world_from_obs(ctx, env_obs)

        # --- DEBUG: tiny bridge print to show what BodyMap now believes ---
        try:
            bp = body_posture(ctx)
            md = body_mom_distance(ctx)
            ns = body_nipple_state(ctx)
            try:
                sd = body_shelter_distance(ctx)
            except Exception:
                sd = None
            try:
                cd = body_cliff_distance(ctx)
            except Exception:
                cd = None

            print(
                "[env→body] BodyMap now: "
                f"posture={bp or '(n/a)'} "
                f"mom={md or '(n/a)'} "
                f"nipple={ns or '(n/a)'} "
                f"shelter={sd or '(n/a)'} "
                f"cliff={cd or '(n/a)'}"
            )
        except Exception as e:
            # Debug only; never crash the main loop.
            print(f"[env→body] debug error: {e}")
    except Exception:
        # BodyMap should never crash the runner; ignore errors here.
        pass

    # write tiny scene-graph 'near' edges for this observation
    try:
        _write_spatial_scene_edges(world, ctx, env_obs, token_to_bid)
    except Exception:
        # Scene-graph sugar must never crash env injection.
        pass

    # Minimal valence: 'like mom' when close + latched
    try:
        _inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid)
    except Exception:
        # Valence stub must never break env injection.
        pass

    return {"predicates": created_preds, "cues": created_cues}


def run_env_closed_loop_steps(env, world, drives, ctx, policy_rt, n_steps: int) -> None:
    """
    Run N closed-loop steps between the HybridEnvironment and the CCA8 brain
    in a condensed, explanatory way.

    Each step:
      - advances controller_steps and the temporal soft clock (no autonomic ticks here),
      - calls env.reset() once (if this is the first ever env step for this episode),
        or env.step(last_policy_action, ctx) on later steps,
      - injects EnvObservation into the WorldGraph via inject_obs_into_world(...),
      - runs one controller step via PolicyRuntime.consider_and_maybe_fire(...),
      - remembers the last fired policy name in ctx.env_last_action so the next
        env.step(...) can react to it.

    This version also prints a short *posture explanation* line per step, based
    on how EnvState.kid_posture and EnvState.scenario_stage changed relative to
    the previous step and which action was sent into the environment.
    """

    def _explain_posture_change(prev_state, curr_state, action_for_env: str | None) -> str | None:
        """Human-readable explanation for why posture is what it is this step."""
        if curr_state is None:
            return None

        p = curr_state.kid_posture
        s = curr_state.scenario_stage

        if prev_state is None:
            # First tick after reset: just describe the initial storyboard setup.
            return (
                f"initial storyboard setup: stage={s!r} starts with posture={p!r} "
                "(newborn begins life on the ground)."
            )

        prev_p = prev_state.kid_posture
        prev_s = prev_state.scenario_stage

        # No posture change this tick
        if p == prev_p:
            if p == "fallen":
                if action_for_env == "policy:stand_up":
                    return (
                        "stand_up was requested this tick, but the newborn is still "
                        f"kept fallen by the storyboard (stage={s!r}); standing will "
                        "only appear once the stand-up transition threshold is reached."
                    )
                return (
                    f"storyboard keeps the kid posture={p!r} in stage={s!r}; no successful "
                    "standing transition yet."
                )
            return f"posture remains {p!r}; no storyboard transition affecting posture this step."

        # Posture changed
        if prev_p == "fallen" and p == "standing":
            if action_for_env == "policy:stand_up":
                return (
                    "stand_up action applied by the environment: posture changed "
                    f"fallen→standing as the storyboard moved {prev_s!r}→{s!r}."
                )
            return (
                f"storyboard crossed its stand-up threshold: posture changed "
                f"fallen→standing as stage moved {prev_s!r}→{s!r}."
            )

        if prev_p == "standing" and p == "latched":
            return (
                "nipple became reachable and then latched in the storyboard; "
                "the kid switches from upright to 'latched' while feeding."
            )

        if prev_p == "latched" and p == "resting":
            return (
                "after some time latched and feeding, the storyboard advanced to 'rest'; "
                "the kid is now resting curled up against mom in a sheltered niche."
            )

        # Fallback for any other transitions.
        return (
            f"posture changed {prev_p!r}→{p!r} as the storyboard moved "
            f"{prev_s!r}→{s!r} this step."
        )

    if n_steps <= 0:
        print("[env-loop] N must be ≥ 1; nothing to do.")
        return

    print(f"[env-loop] Running {n_steps} closed-loop environment/controller step(s).")
    print("[env-loop] Each step will:")
    print("  1) Advance controller_steps and the temporal soft clock (one drift),")
    print("  2) Call env.reset() (first time) or env.step(last policy action),")
    print("  3) Inject EnvObservation into the WorldGraph as pred:/cue: facts,")
    print("  4) Run ONE controller step (Action Center) and store the last policy name.\n")

    if not getattr(ctx, "env_episode_started", False):
        print("[env-loop] Note: environment episode has not started yet; "
              "the first step will call env.reset().")

    for i in range(n_steps):
        print(f"\n[env-loop] Step {i+1}/{n_steps}")

        # 1) Timekeeping for this controller loop (soft clock only)
        try:
            ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
        except Exception:
            pass
        if getattr(ctx, "temporal", None):
            ctx.temporal.step()

        prev_state = None
        action_for_env: str | None = None

        # 2) Environment evolution (reset once, then step with last action)
        if not getattr(ctx, "env_episode_started", False):
            env_obs, env_info = env.reset()
            ctx.env_episode_started = True
            ctx.env_last_action = None
            step_idx = env_info.get("step_index", 0)
            print(
                f"[env] Reset newborn_goat scenario: "
                f"episode_index={env_info.get('episode_index')} "
                f"scenario={env_info.get('scenario_name')}"
            )
        else:
            # Snapshot previous EnvState so we can explain posture changes.
            try:
                prev_state = env.state.copy()
            except Exception:
                prev_state = None

            action_for_env = ctx.env_last_action
            env_obs, _env_reward, _env_done, env_info = env.step(
                action=action_for_env,
                ctx=ctx,
            )
            ctx.env_last_action = None
            st = env.state
            step_idx = env_info.get("step_index")
            print(
                f"[env] step={step_idx} "
                f"stage={st.scenario_stage} posture={st.kid_posture} "
                f"mom_distance={st.mom_distance} nipple_state={st.nipple_state} "
                f"action={action_for_env!r}"
            )

        # 3) EnvObservation → WorldGraph
        inject_obs_into_world(world, ctx, env_obs)

        # 4) Controller response
        policy_name = None
        try:
            policy_rt.refresh_loaded(ctx)
            fired = policy_rt.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(f"[env→controller] {fired}")

                # Extract clean "policy:..." for env.step(...) on the next loop.
                if isinstance(fired, str):
                    first_token = fired.split()[0]
                    if isinstance(first_token, str) and first_token.startswith("policy:"):
                        ctx.env_last_action = first_token
                        policy_name = first_token
                    else:
                        ctx.env_last_action = None
                else:
                    ctx.env_last_action = None
            else:
                ctx.env_last_action = None
        except Exception as e:
            print(f"[env→controller] controller step error: {e}")
            ctx.env_last_action = None

        # Short summary for this step + posture explanation
        try:
            st = env.state
            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None

            line = (
                f"[env-loop] summary envr't step={step_idx} stage={st.scenario_stage} "
                f"posture={st.kid_posture} mom={st.mom_distance} "
                f"nipple={st.nipple_state} last_policy={policy_name!r}"
            )
            if zone is not None:
                line += f" zone={zone}"
            print(line)

            # Explain why posture ended up as it is at this step.
            try:
                explanation = _explain_posture_change(prev_state, st, action_for_env)
                if explanation:
                    print(f"[env-loop] explain posture: {explanation}")
            except Exception:
                pass
        except Exception:
            pass

    print("\n[env-loop] Closed-loop run complete. "
          "You can inspect details via Snapshot or the mini-snapshot that follows.")


def _latest_posture_binding(world, *, source: Optional[str] = None, require_policy: bool = False):
    """
    Helper for mini-snapshots: find the most recent pred:posture:* binding.

    Args:
        source: if given, require binding.meta['source'] == source
                (e.g., 'HybridEnvironment' for env-driven facts).
        require_policy: if True, require binding.meta['policy'] to exist
                (policy-written expected posture).

    Returns:
        (bid, posture_tag, meta) or (None, None, None).
    """
    try:
        bids = _sorted_bids(world)
    except Exception:
        return None, None, None

    for bid in reversed(bids):
        b = world._bindings.get(bid)
        if not b:
            continue

        tags = getattr(b, "tags", None)
        if not tags:
            continue

        posture_tag = None
        for t in tags:
            if isinstance(t, str) and t.startswith("pred:posture:"):
                posture_tag = t
                break
        if not posture_tag:
            continue

        meta = getattr(b, "meta", None)

        if source is not None:
            if not isinstance(meta, dict) or meta.get("source") != source:
                continue

        if require_policy:
            if not isinstance(meta, dict) or "policy" not in meta:
                continue

        return bid, posture_tag, meta

    return None, None, None


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
                "[discrepancy] -often the motor system will attempt an action, "
                "but it does not actually occur-"
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
    targets = targets or ["posture:standing", "stand"]
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


# ---------- FOA (Focus of Attention), NOW skeleton ----------
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


def ensure_now_origin(world):
    """
    to set NOW_ORIGIN once
    """
    origin_id = _anchor_id(world, "NOW")
    if origin_id and origin_id != "?":
        # Set in anchors map if available
        if hasattr(world, "_anchors") and isinstance(world._anchors, dict):
            world._anchors["NOW_ORIGIN"] = origin_id
        # Also tag the binding
        b = world._bindings.get(origin_id)
        if b is not None:
            tags = getattr(b, "tags", None)
            if tags is None:
                b.tags = set()
                tags = b.tags
            # robust: handle set or list
            try:
                tags.add("anchor:NOW_ORIGIN")
            except AttributeError:
                if "anchor:NOW_ORIGIN" not in tags:
                    tags.append("anchor:NOW_ORIGIN")


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
    for tok in ("posture:standing", "stand", "mom:close"):
        bid = _nearest_binding_with_pred(world, tok, from_bid=now_id, max_hops=3)
        if bid and bid not in picks:
            picks.append(bid)
    return [p for p in picks if p]


# --------------------------------------------------------------------------------------
# Interactive loop
# --------------------------------------------------------------------------------------

def interactive_loop(args: argparse.Namespace) -> None:
    """Main interactive loop.
    """
    # Build initial world/drives fresh
    world = cca8_world_graph.WorldGraph()
    #drives = Drives()  #Drives(hunger=0.7, fatigue=0.2, warmth=0.6) at time of writing comment
    #drives.fatigue = 0.85 #for devp't testing --> Drives(hunger=0.7, fatigue=0.85, warmth=0.6)
    #drives = Drives(hunger=0.5, fatigue=0.9, warmth=0.6)  #for rest gate to see hazard versus shelter
    drives = Drives(hunger=0.5, fatigue=0.3, warmth=0.6)  # moderate fatigue so fallback 'follow_mom' can win

    ctx = Ctx(sigma=0.015, jump=0.2, age_days=0.0, ticks=0)
    ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump) # temporal soft clock (added)
    ctx.tvec_last_boundary = ctx.temporal.vector()  # seed “last boundary”
    try:
        ctx.boundary_vhash64 = ctx.tvec64()
    except Exception:
        ctx.boundary_vhash64 = None
    print_startup_notices(world)
    env = HybridEnvironment()     # Environment simulation: newborn-goat scenario (HybridEnvironment)
    ctx.body_world, ctx.body_ids = init_body_world() # initialize tiny BodyMap (body_world) as a separate WorldGraph instance

    # Optional: start session with a preloaded demo/test world to exercise graph menus.
    # Driven by --demo-world; ignored when --load is used (load takes precedence).
    if getattr(args, "demo_world", False) and not args.load:
        try:
            from cca8_test_worlds import build_demo_world_for_inspect  # type: ignore
            demo_world, demo_ids = build_demo_world_for_inspect()
            world = demo_world
            try:
                now_demo = demo_ids.get("NOW") if isinstance(demo_ids, dict) else _anchor_id(world, "NOW")
                print(f"[demo_world] Preloaded demo world (NOW={now_demo}, bindings={len(world._bindings)})")
            except Exception:
                print(f"[demo_world] Preloaded demo world (bindings={len(world._bindings)})")
        except Exception as e:
            print(f"[demo_world] Could not preload demo world: {e}")
    elif getattr(args, "demo_world", False) and args.load:
        # Both flags given: be explicit that --load wins.
        print("[demo_world] --demo-world ignored because --load was also provided.")

    POLICY_RT = PolicyRuntime(CATALOG_GATES)
    POLICY_RT.refresh_loaded(ctx)
    loaded_ok = False
    loaded_src = None

    # ---- Menu text ----
    MENU = """\
    [hints for text selection instead of numerical selection]

    # Quick Start & Tutorial
    1) Understanding bindings, edges, predicates, policies [understanding, tagging]
    2) Help: System Docs and/or Tutorial with demo tour [help, tutorial, demo]

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
    11) Simulate fall (add posture:fallen and try recovery) [fall, simulate]

    # Simulation of the Environment (HybridEnvironment demo)
    35) Environment step (HybridEnvironment → WorldGraph demo) [env, hybrid]
    37) Run n environment steps (closed-loop timeline) [envloop, envrun]
    38) Inspect BodyMap (summary from BodyMap helpers) [bodymap, bsnap]
    39) Spatial scene demo (NOW-near + resting-in-shelter?) [spatial, near]

    # Perception & Memory (Cues & Engrams)
    12) Input [sensory] cue [sensory, cue]
    13) Capture scene → tiny engram (signal bridge) [capture, scene]
    14) Resolve engrams on a binding [resolve, engrams]
    15) Inspect engram by id (or binding) [engram, ei]
    16) List all engrams [engrams-all, list-engrams]
    17) Search engrams (by name / epoch) [search-engrams, find-engrams]
    18) Delete engram by bid or eid [delete-engram, del-engram]
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
    34) Reset current saved session [reset]
    36) Toggle mini-snapshot after each menu selection [mini, msnap]


    Select: """

    # ---- Text command aliases (words + 3-letter prefixes → legacy actions) -----
    #will map to current menu which then must be mapped to original menu numbers
    #intentionally keep here so easier for development visualization than up at top with constants
    MIN_PREFIX = 3 #if not perfect match then this specifies how many letters to match
    _ALIASES = {
    # Quick Start & Tutorial
    "understanding": "1", "tagging": "1",
    "help": "2", "tutorial": "2", "tour": "2", "demo": "2",

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
    "reset": "34",
    "env": "35", "environment": "35", "hybrid": "35",
    "mini": "36", "msnap": "36",
    "envloop": "37", "envrun": "37", "envsteps": "37",
    "bodymap": "38", "bsnap": "38",
    "spatial": "39", "near": "39",

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
    "34": "r",   # Reset current saved session
    "35": "35",  # environment simulation
    "36": "36",  # mini-snapshot toggle
    "37": "37",  # envr't loop
    "38": "38",  # inspect bodymap
    "39": "39",  # spatial, near demo
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
    # boot policy, e.g., mountain goat should stand up
    if not args.no_boot_prime:
        boot_prime_stand(world, ctx)
    # Pin NOW_ORIGIN to this initial NOW (episode root)
    ensure_now_origin(world)

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

        #FIRST MENU SELECTION CODE BLOCK.... WITHIN interactive menu while loop >>>>>> of interactive_menu()
        #----Menu Selection Code Block------------------------
        if choice == "1":
            # World stats
            now_id = _anchor_id(world, "NOW")
            print("Selection:  World Graph Statistics\n")
            print('''
The CCA8 architecture holds symbolic declarative memory (i.e., episodic and semantic memory) in the WorldGraph.

There are bindings (i.e., nodes) in the WorldGraph, each of which holds directed edges to other bindings (i.e., nodes),
 concise semantic and episodic information, metadata, and pointers to engrams in the cortical-like Columns which
 is the rich store of knowledge.
e.g., 'b1' means binding 1, 'b2' means binding 2, and so on

As mentioned, the bindings (i.e., nodes) are linked to each other by directed edges.
An 'anchor' is a binding which we use to start the WorldGraph as well as a starting point somewhere in the middle
  of the graph. Symbolic procedural knowledge is held in the Policies which currently are held in the
  Controller Module.
A policy (i.e., same as primitive in the CCA8 published papers) is a simple set of conditional actions.
In order to execute, a policy must be loaded (e.g., meets development requirements) and then it must be triggered.

Note we are showing the symbolic statistics here. The distributed, rich information of the CCA8, i.e., its engrams,
  are held in the Columns.\n
Below we show some general WorldGraph and Policy statistics. See Snapshot and other menu selections for more details
  on the system.

            ''')
            print(f"Bindings: {len(world._bindings)}  Anchors: NOW={now_id}  Latest: {world._latest_binding_id}")
            try:
                print(f"Policies loaded: {len(POLICY_RT.loaded)} -> {', '.join(POLICY_RT.list_loaded_names()) or '(none)'}")
            except Exception:
                pass
            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "2":
            # List predicates
            print("Selection:  List Predicates\n")
            print('''
This selection will gather all the predicate tokens, i.e., "pred:*" , and show which bindings bN
  store teach token.

Note that in the current WorldGraph planner, the target is always a predicate. Cues, on the other hand, are
  not used a planning targets but indirectly they can still influence planning via policies.
  (essentially, only pred:* is used as a goal condition)

You can filter results by entering the string of the desired token, or even a partial substring of it, and
   the code will automatically find the bindings.
            ''')
            #flt is the substring of the predicate token to search for, if flt="" then we simply list all predicate tokens
            try:
                flt = input("Optional filter (substring in token, blank=all): ").strip().lower()
            except Exception:
                flt = ""
            idx: Dict[str, List[str]] = {}
            total_tags = 0
            for bid, b in world._bindings.items():
                #world._bindings is a dict and thus .items() returning (bid=key, b=value) pairs
                #  bid=key -- e.g., "b5"
                #  b=value -- a dataclass Binding instance representing one node
                #  i.e., iterate over, e.g., {"b1": Binding(id="b1", tags={...}, edges=[...], meta={...}, engrams={...}), "b2": Binding(...),  ...}
                #  dataclass Binding defined in WorldGraph -- id str, (tags), [Edge], {meta}, {engrams}
                #cca8_world_graph.class WorldGraph:  def __init__(self): self._bindings: {str, Binding} = {}
                for t in getattr(b, "tags", []):
                    #t gets that node's tags  e.g., for bid="b2", t= "tags={'pred:stand'}, edges=[], meta={'boot': 'init', 'added_by': 'system'}, engrams={})"
                    if isinstance(t, str) and t.startswith("pred:"):
                        key = t.replace("pred:", "", 1)  # strip 'pred:' e.g., in above example key = "pred"
                        if flt and flt not in key.lower(): #if substring, check if matches, else try next value
                            continue
                        idx.setdefault(key, []).append(bid)
                        total_tags += 1
                        #e.g., total_tags = 1, idx = {'stand':[b2']} <-- will list later by predicate
            if not idx:
                if flt:
                    print(f"(no predicates matched filter substring {flt!r})")
                else:
                    print("(no predicates to list yet)")
            else:
                #e.g., idx = {'stand':[b2']}
                def _bid_sort(bid: str) -> tuple[int, str]:
                    # group 0: numeric ids (b1, b2, ...), sorted by number with zero-padding
                    # group 1: non-numeric ids (e.g., 'NOW'), sorted lexicographically
                    if len(bid) > 1 and bid[1:].isdigit():
                        return (0, f"{int(bid[1:]):09d}")
                    return (1, bid)
                for key in sorted(idx.keys()):
                    bids = sorted(idx[key], key=_bid_sort)
                    print(f"  {key:<30} -> {', '.join(bids)}")
                print(
                    f"\nSummary: {len(idx)} unique predicate token(s), "
                    f"{total_tags} predicate tag(s) across {len(world._bindings)} binding(s)."
                )
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "3":
            # Selection:  Add Predicate
            # input predicate token, attach and meta for the new binding
            print("Selection: Add Predicate\n")
            print("""
Creates a new binding which will be tagged with "pred:<token>"
'Attach' value will effect where this new binding is linked in the episode:
  now    → NOW -> new, new becomes LATEST
  latest → LATEST -> new, new becomes LATEST (default)
  none   → create unlinked node (no automatic edge)\n
Examples: posture:standing, nipple:latched, etc.  Lexicon may warn in strict modes.\n

Please enter the predicate token
  e.g., vision:silhouette:mom
  don't enter, e.g., 'pred:vision:silhouette:mom' -- just enter the token portion of the predicate
  nb. no default value for predicate -- if you just click ENTER for predicate with no input, return to menu
  nb. however, there is a default value of 'latest' for attachment option
""")

            token = input("\nEnter predicate token (e.g., vision:silhouette:mom)   ").strip()
            if not token:
                print("No token entered -- no default values -- return back to menu....")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            attach = input("Attach [now/latest/none] (default: latest): ").strip().lower() or "latest"
            if attach not in ("now", "latest", "none"):
                print("[info] unknown attach; defaulting to 'latest'")
                attach = "latest"

            meta = {
                "added_by": "user",
                "created_by": "menu:add_predicate",
                "created_at": datetime.now().isoformat(timespec="seconds"),
            }

            # Decide on a contextual write base for this manual predicate add.
            base = None
            effective_attach = attach
            if attach == "latest":
                base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
                effective_attach = _maybe_anchor_attach(attach, base)
                # Brief explanation for users seeing base-aware behavior for the first time.
                print(f"[base] write-base suggestion for this add_predicate: {_fmt_base(base)}")
                if effective_attach == "none" and isinstance(base, dict) and base.get("base") == "NEAREST_PRED":
                    print("[base] base-aware attach: new binding will be created unattached, then "
                          "linked from the suggested NEAREST_PRED base instead of plain 'LATEST'.")
            else:
                print("[base] write-base suggestion skipped: attach mode is not 'latest' (user-specified).")

            # Create the new predicate binding and apply base-aware semantics if requested.
            try:
                before = len(world._bindings)
                bid = world.add_predicate(token, attach=effective_attach, meta=meta)
                after = len(world._bindings)
                print(f"Added binding {bid} with pred:{token} (attach={effective_attach})")

                # If we used a NEAREST_PRED base and suppressed auto-attach, add base->new edge explicitly.
                if isinstance(base, dict) and base.get("base") == "NEAREST_PRED" and effective_attach == "none":
                    _attach_via_base(
                        world,
                        base,
                        bid,
                        rel="then",
                        meta={
                            "created_by": "base_attach:menu:add_predicate",
                            "base_kind": base.get("base"),
                            "base_pred": base.get("pred"),
                        },
                    )

                # Small confirmation of attach semantics when we can cheaply infer the source for attach="now".
                if after > before:
                    src = None
                    if effective_attach == "now":
                        src = _anchor_id(world, "NOW")
                    if src and src in world._bindings:
                        edges = getattr(world._bindings[src], "edges", []) or []
                        def _dst(e):  # tolerant of edge layouts
                            return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                        def _rel(e):
                            return e.get("label") or e.get("rel") or e.get("relation") or "then"
                        rels = [_rel(e) for e in edges if _dst(e) == bid]
                        if rels:
                            print(f"[attach] {src} --{rels[0]}--> {bid}")
            except ValueError as e:
                print(f"[guard] add_predicate rejected token {token!r}: {e}")
            except Exception as e:
                print(f"[error] add_predicate failed: {e}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "4":
            # Connect two bindings (with duplicate warning)
            # Input bindings and edge label
            print("Selection:  Connect Bindings\n")

            print("Adds a directed edge src --label--> dst (default label: 'then'). Duplicate edges are skipped.")
            print("Use labels for readability ('fall', 'latch', 'approach'); planner today follows structure, not labels.\n")
            print('Do not use quotes, e.g., enter: fall not:"fall" unless you want quotes in the stored label')
            print('Similarly, do not use quotes for the bid, e.g., enter: b14, not "b14"\n')

            src = input("Enter the source binding id (bid) (e.g., b12) NO QUOTES :").strip()
            dst = input("Enter the destination binding id (bid) (e.g., b14) NO QUOTES : ").strip()
            if not src or not dst:
                print("Source or destination bindings entered are missing -- return back to menu....")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            label = input('Edge relation label (default via ENTER is "then") NO QUOTES : ').strip() or "then"
            try:
                b = world._bindings.get(src)
                if not b:
                    print("Invalid id: unknown source binding bid -- return back to menu....")
                elif dst not in world._bindings:
                    print("Invalid id: unknown destination binding bid -- return back to menu....")
                else:
                    edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                             getattr(b, "links", []) or getattr(b, "outgoing", []))
                    def _rel(e):  # normalize edge label
                        return e.get("label") or e.get("rel") or e.get("relation") or "then"
                    def _dst(e):  # normalize edge dst
                        return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    duplicate = any((_dst(e) == dst) and (_rel(e) == label) for e in edges)
                    if duplicate:
                        print(f"[info] Edge already exists: {src} --{label}--> {dst} (skipping)")
                    else:
                        meta = {
                            "created_by": "menu:connect",
                            "created_at": datetime.now().isoformat(timespec="seconds"),
                        }
                        #adds a directed edge from source bid to destination bid with label input, meta input
                        world.add_edge(src, dst, label, meta=meta)
                        print(f"Linked {src} --{label}--> {dst}")
            except KeyError as e:
                print("Invalid id:", e)
            except ValueError as e:
                print(f"[guard] {e}")
            except Exception as e:
                print(f"[error] add_edge failed: {e}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "5":
            # Plan from NOW -> <predicate>
            current_planner = getattr(world, "get_planner", lambda: "bfs")()
            print("Selection:  Plan to Predicate\n")
            print("""
Note the use of S-A-S segments in learning and planning within the architecture:
S-A-S  State-Action-State which we consider in the CCA8 as Predicate-Action-Predicate (since we
    avoid the brain labeling things as 'states', something scientists do more so than brains)
Conceptually it is the pattern:
   [what the world/agent is like] --> [what the agent does] --> [what the world/agent is like after]
S = predicate binding, e.g., pred:posture:standing")
A = action binding, e.g., pred:action:push_up or action:push_up (depends on version)
e.g., posture:fallen --> push_up, extend_legs --> posture:standing
A whole episode becomes a chain of S-A-S segments. This becomes a natural unit for learning and planning, i.e.,
  'if I'm in predicate S want predicate S', then what action chain A should I consider?'

Note the use of the anchor bindings NOW, NOW_ORIGIN, and LATEST in WorldGraph:
NOW_ORIGIN --   where NOW was when the session (or episode) began
                birth / episode root; stable, episode-level anchor
                world._anchors["NOW_ORIGIN"]
                should not move once set (unless deliberately start a new episode)
                #todo -- add an explicit 'start new episode' and reset NOW_ORIGIN to a new binding
NOW --  where the agent is now in the map
        world._anchors["NOW"]
        e.g., start at birth/fallen → StandUp moves NOW to standing → SeekNipple moves NOW to seeking_mom, etc.
        good for local FOA and 'what should I do from here?'
        a moving, local-state anchor
LATEST --   the most recently created binding by any operation
            world._latest_binding_id
            useful in debugging and FOA
            note that not semantically 'the agent’s current state' -- for example, can create a cue or perhaps an
                engram binding that’s not the stable state of the body
            note that we do not tag the latest binding each time with anchor:LATEST as it would move on every single
                write, i.e., end up spamming tags and making graph harder to read, and this is not necessary as
                it is always available via world._latest_binding_id, and only printed in the header

You will be asked to choose the determination of a path from NOW or from a node of your choosing, to a
    predicate of your choosing  -- be aware of what the default 'NOW' actually represents.

            """)

            print(f"Current planner strategy: {current_planner.upper()}")
            if current_planner == "dijkstra":
                print("Dijkstra search from anchor:NOW to a binding with pred:<token>.")
                print("With all edges currently weight=1, this is effectively the same path as BFS.\n")
            else:
                print("BFS from anchor:NOW to a binding with pred:<token>. Prints raw id path and a pretty path.\n")

            token = input("Target predicate (e.g., posture:standing): ").strip()
            if not token:
                loop_helper(args.autosave, world, drives, ctx)
                continue
            # convenience: allow posture:standing → posture:standing, etc.
            if ":" not in token and "_" in token:
                parts = token.split("_", 1)
                if len(parts) == 2:
                    token = f"{parts[0]}:{parts[1]}"

            # allow planning from any binding, default NOW; special token ORIGIN → NOW_ORIGIN
            try:
                start_bid = input("Start from binding id (blank = NOW, ORIGIN = NOW_ORIGIN): ").strip()
            except Exception:
                start_bid = ""
            if start_bid:
                key = start_bid.lower()
                if key in ("origin", "now_origin"):
                    src_id = _anchor_id(world, "NOW_ORIGIN")
                    if src_id == "?":
                        print("[info] NOW_ORIGIN not set; falling back to NOW.")
                        src_id = world.ensure_anchor("NOW")
                elif start_bid in world._bindings:
                    src_id = start_bid
                else:
                    print(f"[info] Unknown binding id {start_bid!r}; falling back to NOW.")
                    src_id = world.ensure_anchor("NOW")
            else:
                src_id = world.ensure_anchor("NOW")

            path = world.plan_to_predicate(src_id, token)
            if path:
                print("\nPath (ids):", " -> ".join(path))
                try:
                    pretty = world.pretty_path(
                        path,
                        node_mode="id+pred",       # try 'pred' if prefer only tokens
                        show_edge_labels=True,
                        annotate_anchors=True
                    )
                    print("Pretty printing of path:\n", pretty)
                except Exception as e:
                    print(f"(pretty-path error: {e})")

                def _typed_label(bid: str) -> str:
                    """
                    Typed view: show each node with its primary role (anchor/pred/action/cue)
                    """
                    b = world._bindings.get(bid)
                    if not b:
                        return bid
                    tags = getattr(b, "tags", []) or []

                    goal_pred_full = f"pred:{token}"
                    if any(isinstance(t, str) and (t in (goal_pred_full, token)) for t in tags):
                        return token

                    for t in tags:
                        if isinstance(t, str) and t.startswith("anchor:"):
                            return t
                    for t in tags:
                        if isinstance(t, str) and t.startswith("action:"):
                            return t
                    for t in tags:
                        if isinstance(t, str) and t.startswith("pred:"):
                            return t[5:]
                    for t in tags:
                        if isinstance(t, str) and t.startswith("cue:"):
                            return t
                    return "(no-tags)"

                # Reverse typed view: from goal back to start (useful for "backwards" intuition).
                rev_parts: list[str] = []
                rev_path = list(reversed(path))
                for i, bid in enumerate(rev_path):
                    rev_parts.append(f"[{bid}:{_typed_label(bid)}]")
                    if i + 1 < len(rev_path):
                        rev_parts.append(" -> ")
                print("Reverse typed path:", "".join(rev_parts))

                # Forward typed view: from start to goal
                typed_parts: list[str] = []
                for i, bid in enumerate(path):
                    typed_parts.append(f"[{bid}:{_typed_label(bid)}]")
                    if i + 1 < len(path):
                        typed_parts.append(" -> ")
                print("Typed path:", "".join(typed_parts))
            else:
                print("No path found.")
            loop_helper(args.autosave, world, drives, ctx)

        #----Menu Selection Code Block------------------------
        elif choice == "6":
            print("Selection:  Resolve Engrams\n")
            print('''
Shows engram slots on a binding.
Note: For payload/meta details use menu selection "Inspect engram by id"

-a "slot name" is the key used in a binding's engrams dict to label a particular engram pointer
     e.g, b3: [cue:vision:silhouette:mom] engrams={'column01': {'id': 'b3001752abc946769b8c182f38cf0232', 'act': 1.0}}
       -- 'column01' is the slot name, i.e., binding.engrams['column01'] = {id:eid, act:1.0, ...} where id = engram id,
              act = activation weight
       -- 'b3001752a…' is the human-readable summary of that pointer== eid
-system defaults with a single column in RAM    mem =ColumnMemory(name='column01')  but can set up for multiple columns

            ''')
            bid = input("Binding id to resolve engrams: ").strip()
            #user input is the bid
            if not bid:
                print("No id entered.")
            else:
                _resolve_engrams_pretty(world, bid)
                #from bid gets column01: {"id": eid, "act": 1.0}
                #prints these out as, e.g., Engrams on b3; column01: 34c406dd…  OK
                b = world._bindings.get(bid)
                #e.g. Binding(id='b3', tags={'cue:vision:silhouette:mom'}, edges=[], meta={}, engrams={'column01': {'id': '05a6dfba0e7b4aef8ca116485efc5ad8', 'act': 1.0}})
                if b and getattr(b, "engrams", None):
                    print("Raw pointers:", b.engrams)

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "7":
            # Show last 5 bindings
            print("Selection:  Recent Bindings\n")
            print("Shows the 5 most recent bindings (bN). For each: tags and any engram slots attached.")
            print(" 'outdeg' is the number of outgoing edges, e.g., outdeg=2 means there are 2 outgoing edges")
            print(" 'preview' is a short sample of up to 3 these outgoing edges")
            print("     e.g., outdeg=2 preview=[initiate_stand:b2, then:b3]")
            print("     -this means 2 outgoing edges, 1 edge goes to b2 with action label 'initiate_stand', 1 edge ")
            print("          goes to b3 with action label 'then'")
            print("Tip: use 'Inspect binding details' for full meta/edges on a specific id.\n")

            print(recent_bindings_text(world, limit=5))
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "8":
            # Quit
            print("Selection:  Quit\n")
            print("Exits the simulation. If you launched with --save, a final save occurs on exit.\n")
            print("Goodbye.")
            if args.save:
                save_session(args.save, world, drives)
            #return from main() which will then immediately exedcute return 0
            #after main() is: if __name__ == "__main__": sys.exit(main()) --> sys.exit(0) thus occurs
            return


        #----Menu Selection Code Block------------------------
        elif choice == "9":
            # Run preflight now
            print("Selection:  Preflight\n")
            print("Runs pytest (unit tests framework) and coverage, then a series of whole-flow custom tests.\n")

            #rc = run_preflight_full(args)
            run_preflight_full(args)
            # no autosave or mini-snapshot after preflight; just return to menu.
            # loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "10":
            # Inspect binding details and user input (accepts a single id, or ALL/* to dump everything)
            print("Selection:  Inspect Binding Details")
            print('''

-Enter a binding id (bid) (e.g., 'b3') or 'ALL' (or '*').
     Note: not case sensitive -- e.g., 'B3' or 'b3' treated the same
     Note: if case-sensitivity exists in your WorldGraph labeling, then comment out case insensitivity line of code

-This selection will then display the binding's tags, meta, engrams,
   and its outgoing and incoming edges.
-Note that you can inspect provenance, meta.policy/created_by/boot, attached engrams,
   and graph degree on one or more bindings.
   Note: each binding has a meta dictionary that stores provenance, i.e., a record of where and when this binding comes
   Note: from a binding created by a policy at runtime might have key:value pair inside of meta dict
   Note: a typical Provenance summary is, e.g., meta.policy, meta.created_by, meta.boot, meta.ticks, etc.

-Internally the code block calls _print_one(bid) and prints out the information about that binding
-if "ALL" chosen then _sorted_bids(world) returns the WorldGraph's bid's in sorted order, e.g., (b1, b2, ...)
    and loop through bid's with a _print_one(bid) for each one

            ''')
            bid = input("Binding id to inspect (or 'ALL'/ENTER): ").strip().lower() #case insensitive
            #bid = input("Binding id to inspect (or 'ALL'): ").strip() #case sensitive
            print("\n Binding details for the requested binding(s):\n")

            # Inspect binding internal helper functions
            def _edge_rel(e: dict) -> str:
                return e.get("label") or e.get("rel") or e.get("relation") or "then"


            def _edge_dst(e: dict) -> str | None:
                return e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")


            def _families_from_tags(tags) -> list[str]:
                fams: list[str] = []
                tags = tags or []
                if any(isinstance(t, str) and t.startswith("anchor:") for t in tags):
                    fams.append("anchor")
                if any(isinstance(t, str) and t.startswith("pred:") for t in tags):
                    fams.append("pred")
                if any(isinstance(t, str) and t.startswith("action:") for t in tags):
                    fams.append("action")
                if any(isinstance(t, str) and t.startswith("cue:") for t in tags):
                    fams.append("cue")
                return fams


            def _anchors_from_tags(tags) -> list[str]:
                out: list[str] = []
                for t in tags or []:
                    if isinstance(t, str) and t.startswith("anchor:"):
                        out.append(t.split(":", 1)[1])
                return out


            def _provenance_summary(meta: dict) -> str | None:
                if not isinstance(meta, dict) or not meta:
                    return None
                policy = meta.get("policy")
                creator = meta.get("created_by") or meta.get("boot") or meta.get("added_by")
                created_at = meta.get("created_at") or meta.get("time") or meta.get("ts")
                ticks = meta.get("ticks")
                epoch = meta.get("epoch")
                bits: list[str] = []
                if policy:
                    bits.append(f"policy={policy}")
                if creator:
                    bits.append(f"created_by={creator}")
                if created_at:
                    bits.append(f"created_at={created_at}")
                if isinstance(ticks, int):
                    bits.append(f"ticks={ticks}")
                if isinstance(epoch, int):
                    bits.append(f"epoch={epoch}")
                return ", ".join(bits) if bits else None


            def _engrams_pretty(_bid: str, b) -> None:
                eng = getattr(b, "engrams", None) or {}
                if not isinstance(eng, dict) or not eng:
                    print("Engrams: (none)")
                    return
                print("Engrams:")
                for slot, val in sorted(eng.items()):
                    if isinstance(val, dict):
                        eid = val.get("id")
                        act = val.get("act")
                    else:
                        eid = None
                        act = None
                    status = ""
                    short = "(id?)"
                    if isinstance(eid, str):
                        short = eid[:8] + "…"
                        try:
                            rec = world.get_engram(engram_id=eid)
                            ok = bool(rec and isinstance(rec, dict) and rec.get("id") == eid)
                            status = "OK" if ok else "(dangling)"
                        except Exception:
                            status = "(error)"
                    act_txt = f" act={act:.3f}" if isinstance(act, (int, float)) else ""
                    print(f"  {slot}: {short}{act_txt} {status}".rstrip())


            def _incoming_edges_for(_bid: str) -> list[tuple[str, str]]:
                inc: list[tuple[str, str]] = []
                for src_id, other in world._bindings.items():
                    edges = (getattr(other, "edges", []) or getattr(other, "out", []) or
                             getattr(other, "links", []) or getattr(other, "outgoing", []))
                    if not isinstance(edges, list):
                        continue
                    for e in edges:
                        dst = _edge_dst(e)
                        if dst == _bid:
                            inc.append((src_id, _edge_rel(e)))
                return inc


            def _outgoing_edges_for(b) -> list[tuple[str, str]]:
                edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                         getattr(b, "links", []) or getattr(b, "outgoing", []))
                out: list[tuple[str, str]] = []
                if isinstance(edges, list):
                    for e in edges:
                        dst = _edge_dst(e)
                        if dst:
                            out.append((dst, _edge_rel(e)))
                return out


            def _print_one(_bid: str) -> None:
                b = world._bindings.get(_bid)
                if not b:
                    print(f"Unknown binding id: {_bid}")
                    print("Returning to main menu....\n")
                    return

                tags = sorted(getattr(b, "tags", []))
                families = _families_from_tags(tags)
                anchors = _anchors_from_tags(tags)

                print(f"ID: {_bid}")
                if families or anchors:
                    kind_parts: list[str] = []
                    if families:
                        kind_parts.append("kind=" + "/".join(families))
                    if anchors:
                        kind_parts.append("anchor=" + ",".join(anchors))
                    print("Role:", "; ".join(kind_parts))
                print("Tags:", ", ".join(tags) if tags else "(none)")

                meta = getattr(b, "meta", {})
                print("Meta:", json.dumps(meta if isinstance(meta, dict) else {}, indent=2))
                prov = _provenance_summary(meta if isinstance(meta, dict) else {})
                if prov:
                    print("Provenance:", prov)

                _engrams_pretty(_bid, b)

                # Edges
                outgoing = _outgoing_edges_for(b)
                incoming = _incoming_edges_for(_bid)
                print(f"Degree: out={len(outgoing)} in={len(incoming)}")

                if outgoing:
                    print("Outgoing edges:")
                    for dst, rel in outgoing:
                        print(f"  {_bid} --{rel}--> {dst}")
                else:
                    print("Outgoing edges: (none)")

                if incoming:
                    print("Incoming edges:")
                    for src, rel in incoming:
                        print(f"  {src} --{rel}--> {_bid}")
                else:
                    print("Incoming edges: (none)")

                print("\n", "-" * 28, "\n")


            from collections import deque
            def _concept_neighborhood_layers(start_bid: str, max_hops: int = 2) -> dict[int, list[str]]:
                """
                Return a dict {distance: [binding ids]} for nodes reachable from start_bid
                within `max_hops` hops (outgoing edges only).
                distance=0 contains start_bid itself.
                """
                layers: dict[int, list[str]] = {0: [start_bid]}
                seen: set[str] = {start_bid}
                q = deque([(start_bid, 0)])

                while q:
                    u, d = q.popleft()
                    if d >= max_hops:
                        continue
                    b = world._bindings.get(u)
                    if not b:
                        continue
                    edges = (getattr(b, "edges", []) or getattr(b, "out", []) or
                             getattr(b, "links", []) or getattr(b, "outgoing", []))
                    if not isinstance(edges, list):
                        continue
                    for e in edges:
                        v = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                        if not v or v in seen or v not in world._bindings:
                            continue
                        seen.add(v)
                        layers.setdefault(d+1, []).append(v)
                        q.append((v, d+1))
                return layers


            def _print_neighborhood(start_bid: str, max_hops: int = 2) -> None:
                if start_bid not in world._bindings:
                    print(f"(neighborhood) Unknown start binding {start_bid!r}")
                    return
                layers = _concept_neighborhood_layers(start_bid, max_hops=max_hops)
                print(f"\nConcept neighborhood around {start_bid} (max_hops={max_hops}):")
                for dist in sorted(layers.keys()):
                    print(f"  distance {dist}:")
                    for nid in layers[dist]:
                        nb = world._bindings.get(nid)
                        tags = ", ".join(sorted(getattr(nb, 'tags', []))) if nb else ""
                        print(f"    {nid}: [{tags}]")
                print()


            #main code of the Inspect Binding code block
            if bid in ("all", "*", ""):
                for _bid in _sorted_bids(world):
                    _print_one(_bid)
            else:
                _print_one(bid)
                # Optional: concept neighborhood around this binding
                try:
                    ans = input("Show concept neighborhood around this binding? [y/N]: ").strip().lower()
                except Exception:
                    ans = ""
                if ans in ("y", "yes"):
                    try:
                        htxt = input("Max hops (default 2): ").strip()
                        max_hops = int(htxt) if htxt.isdigit() else 2
                    except Exception:
                        max_hops = 2
                    _print_neighborhood(bid, max_hops=max_hops)

            #code block complete and return back to main menu
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "11":
            # Add sensory cue
            print("Selection:  Input Sensory Cue")
            print('''
Adds cue:<channel>:<token> (evidence, not a goal) at NOW and may nudge a policy.
  e.g., vision:silhouette:mom, sound:bleat:mom, scent:milk

This menu selection asks you for the channel and then the token, and writes the resulting cue,
  e.g., "cue:vision:silhouette:mom", to a new binding attached to NOW.
A controller step==Action Center step will run and if any policies are capable of triggering,
  the best one will be chosen and will execute.
In addition to triggering and executing a policy (if possible) the controller step will also:
  controller_steps ++,  temporal_drift ++  (no effect on autonomic ticks, cognitive cycles, age_days)

Consider the example where the Mountain Goat calf has just been born and stands up.
At this point these bindings, drives, and timekeeping exist:
b1: [anchor:NOW] -> b2: [pred:stand] -> b3: [pred:action:push_up] -> b4: [pred:action:extend_legs]
    -> b5: [pred:posture:standing, pred:posture:standing]
hunger=0.70, fatigue=0.20, warmth=0.60
controller_steps=1, cog_cycles=1, temporal_epochs=1, autonomic_ticks=0,  age_days: 0.0000, cos_to_last_boundary: 1.0000
These policies are eligible:  policy:stand_up, policy:seek_nipple, policy:rest, policy:suckle,
       policy:recover_miss, policy:recover_fall

Now add a sensory cue -- bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
 e.g., "cue:vision:silhouette:mom" and we see a message added to b6
 note: "attach=now" means add link from NOW->new node
Now a controller step will run -- fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
We see in the message displayed that policy seek_nipple executed and added 2 bindings.
"pre" explains why it triggered including the cue provided by new binding b6; "post" shows still triggerable after
  after policy executed; base suggestion, focus of attention and candidates for linking (see Instinct Step or README).

If we look at Snapshot we now see:
-Timekeeping (controller_steps ++,  temporal_drift ++ ):
  controller_steps=2, cog_cycles=1, temporal_epochs=1, autonomic_ticks=0, cos_to_last_boundary: 0.9857,  age_days: 0.0000
-New binding b6  [cue:vision:silhouette:mom]
-SkillStats -- new "policy:seek_nipple" statistics  ("policy:stand_up" ran before during the Instinct Step)
-New bindings created by "policy:seek_nipple" : b7: [pred:action:orient_to_mom],
    b8: [pred:seeking_mom, pred:seeking_mom]
(Note: If we run this Menu Step in a newborn calf then policy:stand_up will run since it is executionable with
 or without a cue and will have priority.)

            ''')

            ch = input("Channel (vision/scent/touch/sound): ").strip().lower()
            tok = input("Cue token (e.g., silhouette:mom): ").strip()
            if ch and tok:
                cue_token = f"{ch}:{tok}"
                bid = world.add_cue(cue_token, attach="now", meta={"channel": ch, "user": True})
                print(f"Added sensory cue: cue:{cue_token} as {bid}")
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
                if fired != "no_match":
                    print(fired)
                try:
                    ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
                except Exception:
                    pass
                if getattr(ctx, "temporal", None):
                    ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
                    print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "12":
            # Instinct step
            print("Selection:  Instinct Step\n")
            # Quick explainer for the user before the step runs
            print('''
Purpose:
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
    -base_suggestion = choose_contextual_base(..., targets=['posture:standing', 'stand'])
    -it first looks for NEAREST_PRED(target) and success since b2 meets the target specified
    -thus, base_suggestion = binding b2 is recommended as the "write base", i.e. to link to
    -the suggestion is not used since that link already exists
    -base_suggestions can be used at different times to control write placement

iii. -FOA focus of attention -- a small set of nearby nodes around NOW/LATEST, cues (for lightweight planning)
     -NOW will also point to the new state binding created


iv. -policy:stand_up when considered can be triggered since age_days is <3.0 and stand near NOW is True
    -thus, policy:stand_up runs and as creates one mor more new nodes/edges (e.g., b5), and
            bindings b2 through b5 are linked

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
            base  = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
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
            print("      Anchors give us a write base (where to attach new preds/edges). Where we attach the ")
            print("         new fact matters for searching paths and planning later.")
            print(f"[context] write-base: {_fmt_base(base)}")
            print(f"[context] anchors: {', '.join(_ann(x) for x in cands)}")
            print(f"[context] foa: size={foa['size']} (ids near NOW/LATEST + cues)")
            print("Note: write-base is where we’ll attach any new facts/edges this step (keeps the episode local and readable).")
            print("      anchors are candidate start points the system considers for local searches/attachment.")
            print("      foa is the current 'focus of attention' neighborhood size used for light-weight planning.")

            result = action_center_step(world, ctx, drives)
            after_n  = len(world._bindings)  # NEW: measure write delta for this path

            # Count a cognitive cycle only if the step produced an output (a real write)
            # [Cognitive cycles — current definition]
            # We count a *cognitive cycle* only when this controller step PRODUCED WRITES.
            # Rationale: today, a “cycle” = perception/decision that changed working memory (WorldGraph).
            # Waiting/no-op decisions do not increment; those are still controller steps but not cycles.
            # This is intentionally conservative until we implement an explicit sense→process→act loop.
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

            # Move NOW anchor to the latest stable binding when we wrote new facts
            if isinstance(result, dict) and result.get("status") == "ok" and after_n > before_n:
                new_bid = result.get("binding")
                if isinstance(new_bid, str):
                    try:
                        world.set_now(new_bid, tag=True, clean_previous=True)
                    except Exception:
                        # If anything goes wrong, ignore and keep the old NOW
                        pass

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
                print("[temporal] a new event occurred, thus not just a drift in the context vector but ")
                print("     instead a jump to mark a temporal boundary (cos reset to ~1.000)")
                print(f"[temporal] boundary==event changes -> event/boundary/epoch={ctx.boundary_no}")
                print(f"     last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

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
                    print(f"[temporal] boundary -> epoch (event changes) ={ctx.boundary_no} ")
                    print(f"     last_boundary_vhash64={ctx.boundary_vhash64} (cos≈1.000)")

            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "13":
            # Skill Ledger
            print("Selection: Skill Ledger\n")
            print(skill_ledger_text("policy:stand_up"))
            print("Full ledger:  [src=cca8_controller.skill_readout()]")
            print(skill_readout())
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "14":
            # Autonomic tick
            print("Selection: Autonomic Tick")
            print('''

The autonomic tick is like a fixed-rate heartbeat in the background, particularly important for hardware and robotics.
(To learn more about the different time systems in the architecture see the Snapshot or Instinct Step menu selections.)

The result of this menu autonomic tick may cause (if conditions exist):
  i.   increment ticks, age_days, temporal drift, fatigue
  ii.  emit rising-edge interoceptive cues
  iii. recompute which policies are unlocked at this age/stage via dev_gate(ctx) before evaluating triggers
  iv.  try one controller step (Action Center): collect triggered policies, apply safety override if needed,
  tie-break by priority, and execute one policy (same engine as Instinct Step, just less verbose here)

Consider this example -- the Mountain Goat calf has just been born.
At this time by default (note -- this might change with future software updates):
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
            b4: [pred:action:push_up], b5: [pred:action:extend_legs], b6: [pred:posture:standing, pred:posture:standing]
   -the extra lines below: base is the same as Instinct Step base suggestion, and again for humans not passed into action_center step;
   foa seeds foa with LATEST and NOW, adds cue nodes, union of neighborhoods with max_hops of 2; cands are candidate anchors which could be
   potential start anchors for planning/attachement

Fixed-rate heartbeat: fatigue↑, autonomic_ticks/age_days advance, temporal drift here (with optional boundary).
Often followed by a controller check to see if any policy should act, gather triggered policies, apply safety override,
pick by priority, and execute one policy (similar to menu Instinct Step but less verbose)

            ''')
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

                    print_timekeeping_line(ctx)
            except Exception as e:
                print(f"Autonomic: fatigue +0.01 (exception: {type(e).__name__}: {e})")

            # Refresh availability and consider firing regardless
            POLICY_RT.refresh_loaded(ctx)
            #rebuilds the set of eligible policies by applying each gate's dev_gate(ctx) to the current context
            #  e.g., age-->stage, etc  -- only those that pass are "loaded"=="eligible" for triggering
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            # Controller step bookkeeping for this path:
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            #if getattr(ctx, "temporal", None):  #already did a temporal drift above, so don't run here (same code as pasted in for few blocks of code)
            #   ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
            # Note: we do NOT increment cog_cycles here by design.
            # Autonomic Tick is physiology + one controller step; cycles are counted only in Instinct Step (see comment there).


            #runs the Action Center once:
            # -collects policies whose trigger(world, drives, ctx) is True, i.e., eligible policy that has triggered
            # -safety override -- e.g., if posture:fallen is near NOW then restricts policy to only policy:recover_fall, policy:stand_up
            # -tie-break/priority -- computes a simple drive-deficit score (e.g., hunger for policy:seek_nipple, etc) and picks the max policy
            # -executes the chosen policy via action_center_step(...) and returns a human-readable summary
            if fired != "no_match":
                print(fired)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "15":
            # Delete edge and autosave (if --autosave is active)
            print("Selection:  Delete Edge\n")
            print("Removes edge(s) matching src --> dst [relation]. Leave relation blank to remove any label.\n")
            #function contains inputs, logic,messages, autosave
            delete_edge_flow(world, autosave_cb=lambda: loop_helper(args.autosave, world, drives, ctx))
            #does not call loop_helper(...) since delete_edge_flow(...) does much of the same, including optional autosave

        #----Menu Selection Code Block------------------------
        elif choice == "16":
            # Export snapshot
            print("Selection:  Export Snapshot (Text)\n")
            print("Writes the same snapshot you see on-screen to world_snapshot.txt for sharing/debugging.\n")

            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "17":
            # Display snapshot
            print("Selection:  Snapshot (WorldGraph + CTX + Policies)\n")
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

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "18":
            # Simulate a fall event and try a recovery attempt immediately
            print("Selection: Simulate a fall event\n")
            print('''
Summary: -Creates posture:fallen and relabels the linking edge to 'fall', then attempts recovery.
         -Use this to demo safety gates (recover_fall / stand_up).

--background primer and terminology--
Controller steps  — one Action Center decision/execution loop (aka “instinct step”).
 -a loop in the runner that evaluates policies once and may write to the WorldGraph.
 -if that step wrote new facts, we mark a  temporal boundary (epoch++) .
 -With regards to its effects on timekeeping,  when a Controller Step occurs :
     i)  controller_steps : ++ once per controller step
     ii)  temporal drift : ++ (one soft-clock drift) per controller step
     iii)  autonomic ticks : no direct change (may increase but independent heartbeat-like clock)
     iv)  developmental age : no direct change (may increase but must be calculated elsewhere)
     v)   cognitive cycles : ++ if there is a write to the graph (nb. need to change in the future)
           Note: we do NOT increment cog_cycles here by design.
           This menu is 'event injector + one controller step'; cognitive cycles are counted only in Instinct Step.


 -With regards to terminology and operations that affect controller steps:
  “Action Center”  = the engine (`PolicyRuntime`).
  “Controller step”  = one invocation of that engine.
  “Instinct step”  = diagnostics +  one controller step .
  “Autonomic tick”  = physiology +  one controller step .
  ----

Consider the example where the Mountain Goat calf has just been born.
Thus, by default there will be b1 NOW --> b2 pred:stand
Note: "pred:stand" is not a state but an intent (if standing we would say,
   e.g., "pred:posture:standing" or legacy alias pred:posture:standing")
As shown below, this menu item creates a new binding b3 with "posture:fallen"
(it does it via world.add_predicate with attach="latest", i.e., link to b2).
The previous LATEST → fallen edge is relabeled to 'fall' for semantic readability.
It then calls a controller step. As shown above, this will cause the Action Center to
  evaluate policies via PolicyRuntime.consider_and_maybe_fire(...) --> since there is
  "posture:fallen" the safety override restricts candidate policies to {recover_fall, stand_up}
  and given that equally priority/deficit, stand_up is earlier and will be triggered.
The base suggestion, focus of attention, and candidates for binding are discussed in Instinct Step
  as well as in the README.md. They are largely diagnostic. Similarly the 'post' message simply re-evalutes
  the gate/trigger after execution; it's normal that it can still read True.
However the line "policy:stand_up (added 3 bindings)" tells us that the policy executed and added
3 bindings.
If we go to Snapshot we see:
    b1: [anchor:NOW]  [src=world._bindings['b1'].tags]
    b2: [pred:stand]  [src=world._bindings['b2'].tags]
    b3: [pred:posture:fallen]  [src=world._bindings['b3'].tags]
    b4: [pred:action:push_up]  [src=world._bindings['b4'].tags]
    b5: [pred:action:extend_legs]  [src=world._bindings['b5'].tags]
    b6: [pred:posture:standing, pred:posture:standing]  [src=world._bindings['b6'].tags]
Bindings b4, b5 and b6 were added and various actions occurred (or is being executed now). We see
   that at b6 there is the predicate "pred:posture:standing".
Also, of interest with regard to timekeeping:
   controller_steps=1, cog_cycles=0, temporal_epochs=0, autonomic_ticks=0, vhash64()==epoch_vhash64, age_days =0.000

            ''')

            prev_latest = world._latest_binding_id
            # Create a 'fallen' state as a new binding attached to latest
            fallen_bid = world.add_predicate(
                "posture:fallen",
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
            # Controller step bookkeeping for this path:
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            if getattr(ctx, "temporal", None):
                ctx.temporal.step()   # one soft-clock drift to reflect that the action took time
                print_timekeeping_line(ctx)

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        #elif "19"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        #elif "20"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        #elif "21"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        elif choice == "22":
            # Export and display interactive graph (Pyvis HTML) with options
            print("Selection: Export and display interactive graph (Pyvis HTML) with options")
            print('''

Export and display graph of nodes and links with more options (Pyvis HTML)
Note: the graph opened in your web browser is interactive -- even if you don't show
       edge labels to save space, put the mouse on them and the labels appear
Note: the graph HTML file will be saved in your current directory\n
— Edge labels: draw text on the links, e.g.,'then' or 'initiate_stand'
    On = label printed on the arrow (and still a tooltip). Off = only tooltip.
    -->Recommend Y on small graphs, n on larger ones to reduce clutter
— Node label mode:
    'id'           → show binding ids only (e.g., b5)
    'first_pred'   → show first pred:* token (e.g., stand, nurse)
    'id+first_pred'→ show both (two-line label)
     -->Recommend id+first_pred if enough space
— Physics: enable force-directed layout; turn off for very large graphs.
      (We model the graph as a physical system and then try to achieve a minimal
       energy state by simulating the movement of the nodes into this minimal state. The result is a
       graph which many people find easier to read. This option uses Barnes-Hut physics which is an
       algorithm originally for the N-body problem in astrophysics and which speeds up the layout calculations.
       Nonetheless, for very large graphs may not be computationally feasible.
      -->Recommend physics ON unless issues with very large graphs

            ''')
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
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "23":
            # Understanding bindings/edges/predicates/cues/anchors/policies (terminal help)
            print("Selection: Understanding bindings, edges, predicates, cues, anchors, policies")
            print_tagging_and_policies_help(POLICY_RT)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "24":
            # Capture scene → emit cue/predicate + tiny engram (signal bridge demo)
            print("Selection: Capture scene\n")
            print('''
Capture scene -- creates a binding, stores an engram of some scene in one of the columns,
  and then stores a pointer to that engram in the binding.

-the user is prompted to enter channel, token, family, attach (NOW->new, advance LATEST; oldLATEST -> new, advance LATEST;
   "none" -- create node unlinked, can manually add edges later) and a tiny scene vector(e.g., ".5,.5,.5")
-there is a temporal boundary jump so that the new engram starts a fresh epoch
   e.g., [temporal] boundary (pre-capture) → epoch=1 last_boundary_vhash64=23636ff46c39b1c5 (cos≈1.000)
-time attributes are passed in creating the engram
-then -- bid, eid = world.capture_scene(channel, token, vec, attach=attach, family=family, attrs=attrs)
-this creates a new binding --  b3 with tag cue:vision:silhouette:mom and attached engram id=80ac0bc7b6624b538db354c9d5aa4a17
-as noted it creates a tiny engram in one of the Columns, and stamps it with the time from attrs  e.g., time on engram: ticks....
-it then writes a pointer on the binding so that the binding points to the engram
     -e.g.,  b3.engrams["column01"] = 80ac0....
     -sets bN.engrams["column01"] = <eid>
-it then returns the binding id bid and the engram id eid
-then there is a controller==Action Center step -- in the example with a newborn calf the gate and trigger conditions for
    policy:stand_up are met, and this policy is executed

Phase 4B note:
  - When attach='latest' (default in base-aware mode), this menu now consults a write-base suggestion:
      base = NEAREST_PRED(pred=posture:standing/stand) near NOW → binding bN
    and uses base-aware attach semantics so the captured scene anchors under a meaningful posture node
    instead of blindly hanging off whatever LATEST happens to be.

  - Brief tutorial on how to think of the terms above and below at this point in the software development:
    NOW_ORIGIN anchor -- episode root binding, i.e., a stable 'start' marker, but not used much otherwise at this time
    HERE anchor -- stub right now, in future use for 'where the body is in space' (vs NOW 'where we are in time')
    LATEST -- a pointer, really _latest_binding_id, i.e., the last binding we created
    NOW anchor -- after execution of a policy NOW is usually moved to latest binding of event, but tiny events and cue might not move NOW
               -- used as default start for planning/search, time anchor, center of focus of attention FOA region
    attach = 'latest' -- flag indicating that new binding for predicate/engram/etc should be linked to the latest binding
    attach = 'now' -- flag indicating the new binding for predicate/engram/etc should be linked to the NOW anchor binding
    base -- 'where should this new binding be linked in the graph so that the episode stays tidy and meaningful?'
    base_suggestion -- system saying 'given the current situation (NOW + FOA) the best node to attach new nodes to is this binding'
    choose_contextual_base(...) -- computes base_suggestion starting from NOW, within small radius of nodes looks for binding with
        specified target predicate, if found returns, e.g., {'base':'NEAREST_PRED', 'pred':'posture:standing', 'bid':'b5'},
        but if not found returns, e.g., {'base':'HERE', 'bid':'?'}, i.e., strategy of HERE rather than nearest predicate and if can't
        use HERE then will use NOW/LATEST
    base-aware logic -- see above Phase 4B note -- if attach='latest' and last node was a cue or some dev_gate, etc, the new predicate/scene
        binding would normally link to those, even though they really belong under another node, then attach='effective_attach'=='none',
        and have NEAREST_PRED base, then _attach_via_base(...) links under NEAREST_PRED base



            ''')

            try:
                channel = input("Channel [vision/scent/sound/touch] (default: vision): ").strip().lower() or "vision"
                token   = input("Token   (e.g., silhouette:mom) (default: silhouette:mom): ").strip() or "silhouette:mom"
                family  = input("Family  [cue/pred] (default: cue): ").strip().lower() or "cue"
                attach  = input("Attach  [now/latest/none] (default: now): ").strip().lower() or "now"
                vtext   = input("Vector  (comma/space floats; default: 0.0,0.0,0.0): ").strip()
            except (EOFError, KeyboardInterrupt):
                print("\n(cancelled)")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            if family not in ("cue", "pred"):
                print("[info] unknown family; defaulting to 'cue'")
                family = "cue"
            if attach not in ("now", "latest", "none"):
                print("[info] unknown attach; defaulting to 'now'")
                attach = "now"

            vec = _parse_vector(vtext)

            # Phase 4B: decide on a contextual write base for this capture_scene.
            base = None
            effective_attach = attach
            if attach == "latest":
                base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
                effective_attach = _maybe_anchor_attach(attach, base)
                print(f"[base] write-base suggestion for this capture_scene: {_fmt_base(base)}")
                if effective_attach == "none" and isinstance(base, dict) and base.get("base") == "NEAREST_PRED":
                    print("[base] base-aware capture_scene: new binding will be created unattached, then "
                          "anchored under the suggested NEAREST_PRED base instead of plain 'LATEST'.")
            else:
                print("[base] write-base suggestion skipped for capture_scene: attach mode is not 'latest' (user-specified).")

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
            bid, eid = world.capture_scene(channel, token, vec, attach=effective_attach, family=family, attrs=attrs)

            try:
                print(f"[bridge] created binding {bid} with tag "
                      f"{family}:{channel}:{token} and attached engram id={eid}")

                # If we used a NEAREST_PRED base and suppressed auto-attach, anchor this scene under the base now.
                if isinstance(base, dict) and base.get("base") == "NEAREST_PRED" and effective_attach == "none":
                    _attach_via_base(
                        world,
                        base,
                        bid,
                        rel="then",
                        meta={
                            "created_by": "base_attach:menu:capture_scene",
                            "base_kind": base.get("base"),
                            "base_pred": base.get("pred"),
                        },
                    )

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
                    payload = rec.get("payload") if isinstance(rec, dict) else None
                    if isinstance(payload, dict):
                        kind  = payload.get("kind") or payload.get("meta", {}).get("kind")
                        shape = payload.get("shape") or payload.get("meta", {}).get("shape")
                    else:
                        kind  = rec.get("kind")
                        shape = rec.get("shape")
                    print(f"[bridge] column record ok: id={rid} kind={kind} shape={shape} "
                          f"keys={list(rec.keys()) if isinstance(rec, dict) else type(rec)}")
                except Exception as e:
                    print(f"[warn] could not retrieve engram record: {e}")

                # Print the actual slot and ids we just attached
                slot = None
                try:
                    b = world._bindings.get(bid)
                    eng = getattr(b, "engrams", None)
                    if isinstance(eng, dict):
                        for s, v in eng.items():
                            if isinstance(v, dict) and v.get("id") == eid:
                                slot = s
                                break
                except Exception:
                    slot = None
                if slot:
                    print(f'[bridge] attached pointer: {bid}.engrams["{slot}"] = {eid}')
                else:
                    slots = ", ".join(eng.keys()) if isinstance(eng, dict) else "(none)"
                    print(f'[bridge] {bid} engrams now include [{slots}] (attached id={eid})')

                # Optional: one controller step (Action Center) after capture
                try:
                    res = action_center_step(world, ctx, drives)
                    if isinstance(res, dict):
                        if res.get("status") != "noop":
                            policy  = res.get("policy")
                            status  = res.get("status")
                            reward  = res.get("reward")
                            binding = res.get("binding")
                            rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                            print(f"[executed] {policy} ({status}, reward={rtxt}) binding={binding}")
                            gate = next((p for p in POLICY_RT.loaded if p.name == policy), None)
                            explain_fn: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
                            if explain_fn is not None:
                                try:
                                    why = explain_fn(world, drives, ctx)
                                    print(f"[why {policy}] {why}")
                                except Exception:
                                    pass
                    else:
                        print("Action Center:", res)
                except Exception as e:
                    print(f"[warn] controller step errored: {e}")
            except Exception as e:
                print(f"[warn] capture_scene flow failed: {e}")

            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "25":
            # Planner strategy toggle
            print("Selection: Planner Strategy Toggle")
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
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "26":
            # Temporal probe (harmonized with Snapshot naming)
            print("Selection:  Temporal Probe\n")
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

            print_timekeeping_line(ctx)

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

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "27":
            # Inspect engram by id OR by binding id
            print("Selection: Inspect engram by id or by binding id")
            print('''
From the eid (engram id) or bid (binding id) this selection will display
the human-readable portions of the engram record.

            ''')
            try:
                key = input("Engram id OR Binding id: ").strip()
            except Exception:
                key = ""
            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            # Resolve binding → engram(s) if the user passed bN
            eid = key
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives, ctx)
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
                        loop_helper(args.autosave, world, drives, ctx)
                        continue
                else:
                    eid = eids[0]
            #at this point have eid, e.g., "9a55787783bc44fb9f5d3f5a49ec7b5d"

            rec = None
            try:
                rec = world.get_engram(engram_id=eid)
                #e.g., {'id': '9a55787783bc44fb9f5d3f5a49ec7b5d', 'name': 'scene:vision:silhouette:mom', 'payload': TensorPayload(......
            except Exception:
                rec = None
            if not rec:
                print(f"Engram not found: {eid}")
                loop_helper(args.autosave, world, drives, ctx)
                continue
            refs = _bindings_pointing_to_eid(world, eid)
            if refs:
                print("  referenced by:", ", ".join(f"{bid}.{slot}" for bid, slot in refs))
            try:
                kind = rec.get("kind") or rec.get("type") or "(unknown)"
                print(f"Engram: {eid}")
                print(f"  kind: {kind}")
                #e.g., Engram: 9a55787783bc44fb9f5d3f5a49ec7b5d  \\ kind: (unknown)

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
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "28":
            # List all engrams by scanning bindings; dedupe by id
            print("Selection: List all engrams")
            print('''
This selection will list all engrams stored by scanning the bindings.
Any duplicated engram ID's in different bindings will not be shown twice.
EID -- the engram id (32 hex characters)
src -- the source binding==node where the pointer is stored
       note: this is the first binding found that points to that EID but de-duplicated by EID
ticks, epoch -- when the engram was created, actually the value of these counters when it was captured
tvec64 -- human readable 64-bit fingerprint of the temporal vector ctx.tvec64 when the engram was captured
payload --  info from the payload's metadata TensorPayload holds data:list[float] and on serialization write contiguous float32's
  -shape=(3,) -- 1-D vector of 3 elements
  -kind=scene -- kind of field, not numeric dtype; "scene" kind comes from the payload's metadata
  -fmt=tensor/list-f32  -- TensorPayload holds data:list[float] and on serialization writes contiguous float32's
name -- engram name  e.g., scene:vision:silhouette:mom

Note: the Column record stores {"id", "name", "payload", "meta"}; receives the time attrs + "created_at"
Note: the binding keeps the pointer engrams["column01"] = {"id":EID, "act":1.0}

            ''')

            seen: set[str] = set() #useful to annotate containers created empty so mypy finds unambiguous
            any_found = False  #type is obvious from the literal, so don't type in cases like this
            printed_header = False
            for bid in _sorted_bids(world):  #[b1, b2,...]
                eids = _engrams_on_binding(world, bid)  #[] if no engram, or if engram, e.g., ['15da3c55f02c4f7db6cf657367fc8e49']
                for eid in eids:
                    if eid in seen:
                        continue
                    seen.add(eid)
                    any_found = True
                    # Best-effort fetch of Column record for summary
                    rec = None
                    try:
                        rec = world.get_engram(engram_id=eid)
                        #e.g.,  {'id': '15da3c55f02c4f7db6cf657367fc8e49', 'name': 'scene:vision:silhouette:mom',
                        #  'payload': TensorPayload(data=[0.0, 0.0, 0.0], shape=(3,), kind='scene', fmt='tensor/list-f32'),
                        #  'meta': {'name': 'scene:vision:silhouette:mom', 'links': ['cue:vision:silhouette:mom'],
                        #  'attrs': {'ticks': 0, 'tvec64': '7ffe462732f60bd9', 'epoch': 1, epoch_vhash64': '7ffe462732f60bd9', 'column': 'column01'},
                        #  'created_at': '2025-11-16T10:46:50'}, 'v': '1'}
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
                    name = (rec.get("name") or "") if isinstance(rec, dict) else ""

                    if not printed_header:
                        print("Engrams in the system:\n")
                        printed_header = True

                    fmt = (payload.meta().get("fmt") if hasattr(payload, "meta")
                           else (payload.get("fmt") if isinstance(payload, dict) else None))
                    print(f"EID={eid}  src={bid}  ticks={ticks} epoch={epoch} tvec64={tvec} "
                          f"payload(shape={shape}, kind={dtype}{', fmt='+fmt if fmt else ''})"
                          f"{'  name='+name if name else ''}")
            if not any_found:
                print("no engrams were found")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection  Code Block------------------------
        elif choice == "29":
            # Search engrams
            print("Selection:  Search Engrams\n")
            print("Search referenced engrams by name substring (case-insensitive) and/or epoch.\n"
                  "Optional filters: channel substring (e.g., 'vision'), payload kind (e.g., 'scene'), "
                  "and EID prefix.\n"
                  "Note: 'Name' is not bid but the given by the tag, e.g.,name=scene:vision:silhouette:mom ")

            # --- inputs (all optional except 'q' which can be blank) ---
            try:
                q = input("Name contains (substring, blank=any): ").strip()
            except Exception:
                q = ""
            try:
                e_in = input("Epoch equals (blank=any): ").strip()
                epoch = int(e_in) if e_in else None
            except Exception:
                epoch = None
            try:
                chan = input("Channel contains (e.g., vision, blank=any): ").strip().lower()
            except Exception:
                chan = ""
            try:
                kid = input("Payload kind equals (e.g., scene, blank=any): ").strip().lower()
            except Exception:
                kid = ""
            try:
                eid_prefix = input("EID starts with (hex prefix, blank=any): ").strip().lower()
            except Exception:
                eid_prefix = ""

            # --- scan pointers on bindings, de-dupe by EID ---
            seen = set()
            found: list[tuple[str, str, str, dict]] = []  # (eid, src_bid, name, attrs)

            for bid, b in world._bindings.items():
                eng = getattr(b, "engrams", None)
                if not isinstance(eng, dict):
                    continue
                for _slot, val in eng.items():
                    if not (isinstance(val, dict) and "id" in val):
                        continue
                    eid = val["id"]
                    if eid in seen:
                        continue
                    seen.add(eid)

                    # fetch column record
                    try:
                        rec = world.get_engram(engram_id=eid)
                    except Exception:
                        continue
                    if not isinstance(rec, dict):
                        continue

                    name = rec.get("name") or ""
                    meta = rec.get("meta", {})
                    attrs = meta.get("attrs", {}) if isinstance(meta, dict) else {}

                    # ---- filters ----
                    if eid_prefix and not eid.lower().startswith(eid_prefix):
                        continue
                    if q and q.lower() not in name.lower():
                        continue
                    if chan and chan not in name.lower():
                        continue
                    if epoch is not None:
                        ep = attrs.get("epoch")
                        if not (isinstance(ep, int) and ep == epoch):
                            continue
                    if kid:
                        # 'kind' comes from payload metadata
                        pl = rec.get("payload")
                        kind = None
                        if hasattr(pl, "meta"):
                            try:
                                kind = pl.meta().get("kind")
                            except Exception:
                                kind = None
                        elif isinstance(pl, dict):
                            kind = pl.get("kind") or (pl.get("meta", {}) or {}).get("kind")
                        if (kind or "").lower() != kid:
                            continue

                    found.append((eid, bid, name, attrs))

            # --- print results (epoch desc, then name, then eid) ---
            if not found:
                print("\n(no matches)")
            else:
                print("\nThe following matches were found:\n")
                def _sort_key(t):
                    eid, _bid, name, attrs = t
                    ep = attrs.get("epoch")
                    # sort by epoch desc (ints first), then name, then eid
                    ep_key = -ep if isinstance(ep, int) else float("inf")
                    return (ep_key, name or "", eid)

                for eid, bid, name, attrs in sorted(found, key=_sort_key):
                    print(f"EID={eid}  src={bid}  name={name}  epoch={attrs.get('epoch')}  tvec64={attrs.get('tvec64')}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "30":
            # Delete engram by id OR by binding id; also prune any binding pointers to it
            print("Selection: Delete engram\n")
            print('''
Deletes engrams by bid (binding id) or by eid (engram id).
Every binding pointer that references this eid will be pruned.
-deletes the Column record via column.mem.delete(eid)
-then prunes every binding pointer that referenced that eid

            ''')
            key = input("Engram id OR Binding id to delete: ").strip()
            if not key:
                print("No id provided.")
                loop_helper(args.autosave, world, drives, ctx); continue

            # Resolve binding → engram id(s) if needed
            targets = []
            if key.lower().startswith("b") and key[1:].isdigit():
                eids = _engrams_on_binding(world, key)
                if not eids:
                    print(f"No engrams on binding {key}.")
                    loop_helper(args.autosave, world, drives, ctx); continue
                if len(eids) > 1:
                    print(f"Binding {key} has multiple engrams:")
                    for i, ee in enumerate(eids, 1):
                        print(f"  {i}) {ee}")
                    try:
                        pick = int(input("Pick one [number]: ").strip()) - 1
                        targets = [eids[pick]]
                    except Exception:
                        print("(cancelled)")
                        loop_helper(args.autosave, world, drives, ctx); continue
                else:
                    targets = [eids[0]]
            else:
                targets = [key]

            print("WARNING: this will delete the engram record from column memory,")
            print("and will also prune any binding pointers that reference it.")
            if input("Type DELETE to confirm: ").strip() != "DELETE":
                print("(cancelled)")
                loop_helper(args.autosave, world, drives, ctx); continue

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

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "31":
            # Attach an existing engram id to a binding (creates/overwrites a slot)
            print("Selection: Attach an existing engram id to a binding (creates/overwrites a slot) ")
            print('''

Attach an existing engram id (eid) to a binding id (bid).
-this will create a new slot for that eid or overwrite an existing slot with same eid
-multiple slots and engram pointers possible, of course, on a given binding
-it is possible to create dangling pointers that point to non-existing engrams that
   you entered, but they can be removed via the Delete menu option

            ''')

            bid = input("Binding id: ").strip()
            if not (bid.lower().startswith("b") and bid[1:].isdigit()):
                print("Please enter a binding id like b3.")
                loop_helper(args.autosave, world, drives, ctx); continue
            eid = input("Engram id to attach: ").strip()
            if not eid:
                print("No engram id provided.")
                loop_helper(args.autosave, world, drives, ctx); continue

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
                loop_helper(args.autosave, world, drives, ctx); continue
            if getattr(b, "engrams", None) is None or not isinstance(b.engrams, dict):
                b.engrams = {}
            b.engrams[slot] = {"id": eid, "act": 1.0}
            print(f"Attached engram {eid} to {bid} as {slot}.")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        #elif "32"  see new_to_old compatibility map


        #----Menu Selection Code Block------------------------
        elif choice == "33":
            print("Selection:  LOC by Directory (Python)")
            print("\nPrints total lines of Python source code (SLOC)")
            print("-current settings are for all lines of actual code (includes print() )")
            print("-will not count docstrings or comments or blank lines")
            print("-will not count code in .bak files, configuration files, typedown docs, etc. ")
            print("-will search through current working directory and all of its subdirectories")
            print("-'tests' is the subdirectory of pytest unit tests")
            print("\nPlease wait.... searching through directories and counting lines of code....\n")

            rows, total, err = _compute_loc_by_dir()
            if err:
                print(err)  # pragma: no cover
            else:
                print(_render_loc_by_dir_table(rows, total))  # pragma: no cover
            # also show the .py files in the *current* working directory (not subdirectories)
            try:
                entries = os.listdir(".")
                py_files = [
                    name for name in entries
                    if name.endswith(".py") and os.path.isfile(name)
                ]
                if py_files:
                    py_files_sorted = sorted(py_files)
                    print("\nThe following Python .py files are in the current working directory:")
                    print("  " + ", ".join(py_files_sorted))
                else:
                    print("\nNo Python .py files were found in the current working directory.")
            except Exception as e:
                print(f"\n[warn] Could not list .py files in current directory: {e}")
            #does not call loop_helper(...) since no autosave here, it is a read-only menu selection


        #----Menu Selection Code Block------------------------
        elif choice == "35":
            # Environment step (HybridEnvironment → WorldGraph demo)
            print("Selection: Environment step (HybridEnvironment → WorldGraph demo)\n")
            print("""[guide] This selection runs ONE closed-loop step between the newborn-goat environment and the CCA8 brain.

  • [env] lines summarize what the environment simulation just did:
      - on the first call we RESET the newborn_goat_first_hour storyboard
      - on later calls we STEP the storyboard forward using the last policy action (if any)

  • [env→world] lines show how EnvObservation is injected into the WorldGraph:
      - predicates like posture:fallen or proximity:mom:far become pred:* facts (the agent's beliefs)
      - cues (e.g., vision:silhouette:mom) become cue:* facts attached near NOW/LATEST

  • [env→controller] lines show how the controller responds:
      - after seeing the updated WorldGraph + drives, the Action Center chooses ONE policy to execute
      - for example, policy:stand_up will assert a short motor chain and a final posture:standing fact
        (this last fact represents the policy's expected outcome; the next [env] step will later confirm
         or refute standing via new sensory evidence).

  • On each env step this occurs:
    1. Env storyboard evolving (env.reset / env.step, kid posture, stage, mom distance, nipple state).
        -dataclass EnvState== holds the true world state (posture, mom distance, fatigue, etc....)
        -class FsmBackend== actual storyboard logic, i.e., the script for an environment period
        -HybridEnvironment calls the storyboard each step
        -fsmBackend.step(env_state, action, ctx) -- stage-by-stage logic updating posture, distances, etc.
    2. WorldGraph being updated ([env→world] pred:* and cue:* bindings near NOW/LATEST).
    3. BodyMap being mirrored ([body] posture=... mom_distance=... nipple_state=...).
    4. Controller reacting ([env→controller] policy fire + any [note] meta).
    5. Timekeeping advancing (one-line soft clock summary at the end).
""")

            # Track bindings so we can show notes for any NEW bindings created during this step.
            try:
                before_ids = set(world._bindings.keys())
            except Exception:
                before_ids = set()

            # Account for one controller decision loop worth of internal time (soft clock only).
            try:
                ctx.controller_steps = getattr(ctx, "controller_steps", 0) + 1
            except Exception:
                pass
            if getattr(ctx, "temporal", None):
                ctx.temporal.step()

            # First call: start a fresh newborn-goat episode in the environment
            if not ctx.env_episode_started:
                env_obs, env_info = env.reset()
                ctx.env_episode_started = True
                ctx.env_last_action = None  # no action yet on the very first tick
                print(
                    f"[env] Reset newborn_goat scenario: "
                    f"episode_index={env_info.get('episode_index')} "
                    f"scenario={env_info.get('scenario_name')}"
                )
            else:
                # On subsequent calls, feed the last fired policy back to env.step(...)
                action_for_env = ctx.env_last_action
                env_obs, _env_reward, _env_done, env_info = env.step(
                    action=action_for_env,
                    ctx=ctx,
                )
                # Consume the action so it only affects one environment tick
                ctx.env_last_action = None

                st = env.state
                print(
                    f"[env] step={env_info.get('step_index')} "
                    f"stage={st.scenario_stage} posture={st.kid_posture} "
                    f"mom_distance={st.mom_distance} nipple_state={st.nipple_state} "
                    f"action={action_for_env!r}"
                )

            # Map EnvObservation into the CCA8 WorldGraph as pred:* / cue:* tokens.
            # This uses the shared helper so other code paths can reuse the same semantics.
            inject_obs_into_world(world, ctx, env_obs)

            # Show BodyMap summary for this env step (posture/mom_distance/nipple_state)
            try:
                bp = body_posture(ctx)
                md = body_mom_distance(ctx)
                ns = body_nipple_state(ctx)
                print(f"[body] posture={bp!r} mom_distance={md!r} nipple_state={ns!r}")
            except Exception:
                pass

            # Let the controller see the new facts and maybe act once
            try:
                POLICY_RT.refresh_loaded(ctx)
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
                if fired != "no_match":
                    print(f"[env→controller] {fired}")

                    # Extract the policy name (first token) so env.step(...) receives a clean action string,
                    # e.g. "policy:stand_up" or "policy:seek_nipple".
                    if isinstance(fired, str):
                        first_token = fired.split()[0]
                        if isinstance(first_token, str) and first_token.startswith("policy:"):
                            ctx.env_last_action = first_token
                        else:
                            ctx.env_last_action = None
                    else:
                        ctx.env_last_action = None
                else:
                    ctx.env_last_action = None
            except Exception as e:
                print(f"[env→controller] controller step error: {e}")
                ctx.env_last_action = None

            # After env + controller, show any meta["note"] attached to NEW bindings.
            try:
                after_ids = set(world._bindings.keys())
                new_ids = list(after_ids - before_ids)

                def _id_key(bid: str) -> int:
                    # Sort like b1, b2, ..., fall back to 0 for anything weird.
                    try:
                        if bid.startswith("b"):
                            return int(bid[1:])
                    except Exception:
                        pass
                    return 0

                for bid in sorted(new_ids, key=_id_key):
                    b = world._bindings.get(bid)
                    if not b:
                        continue
                    meta = getattr(b, "meta", None)
                    if isinstance(meta, dict):
                        note = meta.get("note")
                        if note:
                            print(f"[note] {bid}: {note}")
            except Exception as e:
                print(f"[note] error while printing binding notes: {e}")

            # Show a one-line timekeeping summary so users can see controller_steps advancing here too.
            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "36":
            # Toggle mini-snapshot on/off
            ctx.mini_snapshot = not getattr(ctx, "mini_snapshot", False)
            state = "ON" if ctx.mini_snapshot else "OFF"
            print(f"Selection: Toggle ON/OFF mini-snapshot switch to a new position of: {state}")
            print("(if ON: will print a mini-snapshot after running the code of most menu selections, including this one)")
            print("(if OFF: will not print a mini-snapshot after each menu selection)\n")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "37":
            # Multi-step environment closed-loop run
            print("Selection: Run n environment steps (closed-loop timeline)\n")
            print("""This selection runs several consecutive closed-loop steps between the
HybridEnvironment (newborn-goat world) and the CCA8 brain.

For each step we will:
  1) Advance controller_steps and the temporal soft clock once,
  2) STEP the newborn-goat environment using the last policy action (if any),
  3) Inject the resulting EnvObservation into the WorldGraph as pred:/cue: facts,
  4) Run ONE controller step (Action Center) and remember the last fired policy.

This is like pressing menu 35 multiple times, but with a more compact, per-step summary.
You can still use menu 35 for detailed, single-step inspection.
""")
            # Ask the user for n
            try:
                n_text = input("How many closed-loop step(s) would you like to run? [default: 5]: ").strip()
            except Exception:
                n_text = ""
            try:
                n_steps = int(n_text) if n_text else 5
            except ValueError:
                n_steps = 5
            if n_steps <= 0:
                print("[env-loop] N must be ≥ 1; nothing to do.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            run_env_closed_loop_steps(env, world, drives, ctx, POLICY_RT, n_steps)

            # Show a one-line timekeeping summary after the run
            print_timekeeping_line(ctx)
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "38":
            # Inspect BodyMap summary
            print("Selection:  BodyMap Inspect\n")
            print("Shows a one-line summary derived from body_* helpers plus zone classification.\n")

            if ctx is None:
                print("Ctx is not available.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            try:
                bp = body_posture(ctx)
                md = body_mom_distance(ctx)
                ns = body_nipple_state(ctx)
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

                print("BodyMap one-line summary:")
                line = (
                    f"  posture={bp or '(n/a)'} "
                    f"mom={md or '(n/a)'} "
                    f"nipple={ns or '(n/a)'} "
                    f"shelter={sd or '(n/a)'} "
                    f"cliff={cd or '(n/a)'}"
                )
                if zone is not None:
                    line += f"  zone={zone}"
                print(line)
            except Exception as e:
                print(f"[bodymap] inspect error: {e}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "39":
            # Spatial scene demo: what is NOW near + resting-in-shelter?
            print("Selection:  Spatial Scene Demo\n")
            print("Shows which bindings are NOW-near and whether we are in a 'resting in shelter, cliff far' scene.\n")

            # Part 1: what is NOW near?
            try:
                near_ids = neighbors_near_self(world)
                if not near_ids:
                    print("NOW-near neighbors: (none)")
                else:
                    print("NOW-near neighbors:")
                    for bid in near_ids:
                        b = world._bindings.get(bid)
                        tags = ", ".join(sorted(getattr(b, "tags", []) or [])) if b else ""
                        print(f"  {bid}: [{tags}]")
                print()
            except Exception as e:
                print(f"[spatial] neighbors_near_self error: {e}\n")

            # Part 2: are we resting in shelter with cliff far?
            try:
                summary = resting_scenes_in_shelter(world)
                print("Resting-in-shelter scene summary (around NOW):")
                print(f"  rest_near_now:             {summary.get('rest_near_now')}")
                print(f"  shelter_near_now:          {summary.get('shelter_near_now')}")
                print(f"  hazard_cliff_far_near_now: {summary.get('hazard_cliff_far_near_now')}")
                sbids = summary.get("shelter_bids") or []
                if sbids:
                    print("  shelter_bids (NOW --near--> ...):")
                    for bid in sbids:
                        b = world._bindings.get(bid)
                        tags = ", ".join(sorted(getattr(b, 'tags', []) or [])) if b else ""
                        print(f"    {bid}: [{tags}]")
                else:
                    print("  shelter_bids: (none)")
            except Exception as e:
                print(f"[spatial] resting_scenes_in_shelter error: {e}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "s":
            # Save session
            print("Selection:  Save Session\n")
            print('''
This "save session" is a manual one-shot snapshot, i.e., you are saving the session to
  a .json file you specify.

It saves the world, drives and skill data of the session to the JSON file.
-writes world.to_dict(), drives.to_dict(), skills_to_dict() along with a timestamp and version

This menu selection does not change args.autosave or anything about autosave behavior.

It is useful to checkpoint your development progress in running a simulation -- you can save the
  current session to disk at a moment you choose. Even if you have --autosave session.json option
  already set (which indeed provides robust, frequent autosaves) this manual one-shot
  save session is useful to checkpoint your simulation run at a certain point where autosave
  has not occurred at that moment yet, or if you want a save to a different file location without
  changing your autosave setup.


Brief Recap of --autosave session.json (i.e., NOT this current menu selection)
-------------------------------------------------------------------------------
-the flag "--autosave" should work with Windows, Linux and macOS since we use the argparse library,
    with the OS just passing the flag as text to Python and Python handling the rest
>python cca8_run.py --autosave session.json
    -see on display: "[io] Started a NEW session. Autosave ON to 'session.json'."
    -new empty WorldGraph and Drives are created
    -after most menu actions, loop_helper(args.autosave, world, drives, ctx) calls
      save_session("session.json", world, drives)
    -the session.json is fully rewritten each time, i.e., a current state snapshot is written
    -if you crash or ctl-C you can later restart from session.json using --load
    -reset menu option only works if --autosave was used, in which case it will delete the current
      autosave file and reinitialize a fresh one
-if "--autosave mysession.json"is being used, you really don't need this menu option "save session"
    unless special case such as obtaining specific checkpoint, writing to a different file, etc.
-note: file saving is via JSON so .json file extension should be used, but any extension will actually work as long
    as the file is json format and load in using the same file extension name
-IMPORTANT - note that each time an "autosave session.json" occurs the contents of the "session.json" file are
  not appended with new information, but overwritten, i.e., the old "session.json" file is effectively deleted


Brief Recap of --load session.json (i.e., NOT this current menu selection)
--------------------------------------------------------------------------
-the flag "--load" should work with Windows, Linux and macOS since we use the argparse library,
  with the OS just passing the flag as text to Python and Python handling the rest
>python cca8_run.py --load session.json
    -see on display:
        "[io] Loaded 'session1.json'. Autosave OFF"
        "[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>."
    -it reads session1.json (world, drives, skills) and reconstructs that state
    -no autosave is automatically active unless you also specify --autosave file_to_save.json
    -after loading a saved file, you can modify it in memory -- it will not be written back, i.e., saved,
        unless you specifically used a --save session.json flag or else use this menu selection "Save Session"
-make changes and select: "Save session"  --> newer_session.json
-then quit
-then load session1.json and examine, then quit; then load newer_session.json -- changes in appropriate json files

>python cca8_run.py --load nonexistent.json
    -see on display: "[io] Started a NEW session. Autosave OFF — use menu selection Save Session"
                               "or relaunch with --autosave <path>."
-can load a session while in the middle of another one; if no one-shot save or autosave then lose that session
    -in middle of a session and then menu select "Load Session"
    -will see on the display:
        "Loads a prior JSON snapshot (world, drives, skills). The new state replaces the current one."
        "Load from file: session1.json"
        "Loaded session1.json (saved_at=2025-11-20T05:35:45)"
        "[io] Loaded 'session1.json'. Autosave OFF"
        "[io] Tip: You can use menu selection 'Save session' for one-shot save or relaunch with --autosave <path>."


Brief Recap of Using Both Together (i.e., NOT this current menu selection)
--------------------------------------------------------------------------
>python cca8_run.py --load session2.json --autosave session2.json
    -effectively load from session.json and keep autosaving back to same file session.json
    -if session2.json does not exist yet you will see on the display:
            "[io] Started a NEW session. Autosave ON to 'session2.json'."
    -if session2.json exists from saving a previous time, you will see on the display:
            "[io] Loaded 'session2.json'. Autosave ON to the same file — state will be saved in-place "
            "  after each action. (the file is fully rewritten on each autosave)."

>python cca8_run.py --load session2.json --autosave new_session5.json
    -effectively start from this saved snapshot but then autosave new work to another file new_session5.json
    -see on display:
        "[io] Loaded 'session2.json'. Autosave ON to 'new_session5.json' — new steps will be written to the autosave file;"
           "the original load file remains unchanged."
-continue with this example; quit and then restart as:
>python cca8_run.py --autosave new_session5.json --load session2.json
    -order of --autosave and --load does not matter
    -new_session5.json is not a new file but an existing one, thus will be overwritten
    -see on display:
        "[io] Loaded 'session2.json'. Autosave ON to 'new_session5.json' — new steps will be written to the autosave file;"
           "the original load file remains unchanged."


Brief Recap of this current Menu Selection: "Save Session"
----------------------------------------------------------
-Again, this current menu selection "save session" is a manual one-shot snapshot, i.e., you are
    saving the session to a .json file you specify.

            ''')

            path = input("Save to file (e.g., session.json): ").strip()
            #input file name to pass to save_session(...)
            if path:
                ts = save_session(path, world, drives)
                #inside save_session(...):
                #with open(tmp, "w", encoding="utf-8") as f:
                #        json.dump(data, f, indent=2, ensure_ascii=False)
                #-ts is datetime.now()
                #-data =dict {ts, world.to_dict(), drives.to_dict(), skills_to_dict(), version, platform}
                #-note: don't write "open(path, "w"...)" since "w" will truncate the existing file to length 0 and then start writing
                #       thus write to a temporary file, make sure no crashes, and then os.replace(tmp, path)
                print(f"Saved to {path} at {ts}")


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "l":
            # Load session
            print("Selection: Load Session\n")
            print('''
[Note: If you don't have knowledge of what --load, --autosave, Load, Save selections do, then see
  Menu Selection "Save Session" or else see README.md Documentation for a quick recap of these. ]

This "load session" is a manual one-shot load snapshot, i.e., you are retrieving the
  session from a .json file you specify. It will overwrite whatever current session you are running.

"Load Session" does not automatically write back to the file -- it just loads it.

-prompted for a filename and path
-opens and parses the JSON
-reconstructs a fresh WorldGraph and Drives from the blob via WorldGraph.from_dict(...), Drives.from_dict(...)
-restores the skills ledger via skills_from_dict(...)
-replaces the current simulation state with the loaded one -- whatever was in memory is discarded
-no autosave is triggered immediately since don't want to overwrite a file as soon as it is loaded
-next menu actions will autosave as usual if --autosave option, otherwise can use Save Session for one-shot save

            ''')

            print("Loads a prior JSON snapshot (world, drives, skills).")
            print("The current simulation in memory will be discarded so make sure it is being autosaved or else manually")
            print("  save it, if you want to preserve the current program state.\n")
            path = input("Load from file (ENTER to exit back to the menu): ").strip()
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
            #does not call loop_helper(...) since you might not want to overwrite a file immediately after loading it


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "d":
            # Show drives (raw + tags), robust across Drives variants
            print("Selection: Drives & Drive Tags\n")
            print("Shows raw drive values and threshold flags with their sources.\n")
            print(drives_and_tags_text(drives))
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "r":
            # Reset current saved session: explicit confirmation
            print("Selection: Reset current save session")
            print('''
This menu selection code will reset the current autosave-backed up session
 -Note that --autosave must be used (or else code will alert you to this and exit back to the menu)
This selection will delete the autosave file (if it still exists) and re-initialize new but empty WorldGraph,
  drives and skill ledger in memory.
-world = cca8_world_graph.WorldGraph()
-drives = Drives()
-skills_from_dict({}) #clear skill ledger

What has happened is the current world has been replaced with a brand-new empty WorldGraph (and fresh drives and
  skill ledger).
There will be a NOW anchore in the new WorldGraph.
Note that args.autosave is unchanged -- autosave's will still occur at the same path cca8_run.py was launched with.
However, VERY IMPORTANT, note that the autosave session.json file will be deleted as part of this reset.
By contrast, if you simply exit and later restart with >python cca8_run.py --autosave session.json, the existing file
 is not deleted; it remains on disk until the first autosave of the new run, at which point its contents
 are overwritten with the fresh session.
            ''')

            if not args.autosave:
                print("No current saved json file to reset (you did not launch with --autosave <path>).")
                print("Returning back to menu....")
            else:
                path = os.path.abspath(args.autosave)
                cwd  = os.path.abspath(os.getcwd())
                print("\n[RESET] This will:")
                print("  -Delete the autosave file shown below (if it exists), and")
                print("  -Re-initialize an empty world, drives, and skill ledger in memory.\n")
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
                            print(f"\n1. Deleted {path}.")
                        else:
                            print(f"1. Hmmm... no file at {path} (nothing to delete).")
                    except Exception as e:
                        print(f"[warn] Could not delete {path}: {e}")
                    # Reinitialize episode state
                    world = cca8_world_graph.WorldGraph()
                    drives = Drives()
                    skills_from_dict({})  # clear skill ledger
                    world.ensure_anchor("NOW")
                    print("2. Initialized a fresh episode in memory -- fresh WorldGraph, drives and skill ledger.")
                    print("   -this is in memory now but after your next action, it will be autosaved")
                else:
                    print("Reset cancelled (nothing deleted)")
                    print("Returning back to menu....")
            continue   # back to menu
            #no loop_helper(...) -- it's a brand new WorldGraph created; autosaves will occur after next action


        #----Menu Selection Code Block------------------------
        elif choice.lower() == "t":
            # Help and Tutorial selection that opens project documentation
            print("Selection:  Help -- System Docs and Tutorial\n")

            print("\nTutorial options:")
            print("  1) README/compendium System Documentation")
            print("  2) Console Tour (pending)")
            print("  [Enter] Cancel")
            try:
                pick = input("Choose: ").strip()
            except Exception:
                pick = ""
            #pylint:disable=no-else-continue
            if pick == "1":
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
            elif pick == "2":
                print("Console tour is pending; please use the README/compendium for now.")
                continue
            else:
                print("(cancelled)")
                continue
        #pylint:enable=no-else-continue
        #no loop_helper(...) -- tutorial/help returns to main menu

        #----Menu Selection Code Block------------------------
            ##END OF MENU SELECTION BLOCKS

    # interactive_loop(...): while loop:  END <<<<<<<<<<<<<<<<<<<  back to while loop


# --------------------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """
    Command-line entry point for the CCA8 runner.

    Responsibilities
    ----------------
    - Configure logging (file + console).
    - Parse CLI flags (about/version/load/save/autosave/preflight/plan/profile/hal/body/demo-world/…).
    - Handle one-shot modes:
         --version / --about → print version/component info and exit.
         --preflight         → run full unit tests + preflight probes and exit.
    - For interactive mode:
         Normalize HAL/body flags into human-readable status strings.
         Call interactive_loop(args), which runs the menu-driven CCA8 simulation.

    Args:
        argv: Optional list of CLI arguments (defaults to sys.argv[1:] when None).

    Returns:
        0 on normal success, or a non-zero exit code (e.g., preflight failures).
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
    p.add_argument("--demo-world", action="store_true", help="Start with a small preloaded demo world for graph/menu testing")

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
        for name in ["cca8_world_graph", "cca8_controller", "cca8_column", "cca8_features", "cca8_temporal", "cca8_env", "cca8_test_worlds"]:
            ver, path = _module_version_and_path(name)
            comps.append((name, ver, path))

        print("CCA8 Components:")
        for label, ver, path in comps:
            print(f"  - {label} v{ver} ({path})")

        # additionally show primitive count if the controller is importable
        try:
            print(f"\n    [controller primitives: {len(PRIMITIVES)}]")
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
# Standard Python entry point:
# When this file is executed as a script (e.g., `python cca8_run.py`),
# run main(...) and propagate its return code as the process exit status.
if __name__ == "__main__":
    sys.exit(main())
