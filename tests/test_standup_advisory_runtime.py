# -*- coding: utf-8 -*-
"""Phase 3B tests for the StandUp map-native advisory surface."""

from __future__ import annotations

import json
from dataclasses import replace

import pytest

import cca8_run
from cca8_controller import Drives
from cca8_context import Ctx
from cca8_env import EnvObservation, HybridEnvironment
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_standup_compare import (
    StandUpAdvisoryKindV1,
    StandUpAdvisorySeverityV1,
    StandUpMapRecommendationV1,
    render_standup_advisory_lines_v1,
    standup_advisory_observation_step_v1,
    standup_advisory_selection_step_v1,
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
        env_meta={"scenario_stage": "phase3b_test"},
    )


def _compare_observation(
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


def _select_and_advise(
    ctx: Ctx,
    *,
    legacy_gate_triggered: bool,
    selected_policy: str,
) -> dict[str, object]:
    """Record the legacy selection and finalize the Phase 3B advisory."""
    standup_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=legacy_gate_triggered,
        selected_policy=selected_policy,
    )
    return standup_advisory_selection_step_v1(ctx)


def _arm_fallen_standup(ctx: Ctx) -> None:
    """Create fallen evidence and arm one legacy-selected StandUp expectation."""
    _compare_observation(ctx, _observation("posture:fallen"))
    _select_and_advise(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )


def _advisory_row(summary: dict[str, object]) -> dict[str, object]:
    """Return the advisory row from one summary with a useful assertion."""
    row = summary.get("advisory")
    assert isinstance(row, dict)
    return row


def test_fresh_agreement_produces_clear_advisory_without_authority() -> None:
    """Agreement should be explicitly clear while preserving the legacy executor."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:fallen"))
    summary = _select_and_advise(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )
    row = _advisory_row(summary)

    assert summary["status"] == "clear"
    assert row["phase"] == "3B"
    assert row["authority_level"] == "advisory"
    assert row["authority"] == "advisory_only"
    assert row["kind"] == StandUpAdvisoryKindV1.CLEAR.value
    assert row["severity"] == StandUpAdvisorySeverityV1.INFO.value
    assert row["active"] is False
    assert row["legacy_executes"] is True
    assert row["map_can_override"] is False
    assert row["protected_safety_can_be_overridden"] is False
    assert row["fallback_required"] is False


def test_aging_support_warns_but_remains_actionable_without_forcing_fallback() -> None:
    """One missing observation should produce caution while Phase 2B remains actionable."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:fallen"))
    _compare_observation(
        ctx,
        _observation("proximity:mom:far"),
        update_bodymap=False,
    )

    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.SUPPORT_AGING.value
    assert row["severity"] == StandUpAdvisorySeverityV1.CAUTION.value
    assert row["support_status"] == "aging"
    assert row["map_recommendation"] == StandUpMapRecommendationV1.STAND_UP.value
    assert row["fallback_required"] is False
    assert row["resample_recommended"] is True


def test_stale_or_invalidated_posture_requests_bodymap_fallback_and_resampling() -> None:
    """Unsupported maintained posture should become an explicit bounded advisory."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:standing"))
    _compare_observation(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    _compare_observation(ctx, _observation("proximity:mom:far"), update_bodymap=False)

    stale_summary = standup_advisory_observation_step_v1(ctx)
    stale = _advisory_row(stale_summary)
    assert stale["kind"] == StandUpAdvisoryKindV1.POSTURE_UNSUPPORTED.value
    assert stale["support_status"] == "stale"
    assert stale["map_recommendation"] == StandUpMapRecommendationV1.DEFER.value
    assert stale["fallback_required"] is True
    assert stale["fallback_source"] == "bodymap_policy_runtime"
    assert stale["resample_recommended"] is True

    _compare_observation(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    invalidated_summary = standup_advisory_observation_step_v1(ctx)
    invalidated = _advisory_row(invalidated_summary)
    assert invalidated["kind"] == StandUpAdvisoryKindV1.POSTURE_UNSUPPORTED.value
    assert invalidated["support_status"] == "invalidated"
    assert invalidated["map_body_interpretation"] == "unknown"
    assert invalidated["fallback_required"] is True


def test_expected_transform_failure_is_flagged_without_executing_a_map_action() -> None:
    """An unavailable expected successor should request review and BodyMap fallback."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:fallen"))
    transaction = ctx.navmap_standup_compare_transaction
    assert transaction is not None
    ctx.navmap_standup_compare_transaction = replace(
        transaction,
        map_recommendation=StandUpMapRecommendationV1.DEFER,
        map_reason="expected_successor_unavailable:ValueError",
        expected_successor_map=None,
    )

    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.EXPECTED_TRANSFORM_FAILURE.value
    assert row["severity"] == StandUpAdvisorySeverityV1.WARNING.value
    assert row["transform_review_recommended"] is True
    assert row["fallback_required"] is True
    assert row["requested_followup_is_behavioral_command"] is False


