#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Policy gates, newborn control bridges, EFE diagnostics, and policy runtime for CCA8.

Purpose
-------
This module owns the runner-facing policy-selection subsystem that was
historically embedded in ``cca8_run.py``. It provides:

- BodyMap-, WorkingMap-, and NavSummary-aware policy gates
- newborn survival and conflicted-repair control bridges
- diagnostic expected-free-energy-style scoring
- the declarative ``PolicyGate`` catalog
- ``PolicyRuntime`` trigger filtering, safety filtering, tie-breaking, and execution
- the WorkingMap Creative candidate-scoring diagnostic

Dependency boundary
-------------------
The module never imports :mod:`cca8_run`. The runner supplies an explicit
:class:`PolicyRuntimeHooks` bundle whose callables resolve the runner's current
compatibility surface at call time. This preserves existing monkeypatch seams
without creating a circular import.

Behavior boundary
-----------------
Phase 3D changes the bounded StandUp trigger authority supplied through
``PolicyRuntimeHooks``. Phase 4F similarly lets exact current maternal WNM/NavMap
evidence control one FollowMom applicability domain while preserving protected
legacy false results, named true compatibility forces, and complete legacy
fallback. Phase 5 lets the post-latch gate consult current map-linked feeding
evidence while leaving SeekNipple/Suckle selection authority, gate order, global
tie-breaking, controller execution, and protected safety unchanged.
"""

from __future__ import annotations

# The extracted controller path intentionally preserves the defensive style of
# the historical runner implementation.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-nested-blocks
# pylint: disable=too-many-statements

import random
from dataclasses import dataclass
from typing import Any, Callable, List, Optional

from cca8_context import CreativeCandidate, Ctx
from cca8_controller import Drives, FATIGUE_HIGH, HUNGER_HIGH
from cca8_terrain import terrain_motion_veto_v1, terrain_safe_to_rest_v1
from cca8_feeding import (
    feeding_latch_evidence_v1,
    feeding_milk_evidence_v1,
    feeding_summary_v1,
)


__version__ = "0.6.1"


@dataclass(frozen=True, slots=True)
class PolicyRuntimeHooks:  # pylint: disable=too-few-public-methods
    """Runner callbacks required by the extracted policy subsystem.

    Every field is intentionally callable. The runner installs small lambdas
    rather than frozen function objects, so replacing a historical runner name
    during a focused test still changes the behavior seen by this module.
    """

    bodymap_is_stale: Callable[..., Any]
    body_posture: Callable[..., Any]
    body_mom_distance: Callable[..., Any]
    body_nipple_state: Callable[..., Any]
    body_shelter_distance: Callable[..., Any]
    body_cliff_distance: Callable[..., Any]
    body_space_zone: Callable[..., Any]
    fallen_near_now: Callable[..., Any]
    has_pred_near_now: Callable[..., Any]
    any_cue_tokens_present: Callable[..., Any]
    present_cue_bids: Callable[..., Any]
    newborn_active_retrieved_hint: Callable[..., Any]
    newborn_stress_profile_from_ctx: Callable[..., Any]
    goat04_context_hint_active: Callable[..., Any]
    experiment_policy_debug_record: Callable[..., Any]
    experiment_llm_candidate_rows: Callable[..., Any]
    run_experiment_llm_adviser_once: Callable[..., Any]
    experiment_metric_text: Callable[..., Any]
    choose_contextual_base: Callable[..., Any]
    compute_foa: Callable[..., Any]
    candidate_anchors: Callable[..., Any]
    action_center_step: Callable[..., Any]
    skill_q: Callable[..., Any]
    update_skill: Callable[..., Any]
    register_policy_scratch_chain: Callable[..., Any]
    policy_primitives: Callable[..., Any]
    standup_guarded_trigger: Callable[..., Any]
    standup_guarded_safety_active: Callable[..., Any]
    standup_guarded_explain: Callable[..., Any]
    followmom_authority_trigger: Callable[..., Any]
    followmom_authority_explain: Callable[..., Any]
    followmom_authority_legacy_bridge_allowed: Callable[..., Any]


_POLICY_RUNTIME_HOOKS: PolicyRuntimeHooks | None = None


def configure_policy_runtime_hooks(hooks: PolicyRuntimeHooks) -> None:
    """Install the dependency bundle used by policy helpers and ``PolicyRuntime``."""
    global _POLICY_RUNTIME_HOOKS  # pylint: disable=global-statement
    if not isinstance(hooks, PolicyRuntimeHooks):
        raise TypeError("hooks must be a PolicyRuntimeHooks instance")
    _POLICY_RUNTIME_HOOKS = hooks


def _policy_runtime_hooks() -> PolicyRuntimeHooks:
    """Return the configured dependency bundle or fail with a clear message."""
    hooks = _POLICY_RUNTIME_HOOKS
    if hooks is None:
        raise RuntimeError(
            "CCA8 policy-runtime hooks are not configured. Import cca8_run or call "
            "configure_policy_runtime_hooks(...)."
        )
    return hooks


# The names below deliberately match the historical runner globals. Keeping
# these tiny delegators lets the moved algorithm remain readable and makes the
# compatibility boundary explicit in one place.
def bodymap_is_stale(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap-staleness helper."""
    return _policy_runtime_hooks().bodymap_is_stale(*args, **kwargs)


