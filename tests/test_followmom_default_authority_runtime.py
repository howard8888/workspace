# -*- coding: utf-8 -*-
"""Phase 4E-B/4F tests for guarded and default FollowMom NavMap authority."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

import cca8_context
import cca8_followmom_authority
import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_followmom_advisory import (
    followmom_advisory_observation_step_v1,
    followmom_advisory_selection_step_v1,
)
from cca8_followmom_authority import (
    FollowMomAuthorityDecisionV1,
    FollowMomAuthorityModeV1,
    followmom_authority_legacy_bridge_allowed_v1,
    followmom_authority_mode_v1,
    followmom_authority_selection_step_v1,
    followmom_authority_trigger_value_v1,
    followmom_authority_summary_v1,
    render_followmom_authority_lines_v1,
)
from cca8_followmom_compare import (
    FollowMomExpectedPendingV1,
    followmom_compare_observation_step_v1,
    followmom_compare_selection_step_v1,
)
from cca8_maternal_continuity import maternal_continuity_shadow_observation_step_v1
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import maternal_temporal_shadow_observation_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_policy_runtime import (
    CATALOG_GATES,
    PolicyRuntime,
    _follow_mom_legacy_gate_evaluation_v1,
)
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph

_FOLLOW_MOM = "policy:follow_mom"


def _ctx_with_bodymap() -> Ctx:
    """Return one context with the compatibility BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(
    *,
    maternal: tuple[float, float] | None,
    time_value: float,
    step_index: int,
    posture: str = "standing",
    proximity_predicate: str | None = "proximity:mom:far",
    extra_predicates: tuple[str, ...] = (),
    identity_handle: str | None = None,
    identity_status: str | None = None,
    identity_candidates: list[str] | None = None,
    observability: str | None = None,
    observability_reason: str | None = None,
    negative_evidence: bool | dict[str, object] | None = None,
    blackout: bool = False,
) -> EnvObservation:
    """Return one deterministic maternal observation for authority tests."""
    predicates = [f"posture:{posture}"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    predicates.extend(extra_predicates)
    metadata: dict[str, object] = {
        "scenario_stage": "phase4f_authority_test",
        "time_since_birth": float(time_value),
        "step_index": int(step_index),
        "kid_position": {"x": 0.0, "y": 0.0},
        "mom_position": (
            {"x": float(maternal[0]), "y": float(maternal[1])}
            if maternal is not None
            else None
        ),
    }
    if identity_handle is not None:
        metadata["maternal_identity_handle"] = identity_handle
    if identity_status is not None:
        metadata["maternal_identity_status"] = identity_status
    if identity_candidates is not None:
        metadata["maternal_identity_candidates"] = list(identity_candidates)
    if observability is not None:
        metadata["maternal_observability"] = observability
    if observability_reason is not None:
        metadata["maternal_observability_reason"] = observability_reason
    if negative_evidence is not None:
        metadata["maternal_negative_evidence"] = negative_evidence
    if blackout:
        metadata["newborn_obs_blackout"] = True
        metadata["newborn_obs_blackout_kind"] = "phase4f_test_dropout"
    return EnvObservation(
        raw_sensors={"distance_to_mom": 999.0},
        predicates=predicates,
        cues=[],
        env_meta=metadata,
    )


def _update_dependencies(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Run current BodyMap, temporal, Phase 2, and maternal Phase 4A-4C work."""
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    maternal_temporal_shadow_observation_step_v1(ctx, env_obs)
    maternal_continuity_shadow_observation_step_v1(ctx, env_obs)


def _observe(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    applied_policy: str | None = None,
) -> dict[str, object]:
    """Run one complete Phase 4D observation followed by Phase 4E-A advice."""
    _update_dependencies(ctx, env_obs)
    followmom_compare_observation_step_v1(ctx, applied_policy=applied_policy)
    return followmom_advisory_observation_step_v1(ctx)


def _selected_policy(fired: str) -> str | None:
    """Return the selected policy token from one PolicyRuntime result."""
    first = fired.split()[0] if isinstance(fired, str) and fired else ""
    return first if first.startswith("policy:") else None


def _run_policy_runtime(
    ctx: Ctx,
    *,
    drives: Drives | None = None,
    world: WorldGraph | None = None,
) -> tuple[str | None, dict[str, object]]:
    """Run the real selector and finalize compare, advisory, and authority traces."""
    control_world = world or WorldGraph()
    control_world.set_tag_policy("allow")
    control_world.ensure_anchor("NOW")
    runtime = PolicyRuntime(CATALOG_GATES)
    runtime.refresh_loaded(ctx)
    fired = runtime.consider_and_maybe_fire(
        control_world,
        drives or Drives(hunger=0.0, fatigue=0.0, warmth=0.6),
        ctx,
    )
    selected = _selected_policy(fired)

    debug = ctx.experiment_policy_debug_last
    assert isinstance(debug, dict)
    legacy_gate = debug.get("followmom_legacy_gate_triggered")
    legacy_candidate = debug.get("followmom_legacy_effective_candidate")
    active_candidate = debug.get("followmom_active_effective_candidate")
    assert isinstance(legacy_gate, bool)
    assert isinstance(legacy_candidate, bool)
    assert isinstance(active_candidate, bool)

    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=legacy_gate,
        legacy_effective_candidate=legacy_candidate,
        selected_policy=selected,
    )
    followmom_advisory_selection_step_v1(ctx)
    summary = followmom_authority_selection_step_v1(
        ctx,
        active_effective_candidate=active_candidate,
        selected_policy=selected,
    )
    return selected, summary


def _decision(summary: dict[str, object]) -> dict[str, object]:
    """Return the authority decision dictionary from one active summary."""
    row = summary.get("decision")
    assert isinstance(row, dict)
    return row


def _three_sample_relation(
    ctx: Ctx,
    distances: tuple[float, float, float],
    *,
    proximity_predicate: str = "proximity:mom:far",
) -> None:
    """Create one supported three-sample maternal temporal relation."""
    for index, distance in enumerate(distances):
        _observe(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate=proximity_predicate,
            ),
        )


def test_context_defaults_to_phase4f_with_reversible_guarded_and_legacy_modes() -> None:
    """New contexts should use default authority while preserving migration modes."""
    ctx = Ctx()

    assert ctx.navmap_followmom_authority_mode == "default"
    assert ctx.navmap_followmom_guarded_enabled is None
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.DEFAULT

    ctx.navmap_followmom_authority_mode = "guarded"
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.GUARDED

    ctx.navmap_followmom_authority_mode = "legacy"
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.LEGACY

    ctx.navmap_followmom_authority_mode = "not_a_mode"
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.LEGACY

    ctx.navmap_followmom_authority_mode = "default"
    ctx.navmap_followmom_guarded_enabled = True
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.GUARDED
    ctx.navmap_followmom_guarded_enabled = False
    assert followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.LEGACY


def test_repeated_same_cycle_gate_evaluation_reuses_one_authority_decision() -> None:
    """Diagnostic trigger inspection should not create duplicate lifecycle rows."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    legacy = _follow_mom_legacy_gate_evaluation_v1(WorldGraph(), ctx)

    first = followmom_authority_trigger_value_v1(
        ctx,
        legacy_gate_triggered=legacy.triggered,
        legacy_gate_reason=legacy.reason,
        protected_legacy_veto=legacy.protected_veto,
        legacy_compatibility_force=legacy.compatibility_force,
    )
    decision = ctx.navmap_followmom_authority_decision
    assert isinstance(decision, FollowMomAuthorityDecisionV1)
    first_decision_no = decision.decision_no

    second = followmom_authority_trigger_value_v1(
        ctx,
        legacy_gate_triggered=legacy.triggered,
        legacy_gate_reason=legacy.reason,
        protected_legacy_veto=legacy.protected_veto,
        legacy_compatibility_force=legacy.compatibility_force,
    )

    assert first is True
    assert second is True
    assert ctx.navmap_followmom_authority_decision_no == first_decision_no
    assert len(ctx.navmap_followmom_authority_history) == 1


def test_current_exact_far_relation_uses_default_map_authority_and_arms_expectation() -> None:
    """A current exact far relation should make the map the normal FollowMom source."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected == _FOLLOW_MOM
    assert summary["phase"] == "4F"
    assert summary["status"] == "default_map_authority"
    assert summary["default_authority_active"] is True
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert decision["triggered"] is True
    assert decision["map_recommendation"] == "follow_mom"
    assert decision["advisory_kind"] == "follow_supported"
    assert decision["fallback_used"] is False
    assert decision["current_exact_authority_only"] is True
    assert decision["expected_pending_armed"] is True
    assert isinstance(ctx.navmap_followmom_compare_pending, FollowMomExpectedPendingV1)
    assert ctx.navmap_followmom_compare_pending.selection_phase == "4F"
    assert ctx.navmap_followmom_compare_pending.selection_authority == "default_followmom"
    assert ctx.navmap_followmom_compare_pending.cognitive_source == "wnm_navmap"


def test_near_stable_map_authority_suppresses_permissive_legacy_followmom() -> None:
    """Exact near stable evidence should suppress the old permissive fallback."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (0.60, 0.62, 0.64), proximity_predicate="proximity:mom:close")

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)
    debug = ctx.experiment_policy_debug_last

    assert selected != _FOLLOW_MOM
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert decision["triggered"] is False
    assert decision["map_recommendation"] == "do_not_follow"
    assert decision["advisory_kind"] == "do_not_recruit"
    assert decision["map_suppressed_legacy_candidate"] is True
    assert decision["selection_result"] == "default_do_not_follow_respected"
    assert debug["followmom_legacy_gate_triggered"] is True
    assert debug["followmom_legacy_effective_candidate"] is True
    assert debug["followmom_active_gate_triggered"] is False
    assert debug["followmom_active_effective_candidate"] is False


def test_near_receding_map_authority_recruits_regulation_followmom() -> None:
    """Supported near recession should recruit FollowMom with a regulation expectation."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (0.40, 0.60, 0.80), proximity_predicate="proximity:mom:close")
    world = WorldGraph()
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")
    world.add_predicate("seeking_mom", attach="now")

    selected, summary = _run_policy_runtime(ctx, world=world)
    decision = _decision(summary)
    expected = decision["expected_successor"]

    assert selected == _FOLLOW_MOM
    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert decision["triggered"] is True
    assert decision["map_recommendation"] == "follow_mom"
    assert decision["map_reason"] == "near_but_separation_receding"
    assert decision["advisory_kind"] == "follow_supported"
    assert decision["temporal_valid"] is True
    assert decision["temporal_trend"] == "receding"
    assert isinstance(expected, dict)
    assert expected["expectation_kind"] == "regulate_near_separation"
    assert decision["expected_pending_armed"] is True


def test_far_approaching_without_prior_follow_success_suppresses_initial_recruitment() -> None:
    """Relative approach alone should not recruit a new FollowMom trajectory."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (5.0, 4.0, 3.0))

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected != _FOLLOW_MOM
    assert decision["map_reason"] == "far_but_separation_already_approaching"
    assert decision["advisory_kind"] == "do_not_recruit"
    assert decision["triggered"] is False
    assert decision["prior_outcome"] is None
    assert decision["expected_successor"] is None


def test_far_approaching_after_successful_applied_follow_continues_and_rearms() -> None:
    """Immediate successful progress should support one further FollowMom step."""
    ctx = _ctx_with_bodymap()

    _observe(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    selected, _ = _run_policy_runtime(ctx)
    assert selected == _FOLLOW_MOM

    _observe(
        ctx,
        _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    selected, _ = _run_policy_runtime(ctx)
    assert selected == _FOLLOW_MOM

    _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=2.0, step_index=2),
        applied_policy=_FOLLOW_MOM,
    )
    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected == _FOLLOW_MOM
    assert decision["map_recommendation"] == "do_not_follow"
    assert decision["advisory_kind"] == "continue_supported"
    assert decision["advisory_scope"] == "continue"
    assert decision["triggered"] is True
    assert decision["prior_outcome"] == "success"
    assert decision["prior_action_applied"] == _FOLLOW_MOM
    expected = decision["expected_successor"]
    assert isinstance(expected, dict)
    assert expected["transaction_no"] == decision["transaction_no"]
    assert expected["source_distance"] == pytest.approx(3.0)
    assert expected["provenance"]["source_ref"].startswith(
        "behavioral_primitive:follow_mom:phase4f_authority:"
    )
    assert decision["expected_pending_armed"] is True


def test_authority_selected_expectation_closes_from_environment_evidence_with_metadata() -> None:
    """The next observation, not the motor command, should determine outcome."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    selected, _ = _run_policy_runtime(ctx)
    assert selected == _FOLLOW_MOM

    _observe(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    outcome = ctx.navmap_followmom_compare_last_outcome

    assert outcome is not None
    assert outcome.outcome == "success"
    assert outcome.selection_phase == "4F"
    assert outcome.selection_authority == "default_followmom"
    assert outcome.cognitive_source == "wnm_navmap"
    row = outcome.as_dict()
    assert row["follow_mom_authority"] == "default_followmom"
    assert row["cognitive_source"] == "wnm_navmap"
    assert row["execution_source"] == "policy_runtime_action_center"
    assert row["legacy_primitive_executor_unchanged"] is True
    assert row["map_can_override"] is False
    assert row["map_can_trigger_follow_mom"] is False
    assert row["comparison_module_can_trigger_follow_mom"] is False
    assert row["selection_map_can_supply_followmom_gate"] is True
    assert row["selection_map_authority_used"] is True


@pytest.mark.parametrize(
    ("applied_policy", "distance", "expected_outcome", "expected_advisory"),
    [
        (_FOLLOW_MOM, 3.0, "failure", "followmom_outcome_failure"),
        (_FOLLOW_MOM, None, "unknown", "followmom_outcome_unknown"),
        ("policy:rest", 2.0, "not_applied", "action_handoff_mismatch"),
    ],
)
def test_outcome_review_states_force_complete_legacy_fallback(
    applied_policy: str,
    distance: float | None,
    expected_outcome: str,
    expected_advisory: str,
) -> None:
    """Failure, uncertainty, and action mismatch should not receive map authority."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    selected, _ = _run_policy_runtime(ctx)
    assert selected == _FOLLOW_MOM

    _observe(
        ctx,
        _observation(
            maternal=(distance, 0.0) if distance is not None else None,
            time_value=1.0,
            step_index=1,
            proximity_predicate="proximity:mom:far" if distance is not None else None,
        ),
        applied_policy=applied_policy,
    )
    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert ctx.navmap_followmom_compare_last_outcome is not None
    assert ctx.navmap_followmom_compare_last_outcome.outcome == expected_outcome
    assert decision["advisory_kind"] == expected_advisory
    assert decision["trigger_authority_source"] == "legacy_fallback"
    assert decision["fallback_used"] is True
    assert str(decision["fallback_reason"]).startswith(f"advisory_{expected_advisory}")


def test_old_success_does_not_authorize_continuation_outside_immediate_window() -> None:
    """One old FollowMom success must not become indefinite persistence authority."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    selected, _ = _run_policy_runtime(ctx)
    assert selected == _FOLLOW_MOM
    _observe(
        ctx,
        _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )

    _observe(ctx, _observation(maternal=(3.5, 0.0), time_value=2.0, step_index=2))
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=3.0, step_index=3))
    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["map_reason"] == "far_but_separation_already_approaching"
    assert decision["advisory_kind"] == "do_not_recruit"
    assert decision["prior_outcome"] is None
    assert selected != _FOLLOW_MOM


@pytest.mark.parametrize(
    "observation",
    [
        _observation(
            maternal=(3.0, 0.0),
            time_value=0.0,
            step_index=0,
            identity_status="ambiguous",
            identity_candidates=["goat:mom", "goat:other"],
        ),
        _observation(
            maternal=(3.0, 0.0),
            time_value=0.0,
            step_index=0,
            identity_handle="different_goat",
        ),
    ],
)
def test_identity_ambiguity_or_mismatch_defers_to_legacy(observation: EnvObservation) -> None:
    """Unsupported maternal correspondence should never receive FollowMom authority."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, observation)

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["map_recommendation"] == "defer"
    assert decision["trigger_authority_source"] == "legacy_fallback"
    assert decision["fallback_used"] is True
    assert decision["map_authority_used"] is False


@pytest.mark.parametrize(
    ("disabled_field", "expected_fallback_reason"),
    [
        ("navmap_followmom_compare_enabled", "compare_transaction_unavailable"),
        ("navmap_followmom_advisory_enabled", "matching_advisory_unavailable"),
    ],
)
def test_disabled_compare_or_advisory_dependency_uses_complete_legacy_fallback(
    disabled_field: str,
    expected_fallback_reason: str,
) -> None:
    """Default authority should fail safely when a required migration layer is disabled."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (0.60, 0.62, 0.64), proximity_predicate="proximity:mom:close")
    setattr(ctx, disabled_field, False)

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected in {_FOLLOW_MOM, "policy:seek_nipple"}
    assert decision["trigger_authority_source"] == "legacy_fallback"
    assert decision["triggered"] is True
    assert decision["fallback_used"] is True
    assert decision["fallback_reason"] == expected_fallback_reason


def test_explicit_occlusion_predicted_region_remains_non_authoritative() -> None:
    """The Phase 4D occlusion experiment should fall back until a later authority slice."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _observe(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            observability="occluded",
            observability_reason="known_rock_occluder",
        ),
    )

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["source_mode"] == "predicted_region"
    assert decision["predicted_region_authority_allowed"] is False
    assert decision["trigger_authority_source"] == "legacy_fallback"
    assert str(decision["fallback_reason"]).startswith("source_mode_predicted_region")


