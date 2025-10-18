# -*- coding: utf-8 -*-
#!/usr/bin/env python3
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
  The Action Center scans the ordered list of policies and runs the first that triggers (one "tick").
- **Autosave/Load**: JSON snapshot with `world`, `drives`, `skills`, plus a `saved_at` timestamp.

This runner presents an interactive menu for inspecting the world, planning, adding predicates,
emitting sensory cues, and running the Action Center ("Instinct step"). It also supports
non-interactive utility flags for scripting, like `--about`, `--version`, and `--plan <predicate>`.
"""

# --- Imports -------------------------------------------------------------
# Standard Library Imports
from __future__ import annotations
import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Any, Dict, List, Callable

# PyPI and Third-Party Imports
# --none at this time at program startup --

# CCA8 Module Imports
#import cca8_world_graph as wgmod  # modular alternative: allows swapping WorldGraph engines
import cca8_world_graph
from cca8_controller import Drives, action_center_step, skill_readout, skills_to_dict, skills_from_dict

# --- Public API index and version-----------------------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.7.11"
__all__ = [
    "main",
    "interactive_loop",
    "run_preflight_full",
    "snapshot_text",
    "export_snapshot",
    "world_delete_edge",
    "boot_prime_stand",
    "__version__",
    "Ctx",
]

# --- Runtime Context (ENGINE↔CLI seam) --------------------------------------------
@dataclass(slots=True)
class Ctx:
    """Mutable runtime context for the agent.

    This deliberately small struct is the boundary object passed between the
    engine (pure helpers) and the CLI. Defaults match the prior inline stub.
    """
    sigma: float = 0.015
    jump: float = 0.2
    age_days: float = 0.0
    ticks: int = 0
    profile: str = "Mountain Goat"
    hal: Optional[Any] = None
    body: str = "(none)"


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
        self.body = body or "(none)"
        # future usage: load body profile (motor map), open serial/network, etc.

    # Actuators
    def push_up(self):        pass
    def extend_legs(self):    pass
    def orient_to_mom(self):  pass

    # Sensors
    def sense_vision_mom(self):  return False
    def sense_vestibular_fall(self): return False


# --------------------------------------------------------------------------------------
# Two-gate policy and helpers and console helpers
# --------------------------------------------------------------------------------------

def print_header(hal_str: str = "HAL: off (no embodiment)", body_str: str = "Body: (none)"):
    print('\n\n# --------------------------------------------------------------------------------------')
    print('# NEW RUN   NEW RUN')
    print('# --------------------------------------------------------------------------------------')
    print("\nA Warm Welcome to the CCA8 Mammalian Brain Simulation")
    print(f"(cca8_run.py v{__version__})\n")
    print(f"Entry point program being run: {os.path.abspath(sys.argv[0])}")
    print(f"OS: {sys.platform} (run system-dependent utilities for more detailed system/simulation info)")
    print('(for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)')
    print(f'\nEmbodiment:  HAL (hardware abstraction layer) setting: {hal_str}')
    print(f'Embodiment:  body_type-version_number-serial_number (i.e., robotic embodiment): {body_str} ')

    print("\nThe simulation of the cognitive architecture can be adjusted to add or take away")
    print("  various features, allowing exploration of different evolutionary-like configurations.\n")
    print("  1. Mountain Goat-like brain simulation")
    print("  2. Chimpanzee-like brain simulation")
    print("  3. Human-like brain simulation")
    print("  4. Human-like one-agent multiple-brains simulation")
    print("  5. Human-like one-brain simulation × multiple-agents society")
    print("  6. Human-like one-agent multiple-brains simulation with combinatorial planning")
    print("  7. Super-Human-like machine simulation\n")
    print("Pending additional intro material here....")

def loop_helper(autosave_from_args: Optional[str], world, drives, time_limited: bool = False):
    """Operations to run at the end of each menu branch before looping again.

    Currently: autosave (if enabled). Future: time-limited bypasses for real-world ops.
    """
    if time_limited:
        return
    if autosave_from_args:
        ts = save_session(autosave_from_args, world, drives)
        # Quiet by default; uncomment for debugging:
        # print(f"[autosaved {ts}] {autosave_from_args}")

def _drive_tags(drives) -> list[str]:
    """Robustly compute drive:* tags even if Drives.predicates() is missing.

    If the Drives class has a .predicates() method, use that; otherwise derive
    default tags by thresholds: hunger>0.6 → drive:hunger_high;
    fatigue>0.7 → drive:fatigue_high; warmth<0.3 → drive:cold.
    """
    if hasattr(drives, "predicates") and callable(getattr(drives, "predicates")):
        try:
            tags = list(drives.predicates())
            return [t for t in tags if isinstance(t, str)]
        except Exception:
            pass
    tags = ["state:breathing_ok"]
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

def _normalize_pred(tok: str) -> str:
    return tok if tok.startswith("pred:") else f"pred:{tok}"

def _neighbors(world, bid: str) -> List[str]:
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

def _bfs_reachable(world, src: str, dst: str, max_hops: int = 3) -> bool:
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
    want = _normalize_pred(token)
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out

def _bindings_with_cue(world, token: str) -> List[str]:
    want = f"cue:{token}"
    out = []
    for bid, b in world._bindings.items():
        for t in getattr(b, "tags", []):
            if t == want:
                out.append(bid)
                break
    return out

def any_cue_tokens_present(world, tokens: List[str]) -> bool:
    return any(_bindings_with_cue(world, tok) for tok in tokens)

def has_pred_near_now(world, token: str, hops: int = 3) -> bool:
    now_id = _anchor_id(world, "NOW")
    for bid in _bindings_with_pred(world, token):
        if _bfs_reachable(world, now_id, bid, max_hops=hops):
            return True
    return False

def any_pred_present(world, tokens: List[str]) -> bool:
    return any(_bindings_with_pred(world, tok) for tok in tokens)

@dataclass
class PolicyGate:
    name: str
    dev_gate: Callable[[Any], bool]                      # ctx -> bool
    trigger: Callable[[Any, Any, Any], bool]             # (world, drives, ctx) -> bool
    explain: Optional[Callable[[Any, Any, Any], str]] = None

class PolicyRuntime:
    def __init__(self, catalog: List[PolicyGate]):
        self.catalog = list(catalog)
        self.loaded: List[PolicyGate] = []

    def refresh_loaded(self, ctx) -> None:
        self.loaded = [p for p in self.catalog if _safe(p.dev_gate, ctx)]

    def list_loaded_names(self) -> List[str]:
        return [p.name for p in self.loaded]

    def consider_and_maybe_fire(self, world, drives, ctx, tie_break: str = "first") -> str:
        # 1) evaluate triggers on available policies
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        if not matches:
            return "no_match"

        # If we are fallen, only allow safety gates to execute this tick
        if has_pred_near_now(world, "state:posture_fallen"):
            safety_only = {"policy:recover_fall", "policy:stand_up"}
            matches = [p for p in matches if p.name in safety_only]
            if not matches:
                return "no_match"

        # 2) prefer safety-critical gates if present (then fallback)
        safety = ("policy:recover_fall", "policy:stand_up")
        chosen = next((p for p in matches if p.name in safety), matches[0])

        # 3) context we’ll log (base suggestion, candidate anchors, FOA)
        base  = choose_contextual_base(world, ctx, targets=["state:posture_standing", "stand"])
        foa   = compute_foa(world, ctx, max_hops=2)
        cands = candidate_anchors(world, ctx)

        # PRE-state explanation for the gate we intend to run
        pre_expl = chosen.explain(world, drives, ctx) if chosen.explain else "explain: (not provided)"

        # 4) run the controller once
        try:
            before_n = len(world._bindings)
            result   = action_center_step(world, ctx, drives)
            after_n  = len(world._bindings)
            delta_n  = after_n - before_n
            # use the controller’s own label when available
            label    = result.get("policy") if isinstance(result, dict) and "policy" in result else chosen.name
        except Exception as e:
            return f"{chosen.name} (error: {e})"

        # 5) POST-state explanation for what actually ran
        gate_for_label = next((p for p in self.loaded if p.name == label), chosen)
        post_expl = gate_for_label.explain(world, drives, ctx) if gate_for_label.explain else "explain: (not provided)"

        # 6) annotate anchors for readability (NOW/HERE tagging)
        now_id  = _anchor_id(world, "NOW")
        here_id = _anchor_id(world, "HERE") if hasattr(world, "_anchors") else None
        def _ann(bid: str) -> str:
            if bid == now_id: return f"{bid}(NOW)"
            if here_id and bid == here_id: return f"{bid}(HERE)"
            return f"{bid}"

        # 7) multi-line message
        msg = []
        msg.append(f"Policy executed: {label}")
        msg.append(f"  why(pre):  {pre_expl}")
        msg.append(f"  why(post): {post_expl}")
        msg.append(f"  base_suggestion: {base}")
        msg.append(f"  anchors: [{', '.join(_ann(x) for x in cands)}]")
        msg.append(f"  foa: size={foa['size']} seeds={foa['seeds']}")
        msg.append(f"  effect: {delta_n:+d} new binding(s), result={result}")
        return '\n'.join(msg)

def _safe(fn, *args):
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
            print(f"[boot] Seeded stand as {new_bid} (NOW -> stand)")
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
    print("  • Pretty paths show first pred:* as the node label (fallback to id) and --label--> between nodes")
    print("  • Try: menu 12 'Plan from NOW', menu 7 'Display snapshot', menu 22 'Export interactive graph'\n")

    print("Policies (Action Center overview)")
    print("  • Policies live in cca8_controller and expose:")
    print("      - dev_gate(ctx)       → True/False (availability by development stage/context)")
    print("      - trigger(world, drives, ctx) → True/False (should we act now?)")
    print("      - execute(world, ctx, drives) → adds bindings/edges; stamps provenance")
    print("  • Action Center scans loaded policies in order each tick; first match runs (with safety priority for recovery)")
    print("  • After execute, you may see:")
    print("      - new bindings (with meta.policy)")
    print("      - new edges (with edge.meta.created_by)")
    print("      - skill ledger updates (menu 13 'Show skill stats')\n")

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
    print("\n(See README.md → Tagging Standard for the full write-up.)\n")


# --------------------------------------------------------------------------------------
# Menu text
# --------------------------------------------------------------------------------------

MENU = """\
[hints for text selection instead of numerical selection]
# Inspect / View
1) World stats
2) Show last 5 bindings
3) Inspect binding details
4) List predicates
5) Show drives (raw + tags)
6) Show skill stats
7) Display snapshot (bindings + edges + ctx + policies)
8) Resolve engrams on a binding