def body_posture(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap posture helper."""
    return _policy_runtime_hooks().body_posture(*args, **kwargs)


def body_mom_distance(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap mother-distance helper."""
    return _policy_runtime_hooks().body_mom_distance(*args, **kwargs)


def body_nipple_state(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap nipple-state helper."""
    return _policy_runtime_hooks().body_nipple_state(*args, **kwargs)


def body_shelter_distance(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap shelter-distance helper."""
    return _policy_runtime_hooks().body_shelter_distance(*args, **kwargs)


def body_cliff_distance(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap cliff-distance helper."""
    return _policy_runtime_hooks().body_cliff_distance(*args, **kwargs)


def body_space_zone(*args: Any, **kwargs: Any) -> Any:
    """Call the configured BodyMap spatial-zone helper."""
    return _policy_runtime_hooks().body_space_zone(*args, **kwargs)


def standup_guarded_trigger_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured Phase 3C/3D StandUp authority trigger."""
    return _policy_runtime_hooks().standup_guarded_trigger(*args, **kwargs)


def standup_guarded_safety_active_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured guarded/default map-fallen safety indicator."""
    return _policy_runtime_hooks().standup_guarded_safety_active(*args, **kwargs)


def standup_guarded_explain_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured Phase 3C/3D StandUp authority explainer."""
    return _policy_runtime_hooks().standup_guarded_explain(*args, **kwargs)


def followmom_authority_trigger_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured Phase 4E-B/4F FollowMom authority trigger."""
    return _policy_runtime_hooks().followmom_authority_trigger(*args, **kwargs)


def followmom_authority_explain_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured Phase 4E-B/4F FollowMom authority explainer."""
    return _policy_runtime_hooks().followmom_authority_explain(*args, **kwargs)


def followmom_authority_legacy_bridge_allowed_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the authority guard for the historical FollowMom force bridge."""
    return _policy_runtime_hooks().followmom_authority_legacy_bridge_allowed(*args, **kwargs)


def _fallen_near_now(*args: Any, **kwargs: Any) -> Any:
    """Call the configured fallen-near-current-state safety helper."""
    return _policy_runtime_hooks().fallen_near_now(*args, **kwargs)


def has_pred_near_now(*args: Any, **kwargs: Any) -> Any:
    """Call the configured current-neighborhood predicate query."""
    return _policy_runtime_hooks().has_pred_near_now(*args, **kwargs)


def any_cue_tokens_present(*args: Any, **kwargs: Any) -> Any:
    """Call the configured cue-presence query."""
    return _policy_runtime_hooks().any_cue_tokens_present(*args, **kwargs)


def present_cue_bids(*args: Any, **kwargs: Any) -> Any:
    """Call the configured current cue-binding query."""
    return _policy_runtime_hooks().present_cue_bids(*args, **kwargs)


def _newborn_active_retrieved_hint_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured newborn retrieved-hint reader."""
    return _policy_runtime_hooks().newborn_active_retrieved_hint(*args, **kwargs)


def _newborn_stress_profile_from_ctx_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured newborn stress-profile reader."""
    return _policy_runtime_hooks().newborn_stress_profile_from_ctx(*args, **kwargs)


def _goat04_context_hint_active_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured goat04 context-hint reader."""
    return _policy_runtime_hooks().goat04_context_hint_active(*args, **kwargs)


def _experiment_policy_debug_record_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured experiment policy-debug recorder."""
    return _policy_runtime_hooks().experiment_policy_debug_record(*args, **kwargs)


def _experiment_llm_candidate_rows_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured bounded LLM-candidate builder."""
    return _policy_runtime_hooks().experiment_llm_candidate_rows(*args, **kwargs)


def _run_experiment_llm_adviser_once_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured bounded LLM adviser."""
    return _policy_runtime_hooks().run_experiment_llm_adviser_once(*args, **kwargs)


def _experiment_metric_text_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured experiment metric formatter."""
    return _policy_runtime_hooks().experiment_metric_text(*args, **kwargs)


def choose_contextual_base(*args: Any, **kwargs: Any) -> Any:
    """Call the configured contextual write-base helper."""
    return _policy_runtime_hooks().choose_contextual_base(*args, **kwargs)


def compute_foa(*args: Any, **kwargs: Any) -> Any:
    """Call the configured focus-of-attention helper."""
    return _policy_runtime_hooks().compute_foa(*args, **kwargs)


def candidate_anchors(*args: Any, **kwargs: Any) -> Any:
    """Call the configured candidate-anchor helper."""
    return _policy_runtime_hooks().candidate_anchors(*args, **kwargs)


def action_center_step(*args: Any, **kwargs: Any) -> Any:
    """Call the configured controller Action Center."""
    return _policy_runtime_hooks().action_center_step(*args, **kwargs)


def skill_q(*args: Any, **kwargs: Any) -> Any:
    """Call the configured skill-value reader."""
    return _policy_runtime_hooks().skill_q(*args, **kwargs)


def update_skill(*args: Any, **kwargs: Any) -> Any:
    """Call the configured skill-ledger update helper."""
    return _policy_runtime_hooks().update_skill(*args, **kwargs)


def register_policy_scratch_chain_v1(*args: Any, **kwargs: Any) -> Any:
    """Call the configured WorkingMap Scratch provenance registrar."""
    return _policy_runtime_hooks().register_policy_scratch_chain(*args, **kwargs)


def policy_primitives_v1() -> Any:
    """Return the current runner-visible controller primitive catalog."""
    return _policy_runtime_hooks().policy_primitives()


def _wm_navsummary_get_v1(ctx: Ctx | None) -> dict[str, Any]:
    """Return the current cached WM.NavSummary dict, or {} when unavailable.

    Policies should prefer this helper over directly reading MapSurface slot-families.
    That keeps the gating seam stable even if we later change how NavSummary is computed.
    """
    if ctx is None:
        return {}
    ns = getattr(ctx, "wm_navsummary", None)
    return ns if isinstance(ns, dict) else {}


def _wm_navsummary_bool_v1(ctx: Ctx | None, key: str, default: bool = False) -> bool:
    """Read a boolean-like NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    if key not in ns:
        return bool(default)
    try:
        return bool(ns.get(key))
    except Exception:
        return bool(default)


def _wm_navsummary_int_v1(ctx: Ctx | None, key: str) -> int | None:
    """Read an integer NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    try:
        v = ns.get(key)
        return int(v) if isinstance(v, int) else None
    except Exception:
        return None


def _wm_navsummary_float_v1(ctx: Ctx | None, key: str) -> float | None:
    """Read a float-like NavSummary field safely."""
    ns = _wm_navsummary_get_v1(ctx)
    try:
        v = ns.get(key)
        if isinstance(v, (int, float)):
            return float(v)
    except Exception:
        return None
    return None


def _wm_navsummary_explain_bits_v1(ctx: Ctx | None) -> str:
    """Return a compact human-readable NavSummary excerpt for gate explanations."""
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return "navsummary=(none)"

    hazard_near = 1 if _wm_navsummary_bool_v1(ctx, "hazard_near", False) else 0
    traversable_near = 1 if _wm_navsummary_bool_v1(ctx, "traversable_near", False) else 0

    hazard_density = _wm_navsummary_float_v1(ctx, "hazard_density")
    hd_txt = f"{hazard_density:.2f}" if isinstance(hazard_density, float) else "n/a"

    corridors = _wm_navsummary_int_v1(ctx, "corridor_count")
    corr_txt = str(corridors) if isinstance(corridors, int) else "n/a"

    goal_dir = ns.get("goal_dir")
    goal_dir_txt = goal_dir if isinstance(goal_dir, str) and goal_dir else "(none)"

    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")
    safe_cost_txt = str(safe_cost) if isinstance(safe_cost, int) else "n/a"

    return (
        "navsummary("
        f"hazard_near={hazard_near}, "
        f"traversable_near={traversable_near}, "
        f"hazard_density={hd_txt}, "
        f"corridors={corr_txt}, "
        f"goal_dir={goal_dir_txt}, "
        f"safe_cost={safe_cost_txt})"
    )


def _wm_follow_mom_blocked_by_topology_v1(ctx: Ctx | None) -> bool:
    """Return True when fallback follow_mom should be suppressed by current topology.

    Conservative v1 rule:
      - If NavSummary is unavailable: do not block here.
      - If no traversable outlet is visible near SELF: block fallback movement.
      - If hazard is near AND no currently visible safe path to a goal exists: block fallback movement.

    This keeps follow_mom available as a simple default in easy scenes, while making it stop
    pretending to be a good generic fallback in locally hazardous or topology-poor scenes.
    """
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return False

    traversable_near = _wm_navsummary_bool_v1(ctx, "traversable_near", False)
    hazard_near = _wm_navsummary_bool_v1(ctx, "hazard_near", False)
    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")

    if not traversable_near:
        return True
    if hazard_near and safe_cost is None:
        return True
    return False


def _wm_probe_supported_by_topology_v1(ctx: Ctx | None) -> bool:
    """Return True when NavSummary says the local scene is topology-relevant enough to justify probing.

    Conservative v1 signal:
      - hazard_near, OR
      - hazard_density is clearly non-trivial, OR
      - no traversable local outlet and no safe path is visible.

    This keeps probe tied to hazardous/uncertain topology, not generic curiosity.
    """
    ns = _wm_navsummary_get_v1(ctx)
    if not ns:
        return False

    if _wm_navsummary_bool_v1(ctx, "hazard_near", False):
        return True

    hazard_density = _wm_navsummary_float_v1(ctx, "hazard_density")
    if isinstance(hazard_density, float) and hazard_density >= 0.15:
        return True

    traversable_near = _wm_navsummary_bool_v1(ctx, "traversable_near", False)
    safe_cost = _wm_navsummary_int_v1(ctx, "shortest_safe_path_cost")
    if (not traversable_near) and safe_cost is None:
        return True

    return False


#pylint: disable=superfluous-parens
def _gate_stand_up_trigger_legacy_body_first(world, _drives: Drives, ctx) -> bool:
    """Return the pre-Phase-3C BodyMap/WorkingMap/WorldGraph StandUp gate."""
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None

    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        strict_current = bool(getattr(ctx, "experiment_newborn_require_current_state", False)) if ctx is not None else False
        governed_workingmap = strict_current and bool(
            getattr(ctx, "experiment_newborn_explicit_missingness", False)
        )
        if governed_workingmap:
            wm_state = _newborn_workingmap_state_v1(ctx)
            wm_posture = wm_state.get("posture")
            wm_sources = wm_state.get("source_by_field")
            wm_sources = wm_sources if isinstance(wm_sources, dict) else {}
            if wm_posture is not None:
                _record_newborn_guarded_field_use_v1(
                    ctx,
                    consumer="stand_up_gate",
                    field="posture",
                    value=wm_posture,
                    source=wm_sources.get("posture"),
                )
            fallen = wm_posture == "fallen"
            standing = wm_posture == "standing"
        else:
            fallen = has_pred_near_now(world, "posture:fallen")
            standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    return fallen or (stand_intent and not standing)


def _gate_stand_up_trigger_body_first(world, drives: Drives, ctx) -> bool:
    """Return the active StandUp gate under Phase 3C/3D authority.

    Phase 3D makes actionable maintained WNM geometry the normal cognitive
    source. Explicit legacy mode preserves the historical BodyMap-first gate.
    Fresh BodyMap fallen remains a protected safety override, and unsupported
    map states fall back to the complete historical result.
    """
    legacy_triggered = _gate_stand_up_trigger_legacy_body_first(world, drives, ctx)
    bodymap_fresh = bool(ctx is not None and not bodymap_is_stale(ctx))
    protected_bodymap_fallen = bool(bodymap_fresh and body_posture(ctx) == "fallen")
    return bool(
        standup_guarded_trigger_v1(
            ctx,
            legacy_gate_triggered=legacy_triggered,
            protected_bodymap_fallen=protected_bodymap_fallen,
        )
    )


def _gate_stand_up_explain(world, drives: Drives, ctx) -> str:
    """Return a legacy-gate explanation plus the active StandUp authority source."""
    hunger = float(getattr(drives, "hunger", 0.0))
    stale = bodymap_is_stale(ctx) if ctx is not None else True
    bp = body_posture(ctx) if ctx is not None and not stale else None
    if bp is not None:
        fallen = (bp == "fallen")
        standing = (bp == "standing")
    else:
        fallen = has_pred_near_now(world, "posture:fallen")
        standing = has_pred_near_now(world, "posture:standing")

    stand_intent = has_pred_near_now(world, "stand")
    guarded = str(standup_guarded_explain_v1(ctx))
    return (
        f"dev_gate: age_days={getattr(ctx, 'age_days', 0.0):.2f}<=3.0, legacy_trigger: "
        f"fallen={fallen} or (stand_intent={stand_intent} and not standing={not standing}) "
        f"(hunger={hunger:.2f}); {guarded}"
    )


def _gate_seek_nipple_trigger_body_first(world, drives: Drives, ctx) -> bool:
    """
    SeekNipple gate that supports two paths:

      1) the original hunger-driven path, and
      2) a narrow newborn bridge path once the kid is standing and mom is already near.

    Why this change
    ---------------
    In the hardened newborn benchmark, the kid can now successfully recover posture and
    approach mom, but the default interactive run keeps hunger at 0.50. That means the
    original hunger-only gate can leave the agent stuck in:

        first_stand + mom near + nipple hidden + safe zone

    The bridge below is intentionally narrow:
      - posture must be standing,
      - the kid must not be fallen,
      - mom-distance information must actually exist,
      - mom must be near/touching,
      - nipple must not already be latched,
      - and seeking_mom must not already be active.

    This keeps the old behavior for generic cases while letting the newborn task move
    from "reached mom" into "find nipple".

    Benchmark-only strict mode
    --------------------------
    In strict newborn benchmark mode, current state still comes first. However, when
    current distance/nipple information is sparse due to blackout, we now allow the
    short-lived retrieved hint to supply that information. This is the missing bridge
    between "retrieval happened" and "retrieval changed control".
    """
    # Once latched, do not search for the nipple again. The correct next bridge
    # is suckle, then rest.
    if _newborn_post_latch_sequence_active_v1(world, ctx):
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

    strict_current = bool(getattr(ctx, "experiment_newborn_require_current_state", False)) if ctx is not None else False
    hint = _newborn_active_retrieved_hint_v1(ctx) if strict_current else {}
    governed_workingmap = strict_current and bool(
        getattr(ctx, "experiment_newborn_explicit_missingness", False)
    )
    wm_state = _newborn_workingmap_state_v1(ctx) if governed_workingmap else {}

    # Mom-distance check: use BodyMap first. In strict newborn experiment mode,
    # use the retrieved hint next. Only non-strict mode falls back to old graph history.
    have_distance = False
    mom_near = False

    if ctx is not None and not stale:
        md = body_mom_distance(ctx)
        if md is not None:
            have_distance = True
            mom_near = md in ("near", "touching")

    if not have_distance and governed_workingmap:
        wm_md = wm_state.get("mom_distance")
        if isinstance(wm_md, str) and wm_md:
            have_distance = True
            mom_near = wm_md in ("near", "touching")
            wm_sources = wm_state.get("source_by_field")
            wm_sources = wm_sources if isinstance(wm_sources, dict) else {}
            _record_newborn_guarded_field_use_v1(ctx, consumer="seek_nipple_gate", field="mom_distance", value=wm_md, source=wm_sources.get("mom_distance"))

    if not have_distance and strict_current:
        hm = hint.get("mom_distance")
        if isinstance(hm, str) and hm:
            have_distance = True
            mom_near = hm in ("near", "touching")

    if not have_distance and not strict_current:
        close = has_pred_near_now(world, "proximity:mom:close")
        far = has_pred_near_now(world, "proximity:mom:far")
        if close or far:
            have_distance = True
            mom_near = close

    # In the strict newborn benchmark, if distance is still unknown even after
    # consulting the retrieved hint, do not infer "mom is near enough".
    if strict_current and not have_distance:
        return False

    # If we have distance information and mom is not near, seeking is premature.
    if have_distance and not mom_near:
        return False

    # If current state or retrieved hint says we are already latched/drinking, do not seek again.
    ns = body_nipple_state(ctx) if ctx is not None and not stale else None
    if ns is None and governed_workingmap:
        wm_ns = wm_state.get("nipple_state")
        if isinstance(wm_ns, str) and wm_ns:
            ns = wm_ns
            wm_sources = wm_state.get("source_by_field")
            wm_sources = wm_sources if isinstance(wm_sources, dict) else {}
            _record_newborn_guarded_field_use_v1(ctx, consumer="seek_nipple_gate", field="nipple_state", value=wm_ns, source=wm_sources.get("nipple_state"))
    if ns is None and strict_current:
        hn = hint.get("nipple_state")
        if isinstance(hn, str) and hn:
            ns = hn
    if ns == "latched":
        return False

    # If 'seeking_mom' is already active near NOW, do not duplicate the behavior.
    if has_pred_near_now(world, "seeking_mom"):
        return False

    # Original hunger-driven path.
    hunger = float(getattr(drives, "hunger", 0.0))
    if hunger > float(HUNGER_HIGH):
        return True

    # Newborn bridge path:
    # once we are upright and truly near mom, allow nipple-seeking even if hunger
    # is only moderate in the interactive demo.
    if have_distance and mom_near:
        return True

    return False


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
    Rest gate that supports both ordinary fatigue-driven rest and a narrow
    newborn completion bridge, while suppressing redundant rest after success.

    Why this exists
    ---------------
    In the hardened newborn benchmark, ``rest`` is the correct bridge action in
    ``first_latch``. However, once the newborn has already reached the stable
    solved end-state, repeatedly firing ``policy:rest`` adds clutter without
    helping behavior.

    Rules
    -----
    - Ordinary mode:
        fatigue > FATIGUE_HIGH or cue:drive:fatigue_high present
    - goat04 contextual mode:
        an active hawk hint may request rest even when fatigue is mild
        an active fox hint suppresses rest
    - newborn bridge:
        ``_should_force_rest_bridge_v1(...)`` may request rest in ``first_latch``
        even when fatigue is still low
    - newborn solved-state quiescence:
        ``_should_quiesce_rest_v1(...)`` suppresses rest once the newborn is
        already in stable ``stage='rest'`` with safe geometry
    - BodyMap/space veto remains in force:
        do not rest when zone == 'unsafe_cliff_near'
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_high = fatigue > float(FATIGUE_HIGH)
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])
    goat04_hint = _goat04_context_hint_active_v1(ctx)
    newborn_rest_bridge = _should_force_rest_bridge_v1(world, ctx)
    rest_quiesce = _should_quiesce_rest_v1(world, ctx)

    if goat04_hint == "fox":
        return False

    if rest_quiesce:
        return False

    # Phase 6 may add a conservative rest veto only when current evidence was
    # projected from the operative terrain route WNM. ``None`` preserves the
    # complete legacy path; a true safety result never weakens BodyMap safety.
    if terrain_safe_to_rest_v1(ctx) is False:
        return False

    # Newborn hard-mode bridge:
    # after explicit suckling has produced milk:drinking, Rest is the correct
    # task-completion action even if ordinary fatigue is not high.
    if newborn_rest_bridge:
        return True

    # goat04 hawk-context bridge or ordinary fatigue-based Rest gate.
    if not (fatigue_high or fatigue_cue or goat04_hint == "hawk"):
        return False

    try:
        if ctx is not None:
            zone = body_space_zone(ctx)
            if zone == "unsafe_cliff_near":
                return False
    except Exception:
        return True

    return True


def _gate_rest_explain_body_space(world, drives: Drives, ctx) -> str:
    """
    Human-readable explanation matching _gate_rest_trigger_body_space.
    """
    fatigue = float(getattr(drives, "fatigue", 0.0))
    fatigue_cue = any_cue_tokens_present(world, ["drive:fatigue_high"])
    goat04_hint = _goat04_context_hint_active_v1(ctx)
    newborn_rest_bridge = _should_force_rest_bridge_v1(world, ctx)
    rest_quiesce = _should_quiesce_rest_v1(world, ctx)
    terrain_safe_rest = terrain_safe_to_rest_v1(ctx)
    stage = getattr(ctx, "lt_obs_last_stage", None) if ctx is not None else None

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
        f"or goat04_hint={goat04_hint!r} "
        f"or newborn_rest_bridge={newborn_rest_bridge} "
        f"(phase6_terrain_safe_to_rest={terrain_safe_rest}, "
        f"newborn_rest_quiesce={rest_quiesce}, stage={stage!r}, "
        f"rest_zone={zone}, shelter={shelter}, cliff={cliff})"
    )


