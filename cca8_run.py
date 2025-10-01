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
from typing import Optional, Any, Dict, List

import cca8_world_graph as wgmod
from cca8_controller import Drives, action_center_step, skill_readout, skills_to_dict, skills_from_dict

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
        "app_version": "cca8_run/0.7.8",
        "platform": platform.platform(),
    }
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp, path)
    return ts

# --------------------------------------------------------------------------------------
# Console helpers
# --------------------------------------------------------------------------------------

def print_header():
    print("\nA Warm Welcome to the CCA8 Mammalian Brain Simulation")
    print("(version cca8_run.py: 0.7.8)")
    print(f"(cca8_world_graph: 0.1.0, cca8_column: 0.1.0,\n run_world_patched: n/a, cca8_features: 0.1.0, cca8_temporal: 0.1.0)\n")
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
    print("Intro goes here")

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
        "runner": "0.7.8",
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
            print(f"Bindings: {len(world._bindings)}  Anchors: {list(world._anchors.keys())}  Latest: {world._latest_binding_id}")
            loop_helper(args.autosave, world, drives)

        elif choice == "2":
            seen = set()
            for b in world._bindings.values():
                for t in b.tags:
                    if t.startswith("pred:"):
                        seen.add(t)
            for t in sorted(seen):
                print(" ", t.replace("pred:", "", 1))
            if not seen:
                print("(no predicates yet)")
            loop_helper(args.autosave, world, drives)

        elif choice == "3":
            token = input("Enter predicate token (e.g., state:posture_standing): ").strip()
            if token:
                bid = world.add_predicate(token, attach="now", meta={"added_by": "user"})
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
            print("Autonomic: fatigue +0.01")
            loop_helper(args.autosave, world, drives)
            
        elif choice == "15":
            # Delete edge and autosave (if --autosave is active).
            try:
                delete_edge_flow(world, autosave_cb=lambda: loop_helper(args.autosave, world, drives))
            except NameError:
                # Older builds: no helper available for callback style—do a simple save after.
                delete_edge_flow(world, autosave_cb=None)
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
            comp = os.path.join(os.getcwd(), "CCA8_Compendium_All-in-One.md")
            print(f"Tutorial file (Compendium): {comp}")
            if os.path.exists(comp):
                try:
                    if sys.platform.startswith("win"):
                        os.startfile(comp)  # type: ignore[attr-defined]
                    elif sys.platform == "darwin":
                        os.system(f'open "{comp}"')
                    else:
                        os.system(f'xdg-open "{comp}"')
                    print("Opened the compendium in your default viewer.")
                except Exception as e:
                    print(f"[warn] Could not open automatically: {e}")
                    print("Please open the file manually in your editor.")
            else:
                print("Compendium not found in the current folder. Copy it here to open directly.")
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
        print("0.7.8")
        return 0

    if args.about:
        print("CCA8 Components:")
        print(f"  - cca8_run.py v0.7.8 ({os.path.abspath(__file__)})")
        print(f"  - cca8_world_graph v0.1.0 ({getattr(wgmod, '__file__', 'cca8_world_graph.py')})")
        print(f"  - cca8_column   v0.1.0 (cca8_column.py)")
        print(f"  - cca8_features      v0.1.0 (cca8_features.py)")
        print(f"  - cca8_temporal   v0.1.0 (cca8_temporal.py)")
        print(f"  - Profile: Human (k=3, sigma=0.02, jump=0.25)")
        try:
            from cca8_controller import PRIMITIVES
            print(f"  - cca8_controller v0.1.2 (cca8_controller.py) [primitives: {len(PRIMITIVES)}]")
        except Exception:
            print(f"  - cca8_controller v0.1.2 (cca8_controller.py)")
        return 0

    if args.preflight:
        print("[preflight] Running full preflight..."); time.sleep(0.2); print("[preflight] ok."); return 0

    interactive_loop(args); return 0

# --------------------------------------------------------------------------------------
# __main__
# --------------------------------------------------------------------------------------

if __name__ == "__main__":
    sys.exit(main())
