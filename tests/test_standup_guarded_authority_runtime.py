# -*- coding: utf-8 -*-
"""Phase 3C tests for guarded StandUp NavMap authority and fallback."""

from __future__ import annotations

import json

import pytest

import cca8_run
from cca8_controller import Drives
from cca8_context import Ctx
from cca8_env import EnvObservation, HybridEnvironment
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, update_body_world_from_obs
from cca8_policy_runtime import (
    CATALOG_GATES,
    PolicyRuntime,
    _gate_stand_up_trigger_body_first,
)
from cca8_standup_compare import (
    StandUpGuardedAuthoritySourceV1,
    render_standup_guarded_lines_v1,
    standup_advisory_selection_step_v1,
    standup_compare_observation_step_v1,
    standup_compare_selection_step_v1,
    standup_guarded_selection_step_v1,
    standup_guarded_summary_v1,
)
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap(*, guarded: bool = True) -> Ctx:
    """Return one context with BodyMap initialized and guarded mode configured."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.navmap_standup_guarded_enabled = guarded
    return ctx


def _observation(*predicates: str) -> EnvObservation:
    """Return one minimal interpreted observation packet."""
    return EnvObservation(
        raw_sensors={},
        predicates=list(predicates),
        cues=[],
        env_meta={"scenario_stage": "phase3c_test"},
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
    """Finalize compare, advisory, and guarded records after selection."""
    guarded = standup_guarded_summary_v1(ctx)
    decision = guarded.get("decision") if isinstance(guarded, dict) else None
    legacy_triggered = decision.get("legacy_gate_triggered") if isinstance(decision, dict) else None
    assert isinstance(legacy_triggered, bool)

    standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=legacy_triggered,
        selected_policy=selected_policy,
    )
    standup_advisory_selection_step_v1(ctx)
    return standup_guarded_selection_step_v1(ctx, selected_policy=selected_policy)


def test_guarded_flag_off_is_exact_legacy_pass_through_without_phase3c_state() -> None:
    """Disabled guarded authority must preserve the legacy gate and create no state."""
    ctx = _ctx_with_bodymap(guarded=False)
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)

    assert triggered is False
    assert ctx.navmap_standup_guarded_decision is None
    assert ctx.navmap_standup_guarded_last_update is None
    assert ctx.navmap_standup_guarded_history == []
    assert standup_guarded_summary_v1(ctx)["status"] == "disabled"


def test_fresh_fallen_map_can_override_legacy_standing_trigger_result() -> None:
    """Guarded map authority should trigger StandUp when BodyMap still says standing."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    posture_id = ctx.body_ids["posture"]
    before_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    summary = standup_guarded_summary_v1(ctx)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert triggered is True
    assert summary["status"] == "guarded_map_authority"
    assert decision["trigger_authority_source"] == StandUpGuardedAuthoritySourceV1.WNM_NAVMAP.value
    assert decision["map_authority_used"] is True
    assert decision["map_can_override_legacy_trigger"] is True
    assert decision["legacy_gate_triggered"] is False
    assert decision["map_body_interpretation"] == "fallen_like"
    assert decision["support_status"] == "fresh"
    after_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_fresh_standing_map_can_suppress_non_safety_legacy_stand_intent() -> None:
    """A valid standing WNM may defeat a stale graph-only stand intent."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    ctx.controller_steps = 10  # make BodyMap stale so the legacy path consults the graph
    world = _world()
    world.add_predicate("stand", attach="now")

    triggered = _gate_stand_up_trigger_body_first(world, Drives(), ctx)
    decision = standup_guarded_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["legacy_gate_triggered"] is True
    assert decision["map_recommendation"] == "do_not_stand"
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert triggered is False


def test_stale_map_falls_back_to_bodymap_legacy_result() -> None:
    """Stale maintained geometry must not retain guarded trigger authority."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    decision = standup_guarded_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["support_status"] == "stale"
    assert decision["trigger_authority_source"] == "bodymap_fallback"
    assert decision["fallback_used"] is True
    assert decision["fallback_reason"] == "support_stale"
    assert triggered is False


