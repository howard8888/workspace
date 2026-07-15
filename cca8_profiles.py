#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""CCA8 startup profile narratives, scaffolds, and interactive selection.

Purpose
-------
This module owns the profile-selection text and the experimental profile
scaffolds that were historically embedded in :mod:`cca8_run`.  The implemented
runtime still uses the Mountain Goat defaults; the other profiles explain the
planned architecture and run bounded, deterministic dry-run demonstrations.

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`.  It depends on stable WorldGraph and
controller APIs.  The runner keeps its historical profile names through aliases
and small wrappers so existing imports and monkeypatch-based tests continue to
work.
"""

from __future__ import annotations

# The profile demonstrations intentionally favor readable, linear scaffolding.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=import-outside-toplevel
# pylint: disable=line-too-long
# pylint: disable=multiple-statements
# pylint: disable=no-member
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements

import copy
import os
import random
import sys
import webbrowser
from collections import Counter, defaultdict
from dataclasses import dataclass
from typing import Any, Callable, DefaultDict

import cca8_world_graph
from cca8_controller import Drives, action_center_step

__version__ = "0.1.0"

ProfileTuple = tuple[str, float, float, int]

__all__ = [
    "ProfileOperations",
    "ProfileRuntime",
    "choose_profile",
    "profile_rcos_api",
    "profile_chimpanzee",
    "profile_human",
    "profile_human_multi_brains",
    "profile_society_multi_agents",
    "profile_multi_brains_adv_planning",
    "profile_superhuman",
    "open_readme_tutorial",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class ProfileRuntime:  # pylint: disable=too-few-public-methods
    """Stable operations used by the bounded profile demonstrations."""

    world_factory: Callable[[], Any]
    world_from_dict: Callable[[dict[str, Any]], Any]
    drives_factory: Callable[[], Any]
    action_center_step: Callable[[Any, Any, Any], Any]


@dataclass(frozen=True, slots=True)
class ProfileOperations:  # pylint: disable=too-few-public-methods,too-many-instance-attributes
    """Profile callbacks used by the interactive profile chooser.

    Passing the callbacks explicitly keeps profile selection independent of the
    runner while allowing ``cca8_run`` to preserve its historical call-time
    monkeypatch seams.
    """

    open_tutorial: Callable[[], None]
    chimpanzee: Callable[[Any], ProfileTuple]
    human: Callable[[Any], ProfileTuple]
    human_multi_brains: Callable[[Any, Any], ProfileTuple]
    society_multi_agents: Callable[[Any], ProfileTuple]
    multi_brains_adv_planning: Callable[[Any], ProfileTuple]
    superhuman: Callable[[Any], ProfileTuple]


def default_profile_runtime() -> ProfileRuntime:
    """Return the normal profile-demonstration dependency bundle."""
    return ProfileRuntime(
        world_factory=cca8_world_graph.WorldGraph,
        world_from_dict=cca8_world_graph.WorldGraph.from_dict,
        drives_factory=Drives,
        action_center_step=action_center_step,
    )

def _goat_defaults():
    """Return the Mountain Goat default profile tuple: (name, sigma, jump, winners_k)."""
    return ("Mountain Goat", 0.015, 0.2, 2)

def _print_goat_fallback():
    """Explain that the chosen profile is not implemented and we fall back to Mountain Goat."""
    print("\n\n======================\n\nAlthough scaffolding is in place, currently this evolutionary-like configuration is not available. "
          "\nProfile will be set to mountain goat-like brain simulation.\n\n======================\n\n")

def profile_rcos_api(_ctx) -> tuple[str, float, float, int]:
    """Explain the planned RCOS API configuration; fall back to Mountain Goat defaults."""
    print(r"""
Robotic Cognitive Operating System (RCOS)

CCA8 can be considered in two ways:

1. As a developmental cognitive architecture inspired by early mammalian brains.

OR

2. As the kernel of a Robotic Cognitive Operating System (RCOS): a layer that manages embodiment,
   behavior, and cognition on top of low-level robot firmware, real-time operating systems, and
   middleware such as ROS 2.

The RCOS is an integration architecture: not "LLM + motors," but a structured system that unifies
cognition with embodied control.

The real world is not merely a larger simulation. It is slow, noisy, expensive, partially observable,
physically risky, and not perfectly repeatable. A robot may encounter shadows, sensor noise, slip,
friction changes, unexpected contact, latency, battery limits, actuator faults, object deformation,
and human interruption.

Therefore, a CCA8 RCOS should not allow a high-level planner, LLM, VLA, or learned world model to
control the body directly without a supervisory layer. CCA8's role is to manage the boundary between
imagined futures and real consequences.

Although scaffolding is in place, an RCOS API configuration is not available.
    """)
    _print_goat_fallback()
    return _goat_defaults()

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

def profile_human_multi_brains(
    _ctx: Any,
    world: Any,
    *,
    runtime: ProfileRuntime | None = None,
) -> ProfileTuple:
    """Dry-run multi-brain sandbox (no writes); print trace; fall back to Mountain Goat defaults."""
    runtime = runtime or default_profile_runtime()

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
        random.seed(42)  # deterministic demo

        print("[scaffold] Spawning 5 parallel 'brains' (sandbox worlds)...")
        # Thick clones for now; later this could be a thin overlay (base + delta)
        base_dict = world.to_dict()
        brains = []
        for i in range(5):
            try:
                clone = runtime.world_from_dict(copy.deepcopy(base_dict))
            except Exception:
                # Fallback: construct an empty world (still fine for a stub)
                clone = runtime.world_factory()
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
        counts = Counter(r for r, _, _ in proposals)
        confidence_rows: DefaultDict[str, list[float]] = defaultdict(list)
        max_conf: DefaultDict[str, float] = defaultdict(float)
        for response, confidence, _ in proposals:
            confidence_rows[response].append(confidence)
            if confidence > max_conf[response]:
                max_conf[response] = confidence
        avg_conf = {
            response: sum(values) / len(values)
            for response, values in confidence_rows.items()
        }

        popular = max(counts.items(), key=lambda item: (item[1], avg_conf[item[0]], max_conf[item[0]]))
        winning_resp = popular[0]
        print(
            f"[scaffold] Winner by popularity: {winning_resp} "
            f"(votes={counts[winning_resp]}, avg_conf={avg_conf[winning_resp]:.2f}, "
            f"max_conf={max_conf[winning_resp]:.2f})"
        )

        print("[scaffold] (No changes committed—this is a dry run only.)\n")
    except Exception as e:
        print(f"[scaffold] Note: sandbox demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def profile_society_multi_agents(
    _ctx: Any,
    *,
    runtime: ProfileRuntime | None = None,
) -> ProfileTuple:
    """Dry-run 3-agent society (no writes); print trace; fall back to Mountain Goat defaults."""
    runtime = runtime or default_profile_runtime()

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
            w = runtime.world_factory()
            w.ensure_anchor("NOW")
            d = runtime.drives_factory()
            agents.append(_Agent(name=f"A{i+1}", world=w, drives=d))

        print(f"[scaffold] Created {len(agents)} agents: {', '.join(a.name for a in agents)}")

        # One tick: each agent runs action_center_step (dry outcome)
        for a in agents:
            try:
                res = runtime.action_center_step(a.world, _ctx, a.drives)
                print(f"[scaffold] {a.name}: Action Center → {res}")
            except Exception as e:
                print(f"[scaffold] {a.name}: controller error: {e}")

        # Simple broadcast message: A1 'bleats', A2 receives a cue (sound:bleat:mom)
        try:
            print("[scaffold] A1 broadcasts 'sound:bleat:mom' → A2")
            bid = agents[1].world.add_cue("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            #bid = agents[1].world.add_predicate("sound:bleat:mom", attach="now", meta={"sender": agents[0].name})
            print(f"[scaffold] A2 received cue as binding {bid}; running one controller step on A2...")
            res2 = runtime.action_center_step(agents[1].world, _ctx, agents[1].drives)
            print(f"[scaffold] A2: Action Center → {res2}")
        except Exception as e:
            print(f"[scaffold] message/cue demo note: {e}")

        print("[scaffold] (End of society dry-run; no snapshots written.)\n")
    except Exception as e:
        print(f"[scaffold] Society demo encountered a recoverable issue: {e}\n")

    _print_goat_fallback()
    return _goat_defaults()

def profile_multi_brains_adv_planning(_ctx) -> ProfileTuple:
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
        def _better(
            current: tuple[list[str], float] | None,
            candidate: tuple[list[str], float],
        ) -> bool:
            if current is None:
                return True
            current_plan, current_score = current
            candidate_plan, candidate_score = candidate
            return (candidate_score > current_score) or (
                candidate_score == current_score
                and (
                    len(candidate_plan) < len(current_plan)
                    or (len(candidate_plan) == len(current_plan) and tuple(candidate_plan) < tuple(current_plan))
                )
            )

        brain_summaries: list[tuple[int, list[str], float, float]] = []

        for bi in range(1, brain_count + 1):
            best: tuple[list[str], float] | None = None
            sum_scores = 0.0
            for _ in range(procs_per_brain):
                plan  = [random.choice(actions) for _ in range(horizon)]
                score = sum(reward.get(a, 0.0) for a in plan) - cost_per_step * len(plan)
                sum_scores += score
                if _better(best, (plan, score)):
                    best = (plan, score)
            avg = sum_scores / procs_per_brain
            if best is None:
                continue
            best_plan, best_score = best
            brain_summaries.append((bi, best_plan, best_score, avg))
            print(
                f"[scaffold] Brain#{bi:>2}: best={best_plan}  best_score={best_score:.3f}  "
                f"avg_score={avg:.3f}  (processors={procs_per_brain})"
            )

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

def profile_superhuman(_ctx) -> ProfileTuple:
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

def open_readme_tutorial() -> None:
    """Open README.md in the default viewer, then return.
    This may or may not have the same behavior as main-menu 'T'
    (it does at time of writing but future versions may diverge
    """
    # pylint: disable=import-outside-toplevel
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

_open_readme_tutorial = open_readme_tutorial

def default_profile_operations() -> ProfileOperations:
    """Return chooser callbacks backed by this module's profile functions."""
    runtime = default_profile_runtime()
    return ProfileOperations(
        open_tutorial=open_readme_tutorial,
        chimpanzee=profile_chimpanzee,
        human=profile_human,
        human_multi_brains=lambda ctx, world: profile_human_multi_brains(ctx, world, runtime=runtime),
        society_multi_agents=lambda ctx: profile_society_multi_agents(ctx, runtime=runtime),
        multi_brains_adv_planning=profile_multi_brains_adv_planning,
        superhuman=profile_superhuman,
    )

def choose_profile(
    ctx: Any,
    world: Any,
    *,
    operations: ProfileOperations | None = None,
) -> dict[str, Any]:
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
    operations = operations or default_profile_operations()
    goat = _goat_defaults()

    while True:
        try:
            choice = input("Please make a choice [1–7 or T | Enter = Mountain Goat]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled selection.... will exit program....")
            sys.exit(0)

        # Fast path: Enter accepts default
        if choice == "":
            name, sigma, jump, k = goat
            break

        # Tutorial: open README, then re-prompt
        if choice.lower() == "t":
            operations.open_tutorial()
            continue  # re-show prompt

        # Numeric choices
        if choice == "1":
            name, sigma, jump, k = goat
            break
        if choice == "2":
            name, sigma, jump, k = operations.chimpanzee(ctx)
            break
        if choice == "3":
            name, sigma, jump, k = operations.human(ctx)
            break
        if choice == "4":
            name, sigma, jump, k = operations.human_multi_brains(ctx, world)
            break
        if choice == "5":
            name, sigma, jump, k = operations.society_multi_agents(ctx)
            break
        if choice == "6":
            name, sigma, jump, k = operations.multi_brains_adv_planning(ctx)
            break
        if choice == "7":
            name, sigma, jump, k = operations.superhuman(ctx)
            break

        # Anything else: prompt again (no silent default)
        print(f"The selection {choice!r} is not valid. Please enter 1–7, 'T', or press Enter for Mountain Goat.\n")

    ctx.profile = name
    return {"name": name, "ctx_sigma": sigma, "ctx_jump": jump, "winners_k": k}
