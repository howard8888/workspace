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
# pylint: disable=too-many-lines
#   This module intentionally stores long, user-visible future-profile narratives.

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

__version__ = "0.2.2"

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
    "profile_cca11_governed_cognitive_plurality",
    "profile_cca12_governed_pod",
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
    # Optional defaults preserve compatibility with callers that construct the
    # pre-CCA11 ProfileOperations bundle directly.  The runner supplies both.
    cca11: Callable[[Any], ProfileTuple] | None = None
    cca12: Callable[[Any], ProfileTuple] | None = None


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


_PROFILE_MENU_PAUSE_ACTIVE = False
_PROFILE_DIVIDER = "=" * 78


def _profile_heading(title: str) -> None:
    """Print one profile heading and pause only during interactive Profile Menu selection.

    Direct profile calls such as ``--profile chimp`` remain non-interactive.  The
    pause is enabled transiently by :func:`choose_profile` only for numbered
    Profile Menu selections 2 through 9.
    """
    print()
    print(_PROFILE_DIVIDER)
    print(title)
    print(_PROFILE_DIVIDER)
    print()
    if _PROFILE_MENU_PAUSE_ACTIVE:
        input("Please ENTER to continue...")
        print()


def _print_goat_intro() -> None:
    """Print the concise operational-baseline description for Profile Menu choice 1."""
    _profile_heading("MOUNTAIN GOAT-LIKE BRAIN SIMULATION")
    print(
        "This is the operational CCA8 baseline: a goat-level mammalian cognitive architecture.\n"
        "Current development is progressively converting its cognition to NavMap/WNM-centered operation.\n"
    )


def _run_interactive_profile_choice(callback: Callable[..., ProfileTuple], *args: Any) -> ProfileTuple:
    """Run one numbered research-profile callback with the Profile Menu pause enabled."""
    global _PROFILE_MENU_PAUSE_ACTIVE  # pylint: disable=global-statement

    previous = _PROFILE_MENU_PAUSE_ACTIVE
    _PROFILE_MENU_PAUSE_ACTIVE = True
    try:
        return callback(*args)
    finally:
        _PROFILE_MENU_PAUSE_ACTIVE = previous


def _print_goat_fallback():
    """Explain that a research profile is not operational and use the safe baseline."""
    print()
    print(_PROFILE_DIVIDER)
    print("PROFILE STATUS")
    print(_PROFILE_DIVIDER)
    print()
    print(
        "Although narrative or dry-run scaffolding is in place, this research profile is not yet "
        "an operational cognitive architecture."
    )
    print()
    print("PROFILE WILL BE SET TO MOUNTAIN GOAT-LIKE BRAIN SIMULATION")
    print()
    print(_PROFILE_DIVIDER)
    print()


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
    _profile_heading("Chimpanzee-like brain simulation")
    print('''
As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
The chimpanzee has the main structures of the mountain goat brain (some differences nonetheless in these
    "similar" structures) but enhanced feedback pathways allowing better causal reasoning. Also better
    combinatorial language.\n
    ''')
    _print_goat_fallback()
    return _goat_defaults()

