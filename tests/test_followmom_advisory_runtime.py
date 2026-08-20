# -*- coding: utf-8 -*-
"""Phase 4E-A tests for non-binding FollowMom advisory behavior."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

import cca8_navmap_runtime
import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_followmom_advisory import (
    FollowMomAdvisoryKindV1,
    FollowMomAdvisoryV1,
    followmom_advisory_observation_step_v1,
    followmom_advisory_selection_step_v1,
    render_followmom_advisory_lines_v1,
)
from cca8_followmom_compare import (
    followmom_compare_observation_step_v1,
    followmom_compare_selection_step_v1,
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
    negative_evidence: bool | dict[str, object] | None = None,
) -> EnvObservation:
    """Return one deterministic maternal observation for advisory tests."""
    predicates = [f"posture:{posture}"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    metadata: dict[str, object] = {
        "scenario_stage": "phase4e_advisory_test",
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
    if negative_evidence is not None:
        metadata["maternal_negative_evidence"] = negative_evidence
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


def _select(
    ctx: Ctx,
    *,
    gate: bool | None,
    candidate: bool | None,
    selected: str | None,
) -> dict[str, object]:
    """Finalize Phase 4D comparison and refresh Phase 4E-A advice."""
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=gate,
        legacy_effective_candidate=candidate,
        selected_policy=selected,
    )
    return followmom_advisory_selection_step_v1(ctx)


def _advisory(summary: dict[str, object]) -> dict[str, object]:
    """Return the advisory dictionary from one active summary."""
    row = summary.get("advisory")
    assert isinstance(row, dict)
    return row


def test_far_current_exact_relation_advises_follow_recruitment_without_authority() -> None:
    """Supported far geometry should produce explicit non-binding start advice."""
    ctx = _ctx_with_bodymap()

    summary = _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )
    advisory = _advisory(summary)

    assert advisory["kind"] == "follow_supported"
    assert advisory["scope"] == "start"
    assert advisory["map_recommendation"] == "follow_mom"
    assert advisory["authority"] == "advisory_only"
    assert advisory["legacy_executes"] is True
    assert advisory["map_can_override"] is False
    assert advisory["map_can_trigger_follow_mom"] is False
    assert advisory["map_can_suppress_follow_mom"] is False
    assert advisory["policy_selection_mutation_allowed"] is False


def test_near_stable_relation_advises_not_to_recruit_new_followmom() -> None:
    """Near stable separation should advise against starting a new trajectory."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((0.60, 0.62, 0.64)):
        summary = _observe(
            ctx,
            _observation(
                maternal=(distance, 0.0),
                time_value=float(index),
                step_index=index,
                proximity_predicate="proximity:mom:close",
            ),
        )

    advisory = _advisory(summary)
    assert advisory["kind"] == "do_not_recruit"
    assert advisory["scope"] == "start"
    assert advisory["map_recommendation"] == "do_not_follow"
    assert advisory["recommended_response"] == "do_not_recruit_new_followmom_trajectory"


def test_far_approaching_without_prior_applied_follow_is_start_advice_not_continuation() -> None:
    """Relative approach alone must not be interpreted as successful ongoing following."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        summary = _observe(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    advisory = _advisory(summary)
    assert advisory["map_reason"] == "far_but_separation_already_approaching"
    assert advisory["kind"] == "do_not_recruit"
    assert advisory["scope"] == "start"
    assert advisory["prior_outcome"] is None


def test_far_approaching_after_immediately_prior_follow_success_advises_continuation() -> None:
    """Successful applied FollowMom should distinguish continuation from initial applicability."""
    ctx = _ctx_with_bodymap()

    _observe(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    _observe(
        ctx,
        _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    summary = _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=2.0, step_index=2),
        applied_policy=_FOLLOW_MOM,
    )
    advisory = _advisory(summary)

    assert advisory["map_recommendation"] == "do_not_follow"
    assert advisory["map_reason"] == "far_but_separation_already_approaching"
    assert advisory["kind"] == "continue_supported"
    assert advisory["scope"] == "continue"
    assert advisory["prior_outcome"] == "success"
    assert advisory["prior_action_applied"] == _FOLLOW_MOM
    assert advisory["recommended_response"] == "advise_continuation_while_progress_remains_supported"


def test_old_follow_success_is_not_reused_after_its_immediate_transaction_window() -> None:
    """One old success must not generate continuation advice indefinitely."""
    ctx = _ctx_with_bodymap()

    _observe(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    _observe(
        ctx,
        _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=2.0, step_index=2),
        applied_policy=_FOLLOW_MOM,
    )

    summary = _observe(
        ctx,
        _observation(maternal=(2.5, 0.0), time_value=3.0, step_index=3),
    )
    advisory = _advisory(summary)

    assert advisory["map_reason"] == "far_but_separation_already_approaching"
    assert advisory["kind"] == "do_not_recruit"
    assert advisory["prior_outcome"] is None


def test_failed_expected_relation_takes_precedence_over_new_map_advice() -> None:
    """A failed applied FollowMom expectation should request explicit outcome review."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    summary = _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    advisory = _advisory(summary)

    assert advisory["kind"] == "followmom_outcome_failure"
    assert advisory["severity"] == "warning"
    assert advisory["scope"] == "outcome_review"
    assert advisory["prior_outcome"] == "failure"
    assert advisory["fallback_required"] is True
    assert advisory["outcome_review_recommended"] is True