def _record_newborn_guarded_field_use_v1(
    ctx,
    *,
    consumer: str,
    field: str,
    value: Any,
    source: Any,
) -> None:
    """Record a strict-gate consultation of a guarded-repaired WorkingMap field.

    The event is diagnostic only. A field is counted at most once per controller
    step so repeated gate evaluation cannot inflate the use count.
    """
    if ctx is None or source != "retrieved_guarded":
        return
    try:
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
        key = f"{step_now}|{field}"
        seen = getattr(ctx, "experiment_newborn_guarded_use_seen", None)
        if not isinstance(seen, set):
            seen = set()
        if key in seen:
            return
        seen.add(key)
        ctx.experiment_newborn_guarded_use_seen = seen

        event = {
            "step": step_now,
            "consumer": str(consumer or "gate"),
            "field": str(field),
            "value": value,
            "source": "retrieved_guarded",
        }
        events = getattr(ctx, "experiment_newborn_guarded_use_events", None)
        if not isinstance(events, list):
            events = []
        events.append(event)
        if len(events) > 256:
            del events[:-256]
        ctx.experiment_newborn_guarded_use_events = events
        ctx.experiment_newborn_guarded_use_count = len(events)
    except Exception:
        pass


def _newborn_workingmap_state_v1(ctx) -> dict[str, Any]:
    """Read current/repaired newborn fields from WorkingMap.MapSurface only.

    This helper deliberately ignores long-term WorldGraph history and policy
    scratch nodes. It reads the stable ``wm:entity`` bindings that receive the
    visible observation and the condition-specific governance operation. In the
    publication benchmark this is the causal seam through which guarded merge or
    replacement readback can support policy selection after BodyMap information
    is missing.
    """
    out: dict[str, Any] = {
        "posture": None,
        "mom_distance": None,
        "nipple_state": None,
        "milk_drinking": None,
        "zone": "unknown",
        "route_state": None,
        "source_by_field": {
            "posture": None,
            "mom_distance": None,
            "nipple_state": None,
            "milk_drinking": None,
            "zone": None,
            "route_state": None,
        },
    }
    if ctx is None:
        return out

    try:
        ww = getattr(ctx, "working_world", None)
        ent_map = getattr(ctx, "wm_entities", None)
        if ww is None or not isinstance(ent_map, dict):
            return out
        bindings = getattr(ww, "_bindings", {})
        if not isinstance(bindings, dict):
            return out

        def tags_for(eid: str) -> set[str]:
            bid = ent_map.get(eid)
            if not (isinstance(bid, str) and bid in bindings):
                return set()
            binding = bindings.get(bid)
            tags = getattr(binding, "tags", None)
            try:
                return set(tags or [])
            except Exception:
                return set()

        def source_for(eid: str, family: str) -> str | None:
            bid = ent_map.get(eid)
            if not (isinstance(bid, str) and bid in bindings):
                return None
            binding = bindings.get(bid)
            meta = getattr(binding, "meta", None)
            meta = meta if isinstance(meta, dict) else {}
            wmm = meta.get("wm")
            wmm = wmm if isinstance(wmm, dict) else {}
            source_map = wmm.get("source_by_family")
            source_map = source_map if isinstance(source_map, dict) else {}
            item = source_map.get(family)
            if isinstance(item, dict):
                source = item.get("source")
                return source if isinstance(source, str) and source else None
            if isinstance(item, str) and item:
                return item
            return None

        self_tags = tags_for("self")
        mom_tags = tags_for("mom") | tags_for("mother")
        shelter_tags = tags_for("shelter")
        cliff_tags = tags_for("cliff")

        source_by_field = out["source_by_field"]
        if "pred:resting" in self_tags:
            out["posture"] = "resting"
            source_by_field["posture"] = source_for("self", "resting")
        elif "pred:posture:standing" in self_tags:
            out["posture"] = "standing"
            source_by_field["posture"] = source_for("self", "posture")
        elif "pred:posture:fallen" in self_tags:
            out["posture"] = "fallen"
            source_by_field["posture"] = source_for("self", "posture")

        mom_source = source_for("mom", "proximity:mom") or source_for("mother", "proximity:mom")
        if "pred:proximity:mom:close" in mom_tags:
            out["mom_distance"] = "near"
            source_by_field["mom_distance"] = mom_source
        elif "pred:proximity:mom:far" in mom_tags:
            out["mom_distance"] = "far"
            source_by_field["mom_distance"] = mom_source

        if "pred:milk:drinking" in self_tags:
            out["milk_drinking"] = True
            out["nipple_state"] = "latched"
            source_by_field["milk_drinking"] = source_for("self", "milk")
            source_by_field["nipple_state"] = source_for("self", "milk")
        elif "pred:nipple:latched" in self_tags:
            out["nipple_state"] = "latched"
            source_by_field["nipple_state"] = source_for("self", "nipple")
        elif "pred:nipple:found" in self_tags:
            out["nipple_state"] = "reachable"
            source_by_field["nipple_state"] = source_for("self", "nipple")
        elif "pred:nipple:hidden" in self_tags:
            out["nipple_state"] = "hidden"
            source_by_field["nipple_state"] = source_for("self", "nipple")

        if "pred:route:blocked" in self_tags:
            out["route_state"] = "blocked"
            source_by_field["route_state"] = source_for("self", "route")
        elif "pred:route:clear" in self_tags:
            out["route_state"] = "clear"
            source_by_field["route_state"] = source_for("self", "route")

        shelter_near = "pred:proximity:shelter:near" in shelter_tags
        cliff_near = "pred:hazard:cliff:near" in cliff_tags
        shelter_source = source_for("shelter", "proximity:shelter")
        cliff_source = source_for("cliff", "hazard:cliff")
        if cliff_near and not shelter_near:
            out["zone"] = "unsafe_cliff_near"
            source_by_field["zone"] = cliff_source
        elif shelter_near and not cliff_near:
            out["zone"] = "safe"
            source_by_field["zone"] = shelter_source
    except Exception:
        return out

    return out


def _follow_mom_bridge_state_v1(world, ctx) -> dict[str, Any]:
    """Return the compact body/world state used by follow_mom gating and no-match fallback.

    I keep this helper tiny and explicit because the hardened newborn benchmark now
    depends on action-driven recovery and approach behavior. The runner therefore needs
    one place that answers:

        posture?
        mom_distance?
        nipple_state?
        zone?
        bodymap fresh or stale?

    BodyMap is preferred when fresh. If it is stale or unavailable, we normally fall
    back to near-NOW WorldGraph predicates so the controller still has a conservative
    view of the current situation.

    Benchmark-only strict mode
    --------------------------
    When ctx.experiment_newborn_require_current_state is True, this helper does NOT
    reconstruct current-state values from older long-term graph predicates. It uses:

      1) fresh BodyMap/current-state values first,
      2) the governed WorkingMap MapSurface, then
      3) the optional legacy retrieved hint (disabled in the publication protocol).

    That gives episodic readback a real causal role during blackout windows without
    letting older long-term graph history silently masquerade as "truth now".
    """
    stale = True
    posture = None
    mom_distance = None
    nipple_state = None
    milk_drinking = None
    zone = "unknown"
    route_state = None

    try:
        if ctx is not None:
            stale = bodymap_is_stale(ctx)
            if not stale:
                posture = body_posture(ctx)
                mom_distance = body_mom_distance(ctx)
                nipple_state = body_nipple_state(ctx)
                try:
                    zone = body_space_zone(ctx)
                except Exception:
                    zone = "unknown"
    except Exception:
        stale = True
        posture = None
        mom_distance = None
        nipple_state = None
        zone = "unknown"

    strict_current = bool(getattr(ctx, "experiment_newborn_require_current_state", False)) if ctx is not None else False
    governed_workingmap = strict_current and bool(
        getattr(ctx, "experiment_newborn_explicit_missingness", False)
    )
    if strict_current:
        wm_state = _newborn_workingmap_state_v1(ctx) if governed_workingmap else {}

        wm_sources = wm_state.get("source_by_field")
        wm_sources = wm_sources if isinstance(wm_sources, dict) else {}
        if governed_workingmap and posture is None:
            posture = wm_state.get("posture")
            if posture is not None:
                _record_newborn_guarded_field_use_v1(ctx, consumer="bridge_state", field="posture", value=posture, source=wm_sources.get("posture"))
        if governed_workingmap and mom_distance is None:
            mom_distance = wm_state.get("mom_distance")
            if mom_distance is not None:
                _record_newborn_guarded_field_use_v1(ctx, consumer="bridge_state", field="mom_distance", value=mom_distance, source=wm_sources.get("mom_distance"))
        if governed_workingmap and nipple_state is None:
            nipple_state = wm_state.get("nipple_state")
            if nipple_state is not None:
                _record_newborn_guarded_field_use_v1(ctx, consumer="bridge_state", field="nipple_state", value=nipple_state, source=wm_sources.get("nipple_state"))
        if governed_workingmap and milk_drinking is None and isinstance(wm_state.get("milk_drinking"), bool):
            milk_drinking = wm_state.get("milk_drinking")
            _record_newborn_guarded_field_use_v1(ctx, consumer="bridge_state", field="milk_drinking", value=milk_drinking, source=wm_sources.get("milk_drinking"))
        if governed_workingmap and zone in (None, "", "unknown"):
            wm_zone = wm_state.get("zone")
            if isinstance(wm_zone, str) and wm_zone:
                zone = wm_zone
                _record_newborn_guarded_field_use_v1(ctx, consumer="bridge_state", field="zone", value=zone, source=wm_sources.get("zone"))
        if governed_workingmap and route_state is None:
            route_state = wm_state.get("route_state")
            if route_state is not None:
                _record_newborn_guarded_field_use_v1(
                    ctx,
                    consumer="bridge_state",
                    field="route_state",
                    value=route_state,
                    source=wm_sources.get("route_state"),
                )

        hint = _newborn_active_retrieved_hint_v1(ctx)

        if posture is None:
            hp = hint.get("posture")
            if isinstance(hp, str) and hp:
                posture = hp

        if mom_distance is None:
            hm = hint.get("mom_distance")
            if isinstance(hm, str) and hm:
                mom_distance = hm

        if nipple_state is None:
            hn = hint.get("nipple_state")
            if isinstance(hn, str) and hn:
                nipple_state = hn

        hm_drinking = hint.get("milk_drinking")
        if isinstance(hm_drinking, bool):
            milk_drinking = hm_drinking

        if zone in (None, "", "unknown"):
            hz = hint.get("zone")
            if isinstance(hz, str) and hz:
                zone = hz

        return {
            "bodymap_stale": bool(stale),
            "posture": posture,
            "mom_distance": mom_distance,
            "nipple_state": nipple_state,
            "milk_drinking": milk_drinking,
            "zone": zone,
            "route_state": route_state,
        }

    if posture is None:
        if has_pred_near_now(world, "posture:fallen"):
            posture = "fallen"
        elif has_pred_near_now(world, "posture:standing"):
            posture = "standing"
        elif has_pred_near_now(world, "resting"):
            posture = "resting"

    if mom_distance is None:
        if has_pred_near_now(world, "proximity:mom:close"):
            mom_distance = "near"
        elif has_pred_near_now(world, "proximity:mom:far"):
            mom_distance = "far"

    if nipple_state is None:
        if has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking"):
            nipple_state = "latched"
        elif has_pred_near_now(world, "nipple:found"):
            nipple_state = "reachable"
        elif has_pred_near_now(world, "nipple:hidden"):
            nipple_state = "hidden"

    try:
        milk_drinking = has_pred_near_now(world, "milk:drinking")
    except Exception:
        milk_drinking = None

    if route_state is None:
        try:
            if has_pred_near_now(world, "route:blocked"):
                route_state = "blocked"
            elif has_pred_near_now(world, "route:clear"):
                route_state = "clear"
        except Exception:
            route_state = None

    return {
        "bodymap_stale": bool(stale),
        "posture": posture,
        "mom_distance": mom_distance,
        "nipple_state": nipple_state,
        "milk_drinking": milk_drinking,
        "zone": zone,
        "route_state": route_state,
    }