# Build / Edit
9) [Add] predicate (creates column engram + binding with pointer)
10) Connect two bindings (src, dst, relation)
11) Delete edge (source, destn, relation)

# Plan / Act
12) Plan from NOW -> <predicate>
13) Input [sensory] cue (vision/smell/touch/sound)
14) Instinct step (Action Center)
15) Autonomic tick (emit interoceptive cues)
16) Simulate fall (add state:posture_fallen and try recovery)

# Save / Export / System
17) Export snapshot (bindings + edges + ctx + policies)
18) Save session → path   [S]
19) Load session → path   [L]
20) Run preflight now
21) Quit
22) Export and display interactive graph with options
23) Understanding bindings, edges, predicates, cues, anchors, policies

[S] Save session → path
[L] Load session → path
[D] Show drives (raw + tags)
[R] Reset current saved session
[T] Tutorial on using and maintaining this simulation

Select: """


# --------------------------------------------------------------------------------------
# Profile stubs (experimental profiles print info and fall back to Mountain Goat)
# --------------------------------------------------------------------------------------

def _goat_defaults():
    # (name, sigma, jump, winners_k)
    return ("Mountain Goat", 0.015, 0.2, 2)

def _print_goat_fallback():
    print("This evolutionary-like configuration is not currently available. "
          "Profile is set to mountain goat-like brain simulation.\n")

def profile_chimpanzee(ctx) -> tuple[str, float, float, int]:
    print(
        "\nChimpanzee-like brain simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language.\n'
    )
    _print_goat_fallback()
    return _goat_defaults()

def profile_human(ctx) -> tuple[str, float, float, int]:
    print(
        "\nHuman-like brain simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
    )
    _print_goat_fallback()
    return _goat_defaults()

def profile_human_multi_brains(ctx, world) -> tuple[str, float, float, int]:
    # Narrative
    print(
        "\nHuman-like one-agent multiple-brains simulation"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this model each agent has multiple brains operating in parallel. There is an intelligent voting mechanism to decide on a response whereby "
        "each of the 5 processes running in parallel can give a response with an indication of how certain they are this is the best response, and the most "
        "certain + most popular response is chosen. As well, all 5 symbolic maps along with their rich store of information in their engrams is continually learning "
        "and updated.\n"
    )
    print(
        "Implementation sketch for multiple-brains in one agent:"
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
        import copy, random
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
        for i, bw in enumerate(brains, start=1):
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
        from collections import Counter, defaultdict
        counts = Counter(r for r, _, _ in proposals)
        avg_conf = defaultdict(list)
        max_conf = defaultdict(float)
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

def profile_society_multi_agents(ctx) -> tuple[str, float, float, int]:
    print(
        "\nHuman-like one-brain simulation × multiple-agents society"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this simulation we have multiple agents each with one human-like brain, all interacting with each other.\n"
    )
    print(
        "Implementation sketch for multiple agents (one brain per agent):"
        "\n  • Representation: each agent has its own WorldGraph, Drives, and policy set; no shared mutable state."
        "\n  • Scheduler: iterate agents each tick (single process first; later, one process per agent with queues)."
        "\n  • Communication: send messages as tags/edges in the receiver’s world (e.g., pred:sound:bleat:mom)."
        "\n  • Persistence: autosave per agent (session_A1.json, session_A2.json, ...)."
        "\n  • Safety: this stub simulates 3 agents for one tick; everything is printed only; no files are written.\n"
    )

    # Scaffolding: create 3 tiny agents, run one tick, pass a simple message
    try:
        import random
        from dataclasses import dataclass

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
                res = action_center_step(a.world, ctx, a.drives)
                print(f"[scaffold] {a.name}: Action Center → {res}")
            except Exception as e:
                print(f"[scaffold] {a.name}: controller error: {e}")

        # Simple broadcast message: A1 'bleats', A2 receives a cue (sound:bleat:mom)
        try:
            print("[scaffold] A1 broadcasts 'sound:bleat:mom' → A2")
            bid = agents[1].world.add_cue("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            #bid = agents[1].world.add_predicate("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            print(f"[scaffold] A2 received cue as binding {bid}; running one controller step on A2...")
            res2 = action_center_step(agents[1].world, ctx, agents[1].drives)
            print(f"[scaffold] A2: Action Center → {res2}")
        except Exception as e:
            print(f"[scaffold] message/cue demo note: {e}")

        print("[scaffold] (End of society dry-run; no snapshots written.)\n")
    except Exception as e:
        print(f"[scaffold] Society demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()
    
def profile_multi_brains_adv_planning(ctx) -> tuple[str, float, float, int]:
    print(
        "\nHuman-like one-agent multiple-brains simulation with combinatorial planning"
        "\n\nAs per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning. "
        "The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these "
        '"same" structures) but enhanced feedback pathways allowing better causal reasoning. Also better combinatorial language. '
        "The human simulation has further enhanced feedback pathways and full causal reasoning, full analogical reasoning and compositional reasoning/language.\n"
        "\nIn this model there are multiple brains, e.g., 5 at the time of this writing, in one agent."
        "There is an intelligent voting mechanism to decide on a response whereby each of the 5 processes running in parallel can give a response with an "
        "indication of how certain they are this is the best response, and the most certain + most popular response is chosen. As well, all 5 "
        "symbolic maps along with their rich store of information in their engrams is continually learning and updated.\n"
        "\nIn addition, in this model each brain has multiple von Neumann processors to independently explore different possible routes to take "
        "or different possible decisions to make.\n"
    )
    print(
        "Implementation sketch (this stub does not commit changes to the live world):"
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
        import random
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
            for pj in range(procs_per_brain):
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

def profile_superhuman(ctx) -> tuple[str, float, float, int]:
    print(
        "\nSuper-human-like machine simulation"
        "\n\nFeatures sketch for an ASI-grade architecture:"
        "\n  • Hierarchical memory: massive multi-modal engrams (vision/sound/touch/text) linked to a compact symbolic index."
        "\n  • Weighted graph planning: edges carry costs/uncertainty; A*/landmarks for long-range navigation in concept space."
        "\n  • Meta-controller: blends proposals from symbolic search, neural value estimation, and program-synthesis planning."
        "\n  • Self-healing & explanation: detect/repair inconsistent states; produce human-readable rationales for actions."
        "\n  • Tool-use & embodiment: external tools (math/vision/robots) wrapped as policies with provenances and safeguards."
        "\n  • Safety envelope: constraint-checking policies that can veto/redirect unsafe plans."
        "\n\nThis stub prints a dry-run of the meta-controller triage and falls back to the Mountain Goat profile.\n"
    )

    # Scaffolding: three-module meta-controller, pick best proposal (no world writes)
    try:
        import random
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

# --------------------------------------------------------------------------------------
# World/intro flows and preflight-lite stamp helpers
# --------------------------------------------------------------------------------------

def choose_profile(ctx, world) -> dict:
    """Prompt once; always default to Mountain Goat unless a profile is implemented.
    For unimplemented profiles, print a narrative and fall back to goat defaults.
    Returns a dict: {"name", "ctx_sigma", "ctx_jump", "winners_k"}.
    """
    GOAT = ("Mountain Goat", 0.015, 0.2, 2)
    try:
        choice = input("Please make a choice [1-7]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled selection.... will exit program....")
        sys.exit(0)

    if choice == "1":
        name, sigma, jump, k = GOAT
    elif choice == "2":
        name, sigma, jump, k = profile_chimpanzee(ctx)
    elif choice == "3":
        name, sigma, jump, k = profile_human(ctx)
    elif choice == "4":
        name, sigma, jump, k = profile_human_multi_brains(ctx, world)
    elif choice == "5":
        name, sigma, jump, k = profile_society_multi_agents(ctx)
    elif choice == "6":
        name, sigma, jump, k = profile_multi_brains_adv_planning(ctx)
    elif choice == "7":
        name, sigma, jump, k = profile_superhuman(ctx)
    else:
        print(f"The selection {choice} is not valid or not available at this time.\n Therefore, defaulting to selection Mountain Goat.")
        name, sigma, jump, k = GOAT

    ctx.profile = name  # record on ctx so it appears in CTX snapshot
    return {"name": name, "ctx_sigma": sigma, "ctx_jump": jump, "winners_k": k}

def versions_dict() -> dict:
    """Collect versions/platform info used for preflight stamps."""
    return {
        "runner": __version__,
        "world_graph": "...",
        "column": "...",
        "features": "...",
        "temporal": "...",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }

def run_preflight_full(args) -> int:
    """
    Full preflight: quick, deterministic checks with one-line PASS/FAIL per item.
    Returns 0 for ok, non-zero for any failure.
    """
    print("[preflight] Running full preflight...")

    failures = 0
    def ok(msg):   print(f"[preflight] PASS  - {msg}")
    def bad(msg):  nonlocal failures; failures += 1; print(f"[preflight] FAIL  - {msg}")

    # 1) Python & platform
    try:
        pyver = sys.version.split()[0]
        ok(f"python={pyver} platform={platform.platform()}")
    except Exception as e:
        bad(f"could not read python/platform: {e}")

    # 2a) CCA8 modules present & importable (plus key symbols)
    try:
        import importlib, os as _os

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
        import pyvis  # type: ignore
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
        
    # 2a) WorldGraph.set_now() — anchor remap & tag housekeeping
    try:
        # fresh temp world just for this test
        _w2 = cca8_world_graph.WorldGraph()

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
            try:
                ts.add(t)        # set
            except AttributeError:
                if t not in ts:  # list
                    ts.append(t)

        def _tag_discard(bid_: str, t: str):
            ts = getattr(_w2._bindings[bid_], "tags", None)
            if ts is None:
                return
            try:
                ts.discard(t)    # set
            except AttributeError:
                try:
                    ts.remove(t) # list
                except ValueError:
                    pass

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
              
    # Z1) Attach semantics (NOW/latest → new binding)
    try:
        _w = cca8_world_graph.WorldGraph()
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

    # Z3) Action metrics aggregator (run with numbers on edge.meta)
    try:
        _w4 = cca8_world_graph.WorldGraph()
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

    # Z4) BFS sanity (shortest-hop path found)
    try:
        _w5 = cca8_world_graph.WorldGraph()
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

    # Summary
    if failures == 0:
        print("[preflight] ok\n\n")
        return 0
    else:
        print(f"[preflight] completed with {failures} failure(s). See lines above.")
        return 1

def run_preflight_lite_maybe():
    """Optional 'lite' preflight on startup (controlled by CCA8_PREFLIGHT)."""
    mode = os.environ.get("CCA8_PREFLIGHT", "lite").lower()
    if mode == "off":
        return
    print("[preflight-lite] checks ok\n\n")

def _anchor_id(world, name="NOW") -> str:
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
    def key_fn(bid: str):
        try: return int(bid[1:])  # sort b1,b2,... numerically
        except: return 10**9
    return sorted(world._bindings.keys(), key=key_fn)

def snapshot_text(world, drives=None, ctx=None, policy_rt=None) -> str:
    """Return the same snapshot text that #16 writes to world_snapshot.txt."""
    lines: List[str] = []
    lines.append("\n--------------------------------------------------------------------------------------")
    lines.append(f"WorldGraph snapshot at {datetime.now()}")
    lines.append("--------------------------------------------------------------------------------------")
    body = getattr(ctx, "body", None) or getattr(getattr(ctx, "hal", None), "body", None) or "(none)"
    lines.append(f"EMBODIMENT: body={body}")
    now_id = _anchor_id(world, "NOW")
    lines.append(f"NOW={now_id}  LATEST={world._latest_binding_id}")
    lines.append("")

    # CTX
    # CTX
    lines.append("CTX:")
    if ctx is not None:
        try:
            from dataclasses import is_dataclass, asdict
            if is_dataclass(ctx):
                ctx_dict = asdict(ctx)
            else:
                ctx_dict = dict(vars(ctx))
        except Exception:
            ctx_dict = {}
        if ctx_dict:
            for k in sorted(ctx_dict.keys()):
                v = ctx_dict[k]
                if isinstance(v, float):
                    lines.append(f"  {k}: {v:.4f}")
                else:
                    lines.append(f"  {k}: {v}")
        else:
            lines.append("  (none)")
    else:
        lines.append("  (none)")
    lines.append("")

    # DRIVES
    lines.append("DRIVES:")
    if drives is not None:
        try:
            lines.append(f"  hunger={drives.hunger:.2f}, fatigue={drives.fatigue:.2f}, warmth={drives.warmth:.2f}")
        except Exception:
            lines.append("  (unavailable)")
    else:
        lines.append("  (none)")
    lines.append("")

    # POLICIES (skills readout)
    lines.append("POLICIES:")
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
    lines.append("POLICIES LOADED (meet devpt requirements):")
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
        tags = ", ".join(getattr(b, "tags", []))
        lines.append(f"{bid}: [{tags}]")

    # EDGES
    lines.append("")
    lines.append("EDGES:")
    for bid in _sorted_bids(world):
        b = world._bindings[bid]
        edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
        if isinstance(edges, list):
            for e in edges:
                rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                if dst:
                    lines.append(f"{bid} --{rel}--> {dst}")

    #return  text to display
    lines.append("--------------------------------------------------------------------------------------\n")
    return "\n".join(lines)

