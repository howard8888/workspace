# -*- coding: utf-8 -*-
"""Phase 4D tests for FollowMom map-native comparison and expected relations."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_followmom_compare import (
    FollowMomCompareTransactionV1,
    FollowMomExpectedPendingV1,
    FollowMomMapRecommendationV1,
    followmom_compare_observation_step_v1,
    followmom_compare_selection_step_v1,
    render_followmom_compare_lines_v1,
)
from cca8_maternal_continuity import maternal_continuity_shadow_observation_step_v1
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import maternal_temporal_shadow_observation_step_v1
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


_FOLLOW_MOM = "policy:follow_mom"


def _ctx_with_bodymap() -> Ctx:
    """Return one context with the compatibility BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    ctx.navmap_followmom_authority_mode = "legacy"
    return ctx


def _observation(
    *,
    maternal: tuple[float, float] | None,
    time_value: float,
    step_index: int,
    posture: str = "standing",
    proximity_predicate: str | None = "proximity:mom:far",
    identity_handle: str | None = None,
    identity_status: str | None = None,
    identity_candidates: list[str] | None = None,
    observability: str | None = None,
    observability_reason: str | None = None,
    negative_evidence: bool | dict[str, object] | None = None,
    blackout: bool = False,
) -> EnvObservation:
    """Return one deterministic maternal observation with optional identity metadata."""
    predicates = [f"posture:{posture}"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    metadata: dict[str, object] = {
        "scenario_stage": "phase4d_test",
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
        metadata["newborn_obs_blackout_kind"] = "phase4d_test_dropout"
    return EnvObservation(
        raw_sensors={"distance_to_mom": 999.0},
        predicates=predicates,
        cues=[],
        env_meta=metadata,
    )


def _update_dependencies(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Run BodyMap, Sequential/Error, Phase 2, and maternal Phases 4A-4C."""
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    maternal_temporal_shadow_observation_step_v1(ctx, env_obs)
    maternal_continuity_shadow_observation_step_v1(ctx, env_obs)


def _update_phase4d(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    applied_policy: str | None = None,
) -> dict[str, object]:
    """Run all current observation dependencies followed by Phase 4D."""
    _update_dependencies(ctx, env_obs)
    return followmom_compare_observation_step_v1(ctx, applied_policy=applied_policy)


def _transaction(row: dict[str, object]) -> dict[str, object]:
    """Return the transaction dictionary from one Phase 4D summary."""
    transaction = row.get("transaction")
    assert isinstance(transaction, dict)
    return transaction


def _legacy_values_from_debug(ctx: Ctx) -> tuple[bool | None, bool | None, str | None]:
    """Return FollowMom gate/candidate/winner values from PolicyRuntime diagnostics."""
    debug = ctx.experiment_policy_debug_last
    initial = debug.get("matches_initial") if isinstance(debug, dict) else None
    effective = debug.get("matches_before_choice") if isinstance(debug, dict) else None
    chosen = debug.get("chosen") if isinstance(debug, dict) else None
    legacy_gate = debug.get("followmom_legacy_gate_triggered") if isinstance(debug, dict) else None
    legacy_candidate = debug.get("followmom_legacy_effective_candidate") if isinstance(debug, dict) else None
    gate = legacy_gate if isinstance(legacy_gate, bool) else (
        _FOLLOW_MOM in initial if isinstance(initial, list) else None
    )
    candidate = legacy_candidate if isinstance(legacy_candidate, bool) else (
        _FOLLOW_MOM in effective if isinstance(effective, list) else None
    )
    selected = chosen if isinstance(chosen, str) else None
    return gate, candidate, selected


def _run_legacy_selector(ctx: Ctx, *, drives: Drives | None = None) -> str:
    """Run the real legacy PolicyRuntime once and return the selected policy name."""
    world = WorldGraph()
    world.set_tag_policy("allow")
    world.ensure_anchor("NOW")
    runtime = PolicyRuntime(CATALOG_GATES)
    runtime.refresh_loaded(ctx)
    fired = runtime.consider_and_maybe_fire(
        world,
        drives or Drives(hunger=0.0, fatigue=0.0, warmth=0.6),
        ctx,
    )
    first_token = fired.split()[0] if isinstance(fired, str) else ""
    return first_token if first_token.startswith("policy:") else ""


def test_visible_far_relation_recommends_follow_with_compact_expected_successor() -> None:
    """Visible far geometry should recommend FollowMom before temporal history exists."""
    ctx = _ctx_with_bodymap()

    row = _update_phase4d(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )
    transaction = _transaction(row)
    expected = transaction["expected_successor"]

    assert transaction["map_recommendation"] == "follow_mom"
    assert transaction["map_reason"] == "current_exact_far_without_supported_approach"
    assert transaction["source_mode"] == "current_exact"
    assert transaction["temporal_valid"] is False
    assert isinstance(expected, dict)
    assert expected["expectation_kind"] == "reduce_separation"
    assert expected["relation_type"] == "self_maternal_separation"
    assert expected["source_class"] == "expected"
    assert expected["current_truth"] is False
    assert expected["creates_navmap_revision"] is False
    assert expected["provenance"]["source_class"] == "expected"
    assert transaction["authority"] == "compare_only"
    assert transaction["legacy_executes"] is True
    assert transaction["map_can_override"] is False


def test_far_approaching_relation_recommends_do_not_follow() -> None:
    """A supported far-but-approaching relation should avoid unnecessary pursuit."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        row = _update_phase4d(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    transaction = _transaction(row)
    assert transaction["proximity"] == "far"
    assert transaction["temporal_trend"] == "approaching"
    assert transaction["temporal_valid"] is True
    assert transaction["map_recommendation"] == "do_not_follow"
    assert transaction["expected_successor"] is None


def test_far_stable_or_receding_relation_recommends_follow() -> None:
    """Far separation without supported approach should remain FollowMom-applicable."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((2.0, 2.5, 3.0)):
        row = _update_phase4d(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    transaction = _transaction(row)
    assert transaction["temporal_trend"] == "receding"
    assert transaction["map_recommendation"] == "follow_mom"
    assert transaction["expected_successor"]["expectation_kind"] == "reduce_separation"


def test_near_receding_relation_recommends_regulation_follow() -> None:
    """A near but receding maternal relation should request regulated following."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((0.4, 0.6, 0.8)):
        row = _update_phase4d(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate="proximity:mom:close",
            ),
        )

    transaction = _transaction(row)
    assert transaction["proximity"] == "near"
    assert transaction["temporal_trend"] == "receding"
    assert transaction["map_recommendation"] == "follow_mom"
    assert transaction["expected_successor"]["expectation_kind"] == "regulate_near_separation"


def test_near_stable_relation_recommends_do_not_follow() -> None:
    """A near relation that is not receding should not recruit FollowMom."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((0.60, 0.62, 0.64)):
        row = _update_phase4d(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate="proximity:mom:close",
            ),
        )

    transaction = _transaction(row)
    assert transaction["temporal_trend"] == "stable"
    assert transaction["map_recommendation"] == "do_not_follow"
    assert transaction["expected_successor"] is None


def test_occluded_coasting_region_entirely_far_can_recommend_follow() -> None:
    """A bounded non-authoritative coasting region may support a far recommendation."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4d(
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
    transaction = _transaction(row)

    assert transaction["source_mode"] == "predicted_region"
    assert transaction["observability"] == "occluded"
    assert transaction["track_status"] == "coasting"
    assert transaction["uncertainty_radius"] == pytest.approx(0.75)
    assert transaction["map_recommendation"] == "follow_mom"
    assert transaction["map_reason"] == "bounded_coasting_region_entirely_far"
    assert transaction["expected_successor"]["source_uncertainty_radius"] == pytest.approx(0.75)


def test_generic_sensor_dropout_predicted_region_defers() -> None:
    """Generic missingness must not be promoted to the explicit-occlusion experiment."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4d(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            blackout=True,
        ),
    )
    transaction = _transaction(row)

    assert transaction["source_mode"] == "predicted_region"
    assert transaction["observability"] == "sensor_dropout"
    assert transaction["map_recommendation"] == "defer"
    assert transaction["map_reason"] == "predicted_region_requires_explicit_occlusion_sensor_dropout"


def test_predicted_region_crossing_near_far_boundary_defers() -> None:
    """Uncertainty spanning the near/far threshold should preserve DEFER."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(1.2, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4d(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            observability="occluded",
        ),
    )
    transaction = _transaction(row)

    assert transaction["source_mode"] == "predicted_region"
    assert transaction["map_recommendation"] == "defer"
    assert transaction["map_reason"] == "predicted_region_crosses_near_far_boundary"
    assert transaction["fallback_required"] is True
    assert transaction["expected_successor"] is None


