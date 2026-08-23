#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Interactive session-configuration and retired-control-panel guidance.

Purpose
-------
This module owns two Main Menu flows that do not belong in the composition
root:

- Menu 40, which edits the starting drives, developmental age, observation
  masking, and bounded WorkingMap-to-Column auto-retrieval settings;
- Menu 41, which is now a reference-only explanation of the hardwired memory
  pipeline and its historical experimental knobs.

The functions mutate only the explicit ``drives`` and ``ctx`` objects supplied
by the runner. They do not import :mod:`cca8_run`, construct cognitive state,
or execute a policy.
"""

from __future__ import annotations

# The interactive settings flow is deliberately defensive so a malformed
# development value cannot terminate the CCA8 session.
# pylint: disable=broad-exception-caught
# pylint: disable=too-many-statements

from typing import Any

__version__ = "0.1.0"

__all__ = [
    "configure_episode_starting_state_v1",
    "retired_memory_pipeline_guide_text_v1",
    "show_retired_memory_pipeline_guide_v1",
    "__version__",
]


def _safe_float(value: Any, default: float = 0.0) -> float:
    """Return one finite-enough development setting as a float."""
    try:
        return float(value)
    except (TypeError, ValueError):
        return float(default)


def _prompt_float(
    label: str,
    current: float,
    low: float | None = None,
    high: float | None = None,
) -> float:
    """Prompt for a float, preserving the current value on blank or error."""
    try:
        raw = input(f"{label} (current={current:.2f}): ").strip()
    except Exception:
        return current
    if not raw:
        return current

    try:
        value = float(raw)
    except (TypeError, ValueError):
        print(f"  [warn] Could not parse {label!r}; keeping previous value.")
        return current

    if low is not None and value < low:
        print(f"  [warn] {label} below minimum {low:.2f}; clamping.")
        value = low
    if high is not None and value > high:
        print(f"  [warn] {label} above maximum {high:.2f}; clamping.")
        value = high
    return value


def configure_episode_starting_state_v1(drives: Any, ctx: Any) -> None:
    """Interactively update explicit episode-starting and masking settings.

    The operation preserves the historical Menu 40 behavior. Drive values are
    clamped to ``[0.0, 1.0]``; developmental age is clamped to zero or above;
    observation-mask probability is clamped to ``[0.0, 1.0]``. Blank numeric
    responses keep the current value. The verbose-mask prompt intentionally
    retains its historical blank-means-toggle behavior.
    """
    print("Selection: Configure episode starting state (drives + age_days)\n")
    print("(For development work, it is useful to adjust starting state attributes and see the")
    print("  effect on program behavior.)\n")

    current_hunger = _safe_float(getattr(drives, "hunger", 0.0))
    current_fatigue = _safe_float(getattr(drives, "fatigue", 0.0))
    current_warmth = _safe_float(getattr(drives, "warmth", 0.0))
    current_age = _safe_float(getattr(ctx, "age_days", 0.0) or 0.0)

    current_mask_probability = _safe_float(getattr(ctx, "obs_mask_prob", 0.0) or 0.0)
    current_mask_seed = getattr(ctx, "obs_mask_seed", None)
    mask_mode = "seeded" if current_mask_seed is not None else "global"
    current_mask_verbose = bool(getattr(ctx, "obs_mask_verbose", True))

    print()
    print(
        "Partial observability (obs masking): "
        f"obs_mask_prob={current_mask_probability:.2f} mode={mask_mode} "
        f"obs_mask_seed={current_mask_seed!r} verbose={current_mask_verbose}"
    )
    print("  obs_mask_prob:")
    print("    0.00 = fully observed (default)")
    print("    0.10–0.30 = mild partial observability (good starting range)")
    print("  obs_mask_seed:")
    print("    None = stochastic masking (uses global RNG)")
    print("    int  = reproducible masking (seeded per env step; independent of RL randomness)")
    print("  Protected (never dropped): posture:* , hazard:cliff:* , proximity:shelter:*")

    raw = input("Set obs_mask_prob in [0..1] (blank=keep current): ").strip()
    if raw:
        try:
            ctx.obs_mask_prob = max(0.0, min(1.0, float(raw)))
            ctx.obs_mask_last_cfg_sig = None
            print(f"(updated) obs_mask_prob={ctx.obs_mask_prob:.2f}")
        except (TypeError, ValueError):
            print("(warn) invalid obs_mask_prob; keeping current value.")

    raw = input("Set obs_mask_seed (blank=keep; 'none'/'off'=disable; int=enable): ").strip().lower()
    if raw:
        if raw in ("none", "off", "disable", "disabled"):
            ctx.obs_mask_seed = None
            ctx.obs_mask_last_cfg_sig = None
            print("(updated) obs_mask_seed=None (stochastic/global RNG)")
        else:
            try:
                ctx.obs_mask_seed = int(float(raw))
                ctx.obs_mask_last_cfg_sig = None
                print(f"(updated) obs_mask_seed={ctx.obs_mask_seed} (reproducible)")
            except (TypeError, ValueError):
                print("(warn) invalid obs_mask_seed; keeping current value.")

    raw = input("obs-mask verbose logs? [Enter=toggle | on | off]: ").strip().lower()
    if raw in ("on", "true", "1", "yes", "y"):
        ctx.obs_mask_verbose = True
    elif raw in ("off", "false", "0", "no", "n"):
        ctx.obs_mask_verbose = False
    elif raw == "":
        ctx.obs_mask_verbose = not bool(getattr(ctx, "obs_mask_verbose", True))
    print(f"(now) obs_mask_verbose={bool(getattr(ctx, 'obs_mask_verbose', True))}")

    auto_retrieve_enabled = bool(getattr(ctx, "wm_mapsurface_autoretrieve_enabled", False))
    auto_retrieve_mode = str(getattr(ctx, "wm_mapsurface_autoretrieve_mode", "merge") or "merge").strip().lower()
    if auto_retrieve_mode == "r":
        auto_retrieve_mode = "replace"
    if auto_retrieve_mode not in ("merge", "replace"):
        auto_retrieve_mode = "merge"

    print()
    print(f"WM<->Column auto-retrieve (keyframes): enabled={auto_retrieve_enabled} mode={auto_retrieve_mode}")
    print("  merge   = conservative prior fill (no overwrite; no cue leakage)")
    print("  replace = rebuild MapSurface from engram snapshot (debug/strong prior)")

    raw = input("Set auto-retrieve enabled? [Enter=keep | t=toggle | on | off]: ").strip().lower()
    if raw in ("t", "toggle"):
        auto_retrieve_enabled = not auto_retrieve_enabled
    elif raw in ("on", "true", "1", "yes", "y"):
        auto_retrieve_enabled = True
    elif raw in ("off", "false", "0", "no", "n", "disable", "disabled"):
        auto_retrieve_enabled = False
    elif raw:
        print("(warn) invalid input; keeping current enabled setting.")
    ctx.wm_mapsurface_autoretrieve_enabled = auto_retrieve_enabled

    raw = input("Set auto-retrieve mode? [Enter=keep | t=toggle | merge | replace]: ").strip().lower()
    if raw in ("t", "toggle"):
        auto_retrieve_mode = "replace" if auto_retrieve_mode == "merge" else "merge"
    elif raw in ("merge", "m"):
        auto_retrieve_mode = "merge"
    elif raw in ("replace", "r"):
        auto_retrieve_mode = "replace"
    elif raw:
        print("(warn) invalid mode; keeping current mode.")
    ctx.wm_mapsurface_autoretrieve_mode = auto_retrieve_mode
    print(
        f"(now) wm_mapsurface_autoretrieve_enabled={auto_retrieve_enabled} "
        f"wm_mapsurface_autoretrieve_mode={auto_retrieve_mode}"
    )

    print("Current values:")
    print(f"  hunger   = {current_hunger:.2f}")
    print(f"  fatigue  = {current_fatigue:.2f}")
    print(f"  warmth   = {current_warmth:.2f}")
    print(f"  age_days = {current_age:.2f}")
    print("\nEnter new values or press Enter to keep the current value.")
    print("Drives are clamped to the range [0.0, 1.0]. age_days must be ≥ 0.\n")

    new_hunger = _prompt_float("hunger", current_hunger, 0.0, 1.0)
    new_fatigue = _prompt_float("fatigue", current_fatigue, 0.0, 1.0)
    new_warmth = _prompt_float("warmth", current_warmth, 0.0, 1.0)

    drives.hunger = new_hunger
    drives.fatigue = new_fatigue
    drives.warmth = new_warmth

    try:
        raw_age = input(f"age_days (current={current_age:.2f}): ").strip()
    except Exception:
        raw_age = ""
    if raw_age:
        try:
            new_age = float(raw_age)
            if new_age < 0.0:
                print("  [warn] age_days below 0.0; clamping to 0.0.")
                new_age = 0.0
            ctx.age_days = new_age
        except (TypeError, ValueError):
            print("  [warn] Could not parse age_days; keeping previous value.")
    else:
        ctx.age_days = current_age

    print("\n[config] Updated episode starting state:")
    print(
        f"  hunger={getattr(drives, 'hunger', new_hunger):.2f} "
        f"fatigue={getattr(drives, 'fatigue', new_fatigue):.2f} "
        f"warmth={getattr(drives, 'warmth', new_warmth):.2f} "
        f"age_days={getattr(ctx, 'age_days', current_age):.2f}"
    )


def retired_memory_pipeline_guide_text_v1() -> str:
    """Return the reference-only Menu 41 memory/RL control-panel guide."""
    return r'''
[guide] This menu is the main "knobs and buttons" reference card for CCA8 experiments.

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
  Exploration probability in [0..1]. If None, exploration is disabled (epsilon=0).

rl_delta (float)
  Defines the deficit near-tie band within which q is allowed to decide among candidates.

(For full examples and the authoritative contract, see README.md: keyframes, WM<->Column pipeline, and cognitive cycles.)
'''.strip("\n")


def show_retired_memory_pipeline_guide_v1() -> None:
    """Print Menu 41's reference card without exposing unreachable controls."""
    print("Menu 41 retired. Memory pipeline is hardwired (Phase VII daily-driver).")
    print(retired_memory_pipeline_guide_text_v1())
    print("\nSelection: Control Panel (RL policy selection + memory knobs)\n")