def test_map_legacy_disagreement_is_advisory_only_and_preserves_bodymap_and_action() -> None:
    """The advisory may flag disagreement but cannot alter the legacy winner or BodyMap."""
    ctx = _ctx_with_bodymap()
    update_body_world_from_obs(ctx, _observation("posture:standing"))
    posture_id = ctx.body_ids["posture"]
    before_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    _compare_observation(ctx, _observation("posture:fallen"), update_bodymap=False)
    ctx.env_last_action = "policy:follow_mom"

    summary = _select_and_advise(
        ctx,
        legacy_gate_triggered=False,
        selected_policy="policy:follow_mom",
    )
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.MAP_LEGACY_DISAGREEMENT.value
    assert row["disagreement_review_recommended"] is True
    assert row["fallback_required"] is True
    assert row["selected_policy_before_advisory"] == "policy:follow_mom"
    assert row["selected_policy_after_advisory"] == "policy:follow_mom"
    assert ctx.env_last_action == "policy:follow_mom"
    after_tags = set(ctx.body_world._bindings[posture_id].tags)  # pylint: disable=protected-access
    assert after_tags == before_tags


def test_advisory_cannot_block_legacy_safety_when_map_says_do_not_stand() -> None:
    """A legacy-selected safety StandUp remains selected despite map disagreement."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:standing"))
    ctx.env_last_action = "policy:stand_up"

    summary = _select_and_advise(
        ctx,
        legacy_gate_triggered=True,
        selected_policy="policy:stand_up",
    )
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.MAP_LEGACY_DISAGREEMENT.value
    assert row["map_recommendation"] == StandUpMapRecommendationV1.DO_NOT_STAND.value
    assert row["selection_comparison"] == "disagree_standup_selected"
    assert row["protected_safety_can_be_overridden"] is False
    assert ctx.env_last_action == "policy:stand_up"


def test_failed_standup_outcome_becomes_highest_priority_advisory() -> None:
    """A failed applied StandUp should be flagged on the immediately following transaction."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    _compare_observation(
        ctx,
        _observation("posture:fallen"),
        applied_policy="policy:stand_up",
    )
    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.STANDUP_OUTCOME_FAILURE.value
    assert row["severity"] == StandUpAdvisorySeverityV1.WARNING.value
    assert row["prior_outcome_transaction_no"] == 1
    assert row["prior_outcome"] == "failure"
    assert row["outcome_review_recommended"] is True
    assert row["fallback_required"] is True


def test_unknown_outcome_requests_resampling_without_declaring_failure() -> None:
    """Applied StandUp with missing next posture should request resampling."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    _compare_observation(
        ctx,
        _observation("proximity:mom:far"),
        update_bodymap=False,
        applied_policy="policy:stand_up",
    )
    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.STANDUP_OUTCOME_UNKNOWN.value
    assert row["prior_outcome"] == "unknown"
    assert row["resample_recommended"] is True
    assert row["outcome_review_recommended"] is True


def test_non_applied_armed_action_flags_handoff_mismatch() -> None:
    """An armed StandUp not applied by the environment should remain a diagnostic handoff issue."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    _compare_observation(
        ctx,
        _observation("posture:fallen"),
        applied_policy="policy:follow_mom",
    )
    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert row["kind"] == StandUpAdvisoryKindV1.ACTION_HANDOFF_MISMATCH.value
    assert row["prior_outcome"] == "not_applied"
    assert row["outcome_review_recommended"] is True
    assert row["recommended_response"] == "retain_legacy_action_and_review_action_handoff"


def test_successful_outcome_does_not_leave_a_persistent_failure_advisory() -> None:
    """A successful previous transaction should allow the current standing transaction to clear."""
    ctx = _ctx_with_bodymap()
    _arm_fallen_standup(ctx)

    _compare_observation(
        ctx,
        _observation("posture:standing"),
        applied_policy="policy:stand_up",
    )
    summary = standup_advisory_observation_step_v1(ctx)
    row = _advisory_row(summary)

    assert ctx.navmap_standup_compare_last_outcome is not None
    assert ctx.navmap_standup_compare_last_outcome.outcome == "success"
    assert row["kind"] == StandUpAdvisoryKindV1.CLEAR.value
    assert row["active"] is False
    assert row["prior_outcome"] == "success"


