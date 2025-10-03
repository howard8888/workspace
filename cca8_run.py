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

from __future__ import annotations

import argparse
import json
import os
import platform
import sys
import time
from datetime import datetime
from dataclasses import dataclass
from typing import Optional, Any, Dict, List

import cca8_world_graph as wgmod
from cca8_controller import Drives, action_center_step, skill_readout, skills_to_dict, skills_from_dict

__version__ = "0.7.9"

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

# --------------------------------------------------------------------------------------
# Two-gate policy and helpers and console helpers
# --------------------------------------------------------------------------------------

def print_header():
    print("\nA Warm Welcome to the CCA8 Mammalian Brain Simulation")
    print(f"(cca8_run.py v{__version__})\n")
    print(f"Entry point program being run: {os.path.abspath(sys.argv[0])}")
    print(f"OS: {sys.platform} (run system-dependent utilities for more detailed info)")
    print('(for non-interactive execution, ">python cca8_run.py --help" to see optional flags you can set)')
    print("Embodiment: this version of the CCA8 simulation is currently configured to run without a robot body")
    print("(HAL(hardware abstraction layer) must be provided with embodiment drivers and HAL flag set)\n")
    print("The simulation of the cognitive architecture can be adjusted to add or take away")
    print("  various features, allowing exploration of different evolutionary-like configurations.\n")
    print("  1. Mountain Goat-like brain simulation")
    print("  2. Chimpanzee-like brain simulation")
    print("  3. Human-like brain simulation")
    print("  4. Super-Human-like machine simulation\n")
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

class PolicyRuntime:
    def __init__(self, catalog: List[PolicyGate]):
        self.catalog = list(catalog)
        self.loaded: List[PolicyGate] = []

    def refresh_loaded(self, ctx) -> None:
        self.loaded = [p for p in self.catalog if _safe(p.dev_gate, ctx)]

    def list_loaded_names(self) -> List[str]:
        return [p.name for p in self.loaded]

    def consider_and_maybe_fire(self, world, drives, ctx, tie_break: str = "first") -> str:
        # evaluate triggers on available policies
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        if not matches:
            return "no_match"
        chosen = matches[0] if tie_break == "first" else matches[0]  # placeholder for later scoring
        # delegate actual step selection/execution to your existing Action Center primitive
        try:
            result = action_center_step(world, ctx, drives)
        except Exception as e:
            return f"{chosen.name} (error: {e})"
        return f"{chosen.name} -> {result}"

def _safe(fn, *args):
    try:
        return bool(fn(*args))
    except Exception:
        return False

CATALOG_GATES: List[PolicyGate] = [
    PolicyGate(
        name="policy:stand_up",
        dev_gate=lambda ctx: getattr(ctx, "age_days", 0.0) <= 3.0,  # available from birth
        trigger=lambda W, D, ctx: has_pred_near_now(W, "stand")
    ),
    PolicyGate(
        name="policy:seek_mom",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: (getattr(D, "hunger", 0.0) > 0.6) and any_pred_present(
            W, ["vision:silhouette:mom", "smell:milk:scent", "sound:bleat:mom"]
        )
    ),
    PolicyGate(
        name="policy:suckle",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: has_pred_near_now(W, "mom:close")
    ),
    PolicyGate(
        name="policy:recover_miss",
        dev_gate=lambda ctx: True,
        trigger=lambda W, D, ctx: has_pred_near_now(W, "nipple:missed")
    ),
]

# --------------------------------------------------------------------------------------
# Menu text
# --------------------------------------------------------------------------------------

MENU = """\
1) World stats
2) List predicates
3) Add predicate (creates column engram + binding with pointer)
4) Connect two bindings (src, dst, relation)
5) Plan from NOW -> <predicate>
6) Resolve engrams on a binding
7) Show last 5 bindings
8) Quit
9) Run preflight now
10) Inspect binding details
11) Add sensory cue (vision/smell/touch/sound)
12) Instinct step (Action Center)
13) Show skill stats
14) Autonomic tick (emit interoceptive cues)
15) Delete edge (source, destn, relation)
16) Export snapshot (bindings + edges + ctx + policies)

[S] Save session → path
[L] Load session → path
[D] Show drives (raw + tags)
[R] Reset current saved session
[T] Tutorial on using and maintaining this simulation
    
Select: """