def test_unknown_expected_relation_requests_resampling_and_legacy_fallback() -> None:
    """Missing current exact localization should keep the outcome uncertain."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    summary = _observe(
        ctx,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
        applied_policy=_FOLLOW_MOM,
    )
    advisory = _advisory(summary)

    assert advisory["kind"] == "followmom_outcome_unknown"
    assert advisory["severity"] == "caution"
    assert advisory["prior_outcome"] == "unknown"
    assert advisory["fallback_required"] is True
    assert advisory["resample_recommended"] is True


def test_different_applied_action_reports_handoff_mismatch_without_rewriting_action() -> None:
    """An armed FollowMom expectation must not judge an action the environment did not receive."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    summary = _observe(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=1.0, step_index=1),
        applied_policy="policy:rest",
    )
    advisory = _advisory(summary)

    assert advisory["kind"] == "action_handoff_mismatch"
    assert advisory["prior_outcome"] == "not_applied"
    assert advisory["prior_action_applied"] == "policy:rest"
    assert advisory["advice_is_behavioral_command"] is False


def test_deferred_map_advice_explicitly_preserves_legacy_fallback() -> None:
    """Ambiguous maternal identity should advise defer, resample, and legacy fallback."""
    ctx = _ctx_with_bodymap()

    summary = _observe(
        ctx,
        _observation(
            maternal=(3.0, 0.0),
            time_value=0.0,
            step_index=0,
            identity_status="ambiguous",
            identity_candidates=["goat:mom", "goat:other"],
        ),
    )
    advisory = _advisory(summary)

    assert advisory["kind"] == "map_deferred"
    assert advisory["scope"] == "fallback"
    assert advisory["map_recommendation"] == "defer"
    assert advisory["fallback_required"] is True
    assert advisory["fallback_source"] == "legacy_bodymap_policy_runtime"
    assert advisory["resample_recommended"] is True


def test_map_follow_blocked_by_legacy_filters_preserves_the_filter_and_selected_policy() -> None:
    """Advisory must not bypass a safety, sequence, topology, or other legacy filter."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    summary = _select(ctx, gate=True, candidate=False, selected="policy:stand_up")
    advisory = _advisory(summary)

    assert advisory["kind"] == "legacy_block_preserved"
    assert advisory["severity"] == "warning"
    assert advisory["legacy_filter_preserved"] is True
    assert advisory["protected_safety_can_be_overridden"] is False
    assert advisory["selected_policy_before_advisory"] == "policy:stand_up"
    assert advisory["selected_policy_after_advisory"] == "policy:stand_up"
    assert advisory["legacy_action_unchanged"] is True


def test_map_follow_losing_arbitration_records_review_without_overriding_winner() -> None:
    """A stronger legacy winner should remain selected when FollowMom was only a candidate."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    summary = _select(ctx, gate=True, candidate=True, selected="policy:rest")
    advisory = _advisory(summary)

    assert advisory["kind"] == "arbitration_review"
    assert advisory["scope"] == "selection_review"
    assert advisory["selected_policy"] == "policy:rest"
    assert advisory["disagreement_review_recommended"] is True
    assert advisory["map_can_override"] is False