def test_invalidated_map_falls_back_to_graph_when_bodymap_is_stale() -> None:
    """Invalidated map authority should preserve the complete legacy fallback chain."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    for _ in range(3):
        _shadow_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    ctx.controller_steps = 10
    world = _world()
    world.add_predicate("posture:fallen", attach="now")

    triggered = _gate_stand_up_trigger_body_first(world, Drives(), ctx)
    decision = standup_guarded_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["map_maintained"] is False
    assert decision["support_status"] == "invalidated"
    assert decision["legacy_gate_triggered"] is True
    assert decision["trigger_authority_source"] == "bodymap_fallback"
    assert triggered is True


def test_fresh_bodymap_fallen_is_protected_and_map_cannot_suppress_standup() -> None:
    """Protected BodyMap safety must beat a valid map recommendation not to stand."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:fallen"))
    _shadow_compare(ctx, _observation("posture:standing"), update_bodymap=False)

    triggered = _gate_stand_up_trigger_body_first(_world(), Drives(), ctx)
    decision = standup_guarded_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert triggered is True
    assert decision["map_recommendation"] == "do_not_stand"
    assert decision["trigger_authority_source"] == "protected_bodymap_safety"
    assert decision["protected_bodymap_fallen"] is True
    assert decision["map_can_override_protected_safety"] is False
    assert decision["protected_safety_can_be_overridden"] is False


def test_guarded_fallen_map_activates_safety_filter_and_selects_standup() -> None:
    """Map-derived fallen-like posture should make StandUp the sole safety candidate."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    posture_id = ctx.body_ids["posture"]
    before_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)

    fired, selected = _fire_policy_runtime(
        ctx,
        drives=Drives(hunger=0.95, fatigue=0.20, warmth=0.60),
    )

    assert selected == "policy:stand_up"
    assert fired.startswith("policy:stand_up")
    debug = ctx.experiment_policy_debug_last
    assert debug["guarded_map_fallen_safety_filter"] is True
    assert debug["matches_after_safety"] == ["policy:stand_up"]
    after_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_guarded_standing_map_removes_standup_from_trigger_set() -> None:
    """A guarded standing representation should leave ordinary fallback behavior available."""
    ctx = _ctx_with_bodymap()
    _shadow_compare(ctx, _observation("posture:standing"))
    ctx.controller_steps = 10
    world = _world()
    world.add_predicate("stand", attach="now")

    fired, selected = _fire_policy_runtime(ctx, world=world)

    assert selected == "policy:follow_mom"
    assert fired.startswith("policy:follow_mom")
    assert "policy:stand_up" not in ctx.experiment_policy_debug_last["matches_initial"]


def test_guarded_selection_finalizes_source_and_arms_expected_successor() -> None:
    """A map-authorized StandUp selection should arm the Phase 3 expected map."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fired, selected = _fire_policy_runtime(ctx)

    summary = _finalize_selection(ctx, selected)
    decision = summary["decision"]

    assert isinstance(decision, dict)
    assert selected == "policy:stand_up"
    assert decision["source_stage"] == "selection"
    assert decision["selection_result"] == "guarded_standup_selected"
    assert decision["expected_pending_armed"] is True
    assert ctx.navmap_standup_compare_pending is not None


def test_guarded_map_selected_standup_can_close_with_successful_evidence() -> None:
    """Guarded trigger authority should still use the existing expected/evidence loop."""
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