# --------------------------------------------------------------------------------------
# World/intro flows and preflight-lite stamp helpers
# --------------------------------------------------------------------------------------

def choose_profile(ctx) -> dict:
    """Prompt for a profile and set ctx parameters.

    Returns:
        A dict describing the chosen profile (name, sigma, jump, k).
    """
    name = ""
    sigma = 0.015
    jump = 0.2
    k = 2

    while True:
        try:
            choice = input("Please make a choice [1-4]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled.")
            sys.exit(0)

        if choice == "1":
            name = "Mountain Goat"
            sigma, jump, k = 0.015, 0.2, 2
            break
        elif choice == "2":
            name = "Chimpanzee"
            sigma, jump, k = 0.02, 0.25, 3
            break
        elif choice == "3":
            name = "Human"
            sigma, jump, k = 0.03, 0.3, 4
            break
        elif choice == "4":
            name = "Super-Human"
            sigma, jump, k = 0.05, 0.35, 5
            break
        else:
            print("Select 1, 2, 3, or 4.")

    CURRENT_PROFILE = {"name": name, "ctx_sigma": sigma, "ctx_jump": jump, "winners_k": k}
    return CURRENT_PROFILE

def versions_dict() -> dict:
    """Collect versions/platform info used for preflight stamps."""
    return {
        "runner": __version__,
        "world_graph": "0.1.0",
        "column": "0.1.0",
        "features": "0.1.0",
        "temporal": "0.1.0",
        "platform": platform.platform(),
        "python": sys.version.split()[0],
    }

def run_preflight_lite_maybe():
    """Optional 'lite' preflight on startup (controlled by CCA8_PREFLIGHT)."""
    mode = os.environ.get("CCA8_PREFLIGHT", "lite").lower()
    if mode == "off":
        return
    print("[preflight-lite] basic checks ok.\n")
    
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
    
def export_snapshot(world, drives=None, ctx=None, policy_rt=None, path_txt="world_snapshot.txt", path_dot="world_snapshot.dot") -> None:

    """Write a complete snapshot of bindings + edges to text and DOT files, plus ctx/drives/policies."""
    # Text dump
    with open(path_txt, "w", encoding="utf-8") as f:
        now_id = _anchor_id(world, "NOW")
        f.write(f"NOW={now_id}  LATEST={world._latest_binding_id}\n\n")

        # CTX section (if provided)
        if ctx is not None:
            try:
                ctx_dict = dict(vars(ctx))
            except Exception:
                ctx_dict = {}
            f.write("CTX:\n")
            if ctx_dict:
                for k in sorted(ctx_dict.keys()):
                    v = ctx_dict[k]
                    # keep it readable
                    if isinstance(v, float):
                        f.write(f"  {k}: {v:.4f}\n")
                    else:
                        f.write(f"  {k}: {v}\n")
            else:
                f.write("  (none)\n")
            f.write("\n")

        # DRIVES section (if provided)
        if drives is not None:
            f.write("DRIVES:\n")
            try:
                f.write(f"  hunger={drives.hunger:.2f}, fatigue={drives.fatigue:.2f}, warmth={drives.warmth:.2f}\n")
            except Exception:
                f.write("  (unavailable)\n")
            f.write("\n")

        # POLICIES / skills
        try:
            sr = skill_readout()  # imported from controller
            f.write("POLICIES:\n")
            if sr.strip():
                # skill_readout() already returns formatted text
                for line in sr.strip().splitlines():
                    f.write(f"  {line}\n")
            else:
                f.write("  (none)\n")
            f.write("\n")
        except Exception:
            pass
              
        # POLICY GATES (availability)
        if policy_rt is not None:
            f.write("POLICY_GATES_LOADED:\n")
            names = policy_rt.list_loaded_names()
            if names:
                for nm in names:
                    f.write(f"  - {nm}\n")
            else:
                f.write("  (none)\n")
            f.write("\n")

        # BINDINGS list
        f.write("BINDINGS:\n")
        for bid in _sorted_bids(world):
            b = world._bindings[bid]
            tags = ", ".join(getattr(b, "tags", []))
            f.write(f"{bid}: [{tags}]\n")

        # EDGES list
        f.write("\nEDGES:\n")
        for bid in _sorted_bids(world):
            b = world._bindings[bid]
            edges = getattr(b, "edges", []) or getattr(b, "out", []) or getattr(b, "links", []) or getattr(b, "outgoing", [])
            if isinstance(edges, list):
                for e in edges:
                    rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
                    dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    if dst:
                        f.write(f"{bid} --{rel}--> {dst}\n")

    # Graphviz DOT (optional nice rendering)
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

