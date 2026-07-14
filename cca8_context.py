# -*- coding: utf-8 -*-
"""Runtime-context data structures for the CCA8 simulation.

This module owns the mutable :class:`Ctx` object passed through the runner,
controller, environment, memory, and diagnostic paths. It also owns the two
small dataclasses used directly by ``Ctx`` default factories and field types:
``CreativeCandidate`` and ``ExperimentProtocolConfig``.

The extraction is intentionally structural. Field names, ordering, defaults,
and method behavior are preserved from ``cca8_run.py`` so existing snapshots,
tests, imports, and runtime code continue to behave as before.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Optional

import cca8_world_graph
from cca8_navpatch import SurfaceGridV1
from cca8_temporal import TemporalContext

__version__ = "0.1.0"
__all__ = ["CreativeCandidate", "ExperimentProtocolConfig", "Ctx", "__version__"]


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
class ExperimentProtocolConfig:
    """Mutable experiment protocol settings stored on ctx.

    This is intentionally separate from everyday simulation settings. When the
    user never enters the experiments menu, the ordinary CCA8 workflow should
    behave exactly as before.
    """
    protocol_version: str = "exp_protocol_v1"
    benchmark_id: str = "newborn_long_horizon"
    condition_ids: list[str] = field(default_factory=lambda: ["A", "B", "C", "D", "E"])
    seed_list: list[int] = field(default_factory=lambda: [11, 23, 37, 41, 53])
    episodes_per_seed: int = 1
    max_cycles: int = 60
    obs_mask_prob: float = 0.50    #independent drop probability for each non-protected observation token
    # Newborn long-horizon stress profile.
    # baseline       : existing task, with ordinary obs_mask only
    # blackout_short : milestone-locked local-state blackout, usually 2-3 cycles
    # blackout_long  : longer local-state blackout, usually 5+ cycles
    # route_loss     : memory-critical external route/task-state loss, usually 8+ cycles
    newborn_stress_profile: str = "baseline"
    newborn_blackout_length: int = 3
    action_vocab_version: str = "cca8_action_vocab_v1"
    scratch_clear_policy: str = "per_episode_reset"
    jsonl_write_cycle_records: bool = True
    jsonl_write_episode_records: bool = True
    llm_model: Optional[str] = None
    llm_adviser_ambiguity_delta: float = 0.10
    llm_adviser_max_candidates: int = 4

    # Patch-2 additions:
    # - run_label gives the user a stable human-readable tag for filenames.
    # - output_dir is where prepared JSONL files will live once execution is wired in.
    run_label: str = "--no run_label chosen--"
    output_dir: str = "testvalues"   #directory where jsonl and other result files will be written to


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

    # Formal predictive-feedback records (first NavMap prediction milestone).
    # These are JSON-safe dicts built from cca8_predictive.PredictionRecord / PredictionError.
    # They do not change policy selection; they make the existing posture-only pred_err_v0 path inspectable.
    prediction_next_record: dict[str, Any] = field(default_factory=dict)
    prediction_last_error_record: dict[str, Any] = field(default_factory=dict)
    prediction_error_history: list[dict[str, Any]] = field(default_factory=list)

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

    # Sequential / error unit (CCA7 cerebellum-inspired) — temporal deltas + prediction errors (stub)
    # -----------------------------------------------------------------------------------------
    # Diagnostic-first: tracks short windows of sensory change over time. Does NOT change policy selection yet.
    seqerr_enabled: bool = True
    seqerr_verbose: bool = False
    seqerr_window: int = 4

    # Optional attention hook (predictive-coding seam). OFF by default to keep behavior unchanged.
    seqerr_attention_enabled: bool = False
    seqerr_attention_threshold: float = 0.25
    seqerr_attention_request: Optional[str] = None

    # Latest computed bundle + short ring buffer (JSON-safe).
    seqerr_last: dict[str, Any] = field(default_factory=dict)
    seqerr_history: list[dict[str, Any]] = field(default_factory=list)
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
    # Dirty-cache v2 also watches SELF local-window shift, zoom, focus, and hazard evidence.
    wm_zoom_level: int = 0
    wm_surfacegrid_last_scene_fingerprint: dict[str, Any] = field(default_factory=dict)
    wm_surfacegrid_dirty: bool = True
    wm_surfacegrid_dirty_reasons: list[str] = field(default_factory=list)
    wm_surfacegrid_compose_ms: float = 0.0
    wm_surfacegrid_last_ascii: Optional[str] = None
    # Last ASCII map actually printed to the terminal.
    # This is separate from wm_surfacegrid_last_ascii, which is the current
    # composed map snapshot for this tick. Keeping both lets the footer say
    # "unchanged" without re-dumping the full map every cycle.
    wm_surfacegrid_last_printed_ascii: Optional[str] = None
    # Normalized framed block last emitted to the terminal.
    # I keep this separate from wm_surfacegrid_last_printed_ascii because the raw
    # ascii snapshot can vary for non-visual reasons while the human-visible framed
    # terminal block is unchanged.
    wm_surfacegrid_last_printed_block: Optional[str] = None
    # SurfaceGrid printing controls (terminal UX)
    wm_surfacegrid_ascii_enabled: bool = True
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
    # --- WM.NavSummary (Phase X P1.4) -----------------------------------------------
    # Small cached numeric summaries derived from WM.SurfaceGrid.
    # This lets later policy refactors read one stable dict instead of proliferating
    # more pred:* tags for every topological fact.
    wm_navsummary_enabled: bool = True
    wm_navsummary_local_radius: int = 2
    wm_navsummary: dict[str, Any] = field(default_factory=dict)

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

    # --- WM demo knobs (debug-only; default OFF) ---------------------------------------
    # If wm_demo_force_ambiguity_steps > 0, NavPatch matching will force an "ambiguous" commit
    # for wm_demo_force_ambiguity_entity for that many env steps, then auto-decrement to 0.
    #wm_demo_force_ambiguity_steps: int = 0
    wm_demo_force_ambiguity_steps: int = 12  #to force ambiguity for testing
    wm_demo_force_ambiguity_entity: str = "cliff"
    wm_demo_force_ambiguity_margin: float = 0.0

    # MapSurface: stateful "workspace" graph (separate WorldGraph instance)
    # ---------------------------------------------------------------
    # WorkingMap is episodic (write-everything). MapSurface is intended to be
    # stateful: a small set of entity nodes (starting with SELF) whose pred:* tags
    # are overwritten each tick by slot-family ("belief register"), similar in spirit
    # to CCA7's heavy usage of feedback loops and map-like working memory.
    map_surface_world: Optional[cca8_world_graph.WorldGraph] = None
    map_surface_ids: dict[str, str] = field(default_factory=dict)

    # SurfaceGrid: last local spatial / affordance surface (debug + future planning)
    # ---------------------------------------------------------------------------
    # This is populated from EnvObservation.surface_grid (environment-side perception).
    # It is a JSON-safe dict representation today, but can become a real grid/costmap
    # object once we plug in a robot backend.
    surface_grid: dict[str, Any] = field(default_factory=dict)

    # Predictive coding / attention (top-down modulation)
    # ---------------------------------------------------
    # Minimal v1:
    #   - predict "world stays the same" by default (prev slots == predictions)
    #   - compute mismatch slots as a prediction error signal
    #   - optionally request attention (percept_focus) on the most surprising slot
    predcode_enabled: bool = True
    predcode_prev_slots: dict[str, str] = field(default_factory=dict)
    predcode_last_error: dict[str, Any] = field(default_factory=dict)

    # A simple attention request used by PerceptionAdapter / robot backends.
    # Examples: "mom", "proximity:mom", "hazard:cliff".
    percept_focus: Optional[str] = None

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

    # Map-switch event logging (P3.11)
    wm_mapswitch_last_events: list[dict[str, Any]] = field(default_factory=list)
    wm_mapswitch_history: list[dict[str, Any]] = field(default_factory=list)
    wm_mapswitch_history_limit: int = 50

    # goat_foraging_04 contextual map-switch bookkeeping (episode-local)
    wm_goat04_seeded_contexts: set[str] = field(default_factory=set)
    wm_goat04_seed_engram_by_context: dict[str, str] = field(default_factory=dict)
    # newborn_long_horizon benchmark seed snapshots (episode-local)
    wm_newborn_b2_seeded_labels: set[str] = field(default_factory=set)
    wm_newborn_b2_seed_engram_by_label: dict[str, str] = field(default_factory=dict)

    # goat04 retrieval → control bridge
    # --------------------------------
    # B1 is supposed to test whether recovered context changes downstream behavior.
    # The current retrieval machinery can recover a fox/hawk context, but without a
    # short-lived control bridge the controller often keeps falling through to the
    # permissive follow_mom fallback. These fields hold a tiny, explicit, expiring
    # hint derived from retrieved context only (not hidden oracle truth).
    goat04_control_context: Optional[str] = None
    goat04_control_source: Optional[str] = None
    goat04_control_until_step: int = -1


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

    # NavMap read-only diagnostics (scene_body candidate pool; no policy/WorldGraph/Column effects)
    navmap_scene_body_candidates_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_scene_body_max_candidates_v1: int = 25
    navmap_last_observation_update_v1: Optional[dict[str, Any]] = None
    navmap_observation_update_history_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_observation_update_history_limit_v1: int = 25
    navmap_last_payload_v1: Optional[dict[str, Any]] = None
    navmap_pending_action_v1: Optional[str] = None
    navmap_pending_reward_v1: float = 0.0
    navmap_last_transition_v1: Optional[dict[str, Any]] = None
    navmap_transition_history_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_transition_history_limit_v1: int = 25
    navmap_last_policy_outcome_v1: Optional[dict[str, Any]] = None
    navmap_policy_outcome_history_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_policy_outcome_history_limit_v1: int = 25
    navmap_policy_outcome_index_v1: dict[str, dict[str, Any]] = field(default_factory=dict)
    navmap_policy_outcome_index_limit_v1: int = 100
    navmap_last_policy_outcome_index_row_v1: Optional[dict[str, Any]] = None
    navmap_last_expected_current_payload_v1: Optional[dict[str, Any]] = None
    navmap_last_expected_current_comparison_v1: Optional[dict[str, Any]] = None
    navmap_expected_current_history_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_expected_current_history_limit_v1: int = 25
    navmap_expected_current_context_shift_threshold_v1: int = 3
    navmap_last_accepted_current_v1: Optional[dict[str, Any]] = None
    navmap_accepted_current_history_v1: list[dict[str, Any]] = field(default_factory=list)
    navmap_accepted_current_history_limit_v1: int = 25

    # Working NavMap surface bridge (diagnostic-only; not a policy/WorldGraph/Column writer)
    working_navmap_surface_v1: Optional[dict[str, Any]] = None
    working_navmap_surface_history_v1: list[dict[str, Any]] = field(default_factory=list)
    working_navmap_surface_history_limit_v1: int = 25

    # Per-cycle JSON log record (Phase X): minimal, replayable trace contract
    # ---------------------------------------------------------------------
    # When enabled, each closed-loop env step appends a JSON-safe dict record to ctx.cycle_json_records,
    # and optionally writes it to ctx.cycle_json_path as JSONL (one record per line).
    cycle_json_enabled: bool = False
    cycle_json_path: Optional[str] = None
    cycle_json_max_records: int = 2000
    cycle_json_records: list[dict[str, Any]] = field(default_factory=list)

    # Experiment protocol scaffolding (long-horizon paper)
    # --------------------------------------------------------------
    # These settings are additive and should not affect normal simulation when the
    # experiments menu is never used. Later patches will read this config to run
    # controlled A/B/C/D/E batches from the main runner.
    experiment_cfg: ExperimentProtocolConfig = field(default_factory=ExperimentProtocolConfig)
    experiment_last_summary: dict[str, Any] = field(default_factory=dict)
    # Policy-selection debug trace for benchmark regression diagnosis.
    # Diagnostic only: does not affect policy triggers, filtering, scoring, or execution.
    experiment_policy_debug_last: dict[str, Any] = field(default_factory=dict)
    experiment_policy_debug_events: list[dict[str, Any]] = field(default_factory=list)
    experiment_active_condition_id: Optional[str] = None
    experiment_active_condition_label: Optional[str] = None
    experiment_llm_adviser_enabled: bool = False
    experiment_llm_role: str = "none"
    experiment_llm_model_name: Optional[str] = None
    experiment_llm_call_count: int = 0
    experiment_llm_latency_ms_total: float = 0.0
    experiment_last_llm_advice_summary: dict[str, Any] = field(default_factory=dict)
    experiment_llm_first_error_printed: bool = False
    experiment_llm_first_error_summary: Optional[str] = None

    # Newborn B2 benchmark hardening
    # ------------------------------
    # When True, the newborn bridge gates must rely on fresh current-state memory
    # (BodyMap / committed current state) rather than reconstructing "truth now"
    # from older long-term episode predicates near NOW.
    #
    # This is benchmark-only. It should be enabled by the Menu 49 sandbox for
    # newborn_long_horizon, not for ordinary interactive runs.
    experiment_newborn_require_current_state: bool = False
    # When True, the newborn benchmark is allowed to bridge across a blackout only
    # if a recent wm_mapsurface retrieval/apply event succeeded.
    #
    # This makes "resume the long-horizon task after missing current evidence"
    # depend on episodic readback rather than on stage-local bridge logic alone.
    experiment_newborn_require_resume_memory: bool = False
    # Short-lived retrieved-state bridge for newborn B2.
    # -------------------------------------------------
    # A newborn retrieval can succeed at the WorkingMap/Column seam but still fail
    # to change control if the gates only read fresh BodyMap values. These fields
    # hold a tiny decoded hint from the most recent retrieved wm_mapsurface engram
    # so strict benchmark gates can consult it during brief blackout windows.
    experiment_newborn_retrieved_hint: dict[str, Any] = field(default_factory=dict)
    experiment_newborn_retrieved_hint_until_step: int = -1
    experiment_newborn_retrieved_hint_source: Optional[str] = None

    # Retrieved-hint instrumentation.
    # "used_step_count" is a conservative control-use proxy: it counts a cycle when
    # the active retrieved hint is returned to a newborn bridge/gate helper.
    experiment_newborn_retrieved_hint_set_count: int = 0
    experiment_newborn_retrieved_hint_active_step_count: int = 0
    experiment_newborn_retrieved_hint_used_step_count: int = 0
    experiment_newborn_retrieved_hint_last_active_step_counted: int = -1
    experiment_newborn_retrieved_hint_last_used_step_counted: int = -1
    experiment_newborn_retrieved_hint_events: list[dict[str, Any]] = field(default_factory=list)

    # Newborn benchmark stressor runtime state.
    # These fields are episode-local and are reset by experiment_configure_benchmark_runtime_v1.
    experiment_newborn_blackout_start_step: int = -1
    experiment_newborn_blackout_until_step: int = -1
    experiment_newborn_blackout_reason: Optional[str] = None

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
