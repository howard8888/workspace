# -*- coding: utf-8 -*-
"""Phase 3A tests for the StandUp map-native compare transaction."""

from __future__ import annotations

import json

import pytest

import cca8_run
from cca8_controller import Drives
from cca8_context import Ctx
from cca8_env import EnvObservation, HybridEnvironment
from cca8_navmap_kernel import (
    NavBodyStateInterpretationV1,
    NavSourceClassV1,
    get_element,
)
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_standup_compare import (
    StandUpMapRecommendationV1,
    render_standup_compare_lines_v1,
    standup_compare_observation_step_v1,
    standup_compare_selection_step_v1,
)
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap() -> Ctx:
    """Return one context with the authoritative legacy BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(*predicates: str) -> EnvObservation:
    """Return one minimal interpreted observation packet."""
    return EnvObservation(
        raw_sensors={},
        predicates=list(predicates),
        cues=[],
        env_meta={"scenario_stage": "phase3a_test"},
    )


def _shadow_and_compare(ctx: Ctx, env_obs: EnvObservation, *, update_bodymap: bool = True) -> dict[str, object]:
    """Update BodyMap optionally, update Phase 2B, and run Phase 3A observation work."""
    if update_bodymap:
        update_body_world_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    return standup_compare_observation_step_v1(ctx)


def _arm_fallen_standup(ctx: Ctx) -> None:
    """Create fallen map evidence and arm one legacy-selected StandUp expectation."""
    _shadow_and_compare(ctx, _observation("posture:fallen"))
    standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )


def test_fallen_geometry_recommends_standup_and_builds_expected_upright_successor() -> None:
    """Fresh maintained FALLEN_LIKE geometry should independently recommend StandUp."""
    ctx = _ctx_with_bodymap()

    summary = _shadow_and_compare(ctx, _observation("posture:fallen"))
    transaction = summary["transaction"]

    assert isinstance(transaction, dict)
    assert transaction["authority_level"] == "compare_dual_run"
    assert transaction["authority"] == "compare_only"
    assert transaction["legacy_executes"] is True
    assert transaction["map_can_override"] is False
    assert transaction["execution_source"] == "legacy_bodymap_policy_runtime"
    assert transaction["fallback_status"] == "not_applicable_compare_only"
    assert transaction["map_body_interpretation"] == "fallen_like"
    assert transaction["map_recommendation"] == StandUpMapRecommendationV1.STAND_UP.value
    assert transaction["expected_successor_body_state"]["interpretation"] == "standing_like"
    assert transaction["expected_successor_ref"]["map_id"].startswith("goat_self_ground_expected_standup_v2_t")

    compare = ctx.navmap_standup_compare_transaction
    assert compare is not None
    assert compare.expected_successor_map is not None
    assert compare.expected_successor_map.provenance.source_class is NavSourceClassV1.EXPECTED
    assert compare.expected_successor_map.map_id != ctx.navmap_v2_shadow_body_ground.map_id


def test_expected_successor_changes_task_level_self_geometry_but_preserves_ground() -> None:
    """The expected map should project upright SELF geometry without inventing a motor trajectory."""
    ctx = _ctx_with_bodymap()
    _shadow_and_compare(ctx, _observation("posture:fallen"))

    transaction = ctx.navmap_standup_compare_transaction
    assert transaction is not None
    expected = transaction.expected_successor_map
    maintained = ctx.navmap_v2_shadow_body_ground
    assert expected is not None
    assert maintained is not None

    for element_id in ("self_body", "self_head", "self_foot"):
        assert get_element(expected, element_id).geometry != get_element(maintained, element_id).geometry
        assert get_element(expected, element_id).provenance.source_class is NavSourceClassV1.EXPECTED

    assert get_element(expected, "ground_surface") == get_element(maintained, "ground_surface")
    assert all("joint" not in element.role and "hoof_path" not in element.role for element in expected.elements)


def test_standing_geometry_recommends_do_not_stand_without_expected_successor() -> None:
    """Fresh maintained STANDING_LIKE geometry should reject StandUp applicability."""
    ctx = _ctx_with_bodymap()

    summary = _shadow_and_compare(ctx, _observation("posture:standing"))
    transaction = summary["transaction"]

    assert isinstance(transaction, dict)
    assert transaction["map_body_interpretation"] == "standing_like"
    assert transaction["map_recommendation"] == StandUpMapRecommendationV1.DO_NOT_STAND.value
    assert transaction["expected_successor_ref"] is None
    assert transaction["expected_successor_body_state"] is None


def test_stale_or_invalidated_shadow_defers_instead_of_using_unsupported_posture() -> None:
    """Unsupported maintained content must not produce an actionable map recommendation."""
    ctx = _ctx_with_bodymap()
    _shadow_and_compare(ctx, _observation("posture:standing"))
    _shadow_and_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)

    stale_summary = _shadow_and_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    stale = stale_summary["transaction"]
    assert isinstance(stale, dict)
    assert stale["support_status"] == "stale"
    assert stale["map_recommendation"] == StandUpMapRecommendationV1.DEFER.value
    assert stale["map_reason"] == "support_stale"
    assert stale["expected_successor_ref"] is None

    invalidated_summary = _shadow_and_compare(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    invalidated = invalidated_summary["transaction"]
    assert isinstance(invalidated, dict)
    assert invalidated["map_maintained"] is False
    assert invalidated["map_body_interpretation"] == "unknown"
    assert invalidated["map_recommendation"] == StandUpMapRecommendationV1.DEFER.value
    assert invalidated["map_reason"] == "shadow_not_maintained"


def test_selection_comparison_records_agreement_and_arms_expected_without_changing_action() -> None:
    """The legacy-selected StandUp should be observed and armed, never replaced."""
    ctx = _ctx_with_bodymap()
    _shadow_and_compare(ctx, _observation("posture:fallen"))
    ctx.env_last_action = "policy:stand_up"

    summary = standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )
    transaction = summary["transaction"]

    assert isinstance(transaction, dict)
    assert transaction["gate_comparison"] == "agree_trigger"
    assert transaction["selection_comparison"] == "agree_standup_selected"
    assert transaction["pending_expected_armed"] is True
    assert summary["pending_expected"] is True
    assert ctx.env_last_action == "policy:stand_up"


def test_map_legacy_disagreement_is_recorded_without_arming_or_overriding() -> None:
    """A map recommendation must remain diagnostic when the legacy winner differs."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    posture_id = ctx.body_ids["posture"]
    before_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    _shadow_and_compare(ctx, _observation("posture:fallen"), update_bodymap=False)
    ctx.env_last_action = "policy:follow_mom"

    summary = standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=False,
        selected_policy="policy:follow_mom",
    )
    transaction = summary["transaction"]

    assert isinstance(transaction, dict)
    assert transaction["legacy_bodymap_posture"] == "standing"
    assert transaction["gate_comparison"] == "disagree_map_trigger_legacy_no"
    assert transaction["selection_comparison"] == "map_standup_not_selected"
    assert summary["pending_expected"] is False
    assert ctx.navmap_standup_compare_pending is None
    assert ctx.env_last_action == "policy:follow_mom"
    after_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_expected_successor_success_uses_next_evidence_map_and_clears_pending() -> None:
    """Applied StandUp followed by upright evidence should close as a successful transaction."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    next_obs = _observation("posture:standing")
    update_body_world_from_obs(ctx, next_obs)
    navmap_v2_shadow_observation_step_v1(ctx, next_obs)
    summary = standup_compare_observation_step_v1(ctx, applied_policy="policy:stand_up")
    outcome = summary["observed_outcome"]

    assert isinstance(outcome, dict)
    assert outcome["outcome"] == "success"
    assert outcome["observed_interpretation"] == "standing_like"
    assert outcome["match_status"] == "exact"
    assert outcome["structured_residual"]["has_content_difference"] is False
    assert outcome["evidence_map_ref"]["map_id"].endswith("o000002")
    assert summary["pending_expected"] is False
    assert ctx.navmap_standup_compare_pending is None


def test_expected_successor_failure_records_structured_residual() -> None:
    """Applied StandUp followed by fallen evidence should close as a geometric failure."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    next_obs = _observation("posture:fallen")
    update_body_world_from_obs(ctx, next_obs)
    navmap_v2_shadow_observation_step_v1(ctx, next_obs)
    summary = standup_compare_observation_step_v1(ctx, applied_policy="policy:stand_up")
    outcome = summary["observed_outcome"]

    assert isinstance(outcome, dict)
    assert outcome["outcome"] == "failure"
    assert outcome["observed_interpretation"] == "fallen_like"
    assert outcome["structured_residual"]["has_content_difference"] is True
    assert set(outcome["changed_element_ids"]) == {"self_body", "self_foot", "self_head"}