def test_map_do_not_recruit_against_legacy_follow_warns_but_cannot_suppress() -> None:
    """The advisory may flag a permissive legacy follow without suppressing it."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _observe(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    summary = _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    advisory = _advisory(summary)

    assert advisory["kind"] == "do_not_recruit"
    assert advisory["severity"] == "warning"
    assert advisory["selected_policy"] == _FOLLOW_MOM
    assert advisory["fallback_required"] is True
    assert advisory["disagreement_review_recommended"] is True
    assert advisory["map_can_suppress_follow_mom"] is False
    assert advisory["selected_policy_after_advisory"] == _FOLLOW_MOM


def test_successful_continuation_never_overrides_a_new_legacy_block_or_other_winner() -> None:
    """Prior progress must yield to current legacy filtering and protected execution."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(5.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    _observe(
        ctx,
        _observation(maternal=(4.0, 0.0), time_value=1.0, step_index=1),
        applied_policy=_FOLLOW_MOM,
    )
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=2.0, step_index=2),
        applied_policy=_FOLLOW_MOM,
    )

    summary = _select(ctx, gate=True, candidate=False, selected="policy:stand_up")
    advisory = _advisory(summary)

    assert advisory["kind"] != "continue_supported"
    assert advisory["selected_policy"] == "policy:stand_up"
    assert advisory["selected_policy_after_advisory"] == "policy:stand_up"
    assert advisory["protected_safety_can_be_overridden"] is False


def test_observation_and_selection_refresh_one_history_row_per_transaction() -> None:
    """Provisional advice should be replaced, not duplicated, after selection."""
    ctx = _ctx_with_bodymap()

    observation_summary = _observe(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )
    assert _advisory(observation_summary)["source_stage"] == "observation"
    assert len(ctx.navmap_followmom_advisory_history) == 1

    selection_summary = _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)
    assert _advisory(selection_summary)["source_stage"] == "selection"
    assert len(ctx.navmap_followmom_advisory_history) == 1
    assert ctx.navmap_followmom_advisory_history[0]["source_stage"] == "selection"


def test_advisory_history_is_bounded_json_safe_and_record_is_immutable() -> None:
    """Phase 4E-A records should remain bounded, serializable, and frozen."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_advisory_history_limit = 2

    for index, distance in enumerate((4.0, 3.5, 3.0, 2.5)):
        _observe(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )
        _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    assert len(ctx.navmap_followmom_advisory_history) == 2
    json.dumps(ctx.navmap_followmom_advisory_history)
    json.dumps(cca8_run.followmom_advisory_summary_v1(ctx))

    advisory = ctx.navmap_followmom_advisory
    assert isinstance(advisory, FollowMomAdvisoryV1)
    with pytest.raises(FrozenInstanceError):
        advisory.reason = "mutated"  # type: ignore[misc]


def test_advisory_refresh_does_not_mutate_bodymap_navmap_or_selected_action() -> None:
    """Phase 4E-A should modify only its bounded context records."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    followmom_compare_selection_step_v1(
        ctx,
        legacy_gate_triggered=True,
        legacy_effective_candidate=True,
        selected_policy=_FOLLOW_MOM,
    )
    assert ctx.body_world is not None
    assert ctx.navmap_maternal_map is not None
    body_before = ctx.body_world.to_dict()
    map_signature_before = ctx.navmap_maternal_map.content_signature()
    pending_before = ctx.navmap_followmom_compare_pending

    summary = followmom_advisory_selection_step_v1(ctx)
    advisory = _advisory(summary)

    assert ctx.body_world.to_dict() == body_before
    assert ctx.navmap_maternal_map.content_signature() == map_signature_before
    assert ctx.navmap_followmom_compare_pending is pending_before
    assert advisory["selected_policy_before_advisory"] == _FOLLOW_MOM
    assert advisory["selected_policy_after_advisory"] == _FOLLOW_MOM


def test_disabled_advisory_and_disabled_compare_paths_are_inert() -> None:
    """Feature flags should return explicit statuses without creating advisory records."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_followmom_advisory_enabled = False
    _update_dependencies(
        ctx,
        _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0),
    )
    followmom_compare_observation_step_v1(ctx)

    disabled = followmom_advisory_observation_step_v1(ctx)
    assert disabled["status"] == "disabled"
    assert disabled["map_can_override"] is False
    assert ctx.navmap_followmom_advisory is None
    assert ctx.navmap_followmom_advisory_history == []

    ctx.navmap_followmom_advisory_enabled = True
    ctx.navmap_followmom_compare_enabled = False
    compare_disabled = followmom_advisory_observation_step_v1(ctx)
    assert compare_disabled["status"] == "compare_disabled"
    assert ctx.navmap_followmom_advisory is None


def test_renderer_and_runner_alias_expose_start_continue_and_authority_contract() -> None:
    """Terminal and compatibility surfaces should show the Phase 4E-A contract."""
    ctx = _ctx_with_bodymap()
    _observe(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _select(ctx, gate=True, candidate=True, selected=_FOLLOW_MOM)

    lines = render_followmom_advisory_lines_v1(ctx)
    runner_lines = cca8_run.render_followmom_advisory_lines_v1(ctx)

    assert lines == runner_lines
    assert lines[0] == "FOLLOWMOM PHASE 4E-A ADVISORY:"
    assert any("authority=advisory_only" in line for line in lines)
    assert any("scope=start" in line for line in lines)
    assert any("selection_unchanged=True" in line for line in lines)


def test_navmap_runtime_runs_observation_advisory_after_phase4d_compare() -> None:
    """The live NavMap observation bridge should populate provisional Phase 4E-A advice."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)

    navmap_ctx_observation_update_step_v1(ctx, env_obs)

    assert ctx.navmap_followmom_advisory is not None
    assert ctx.navmap_followmom_advisory.source_stage == "observation"
    assert ctx.navmap_followmom_advisory.kind is FollowMomAdvisoryKindV1.FOLLOW_SUPPORTED