def _newborn_conflicted_repair_status_v1(ctx) -> str:
    """Return the integrated repair challenge status used by policy gates."""
    if ctx is None:
        return "waiting"
    try:
        profile = _newborn_stress_profile_from_ctx_v1(ctx)
    except Exception:
        profile = "baseline"
    if profile != "conflicted_repair":
        return "inactive"
    raw = getattr(ctx, "experiment_conflicted_repair_status", "waiting")
    status = str(raw or "waiting").strip().lower()
    if status not in {"waiting", "armed", "active", "passed", "failed"}:
        return "waiting"
    return status


def _newborn_conflicted_repair_gate_state_v1(world, ctx) -> dict[str, Any]:
    """Return the governed state used by the integrated challenge gates."""
    state = _follow_mom_bridge_state_v1(world, ctx)
    wm_state = _newborn_workingmap_state_v1(ctx)
    sources = wm_state.get("source_by_field")
    sources = sources if isinstance(sources, dict) else {}
    route_state = wm_state.get("route_state")
    if route_state is not None:
        state["route_state"] = route_state
        _record_newborn_guarded_field_use_v1(
            ctx,
            consumer="conflicted_repair_gate",
            field="route_state",
            value=route_state,
            source=sources.get("route_state"),
        )
    return state


def _newborn_recent_retrieval_ok_v1(ctx, *, max_age_steps: int = 3) -> bool:
    """Return True when a recent wm_mapsurface retrieval changed governed state.

    Why this exists
    ---------------
    The newborn benchmark now needs a way to distinguish:

      - "I can continue because I still have fresh current evidence", from
      - "I can continue because episodic readback just restored a useful prior."

    We intentionally keep this helper tiny and benchmark-oriented.
    It inspects the latest map-switch event and treats it as "recent enough"
    only when:

      - the event exists,
      - the event reports ok=True,
      - the condition-specific load was structurally non-noop,
      - and it occurred within ``max_age_steps`` controller steps.

    This is not a general memory-quality score. It is only a narrow bridge gate
    for Menu 49 newborn_long_horizon hardening.
    """
    if ctx is None:
        return False

    events = getattr(ctx, "wm_mapswitch_last_events", None)
    if not isinstance(events, list) or not events:
        return False

    event = events[-1]
    if not isinstance(event, dict):
        return False
    if not bool(event.get("ok")):
        return False

    load = event.get("load")
    load = load if isinstance(load, dict) else {}
    mode = str(load.get("mode") or "merge").strip().lower()
    if mode == "replace":
        changed = int(load.get("entities", 0) or 0) > 0 or int(load.get("relations", 0) or 0) > 0
    else:
        changed = any(
            int(load.get(name, 0) or 0) > 0
            for name in ("added_entities", "filled_slots", "added_edges", "filled_metadata")
        )
    if not changed:
        return False

    event_step_raw = event.get("step")
    if event_step_raw is None:
        return False

    try:
        event_step = int(event_step_raw)
        step_now = int(getattr(ctx, "controller_steps", 0) or 0)
    except Exception:
        return False

    age_steps = step_now - event_step
    return 0 <= age_steps <= max(1, int(max_age_steps))


def _newborn_follow_fallback_blocked_without_memory_v1(world, ctx) -> bool:
    """Return True when generic follow_mom fallback should be blocked in newborn benchmark mode.

    Why this exists
    ---------------
    The current newborn benchmark already has:
      - strict current-state use for some bridge gates,
      - a recent-retrieval check for explicit bridge continuation,
      - and real partial observability via blackout + obs masking.

    However, one important leak remains:
    the generic follow_mom fallback can still keep the task moving even when
    current evidence is sparse, simply because posture is not fallen/resting and
    topology does not veto the action.

    That makes episodic readback less important than the paper intends.

    Rule
    ----
    In newborn benchmark resume-memory mode, block the *generic* follow_mom
    fallback when all of the following are true:

      - posture is standing,
      - current local evidence is sparse/unknown (BodyMap stale or key slots missing),
      - and there was no recent successful wm_mapsurface retrieval/apply event.

    This helper does NOT replace the explicit newborn bridge:
    `_should_force_follow_mom_bridge_v1(...)` still handles the narrower case
    where the system specifically knows mom is far and wants to continue a
    post-stand approach sequence.

    This helper only stops the architecture from drifting forward on a vague
    permissive fallback during blackout-like uncertainty.
    """
    if ctx is None:
        return False

    if not bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)):
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)
    if st.get("posture") != "standing":
        return False

    bodymap_stale = bool(st.get("bodymap_stale"))
    evidence_sparse = (
        bodymap_stale
        or (st.get("mom_distance") is None)
        or (st.get("nipple_state") is None)
    )

    if not evidence_sparse:
        return False

    return not _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _newborn_follow_bridge_requires_legacy_compatibility_v1(ctx: Any) -> bool:
    """Return whether the current bridge still serves the newborn route consumer.

    The current environment overloads ``policy:follow_mom`` during the
    ``struggle``/``first_stand`` route phase: the primitive moves the kid from
    exposed terrain toward shelter in addition to regulating maternal
    separation. Phase 4F does not yet own terrain or route geometry, so that
    explicit consumer remains a legacy compatibility force until Phase 6
    migrates it. A generic far-maternal fallback outside those stages remains
    map-reviewable.
    """
    if ctx is None:
        return False
    stage = getattr(ctx, "lt_obs_last_stage", None)
    return stage in {"struggle", "first_stand"}


def _should_force_follow_mom_bridge_v1(world, ctx) -> bool:
    """Return True when follow_mom should bridge post-stand recovery into mom-approach.

    Why this exists
    ---------------
    This bridge prevents the hardened newborn benchmark from stalling forever in
    ``first_stand`` after the kid has already recovered posture.

    New benchmark hardening
    -----------------------
    In ordinary mode, the bridge remains permissive once posture is standing and
    mom is still far.

    In newborn benchmark resume-memory mode, that permissive bridge is allowed to
    carry progress across a blackout only if:

      - current evidence is genuinely missing/unknown, and
      - a recent wm_mapsurface retrieval/apply event succeeded.

    This gives episodic readback a real causal role without changing ordinary
    interactive runs.
    """
    # The integrated conflicted-repair benchmark supplies its own explicit
    # follow gate. The generic bridge must remain disabled while the challenge
    # is armed or active, otherwise it can force follow_mom despite a visible
    # blocked route and bypass both the probe requirement and the repair test.
    if _newborn_conflicted_repair_status_v1(ctx) in {"armed", "active", "failed"}:
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)

    if st.get("posture") != "standing":
        return False

    mom_distance = st.get("mom_distance")
    if mom_distance != "far":
        return False

    nipple_state = st.get("nipple_state")
    if nipple_state == "latched":
        return False

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False)) if ctx is not None else False
    if not require_resume_memory:
        return True

    bodymap_stale = bool(st.get("bodymap_stale"))
    current_evidence_missing = bodymap_stale or (mom_distance is None)

    # If current evidence is present and explicitly says "mom is far", ordinary bridge is fine.
    # We only require episodic readback when we are trying to continue through a blackout-like
    # uncertainty window.
    if not current_evidence_missing:
        return True

    return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _newborn_milk_drinking_slot_seen_v1(ctx) -> bool:
    """Return True when the current observation slot cache has recorded milk drinking.

    This is a narrow newborn benchmark helper. It does not allow latch alone to
    count as feeding. It only returns True after the long-term observation slot
    cache has actually seen the token "milk:drinking".

    Rationale:
        Under route_loss, the visible milk predicate can disappear from the near-NOW
        graph immediately after the milk-drinking milestone, while the slot cache
        still records that the milk slot reached "milk:drinking". The rest bridge
        should be allowed to use that current-state cache to complete the feeding
        sequence.
    """
    if ctx is None:
        return False

    try:
        slots = getattr(ctx, "lt_obs_slots", None)
        if not isinstance(slots, dict):
            return False

        milk_slot = slots.get("milk")
        if not isinstance(milk_slot, dict):
            return False

        return milk_slot.get("token") == "milk:drinking"
    except Exception:
        return False


def _should_force_rest_bridge_v1(world, ctx) -> bool:
    """Return True when rest should bridge the newborn from feeding into completion.

    In hard newborn mode, Rest must not skip the explicit Suckle -> milk_drinking
    seam. Once milk drinking is visible, however, Rest should be allowed even when
    ordinary fatigue is still low.
    """
    if ctx is None:
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)
    stage = getattr(ctx, "lt_obs_last_stage", None)

    try:
        route_loss_active = _newborn_stress_profile_from_ctx_v1(ctx) == "route_loss"
    except Exception:
        route_loss_active = False

    hard_newborn = bool(getattr(ctx, "experiment_newborn_require_current_state", False))
    milk_drinking_now = _newborn_milk_drinking_current_v1(world, ctx)
    feeding_now = bool(milk_drinking_now)

    # Back-compatible non-hard path: ordinary storyboard may still treat latch/first_latch
    # as feeding. Hard newborn mode must require milk_drinking first.
    if not feeding_now and not hard_newborn and not route_loss_active:
        feeding_now = stage == "first_latch"
        if not feeding_now:
            if st.get("nipple_state") == "latched":
                feeding_now = True
            else:
                try:
                    feeding_now = has_pred_near_now(world, "milk:drinking")
                except Exception:
                    feeding_now = False

    if not feeding_now:
        return False
    if st.get("posture") == "fallen":
        return False
    if st.get("mom_distance") == "far":
        return False
    if st.get("zone") == "unsafe_cliff_near":
        return False

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))
    if not require_resume_memory:
        return True

    bodymap_stale = bool(st.get("bodymap_stale"))
    evidence_sparse = bodymap_stale or (st.get("nipple_state") is None) or (st.get("mom_distance") is None)

    if route_loss_active:
        if not milk_drinking_now:
            return False
        if evidence_sparse:
            return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)
        return True

    if not evidence_sparse:
        return True

    return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)