def export_snapshot(world, drives=None, ctx=None, policy_rt=None, path_txt="world_snapshot.txt", path_dot="world_snapshot.dot") -> None:
    """Write a complete snapshot of bindings + edges to text and DOT files, plus ctx/drives/policies."""
    # Text dump (reuse the same builder as #17)
    text_blob = snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt)
    with open(path_txt, "w", encoding="utf-8") as f:
        f.write(text_blob + "\n")

    # Graphviz DOT (optional rendering)
    with open(path_dot, "w", encoding="utf-8") as g:
        g.write("digraph CCA8 {\n  rankdir=LR;\n  node [shape=box,fontsize=10];\n")
        for bid in _sorted_bids(world):
            b = world._bindings[bid]
            tag_lines = "\\n".join(t.replace("pred:", "") for t in getattr(b, "tags", []))
            g.write(f'  {bid} [label="{bid}\\n{tag_lines}"];\n')
        for bid in _sorted_bids(world):
            b = world._bindings[bid]
            edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
            if isinstance(edges, list):
                for e in edges:
                    rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                    dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    if dst:
                        g.write(f'  {bid} -> {dst} [label="{rel}"];\n')
        g.write("}\n")

    # Final message with absolute paths + directory
    import os
    path_txt_abs = os.path.abspath(path_txt)
    path_dot_abs = os.path.abspath(path_dot)
    out_dir = os.path.dirname(path_txt_abs)
    print("Exported snapshot:")
    print(f"  {path_txt_abs}")
    print(f"  {path_dot_abs}")
    print(f"Directory: {out_dir}")


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
        print(f"[io] Started a NEW session. Autosave OFF — use [S] to save or pass --autosave <path>.")



