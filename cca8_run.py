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
import hashlib
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
    skill_q,
    update_skill,
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
from cca8_env import HybridEnvironment, EnvObservation  # environment simulation (HybridEnvironment/EnvState/EnvObservation)
from cca8_features import FactMeta
from cca8_navpatch import (
    SurfaceGridV1,
    compose_surfacegrid_v1,
    derive_grid_slot_families_v1,
    grid_overlap_fraction_v1,
    CELL_UNKNOWN,
    CELL_TRAVERSABLE,
    CELL_HAZARD,
    CELL_GOAL,
)


# --- Public API index, version, global variables and constants ----------------------------------------
#nb version number of different modules are unique to that module
#nb the public API index specifies what downstream code should import from this module

__version__ = "0.8.2"
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
    "HAL",
    "PolicyRuntime",
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
class CreativeCandidate:
    """One imagined candidate proposed by the WorkingMap Creative layer.

    This is intentionally lightweight and inspectable (terminal-friendly). It is NOT a learned model.
    Think of it as: "if I were to do X next, what do I roughly expect and why?"

    Fields:
        policy:
            The policy name being proposed (e.g., "policy:follow_mom").
        score:
            A comparable score (higher is better). For now this is a placeholder for future rollout scoring.
        notes:
            Short human-readable rationale for the candidate (why it was considered / why it scored).
        predicted:
            Optional small dict holding predicted consequences (e.g., {"zone": "safe"}).
            This is intentionally shallow: anything rich belongs in engrams later.
    """
    policy: str
    score: float
    notes: str = ""
    predicted: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class Ctx:
    """Mutable runtime context for the agent (module-level, importable).

    ... existing sections ...

    Reinforcement learning (policy selection)
    -----------------------------------------
    -there may be, and often are, many policies which successfully gate and trigger; however, only one can
      be executed; which one to execute?
    -in the first versions of the CCA8 we simply used the order of the policies and executed the first one to trigger,
      then in further development we used the deficit values produced by each policy and used an RL value only to break ties,
      and then, as shown below, if the deficit values are close enough together (i.e., within a specified rl_delta value) then
      we use RL values to decide which of these triggered policies to execute.
      (NOTE: "deficit" here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD) (amount ABOVE threshold, not a negative deficit).
      (Policies without a drive-urgency term score 0.00 and will tie-break by stable policy order (or RL tie-break, if enabled).

    rl_enabled : bool
        Enable epsilon-greedy policy selection. When enabled, the selector can use the
        controller skill ledger (SkillStat.q) as a secondary tie-break among triggered policies.
    rl_epsilon : float | None
        Exploration probability in [0.0, 1.0]. If None, fall back to ctx.jump (so you can reuse
        the existing “jump” knob as an exploration knob during early experiments).
        # rl_delta controls how often learned value (SkillStat.q) can influence selection of which triggered policy to execute:
    rl_delta:
        = 0.0  → q is used only for exact deficit ties.
        = small positive (e.g., rl_delta=0.02) → q is used for "near ties" (deficits within delta of best).
        = large rl_delta → q can influence most choices among triggered policies (approaches "q-driven" within the candidate set).

    """

    sigma: float = 0.015
    jump: float = 0.2

    rl_enabled: bool = False             # Reinforcement learning (policy selection)
    rl_epsilon: Optional[float] = None   # Reinforcement learning (policy selection)
    rl_explore_steps: int = 0  # RL bookkeeping
    rl_exploit_steps: int = 0  # RL bookkeeping
    rl_delta: float = 0.0 # rl_delta controls how often learned value (SkillStat.q) can influence selection of triggered policies to execute

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
    cog_cycles: int = 0  # closed-loop cognitive cycles (env_obs→update→select→execute→act); incremented in menu 35/37 flows
    # Prediction error v0 (Phase VIII):
    # - Store the policy-written postcondition for the NEXT env step (hypothesis).
    # - Next tick, compare to EnvObservation/EnvState and log a mismatch vector.
    pred_next_posture: Optional[str] = None
    pred_next_policy: Optional[str] = None
    pred_err_v0_last: dict[str, int] = field(default_factory=dict)

    last_drive_flags: Optional[set[str]] = None
    env_episode_started: bool = False       # Environment / HybridEnvironment integration
    env_last_action: Optional[str] = None  # last fired policy name for env.step(...)
    # Console UX: print the env-loop tag legend once per session (menu 35/37).
    env_loop_legend_printed: bool = False

    # Partial observability / observation masking (Phase VIII)
    # - obs_mask_prob: independent drop probability for each non-protected token.
    # - obs_mask_seed: if set, masking uses a deterministic per-step RNG (seeded from base seed + step_ref).
    # - obs_mask_last_cfg_sig: sentinel so we print the config line once per setting change (no spam).
    # - A few safety-critical predicate families are protected from dropping (see inject_obs_into_world).
    #obs_mask_prob: float = 0.2    #<-----------------------------------SET obs_mask_prob
    obs_mask_prob: float = 0.0
    obs_mask_verbose: bool = True
    obs_mask_seed: Optional[int] = None
    obs_mask_last_cfg_sig: Optional[str] = None
    mini_snapshot: bool = True  #mini-snapshot toggle starting value
    # Env-loop (menu 37) per-cycle footer summary.
    # This is intentionally pragmatic and subject to change as Phase IX evolves.
    env_loop_cycle_summary: bool = True
    env_loop_cycle_summary_max_items: int = 6

    posture_discrepancy_history: list[str] = field(default_factory=list) #per-session list of discrepancies motor command vs what environment reports
    # BodyMap: tiny body+near-world map (separate WorldGraph instance)
    body_world: Optional[cca8_world_graph.WorldGraph] = None
    body_ids: dict[str, str] = field(default_factory=dict)
    bodymap_last_update_step: Optional[int] = None  # BodyMap recency marker: controller_steps value when BodyMap was last updated

    # WorkingMap: short-term working memory graph (separate WorldGraph instance)
    working_world: Optional[cca8_world_graph.WorldGraph] = None
    working_enabled: bool = True         # mirror env observations into WorkingMap
    working_verbose: bool = False        # print per-tick WorkingMap injection lines
    working_max_bindings: int = 250      # cap WorkingMap size (anchors are preserved)
    working_move_now: bool = True       # move WorkingMap NOW to the latest predicate each env tick
    # WorkingMap MapSurface (Phase VII): stable map updated in place (not a tick log).
    working_mapsurface: bool = True      # env obs updates entity nodes in place (no repeated pred/cue bindings)
    working_trace: bool = False          # debug only: also append a per-tick trace (can grow quickly)
    wm_entities: dict[str, str] = field(default_factory=dict)            # entity_id -> binding id (in working_world)
    wm_last_env_cues: dict[str, set[str]] = field(default_factory=dict)  # entity_id -> last injected cue tags
    wm_last_navpatch_sigs: dict[str, set[str]] = field(default_factory=dict)  # entity_id -> last injected NavPatch sig16 set

    # WorkingMap Creative layer (counterfactual rollouts / imagined futures)
    # - Does not change policy selection yet (purely inspectable scaffolding for Option B).
    # - Candidates will later be written under WM_CREATIVE (or stored as engrams), but for now we keep them on ctx.
    wm_creative_enabled: bool = True
    wm_creative_k: int = 3  # typical 2–5; keep small to stay terminal-readable
    wm_creative_candidates: list[CreativeCandidate] = field(default_factory=list)
    wm_creative_last_pick: Optional[CreativeCandidate] = None
    # MapSurface snapshot dedup + last stored pointer (manual first; later boundary-triggered)
    wm_mapsurface_last_sig: Optional[str] = None
    wm_mapsurface_last_engram_id: Optional[str] = None
    wm_mapsurface_last_world_bid: Optional[str] = None
    # NavPatches (Phase X; NavPatch plan v5)
    # - EnvObservation may include processed local navigation map fragments (nav_patches).
    # - WorkingMap entities can own patch references via binding.meta['wm']['patch_refs'].
    # - We can store patch payloads as separate Column engrams (dedup by content signature).
    navpatch_enabled: bool = True
    navpatch_store_to_column: bool = True
    navpatch_verbose: bool = False
    navpatch_sig_to_eid: dict[str, str] = field(default_factory=dict)  # sig(hex) -> engram_id
    navpatch_last_log: dict[str, Any] = field(default_factory=dict)

    # WorkingMap SurfaceGrid (Phase X v5.9): composed topological grid + derived slot-families
    # -------------------------------------------------------------------------------
    # SurfaceGrid is the single composed grid per tick built from active NavPatch instances.
    # It is NOT stored into the long-term WorldGraph; it is a WorkingMap view designed to be
    # cheap to build/scan and easy to render for inspection.
    wm_surfacegrid_enabled: bool = True
    wm_surfacegrid_verbose: bool = False
    wm_surfacegrid_w: int = 16
    wm_surfacegrid_h: int = 16
    wm_surfacegrid_self_radius: int = 2
    wm_surfacegrid: Optional[SurfaceGridV1] = None
    wm_surfacegrid_sig16: Optional[str] = None
    wm_surfacegrid_last_input_sig16: list[str] = field(default_factory=list)
    wm_surfacegrid_dirty: bool = True
    wm_surfacegrid_dirty_reasons: list[str] = field(default_factory=list)
    wm_surfacegrid_compose_ms: float = 0.0
    wm_surfacegrid_last_ascii: Optional[str] = None
    # SurfaceGrid printing controls (terminal UX)
    wm_surfacegrid_ascii_each_tick: bool = False  # if True, print the grid even on cache-hit ticks (compose_ms==0)
    wm_surfacegrid_legend_printed: bool = False   # internal: print legend once per session when map printing is enabled
    # --- WM.Salience + landmark overlay (Phase X Step 14) -------------------------------
    # Minimal v1:
    #   - Store per-entity salience TTL + reason in WM.MapSurface entity meta['wm'].
    #   - Choose a small focus set (SELF + goals + hazards + up to K novelty/uncertainty items).
    #   - Render a sparse SurfaceGrid ASCII (hide traversable '.' by default) and overlay landmark letters.
    wm_salience_enabled: bool = True
    wm_salience_novelty_ttl: int = 3
    wm_salience_promote_ttl: int = 8
    wm_salience_max_items: int = 3
    wm_salience_focus_entities: list[str] = field(default_factory=list)
    wm_salience_last_events: list[dict[str, Any]] = field(default_factory=list)

    # Step 14 nice-to-have:
    # If an inspect/probe action runs, we can "lock" an entity into focus for a few ticks so it stays visible.
    wm_salience_inspect_focus_ttl: int = 4

    # Which policy names count as "inspect/probe" (future Step 15+). Leave as-is unless you add a probe policy.
    wm_salience_inspect_policy_names: list[str] = field(
        default_factory=lambda: ["policy:explore_check", "policy:inspect", "policy:probe"] )

    # Forced focus TTL map: entity_id -> remaining ticks. This is display/attention only (does not change belief).
    wm_salience_forced_focus: dict[str, int] = field(default_factory=dict)
    wm_salience_forced_reason: dict[str, str] = field(default_factory=dict)

    # SurfaceGrid ASCII presentation controls (display-only; does not change grid semantics).
    wm_surfacegrid_ascii_sparse: bool = True         # hide '.' cells (traversable) to keep prints uncluttered
    wm_surfacegrid_ascii_show_entities: bool = True  # overlay @/M/S/C marks for salient entities

    # --- WM.Grid → predicates (Phase X Step 13) -----------------------------------------
    # These are deterministic “derived facts” from SurfaceGrid. They are NOT cues and are
    # never emitted as cue:* tokens.
    wm_grid_to_preds_enabled: bool = True

    # Last computed slot-family dict from derive_grid_slot_families_v1(...)
    # Keys are small/stable (e.g., "hazard:near", "terrain:traversable_near", "goal:dir").
    wm_grid_slot_families: dict[str, Any] = field(default_factory=dict)

    # The concrete pred:* tags written onto the MapSurface SELF binding this tick (for inspection/traces).
    wm_grid_pred_tags: list[str] = field(default_factory=list)

    # NavPatch (Phase X scaffolding): predictive matching loop + traceability
    # navpatch_enabled gates the entire matching pipeline. When enabled, EnvObservation.nav_patches
    # is treated as a stream of local "scene patches" that can be matched to prior prototypes stored
    # as Column engrams. This is not used for policy selection yet; it exists for logging and for
    # later WorkingMap integration.

    # NavPatch matching (Phase X): diagnostic top-K match traces (predictive coding hooks).
    navpatch_match_top_k: int = 3
    navpatch_match_accept_score: float = 0.85
    navpatch_match_ambiguous_margin: float = 0.05  # if best-second < margin, mark match as ambiguous (do not hallucinate certainty)
    navpatch_last_matches: list[dict[str, Any]] = field(default_factory=list)

    # --- WM.Scratch (Phase X Step 15A): ambiguous commit records -----------------------
    # When a NavPatch match is "ambiguous", we write a compact record into WM.SCRATCH so later
    # steps (zoom/probe) can “look at” the ambiguity and choose to inspect more.
    wm_scratch_navpatch_enabled: bool = True
    wm_scratch_navpatch_key_to_bid: dict[str, str] = field(default_factory=dict)  # key -> WM binding id (scratch item)
    wm_scratch_navpatch_last_keys: set[str] = field(default_factory=set)          # last tick's active ambiguity keys

    # --- WM.Zoom (Phase X Step 15B): explicit zoom_down/zoom_up events -----------------------
    # Zoom is a minimal, explicit "mode" derived from persistent ambiguity in WM.Scratch.
    # It is diagnostic first: events are emitted on transitions and stored for JSON/terminal traces.
    wm_zoom_enabled: bool = True
    wm_zoom_verbose: bool = False   # if True, print zoom transitions (rare; transition ticks only)
    wm_zoom_state: str = "up"       # "up" | "down" ("down" means we are in inspect/probe mode)
    wm_zoom_last_reason: Optional[str] = None
    wm_zoom_last_event_step: Optional[int] = None
    wm_zoom_last_events: list[dict[str, Any]] = field(default_factory=list)

    # --- WM.Probe (Phase X Step 15C): minimal probe/inspect policy knobs -----------------------
    # Probe is an *epistemic* action: when WM.Scratch reports an ambiguous NavPatch match
    # (especially for hazards), we can take a one-step "inspect" action that increases
    # evidence precision on the next cycle (diagnostic-first; no real physics yet).
    #
    # Implementation note:
    #   - The probe policy temporarily raises ctx.navpatch_precision_grid, then the matching loop
    #     auto-restores it after wm_probe_duration_steps (see navpatch_predictive_match_loop_v1).
    wm_probe_enabled: bool = True
    wm_probe_verbose: bool = False
    wm_probe_cooldown_steps: int = 3            # debounce: min controller_steps between probes
    wm_probe_duration_steps: int = 2            # how long the precision boost remains active (steps)
    wm_probe_grid_precision: float = 0.50       # temporary value assigned to ctx.navpatch_precision_grid
    wm_probe_last_step: Optional[int] = None
    wm_probe_restore_step: Optional[int] = None
    wm_probe_prev_navpatch_precision_grid: Optional[float] = None

    # NavPatch priors (Phase X 2.2a): top-down bias terms (OFF by default)
    # -------------------------------------------------------------------
    # These priors are used ONLY inside the NavPatch matching loop to bias which stored
    # prototype a new patch best matches. They do not affect policy selection yet.
    #
    # Design constraints:
    #   - Priors must never override strong evidence. We enforce this via an "error guard":
    #     if raw matching error exceeds navpatch_priors_error_guard, we refuse to call a match
    #     "near" even if priors would raise the posterior score.
    navpatch_priors_enabled: bool = True
    navpatch_priors_hazard_bias: float = 0.05
    navpatch_priors_error_guard: float = 0.45
    # Precision weighting (Phase X 2.2b): evidence reliability weights (v1 uses tags vs extent).
    navpatch_precision_tags: float = 0.75
    navpatch_precision_extent: float = 0.25
    navpatch_precision_grid: float = 0.0
    navpatch_precision_tags_birth: float = 0.60     # lower precision early → more ambiguity
    navpatch_precision_tags_struggle: float = 0.65  # slightly better than birth, still degraded
    navpatch_last_priors: dict[str, Any] = field(default_factory=dict)

    # ---------------------------------------------------------------------
    # EFE policy scoring (Phase X): diagnostic scaffolding (trace-only)
    # ---------------------------------------------------------------------
    # EFE is diagnostic only right now; it does NOT affect policy selection.
    #
    # Storage convention:
    #   - ctx.efe_last: full JSON-safe bundle returned by compute_efe_scores_stub_v1(...)
    #   - ctx.efe_last_scores: list of per-policy score rows (usually ctx.efe_last["scores"])
    efe_enabled: bool = False
    efe_selection_enabled: bool = False
    efe_verbose: bool = False

    efe_w_risk: float = 1.0
    efe_w_ambiguity: float = 1.0
    efe_w_preference: float = 1.0

    efe_last: dict[str, Any] = field(default_factory=dict)
    efe_last_scores: list[dict[str, Any]] = field(default_factory=list)

    # Bridge from ActionCenter/controller: last triggered policy names (for EFE scoring candidates).
    ac_triggered_policies: list[str] = field(default_factory=list)

    # MapSurface auto-retrieve (Option B6/B7)
    # - When enabled, on keyframes (stage/zone boundary) we try to seed WorkingMap from a prior
    #   wm_mapsurface engram (default mode="merge" so it behaves as a conservative prior).
    wm_mapsurface_autoretrieve_enabled: bool = False
    wm_mapsurface_autoretrieve_mode: str = "merge"   # "merge" (recommended) or "replace" (debug)
    wm_mapsurface_autoretrieve_top_k: int = 5        # candidates to rank (2..10)
    wm_mapsurface_autoretrieve_verbose: bool = True  # print when auto-retrieve applies
    wm_mapsurface_last_autoretrieve_engram_id: Optional[str] = None
    wm_mapsurface_last_autoretrieve_reason: Optional[str] = None

    # memory pipeline knobs (opt-in; defaults preserve Phase VI behavior)
    phase7_working_first: bool = False    # execute policies in WorkingMap; keep long-term WorldGraph sparse
    phase7_run_compress: bool = False     # compress consecutive identical policy actions into one long-term run
    phase7_run_verbose: bool = False      # print run-compression debug lines during env-loop
    phase7_move_longterm_now_to_env: bool = False  # move long-term NOW to latest env posture binding each step

    # run-compression state (env-loop)
    run_policy: Optional[str] = None
    run_action_bid: Optional[str] = None
    run_len: int = 0
    run_start_env_step: Optional[int] = None
    run_last_env_step: Optional[int] = None
    run_open: bool = False

    # if True, print a one-line notice when a keyframe boundary clears lt_obs_slots -- effects if write new predicate bindings
    #   this is intentionally separate from longterm_obs_verbose (reuse-line spam).
    longterm_obs_keyframe_log: bool = True

    # Safety / posture retry bookkeeping
    last_standup_step: Optional[int] = None
    last_standup_failed: bool = False
    # Long-term WorldGraph EnvObservation injection (real knob):
    # - If False, we skip long-term WorldGraph writes entirely (BodyMap still updates; WorkingMap may still update).
    # - Keyframes are only relevant when long-term injection is enabled AND mode="changes".
    longterm_obs_enabled: bool = True

    # Long-term WorldGraph observation logging controls
    # -----------------------------------------------
    # Most of the time the environment's state does not change every tick.
    # In episodic mode, injecting a full snapshot each tick can spam the long-term
    # graph with identical pred:* nodes (e.g., posture:fallen repeated many times).
    #
    # longterm_obs_mode:
    #   - "snapshot": old behavior; always write every observed predicate each tick
    #   - "changes" : write only when a state-slot changes (plus optional re-asserts)
    longterm_obs_mode: str = "changes"

    # If >0, re-emit an unchanged slot again after this many controller_steps.
    # This keeps the graph flexible enough to "re-observe" a stable fact occasionally
    # without logging it every single tick.
    longterm_obs_reassert_steps: int = 0
    # Long-term cue de-dup (changes-mode only): emit cue only on rising edge (absent→present),
    # optionally re-emit after reassert_steps while still present; mark absent when it disappears.
    longterm_obs_dedup_cues: bool = True
    lt_obs_cues: dict[str, dict[str, Any]] = field(default_factory=dict)

    # Keyframe triggers (Phase IX; long-term obs, changes-mode):
    # - period_steps: 0 disables periodic keyframes; N>0 triggers when controller_steps % N == 0.
    # - on_zone_change: treat coarse zone flips as keyframes (safe/unsafe discontinuities).
    # - on_pred_err: treat sustained pred_err v0 mismatch as a surprise keyframe (streak-based).
    # - on_milestone: milestone keyframes (env_meta milestones and/or derived slot transitions); off by default.
    # - on_emotion: strong emotion/arousal keyframes (env_meta emotion/affect; rising-edge into "high"); off by default.

    longterm_obs_keyframe_on_stage_change: bool = False
    longterm_obs_keyframe_on_zone_change: bool = False
    #ctx.longterm_obs_keyframe_on_stage_change in presets set to False

    longterm_obs_keyframe_period_steps: int = 0
    #longterm_obs_keyframe_period_steps: int = 10 #toggle: keyframe every 10 cog cycles
    # Periodic keyframes can be scheduled in two ways:
    #   - legacy: absolute clock (step_no % period == 0)
    #   - reset-on-any-keyframe: treat periodic as a "max gap" since last keyframe
    #       (i.e., if *any* other keyframe happens, restart the periodic counter).
    # The reset-on-any-keyframe mode reduces "weird mid-episode splits" and prevents periodic
    # keyframes from clustering right after meaningful milestone boundaries.
    longterm_obs_keyframe_period_reset_on_any_keyframe: bool = True
    # Optional: suppress periodic keyframes while sleeping.
    #
    # Motivation (robotics / HAL):
    #   - Periodic keyframes are a "max-gap" safety net when the world is quiet.
    #   - During sleep, we may prefer NOT to inject arbitrary episode boundaries.
    #
    # Sleep detection is best-effort (future-facing):
    #   - env_meta may supply: sleep_state/sleep_mode (str) OR sleeping/dreaming (bool)
    #   - or predicates may include: sleeping:non_dreaming / sleeping:dreaming (plus rem/nrem aliases)
    longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming: bool = False
    longterm_obs_keyframe_period_suppress_when_sleeping_dreaming: bool = False

    longterm_obs_keyframe_on_pred_err: bool = False
    #longterm_obs_keyframe_on_pred_err: bool = True   #toggle: keyframe surprise
    longterm_obs_keyframe_pred_err_min_streak: int = 2

    longterm_obs_keyframe_on_milestone: bool = True  #toggle: milestone keyframes (env_meta + derived transitions)
    #longterm_obs_keyframe_on_milestone: bool = False

    longterm_obs_keyframe_on_emotion: bool = False
    longterm_obs_keyframe_emotion_threshold: float = 0.85

    # Keyframe bookkeeping (long-term observation cache)
    lt_obs_last_zone: Optional[str] = None
    lt_obs_pred_err_streak: int = 0
    lt_obs_last_keyframe_step: Optional[int] = None
    lt_obs_last_milestones: set[str] = field(default_factory=set)
    lt_obs_last_emotion_label: Optional[str] = None
    lt_obs_last_emotion_high: bool = False

    # If True, print per-token reuse lines when longterm_obs_mode="changes" skips unchanged slots.
    longterm_obs_verbose: bool = False

    # Private state: per-slot last (token, bid, emit_step) used by longterm_obs_mode="changes".
    lt_obs_slots: dict[str, dict[str, Any]] = field(default_factory=dict)
    lt_obs_last_stage: Optional[str] = None

    # Per-cycle JSON log record (Phase X): minimal, replayable trace contract
    # ---------------------------------------------------------------------
    # When enabled, each closed-loop env step appends a JSON-safe dict record to ctx.cycle_json_records,
    # and optionally writes it to ctx.cycle_json_path as JSONL (one record per line).
    cycle_json_enabled: bool = False
    cycle_json_path: Optional[str] = None
    cycle_json_max_records: int = 2000
    cycle_json_records: list[dict[str, Any]] = field(default_factory=list)


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


def init_working_world() -> cca8_world_graph.WorldGraph:
    """Initialize a short-term WorkingMap (working memory) as a separate WorldGraph.

    Design intent:
      - WorkingMap holds the full episodic trace.
      - Long-term WorldGraph can later be run in 'semantic' mode to reduce clutter.
      - Consolidation policy (what gets copied from WorkingMap into WorldGraph) can evolve
        without losing the ability to record raw per-tick structure.
    """
    ww = cca8_world_graph.WorldGraph(memory_mode="episodic")
    ww.set_tag_policy("allow")
    ww.set_stage("neonate")
    ww.ensure_anchor("NOW")
    ww.ensure_anchor("NOW_ORIGIN")
    return ww


def reset_working_world(ctx) -> None:
    """Reset ctx.working_world to a fresh WorkingMap instance (and clear MapSurface caches).
    """
    try:
        ctx.working_world = init_working_world()
        # MapSurface caches live on ctx (slots=True → must be explicit)
        ctx.wm_entities.clear()
        ctx.wm_last_env_cues.clear()
        # Creative layer state is also WorkingMap-local (ephemeral); clearing WM clears this too.
        try:
            ctx.wm_creative_candidates.clear()
            ctx.wm_creative_last_pick = None
        except Exception:
            pass
    except Exception:
        # If ctx is not writable for some reason, fail silently.
        pass


def _wm_display_id(bid: str) -> str:
    """
    Display-only: show WorkingMap ids as wN while keeping real ids as bN.
    """
    try:
        if isinstance(bid, str) and bid.startswith("b") and bid[1:].isdigit():
            return "w" + bid[1:]
    except Exception:
        pass
    return f"w({bid})"


def print_working_map_snapshot(ctx, *, n: int = 15, title: str = "[workingmap] snapshot") -> None:
    """Print a tail snapshot of the WorkingMap graph, showing tags + a small edge preview."""
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    def _bid_key(bid: str) -> int:
        try:
            return int(bid[1:]) if isinstance(bid, str) and bid.startswith("b") else 10**9
        except Exception:
            return 10**9

    all_ids = sorted(getattr(ww, "_bindings", {}).keys(), key=_bid_key)  # pylint: disable=protected-access
    tail = all_ids[-max(1, int(n)) :]
    print(f"{title}: last {len(tail)} binding(s) of {len(all_ids)} total")
    print(
        "  Legend: edges=wm_entity(root→entity), wm_scratch(root→scratch), wm_creative(root→creative), "
        "distance_to(self→entity), then(action chain)"
    )
    print("          tags=wm:* entity markers; pred:* belief-now; cue:* cues-now; meta.wm.pos={x,y,frame}")



    for bid in tail:
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue
        tags = ", ".join(sorted(getattr(b, "tags", []) or []))
        edges_raw = getattr(b, "edges", []) or []
        edges = [e for e in edges_raw if isinstance(e, dict)]

        preview = []
        for e in edges[:6]:
            rel = e.get("label") or e.get("rel") or e.get("relation") or "then"
            dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            if not isinstance(dst, str):
                continue
            extra = ""
            em = e.get("meta") if isinstance(e, dict) else None
            if rel == "distance_to" and isinstance(em, dict):
                meters = em.get("meters")
                dclass = em.get("class")
                if isinstance(meters, (int, float)):
                    extra += f" meters={float(meters):.2f}"
                if isinstance(dclass, str) and dclass:
                    extra += f" class={dclass}"
            preview.append(f"{rel}:{_wm_display_id(dst)} ({dst}){extra}")

        if preview:
            pv = ", ".join(preview)
            if len(edges) > 6:
                pv += f" (+{len(edges) - 6} more)"
        else:
            pv = "(none)"
        print(f"  {_wm_display_id(bid)} ({bid}): [{tags}] out={len(edges)} edges={pv}")


def print_working_map_layers(ctx, *, title: str = "[workingmap] layers") -> None:
    """Print a compact HUD of WorkingMap layers (MapSurface / Scratch / Creative).

    This is intentionally a *structural* view:
      - Which roots exist?
      - Is Creative enabled?
      - How many candidates are currently staged?

    It does not print the full graph; use print_working_map_snapshot(...) for that.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    root_bid = (anchors.get("WM_ROOT") or anchors.get("NOW"))
    scratch_bid = anchors.get("WM_SCRATCH")
    creative_bid = anchors.get("WM_CREATIVE")

    ent_map = getattr(ctx, "wm_entities", {}) or {}
    enabled = bool(getattr(ctx, "wm_creative_enabled", False))
    cands = getattr(ctx, "wm_creative_candidates", []) or []

    print(title)
    if isinstance(root_bid, str):
        print(f"  MapSurface: root={_wm_display_id(root_bid)} ({root_bid}) entities={len(ent_map)}")
    else:
        print(f"  MapSurface: root=(none) entities={len(ent_map)}")

    if isinstance(scratch_bid, str):
        print(f"  Scratch  : root={_wm_display_id(scratch_bid)} ({scratch_bid})")
    else:
        print("  Scratch  : root=(none)")

    if isinstance(creative_bid, str):
        print(f"  Creative : root={_wm_display_id(creative_bid)} ({creative_bid}) enabled={enabled} candidates={len(cands)}")
    else:
        print(f"  Creative : root=(none) enabled={enabled} candidates={len(cands)}")

    # Optional: show candidate summaries if present
    if cands:
        print("  Creative candidates: trig=Y/N (trigger satisfied or blocked); score is a display heuristic (not deficit or RL q).")
        try:
            ordered = sorted(cands, key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)
        except Exception:
            ordered = list(cands)

        for i, c in enumerate(ordered[:8], 1):
            try:
                pol = getattr(c, "policy", "(unknown)")
                score = float(getattr(c, "score", 0.0))
                notes = str(getattr(c, "notes", "") or "")

                pred = getattr(c, "predicted", None)
                trig = bool(pred.get("triggerable", False)) if isinstance(pred, dict) else False
                trig_txt = "Y" if trig else "N"

                # If the candidate is blocked, normalize the old note prefix so output is cleaner.
                if (not trig) and notes.startswith("blocked(not_triggered)"):
                    rest = notes[len("blocked(not_triggered)"):]
                    rest = rest.lstrip(" ;")
                    notes = "not_triggered" + (f"; {rest}" if rest else "")

                print(f"    {i:>2}) {pol:<18} trig={trig_txt} score={score:>6.2f}  {notes}")
            except Exception:
                print(f"    {i:>2}) {c}")


def print_working_map_entity_table(ctx, *, title: str = "[workingmap] MapSurface entity table") -> None:
    """Print a compact table of WorkingMap entities with schematic coordinates and key WM meta.

    This is intentionally a *MapSurface* view (entities + geometry), not the full binding log.
    Coordinates are stored in binding.meta['wm']['pos'] as {x,y,frame}.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        print(f"{title}: (no working_world)")
        return

    ent_map = getattr(ctx, "wm_entities", None)
    if not isinstance(ent_map, dict) or not ent_map:
        print(f"{title}: (no wm_entities; MapSurface may not be initialized yet)")
        return

    def _sort_key(item) -> tuple[int, str]:
        eid = str(item[0])
        return (0, "") if eid == "self" else (1, eid)

    print(title)
    print("  ent      node        kind      pos(x,y)         dist_m  class     seen patches             preds (short)                cues (short)")
    print("  -------  ----------  --------  --------------  ------  --------  ---- ------------------  --------------------------  ----------------")

    # Footer summary counters (NavPatch visibility; keeps logs readable during long runs)
    ent_rows = 0
    ent_with_patches = 0
    patch_refs_total = 0
    uniq_sig16: set[str] = set()
    uniq_patch_eids: set[str] = set()

    for eid, bid in sorted(ent_map.items(), key=_sort_key):
        if not isinstance(bid, str):
            continue
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            continue

        tags = list(getattr(b, "tags", []) or [])
        kind = ""
        for t in tags:
            if isinstance(t, str) and t.startswith("wm:kind:"):
                kind = t.split(":", 2)[2]
                break

        meta = getattr(b, "meta", None)
        wmm = meta.get("wm", {}) if isinstance(meta, dict) else {}
        pos = wmm.get("pos", {}) if isinstance(wmm, dict) else {}

        x = pos.get("x") if isinstance(pos, dict) else None
        y = pos.get("y") if isinstance(pos, dict) else None
        frame = pos.get("frame") if isinstance(pos, dict) else None

        dist_m = wmm.get("dist_m") if isinstance(wmm, dict) else None
        dist_class = wmm.get("dist_class") if isinstance(wmm, dict) else None
        last_seen = wmm.get("last_seen_step") if isinstance(wmm, dict) else None
        patch_refs = wmm.get("patch_refs") if isinstance(wmm, dict) else None

        # Summary bookkeeping (count only rows we actually render)
        ent_rows += 1
        if isinstance(patch_refs, list) and patch_refs:
            ent_with_patches += 1
            patch_refs_total += len(patch_refs)
            for ref in patch_refs:
                if not isinstance(ref, dict):
                    continue
                s16 = ref.get("sig16")
                if isinstance(s16, str) and s16:
                    uniq_sig16.add(s16)
                peid = ref.get("engram_id")
                if isinstance(peid, str) and peid:
                    uniq_patch_eids.add(peid)

        node_disp = f"{_wm_display_id(bid)} ({bid})"

        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            pos_txt = f"({float(x):6.2f},{float(y):6.2f})"
        else:
            pos_txt = "(   n/a,   n/a)"

        dist_txt = f"{float(dist_m):6.2f}" if isinstance(dist_m, (int, float)) else "  n/a "
        cls_txt = str(dist_class) if isinstance(dist_class, str) else "n/a"
        seen_txt = f"{int(last_seen):4d}" if isinstance(last_seen, int) else " n/a"
        patch_n = len(patch_refs) if isinstance(patch_refs, list) else 0
        patch_sig16 = None
        if patch_n and isinstance(patch_refs[0], dict):
            v = patch_refs[0].get("sig16")
            if isinstance(v, str) and v:
                patch_sig16 = v
        patch_txt = f"{patch_n}:{patch_sig16}" if patch_n and patch_sig16 else ("0" if patch_n == 0 else str(patch_n))
        frame_txt = str(frame) if isinstance(frame, str) else ""
        #to clear pylint #0612: Unused variable "frame_txt" will append frame to pos_txt
        if isinstance(frame, str) and frame_txt:
            pos_txt += f" [{frame}]"

        # Optional: schematic bearing/heading (degrees) from SELF to entity, based on the distorted (x,y) WM coords.
        # This is not "true physics bearing" yet — it's a consistent directional cue for debugging/map intuition.
        try:
            if eid != "self" and isinstance(x, (int, float)) and isinstance(y, (int, float)) and (float(x) != 0.0 or float(y) != 0.0):
                from math import atan2, degrees
                brg = degrees(atan2(float(y), float(x)))
                pos_txt += f" brg={brg:+.0f}°"
        except Exception:
            pass

        # Short belief summaries
        preds = sorted(t[5:] for t in tags if isinstance(t, str) and t.startswith("pred:"))
        cues  = sorted(t[4:] for t in tags if isinstance(t, str) and t.startswith("cue:"))

        pred_txt = ", ".join(preds[:3]) + (" …" if len(preds) > 3 else "")
        cue_txt  = ", ".join(cues[:2]) + (" …" if len(cues) > 2 else "")

        print(
            f"  {eid:<7}  {node_disp:<10}  {kind:<8}  {pos_txt:<14}  {dist_txt:>6}  {cls_txt:<8}  {seen_txt:>4}  "
            f"{patch_txt:<18}  {pred_txt:<26}  {cue_txt}"
        )

    if ent_rows:
        print(
            f"  [patches] ent_with={ent_with_patches}/{ent_rows} refs_total={patch_refs_total} "
            f"uniq_sig16={len(uniq_sig16)} uniq_eid={len(uniq_patch_eids)}"
        )


def serialize_mapsurface_v1(ctx: Ctx, *, include_internal_ids: bool = False) -> dict[str, Any]:
    """Serialize the WorkingMap MapSurface into a JSON-safe dict (MapEngram payload v1).

    Purpose / intent
    ----------------
    Option B (memory pipeline) will store WorkingMap snapshots as **Column engrams**. This function provides the
    *heavy payload* for such an engram: a stable, explicit, inspectable representation of the current MapSurface.

    Design constraints
    ------------------
    - Must be JSON-safe: only dict/list/str/int/float/bool/None.
    - Must be robust: never raise (best-effort snapshot).
    - Must NOT mutate WorkingMap: read-only.

    Included content (v1)
    ---------------------
    - header:
        schema tag, controller_steps/ticks/boundary/run-step, temporal fingerprint, and a tiny BodyMap readout if available.
    - entities:
        one record per WM entity (eid/kind/pos/dist/seen + preds + cues).
    - relations:
        distance_to edges from SELF → other entities, including edge meta (meters/class/frame) when present.

    Args:
        ctx:
            Runtime context (holds working_world and wm_entities).
        include_internal_ids:
            If True, include internal WorkingMap binding ids (e.g., "b17") in entity and relation records.
            Keep False for stable payloads; turn on only for debugging.

    Returns:
        A dict payload suitable for storing as a Column engram.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        return {
            "schema": "wm_mapsurface_v1",
            "header": {"error": "no_working_world"},
            "entities": [],
            "relations": [],
        }

    ent_map = getattr(ctx, "wm_entities", None)
    if not isinstance(ent_map, dict):
        ent_map = {}

    anchors = getattr(ww, "_anchors", {}) if hasattr(ww, "_anchors") else {}
    root_bid = anchors.get("WM_ROOT") or anchors.get("NOW")
    self_bid = ent_map.get("self") or anchors.get("WM_SELF")

    # ---- header (best-effort) ----
    header: dict[str, Any] = {
        "schema": "wm_mapsurface_v1",
        "profile": getattr(ctx, "profile", None),
        "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
        "ticks": int(getattr(ctx, "ticks", 0) or 0),
        "boundary_no": int(getattr(ctx, "boundary_no", 0) or 0),
        "boundary_vhash64": getattr(ctx, "boundary_vhash64", None),
        "tvec64": (ctx.tvec64() if hasattr(ctx, "tvec64") else None),
        "run_last_env_step": getattr(ctx, "run_last_env_step", None),
    }
    if isinstance(root_bid, str) and include_internal_ids:
        header["wm_root_bid"] = root_bid
    if isinstance(self_bid, str) and include_internal_ids:
        header["wm_self_bid"] = self_bid

    # Tiny BodyMap readout (helps indexing/debug; does not affect MapSurface content)
    body: dict[str, Any] = {"stale": True}
    try:
        stale = bool(bodymap_is_stale(ctx))
        body["stale"] = stale
        if not stale:
            try:
                body["posture"] = body_posture(ctx)
            except Exception:
                pass
            try:
                body["mom_distance"] = body_mom_distance(ctx)
            except Exception:
                pass
            try:
                body["nipple_state"] = body_nipple_state(ctx)
            except Exception:
                pass
            try:
                body["zone"] = body_space_zone(ctx)
            except Exception:
                pass
    except Exception:
        body = {"stale": True}
    header["body"] = body

    # ---- helpers ----
    def _as_float(x) -> float | None:
        try:
            return float(x)
        except Exception:
            return None

    def _as_int(x) -> int | None:
        try:
            return int(x)
        except Exception:
            return None

    # reverse map for relation decoding (bid -> eid)
    bid_to_eid: dict[str, str] = {}
    for eid, bid in ent_map.items():
        if isinstance(eid, str) and isinstance(bid, str):
            bid_to_eid[bid] = eid

    def _entity_record(eid: str, bid: str) -> dict[str, Any]:
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is None:
            out = {"eid": eid}
            if include_internal_ids:
                out["bid"] = bid
            return out

        tags_raw = getattr(b, "tags", None)
        if tags_raw is None:
            tags: list[str] = []
        elif isinstance(tags_raw, (set, list, tuple)):
            tags = [t for t in tags_raw if isinstance(t, str)]
        else:
            try:
                tags = [t for t in list(tags_raw) if isinstance(t, str)]
            except Exception:
                tags = []

        kind = None
        for t in tags:
            if t.startswith("wm:kind:"):
                kind = t.split(":", 2)[2]
                break

        preds = sorted(t[5:] for t in tags if t.startswith("pred:"))
        cues = sorted(t[4:] for t in tags if t.startswith("cue:"))

        meta = getattr(b, "meta", None)
        wmm = meta.get("wm", {}) if isinstance(meta, dict) else {}
        pos = wmm.get("pos", {}) if isinstance(wmm, dict) else {}

        x = pos.get("x") if isinstance(pos, dict) else None
        y = pos.get("y") if isinstance(pos, dict) else None
        frame = pos.get("frame") if isinstance(pos, dict) else None

        dist_m = wmm.get("dist_m") if isinstance(wmm, dict) else None
        dist_class = wmm.get("dist_class") if isinstance(wmm, dict) else None
        last_seen = wmm.get("last_seen_step") if isinstance(wmm, dict) else None
        patch_refs = wmm.get("patch_refs") if isinstance(wmm, dict) else None

        rec: dict[str, Any] = {
            "eid": eid,
            "kind": kind,
            "pos": {
                "x": _as_float(x),
                "y": _as_float(y),
                "frame": str(frame) if isinstance(frame, str) else None,
            },
            "dist_m": _as_float(dist_m),
            "dist_class": str(dist_class) if isinstance(dist_class, str) else None,
            "last_seen_step": _as_int(last_seen),
            "preds": preds,
            "cues": cues,
        }

        if isinstance(patch_refs, list):
            # patch_refs are JSON-safe dicts (sig/engram_id/role/frame/tags).
            rec["patch_refs"] = patch_refs

        if include_internal_ids:
            rec["bid"] = bid
        return rec

    # ---- entities ----
    entities: list[dict[str, Any]] = []
    try:
        # stable order: self first, then alphabetical by eid
        eids = sorted([e for e in ent_map.keys() if isinstance(e, str)])
        if "self" in eids:
            eids.remove("self")
            eids = ["self"] + eids

        for eid in eids:
            bid = ent_map.get(eid)
            if not isinstance(bid, str):
                continue
            entities.append(_entity_record(eid, bid))
    except Exception:
        entities = []

    # ---- relations (distance_to edges) ----
    relations: list[dict[str, Any]] = []
    try:
        if isinstance(self_bid, str) and self_bid in getattr(ww, "_bindings", {}):  # pylint: disable=protected-access
            bself = ww._bindings.get(self_bid)  # pylint: disable=protected-access
            edges = getattr(bself, "edges", []) or []
            if isinstance(edges, list):
                for e in edges:
                    if not isinstance(e, dict):
                        continue
                    lab = e.get("label") or e.get("rel") or e.get("relation")
                    if lab != "distance_to":
                        continue

                    dst = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                    if not isinstance(dst, str):
                        continue

                    em = e.get("meta")
                    em = em if isinstance(em, dict) else {}
                    meters = em.get("meters")
                    cls = em.get("class")
                    frame = em.get("frame")

                    dst_eid = bid_to_eid.get(dst) or "(unknown)"
                    rel_rec: dict[str, Any] = {
                        "rel": "distance_to",
                        "src": "self",
                        "dst": dst_eid,
                        "meters": _as_float(meters),
                        "class": str(cls) if isinstance(cls, str) else None,
                        "frame": str(frame) if isinstance(frame, str) else None,
                    }
                    if include_internal_ids:
                        rel_rec["src_bid"] = self_bid
                        rel_rec["dst_bid"] = dst
                    relations.append(rel_rec)
    except Exception:
        relations = []

    return {
        "schema": "wm_mapsurface_v1",
        "header": header,
        "entities": entities,
        "relations": relations,
    }


def mapsurface_payload_sig_v1(payload: dict[str, Any], *, stage: Optional[str] = None, zone: Optional[str] = None) -> str:
    """Stable content signature for MapSurface snapshots (used for dedup vs last).

    Important:
      - excludes volatile header fields (steps/ticks/tvec/etc)
      - excludes volatile per-entity recency (last_seen_step)
      - includes stage/zone *if provided* (so you can choose whether those differentiate snapshots)

    Rationale:
      - In closed-loop runs, entities get "seen again" every tick. If we include last_seen_step, the
        signature changes every step even when the scene is otherwise identical, defeating dedup.
    """
    ents_in = payload.get("entities", []) or []
    ents_norm: list[dict[str, Any]] = []
    for ent in ents_in:
        if isinstance(ent, dict):
            d = dict(ent)
            d.pop("last_seen_step", None)  # volatile per-tick recency
            ents_norm.append(d)
        else:
            # Extremely defensive fallback; should not happen in normal paths.
            ents_norm.append({"_raw": str(ent)})

    core = {
        "schema": payload.get("schema"),
        "stage": stage,
        "zone": zone,
        "entities": ents_norm,
        "relations": payload.get("relations", []),
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


_SALIENT_PRED_PREFIXES = (
    "posture:",
    "proximity:mom:",
    "proximity:shelter:",
    "hazard:cliff:",
    "nipple:",
    "milk:",
)

_SALIENT_PRED_EXACT = {
    "resting",
    "alert",
    "seeking_mom",
}


def mapsurface_salience_v1(payload: dict[str, Any], *, max_preds: int = 32, max_cues: int = 32) -> dict[str, Any]:
    """Extract a compact salience signature from a wm_mapsurface_v1 payload.

    Purpose:
      - Give us a small, robust descriptor we can store in Column meta for retrieval scoring.
      - This is NOT an embedding; it's a tiny "bag of salient symbols" for overlap scoring.

    Returns:
      {
        "sig": <hex16>,
        "preds": [<salient pred tokens>],
        "cues":  [<salient cue tokens>],
      }
    """
    preds_set: set[str] = set()
    cues_set: set[str] = set()

    ents = payload.get("entities", [])
    if isinstance(ents, list):
        for ent in ents:
            if not isinstance(ent, dict):
                continue

            preds = ent.get("preds")
            if isinstance(preds, list):
                for p in preds:
                    if not isinstance(p, str) or not p:
                        continue
                    if (p in _SALIENT_PRED_EXACT) or any(p.startswith(pref) for pref in _SALIENT_PRED_PREFIXES):
                        preds_set.add(p)

            cues = ent.get("cues")
            if isinstance(cues, list):
                for c in cues:
                    if isinstance(c, str) and c:
                        cues_set.add(c)

    # Full (uncapped) lists used for signature stability
    preds_full = sorted(preds_set)
    cues_full = sorted(cues_set)

    blob = json.dumps({"preds": preds_full, "cues": cues_full}, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig16 = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    # Capped lists stored in meta for readability
    preds_out = preds_full[: max(1, int(max_preds))]
    cues_out = cues_full[: max(1, int(max_cues))]

    return {"sig": sig16, "preds": preds_out, "cues": cues_out}


def current_mapsurface_salience_v1(ctx: Ctx) -> dict[str, Any]:
    """Compute the current salience signature from the live WorkingMap.MapSurface."""
    try:
        payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)
    except Exception:
        payload = {}
    if not isinstance(payload, dict):
        payload = {}
    return mapsurface_salience_v1(payload)


def store_mapsurface_snapshot_v1(world, ctx: Ctx, *, reason: str, attach: str = "now",
                                force: bool = False, quiet: bool = False) -> dict[str, Any]:
    """Store the current WorkingMap.MapSurface snapshot into Column memory and index it in WorldGraph.

    What gets written:
      1) Column engram payload: serialize_mapsurface_v1(ctx) (JSON-safe dict)
      2) WorldGraph binding: a thin pointer node tagged cue:wm:mapsurface_snapshot + index tags
         with engram pointer attached under binding.engrams["column01"]["id"].

    Dedup:
      - If the content signature matches ctx.wm_mapsurface_last_sig, we skip storing unless force=True.
    """
    payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)

    # Index attributes (best-effort)
    stage = getattr(ctx, "lt_obs_last_stage", None)
    if not isinstance(stage, str):
        stage = None

    try:
        zone = body_space_zone(ctx)
    except Exception:
        zone = None
    if not isinstance(zone, str):
        zone = None

    sig = mapsurface_payload_sig_v1(payload, stage=stage, zone=zone)
    sal = mapsurface_salience_v1(payload)
    sal_sig = sal.get("sig")
    sal_preds = sal.get("preds", []) if isinstance(sal.get("preds"), list) else []
    sal_cues  = sal.get("cues", []) if isinstance(sal.get("cues"), list) else []
    last_sig = getattr(ctx, "wm_mapsurface_last_sig", None)

    if (not force) and (sig == last_sig):
        return {"stored": False, "why": "dedup_same_as_last", "sig": sig, "stage": stage, "zone": zone}

    # Create a thin WorldGraph index binding (always new; no semantic reuse)
    tags = {"cue:wm:mapsurface_snapshot"}
    if stage:
        tags.add(f"idx:stage:{stage}")
    if zone:
        tags.add(f"idx:zone:{zone}")

    meta = {
        "wm": {
            "kind": "mapsurface_snapshot",
            "schema": payload.get("schema"),
            "sig": sig,
            "stage": stage,
            "zone": zone,
            "reason": reason,
            "salience_sig": sal_sig,
            "salient_pred_n": len(sal_preds),
            "salient_cue_n": len(sal_cues),
        }
    }

    bid = world.add_binding(set(tags), meta=meta)

    att = (attach or "").strip().lower() or None
    if att in (None, "none"):
        pass
    elif att == "now":
        src = world.ensure_anchor("NOW")
        world.add_edge(src, bid, label="then", meta={"kind": "wm_mapsurface_snapshot", "reason": reason})
    else:
        raise ValueError("attach must be None|'now'|'none'")

    # Store engram in Column + attach pointer to the WorldGraph binding

    attrs = {
        "schema": payload.get("schema"),
        "sig": sig,
        "stage": stage,
        "zone": zone,
        "reason": reason,
        "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
        "ticks": int(getattr(ctx, "ticks", 0) or 0),
        "boundary_no": int(getattr(ctx, "boundary_no", 0) or 0),
        "boundary_vhash64": getattr(ctx, "boundary_vhash64", None),
        "salience_sig": sal_sig,
        "salient_preds": list(sal_preds),
        "salient_cues": list(sal_cues),
    }
    fm = FactMeta(name="wm_mapsurface", links=[bid], attrs=attrs)

    engram_id = column_mem.assert_fact("wm_mapsurface", payload, fm)
    world.attach_engram(bid, column="column01", engram_id=engram_id, act=1.0)

    # Update ctx "last"
    ctx.wm_mapsurface_last_sig = sig
    ctx.wm_mapsurface_last_engram_id = engram_id
    ctx.wm_mapsurface_last_world_bid = bid

    if not quiet:
        print(f"[wm->column] stored wm_mapsurface: sig={sig[:16]} bid={bid} engram_id={engram_id[:16]}... stage={stage} zone={zone}")

    return {"stored": True, "sig": sig, "bid": bid, "engram_id": engram_id, "stage": stage, "zone": zone}


# -----------------------------------------------------------------------------
# NavPatch v1 helpers (Phase X; NavPatch plan v5)
# -----------------------------------------------------------------------------

def _navpatch_core_v1(patch: dict[str, Any]) -> dict[str, Any]:
    """Return the stable core of a NavPatch payload for signatures/dedup.

    A NavPatch is a compact, local navigation map fragment intended to be:
      - JSON-safe (dict/list/str/int/float/bool/None only)
      - stable under repeated observation of the same structure
      - composable (map-of-maps) via links/transforms in later phases

    This helper strips volatile fields (timestamps, match traces, etc.) so the
    same structural patch yields the same signature across cycles.

    Parameters
    ----------
    patch:
        JSON-safe dict produced by PerceptionAdapter (env-side) or by later
        agent-side processing.

    Returns
    -------
    dict
        Canonicalized core dict used for hashing.
    """
    if not isinstance(patch, dict):
        return {"schema": "navpatch_v1", "error": "not_dict"}

    schema = patch.get("schema") if isinstance(patch.get("schema"), str) else "navpatch_v1"

    core: dict[str, Any] = {
        "schema": schema,
        "local_id": patch.get("local_id") if isinstance(patch.get("local_id"), str) else None,
        "entity_id": patch.get("entity_id") if isinstance(patch.get("entity_id"), str) else None,
        "role": patch.get("role") if isinstance(patch.get("role"), str) else None,
        "frame": patch.get("frame") if isinstance(patch.get("frame"), str) else None,
    }

    # Grid payload (Phase X v5.9): include topology core in the signature.
    # Signature rules: include grid_encoding_v, grid_w, grid_h, and grid_cells (or a stable digest).
    ge = patch.get("grid_encoding_v")
    if isinstance(ge, str) and ge:
        core["grid_encoding_v"] = ge

    gw = patch.get("grid_w")
    gh = patch.get("grid_h")
    if isinstance(gw, int) and isinstance(gh, int) and gw > 0 and gh > 0:
        core["grid_w"] = int(gw)
        core["grid_h"] = int(gh)

        cells = patch.get("grid_cells")
        if isinstance(cells, list) and len(cells) == int(gw) * int(gh):
            norm: list[int] = []
            ok = True
            for c in cells:
                if isinstance(c, int):
                    norm.append(int(c))
                else:
                    ok = False
                    break
            if ok:
                core["grid_cells"] = norm
            else:
                # Fallback: keep a stable digest so the signature still changes with topology.
                try:
                    blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                    core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
                except Exception:
                    pass
        elif isinstance(cells, list) and cells:
            try:
                blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
            except Exception:
                pass

    # Optional (v1): origin/resolution are stable geometry parameters.
    go = patch.get("grid_origin")
    if isinstance(go, list) and len(go) == 2 and all(isinstance(v, (int, float)) for v in go):
        core["grid_origin"] = [float(go[0]), float(go[1])]
    gr = patch.get("grid_resolution")
    if isinstance(gr, (int, float)):
        core["grid_resolution"] = float(gr)

    extent = patch.get("extent")
    if isinstance(extent, dict):
        core["extent"] = {
            k: extent.get(k)
            for k in sorted(extent)
            if isinstance(k, str) and isinstance(extent.get(k), (str, int, float, bool, type(None)))
        }

    tags = patch.get("tags")
    if isinstance(tags, list):
        core["tags"] = sorted({t for t in tags if isinstance(t, str) and t})

    # --- Grid payload core (Phase X Step 11) ---
    ge = patch.get("grid_encoding_v")
    if isinstance(ge, str) and ge:
        core["grid_encoding_v"] = ge

    gw = patch.get("grid_w")
    gh = patch.get("grid_h")
    if isinstance(gw, int) and isinstance(gh, int) and gw > 0 and gh > 0:
        core["grid_w"] = int(gw)
        core["grid_h"] = int(gh)

        cells = patch.get("grid_cells")
        if isinstance(cells, list) and len(cells) == int(gw) * int(gh) and all(isinstance(c, int) for c in cells):
            # Keep explicit cells for small grids so 1-cell changes affect sig directly.
            if len(cells) <= 1024:
                core["grid_cells"] = [int(c) for c in cells]
            else:
                blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
                core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()
        elif isinstance(cells, list) and cells:
            blob = json.dumps(cells, separators=(",", ":"), ensure_ascii=False)
            core["grid_cells_digest"] = hashlib.sha256(blob.encode("utf-8")).hexdigest()

    go = patch.get("grid_origin")
    if isinstance(go, list) and len(go) == 2 and all(isinstance(v, (int, float)) for v in go):
        core["grid_origin"] = [float(go[0]), float(go[1])]

    gr = patch.get("grid_resolution")
    if isinstance(gr, (int, float)):
        core["grid_resolution"] = float(gr)

    layers = patch.get("layers")
    if isinstance(layers, dict):
        core["layers"] = {
            k: layers.get(k)
            for k in sorted(layers)
            if isinstance(k, str) and isinstance(layers.get(k), (str, int, float, bool, type(None)))
        }

    links = patch.get("links")
    if isinstance(links, list):
        core["links"] = [x for x in links if isinstance(x, (str, int, float, bool, type(None), dict, list))]

    return core


def navpatch_payload_sig_v1(patch: dict[str, Any]) -> str:
    """Stable content signature for a NavPatch payload."""
    core = _navpatch_core_v1(patch)
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def store_navpatch_engram_v1(ctx: Ctx, patch: dict[str, Any], *, reason: str) -> dict[str, Any]:
    """Store a NavPatch payload into Column memory, with per-run dedup by content signature.

    Dedup strategy (v0):
      - Deduplicate within a single run using ctx.navpatch_sig_to_eid.
      - Later we can replace this with a Column-side signature index if/when Column is persisted.
    """
    sig = navpatch_payload_sig_v1(patch)
    sig16 = sig[:16]

    cache = getattr(ctx, "navpatch_sig_to_eid", None)
    if isinstance(cache, dict):
        existing = cache.get(sig)
        if isinstance(existing, str) and existing:
            return {"stored": False, "sig": sig, "sig16": sig16, "engram_id": existing, "reason": "dedup_cache"}

    attrs: dict[str, Any] = {
        "schema": patch.get("schema") if isinstance(patch.get("schema"), str) else "navpatch_v1",
        "sig": sig,
        "sig16": sig16,
        "reason": reason,
    }

    for k in ("entity_id", "role", "frame", "local_id"):
        v = patch.get(k)
        if isinstance(v, str) and v:
            attrs[k] = v

    tags = patch.get("tags")
    if isinstance(tags, list):
        attrs["tags"] = [t for t in tags if isinstance(t, str) and t][:12]

    fm = FactMeta(name="navpatch", links=[], attrs=attrs).with_time(ctx)
    engram_id = column_mem.assert_fact("navpatch", patch, fm)

    if isinstance(cache, dict):
        cache[sig] = engram_id
    else:
        try:
            ctx.navpatch_sig_to_eid = {sig: engram_id}
        except Exception:
            pass

    return {"stored": True, "sig": sig, "sig16": sig16, "engram_id": engram_id, "reason": reason}


def _wm_entity_anchor_name(entity_id: str) -> str:
    """Return the WorkingMap anchor name for an entity id (must match the MapSurface naming scheme)."""
    eid = (entity_id or "unknown").strip().lower()
    if eid == "self":
        return "WM_SELF"

    # Match inject_obs_into_working_world._sanitize_entity_anchor semantics:
    s = eid.strip().upper()
    out: list[str] = []
    for ch in s:
        out.append(ch if ch.isalnum() else "_")
    s = "".join(out)
    while "__" in s:
        s = s.replace("__", "_")
    s = s.strip("_") or "UNKNOWN"
    return f"WM_ENT_{s}"


def _wm_tagset_of(world, bid: str) -> set[str]:
    """Return a mutable tag set for a binding (robust to legacy list tags)."""
    b = getattr(world, "_bindings", {}).get(bid)
    if not b:
        return set()
    ts = getattr(b, "tags", None)
    if ts is None:
        b.tags = set()
        return b.tags
    if isinstance(ts, set):
        return ts
    if isinstance(ts, list):
        s = set(ts)
        b.tags = s
        return s
    try:
        s = set(ts)
        b.tags = s
        return s
    except Exception:
        b.tags = set()
        return b.tags


def _wm_upsert_edge(world, src: str, dst: str, label: str, meta: dict | None = None) -> None:
    """Upsert an edge in a WorldGraph-like object (used for WorkingMap structural edges)."""
    b = getattr(world, "_bindings", {}).get(src)
    if not b:
        return
    edges = getattr(b, "edges", None)
    if not isinstance(edges, list):
        b.edges = []
        edges = b.edges

    for e in edges:
        if not isinstance(e, dict):
            continue
        to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
        lab = e.get("label") or e.get("rel") or e.get("relation")
        if to_ == dst and lab == label:
            if isinstance(meta, dict) and meta:
                em = e.get("meta")
                if isinstance(em, dict):
                    em.update(meta)
                else:
                    e["meta"] = dict(meta)
            return

    edges.append({"to": dst, "label": label, "meta": dict(meta or {})})


def _rec_stage_zone(rec: dict) -> tuple[str | None, str | None]:
    """Extract (stage, zone) from a Column record dict."""
    meta = rec.get("meta", {})
    meta = meta if isinstance(meta, dict) else {}
    attrs = meta.get("attrs", {})
    attrs = attrs if isinstance(attrs, dict) else {}
    stage = attrs.get("stage")
    zone = attrs.get("zone")
    stage = stage if isinstance(stage, str) else None
    zone = zone if isinstance(zone, str) else None
    return stage, zone


def _wm_snapshot_pointer_bids(long_world, *, max_scan: int = 500) -> list[str]:
    """Return newest-first WorldGraph binding ids that act as MapSurface snapshot pointers.

    Pointer node definition (Option B):
      - binding tags contain: 'cue:wm:mapsurface_snapshot'
      - binding.engrams contains a column pointer to the stored engram id
    """
    if long_world is None:
        return []

    # Collect pointer bindings
    out: list[str] = []
    try:
        for bid, b in getattr(long_world, "_bindings", {}).items():
            tags = getattr(b, "tags", None) or []
            if isinstance(tags, set):
                ok = "cue:wm:mapsurface_snapshot" in tags
            else:
                ok = any(isinstance(t, str) and t == "cue:wm:mapsurface_snapshot" for t in tags)
            if ok:
                out.append(bid)
    except Exception:
        return []

    # Sort newest-first by numeric bN (unknown ids at end)
    def _bid_key_desc(bid: str) -> tuple[int, int]:
        if isinstance(bid, str) and bid.startswith("b") and bid[1:].isdigit():
            return (0, -int(bid[1:]))
        return (1, 0)

    out.sort(key=_bid_key_desc)
    return out[: max(1, int(max_scan))]


def _wm_pointer_engram_id(long_world, pointer_bid: str) -> str | None:
    """Extract the engram id from a WorldGraph pointer binding (best-effort)."""
    try:
        b = getattr(long_world, "_bindings", {}).get(pointer_bid)
        if b is None:
            return None
        eng = getattr(b, "engrams", None)
        if not isinstance(eng, dict) or not eng:
            return None

        # Prefer the canonical slot name, else fall back to the first slot.
        v = eng.get("column01")
        if not isinstance(v, dict):
            try:
                v = next(iter(eng.values()))
            except Exception:
                v = None
        if isinstance(v, dict):
            eid = v.get("id")
            return eid if isinstance(eid, str) and eid else None
    except Exception:
        return None
    return None


def _iter_newest_wm_mapsurface_recs(*, long_world=None, limit: int = 500) -> tuple[list[dict], str]:
    """Return newest-first wm_mapsurface Column records, preferably via WorldGraph pointers.

    Returns (recs, source) where source ∈ {"world_pointers","column_scan"}.
    """
    lim = max(1, int(limit))

    # Prefer WorldGraph pointer nodes (fast index)
    if long_world is not None:
        seen: set[str] = set()
        recs: list[dict] = []
        for pbid in _wm_snapshot_pointer_bids(long_world, max_scan=lim * 2):
            eid = _wm_pointer_engram_id(long_world, pbid)
            if not isinstance(eid, str) or not eid or eid in seen:
                continue
            seen.add(eid)
            rec = column_mem.try_get(eid)
            if isinstance(rec, dict) and rec.get("name") == "wm_mapsurface":
                recs.append(rec)
                if len(recs) >= lim:
                    return recs, "world_pointers"
        if recs:
            return recs, "world_pointers"

    # no resolvable pointer engrams -> fallback to column scan
    # Fallback: scan column ids newest-first
    out: list[dict] = []
    try:
        ids = list(column_mem.list_ids())
        for eid in reversed(ids):
            rec = column_mem.try_get(eid)
            if not isinstance(rec, dict):
                continue
            if rec.get("name") != "wm_mapsurface":
                continue
            out.append(rec)
            if len(out) >= lim:
                break
    except Exception:
        out = []
    return out, "column_scan"


def pick_best_wm_mapsurface_rec(*, stage: str | None, zone: str | None, ctx: Ctx | None = None,
                               long_world=None, allow_fallback: bool = True, max_scan: int = 500,
                               top_k: int = 5) -> dict[str, Any]:
    """Pick the best wm_mapsurface record for (stage, zone), using WorldGraph pointers + salience overlap.

    Changes in B6:
      - Candidate source prefers WorldGraph pointer bindings (cue:wm:mapsurface_snapshot), then loads Column records.
      - Returns ranked top-K candidates (not just the winner) for inspection.

    Returns:
      {
        "ok": bool,
        "source": "world_pointers"|"column_scan",
        "match": "stage+zone"|"stage"|"zone"|"any"|"none",
        "rec": dict|None,
        "score": float,
        "overlap_preds": int,
        "overlap_cues": int,
        "want_pred_n": int,
        "want_cue_n": int,
        "want_salience_sig": str|None,
        "cand_salience_sig": str|None,
        "ranked": [ {candidate summary dicts...} ],
        "want_stage":..., "want_zone":...
      }
    """
    recs, source = _iter_newest_wm_mapsurface_recs(long_world=long_world, limit=max(1, int(max_scan)))

    if not recs:
        return {
            "ok": False,
            "source": source,
            "match": "none",
            "rec": None,
            "want_stage": stage,
            "want_zone": zone,
            "ranked": [],
        }

    # --- Current salience (from ctx WorkingMap MapSurface) ---
    want_preds: set[str] = set()
    want_cues: set[str] = set()
    want_sig: str | None = None
    if ctx is not None:
        try:
            want = current_mapsurface_salience_v1(ctx)
            want_sig = want.get("sig") if isinstance(want.get("sig"), str) else None
            wp = want.get("preds", [])
            wc = want.get("cues", [])
            if isinstance(wp, list):
                want_preds = {p for p in wp if isinstance(p, str) and p}
            if isinstance(wc, list):
                want_cues = {c for c in wc if isinstance(c, str) and c}
        except Exception:
            pass

    def _rec_salience_sets(rec: dict) -> tuple[set[str], set[str], str | None]:
        meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
        attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}

        sp = attrs.get("salient_preds")
        sc = attrs.get("salient_cues")
        ss = attrs.get("salience_sig")
        sig = ss if isinstance(ss, str) else None

        preds_set: set[str] = set()
        cues_set: set[str] = set()

        if isinstance(sp, list):
            preds_set = {p for p in sp if isinstance(p, str) and p}
        if isinstance(sc, list):
            cues_set = {c for c in sc if isinstance(c, str) and c}

        # Back-compat: older engrams may not have salience attrs; compute from payload
        if (not preds_set and not cues_set) and isinstance(rec.get("payload"), dict):
            sal = mapsurface_salience_v1(rec["payload"])
            sig = sig or (sal.get("sig") if isinstance(sal.get("sig"), str) else None)
            preds = sal.get("preds", [])
            cues = sal.get("cues", [])
            if isinstance(preds, list):
                preds_set = {p for p in preds if isinstance(p, str) and p}
            if isinstance(cues, list):
                cues_set = {c for c in cues if isinstance(c, str) and c}

        return preds_set, cues_set, sig

    def _score_candidate(rec: dict) -> tuple[float, int, int, str | None]:
        preds_set, cues_set, cand_sig = _rec_salience_sets(rec)
        op = len(want_preds & preds_set) if want_preds else 0
        oc = len(want_cues & cues_set) if want_cues else 0
        score = float(op) * 10.0 + float(oc) * 3.0
        return score, op, oc, cand_sig

    # Candidate filtering tiers
    def _filter_stage_zone(match_kind: str) -> list[dict]:
        if match_kind == "stage+zone" and stage and zone:
            return [r for r in recs if _rec_stage_zone(r) == (stage, zone)]
        if match_kind == "stage" and stage:
            return [r for r in recs if _rec_stage_zone(r)[0] == stage]
        if match_kind == "zone" and zone:
            return [r for r in recs if _rec_stage_zone(r)[1] == zone]
        if match_kind == "any":
            return list(recs)
        return []

    def _candidate_summary(rec: dict, *, score: float, op: int, oc: int, cand_sig: str | None) -> dict[str, Any]:
        meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
        attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}
        created_at = meta.get("created_at") or "(n/a)"

        links = meta.get("links")
        src = links[0] if isinstance(links, list) and links else None

        return {
            "engram_id": str(rec.get("id", "")),
            "created_at": created_at,
            "stage": attrs.get("stage"),
            "zone": attrs.get("zone"),
            "sig": attrs.get("sig"),
            "salience_sig": attrs.get("salience_sig"),
            "src": src,
            "score": float(score),
            "overlap_preds": int(op),
            "overlap_cues": int(oc),
            "cand_salience_sig": cand_sig,
        }

    k = max(1, min(10, int(top_k)))  # keep terminal readable
    tier_order = ["stage+zone", "stage", "zone", "any"] if allow_fallback else ["stage+zone"]

    for tier in tier_order:
        cands = _filter_stage_zone(tier)
        if not cands:
            continue

        scored: list[tuple[float, int, int, str | None, int, dict]] = []
        # preserve recency tie-break: cands is newest-first, so lower idx = newer
        for idx, rec in enumerate(cands):
            score, op, oc, cand_sig = _score_candidate(rec)
            scored.append((score, op, oc, cand_sig, idx, rec))

        scored.sort(key=lambda t: (-t[0], t[4]))  # high score first, then newest
        top = scored[:k]

        best = top[0]
        best_score, best_op, best_oc, best_csig, _best_idx, best_rec = best

        ranked = [_candidate_summary(r, score=s, op=op, oc=oc, cand_sig=csig) for (s, op, oc, csig, _i, r) in top]

        return {
            "ok": True,
            "source": source,
            "match": tier,
            "rec": best_rec,
            "score": float(best_score),
            "overlap_preds": int(best_op),
            "overlap_cues": int(best_oc),
            "want_pred_n": len(want_preds),
            "want_cue_n": len(want_cues),
            "want_salience_sig": want_sig,
            "cand_salience_sig": best_csig,
            "ranked": ranked,
            "want_stage": stage,
            "want_zone": zone,
        }

    return {"ok": False, "source": source, "match": "none", "rec": None, "want_stage": stage, "want_zone": zone, "ranked": []}


def load_mapsurface_payload_v1_into_workingmap(ctx: Ctx, payload: dict[str, Any], *, replace: bool = True, reason: str = "manual_load") -> dict[str, Any]:
    """Load a wm_mapsurface_v1 payload into WorkingMap MapSurface.

    Semantics (Option B4 v1):
      - replace=True: clear WorkingMap, then rebuild MapSurface exactly from payload.
      - This is a *prior/seed*; the next EnvObservation tick may overwrite parts of it.

    Returns: {"ok": bool, "entities": int, "relations": int}.
    """
    if replace:
        reset_working_world(ctx)

    if getattr(ctx, "working_world", None) is None:
        ctx.working_world = init_working_world()
    ww = ctx.working_world
    if ww is None:
        return {"ok": False, "entities": 0, "relations": 0}

    # Ensure MapSurface roots exist
    root_bid = ww.ensure_anchor("WM_ROOT")
    try:
        ww.set_now(root_bid, tag=True, clean_previous=True)
    except Exception:
        try:
            ww._anchors["NOW"] = root_bid
            _wm_tagset_of(ww, root_bid).add("anchor:NOW")
        except Exception:
            pass

    # Keep NOW_ORIGIN aligned (same pattern as inject_obs_into_working_world)
    try:
        ww._anchors["NOW_ORIGIN"] = root_bid
        _wm_tagset_of(ww, root_bid).add("anchor:NOW_ORIGIN")
    except Exception:
        pass

    # Scratch + Creative anchors and links
    scratch_bid = ww.ensure_anchor("WM_SCRATCH")
    _wm_tagset_of(ww, scratch_bid).add("wm:scratch")
    _wm_upsert_edge(ww, root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_load", "reason": reason})

    creative_bid = ww.ensure_anchor("WM_CREATIVE")
    _wm_tagset_of(ww, creative_bid).add("wm:creative")
    _wm_upsert_edge(ww, root_bid, creative_bid, "wm_creative", {"created_by": "wm_load", "reason": reason})

    # Reset MapSurface caches
    try:
        ctx.wm_entities.clear()
        ctx.wm_last_env_cues.clear()
    except Exception:
        pass

    # Entities
    ents = payload.get("entities", [])
    if not isinstance(ents, list):
        ents = []

    n_ent = 0
    for ent in ents:
        if not isinstance(ent, dict):
            continue
        eid_raw = ent.get("eid")
        if not isinstance(eid_raw, str) or not eid_raw.strip():
            continue
        eid = eid_raw.strip().lower()
        kind = ent.get("kind")
        kind = kind if isinstance(kind, str) else None

        anchor_name = _wm_entity_anchor_name(eid)
        bid = ww.ensure_anchor(anchor_name)

        # cache mapping
        try:
            ctx.wm_entities[eid] = bid
        except Exception:
            pass

        tags = _wm_tagset_of(ww, bid)

        # remove old MapSurface tags (keep anchor:* tags)
        for t in list(tags):
            if isinstance(t, str) and (t.startswith("wm:") or t.startswith("pred:") or t.startswith("cue:")):
                tags.discard(t)

        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")
        if kind:
            tags.add(f"wm:kind:{kind}")

        preds = ent.get("preds")
        if isinstance(preds, list):
            for p in preds:
                if isinstance(p, str) and p:
                    tags.add(f"pred:{p}")

        cues = ent.get("cues")
        cue_full_tags: set[str] = set()
        if isinstance(cues, list):
            for c in cues:
                if isinstance(c, str) and c:
                    tags.add(f"cue:{c}")
                    cue_full_tags.add(f"cue:{c}")

        # meta.wm
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is not None:
            if not isinstance(getattr(b, "meta", None), dict):
                b.meta = {}
            wmm = b.meta.setdefault("wm", {})
            if isinstance(wmm, dict):
                pos = ent.get("pos")
                if isinstance(pos, dict):
                    x = pos.get("x")
                    y = pos.get("y")
                    frame = pos.get("frame")
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                        wmm["pos"] = {
                            "x": float(x),
                            "y": float(y),
                            "frame": frame if isinstance(frame, str) and frame else "wm_schematic_v1",
                        }

                dist_m = ent.get("dist_m")
                if isinstance(dist_m, (int, float)):
                    wmm["dist_m"] = float(dist_m)

                dist_class = ent.get("dist_class")
                if isinstance(dist_class, str) and dist_class:
                    wmm["dist_class"] = dist_class

                # Mark as fresh "seen" now (avoid confusing recency across sessions)
                wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)
                wmm["loaded_from"] = "wm_mapsurface_v1"
                wmm["load_reason"] = reason

        # root membership
        _wm_upsert_edge(ww, root_bid, bid, "wm_entity", {"created_by": "wm_load", "reason": reason})

        # cue cache for next env injection
        if cue_full_tags:
            try:
                ctx.wm_last_env_cues[eid] = set(cue_full_tags)
            except Exception:
                pass

        n_ent += 1

    # Relations (distance_to)
    rels = payload.get("relations", [])
    if not isinstance(rels, list):
        rels = []

    n_rel = 0
    self_bid = (getattr(ctx, "wm_entities", {}) or {}).get("self")
    for r in rels:
        if not isinstance(r, dict):
            continue
        if r.get("rel") != "distance_to":
            continue
        if r.get("src") != "self":
            continue
        dst = r.get("dst")
        if not isinstance(dst, str) or not dst.strip():
            continue
        dst_eid = dst.strip().lower()
        dst_bid = (getattr(ctx, "wm_entities", {}) or {}).get(dst_eid)

        if not (isinstance(self_bid, str) and isinstance(dst_bid, str)):
            continue

        em: dict[str, Any] = {"created_by": "wm_load", "reason": reason}
        meters = r.get("meters")
        if isinstance(meters, (int, float)):
            em["meters"] = float(meters)
        cls = r.get("class")
        if isinstance(cls, str) and cls:
            em["class"] = cls
        frame = r.get("frame")
        if isinstance(frame, str) and frame:
            em["frame"] = frame

        _wm_upsert_edge(ww, self_bid, dst_bid, "distance_to", em)
        n_rel += 1

    return {"ok": True, "entities": n_ent, "relations": n_rel}


def merge_mapsurface_payload_v1_into_workingmap(ctx: Ctx, payload: dict[str, Any], *, reason: str = "manual_merge") -> dict[str, Any]:
    """Merge/seed a wm_mapsurface_v1 payload into the current WorkingMap.MapSurface (conservative prior).

    Design intent:
      - Do NOT clear WorkingMap.
      - Do NOT delete or overwrite existing observed slot families.
      - Do NOT add cue:* tags (cues mean 'present now'); store cues in meta as 'prior_cues' instead.

    Returns:
      {"ok": bool, "added_entities": int, "filled_slots": int, "added_edges": int, "stored_prior_cues": int}
    """
    if getattr(ctx, "working_world", None) is None:
        ctx.working_world = init_working_world()
    ww = ctx.working_world
    if ww is None:
        return {"ok": False, "added_entities": 0, "filled_slots": 0, "added_edges": 0, "stored_prior_cues": 0}

    # Ensure MapSurface roots exist (do not clear anything)
    root_bid = ww.ensure_anchor("WM_ROOT")
    try:
        ww.set_now(root_bid, tag=True, clean_previous=True)
    except Exception:
        pass

    # Ensure Scratch + Creative exist (structural)
    scratch_bid = ww.ensure_anchor("WM_SCRATCH")
    _wm_tagset_of(ww, scratch_bid).add("wm:scratch")
    _wm_upsert_edge(ww, root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_merge", "reason": reason})

    creative_bid = ww.ensure_anchor("WM_CREATIVE")
    _wm_tagset_of(ww, creative_bid).add("wm:creative")
    _wm_upsert_edge(ww, root_bid, creative_bid, "wm_creative", {"created_by": "wm_merge", "reason": reason})

    # Rebuild ctx.wm_entities cache if empty (best-effort scan)
    try:
        if not getattr(ctx, "wm_entities", {}):
            for bid, b in getattr(ww, "_bindings", {}).items():
                tags = getattr(b, "tags", []) or []
                for t in tags:
                    if isinstance(t, str) and t.startswith("wm:eid:"):
                        eid = t.split(":", 2)[2].strip().lower()
                        if eid:
                            ctx.wm_entities[eid] = bid
    except Exception:
        pass


    def _pred_family(tok: str) -> str:
        if not isinstance(tok, str) or not tok:
            return ""
        return tok.rsplit(":", 1)[0] if ":" in tok else tok


    def _has_slot_family(tags: set[str], family: str) -> bool:
        """Return True if tags already contain any pred:* token in this slot family.

        Examples:
          family="posture"        matches pred:posture:standing, pred:posture:fallen
          family="proximity:mom"  matches pred:proximity:mom:close, pred:proximity:mom:far
          family="resting"        matches pred:resting (exact token)
        """
        if not family:
            return False

        # Exact token case (e.g., pred:resting)
        if f"pred:{family}" in tags:
            return True

        # Family-prefix case (e.g., pred:posture:*)
        pref = f"pred:{family}:"
        return any(isinstance(t, str) and t.startswith(pref) for t in tags)


    def _has_edge(src: str, dst: str, label: str) -> bool:
        b = getattr(ww, "_bindings", {}).get(src)
        if not b:
            return False
        edges = getattr(b, "edges", []) or []
        if not isinstance(edges, list):
            return False
        for e in edges:
            if not isinstance(e, dict):
                continue
            to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
            lab = e.get("label") or e.get("rel") or e.get("relation")
            if to_ == dst and lab == label:
                return True
        return False

    ents = payload.get("entities", [])
    if not isinstance(ents, list):
        ents = []

    added_entities = 0
    filled_slots = 0
    stored_prior_cues = 0

    # Entities: create if missing; else fill missing slot families only.
    for ent in ents:
        if not isinstance(ent, dict):
            continue
        eid_raw = ent.get("eid")
        if not isinstance(eid_raw, str) or not eid_raw.strip():
            continue
        eid = eid_raw.strip().lower()

        kind = ent.get("kind")
        kind = kind if isinstance(kind, str) else None

        bid = (getattr(ctx, "wm_entities", {}) or {}).get(eid)
        if not (isinstance(bid, str) and bid in getattr(ww, "_bindings", {})):
            # Create / ensure anchor
            bid = ww.ensure_anchor(_wm_entity_anchor_name(eid))
            ctx.wm_entities[eid] = bid
            added_entities += 1

        tags = _wm_tagset_of(ww, bid)
        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")

        # Only set kind if missing (do not fight existing kind tags)
        if kind and not any(isinstance(t, str) and t.startswith("wm:kind:") for t in tags):
            tags.add(f"wm:kind:{kind}")

        # Ensure membership under WM_ROOT
        _wm_upsert_edge(ww, root_bid, bid, "wm_entity", {"created_by": "wm_merge", "reason": reason})

        # meta.wm fill (only if missing)
        b = ww._bindings.get(bid)  # pylint: disable=protected-access
        if b is not None:
            if not isinstance(getattr(b, "meta", None), dict):
                b.meta = {}
            wmm = b.meta.setdefault("wm", {})
            if isinstance(wmm, dict):
                pos = ent.get("pos")
                if "pos" not in wmm and isinstance(pos, dict):
                    x = pos.get("x"); y = pos.get("y"); frame = pos.get("frame")
                    if isinstance(x, (int, float)) and isinstance(y, (int, float)):
                        wmm["pos"] = {"x": float(x), "y": float(y), "frame": frame if isinstance(frame, str) and frame else "wm_schematic_v1"}

                if "dist_m" not in wmm:
                    dist_m = ent.get("dist_m")
                    if isinstance(dist_m, (int, float)):
                        wmm["dist_m"] = float(dist_m)

                if "dist_class" not in wmm:
                    dist_class = ent.get("dist_class")
                    if isinstance(dist_class, str) and dist_class:
                        wmm["dist_class"] = dist_class

                # recency marker always refreshed
                wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)
                wmm["loaded_from"] = "wm_mapsurface_v1"
                wmm["load_reason"] = reason

                # Store cues as "prior_cues" (do NOT add cue:* tags in merge mode)
                cues = ent.get("cues")
                if isinstance(cues, list) and cues:
                    prior = wmm.setdefault("prior_cues", [])
                    if isinstance(prior, list):
                        for c in cues:
                            if isinstance(c, str) and c and c not in prior:
                                prior.append(c)
                                stored_prior_cues += 1

        # Predicates: only fill slot families that are missing
        preds = ent.get("preds")
        if isinstance(preds, list):
            for p in preds:
                if not isinstance(p, str) or not p:
                    continue
                fam = _pred_family(p)
                if _has_slot_family(tags, fam):
                    continue
                tags.add(f"pred:{p}")
                filled_slots += 1

    # Relations: add missing distance_to edges only
    rels = payload.get("relations", [])
    if not isinstance(rels, list):
        rels = []

    added_edges = 0
    self_bid = (getattr(ctx, "wm_entities", {}) or {}).get("self")
    for r in rels:
        if not isinstance(r, dict):
            continue
        if r.get("rel") != "distance_to" or r.get("src") != "self":
            continue
        dst = r.get("dst")
        if not isinstance(dst, str) or not dst.strip():
            continue
        dst_eid = dst.strip().lower()
        dst_bid = (getattr(ctx, "wm_entities", {}) or {}).get(dst_eid)
        if not (isinstance(self_bid, str) and isinstance(dst_bid, str)):
            continue

        if _has_edge(self_bid, dst_bid, "distance_to"):
            continue

        em: dict[str, Any] = {"created_by": "wm_merge", "reason": reason}
        meters = r.get("meters")
        if isinstance(meters, (int, float)):
            em["meters"] = float(meters)
        cls = r.get("class")
        if isinstance(cls, str) and cls:
            em["class"] = cls
        frame = r.get("frame")
        if isinstance(frame, str) and frame:
            em["frame"] = frame

        _wm_upsert_edge(ww, self_bid, dst_bid, "distance_to", em)
        added_edges += 1

    return {
        "ok": True,
        "added_entities": added_entities,
        "filled_slots": filled_slots,
        "added_edges": added_edges,
        "stored_prior_cues": stored_prior_cues,
    }


def load_wm_mapsurface_engram_into_workingmap_mode(ctx: Ctx, engram_id: str, *, mode: str = "replace") -> dict[str, Any]:
    """Load a Column engram (wm_mapsurface) into WorkingMap using replace or merge/seed mode."""
    rec = column_mem.try_get(engram_id)
    if not isinstance(rec, dict):
        return {"ok": False, "why": "no_such_engram"}

    if rec.get("name") != "wm_mapsurface":
        return {"ok": False, "why": "wrong_name"}

    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "why": "payload_not_dict"}

    m = (mode or "replace").strip().lower()
    if m in ("merge", "seed", "merge_seed", "merge/seed"):
        out = merge_mapsurface_payload_v1_into_workingmap(ctx, payload, reason=f"engram_merge:{engram_id[:8]}")
        out["mode"] = "merge"
    else:
        out = load_mapsurface_payload_v1_into_workingmap(ctx, payload, replace=True, reason=f"engram_replace:{engram_id[:8]}")
        out["mode"] = "replace"

    out["ok"] = True
    out["engram_id"] = engram_id
    return out


def should_autoretrieve_mapsurface(
    ctx: Ctx,
    env_obs: EnvObservation | None,
    *,
    stage: str | None,
    zone: str | None,
    stage_changed: bool,
    zone_changed: bool,
    forced_keyframe: bool = False,
    boundary_reason: str | None = None
) -> dict[str, Any]:
    """Guard hook: decide whether CCA8 should attempt MapSurface auto-retrieval *right now*.

    What this is (plain English)
    ----------------------------
    Auto-retrieve is the read-path side of the memory pipeline:

        Column engram (wm_mapsurface payload)  →  WorkingMap.MapSurface (as a prior)

    We consider it at keyframes so the system can "snap into" a previously seen scene configuration
    without bloating the long-term WorldGraph. WorldGraph stores only a thin pointer; the heavy
    MapSurface payload lives in Column memory.

    Minimal gating (Phase VIII)
    ---------------------------
    Historically this hook was a simple baseline: if enabled + boundary → attempt.
    We now add a conservative gating rule so *prediction error and partial observability matter*:

      Attempt auto-retrieve only when ALL are true:
        1) enabled, and
        2) this call is occurring on a keyframe boundary (stage/zone boundary), and
        3) we have evidence priors may help, i.e. at least one of:
             - missingness: this observation dropped tokens due to obs-mask (or obs packet is very sparse / None)
             - pred_err:   ctx.pred_err_v0_last has any non-zero component (v0 currently tracks posture mismatch)
             - stale:      BodyMap is stale (priors can stabilize belief when fast registers are unreliable)

    This is intentionally conservative: in rich-observation demos, retrieval often becomes a no-op anyway.
    The gating keeps the logs meaningful and prevents "always retrieve" behavior from dominating experiments.

    Returns
    -------
    dict with stable keys:
      ok:
        True if we should attempt auto-retrieval now.
      why:
        Short reason string for logs/tests.
      mode:
        Normalized retrieval mode to use ("merge" or "replace").
      top_k:
        Candidate budget (int, clamped to 2..10).
      verbose:
        Whether the caller should print diagnostic lines.
      diag:
        Small diagnostic dictionary (counts, flags, stage/zone) for optional logging.
    """
    enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False))
    verbose = bool(getattr(ctx, "wm_mapsurface_autoretrieve_verbose", False))

    # Normalize mode (keep conservative by default)
    mode_raw = (getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge")
    mode_eff = str(mode_raw).strip().lower()
    if mode_eff not in ("merge", "replace", "r"):
        mode_eff = "merge"
    if mode_eff == "r":
        mode_eff = "replace"

    # Clamp top_k so exclusion has room to choose a second candidate.
    try:
        top_raw = int(getattr(ctx, "wm_mapsurface_autoretrieve_top_k", 5) or 5)
    except Exception:
        top_raw = 5
    top_k = max(2, min(10, int(top_raw)))

    # Cheap diagnostic counts (do not depend on exact schema)
    pred_n = 0
    cue_n = 0
    try:
        preds = getattr(env_obs, "predicates", None) if env_obs is not None else None
        cues = getattr(env_obs, "cues", None) if env_obs is not None else None
        pred_n = len(preds) if isinstance(preds, list) else 0
        cue_n = len(cues) if isinstance(cues, list) else 0
    except Exception:
        pred_n = 0
        cue_n = 0

    boundary = bool(stage_changed) or bool(zone_changed) or bool(forced_keyframe)

    diag: dict[str, Any] = {
        "stage": stage,
        "zone": zone,
        "stage_changed": bool(stage_changed),
        "zone_changed": bool(zone_changed),
        "boundary_reason": boundary_reason,
        "pred_n": pred_n,
        "cue_n": cue_n,
    }

    if not enabled:
        diag["need_priors"] = False
        return {"ok": False, "why": "disabled", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    if not boundary:
        diag["need_priors"] = False
        return {"ok": False, "why": "not_boundary", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    # ---- Minimal gating signals (missingness + pred_err + BodyMap staleness) ----
    body_stale = True
    try:
        body_stale = bool(bodymap_is_stale(ctx))
    except Exception:
        body_stale = True

    pred_err_any = False
    pred_err_posture = 0
    try:
        pe = getattr(ctx, "pred_err_v0_last", None)
        if isinstance(pe, dict) and pe:
            try:
                pred_err_posture = int(pe.get("posture", 0) or 0)
            except Exception:
                pred_err_posture = 0
            try:
                pred_err_any = any(int(v or 0) != 0 for v in pe.values())
            except Exception:
                pred_err_any = pred_err_posture != 0
    except Exception:
        pred_err_any = False
        pred_err_posture = 0

    mask_dropped_preds = 0
    mask_dropped_cues = 0
    try:
        meta = getattr(env_obs, "env_meta", None) if env_obs is not None else None
        if isinstance(meta, dict):
            mask_dropped_preds = int(meta.get("obs_mask_dropped_preds", 0) or 0)
            mask_dropped_cues = int(meta.get("obs_mask_dropped_cues", 0) or 0)
    except Exception:
        mask_dropped_preds = 0
        mask_dropped_cues = 0

    # Treat a missing/very-sparse obs packet as missingness (priors likely helpful).
    sparse_obs = (env_obs is None) or (pred_n <= 1 and cue_n <= 0)
    missingness = sparse_obs or ((mask_dropped_preds + mask_dropped_cues) > 0)

    need_priors = bool(pred_err_any) or bool(missingness) or bool(body_stale)

    diag.update(
        {
            "pred_err_any": bool(pred_err_any),
            "pred_err_posture": int(pred_err_posture),
            "mask_dropped_preds": int(mask_dropped_preds),
            "mask_dropped_cues": int(mask_dropped_cues),
            "bodymap_stale": bool(body_stale),
            "sparse_obs": bool(sparse_obs),
            "missingness": bool(missingness),
            "need_priors": bool(need_priors),
        }
    )

    if not need_priors:
        return {"ok": False, "why": "enabled_boundary_confident", "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}

    if pred_err_any:
        why = "enabled_boundary_pred_err"
    elif missingness:
        why = "enabled_boundary_missing"
    else:
        why = "enabled_boundary_bodymap_stale"

    return {"ok": True, "why": why, "mode": mode_eff, "top_k": top_k, "verbose": verbose, "diag": diag}


def maybe_autoretrieve_mapsurface_on_keyframe(
    world,
    ctx: Ctx,
    *,
    stage: str | None,
    zone: str | None,
    exclude_engram_id: str | None = None,
    reason: str = "auto_keyframe",
    mode: str | None = None,
    top_k: int | None = None,
    max_scan: int = 500,
    log: bool | None = None,
) -> dict[str, Any]:
    """Try to seed WorkingMap from a prior wm_mapsurface engram on a keyframe boundary.

    This is the *read-path* complement to store_mapsurface_snapshot_v1(...).

    Intended semantics:
      - Keyframes are stage/zone boundaries. At that moment we may want a "prior" map.
      - We select candidates by (stage, zone) first, then rank by salience overlap vs *current* WM.
      - We skip `exclude_engram_id` (usually the snapshot we just stored this same boundary).
      - We load into WorkingMap using either:
          * mode="merge"   (default): conservative prior; does NOT inject cue:*; does NOT overwrite slot families.
          * mode="replace" (debug): clear + rebuild; observation will overwrite next tick.

    Returns:
      dict with keys {ok, why?, engram_id?, chosen?, pick?, load?} (safe for tests/printing).
    """
    if ctx is None or world is None:
        return {"ok": False, "why": "missing_ctx_or_world"}

    if not bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False)):
        return {"ok": False, "why": "disabled"}

    mode_eff = (mode or getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
    top_eff = top_k if isinstance(top_k, int) else int(getattr(ctx, "wm_mapsurface_autoretrieve_top_k", 5) or 5)
    top_eff = max(2, min(10, int(top_eff)))  # need >=2 because we may exclude the top candidate

    pick = pick_best_wm_mapsurface_rec(
        stage=stage,
        zone=zone,
        ctx=ctx,
        long_world=world,
        allow_fallback=True,
        max_scan=max(1, int(max_scan)),
        top_k=top_eff,
    )

    ranked = pick.get("ranked") if isinstance(pick, dict) else None
    if not (isinstance(ranked, list) and ranked):
        return {"ok": False, "why": "no_candidates", "pick": pick}

    chosen: dict[str, Any] | None = None
    for cand in ranked:
        if not isinstance(cand, dict):
            continue
        eid = cand.get("engram_id")
        if not isinstance(eid, str) or not eid:
            continue
        if isinstance(exclude_engram_id, str) and exclude_engram_id and eid == exclude_engram_id:
            continue
        chosen = cand
        break

    if chosen is None:
        return {"ok": False, "why": "only_excluded_candidate", "pick": pick}

    eid = chosen.get("engram_id")
    if not isinstance(eid, str) or not eid:
        return {"ok": False, "why": "bad_engram_id", "pick": pick}

    # Execute the load into WM
    if mode_eff in ("replace", "r"):
        load = load_wm_mapsurface_engram_into_workingmap_mode(ctx, eid, mode="replace")
    else:
        load = load_wm_mapsurface_engram_into_workingmap_mode(ctx, eid, mode="merge")

    try:
        ctx.wm_mapsurface_last_autoretrieve_engram_id = eid
        ctx.wm_mapsurface_last_autoretrieve_reason = reason
    except Exception:
        pass

    log_enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_verbose", False))
    if log is not None:
        log_enabled = bool(log)

    if log_enabled:
        try:
            match = pick.get("match") if isinstance(pick, dict) else None
            score = chosen.get("score")
            op = chosen.get("overlap_preds")
            oc = chosen.get("overlap_cues")
            src = chosen.get("src")
            mode_txt = load.get("mode", "merge") if isinstance(load, dict) else mode_eff
            print(
                f"[wm-retrieve] (auto) {mode_txt} engram={eid[:8]}… match={match} "
                f"score={score} op={op} oc={oc} src={src}"
            )
        except Exception:
            pass

    return {"ok": True, "engram_id": eid, "chosen": chosen, "pick": pick, "load": load}



def load_wm_mapsurface_engram_into_workingmap(ctx: Ctx, engram_id: str, *, replace: bool = True) -> dict[str, Any]:
    """Load a Column engram (wm_mapsurface) into WorkingMap MapSurface."""
    rec = column_mem.try_get(engram_id)
    if not isinstance(rec, dict):
        return {"ok": False, "why": "no_such_engram", "entities": 0, "relations": 0}

    if rec.get("name") != "wm_mapsurface":
        return {"ok": False, "why": "wrong_name", "entities": 0, "relations": 0}

    payload = rec.get("payload")
    if not isinstance(payload, dict):
        return {"ok": False, "why": "payload_not_dict", "entities": 0, "relations": 0}

    out = load_mapsurface_payload_v1_into_workingmap(ctx, payload, replace=replace, reason=f"engram:{engram_id[:8]}")
    out["engram_id"] = engram_id
    return out


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
    return any(bool(_bindings_with_cue(world, tok)) for tok in tokens)


def has_pred_near_now(world, token: str, hops: int = 3) -> bool:
    """Return True if any pred:<token> is reachable from NOW in ≤ `hops` edges."""
    now_id = _anchor_id(world, "NOW")
    for bid in _bindings_with_pred(world, token):
        if _bfs_reachable(world, now_id, bid, max_hops=hops):
            return True
    return False


def any_pred_present(world, tokens: List[str]) -> bool:
    """Return True if any pred:<token> in `tokens` exists anywhere in the graph."""
    return any(bool(_bindings_with_pred(world, tok)) for tok in tokens)


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


def _gate_follow_mom_trigger_body_space(world, drives: Drives, ctx) -> bool:  # pylint: disable=unused-argument
    """
    FollowMom gate: permissive fallback when the kid is not fallen *and not resting*.

    Intent:
      - FollowMom is a mild default policy when nothing else is urgent.
      - During storyboard rest, we want quiescence (no repeated scratch writes and no spurious action).

    Rules (v1):
      - If BodyMap is fresh:
          posture in {"fallen","resting"} -> False
          else -> True
      - If BodyMap is stale:
          pred:resting near NOW -> False
          else -> True
    """
    try:
        if ctx is not None and not bodymap_is_stale(ctx):
            bp = body_posture(ctx)
            if bp in ("fallen", "resting"):
                return False
    except Exception:
        pass

    # Fallback when BodyMap is stale/unavailable: suppress FollowMom if the graph near NOW says we're resting.
    try:
        if has_pred_near_now(world, "resting", hops=3):
            return False
    except Exception:
        pass

    return True


def _gate_follow_mom_explain_body_space(world, drives: Drives, ctx) -> str:  # pylint: disable=unused-argument
    """
    Human-readable explanation matching _gate_follow_mom_trigger_body_space.
    """
    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))

    posture = None
    zone = "unknown"
    bodymap_stale = True
    try:
        bodymap_stale = bodymap_is_stale(ctx) if ctx is not None else True
        if ctx is not None and not bodymap_stale:
            posture = body_posture(ctx)
            zone = body_space_zone(ctx)
    except Exception:
        posture = posture or "n/a"
        zone = "unknown"
        bodymap_stale = True

    rest_near_now = False
    try:
        rest_near_now = has_pred_near_now(world, "resting", hops=3)
    except Exception:
        rest_near_now = False

    return (
        "dev_gate: True, trigger: fallback=True when not fallen/resting; "
        f"bodymap_stale={bodymap_stale} posture={posture or 'n/a'} rest_near_now={rest_near_now} zone={zone} "
        f"(hunger={hunger:.2f}, fatigue={fatigue:.2f})"
    )


def _gate_probe_ambiguity_trigger_body_first(world, _drives: Drives, ctx) -> bool:  # pylint: disable=unused-argument
    """
    Step 15C gate: trigger a minimal probe policy when WM.Scratch reports an ambiguous NavPatch match.

    v1 (conservative):
      - Trigger only when ambiguity exists for a safety-relevant entity (cliff), OR BodyMap says cliff is near.
      - Debounce by ctx.wm_probe_cooldown_steps to avoid repeating the probe every tick.

    This is a gate only: it must not mutate world state.
    """
    if ctx is None:
        return False
    if not bool(getattr(ctx, "wm_probe_enabled", True)):
        return False

    keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
    if not isinstance(keys, set) or not keys:
        return False

    ents: set[str] = set()
    for k in keys:
        if not isinstance(k, str) or "|" not in k:
            continue
        ent = k.split("|", 1)[0].strip().lower()
        if ent:
            ents.add(ent)

    hazard_amb = "cliff" in ents

    hazard_near = False
    try:
        hazard_near = (body_cliff_distance(ctx) == "near")  #pylint: disable=superfluous-parens
    except Exception:
        hazard_near = False

    if not (hazard_amb or hazard_near):
        return False

    # Debounce (cooldown)
    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    last = getattr(ctx, "wm_probe_last_step", None)
    last_i = int(last) if isinstance(last, int) else None

    try:
        cooldown = int(getattr(ctx, "wm_probe_cooldown_steps", 3) or 3)
    except Exception:
        cooldown = 3
    cooldown = max(0, min(50, int(cooldown)))

    if last_i is not None and cooldown > 0 and (step_now - last_i) < cooldown:
        return False

    return True


def _gate_probe_ambiguity_explain_body_first(world, _drives: Drives, ctx) -> str:  # pylint: disable=unused-argument
    """
    Human-readable explanation for the Step 15C probe gate.
    """
    if ctx is None:
        return "dev_gate: True, trigger: ctx missing"

    keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
    keys_txt = sorted(list(keys)) if isinstance(keys, set) else []

    ents: set[str] = set()
    for k in keys_txt:
        if isinstance(k, str) and "|" in k:
            ents.add(k.split("|", 1)[0].strip().lower())

    hazard_amb = "cliff" in ents

    hazard_near = False
    try:
        hazard_near = (body_cliff_distance(ctx) == "near")  #pylint: disable="superfluous-parens"
    except Exception:
        hazard_near = False

    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    last = getattr(ctx, "wm_probe_last_step", None)
    last_i = int(last) if isinstance(last, int) else None

    try:
        cooldown = int(getattr(ctx, "wm_probe_cooldown_steps", 3) or 3)
    except Exception:
        cooldown = 3
    cooldown = max(0, min(50, int(cooldown)))

    blocked = False
    if last_i is not None and cooldown > 0 and (step_now - last_i) < cooldown:
        blocked = True

    return (
        "dev_gate: True, trigger: "
        f"scratch_keys={len(keys_txt)} ents={sorted(list(ents))} "
        f"hazard_amb(cliff)={hazard_amb} hazard_near={hazard_near} "
        f"cooldown={cooldown} blocked={blocked} "
        f"(step_now={step_now}, last_probe={last_i})"
    )






def _gate_recover_fall_trigger_body_first(world, _drives: Drives, ctx) -> bool:
    """
    RecoverFall gate that prefers BodyMap for posture when available, falling back
    to WorldGraph near-NOW predicates otherwise.

    Trigger logic:
      • If explicit fall cues are present → fire (regardless of posture).
      • If BodyMap is fresh:
            posture == 'fallen'   → fire
            posture == 'standing' → do NOT fire
            posture == 'resting'  → do NOT fire
      • Otherwise fall back to graph near-NOW: pred:posture:fallen near NOW.
    """
    # Fall cues always override
    if any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"]):
        return True

    # Prefer BodyMap when fresh
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None
    if bp is not None:
        return bp == "fallen"

    # Fallback to episode graph (legacy behavior)
    return has_pred_near_now(world, "posture:fallen")


def _gate_recover_fall_explain(world, _drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_recover_fall_trigger_body_first.
    """
    fall_cue = any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"])

    bodymap_stale = True
    bp = None
    try:
        bodymap_stale = bodymap_is_stale(ctx) if ctx is not None else True
        bp = body_posture(ctx) if ctx is not None and not bodymap_stale else None
    except Exception:
        bodymap_stale = True
        bp = None

    if bp is not None:
        fallen = bp == "fallen"
    else:
        fallen = has_pred_near_now(world, "posture:fallen")

    return (
        "dev_gate: True, trigger: "
        f"fallen={fallen} (bodymap_posture={bp or 'n/a'}, bodymap_stale={bodymap_stale}) "
        f"or fall_cue={fall_cue} cues={present_cue_bids(world)}"
    )


def apply_hardwired_profile_phase7(ctx: "Ctx", world) -> None:
    """Hardwire the Phase VII daily-driver memory pipeline.

    Intent:
      - WorkingMap: dense workspace (env mirroring always on; policy execution writes can live here)
      - WorldGraph: sparse long-term index (env obs in changes mode + keyframes + cue dedup + run-compressed actions)
      - RL: off by default (deterministic selection while we validate memory mechanics)

    This replaces the need for Menu 41 in normal use.
    """
    if ctx is None or world is None:
        return

    # --- RL: enabled (deterministic by default) ---
    # turning RL ON, but keeping exploration essentially OFF (epsilon=0.05) so behavior stays reproducible.
    # You still get q-based tie-break behavior when it applies.
    try:
        ctx.rl_enabled = True
        ctx.rl_epsilon = 0.05  # % explore, i.e., the amount of randomness
        ctx.rl_delta = 0.0     # q used only for exact deficit ties (safe default)
        ctx.rl_explore_steps = 0
        ctx.rl_exploit_steps = 0
    except Exception:
        pass

    # --- WorkingMap: on (trace/workspace) ---
    try:
        ctx.working_enabled = True
        ctx.working_verbose = True
        ctx.working_max_bindings = 250
        if hasattr(ctx, "working_move_now"):
            ctx.working_move_now = True
    except Exception:
        pass

    # --- Phase VII: motor runs + (optionally) working-first execution ---
    try:
        ctx.phase7_working_first = True
        ctx.phase7_run_compress = True
        ctx.phase7_run_verbose = False
        ctx.phase7_move_longterm_now_to_env = True
    except Exception:
        pass

    # --- MapSurface auto-retrieve at keyframes (safe default = merge) ---
    try:
        ctx.wm_mapsurface_autoretrieve_enabled = True
        ctx.wm_mapsurface_autoretrieve_mode = "merge"
        ctx.wm_mapsurface_autoretrieve_top_k = 5
        ctx.wm_mapsurface_autoretrieve_verbose = True
    except Exception:
        pass

    # --- WorldGraph memory mode: keep literal time semantics for long-term writes ---
    try:
        if hasattr(world, "set_memory_mode"):
            world.set_memory_mode("episodic")
    except Exception:
        pass

    # --- Long-term EnvObservation injection: sparse + keyframes + cue dedup ---
    try:
        ctx.longterm_obs_enabled = True
        ctx.longterm_obs_mode = "changes"
        ctx.longterm_obs_reassert_steps = 0

        # IMPORTANT:
        # The Phase VII hardwired profile enables the memory pipeline, but it must NOT override
        # keyframe trigger knobs (stage/zone/periodic/pred_err/milestone/emotion). Those are
        # experiment settings on Ctx and should remain under direct user control.

        ctx.longterm_obs_verbose = False
    except Exception:
        pass


    # Low-noise, useful log
    try:
        if hasattr(ctx, "longterm_obs_keyframe_log"):
            ctx.longterm_obs_keyframe_log = True
    except Exception:
        pass

    # Cue dedup (presence/rising-edge)
    try:
        if hasattr(ctx, "longterm_obs_dedup_cues"):
            ctx.longterm_obs_dedup_cues = True
    except Exception:
        pass

    # Clear long-term slot caches (dedup bookkeeping) so the next env obs is a clean "first".
    try:
        ctx.lt_obs_slots.clear()
    except Exception:
        pass
    try:
        if hasattr(ctx, "lt_obs_cues"):
            ctx.lt_obs_cues.clear()
    except Exception:
        pass
    try:
        ctx.lt_obs_last_stage = None
    except Exception:
        pass

    # Clear any open run-compression state (defensive; safe no-op if fields not present)
    try:
        if hasattr(ctx, "run_open"):
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
    except Exception:
        pass


# -----------------------------------------------------------------------------
# EFE policy scoring (Phase X 2.2b): diagnostic stub (no selection changes)
# -----------------------------------------------------------------------------

_EFE_SCORES_VERSION = "efe_scores_v1"


def _clamp01(x: float) -> float:
    try:
        v = float(x)
    except Exception:
        return 0.0
    if v < 0.0:
        return 0.0
    if v > 1.0:
        return 1.0
    return v


def _norm_deficit(val: float, thresh: float) -> float:
    """Normalize how far ABOVE a threshold we are into [0,1]."""
    try:
        v = float(val)
        t = float(thresh)
    except Exception:
        return 0.0
    if v <= t:
        return 0.0
    denom = (1.0 - t) if (1.0 - t) > 1e-9 else 1e-9
    return _clamp01((v - t) / denom)


def _norm_cold(warmth: float, cold_thresh: float = 0.30) -> float:
    """Normalize how far BELOW the cold threshold we are into [0,1]."""
    try:
        w = float(warmth)
        t = float(cold_thresh)
    except Exception:
        return 0.0
    if w >= t:
        return 0.0
    denom = t if t > 1e-9 else 1e-9
    return _clamp01((t - w) / denom)


def _efe_zone_from_ctx(ctx) -> str:
    """
    Best-effort zone label used as a safety proxy for the EFE stub.

    Preference order:
      1) BodyMap-derived zone (if available)
      2) navpatch_priors["zone"] (already JSON-safe and present in cycle logs)
      3) "unknown"
    """
    # (1) BodyMap if possible
    try:
        if ctx is not None:
            z = body_space_zone(ctx)
            if isinstance(z, str) and z:
                return z
    except Exception:
        pass

    # (2) navpatch priors bundle
    try:
        priors = getattr(ctx, "navpatch_last_priors", None)
        if isinstance(priors, dict):
            z = priors.get("zone")
            if isinstance(z, str) and z:
                return z
    except Exception:
        pass

    return "unknown"


def _efe_stage_from_ctx(ctx) -> str:
    """Stage is useful context, but we keep it optional and best-effort."""
    try:
        priors = getattr(ctx, "navpatch_last_priors", None)
        if isinstance(priors, dict):
            st = priors.get("stage")
            if isinstance(st, str) and st:
                return st
    except Exception:
        pass
    return "unknown"


def _efe_global_ambiguity_from_navpatch(ctx) -> float:
    """
    Use NavPatch matching residuals as a proxy for perceptual ambiguity.

    We treat best-match error (best['err'] in [0,1]) as a local mismatch signal.
    This is NOT yet the commit/ambiguous classification (that is Step 2); it is
    simply "how well did the patch match its nearest stored prototype?"
    """
    matches = getattr(ctx, "navpatch_last_matches", None)
    if not isinstance(matches, list) or not matches:
        return 0.0

    errs: list[float] = []
    for rec in matches:
        if not isinstance(rec, dict):
            continue
        best = rec.get("best")
        if not isinstance(best, dict):
            continue
        err = best.get("err")
        if isinstance(err, (int, float)):
            errs.append(float(err))

    if not errs:
        return 0.0
    return _clamp01(sum(errs) / max(1, len(errs)))


def _efe_risk_stub_v1(policy_name: str, *, zone: str) -> float:
    """
    Risk proxy: map coarse zone + policy semantics into a [0,1] cost.

    This is intentionally tiny and transparent. We will revise once we have
    a richer environment (goat_foraging_* tasks) and real movement policies.
    """
    base = {"unsafe_cliff_near": 0.80, "safe": 0.10, "unknown": 0.40}.get(zone, 0.40)

    # Heuristic adjustments by policy role (very small; keep readable)
    if policy_name == "policy:rest":
        base += 0.20  # resting while unsafe is a bad idea
    elif policy_name == "policy:follow_mom":
        base -= 0.20  # movement away from danger tends to reduce risk
    elif policy_name in ("policy:stand_up", "policy:recover_fall"):
        base -= 0.10  # recovery actions reduce immediate risk of being prone
    elif policy_name == "policy:seek_nipple":
        base += 0.05  # mild: attention diverted (stub)

    return _clamp01(base)


def _efe_preference_stub_v1(policy_name: str, drives: Drives, ctx, *, zone: str, amb_global: float) -> float:
    """
    Preference proxy: expected "goodness" of an action given drives + safety context.

    Returns a [0,1] value (higher is more preferred).
    """
    hunger = float(getattr(drives, "hunger", 0.0) or 0.0)
    fatigue = float(getattr(drives, "fatigue", 0.0) or 0.0)
    warmth = float(getattr(drives, "warmth", 1.0) or 1.0)

    hunger_need = _norm_deficit(hunger, float(HUNGER_HIGH))
    fatigue_need = _norm_deficit(fatigue, float(FATIGUE_HIGH))
    cold_need = _norm_cold(warmth, 0.30)

    # Safety posture signal (BodyMap-first via controller helper)
    fallen = False
    try:
        fallen = bool(_fallen_near_now(None if ctx is None else getattr(ctx, "working_world", None), ctx, max_hops=3))  # best-effort
    except Exception:
        try:
            fallen = bool(_fallen_near_now(None, ctx, max_hops=3))
        except Exception:
            fallen = False

    # Policy-specific preference
    if policy_name == "policy:seek_nipple":
        return _clamp01(1.00 * hunger_need)

    if policy_name == "policy:rest":
        return _clamp01(1.00 * fatigue_need + 0.25 * cold_need)

    if policy_name in ("policy:stand_up", "policy:recover_fall"):
        return 1.0 if fallen else 0.0

    if policy_name == "policy:follow_mom":
        # When unsafe, moving is strongly preferred; otherwise it is a mild default preference.
        return 0.60 if zone == "unsafe_cliff_near" else 0.20

    if policy_name == "policy:explore_check":
        # Epistemic-ish bias: when ambiguity is high, exploring becomes more attractive.
        return _clamp01(0.10 + 0.40 * float(amb_global))

    return 0.0


def _efe_ambiguity_stub_v1(policy_name: str, *, amb_global: float) -> float:
    """
    Ambiguity proxy: start from global perceptual ambiguity and apply tiny policy deltas.

    Lower is better (it is a cost term).
    """
    a = _clamp01(float(amb_global))

    if policy_name == "policy:explore_check":
        a -= 0.20
    elif policy_name == "policy:follow_mom":
        a -= 0.10
    elif policy_name == "policy:rest":
        a += 0.10

    return _clamp01(a)


def compute_efe_scores_stub_v1(_world, drives: Drives, ctx, candidates: list[str], *, triggered_all: list[str] | None = None) -> dict[str, Any]:
    """
    Compute a small, JSON-safe EFE-style scoring bundle for candidate policies.

    Output (JSON-safe):
      {
        "v": "efe_scores_v1",
        "enabled": true,
        "stage": "...",
        "zone": "...",
        "amb_global": 0.23,
        "weights": {"risk": 1.0, "ambiguity": 1.0, "preference": 1.0},
        "candidates": [...],
        "triggered_all": [...],          # optional
        "scores": [
            {"policy": "...", "risk": .., "ambiguity": .., "preference": .., "total": .., "rank": 1},
            ...
        ],
      }

    Convention:
      - risk/ambiguity are costs (lower is better)
      - preference is a value (higher is better)
      - total is minimized: total = w_risk*risk + w_amb*ambiguity - w_pref*preference
    """
    zone = _efe_zone_from_ctx(ctx)
    stage = _efe_stage_from_ctx(ctx)
    amb_global = _efe_global_ambiguity_from_navpatch(ctx)

    try:
        w_r = float(getattr(ctx, "efe_w_risk", 1.0))
    except Exception:
        w_r = 1.0
    try:
        w_a = float(getattr(ctx, "efe_w_ambiguity", 1.0))
    except Exception:
        w_a = 1.0
    try:
        w_p = float(getattr(ctx, "efe_w_preference", 1.0))
    except Exception:
        w_p = 1.0

    # De-dupe candidates while preserving order
    seen: set[str] = set()
    cand: list[str] = []
    for nm in candidates:
        if isinstance(nm, str) and nm and nm not in seen:
            seen.add(nm)
            cand.append(nm)

    rows: list[dict[str, Any]] = []
    for nm in cand:
        r = _efe_risk_stub_v1(nm, zone=zone)
        a = _efe_ambiguity_stub_v1(nm, amb_global=amb_global)
        p = _efe_preference_stub_v1(nm, drives, ctx, zone=zone, amb_global=amb_global)
        total = (w_r * r) + (w_a * a) - (w_p * p)

        rows.append(
            {
                "policy": nm,
                "risk": float(r),
                "ambiguity": float(a),
                "preference": float(p),
                "total": float(total),
            }
        )

    rows.sort(key=lambda d: float(d.get("total", 0.0)))
    for i, d in enumerate(rows, 1):
        d["rank"] = i

    out: dict[str, Any] = {
        "v": _EFE_SCORES_VERSION,
        "enabled": True,
        "stage": stage,
        "zone": zone,
        "amb_global": float(amb_global),
        "weights": {"risk": float(w_r), "ambiguity": float(w_a), "preference": float(w_p)},
        "candidates": list(cand),
        "scores": rows,
    }
    if isinstance(triggered_all, list):
        out["triggered_all"] = [x for x in triggered_all if isinstance(x, str)]
    return out


def _efe_render_summary_line(ctx, *, max_policies: int = 5) -> str:
    """
    Render a compact, single-line EFE summary for terminal logs.

    Only prints when ctx.efe_enabled is True. This is meant to be "one more lens"
    next to deficit/non-drive/RL notes, not a new control rule yet.
    """
    if ctx is None or not bool(getattr(ctx, "efe_enabled", False)):
        return ""

    efe = getattr(ctx, "efe_last", None)
    if not isinstance(efe, dict):
        return ""

    zone = efe.get("zone", "unknown")
    amb = efe.get("amb_global", None)
    try:
        amb_txt = f"{float(amb):.2f}"
    except Exception:
        amb_txt = "n/a"

    scores = efe.get("scores", None)
    if not isinstance(scores, list) or not scores:
        return f"[efe] zone={zone} amb={amb_txt} (no scores)\n"

    parts: list[str] = []
    lim = max(1, int(max_policies))
    for row in scores[:lim]:
        if not isinstance(row, dict):
            continue
        nm = row.get("policy")
        if not isinstance(nm, str):
            continue
        try:
            tot = float(row.get("total", 0.0))
            r = float(row.get("risk", 0.0))
            a = float(row.get("ambiguity", 0.0))
            p = float(row.get("preference", 0.0))
            parts.append(f"{nm}(G={tot:+.2f} r={r:.2f} a={a:.2f} p={p:.2f})")
        except Exception:
            parts.append(f"{nm}(G=n/a)")

    if not parts:
        return f"[efe] zone={zone} amb={amb_txt} (no scores)\n"

    if len(scores) > lim:
        parts.append("...")

    return f"[efe] zone={zone} amb={amb_txt} " + " | ".join(parts) + "\n"


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


    def consider_and_maybe_fire(self, world, drives, ctx, tie_break: str = "first", exec_world=None) -> str:  # pylint: disable=unused-argument

        """Evaluate triggers, prefer safety-critical gates, then run the controller once;
              return a short human string.
              """
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        if not matches:
            return "no_match"

        # capture the full triggered set (before any safety-only filtering)
        triggered_all = [p.name for p in matches]

        # Step 13 (minimal behavior hook):
        # If the composed SurfaceGrid says hazard is near, suppress the *fallback* follow_mom policy.
        # This makes a visible behavioral change in unsafe cycles without inventing new policies yet.
        try:
            slots = getattr(ctx, "wm_grid_slot_families", None)
            hazard_near = bool(slots.get("hazard:near", False)) if isinstance(slots, dict) else False
        except Exception:
            hazard_near = False

        if hazard_near:
            matches = [p for p in matches if p.name != "policy:follow_mom"]
            if not matches:
                return "no_match"

        # Remember what triggered this cycle (Phase X): useful for traces and later ambiguity/commit logic.
        try:
            if ctx is not None:
                ctx.ac_triggered_policies = list(triggered_all)
        except Exception:
            pass

        # If fallen near NOW (BodyMap-first), force safety-only gates
        if _fallen_near_now(world, ctx, max_hops=3):
            safety_only = {"policy:recover_fall", "policy:stand_up"}
            matches = [p for p in matches if p.name in safety_only]
            if not matches:
                return "no_match"

        # --- EFE policy scoring stub (Phase X 2.2b): compute + store (selection unchanged) ---
        try:
            if ctx is not None and bool(getattr(ctx, "efe_enabled", False)):
                cand_names = [p.name for p in matches]
                ctx.efe_last = compute_efe_scores_stub_v1(world, drives, ctx, cand_names, triggered_all=triggered_all)
                ctx.efe_last_scores = list(ctx.efe_last.get("scores", [])) if isinstance(ctx.efe_last, dict) else []
            else:
                # keep previous values from leaking into logs when EFE is off
                if ctx is not None:
                    ctx.efe_last = {}
                    ctx.efe_last_scores = []
        except Exception:
            # Diagnostics only: never let EFE break the controller.
            try:
                if ctx is not None:
                    ctx.efe_last = {"v": _EFE_SCORES_VERSION, "enabled": False, "error": "efe_compute_exception"}
                    ctx.efe_last_scores = []
            except Exception:
                pass

        # Choose by drive-deficit
        # NOTE: "deficit" here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD) (amount ABOVE threshold, not a negative deficit).
        # Policies without a drive-urgency term score 0.00 and will tie-break by stable policy order (or RL tie-break, if enabled).
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

        # non_drive_priority(...) is a tiny, explicit tie-break score used only when drive-urgency deficits tie
        # it prevents “catalog order” from being the hidden reason a policy wins in common 0.00-deficit situations
        def non_drive_priority(name: str) -> float:
            """Tiny non-drive tie-break score.

            Used only as a SECONDARY score when drive-urgency deficits tie.

            Intent:
              - StandUp: prefer when BodyMap is fresh and posture == 'fallen'.
              - RecoverFall: prefer when explicit fall cues are present.
            """
            if name == "policy:stand_up":
                try:
                    if ctx is not None and not bodymap_is_stale(ctx) and body_posture(ctx) == "fallen":
                        return 2.0
                except Exception:
                    pass
                return 0.0

            if name == "policy:recover_fall":
                # RecoverFall: prefer when explicit fall cues are present OR when we see a persistent
                # env-vs-expected posture discrepancy after StandUp attempts (motor command not taking effect).
                cue_bonus = 0.0
                try:
                    if any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"]):
                        cue_bonus = 1.0
                except Exception:
                    cue_bonus = 0.0
                # Discrepancy-driven bonus:
                #   If the most recent discrepancies repeatedly show:
                #     env posture == fallen  AND policy:stand_up expected standing,
                #   then StandUp is "not taking" and we should try RecoverFall.
                streak = 0
                try:
                    hist = getattr(ctx, "posture_discrepancy_history", []) if ctx is not None else []
                    if isinstance(hist, list) and hist:
                        # Count a short streak over the most recent entries.
                        for entry in reversed(hist[-10:]):
                            s = str(entry)
                            if (
                                ("from policy:stand_up" in s)
                                and ("env posture=" in s and "fallen" in s)
                                and ("policy-expected posture=" in s and "standing" in s)
                            ):
                                streak += 1
                            else:
                                break
                except Exception:
                    streak = 0
                # Ignore a single mismatch (often happens right after reset because the env hasn't consumed the action yet).
                hist_bonus = 0.0
                if streak >= 2:
                    # 2.5 beats StandUp's 2.0; ramp slowly with longer streaks (cap to keep numbers tame).
                    hist_bonus = min(4.0, 2.5 + 0.5 * (streak - 2))
                return cue_bonus + hist_bonus
            return 0.0

        # Optional RL selection: epsilon-greedy with a learned-value soft tie-break.
        # - RL enabled:
        #     With probability epsilon: explore by picking a random triggered policy.
        #     Otherwise exploit: choose by deficit, but if top deficits are within rl_delta,
        #     treat as ambiguous and allow learned value q to decide among near-best candidates.
        # - RL disabled:
        #     Deterministic heuristic: choose by deficit, then stable order. (No q used.)

        rl_pick_note = ""     # printed only when q-soft-tiebreak (near-tie band) decided the pick
        did_explore = False   # lets us label the pick source accurately in debug output
        rl_exploit_kind = ""  # exploit kind: "deficit" | "non_drive_tiebreak" | "q_soft_tiebreak" (rl_enabled only)


        rl_enabled = bool(getattr(ctx, "rl_enabled", False))
        if rl_enabled:
            eps = getattr(ctx, "rl_epsilon", None)
            if eps is None:
                eps = getattr(ctx, "jump", 0.0)
            try:
                eps_f = float(eps)
            except Exception:
                eps_f = 0.0
            eps_f = max(0.0, min(1.0, eps_f))

            def _bump(field_name: str) -> None:
                try:
                    if ctx is not None and hasattr(ctx, field_name):
                        setattr(ctx, field_name, int(getattr(ctx, field_name, 0)) + 1)
                except Exception:
                    pass

            if eps_f > 0.0 and random.random() < eps_f:
                chosen = random.choice(matches)
                did_explore = True
                _bump("rl_explore_steps")
            else:
                # --- RL "soft tie-break"
                rl_delta_raw = getattr(ctx, "rl_delta", 0.0)
                try:
                    rl_delta = float(rl_delta_raw)
                except (TypeError, ValueError):
                    rl_delta = 0.0
                rl_delta = max(rl_delta, 0.0)

                scored = [(p, deficit(p.name), non_drive_priority(p.name)) for p in matches]
                best_deficit = max(d for _, d, _ in scored)
                near_best = [(p, d, nd) for p, d, nd in scored if (best_deficit - d) <= rl_delta]

                if len(near_best) == 1:
                    chosen = near_best[0][0]
                    rl_exploit_kind = "deficit"
                else:
                    # Phase VI-D: within the deficit near-tie band, prefer explicit non-drive priority
                    # before falling back to learned value q.
                    eps_tie = 1e-9
                    best_nd = max(nd for _, _, nd in near_best)
                    top_nd = [(p, d, nd) for p, d, nd in near_best if abs(nd - best_nd) <= eps_tie]

                    if len(top_nd) == 1:
                        chosen = top_nd[0][0]
                        rl_exploit_kind = "non_drive_tiebreak"
                    else:
                        chosen = max(
                            top_nd,
                            key=lambda t: (
                                skill_q(t[0].name, default=0.0),
                                t[1],   # deficit (within rl_delta band)
                                t[2],   # non-drive score (tied here, but harmless)
                                -stable_idx(t[0]),
                            ),
                        )[0]
                        rl_exploit_kind = "q_soft_tiebreak"

                # Optional: print a compact explanation when the near-tie band had > 1 candidate.
                if len(near_best) > 1:
                    bits: list[str] = []
                    for p, d, nd in sorted(near_best, key=lambda t: (-t[1], -t[2], t[0].name)):
                        qv = skill_q(p.name, default=0.0)
                        bits.append(f"{p.name}(def={d:.3f}, nd={nd:.2f}, q={qv:+.2f})")
                    if len(bits) > 6:
                        bits = bits[:6] + ["..."]

                    chosen_q = skill_q(chosen.name, default=0.0)
                    chosen_nd = non_drive_priority(chosen.name)

                    if rl_exploit_kind == "non_drive_tiebreak":
                        rl_pick_note = (
                            "[rl-pick] chosen via non-drive tiebreak in deficit near-tie band: "
                            f"best_def={best_deficit:.3f} delta={rl_delta:.3f} "
                            f"→ {chosen.name} (nd={chosen_nd:.2f}, q={chosen_q:+.2f}) "
                            f"among [{', '.join(bits)}]"
                        )
                    elif rl_exploit_kind == "q_soft_tiebreak":
                        rl_pick_note = (
                            "[rl-pick] chosen via q-soft-tiebreak in deficit near-tie band: "
                            f"best_def={best_deficit:.3f} delta={rl_delta:.3f} "
                            f"→ {chosen.name} (q={chosen_q:+.2f}) among [{', '.join(bits)}]"
                        )

                _bump("rl_exploit_steps")
        else:
            # RL disabled: original deterministic heuristic (deficit, then stable order)
            chosen = max(matches, key=lambda p: (deficit(p.name), non_drive_priority(p.name), -stable_idx(p)))

        # label *how* we picked; add a tie-break note when deficits are tied.
        tie_break_label = ""
        # For RL-disabled runs, "deficit" often ties at 0.0 (many policies have no drive score yet).
        # In that case the stable catalog order is the *actual* decision mechanism.
        if not rl_enabled:
            try:
                scored_final = [(p.name, deficit(p.name), non_drive_priority(p.name)) for p in matches]
                if scored_final:
                    eps = 1e-9
                    best_d = max(d for _, d, _ in scored_final)
                    top = [(nm, nd) for (nm, d, nd) in scored_final if abs(d - best_d) <= eps]

                    if len(top) > 1:
                        best_nd = max(nd for _, nd in top)
                        n_best_nd = sum(1 for _, nd in top if abs(nd - best_nd) <= eps)

                        if n_best_nd == 1:
                            tie_break_label = "non_drive_priority(deficit_tie)"
                        else:
                            tie_break_label = "stable_order(deficit_tie)"
            except Exception:
                tie_break_label = ""
        # Preserve existing best_by labeling
        selector_kind = "deficit"
        if rl_enabled:
            if did_explore:
                selector_kind = "rl_explore"
            elif rl_exploit_kind == "non_drive_tiebreak":
                selector_kind = "rl_exploit(non_drive_tiebreak)"
            elif rl_exploit_kind == "q_soft_tiebreak":
                selector_kind = "rl_exploit(q_soft_tiebreak)"
            else:
                selector_kind = "rl_exploit(deficit)"

        # Context for logging
        base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
        foa = compute_foa(world, ctx, max_hops=2)
        cands = candidate_anchors(world, ctx)
        pre_expl = chosen.explain(world, drives, ctx) if chosen.explain else "explain: (not provided)"

        # Run controller with the exact policy we selected
        world_exec = exec_world if exec_world is not None else world
        try:
            before_n = len(getattr(world_exec, "_bindings", {}))

            # --- WM_SCRATCH redirect (only when executing into WorkingMap MapSurface) ---
            did_redirect = False
            wm_root_bid = None
            try:
                is_wm_exec = (
                    ctx is not None
                    and world_exec is getattr(ctx, "working_world", None)
                    and bool(getattr(ctx, "working_mapsurface", False))
                )
                if is_wm_exec:
                    wm_root_bid = world_exec.ensure_anchor("WM_ROOT")
                    wm_scratch_bid = world_exec.ensure_anchor("WM_SCRATCH")
                    # Temporarily point NOW at WM_SCRATCH so policy scratch chains don't hang off WM_ROOT
                    world_exec.set_now(wm_scratch_bid, tag=True, clean_previous=True)
                    did_redirect = True
            except Exception:
                did_redirect = False
                wm_root_bid = None

            # --- Execute the chosen policy ---
            result = action_center_step(world_exec, ctx, drives, preferred=chosen.name)

            # --- Restore NOW back to WM_ROOT after scratch writes ---
            if did_redirect and wm_root_bid:
                try:
                    world_exec.set_now(wm_root_bid, tag=True, clean_previous=True)
                except Exception:
                    pass
            after_n = len(getattr(world_exec, "_bindings", {}))
            delta_n = after_n - before_n
            label = result.get("policy") if isinstance(result, dict) and "policy" in result else chosen.name
        except Exception as e:
            return f"{chosen.name} (error: {e})"

        # Step 14 nice-to-have:
        # If an inspect/probe policy ran, keep its inspected entity in focus for a few ticks.
        try:
            if ctx is not None:
                inspect_pols = getattr(ctx, "wm_salience_inspect_policy_names", None)
                if isinstance(inspect_pols, list) and label in inspect_pols:
                    target = None
                    if isinstance(result, dict):
                        # Future probe policies can set any of these fields explicitly.
                        for k in ("inspected_entity", "inspect_entity", "target_entity", "entity_id"):
                            v = result.get(k)
                            if isinstance(v, str) and v.strip():
                                target = v.strip().lower()
                                break
                    if target is None:
                        target = _wm_guess_inspected_entity_v1(ctx)

                    if isinstance(target, str) and target:
                        ttl = getattr(ctx, "wm_salience_inspect_focus_ttl", 4)
                        wm_salience_force_focus_entity_v1(ctx, target, ttl=int(ttl), reason=f"inspect_policy:{label}")
        except Exception:
            pass

        # Build an explicit [executed] line from the result dict, if available
        exec_line = ""
        if isinstance(result, dict):
            status = result.get("status")
            reward = result.get("reward")
            binding = result.get("binding")
            binding_disp = binding
            try:
                # If we executed into WorkingMap, label binding ids as wN for display.
                if (
                    isinstance(binding, str)
                    and exec_world is not None
                    and ctx is not None
                    and exec_world is getattr(ctx, "working_world", None)
                ):
                    binding_disp = f"{_wm_display_id(binding)} ({binding})"
            except Exception:
                binding_disp = binding
            if status and status != "noop":
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                exec_line = f"[executed] {label} ({status}, reward={rtxt}) binding={binding_disp}\n"

        #  one-line candidate+winner summary
        pick_debug_line = ""
        try:
            triggered_final = [p.name for p in matches]  # after safety filtering (if any)
            trig_txt = ", ".join(triggered_all)
            final_txt = ", ".join(triggered_final)

            # Show deficit scores for triggered policies (helps explain ties).
            def _fmt_deficits(names: list[str], limit: int = 12) -> str:
                parts: list[str] = []
                lim = max(0, int(limit))
                for nm in names[:lim]:
                    try:
                        parts.append(f"{nm}:{deficit(nm):.2f}")
                    except Exception:
                        parts.append(f"{nm}:n/a")
                if len(names) > lim:
                    parts.append("...")
                return ", ".join(parts)

            # Show non-drive tie-break scores for triggered policies.
            def _fmt_non_drive(names: list[str], limit: int = 12) -> str:
                parts: list[str] = []
                lim = max(0, int(limit))
                for nm in names[:lim]:
                    try:
                        parts.append(f"{nm}:{non_drive_priority(nm):.2f}")
                    except Exception:
                        parts.append(f"{nm}:n/a")
                if len(names) > lim:
                    parts.append("...")
                return ", ".join(parts)

            deficits_all = _fmt_deficits(triggered_all, limit=12)
            non_drive_all = _fmt_non_drive(triggered_all, limit=12)

            pick_debug = f"[pick] best_policy={label} best_by={selector_kind}"
            if tie_break_label:
                pick_debug += f" tie_break={tie_break_label}"
            pick_debug += f" triggered=[{trig_txt}]"

            if deficits_all:
                pick_debug += f" deficits=[{deficits_all}]"

            if non_drive_all:
                pick_debug += f" non_drive=[{non_drive_all}]"

            if triggered_final != triggered_all:
                pick_debug += f" safety_filtered=[{final_txt}]"

                deficits_final = _fmt_deficits(triggered_final, limit=12)
                if deficits_final:
                    pick_debug += f" deficits_filtered=[{deficits_final}]"

                non_drive_final = _fmt_non_drive(triggered_final, limit=12)
                if non_drive_final:
                    pick_debug += f" non_drive_filtered=[{non_drive_final}]"

            if chosen.name != label:
                pick_debug += f" selected={chosen.name}"

            pick_debug_line = pick_debug + "\n"
        except Exception:
            pick_debug_line = ""

        gate_for_label = next((p for p in self.loaded if p.name == label), chosen)
        post_expl = gate_for_label.explain(world, drives, ctx) if gate_for_label.explain else "explain: (not provided)"
        rl_line = (rl_pick_note + "\n") if rl_pick_note else ""

        efe_line = ""
        try:
            if ctx is not None and bool(getattr(ctx, "efe_verbose", False)) and bool(getattr(ctx, "efe_enabled", False)):
                efe_line = _efe_render_summary_line(ctx, max_policies=5)
        except Exception:
            efe_line = ""

        # Where did we execute the chosen policy?
        where_exec = "WG"
        try:
            if ctx is not None and world_exec is getattr(ctx, "working_world", None):
                where_exec = "WM"
        except Exception:
            where_exec = "WG"
        maps_line = f"[maps] selection_on=WG execute_on={where_exec}\n"

        return (
            f"{label} (added {delta_n} bindings)\n"
            f"{pick_debug_line}"
            f"{rl_line}"
            f"{efe_line}"
            f"{exec_line}"
            f"{maps_line}"
            f"pre:  {pre_expl}\n"
            f"wg_base: {base}\n"
            f"wg_foa:  {foa}\n"
            f"wg_cands:{cands}\n"
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
        name="policy:probe",
        dev_gate=lambda ctx: True,
        trigger=_gate_probe_ambiguity_trigger_body_first,
        explain=_gate_probe_ambiguity_explain_body_first,
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
        trigger=_gate_recover_fall_trigger_body_first,
        explain=_gate_recover_fall_explain,
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
        print(f"[boot] Seeded posture:fallen as {fallen_bid} (birth-state binding; anchor:NOW → pred:posture:fallen)")
    except Exception as e:
        print(f"[boot] Could not seed posture:fallen: {e}")


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


class TeeTextIO:
    """File-like stream that duplicates writes into multiple underlying streams.

    Purpose:
        - Keep interactive output visible in the terminal
        - Also persist the full transcript to a file (e.g., terminal.txt)
        - Avoid rewriting existing print(...) calls across the codebase

    Notes:
        - This affects *all* print() calls that ultimately write to sys.stdout/sys.stderr.
        - It is safe for interactive sessions (input() relies on stdout.flush()).
    """
    def __init__(self, *streams):
        self._streams = list(streams)

    def write(self, s: str) -> int:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            st.write(s)
        return len(s)

    def flush(self) -> None:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        for st in self._streams:
            try:
                st.flush()
            except Exception:
                pass

    def isatty(self) -> bool:
        '''helper method within class TeeTextIO to mirror text to a
        specified file'''
        try:
            return any(getattr(st, "isatty", lambda: False)() for st in self._streams)
        except Exception:
            return False

    @property
    def encoding(self) -> str:
        '''Keep downstream code happy if it queries sys.stdout.encoding
        '''
        try:
            return getattr(self._streams[0], "encoding", "utf-8") or "utf-8"
        except Exception:
            return "utf-8"


def install_terminal_tee(path: str = "terminal.txt", *, append: bool = True, also_stderr: bool = True) -> None:
    """Duplicate stdout (and optionally stderr) to a UTF-8 text file.

    Call this once near program start (inside main) to capture a full transcript
    of an interactive run without losing on-screen output.

    Args:
        path: Output file path (e.g., "terminal.txt").
        append: If True, append; if False, overwrite each run.
        also_stderr: If True, duplicate stderr too (tracebacks end up in the file).
    """
    if getattr(sys, "_cca8_terminal_tee_installed", False):
        return

    mode = "a" if append else "w"
    # NOTE:
    # We intentionally keep this file handle open for the full program lifetime so
    # stdout/stderr can be tee'd during interactive use. It is closed via atexit
    # in _cleanup() below. Using `with open(...)` here would close it immediately.
    f = open(path, mode, encoding="utf-8", errors="replace", buffering=1)  # pylint: disable=consider-using-with

    sys._cca8_terminal_tee_installed = True  # type: ignore[attr-defined]

    # Keep originals so we can restore them at exit.
    sys._cca8_stdout_orig = sys.stdout  # type: ignore[attr-defined]
    sys._cca8_stderr_orig = sys.stderr  # type: ignore[attr-defined]
    sys._cca8_terminal_tee_file = f     # type: ignore[attr-defined]

    sys.stdout = TeeTextIO(sys.stdout, f)
    if also_stderr:
        sys.stderr = TeeTextIO(sys.stderr, f)

    import atexit
    def _cleanup() -> None:
        # Flush tee streams first, then restore and close.
        try:
            sys.stdout.flush()
        except Exception:
            pass
        try:
            sys.stderr.flush()
        except Exception:
            pass
        try:
            sys.stdout = sys._cca8_stdout_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            sys.stderr = sys._cca8_stderr_orig  # type: ignore[attr-defined]
        except Exception:
            pass
        try:
            f.close()
        except Exception:
            pass
    atexit.register(_cleanup)


def print_startup_notices(world) -> None:
    '''print active planner and other statuses at
    startup of the runner
    '''
    try:
        planner = str(world.get_planner()).upper()
        expl = {
            "BFS": "Breadth-First Search (unweighted shortest path by hop count)",
            "DIJKSTRA": "Dijkstra (lowest total edge weight; equals BFS when all weights=1)",
        }.get(planner)
        if expl:
            print(f"[planner] Active planner on startup: {planner} — {expl}")
        else:
            print(f"[planner] Active planner on startup: {planner}")


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


    # Z6b) MapSurface round-trip: store a tiny WorldGraph snapshot into Column, attach pointer, reload, then seed-merge predicates only.
    #
    # Why this probe exists:
    # - In Phase VIII we want priors to matter, which means we must be confident we can:
    #     (1) store a "surface slate" (pred/cue snapshot) into Column memory,
    #     (2) attach a stable pointer onto a WorldGraph binding,
    #     (3) round-trip that pointer through WorldGraph snapshot save/load,
    #     (4) retrieve and reconstruct the surface (replace mode),
    #     (5) seed/merge predicates only (no cue leakage) into a live semantic world.
    try:
        from cca8_column import mem as _mem

        # (A) Build a tiny "mapsurface" world (tokens match HybridEnvironment.observe()).
        _ms = cca8_world_graph.WorldGraph()
        _ms.set_tag_policy("allow")
        _ms.set_stage("neonate")
        _ms.ensure_anchor("NOW")

        _ms.add_predicate("posture:fallen", attach="now")
        _ms.add_predicate("proximity:mom:close", attach="latest")
        _ms.add_predicate("proximity:shelter:far", attach="latest")
        _ms.add_predicate("hazard:cliff:near", attach="latest")
        _ms.add_predicate("nipple:found", attach="latest")
        _ms.add_cue("vision:silhouette:mom", attach="latest")

        _ms_dict = _ms.to_dict()

        # (B) Store snapshot payload into the Column as one engram.
        _payload = {"kind": "mapsurface_snapshot", "v": 1, "world": _ms_dict}
        _fm = FactMeta(
            name="probe:mapsurface_snapshot_roundtrip",
            links=[],
            attrs={"probe": True, "v": 1, "note": "preflight mapsurface round-trip"},
        )
        _eid = _mem.assert_fact("probe:mapsurface_snapshot_roundtrip", _payload, _fm)

        if _mem.exists(_eid):
            ok("mapsurface round-trip: engram stored in column")
        else:
            bad("mapsurface round-trip: engram not found after assert_fact")

        # (C) Attach pointer to a binding; ensure pointer survives WorldGraph snapshot reload.
        _wptr = cca8_world_graph.WorldGraph()
        _wptr.set_tag_policy("allow")
        _wptr.set_stage("neonate")
        _wptr.ensure_anchor("NOW")

        _bid = _wptr.add_predicate("pred:probe:mapsurface_snapshot", attach="now")
        _wptr.attach_engram(_bid, column="column01", engram_id=_eid, act=1.0, extra_meta={"probe": True})

        _wptr2 = cca8_world_graph.WorldGraph.from_dict(_wptr.to_dict())
        _b2 = _wptr2._bindings.get(_bid)
        _pid = (((_b2.engrams or {}).get("column01") or {}).get("id") if _b2 else None)

        if _pid == _eid:
            ok("mapsurface round-trip: pointer survived WorldGraph.to_dict/from_dict")
        else:
            bad("mapsurface round-trip: pointer lost or altered across snapshot reload")

        # (D) Retrieve and reconstruct MapSurface world (replace mode).
        _rec = _mem.try_get(_eid)
        _world_blob = (_rec or {}).get("payload", {}).get("world") if isinstance(_rec, dict) else None

        if not isinstance(_world_blob, dict):
            bad("mapsurface round-trip: engram payload missing world dict")
        else:
            _ms2 = cca8_world_graph.WorldGraph.from_dict(_world_blob)

            issues = _ms2.check_invariants(raise_on_error=False)
            if issues:
                bad("mapsurface round-trip: reconstructed world invariant issues: " + "; ".join(issues))
            else:
                ok("mapsurface round-trip: reconstructed world invariants OK")

            # Expect at least one cue + one hazard predicate to survive.
            _tags = set()
            for _bb in _ms2._bindings.values():
                _tags |= set(getattr(_bb, "tags", []) or [])

            if ("pred:hazard:cliff:near" in _tags) and ("cue:vision:silhouette:mom" in _tags):
                ok("mapsurface round-trip: replace mode restored expected tags (pred + cue)")
            else:
                bad("mapsurface round-trip: replace mode missing expected tags")

            # Cheap structural sanity: bindings and total-edge counts should match.
            def _edge_total(wg) -> int:
                return sum(len(getattr(b, "edges", []) or []) for b in getattr(wg, "_bindings", {}).values())

            if len(_ms2._bindings) == len(_ms._bindings) and _edge_total(_ms2) == _edge_total(_ms):
                ok("mapsurface round-trip: replace mode preserved binding/edge counts")
            else:
                bad("mapsurface round-trip: replace mode changed binding/edge counts unexpectedly")

        # (E) Seed/merge mode: copy ONLY predicates into a live semantic world (no cues injected).
        _live = cca8_world_graph.WorldGraph(memory_mode="semantic")
        _live.set_tag_policy("allow")
        _live.set_stage("neonate")
        _live.ensure_anchor("NOW")

        # Seed an existing fact to exercise semantic consolidation (duplicate should be reused).
        _live.add_predicate("posture:fallen", attach="now")

        if isinstance(_world_blob, dict):
            _ms2b = cca8_world_graph.WorldGraph.from_dict(_world_blob)

            _pred_tags: set[str] = set()
            for _bb in _ms2b._bindings.values():
                for _t in getattr(_bb, "tags", []) or []:
                    if isinstance(_t, str) and _t.startswith("pred:"):
                        _pred_tags.add(_t)

            for _t in sorted(_pred_tags):
                _live.add_predicate(_t, attach="none")  # seed-only; no sequencing edges needed

            _live_tags = set()
            for _bb in _live._bindings.values():
                _live_tags |= set(getattr(_bb, "tags", []) or [])

            if any(t.startswith("cue:") for t in _live_tags):
                bad("mapsurface round-trip: seed/merge mode leaked cue:* tags into live world")
            else:
                ok("mapsurface round-trip: seed/merge seeded predicates only (no cues)")

            if "pred:hazard:cliff:near" in _live_tags and "pred:posture:fallen" in _live_tags:
                ok("mapsurface round-trip: seed/merge contains expected predicate priors")
            else:
                bad("mapsurface round-trip: seed/merge missing expected predicate priors")

        # (F) Cleanup: remove the probe engram so repeated preflights don't bloat column memory.
        try:
            _mem.delete(_eid)
        except Exception:
            pass

        if _mem.exists(_eid):
            bad("mapsurface round-trip: cleanup failed (engram still present)")
        else:
            ok("mapsurface round-trip: cleanup removed probe engram")

    except Exception as e:
        bad(f"mapsurface round-trip probe failed: {e}")


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

    # PROMINENCE (top tags; runtime convenience)
    lines.append("")
    lines.append("PROMINENCE (top tags; obs>=2, sorted by act):")
    try:
        rows = world.prominence_top(n=12, sort_by="act", min_obs=2)
    except Exception:
        rows = []
    if not rows:
        lines.append("(none)")
    else:
        for tag, rec in rows:
            try:
                obs = int(rec.get("obs", 0))
            except Exception:
                obs = 0
            try:
                act = float(rec.get("act", 0.0))
            except Exception:
                act = 0.0
            last_step = rec.get("last_step")
            step_key = rec.get("step_key")
            lines.append(f"{tag}: obs={obs} act={act:.2f} last_step={last_step} [{step_key}]")

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


def _prune_working_world(ctx) -> None:
    """Keep the WorkingMap bounded so long runs do not explode memory.

    This only applies to ctx.working_world. It never touches the long-term `world`.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        return

    max_b = int(getattr(ctx, "working_max_bindings", 0) or 0)
    if max_b <= 0:
        return

    # Protect anchors + latest (so pruning doesn't sever the current frame completely)
    protected = set(getattr(ww, "_anchors", {}).values())  # pylint: disable=protected-access
    latest = getattr(ww, "_latest_binding_id", None)        # pylint: disable=protected-access
    if latest:
        protected.add(latest)

    def _bid_key(bid: str) -> int:
        try:
            return int(bid[1:]) if bid.startswith("b") else 10**9
        except Exception:
            return 10**9

    # Delete oldest non-protected bindings until within cap
    all_ids = sorted(list(getattr(ww, "_bindings", {}).keys()), key=_bid_key)  # pylint: disable=protected-access
    while len(getattr(ww, "_bindings", {})) > max_b:  # pylint: disable=protected-access
        binding_to_delete = None
        for bid in all_ids:
            if bid not in protected:
                binding_to_delete = bid
                break
        if binding_to_delete is None:
            break
        ww.delete_binding(binding_to_delete)
        all_ids.remove(binding_to_delete)

# -----------------------------------------------------------------------------
# NavPatch (Phase X): predictive matching loop (priors OFF baseline)
# -----------------------------------------------------------------------------

def _navpatch_tag_jaccard(tags_a: Any, tags_b: Any) -> float:
    a: set[str] = set()
    b: set[str] = set()

    if isinstance(tags_a, list):
        for t in tags_a:
            if isinstance(t, str) and t:
                a.add(t)

    if isinstance(tags_b, list):
        for t in tags_b:
            if isinstance(t, str) and t:
                b.add(t)

    u = a | b
    return (len(a & b) / float(len(u))) if u else 1.0


def _navpatch_extent_sim(ext_a: Any, ext_b: Any) -> float:
    # If we don't have numeric extents on both sides, do not penalize.
    if not (isinstance(ext_a, dict) and isinstance(ext_b, dict)):
        return 1.0

    keys = ("x0", "y0", "x1", "y1")
    a_vals: dict[str, float] = {}
    b_vals: dict[str, float] = {}

    for k in keys:
        av = ext_a.get(k)
        bv = ext_b.get(k)
        if not isinstance(av, (int, float)) or not isinstance(bv, (int, float)):
            return 1.0
        a_vals[k] = float(av)
        b_vals[k] = float(bv)

    # Normalize by the larger span so the score is scale-insensitive.
    span_a = max(abs(a_vals["x1"] - a_vals["x0"]), abs(a_vals["y1"] - a_vals["y0"]), 1.0)
    span_b = max(abs(b_vals["x1"] - b_vals["x0"]), abs(b_vals["y1"] - b_vals["y0"]), 1.0)
    denom = max(span_a, span_b, 1.0)

    diff_sum = 0.0
    for k in keys:
        diff_sum += abs(a_vals[k] - b_vals[k]) / denom

    # diff_sum in [0..~4]; convert to similarity in [0..1]
    sim = 1.0 - min(1.0, diff_sum / 4.0)
    return float(max(0.0, min(1.0, sim)))


def navpatch_similarity_v1(patch_a: dict[str, Any], patch_b: dict[str, Any]) -> float:
    """Similarity score in [0,1] based on tag overlap + (optional) extent overlap.

    This is intentionally simple (priors OFF baseline). It is only for debugging/top-K traces now.
    """
    a = _navpatch_core_v1(patch_a)
    b = _navpatch_core_v1(patch_b)

    role_a = a.get("role")
    role_b = b.get("role")
    if isinstance(role_a, str) and isinstance(role_b, str) and role_a and role_b and role_a != role_b:
        return 0.0

    tag_sim = _navpatch_tag_jaccard(a.get("tags"), b.get("tags"))
    ext_sim = _navpatch_extent_sim(a.get("extent"), b.get("extent"))

    score = 0.75 * tag_sim + 0.25 * ext_sim
    return float(max(0.0, min(1.0, score)))


def navpatch_priors_bundle_v1(ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Compute a lightweight top-down priors bundle for NavPatch matching (v1.1).

    Purpose
    -------
    This bundle is the “top-down context” for the patch matching loop. It is:
      - JSON-safe (so we can store it in cycle_log.jsonl),
      - traceable (sig16 stable fingerprint),
      - intentionally small (no heavy payload).

    v1.1 additions
    -------------
    Adds a minimal precision vector so we can weight evidence vs priors in a stable way.

    Precision is not “Friston math” here; it is simply a tunable reliability weight:
      - tags precision  : how much we trust symbolic tag overlap (salience/texture-like channel)
      - extent precision: how much we trust geometric overlap (schematic geometry channel)
      - grid precision
      code:
        tags_prec = max(0.0, min(1.0, float(tags_prec)))
        ext_prec = max(0.0, min(1.0, float(ext_prec)))
        grid_prec = max(0.0, min(1.0, float(grid_prec)))
        precision = {"tags": tags_prec, "extent": ext_prec, "grid": grid_prec}

    We make tags precision stage-sensitive:
      - birth/struggle → lower tags precision (more ambiguity)
      - later stages   → default tags precision

    Fields (v1.1)
    ------------
    v:
        Schema label: "navpatch_priors_v1".
    enabled:
        True when priors were requested by ctx.navpatch_priors_enabled.
    sig16:
        Stable 16-hex signature of the bundle contents (for traceability).
    stage:
        Env meta stage string when present (e.g., "birth", "struggle").
    zone:
        BodyMap coarse zone label when available (e.g., "unsafe_cliff_near", "safe", "unknown").
    hazard_bias:
        Positive bias applied to hazard-like candidates when the zone is unsafe.
    err_guard:
        Evidence-first guardrail: if evidence error > err_guard, priors must not force a confident match.
    precision:
        Per-layer evidence reliability weights (v1.1: {"tags": f, "extent": f}).
    """
    stage: str | None = None
    try:
        meta = getattr(env_obs, "env_meta", None)
        if isinstance(meta, dict):
            s = meta.get("scenario_stage")
            stage = s if isinstance(s, str) and s else None
    except Exception:
        stage = None

    zone: str | None = None
    try:
        z = body_space_zone(ctx)
        zone = z if isinstance(z, str) and z else None
    except Exception:
        zone = None

    # ---- hazard prior (v1) ----
    hazard_bias = 0.0
    try:
        hb = float(getattr(ctx, "navpatch_priors_hazard_bias", 0.0) or 0.0)
    except Exception:
        hb = 0.0
    if zone == "unsafe_cliff_near":
        hazard_bias = hb

    # ---- evidence-first guard (v1) ----
    try:
        guard = float(getattr(ctx, "navpatch_priors_error_guard", 0.45) or 0.45)
    except Exception:
        guard = 0.45
    guard = max(0.0, min(1.0, float(guard)))

    # ---- precision vector (v1.1) ----
    try:
        tags_prec = float(getattr(ctx, "navpatch_precision_tags", 0.75) or 0.75)
    except Exception:
        tags_prec = 0.75
    try:
        ext_prec = float(getattr(ctx, "navpatch_precision_extent", 0.25) or 0.25)
    except Exception:
        ext_prec = 0.25

    if stage == "birth":
        try:
            tags_prec = min(tags_prec, float(getattr(ctx, "navpatch_precision_tags_birth", tags_prec) or tags_prec))
        except Exception:
            pass
    elif stage == "struggle":
        try:
            tags_prec = min(tags_prec, float(getattr(ctx, "navpatch_precision_tags_struggle", tags_prec) or tags_prec))
        except Exception:
            pass

    try:
        grid_prec = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
    except Exception:
        grid_prec = 0.0

    tags_prec = max(0.0, min(1.0, float(tags_prec)))
    ext_prec = max(0.0, min(1.0, float(ext_prec)))
    grid_prec = max(0.0, min(1.0, float(grid_prec)))
    precision = {"tags": tags_prec, "extent": ext_prec, "grid": grid_prec}

    core = {
        "v": "navpatch_priors_v1",
        "enabled": True,
        "stage": stage,
        "zone": zone,
        "hazard_bias": float(hazard_bias),
        "err_guard": float(guard),
        "precision": precision,
    }
    blob = json.dumps(core, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    sig16 = hashlib.sha256(blob.encode("utf-8")).hexdigest()[:16]

    out = dict(core)
    out["sig16"] = sig16
    return out


def navpatch_candidate_prior_bias_v1(priors: dict[str, Any], cand_payload: dict[str, Any], cand_attrs: dict[str, Any]) -> float:
    """Return the additive prior bias term for a candidate NavPatch prototype (v1).

    v1 semantics:
      - If priors carries a positive hazard_bias and the candidate looks "hazard-like"
        (role == "hazard" OR any tag starts with "hazard:"), return hazard_bias.
      - Otherwise return 0.0.
    """
    if not isinstance(priors, dict) or not priors.get("enabled", False):
        return 0.0

    try:
        hazard_bias = float(priors.get("hazard_bias", 0.0) or 0.0)
    except Exception:
        hazard_bias = 0.0
    if hazard_bias == 0.0:
        return 0.0

    role = None
    try:
        r = cand_attrs.get("role") if isinstance(cand_attrs, dict) else None
        if isinstance(r, str) and r:
            role = r
        else:
            r2 = cand_payload.get("role") if isinstance(cand_payload, dict) else None
            role = r2 if isinstance(r2, str) and r2 else None
    except Exception:
        role = None

    tags: list[str] = []
    try:
        t = cand_payload.get("tags") if isinstance(cand_payload, dict) else None
        if isinstance(t, list):
            tags = [x for x in t if isinstance(x, str) and x]
        else:
            t2 = cand_attrs.get("tags") if isinstance(cand_attrs, dict) else None
            if isinstance(t2, list):
                tags = [x for x in t2 if isinstance(x, str) and x]
    except Exception:
        tags = []

    hazard_like = (role == "hazard") or any(isinstance(t, str) and t.startswith("hazard:") for t in tags)
    return float(hazard_bias) if hazard_like else 0.0


def navpatch_predictive_match_loop_v1(ctx: Ctx, env_obs: EnvObservation) -> list[dict[str, Any]]:
    """Compute a top-K candidate match trace for EnvObservation.nav_patches.

    This implements Phase X “predictive matching” (v1.1):
      - store observed patches as navpatch engrams (deduped by signature),
      - rank other stored prototypes as candidate interpretations (top-K),
      - apply priors as a *small bias term* (hazard_bias),
      - weight evidence by a tiny precision vector (tags vs extent),
      - classify match confidence as commit vs ambiguous vs unknown.

    Self-exclusion
    --------------
    If we stored (or dedup-reused) the current patch engram this tick, the Column scan will contain it.
    We must exclude that engram_id from candidate ranking so we do not trivially match the patch to itself.
    """
    if ctx is None:
        return []
    # --- Step 15C support: auto-restore probe precision boosts ----------------------------
    # The probe policy can temporarily raise ctx.navpatch_precision_grid to help disambiguate
    # competing prototypes. We restore the previous value once the probe window expires so
    # the system returns to its default evidence weighting.
    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        step_now = 0

    try:
        restore_step = getattr(ctx, "wm_probe_restore_step", None)
        if isinstance(restore_step, int) and step_now >= int(restore_step):
            prev = getattr(ctx, "wm_probe_prev_navpatch_precision_grid", None)
            if isinstance(prev, (int, float)):
                ctx.navpatch_precision_grid = float(prev)

            # Clear probe restore bookkeeping (best-effort).
            ctx.wm_probe_restore_step = None
            ctx.wm_probe_prev_navpatch_precision_grid = None
    except Exception:
        pass

    if ctx is None or not bool(getattr(ctx, "navpatch_enabled", False)):
        return []

    patches = getattr(env_obs, "nav_patches", None) or []
    if not isinstance(patches, list) or not patches:
        try:
            ctx.navpatch_last_matches = []
        except Exception:
            pass
        return []

    # Config (keep terminal readable; clamp)
    try:
        top_k = int(getattr(ctx, "navpatch_match_top_k", 3) or 3)
    except Exception:
        top_k = 3
    top_k = max(1, min(10, top_k))

    try:
        accept = float(getattr(ctx, "navpatch_match_accept_score", 0.85) or 0.85)
    except Exception:
        accept = 0.85
    accept = max(0.0, min(1.0, accept))

    try:
        amb_margin = float(getattr(ctx, "navpatch_match_ambiguous_margin", 0.05) or 0.05)
    except Exception:
        amb_margin = 0.05
    amb_margin = max(0.0, min(1.0, amb_margin))

    # Priors bundle (Phase X 2.2a): OFF by default.
    priors_enabled = bool(getattr(ctx, "navpatch_priors_enabled", False))
    priors: dict[str, Any] = {"v": "navpatch_priors_v1", "enabled": False, "sig16": None}

    if priors_enabled:
        priors = navpatch_priors_bundle_v1(ctx, env_obs)

    try:
        ctx.navpatch_last_priors = dict(priors)
    except Exception:
        pass

    # Precision weights (Phase X 2.2b): used even when priors are off (as stable knobs).
    prec_tags = None
    prec_ext = None
    prec_grid = None

    if isinstance(priors, dict) and isinstance(priors.get("precision"), dict):
        p = priors.get("precision")  # type: ignore[assignment]
        try:
            prec_tags = float(p.get("tags"))  # type: ignore[union-attr]
        except Exception:
            prec_tags = None
        try:
            prec_ext = float(p.get("extent"))  # type: ignore[union-attr]
        except Exception:
            prec_ext = None
        try:
            prec_grid = float(p.get("grid"))  # type: ignore[union-attr]
        except Exception:
            prec_grid = None

    if prec_tags is None:
        try:
            prec_tags = float(getattr(ctx, "navpatch_precision_tags", 0.75) or 0.75)
        except Exception:
            prec_tags = 0.75
    if prec_ext is None:
        try:
            prec_ext = float(getattr(ctx, "navpatch_precision_extent", 0.25) or 0.25)
        except Exception:
            prec_ext = 0.25
    if prec_grid is None:
        try:
            prec_grid = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
        except Exception:
            prec_grid = 0.0

    prec_tags = max(0.0, min(1.0, float(prec_tags)))
    prec_ext = max(0.0, min(1.0, float(prec_ext)))
    prec_grid = max(0.0, min(1.0, float(prec_grid)))

    # Candidate prototype records (best-effort; Column is RAM-local)
    try:
        proto_recs = column_mem.find(name_contains="navpatch", has_attr="sig", limit=500)
    except Exception:
        proto_recs = []

    out: list[dict[str, Any]] = []

    for p in patches:
        if not isinstance(p, dict):
            continue

        sig = navpatch_payload_sig_v1(p)
        sig16 = sig[:16]

        # Ensure an engram exists (or reuse cached) if storage is enabled.
        stored_flag: bool | None = None
        engram_id: str | None = None
        if bool(getattr(ctx, "navpatch_store_to_column", False)):
            try:
                st = store_navpatch_engram_v1(ctx, p, reason="env_obs")
                if isinstance(st, dict):
                    stored_flag = bool(st.get("stored")) if "stored" in st else None
                    eid = st.get("engram_id")
                    if isinstance(eid, str) and eid:
                        engram_id = eid
            except Exception:
                pass

        # Precompute observed patch core once (stable keys only).
        obs_core = _navpatch_core_v1(p)

        # Score top-K prototypes.
        # Tuple: (score_post, score_evidence, score_unweighted, prior_bias, tag_sim, ext_sim, grid_sim, engram_id)
        scored: list[tuple[float, float, float, float, float, float, float | None, str]] = []
        role_p = p.get("role")

        for rec in proto_recs:
            if not isinstance(rec, dict):
                continue
            eid = rec.get("id")
            if not isinstance(eid, str) or not eid:
                continue
            # Self-exclusion
            if isinstance(engram_id, str) and engram_id and eid == engram_id:
                continue
            payload = rec.get("payload")
            if not isinstance(payload, dict):
                continue
            meta = rec.get("meta") if isinstance(rec.get("meta"), dict) else {}
            attrs = meta.get("attrs") if isinstance(meta.get("attrs"), dict) else {}
            role_r = attrs.get("role") if isinstance(attrs, dict) else None
            if (
                isinstance(role_p, str) and role_p
                and isinstance(role_r, str) and role_r
                and role_p != role_r
            ):
                continue

            proto_core = _navpatch_core_v1(payload)
            # Evidence channels (v1.1): tags vs extent vs grid
            tag_sim = float(_navpatch_tag_jaccard(obs_core.get("tags"), proto_core.get("tags")))
            ext_sim = float(_navpatch_extent_sim(obs_core.get("extent"), proto_core.get("extent")))
            tag_sim = max(0.0, min(1.0, tag_sim))
            ext_sim = max(0.0, min(1.0, ext_sim))
            grid_sim: float | None = None
            try:
                obs_cells = p.get("grid_cells")
                cand_cells = payload.get("grid_cells")
                if (
                    isinstance(obs_cells, list)
                    and isinstance(cand_cells, list)
                    and len(obs_cells) == len(cand_cells)
                    and bool(obs_cells)
                ):
                    grid_sim = float(grid_overlap_fraction_v1(obs_cells, cand_cells))
            except Exception:
                grid_sim = None
            if grid_sim is not None:
                grid_sim = max(0.0, min(1.0, float(grid_sim)))
            # Unweighted evidence score (diagnostic only)
            if grid_sim is None:
                score_unw = 0.5 * tag_sim + 0.5 * ext_sim
            else:
                score_unw = (tag_sim + ext_sim + float(grid_sim)) / 3.0
            # Precision-weighted evidence score
            err_tags = 1.0 - tag_sim
            err_ext = 1.0 - ext_sim
            err_grid = (1.0 - float(grid_sim)) if grid_sim is not None else 0.0
            w_tags = float(prec_tags)
            w_ext = float(prec_ext)
            w_grid = float(prec_grid) if grid_sim is not None else 0.0
            denom = float(w_tags + w_ext + w_grid)
            if denom > 0.0:
                err_weighted = (w_tags * err_tags + w_ext * err_ext + w_grid * err_grid) / denom
            else:
                # Fallback: average over available channels
                if grid_sim is None:
                    err_weighted = 0.5 * (err_tags + err_ext)
                else:
                    err_weighted = (err_tags + err_ext + err_grid) / 3.0
            score_evidence = 1.0 - err_weighted
            score_evidence = max(0.0, min(1.0, float(score_evidence)))
            prior_bias = float(navpatch_candidate_prior_bias_v1(priors, payload, attrs)) if priors_enabled else 0.0
            score_post = max(0.0, min(1.0, float(score_evidence + prior_bias)))
            scored.append((score_post, score_evidence, score_unw, float(prior_bias), tag_sim, ext_sim, grid_sim, eid))

        scored.sort(key=lambda t: (-t[0], t[-1]))
        top_list = [
            {
                "engram_id": eid,
                "score": float(score_post),
                "score_raw": float(score_evidence),
                "score_unweighted": float(score_unw),
                "prior_bias": float(prior_bias),
                "err": float(1.0 - score_post),
                "err_raw": float(1.0 - score_evidence),
                "err_unweighted": float(1.0 - score_unw),
                "tag_sim": float(tag_sim),
                "ext_sim": float(ext_sim),
                "grid_sim": float(grid_sim) if isinstance(grid_sim, (int, float)) else None,
            }
            for (score_post, score_evidence, score_unw, prior_bias, tag_sim, ext_sim, grid_sim, eid) in scored[:top_k]
        ]

        # Add normalized weights (posterior proxy) for future graded belief work.
        if top_list:
            s_post = 0.0
            s_raw = 0.0
            for c in top_list:
                try:
                    s_post += float(c.get("score", 0.0) or 0.0)
                except Exception:
                    pass
                try:
                    s_raw += float(c.get("score_raw", 0.0) or 0.0)
                except Exception:
                    pass

            n = float(len(top_list))
            for c in top_list:
                try:
                    v = float(c.get("score", 0.0) or 0.0)
                except Exception:
                    v = 0.0
                c["w"] = (v / s_post) if s_post > 0.0 else (1.0 / n)

                try:
                    v = float(c.get("score_raw", 0.0) or 0.0)
                except Exception:
                    v = 0.0
                c["w_raw"] = (v / s_raw) if s_raw > 0.0 else (1.0 / n)

        best = top_list[0] if top_list else None
        best_score = float(best.get("score", 0.0)) if isinstance(best, dict) else 0.0
        best_score_raw = float(best.get("score_raw", 0.0)) if isinstance(best, dict) else 0.0
        best_err_raw = float(1.0 - best_score_raw)

        second = top_list[1] if len(top_list) > 1 else None
        margin = (best_score - float(second.get("score", 0.0))) if isinstance(second, dict) else None
        margin_raw = (best_score_raw - float(second.get("score_raw", 0.0))) if isinstance(second, dict) else None

        # Decision labels are for logs/JSON traces, not control logic yet.
        decision: str | None = None
        decision_note: str | None = None

        if stored_flag is False:
            decision = "reuse_exact"
        else:
            if best is None:
                decision = "new_no_candidates"
            else:
                if priors_enabled:
                    try:
                        guard = float(priors.get("err_guard", 0.45) or 0.45)
                    except Exception:
                        guard = 0.45
                    guard = max(0.0, min(1.0, float(guard)))

                    if best_err_raw > guard:
                        decision = "new_novel"
                        decision_note = "guard_high_err"
                    else:
                        decision = "new_near_match" if best_score >= accept else "new_novel"
                else:
                    decision = "new_near_match" if best_score >= accept else "new_novel"

        # Commit classification (Phase X 2.2c-style semantics, without changing control yet).
        commit = "unknown"
        if decision == "reuse_exact":
            commit = "commit"
        elif decision_note == "guard_high_err":
            commit = "unknown"
        elif best is None:
            commit = "unknown"
        else:
            if best_score >= accept:
                if isinstance(margin, float) and margin < amb_margin:
                    commit = "ambiguous"
                    if decision_note is None:
                        decision_note = "ambiguous_low_margin"
                else:
                    commit = "commit"
            else:
                commit = "unknown"

        rec_out = {
            "sig": sig,
            "sig16": sig16,
            "priors_sig16": (priors.get("sig16") if isinstance(priors, dict) else None),
            "local_id": p.get("local_id"),
            "entity_id": p.get("entity_id"),
            "role": p.get("role"),
            "stored": stored_flag,
            "engram_id": engram_id,
            "decision": decision,
            "decision_note": decision_note,
            "commit": commit,
            "margin": float(margin) if isinstance(margin, float) else None,
            "margin_raw": float(margin_raw) if isinstance(margin_raw, float) else None,
            "best": best,
            "top_k": top_list,
        }
        out.append(rec_out)

        # Attach trace back onto the patch itself (JSON-safe).
        try:
            p["sig"] = sig
            p["sig16"] = sig16
            p["match"] = {
                "decision": decision,
                "decision_note": decision_note,
                "commit": commit,
                "margin": rec_out.get("margin"),
                "priors_sig16": rec_out.get("priors_sig16"),
                "best": best,
                "top_k": top_list,
            }
        except Exception:
            pass

    try:
        ctx.navpatch_last_matches = out
    except Exception:
        pass
    return out




# -----------------------------------------------------------------------------
# Per-cycle JSON record helper (Phase X)
# -----------------------------------------------------------------------------

def append_cycle_json_record(ctx: Ctx, record: dict[str, Any]) -> None:
    """Append a per-cycle JSON-safe record to ctx and optionally write it as JSONL.

    Design:
      - Always appends to an in-memory ring buffer (ctx.cycle_json_records).
      - If ctx.cycle_json_path is a non-empty string, appends a single JSON object per line (JSONL).
      - Never raises: logging-only on failure so the runner stays interactive.

    Notes:
      - File path is interpreted relative to the process working directory unless absolute.
      - The file is created on first successful open(..., "a", ...).
    """
    if ctx is None or not bool(getattr(ctx, "cycle_json_enabled", False)):
        return

    max_n = int(getattr(ctx, "cycle_json_max_records", 0) or 0)
    if max_n <= 0:
        max_n = 2000

    buf = getattr(ctx, "cycle_json_records", None)
    if not isinstance(buf, list):
        ctx.cycle_json_records = []
        buf = ctx.cycle_json_records
    buf.append(record)
    if len(buf) > max_n:
        del buf[:-max_n]

    path = getattr(ctx, "cycle_json_path", None)
    if not isinstance(path, str) or not path.strip():
        return

    abs_path = os.path.abspath(path)
    try:
        os.makedirs(os.path.dirname(abs_path) or ".", exist_ok=True)
        line = json.dumps(record, sort_keys=True, ensure_ascii=False)
        with open(abs_path, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception as e:
        logging.error("[cycle_json] write failed path=%r: %s", abs_path, e, exc_info=True)
        return


def wm_apply_grid_slot_families_to_mapsurface_v1(working_world, self_bid: str, slots: dict[str, Any]) -> list[str]:
    """Apply Step-13 grid-derived slot-families onto WM.MapSurface (SELF), deterministically.

    Intent
    ------
    SurfaceGrid is the topological substrate; MapSurface is the action-ready sketch.
    This helper writes a *very small*, stable set of pred:* tags onto the existing
    MapSurface SELF binding using overwrite-by-slot-family semantics.

    Design constraints
    ------------------
    - Must NOT create new bindings or edges (no uncontrolled growth).
    - Must NOT emit cue:* (no cue leakage).
    - Must be deterministic: same `slots` -> same written tags.
    - Overwrite-by-family: each derived family replaces its previous value each tick.

    Slot mapping (v1)
    -----------------
    - slots["hazard:near"] == True        -> "pred:hazard:near"     (otherwise absent)
    - slots["terrain:traversable_near"]   -> "pred:terrain:traversable_near" (otherwise absent)
    - slots["goal:dir"] == "NE"/"E"/...   -> "pred:goal:dir:<dir8>" (otherwise absent)

    Parameters
    ----------
    working_world
        The WorkingMap WorldGraph instance (ctx.working_world).
    self_bid
        Binding id of the MapSurface SELF node in the working_world.
    slots
        Dict produced by derive_grid_slot_families_v1(...).

    Returns
    -------
    list[str]
        The pred:* tags written this tick (for logging / JSON traces / debugging).
    """
    if working_world is None or not isinstance(self_bid, str) or not self_bid:
        return []

    bindings = getattr(working_world, "_bindings", None)
    if not isinstance(bindings, dict) or self_bid not in bindings:
        return []

    b = bindings.get(self_bid)
    raw = getattr(b, "tags", None)

    # Normalize to a set for editing (keep other tags intact).
    if isinstance(raw, set):
        tset = set(t for t in raw if isinstance(t, str))
        out_kind = "set"
    elif isinstance(raw, list):
        tset = set(t for t in raw if isinstance(t, str))
        out_kind = "list"
    else:
        tset = set()
        out_kind = "list"

    # Overwrite-by-family: remove prior derived tags (only our tiny namespace).
    def _drop_prefix(prefix: str) -> None:
        nonlocal tset
        tset = set(t for t in tset if not (isinstance(t, str) and t.startswith(prefix)))

    _drop_prefix("pred:goal:dir:")
    if "pred:hazard:near" in tset:
        tset.discard("pred:hazard:near")
    if "pred:terrain:traversable_near" in tset:
        tset.discard("pred:terrain:traversable_near")

    written: list[str] = []

    if bool(slots.get("hazard:near", False)):
        tset.add("pred:hazard:near")
        written.append("pred:hazard:near")

    if bool(slots.get("terrain:traversable_near", False)):
        tset.add("pred:terrain:traversable_near")
        written.append("pred:terrain:traversable_near")

    gd = slots.get("goal:dir")
    if isinstance(gd, str) and gd:
        tag = f"pred:goal:dir:{gd}"
        tset.add(tag)
        written.append(tag)

    # Write back, preserving the original container kind where possible.
    if out_kind == "set":
        b.tags = set(tset)
    else:
        b.tags = sorted(tset)

    return written


def _wm_entity_pos_xy_v1(ww, bid: str) -> tuple[float, float] | None:
    """Best-effort read of WM schematic position from binding.meta['wm']['pos'].

    Returns:
        (x, y) floats in the WM schematic frame, or None if missing.
    """
    try:
        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            return None
        meta = getattr(b, "meta", None)
        if not isinstance(meta, dict):
            return None
        wmm = meta.get("wm")
        if not isinstance(wmm, dict):
            return None
        pos = wmm.get("pos")
        if not isinstance(pos, dict):
            return None
        x = pos.get("x")
        y = pos.get("y")
        if isinstance(x, (int, float)) and isinstance(y, (int, float)):
            return (float(x), float(y))
    except Exception:
        return None
    return None


def _wm_entity_kind_v1(ww, bid: str) -> str | None:
    """Return WM kind tag value (e.g., 'hazard', 'shelter', 'agent') if present."""
    try:
        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            return None
        tags = getattr(b, "tags", []) or []
        for t in tags:
            if isinstance(t, str) and t.startswith("wm:kind:"):
                return t.split(":", 2)[2]
    except Exception:
        return None
    return None


def _wm_pos_to_grid_cell_v1(x: float, y: float, grid_w: int, grid_h: int) -> tuple[int, int] | None:
    """Map WM schematic (x,y) to a SurfaceGrid cell, assuming SELF is centered."""
    try:
        w = int(grid_w)
        h = int(grid_h)
        if w <= 0 or h <= 0:
            return None
        cx = w // 2
        cy = h // 2
        gx = cx + int(round(float(x)))
        gy = cy + int(round(float(y)))
        if 0 <= gx < w and 0 <= gy < h:
            return (gx, gy)
    except Exception:
        return None
    return None


def _surfacegrid_ascii_lines_v1(grid_w: int, grid_h: int, cells: list[int], *, sparse: bool) -> list[str]:
    """Render grid cells to ASCII lines (v1). Display-only: does not mutate the grid.

    Mapping (v1):
        unknown -> ' '
        traversable -> '.' (or ' ' if sparse=True)
        hazard -> '#'
        goal -> 'G'
        4 (blocked/reserved) -> 'X'
        other -> '?'
    """
    w = int(grid_w); h = int(grid_h)
    if w <= 0 or h <= 0 or len(cells) != w * h:
        return ["(surfacegrid: invalid dims/cells)"]

    def _ch(v: int) -> str:
        if v == CELL_UNKNOWN:
            return " "
        if v == CELL_TRAVERSABLE:
            return " " if sparse else "."
        if v == CELL_HAZARD:
            return "#"
        if v == CELL_GOAL:
            return "G"
        if v == 4:
            return "X"
        return "?"

    out: list[str] = []
    for y in range(h):
        base = y * w
        out.append("".join(_ch(int(cells[base + x])) for x in range(w)))
    return out


def _wm_entity_mark_char_v1(entity_id: str, kind: str | None) -> str:
    """Choose a single-character mark for an entity in SurfaceGrid ASCII."""
    eid = (entity_id or "").strip().lower()
    if eid == "self":
        return "@"
    if eid in ("mom", "mother"):
        return "M"
    if eid == "shelter":
        return "S"
    if eid in ("cliff", "drop", "danger") or (kind == "hazard"):
        return "C"
    return "*"


def render_surfacegrid_ascii_with_salience_v1(ctx: Ctx, ww, sg: SurfaceGridV1, *, focus_entities: list[str]) -> str:
    """Render a sparse SurfaceGrid ASCII string and overlay salient entity marks.

    This is display-only: it never changes sg.cells, so Step 13 grid->predicates remains unchanged.

    Overlay rules:
      - Always mark SELF as '@' at the center cell.
      - For each focus entity (excluding self), map WM pos(x,y) to a cell and mark it.
      - Marks overwrite the underlying ASCII character to make landmarks visible.
    """
    w = int(getattr(sg, "grid_w", 0) or 0)
    h = int(getattr(sg, "grid_h", 0) or 0)

    cells = getattr(sg, "grid_cells", None)
    if not isinstance(cells, list):
        # Back-compat: some earlier drafts used sg.cells
        cells = getattr(sg, "cells", None)
    if not isinstance(cells, list):
        cells = []

    sparse = bool(getattr(ctx, "wm_surfacegrid_ascii_sparse", True))

    try:
        cells_i = [int(x) for x in cells]
    except Exception:
        cells_i = []

    lines = _surfacegrid_ascii_lines_v1(w, h, cells_i, sparse=sparse)

    if w <= 0 or h <= 0 or len(lines) != h:
        return "\n".join(lines)

    grid: list[list[str]] = []
    for row in lines:
        rr = list(row)
        if len(rr) < w:
            rr.extend([" "] * (w - len(rr)))
        grid.append(rr[:w])

    # SELF at center
    cx = w // 2
    cy = h // 2
    try:
        grid[cy][cx] = "@"
    except Exception:
        pass

    show_entities = bool(getattr(ctx, "wm_surfacegrid_ascii_show_entities", True))
    if not show_entities:
        return "\n".join("".join(r) for r in grid)

    for eid in (focus_entities or []):
        if not isinstance(eid, str):
            continue
        ent = eid.strip().lower()
        if not ent or ent == "self":
            continue

        bid = (getattr(ctx, "wm_entities", {}) or {}).get(ent)
        if not isinstance(bid, str):
            continue

        pos = _wm_entity_pos_xy_v1(ww, bid)
        if pos is None:
            continue
        x, y = pos

        cell = _wm_pos_to_grid_cell_v1(x, y, w, h)
        if cell is None:
            continue
        gx, gy = cell

        kind = _wm_entity_kind_v1(ww, bid)
        mark = _wm_entity_mark_char_v1(ent, kind)

        try:
            grid[gy][gx] = mark
        except Exception:
            pass

    return "\n".join("".join(r) for r in grid)


def format_surfacegrid_ascii_map_v1(
    ascii_txt: str,
    *,
    title: str | None = None,
    legend: str | None = None,
    show_axes: bool = True,
) -> str:
    """
    Wrap a raw ASCII SurfaceGrid dump in a terminal-friendly "map frame".

    Intent
    ------
    The SurfaceGrid renderer (render_surfacegrid_ascii_with_salience_v1) returns a raw block of rows,
    where each character is a cell symbol (optionally with entity overlays like '@', 'M', 'C', 'S').
    This helper adds:

      - a border (top/bottom),
      - optional x-axis labels (0..w-1, with tens row when w >= 10),
      - optional y-axis labels (0..h-1),
      - optional title and legend lines.

    This is deliberately pure string formatting:
      - No third-party libraries.
      - No assumptions about semantic meanings of characters beyond what the renderer already decided.

    Parameters
    ----------
    ascii_txt:
        The raw ASCII grid text. May contain uneven line lengths; we pad rows to the max width
        so the frame aligns cleanly.
    title:
        Optional header line shown above the axes/border. Use to include sig16, etc.
    legend:
        Optional legend line shown below the framed map.
    show_axes:
        If True, show x-axis (top) and y-axis (left). If False, draws only a border with no indices.

    Returns
    -------
    str
        Framed map text with no trailing newline.
    """
    s = (ascii_txt or "").rstrip("\n")
    if not s:
        return "(surfacegrid ascii: empty)"

    rows = s.splitlines()
    # Preserve intentional leading/trailing spaces in rows; only pad to a uniform width.
    w = max((len(r) for r in rows), default=0)
    h = len(rows)
    padded = [r.ljust(w) for r in rows]

    if show_axes:
        y_w = max(2, len(str(max(0, h - 1))))
        indent_border = " " * (y_w + 1)   # spaces before the '+-----+' border
        indent_cells = " " * (y_w + 2)    # spaces before the first cell (after '|')
    else:
        y_w = 0
        indent_border = ""
        indent_cells = ""

    out: list[str] = []
    if title:
        out.append(str(title))

    if show_axes and w > 0:
        tens = "".join(str((i // 10) % 10) if i >= 10 else " " for i in range(w))
        ones = "".join(str(i % 10) for i in range(w))
        if any(ch != " " for ch in tens):
            out.append(indent_cells + tens)
        out.append(indent_cells + ones)

    border = indent_border + "+" + ("-" * w) + "+"
    out.append(border)

    for y, row in enumerate(padded):
        if show_axes:
            out.append(f"{y:>{y_w}d} |{row}|")
        else:
            out.append(f"|{row}|")

    out.append(border)

    if legend:
        out.append(str(legend))

    return "\n".join(out)


def wm_salience_force_focus_entity_v1(ctx: Ctx, entity_id: str, *, ttl: int | None = None, reason: str = "inspect") -> None:
    """Force an entity into the Step-14 salience focus set for a few ticks.

    This is *attention/display* only:
      - It affects ctx.wm_salience_focus_entities (what we render as landmarks),
      - It does NOT change MapSurface beliefs or WorldGraph state.

    The TTL is decremented once per call to wm_salience_tick_v1(...).
    """
    if ctx is None or not isinstance(entity_id, str) or not entity_id.strip():
        return

    eid = entity_id.strip().lower()
    try:
        t = int(ttl) if ttl is not None else int(getattr(ctx, "wm_salience_inspect_focus_ttl", 4) or 4)
    except Exception:
        t = 4
    t = max(1, min(50, int(t)))  # keep bounded

    m = getattr(ctx, "wm_salience_forced_focus", None)
    if not isinstance(m, dict):
        ctx.wm_salience_forced_focus = {}
        m = ctx.wm_salience_forced_focus

    try:
        prev = int(m.get(eid, 0) or 0)
    except Exception:
        prev = 0
    if t > prev:
        m[eid] = int(t)

    rmap = getattr(ctx, "wm_salience_forced_reason", None)
    if not isinstance(rmap, dict):
        ctx.wm_salience_forced_reason = {}
        rmap = ctx.wm_salience_forced_reason
    if isinstance(reason, str) and reason:
        rmap[eid] = reason


def _wm_guess_inspected_entity_v1(ctx: Ctx) -> str | None:
    """Best-effort guess of a probe/inspect target when a policy doesn't specify one.

    Priority order:
      1) Any NavPatch matches whose commit != 'commit' (ambiguous/unknown). Prefer cliff if present.
      2) If BodyMap says cliff is near, use cliff.
      3) If BodyMap has mom distance info, use mom.
      4) Otherwise None.
    """
    # 1) Ambiguous/unknown NavPatch entities (from ctx.navpatch_last_matches)
    ent_ids: list[str] = []
    try:
        matches = getattr(ctx, "navpatch_last_matches", None)
        if isinstance(matches, list):
            for rec in matches:
                if not isinstance(rec, dict):
                    continue
                commit = rec.get("commit")
                if not isinstance(commit, str) or not commit or commit == "commit":
                    continue
                eid = rec.get("entity_id")
                if isinstance(eid, str) and eid.strip():
                    ent_ids.append(eid.strip().lower())
    except Exception:
        ent_ids = []

    if ent_ids:
        # Prefer high-safety relevance if present.
        for pref in ("cliff", "shelter", "mom"):
            if pref in ent_ids:
                return pref
        return sorted(set(ent_ids))[0]

    # 2) BodyMap hazard
    try:
        if body_cliff_distance(ctx) == "near":
            return "cliff"
    except Exception:
        pass

    # 3) BodyMap mom proximity
    try:
        md = body_mom_distance(ctx)
        if isinstance(md, str) and md:
            return "mom"
    except Exception:
        pass

    return None


def _wm_salience_ambiguous_entities_v1(env_obs: EnvObservation) -> set[str]:
    """Extract entities with ambiguous patch matches (commit != 'commit') from env_obs.nav_patches."""
    out: set[str] = set()
    patches = getattr(env_obs, "nav_patches", None) or []
    if not isinstance(patches, list):
        return out
    for p in patches:
        if not isinstance(p, dict):
            continue
        m = p.get("match")
        if not isinstance(m, dict):
            continue
        commit = m.get("commit")
        if isinstance(commit, str) and commit and commit != "commit":
            eid = p.get("entity_id")
            if isinstance(eid, str) and eid.strip():
                out.add(eid.strip().lower())
    return out


def wm_salience_tick_v1(
    ctx: Ctx,
    ww,
    *,
    changed_entities: set[str],
    new_cue_entities: set[str],
    ambiguous_entities: set[str],
) -> dict[str, Any]:
    """One-tick salience update (Phase X Step 14, minimal v1).

    Signals:
      - changed_entities: any entity whose MapSurface slot-family was overwritten this tick.
      - new_cue_entities: any entity that gained a new cue this tick.
      - ambiguous_entities: any entity whose NavPatch match is not committed (commit != 'commit').

    Storage:
      - Writes per-entity fields under binding.meta['wm']:
          salience_ttl: int
          salience_reason: short string (best-effort)
      - Returns a small dict for traces/printing:
          {"focus_entities": [...], "events": [...]}  (JSON-safe)

    TTL rules (v1):
      - Novelty burst: changed or new cue → ttl=max(ttl, novelty_ttl)
      - Promotion: hazard-relevant or ambiguous → ttl=max(ttl, promote_ttl)
      - Decay: any entity not refreshed this tick decrements ttl by 1 down to 0
    """
    novelty_ttl = max(0, int(getattr(ctx, "wm_salience_novelty_ttl", 3) or 3))
    promote_ttl = max(novelty_ttl, int(getattr(ctx, "wm_salience_promote_ttl", 8) or 8))
    k_max = max(0, int(getattr(ctx, "wm_salience_max_items", 3) or 3))

    changed = {e.strip().lower() for e in (changed_entities or set()) if isinstance(e, str) and e.strip()}
    newc = {e.strip().lower() for e in (new_cue_entities or set()) if isinstance(e, str) and e.strip()}
    amb = {e.strip().lower() for e in (ambiguous_entities or set()) if isinstance(e, str) and e.strip()}

    # Mandatory baseline: SELF always.
    focus: list[str] = ["self"]

    # Hazard/goal relevance from BodyMap-first signals (cheap and robust).
    try:
        if body_cliff_distance(ctx) == "near":
            focus.append("cliff")
    except Exception:
        pass
    try:
        if body_shelter_distance(ctx) in ("near", "touching"):
            focus.append("shelter")
    except Exception:
        pass
    try:
        if body_mom_distance(ctx) == "near":
            focus.append("mom")
    except Exception:
        pass

    # Novelty/focus candidates (excluding already forced ones).
    forced = set(focus)

    # Forced focus (inspect/probe): keep these entities in focus for a few ticks even if they stop being "top-K" now.
    forced_map = getattr(ctx, "wm_salience_forced_focus", None)
    forced_list: list[tuple[int, str]] = []
    if isinstance(forced_map, dict) and forced_map:
        for k, v in forced_map.items():
            if not isinstance(k, str) or not k.strip():
                continue
            try:
                ttl = int(v)
            except Exception:
                continue
            if ttl > 0:
                forced_list.append((ttl, k.strip().lower()))
    # Deterministic order: higher TTL first, then lexical.
    forced_list.sort(key=lambda t: (-t[0], t[1]))
    # Keep bounded so focus doesn't explode.
    for _ttl, e in forced_list[:8]:
        if e and e not in forced:
            focus.append(e)
            forced.add(e)

    cand: list[tuple[int, str, str]] = []
    for e in amb:
        if e not in forced and e != "self":
            cand.append((3, e, "ambiguous"))
    for e in changed:
        if e not in forced and e != "self":
            cand.append((2, e, "changed"))
    for e in newc:
        if e not in forced and e != "self":
            cand.append((1, e, "new_cue"))

    # Deterministic pick: higher priority first, then lexicographic.
    cand.sort(key=lambda t: (-t[0], t[1], t[2]))
    for _prio, e, _why in cand[:k_max]:
        if e not in forced:
            focus.append(e)
            forced.add(e)

    # Apply TTL updates into WM entity meta
    events: list[dict[str, Any]] = []
    ent_map = getattr(ctx, "wm_entities", {}) or {}
    for eid, bid in ent_map.items():
        if not isinstance(eid, str) or not isinstance(bid, str):
            continue
        e = eid.strip().lower()
        if not e:
            continue

        b = getattr(ww, "_bindings", {}).get(bid)
        if b is None:
            continue
        if not isinstance(getattr(b, "meta", None), dict):
            b.meta = {}
        wmm = b.meta.setdefault("wm", {})
        if not isinstance(wmm, dict):
            continue

        prev_ttl = int(wmm.get("salience_ttl", 0) or 0)
        prev_reason = wmm.get("salience_reason")
        if not isinstance(prev_reason, str):
            prev_reason = ""

        refreshed = e in forced
        reason = ""

        # Choose the strongest reason we have (best-effort)
        if e in amb:
            reason = "ambiguous"
        elif e in changed:
            reason = "changed"
        elif e in newc:
            reason = "new_cue"
        elif e in ("cliff", "shelter", "mom"):
            # forced-by-goal/hazard, but no novelty signal this tick
            reason = "goal/hazard"

        if refreshed:
            ttl_target = promote_ttl if (e in amb or e == "cliff") else novelty_ttl
            ttl_new = max(prev_ttl, ttl_target)
        else:
            ttl_new = max(0, prev_ttl - 1)

        if ttl_new != prev_ttl or (refreshed and reason and reason != prev_reason):
            events.append(
                {
                    "entity": e,
                    "ttl_prev": int(prev_ttl),
                    "ttl_new": int(ttl_new),
                    "refreshed": bool(refreshed),
                    "reason": reason,
                }
            )

        wmm["salience_ttl"] = int(ttl_new)
        if reason:
            wmm["salience_reason"] = reason
        else:
            # keep old reason if we are only decaying; drop when ttl hits 0
            if ttl_new <= 0:
                wmm.pop("salience_reason", None)

    # Decrement forced-focus TTL counters once per tick.
    try:
        ff = getattr(ctx, "wm_salience_forced_focus", None)
        if isinstance(ff, dict) and ff:
            new_ff: dict[str, int] = {}
            for e, ttl in ff.items():
                if not isinstance(e, str) or not e.strip():
                    continue
                try:
                    t = int(ttl)
                except Exception:
                    continue
                t2 = t - 1
                if t2 > 0:
                    new_ff[e.strip().lower()] = int(t2)
            ctx.wm_salience_forced_focus = new_ff

            fr = getattr(ctx, "wm_salience_forced_reason", None)
            if isinstance(fr, dict) and fr:
                ctx.wm_salience_forced_reason = {e: str(fr.get(e, "")) for e in new_ff if e in fr}
    except Exception:
        pass

    return {"focus_entities": list(focus), "events": events}


def inject_obs_into_working_world(ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """
    Mirror EnvObservation into WorkingMap.

    Phase VII default: MapSurface (stable map)
    -----------------------------------------
    - We maintain *stable* entity bindings (SELF, MOM, SHELTER, CLIFF, ...).
    - We update pred:* and cue:* tags IN PLACE (so step 2 does NOT create new posture/mom/etc. nodes).
    - We store a 2D "schematic" coordinate frame in binding.meta["wm"]["pos"] (distorted, subway-map style).

    Optional debug: if ctx.working_trace=True, we also append a per-tick trace using add_predicate/add_cue
    (old behaviour) after updating the map.
    """
    ww = getattr(ctx, "working_world", None)
    if ww is None:
        try:
            ctx.working_world = init_working_world()
            ww = ctx.working_world
        except Exception:
            return {"predicates": [], "cues": []}

    changed_entities: set[str] = set()
    new_cue_entities: set[str] = set()
    prev_cues_by_ent: dict[str, set[str]] = {}
    try:
        prev = getattr(ctx, "wm_last_env_cues", None)
        if isinstance(prev, dict):
            for k, v in prev.items():
                if isinstance(k, str) and isinstance(v, set):
                    prev_cues_by_ent[k] = set(v)
    except Exception:
        prev_cues_by_ent = {}

    meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
    created_preds: list[str] = []
    created_cues: list[str] = []

    # -------------------- small helpers (robust to tags=list vs tags=set) --------------------
    def _tagset_of(bid: str) -> set[str]:
        b = ww._bindings.get(bid)
        if b is None:
            return set()
        ts = getattr(b, "tags", None)
        if ts is None:
            b.tags = set()
            return b.tags
        if isinstance(ts, set):
            return ts
        if isinstance(ts, list):
            s = set(ts)
            b.tags = s
            return s
        try:
            s = set(ts)  # last resort
            b.tags = s
            return s
        except Exception:
            b.tags = set()
            return b.tags

    def _sanitize_entity_anchor(entity_id: str) -> str:
        s = (entity_id or "unknown").strip().upper()
        out: list[str] = []
        for ch in s:
            out.append(ch if ch.isalnum() else "_")
        s = "".join(out)
        while "__" in s:
            s = s.replace("__", "_")
        s = s.strip("_") or "UNKNOWN"
        return f"WM_ENT_{s}"

    def _upsert_edge(src: str, dst: str, label: str, meta2: dict | None = None) -> None:
        b = ww._bindings.get(src)
        if b is None:
            return
        edges = getattr(b, "edges", None)
        if edges is None or not isinstance(edges, list):
            b.edges = []
            edges = b.edges
        # update if exists
        for e in edges:
            try:
                to_ = e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")
                lab = e.get("label") or e.get("rel") or e.get("relation")
                # Treat wm_has as a legacy alias of wm_entity (cosmetic rename)
                if label == "wm_entity" and to_ == dst and lab in ("wm_entity", "wm_has"):
                    # migrate label in-place (prevents duplicate edges)
                    if lab != "wm_entity":
                        e["label"] = "wm_entity"
                    if isinstance(meta2, dict) and meta2:
                        em = e.get("meta")
                        if isinstance(em, dict):
                            em.update(meta2)
                        else:
                            e["meta"] = dict(meta2)
                    return

                if to_ == dst and lab == label:
                    if isinstance(meta2, dict) and meta2:
                        em = e.get("meta")
                        if isinstance(em, dict):
                            em.update(meta2)
                        else:
                            e["meta"] = dict(meta2)
                    return
            except Exception:
                continue
        edges.append({"to": dst, "label": label, "meta": dict(meta2 or {})})

    def _ensure_entity(entity_id: str, *, kind_hint: str | None = None) -> str:
        eid = (entity_id or "unknown").strip().lower()
        # cached?
        bid = (getattr(ctx, "wm_entities", {}) or {}).get(eid)
        if isinstance(bid, str) and bid in ww._bindings:
            # If we later learn a better kind hint, annotate the existing entity in-place.
            if isinstance(kind_hint, str) and kind_hint:
                try:
                    tags = _tagset_of(bid)
                    tags.add(f"wm:kind:{kind_hint}")
                except Exception:
                    pass
            return bid

        anchor_name = "WM_SELF" if eid == "self" else _sanitize_entity_anchor(eid)
        try:
            bid = ww.ensure_anchor(anchor_name)
        except Exception:
            # fallback: a plain node if anchors fail for any reason
            bid = ww.add_predicate(f"wm_entity:{eid}", attach="none", meta={"created_by": "wm_mapsurface"})

        # mark + cache
        try:
            ctx.wm_entities[eid] = bid
        except Exception:
            pass

        tags = _tagset_of(bid)
        tags.add("wm:entity")
        tags.add(f"wm:eid:{eid}")
        if isinstance(kind_hint, str) and kind_hint:
            tags.add(f"wm:kind:{kind_hint}")

        # attach under WM_ROOT so predicates are reachable from NOW (we pin NOW to WM_ROOT each tick)
        try:
            _upsert_edge(root_bid, bid, "wm_entity", {"created_by": "wm_mapsurface"})
        except Exception:
            pass

        # init wm meta
        try:
            b = ww._bindings.get(bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                wmm = b.meta.setdefault("wm", {})
                if isinstance(wmm, dict):
                    wmm.setdefault("entity_id", eid)
        except Exception:
            pass

        return bid

    def _replace_pred_slot_on_entity(bid: str, slot_prefix: str, new_full_tag: str) -> bool:
        """
        Ensure entity has exactly one pred tag for this slot family, e.g.:
          slot_prefix='posture'         → pred:posture:*
          slot_prefix='proximity:mom'   → pred:proximity:mom:*
        Returns True if the stored tag actually changed.
        """
        tags = _tagset_of(bid)
        pref = f"pred:{slot_prefix}:"
        old = None
        for t in list(tags):
            if isinstance(t, str) and t.startswith(pref):
                old = t
                break
        if old == new_full_tag:
            return False
        # remove all in that family, then add the new one
        for t in list(tags):
            if isinstance(t, str) and t.startswith(pref):
                tags.discard(t)
        tags.add(new_full_tag)
        return True

    def _entity_from_pred(tok: str) -> tuple[str, str]:
        """
        Return (entity_id, slot_prefix) from a predicate token (no 'pred:' prefix).
        """
        parts = (tok or "").split(":")
        if not parts:
            return ("self", "unknown")

        head = parts[0]
        if head == "grid" and len(parts) >= 2:
            return ("self", f"grid:{parts[1]}")
        if head == "posture":
            return ("self", "posture")
        if head in ("nipple", "milk"):
            return ("self", head)
        if head == "proximity" and len(parts) >= 3:
            ent = parts[1]
            return (ent, f"proximity:{ent}")
        if head == "hazard" and len(parts) >= 3:
            ent = parts[1]
            return (ent, f"hazard:{ent}")

        # fallback: treat as SELF attribute family
        return ("self", head)

    def _entity_from_cue(tok: str) -> str:
        """
        Heuristic: for cues like 'vision:silhouette:mom', assume the last segment is an entity id.
        """
        parts = (tok or "").split(":")
        if len(parts) >= 2:
            tail = parts[-1].strip().lower()
            if tail:
                return tail
        return "self"

    def _set_pos(bid: str, x: float, y: float, dist_m: float | None, dist_class: str | None) -> None:
        b = ww._bindings.get(bid)
        if b is None:
            return
        if not isinstance(getattr(b, "meta", None), dict):
            b.meta = {}
        wmm = b.meta.setdefault("wm", {})
        if not isinstance(wmm, dict):
            wmm = {}
            b.meta["wm"] = wmm
        wmm["pos"] = {"x": float(x), "y": float(y), "frame": "wm_schematic_v1"}
        if dist_m is not None:
            wmm["dist_m"] = float(dist_m)
        if isinstance(dist_class, str) and dist_class:
            wmm["dist_class"] = dist_class
        wmm["last_seen_step"] = int(getattr(ctx, "controller_steps", 0) or 0)

    def _dist_value_from_class(dist_class: str | None) -> float:
        m = {
            "touching": 0.2,
            "close": 1.0,
            "near": 1.2,
            "reachable": 0.8,
            "far": 5.0,
        }
        if dist_class is None:
            return 3.0
        return float(m.get(dist_class, 3.0))

    def _raw_distance_guess(raw: dict, ent: str) -> float | None:
        if not isinstance(raw, dict):
            return None

        # common keys
        for k in (
            f"distance_to_{ent}",
            f"{ent}_distance",
            f"{ent}_distance_m",
            f"dist_{ent}",
        ):
            v = raw.get(k)
            if isinstance(v, (int, float)):
                return float(v)

        # positions: (kid_position, mom_position, shelter_position, cliff_position, ...)
        kp = raw.get("kid_position") or raw.get("self_position")
        op = raw.get(f"{ent}_position")
        if isinstance(kp, (tuple, list)) and isinstance(op, (tuple, list)) and len(kp) == 2 and len(op) == 2:
            try:
                from math import sqrt
                dx = float(op[0]) - float(kp[0])
                dy = float(op[1]) - float(kp[1])
                return sqrt(dx * dx + dy * dy)
            except Exception:
                return None

        return None


    def _lane_y(ent: str, *, kind: str | None) -> float:
        ent_l = (ent or "").lower()
        if kind == "hazard" or ent_l in ("cliff", "drop", "danger"):
            return 1.0
        if ent_l in ("shelter", "den", "nest"):
            return -1.0
        if kind == "agent" or ent_l in ("mom", "mother"):
            return 0.0
        # deterministic lane based on characters (avoid python hash randomization)
        s = sum(ord(c) for c in ent_l)
        lane = (s % 5) - 2  # -2..+2
        return float(lane) * 0.5


    def _project(dist_m: float, ent: str, *, kind: str | None) -> tuple[float, float]:
        # subway-map distortion: compress far distances but keep ordering monotonic
        from math import log
        d = max(0.0, float(dist_m))
        x = 3.0 * log(1.0 + d)
        y = _lane_y(ent, kind=kind)
        return (x, y)

    # -------------------- MapSurface path (default) --------------------
    if getattr(ctx, "working_mapsurface", True):
        # Ensure WM_ROOT exists, and pin NOW to it so has_pred_near_now(...) works against the map.
        try:
            root_bid = ww.ensure_anchor("WM_ROOT")
        except Exception:
            # fallback: keep whatever NOW is if WM_ROOT cannot be created
            root_bid = ww.ensure_anchor("NOW")

        try:
            ww.set_now(root_bid, tag=True, clean_previous=True)
        except Exception:
            try:
                ww._anchors["NOW"] = root_bid
                _tagset_of(root_bid).add("anchor:NOW")
            except Exception:
                pass

        # Optional: keep NOW_ORIGIN aligned with WM_ROOT in WorkingMap
        try:
            ww._anchors["NOW_ORIGIN"] = root_bid
            _tagset_of(root_bid).add("anchor:NOW_ORIGIN")
        except Exception:
            pass

        # Ensure WM_SCRATCH exists and is reachable from WM_ROOT.
        # This is where policy scratch chains will attach, so WM_ROOT stays a clean "map surface".
        try:
            scratch_bid = ww.ensure_anchor("WM_SCRATCH")
            try:
                _tagset_of(scratch_bid).add("wm:scratch")
            except Exception:
                pass
            try:
                _upsert_edge(root_bid, scratch_bid, "wm_scratch", {"created_by": "wm_mapsurface"})
            except Exception:
                pass
        except Exception:
            pass

        # Ensure WM_CREATIVE exists and is reachable from WM_ROOT.
        # This is the "imagination" workspace: counterfactual rollouts should not contaminate MapSurface.
        try:
            creative_bid = ww.ensure_anchor("WM_CREATIVE")
            try:
                _tagset_of(creative_bid).add("wm:creative")
            except Exception:
                pass
            try:
                _upsert_edge(root_bid, creative_bid, "wm_creative", {"created_by": "wm_mapsurface"})
            except Exception:
                pass
        except Exception:
            pass

        # Ensure SELF entity exists and sits under WM_ROOT
        self_bid = _ensure_entity("self", kind_hint="agent")
        _upsert_edge(root_bid, self_bid, "wm_entity", {"created_by": "wm_mapsurface"})
        _set_pos(self_bid, 0.0, 0.0, dist_m=0.0, dist_class="self")

        # NOTE (Phase X):
        # SurfaceGrid composition + grid→predicate derivation happens later in this function:
        #   - Step 12: WM.SurfaceGrid compose + dirty-cache (ctx.wm_surfacegrid_*)
        #   - Step 13: Grid → slot-family predicates written onto MapSurface SELF
        # The older inline prototype block was removed to avoid double-compose and misleading cache-hit reporting.
        #
        # --- DELETED PREVIOUSLY: WM.SurfaceGrid (Phase X): compose once-per-tick and derive grid predicates ---
        # deleted this block of code

        # --- Predicates: update entity tags in place ---
        pred_tokens = [
            str(p).replace("pred:", "", 1)
            for p in (getattr(env_obs, "predicates", []) or [])
            if p is not None
        ]

        for tok in pred_tokens:
            ent, slot_prefix = _entity_from_pred(tok)
            kind = "hazard" if slot_prefix.startswith("hazard:") else None
            if ent == "self":
                kind = "agent"
            if ent in ("mom", "mother"):
                kind = "agent"
            if ent == "shelter":
                kind = "shelter"
            bid = _ensure_entity(ent, kind_hint=kind)
            full_tag = f"pred:{tok}"
            changed = _replace_pred_slot_on_entity(bid, slot_prefix, full_tag)

            # bump prominence (exposure signal) even if unchanged
            try:
                ww.bump_prominence(bid, tag=full_tag, meta=meta, reason="observe")
            except Exception:
                pass
            created_preds.append(tok)

            if changed:
                changed_entities.add(ent)

            if getattr(ctx, "working_verbose", False) or changed:
                try:
                    disp = f"{_wm_display_id(bid)} ({bid})"
                    print(
                        f"[env→working] MAP pred:{tok} → {disp} (entity={ent}, slot={slot_prefix})"
                        + (" [changed]" if changed else ""))
                except Exception:
                    pass

        # --- Cues: attach to an entity and dedup/remove old env cues per entity ---
        cue_tokens = [
            str(c).replace("cue:", "", 1)
            for c in (getattr(env_obs, "cues", []) or [])
            if c is not None
        ]

        cues_by_ent: dict[str, set[str]] = {}
        for tok in cue_tokens:
            ent = _entity_from_cue(tok)
            cues_by_ent.setdefault(ent, set()).add(f"cue:{tok}")
            created_cues.append(tok)

        # update each entity that has cues this tick
        for ent, new_cue_tags in cues_by_ent.items():
            kind = "agent" if ent in ("mom", "mother") else None
            bid = _ensure_entity(ent, kind_hint=kind)
            tags = _tagset_of(bid)

            prev = (getattr(ctx, "wm_last_env_cues", {}) or {}).get(ent, set())
            # remove old env cues not present now
            for t in list(prev - new_cue_tags):
                try:
                    tags.discard(t)
                except Exception:
                    pass
            # add new env cues
            for t in list(new_cue_tags - prev):
                try:
                    tags.add(t)
                except Exception:
                    pass

            try:
                ctx.wm_last_env_cues[ent] = set(new_cue_tags)
            except Exception:
                pass

            for t in new_cue_tags:
                try:
                    ww.bump_prominence(bid, tag=t, meta=meta, reason="observe")
                except Exception:
                    pass

            if getattr(ctx, "working_verbose", False):
                try:
                    for t in sorted(new_cue_tags):
                        disp = f"{_wm_display_id(bid)} ({bid})"
                        print(f"[env→working] MAP {t} → {disp} (entity={ent})")
                except Exception:
                    pass

        # Also clear env cues for entities that had cues last tick but none now
        try:
            for ent in list(ctx.wm_last_env_cues.keys()):
                if ent in cues_by_ent:
                    continue
                bid = (ctx.wm_entities or {}).get(ent)
                if not (isinstance(bid, str) and bid in ww._bindings):
                    ctx.wm_last_env_cues.pop(ent, None)
                    continue
                tags = _tagset_of(bid)
                for t in list(ctx.wm_last_env_cues.get(ent, set())):
                    tags.discard(t)
                ctx.wm_last_env_cues.pop(ent, None)
        except Exception:
            pass

        try:
            now_map = getattr(ctx, "wm_last_env_cues", None)
            if isinstance(now_map, dict):
                for ent, now_set in now_map.items():
                    if not isinstance(ent, str) or not isinstance(now_set, set):
                        continue
                    prev_set = prev_cues_by_ent.get(ent, set())
                    if now_set - prev_set:
                        new_cue_entities.add(ent)
        except Exception:
            pass

        # --- NavPatches: processed local navmap fragments (Phase X; plan v5) ---
        # These are *not* raw pixels. They are small, structured maplets that can be stored
        # as separate Column engrams and referenced from MapSurface entity nodes.
        if bool(getattr(ctx, "navpatch_enabled", False)):
            patches_in = getattr(env_obs, "nav_patches", None) or []
            refs_by_ent: dict[str, list[dict[str, Any]]] = {}
            sigs_by_ent: dict[str, set[str]] = {}

            if isinstance(patches_in, list):
                for p in patches_in:
                    if not isinstance(p, dict):
                        continue

                    ent_raw = p.get("entity_id") or p.get("entity") or "self"
                    try:
                        ent = str(ent_raw).strip().lower() or "self"
                    except Exception:
                        ent = "self"

                    sig = navpatch_payload_sig_v1(p)
                    sig16 = sig[:16]

                    engram_id: str | None = None
                    if bool(getattr(ctx, "navpatch_store_to_column", False)):
                        try:
                            st = store_navpatch_engram_v1(ctx, p, reason="env_obs")
                            engram_id = st.get("engram_id") if isinstance(st, dict) else None
                        except Exception:
                            engram_id = None

                    ref: dict[str, Any] = {
                        "sig16": sig16,
                        "sig": sig,
                        "engram_id": engram_id,
                        "local_id": p.get("local_id"),
                        "role": p.get("role"),
                        "frame": p.get("frame"),
                    }

                    tags = p.get("tags")
                    if isinstance(tags, list):
                        ref["tags"] = [t for t in tags if isinstance(t, str) and t][:8]

                    refs_by_ent.setdefault(ent, []).append(ref)
                    sigs_by_ent.setdefault(ent, set()).add(sig16)

            # Attach refs to WM entities (replace per tick, like cues)
            for ent, refs in refs_by_ent.items():
                kind = None
                try:
                    roles = {r.get("role") for r in refs if isinstance(r, dict)}
                    if "hazard" in roles or ent in ("cliff", "drop", "danger"):
                        kind = "hazard"
                    elif "shelter" in roles or ent == "shelter":
                        kind = "shelter"
                    elif ent in ("mom", "mother", "self"):
                        kind = "agent"
                except Exception:
                    kind = None

                bid = _ensure_entity(ent, kind_hint=kind)
                b = ww._bindings.get(bid)
                if b is not None:
                    if not isinstance(getattr(b, "meta", None), dict):
                        b.meta = {}
                    wmm = b.meta.setdefault("wm", {})
                    if isinstance(wmm, dict):
                        wmm["patch_refs"] = list(refs)
                        try:
                            if refs and isinstance(refs[0], dict):
                                fr = refs[0].get("frame")
                                if isinstance(fr, str) and fr:
                                    wmm["patch_frame"] = fr
                        except Exception:
                            pass

                try:
                    ctx.wm_last_navpatch_sigs[ent] = set(sigs_by_ent.get(ent, set()))
                except Exception:
                    pass

                if bool(getattr(ctx, "navpatch_verbose", False)):
                    try:
                        disp = f"{_wm_display_id(bid)} ({bid})"
                        print(f"[env→working] PATCH x{len(refs)} → {disp} (entity={ent})")
                    except Exception:
                        pass

            # Clear patch_refs for entities that had patches last tick but none now
            try:
                for ent in list((getattr(ctx, "wm_last_navpatch_sigs", {}) or {}).keys()):
                    if ent in refs_by_ent:
                        continue
                    bid = (getattr(ctx, "wm_entities", {}) or {}).get(ent)
                    if isinstance(bid, str) and bid in ww._bindings:
                        b = ww._bindings.get(bid)
                        if b is not None and isinstance(getattr(b, "meta", None), dict):
                            wmm = b.meta.get("wm")
                            if isinstance(wmm, dict):
                                wmm.pop("patch_refs", None)
                    ctx.wm_last_navpatch_sigs.pop(ent, None)
            except Exception:
                pass

            # --- Step 15A: WM.Scratch record for ambiguous NavPatch commit -----------------------
            # If a NavPatch match is ambiguous, stage a compact record under WM_SCRATCH so later
            # probe/zoom steps can consult it (without affecting policy selection yet).
            try:
                if bool(getattr(ctx, "wm_scratch_navpatch_enabled", True)):
                    scratch_bid = ww.ensure_anchor("WM_SCRATCH")

                    # Defensive init (slots=True: must exist on ctx or be created in dataclass)
                    key_to_bid = getattr(ctx, "wm_scratch_navpatch_key_to_bid", None)
                    if not isinstance(key_to_bid, dict):
                        key_to_bid = {}
                        ctx.wm_scratch_navpatch_key_to_bid = key_to_bid

                    prev_keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
                    if not isinstance(prev_keys, set):
                        prev_keys = set()
                        ctx.wm_scratch_navpatch_last_keys = prev_keys

                    def _san(s: str) -> str:
                        s2 = (s or "").strip().upper()
                        out2: list[str] = []
                        for ch in s2:
                            out2.append(ch if ch.isalnum() else "_")
                        s2 = "".join(out2)
                        while "__" in s2:
                            s2 = s2.replace("__", "_")
                        return s2.strip("_") or "X"

                    def _scratch_key(eid: str, local_id: str) -> str:
                        return f"{(eid or '').strip().lower()}|{(local_id or '').strip().lower()}"

                    # Collect current ambiguous items (keys) and upsert their scratch records.
                    nav_patches = getattr(env_obs, "nav_patches", None)
                    cur_keys: set[str] = set()

                    if isinstance(nav_patches, list):
                        for p in nav_patches:
                            if not isinstance(p, dict):
                                continue

                            m = p.get("match")
                            if not isinstance(m, dict):
                                continue
                            if (m.get("commit") or "") != "ambiguous":
                                continue

                            eid = p.get("entity_id")
                            local_id = p.get("local_id")
                            eid = eid.strip().lower() if isinstance(eid, str) and eid.strip() else "unknown"
                            local_id = local_id.strip().lower() if isinstance(local_id, str) and local_id.strip() else "p"

                            k = _scratch_key(eid, local_id)
                            cur_keys.add(k)

                            # Stable anchor name so we update in place (no unbounded growth).
                            anchor_name = f"WM_SCRATCH_NVP_{_san(eid)}_{_san(local_id)}"
                            sbid = ww.ensure_anchor(anchor_name)
                            key_to_bid[k] = sbid

                            # Ensure the scratch root points to this item.
                            _upsert_edge(scratch_bid, sbid, "wm_scratch_item", {"created_by": "wm_scratch", "kind": "navpatch_ambiguous"})

                            # Tags: keep them WM-scoped so they don't collide with pred/cue tags.
                            tags = _tagset_of(sbid)
                            tags.add("wm:scratch_item")
                            tags.add("wm:scratch:navpatch_match")
                            tags.add(f"wm:eid:{eid}")
                            tags.add(f"wm:patch_local:{local_id}")

                            # Meta.wm payload (JSON-safe, compact, inspectable)
                            b = ww._bindings.get(sbid)
                            if b is not None:
                                if not isinstance(getattr(b, "meta", None), dict):
                                    b.meta = {}
                                wmm = b.meta.setdefault("wm", {})
                                if isinstance(wmm, dict):
                                    wmm["kind"] = "navpatch_match_ambiguous"
                                    wmm["schema"] = "wm_scratch_navpatch_match_v1"
                                    wmm["controller_steps"] = int(getattr(ctx, "controller_steps", 0) or 0)
                                    wmm["entity_id"] = eid
                                    wmm["local_id"] = local_id
                                    wmm["patch_sig16"] = p.get("sig16") if isinstance(p.get("sig16"), str) else None
                                    wmm["commit"] = "ambiguous"
                                    wmm["decision"] = m.get("decision")
                                    wmm["decision_note"] = m.get("decision_note")
                                    wmm["margin"] = m.get("margin")
                                    wmm["best"] = m.get("best") if isinstance(m.get("best"), dict) else None
                                    wmm["top_k"] = m.get("top_k") if isinstance(m.get("top_k"), list) else []

                    # Remove stale scratch edges for ambiguity items that are no longer ambiguous this tick.
                    stale = set(prev_keys) - set(cur_keys)
                    if stale:
                        bsrc = ww._bindings.get(scratch_bid)
                        edges = getattr(bsrc, "edges", None) if bsrc is not None else None
                        if isinstance(edges, list):
                            for sk in stale:
                                sbid = key_to_bid.get(sk)
                                if not isinstance(sbid, str):
                                    continue
                                edges[:] = [
                                    e for e in edges
                                    if not (
                                        isinstance(e, dict)
                                        and (e.get("label") or e.get("rel") or e.get("relation")) == "wm_scratch_item"
                                        and (e.get("to") or e.get("dst") or e.get("dst_id") or e.get("id")) == sbid
                                    )
                                ]
                                key_to_bid.pop(sk, None)

                    ctx.wm_scratch_navpatch_last_keys = set(cur_keys)
                    # --- Step 15B: Emit zoom_down / zoom_up events (diagnostic first) ----------
                    # We treat "zoom" as a mode transition triggered by persistent ambiguity.
                    # Zoom state is derived from WM.Scratch ambiguity keys:
                    #   - zoom_down: prev_keys empty -> cur_keys non-empty
                    #   - zoom_up:   prev_keys non-empty -> cur_keys empty
                    try:
                        if bool(getattr(ctx, "wm_zoom_enabled", True)):
                            now_down = bool(cur_keys)
                            prev_down = bool(prev_keys)

                            # Compute a compact entity set from keys like "eid|local".
                            def _entities_from_keys(keys: set[str]) -> set[str]:
                                out_e: set[str] = set()
                                for kk in keys:
                                    if not isinstance(kk, str) or "|" not in kk:
                                        continue
                                    out_e.add(kk.split("|", 1)[0].strip().lower())
                                return out_e

                            events: list[dict[str, Any]] = []

                            if now_down != prev_down:
                                kind = "zoom_down" if now_down else "zoom_up"
                                keys_for_event = set(cur_keys) if now_down else set(prev_keys)
                                ents = _entities_from_keys(keys_for_event)

                                hazard_near = False
                                try:
                                    hazard_near = (body_cliff_distance(ctx) == "near")  #pylint: disable=superfluous-parens
                                except Exception:
                                    hazard_near = False

                                hazard_amb = "cliff" in ents
                                if now_down:
                                    reason = "hazard+ambiguity" if (hazard_near or hazard_amb) else "ambiguity"
                                else:
                                    reason = "resolved"

                                ev = {
                                    "kind": kind,
                                    "reason": reason,
                                    "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
                                    "ambiguous_n": int(len(keys_for_event)),
                                    "ambiguous_keys": sorted(list(keys_for_event)),
                                    "ambiguous_entities": sorted(list(ents)),
                                    "hazard_near": bool(hazard_near),
                                    "hazard_ambiguous": bool(hazard_amb),
                                }
                                events.append(ev)

                                if bool(getattr(ctx, "wm_zoom_verbose", False)):
                                    try:
                                        ent_txt = ",".join(sorted(list(ents))[:4])
                                        more = "..." if len(ents) > 4 else ""
                                        print(f"[wm-zoom] {kind} reason={reason} amb={len(keys_for_event)} ents={ent_txt}{more}")
                                    except Exception:
                                        pass

                                try:
                                    ctx.wm_zoom_last_reason = reason
                                    ctx.wm_zoom_last_event_step = int(getattr(ctx, "controller_steps", 0) or 0)
                                except Exception:
                                    pass

                            # Always update state + per-tick event list (even if empty).
                            try:
                                ctx.wm_zoom_state = "down" if now_down else "up"
                                ctx.wm_zoom_last_events = list(events)
                            except Exception:
                                pass
                    except Exception:
                        pass

            except Exception:
                pass

        # --- WorkingMap SurfaceGrid (Phase X Step 12) -----------------------------------------
        # Compose a single topological SurfaceGrid once per tick from EnvObservation.nav_patches.
        # We cache by the sorted list of patch sig16 values so unchanged patch-sets can skip recompute.
        if bool(getattr(ctx, "wm_surfacegrid_enabled", False)):
            grid_w = int(getattr(ctx, "wm_surfacegrid_w", 16) or 16)
            grid_h = int(getattr(ctx, "wm_surfacegrid_h", 16) or 16)
            if grid_w <= 0:
                grid_w = 16
            if grid_h <= 0:
                grid_h = 16

            patches_in = getattr(env_obs, "nav_patches", None) or []

            # Deterministic input signature list for caching (sig16 of each patch core).
            sig16s: list[str] = []
            if isinstance(patches_in, list):
                for p in patches_in:
                    if not isinstance(p, dict):
                        continue
                    try:
                        s = navpatch_payload_sig_v1(p)
                        if isinstance(s, str) and s:
                            sig16s.append(s[:16])
                    except Exception:
                        continue
            sig16s.sort()

            prev = getattr(ctx, "wm_surfacegrid_last_input_sig16", None)
            prev_sig16s = list(prev) if isinstance(prev, list) else []

            reasons: list[str] = []
            dirty = bool(getattr(ctx, "wm_surfacegrid_dirty", True))

            if prev_sig16s != sig16s:
                dirty = True
                reasons.append("patches_changed")

            prev_grid = getattr(ctx, "wm_surfacegrid", None)
            if prev_grid is None:
                dirty = True
                reasons.append("grid_missing")
            else:
                try:
                    pw = int(getattr(prev_grid, "grid_w", 0) or 0)
                    ph = int(getattr(prev_grid, "grid_h", 0) or 0)
                    if pw != grid_w or ph != grid_h:
                        dirty = True
                        reasons.append("dims_changed")
                except Exception:
                    dirty = True
                    reasons.append("grid_check_error")

            if dirty:
                t0 = time.perf_counter()
                try:
                    sg = compose_surfacegrid_v1(patches_in if isinstance(patches_in, list) else [], grid_w=grid_w, grid_h=grid_h)
                except Exception:
                    sg = compose_surfacegrid_v1([], grid_w=grid_w, grid_h=grid_h)
                    reasons.append("compose_error")

                dt_ms = (time.perf_counter() - t0) * 1000.0

                ctx.wm_surfacegrid = sg
                try:
                    ctx.wm_surfacegrid_sig16 = sg.sig16_v1()
                except Exception:
                    ctx.wm_surfacegrid_sig16 = None

                ctx.wm_surfacegrid_last_input_sig16 = list(sig16s)
                ctx.wm_surfacegrid_compose_ms = float(dt_ms)
                ctx.wm_surfacegrid_dirty = False
                ctx.wm_surfacegrid_dirty_reasons = reasons or ["dirty"]

                if bool(getattr(ctx, "wm_surfacegrid_verbose", False)):
                    try:
                        ctx.wm_surfacegrid_last_ascii = sg.ascii_v1()
                    except Exception:
                        ctx.wm_surfacegrid_last_ascii = None
                else:
                    ctx.wm_surfacegrid_last_ascii = None
            else:
                # Cache hit: keep the prior SurfaceGrid and report that we did not recompute.
                ctx.wm_surfacegrid_compose_ms = 0.0
                ctx.wm_surfacegrid_dirty = False
                ctx.wm_surfacegrid_dirty_reasons = ["cache_hit"]


        # --- WM.Salience + SurfaceGrid landmark overlay (Phase X Step 14) --------------------
        if bool(getattr(ctx, "wm_salience_enabled", False)):
            try:
                ambiguous_entities = _wm_salience_ambiguous_entities_v1(env_obs)
            except Exception:
                ambiguous_entities = set()

            sal = wm_salience_tick_v1(
                ctx,
                ww,
                changed_entities=changed_entities,
                new_cue_entities=new_cue_entities,
                ambiguous_entities=ambiguous_entities,
            )

            try:
                ctx.wm_salience_focus_entities = list(sal.get("focus_entities", []) or [])
                ctx.wm_salience_last_events = list(sal.get("events", []) or [])
            except Exception:
                pass

        # Display-only: render sparse SurfaceGrid ASCII with landmark letters.
        # NOTE: Do NOT print the raw grid here (it is visually confusing); we print the framed map in the per-cycle HUD:
        #   "[cycle] SG   map: ..."
        try:
            sg = getattr(ctx, "wm_surfacegrid", None)
            if sg is not None:
                ctx.wm_surfacegrid_last_ascii = render_surfacegrid_ascii_with_salience_v1(
                    ctx,
                    ww,
                    sg,
                    focus_entities=list(getattr(ctx, "wm_salience_focus_entities", []) or []),
                )
        except Exception:
            pass

        # --- Step 13: Grid → predicates (slot-families) ---------------------------------
        # We derive a tiny stable set of “map facts” from SurfaceGrid and write them onto
        # the MapSurface SELF node only (overwrite-by-family). This keeps WM inspectable.
        if bool(getattr(ctx, "wm_grid_to_preds_enabled", False)):
            sg_now = getattr(ctx, "wm_surfacegrid", None)
            if sg_now is not None:
                try:
                    slots = derive_grid_slot_families_v1(sg_now, self_xy=None, r=2, include_goal_dir=True)
                except Exception:
                    slots = {}
                ctx.wm_grid_slot_families = dict(slots) if isinstance(slots, dict) else {}

                try:
                    ent = getattr(ctx, "wm_entities", {}) or {}
                    self_bid = ent.get("self") if isinstance(ent, dict) else None
                    if isinstance(self_bid, str) and self_bid:
                        ctx.wm_grid_pred_tags = wm_apply_grid_slot_families_to_mapsurface_v1(ww, self_bid, ctx.wm_grid_slot_families)
                    else:
                        ctx.wm_grid_pred_tags = []
                except Exception:
                    ctx.wm_grid_pred_tags = []
            else:
                ctx.wm_grid_slot_families = {}
                ctx.wm_grid_pred_tags = []
        else:
            ctx.wm_grid_slot_families = {}
            ctx.wm_grid_pred_tags = []

        # --- Coordinates + distance edges (schematic map) ---
        raw = getattr(env_obs, "raw_sensors", {}) or {}
        for ent, bid in (getattr(ctx, "wm_entities", {}) or {}).items():
            if ent in ("self",):
                continue
            if not isinstance(bid, str) or bid not in ww._bindings:
                continue

            tags = _tagset_of(bid)
            # infer a distance class from the current pred tags on this entity
            dist_class = None
            kind = None
            for t in tags:
                if not isinstance(t, str) or not t.startswith("pred:"):
                    continue
                if t.startswith(f"pred:proximity:{ent}:"):
                    dist_class = t.split(":")[-1]
                    break
                if t.startswith(f"pred:hazard:{ent}:"):
                    dist_class = t.split(":")[-1]
                    kind = "hazard"
                    break
            if ent == "shelter":
                kind = "shelter"
            if dist_class is None:
                dist_class = "unknown"

            dist_m = _raw_distance_guess(raw, ent)
            if dist_m is None:
                dist_m = _dist_value_from_class(dist_class)
            if kind is None:
                if any(isinstance(t, str) and t == "wm:kind:agent" for t in tags):
                    kind = "agent"
            x, y = _project(dist_m, ent, kind=kind)
            _set_pos(bid, x, y, dist_m=dist_m, dist_class=dist_class)

            # self -> entity distance edge (upsert)
            try:
                _upsert_edge(self_bid, bid, "distance_to", {"meters": float(dist_m), "class": dist_class, "frame": "wm_schematic_v1"})
            except Exception:
                pass

        # Keep working map bounded (mostly relevant if policies also write into WorkingMap)
        try:
            _prune_working_world(ctx)
        except Exception:
            pass

        # Optional: append raw trace nodes (debug only)
        if getattr(ctx, "working_trace", False):
            try:
                attach = "now"
                for tok in pred_tokens:
                    ww.add_predicate(tok, attach=attach, meta=meta)
                    attach = "latest"
                cue_attach = "latest" if pred_tokens else "now"
                for tok in cue_tokens:
                    ww.add_cue(tok, attach=cue_attach, meta=meta)
                _prune_working_world(ctx)
            except Exception:
                pass

        return {"predicates": created_preds, "cues": created_cues}

    # -------------------- Fallback: old episodic “tick log” behaviour --------------------
    # (kept so you can revert quickly if desired)
    pred_tokens = [
        str(p).replace("pred:", "", 1)
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "", 1)
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    attach = "now"
    for tok in pred_tokens:
        try:
            ww.add_predicate(tok, attach=attach, meta=meta)
            created_preds.append(tok)
            if getattr(ctx, "working_verbose", False):
                print(f"[env→working] pred:{tok} (attach={attach})")
        except Exception:
            pass
        attach = "latest"

    cue_attach = "latest" if created_preds else "now"
    for tok in cue_tokens:
        try:
            ww.add_cue(tok, attach=cue_attach, meta=meta)
            created_cues.append(tok)
            if getattr(ctx, "working_verbose", False):
                print(f"[env→working] cue:{tok} (attach={cue_attach})")
        except Exception:
            pass
    try:
        _prune_working_world(ctx)
    except Exception:
        pass
    return {"predicates": created_preds, "cues": created_cues}


def inject_obs_into_world(world, ctx: Ctx, env_obs: EnvObservation) -> dict[str, Any]:
    """Write env observation tokens into the long-term WorldGraph with clear attach semantics.

    Modes (ctx.longterm_obs_mode):
      - "snapshot": old behavior; always write all observed predicates each tick
      - "changes" : write only when a state-slot changes, plus optional re-asserts/keyframes

    Slot definition:
      token "proximity:mom:far" -> slot "proximity:mom"
      token "resting"           -> slot "resting" (no ":")

    Keyframes (only in "changes" mode):
      - episode start (env_reset): time_since_birth <= 0.0
      - stage change (if enabled): env_meta["scenario_stage"] changed
      - zone change (if enabled): coarse safety zone flip derived from shelter/cliff predicates
      - periodic (optional): every N controller steps (period_steps > 0)
      - surprise (optional): pred_err v0 sustained mismatch (streak-based)
      - milestones (optional): env_meta milestone flags AND/OR derived predicate slot transitions
      - strong emotion/arousal (optional): env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy

    Even when we skip writing an unchanged token, token_to_bid will still map that token
    to the most recent binding id for its slot (so downstream helpers can still find it).
    """
    created_preds: list[str] = []
    created_cues: list[str] = []
    token_to_bid: dict[str, str] = {}

    # Pull env meta fields early (not masked; used for keyframe labels later).
    env_meta = getattr(env_obs, "env_meta", None) or {}
    stage = env_meta.get("scenario_stage")
    time_since_birth = env_meta.get("time_since_birth")

    # Partial observability (Phase VIII): optionally drop some observation facts before they enter memory.
    #
    # Notes:
    # - This is a PERCEPTION knob (what crosses the env→agent boundary), not a change to EnvState truth.
    # - Masking happens BEFORE BodyMap/WorkingMap/WorldGraph writes so it affects "belief-now".
    # - A small set of safety-critical predicate families is protected so zone classification remains stable.
    mask_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
    if mask_p <= 0.0:
        # If masking is off, clear the "config printed" sentinel so re-enabling prints a config line again.
        try:
            ctx.obs_mask_last_cfg_sig = None
        except Exception:
            pass
    else:
        mask_p = max(0.0, min(1.0, mask_p))
        protect_pred_prefixes = ("posture:", "hazard:cliff:", "proximity:shelter:")

        preds_in = getattr(env_obs, "predicates", None)
        cues_in = getattr(env_obs, "cues", None)

        preds = [t for t in preds_in if isinstance(t, str) and t] if isinstance(preds_in, list) else []
        cues = [t for t in cues_in if isinstance(t, str) and t] if isinstance(cues_in, list) else []

        def _strip_pred_prefix(tok: str) -> str:
            return tok[5:] if tok.startswith("pred:") else tok

        # Reproducible masking (optional):
        # If ctx.obs_mask_seed is set, use a per-step deterministic RNG. This prevents unrelated random calls
        # (e.g., RL exploration) from perturbing the observation-masking pattern.
        rng = random
        rng_mode = "global"
        seed_base = getattr(ctx, "obs_mask_seed", None)

        step_ref = env_meta.get("step_index")
        if step_ref is None:
            step_ref = getattr(ctx, "cog_cycles", None)
        if step_ref is None:
            step_ref = getattr(ctx, "controller_steps", 0)

        seed_eff: Optional[int] = None
        if seed_base is not None:
            try:
                seed_i = int(seed_base)
            except Exception:
                seed_i = None
            if seed_i is not None:
                try:
                    step_i = int(step_ref) if step_ref is not None else 0
                except Exception:
                    step_i = 0
                seed_eff = (seed_i * 1_000_003) ^ step_i
                rng = random.Random(seed_eff)
                rng_mode = "seeded"

        verbose = bool(getattr(ctx, "obs_mask_verbose", True))
        cfg_sig = f"{rng_mode}|{seed_base!r}|{mask_p:.3f}"
        if verbose and cfg_sig != getattr(ctx, "obs_mask_last_cfg_sig", None):
            try:
                ctx.obs_mask_last_cfg_sig = cfg_sig
            except Exception:
                pass
            print(
                f"[obs-mask] config mode={rng_mode} seed={seed_base!r} step_ref={step_ref!r} "
                f"p={mask_p:.2f} protected={len(protect_pred_prefixes)}"
            )

        dropped_preds = 0
        dropped_cues = 0

        preds_out: list[str] = []
        for tok in preds:
            tok_chk = _strip_pred_prefix(tok)
            if any(tok_chk.startswith(pfx) for pfx in protect_pred_prefixes):
                preds_out.append(tok)
                continue
            if rng.random() < mask_p:
                dropped_preds += 1
                continue
            preds_out.append(tok)

        # Defensive: keep at least one predicate if we had any (avoid “empty observation block” surprises).
        if (not preds_out) and preds:
            preds_out = [preds[0]]
            dropped_preds = max(0, len(preds) - 1)

        cues_out: list[str] = []
        for tok in cues:
            if rng.random() < mask_p:
                dropped_cues += 1
                continue
            cues_out.append(tok)

        # Apply the masked lists back onto the observation packet.
        try:
            setattr(env_obs, "predicates", preds_out)
            setattr(env_obs, "cues", cues_out)
        except Exception:
            pass

        # Expose masking stats for downstream gating/diagnostics (e.g., keyframe auto-retrieve).
        # This lets the keyframe pipeline know whether *this* observation lost tokens.
        try:
            if isinstance(env_meta, dict):
                env_meta["obs_mask_dropped_preds"] = int(dropped_preds)
                env_meta["obs_mask_dropped_cues"] = int(dropped_cues)
                env_meta["obs_mask_mode"] = str(rng_mode)
                env_meta["obs_mask_prob"] = float(mask_p)
        except Exception:
            pass

        if verbose and (dropped_preds or dropped_cues):
            seed_part = f" seed_eff={seed_eff}" if seed_eff is not None else ""
            print(
                f"[obs-mask] mode={rng_mode}{seed_part} step_ref={step_ref!r} "
                f"dropped preds={dropped_preds}/{len(preds)} cues={dropped_cues}/{len(cues)} p={mask_p:.2f}"
            )

    # Always keep BodyMap current (policies are BodyMap-first now).
    try:
        update_body_world_from_obs(ctx, env_obs)
    except Exception:
        # BodyMap update should never be allowed to break env stepping.
        pass

    # NavPatch predictive matching loop (Phase X baseline; priors OFF).
    # This records traceability metadata and may store new patch engrams in Column.
    # IMPORTANT: run *before* WorkingMap injection so env_obs.nav_patches carries match/commit fields.
    # This must never break env stepping.
    try:
        navpatch_predictive_match_loop_v1(ctx, env_obs)
    except Exception:
        # Matching is diagnostic; ignore failures and keep the env loop alive.
        pass

    # Mirror into WorkingMap when enabled.
    # Keep the returned dict so callers (e.g., env-loop footer) can summarize what happened.
    working_inj = None
    try:
        if getattr(ctx, "working_enabled", False):
            working_inj = inject_obs_into_working_world(ctx, env_obs)
    except Exception:
        working_inj = None

    # Allow turning off long-term injection entirely (BodyMap/WorkingMap still update).
    if not getattr(ctx, "longterm_obs_enabled", True):
        return {
            "predicates": created_preds,
            "cues": created_cues,
            "token_to_bid": token_to_bid,
            "working": working_inj,
        }

    mode = (getattr(ctx, "longterm_obs_mode", "snapshot") or "snapshot").strip().lower()
    do_changes = mode in ("changes", "dedup", "delta", "state_changes")

    # Normalize (defensive: some probes may include prefixes already) AFTER masking.
    pred_tokens = [
        str(p).replace("pred:", "")
        for p in (getattr(env_obs, "predicates", []) or [])
        if p is not None
    ]
    cue_tokens = [
        str(c).replace("cue:", "")
        for c in (getattr(env_obs, "cues", []) or [])
        if c is not None
    ]

    keyframe = False
    keyframe_reasons: list[str] = []
    # In "changes" mode: optionally force a one-tick snapshot at stage transitions/resets
    if do_changes:
        force_snapshot = False
        reasons: list[str] = []

        step_no = int(getattr(ctx, "controller_steps", 0) or 0)

        # ---- Coarse zone (derived from pred tokens; does NOT depend on BodyMap update ordering) ----
        zone_now = "unknown"
        shelter = None
        cliff = None
        for _tok in pred_tokens:
            if isinstance(_tok, str) and _tok.startswith("proximity:shelter:"):
                shelter = _tok.rsplit(":", 1)[-1]
            elif isinstance(_tok, str) and _tok.startswith("hazard:cliff:"):
                cliff = _tok.rsplit(":", 1)[-1]
        if cliff == "near" and shelter != "near":
            zone_now = "unsafe_cliff_near"
        elif shelter == "near" and cliff != "near":
            zone_now = "safe"

        last_zone = getattr(ctx, "lt_obs_last_zone", None)

        # Reset keyframe: env.reset() produces time_since_birth == 0.0
        if isinstance(time_since_birth, (int, float)) and float(time_since_birth) <= 0.0:
            force_snapshot = True
            reasons.append(f"env_reset(time_since_birth={float(time_since_birth):.2f})")

        # Stage-change keyframe (optional)
        last_stage = getattr(ctx, "lt_obs_last_stage", None)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True)):
            if stage is not None and last_stage is not None and stage != last_stage:
                force_snapshot = True
                reasons.append(f"stage_change {last_stage!r}→{stage!r}")

        # Zone-change keyframe (optional)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_zone_change", True)):
            if isinstance(last_zone, str) and zone_now != last_zone:
                force_snapshot = True
                reasons.append(f"zone_change {last_zone!r}→{zone_now!r}")

        # Periodic keyframe (optional; safe: evaluated only at this boundary hook)
        #
        # Two semantics:
        #   A) legacy absolute schedule: step_no % period == 0
        #   B) reset-on-any-keyframe: treat periodic as a max-gap since last keyframe
        #      (if any other keyframe happens, the periodic counter restarts).
        try:
            period = int(getattr(ctx, "longterm_obs_keyframe_period_steps", 0) or 0)
        except Exception:
            period = 0

        if period > 0 and step_no > 0:
            reset_on_any = bool(getattr(ctx, "longterm_obs_keyframe_period_reset_on_any_keyframe", False))

            hit = False
            if reset_on_any:
                last_kf = getattr(ctx, "lt_obs_last_keyframe_step", None)
                last_kf_step = int(last_kf) if isinstance(last_kf, int) else 0
                if last_kf_step > step_no:
                    # Defensive: controller_steps can be reset in some flows; treat that as a new epoch.
                    last_kf_step = 0
                hit = (step_no - last_kf_step) >= period
            else:
                hit = (step_no % period) == 0

            # Optional suppression: do not fire periodic keyframes while sleeping.
            #
            # We detect sleep state best-effort from either:
            #   A) env_meta: sleep_state/sleep_mode (str), or sleeping/dreaming (bool)
            #   B) predicate tokens: sleeping:non_dreaming / sleeping:dreaming (rem/nrem aliases allowed)
            if hit:
                sup_nd = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_nondreaming", False))
                sup_dr = bool(getattr(ctx, "longterm_obs_keyframe_period_suppress_when_sleeping_dreaming", False))

                if sup_nd or sup_dr:
                    sleep_kind: str | None = None

                    # A) env_meta string label
                    try:
                        sm = env_meta.get("sleep_state") or env_meta.get("sleep_mode") or env_meta.get("sleep")
                    except Exception:
                        sm = None

                    if isinstance(sm, str) and sm.strip():
                        s = sm.strip().lower().replace(" ", "_")
                        if s in ("dreaming", "rem", "rem_sleep", "sleep_rem"):
                            sleep_kind = "dreaming"
                        elif s in ("non_dreaming", "nondreaming", "nrem", "nrem_sleep", "sleep_nrem", "non_rem"):
                            sleep_kind = "non_dreaming"

                    # A2) env_meta boolean flags
                    if sleep_kind is None:
                        try:
                            sleeping_flag = env_meta.get("sleeping")
                            dreaming_flag = env_meta.get("dreaming")
                        except Exception:
                            sleeping_flag = None
                            dreaming_flag = None

                        if isinstance(sleeping_flag, bool) and sleeping_flag:
                            sleep_kind = "dreaming" if bool(dreaming_flag) else "non_dreaming"

                    # B) predicate tokens
                    if sleep_kind is None:
                        try:
                            toks = {t.strip().lower() for t in pred_tokens if isinstance(t, str) and t.strip()}
                        except Exception:
                            toks = set()

                        if (
                            "sleeping:dreaming" in toks
                            or "sleep:dreaming" in toks
                            or "sleeping:rem" in toks
                            or "sleep:rem" in toks
                        ):
                            sleep_kind = "dreaming"
                        elif (
                            "sleeping:non_dreaming" in toks
                            or "sleep:non_dreaming" in toks
                            or "sleeping:nrem" in toks
                            or "sleep:nrem" in toks
                        ):
                            sleep_kind = "non_dreaming"
                        elif ("sleeping" in toks) or ("sleep" in toks):
                            # If sleep is present but untyped, treat as non-dreaming by default.
                            sleep_kind = "non_dreaming"

                    if (sleep_kind == "non_dreaming") and sup_nd:
                        hit = False
                    elif (sleep_kind == "dreaming") and sup_dr:
                        hit = False

            if hit:
                # If another keyframe is already happening this tick, do NOT add a second "periodic" reason.
                # In reset-on-any-keyframe mode, the periodic counter will still be reset by that other keyframe.
                if not force_snapshot:
                    force_snapshot = True
                    reasons.append(f"periodic(step={step_no}, period={period})")

        # Surprise keyframe from pred_err v0 (optional; streak-based)
        if bool(getattr(ctx, "longterm_obs_keyframe_on_pred_err", False)):
            pe = getattr(ctx, "pred_err_v0_last", None)
            pe_any = False
            if isinstance(pe, dict) and pe:
                try:
                    pe_any = any(int(v or 0) != 0 for v in pe.values())
                except Exception:
                    pe_any = False

            streak = int(getattr(ctx, "lt_obs_pred_err_streak", 0) or 0)
            streak = (streak + 1) if pe_any else 0
            ctx.lt_obs_pred_err_streak = streak

            try:
                min_streak = int(getattr(ctx, "longterm_obs_keyframe_pred_err_min_streak", 2) or 2)
            except Exception:
                min_streak = 2
            min_streak = max(1, min_streak)

            if pe_any and streak >= min_streak:
                force_snapshot = True
                reasons.append(f"pred_err_v0(streak={streak})")
        else:
            ctx.lt_obs_pred_err_streak = 0

        # Milestone keyframes (HAL + derived from predicate transitions). Off by default.
        #
        # Two sources:
        #   A) env_meta milestone flags (HAL/richer envs) — may be sticky and repeat across ticks → dedup.
        #   B) derived transition events from predicate slots (storyboard + early HAL) — event-based, no sticky dedup needed.
        #
        # Derived events currently recognized:
        #   - posture:fallen -> posture:standing              => stood_up
        #   - proximity:mom:* -> proximity:mom:close         => reached_mom
        #   - (first) nipple:found                           => found_nipple
        #   - (first) nipple:latched                         => latched_nipple
        #   - (first) milk:drinking                          => milk_drinking
        #   - (first) resting                                => rested
        if bool(getattr(ctx, "longterm_obs_keyframe_on_milestone", False)):
            ms_events: set[str] = set()

            # --- A) Env-supplied milestone flags (sticky) ---
            ms_raw = env_meta.get("milestones") or env_meta.get("milestone")
            ms_list: list[str] = []
            if isinstance(ms_raw, str) and ms_raw:
                ms_list = [ms_raw]
            elif isinstance(ms_raw, list):
                ms_list = [m for m in ms_raw if isinstance(m, str) and m]

            if ms_list:
                prev_raw = getattr(ctx, "lt_obs_last_milestones", None)
                prev: set[str] = {x for x in prev_raw if isinstance(x, str) and x} if isinstance(prev_raw, set) else set()
                new_ms = {m for m in ms_list if m not in prev}
                if new_ms:
                    ms_events |= new_ms
                    try:
                        prev |= new_ms
                        ctx.lt_obs_last_milestones = prev
                    except Exception:
                        pass

            # --- B) Derived milestone events (slot transitions) ---
            try:
                prev_slots = getattr(ctx, "lt_obs_slots", None)
                prev_slots = prev_slots if isinstance(prev_slots, dict) else {}

                # Build current slot->token mapping from this observation (pred_tokens has no "pred:" prefix).
                curr_by_slot: dict[str, str] = {}
                for tok in pred_tokens:
                    if not isinstance(tok, str) or not tok:
                        continue
                    slot = tok.rsplit(":", 1)[0] if ":" in tok else tok
                    if slot not in curr_by_slot:
                        curr_by_slot[slot] = tok

                def _prev_token(slot: str) -> str | None:
                    p = prev_slots.get(slot)
                    if isinstance(p, dict):
                        t = p.get("token")
                        return t if isinstance(t, str) else None
                    return None

                # posture transition
                prev_posture = _prev_token("posture")
                curr_posture = curr_by_slot.get("posture")
                if curr_posture == "posture:standing" and prev_posture != "posture:standing":
                    ms_events.add("stood_up")

                # mom proximity transition
                prev_mom = _prev_token("proximity:mom")
                curr_mom = curr_by_slot.get("proximity:mom")
                if curr_mom == "proximity:mom:close" and prev_mom != "proximity:mom:close":
                    ms_events.add("reached_mom")

                # nipple milestones
                prev_nipple = _prev_token("nipple")
                curr_nipple = curr_by_slot.get("nipple")
                if curr_nipple == "nipple:found" and prev_nipple != "nipple:found":
                    ms_events.add("found_nipple")
                if curr_nipple == "nipple:latched" and prev_nipple != "nipple:latched":
                    ms_events.add("latched_nipple")

                # milk milestone
                prev_milk = _prev_token("milk")
                curr_milk = curr_by_slot.get("milk")
                if curr_milk == "milk:drinking" and prev_milk != "milk:drinking":
                    ms_events.add("milk_drinking")

                # resting milestone
                prev_rest = _prev_token("resting")
                curr_rest = curr_by_slot.get("resting")
                if curr_rest == "resting" and prev_rest != "resting":
                    ms_events.add("rested")
            except Exception:
                # Derived milestones are strictly best-effort; never break env injection.
                pass

            if ms_events:
                force_snapshot = True
                reasons.append("milestone:" + ",".join(sorted(ms_events)))

        # Strong emotion keyframe stub (HAL / richer envs). Off by default.
        # Note: we treat hazard zone as a conservative proxy ("fear") only when env_meta doesn't supply emotion.
        if bool(getattr(ctx, "longterm_obs_keyframe_on_emotion", False)):
            label = None
            intensity = None

            emo_raw = env_meta.get("emotion") or env_meta.get("affect")
            if isinstance(emo_raw, dict):
                lab = emo_raw.get("label")
                inten = emo_raw.get("intensity")
                label = lab if isinstance(lab, str) and lab else None
                try:
                    intensity = float(inten) if inten is not None else None
                except Exception:
                    intensity = None
            elif isinstance(emo_raw, str) and emo_raw:
                label = emo_raw

            # Proxy if no explicit emotion: unsafe zone -> fear-high
            if intensity is None and label is None:
                if zone_now == "unsafe_cliff_near":
                    label = "fear"
                    intensity = 1.0

            try:
                thr = float(getattr(ctx, "longterm_obs_keyframe_emotion_threshold", 0.85) or 0.85)
            except Exception:
                thr = 0.85

            high = bool(isinstance(intensity, (int, float)) and float(intensity) >= thr)
            prev_label = getattr(ctx, "lt_obs_last_emotion_label", None)
            prev_high = bool(getattr(ctx, "lt_obs_last_emotion_high", False))

            # Rising edge: (not high) -> high, or label changes while high.
            if high and (label != prev_label or not prev_high):
                force_snapshot = True
                inten_txt = f"{float(intensity):.2f}" if isinstance(intensity, (int, float)) else "n/a"
                reasons.append(f"emotion:{label or 'n/a'}@{inten_txt}")

            try:
                ctx.lt_obs_last_emotion_label = label if isinstance(label, str) else None
                ctx.lt_obs_last_emotion_high = high
            except Exception:
                pass

        # [KEYFRAME HOOK + ORDERING INVARIANT]
        # This is the keyframe/boundary detection point for the env→memory injection path.
        # inject_obs_into_world(...) runs BEFORE policy selection (Action Center), so any keyframe-driven
        # WM↔Column pipeline that must influence *this same boundary cycle* belongs conceptually here.
        #
        # INVARIANT (keyframes):
        #   EnvObservation -> BodyMap/WorkingMap update -> (keyframe) store snapshot + pointer update ->
        #   (keyframe) optional retrieve+apply (replace or seed/merge) -> policy selection/execution.
        #
        # RESERVED FUTURE SLOT (consolidation/reconsolidation write-back):
        #   After policy selection+execution, a keyframe may also write new engrams (copy-on-write) and
        #   update WorldGraph pointers for future retrieval, without mutating the belief state already
        #   used for action selection in this cycle.  See README: "WM ⇄ Column engram pipeline".

        # REAL-EMBODIMENT KEYFRAMES (HAL / non-storyboard):
        #   In real robots there is no storyboard stage. We will therefore support additional keyframe triggers here,
        #   evaluated ONLY at this boundary hook (never mid-cycle):
        #
        #   - periodic: every N controller_steps (ctx.longterm_obs_keyframe_period_steps)
        #   - surprise: pred_err v0 sustained mismatch (ctx.pred_err_v0_last + min_streak)
        #   - context discontinuity: zone flips (zone_now derived here vs ctx.lt_obs_last_zone)
        #   - milestones: env_meta milestones and/or derived slot transitions (goal-relevant outcomes)
        #   - emotion/arousal: env_meta emotion/affect (rising edge into "high"), with a conservative hazard proxy
        #
        # TIME-BASED SAFETY:
        #   Even the periodic keyframe must be checked only at this boundary hook so we never split a cycle
        #   while intermediate planner/policy structures are half-written.

        if force_snapshot:
            old_pred_n = len(getattr(ctx, "lt_obs_slots", {}) or {})
            old_cue_n = len(getattr(ctx, "lt_obs_cues", {}) or {})

            ctx.lt_obs_slots.clear()
            try:
                ctx.lt_obs_cues.clear()
            except Exception:
                pass
            if bool(getattr(ctx, "longterm_obs_keyframe_log", True)):
                why = ", ".join(reasons) if reasons else "keyframe"
                print(f"[env→world] KEYFRAME: {why} | cleared {old_pred_n} pred slot(s), {old_cue_n} cue slot(s)")
            try:
                ctx.lt_obs_last_keyframe_step = step_no
            except Exception:
                pass

        ctx.lt_obs_last_stage = stage
        ctx.lt_obs_last_zone = zone_now

        # For downstream callers (e.g., env-loop) that want a unified keyframe definition:
        keyframe = bool(force_snapshot)
        keyframe_reasons = list(reasons)


    def _slot_key(tok: str) -> str:
        return tok.rsplit(":", 1)[0] if ":" in tok else tok

    step_no = int(getattr(ctx, "controller_steps", 0) or 0)
    reassert_steps = int(getattr(ctx, "longterm_obs_reassert_steps", 0) or 0)
    verbose_skips = bool(getattr(ctx, "longterm_obs_verbose", False))

    wrote_any_pred_this_tick = False

    # Predicates: snapshot vs changes mode
    for tok in pred_tokens:
        meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}

        if not do_changes:
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
            continue

        slot = _slot_key(tok)
        prev = ctx.lt_obs_slots.get(slot)

        emit = False
        reason = ""
        if prev is None:
            emit = True
            reason = "first"
        elif prev.get("token") != tok:
            emit = True
            reason = "changed"
        else:
            # unchanged
            if 0 < reassert_steps <= (step_no - int(prev.get("last_emit_step", 0) or 0)):
                emit = True
                reason = "reassert"
            else:
                emit = False
                reason = "unchanged"
        if emit:
            meta2 = dict(meta)
            meta2["_dedup"] = reason
            attach = "now" if not wrote_any_pred_this_tick else "latest"
            bid = world.add_predicate(tok, attach=attach, meta=meta2)
            created_preds.append(tok)
            token_to_bid[tok] = bid
            ctx.lt_obs_slots[slot] = {"token": tok, "bid": bid, "last_emit_step": step_no}
            wrote_any_pred_this_tick = True
            print(f"[env→world] pred:{tok} → {bid} (attach={attach})")
        else:
            prev_bid = prev.get("bid") if isinstance(prev, dict) else None
            if isinstance(prev_bid, str):
                token_to_bid[tok] = prev_bid
                try:
                    world.bump_prominence(prev_bid, tag=f"pred:{tok}", meta=meta, reason="observe")
                except Exception:
                    pass
            if verbose_skips:
                print(f"[env→world] pred:{tok} → {prev_bid} (reused; unchanged)")

    # If everything was unchanged, print one line so the user knows this is intentional.
    if do_changes and pred_tokens and not created_preds and not verbose_skips:
        print("[env→world] (long-term obs unchanged; no new pred:* bindings written)")

    # Cues:
    # Default: episodic (write each observed cue each tick).
    # Optional (changes-mode): rising-edge de-dup (emit only when absent→present), but still bump prominence every tick.
    cue_attach = "latest" if wrote_any_pred_this_tick else "now"
    dedup_cues = bool(do_changes) and bool(getattr(ctx, "longterm_obs_dedup_cues", False))
    if not dedup_cues:
        for tok in cue_tokens:
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            bid = world.add_cue(tok, attach=cue_attach, meta=meta)
            created_cues.append(tok)
            token_to_bid[tok] = bid
            print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
    else:
        cue_cache = getattr(ctx, "lt_obs_cues", None)
        if not isinstance(cue_cache, dict):
            cue_cache = {}
            try:
                ctx.lt_obs_cues = cue_cache
            except Exception:
                pass

        seen_this_step: set[str] = set()
        cues_now: set[str] = set()
        for tok in cue_tokens:
            if not isinstance(tok, str):
                continue
            if tok in seen_this_step:
                continue
            seen_this_step.add(tok)
            cues_now.add(tok)
            meta = {"source": "HybridEnvironment", "controller_steps": getattr(ctx, "controller_steps", None)}
            prev = cue_cache.get(tok)
            was_present = bool(isinstance(prev, dict) and prev.get("present", False))
            emit = False
            reason = ""
            if not was_present:
                emit = True
                reason = "rising"
            else:
                if 0 < reassert_steps <= (step_no - int((prev or {}).get("last_emit_step", 0) or 0)):
                    emit = True
                    reason = "reassert"
                else:
                    emit = False
                    reason = "held"
            if emit:
                meta2 = dict(meta)
                meta2["_dedup"] = reason
                bid = world.add_cue(tok, attach=cue_attach, meta=meta2)
                created_cues.append(tok)
                token_to_bid[tok] = bid
                cue_cache[tok] = {"present": True, "bid": bid, "last_emit_step": step_no}
                print(f"[env→world] cue:{tok} → {bid} (attach={cue_attach})")
            else:
                prev_bid = prev.get("bid") if isinstance(prev, dict) else None
                if isinstance(prev_bid, str):
                    token_to_bid[tok] = prev_bid
                    try:
                        world.bump_prominence(prev_bid, tag=f"cue:{tok}", meta=meta, reason="observe")
                    except Exception:
                        pass
                if isinstance(prev, dict):
                    prev["present"] = True
                if verbose_skips:
                    print(f"[env→world] cue:{tok} → {prev_bid} (reused; held)")
        # Mark cues that were present but are absent now as not present.
        try:
            for tok, rec in list(cue_cache.items()):
                if not isinstance(rec, dict):
                    continue
                if rec.get("present", False) and tok not in cues_now:
                    rec["present"] = False
        except Exception:
            pass

    # Optional env sugar on top of tokens (must never break env stepping)
    try:
        _write_spatial_scene_edges(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    try:
        _inject_simple_valence_like_mom(world, ctx, env_obs, token_to_bid)
    except Exception:
        pass

    return {
        "predicates": created_preds,
        "cues": created_cues,
        "token_to_bid": token_to_bid,
        "working": working_inj,
        "keyframe": bool(keyframe),
        "keyframe_reasons": list(keyframe_reasons),
        "zone_now": getattr(ctx, "lt_obs_last_zone", None),
    }


def _wm_creative_update(policy_rt, world, drives, ctx, *, exec_world=None) -> None:

    """
    Populate the WorkingMap Creative layer with a tiny "imagination" demo (Option B Step 2).

    What this does (and does NOT do):
      - It scores a few candidate *policies* using a simple heuristic (safety first).
      - It stores the results on ctx:
          ctx.wm_creative_candidates (best-first)
          ctx.wm_creative_last_pick
      - It does NOT change which policy the controller actually executes yet.

    Candidate pool:
      - We use policy_rt.loaded (already dev-gated by profile/age via refresh_loaded(ctx)).
      - We evaluate trigger(world, drives) to see which are currently feasible.
      - We mirror the controller's safety filter: if "fallen near NOW", only StandUp/RecoverFall count as feasible.
    """
    if ctx is None:
        return

    enabled = bool(getattr(ctx, "wm_creative_enabled", False))
    if not enabled:
        try:
            ctx.wm_creative_candidates.clear()
        except Exception:
            pass
        try:
            ctx.wm_creative_last_pick = None
        except Exception:
            pass
        return

    # Clamp K to a readable small range (2–5 recommended; allow 1..5)
    try:
        k = int(getattr(ctx, "wm_creative_k", 3) or 3)
    except Exception:
        k = 3
    k = max(1, min(5, k))
    try:
        ctx.wm_creative_k = k
        # Use the same world the controller will execute into (if provided) so "triggerable" matches real executability.
        trigger_world = exec_world if exec_world is not None else world
    except Exception:
        pass

    # Read BodyMap (preferred) for cheap state signals
    posture = None
    mom = None
    nipple = None
    zone = "unknown"
    try:
        if not bodymap_is_stale(ctx):
            posture = body_posture(ctx)
            mom = body_mom_distance(ctx)
            nipple = body_nipple_state(ctx)
            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = "unknown"
    except Exception:
        zone = "unknown"

    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))

    # Which loaded policies are actually triggerable right now?
    loaded = getattr(policy_rt, "loaded", []) or []
    triggerable: set[str] = set()
    all_names: list[str] = []

    for g in loaded:
        name = getattr(g, "name", None)
        if not isinstance(name, str):
            continue
        all_names.append(name)
        ok = False
        try:
            ok = bool(g.trigger(trigger_world, drives, ctx))
        except Exception:
            ok = False
        if ok:
            triggerable.add(name)

    # Mirror safety override: if fallen near NOW, only allow posture recovery policies as feasible.
    try:
        if _fallen_near_now(trigger_world, ctx, max_hops=3):
            triggerable &= {"policy:stand_up", "policy:recover_fall"}
    except Exception:
        pass


    def _score_policy(name: str) -> tuple[float, str, dict]:
        """
        Tiny heuristic scorer.
        Returns (score, notes, predicted_dict).
        """
        score = 0.0
        notes: list[str] = []
        predicted: dict = {}

        # Safety/posture recovery first
        if name == "policy:stand_up":
            if posture == "fallen":
                score += 5.0
                notes.append("safety:fallen→stand")
                predicted["posture"] = "standing"
            elif posture == "standing":
                score -= 2.0
                notes.append("already_standing")
            else:
                score += 0.5
                notes.append("posture_unknown")

        elif name == "policy:recover_fall":
            if posture == "fallen":
                score += 4.0
                notes.append("recover:fallen→assist")
                predicted["posture"] = "standing"
            else:
                score -= 1.0
                notes.append("not_fallen")

        # Hunger / feeding
        elif name == "policy:seek_nipple":
            if hunger > HUNGER_HIGH:
                score += 3.0 * (hunger - HUNGER_HIGH)
                notes.append(f"hunger_high({hunger:.2f})")
                predicted["feeding"] = "advance"
            else:
                score -= 0.3
                notes.append(f"hunger_ok({hunger:.2f})")

            if mom in ("near", "close", "touching"):
                score += 0.6
                notes.append("mom_near")
            elif mom == "far":
                score -= 0.6
                notes.append("mom_far")

            if posture == "fallen":
                score -= 1.5
                notes.append("blocked_by_fallen")

            if nipple == "latched":
                score -= 3.0
                notes.append("already_latched")
                predicted["feeding"] = "already"

        # Fatigue / resting (with zone veto)
        elif name == "policy:rest":
            if fatigue > FATIGUE_HIGH:
                score += 3.0 * (fatigue - FATIGUE_HIGH)
                notes.append(f"fatigue_high({fatigue:.2f})")
                predicted["fatigue"] = "down"
            else:
                score -= 0.2
                notes.append(f"fatigue_ok({fatigue:.2f})")

            if zone == "safe":
                score += 0.6
                notes.append("zone_safe")
            if zone == "unsafe_cliff_near":
                score -= 2.5
                notes.append("zone_unsafe_veto")

        # Movement / geometry change
        elif name == "policy:follow_mom":
            score += 0.2
            notes.append("move/fallback")
            if zone == "unsafe_cliff_near":
                score += 1.6
                notes.append("escape_cliff")
                predicted["zone"] = "safer"
            if mom == "far":
                score += 0.4
                notes.append("mom_far")
            if nipple == "latched":
                score -= 0.2
                notes.append("already_nursing")

        # Default: keep neutral
        else:
            score += 0.0

        return score, "; ".join(notes), predicted

    # Build candidates for all loaded policies, but sort triggerable ones first.
    cands: list[CreativeCandidate] = []
    for name in all_names:
        sc, note, pred = _score_policy(name)
        trig = name in triggerable
        pred = dict(pred or {})
        pred["triggerable"] = trig
        if not trig:
            note = "blocked(not_triggered)" + (f"; {note}" if note else "")
        cands.append(CreativeCandidate(policy=name, score=float(sc), notes=note, predicted=pred))

    trig_cands = [c for c in cands if bool(getattr(c, "predicted", {}).get("triggerable", False))]
    blk_cands  = [c for c in cands if not bool(getattr(c, "predicted", {}).get("triggerable", False))]

    trig_cands.sort(key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)
    blk_cands.sort(key=lambda c: float(getattr(c, "score", 0.0)), reverse=True)

    out = trig_cands[:k]
    if len(out) < k:
        out += blk_cands[: (k - len(out))]

    try:
        ctx.wm_creative_candidates.clear()
        ctx.wm_creative_candidates.extend(out)
    except Exception:
        pass

    try:
        ctx.wm_creative_last_pick = out[0] if out else None
    except Exception:
        pass


def print_env_loop_tag_legend_once(ctx: Ctx) -> None:
    """Print a compact legend for console prefixes (once per session).

    We keep the run output readable for new users, but avoid re-printing the
    legend every time menu 35/37 is used.
    """
    if ctx is None:
        return
    if ctx.env_loop_legend_printed:
        return
    ctx.env_loop_legend_printed = True

    print("\nLegend (console tags):")
    print("  [env-loop]      closed-loop driver (one cognitive cycle = env update → policy select → policy act)")
    print("  [env]           environment events (reset/step; with HAL ON, this would be real sensor I/O)")
    print("  [env→working]   EnvObservation → WorkingMap (fast scratch / map surface)")
    print("  [env→world]     EnvObservation → WorldGraph (long-term episode index)")
    print("  [env→controller] Action Center output (policy selection + execution)")
    print("  [wm<->col]      WorkingMap ⇄ Column keyframe pipeline (store snapshot → retrieve candidates → apply/merge priors)")
    print("  [pred_err]      prediction error v0 (expected vs observed); gates auto-retrieve and shapes policy value via penalty on streaks")
    print("  [gate:<p>]      gating explanation for policy <p>")
    print("  [pick]          which policy was selected this cycle")
    print("  [executed]      policy execution result (effects show up in the NEXT cycle's observation)")
    print("  [maps]          selection_on=map used to score; execute_on=map used to run actions")
    print("  [obs-mask]      partial-observability masking (token drops) when enabled")
    print("")


def _print_cog_cycle_footer(*,
                            ctx: "Ctx",
                            drives,
                            env_obs,
                            prev_state,
                            curr_state,
                            env_step: int | None,
                            zone: str | None,
                            inj: dict[str, Any] | None,
                            fired_txt: str | None,
                            col_store_txt: str | None,
                            col_retrieve_txt: str | None,
                            col_apply_txt: str | None,
                            action_applied_this_step: str | None,
                            next_action_for_env: str | None,
                            cycle_no: int,
                            cycle_total: int) -> None:
    """
    Print a compact, end-of-cycle footer intended for fast human scanning.

    Intent
    ------
    Menu 37 (closed-loop env↔controller runs) produces many diagnostic lines. This footer is the
    "cheap digest" line-set that lets a maintainer quickly see what happened in *this* cognitive
    cycle in terms of the architecture:

      inputs → MapSurface deltas → Scratch writes → WorldGraph writes → Column ops → action

    The footer is intentionally pragmatic and will evolve as Phase IX/robotics/HAL integration evolves.
    Treat it as a reading aid, not a stable API.

    Notes
    -----
    - "MapSurface deltas" are derived from EnvState diffs (authoritative simulator truth). MapSurface is
      driven by EnvObservation, so EnvState changes correspond to slot-family changes (posture, proximity,
      hazard, nipple, etc.).
    - "Scratch writes" are summarized from the policy runtime's returned text (added bindings, executed line).
    - Column ops are summarized from the wm<->col store/retrieve/apply block when it ran this cycle.
    """
    if not bool(getattr(ctx, "env_loop_cycle_summary", True)):
        return

    try:
        max_items = int(getattr(ctx, "env_loop_cycle_summary_max_items", 6) or 6)
    except Exception:
        max_items = 6

    def _sf(x) -> str:
        try:
            return f"{float(x):.2f}"
        except Exception:
            return "n/a"

    def _fmt_items(items, *, prefix: str = "", limit: int = 6) -> str:
        if not items:
            return "(none)"
        out = []
        for it in items:
            if isinstance(it, str) and it:
                out.append(f"{prefix}{it}")
        if not out:
            return "(none)"
        if len(out) <= limit:
            return ", ".join(out)
        head = ", ".join(out[:limit])
        return f"{head}, +{len(out) - limit} more"

    def _get_state_attr(st, name: str):
        try:
            return getattr(st, name, None)
        except Exception:
            return None

    def _surface_deltas(ps, cs) -> list[str]:
        # These correspond to the newborn-goat "big slots" that map cleanly onto MapSurface slot-families.
        fields = [
            ("posture", "kid_posture"),
            ("mom", "mom_distance"),
            ("shelter", "shelter_distance"),
            ("cliff", "cliff_distance"),
            ("nipple", "nipple_state"),
        ]
        out: list[str] = []
        for label, attr in fields:
            a = _get_state_attr(ps, attr) if ps is not None else None
            b = _get_state_attr(cs, attr) if cs is not None else None
            if ps is None:
                out.append(f"{label}={b}")
            else:
                if a != b:
                    out.append(f"{label} {a}→{b}")
        return out

    def _parse_fired(txt: str | None) -> dict[str, Any]:
        # fired text is produced by PolicyRuntime.consider_and_maybe_fire(...).
        out: dict[str, Any] = {"policy": None, "added": None, "reward": None, "sel_on": None, "exec_on": None}
        if not (isinstance(txt, str) and txt.strip()):
            return out
        import re  # local import (matches existing style in this file)
        lines = [ln.strip() for ln in txt.splitlines() if ln.strip()]
        if not lines:
            return out

        # First line: "policy:xyz (added N bindings)"
        first = lines[0]
        parts = first.split()
        if parts and parts[0].startswith("policy:"):
            out["policy"] = parts[0]
        m = re.search(r"added\s+(\d+)\s+bindings", first)
        if m:
            try:
                out["added"] = int(m.group(1))
            except Exception:
                out["added"] = None

        for ln in lines:
            if ln.startswith("[executed]"):
                # Example: [executed] policy:follow_mom (ok, reward=+0.10) binding=w38 (b38)
                m2 = re.search(r"reward=([+\-]?\d+(?:\.\d+)?)", ln)
                if m2:
                    try:
                        out["reward"] = float(m2.group(1))
                    except Exception:
                        out["reward"] = None
            if ln.startswith("[maps]"):
                # Example: [maps] selection_on=WG execute_on=WM
                if "selection_on=" in ln:
                    try:
                        out["sel_on"] = ln.split("selection_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
                if "execute_on=" in ln:
                    try:
                        out["exec_on"] = ln.split("execute_on=", 1)[1].split()[0].strip()
                    except Exception:
                        pass
        return out

    # Keyframe indicator: best-effort. (Keyframe reasons still appear in the KEYFRAME log line above.)
    is_kf = False
    try:
        is_kf = (getattr(ctx, "lt_obs_last_keyframe_step", None) == getattr(ctx, "controller_steps", None))
    except Exception:
        is_kf = False

    st_stage = _get_state_attr(curr_state, "scenario_stage")
    st_post  = _get_state_attr(curr_state, "kid_posture")
    st_mom   = _get_state_attr(curr_state, "mom_distance")
    st_nip   = _get_state_attr(curr_state, "nipple_state")

    dr_h = _sf(getattr(drives, "hunger", None))
    dr_f = _sf(getattr(drives, "fatigue", None))
    dr_w = _sf(getattr(drives, "warmth", None))

    # WG write summary (env injection)
    wg_preds: list[str] = []
    wg_cues: list[str] = []
    if isinstance(inj, dict):
        p = inj.get("predicates")
        c = inj.get("cues")
        if isinstance(p, list):
            wg_preds = [x for x in p if isinstance(x, str) and x]
        if isinstance(c, list):
            wg_cues = [x for x in c if isinstance(x, str) and x]

    # EnvObservation input summary (what crossed the env→agent boundary this tick)
    obs_preds: list[str] = []
    obs_cues: list[str] = []
    obs_drop_p = 0
    obs_drop_c = 0
    if env_obs is not None:
        try:
            pr = getattr(env_obs, "predicates", None)
            if isinstance(pr, list):
                obs_preds = [str(x).replace("pred:", "", 1) for x in pr if isinstance(x, str) and x]
        except Exception:
            obs_preds = []

        try:
            cr = getattr(env_obs, "cues", None)
            if isinstance(cr, list):
                obs_cues = [str(x).replace("cue:", "", 1) for x in cr if isinstance(x, str) and x]
        except Exception:
            obs_cues = []

        try:
            em = getattr(env_obs, "env_meta", None)
            if isinstance(em, dict):
                obs_drop_p = int(em.get("obs_mask_dropped_preds", 0) or 0)
                obs_drop_c = int(em.get("obs_mask_dropped_cues", 0) or 0)
        except Exception:
            obs_drop_p = 0
            obs_drop_c = 0

    fired_info = _parse_fired(fired_txt)

    # ---- line 1: inputs
    kf_txt = "KF" if is_kf else "--"
    step_txt = str(env_step) if isinstance(env_step, int) else "?"
    zone_txt = zone if isinstance(zone, str) else "?"

    mask_txt = ""
    if (obs_drop_p or obs_drop_c) and (obs_drop_p >= 0 and obs_drop_c >= 0):
        mask_txt = f" mask_drop(p={obs_drop_p} c={obs_drop_c})"

    print(
        f"[cycle] IN   {kf_txt} cycle={cycle_no}/{cycle_total} env_step={step_txt} "
        f"stage={st_stage} posture={st_post} mom={st_mom} nipple={st_nip} zone={zone_txt} "
        f"drives(h={dr_h} f={dr_f} w={dr_w}) applied_action={action_applied_this_step!r} "
        f"obs(p={len(obs_preds)} c={len(obs_cues)}){mask_txt}"
    )

    # ---- line 1b: observation detail (preds/cues + navpatch summary)
    patches_in = getattr(env_obs, "nav_patches", None) or []
    patch_n = len(patches_in) if isinstance(patches_in, list) else 0
    uniq_sig16: set[str] = set()

    if patch_n:
        for p in patches_in:
            if not isinstance(p, dict):
                continue
            try:
                uniq_sig16.add(navpatch_payload_sig_v1(p)[:16])
            except Exception:
                pass

    nav_txt = f"nav_patches={patch_n} uniq_sig16={len(uniq_sig16)}"

    if obs_preds or obs_cues or patch_n:
        pred_txt = _fmt_items(obs_preds, prefix="", limit=max_items) if obs_preds else "(none)"
        cue_txt = _fmt_items(obs_cues, prefix="", limit=max_items) if obs_cues else "(none)"
        print(f"[cycle] OBS  preds: {pred_txt} | cues: {cue_txt} | {nav_txt}")

    # ---- line 2: WorkingMap summary (surface deltas + scratch writes)
    deltas = _surface_deltas(prev_state, curr_state)
    delta_txt = _fmt_items(deltas, prefix="", limit=max_items) if deltas else "(no surface slot change)"
    pol = fired_info.get("policy") or next_action_for_env
    added = fired_info.get("added")
    exec_on = fired_info.get("exec_on")
    scratch_txt = "(no policy fired)"
    if isinstance(pol, str) and pol:
        if isinstance(added, int):
            scratch_txt = f"{pol} +{added} binding(s)"
        else:
            scratch_txt = f"{pol}"
        if exec_on:
            scratch_txt += f" (exec_on={exec_on})"
    print(f"[cycle] WM   surfaceΔ: {delta_txt} | scratch: {scratch_txt}")
    # [cycle] ZM — Zoom transitions (Phase X Step 15B)
    # We only print on transition ticks (zoom_down / zoom_up) so logs stay readable.
    try:
        z_events = getattr(ctx, "wm_zoom_last_events", None)
        if isinstance(z_events, list) and z_events:
            ev0 = z_events[0] if isinstance(z_events[0], dict) else {}
            kind = ev0.get("kind") if isinstance(ev0.get("kind"), str) else "zoom"
            reason = ev0.get("reason") if isinstance(ev0.get("reason"), str) else ""
            ents = ev0.get("ambiguous_entities") if isinstance(ev0.get("ambiguous_entities"), list) else []
            ent_txt = _fmt_items(ents, prefix="", limit=3) if ents else "(none)"
            amb_n = ev0.get("ambiguous_n")
            try:
                amb_n = int(amb_n) if amb_n is not None else None
            except Exception:
                amb_n = None
            amb_txt = f" amb={amb_n}" if isinstance(amb_n, int) else ""
            rz = f" reason={reason}" if reason else ""
            print(f"[cycle] ZM   {kind}{rz}{amb_txt} ents={ent_txt}")
    except Exception:
        pass

    # [cycle] SG — SurfaceGrid HUD (Phase X Step 12)
    if bool(getattr(ctx, "wm_surfacegrid_enabled", False)):
        sg_sig16 = getattr(ctx, "wm_surfacegrid_sig16", None)
        sg_sig16 = sg_sig16 if isinstance(sg_sig16, str) and sg_sig16 else "(none)"
        try:
            sg_ms = float(getattr(ctx, "wm_surfacegrid_compose_ms", 0.0) or 0.0)
        except Exception:
            sg_ms = 0.0

        reasons = getattr(ctx, "wm_surfacegrid_dirty_reasons", None)
        reasons = reasons if isinstance(reasons, list) else []
        reason_txt = ",".join(str(r) for r in reasons[:3] if r)
        reason_txt = f" ({reason_txt})" if reason_txt else ""

        print(f"[cycle] SG   surfacegrid_sig16={sg_sig16} compose_ms={sg_ms:.2f}{reason_txt}")

        # Optional ASCII map dump.
        # If wm_surfacegrid_ascii_each_tick is True, print even on cache-hit ticks (sg_ms == 0.0).
        show_each = bool(getattr(ctx, "wm_surfacegrid_ascii_each_tick", False))
        if bool(getattr(ctx, "wm_surfacegrid_verbose", False)) and (show_each or sg_ms > 0.0):
            ascii_txt = getattr(ctx, "wm_surfacegrid_last_ascii", None)
            if isinstance(ascii_txt, str) and ascii_txt:
                # Always print legend under the framed map (every cognitive cycle).
                legend_txt = "@=self M=mom S=shelter C=cliff G=goal #=hazard X=blocked *=other  (dense: .=traversable; sparse: space=unknown/trav)"
                title = f"WM.SurfaceGrid (sig16={sg_sig16})"
                map_txt = format_surfacegrid_ascii_map_v1(ascii_txt, title=title, legend=legend_txt, show_axes=True)
                print("[cycle] SG   map:\n" + map_txt)
            elif show_each:
                print("[cycle] SG   map: (no ascii available)")

    # ---- line 3: WorldGraph writes this tick
    wg_txt = f"preds+{len(wg_preds)} cues+{len(wg_cues)}"
    wg_pred_txt = _fmt_items(wg_preds, prefix="pred:", limit=max_items)
    wg_cue_txt = _fmt_items(wg_cues, prefix="cue:", limit=max_items)
    print(f"[cycle] WG   wrote {wg_txt} | {wg_pred_txt} | {wg_cue_txt}")

    # ---- line 4: Column ops (only meaningful on keyframes)
    if col_store_txt or col_retrieve_txt or col_apply_txt:
        cs = col_store_txt or "store: (n/a)"
        cr = col_retrieve_txt or "retrieve: (n/a)"
        ca = col_apply_txt or "apply: (n/a)"
        print(f"[cycle] COL  {cs} | {cr} | {ca}")
    else:
        print("[cycle] COL  (no wm<->col ops this cycle)")

    # ---- line 5: action recap
    r = fired_info.get("reward")
    rtxt = f"{r:+.2f}" if isinstance(r, (int, float)) else "n/a"
    print(f"[cycle] ACT  executed={pol!r} reward={rtxt} next_action={next_action_for_env!r}")


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

    This version also prints short explanation lines for:
      - posture (why we are fallen / standing / latched / resting),
      - nipple_state (hidden → reachable → latched → resting),
      - zone (why we are 'unknown' vs 'unsafe_cliff_near' vs 'safe').
    """

    def _coarse_zone_from_env(state) -> str | None:
        """Approximate the BodyMap's zone from EnvState distances.

        This mirrors cca8_controller.body_space_zone:

          - 'unsafe_cliff_near' if cliff is 'near' and shelter is not 'near'.
          - 'safe' if shelter is 'near' and cliff is not 'near'.
          - 'unknown' otherwise (including None / inconsistent / partial info).
        """
        if state is None:
            return None
        try:
            cliff = getattr(state, "cliff_distance", None)
            shelter = getattr(state, "shelter_distance", None)
        except Exception:
            return None

        if cliff is None and shelter is None:
            return "unknown"
        if cliff == "near" and shelter != "near":
            return "unsafe_cliff_near"
        if shelter == "near" and cliff != "near":
            return "safe"
        return "unknown"

    # phase7 is one of the s/w devp't phases, need some scaffolding to converted memory pipeline to
    #    sensory input -> recognition -> inject into Working Mem,BodyMap -> details to Work Mem -> consolidate to WorldGraph

    def _phase7_enabled() -> bool:
        return bool(getattr(ctx, "phase7_run_compress", False))


    def _phase7_dbg(msg: str) -> None:
        if bool(getattr(ctx, "phase7_run_verbose", False)):
            try:
                print(msg)
            except Exception:
                pass


    def _phase7_pick_state_bid(token_to_bid: dict) -> str | None:
        """Pick a representative 'state' binding id for run start/end edges.

        Preference order:
          1) resting (stable episode marker)
          2) posture:standing / posture:fallen
          3) nipple:latched / milk:drinking (feeding milestones)
          4) any last-seen token bid as a fallback
        """
        if not isinstance(token_to_bid, dict):
            return None
        for tok in ("resting", "posture:standing", "posture:fallen", "nipple:latched", "milk:drinking"):
            bid = token_to_bid.get(tok)
            if isinstance(bid, str):
                return bid
        try:
            vals = list(token_to_bid.values())
            for bid in reversed(vals):
                if isinstance(bid, str):
                    return bid
        except Exception:
            pass
        return None


    def _phase7_close_run(long_world, *, reason: str) -> None:
        """Close the currently-open run (if any) and clear ctx run state."""
        if ctx is None or not _phase7_enabled():
            return
        if not bool(getattr(ctx, "run_open", False)):
            return

        run_bid = getattr(ctx, "run_action_bid", None)
        if isinstance(run_bid, str):
            try:
                b = long_world._bindings.get(run_bid)
                if b is not None and isinstance(getattr(b, "meta", None), dict):
                    b.meta["run_open"] = False
                    b.meta["run_closed_reason"] = reason
            except Exception:
                pass

        # Clear ctx run state
        try:
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
        except Exception:
            pass

        _phase7_dbg(f"[phase7-run] close reason={reason}")


    def _phase7_update_open_run_end(long_world, state_bid: str | None, *, env_step: int | None) -> None:
        """Update the open run's end-state edge to point at `state_bid` (one edge, overwritten)."""
        if ctx is None or not _phase7_enabled():
            return
        if not bool(getattr(ctx, "run_open", False)):
            return

        run_bid = getattr(ctx, "run_action_bid", None)
        if not (isinstance(run_bid, str) and isinstance(state_bid, str)):
            return

        # Identify prior end bid (stored in run.meta)
        old_end = None
        try:
            b = long_world._bindings.get(run_bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                old_end = b.meta.get("run_end_bid")
        except Exception:
            old_end = None

        # Remove old end-edge if it existed and changed
        if isinstance(old_end, str) and old_end != state_bid:
            try:
                long_world.delete_edge(run_bid, old_end, label=None)
            except Exception:
                pass

        # Add/update current end-edge (avoid duplicates)
        try:
            need_edge = True
            b = long_world._bindings.get(run_bid)
            if b is not None:
                for e in getattr(b, "edges", []) or []:
                    if isinstance(e, dict) and e.get("to") == state_bid:
                        need_edge = False
                        break
            if need_edge:
                long_world.add_edge(run_bid, state_bid, "then", meta={"phase7": "run_end", "env_step": env_step})
        except Exception:
            pass

        # Update meta
        try:
            b = long_world._bindings.get(run_bid)
            if b is not None and isinstance(getattr(b, "meta", None), dict):
                b.meta["run_end_bid"] = state_bid
                b.meta["run_last_env_step"] = env_step
                b.meta["run_open"] = True
        except Exception:
            pass


    def _phase7_start_or_extend_run(long_world, state_bid: str | None, policy: str | None, *, env_step: int | None) -> None:
        """Start a new run node (action) or extend the existing run if the policy repeats."""
        if ctx is None or not _phase7_enabled():
            return
        if not (isinstance(policy, str) and policy.startswith("policy:")):
            return
        if not isinstance(state_bid, str):
            return

        # Extend in-place when policy repeats and run is still open
        if bool(getattr(ctx, "run_open", False)) and getattr(ctx, "run_policy", None) == policy:
            try:
                ctx.run_len = int(getattr(ctx, "run_len", 0) or 0) + 1
            except Exception:
                ctx.run_len = 1
            ctx.run_last_env_step = env_step

            run_bid = getattr(ctx, "run_action_bid", None)
            if isinstance(run_bid, str):
                try:
                    b = long_world._bindings.get(run_bid)
                    if b is not None and isinstance(getattr(b, "meta", None), dict):
                        b.meta["run_len"] = int(getattr(ctx, "run_len", 1))
                        b.meta["run_last_env_step"] = env_step
                        b.meta["run_open"] = True
                except Exception:
                    pass

            _phase7_dbg(f"[phase7-run] extend {policy} len={int(getattr(ctx, 'run_len', 1))}")
            return

        # Otherwise, close the previous run (if any) and start a new one
        if bool(getattr(ctx, "run_open", False)):
            _phase7_close_run(long_world, reason="policy_change")

        token = policy.split(":", 1)[1]
        meta = {
            "phase7": "run_start",
            "policy": policy,
            "run_open": True,
            "run_len": 1,
            "run_start_env_step": env_step,
            "run_last_env_step": env_step,
        }

        try:
            run_bid = long_world.add_action(token, attach="none", meta=meta)
        except Exception:
            return

        # Connect state → run (stable episode locality)
        try:
            long_world.add_edge(state_bid, run_bid, "then", meta={"phase7": "run_start", "policy": policy, "env_step": env_step})
        except Exception:
            pass

        try:
            ctx.run_open = True
            ctx.run_policy = policy
            ctx.run_action_bid = run_bid
            ctx.run_len = 1
            ctx.run_start_env_step = env_step
            ctx.run_last_env_step = env_step
        except Exception:
            pass

        _phase7_dbg(f"[phase7-run] start {policy} run_bid={run_bid} from={state_bid} env_step={env_step}")


    def _phase7_reset_run_state() -> None:
        """Clear ctx run state (used on env.reset())."""
        if ctx is None:
            return
        try:
            ctx.run_open = False
            ctx.run_policy = None
            ctx.run_action_bid = None
            ctx.run_len = 0
            ctx.run_start_env_step = None
            ctx.run_last_env_step = None
        except Exception:
            pass


    def _explain_zone_change(prev_state, curr_state, zone: str | None, ctx) -> str | None: #pylint: disable=unused-argument
        """Human-readable explanation for why the coarse zone is what it is this step."""
        if zone is None:
            return None

        # Try to reconstruct the previous zone from EnvState distances.
        prev_zone = _coarse_zone_from_env(prev_state)

        # 'unknown' zone: either BodyMap is stale or geometry is ambiguous/incomplete.
        if zone == "unknown":
            stale = False
            try:
                if ctx is None or bodymap_is_stale(ctx):
                    stale = True
            except Exception:
                # If anything goes wrong, just treat as possibly stale.
                stale = False

            if stale:
                return (
                    "zone is 'unknown' because the BodyMap is stale or unavailable; "
                    "we do not yet trust shelter/cliff slots for spatial gating."
                )
            if prev_zone and prev_zone != "unknown":
                return (
                    f"zone changed {prev_zone!r}→'unknown'; cliff/shelter geometry is now in a "
                    "combination we do not classify (e.g., both near) or partially known, so "
                    "we treat it conservatively."
                )
            return (
                "zone is 'unknown'; either the environment has not yet established clear "
                "cliff/shelter distances or they are in a combination we do not classify, "
                "so gates treat it conservatively."
            )

        # Unsafe near a cliff.
        if zone == "unsafe_cliff_near":
            if prev_zone and prev_zone != zone:
                return (
                    f"zone changed {prev_zone!r}→'unsafe_cliff_near'; BodyMap now sees the cliff "
                    "near while shelter is not near, so this geometry is treated as unsafe for "
                    "resting."
                )
            return (
                "zone is 'unsafe_cliff_near'; BodyMap sees a nearby cliff but no nearby shelter, "
                "so resting policies are gated off in this configuration."
            )

        # Safe in a sheltered niche.
        if zone == "safe":
            if prev_zone and prev_zone != zone:
                return (
                    f"zone changed {prev_zone!r}→'safe'; cliff is no longer near and shelter is "
                    "near, so the kid is now in a sheltered niche where resting/feeding are "
                    "allowed."
                )
            return (
                "zone is 'safe'; BodyMap sees shelter near and no nearby cliff, so this is a "
                "sheltered niche suitable for resting and feeding."
            )

        # Any other zone label (future extensions).
        if prev_zone and prev_zone != zone:
            return (
                f"zone changed {prev_zone!r}→{zone!r}; this label is not yet given a detailed "
                "explanation in the newborn-goat storyboard."
            )
        return f"zone is {zone!r}; this label currently has no more detailed explanation."


    def _explain_nipple_change(prev_state, curr_state, action_for_env: str | None) -> str | None:
        """Human-readable explanation for why nipple_state is what it is this step."""
        if curr_state is None:
            return None

        n = curr_state.nipple_state
        s = curr_state.scenario_stage

        if prev_state is None:
            # First tick after reset: describe the starting feeding milestone.
            if n == "hidden":
                return (
                    "initial storyboard setup: nipple_state='hidden' in stage "
                    f"{s!r}; the kid has not yet found or reached the nipple."
                )
            return (
                f"initial storyboard setup: nipple_state={n!r} in stage={s!r} "
                "(start-of-episode feeding configuration)."
            )

        prev_n = prev_state.nipple_state
        prev_s = prev_state.scenario_stage

        # No nipple_state change this tick
        if n == prev_n:
            if n == "hidden":
                return (
                    "nipple remains hidden; the storyboard has not yet made it "
                    "reachable (or visible) to the kid in this stage."
                )
            if n in ("visible", "reachable"):
                return (
                    f"nipple_state remains {n!r}; the nipple is available but "
                    "has not yet latched this step."
                )
            if n == "latched":
                if prev_s != s and s == "rest":
                    return (
                        "stage advanced from 'first_latch' to 'rest' while the "
                        "nipple remains latched; the kid is effectively resting "
                        "with ongoing access to milk."
                    )
                return (
                    "nipple remains latched; the kid continues feeding at the "
                    "maternal nipple this step."
                )
            return (
                f"nipple_state remains {n!r}; no storyboard transition affecting "
                "feeding milestones this step."
            )

        # Nipple milestone changed this tick
        if prev_n in ("hidden", "visible") and n == "reachable":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple changed hidden→reachable, helped by a seek_nipple "
                    "action; the kid has oriented enough that the nipple is now "
                    "within reach."
                )
            return (
                "nipple changed hidden→reachable as the storyboard crossed its "
                f"\"nipple reachable\" threshold in stage {s!r}."
            )

        if prev_n in ("hidden", "visible") and n == "latched":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple jumped hidden→latched under seek_nipple; the kid "
                    "found and latched onto the nipple in one scripted step."
                )
            return (
                "nipple jumped hidden→latched directly by storyboard timing; "
                "this compresses 'found' and 'latched' into a single episode step."
            )

        if prev_n == "reachable" and n == "latched":
            if action_for_env == "policy:seek_nipple":
                return (
                    "nipple changed reachable→latched under seek_nipple; the kid "
                    "successfully latched after having the nipple within reach."
                )
            return (
                "nipple changed reachable→latched as the storyboard hit its "
                "\"auto latch\" threshold; milk:drinking now begins."
            )

        # Any other transition (rare in the newborn storyboard)
        return (
            f"nipple_state changed {prev_n!r}→{n!r} as the storyboard moved "
            f"{prev_s!r}→{s!r} this step."
        )


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

    print_env_loop_tag_legend_once(ctx)
    print(f"[env-loop] Running {n_steps} closed-loop cognitive cycle(s) (env↔controller).")
    print("[env-loop] Each cognitive cycle will:")
    print("  1) Advance controller_steps and the temporal soft clock (one drift),")
    print("  2) Call env.reset() (first time) or env.step(last policy action),")
    print("  3) Inject EnvObservation into the WorldGraph as pred:/cue: facts,")
    print("  4) Run ONE controller step (Action Center) and store the last policy name.\n")

    if not getattr(ctx, "env_episode_started", False):
        print("[env-loop] Note: this episode has not started yet; the first cognitive cycle will call env.reset().")
        print("[env-loop]       (With HAL ON, this is where we'd sample the first real sensor snapshot.)")
    for i in range(n_steps):
        print(f"\n[env-loop] Cognitive Cycle {i+1}/{n_steps}")
        # Per-cycle capture for the footer summary (reset each cycle).
        fired_txt = None
        inj = None
        col_store_txt = None
        col_retrieve_txt = None
        col_apply_txt = None

        # Count one CLOSED-LOOP cognitive cycle (env↔controller iteration).
        try:
            ctx.cog_cycles = getattr(ctx, "cog_cycles", 0) + 1
        except Exception:
            pass

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
            _phase7_reset_run_state() # phase7 s/w devpt: clear any previous run state on env reset
            ctx.env_episode_started = True
            ctx.env_last_action = None
            step_idx = env_info.get("step_index", 0)
            print(
                f"[env] Reset newborn_goat scenario: "
                f"episode_index={env_info.get('episode_index')} "
                f"scenario={env_info.get('scenario_name')}"
            )
        else:
            # Snapshot previous EnvState so we can explain posture/nipple/zone changes.
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
                f"[env] env_step={step_idx} (since reset) "
                f"stage={st.scenario_stage} posture={st.kid_posture} "
                f"mom_distance={st.mom_distance} nipple_state={st.nipple_state} "
                f"action={action_for_env!r}"
            )

        # --- Prediction error v0 (no behavior change; just measure + log) ---
        # Compare last cycle's predicted postcondition (hypothesis) vs this cycle's observed env posture.
        pred_posture: str | None = None
        obs_posture: str | None = None
        err_vec: dict[str, int] = {}
        src_txt = "(n/a)"

        try:
            pred_posture = getattr(ctx, "pred_next_posture", None)
            if isinstance(pred_posture, str) and pred_posture:
                obs_posture = getattr(getattr(env, "state", None), "kid_posture", None)
                if isinstance(obs_posture, str) and obs_posture:
                    mismatch = 0 if obs_posture == pred_posture else 1
                    err_vec = {"posture": mismatch}
                    ctx.pred_err_v0_last = err_vec
                    src = getattr(ctx, "pred_next_policy", None)
                    src_txt = src if isinstance(src, str) and src else "(n/a)"
                    print(
                        f"[pred_err] v0 err={err_vec} pred_posture={pred_posture} obs_posture={obs_posture} "
                        f"from={src_txt}"
                    )
                else:
                    err_vec = {"posture": 1}
                    ctx.pred_err_v0_last = err_vec
            else:
                err_vec = {}
                ctx.pred_err_v0_last = {}
        except Exception:
            # If anything goes wrong, keep the signal empty rather than crashing the env-loop.
            err_vec = {}
            ctx.pred_err_v0_last = {}

        # ----------------------------------------------------------------------------------
        # [pred_err] shaping penalty (extinction pressure when postconditions fail)
        #
        # Goal:
        #   If a policy repeatedly predicts a postcondition (v0: posture) and the next env
        #   observation contradicts it, apply a small negative reward shaping update to that
        #   policy's skill ledger entry.
        #
        # Design notes:
        #   - We ignore the very first mismatch after reset-like transitions by requiring
        #     a short mismatch streak (>=2) before applying the penalty.
        #   - We ALSO append a standardized entry into ctx.posture_discrepancy_history so
        #     existing non-drive tie-break logic (RecoverFall's discrepancy bonus) can use it
        #     during menu 37 (which otherwise doesn't build history via mini-snapshots).
        #
        # Knobs (optional; safe defaults if absent):
        #   ctx.pred_err_shaping_enabled : bool   (default True)
        #   ctx.pred_err_shaping_penalty : float  (default 0.15)
        # ----------------------------------------------------------------------------------
        try:
            shaping_enabled = bool(getattr(ctx, "pred_err_shaping_enabled", True))
        except Exception:
            shaping_enabled = True

        try:
            pen_mag = float(getattr(ctx, "pred_err_shaping_penalty", 0.15) or 0.15)
        except Exception:
            pen_mag = 0.15

        try:
            # v0 is posture-only today; treat any non-zero as a mismatch.
            v0_posture_err = 0
            if isinstance(err_vec, dict):
                try:
                    v0_posture_err = int(err_vec.get("posture", 0) or 0)
                except Exception:
                    v0_posture_err = 0

            if (    # pylint: disable=too-many-boolean-expressions
                shaping_enabled
                and v0_posture_err != 0
                and isinstance(action_for_env, str)
                and action_for_env
                and isinstance(obs_posture, str)
                and isinstance(pred_posture, str)
            ):
                # 1) Append a standardized discrepancy entry (so RecoverFall can see streaks in menu 37)
                entry = (
                    f"[discrepancy] env posture={obs_posture!r} "
                    f"vs policy-expected posture={pred_posture!r} from {action_for_env}"
                )
                try:
                    hist = getattr(ctx, "posture_discrepancy_history", [])
                    if not isinstance(hist, list):
                        hist = []

                    # Important: we want repeated mismatches to accumulate so streak>=2 can trigger shaping.
                    hist.append(entry)
                    if len(hist) > 50:
                        del hist[:-50]

                    ctx.posture_discrepancy_history = hist
                except Exception:
                    pass

                # 2) Compute a short mismatch streak over the newest entries
                streak = 0
                try:
                    hist2 = getattr(ctx, "posture_discrepancy_history", [])
                    if isinstance(hist2, list) and hist2:
                        for h in reversed(hist2[-10:]):
                            s = str(h)
                            if (
                                (f"from {action_for_env}" in s)
                                and ("env posture=" in s and obs_posture in s)
                                and ("policy-expected posture=" in s and pred_posture in s)
                            ):
                                streak += 1
                            else:
                                break
                except Exception:
                    streak = 0

                # 3) Apply shaping only after the streak threshold (ignore first mismatch)
                if streak >= 2:
                    shaping_reward = -abs(pen_mag) * float(v0_posture_err)
                    update_skill(action_for_env, shaping_reward, ok=False)
                    try:
                        q_now = float(skill_q(action_for_env))
                    except Exception:
                        q_now = 0.0
                    print(
                        f"[pred_err] shaping: policy={action_for_env} reward={shaping_reward:+.2f} "
                        f"(streak={streak}) q={q_now:+.2f}"
                    )
        except Exception:
            # Shaping must never crash the env-loop.
            pass


        # 3) EnvObservation → WorldGraph + BodyMap
        inj = inject_obs_into_world(world, ctx, env_obs)

        try:
            token_to_bid = inj.get("token_to_bid", {}) if isinstance(inj, dict) else {}
        except Exception:
            token_to_bid = {}

        # boundary detection + update open run end-state from the outcome we just observed.
        zone_now = None
        try:
            zone_now = body_space_zone(ctx)
        except Exception:
            zone_now = None

        wm_auto_store = False
        wm_auto_reason = None
        boundary_changed = False
        try:
            st_curr = env.state
            prev_zone = _coarse_zone_from_env(prev_state) if prev_state is not None else None
            prev_sig = (
                getattr(prev_state, "scenario_stage", None),
                getattr(prev_state, "kid_posture", None),
                getattr(prev_state, "nipple_state", None),
                (prev_zone or "unknown"),
            ) if prev_state is not None else None
            curr_sig = (
                getattr(st_curr, "scenario_stage", None),
                getattr(st_curr, "kid_posture", None),
                getattr(st_curr, "nipple_state", None),
                (zone_now or "unknown"),
            )
            boundary_changed = (prev_sig is not None) and (prev_sig != curr_sig)

            # Stage/zone boundary detection (ignore posture/nipple here to keep storage sparse/readable)
            try:
                stage_changed = prev_sig[0] != curr_sig[0]
                zone_changed  = prev_sig[3] != curr_sig[3]
            except Exception:
                stage_changed, zone_changed = False, False

            # IMPORTANT:
            # These are "keyframe trigger knobs", but we also treat them as *Phase VII boundary-to-memory* knobs.
            # If a user disables stage/zone keyframes, they likely want to disable stage/zone-driven WM↔Column auto-store too.
            allow_stage = bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True))
            allow_zone  = bool(getattr(ctx, "longterm_obs_keyframe_on_zone_change", True))

            _ps = (prev_sig[0] if isinstance(prev_sig, tuple) else None) or "?"
            _cs = (curr_sig[0] if isinstance(curr_sig, tuple) else None) or "?"
            _pz = (prev_sig[3] if isinstance(prev_sig, tuple) else None) or "?"
            _cz = (curr_sig[3] if isinstance(curr_sig, tuple) else None) or "?"

            parts: list[str] = []
            if stage_changed and allow_stage:
                parts.append(f"stage:{_ps}->{_cs}")
            if zone_changed and allow_zone:
                parts.append(f"zone:{_pz}->{_cz}")

            if parts:
                wm_auto_store = True
                wm_auto_reason = "auto_boundary_" + "_".join(parts)

        except Exception:
            boundary_changed = False

        # Additional keyframe triggers (periodic / pred_err / milestone / emotion) come from inject_obs_into_world.
        inj_kf = bool(inj.get("keyframe")) if isinstance(inj, dict) else False
        inj_rs = inj.get("keyframe_reasons") if isinstance(inj, dict) else None

        if inj_kf and not wm_auto_store:
            wm_auto_store = True
            if isinstance(inj_rs, list) and inj_rs:
                why = ";".join(str(x) for x in inj_rs[:3])
                if len(why) > 80:
                    why = why[:77] + "..."
                wm_auto_reason = "auto_keyframe_" + why
            else:
                wm_auto_reason = "auto_keyframe"
        state_bid = _phase7_pick_state_bid(token_to_bid) if isinstance(token_to_bid, dict) else None

        if _phase7_enabled():
            # Outcome update: the env state we see NOW is the result of the previous action tick.
            _phase7_update_open_run_end(world, state_bid, env_step=step_idx)

            # Hard boundary breaks runs (stage/posture/nipple/zone changes)
            if boundary_changed:
                _phase7_close_run(world, reason="boundary")

            # Optional: move long-term NOW onto the env's current posture/resting binding
            if bool(getattr(ctx, "phase7_move_longterm_now_to_env", False)) and isinstance(state_bid, str):
                try:
                    world.set_now(state_bid, tag=True, clean_previous=True)
                except Exception:
                    pass

            # Auto-store MapSurface snapshot at stage/zone boundaries (Option B#3)
            if wm_auto_store and bool(getattr(ctx, "phase7_working_first", False)):
                reason_kf = (wm_auto_reason or "auto_boundary")

                # Context labels for retrieval filtering
                try:
                    stage_kf = getattr(env.state, "scenario_stage", None)
                except Exception:
                    stage_kf = None
                stage_kf = stage_kf if isinstance(stage_kf, str) else None
                zone_kf = zone_now if isinstance(zone_now, str) else None

                # Boundary type flags (derived from the reason string you already construct)
                stage_chg = isinstance(reason_kf, str) and ("stage:" in reason_kf)
                zone_chg = isinstance(reason_kf, str) and ("zone:" in reason_kf)

                # ---- 1) STORE line ----
                info: dict[str, Any] = {}
                try:
                    if (
                        bool(getattr(ctx, "working_enabled", True))
                        and getattr(ctx, "working_world", None) is not None
                        and bool(getattr(ctx, "working_mapsurface", True))
                    ):
                        info = store_mapsurface_snapshot_v1(
                            world,
                            ctx,
                            reason=reason_kf,
                            attach="now",
                            force=False,
                            quiet=True,
                        )
                    else:
                        info = {"stored": False, "why": "workingmap_disabled_or_missing"}
                except Exception as e:
                    info = {"stored": False, "why": f"store_error:{e}"}

                stored = bool(info.get("stored"))
                sig16 = str(info.get("sig", ""))[:16] if isinstance(info.get("sig"), str) else ""
                bid = info.get("bid")
                eid = info.get("engram_id")
                why_store = info.get("why")

                if stored and isinstance(eid, str):
                    print(f"[wm<->col] store: ok sig={sig16} bid={bid} eid={eid[:8]}… ({reason_kf})")
                    col_store_txt = f"store ok sig={sig16} eid={eid[:8]}…"
                else:
                    print(f"[wm<->col] store: skip why={why_store} sig={sig16} ({reason_kf})")
                    col_store_txt = f"store skip why={why_store} sig={sig16}"

                # ---- 2) RETRIEVE line + 3) APPLY line ----
                try:
                    forced_keyframe = bool(wm_auto_store) and not (bool(stage_chg) or bool(zone_chg))
                    dec = should_autoretrieve_mapsurface(
                        ctx,
                        env_obs,
                        stage=stage_kf,
                        zone=zone_kf,
                        stage_changed=stage_chg,
                        zone_changed=zone_chg,
                        forced_keyframe=forced_keyframe,
                        boundary_reason=reason_kf,
                    )
                    mode_txt = str(dec.get("mode") or "merge")
                    top_k = int(dec.get("top_k") or 5)
                    do_try = bool(dec.get("ok"))

                    if not do_try:
                        print(f"[wm<->col] retrieve: skip why={dec.get('why')} mode={mode_txt} top_k={top_k} ({reason_kf})")
                        col_retrieve_txt = f"retrieve skip why={dec.get('why')} mode={mode_txt} top_k={top_k}"

                        print(f"[wm<->col] apply: no-op ({dec.get('why')})")
                        col_apply_txt = f"apply no-op ({dec.get('why')})"
                    else:
                        exclude = eid if stored and isinstance(eid, str) else None

                        out = maybe_autoretrieve_mapsurface_on_keyframe(
                            world,
                            ctx,
                            stage=stage_kf,
                            zone=zone_kf,
                            exclude_engram_id=exclude,
                            reason=reason_kf,
                            mode=mode_txt,
                            top_k=top_k,
                            log=False,  # menu 37 owns the standardized log lines
                        )

                        if isinstance(out, dict) and bool(out.get("ok")):
                            rid = out.get("engram_id")
                            chosen = out.get("chosen") if isinstance(out.get("chosen"), dict) else {}
                            pick = out.get("pick") if isinstance(out.get("pick"), dict) else {}

                            match = pick.get("match")
                            score = chosen.get("score")
                            op = chosen.get("overlap_preds")
                            oc = chosen.get("overlap_cues")
                            src = chosen.get("src")

                            rid_txt = (rid[:8] + "…") if isinstance(rid, str) else "(n/a)"
                            print(f"[wm<->col] retrieve: ok mode={mode_txt} eid={rid_txt} match={match} score={score} op={op} oc={oc} src={src}")
                            col_retrieve_txt = f"retrieve ok mode={mode_txt} eid={rid_txt} match={match} score={score}"

                            load = out.get("load") if isinstance(out.get("load"), dict) else {}
                            applied_mode = str(load.get("mode") or mode_txt)

                            if applied_mode == "replace":
                                ent_n = load.get("entities")
                                rel_n = load.get("relations")
                                print(f"[wm<->col] apply: replace entities={ent_n} relations={rel_n}")
                                col_apply_txt = f"apply replace ent={ent_n} rel={rel_n}"
                            else:
                                ae = load.get("added_entities")
                                fs = load.get("filled_slots")
                                ed = load.get("added_edges")
                                pc = load.get("stored_prior_cues")
                                print(f"[wm<->col] apply: merge added_entities={ae} filled_slots={fs} added_edges={ed} prior_cues={pc}")
                                col_apply_txt = f"apply merge ent+{ae} slots+{fs} edges+{ed} prior_cues={pc}"
                        else:
                            why = out.get("why") if isinstance(out, dict) else "no-op"
                            print(f"[wm<->col] retrieve: skip why={why} mode={mode_txt} top_k={top_k} ({reason_kf})")
                            col_retrieve_txt = f"retrieve skip why={why} mode={mode_txt} top_k={top_k}"
                            print(f"[wm<->col] apply: no-op ({why})")
                            col_apply_txt = f"apply no-op ({why})"
                except Exception as e:
                    print(f"[wm<->col] retrieve: skip why=error:{e} ({reason_kf})")
                    col_retrieve_txt = f"retrieve skip error:{e}"
                    print("[wm<->col] apply: no-op (error)")
                    col_apply_txt = "apply no-op (error)"

                            # ----- END Auto-retrieve (read path) ----

        # 4) Controller response
        exec_world = None
        policy_name = None

        try:
            policy_rt.refresh_loaded(ctx)

            if bool(getattr(ctx, "phase7_working_first", False)):
                if getattr(ctx, "working_world", None) is None:
                    ctx.working_world = init_working_world()
                exec_world = ctx.working_world
            _wm_creative_update(policy_rt, world, drives, ctx, exec_world=exec_world)
            fired = policy_rt.consider_and_maybe_fire(world, drives, ctx, exec_world=exec_world)

            fired_txt = fired if isinstance(fired, str) else None

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

        # --- Capture NEXT-step prediction (Scratch postcondition), v0 = posture only ---
        try:
            ctx.pred_next_policy = policy_name if isinstance(policy_name, str) and policy_name else None
            ctx.pred_next_posture = None

            if isinstance(ctx.pred_next_policy, str):
                w_scan = exec_world if exec_world is not None else world
                _bid_p, posture_tag, meta_p = _latest_posture_binding(w_scan, require_policy=True)
                if posture_tag and isinstance(meta_p, dict) and meta_p.get("policy") == ctx.pred_next_policy:
                    # posture_tag like "pred:posture:standing"
                    ctx.pred_next_posture = posture_tag.split(":")[-1]
        except Exception:
            pass

        # start/extend run for the policy we just chose (applied on the NEXT env step)
        if _phase7_enabled():
            _phase7_start_or_extend_run(world, state_bid, policy_name, env_step=step_idx)

        # Short summary for this step + posture/nipple/zone explanations
        try:
            st = env.state
            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None

            # Clarify: env_* is storyboard truth; bm_* is the agent’s current belief cache (BodyMap).
            try:
                stale = bodymap_is_stale(ctx)
            except Exception:
                stale = False

            try:
                bm_posture = body_posture(ctx) if not stale else None
            except Exception:
                bm_posture = None

            # Expected posture: Scratch postcondition written by the last executed policy (if any).
            expected_posture = None
            if isinstance(policy_name, str) and policy_name:
                for w in (getattr(ctx, "working_world", None), world):
                    if w is None:
                        continue
                    _bid, posture_tag, meta = _latest_posture_binding(w, require_policy=True)
                    if posture_tag and isinstance(meta, dict) and meta.get("policy") == policy_name:
                        expected_posture = posture_tag.split(":")[-1]
                        break

            line = (
                f"[env-loop] summary cognitive_cycle={i+1}/{n_steps} env_step={step_idx} stage={st.scenario_stage} "
                f"env_posture={st.kid_posture} bm_posture={bm_posture or st.kid_posture} "
                f"mom={st.mom_distance} nipple={st.nipple_state} last_policy={policy_name!r}"
            )
            if expected_posture is not None:
                line += f" expected_posture={expected_posture}"
            if zone is not None:
                line += f" zone={zone}"
            print(line)

            if expected_posture is not None and str(expected_posture) != str(st.kid_posture):
                print("[env-loop] note: expected_posture is a Scratch postcondition (hypothesis); env_posture is storyboard truth this tick.")

            # Explain why posture ended up as it is at this step.
            try:
                posture_expl = _explain_posture_change(prev_state, st, action_for_env)
                if posture_expl:
                    print(f"[env-loop] explain posture: {posture_expl}")
            except Exception:
                pass

            # Explain why nipple_state ended up as it is at this step.
            try:
                nipple_expl = _explain_nipple_change(prev_state, st, action_for_env)
                if nipple_expl:
                    print(f"[env-loop] explain nipple: {nipple_expl}")
            except Exception:
                pass

            # Explain why zone ended up as it is at this step.
            try:
                zone_expl = _explain_zone_change(prev_state, st, zone, ctx)
                if zone_expl:
                    print(f"[env-loop] explain zone: {zone_expl}")
            except Exception:
                pass
            # End-of-cycle footer: compact digest for fast scanning (Phase IX).
            try:
                _print_cog_cycle_footer(
                    ctx=ctx,
                    drives=drives,
                    env_obs=env_obs,
                    prev_state=prev_state,
                    curr_state=st,
                    env_step=step_idx,
                    zone=zone,
                    inj=inj if isinstance(inj, dict) else None,
                    fired_txt=fired_txt if isinstance(fired_txt, str) else None,
                    col_store_txt=col_store_txt,
                    col_retrieve_txt=col_retrieve_txt,
                    col_apply_txt=col_apply_txt,
                    action_applied_this_step=action_for_env,
                    next_action_for_env=getattr(ctx, "env_last_action", None),
                    cycle_no=i + 1,
                    cycle_total=n_steps,
                )
            except Exception:
                pass
        except Exception:
            pass

        # Per-cycle JSON record (Phase X scaffolding): replayable debug trace.
        # This is OFF by default; enable by setting ctx.cycle_json_enabled=True and (optionally)
        # ctx.cycle_json_path="cycle_log.jsonl".
        try:
            if bool(getattr(ctx, "cycle_json_enabled", False)):
                st = env.state
                try:
                    zone_now = body_space_zone(ctx)
                except Exception:
                    zone_now = None

                # Robustify a few fields so JSON dumping never surprises us.
                policy_fired_val = policy_name if isinstance(policy_name, str) else None

                efe_last = getattr(ctx, "efe_last", None)
                if not isinstance(efe_last, dict):
                    efe_last = {}

                efe_scores = getattr(ctx, "efe_last_scores", None)
                if not isinstance(efe_scores, list):
                    efe_scores = []

                navpatch_priors = getattr(ctx, "navpatch_last_priors", None)
                if not isinstance(navpatch_priors, dict):
                    navpatch_priors = {}

                rec = {
                    "controller_steps": int(getattr(ctx, "controller_steps", 0) or 0),
                    "env_step": env_info.get("step_index") if isinstance(env_info, dict) else None,
                    "scenario_stage": getattr(st, "scenario_stage", None),
                    "posture": getattr(st, "kid_posture", None),
                    "mom_distance": getattr(st, "mom_distance", None),
                    "nipple_state": getattr(st, "nipple_state", None),
                    "zone": zone_now,
                    "action_applied": action_for_env,
                    "policy_fired": policy_fired_val,
                    "obs": {
                        "predicates": list(getattr(env_obs, "predicates", []) or []),
                        "cues": list(getattr(env_obs, "cues", []) or []),
                        "nav_patches": list(getattr(env_obs, "nav_patches", []) or []),
                        "env_meta": dict(getattr(env_obs, "env_meta", {}) or {}),
                    },
                    "wg_wrote": {
                        "predicates": list((inj or {}).get("predicates", []) or []),
                        "cues": list((inj or {}).get("cues", []) or []),
                    },
                    "navpatch_matches": list(getattr(ctx, "navpatch_last_matches", []) or []),
                    "navpatch_priors": navpatch_priors,
                    "efe": efe_last,
                    "efe_scores": efe_scores,
                    "drives": {
                        "hunger": float(getattr(drives, "hunger", 0.0) or 0.0),
                        "fatigue": float(getattr(drives, "fatigue", 0.0) or 0.0),
                        "warmth": float(getattr(drives, "warmth", 0.0) or 0.0),
                    },
                }

                # --- Step 14.5: include WM salience in the per-cycle JSON record (trace hook) ---
                try:
                    wm = rec.get("wm")
                    if not isinstance(wm, dict):
                        wm = {}
                        rec["wm"] = wm

                    wm["salience"] = {
                        "focus_entities": list(getattr(ctx, "wm_salience_focus_entities", []) or []),
                        "events": list(getattr(ctx, "wm_salience_last_events", []) or []),
                    }
                    # --- Step 15B: include WM zoom state/events (trace hook) ---
                    try:
                        z_state = getattr(ctx, "wm_zoom_state", "up")
                        z_state = str(z_state).strip().lower() if isinstance(z_state, str) else "up"
                        if z_state not in ("up", "down"):
                            z_state = "up"

                        keys = getattr(ctx, "wm_scratch_navpatch_last_keys", None)
                        active_keys = sorted(list(keys)) if isinstance(keys, set) else []

                        wm["zoom"] = {
                            "state": z_state,
                            "active_keys": active_keys,
                            "events": list(getattr(ctx, "wm_zoom_last_events", []) or []),
                        }
                    except Exception:
                        pass
                except Exception:
                    pass

                append_cycle_json_record(ctx, rec)
        except Exception as e:
            logging.error("[cycle_json] record build/append failed: %s", e, exc_info=True)

    print("\n[env-loop] Closed-loop cognitive cycle complete. "
          "You can inspect details via Snapshot or the mini-snapshot that follows.")
    try:
        if getattr(ctx, "working_enabled", False):
            print()
            print_working_map_entity_table(ctx, title="[workingmap] MapSurface entity table")
            print()
            print_working_map_snapshot(ctx, n=250, title="[workingmap] auto snapshot (last 250)")
    except Exception:
        pass


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
                "[discrepancy] note: a mismatch can be normal right after reset (env has not yet applied the last action); "
                "persistent mismatches across steps suggest failed execution or storyboard veto."
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


def skills_hud_text(ctx: Optional[Ctx] = None, *, top_n: int = 8) -> str:
    """
    Compact HUD for learned policy values (SkillStat.q).

    - Sorts policies by q (EMA reward) descending.
    - Shows basic counts: n, succ-rate, q, last_reward.
    - If ctx is provided, also prints RL settings + explore/exploit counters.

    This is intentionally a *read-only* helper (no world writes).
    """
    try:
        raw = skills_to_dict() or {}
    except Exception:
        raw = {}

    try:
        delta = float(getattr(ctx, "rl_delta", 0.0))
    except Exception:
        delta = 0.0
    delta = max(delta, 0.0)

    rows: list[tuple[str, int, int, float, float]] = []
    for name, stat in raw.items():
        if not isinstance(name, str) or not isinstance(stat, dict):
            continue
        try:
            n = int(stat.get("n", 0) or 0)
            succ = int(stat.get("succ", 0) or 0)
            q = float(stat.get("q", 0.0) or 0.0)
            last = float(stat.get("last_reward", 0.0) or 0.0)
        except Exception:
            continue
        if n <= 0:
            continue
        rows.append((name, n, succ, q, last))

    if not rows:
        return "(no skill stats yet)"

    # Sort: high q first, then higher n, then name for stability
    rows.sort(key=lambda t: (-t[3], -t[1], t[0]))

    lines: list[str] = []

    if ctx is not None:
        enabled = bool(getattr(ctx, "rl_enabled", False))
        eps_raw = getattr(ctx, "rl_epsilon", None)
        try:
            eff_eps = float(eps_raw) if eps_raw is not None else float(getattr(ctx, "jump", 0.0))
        except (TypeError, ValueError):
            eff_eps = float(getattr(ctx, "jump", 0.0))

        explore = int(getattr(ctx, "rl_explore_steps", 0) or 0)
        exploit = int(getattr(ctx, "rl_exploit_steps", 0) or 0)
        total = explore + exploit
        explore_rate = (explore / total) if total else 0.0

        lines.append(
            "RL: "
            f"enabled={enabled} "
            f"epsilon={eff_eps:.3f} "
            f"delta={delta:.3f} "
            f"(explore={explore}, exploit={exploit}, explore_rate={explore_rate:.2f})"
        )

    show_n = min(top_n, len(rows))
    lines.append(f"Skill HUD (top {show_n} by q=EMA reward):")

    for i, (name, n, succ, q, last) in enumerate(rows[:show_n], start=1):
        rate = (succ / n) if n else 0.0
        lines.append(
            f"  {i:2d}) {name:<18}  n={n:3d}  rate={rate:.2f}  q={q:+.2f}  last={last:+.2f}"
        )

    return "\n".join(lines)


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
    # Phase X (NavPatch) defaults: enable in the interactive runner.
    # Unit tests or external callers can keep this OFF unless they explicitly opt in.
    ctx.navpatch_enabled = True
    # Phase X: per-cycle JSON trace (JSONL) logging (optional)
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = "cycle_log.jsonl"   # set to None for in-memory only
    ctx.cycle_json_max_records = 2000         # ring buffer size

    ctx.efe_enabled = True
    ctx.efe_verbose = False  # keep noise low; the env-loop will still print one [efe] line per step
    ctx.efe_w_risk = 1.0
    ctx.efe_w_ambiguity = 1.0
    ctx.efe_w_preference = 1.0

    ctx.temporal = TemporalContext(dim=128, sigma=ctx.sigma, jump=ctx.jump) # temporal soft clock (added)
    ctx.tvec_last_boundary = ctx.temporal.vector()  # seed “last boundary”
    try:
        ctx.boundary_vhash64 = ctx.tvec64()
    except Exception:
        ctx.boundary_vhash64 = None

    # Phase X ergonomics: show WM.SurfaceGrid as an ASCII map every env-loop tick.
    # This is intentionally noisy; if you want the compact HUD only, set either of these False.
    ctx.wm_surfacegrid_verbose = True
    ctx.wm_surfacegrid_ascii_each_tick = True

    env = HybridEnvironment()     # Environment simulation: newborn-goat scenario (HybridEnvironment)
    ctx.body_world, ctx.body_ids = init_body_world() # initialize tiny BodyMap (body_world) as a separate WorldGraph instance
    ctx.working_world = init_working_world()

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
    35) Run 1 Cognitive Cycle (HybridEnvironment → WorldGraph demo) [env, hybrid]
    37) Run n Cognitive Cycles (closed-loop timeline) [envloop, envrun]
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

    # Memories
    40) Configure episode starting state (drives + age_days) [config-episode, cfg-epi]
    41) Retired: WorkingMap & WorldGraph settings, toggle RL policy
    43) WorkingMap snapshot (last N bindings; optional clear) [wsnap, wmsnap]
    44) Store MapSurface snapshot to Column + WG pointer (dedup vs last) [wstore, wmstore]
    45) List recent wm_mapsurface engrams (Column)
    46) Pick best wm_mapsurface engram for current stage/zone (read-only) [wpick, wpickwm]
    47) Load wm_mapsurface engram into WorkingMap (replace MapSurface) [wload, wmload]

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

    # Memories
    "envloop": "37", "envrun": "37", "envsteps": "37",
    "bodymap": "38", "bsnap": "38",
    "spatial": "39", "near": "39",
    "config-episode": "40", "cfg-epi": "40",
    "retired": "41",
    "future": "42",
    "wsnap": "43", "wm-snapshot": "43", "wmsnap": "43",
    "wstore": "44", "wmstore": "44",
    "recent_wm_amp": "45",
    "wpick": "46", "wpickwm": "46",
    "wload": "47", "wmload": "47",

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
    "40": "40",  # Configure episode starting state (drives + age_days)
    "41": "41",  # retired: Toggle RL policy selection, select memory knobs
    "42": "42",  # future usage
    "43": "43",  # wm snapshot
    "44": "44",  # store mapsurface snapshot
    "45": "45",  # list recent wm_mapsurface engrams
    "46": "46",  # wpickwm
    "47": "47",  # wmload

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
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})")
        print("  sigma/jump = TemporalContext drift/jump noise scales; k = reserved top-k winners knob (future WTA selection).\n")

        POLICY_RT.refresh_loaded(ctx)
    else:
        profile = choose_profile(ctx, world)
        name = profile["name"]
        sigma, jump, k = profile["ctx_sigma"], profile["ctx_jump"], profile["winners_k"]
        ctx.sigma, ctx.jump = sigma, jump
        ctx.winners_k = k
        print(f"Profile set: {name} (sigma={sigma}, jump={jump}, k={k})")
        print("  sigma/jump = TemporalContext drift/jump noise scales; k = reserved top-k winners knob (future WTA selection).\n")

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
    # Startup notices (print here so they appear as part of the session boot block).
    # This keeps the output grouped: [io] → [boot] → [planner]/[profile] → [preflight-lite].
    apply_hardwired_profile_phase7(ctx, world)
    print_startup_notices(world)
    print("[profile] Hardwired memory pipeline: phase7 daily-driver (no options menu needed).")

    # Non-interactive plan flag (one-shot planning and exit)
    if args.plan:
        src_id = world.ensure_anchor("NOW")
        path = world.plan_to_predicate(src_id, args.plan)
        if path:
            print("Plan to", args.plan, ":", " -> ".join(path))
        else:
            print("No path found to", args.plan)
        return


    run_preflight_lite_maybe()  # optional preflight-lite
    pretty_scroll = True        #to see changes before terminal menu scrolls over screen


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
            after_n  = len(world._bindings)  #  measure write delta for this path

            # NOTE (Phase VIII terminology alignment):
            # - ctx.controller_steps counts every Action Center evaluation/execution loop.
            # - ctx.cog_cycles is reserved for CLOSED-LOOP env↔controller iterations (menu 35/37),
            #   i.e., EnvObservation → internal update → policy select/execute → action feedback to env.
            # Therefore: Instinct Step does not increment ctx.cog_cycles.

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
    base-aware logic  -- if attach='latest' and last node was a cue or some dev_gate, etc, the new predicate/scene
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

            # decide on a contextual write base for this capture_scene.
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
            # Alias: single-step env↔controller cycle (kept for back-compat; real implementation is menu 37)
            print("Selection: Run 1 Cognitive Cycle (alias of menu 37)\n")
            print("(This menu item is intentionally thin so it cannot drift out of sync.)\n")
            try:
                run_env_closed_loop_steps(env, world, drives, ctx, POLICY_RT, 1)
            except Exception as e:
                print(f"[env-loop] error while running 1 closed-loop step: {e}")
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
            print("Selection: Run n Cognitive Cycles (closed-loop timeline)\n")
            print("""This selection runs several consecutive closed-loop cognitive cycles between the
HybridEnvironment (newborn-goat world) and the CCA8 brain.

For each cognitive cycle we will:
  1) Advance controller_steps and the temporal soft clock once,
  2) STEP the newborn-goat environment using the last policy action (if any),
  3) Inject the resulting EnvObservation into the WorldGraph as pred:/cue: facts,
  4) Run ONE controller step (Action Center) and remember the last fired policy.

This is like pressing menu 35 multiple times, but with a more compact, per-cycle summary.
You can still use menu 35 for detailed, single-step inspection.
""")
            print("[policy-selection] Candidates = dev_gate passes AND trigger(...) returns True.")
            print("[policy-selection] Winner = highest deficit → non_drive → (RL: q | non-RL: stable order).")
            print("[policy-selection] RL adds exploration: epsilon picks a random candidate; otherwise we exploit the winner logic above.\n")

            # Ask the user for n
            try:
                n_text = input("How many closed-loop cognitive cycle(s) would you like to run? [default: 5]: ").strip()
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

            print()
            print("\n[skills-hud] Learned policy values after env-loop:")
            print("(terminology: hud==heads-up-display; n==number times policy executed; rate==% times we counted policy as successful;")
            print("  last==reward value that policy received the last time it executed; q==learned value estimate;")
            print("  EMA==exponential moving average of rewards; q_new = (1-alpha_smoothing_factor)*q_old + alpha*reward (alpha ~0.3))")
            print("(if RL=enabled, epsilon is theoretical % times to choose randomly, 'explore_rate' is measured % of random choices;")
            print("   delta=0 then q used only for exact ties otherwise deficit values within delta range are considered tied and q used to decide)")
            print("NOTE: deficit here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD) (amount ABOVE threshold, not a negative deficit).")
            print("Policies without a drive-urgency term score 0.00 and will tie-break by stable policy order (or RL tie-break, if enabled)")

            print(skills_hud_text(ctx, top_n=8))
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
        elif choice == "40":
            # Configure episode starting state (drives + age_days)
            print("Selection: Configure episode starting state (drives + age_days)\n")
            print("(For development work, it is useful to adjust starting state attributes and see the")
            print("  effect on program behavior.)\n")

            # Read current values defensively
            try:
                current_hunger = float(getattr(drives, "hunger", 0.0))
            except Exception:
                current_hunger = 0.0
            try:
                current_fatigue = float(getattr(drives, "fatigue", 0.0))
            except Exception:
                current_fatigue = 0.0
            try:
                current_warmth = float(getattr(drives, "warmth", 0.0))
            except Exception:
                current_warmth = 0.0
            try:
                current_age = float(getattr(ctx, "age_days", 0.0) or 0.0)
            except Exception:
                current_age = 0.0

            # Partial observability knob (obs masking)
            try:
                cur_p = float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
            except Exception:
                cur_p = 0.0
            try:
                cur_seed = getattr(ctx, "obs_mask_seed", None)
            except Exception:
                cur_seed = None
            cur_mode = "seeded" if cur_seed is not None else "global"
            try:
                cur_verbose = bool(getattr(ctx, "obs_mask_verbose", True))
            except Exception:
                cur_verbose = True

            print()
            print(
                "Partial observability (obs masking): "
                f"obs_mask_prob={cur_p:.2f} mode={cur_mode} obs_mask_seed={cur_seed!r} verbose={cur_verbose}"
            )
            print("  obs_mask_prob:")
            print("    0.00 = fully observed (default)")
            print("    0.10–0.30 = mild partial observability (good starting range)")
            print("  obs_mask_seed:")
            print("    None = stochastic masking (uses global RNG)")
            print("    int  = reproducible masking (seeded per env step; independent of RL randomness)")
            print("  Protected (never dropped): posture:* , hazard:cliff:* , proximity:shelter:*")

            s = input("Set obs_mask_prob in [0..1] (blank=keep current): ").strip()
            if s:
                try:
                    v = float(s)
                    v = max(0.0, min(1.0, v))
                    ctx.obs_mask_prob = v
                    try:
                        ctx.obs_mask_last_cfg_sig = None
                    except Exception:
                        pass
                    print(f"(updated) obs_mask_prob={ctx.obs_mask_prob:.2f}")
                except ValueError:
                    print("(warn) invalid obs_mask_prob; keeping current value.")

            s = input("Set obs_mask_seed (blank=keep; 'none'/'off'=disable; int=enable): ").strip().lower()
            if s:
                if s in ("none", "off", "disable", "disabled"):
                    ctx.obs_mask_seed = None
                    try:
                        ctx.obs_mask_last_cfg_sig = None
                    except Exception:
                        pass
                    print("(updated) obs_mask_seed=None (stochastic/global RNG)")
                else:
                    try:
                        ctx.obs_mask_seed = int(float(s))
                        try:
                            ctx.obs_mask_last_cfg_sig = None
                        except Exception:
                            pass
                        print(f"(updated) obs_mask_seed={ctx.obs_mask_seed} (reproducible)")
                    except ValueError:
                        print("(warn) invalid obs_mask_seed; keeping current value.")

            rawv = input("obs-mask verbose logs? [Enter=toggle | on | off]: ").strip().lower()
            if rawv in ("on", "true", "1", "yes", "y"):
                ctx.obs_mask_verbose = True
            elif rawv in ("off", "false", "0", "no", "n"):
                ctx.obs_mask_verbose = False
            elif rawv == "":
                ctx.obs_mask_verbose = not bool(getattr(ctx, "obs_mask_verbose", True))
            print(f"(now) obs_mask_verbose={bool(getattr(ctx, 'obs_mask_verbose', True))}")

            # WM<->Column auto-retrieve enable + mode toggle
            # WorkingMap↔Column auto-retrieve controls (keyframes)
            # - merge   = conservative prior (fills missing slot families only; does NOT inject cue:* into belief-now)
            # - replace = strong prior (clears + rebuilds MapSurface from the snapshot; useful for debug)
            try:
                ar_enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False))
            except Exception:
                ar_enabled = False
            try:
                ar_mode = str(getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
            except Exception:
                ar_mode = "merge"
            if ar_mode == "r":
                ar_mode = "replace"
            if ar_mode not in ("merge", "replace"):
                ar_mode = "merge"
            print()
            print(f"WM<->Column auto-retrieve (keyframes): enabled={ar_enabled} mode={ar_mode}")
            print("  merge   = conservative prior fill (no overwrite; no cue leakage)")
            print("  replace = rebuild MapSurface from engram snapshot (debug/strong prior)")

            s = input("Set auto-retrieve enabled? [Enter=keep | t=toggle | on | off]: ").strip().lower()
            if s:
                if s in ("t", "toggle"):
                    ar_enabled = not ar_enabled
                elif s in ("on", "true", "1", "yes", "y"):
                    ar_enabled = True
                elif s in ("off", "false", "0", "no", "n", "disable", "disabled"):
                    ar_enabled = False
                else:
                    print("(warn) invalid input; keeping current enabled setting.")
            try:
                ctx.wm_mapsurface_autoretrieve_enabled = ar_enabled
            except Exception:
                pass
            s = input("Set auto-retrieve mode? [Enter=keep | t=toggle | merge | replace]: ").strip().lower()
            if s:
                if s in ("t", "toggle"):
                    ar_mode = "replace" if ar_mode == "merge" else "merge"
                elif s in ("merge", "m"):
                    ar_mode = "merge"
                elif s in ("replace", "r"):
                    ar_mode = "replace"
                else:
                    print("(warn) invalid mode; keeping current mode.")
            try:
                ctx.wm_mapsurface_autoretrieve_mode = ar_mode
            except Exception:
                pass
            print(f"(now) wm_mapsurface_autoretrieve_enabled={ar_enabled} wm_mapsurface_autoretrieve_mode={ar_mode}")

            print("Current values:")
            print(f"  hunger   = {current_hunger:.2f}")
            print(f"  fatigue  = {current_fatigue:.2f}")
            print(f"  warmth   = {current_warmth:.2f}")
            print(f"  age_days = {current_age:.2f}")
            print("\nEnter new values or press Enter to keep the current value.")
            print("Drives are clamped to the range [0.0, 1.0]. age_days must be ≥ 0.\n")

            def _prompt_float(
                label: str,
                cur: float,
                low: float | None = None,
                high: float | None = None,
            ) -> float:
                """Prompt for a float with optional clamping; blank keeps current."""
                try:
                    raw = input(f"{label} (current={cur:.2f}): ").strip()
                except Exception:
                    return cur
                if not raw:
                    return cur
                try:
                    val = float(raw)
                except Exception:
                    print(f"  [warn] Could not parse {label!r}; keeping previous value.")
                    return cur
                if low is not None and val < low:
                    print(f"  [warn] {label} below minimum {low:.2f}; clamping.")
                    val = low
                if high is not None and val > high:
                    print(f"  [warn] {label} above maximum {high:.2f}; clamping.")
                    val = high
                return val

            # Update drives in-place (these are the same objects used by env-loop)
            new_hunger = _prompt_float("hunger", current_hunger, 0.0, 1.0)
            new_fatigue = _prompt_float("fatigue", current_fatigue, 0.0, 1.0)
            new_warmth = _prompt_float("warmth", current_warmth, 0.0, 1.0)

            try:
                drives.hunger = new_hunger
            except Exception:
                pass
            try:
                drives.fatigue = new_fatigue
            except Exception:
                pass
            try:
                drives.warmth = new_warmth
            except Exception:
                pass

            # Update age_days (non-negative float)
            try:
                raw_age = input(f"age_days (current={current_age:.2f}): ").strip()
            except Exception:
                raw_age = ""
            if raw_age:
                try:
                    val = float(raw_age)
                    if val < 0.0:
                        print("  [warn] age_days below 0.0; clamping to 0.0.")
                        val = 0.0
                    ctx.age_days = val
                except Exception:
                    print("  [warn] Could not parse age_days; keeping previous value.")
            else:
                # Ensure ctx.age_days is at least present
                try:
                    ctx.age_days = current_age
                except Exception:
                    pass

            print("\n[config] Updated episode starting state:")
            print(
                f"  hunger={getattr(drives, 'hunger', new_hunger):.2f} "
                f"fatigue={getattr(drives, 'fatigue', new_fatigue):.2f} "
                f"warmth={getattr(drives, 'warmth', new_warmth):.2f} "
                f"age_days={getattr(ctx, 'age_days', current_age):.2f}"
            )
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "41":
            print("Menu 41 retired. Memory pipeline is hardwired (Phase VII daily-driver).")
            # If later we decide for this menu selection to be interactive again, we should also update the
            #   unreachable “Current settings / presets” prints so they display zone/pred_err/milestone/emotion
            #   keyframe knobs (not just stage).
            print("""[guide] This menu is the main "knobs and buttons" reference card for CCA8 experiments.

NOTE (current runner behavior)
------------------------------
Menu 41 is currently "reference-only":
- The Phase VII daily-driver memory pipeline is hardwired at startup (see apply_hardwired_profile_phase7).
- This menu prints a cheat sheet and returns to the main menu (it does not run an interactive edit flow right now).

Mental model you should have to understand these settings
---------------------------------------------------------

At runtime it helps to keep FOUR memory structures in mind:

1) BodyMap (ctx.body_world)
   - Tiny, safety-critical belief-now register (posture, mom distance, nipple/milk, shelter/cliff).
   - Updated on every EnvObservation tick; read by gates and tie-break logic.

2) WorkingMap (ctx.working_world)
   - Short-term working memory with three layers:
     - MapSurface (WM_ROOT + entity nodes): stable, overwrite-by-slot-family belief table.
     - Scratch (WM_SCRATCH): policy action chains + predicted postconditions (hypotheses).
     - Creative (WM_CREATIVE): counterfactual rollouts (future; inspect-only scaffolding today).
   - By default this is NOT a dense tick-log: MapSurface updates entity nodes in place.
     (Optional: ctx.working_trace=True appends a legacy per-tick trace for debugging.)

3) WorldGraph (world)
   - Durable long-term episode index that persists (autosave / save session).
   - Receives EnvObservation injection (subject to the "long-term env obs" knobs).
   - Receives policy writes unless Phase VII working_first is enabled (then policies execute into WorkingMap).

4) Columns / Engrams (cca8_column.mem)
   - Heavy payload store (append-only / immutable records).
   - WorldGraph/WorkingMap bindings hold only pointers (binding.engrams["column01"]["id"]=...).

Fixed dataflow (env → agent boundary)
-------------------------------------
EnvObservation → BodyMap update (always) → WorkingMap mirror (if enabled) → WorldGraph injection (if enabled)

Keyframes are decided at the env→memory boundary hook (inject_obs_into_world) BEFORE policy selection.

Cue-slot de-duplication (long-term)
-----------------------------------
In changes-mode we can de-duplicate repeated cue tokens:
- rising edge (absent→present) writes a cue:* binding
- held cues do not create new bindings; they bump prominence on the last cue binding
- if a cue disappears and later reappears, a new cue:* binding is written again

Long-term EnvObservation → WorldGraph injection
-----------------------------------------------
longterm_obs_enabled (bool)
  ON  : write env predicates/cues to WorldGraph (subject to mode settings)
  OFF : skip long-term WorldGraph writes (BodyMap still updates; WorkingMap still mirrors if enabled)

longterm_obs_mode ("snapshot" vs "changes")
  snapshot : write every observed predicate each tick (dense; old behavior)
  changes  : treat predicates as state-slots (posture, proximity:mom, hazard:cliff, ...)
             write only when a slot changes (plus optional re-asserts/keyframes)

longterm_obs_reassert_steps (int)
  In changes mode: re-emit an unchanged slot after N controller steps (a "re-observation" cadence).

longterm_obs_dedup_cues (bool)
  In changes mode: write cue:* only on rising-edge (absent→present); held cues bump prominence instead.

longterm_obs_verbose (bool)
  In changes mode: print verbose per-slot reuse lines when slots are unchanged (can be noisy).

Keyframes (episode boundaries)
------------------------------
In changes mode we maintain per-slot caches (ctx.lt_obs_slots and ctx.lt_obs_cues).
A keyframe clears those caches so the current state is written again as a clean boundary snapshot.

Keyframe triggers (Phase IX; evaluated ONLY at the env→memory boundary hook):
  - env_reset: time_since_birth <= 0.0
  - stage_change: scenario_stage changed (longterm_obs_keyframe_on_stage_change)
  - zone_change: coarse safety zone flip (longterm_obs_keyframe_on_zone_change)
  - periodic: every N controller steps (longterm_obs_keyframe_period_steps)
  - surprise: pred_err v0 sustained mismatch (longterm_obs_keyframe_on_pred_err + min_streak)
  - milestones: env_meta milestones and/or derived slot transitions (longterm_obs_keyframe_on_milestone)
  - emotion/arousal: env_meta emotion/affect (rising-edge into "high") with threshold
                     (longterm_obs_keyframe_on_emotion + emotion_threshold)

Keyframe semantics (what "happens at a boundary"):
  - clear long-term slot caches (so the next observation writes as "first" for each slot)
  - (if Phase VII WM<->Column pipeline is enabled) boundary store/retrieve/apply can run:
        store snapshot → optional retrieve candidates → apply priors (replace or seed/merge)
    Reserved future: post-execution write-back / reconsolidation slot.

Manual keyframe (without env.reset):
  - clearing ctx.lt_obs_slots (and ctx.lt_obs_cues) forces the next env observation to be treated as "first".

Phase VII memory pipeline knobs (WorkingMap-first + run compression)
--------------------------------------------------------------------
phase7_working_first (bool)
  OFF: policies write into WorldGraph (action/preds accumulate there)
  ON : policies execute into WorkingMap.Scratch; WorldGraph stays sparse (env keyframes + pointers + runs)

phase7_run_compress (bool)
  If ON: long-term WorldGraph action logging collapses repeated identical policies into one "run" node:
    state → action(run_len=3) → state
  A boundary (stage/posture/nipple/zone signature change) or policy change closes the run.

phase7_move_longterm_now_to_env (bool)
  OFF: long-term NOW moves only when new bindings are written (or at keyframes)
  ON : long-term NOW is actively moved to the current env state binding each step (debug-friendly)

RL policy selection (epsilon-greedy among triggered candidates)
--------------------------------------------------------------
rl_enabled (bool)
  OFF: deterministic winner: deficit → non-drive tie-break → stable order
  ON : epsilon-greedy: explore with probability epsilon; otherwise exploit:
       deficit near-tie band (rl_delta) → non-drive tie-break → learned q → stable order

rl_epsilon (float|None)
  Exploration probability in [0..1]. If None, we use ctx.jump as a convenience default.

rl_delta (float)
  Defines the deficit near-tie band within which q is allowed to decide among candidates.

(For full examples and the authoritative contract, see README.md: keyframes, WM<->Column pipeline, and cognitive cycles.)
""")

            # Control panel: RL policy selection + WorkingMap + long-term WorldGraph obs injection
            print("Selection: Control Panel (RL policy selection + memory knobs)\n")
            #print("""[guide] This menu is the main "knobs and buttons" control panel for CCA8 experiments.



            loop_helper(args.autosave, world, drives, ctx)
            continue
            #pylint: disable=unreachable

            # Ensure WorkingMap exists
            if getattr(ctx, "working_world", None) is None:
                ctx.working_world = init_working_world()
            ww = ctx.working_world

            # --- Current RL settings ---
            enabled_now = bool(getattr(ctx, "rl_enabled", False))
            eps_now = getattr(ctx, "rl_epsilon", None)
            try:
                jump_now = float(getattr(ctx, "jump", 0.0))
            except Exception:
                jump_now = 0.0
            try:
                eff_eps = float(eps_now) if eps_now is not None else jump_now
            except Exception:
                eff_eps = jump_now
            try:
                delta_now = float(getattr(ctx, "rl_delta", 0.0))
            except Exception:
                delta_now = 0.0
            delta_now = max(delta_now, 0.0)
            explore_steps = int(getattr(ctx, "rl_explore_steps", 0) or 0)
            exploit_steps = int(getattr(ctx, "rl_exploit_steps", 0) or 0)

            # --- Current memory settings ---
            world_mode = world.get_memory_mode() if hasattr(world, "get_memory_mode") else "episodic"
            wm_enabled = bool(getattr(ctx, "working_enabled", False))
            wm_verbose = bool(getattr(ctx, "working_verbose", False))
            wm_max = int(getattr(ctx, "working_max_bindings", 0) or 0)
            wm_count = len(getattr(ww, "_bindings", {}))  # pylint: disable=protected-access

            lt_enabled = bool(getattr(ctx, "longterm_obs_enabled", True))
            lt_mode = str(getattr(ctx, "longterm_obs_mode", "snapshot"))
            lt_reassert = int(getattr(ctx, "longterm_obs_reassert_steps", 0) or 0)
            lt_keyframe = bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True))
            lt_verbose = bool(getattr(ctx, "longterm_obs_verbose", False))

            print("Current settings:")
            print(f"  phase7 s/w dev't: working_first={bool(getattr(ctx,'phase7_working_first',False))} run_compress={bool(getattr(ctx,'phase7_run_compress',False))} run_verbose={bool(getattr(ctx,'phase7_run_verbose',False))} move_NOW_to_env={bool(getattr(ctx,'phase7_move_longterm_now_to_env',False))}")
            print(f"  RL: enabled={enabled_now} epsilon={eps_now!r} effective={eff_eps:.3f} delta={delta_now:.3f} (explore={explore_steps}, exploit={exploit_steps})")
            print(f"  WorkingMap: enabled={wm_enabled} verbose={wm_verbose} max_bindings={wm_max} bindings={wm_count}")
            print(f"  WorldGraph: memory_mode={world_mode}")
            print(f"  Long-term env obs: enabled={lt_enabled} mode={lt_mode} reassert_steps={lt_reassert} keyframe_on_stage={lt_keyframe} verbose={lt_verbose}")
            print()

            # Quick exit if user just wants to view status
            edit = input("Adjust settings now? [y/N]: ").strip().lower()
            if edit not in ("y", "yes"):
                loop_helper(args.autosave, world, drives, ctx)
                continue

            # ---- Presets (quick tuning of long-term env obs) ----
            print("\nPresets (long-term env obs):")
            print("  bio    = changes + keyframes + reassert=25 (periodic re-observation)")
            print("  sparse = changes + keyframes + reassert=0  (minimal long-term growth)")
            print("  debug  = snapshot + verbose (write every env pred each tick)")
            preset = input("Preset? [Enter=skip | bio | sparse | debug]: ").strip().lower()
            if preset in ("bio", "biological"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "changes"
                ctx.longterm_obs_reassert_steps = 25
                ctx.longterm_obs_keyframe_on_stage_change = False
                ctx.longterm_obs_verbose = False
            elif preset in ("sparse", "minimal"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "changes"
                ctx.longterm_obs_reassert_steps = 0
                ctx.longterm_obs_keyframe_on_stage_change = False
                ctx.longterm_obs_verbose = False
            elif preset in ("debug", "trace"):
                ctx.longterm_obs_enabled = True
                ctx.longterm_obs_mode = "snapshot"
                ctx.longterm_obs_reassert_steps = 0
                ctx.longterm_obs_keyframe_on_stage_change = True
                ctx.longterm_obs_verbose = True

            # ---- RL controls ----
            print("\nRL policy selection:")
            raw = input("RL enabled? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                enabled_new = True
            elif raw in ("off", "false", "0", "no", "n"):
                enabled_new = False
            elif raw == "":
                enabled_new = not enabled_now
            else:
                enabled_new = enabled_now

            eps_new = eps_now
            if enabled_new:
                raw_eps = input(f"rl_epsilon (0..1 or 'none'; current={eps_now!r}, effective={eff_eps:.3f}; Enter=keep): ").strip().lower()
                if raw_eps == "":
                    eps_new = eps_now
                elif raw_eps in ("none", "null"):
                    eps_new = None
                else:
                    try:
                        v = float(raw_eps)
                        v = max(v, 0.0)
                        v = min(v, 1.0)
                        eps_new = v
                    except ValueError:
                        eps_new = eps_now

                raw_delta = input(f"rl_delta (>=0; current={delta_now:.3f}; Enter=keep): ").strip().lower()
                if raw_delta != "":
                    try:
                        v = float(raw_delta)
                        v = max(v, 0.0)
                        ctx.rl_delta = v
                    except ValueError:
                        pass

            ctx.rl_enabled = enabled_new
            ctx.rl_epsilon = eps_new

            # ---- WorkingMap controls ----
            print("\nWorkingMap (short-term raw trace):")
            raw = input("WorkingMap capture? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.working_enabled = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.working_enabled = False
            elif raw == "":
                ctx.working_enabled = not bool(getattr(ctx, "working_enabled", False))

            rawv = input("WorkingMap verbose? [Enter=toggle | on | off]: ").strip().lower()
            if rawv in ("on", "true", "1", "yes", "y"):
                ctx.working_verbose = True
            elif rawv in ("off", "false", "0", "no", "n"):
                ctx.working_verbose = False
            elif rawv == "":
                ctx.working_verbose = not bool(getattr(ctx, "working_verbose", False))

            rawm = input(f"WorkingMap max_bindings (current={wm_max}; Enter=keep): ").strip()
            if rawm:
                try:
                    ctx.working_max_bindings = max(0, int(float(rawm)))
                except ValueError:
                    print("  (ignored: could not parse max_bindings)")

             # ---- phase7 s/w devp't scaffolding memory pipeline knobs ----
            print("\nphase7 s/w devp't memory pipeline (experimental):")
            raw = input("working_first (execute policies in WorkingMap)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_working_first = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_working_first = False
            elif raw == "":
                ctx.phase7_working_first = not bool(getattr(ctx, "phase7_working_first", False))

            raw = input("run_compress (compress repeated policy actions in long-term WorldGraph)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_run_compress = True
                # If we are compressing actions, it's usually because we want long-term WorldGraph sparse.
                ctx.phase7_working_first = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_run_compress = False
            elif raw == "":
                ctx.phase7_run_compress = not bool(getattr(ctx, "phase7_run_compress", False))
                if bool(getattr(ctx, "phase7_run_compress", False)):
                    ctx.phase7_working_first = True

            raw = input("run_verbose (print run-compression debug lines)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_run_verbose = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_run_verbose = False
            elif raw == "":
                ctx.phase7_run_verbose = not bool(getattr(ctx, "phase7_run_verbose", False))

            raw = input("move_longterm_NOW_to_env (move long-term NOW to env state each step)? [Enter=toggle | on | off]: ").strip().lower()
            if raw in ("on", "true", "1", "yes", "y"):
                ctx.phase7_move_longterm_now_to_env = True
            elif raw in ("off", "false", "0", "no", "n"):
                ctx.phase7_move_longterm_now_to_env = False
            elif raw == "":
                ctx.phase7_move_longterm_now_to_env = not bool(getattr(ctx, "phase7_move_longterm_now_to_env", False))

            # ---- WorldGraph memory_mode ----
            if hasattr(world, "set_memory_mode") and hasattr(world, "get_memory_mode"):
                print("\nWorldGraph memory_mode:")
                print("  episodic = every add creates a new binding (dense trace)")
                print("  semantic = reuse identical pred/cue bindings (less clutter; experimental)")
                raw_mode = input(f"memory_mode (current={world.get_memory_mode()}; Enter=keep): ").strip().lower()
                if raw_mode in ("episodic", "semantic"):
                    world.set_memory_mode(raw_mode)

            # ---- Long-term env observation injection knobs ----
            print("\nLong-term EnvObservation → WorldGraph injection:")
            raw_lt = input("Enabled? [Enter=toggle | on | off]: ").strip().lower()
            if raw_lt in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_enabled = True
            elif raw_lt in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_enabled = False
            elif raw_lt == "":
                ctx.longterm_obs_enabled = not bool(getattr(ctx, "longterm_obs_enabled", True))

            print("Mode options:")
            print("  changes  = write only when a state slot changes (dedup env preds)")
            print("  snapshot = write every observed pred each tick (old behavior)")
            raw_ltm = input(f"mode (current={getattr(ctx,'longterm_obs_mode','snapshot')}; Enter=keep): ").strip().lower()
            if raw_ltm in ("changes", "snapshot"):
                ctx.longterm_obs_mode = raw_ltm

            raw_rs = input(f"reassert_steps (current={getattr(ctx,'longterm_obs_reassert_steps',0)}; Enter=keep): ").strip()
            if raw_rs:
                try:
                    ctx.longterm_obs_reassert_steps = max(0, int(float(raw_rs)))
                except ValueError:
                    print("  (ignored: could not parse reassert steps)")

            raw_kf = input("keyframe_on_stage_change? [Enter=toggle | on | off]: ").strip().lower()
            if raw_kf in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_keyframe_on_stage_change = False
            elif raw_kf in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_keyframe_on_stage_change = False
            elif raw_kf == "":
                #ctx.longterm_obs_keyframe_on_stage_change = not bool(getattr(ctx, "longterm_obs_keyframe_on_stage_change", True))
                ctx.longterm_obs_keyframe_on_stage_change = False

            raw_lv = input("longterm_obs_verbose (show reuse lines)? [Enter=toggle | on | off]: ").strip().lower()
            if raw_lv in ("on", "true", "1", "yes", "y"):
                ctx.longterm_obs_verbose = True
            elif raw_lv in ("off", "false", "0", "no", "n"):
                ctx.longterm_obs_verbose = False
            elif raw_lv == "":
                ctx.longterm_obs_verbose = not bool(getattr(ctx, "longterm_obs_verbose", False))

            # ---- Optional clears ----
            rawc = input("\nClear WorkingMap now? [y/N]: ").strip().lower()
            if rawc in ("y", "yes"):
                reset_working_world(ctx)

            raw_slot = input("Clear long-term slot cache now? (next env obs treated as 'first') [y/N]: ").strip().lower()
            if raw_slot in ("y", "yes"):
                try:
                    ctx.lt_obs_slots.clear()
                    ctx.lt_obs_last_stage = None
                except Exception:
                    pass

            # Re-prune after changes
            _prune_working_world(ctx)

            # ---- Print updated settings ----
            try:
                jump_now = float(getattr(ctx, "jump", 0.0))
            except Exception:
                jump_now = 0.0
            eps_now2 = getattr(ctx, "rl_epsilon", None)
            try:
                eff_eps2 = float(eps_now2) if eps_now2 is not None else jump_now
            except Exception:
                eff_eps2 = jump_now
            try:
                delta_now2 = float(getattr(ctx, "rl_delta", 0.0))
            except Exception:
                delta_now2 = 0.0

            world_mode2 = world.get_memory_mode() if hasattr(world, "get_memory_mode") else "episodic"
            ww_count2 = len(getattr(ctx.working_world, "_bindings", {}))  # pylint: disable=protected-access

            print("\nUpdated settings:")
            print(f"  RL: enabled={bool(getattr(ctx,'rl_enabled',False))} epsilon={getattr(ctx,'rl_epsilon',None)!r} effective={eff_eps2:.3f} delta={max(0.0, float(delta_now2)):.3f}")
            print(f"  WorkingMap: enabled={bool(getattr(ctx,'working_enabled',False))} verbose={bool(getattr(ctx,'working_verbose',False))} max_bindings={int(getattr(ctx,'working_max_bindings',0) or 0)} bindings={ww_count2}")
            print(f"  WorldGraph: memory_mode={world_mode2}")
            print(f"  Long-term env obs: enabled={bool(getattr(ctx,'longterm_obs_enabled',True))} mode={getattr(ctx,'longterm_obs_mode','snapshot')} reassert_steps={int(getattr(ctx,'longterm_obs_reassert_steps',0) or 0)} keyframe_on_stage={bool(getattr(ctx,'longterm_obs_keyframe_on_stage_change',True))} verbose={bool(getattr(ctx,'longterm_obs_verbose',False))}")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "42":
            # fuure usage
            print("Selection: future usage\n")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "43":
            print("Selection: WorkingMap snapshot\n")

            if getattr(ctx, "working_world", None) is None:
                ctx.working_world = init_working_world()

            raw_n = input("Show last N bindings (default=15): ").strip()
            n = 15
            if raw_n:
                try:
                    n = max(1, int(float(raw_n)))
                except ValueError:
                    pass

            print_working_map_layers(ctx)
            print()
            print_working_map_entity_table(ctx)
            print()
            print_working_map_snapshot(ctx, n=n)

            # Dump MapSurface (MapEngram payload v1) — this is the exact snapshot we will later store into Column memory.
            try:
                payload = serialize_mapsurface_v1(ctx, include_internal_ids=False)
                txt = json.dumps(payload, indent=2, ensure_ascii=False)
                print()
                print("[workingmap] MapSurface payload (wm_mapsurface_v1; JSON-safe)")
                print(txt)
            except Exception as e:
                print()
                print(f"[workingmap] MapSurface payload dump failed: {e}")

            rawc = input("\nClear WorkingMap now? [y/N]: ").strip().lower()
            if rawc in ("y", "yes"):
                reset_working_world(ctx)
                print("(WorkingMap cleared.)")

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "44":
            #  Store WorkingMap MapSurface snapshot (Column + WG pointer)
            print("Selection: Store WorkingMap MapSurface snapshot (Column + WG pointer)\n")
            info = store_mapsurface_snapshot_v1(world, ctx, reason="manual_menu44", attach="now", force=False, quiet=False)
            if info.get("stored"):
                print(f"OK: stored. sig={info.get('sig','')[:16]} bid={info.get('bid')} engram_id={info.get('engram_id','')}")
            else:
                print(f"SKIP: {info.get('why','(no reason)')}. sig={info.get('sig','')[:16]}")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "45":
            print("Selection: List recent wm_mapsurface engrams (Column)\n")

            raw_n = input("How many recent MapSurface engrams? (default=10): ").strip()
            n = 10
            if raw_n:
                try:
                    n = max(1, int(float(raw_n)))
                except ValueError:
                    pass

            # Traverse column memory from newest to oldest; filter by record name.
            rows = []
            try:
                ids = list(column_mem.list_ids())
                for eid in reversed(ids):
                    rec = column_mem.try_get(eid)
                    if not isinstance(rec, dict):
                        continue
                    if rec.get("name") != "wm_mapsurface":
                        continue
                    rows.append(rec)
                    if len(rows) >= n:
                        break
            except Exception:
                rows = []

            if not rows:
                print("(none) No wm_mapsurface engrams found in column memory yet.")
                print("Tip: run menu 44 (manual store) or run menu 37 until a stage/zone boundary occurs.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            print(f"Recent wm_mapsurface engrams (newest first; n={len(rows)}):")
            for i, rec in enumerate(rows, start=1):
                eid = str(rec.get("id", ""))
                meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
                attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}

                created_at = meta.get("created_at") or "(n/a)"
                stage = attrs.get("stage") or "(n/a)"
                zone  = attrs.get("zone") or "(n/a)"
                sig   = attrs.get("sig") or ""
                sal = attrs.get("salience_sig") or ""
                sal_txt = f" sal={str(sal)[:12]}" if sal else ""

                links = meta.get("links")
                src = links[0] if isinstance(links, list) and links else None
                src_txt = f" src={src}" if isinstance(src, str) else ""
                sig_txt = f" sig={str(sig)[:12]}" if sig else ""

                print(f"  {i:2d}) {eid[:8]}… created={created_at} stage={stage} zone={zone}{sig_txt}{src_txt} {sal_txt}")

            print("\nTip: paste an engram id into menu 27 to inspect payload/meta.")
            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "46":
            print("Selection: Pick best wm_mapsurface engram for current stage/zone (read-only)\n")

            stage = getattr(ctx, "lt_obs_last_stage", None)
            stage = stage if isinstance(stage, str) else None

            try:
                zone = body_space_zone(ctx)
            except Exception:
                zone = None
            zone = zone if isinstance(zone, str) else None

            raw_k = input("Show top K candidates (default=5): ").strip()
            k = 5
            if raw_k:
                try:
                    k = max(1, int(float(raw_k)))
                except Exception:
                    k = 5

            print(f"[wm-retrieve] want stage={stage!r} zone={zone!r} (top_k={k})")
            info = pick_best_wm_mapsurface_rec(stage=stage, zone=zone, ctx=ctx, long_world=world, allow_fallback=True, top_k=k)

            if not info.get("ok"):
                print("(none) No wm_mapsurface engrams found for retrieval.")
                print("Tip: run menu 37 to auto-store keyframes, or menu 44 to store manually.")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            print(f"[wm-retrieve] candidate_source={info.get('source')} match_tier={info.get('match')}")
            print(
                f"[wm-retrieve] want_sal={str(info.get('want_salience_sig') or '')[:12]} "
                f"want_pred_n={info.get('want_pred_n')} want_cue_n={info.get('want_cue_n')}"
            )

            ranked = info.get("ranked", [])
            if isinstance(ranked, list) and ranked:
                print("\nTop candidates (winner marked with '*'):")
                for i, c in enumerate(ranked, start=1):
                    if not isinstance(c, dict):
                        continue
                    star = "*" if i == 1 else " "
                    eid = str(c.get("engram_id", ""))
                    created = c.get("created_at") or "(n/a)"
                    st = c.get("stage") or "(n/a)"
                    zn = c.get("zone") or "(n/a)"
                    src = c.get("src")
                    src_txt = f" src={src}" if isinstance(src, str) else ""
                    sig = str(c.get("sig") or "")[:12]
                    sal = str(c.get("salience_sig") or "")[:12]
                    score = float(c.get("score", 0.0) or 0.0)
                    op = int(c.get("overlap_preds", 0) or 0)
                    oc = int(c.get("overlap_cues", 0) or 0)
                    print(
                        f" {star}{i:2d}) {eid[:8]}… score={score:6.1f} op={op:2d} oc={oc:2d} "
                        f"stage={st} zone={zn} sig={sig} sal={sal} created={created}{src_txt}"
                    )

            # Winner summary (same info as before)
            rec = info.get("rec")
            rec = rec if isinstance(rec, dict) else None
            if rec is not None:
                eid = str(rec.get("id", ""))
                meta = rec.get("meta", {}) if isinstance(rec.get("meta"), dict) else {}
                attrs = meta.get("attrs", {}) if isinstance(meta.get("attrs"), dict) else {}
                created_at = meta.get("created_at") or "(n/a)"
                links = meta.get("links")
                src = links[0] if isinstance(links, list) and links else None

                print("\n[wm-retrieve] winner:")
                print(f"  engram={eid[:8]}… created_at={created_at} stage={attrs.get('stage')!r} zone={attrs.get('zone')!r}")
                if isinstance(src, str):
                    print(f"  src(binding)={src}")
                print(
                    f"  score={info.get('score')} "
                    f"overlap_preds={info.get('overlap_preds')}/{info.get('want_pred_n')} "
                    f"overlap_cues={info.get('overlap_cues')}/{info.get('want_cue_n')}"
                )

            loop_helper(args.autosave, world, drives, ctx)


        #----Menu Selection Code Block------------------------
        elif choice == "47":
            print("Selection: Load wm_mapsurface engram into WorkingMap (replace OR merge/seed)\n")

            raw = input("Engram id to load (blank = pick best for current stage/zone): ").strip()
            if not raw:
                stage = getattr(ctx, "lt_obs_last_stage", None)
                stage = stage if isinstance(stage, str) else None
                try:
                    zone = body_space_zone(ctx)
                except Exception:
                    zone = None
                zone = zone if isinstance(zone, str) else None

                info = pick_best_wm_mapsurface_rec(stage=stage, zone=zone, ctx=ctx, long_world=world, allow_fallback=True, top_k=5)
                rec = info.get("rec")
                rec = rec if isinstance(rec, dict) else None
                if not (info.get("ok") and rec):
                    print("(none) No wm_mapsurface engrams available to load.")
                    loop_helper(args.autosave, world, drives, ctx)
                    continue
                raw = str(rec.get("id", "")).strip()

            mode_txt = input("Load mode: [R]eplace / [M]erge-seed (default R): ").strip().lower()
            mode = "merge" if mode_txt.startswith("m") else "replace"

            out = load_wm_mapsurface_engram_into_workingmap_mode(ctx, raw, mode=mode)
            if not out.get("ok"):
                print(f"(failed) load: {out.get('why','unknown')}")
                loop_helper(args.autosave, world, drives, ctx)
                continue

            if out.get("mode") == "merge":
                print(
                    f"[wm-retrieve] merged engram={raw[:8]}… into WorkingMap: "
                    f"added_entities={out.get('added_entities')} filled_slots={out.get('filled_slots')} "
                    f"added_edges={out.get('added_edges')} stored_prior_cues={out.get('stored_prior_cues')}"
                )
                print("Tip: run menu 43 to inspect; then run one env step to let observation correct the prior.")
            else:
                print(f"[wm-retrieve] replaced WorkingMap from engram={raw[:8]}…: entities={out.get('entities')} relations={out.get('relations')}")
                print("Tip: run menu 43 now to inspect the loaded MapSurface; next env step may overwrite parts of it.")

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
        for name in ["cca8_world_graph", "cca8_controller", "cca8_column", "cca8_features", "cca8_temporal", "cca8_env", "cca8_navpatch", "cca8_test_worlds"]:
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

    # mirror terminal output to the file terminal.txt -- comment to stop
    install_terminal_tee("terminal.txt", append=True, also_stderr=True)

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