def _should_quiesce_rest_v1(world, ctx) -> bool:
    """Return True when newborn rest should quiesce because the solved end-state is already stable.

    Why this exists
    ---------------
    The newborn rest bridge is supposed to help the kid move from ``first_latch``
    into completion. Once the environment has already reached the solved end-state,
    repeatedly re-firing ``policy:rest`` is no longer useful. This helper therefore
    suppresses rest only when all of the following are already true:

      - the latest environment stage is ``rest``,
      - posture is resting,
      - the spatial niche is explicitly safe,
      - mom is not far,
      - and the feeding relation is still present (latched or drinking).

    This is intentionally narrower than ``_should_force_rest_bridge_v1(...)``.
    We do not use it during ``first_latch`` because the bridge is still needed there.
    """
    if ctx is None:
        return False

    stage = getattr(ctx, "lt_obs_last_stage", None)
    if stage != "rest":
        return False

    st = _follow_mom_bridge_state_v1(world, ctx)

    resting_now = st.get("posture") == "resting"
    if not resting_now:
        try:
            resting_now = has_pred_near_now(world, "resting")
        except Exception:
            resting_now = False
    if not resting_now:
        return False

    if st.get("zone") != "safe":
        return False
    if st.get("mom_distance") == "far":
        return False

    latched_or_drinking = st.get("nipple_state") == "latched"
    if not latched_or_drinking:
        try:
            latched_or_drinking = has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking")
        except Exception:
            latched_or_drinking = False
    if not latched_or_drinking:
        return False

    return True


def _newborn_post_latch_sequence_active_v1(world, ctx) -> bool:
    """Return True when the newborn sequence has entered the post-latch feeding phase.

    Phase 5 current close-up evidence is consulted first. During migration, the
    existing BodyMap/WorkingMap/benchmark sources remain conservative fallbacks.

    This benchmark helper prevents the controller from continuing earlier search
    or locomotor policies after latch has already been reached. Once latched, the
    correct sequence is suckle, then rest. This helper is conservative and accepts
    current BodyMap state, retrieved hint state, or the benchmark stage boundary.
    """
    if ctx is None:
        return False

    try:
        if feeding_latch_evidence_v1(ctx) is True or feeding_milk_evidence_v1(ctx) is True:
            return True
    except Exception:
        pass

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        st = {}

    if st.get("posture") == "latched":
        return True

    if st.get("nipple_state") == "latched":
        return True

    if st.get("milk_drinking") is True:
        return True

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))

    if require_resume_memory and stage == "first_latch":
        return True

    if not require_resume_memory:
        try:
            return has_pred_near_now(world, "nipple:latched") or has_pred_near_now(world, "milk:drinking")
        except Exception:
            return False

    return False


def _bodymap_slot_has_pred_v1(ctx, slot_name: str, pred_token: str) -> bool:
    """Return True if a BodyMap slot currently carries a specific pred:* tag.

    This is intentionally a tiny runner-side helper. It lets bridge gates read the
    same current-state BodyMap that policy gates already trust, without adding a
    new public controller API just for this newborn benchmark seam.
    """
    if ctx is None:
        return False

    try:
        if bodymap_is_stale(ctx):
            return False
    except Exception:
        return False

    try:
        body_world = getattr(ctx, "body_world", None)
        body_ids = getattr(ctx, "body_ids", {}) or {}
        if body_world is None or not isinstance(body_ids, dict):
            return False

        bid = body_ids.get(slot_name)
        if not isinstance(bid, str):
            return False

        binding = getattr(body_world, "_bindings", {}).get(bid)
        if binding is None:
            return False

        tags = set(getattr(binding, "tags", []) or [])
        want = pred_token if pred_token.startswith("pred:") else f"pred:{pred_token}"
        return want in tags

    except Exception:
        return False


def _newborn_graph_has_pred_anywhere_v1(graph, pred_token: str) -> bool:
    """Return True if a graph-like object currently contains a pred:* token anywhere.

    This is intentionally broader than ``has_pred_near_now``. The current newborn
    loop can execute policies in WorkingMap while long-term WorldGraph remains sparse.
    During the late feeding/rest seam, the most reliable current evidence may therefore
    live on WorkingMap's SELF entity rather than near the long-term NOW anchor.
    """
    if graph is None:
        return False

    token = str(pred_token or "").strip()
    if not token:
        return False
    if token.startswith("pred:"):
        token = token.replace("pred:", "", 1)

    want = f"pred:{token}"

    try:
        bindings = getattr(graph, "_bindings", {})
        if not isinstance(bindings, dict):
            return False

        for binding in bindings.values():
            tags = getattr(binding, "tags", None)
            if isinstance(tags, (set, list, tuple)) and want in tags:
                return True

    except Exception:
        return False

    return False


def _newborn_pred_seen_in_control_worlds_v1(world, ctx, pred_token: str) -> bool:
    """Return True if a predicate is visible in long-term, WorkingMap, MapSurface, or BodyMap."""
    token = str(pred_token or "").strip()
    if not token:
        return False
    if token.startswith("pred:"):
        token = token.replace("pred:", "", 1)

    graphs: list[Any] = [world]

    if ctx is not None:
        for attr_name in ("working_world", "map_surface_world", "body_world"):
            try:
                graph = getattr(ctx, attr_name, None)
            except Exception:
                graph = None
            if graph is not None:
                graphs.append(graph)

    for graph in graphs:
        if graph is None:
            continue

        try:
            if has_pred_near_now(graph, token, hops=6):
                return True
        except TypeError:
            try:
                if has_pred_near_now(graph, token):
                    return True
            except Exception:
                pass
        except Exception:
            pass

        if _newborn_graph_has_pred_anywhere_v1(graph, token):
            return True

    return False


def _newborn_milk_drinking_current_v1(world, ctx) -> bool:
    """Return True once current control-visible evidence supports milk drinking.

    Phase 5 makes the source-linked feeding maps the first consulted source.
    When their current evidence is supported, the map-derived milk result is
    definitive for this cycle. During migration, current BodyMap/WorkingMap
    surfaces remain fallback evidence if Phase 5 is unavailable or temporarily
    unsupported. The old scan over ``cycle_json_records`` is disabled once a
    Phase 5 runtime exists, so historical trace rows cannot masquerade as current
    feeding evidence.
    """
    phase5_active = False
    try:
        phase5_status = feeding_summary_v1(ctx)
        phase5_active = phase5_status.get("status") == "active"
        milk_value = feeding_milk_evidence_v1(ctx)
        if isinstance(milk_value, bool):
            return milk_value
    except Exception:
        phase5_active = False
    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
        if st.get("milk_drinking") is True:
            return True
    except Exception:
        pass

    if _newborn_pred_seen_in_control_worlds_v1(world, ctx, "milk:drinking"):
        return True

    try:
        if _newborn_milk_drinking_slot_seen_v1(ctx):
            return True
    except Exception:
        pass

    # Phase 5 deliberately retires the feeding cycle-history dependency.
    # A trace row is historical evidence, not current mouth/nipple relation.
    if phase5_active:
        return False

    try:
        records = getattr(ctx, "cycle_json_records", None)
    except Exception:
        records = None

    if isinstance(records, list):
        for record in records[-12:]:
            if not isinstance(record, dict):
                continue

            obs = record.get("obs")
            obs = obs if isinstance(obs, dict) else {}

            preds = obs.get("predicates")
            if isinstance(preds, list) and "milk:drinking" in preds:
                return True

            meta = obs.get("env_meta")
            meta = meta if isinstance(meta, dict) else {}

            raw = meta.get("milestones")
            if raw is None:
                raw = meta.get("milestone")

            if raw == "milk_drinking":
                return True
            if isinstance(raw, list) and "milk_drinking" in raw:
                return True

    return False


def _should_force_newborn_rest_after_milk_v1(world, ctx) -> bool:
    """Return True when Rest should bridge milk drinking into the final resting state."""
    if ctx is None:
        return False

    if not _newborn_milk_drinking_current_v1(world, ctx):
        return False

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    # The bridge is specifically for the post-latch newborn feeding phase.
    if stage == "rest":
        return False

    if stage != "first_latch":
        try:
            st = _follow_mom_bridge_state_v1(world, ctx)
        except Exception:
            st = {}

        if st.get("posture") != "latched" and st.get("nipple_state") != "latched":
            return False

    try:
        if body_space_zone(ctx) == "unsafe_cliff_near":
            return False
    except Exception:
        pass

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
        if st.get("posture") == "fallen":
            return False
        if st.get("zone") == "unsafe_cliff_near":
            return False
    except Exception:
        pass

    return True


def _should_force_suckle_bridge_v1(world, ctx) -> bool:
    """Return True when Suckle should bridge latch into milk drinking.

    Once milk_drinking is visible anywhere in the current control surfaces, Suckle
    should stop. The next correct bridge is Rest.
    """
    if ctx is None:
        return False

    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        return False

    if st.get("posture") == "fallen":
        return False

    if st.get("zone") == "unsafe_cliff_near":
        return False

    if st.get("mom_distance") == "far":
        return False

    if _newborn_milk_drinking_current_v1(world, ctx):
        return False

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    if stage == "rest":
        return False

    if stage == "first_latch":
        return True

    if st.get("posture") == "latched":
        return True

    if st.get("nipple_state") == "latched":
        return True

    require_resume_memory = bool(getattr(ctx, "experiment_newborn_require_resume_memory", False))

    if require_resume_memory and stage == "first_latch":
        return _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)

    if not require_resume_memory:
        try:
            return has_pred_near_now(world, "nipple:latched")
        except Exception:
            return False

    return False


def _gate_suckle_trigger_newborn_v1(world, _drives: Drives, ctx) -> bool:
    """Trigger suckling after latch and before rest."""
    return _should_force_suckle_bridge_v1(world, ctx)


def _gate_suckle_explain_newborn_v1(world, _drives: Drives, ctx) -> str:
    """Human-readable explanation matching _gate_suckle_trigger_newborn_v1."""
    try:
        st = _follow_mom_bridge_state_v1(world, ctx)
    except Exception:
        st = {}

    try:
        stage = getattr(ctx, "lt_obs_last_stage", None)
    except Exception:
        stage = None

    try:
        recent_retrieval = _newborn_recent_retrieval_ok_v1(ctx, max_age_steps=3)
    except Exception:
        recent_retrieval = False

    return (
        "dev_gate: True, trigger: newborn_suckle_bridge="
        f"{_should_force_suckle_bridge_v1(world, ctx)} "
        f"stage={stage!r} posture={st.get('posture')!r} "
        f"mom={st.get('mom_distance')!r} nipple={st.get('nipple_state')!r} "
        f"milk_drinking={st.get('milk_drinking')!r} zone={st.get('zone')!r} "
        f"recent_retrieval={recent_retrieval}"
    )


@dataclass(frozen=True, slots=True)
class _FollowMomLegacyGateEvaluationV1:
    """One complete historical FollowMom gate result plus protection metadata.

    ``protected_veto`` marks a false legacy result that Phase 4F may not
    override. ``compatibility_force`` marks a true legacy result whose consumer
    has not yet migrated. Named goat04/conflicted-repair paths and the newborn
    ``struggle``/``first_stand`` route consumer may retain that force. The same
    far-maternal bridge outside those route stages remains map-reviewable and
    cannot bypass earned NavMap authority.
    """

    triggered: bool
    reason: str
    protected_veto: bool = False
    compatibility_force: bool = False