def test_predicted_region_exceeding_configured_uncertainty_limit_defers() -> None:
    """The coasting exception should remain bounded by an explicit uncertainty guard."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_compare_maximum_predicted_region_radius = 0.50
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4d(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            observability="occluded",
        ),
    )
    transaction = _transaction(row)

    assert transaction["uncertainty_radius"] == pytest.approx(0.75)
    assert transaction["map_recommendation"] == "defer"
    assert transaction["map_reason"] == "predicted_region_uncertainty_exceeds_limit"


def test_lost_track_defers_without_chasing_last_supported_coordinate() -> None:
    """A lost maternal track must not become a stale exact-point FollowMom trigger."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    for index in (1, 2, 3):
        row = _update_phase4d(
            ctx,
            _observation(maternal=None, time_value=float(index), step_index=index, proximity_predicate=None),
        )

    transaction = _transaction(row)
    assert transaction["track_status"] == "lost"
    assert transaction["source_mode"] == "unavailable"
    assert transaction["distance"] is None
    assert transaction["map_recommendation"] == "defer"
    assert transaction["map_reason"] == "track_lost"


@pytest.mark.parametrize(
    ("extra", "expected_reason"),
    [
        ({"identity_handle": "different_goat"}, "identity_mismatch"),
        ({"identity_status": "ambiguous"}, "identity_ambiguous"),
        (
            {
                "negative_evidence": {
                    "present": True,
                    "reliable": True,
                    "reason": "expected_visible_location_inspected_empty",
                }
            },
            "reliable_negative_location_evidence",
        ),
    ],
)
def test_identity_ambiguity_substitution_or_negative_evidence_defers(
    extra: dict[str, object],
    expected_reason: str,
) -> None:
    """Unsupported identity or reliable negative evidence should prevent map pursuit."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
    kwargs: dict[str, object] = {
        "maternal": None if "negative_evidence" in extra else (2.0, 0.0),
        "time_value": 1.0,
        "step_index": 1,
        "proximity_predicate": None if "negative_evidence" in extra else "proximity:mom:far",
    }
    kwargs.update(extra)

    row = _update_phase4d(ctx, _observation(**kwargs))  # type: ignore[arg-type]
    transaction = _transaction(row)

    assert transaction["map_recommendation"] == "defer"
    assert transaction["map_reason"] == expected_reason
    assert transaction["expected_successor"] is None


def test_follow_selection_arms_expectation_without_changing_existing_action_state() -> None:
    """A legacy-selected FollowMom may arm comparison only, never alter selection state."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    ctx.env_last_action = "policy:sentinel"

    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )
    transaction = _transaction(row)

    assert transaction["gate_comparison"] == "agree_follow_trigger"
    assert transaction["candidate_comparison"] == "agree_follow_candidate"
    assert transaction["selection_comparison"] == "agree_follow_selected"
    assert transaction["pending_expected_armed"] is True
    assert isinstance(ctx.navmap_followmom_compare_pending, FollowMomExpectedPendingV1)
    assert ctx.env_last_action == "policy:sentinel"
    assert transaction["map_can_override"] is False