# ---------- Contextual base selection (skeleton) ----------
def _nearest_binding_with_pred(world, token: str, from_bid: str, max_hops: int = 3) -> str | None:
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

def choose_contextual_base(world, ctx, targets: list[str] | None = None) -> dict:
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
    bids = []
    for bid, b in world._bindings.items():
        ts = getattr(b, "tags", [])
        if any(isinstance(t, str) and t.startswith("cue:") for t in ts):
            bids.append(bid)
    return bids

def neighbors_k(world, start_bid: str, max_hops: int = 2) -> set[str]:
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

def compute_foa(world, ctx, max_hops: int = 2) -> dict:
    """
    Skeleton FOA window: union of neighborhoods around LATEST and NOW, plus cue nodes.
    Later we can weight by drives/costs and restrict size aggressively.
    """
    now_id   = _anchor_id(world, "NOW")
    latest   = world._latest_binding_id
    seeds    = [x for x in [latest, now_id] if x]
    seeds   += present_cue_bids(world)
    # dedupe seeds while preserving original order
    _seen = set()
    seeds = [s for s in seeds if not (s in _seen or _seen.add(s))]
    foa_ids  = set()
    for s in seeds:
        foa_ids |= neighbors_k(world, s, max_hops=max_hops)
    return {"seeds": seeds, "size": len(foa_ids), "ids": foa_ids}

