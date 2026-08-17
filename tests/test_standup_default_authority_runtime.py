# -*- coding: utf-8 -*-
"""Phase 3D tests for default StandUp NavMap authority and legacy fallback."""

from __future__ import annotations

import json

import pytest

import cca8_run
from cca8_controller import Drives
from cca8_context import Ctx
from cca8_env import EnvObservation, HybridEnvironment
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime, _gate_stand_up_trigger_body_first
from cca8_standup_compare import (
    StandUpAuthorityModeV1,
    render_standup_authority_lines_v1,
    standup_advisory_selection_step_v1,
    standup_authority_mode_v1,
    standup_authority_summary_v1,
    standup_compare_observation_step_v1,
    standup_compare_selection_step_v1,
    standup_guarded_selection_step_v1,
)
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap() -> Ctx:
    """Return one new context using the Phase 3D default authority mode."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(*predicates: str) -> EnvObservation:
    """Return one minimal interpreted observation packet."""
    return EnvObservation(
        raw_sensors={},
        predicates=list(predicates),
        cues=[],
        env_meta={"scenario_stage": "phase3d_test"},
    )


def _world() -> WorldGraph:
    """Return one minimal current episode world."""
    world = WorldGraph()
    world.ensure_anchor("NOW")
    world.ensure_anchor("NOW_ORIGIN")
    return world


def _shadow_compare(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    update_bodymap: bool = True,
    applied_policy: str | None = None,
) -> dict[str, object]:
    """Run BodyMap optionally, Phase 2B shadow, and Phase 3A observation work."""
    if update_bodymap:
        update_body_world_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    return standup_compare_observation_step_v1(ctx, applied_policy=applied_policy)


def _fire_policy_runtime(
    ctx: Ctx,
    *,
    world: WorldGraph | None = None,
    drives: Drives | None = None,
) -> tuple[str, str | None]:
    """Run PolicyRuntime once and return its text plus selected policy token."""
    control_world = world if world is not None else _world()
    runtime = PolicyRuntime(CATALOG_GATES)
    runtime.refresh_loaded(ctx)
    fired = runtime.consider_and_maybe_fire(
        control_world,
        drives if drives is not None else Drives(hunger=0.50, fatigue=0.20, warmth=0.60),
        ctx,
    )
    selected = fired.split()[0] if isinstance(fired, str) and fired.startswith("policy:") else None
    return fired, selected


def _finalize_selection(ctx: Ctx, selected_policy: str | None) -> dict[str, object]:
    """Finalize compare, advisory, and active authority records after selection."""
    authority = standup_authority_summary_v1(ctx)
    decision = authority.get("decision") if isinstance(authority, dict) else None
    legacy_triggered = decision.get("legacy_gate_triggered") if isinstance(decision, dict) else None
    assert isinstance(legacy_triggered, bool)

    standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=legacy_triggered,
        selected_policy=selected_policy,
    )
    standup_advisory_selection_step_v1(ctx)
    return standup_guarded_selection_step_v1(ctx, selected_policy=selected_policy)


def test_new_context_defaults_to_phase3d_default_authority() -> None:
    """New sessions should require no enabling flag for map-first StandUp cognition."""
    ctx = _ctx_with_bodymap()

    summary = standup_authority_summary_v1(ctx)

    assert ctx.navmap_standup_authority_mode == "default"
    assert ctx.navmap_standup_guarded_enabled is None
    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.DEFAULT
    assert summary["phase"] == "3D"
    assert summary["status"] == "idle"
    assert summary["authority"] == "default_standup"
    assert summary["default_authority_active"] is True
    assert summary["normal_cognitive_source"] == "wnm_navmap"
    assert summary["legacy_retired"] is False


def test_default_fallen_map_is_normal_source_without_enabling_flag() -> None:
    """Actionable fallen-like WNM geometry should own the default StandUp trigger."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_authority_summary_v1(ctx)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert triggered is True
    assert summary["status"] == "default_map_authority"
    assert summary["phase"] == "3D"
    assert decision["authority_mode"] == "default"
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert decision["normal_cognitive_source"] == "wnm_navmap"
    assert decision["legacy_gate_triggered"] is False
    assert decision["map_body_interpretation"] == "fallen_like"