def test_map_do_not_follow_against_legacy_candidate_records_useful_overtrigger() -> None:
    """A permissive legacy FollowMom candidate can be marked as useful compare evidence."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4d(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )
    transaction = _transaction(row)

    assert transaction["map_recommendation"] == "do_not_follow"
    assert transaction["selection_comparison"] == "disagree_follow_selected"
    assert transaction["disagreement_assessment"] == "potentially_useful_legacy_overtrigger"
    assert transaction["pending_expected_armed"] is False
    assert ctx.navmap_followmom_compare_pending is None


def test_map_follow_blocked_by_legacy_records_potential_harm_without_authority() -> None:
    """A map-only locomotor trigger blocked by legacy safety should be labeled, not executed."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0, posture="fallen"),
    )

    selected = _run_legacy_selector(ctx)
    gate, candidate, chosen = _legacy_values_from_debug(ctx)
    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=gate,
        legacy_effective_candidate=candidate,
        selected_policy=chosen or selected,
    )
    transaction = _transaction(row)

    assert transaction["map_recommendation"] == "follow_mom"
    assert gate is False
    assert candidate is False
    assert selected in {"policy:stand_up", "policy:recover_fall"}
    assert transaction["disagreement_assessment"] == "potentially_harmful_map_overtrigger_if_authoritative"
    assert transaction["pending_expected_armed"] is False
    assert transaction["protected_safety_can_be_overridden"] is False