# --------------------------------------------------------------------------------------
# Interactive loop
# --------------------------------------------------------------------------------------

def interactive_loop(args: argparse.Namespace) -> None:
    """Main interactive loop."""
    # Build initial world/drives fresh
    world = wgmod.WorldGraph()
    drives = Drives()
    ctx = type("Ctx", (), {})()   # minimal context object
    ctx.sigma = 0.015
    ctx.jump = 0.2
    ctx.age_days = 0.0
    ctx.ticks = 0
    POLICY_RT = PolicyRuntime(CATALOG_GATES)
    POLICY_RT.refresh_loaded(ctx)


    # Attempt to load a prior session if requested
    if args.load:
        try:
            with open(args.load, "r", encoding="utf-8") as f:
                blob = json.load(f)
            print(f"Loaded {args.load} (saved_at={blob.get('saved_at','?')})")
            print("A previously saved simulation session is being continued here.\n")
            new_world  = wgmod.WorldGraph.from_dict(blob.get("world", {}))
            new_drives = Drives.from_dict(blob.get("drives", {}))
            skills_from_dict(blob.get("skills", {}))
            world, drives = new_world, new_drives
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
    print_header()
    profile = choose_profile(ctx)
    name = profile["name"]
    sigma, jump, k = profile["ctx_sigma"], profile["ctx_jump"], profile["winners_k"]
    ctx.sigma = sigma
    ctx.jump = jump
    print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
    POLICY_RT.refresh_loaded(ctx)

    # Ensure NOW anchor exists for the episode (so attachments from "now" resolve)
    world.ensure_anchor("NOW")

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
    while True:
        try:
            choice = input(MENU).strip()
        except (EOFError, KeyboardInterrupt):
            print("\nGoodbye.")
            return

        if choice == "1":
            now_id = _anchor_id(world, "NOW")
            print(f"Bindings: {len(world._bindings)}  Anchors: NOW={now_id}  Latest: {world._latest_binding_id}")
            try:
                print(f"Policies loaded: {len(POLICY_RT.loaded)} -> {', '.join(POLICY_RT.list_loaded_names()) or '(none)'}")
            except Exception:
                pass
            loop_helper(args.autosave, world, drives)

        elif choice == "2":
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
            token = input("Enter predicate token (e.g., state:posture_standing): ").strip()
            if token:
                bid = world.add_predicate(token, attach="latest", meta={"added_by": "user"})
                print(f"Added binding {bid} with pred:{token}")
            loop_helper(args.autosave, world, drives)

        elif choice == "4":
            src = input("Source binding id (e.g., b12): ").strip()
            dst = input("Dest binding id (e.g., b13): ").strip()
            label = input('Relation label (e.g., "then"): ').strip() or "then"
            try:
                world.add_edge(src, dst, label)
                print(f"Linked {src} --{label}--> {dst}")
            except KeyError as e:
                print("Invalid id:", e)
            loop_helper(args.autosave, world, drives)

        elif choice == "5":
            token = input("Target predicate (e.g., state:posture_standing): ").strip()
            if not token:
                loop_helper(args.autosave, world, drives)
                continue
            src_id = world.ensure_anchor("NOW")
            path = world.plan_to_predicate(src_id, token)
            if path:
                print("Path:", " -> ".join(path))
            else:
                print("No path found.")
            loop_helper(args.autosave, world, drives)

        elif choice == "6":
            bid = input("Binding id to resolve engrams: ").strip()
            b = world._bindings.get(bid)
            if not b:
                print("Unknown binding id.")
            else:
                print("Engrams:", b.engrams if b.engrams else "(none)")
            loop_helper(args.autosave, world, drives)

        elif choice == "7":
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
            print("Goodbye.")
            if args.save:
                save_session(args.save, world, drives)
            return

        elif choice == "9":
            print("[preflight] Running full preflight...")
            time.sleep(0.2)
            print("[preflight] ok.")
            loop_helper(args.autosave, world, drives)

        elif choice == "10":
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
            ch = input("Channel (vision/smell/touch/sound): ").strip().lower()
            tok = input("Cue token (e.g., mom:close): ").strip()
            if ch and tok:
                pred = f"{ch}:{tok}"
                bid = world.add_predicate(pred, attach="now", meta={"channel": ch, "user": True})
                print(f"Added sensory cue: pred:{pred} as {bid}")
                fired = POLICY_RT.consider_and_maybe_fire(world, drives, ctx, tie_break="first")
                if fired != "no_match":
                    print("Policy executed:", fired)
            loop_helper(args.autosave, world, drives)

        elif choice == "12":
            result = action_center_step(world, ctx, drives)
            print("Action Center:", result)
            loop_helper(args.autosave, world, drives)

        elif choice == "13":
            print(skill_readout())
            loop_helper(args.autosave, world, drives)

        elif choice == "14":
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
                print("Policy executed:", fired)
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
            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives)

        elif choice.lower() == "s":
            path = input("Save to file (e.g., session.json): ").strip()
            if path:
                ts = save_session(path, world, drives)
                print(f"Saved to {path} at {ts}")

        elif choice.lower() == "l":
            path = input("Load from file: ").strip()
            if path and os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        blob = json.load(f)
                    print(f"Loaded {path} (saved_at={blob.get('saved_at','?')})")
                    new_world  = wgmod.WorldGraph.from_dict(blob.get("world", {}))
                    new_drives = Drives.from_dict(blob.get("drives", {}))
                    skills_from_dict(blob.get("skills", {}))
                    world, drives = new_world, new_drives
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
                world = wgmod.WorldGraph()
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
            print("Unknown selection.")