def test_default_standing_map_suppresses_non_safety_legacy_stand_intent() -> None:
    """Valid standing WNM geometry should defeat a stale graph-only stand intent."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    ctx.controller_steps = 10
    world = _world()
    world.add_predicate("stand", attach="now")

    triggered = _gate_stand_up_trigger_body_first(world, Drives(), ctx)
    decision = standup_authority_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["legacy_gate_triggered"] is True
    assert decision["map_recommendation"] == "do_not_stand"
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert triggered is False


def test_default_stale_map_uses_bodymap_fallback() -> None:
    """Stale map content must lose default trigger authority."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_authority_summary_v1(ctx)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert summary["status"] == "bodymap_fallback"
    assert decision["support_status"] == "stale"
    assert decision["trigger_authority_source"] == "bodymap_fallback"
    assert decision["fallback_reason"] == "support_stale"
    assert triggered is False


def test_default_invalidated_map_preserves_complete_legacy_graph_fallback() -> None:
    """Invalidation should preserve the historical BodyMap/graph fallback chain."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    for _ in range(3):
        _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    ctx.controller_steps = 10
    world = _world()
    world.add_predicate("posture:fallen", attach="now")

    triggered = _gate_stand_up_trigger_body_first(world, Drives(), ctx)
    decision = standup_authority_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["map_maintained"] is False
    assert decision["support_status"] == "invalidated"
    assert decision["legacy_gate_triggered"] is True
    assert decision["trigger_authority_source"] == "bodymap_fallback"
    assert triggered is True


def test_default_mode_preserves_fresh_bodymap_fallen_safety_override() -> None:
    """Fresh BodyMap fallen evidence must still defeat map standing content."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:fallen"))
    _shadow_compare(ctx, _observation("posture:standing"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_authority_summary_v1(ctx)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert triggered is True
    assert summary["status"] == "protected_safety_fallback"
    assert decision["map_recommendation"] == "do_not_stand"
    assert decision["trigger_authority_source"] == "protected_bodymap_safety"
    assert decision["protected_bodymap_fallen"] is True
    assert decision["map_can_override_protected_safety"] is False


def test_default_fallen_map_activates_safety_filter_and_selects_standup() -> None:
    """Map-derived fallen-like posture should constrain selection to recovery."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    fired, selected = _fire_policy_runtime(
        ctx,
        drives=Drives(hunger=0.95, fatigue=0.20, warmth=0.60),
    )

    assert selected == "policy:stand_up"
    assert fired.startswith("policy:stand_up")
    assert ctx.experiment_policy_debug_last["guarded_map_fallen_safety_filter"] is True
    assert ctx.experiment_policy_debug_last["matches_after_safety"] == ["policy:stand_up"]


def test_default_selection_arms_expected_successor() -> None:
    """Default map-authorized StandUp should arm the existing expected map."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fired, selected = _fire_policy_runtime(ctx)

    summary = _finalize_selection(ctx, selected)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert selected == "policy:stand_up"
    assert decision["phase"] == "3D"
    assert decision["selection_result"] == "default_standup_selected"
    assert decision["expected_pending_armed"] is True
    assert ctx.navmap_standup_compare_pending is not None


def test_default_selected_standup_closes_with_successful_evidence() -> None:
    """Phase 3D should retain the expected-versus-evidence outcome loop."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fired, selected = _fire_policy_runtime(ctx)
    _finalize_selection(ctx, selected)

    next_obs = _observation("posture:standing")
    update_body_world_from_obs(ctx, next_obs)
    _shadow_compare(ctx, next_obs, update_bodymap=False, applied_policy="policy:stand_up")

    assert ctx.navmap_standup_compare_last_outcome is not None
    assert ctx.navmap_standup_compare_last_outcome.outcome == "success"
    assert ctx.navmap_standup_compare_last_outcome.observed_interpretation.value == "standing_like"


def test_explicit_legacy_mode_restores_legacy_behavior_without_authority_state() -> None:
    """The Phase 3D debug switch should return to exact legacy behavior."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_authority_mode = "legacy"
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_authority_summary_v1(ctx)

    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.LEGACY
    assert triggered is False
    assert ctx.navmap_standup_guarded_decision is None
    assert summary["status"] == "legacy_mode"
    assert summary["authority"] == "legacy_bodymap_policy_runtime"
    assert summary["legacy_retired"] is False


def test_explicit_guarded_mode_retains_phase3c_trace_semantics() -> None:
    """The canonical mode field should still permit the Phase 3C experiment."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_authority_mode = "guarded"
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_authority_summary_v1(ctx)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert triggered is True
    assert summary["phase"] == "3C"
    assert summary["status"] == "guarded_map_authority"
    assert summary["authority"] == "guarded_standup"
    assert decision["feature_flag_enabled"] is True
    assert decision["default_authority_active"] is False


def test_phase3c_compatibility_flag_overrides_canonical_default_mode() -> None:
    """Existing callers setting the old bool should retain deterministic behavior."""
    ctx = _ctx_with_bodymap()

    ctx.navmap_standup_guarded_enabled = True
    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.GUARDED

    ctx.navmap_standup_guarded_enabled = False
    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.LEGACY

    ctx.navmap_standup_guarded_enabled = None
    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.DEFAULT


def test_invalid_authority_mode_fails_safe_to_legacy() -> None:
    """Malformed configuration must never silently grant map authority."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_authority_mode = "not-a-mode"

    assert standup_authority_mode_v1(ctx) is StandUpAuthorityModeV1.LEGACY
    assert standup_authority_summary_v1(ctx)["status"] == "legacy_mode"


def test_default_renderer_exposes_promotion_fallback_and_non_retirement() -> None:
    """Human inspection should make the Phase 3D authority boundary explicit."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fire_policy_runtime(ctx)

    text = "\n".join(render_standup_authority_lines_v1(ctx))

    assert "STANDUP PHASE 3D DEFAULT AUTHORITY:" in text
    assert "status=default_map_authority authority=default_standup" in text
    assert "mode=default normal_cognitive_source=wnm_navmap legacy_retired=False" in text
    assert "source=wnm_navmap trigger=True" in text
    assert "protected_safety_can_be_overridden=False" in text


def test_default_authority_remains_limited_to_standup_and_controller_execution() -> None:
    """Promotion must not enlarge the authority domain or replace motor execution."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fire_policy_runtime(ctx)
    decision = standup_authority_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["bounded_domain"] == "stand_up_trigger_and_expectation"
    assert decision["controller_executor"] == "policy_runtime_action_center"
    assert decision["lower_controller_unchanged"] is True
    assert decision["bodymap_mutation_allowed"] is False
    assert decision["other_policy_authority_allowed"] is False
    assert decision["legacy_debug_mode_available"] is True
    assert decision["legacy_retired"] is False


def test_default_authority_history_is_bounded_and_json_safe() -> None:
    """Gate and selection stages should share one bounded row per decision."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_guarded_history_limit = 1
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fired, selected = _fire_policy_runtime(ctx)
    _finalize_selection(ctx, selected)

    assert len(ctx.navmap_standup_guarded_history) == 1
    assert ctx.navmap_standup_guarded_history[0]["source_stage"] == "selection"
    assert ctx.navmap_standup_guarded_history[0]["authority_mode"] == "default"
    json.dumps(ctx.navmap_standup_guarded_history, allow_nan=False, sort_keys=True)


def test_cycle_json_exposes_phase3d_generic_authority_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should expose the promoted default mode."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        _world(),
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    assert ctx.cycle_json_records
    authority = ctx.cycle_json_records[-1]["standup_authority"]
    guarded_alias = ctx.cycle_json_records[-1]["standup_guarded"]
    assert authority["schema"] == "standup_authority_summary_v1"
    assert authority["phase"] == "3D"
    assert authority["authority_mode"] == "default"
    assert authority["default_authority_active"] is True
    assert authority["decision"]["selected_policy"] == "policy:stand_up"
    assert guarded_alias["phase"] == "3D"
    assert guarded_alias["decision"]["protected_safety_can_be_overridden"] is False