# ---------- Multi-anchor candidates (skeleton) ----------
def candidate_anchors(world, ctx) -> list[str]:
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
    drives = Drives()
    ctx = Ctx()
    #attribute defaults already exist in class Ctx but can be adjusted here also
    ctx.sigma = 0.015
    ctx.jump = 0.2
    ctx.age_days = 0.0
    ctx.ticks = 0
    POLICY_RT = PolicyRuntime(CATALOG_GATES)
    POLICY_RT.refresh_loaded(ctx)
    loaded_ok = False
    loaded_src = None

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
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
        POLICY_RT.refresh_loaded(ctx)
    else:
        profile = choose_profile(ctx, world)
        name = profile["name"]
        sigma, jump, k = profile["ctx_sigma"], profile["ctx_jump"], profile["winners_k"]
        ctx.sigma, ctx.jump = sigma, jump
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
        POLICY_RT.refresh_loaded(ctx)
    _io_banner(args, loaded_src, loaded_ok)

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

    # Interactive menu loop
    pretty_scroll = True  #to see changes before terminal menu scrolls over screen
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

        # ---- Text command aliases (words + 3-letter prefixes → legacy actions) -----
        MIN_PREFIX = 3 #if not perfect match then this specifies how many letters to match
        #will map to current menu which then must be mapped to original menu numbers
        _ALIASES = {
            # Inspect / View
            "world": "1", "stats": "1",
            "last": "2", "bindings": "2",
            "inspect": "3", "details": "3", "id": "3",
            "listpredicates": "4", "listpreds": "4", "listp": "4",
            "drives": "d",
            "skills": "6",
            "snapshot": "7", "display": "7",

            # Build / Edit
            "resolve": "8", "engrams": "8",
            "add": "9", "predicate": "9",
            "connect": "10", "link": "10",
            "delete": "11", "del": "11", "rm": "11",

            # Plan / Act
            "plan": "12",
            "sensory": "13", "cue": "13",
            "instinct": "14", "act": "14",
            "autonomic": "15", "tick": "15",
            "fall": "16", "simulate": "16",

            # Save / Export / System
            "export snapshot": "17",
            "pyvis": "22", "graph": "22", "viz": "22", "html": "22", "interactive": "22", "export and display": "22",
            "save": "s",
            "load": "l",
            "preflight": "20",
            "quit": "21", "exit": "21",  #no 'q' to avoid exit by mistake
            "tutorial": "t", "help": "t",
            
            # Tagging/policies help
            "understanding": "23", "bindings-help": "23", "predicates-help": "23",
            "cues-help": "23", "policies-help": "23", "tagging": "23", "standard": "23",
            
        }

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

        # NEW MENU compatibility: accept new grouped numbers and legacy ones.
        _new_to_old = {
            "1": "1",    # World stats
            "2": "7",    # Show last 5 bindings
            "3": "10",   # Inspect binding details
            "4": "2",    # List predicates
            "5": "d",    # Show drives (raw + tags)
            "6": "13",   # Show skill stats
            "7": "17",   # Display snapshot
            "8": "6",    # Resolve engrams on a binding
            "9": "3",    # Add predicate
            "10": "4",   # Connect two bindings
            "11": "15",  # Delete edge
            "12": "5",   # Plan from NOW -> <predicate>
            "13": "11",  # Add sensory cue
            "14": "12",  # Instinct step
            "15": "14",  # Autonomic tick
            "16": "18",  # Simulate fall
            "17": "16",  # Export snapshot
            "18": "s",   # Save session
            "19": "l",   # Load session
            "20": "9",   # Run preflight now
            "21": "8",   # Quit
            "22": "22",  # Export and display interactive graph (Pyvis HTML)
            "23": "23",  # Understanding bindings/edges/predicates/cues/anchors/policies
        }

        ckey = choice.strip().lower() #ensure any present or future routed value is in correct form

        if ckey in _new_to_old:
            routed = _new_to_old[ckey]
            if pretty_scroll:
                print(f"[[menu numbering auto-compatibility] processed input entry routed to old value: {ckey} → {routed}]")
            choice = routed
        else:
            choice = ckey

        if choice == "1":
            # World stats
            now_id = _anchor_id(world, "NOW")
            print(f"Bindings: {len(world._bindings)}  Anchors: NOW={now_id}  Latest: {world._latest_binding_id}")
            try:
                print(f"Policies loaded: {len(POLICY_RT.loaded)} -> {', '.join(POLICY_RT.list_loaded_names()) or '(none)'}")
            except Exception:
                pass
            loop_helper(args.autosave, world, drives)

        elif choice == "2":
            # List predicates
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
            token = input("Enter predicate token (e.g., state:posture_standing): ").strip()
            if token:
                bid = world.add_predicate(token, attach="latest", meta={"added_by": "user"})
                print(f"Added binding {bid} with pred:{token}")
            loop_helper(args.autosave, world, drives)

        elif choice == "4":
            # Connect two bindings (with duplicate warning)
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

            loop_helper(args.autosave, world, drives)

        elif choice == "5":
            # Plan from NOW -> <predicate>
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
                        node_mode="id+pred",       # try 'pred' if you prefer only tokens
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
            bid = input("Binding id to resolve engrams: ").strip()
            b = world._bindings.get(bid)
            if not b:
                print("Unknown binding id.")
            else:
                print("Engrams:", b.engrams if b.engrams else "(none)")
            loop_helper(args.autosave, world, drives)

        elif choice == "7":
            # Show last 5 bindings
            last_ids = sorted(world._bindings.keys(), key=lambda x: int(x[1:]))[-5:]
            for bid in last_ids:
                b = world._bindings[bid]
                tags = ", ".join(sorted(b.tags))
                print(f"  {bid}: tags=[{tags}] engrams={[k for k in (b.engrams or {}).keys()]}")
            if not last_ids:
                print("(no bindings yet)")
            print()
            loop_helper(args.autosave, world, drives)

        elif choice == "8":
            # Quit
            print("Goodbye.")
            if args.save:
                save_session(args.save, world, drives)
            return

        elif choice == "9":
            # Run preflight now
            rc = run_preflight_full(args)
            loop_helper(args.autosave, world, drives)

        elif choice == "10":
            # Inspect binding details
            bid = input("Binding id to inspect: ").strip()
            b = world._bindings.get(bid)
            if not b:
                print("Unknown binding id.")
            else:
                print(f"ID: {bid}")
                print("Tags:", ", ".join(sorted(b.tags)))
                print("Meta:", json.dumps(b.meta, indent=2))
                if b.edges:
                    print("Edges:")
                    for e in b.edges:
                        print("  --", e.get("label", "?"), "-->", e.get("to"))
                else:
                    print("Edges: (none)")
            loop_helper(args.autosave, world, drives)

        elif choice == "11":
            # Add sensory cue
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
            before_n = len(world._bindings)

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

            # --- execute the controller once (probe) ---
            result = action_center_step(world, ctx, drives)
            print("Action Center:", result)

            # best-effort WHY: match the controller's returned label to a loaded gate
            label = result.get("policy") if isinstance(result, dict) and "policy" in result else "(controller)"
            gate  = next((p for p in POLICY_RT.loaded if p.name == label), None)
            if gate and gate.explain:
                try:
                    print("[instinct] why:", gate.explain(world, drives, ctx))
                except Exception:
                    pass

            # delta and autosave
            after_n = len(world._bindings)
            if after_n == before_n:
                print("(no new bindings/edges created this step)")
            else:
                print(f"(graph updated: bindings {before_n} -> {after_n})")

            loop_helper(args.autosave, world, drives)

        elif choice == "13":
            # Show skill stats
            print(skill_readout())
            loop_helper(args.autosave, world, drives)

        elif choice == "14":
            # Autonomic tick
            drives.fatigue = min(1.0, drives.fatigue + 0.01)
            # advance developmental clock
            try:
                ctx.ticks = getattr(ctx, "ticks", 0) + 1
                ctx.age_days = getattr(ctx, "age_days", 0.0) + 0.01   # tune step as you like
                print(f"Autonomic: fatigue +0.01 | ticks={ctx.ticks} age_days={ctx.age_days:.2f}")
            except Exception:
                print("Autonomic: fatigue +0.01")

            #Refresh availability and consider firing regardless
            POLICY_RT.refresh_loaded(ctx)
            fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx)
            if fired != "no_match":
                print(fired)
            loop_helper(args.autosave, world, drives)

        elif choice == "15":
            # Delete edge and autosave (if --autosave is active).
            try:
                delete_edge_flow(world, autosave_cb=lambda: loop_helper(args.autosave, world, drives))
            except NameError:
                # Older builds: no helper available for callback style—do a simple save after.
                delete_edge_flow(world, autosave_cb=None)
                loop_helper(args.autosave, world, drives)

        elif choice == "16":
            # Export snapshot
            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives)

        elif choice == "17":
            # Display snapshot
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
                            import sys, os, webbrowser
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
            show_edge_labels = False if el in {"n", "no", "0"} else True

            try:
                ph = input("Enable physics (force-directed layout)? [Y/n]: ").strip().lower()
            except Exception:
                ph = ""
            physics = False if ph in {"n", "no", "0"} else True

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
                        import sys, os, webbrowser
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


        elif choice == "18":
            # Simulate a fall event and try a recovery attempt immediately
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

        elif choice.lower() == "s":
            # Save session
            path = input("Save to file (e.g., session.json): ").strip()
            if path:
                ts = save_session(path, world, drives)
                print(f"Saved to {path} at {ts}")

        elif choice.lower() == "l":
            # Load session
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
            print(f"hunger={drives.hunger:.2f}, fatigue={drives.fatigue:.2f}, warmth={drives.warmth:.2f}")
            tags = _drive_tags(drives)
            print("drive tags:", ", ".join(tags) if tags else "(none)")
            loop_helper(args.autosave, world, drives)

        elif choice.lower() == "r":
            # Reset current saved session: delete autosave file (if any) and reinit state
            if not args.autosave:
                print("No current saved json file to reset.")
            else:
                path = args.autosave
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
            continue  # back to menu

        elif choice.lower() == "t":
            # Tutorial access: try to open the local compendium
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
            # no autosave here
            continue

        else:
            print("Input selection does not match any existing options. Please try again.")