def test_navmap_runtime_compare_failure_clears_stale_advisory(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A failed Phase 4D observation update must not leave old active advice visible."""
    ctx = _ctx_with_bodymap()
    first_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, first_obs)
    seqerr_update_from_obs(ctx, first_obs)
    cca8_navmap_runtime.navmap_ctx_observation_update_step_v1(ctx, first_obs)
    assert ctx.navmap_followmom_advisory is not None

    def _raise_compare(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("compare observation failed")

    monkeypatch.setattr(cca8_navmap_runtime, "followmom_compare_observation_step_v1", _raise_compare)
    next_obs = _observation(maternal=(2.5, 0.0), time_value=1.0, step_index=1)
    update_body_world_from_obs(ctx, next_obs)
    seqerr_update_from_obs(ctx, next_obs)
    cca8_navmap_runtime.navmap_ctx_observation_update_step_v1(ctx, next_obs)

    assert ctx.navmap_followmom_advisory is None
    assert ctx.navmap_followmom_advisory_last_update is not None
    assert ctx.navmap_followmom_advisory_last_update["status"] == "dependency_error"
    assert ctx.navmap_followmom_advisory_last_update["reason"] == "phase4d_compare_observation_update_failed"


def test_runner_compare_selection_failure_replaces_provisional_advice(
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    """A failed Phase 4D selection update must replace, not expose, observation-only advice."""
    ctx = _ctx_with_bodymap()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    world = WorldGraph()
    world.ensure_anchor("NOW")

    def _raise_selection(*_args: object, **_kwargs: object) -> None:
        raise RuntimeError("compare selection failed")

    monkeypatch.setattr(cca8_run, "followmom_compare_selection_step_v1", _raise_selection)
    cca8_run.run_env_closed_loop_steps(
        HybridEnvironment(),
        world,
        Drives(),
        ctx,
        PolicyRuntime(CATALOG_GATES),
        1,
    )
    capsys.readouterr()

    assert ctx.navmap_followmom_advisory is None
    assert ctx.navmap_followmom_advisory_last_update is not None
    assert ctx.navmap_followmom_advisory_last_update["status"] == "dependency_error"
    assert ctx.navmap_followmom_advisory_last_update["reason"] == "phase4d_compare_selection_update_failed"
    assert ctx.cycle_json_records[-1]["followmom_advisory"]["status"] == "dependency_error"


def test_cycle_json_exposes_phase4e_advisory_without_behavioral_authority(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should include the non-binding advisory trace."""
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
    summary = ctx.cycle_json_records[-1]["followmom_advisory"]
    advisory = summary["advisory"]
    assert summary["schema"] == "followmom_advisory_summary_v1"
    assert summary["phase"] == "4E-A"
    assert summary["authority"] == "advisory_only"
    assert summary["follow_mom_authority"] == "legacy_bodymap_policy_runtime"
    assert summary["legacy_executes"] is True
    assert summary["map_can_override"] is False
    assert advisory["selected_policy_before_advisory"] == advisory["selected_policy_after_advisory"]


def test_phase4e_context_defaults_are_bounded_and_advisory_only() -> None:
    """The context should start with a bounded, enabled, empty advisory surface."""
    ctx = Ctx()

    assert ctx.navmap_followmom_advisory_enabled is True
    assert ctx.navmap_followmom_advisory_history_limit > 0
    assert ctx.navmap_followmom_advisory is None
    assert ctx.navmap_followmom_advisory_last_update is None
    assert ctx.navmap_followmom_advisory_history == []