def test_reliable_negative_evidence_is_explicit_and_forces_fallback() -> None:
    """Reliable empty-location inspection must remain stronger than a stale prediction."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _observe(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            observability="negative_expected_location",
            negative_evidence={
                "present": True,
                "reliable": True,
                "reason": "expected_visible_location_inspected_empty",
            },
        ),
    )

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["reliable_negative_evidence"] is True
    assert decision["map_recommendation"] == "defer"
    assert decision["trigger_authority_source"] == "legacy_fallback"


def test_fallen_posture_protected_veto_defeats_map_follow_and_standup_wins() -> None:
    """Default FollowMom authority must remain below protected postural safety."""
    ctx = _ctx_with_bodymap()
    _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0, posture="fallen"),
    )

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected in {"policy:stand_up", "policy:recover_fall"}
    assert decision["map_recommendation"] == "follow_mom"
    assert decision["trigger_authority_source"] == "protected_legacy_veto"
    assert decision["triggered"] is False
    assert decision["protected_legacy_veto"] is True
    assert decision["protected_safety_can_be_overridden"] is False
    assert decision["selection_result"] == "protected_veto_respected"


def test_post_latch_sequence_lock_remains_a_protected_veto() -> None:
    """Maternal map authority must not restart locomotion after latch."""
    ctx = _ctx_with_bodymap()
    _observe(
        ctx,
        _observation(
            maternal=(3.0, 0.0),
            time_value=0.0,
            step_index=0,
            extra_predicates=("nipple:latched",),
        ),
    )

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["legacy_gate_reason"] == "post_latch_sequence_lock"
    assert decision["trigger_authority_source"] == "protected_legacy_veto"
    assert decision["triggered"] is False


def test_surfacegrid_topology_veto_remains_above_map_authority() -> None:
    """No visible traversable outlet should block map-recommended FollowMom."""
    ctx = _ctx_with_bodymap()
    ctx.wm_navsummary = {
        "traversable_near": False,
        "hazard_near": True,
        "shortest_safe_path_cost": None,
    }
    _observe(
        ctx,
        _observation(
            maternal=(3.0, 0.0),
            time_value=0.0,
            step_index=0,
            proximity_predicate="proximity:mom:close",
        ),
    )

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["map_recommendation"] == "follow_mom"
    assert decision["legacy_gate_reason"] == "surfacegrid_topology_safety_veto"
    assert decision["trigger_authority_source"] == "protected_legacy_veto"
    assert decision["triggered"] is False


@pytest.mark.parametrize(
    ("hint", "expected_source", "expected_trigger"),
    [
        ("fox", "legacy_compatibility", True),
        ("hawk", "protected_legacy_veto", False),
    ],
)
def test_goat04_context_compatibility_remains_explicit(
    hint: str,
    expected_source: str,
    expected_trigger: bool,
) -> None:
    """Existing goat04 experiment semantics should remain available during migration."""
    ctx = _ctx_with_bodymap()
    ctx.goat04_control_context = hint
    ctx.goat04_control_until_step = 10
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    _, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["trigger_authority_source"] == expected_source
    assert decision["triggered"] is expected_trigger
    assert decision["fallback_used"] is True


def test_newborn_first_stand_route_bridge_remains_explicit_legacy_compatibility() -> None:
    """Phase 4F must preserve the environment's still-unmigrated route consumer."""
    ctx = _ctx_with_bodymap()
    ctx.lt_obs_last_stage = "first_stand"
    _three_sample_relation(ctx, (5.0, 4.0, 3.0))

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected == _FOLLOW_MOM
    assert decision["legacy_gate_reason"] == "newborn_post_stand_mom_far_bridge"
    assert decision["legacy_compatibility_force"] is True
    assert decision["trigger_authority_source"] == "legacy_compatibility"
    assert decision["fallback_used"] is True
    assert decision["map_recommendation"] == "do_not_follow"