def profile_human(_ctx) -> tuple[str, float, float, int]:
    """Print a narrative about the human profile; fall back to Mountain Goat defaults."""
    _profile_heading("Human-like brain simulation")
    print('''
As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
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
    _profile_heading("Human-like one-agent multiple-brains simulation")
    print('''
As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
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

    _profile_heading("Human-like one-brain simulation × multiple-agents society")
    print('''
As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
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
    _profile_heading("Human-like one-agent multiple-brains simulation with combinatorial planning")
    print('''
As per the papers on the Causal Cognitive Architecture, the mountain goat has pre-causal reasoning.
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
    _profile_heading("Super-human-like machine simulation")
    print('''
Features scaffolding for an ASI-grade architecture:
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


CCA11_PROFILE_NARRATIVE = r"""
Research status
---------------
CCA11 is a future architectural research profile.  This selection records the
intended design direction.  It does not claim that the present CCA8 software
already implements CCA11.

CCA11 should be built only after the goat-level CCA8, primate-like CCA9, and
human-like CCA10 mechanisms are sufficiently explicit and testable.  The
present runner therefore prints the research design and then returns safely to
the operational Mountain Goat baseline.


Core idea
---------
CCA11 is one coherent cognitive agent containing several heterogeneous ways of
thinking.

It is not merely a faster CCA10.

It is not simply a larger language model.

It is not a committee of identical programs that votes until one answer wins.

It is not several independent selves competing for control of one body.

CCA11 combines plural thought with governed commitment:

    CCA11
        = one persistent self
        + many cognitive methods
        + several branch-local workspaces
        + explicit provenance
        + one governed commitment structure
        + one controlled external-action path

The superhuman feature is not merely that many voices exist.  It is that the
architecture knows when to recruit them, how to keep their reasoning paths
meaningfully independent, how to preserve disagreement, how to test claims,
and which conclusion is permitted to alter current state or control action.


What remains unified
--------------------
CCA11 preserves:

  - one persistent identity and autobiographical continuity
  - one human-authorized mission and protected goal hierarchy
  - one protected observation/evidence layer
  - one committed Accepted Working Navigation Map for present external control
  - one governed persistent-memory system
  - one provenance and audit system
  - one controlled pathway for consequential external action

CCA11 may operate several active, imagined, or counterfactual Working Navigation
Maps in parallel.  Each branch can be locally authoritative inside its own
simulation or reasoning process.

Branch-local authority is not present-state authority.

A simulated branch may say, "Within this hypothesis, the bridge is unsafe."
That does not make the real bridge unsafe.  Only an explicit acceptance and
commitment operation may revise the map that governs the embodied agent.


Candidate cognitive processes
-----------------------------
A future CCA11 may recruit processes such as:

  - NavMap predictive processing
      Compare expected and observed maps, preserve residuals, and propose
      revisions to the accepted map.

  - causal intervention reasoning
      Ask what would follow if a variable, relation, or action were deliberately
      changed rather than merely observed.

  - analogical reasoning
      Align relational structures across maps and transfer a candidate
      transformation while preserving the differences between the cases.

  - symbolic planning
      Search explicit task, constraint, route, and action structures.

  - probabilistic forecasting
      Estimate bounded and calibrated outcome probabilities when the event
      space, model, and calibration are meaningful.

  - episodic and autobiographical retrieval
      Locate relevant prior maps and trajectories without treating remembered
      content as present truth.

  - semantic or language-based reasoning
      Use an optional LLM or other language system to interpret, summarize,
      explain, or suggest high-level possibilities.

  - scientific hypothesis generation
      Construct competing explanations and propose observations or experiments
      that could distinguish them.

  - skeptical or red-team processing
      Search for counterexamples, hidden assumptions, correlated errors,
      failure modes, and alternative interpretations.

  - authority and safety checking
      Determine whether a proposed state revision or action is permitted,
      adequately supported, reversible, and within delegated human authority.

  - metacognitive allocation
      Decide which processes should be recruited, how much computation they
      receive, whether independent first-pass reasoning is required, and when
      deliberation should stop.

These are not necessarily equal modules.  Some may be congenital safety
mechanisms, some learned NavMap operations, some external tools, and some large
model-based advisers.  Their outputs must use a common proposal contract even
when their internal computations differ.


When the cognitive council is recruited
---------------------------------------
The complete council should not run on every cognitive cycle.  Routine behavior
should remain fast and comparatively inexpensive.

Possible recruitment triggers include:

  - a large or safety-relevant predictive residual
  - disagreement among candidate NavMaps or reasoning processes
  - an explicit UNKNOWN or none-of-the-above result
  - substantial uncertainty or an inadequate candidate set
  - repeated policy failure
  - evidence of long-horizon task drift
  - an unfamiliar situation
  - a high-consequence or poorly reversible decision
  - possible corruption of current state
  - conflict among goals, permissions, or sources of authority
  - a request for independent verification or explanation

This extends the early CCA System-2 direction:

    large surprise or consequential uncertainty
        -> recruit additional processing
        -> preserve alternatives
        -> test assumptions and predictions
        -> repair or revise the accepted map
        -> act only after governed commitment


The proposal interface
----------------------
A cognitive process must not directly rewrite the Accepted Working Navigation
Map merely because it produced a fluent or confident answer.

Instead, it submits a structured proposal to a protected Scratch, Creative,
ProposalMap, or counterfactual workspace.

A proposal should record at least:

  - proposal identifier
  - proposing process and process version
  - question or problem being addressed
  - input map revision and evidence references
  - claim, hypothesis, plan, or proposed map transformation
  - provenance
  - assumptions
  - predicted observations or outcomes
  - counterevidence and known failure conditions
  - support or confidence type
  - calibration information when a numerical probability is claimed
  - recommended action, probe, or abstention
  - reversibility and estimated cost
  - safety and authority implications
  - unresolved objections
  - time and computational resources used

This interface lets a symbolic planner, NavMap process, causal simulator, LLM,
and statistical forecaster communicate without pretending that their internal
representations or numeric scores are identical.


Protected architectural surfaces
--------------------------------
Individual cognitive processes may propose changes, but they must not silently
modify:

  - observed evidence
  - the committed Accepted Working Navigation Map
  - persistent episodic or semantic memory
  - the mission charter
  - protected goals
  - safety constraints
  - human authority
  - external actuators

A separate acceptance and commitment mechanism decides whether a proposal is:

  - rejected
  - retained as an unresolved alternative
  - sent back for revision
  - tested through a probe or experiment
  - escalated for human review
  - committed provisionally
  - accepted as the new authoritative current state
  - authorized for external action

The key CCA11 principle is:

    plurality of thought does not imply plurality of executive authority


Agreement is not the objective
------------------------------
The council should not merely argue until it agrees.

Agreement can be useful, but agreement is not evidence.

Several processes may agree because they:

  - received the same misleading evidence
  - depend on the same underlying model
  - copied one another's conclusion
  - inherited the same hidden assumption
  - were trained on correlated data
  - converged prematurely
  - mistook fluency or confidence for support

Adjudication should therefore consider:

  - quality and provenance of evidence
  - independence or correlation of the reasoning paths
  - compatibility with the observed current state
  - prior predictive performance
  - calibration where defined
  - causal and counterfactual tests
  - safety constraints
  - reversibility
  - expected value of obtaining more information
  - an explicit UNKNOWN, abstention, or reject-all alternative

CCA11 should preserve unresolved disagreement when the evidence does not justify
a single conclusion.  A deliberately dissenting process may be required to
construct the strongest alternative explanation before a high-consequence
commitment is made.


Relationship to Minsky's Society of Mind
----------------------------------------
Marvin Minsky's Society of Mind proposed that intelligence arises from the
organization of many specialized, individually limited agents rather than from
one universal reasoning mechanism.

CCA11 accepts that central pluralist insight:

    no single cognitive method is adequate for every problem

Minsky's technical "agents" are generally subpersonal mechanisms.  They are
closer to specialized processes, critics, selectors, resources, or small program
components than to complete autonomous persons.

CCA11's participating processes may be much larger cognitive systems in their
own right.  A causal reasoner, analogical mapper, NavMap simulator,
probabilistic forecaster, or language model may each perform substantial
internal computation.

CCA11 also makes several executable engineering commitments explicit:

  - proposals use inspectable map and record interfaces
  - observed, expected, inferred, retrieved, imagined, and accepted content
    remain distinguishable
  - provenance is retained
  - no cognitive process receives automatic write access to accepted state
  - external action requires an explicit commitment
  - unresolved dissent may remain active
  - human authority and protected safety constraints remain outside ordinary
    cognitive bargaining

CCA11 can therefore be described as:

    a constitutional society of cognitive processes inside one coherent mind

"Constitutional" means that the processes operate under explicit rules about
state, memory, goals, authority, and action.  It does not mean that every
process is equal or that decisions are made by simple voting.

Minsky supplied a powerful theory of cognitive plurality.  CCA11 would attempt
to turn part of that insight into an inspectable NavMap-centered architecture
with explicit state authority and commitment rules.


Relationship to Goertzel's cognitive synergy, OpenCog, and Hyperon
-------------------------------------------------------------------
Ben Goertzel's cognitive-synergy approach emphasizes that heterogeneous
cognitive processes should help one another overcome the limitations and
processing bottlenecks of any single process.  OpenCog and Hyperon pursue a
shared representational environment in which different forms of reasoning can
cooperate.

CCA11 accepts cognitive synergy as a useful design principle.

A symbolic process may rescue a statistical process that cannot express a
constraint.  A perceptual or statistical process may provide evidence that a
symbolic process lacks.  Episodic memory may provide a prior case.  A causal
reasoner may expose why a pattern-matching answer is fragile.

The proposed CCA11 emphasis is different, although complementary.

Cognitive synergy asks:

    Can another process help when this process is stuck?

CCA11 additionally asks:

    What authority does the resulting proposal possess?

OpenCog/Hyperon-style interoperability, and orchestration proposals such as
HyperClaw, may help route work among heterogeneous processes.  CCA11 requires a
further state-governance contract:

  - Which information is observed evidence?
  - Which content is only expected, inferred, retrieved, or imagined?
  - Which current map is committed?
  - Which process may propose a change?
  - Which proposal may alter accepted state?
  - Which conclusion may control an external action?

The shared substrate in CCA11 is therefore not merely a communication room.  It
includes NavMaps, proposal records, provenance, acceptance rules, commitment
rules, and protected action authority.


Relationship to existing runner profiles
----------------------------------------
Several existing profile demonstrations are precursors:

  - Profile 4 demonstrates several sandbox brains proposing actions.
  - Profile 6 demonstrates parallel combinatorial search.
  - Profile 7 demonstrates arbitration among heterogeneous proposal sources.

CCA11 would integrate and greatly extend these ideas.  It would replace simple
fork-and-vote behavior with specialized reasoning roles, protected map layers,
explicit disagreement, metacognitive allocation, evidence-based adjudication,
governed state commitment, and controlled external action.


Design summary
--------------
CCA11 is a coherent agent whose thoughts may be plural but whose present state,
goals, memory, and authority are governed.

The intended achievement is not a louder committee.  It is disciplined
cognitive diversity inside one inspectable and accountable mind.
"""


CCA12_PROFILE_NARRATIVE = r"""
Research status
---------------
CCA12 is a future federated cognitive-architecture research profile.  It does
not claim that the present CCA8 software already implements a CCA12 pod.

The present runner records the design direction and then returns safely to the
operational Mountain Goat baseline.


Core idea
---------
CCA11 contains several cognitive methods within one coherent self.

CCA12 connects several complete CCA11 cognitive architectures.

    CCA11
        = one self with many cognitive methods

    CCA12
        = many CCA11 selves operating under one governed mission

CCA11 provides cognitive-method plurality.

CCA12 provides agent plurality.

Each CCA11 pod member may have its own:

  - identity and self-model
  - Accepted Working Navigation Map
  - observations and embodiment
  - episodic and autobiographical history
  - learned map-policy transformations
  - active goals within delegated limits
  - attention
  - uncertainty
  - internal cognitive council
  - local action capabilities

CCA12 is therefore not merely a larger internal council.  It is a governed
federation of complete cognitive agents.


Why build a pod?
----------------
A pod of CCA11 systems may provide:

  - parallel exploration of different hypotheses
  - independent replication
  - greater planning breadth and depth
  - different temporal horizons
  - distinct areas of expertise
  - distributed perception
  - multiple physical embodiments
  - adversarial checking
  - fault tolerance
  - graceful degradation
  - continuous operation while some members deliberate, learn, or recover
  - independent confirmation before consequential action

The pod becomes genuinely useful only when its members provide meaningful
diversity or independence.

Ten identical copies using the same model, memories, prompts, assumptions, and
evidence may reproduce the same error ten times.

Useful diversity may come from different reasoning algorithms, model families,
training histories, sensory viewpoints, map histories, assigned roles, temporal
horizons, or deliberately different assumptions.  Some members should produce
an initial analysis before seeing the other members' conclusions.


The Mission Charter
-------------------
CCA12 requires an explicit Mission Charter or pod constitution.

The charter should define:

  - the pod's legitimate mission
  - human authorities
  - protected goals
  - prohibited actions
  - delegation boundaries
  - resource limits
  - privacy and information-sharing rules
  - permitted embodiments and tools
  - conditions requiring independent verification
  - conditions requiring human authorization
  - conditions requiring abstention or shutdown
  - emergency-stop authority
  - rules for adding, suspending, isolating, or retiring a pod member
  - rules governing modification of the charter itself

No ordinary pod member should be able to rewrite the Mission Charter
unilaterally.

The charter is not merely another belief to be outvoted.  It defines the
authority under which the pod exists and acts.


Local minds and shared pod state
--------------------------------
CCA12 should not be implemented as one unstructured, globally mutable memory
that every member can overwrite.

Each member retains its own local cognitive state.

Shared pod information should be published through provenance-preserving
records such as:

  - observations
  - map fragments
  - hypotheses
  - plans
  - predicted outcomes
  - confidence or support claims
  - counterarguments
  - experimental results
  - requests for assistance
  - resource commitments
  - action proposals
  - authority decisions

The pod may maintain a shared Mission Map, Pod Blackboard, or Assertion Ledger
for joint commitments, resources, task allocation, and externally relevant
conclusions.

A statement appearing on the blackboard is not automatically accepted as true.

The record should identify:

  - which member asserted it
  - which evidence supports it
  - which local map revision produced it
  - which assumptions were used
  - whether another member independently confirmed it
  - whether objections remain
  - what authority level it currently possesses
  - when it expires or requires revalidation

Shared state should distinguish at least:

  - published assertion
  - independently confirmed assertion
  - pod-level provisional commitment
  - pod-level accepted mission state
  - authorized external action


Controlled independence
-----------------------
Members should often produce their initial analyses independently before seeing
the conclusions of other members.

This helps reduce:

  - copying
  - anchoring
  - conformity
  - groupthink
  - premature convergence
  - accidental dependence among supposedly independent confirmations

After the initial independent phase, members may exchange critiques, request
evidence, reproduce calculations, or construct competing plans.

The system should record when two conclusions are genuinely independent and
when they share models, data, code, memories, or assumptions.

Independence is not all-or-nothing.  The pod should record dependency structure
rather than simply counting agreeing agents.


Possible pod roles
------------------
A future pod might assign complete CCA11 systems to roles such as:

  - Observer
      Construct the best grounded description of current state.

  - Planner
      Propose routes from accepted state to mission goals.

  - Forecaster
      Estimate outcome distributions, risks, and time horizons.

  - Historian
      Retrieve relevant prior episodes and identify differences from now.

  - Scientist
      Develop causal hypotheses and discriminating experiments.

  - Specialist
      Contribute domain-specific knowledge, tools, or sensor access.

  - Skeptic
      Search for hidden assumptions, counterexamples, and failure modes.

  - Guardian
      Evaluate safety, authority, reversibility, and charter compliance.

  - Integrator
      Construct a traceable synthesis without erasing unresolved dissent.

These are operating roles rather than permanent castes.  A member may change
roles when the Mission Charter and resource allocator permit it.

A pod should avoid making the Integrator a hidden dictator.  Integration is a
recorded operation with evidence and objections, not an uninspectable final
answer generator.


Pod-level adjudication
----------------------
CCA12 should not rely on simple majority vote as its general decision rule.

Different questions require different forms of adjudication:

  - direct observation may be weighted by sensor reliability and provenance
  - specialized questions may use demonstrated domain competence
  - important factual claims may require independent replication
  - uncertain explanations may require adversarial comparison
  - plans may be tested in separate simulations
  - safety-critical proposals may require explicit Guardian authorization
  - high-consequence actions may require two independently produced approvals
  - unresolved or out-of-charter questions may require human escalation

The pod should be able to conclude:

  - one proposal is provisionally best supported
  - several alternatives remain viable
  - the evidence is insufficient
  - another observation or experiment is needed
  - no represented hypothesis is adequate
  - the pod should abstain
  - the decision must be escalated to a human authority

Consensus may be reported, but consensus alone does not establish truth.


External-action authority
-------------------------
For a single shared embodiment, CCA12 should normally expose one controlled
external-action gateway.

A member may recommend an action, but recommendation is not execution.

The gateway should verify:

  - current accepted mission state
  - authority and delegation
  - safety constraints
  - resource ownership
  - conflicting active commitments
  - required confirmations
  - reversibility
  - emergency-stop state

For safety-critical actions, the pod may use a two-key or multi-key rule in
which independently authorized components must agree before execution.

For a pod controlling several embodiments, authority may be divided through
explicit action leases.

An action lease should state:

  - which member may control which embodiment or resource
  - what actions are permitted
  - the geographic, temporal, and mission boundaries
  - expiration conditions
  - revocation authority
  - collision and conflict rules
  - emergency-stop behavior

This permits useful local autonomy without allowing several agents to issue
incompatible commands to the same actuator or resource.


Failure isolation and trust
---------------------------
A CCA12 pod must assume that a member can be mistaken, stale, compromised,
unavailable, or internally inconsistent.

The architecture should support:

  - health and liveness checks
  - capability and calibration records
  - message authentication and provenance
  - bounded permissions
  - quarantine of a malfunctioning member
  - replay of the member's assertions and actions
  - revocation of action leases
  - replacement without silently inheriting the failed member's authority

Trust should be scoped.  A member may be trusted for a sensor stream or a domain
without being trusted to alter the mission charter or authorize physical action.


Failure modes requiring explicit study
--------------------------------------
CCA12 introduces problems that do not exist, or are smaller, inside one CCA11
mind:

  - correlated reasoning errors
  - groupthink and herding
  - stale shared context
  - misleading or poisoned messages
  - authority capture
  - conflicting goals
  - race conditions
  - duplicated actions
  - resource contention
  - deadlock
  - communication loss
  - member failure
  - compromised or deceptive members
  - divergence between local maps and shared mission state
  - gradual drift in the pod's interpretation of its charter

CCA12 is therefore a distributed-systems architecture as well as a cognitive
architecture.

Scaling the number of agents without solving these governance problems may
amplify error rather than intelligence.


Relationship to Minsky's Society of Mind
----------------------------------------
CCA12 is closer than CCA11 to the ordinary-language meaning of a society of
minds, but it is less like Minsky's technical Society of Mind.

Minsky's agents are generally specialized subpersonal mechanisms whose
interaction produces one mind.

A CCA12 member is a complete CCA11 cognitive architecture with its own accepted
state, memory, identity, reasoning, and delegated goals.

CCA12 is therefore a society of complete minds rather than a mind composed of
small agents.

Minsky's central lesson still applies: intelligence depends on organization,
not merely on the number of components.  CCA12 adds explicit distributed
mission, provenance, delegation, and action-authority contracts.


Relationship to Goertzel's cognitive synergy
---------------------------------------------
Cognitive synergy may occur inside each CCA11 member and also across the CCA12
pod.

One member may supply evidence or a representation that allows another member
to overcome a reasoning bottleneck.  A specialist may transform a problem into
a form another member can solve.  A skeptical member may expose an assumption
that every planner shared.

The CCA12 extension is that inter-agent communication does not erase agent
boundaries.

Each assertion retains:

  - source identity
  - local-map provenance
  - evidence
  - assumptions
  - authority
  - confidence type
  - objections
  - independent confirmations

A shared OpenCog/Hyperon-like substrate or HyperClaw-like orchestration layer
could support communication and task routing.  CCA12 additionally requires
federated state governance, a Mission Charter, explicit delegation, and
controlled external-action rights.

The shared substrate enables cooperation.  It does not automatically merge
every member's state into one undifferentiated global consciousness.


Relationship to existing runner profiles
----------------------------------------
Profile 5 is an early society demonstration in which several agents have
separate worlds and exchange a simple message.

CCA12 would extend that idea with:

  - complete CCA11 members
  - a Mission Charter
  - a pod-level assertion ledger
  - explicit task and resource delegation
  - independent first-pass reasoning
  - provenance-preserving communication
  - evidence-based adjudication
  - action leases
  - safety authorization
  - human escalation
  - fault and compromise handling


Design summary
--------------
    CCA12
        = many complete CCA11 selves
        + one governed mission
        + one Mission Charter
        + one provenance-preserving pod ledger
        + controlled delegation
        + governed external-action rights

The superhuman property does not come merely from multiplying agents.

It comes from combining genuine cognitive diversity, useful independence,
parallel computation, disciplined information exchange, explicit mission and
authority governance, traceable adjudication, and controlled action.
"""


def profile_cca11_governed_cognitive_plurality(_ctx: Any) -> ProfileTuple:
    """Describe the future CCA11 architecture, then return the operational baseline."""
    _profile_heading("Selection: CCA11 — One Coherent Superhuman Mind with Governed Cognitive Plurality")
    print(CCA11_PROFILE_NARRATIVE)
    _print_goat_fallback()
    return _goat_defaults()


def profile_cca12_governed_pod(_ctx: Any) -> ProfileTuple:
    """Describe the future CCA12 pod architecture, then return the operational baseline."""
    _profile_heading("Selection: CCA12 — Governed Pod of Complete CCA11 Cognitive Architectures")
    print(CCA12_PROFILE_NARRATIVE)
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
        cca11=profile_cca11_governed_cognitive_plurality,
        cca12=profile_cca12_governed_pod,
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
      - 1..9 → select profile (future profiles print a narrative or dry run, then fall back to goat defaults).
      - 'T' or 't' → open README.md (tutorial) and re-prompt.
      - any other input → default to Mountain Goat (as before).
    """
    operations = operations or default_profile_operations()
    goat = _goat_defaults()

    while True:
        try:
            choice = input("Please make a choice [1–9 or T | Enter = Mountain Goat]: ").strip()
        except (EOFError, KeyboardInterrupt):
            print("\nCancelled selection.... will exit program....")
            sys.exit(0)

        # Fast path: Enter accepts the operational Mountain Goat baseline.
        if choice == "":
            _print_goat_intro()
            name, sigma, jump, k = goat
            break

        # Tutorial: open README, then re-prompt
        if choice.lower() == "t":
            operations.open_tutorial()
            continue  # re-show prompt

        # Numeric choices
        if choice == "1":
            _print_goat_intro()
            name, sigma, jump, k = goat
            break
        if choice == "2":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.chimpanzee, ctx)
            break
        if choice == "3":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.human, ctx)
            break
        if choice == "4":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.human_multi_brains, ctx, world)
            break
        if choice == "5":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.society_multi_agents, ctx)
            break
        if choice == "6":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.multi_brains_adv_planning, ctx)
            break
        if choice == "7":
            name, sigma, jump, k = _run_interactive_profile_choice(operations.superhuman, ctx)
            break
        if choice == "8":
            callback = operations.cca11 or profile_cca11_governed_cognitive_plurality
            name, sigma, jump, k = _run_interactive_profile_choice(callback, ctx)
            break
        if choice == "9":
            callback = operations.cca12 or profile_cca12_governed_pod
            name, sigma, jump, k = _run_interactive_profile_choice(callback, ctx)
            break

        # Anything else: prompt again (no silent default)
        print(f"The selection {choice!r} is not valid. Please enter 1–9, 'T', or press Enter for Mountain Goat.\n")

    ctx.profile = name
    return {"name": name, "ctx_sigma": sigma, "ctx_jump": jump, "winners_k": k}
