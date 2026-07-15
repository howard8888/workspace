#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 explanatory help and new-user terminal tour.

Purpose
-------
This module owns terminal guidance whose primary job is to explain the CCA8
architecture: the bindings/policies help pane and the six-step new-user tour.
The tour receives runner-owned inspection callbacks through an explicit frozen
runtime bridge, so this module remains independent of :mod:`cca8_run`.
"""

from __future__ import annotations

# The tutorial deliberately mirrors the historical defensive, linear flow.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=line-too-long
# pylint: disable=multiple-statements
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements

import json
from dataclasses import dataclass
from typing import Any, Callable, Optional

from cca8_features import time_attrs_from_ctx

__version__ = "0.1.0"

__all__ = [
    "TutorialRuntime",
    "print_tagging_and_policies_help",
    "run_new_user_tour",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class TutorialRuntime:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-owned operations needed by the interactive new-user tour."""

    snapshot_text: Callable[..., str]
    hamming_hex64: Callable[[str, str], int]
    sorted_bids: Callable[[Any], list[str]]
    engrams_on_binding: Callable[[Any, str], list[str]]
    binding_engrams: Callable[[Any, str], Any]
    action_center_step: Callable[[Any, Any, Any], Any]

def print_tagging_and_policies_help(policy_rt=None) -> None:
    """Terminal help: bindings, edges, predicates, cues, anchors, provenance/engrams, and policies.
    """

    print("""

==================== Understanding Bindings, Edges, Predicates, Cues & Policies ====================

What is a Binding?
  • A small 'episode card' that binds together:
      - tags (symbols: predicates / actions / cues / anchors)
      - engrams (pointers to rich memory outside WorldGraph)
      - meta (provenance, timestamps, light notes)
      - edges (directed links from this binding)

  Structure (conceptual):
      { id:'bN', tags:[...], engrams:{...}, meta:{...}, edges:[{'to': 'bK', 'label':'then', 'meta':{...}}, ...] }

Tag Families (use these prefixes)
  • pred:*        → predicates (facts / goals you might plan TO)
      examples: pred:posture:standing, pred:posture:fallen, pred:nipple:latched, pred:milk:drinking,
                pred:proximity:mom:close, pred:proximity:shelter:near, pred:hazard:cliff:near

  • action:*      → actions (verbs; what the agent did or is doing)
      examples: action:push_up, action:extend_legs, action:orient_to_mom

  • cue:*         → evidence/context you NOTICE (policy triggers); not planner goals
      examples: cue:vision:silhouette:mom, cue:scent:milk, cue:sound:bleat:mom, cue:terrain:rocky
                cue:drive:hunger_high, cue:drive:fatigue_high

  • anchor:*      → orientation markers (e.g., anchor:NOW); also mapped in engine anchors {'NOW': 'b1'}

Drive thresholds (house style)
  • Canonical storage: numeric values live in the Drives object:
        drives.hunger, drives.fatigue, drives.warmth
  • Threshold flags are *derived* (e.g., hunger>=HUNGER_HIGH) and are optionally emitted as
    rising-edge *cues* to avoid clutter:
        cue:drive:hunger_high, cue:drive:fatigue_high
  • Only use pred:drive:* when you deliberately want a planner goal like "pred:drive:warm_enough".
    Otherwise treat thresholds as evidence (cue:drive:*).

Edges = Transitions
  • We treat edge labels as weak episode links (often just 'then').
  • Most semantics live in bindings (pred:* and action:*); edge labels are for readability and metrics.
  • Quantities about the transition live in edge.meta (e.g., meters, duration_s, created_by).
  • Planner behavior today: BFS/Dijkstra follow structure (node/edge graph), not label meaning.
  • Duplicate protection: the UI warns on exact duplicates of (src, label, dst)

Provenance & Engrams
  • Who created a binding?   binding.meta['policy'] = 'policy:<name>' (or meta.created_by for non-policy writes)
  • Who created an edge?     edge.meta['created_by'] = 'policy:<name>' (or similar)
  • Where is the rich data?  binding.engrams[...] → pointers (large payloads live outside WorldGraph)

Maps & Memory (where things live)
  • WorldGraph  → symbolic episode index (bindings/edges/tags); great for inspection + planning over pred:*.
  • BodyMap     → agent-centric working state used for gating (fast, “what do I believe right now?”).
  • Drives      → numeric interoception state (hunger/fatigue/etc.); may emit cue:drive:* threshold events.
  • Engrams     → pointers from bindings to richer payloads stored outside the graph (future: Column / disk store).

Memory types (rough mapping)
  • Declarative / semantic → stable pred:* summaries (small in WorldGraph; richer payloads via engrams / Column later).
  • Episodic               → sequences of bindings/edges anchored by NOW (plus engram payload pointers).
  • Procedural             → policies + any learned parameters/weights/skill stats used to select/execute actions.

Anchors
  • anchor:NOW exists; used as the start for planning; may have no pred:*
  • Other anchors (e.g., HERE, NOW_ORIGIN) are allowed; anchors are bindings with special meaning

Planner (BFS/Dijkstra) Basics
  • Goal test: reach a binding whose tags contain the target 'pred:<token>'
  • BFS → fewest hops (unweighted)
  • Dijkstra → lowest total edge weight; weights come from edge.meta keys in this order:
      'weight' → 'cost' → 'distance' → 'duration_s' (default 1.0 if none present)
  • Pretty paths show first pred:* (or id) as the node label and --label--> between nodes

Policies (Action Center overview)
  • Policies live in cca8_controller and expose:
      - dev_gate(ctx)               → availability by development stage/context
      - trigger(world, drives, ctx) → should we act now?
      - execute(world, ctx, drives) → writes bindings/edges; stamps provenance

  • Per controller step the Action Center:
      1) filters by dev_gate and safety overrides (e.g., fallen → recovery-only),
      2) evaluates triggers to form a candidate set,
      3) chooses ONE winner (drive-deficit heuristic; optional RL q soft tie-break),
      4) executes the winner and updates skill stats.
        (NOTE: "deficit" here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD) (amount ABOVE threshold, not a negative deficit).
        (Policies without a drive-urgency term score 0.00 and will tie-break by stable policy order (or RL tie-break, if enabled).

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
    print("  ✓ Use pred:* for facts/goals/events")
    print("  ✓ Use action:* for verbs (what the agent does)")
    print("  ✓ Use cue:* for evidence/conditions/triggers (including cue:drive:* threshold events)")
    print("  ✓ Put creator/time/notes in meta; put action measurements in edge.meta")
    print("  ✓ Allow anchor-only bindings (e.g., anchor:NOW)")
    print("  ✗ Don’t store large data in tags; put it in engrams")

    print("\nExamples")
    print("  pred:posture:fallen --then--> action:push_up --then--> action:extend_legs --then--> pred:posture:standing")
    print("  pred:posture:standing --then--> action:orient_to_mom --then--> pred:seeking_mom --then--> pred:nipple:latched")

    print("\n(See README.md → Tagging Standard for more information.)\n")

def run_new_user_tour(
    world: Any,
    drives: Any,
    ctx: Any,
    policy_rt: Any,
    autosave_cb: Optional[Callable[[], None]] = None,
    *,
    runtime: TutorialRuntime,
) -> None:
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

    bid: Any = None
    eid: Any = None

    # 1) Baseline snapshot
    print("\n[tour] 1/6 — Baseline snapshot")
    try:
        print(runtime.snapshot_text(world, drives=drives, ctx=ctx, policy_rt=policy_rt))
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
                h = runtime.hamming_hex64(vhash, lbvh)
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
            eng = runtime.binding_engrams(world, bid) if isinstance(bid, str) else None
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
            res = runtime.action_center_step(world, ctx, drives)
            if isinstance(res, dict) and res.get("status") != "noop":
                policy_name = res.get("policy")
                execution_status = res.get("status")
                reward = res.get("reward")
                binding = res.get("binding")
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                print(f"[executed] {policy_name} ({execution_status}, reward={rtxt}) binding={binding}")
                gate = next((item for item in policy_rt.loaded if item.name == policy_name), None)
                explain_fn: Optional[Callable[[Any, Any, Any], str]] = getattr(gate, "explain", None) if gate else None
                if explain_fn is not None:
                    try:
                        why = explain_fn(world, drives, ctx)
                        print(f"[why {policy_name}] {why}")
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
        eng = runtime.binding_engrams(world, bid) if isinstance(bid, str) else None
        print(f"Binding {bid} → Engrams:", eng if eng else "(none)")
        rec = world.get_engram(engram_id=eid)
        meta = rec.get("meta", {}) if isinstance(rec, dict) else {}
        print("Engram meta:", json.dumps(meta, indent=2))
        payload = rec.get("payload") if isinstance(rec, dict) else None
        payload_meta = getattr(payload, "meta", None)
        if callable(payload_meta):
            pmeta = payload_meta()
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
        for _bid in runtime.sorted_bids(world):
            for _eid in runtime.engrams_on_binding(world, _bid):
                if _eid in seen:
                    continue
                seen.add(_eid); any_found = True
                rec = None
                try: rec = world.get_engram(engram_id=_eid)
                except Exception: rec = None
                shape = dtype = None
                if isinstance(rec, dict):
                    pl = rec.get("payload")
                    payload_meta = getattr(pl, "meta", None)
                    if callable(payload_meta):
                        try:
                            pm = payload_meta()
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
        for _bid in runtime.sorted_bids(world):
            for _eid in runtime.engrams_on_binding(world, _bid):
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