def test_guarded_mode_exposes_phase4e_b_semantics_without_default_label() -> None:
    """The earned default implementation should retain an inspectable guarded mode."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_authority_mode = "guarded"
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert selected == _FOLLOW_MOM
    assert summary["phase"] == "4E-B"
    assert summary["status"] == "guarded_map_authority"
    assert summary["authority"] == "guarded_followmom"
    assert summary["default_authority_active"] is False
    assert decision["authority_mode"] == "guarded"
    assert decision["normal_cognitive_source"] == "feature_flagged_wnm_navmap"


def test_legacy_mode_preserves_old_followmom_selection_and_creates_no_authority_record() -> None:
    """Explicit rollback mode should bypass Phase 4F and preserve historical behavior."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_authority_mode = "legacy"
    _three_sample_relation(ctx, (0.60, 0.62, 0.64), proximity_predicate="proximity:mom:close")

    selected, summary = _run_policy_runtime(ctx)
    debug = ctx.experiment_policy_debug_last

    assert selected in {_FOLLOW_MOM, "policy:seek_nipple"}
    assert debug["followmom_legacy_gate_triggered"] is True
    assert debug["followmom_active_gate_triggered"] is True
    assert debug["followmom_legacy_effective_candidate"] is True
    assert debug["followmom_active_effective_candidate"] is True
    assert summary["status"] == "legacy_mode"
    assert summary["authority"] == "legacy_bodymap_policy_runtime"
    assert ctx.navmap_followmom_authority_decision is None
    assert ctx.navmap_followmom_authority_history == []