# --------------------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """argument parser and program entry"""

    ##argparse and processing of certain flags here
    # argparse flags
    p = argparse.ArgumentParser(prog="cca8_run.py")
    p.add_argument("--about", action="store_true", help="Print version and component info")
    p.add_argument("--version", action="store_true", help="Print just the runner version")
    p.add_argument("--hal", action="store_true", help="Enable HAL embodiment stub (if available)")
    p.add_argument("--body", help="Body/robot profile to use with HAL")
    #p.add_argument("--period", type=int, default=None, help="Optional period (for tagging)")
    #p.add_argument("--year", type=int, default=None, help="Optional year (for tagging)")
    p.add_argument("--no-intro", action="store_true", help="Skip the intro banner")
    p.add_argument("--profile", choices=["goat","chimp","human","super"],
               help="Pick a profile without prompting (goat=Mountain Goat, chimp=Chimpanzee, human=Human, super=Super-Human)")
    p.add_argument("--preflight", action="store_true", help="Run full preflight and exit")
    #p.add_argument("--write-artifacts", action="store_true", help="Write preflight artifacts to disk")
    p.add_argument("--load", help="Load session from JSON file")
    p.add_argument("--save", help="Save session to JSON file on exit")
    p.add_argument("--autosave", help="Autosave session to JSON file after each action")
    p.add_argument("--plan", metavar="PRED", help="Plan from NOW to predicate and exit")
    p.add_argument("--no-boot-prime", action="store_true", help="Disable boot seeding of stand intent")
    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    # process embodiment flags and continue with code
    try:
        if args.hal:
            args.hal_status_str = "on (however, a full R-HAL has not been implemented\n     at this time, thus software will run without consideration of the robotic embodiment)"
        else:
            args.hal_status_str = "off (runs without consideration of the robotic embodiment)"
        body = (args.body or "").strip()
        args.body_status_str = f"{body if body else 'none specified'}"
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