def test_expected_successor_unknown_and_not_applied_are_explicit_bounded_outcomes() -> None:
    """Missing evidence and a non-applied action should not be mistaken for success or failure."""
    ctx_unknown = _ctx_with_bodymap()
    _arm_fallen_standup(ctx_unknown)
    unknown_obs = _observation("proximity:mom:far")
    navmap_v2_shadow_observation_step_v1(ctx_unknown, unknown_obs)
    unknown_summary = standup_compare_observation_step_v1(ctx_unknown, applied_policy="policy:stand_up")
    unknown_outcome = unknown_summary["observed_outcome"]

    assert isinstance(unknown_outcome, dict)
    assert unknown_outcome["outcome"] == "unknown"
    assert unknown_outcome["observed_interpretation"] == "unknown"
    assert unknown_outcome["match_status"] is None
    assert unknown_outcome["structured_residual"] is None

    ctx_not_applied = _ctx_with_bodymap()
    _arm_fallen_standup(ctx_not_applied)
    fallen_obs = _observation("posture:fallen")
    navmap_v2_shadow_observation_step_v1(ctx_not_applied, fallen_obs)
    skipped_summary = standup_compare_observation_step_v1(
        ctx_not_applied,
        applied_policy="policy:follow_mom",
    )
    skipped_outcome = skipped_summary["observed_outcome"]

    assert isinstance(skipped_outcome, dict)
    assert skipped_outcome["outcome"] == "not_applied"
    assert skipped_outcome["reason"] == "armed_standup_was_not_the_applied_action"
    assert skipped_outcome["match_status"] is None