def test_compare_differential_remains_legacy_based_after_map_suppression() -> None:
    """Phase 4D telemetry should keep comparing against the historical candidate."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (5.0, 4.0, 3.0))

    selected, _ = _run_policy_runtime(ctx)
    transaction = ctx.navmap_followmom_compare_transaction
    debug = ctx.experiment_policy_debug_last

    assert selected != _FOLLOW_MOM
    assert transaction is not None
    assert transaction.legacy_gate_triggered is True
    assert transaction.legacy_effective_candidate is True
    assert transaction.selected_policy is None
    assert transaction.disagreement_assessment.value == "potentially_useful_legacy_overtrigger"
    assert debug["followmom_active_effective_candidate"] is False


def test_historical_force_bridge_cannot_readd_followmom_after_map_suppression() -> None:
    """A later newborn bridge must not silently bypass an actionable do-not-recruit result."""
    ctx = _ctx_with_bodymap()
    _three_sample_relation(ctx, (5.0, 4.0, 3.0))

    selected, summary = _run_policy_runtime(ctx)
    decision = _decision(summary)

    assert decision["trigger_authority_source"] == "wnm_navmap"
    assert decision["triggered"] is False
    assert followmom_authority_legacy_bridge_allowed_v1(ctx) is False
    assert ctx.experiment_policy_debug_last["bridge_follow_mom"] is False
    assert selected != _FOLLOW_MOM


def test_another_global_winner_prevents_expected_relation_arming() -> None:
    """Map applicability should not imply action application when arbitration selects another primitive."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    followmom_authority = cca8_followmom_authority.followmom_authority_trigger_value_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_gate_reason="legacy_permissive_followmom_fallback",
        protected_legacy_veto=False,
        legacy_compatibility_force=False,
    )
    assert followmom_authority is True
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy="policy:rest",
    )
    followmom_advisory_selection_step_v1(ctx)
    summary = followmom_authority_selection_step_v1(
        ctx,
        active_effective_candidate=True,
        selected_policy="policy:rest",
    )
    decision = _decision(summary)

    assert decision["selection_result"] == "default_followmom_not_selected"
    assert decision["expected_pending_armed"] is False
    assert ctx.navmap_followmom_compare_pending is None