def test_guarded_authority_is_limited_to_standup_and_keeps_controller_executor() -> None:
    """The trace must explicitly limit map authority to one trigger domain."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fire_policy_runtime(ctx)
    decision = standup_guarded_summary_v1(ctx)["decision"]

    assert isinstance(decision, dict)
    assert decision["bounded_domain"] == "stand_up_trigger_and_expectation"
    assert decision["controller_executor"] == "policy_runtime_action_center"
    assert decision["lower_controller_unchanged"] is True
    assert decision["bodymap_mutation_allowed"] is False
    assert decision["other_policy_authority_allowed"] is False


def test_guarded_history_is_bounded_updates_selection_row_and_is_json_safe() -> None:
    """Gate and selection stages should share one bounded row per decision."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_guarded_history_limit = 1
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    _shadow_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    _fired, selected = _fire_policy_runtime(ctx)
    _finalize_selection(ctx, selected)

    assert len(ctx.navmap_standup_guarded_history) == 1
    assert ctx.navmap_standup_guarded_history[0]["source_stage"] == "selection"

    _shadow_compare(ctx, _observation("posture:standing"))
    _fire_policy_runtime(ctx)

    assert len(ctx.navmap_standup_guarded_history) == 1
    json.dumps(ctx.navmap_standup_guarded_history, allow_nan=False, sort_keys=True)


def test_guarded_renderer_exposes_source_fallback_and_safety_boundary() -> None:
    """Human inspection should show the authority source and protected fallback."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:fallen"))
    _shadow_compare(ctx, _observation("posture:standing"), update_bodymap=False)
    _fire_policy_runtime(ctx)

    text = "\n".join(render_standup_guarded_lines_v1(ctx))

    assert "STANDUP PHASE 3C GUARDED AUTHORITY:" in text
    assert "status=protected_safety_fallback authority=guarded_standup" in text
    assert "source=protected_bodymap_safety trigger=True" in text
    assert "fallback_used=True fallback_reason=protected_bodymap_fallen" in text
    assert "protected_safety_can_be_overridden=False" in text


def test_live_closed_loop_with_guarded_flag_uses_protected_safety_and_selects_standup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The ordinary birth cycle should retain protected BodyMap safety under Phase 3C."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    world = _world()

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    summary = standup_guarded_summary_v1(ctx)
    decision = summary["decision"]
    assert isinstance(decision, dict)
    assert summary["status"] == "protected_safety_fallback"
    assert decision["selected_policy"] == "policy:stand_up"
    assert decision["selection_result"] == "protected_safety_standup_selected"
    assert ctx.env_last_action == "policy:stand_up"


def test_cycle_json_record_contains_phase3c_guarded_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The machine-readable cycle trace should expose the guarded authority source."""
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
    guarded = ctx.cycle_json_records[-1]["standup_guarded"]
    assert guarded["phase"] == "3C"
    assert guarded["decision"]["selected_policy"] == "policy:stand_up"
    assert guarded["decision"]["protected_safety_can_be_overridden"] is False



def test_guarded_summary_preserves_runtime_error_record() -> None:
    """A defensive runner error must remain visible rather than look like fallback."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_guarded_last_update = {
        "schema": "standup_guarded_summary_v1",
        "phase": "3C",
        "status": "error",
        "authority": "guarded_standup",
        "feature_flag_enabled": True,
        "error_type": "ValueError",
        "error": "synthetic guarded failure",
    }

    summary = standup_guarded_summary_v1(ctx)
    text = "\n".join(render_standup_guarded_lines_v1(ctx))

    assert summary["status"] == "error"
    assert summary["error_type"] == "ValueError"
    assert "status=error" in text
    assert "synthetic guarded failure" in text

def test_default_context_keeps_phase3c_disabled_in_cycle_trace(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The new authority path must remain opt-in for ordinary existing runs."""
    ctx = _ctx_with_bodymap(guarded=False)
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

    guarded = ctx.cycle_json_records[-1]["standup_guarded"]
    assert guarded["status"] == "disabled"
    assert guarded["authority"] == "legacy_bodymap_policy_runtime"
    assert ctx.env_last_action == "policy:stand_up"