def test_map_defer_with_legacy_follow_records_explicit_fallback() -> None:
    """A lost-track map DEFER should make the continuing legacy action visibly a fallback."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    for index in (1, 2, 3):
        _update_phase4d(
            ctx,
            _observation(maternal=None, time_value=float(index), step_index=index, proximity_predicate=None),
        )

    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )
    transaction = _transaction(row)

    assert transaction["map_recommendation"] == "defer"
    assert transaction["fallback_required"] is True
    assert transaction["fallback_source"] == "legacy_bodymap_policy_runtime"
    assert transaction["disagreement_assessment"] == "map_deferred_legacy_fallback"
    assert ctx.navmap_followmom_compare_pending is None


def test_map_follow_loses_arbitration_without_becoming_a_behavioral_override() -> None:
    """Another legacy winner should be recorded as arbitration rather than map execution."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy="policy:rest",
    )
    transaction = _transaction(row)

    assert transaction["selection_comparison"] == "map_follow_not_selected"
    assert transaction["disagreement_assessment"] == "arbitration_difference"
    assert transaction["pending_expected_armed"] is False
    assert ctx.navmap_followmom_compare_pending is None


def test_reduce_separation_expected_successor_reports_success() -> None:
    """A meaningful observed distance reduction should satisfy the compact expectation."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    outcome = row["observed_outcome"]

    assert outcome["outcome"] == "success"
    assert outcome["reason"] == "observed_separation_reduced"
    assert outcome["relation_residual"]["distance_delta"] == pytest.approx(-1.0)
    assert row["pending_expected"] is False


def test_reduce_separation_expected_successor_reports_failure_without_progress() -> None:
    """Unchanged far separation should fail the applied one-step expectation."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )

    assert row["observed_outcome"]["outcome"] == "failure"
    assert row["observed_outcome"]["reason"] == "observed_separation_not_reduced"


def test_near_regulation_expectation_succeeds_when_relation_remains_near() -> None:
    """A near/receding FollowMom action should succeed when the next relation remains near."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((0.4, 0.6, 0.8)):
        _update_phase4d(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate="proximity:mom:close",
            ),
        )
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(
            maternal=(0.95, 0.0),
            time_value=3.0,
            step_index=3,
            proximity_predicate="proximity:mom:close",
        ),
        applied_policy=_FOLLOW_MOM,
    )

    assert row["observed_outcome"]["outcome"] == "success"
    assert row["observed_outcome"]["reason"] == "observed_relation_remains_near"


def test_near_regulation_expectation_fails_after_material_separation_increase() -> None:
    """A near/receding action should fail when the next distance exceeds the allowed envelope."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((0.4, 0.6, 0.8)):
        _update_phase4d(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate="proximity:mom:close",
            ),
        )
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(maternal=(1.2, 0.0), time_value=3.0, step_index=3),
        applied_policy=_FOLLOW_MOM,
    )

    assert row["observed_outcome"]["outcome"] == "failure"
    assert row["observed_outcome"]["reason"] == "observed_near_separation_increased_beyond_allowed_limit"