def test_live_observation_runtime_captures_applied_action_before_clearing_pending_v1() -> None:
    """The existing runtime hook should finalize Phase 3A using the action applied this step."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)
    ctx.navmap_pending_action_v1 = "policy:stand_up"

    standing_obs = _observation("posture:standing")
    update_body_world_from_obs(ctx, standing_obs)
    v1_update = navmap_ctx_observation_update_step_v1(ctx, standing_obs)

    assert v1_update["schema"] == "navmap_observation_update_v1"
    assert ctx.navmap_pending_action_v1 is None
    assert ctx.navmap_standup_compare_last_outcome is not None
    assert ctx.navmap_standup_compare_last_outcome.outcome == "success"
    assert ctx.navmap_standup_compare_last_outcome.action_applied == "policy:stand_up"


def test_live_closed_loop_records_exact_legacy_gate_and_selected_standup(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The runner should compare against PolicyRuntime's actual trigger set and winner."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    world = WorldGraph()
    world.ensure_anchor("NOW")
    world.ensure_anchor("NOW_ORIGIN")
    policy_runtime = PolicyRuntime(CATALOG_GATES)

    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        policy_runtime,
        1,
    )
    capsys.readouterr()

    summary = ctx.navmap_standup_compare_last_update
    assert isinstance(summary, dict)
    transaction = summary["transaction"]
    assert isinstance(transaction, dict)
    assert transaction["legacy_gate_triggered"] is True
    assert transaction["selected_policy"] == "policy:stand_up"
    assert transaction["gate_comparison"] == "agree_trigger"
    assert transaction["selection_comparison"] == "agree_standup_selected"
    assert ctx.env_last_action == "policy:stand_up"


def test_compare_histories_are_bounded_and_json_safe() -> None:
    """Transaction and outcome telemetry should remain bounded and serializable."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_compare_history_limit = 2
    ctx.navmap_standup_compare_outcome_history_limit = 1

    for _ in range(3):
        _shadow_and_compare(ctx, _observation("posture:fallen"))
        standup_compare_selection_step_v1(
            ctx,
            legacy_gate_triggered=True,
            selected_policy="policy:stand_up",
        )
        next_obs = _observation("posture:standing")
        navmap_v2_shadow_observation_step_v1(ctx, next_obs)
        standup_compare_observation_step_v1(ctx, applied_policy="policy:stand_up")

    assert len(ctx.navmap_standup_compare_history) == 2
    assert len(ctx.navmap_standup_compare_outcome_history) == 1
    json.dumps(ctx.navmap_standup_compare_history, allow_nan=False, sort_keys=True)
    json.dumps(ctx.navmap_standup_compare_outcome_history, allow_nan=False, sort_keys=True)


def test_renderer_exposes_map_legacy_expected_and_authority_boundaries() -> None:
    """Human inspection should make compare-only status and both paths explicit."""
    ctx = _ctx_with_bodymap()
    _shadow_and_compare(ctx, _observation("posture:fallen"))
    standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )

    text = "\n".join(render_standup_compare_lines_v1(ctx))

    assert "STANDUP PHASE 3A COMPARE:" in text
    assert "authority=compare_only legacy_executes=True map_can_override=False" in text
    assert "fallback=not_applicable_compare_only" in text
    assert "derived=fallen_like" in text
    assert "recommendation=stand_up" in text
    assert "expected=goat_self_ground_expected_standup_v2_t000001@r1 derived=standing_like" in text
    assert "gate_comparison=agree_trigger" in text
    assert "selection_comparison=agree_standup_selected" in text


def test_disabled_compare_path_has_no_compare_state_side_effects() -> None:
    """The Phase 3A flag should leave the existing Phase 2B shadow untouched."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_compare_enabled = False
    update_body_world_from_obs(ctx, _observation("posture:fallen"))
    navmap_v2_shadow_observation_step_v1(ctx, _observation("posture:fallen"))

    row = standup_compare_observation_step_v1(ctx)

    assert row["status"] == "disabled"
    assert ctx.navmap_standup_compare_transaction is None
    assert ctx.navmap_standup_compare_pending is None
    assert ctx.navmap_standup_compare_history == []
    assert ctx.navmap_v2_shadow_state is not None
    assert ctx.navmap_v2_shadow_state.stable_body_state.interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE
