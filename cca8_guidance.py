#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 architecture guidance and new-user terminal tour.

Purpose
-------
This module owns terminal guidance whose primary job is to explain the CCA8
architecture: the map-first architecture overview, the bindings/policies help
pane, and the six-step new-user tour.
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
import os
import sys
from dataclasses import dataclass
from typing import Any, Callable, Optional

from cca8_features import time_attrs_from_ctx

__version__ = "0.4.0"

__all__ = [
    "ArchitectureMenuRuntimeV1",
    "TutorialRuntime",
    "architecture_explanation_menu_v1",
    "architecture_overview_text_v1",
    "print_architecture_overview_v1",
    "open_readme_compendium_v1",
    "print_tagging_and_policies_help",
    "readme_compendium_path_v1",
    "run_new_user_tour",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class ArchitectureMenuRuntimeV1:  # pylint: disable=too-few-public-methods
    """Runner-owned presentation callbacks for Main Menu #3.

    The callback bundle avoids importing :mod:`cca8_run` and preserves the
    runner's historical monkeypatch seams for the overview and technical
    primer. ``readme_path`` is resolved beside the runner before the menu opens.
    """

    overview_printer: Callable[[Any], None]
    tagging_printer: Callable[[Any], None]
    readme_path: str
    divider: str


@dataclass(frozen=True, slots=True)
class TutorialRuntime:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Runner-owned operations needed by the interactive new-user tour."""

    snapshot_text: Callable[..., str]
    sorted_bids: Callable[[Any], list[str]]
    engrams_on_binding: Callable[[Any, str], list[str]]
    binding_engrams: Callable[[Any, str], Any]
    action_center_step: Callable[[Any, Any, Any], Any]


def readme_compendium_path_v1(runner_file: str) -> str:
    """Return the README path colocated with the supplied runner file."""
    return os.path.join(os.path.dirname(os.path.abspath(runner_file)), "README.md")


def open_readme_compendium_v1(path: str) -> None:
    """Open the README/compendium in the platform default viewer when possible."""
    print(f"System documentation: {path}")
    print()
    if not os.path.exists(path):
        print(f"README.md was not found next to cca8_run.py at: {path}")
        print("Please restore/copy README.md beside cca8_run.py and try again.")
        return

    try:
        if sys.platform.startswith("win"):
            os.startfile(path)  # type: ignore[attr-defined]
        elif sys.platform == "darwin":
            os.system(f'open "{path}"')
        else:
            os.system(f'xdg-open "{path}"')
        print("Opened the README.md/compendium in your default viewer.")
        print()
        print(
            "The large README may take a few seconds to load. If no viewer opens, please open the file manually "
            "in your editor or Markdown viewer."
        )
    except Exception as exc:
        print(f"[warn] Could not open automatically: {exc}")
        print("Please open the file manually in your editor.")


def architecture_explanation_menu_v1(
    policy_rt: Any,
    runtime: ArchitectureMenuRuntimeV1,
) -> None:
    """Display architecture explanation, documentation, and primer choices."""
    print("Selection: Explanation of the Architecture\n")
    print("Architecture explanation options:")
    print("  1) Concise map-first architecture overview")
    print("  2) Open the full README/compendium system documentation")
    print("  3) Technical primer: bindings, tags, edges, drives, and primitives")
    print("  [Enter] Return to Main Menu")

    try:
        pick = input("Choose: ").strip()
    except (EOFError, KeyboardInterrupt):
        print()
        return
    except Exception:
        pick = ""

    if pick == "1":
        print(runtime.divider)
        print()
        runtime.overview_printer(policy_rt)
        return
    if pick == "2":
        open_readme_compendium_v1(runtime.readme_path)
        return
    if pick == "3":
        print("Selection: Technical Architecture Primer")
        print(runtime.divider)
        runtime.tagging_printer(policy_rt)
        return

    print("(cancelled)")


def architecture_overview_text_v1() -> str:
    """Return the concise terminal explanation of the current CCA8 architecture.

    The overview deliberately separates the mature map-first target from the
    mixed-source migration checkpoint that currently runs. It is short enough
    for an interactive terminal but preserves the governing distinctions among
    evidence, protected safety, the operative WNM, long-term memory, primitive
    selection, same-cycle output, and later outcome evidence.
    """
    return """
CCA8 ARCHITECTURE OVERVIEW
==========================

CCA8 is a recurrent, embodied, map-first cognitive architecture inspired by a
mountain-goat-level mammalian brain. Its central cognitive representation is a
Navigation Map (NavMap), not a detached table of symbolic state variables.

The target information path is:

    external world / body
        -> agent-visible sensory evidence
        -> evidence and Local NavMaps + bounded temporal processing
        -> protected BodyMap safety path
        -> sparse WorldGraph memory activation
        -> rich NavMaps reinstated from Columns
        -> alignment, comparison, and structured residuals
        -> ONE operative Working Navigation Map (WNM) + bounded ready set
        -> Policy / Primitive selection and arbitration
        -> selected primitive operates on the operative WNM
        -> Action_n, feedback, WNM transition, retrieval request, or NO_ACTION
        -> Action_n is dispatched before CognitiveCycle_n closes
        -> Observation_(n+1) enters cognition in the next cycle or later

Key architectural roles
-----------------------

  Navigation Map / NavMap
      A bounded, addressable, spatially organized and relationally linked
      representation with an explicit frame, scale, provenance, support, and
      uncertainty. Stable environmental maps are allocentric-biased; local
      sensory, body, object, and action maps may use other explicit frames.

  Operative WNM
      Exactly one NavMap has detailed accepted-current cognitive authority at a
      time. Ready, expected, retrieved, inferred, and imagined maps may affect
      processing but are not co-equal present worlds.

  BodyMap
      A protected fast body and near-space safety path. It may veto unsafe
      action and remains independently protective while ordinary cognition
      migrates toward WNM-derived readouts.

  WorldGraph
      The intended sparse associative, episodic, action, and retrieval index.
      It helps answer "where should memory look?" It is not the complete world
      model or automatic current truth. Legacy symbolic content remains during
      migration and is subject to audit, demotion, derivation, or retirement.

  Columns
      The rich durable store for NavMaps, prototypes, trajectories,
      transformations, and other engrams. Retrieved content remains a candidate
      until aligned, compared with current evidence, and explicitly accepted.

  Sequential/Error and live dynamics
      Bounded histories are compressed into motion, rate, duration, phase,
      contact, support, slip, progress, and uncertainty. CCA8 does not preserve
      a complete movie of successive NavMaps.

  Policy / Primitive system
      Several primitives may be applicable. Protected safety and arbitration
      select one current working primitive. The primitive then operates on the
      WNM and may produce action, expectation, feedback, retrieval, or a map
      transition. Detailed motor trajectories remain below CCA8 in lower
      controllers or the HAL.

Authority rules
---------------

  * OBSERVED, MAINTAINED, EXPECTED, RETRIEVED, INFERRED, IMAGINED, and
    ACCEPTED-CURRENT content remain distinguishable.
  * Reliable current evidence defeats unsupported expectation or memory.
  * UNKNOWN and DEFER are valid outcomes.
  * A command does not prove success; later sensory evidence supplies the
    ordinary outcome signal.
  * Diagnostic traces observe the architecture but are not cognitive memory.

Current implementation versus target
------------------------------------

CCA8 is deliberately migrating one bounded domain at a time. StandUp and
FollowMom already use bounded map-native applicability authority, and feeding,
terrain, temporal, WNM-transition, and Column-memory paths are implemented.
Other consumers still use BodyMap, WorkingMap/MapSurface, SurfaceGrid,
WorldGraph history, drives, and compatibility bridges. The architecture audit
must therefore identify canonical maps, derived projections, protected fast
paths, temporary scaffolding, and structures ready for retirement.

Use Main Menu #1 to watch cognition run and Main Menu #2 to inspect the same
cycle with the Cognitive Storage Oscilloscope / System Inspector.
""".strip()


def print_architecture_overview_v1(policy_rt: Any = None) -> None:
    """Print the concise architecture overview and the currently loaded primitives."""
    print(architecture_overview_text_v1())

    try:
        names = policy_rt.list_loaded_names() if policy_rt is not None else []
    except Exception:
        names = []

    if names:
        print("\nBehavioral primitives currently loaded for this profile:")
        for name in names:
            print(f"  - {name}")
    print()


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
  • NavMaps / operative WNM → rich map-like cognition; exactly one accepted-current map has operative authority.
  • WorldGraph  → sparse episode/retrieval/index structure; historical tags are not automatic current truth.
  • Columns     → rich durable NavMaps, prototypes, trajectories, transformations, and other engrams.
  • BodyMap     → protected fast body/near-space safety path; it can constrain action independently.
  • Drives      → numeric interoception state (hunger/fatigue/etc.); may emit cue:drive:* threshold events.
  • Engram pointers → lightweight WorldGraph references to rich Column payloads.

Memory types (rough mapping)
  • Current cognition      → one operative WNM plus protected evidence/expected/retrieved layers and ready maps.
  • Rich long-term content → versioned NavMaps and engrams in Columns.
  • Sparse episodic index  → WorldGraph bindings, actions, anchors, keyframes, and Column pointers.
  • Procedural             → behavioral primitives plus learned competence/outcome telemetry.

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
               (1) snapshot, (2) timekeeping status, (3) capture a small
               engram, (4) show the binding pointer (b#), (5) inspect that
               engram, (6) list/search engrams.
Hints: Press Enter to accept defaults. Type Q to exit.

**The tutorial portion of the tour is still under construction. All components shown here are available
    as individual menu selections also -- see those and the README.md file for more details.**

[tour] 1/6 — Baseline snapshot
Shows CTX plus explicit runtime counters. Next: timekeeping status.
  • cognitive_cycles orders complete sensory-input → processing → output cycles.
  • controller_steps counts Action Center invocations, including manual flows.
  • autonomic_ticks counts physiology/IO heartbeats independently.
  • age_days is developmental state, not a cycle clock.

[tour] 2/6 — Timekeeping status
Prints the explicit counters without mutating any of them.
Next: capture a tiny engram.
  • Environment step/time belong to EnvState, not Ctx.
  • created_at/saved_at are wall-clock provenance only.
  • Motion trends, freshness, duration, and phase remain source-linked in their owning subsystems.

[tour] 3/6 — Capture a tiny engram
Adds a memory item with time/provenance; visible in Snapshot. Next: show b#.
  • capture_scene creates a binding (cue/pred) and a Column engram.
  • The binding gets a pointer slot (e.g., column01 → EID).
  • Time attrs identify cognitive_cycle, controller_step, autonomic_tick, and age_days.
  • binding.meta['policy'] records provenance when created by a policy.

[tour] 4/6 — Show binding pointer (b#)
Displays the new binding id and its attach target. Next: inspect that engram.
  • A binding is the symbolic “memory link”; engram is the rich payload.
  • The pointer (b#.engrams['slot']=EID) glues symbol ↔ rich memory.
  • Attaching near NOW/LATEST keeps episodes readable for planning.
  • Follow the pointer via Snapshot or “Inspect engram by id.”

[tour] 5/6 — Inspect engram
Shows engram fields (channel, token, attrs). Next: list/search engrams.
  • meta → attrs contains explicit, directly interpretable runtime counters.
  • payload → kind/shape/bytes (varies by Column implementation).
  • Use this to verify data shape and provenance after capture.
  • Engrams persist across saves; pointers can be re-attached later.


[tour] 6/6 — List/search engrams
Lists and filters engrams by token/family.
  • Deduped EIDs with source binding (b#) for quick auditing.
  • Search by name substring and/or cognitive-cycle number.
  • Useful to confirm capture cadence across cognitive cycles.
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

    # 2) Explicit timekeeping status (same signals as menu 26)
    print("\n[tour] 2/6 — Timekeeping status")
    try:
        print(f"  cognitive_cycles={int(getattr(ctx, 'cog_cycles', 0) or 0)}")
        print(f"  controller_steps={int(getattr(ctx, 'controller_steps', 0) or 0)}")
        print(f"  autonomic_ticks={int(getattr(ctx, 'ticks', 0) or 0)}")
        print(f"  age_days={float(getattr(ctx, 'age_days', 0.0) or 0.0):.4f}")
        print("  environment step/time are reported with EnvState observations")
        print("  wall-clock created_at/saved_at values are provenance only")
    except Exception as e:
        print(f"(tour) timekeeping error: {e}")
    if autosave_cb is not None:
        try: autosave_cb()
        except Exception: pass
    if _pause("2/6"):
        return

    # 3) Capture scene with explicit current counter values.
    print("\n[tour] 3/6 — Capture a small scene as a CUE engram")
    try:
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
                print(
                    "[bridge] time on engram: "
                    f"cognitive_cycle={tattrs.get('cognitive_cycle')} "
                    f"controller_step={tattrs.get('controller_step')} "
                    f"autonomic_tick={tattrs.get('autonomic_tick')} "
                    f"age_days={tattrs.get('age_days')}"
                )
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
                    print(
                        f"EID={_eid} src={_bid} name={name} "
                        f"cognitive_cycle={attrs.get('cognitive_cycle')} "
                        f"controller_step={attrs.get('controller_step')}"
                    )
                    found = True
        if not found:
            print("(no matches)")
    except Exception as e:
        print(f"(tour) search error: {e}")

    print("\n=== End of Quick Tour ===")