def test_authority_path_exception_fails_to_typed_legacy_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """An internal default-authority error must preserve the historical gate."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    def _raise_authority_error(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("phase4f_test_error")

    monkeypatch.setattr(
        cca8_followmom_authority,
        "_decision_from_current_state",
        _raise_authority_error,
    )
    triggered = cca8_followmom_authority.followmom_authority_trigger_value_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_gate_reason="legacy_permissive_followmom_fallback",
        protected_legacy_veto=False,
        legacy_compatibility_force=False,
    )
    summary = followmom_authority_summary_v1(ctx)
    decision = _decision(summary)

    assert triggered is True
    assert decision["trigger_authority_source"] == "legacy_fallback"
    assert decision["fallback_used"] is True
    assert decision["fallback_reason"] == "authority_error_RuntimeError"
    assert followmom_authority_legacy_bridge_allowed_v1(ctx) is True


def test_stale_gate_decision_is_not_finalized_or_rearmed_on_a_later_controller_step() -> None:
    """Selection finalization must ignore an old decision if a new gate was not evaluated."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    authority_value = cca8_followmom_authority.followmom_authority_trigger_value_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_gate_reason="legacy_permissive_followmom_fallback",
        protected_legacy_veto=False,
        legacy_compatibility_force=False,
    )
    assert authority_value is True
    decision_before = ctx.navmap_followmom_authority_decision
    assert isinstance(decision_before, FollowMomAuthorityDecisionV1)
    assert decision_before.source_stage == "gate"

    ctx.controller_steps += 1
    summary = followmom_authority_selection_step_v1(
        ctx,
        active_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    assert ctx.navmap_followmom_authority_decision is decision_before
    assert summary["decision"]["source_stage"] == "gate"
    assert ctx.navmap_followmom_compare_pending is None


def test_authority_history_is_bounded_json_safe_and_decision_is_immutable() -> None:
    """Authority lifecycle records should remain bounded, serializable, and frozen."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_authority_history_limit = 2

    for index, distance in enumerate((4.0, 3.8, 3.6, 3.4)):
        _observe(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )
        _run_policy_runtime(ctx)

    assert len(ctx.navmap_followmom_authority_history) == 2
    json.dumps(ctx.navmap_followmom_authority_history)
    json.dumps(followmom_authority_summary_v1(ctx))

    decision = ctx.navmap_followmom_authority_decision
    assert isinstance(decision, FollowMomAuthorityDecisionV1)
    with pytest.raises(FrozenInstanceError):
        decision.reason = "mutated"  # type: ignore[misc]


def test_gate_and_selection_authority_do_not_mutate_bodymap_or_maternal_navmap() -> None:
    """Phase 4F should change only candidate authority and bounded telemetry."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    assert ctx.body_world is not None
    assert ctx.navmap_maternal_map is not None
    body_before = ctx.body_world.to_dict()
    map_signature_before = ctx.navmap_maternal_map.content_signature()

    _run_policy_runtime(ctx)

    assert ctx.body_world.to_dict() == body_before
    assert ctx.navmap_maternal_map.content_signature() == map_signature_before
    decision = ctx.navmap_followmom_authority_decision
    assert decision is not None
    row = decision.as_dict()
    assert row["bodymap_mutation_allowed"] is False
    assert row["navmap_revision_allowed"] is False
    assert row["global_single_winner_unchanged"] is True
    assert row["lower_controller_unchanged"] is True


def test_renderer_runner_alias_and_summary_expose_default_authority_contract() -> None:
    """Human and compatibility surfaces should expose Phase 4F source and safeguards."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _run_policy_runtime(ctx)

    lines = render_followmom_authority_lines_v1(ctx)
    runner_lines = cca8_run.render_followmom_authority_lines_v1(ctx)

    assert lines == runner_lines
    assert lines[0] == "FOLLOWMOM PHASE 4F DEFAULT AUTHORITY:"
    assert any("source=wnm_navmap" in line for line in lines)
    assert any("protected_safety_can_be_overridden=False" in line for line in lines)
    assert cca8_run.followmom_authority_mode_v1(ctx) is FollowMomAuthorityModeV1.DEFAULT


def test_cycle_json_exposes_phase4f_default_authority(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable closed-loop output should include the default authority record."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    world = WorldGraph()
    world.ensure_anchor("NOW")

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    assert ctx.cycle_json_records
    summary = ctx.cycle_json_records[-1]["followmom_authority"]
    assert summary["schema"] == "followmom_authority_summary_v1"
    assert summary["phase"] == "4F"
    assert summary["authority"] == "default_followmom"
    assert summary["default_authority_active"] is True
    assert summary["protected_safety_can_be_overridden"] is False
    assert summary["decision"]["source_stage"] == "selection"


def test_legacy_gate_helper_still_reproduces_protected_and_permissive_results() -> None:
    """The retained historical gate should remain directly inspectable for fallback."""
    ctx = _ctx_with_bodymap()
    standing = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    _update_dependencies(ctx, standing)
    world = WorldGraph()
    world.ensure_anchor("NOW")

    ordinary = _follow_mom_legacy_gate_evaluation_v1(world, ctx)
    assert ordinary.triggered is True
    assert ordinary.protected_veto is False

    fallen = _observation(maternal=(3.0, 0.0), time_value=1.0, step_index=1, posture="fallen")
    _update_dependencies(ctx, fallen)
    protected = _follow_mom_legacy_gate_evaluation_v1(world, ctx)
    assert protected.triggered is False
    assert protected.protected_veto is True
    assert protected.reason == "protected_posture_fallen"


def test_phase4f_component_versions_and_registry_entry_are_current() -> None:
    """The new authority module should be versioned and registered once."""
    assert cca8_followmom_authority.__version__ == "0.1.0"
    assert cca8_run.__version__ == "0.23.0"
    assert cca8_context.__version__ == "0.17.0"

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry["followmom_authority"] == "cca8_followmom_authority"
    assert list(registry).count("followmom_authority") == 1
