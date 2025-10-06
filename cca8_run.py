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
from typing import Optional, Any, Dict, List, Callable

import cca8_world_graph as wgmod
from cca8_controller import Drives, action_center_step, skill_readout, skills_to_dict, skills_from_dict

__version__ = "0.7.10"

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
            and any_pred_present(W, ["vision:silhouette:mom", "smell:milk:scent", "sound:bleat:mom"])
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
            or any_pred_present(W, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])
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
17) Display snapshot (bindings + edges + ctx + policies)
18) Simulate fall (add state:posture_fallen and try recovery)

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
    """Prompt once; always default to Mountain Goat.
    If 2/3/4 (or invalid) is chosen, print a notice and fall back to goat.
    Returns a dict: {"name", "ctx_sigma", "ctx_jump", "winners_k"}.
    """
    GOAT = ("Mountain Goat", 0.015, 0.2, 2)

    try:
        choice = input("Please make a choice [1-4]: ").strip()
    except (EOFError, KeyboardInterrupt):
        print("\nCancelled selection.... will exit program....")
        sys.exit(0)

    if choice == "1":
        name, sigma, jump, k = GOAT
    elif choice in {"2", "3", "4"}:
        print("This evolutionary-like configuration is not currently available. "
              "Profile is set to mountain goat-like brain simulation.")
        name, sigma, jump, k = GOAT
    else:
        # invalid/empty entry → default to goat
        print(f"The selection {choice} is not valid or not available at this time.\n Therefore, defaulting to selection Mountain Goat.")
        name, sigma, jump, k = GOAT

    # record on ctx so it appears in CTX snapshot
    ctx.profile = name

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

    # 2) WorldGraph sanity
    try:
        w = wgmod.WorldGraph()
        w.ensure_anchor("NOW")
        if isinstance(w._bindings, dict) and _anchor_id(w, "NOW") != "?":
            ok("WorldGraph init and NOW anchor")
        else:
            bad("WorldGraph anchor missing or invalid")
    except Exception as e:
        bad(f"WorldGraph init failed: {e}")

    # 3) Controller primitives
    try:
        from cca8_controller import PRIMITIVES, Drives as _Drv
        if isinstance(PRIMITIVES, list) and len(PRIMITIVES) >= 1:
            ok(f"controller primitives loaded (count={len(PRIMITIVES)})")
        else:
            bad("controller primitives missing/empty")
        # Smoke: run an empty action_center_step on a fresh world
        try:
            _w = wgmod.WorldGraph(); _w.ensure_anchor("NOW")
            _d = _Drv()
            _ctx = type("Ctx", (), {})(); _ctx.sigma=0.015; _ctx.jump=0.2; _ctx.age_days=0.0; _ctx.ticks=0
            _ = action_center_step(_w, _ctx, _d)
            ok("action_center_step smoke-run")
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
        ts = save_session(tmp, wgmod.WorldGraph(), d)
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
        w = wgmod.WorldGraph()
        src = w.ensure_anchor("NOW")
        # plan to something that isn't there: expect no path, not an exception
        p = w.plan_to_predicate(src, "milk:drinking")
        ok(f"planner probes (path_found={bool(p)})")
    except Exception as e:
        bad(f"planner probe failed: {e}")

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
    lines.append("CTX:")
    if ctx is not None:
        try:
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

    # Graphviz DOT (optional nice  rendering)
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
        if any(isinstance(t, str) and (t.startswith("pred:vision:") or t.startswith("pred:smell:") or t.startswith("pred:sound:") or t.startswith("pred:touch:")) for t in ts):
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
    world = wgmod.WorldGraph()
    drives = Drives()
    ctx = type("Ctx", (), {})()   # minimal context object
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
            print(f"Loaded {args.load} (saved_at={blob.get('saved_at','?')})")
            print("A previously saved simulation session is being continued here.\n")
            new_world  = wgmod.WorldGraph.from_dict(blob.get("world", {}))
            new_drives = Drives.from_dict(blob.get("drives", {}))
            skills_from_dict(blob.get("skills", {}))
            world, drives = new_world, new_drives
            loaded_ok = True
            loaded_src = args.load
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
        profile = choose_profile(ctx)
        name = profile["name"]
        sigma, jump, k = profile["ctx_sigma"], profile["ctx_jump"], profile["winners_k"]
        ctx.sigma, ctx.jump = sigma, jump
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})\n")
        POLICY_RT.refresh_loaded(ctx)        
    _io_banner(args, loaded_src, loaded_ok)

    # HAL instantiation
    ctx.hal  = None
    ctx.body = "(none)"
    if getattr(args, "hal", False):
        hal = HAL(args.body)
        ctx.hal  = hal  #store hal on ctx for that other primitives can see it
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
            rc = run_preflight_full(args)
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
                    print(fired)
            loop_helper(args.autosave, world, drives)

        elif choice == "12":
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
            export_snapshot(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT)
            loop_helper(args.autosave, world, drives)

        elif choice == "17":
            print(snapshot_text(world, drives=drives, ctx=ctx, policy_rt=POLICY_RT))
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
        print("CCA8 Components:")
        print(f"  - cca8_run.py v{__version__} ({os.path.abspath(__file__)})")
        print(f"  - cca8_world_graph v... ({getattr(wgmod, '__file__', 'cca8_world_graph.py')})")
        print(f"  - cca8_column   v... (cca8_column.py)")
        print(f"  - cca8_features      v... (cca8_features.py)")
        print(f"  - cca8_temporal   v... (cca8_temporal.py)")
        try:
            from cca8_controller import PRIMITIVES
            print(f"  - cca8_controller v... (cca8_controller.py) [primitives: {len(PRIMITIVES)}]")
        except Exception:
            print(f"  - cca8_controller v...(cca8_controller.py)")
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