# --------------------------------------------------------------------------------------
# main()
# --------------------------------------------------------------------------------------

def main(argv: Optional[list[str]] = None) -> int:
    """Argument parser and program entry."""
    p = argparse.ArgumentParser(prog="cca8_run.py")
    p.add_argument("--about", action="store_true", help="Print version and component info")
    p.add_argument("--version", action="store_true", help="Print just the runner version")
    p.add_argument("--hal", action="store_true", help="Enable HAL embodiment stub (if available)")
    p.add_argument("--body", help="Body/robot profile to use with HAL")
    p.add_argument("--period", type=int, default=None, help="Optional period (for tagging)")
    p.add_argument("--year", type=int, default=None, help="Optional year (for tagging)")
    p.add_argument("--no-intro", action="store_true", help="Skip the intro banner")
    p.add_argument("--preflight", action="store_true", help="Run full preflight and exit")
    p.add_argument("--write-artifacts", action="store_true", help="Write preflight artifacts to disk")
    p.add_argument("--load", help="Load session from JSON file")
    p.add_argument("--save", help="Save session to JSON file on exit")
    p.add_argument("--autosave", help="Autosave session to JSON file after each action")
    p.add_argument("--plan", metavar="PRED", help="Plan from NOW to predicate and exit")

    try:
        args = p.parse_args(argv)
    except SystemExit as e:
        return 2 if e.code else 0

    if args.version:
        print(__version__)
        return 0

    if args.about:
        print("CCA8 Components:")
        print(f"  - cca8_run.py v{__version__} ({os.path.abspath(__file__)})")
        print(f"  - cca8_world_graph v... ({getattr(wgmod, '__file__', 'cca8_world_graph.py')})")
        print(f"  - cca8_column   v... (cca8_column.py)")
        print(f"  - cca8_features      v... (cca8_features.py)")
        print(f"  - cca8_temporal   v... (cca8_temporal.py)")
        print(f"  - Profile: Human (k=3, sigma=0.02, jump=0.25)")
        try:
            from cca8_controller import PRIMITIVES
            print(f"  - cca8_controller v... (cca8_controller.py) [primitives: {len(PRIMITIVES)}]")
        except Exception:
            print(f"  - cca8_controller v...(cca8_controller.py)")
        return 0

    if args.preflight:
        print("[preflight] Running full preflight..."); time.sleep(0.2); print("[preflight] ok."); return 0

    interactive_loop(args); return 0

# --------------------------------------------------------------------------------------
# __main__
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