def _follow_mom_legacy_gate_evaluation_v1(
    world: Any,
    ctx: Any,
) -> _FollowMomLegacyGateEvaluationV1:
    """Return the complete pre-Phase-4F FollowMom gate and one explicit reason."""
    hint = _goat04_context_hint_active_v1(ctx)
    if hint == "hawk":
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason="goat04_hawk_context_veto",
            protected_veto=True,
        )
    if hint == "fox":
        return _FollowMomLegacyGateEvaluationV1(
            triggered=True,
            reason="goat04_fox_context_force",
            compatibility_force=True,
        )

    challenge_status = _newborn_conflicted_repair_status_v1(ctx)
    if challenge_status in ("armed", "failed"):
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason=f"conflicted_repair_{challenge_status}_veto",
            protected_veto=True,
        )
    if challenge_status == "active":
        state = _newborn_conflicted_repair_gate_state_v1(world, ctx)
        posture = state.get("posture")
        nipple_state = state.get("nipple_state")
        mom_distance = state.get("mom_distance")
        route_state = state.get("route_state")
        allowed = bool(
            posture == "standing"
            and nipple_state != "latched"
            and mom_distance == "far"
            and route_state == "clear"
        )
        return _FollowMomLegacyGateEvaluationV1(
            triggered=allowed,
            reason=(
                "conflicted_repair_active_route_clear_force"
                if allowed
                else "conflicted_repair_active_gate_veto"
            ),
            protected_veto=not allowed,
            compatibility_force=allowed,
        )

    state = _follow_mom_bridge_state_v1(world, ctx)
    posture = state.get("posture")

    if posture in ("fallen", "resting"):
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason=f"protected_posture_{posture}",
            protected_veto=True,
        )

    if _newborn_post_latch_sequence_active_v1(world, ctx):
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason="post_latch_sequence_lock",
            protected_veto=True,
        )

    # Phase 6 terrain authority is safety-additive only. A current operative
    # route-map veto becomes a protected false legacy result before any
    # permissive newborn bridge or fallback can add FollowMom. Unsupported
    # terrain evidence returns ``None`` and leaves historical behavior intact.
    if terrain_motion_veto_v1(ctx) is True:
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason="phase6_terrain_route_safety_veto",
            protected_veto=True,
        )

    if _should_force_follow_mom_bridge_v1(world, ctx):
        return _FollowMomLegacyGateEvaluationV1(
            triggered=True,
            reason="newborn_post_stand_mom_far_bridge",
            compatibility_force=_newborn_follow_bridge_requires_legacy_compatibility_v1(ctx),
        )

    if _newborn_follow_fallback_blocked_without_memory_v1(world, ctx):
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason="newborn_sparse_state_without_recent_retrieval",
            protected_veto=True,
        )

    if posture is None:
        try:
            if has_pred_near_now(world, "resting", hops=3):
                return _FollowMomLegacyGateEvaluationV1(
                    triggered=False,
                    reason="resting_near_now_veto",
                    protected_veto=True,
                )
        except Exception:
            pass

    try:
        topology_blocked = bool(_wm_follow_mom_blocked_by_topology_v1(ctx))
    except Exception:
        topology_blocked = False
    if topology_blocked:
        return _FollowMomLegacyGateEvaluationV1(
            triggered=False,
            reason="surfacegrid_topology_safety_veto",
            protected_veto=True,
        )

    return _FollowMomLegacyGateEvaluationV1(
        triggered=True,
        reason="legacy_permissive_followmom_fallback",
    )


def _gate_follow_mom_trigger_legacy_body_space(
    world: Any,
    _drives: Drives,
    ctx: Any,
) -> bool:  # pylint: disable=unused-argument
    """Return the complete pre-Phase-4F BodyMap/PolicyRuntime FollowMom gate."""
    return _follow_mom_legacy_gate_evaluation_v1(world, ctx).triggered


def _gate_follow_mom_trigger_body_space(
    world: Any,
    _drives: Drives,
    ctx: Any,
) -> bool:  # pylint: disable=unused-argument
    """Return the active FollowMom gate under guarded/default NavMap authority.

    Every false historical result remains a protected veto. Explicit goat04,
    conflicted-repair, and newborn ``struggle``/``first_stand`` route consumers
    remain compatibility authority. Outside those named consumers, the ordinary
    far-maternal bridge and permissive fallback are historical FollowMom
    opportunities that exact current WNM/NavMap evidence may authorize or
    suppress.
    """
    legacy = _follow_mom_legacy_gate_evaluation_v1(world, ctx)
    return bool(
        followmom_authority_trigger_v1(
            ctx,
            legacy_gate_triggered=legacy.triggered,
            legacy_gate_reason=legacy.reason,
            protected_legacy_veto=legacy.protected_veto,
            legacy_compatibility_force=legacy.compatibility_force,
        )
    )


def _gate_follow_mom_explain_body_space(
    world: Any,
    drives: Drives,
    ctx: Any,
) -> str:  # pylint: disable=unused-argument
    """Return legacy-gate details plus the active FollowMom authority source."""
    hunger = float(getattr(drives, "hunger", 0.0))
    fatigue = float(getattr(drives, "fatigue", 0.0))
    legacy = _follow_mom_legacy_gate_evaluation_v1(world, ctx)
    terrain_veto = terrain_motion_veto_v1(ctx)
    return (
        "dev_gate: True, legacy_followmom_gate="
        f"{legacy.triggered} reason={legacy.reason} "
        f"protected_veto={legacy.protected_veto} compatibility_force={legacy.compatibility_force}; "
        f"{followmom_authority_explain_v1(ctx)}; "
        f"phase6_terrain_motion_veto={terrain_veto}; "
        f"{_wm_navsummary_explain_bits_v1(ctx)} (hunger={hunger:.2f}, fatigue={fatigue:.2f})"
    )