def test_applied_follow_with_missing_current_exact_localization_reports_unknown() -> None:
    """Identity continuity must not fabricate an expected-outcome coordinate."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
        applied_policy=_FOLLOW_MOM,
    )

    assert row["observed_outcome"]["outcome"] == "unknown"
    assert row["observed_outcome"]["observed_distance"] is None
    assert row["observed_outcome"]["reason"] == "current_exact_identity_matched_localization_unavailable"


def test_different_applied_policy_closes_expectation_as_not_applied() -> None:
    """An expectation must not judge FollowMom when the environment received another action."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    row = _update_phase4d(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=1.0, step_index=1),
        applied_policy="policy:rest",
    )

    assert row["observed_outcome"]["outcome"] == "not_applied"
    assert row["observed_outcome"]["action_applied"] == "policy:rest"
    assert row["observed_outcome"]["reason"] == "armed_followmom_was_not_the_applied_action"


def test_navmap_runtime_closes_pending_expectation_from_pending_action_register() -> None:
    """The live runtime should pass the action applied to the current observation into Phase 4D."""
    ctx = _ctx_with_bodymap()
    first = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, first)
    seqerr_update_from_obs(ctx, first)
    navmap_ctx_observation_update_step_v1(ctx, first)
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )
    ctx.navmap_pending_action_v1 = _FOLLOW_MOM

    second = _observation(maternal=(2.0, 0.0), time_value=1.0, step_index=1)
    update_body_world_from_obs(ctx, second)
    seqerr_update_from_obs(ctx, second)
    navmap_ctx_observation_update_step_v1(ctx, second)

    assert ctx.navmap_pending_action_v1 is None
    assert ctx.navmap_followmom_compare_last_outcome is not None
    assert ctx.navmap_followmom_compare_last_outcome.outcome == "success"
    assert ctx.navmap_followmom_compare_last_outcome.action_applied == _FOLLOW_MOM


def test_real_policy_runtime_exposes_gate_candidate_and_winner_for_compare() -> None:
    """The live legacy selector should supply all three Phase 4D differential fields."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    selected = _run_legacy_selector(ctx)
    gate, candidate, chosen = _legacy_values_from_debug(ctx)
    row = followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=gate,
        legacy_effective_candidate=candidate,
        selected_policy=chosen or selected,
    )
    transaction = _transaction(row)

    assert gate is True
    assert candidate is True
    assert selected == _FOLLOW_MOM
    assert transaction["legacy_gate_triggered"] is True
    assert transaction["legacy_effective_candidate"] is True
    assert transaction["selected_policy"] == _FOLLOW_MOM
    assert transaction["pending_expected_armed"] is True


def test_histories_are_bounded_json_safe_and_records_are_immutable() -> None:
    """Phase 4D traces should remain bounded, JSON-safe, and immutable at record level."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_compare_history_limit = 2
    ctx.navmap_followmom_compare_outcome_history_limit = 2

    for index, distance in enumerate((4.0, 3.5, 3.0, 2.5)):
        _update_phase4d(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
            applied_policy=_FOLLOW_MOM if index > 0 else None,
        )
        followmom_compare_selection_step_v1(
            ctx,
            legacy_gate_triggered=True,
            legacy_effective_candidate=True,
            selected_policy=_FOLLOW_MOM,
        )

    assert len(ctx.navmap_followmom_compare_history) == 2
    assert len(ctx.navmap_followmom_compare_outcome_history) == 2
    json.dumps(ctx.navmap_followmom_compare_history)
    json.dumps(ctx.navmap_followmom_compare_outcome_history)
    json.dumps(cca8_run.followmom_compare_summary_v1(ctx))

    transaction = ctx.navmap_followmom_compare_transaction
    assert isinstance(transaction, FollowMomCompareTransactionV1)
    with pytest.raises(FrozenInstanceError):
        transaction.map_reason = "mutated"  # type: ignore[misc]