def test_advisory_history_keeps_one_bounded_json_safe_row_per_transaction() -> None:
    """Observation and selection refreshes should update, not duplicate, one transaction row."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_advisory_history_limit = 1

    _compare_observation(ctx, _observation("posture:standing"))
    standup_advisory_observation_step_v1(ctx)
    _select_and_advise(
        ctx,
        legacy_gate_triggered=False,
        selected_policy="policy:follow_mom",
    )
    assert len(ctx.navmap_standup_advisory_history) == 1
    assert ctx.navmap_standup_advisory_history[0]["source_stage"] == "selection"

    _compare_observation(ctx, _observation("posture:standing"))
    standup_advisory_observation_step_v1(ctx)
    _select_and_advise(
        ctx,
        legacy_gate_triggered=False,
        selected_policy="policy:follow_mom",
    )

    assert len(ctx.navmap_standup_advisory_history) == 1
    assert ctx.navmap_standup_advisory_history[0]["transaction_no"] == 2
    json.dumps(ctx.navmap_standup_advisory_history, allow_nan=False, sort_keys=True)


def test_renderer_exposes_advisory_reason_fallback_and_safety_boundary() -> None:
    """Human inspection should make the Phase 3B recommendation and non-authority explicit."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:standing"))
    _compare_observation(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    _compare_observation(ctx, _observation("proximity:mom:far"), update_bodymap=False)
    standup_advisory_observation_step_v1(ctx)

    text = "\n".join(render_standup_advisory_lines_v1(ctx))

    assert "STANDUP PHASE 3B ADVISORY:" in text
    assert "authority=advisory_only legacy_executes=True map_can_override=False" in text
    assert "protected_safety_can_be_overridden=False" in text
    assert "advisory=posture_unsupported" in text
    assert "fallback_required=True fallback_source=bodymap_policy_runtime" in text
    assert "resample=True" in text


def test_live_closed_loop_finalizes_selection_advisory_without_changing_winner(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The runner should finalize Phase 3B only after the legacy winner already exists."""
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

    row = ctx.navmap_standup_advisory_last_update
    assert isinstance(row, dict)
    assert row["source_stage"] == "selection"
    assert row["kind"] == StandUpAdvisoryKindV1.CLEAR.value
    assert row["selected_policy"] == "policy:stand_up"
    assert row["selected_policy_before_advisory"] == row["selected_policy_after_advisory"]
    assert ctx.env_last_action == "policy:stand_up"


def test_cycle_json_record_contains_phase3b_advisory_summary(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """The existing machine-readable cycle trace should expose the advisory surface."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    world = WorldGraph()
    world.ensure_anchor("NOW")
    world.ensure_anchor("NOW_ORIGIN")

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
    advisory = ctx.cycle_json_records[-1]["standup_advisory"]
    assert advisory["phase"] == "3B"
    assert advisory["advisory"]["selected_policy"] == "policy:stand_up"



def test_compare_disabled_prevents_advisory_from_reusing_an_old_transaction() -> None:
    """The advisory must not revive a stale compare transaction when Phase 3A is off."""
    ctx = _ctx_with_bodymap()
    _compare_observation(ctx, _observation("posture:fallen"))
    assert ctx.navmap_standup_compare_transaction is not None
    ctx.navmap_standup_compare_enabled = False

    summary = standup_advisory_observation_step_v1(ctx)

    assert summary["status"] == "compare_disabled"
    assert ctx.navmap_standup_advisory is None
    assert ctx.navmap_standup_advisory_history == []

def test_disabled_advisory_path_has_no_advisory_state_side_effects() -> None:
    """The Phase 3B flag should leave compare/shadow records available and untouched."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_standup_advisory_enabled = False
    _compare_observation(ctx, _observation("posture:fallen"))

    summary = standup_advisory_observation_step_v1(ctx)

    assert summary["status"] == "disabled"
    assert ctx.navmap_standup_advisory is None
    assert ctx.navmap_standup_advisory_last_update is None
    assert ctx.navmap_standup_advisory_history == []
    assert ctx.navmap_standup_compare_transaction is not None
    assert ctx.navmap_v2_shadow_state is not None