def _gate_probe_ambiguity_trigger_body_first(world, _drives: Drives, ctx) -> bool:  # pylint: disable=unused-argument
    """
    Step 15C gate: trigger a minimal probe policy when WM.Scratch reports an ambiguous NavPatch match.

    Refactor intent
    ---------------
    This gate prefers NavSummary when it is available, but it preserves the original
    Step-15C behavior when NavSummary is absent.

    v1.1 rules
    ----------
      - Probe must be enabled.
      - WM.Scratch must currently hold at least one ambiguity key.
      - Prefer cliff ambiguity, but BodyMap cliff-near remains a fallback support signal.
      - If NavSummary is present:
          * hazard ambiguity requires topology support OR BodyMap cliff-near
          * non-hazard ambiguity requires the stronger fallback (hazard_near + topology support)
      - If NavSummary is absent:
          * preserve backward-compatible behavior: cliff ambiguity alone may trigger probe
      - Respect cooldown exactly as before.
    """
    if ctx is None:
        return False
    if not bool(getattr(ctx, "wm_probe_enabled", True)):
        return False

    challenge_status = _newborn_conflicted_repair_status_v1(ctx)
    if challenge_status in ("armed", "failed"):
        return False
    if challenge_status == "active":
        st = _newborn_conflicted_repair_gate_state_v1(world, ctx)
        return st.get("route_state") == "blocked"

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
        hazard_near = body_cliff_distance(ctx) == "near"
    except Exception:
        hazard_near = False

    if not (hazard_amb or hazard_near):
        return False

    ns = _wm_navsummary_get_v1(ctx)
    navsummary_present = bool(ns)

    topo_support = False
    if navsummary_present:
        try:
            topo_support = _wm_probe_supported_by_topology_v1(ctx)
        except Exception:
            topo_support = False

    # Backward-compatible Step 15C behavior:
    # if NavSummary is missing, a hazard-relevant ambiguity should still be able to trigger probe.
    if hazard_amb:
        if navsummary_present and not (topo_support or hazard_near):
            return False
    else:
        # No explicit cliff ambiguity: require stronger evidence.
        if not navsummary_present:
            return False
        if not (hazard_near and topo_support):
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
        hazard_near = body_cliff_distance(ctx) == "near"
    except Exception:
        hazard_near = False

    ns = _wm_navsummary_get_v1(ctx)
    navsummary_present = bool(ns)

    topo_support = False
    if navsummary_present:
        try:
            topo_support = _wm_probe_supported_by_topology_v1(ctx)
        except Exception:
            topo_support = False

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

    fallback_mode = False
    if hazard_amb and not navsummary_present:
        fallback_mode = True

    return (
        "dev_gate: True, trigger: "
        f"scratch_keys={len(keys_txt)} ents={sorted(list(ents))} "
        f"hazard_amb(cliff)={hazard_amb} hazard_near={hazard_near} "
        f"navsummary_present={navsummary_present} topo_support={topo_support} "
        f"fallback_mode={fallback_mode} "
        f"cooldown={cooldown} blocked={blocked} "
        f"(step_now={step_now}, last_probe={last_i}) {_wm_navsummary_explain_bits_v1(ctx)}"
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
    amb_raw = efe.get("amb_global")

    if amb_raw is None:
        amb_txt = "n/a"
    else:
        try:
            amb_txt = f"{float(amb_raw):.2f}"
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
class PolicyGate:  # pylint: disable=too-few-public-methods
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


    def consider_and_maybe_fire(
        self,
        world,
        drives,
        ctx,
        tie_break: str = "first",
        *,
        exec_world=None,
    ) -> str:  # pylint: disable=unused-argument,too-many-branches,too-many-locals
        """Evaluate triggers, choose one policy, and execute it once.

        The optional ``exec_world`` compatibility seam lets callers evaluate
        triggers on one world object but execute the chosen controller primitive
        on another. When it is omitted, execution happens on ``world`` exactly as
        before.
        """
        _ = tie_break  # compatibility seam for older call sites / docs, avoid unused-argument warning
        matches = [p for p in self.loaded if _safe(p.trigger, world, drives, ctx)]
        triggered_all = [p.name for p in matches]
        legacy_followmom = _follow_mom_legacy_gate_evaluation_v1(world, ctx)
        followmom_loaded = any(p.name == "policy:follow_mom" for p in self.loaded)
        legacy_followmom_candidate = bool(legacy_followmom.triggered and followmom_loaded)
        active_followmom_gate = "policy:follow_mom" in triggered_all

        try:
            debug_state = _follow_mom_bridge_state_v1(world, ctx)
        except Exception as e:
            debug_state = {"error": f"{e.__class__.__name__}: {e}"}
        try:
            debug_stage = getattr(ctx, "lt_obs_last_stage", None)
        except Exception:
            debug_stage = None
        try:
            debug_step = int(getattr(ctx, "controller_steps", 0) or 0)
        except Exception:
            debug_step = -1
        policy_debug: dict[str, Any] = {
            "schema": "experiment_policy_debug_v1",
            "step": int(debug_step),
            "stage": debug_stage if isinstance(debug_stage, str) else None,
            "state": dict(debug_state) if isinstance(debug_state, dict) else {},
            "matches_initial": list(triggered_all),
            "followmom_legacy_gate_triggered": legacy_followmom.triggered,
            "followmom_legacy_gate_reason": legacy_followmom.reason,
            "followmom_legacy_protected_veto": legacy_followmom.protected_veto,
            "followmom_legacy_compatibility_force": legacy_followmom.compatibility_force,
            "followmom_active_gate_triggered": active_followmom_gate,
            "followmom_legacy_effective_candidate": legacy_followmom_candidate,
            "followmom_active_effective_candidate": None,
            "post_latch_sequence": None,
            "matches_after_post_latch": None,
            "bridge_follow_mom": None,
            "legacy_bridge_follow_mom": None,
            "forced_follow_mom": None,
            "matches_after_bridge": None,
            "suppress_follow_mom": None,
            "matches_after_topology": None,
            "fallen_safety_filter": None,
            "legacy_fallen_safety_filter": None,
            "guarded_map_fallen_safety_filter": None,
            "matches_after_safety": None,
            "matches_before_choice": None,
            "chosen": None,
        }

        post_latch_sequence = False
        try:
            post_latch_sequence = _newborn_post_latch_sequence_active_v1(world, ctx)
        except Exception:
            post_latch_sequence = False
        policy_debug["post_latch_sequence"] = bool(post_latch_sequence)

        # Hard sequence lock: after latch, earlier locomotor/search policies should
        # not compete with the late feeding/rest sequence.
        #
        #   before milk_drinking: allow Suckle, block Rest
        #   after milk_drinking : allow Rest, block Suckle
        #
        # This prevents the failure mode where one settling Rest occurs, then the
        # selector falls back into repeated Suckle forever.
        if post_latch_sequence:
            milk_drinking_now = _newborn_milk_drinking_current_v1(world, ctx)

            blocked_post_latch = {"policy:follow_mom", "policy:seek_nipple"}
            if milk_drinking_now:
                blocked_post_latch.add("policy:suckle")
            else:
                blocked_post_latch.add("policy:rest")

            matches = [p for p in matches if p.name not in blocked_post_latch]
            legacy_followmom_candidate = False

            if not milk_drinking_now and not any(p.name == "policy:suckle" for p in matches):
                try:
                    suckle_gate = next((p for p in self.loaded if p.name == "policy:suckle"), None)
                except Exception:
                    suckle_gate = None

                if suckle_gate is not None and _safe(suckle_gate.trigger, world, drives, ctx):
                    matches.append(suckle_gate)

            if milk_drinking_now and not any(p.name == "policy:rest" for p in matches):
                try:
                    rest_gate = next((p for p in self.loaded if p.name == "policy:rest"), None)
                except Exception:
                    rest_gate = None

                if rest_gate is not None and _safe(rest_gate.trigger, world, drives, ctx):
                    matches.append(rest_gate)

        policy_debug["matches_after_post_latch"] = [p.name for p in matches]
        forced_follow_mom = False
        bridge_follow_mom = False
        legacy_bridge_follow_mom = False
        if not post_latch_sequence:
            try:
                legacy_bridge_follow_mom = bool(_should_force_follow_mom_bridge_v1(world, ctx))
            except Exception:
                legacy_bridge_follow_mom = False
            try:
                bridge_follow_mom = bool(
                    followmom_authority_legacy_bridge_allowed_v1(ctx)
                    and legacy_bridge_follow_mom
                )
            except Exception:
                bridge_follow_mom = False

        # If follow_mom already matched because its active gate fired under the
        # newborn bridge, remember that now so the later topology suppression
        # step does not remove it. The independent legacy candidate uses the
        # unmodified historical bridge so Phase 4D differential telemetry stays
        # meaningful even when Phase 4F suppresses the active candidate.
        if bridge_follow_mom and any(p.name == "policy:follow_mom" for p in matches):
            forced_follow_mom = True

        legacy_forced_follow_mom = bool(
            legacy_followmom_candidate
            and legacy_bridge_follow_mom
        )

        # In the conflicted-repair benchmark, a successful probe explicitly
        # clears the hidden route hazard. Once the challenge gate admits
        # follow_mom on route:clear, the ordinary cliff-topology suppressor must
        # not veto that action using pre-challenge terrain state. Condition C is
        # deliberately treated the same way here. Its stale replacement makes
        # route appear clear before any probe, so the environment can record the
        # intended unsafe-follow failure on the next transition.
        if (
            _newborn_conflicted_repair_status_v1(ctx) == "active"
            and any(p.name == "policy:follow_mom" for p in matches)
        ):
            forced_follow_mom = True
        if (
            _newborn_conflicted_repair_status_v1(ctx) == "active"
            and legacy_followmom_candidate
        ):
            legacy_forced_follow_mom = True

        if not matches:
            forced = None
            if (not post_latch_sequence) and bridge_follow_mom and active_followmom_gate:
                try:
                    forced = next((p for p in self.loaded if p.name == "policy:follow_mom"), None)
                except Exception:
                    forced = None

            if forced is None:
                policy_debug["bridge_follow_mom"] = bool(bridge_follow_mom)
                policy_debug["legacy_bridge_follow_mom"] = bool(legacy_bridge_follow_mom)
                policy_debug["forced_follow_mom"] = bool(forced_follow_mom)
                policy_debug["matches_after_bridge"] = []
                policy_debug["followmom_legacy_effective_candidate"] = legacy_followmom_candidate
                policy_debug["followmom_active_effective_candidate"] = False
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

            matches = [forced]
            forced_follow_mom = True
        policy_debug["bridge_follow_mom"] = bool(bridge_follow_mom)
        policy_debug["legacy_bridge_follow_mom"] = bool(legacy_bridge_follow_mom)
        policy_debug["forced_follow_mom"] = bool(forced_follow_mom)
        policy_debug["matches_after_bridge"] = [p.name for p in matches]

        # SurfaceGrid/NavSummary-first suppression hook:
        # block the fallback follow_mom path only when local topology says the move is
        # effectively unsafe or no visible safe outlet exists.
        try:
            suppress_follow_mom = _wm_follow_mom_blocked_by_topology_v1(ctx)
        except Exception:
            suppress_follow_mom = False

        if suppress_follow_mom and not forced_follow_mom:
            matches = [p for p in matches if p.name != "policy:follow_mom"]
        if suppress_follow_mom and not legacy_forced_follow_mom:
            legacy_followmom_candidate = False
        if suppress_follow_mom and not forced_follow_mom:
            if not matches:
                policy_debug["suppress_follow_mom"] = bool(suppress_follow_mom)
                policy_debug["matches_after_topology"] = []
                policy_debug["followmom_legacy_effective_candidate"] = legacy_followmom_candidate
                policy_debug["followmom_active_effective_candidate"] = False
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

        policy_debug["suppress_follow_mom"] = bool(suppress_follow_mom)
        policy_debug["matches_after_topology"] = [p.name for p in matches]

        try:
            if ctx is not None:
                ctx.ac_triggered_policies = list(triggered_all)
        except Exception:
            pass

        try:
            if ctx is not None:
                ctx.experiment_last_llm_advice_summary = {}
        except Exception:
            pass

        # Fallen posture forces safety-only policies. The historical near-NOW/
        # BodyMap route remains available, while Phase 3C/3D may supply a
        # fallen-like WNM signal. Either route can require StandUp, but the map
        # route cannot suppress the protected fresh-BodyMap safety route.
        legacy_fallen_safety_active = _fallen_near_now(world, ctx, max_hops=3)
        guarded_map_fallen_safety_active = bool(standup_guarded_safety_active_v1(ctx))
        fallen_safety_active = bool(legacy_fallen_safety_active or guarded_map_fallen_safety_active)
        policy_debug["fallen_safety_filter"] = fallen_safety_active
        policy_debug["legacy_fallen_safety_filter"] = bool(legacy_fallen_safety_active)
        policy_debug["guarded_map_fallen_safety_filter"] = guarded_map_fallen_safety_active

        if fallen_safety_active:
            safety_only = {"policy:recover_fall", "policy:stand_up"}
            matches = [p for p in matches if p.name in safety_only]
            legacy_followmom_candidate = False
            if not matches:
                policy_debug["matches_after_safety"] = []
                policy_debug["followmom_legacy_effective_candidate"] = False
                policy_debug["followmom_active_effective_candidate"] = False
                _experiment_policy_debug_record_v1(ctx, policy_debug)
                return "no_match"

        policy_debug["matches_after_safety"] = [p.name for p in matches]
        policy_debug["followmom_legacy_effective_candidate"] = legacy_followmom_candidate
        policy_debug["followmom_active_effective_candidate"] = any(
            p.name == "policy:follow_mom" for p in matches
        )

        # --- EFE scoring (diagnostic only) ---
        try:
            if ctx is not None and bool(getattr(ctx, "efe_enabled", False)):
                cand_names = [p.name for p in matches]
                ctx.efe_last = compute_efe_scores_stub_v1(world, drives, ctx, cand_names, triggered_all=triggered_all)
                if isinstance(ctx.efe_last, dict):
                    ctx.efe_last_scores = list(ctx.efe_last.get("scores", []))
                else:
                    ctx.efe_last_scores = []
            else:
                if ctx is not None:
                    ctx.efe_last = {}
                    ctx.efe_last_scores = []
        except Exception:
            try:
                if ctx is not None:
                    ctx.efe_last = {"v": _EFE_SCORES_VERSION, "enabled": False, "error": "efe_compute_exception"}
                    ctx.efe_last_scores = []
            except Exception:
                pass

        # Choose by drive-deficit.
        # "deficit" here means drive-urgency = max(0, drive_value - HIGH_THRESHOLD).
        def deficit(name: str) -> float:
            d = 0.0
            if name == "policy:seek_nipple":
                d += max(0.0, float(getattr(drives, "hunger", 0.0)) - float(HUNGER_HIGH)) * 1.0
            if name == "policy:rest":
                d += max(0.0, float(getattr(drives, "fatigue", 0.0)) - float(FATIGUE_HIGH)) * 0.7
            return d

        def stable_idx(p) -> int:
            try:
                return [q.name for q in self.catalog].index(p.name)
            except ValueError:
                return 10_000


        def non_drive_priority(name: str) -> float:
            """Tiny non-drive tie-break score.

            Used only as a SECONDARY score when drive-urgency deficits tie.

            Intent:
              - StandUp: prefer when BodyMap is fresh and posture == 'fallen'.
              - SeekNipple: once the kid is upright and genuinely near mom, prefer
                nipple-seeking over continuing to spam follow_mom.
              - Suckle: once the newborn is latched but not yet drinking, prefer
                feeding continuation over renewed search/follow actions.
              - Rest: once milk drinking has occurred, prefer resting over
                re-seeking so short blackout windows do not keep breaking latch.
              - RecoverFall: prefer when explicit fall cues are present or when
                repeated stand-up attempts are not taking effect.
            """
            if name == "policy:stand_up":
                try:
                    if bool(standup_guarded_safety_active_v1(ctx)):
                        return 2.0
                    if ctx is not None and not bodymap_is_stale(ctx) and body_posture(ctx) == "fallen":
                        return 2.0
                except Exception:
                    pass
                return 0.0

            if name == "policy:seek_nipple":
                try:
                    if ctx is not None and not bodymap_is_stale(ctx):
                        bp = body_posture(ctx)
                        md = body_mom_distance(ctx)
                        ns = body_nipple_state(ctx)
                        zone = body_space_zone(ctx)

                        if (
                            bp == "standing"
                            and md in ("near", "touching")
                            and ns not in ("latched",)
                            and zone != "unsafe_cliff_near"
                        ):
                            return 1.5
                except Exception:
                    pass
                return 0.0

            if name == "policy:suckle":
                try:
                    if _should_force_suckle_bridge_v1(world, ctx):
                        return 4.5
                except Exception:
                    pass
                return 0.0

            if name == "policy:recover_fall":
                cue_bonus = 0.0
                try:
                    if any_cue_tokens_present(world, ["vestibular:fall", "touch:flank_on_ground", "balance:lost"]):
                        cue_bonus = 1.0
                except Exception:
                    cue_bonus = 0.0

                streak = 0
                try:
                    hist = getattr(ctx, "posture_discrepancy_history", []) if ctx is not None else []
                    if isinstance(hist, list) and hist:
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

                hist_bonus = 0.0
                if streak >= 2:
                    hist_bonus = min(4.0, 2.5 + 0.5 * (streak - 2))
                return cue_bonus + hist_bonus

            if name == "policy:rest":
                try:
                    if _should_force_rest_bridge_v1(world, ctx):
                        return 4.0
                except Exception:
                    pass
                return 0.0

            if name == "policy:probe":
                return 3.0

            return 0.0

        adviser_choice_name = None
        llm_pick_note = ""
        if bool(getattr(ctx, "experiment_llm_adviser_enabled", False)) and len(matches) >= 2:
            try:
                cand_info = _experiment_llm_candidate_rows_v1(
                    matches,
                    world=world,
                    drives=drives,
                    ctx=ctx,
                    deficit_fn=deficit,
                    non_drive_fn=non_drive_priority,
                    stable_idx_fn=stable_idx,
                )
                candidate_rows = cand_info.get("candidate_rows") if isinstance(cand_info, dict) else []
                adviser_summary = _run_experiment_llm_adviser_once_v1(world, drives, ctx, candidate_rows)
            except Exception as e:
                adviser_summary = {
                    "enabled": True,
                    "called": False,
                    "ok": False,
                    "why": "adviser_exception",
                    "error": f"{e.__class__.__name__}: {e}",
                }

            try:
                if ctx is not None:
                    ctx.experiment_last_llm_advice_summary = dict(adviser_summary) if isinstance(adviser_summary, dict) else {}
                    if bool(adviser_summary.get("called")):
                        ctx.experiment_llm_call_count = int(getattr(ctx, "experiment_llm_call_count", 0) or 0) + 1
                        latency_v = adviser_summary.get("latency_ms")
                        if isinstance(latency_v, (int, float)) and not isinstance(latency_v, bool):
                            ctx.experiment_llm_latency_ms_total = (
                                float(getattr(ctx, "experiment_llm_latency_ms_total", 0.0) or 0.0) + float(latency_v)
                            )
            except Exception:
                pass

            try:
                if (
                    ctx is not None
                    and bool(adviser_summary.get("called"))
                    and not bool(adviser_summary.get("ok"))
                    and not bool(getattr(ctx, "experiment_llm_first_error_printed", False))
                ):
                    detail = adviser_summary.get("error_detail")
                    detail = detail if isinstance(detail, dict) else {}

                    msg = detail.get("message") or adviser_summary.get("error") or adviser_summary.get("why")
                    param = detail.get("param")
                    code = detail.get("code")

                    summary = str(msg) if msg is not None else str(adviser_summary.get("why"))
                    if isinstance(param, str) and param:
                        summary += f" | param={param}"
                    if isinstance(code, str) and code:
                        summary += f" | code={code}"

                    print(f"[llm-adviser] first API error: {summary}")
                    ctx.experiment_llm_first_error_printed = True
                    ctx.experiment_llm_first_error_summary = summary

                    if param == "text.format.schema" or code == "invalid_json_schema":
                        ctx.experiment_llm_adviser_enabled = False
            except Exception:
                pass


            if bool(adviser_summary.get("ok")):
                rec_policy = adviser_summary.get("recommended_policy")
                if isinstance(rec_policy, str) and any(p.name == rec_policy for p in matches):
                    adviser_choice_name = rec_policy
                    conf_txt = _experiment_metric_text_v1(adviser_summary.get("confidence"))
                    lat_txt = _experiment_metric_text_v1(adviser_summary.get("latency_ms"))
                    llm_pick_note = (
                        "[llm-adviser] "
                        f"model={adviser_summary.get('model')} recommended={rec_policy} "
                        f"confidence={conf_txt} latency_ms={lat_txt} "
                        f"candidates={adviser_summary.get('candidate_policies')}"
                    )
            elif bool(adviser_summary.get("called")) or adviser_summary.get("why"):
                llm_pick_note = (
                    "[llm-adviser] fallback "
                    f"why={adviser_summary.get('why')} model={adviser_summary.get('model')} "
                    f"candidates={adviser_summary.get('candidate_policies')}"
                )


        def _run_probe_stub_v1() -> dict[str, Any]:
            """Runner-side probe execution shim.

            Why this exists
            ---------------
            The runner has a real probe gate and tests expect probe bookkeeping to change
            immediately when the probe wins. If the controller primitive catalog does not yet
            expose an executable ``policy:probe``, we still need a minimal local execution path.

            Effects
            -------
            - Save the previous grid precision
            - Raise ctx.navpatch_precision_grid to ctx.wm_probe_grid_precision
            - Stamp wm_probe_last_step / wm_probe_restore_step
            - Return a normalized controller-like payload
            """
            step_now = int(getattr(ctx, "controller_steps", 0) or 0)
            duration = int(getattr(ctx, "wm_probe_duration_steps", 2) or 2)
            duration = max(1, min(50, duration))

            prev_precision = float(getattr(ctx, "navpatch_precision_grid", 0.0) or 0.0)
            probe_precision = float(getattr(ctx, "wm_probe_grid_precision", 0.50) or 0.50)

            try:
                ctx.wm_probe_prev_navpatch_precision_grid = prev_precision
            except Exception:
                pass
            try:
                ctx.navpatch_precision_grid = probe_precision
            except Exception:
                pass
            try:
                ctx.wm_probe_last_step = step_now
                ctx.wm_probe_restore_step = step_now + duration
            except Exception:
                pass

            try:
                update_skill("policy:probe", 0.05, ok=True)
            except Exception:
                pass

            return {
                "policy": "policy:probe",
                "status": "ok",
                "reward": 0.05,
                "notes": "runner-side probe shim raised navpatch precision",
                "binding": None,
            }

        rl_pick_note = ""
        did_explore = False
        rl_exploit_kind = ""
        tie_break_label = ""
        selector_kind = "deficit"

        chosen: PolicyGate
        adviser_choice: PolicyGate | None = None

        if isinstance(adviser_choice_name, str) and adviser_choice_name:
            adviser_choice = next(
                (p for p in matches if p.name == adviser_choice_name),
                None,
            )
            if adviser_choice is None:
                adviser_choice_name = None

        rl_enabled = bool(getattr(ctx, "rl_enabled", False))
        if adviser_choice is not None:
            chosen = adviser_choice
            selector_kind = "llm_adviser"
        elif rl_enabled:
            epsilon_raw = getattr(ctx, "rl_epsilon", None)
            if epsilon_raw is None:
                epsilon_raw = getattr(ctx, "jump", 0.0)

            try:
                eps_f = float(epsilon_raw) if epsilon_raw is not None else 0.0
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
                                t[1],
                                t[2],
                                -stable_idx(t[0]),
                            ),
                        )[0]
                        rl_exploit_kind = "q_soft_tiebreak"

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
            chosen = max(matches, key=lambda p: (deficit(p.name), non_drive_priority(p.name), -stable_idx(p)))

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

        if adviser_choice is None:
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

        try:
            policy_debug["matches_before_choice"] = [p.name for p in matches]
            policy_debug["followmom_active_effective_candidate"] = any(
                p.name == "policy:follow_mom" for p in matches
            )
            policy_debug["chosen"] = getattr(chosen, "name", None)
            policy_debug["selector_kind"] = selector_kind
            policy_debug["tie_break_label"] = tie_break_label or None
            policy_debug["selection_reason"] = (
                f"{selector_kind}; tie_break={tie_break_label}" if tie_break_label else selector_kind
            )

            score_rows: list[dict[str, Any]] = []
            for policy in matches:
                score_rows.append(
                    {
                        "policy": policy.name,
                        "deficit": float(deficit(policy.name)),
                        "non_drive": float(non_drive_priority(policy.name)),
                        "q": float(skill_q(policy.name, default=0.0)),
                    }
                )
            policy_debug["score_rows"] = score_rows
            policy_debug["winner_scores"] = next(
                (dict(row) for row in score_rows if row["policy"] == chosen.name),
                None,
            )

            trigger_authority_source = None
            trigger_authority_reason = None
            if chosen.name == "policy:stand_up":
                authority_decision = getattr(ctx, "navmap_standup_guarded_decision", None)
                source = getattr(authority_decision, "authority_source", None)
                trigger_authority_source = getattr(source, "value", source)
                trigger_authority_reason = getattr(authority_decision, "reason", None)
            elif chosen.name == "policy:follow_mom":
                authority_decision = getattr(ctx, "navmap_followmom_authority_decision", None)
                source = getattr(authority_decision, "authority_source", None)
                trigger_authority_source = getattr(source, "value", source)
                trigger_authority_reason = getattr(authority_decision, "reason", None)

            policy_debug["selected_trigger_authority_source"] = trigger_authority_source
            policy_debug["selected_trigger_authority_reason"] = trigger_authority_reason
            _experiment_policy_debug_record_v1(ctx, policy_debug)
        except Exception:
            pass

        base = choose_contextual_base(world, ctx, targets=["posture:standing", "stand"])
        foa = compute_foa(world, ctx, max_hops=2)
        cands = candidate_anchors(world, ctx)
        pre_expl = chosen.explain(world, drives, ctx) if chosen.explain else "explain: (not provided)"

        try:
            exec_target = exec_world if exec_world is not None else world
            before_binding_ids = set(exec_target._bindings)
            before_n = len(before_binding_ids)

            has_real_probe = False
            if chosen.name == "policy:probe":
                try:
                    has_real_probe = any(getattr(p, "name", None) == "policy:probe" for p in policy_primitives_v1())
                except Exception:
                    has_real_probe = False

            if chosen.name == "policy:probe" and not has_real_probe:
                result = _run_probe_stub_v1()
            else:
                result = action_center_step(exec_target, ctx, drives, preferred=chosen.name)

            after_n = len(exec_target._bindings)
            delta_n = after_n - before_n

            label = chosen.name
            if isinstance(result, dict):
                raw_label = result.get("policy")
                if isinstance(raw_label, str) and raw_label:
                    label = raw_label

            try:
                if exec_target is getattr(ctx, "working_world", None):
                    register_policy_scratch_chain_v1(
                        ctx,
                        exec_target,
                        before_binding_ids=before_binding_ids,
                        policy_name=label,
                        policy_result=result if isinstance(result, dict) else None,
                    )
            except Exception:
                # Scratch registration is post-execution provenance. It must not convert a
                # successful primitive into a controller error.
                pass
        except Exception as e:
            return f"{chosen.name} (error: {e})"

        exec_line = ""
        if isinstance(result, dict):
            status = result.get("status")
            reward = result.get("reward")
            binding = result.get("binding")
            if status and status != "noop":
                rtxt = f"{reward:+.2f}" if isinstance(reward, (int, float)) else "n/a"
                exec_line = f"[executed] {label} ({status}, reward={rtxt}) binding={binding}\n"

        pick_debug_line = ""
        try:
            triggered_final = [p.name for p in matches]
            trig_txt = ", ".join(triggered_all)
            final_txt = ", ".join(triggered_final)

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
        post_expl = gate_for_label.explain(exec_target, drives, ctx) if gate_for_label.explain else "explain: (not provided)"
        rl_line = (rl_pick_note + "\n") if rl_pick_note else ""
        llm_line = (llm_pick_note + "\n") if llm_pick_note else ""

        return (
            f"{label} (added {delta_n} bindings)\n"
            f"{pick_debug_line}"
            f"{llm_line}"
            f"{rl_line}"
            f"{exec_line}"
            f"pre:  {pre_expl}\n"
            f"base: {base}\n"
            f"foa:  {foa}\n"
            f"cands:{cands}\n"
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
        trigger=_gate_suckle_trigger_newborn_v1,
        explain=_gate_suckle_explain_newborn_v1,
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


__all__ = [
    "PolicyRuntimeHooks",
    "configure_policy_runtime_hooks",
    "PolicyGate",
    "PolicyRuntime",
    "CATALOG_GATES",
    "compute_efe_scores_stub_v1",
    "_efe_render_summary_line",
    "_wm_creative_update",
    "_gate_stand_up_trigger_legacy_body_first",
    "_gate_stand_up_trigger_body_first",
    "_gate_stand_up_explain",
    "_gate_seek_nipple_trigger_body_first",
    "_gate_seek_nipple_explain",
    "_gate_rest_trigger_body_space",
    "_gate_rest_explain_body_space",
    "_gate_probe_ambiguity_trigger_body_first",
    "_gate_probe_ambiguity_explain_body_first",
    "_gate_follow_mom_trigger_legacy_body_space",
    "_gate_follow_mom_trigger_body_space",
    "_gate_follow_mom_explain_body_space",
    "_gate_suckle_trigger_newborn_v1",
    "_gate_suckle_explain_newborn_v1",
    "_gate_recover_fall_trigger_body_first",
    "_gate_recover_fall_explain",
    "_newborn_workingmap_state_v1",
    "_follow_mom_legacy_gate_evaluation_v1",
    "_follow_mom_bridge_state_v1",
    "_newborn_conflicted_repair_status_v1",
    "_newborn_recent_retrieval_ok_v1",
    "_should_force_follow_mom_bridge_v1",
    "_should_force_rest_bridge_v1",
    "_should_force_suckle_bridge_v1",
    "_should_quiesce_rest_v1",
    "__version__",
]