def test_selection_compare_does_not_mutate_bodymap_or_navmap_revisions() -> None:
    """The post-selection comparator should modify only bounded Phase 4D context records."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    assert ctx.body_world is not None
    assert ctx.navmap_maternal_map is not None
    body_before = ctx.body_world.to_dict()
    maternal_ref_before = ctx.navmap_maternal_state.stable_ref
    maternal_signature_before = ctx.navmap_maternal_map.content_signature()

    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    assert ctx.body_world.to_dict() == body_before
    assert ctx.navmap_maternal_state.stable_ref == maternal_ref_before
    assert ctx.navmap_maternal_map.content_signature() == maternal_signature_before
    assert ctx.navmap_followmom_compare_transaction is not None
    assert ctx.navmap_followmom_compare_transaction.as_dict()["creates_navmap_revision"] is False


def test_renderer_and_runner_alias_expose_compare_authority_boundary() -> None:
    """Terminal and runner compatibility surfaces should report the compare-only contract."""
    ctx = _ctx_with_bodymap()
    _update_phase4d(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )

    lines = render_followmom_compare_lines_v1(ctx)
    runner_lines = cca8_run.render_followmom_compare_lines_v1(ctx)

    assert lines == runner_lines
    assert lines[0] == "FOLLOWMOM PHASE 4D COMPARE:"
    assert any("authority=compare_only" in line for line in lines)
    assert any("follow_mom_authority=legacy_bodymap_policy_runtime" in line for line in lines)
    assert any("map_can_override=False" in line for line in lines)
    assert any("recommendation=follow_mom" in line for line in lines)


def test_disabled_compare_path_remains_behaviorally_inert() -> None:
    """Disabling Phase 4D should leave no transaction or pending expectation."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_compare_enabled = False

    row = _update_phase4d(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )

    assert row["status"] == "disabled"
    assert row["authority"] == "compare_only"
    assert row["map_can_override"] is False
    assert ctx.navmap_followmom_compare_transaction is None
    assert ctx.navmap_followmom_compare_pending is None
    assert FollowMomMapRecommendationV1.FOLLOW_MOM.value == "follow_mom"


def test_cycle_json_exposes_phase4d_followmom_compare_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should include the compare-only FollowMom trace."""
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
    summary = ctx.cycle_json_records[-1]["followmom_compare"]
    transaction = summary["transaction"]
    assert summary["schema"] == "followmom_compare_summary_v1"
    assert summary["phase"] == "4D"
    assert summary["authority"] == "compare_only"
    assert summary["follow_mom_authority"] == "legacy_bodymap_policy_runtime"
    assert summary["legacy_executes"] is True
    assert summary["map_can_override"] is False
    assert transaction["map_can_trigger_follow_mom"] is False


def test_phase4d_context_defaults_are_bounded_and_compare_only() -> None:
    """The context should expose bounded comparison settings with no initial transaction."""
    ctx = Ctx()

    assert ctx.navmap_followmom_compare_enabled is True
    assert ctx.navmap_followmom_compare_history_limit > 0
    assert ctx.navmap_followmom_compare_outcome_history_limit > 0
    assert ctx.navmap_followmom_compare_minimum_distance_reduction > 0.0
    assert ctx.navmap_followmom_compare_maximum_allowed_distance_increase >= 0.0
    assert ctx.navmap_followmom_compare_maximum_predicted_region_radius > 0.0
    assert ctx.navmap_followmom_compare_transaction is None
    assert ctx.navmap_followmom_compare_pending is None
    assert ctx.navmap_followmom_compare_last_outcome is None
    assert ctx.navmap_followmom_compare_history == []
    assert ctx.navmap_followmom_compare_outcome_history == []
