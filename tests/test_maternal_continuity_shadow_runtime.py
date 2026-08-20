# -*- coding: utf-8 -*-
"""Phase 4C tests for maternal identity continuity and localization shadowing."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json

import pytest

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, HybridEnvironment
from cca8_maternal_continuity import (
    MaternalContinuityShadowStateV1,
    maternal_continuity_shadow_observation_step_v1,
    render_maternal_continuity_shadow_lines_v1,
)
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import maternal_temporal_shadow_observation_step_v1
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_temporal import TemporalContext
from cca8_world_graph import WorldGraph


def _ctx_with_bodymap() -> Ctx:
    """Return a context with the compatibility BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(
    *,
    maternal: tuple[float, float] | None,
    time_value: float,
    step_index: int,
    identity_handle: str | None = None,
    identity_status: str | None = None,
    identity_candidates: list[str] | None = None,
    observability: str | None = None,
    observability_reason: str | None = None,
    negative_evidence: bool | dict[str, object] | None = None,
    blackout: bool = False,
    proximity_predicate: str | None = "proximity:mom:far",
) -> EnvObservation:
    """Return one deterministic observation with optional Phase 4C inspection metadata."""
    predicates = ["posture:standing"]
    if proximity_predicate is not None:
        predicates.append(proximity_predicate)
    meta: dict[str, object] = {
        "scenario_stage": "phase4c_test",
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
        meta["maternal_identity_handle"] = identity_handle
    if identity_status is not None:
        meta["maternal_identity_status"] = identity_status
    if identity_candidates is not None:
        meta["maternal_identity_candidates"] = list(identity_candidates)
    if observability is not None:
        meta["maternal_observability"] = observability
    if observability_reason is not None:
        meta["maternal_observability_reason"] = observability_reason
    if negative_evidence is not None:
        meta["maternal_negative_evidence"] = negative_evidence
    if blackout:
        meta["newborn_obs_blackout"] = True
        meta["newborn_obs_blackout_kind"] = "phase4c_test_dropout"
    return EnvObservation(
        raw_sensors={"distance_to_mom": 999.0},
        predicates=predicates,
        cues=[],
        env_meta=meta,
    )


def _update_dependencies(ctx: Ctx, env_obs: EnvObservation) -> None:
    """Run BodyMap, Sequential/Error, Phase 2, Phase 4A, and Phase 4B only."""
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    maternal_temporal_shadow_observation_step_v1(ctx, env_obs)


def _update_phase4c(ctx: Ctx, env_obs: EnvObservation) -> dict[str, object]:
    """Run all observation-side dependencies followed by Phase 4C."""
    _update_dependencies(ctx, env_obs)
    return maternal_continuity_shadow_observation_step_v1(ctx, env_obs)


def _follow_mom_gate() -> object:
    """Return the unchanged legacy FollowMom PolicyGate."""
    return next(gate for gate in CATALOG_GATES if gate.name == "policy:follow_mom")


def test_visible_maternal_evidence_acquires_identity_role_and_exact_localization() -> None:
    """Visible matched evidence should initialize distinct identity, role, and location fields."""
    ctx = _ctx_with_bodymap()

    row = _update_phase4c(
        ctx,
        _observation(maternal=(3.0, 4.0), time_value=0.0, step_index=0),
    )

    assert row["status"] == "acquired"
    assert row["tracked_identity_handle"] == "maternal_individual"
    assert row["identity_support"] == "supported"
    assert row["maternal_role_relation"] == "maternal_caregiver_of"
    assert row["role_retained"] is True
    assert row["observed_entity_inherits_maternal_role"] is True
    assert row["existence_status"] == "observed"
    assert row["observability"] == "observed"
    assert row["localization_status"] == "current_exact"
    assert row["localization_authoritative"] is True
    assert row["current_location"] == {"x": 3.0, "y": 4.0}
    assert row["track_status"] == "active"


def test_one_missing_position_retains_identity_and_role_but_not_current_coordinate() -> None:
    """A missing packet should coast a prior track without fabricating an observed point."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
    )

    assert row["identity_support"] == "retained"
    assert row["role_retained"] is True
    assert row["existence_status"] == "presumed_continuing"
    assert row["current_location"] is None
    assert row["current_exact_coordinate_fabricated"] is False
    assert row["last_supported_location"] == {"x": 3.0, "y": 0.0}
    assert row["last_supported_map_ref"]["map_id"] == "goat_self_maternal_v2"
    assert row["localization_status"] == "predicted_region"
    assert row["localization_authoritative"] is False
    assert row["predicted_region"]["authoritative_current_location"] is False
    assert row["track_status"] == "coasting"


def test_phase4b_motion_projects_a_shifting_and_widening_region() -> None:
    """A supported approach rate may shift a bounded prior but never claim current observation."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4c(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )

    first_missing = _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=3.0, step_index=3, proximity_predicate=None),
    )
    second_missing = _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=4.0, step_index=4, proximity_predicate=None),
    )

    first_region = first_missing["predicted_region"]
    second_region = second_missing["predicted_region"]
    assert first_region["method"] == "phase4b_polar_rate_projection"
    assert first_region["motion_applied"] is True
    assert first_region["center"]["x"] == pytest.approx(2.0)
    assert second_region["center"]["x"] == pytest.approx(1.0)
    assert second_region["radius"] > first_region["radius"]
    assert first_missing["current_location"] is None
    assert second_missing["current_location"] is None


def test_repeated_missingness_loses_localization_track_not_identity_or_role() -> None:
    """The bounded track should become unlocalized and lost while maternal meaning persists."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))

    rows = [
        _update_phase4c(
            ctx,
            _observation(maternal=None, time_value=float(index), step_index=index, proximity_predicate=None),
        )
        for index in (1, 2, 3)
    ]

    assert [row["track_status"] for row in rows] == ["coasting", "unlocalized", "lost"]
    assert rows[-1]["localization_status"] == "unlocalized"
    assert rows[-1]["predicted_region"] is None
    assert rows[-1]["identity_support"] == "retained"
    assert rows[-1]["existence_status"] == "presumed_continuing"
    assert rows[-1]["role_retained"] is True
    assert rows[-1]["lost_track_deletes_identity"] is False
    assert rows[-1]["lost_track_deletes_role"] is False


def test_compatible_reappearance_reacquires_the_same_identity_after_lost_track() -> None:
    """Equivalent identity evidence should refresh localization without creating a new individual."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
    for index in (1, 2, 3):
        _update_phase4c(
            ctx,
            _observation(maternal=None, time_value=float(index), step_index=index, proximity_predicate=None),
        )

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=(1.5, 0.5),
            time_value=4.0,
            step_index=4,
            identity_handle="maternal_individual",
        ),
    )

    assert row["status"] == "reacquired"
    assert row["reacquisition"] == "reacquired"
    assert row["tracked_identity_handle"] == "maternal_individual"
    assert row["observed_identity_handle"] == "maternal_individual"
    assert row["identity_support"] == "supported"
    assert row["role_retained"] is True
    assert row["track_status"] == "active"
    assert row["current_location"] == {"x": 1.5, "y": 0.5}


def test_different_identity_at_old_coordinate_does_not_inherit_role_or_track() -> None:
    """Coordinate coincidence must not grant maternal identity, role, or exact maternal localization."""
    ctx = _ctx_with_bodymap()
    initial = _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=(2.0, 0.0),
            time_value=1.0,
            step_index=1,
            identity_handle="different_goat",
        ),
    )

    assert row["identity_support"] == "mismatch"
    assert ctx.navmap_maternal_last_update["input_classification"] == "maternal_identity_mismatch"
    assert ctx.navmap_maternal_last_update["evidence_readout"]["valid"] is False
    assert ctx.navmap_maternal_state.evidence_map.relations == ()
    assert row["tracked_identity_handle"] == "maternal_individual"
    assert row["observed_identity_handle"] == "different_goat"
    assert row["observed_candidate_location"] == {"x": 2.0, "y": 0.0}
    assert row["current_location"] is None
    assert row["localization_status"] == "unlocalized"
    assert row["track_status"] == "identity_mismatch"
    assert row["observed_entity_inherits_maternal_role"] is False
    assert row["role_retained"] is True
    assert row["last_supported_map_ref"] == initial["last_supported_map_ref"]


def test_identity_substitution_resets_phase4b_trajectory_support() -> None:
    """A different observed individual must not continue the previous maternal motion sequence."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4c(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )
    assert ctx.navmap_maternal_temporal_last_update["readout"]["trend"] == "approaching"

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=(2.0, 0.0),
            time_value=3.0,
            step_index=3,
            identity_handle="different_goat",
        ),
    )

    temporal = ctx.navmap_maternal_temporal_last_update
    assert row["track_status"] == "identity_mismatch"
    assert temporal["status"] == "unknown"
    assert temporal["sample"]["valid"] is False
    assert temporal["sample"]["reason"] == "current_geometry_unknown:identity_mismatch"
    assert temporal["readout"]["trend"] == "unknown"


def test_ambiguous_candidates_are_order_independent_and_choose_no_arbitrary_identity() -> None:
    """Candidate insertion order must not choose an individual or inherit the maternal role."""
    rows = []
    for candidates in (["maternal_individual", "different_goat"], ["different_goat", "maternal_individual"]):
        ctx = _ctx_with_bodymap()
        _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
        rows.append(
            _update_phase4c(
                ctx,
                _observation(
                    maternal=(2.0, 0.0),
                    time_value=1.0,
                    step_index=1,
                    identity_candidates=list(candidates),
                ),
            )
        )

    for row in rows:
        assert row["identity_support"] == "ambiguous"
        assert row["observed_identity_handle"] is None
        assert row["localization_status"] == "ambiguous"
        assert row["track_status"] == "ambiguous"
        assert row["observed_entity_inherits_maternal_role"] is False
        assert row["current_location"] is None
    assert rows[0]["reason"] == rows[1]["reason"]
    assert rows[0]["observability_reason"] == rows[1]["observability_reason"]


def test_reliable_negative_evidence_is_stronger_than_an_ordinary_missing_packet() -> None:
    """Explicit reliable empty-location evidence should withdraw the track immediately."""
    ctx_missing = _ctx_with_bodymap()
    _update_phase4c(ctx_missing, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
    ordinary = _update_phase4c(
        ctx_missing,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
    )

    ctx_negative = _ctx_with_bodymap()
    _update_phase4c(ctx_negative, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
    negative = _update_phase4c(
        ctx_negative,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            negative_evidence={
                "present": True,
                "reliable": True,
                "reason": "expected_visible_location_inspected_empty",
            },
        ),
    )

    assert ordinary["track_status"] == "coasting"
    assert ordinary["existence_status"] == "presumed_continuing"
    assert negative["status"] == "negative_evidence"
    assert negative["observability"] == "negative_expected_location"
    assert negative["track_status"] == "lost"
    assert negative["existence_status"] == "uncertain"
    assert negative["identity_support"] == "retained"
    assert negative["role_retained"] is True


def test_conflicting_visible_position_and_negative_evidence_preserves_ambiguous() -> None:
    """Contradictory inspection fields should defer rather than select an arbitrary truth."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=(1.0, 0.0),
            time_value=1.0,
            step_index=1,
            negative_evidence={"present": True, "reliable": True, "reason": "conflicting_test_evidence"},
        ),
    )

    assert row["identity_support"] == "ambiguous"
    assert row["localization_status"] == "ambiguous"
    assert row["track_status"] == "ambiguous"
    assert row["current_location"] is None


def test_same_identity_reappearing_after_negative_evidence_reacquires_track() -> None:
    """Reliable negative evidence should not permanently delete maternal identity or role."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=0.0, step_index=0))
    _update_phase4c(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            negative_evidence=True,
        ),
    )

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=(1.0, 0.0),
            time_value=2.0,
            step_index=2,
            identity_handle="maternal_individual",
        ),
    )

    assert row["status"] == "reacquired"
    assert row["existence_status"] == "observed"
    assert row["track_status"] == "active"
    assert row["negative_evidence"]["reliable_count"] == 0
    assert row["role_retained"] is True


def test_explicit_occlusion_preserves_identity_with_non_authoritative_region() -> None:
    """Synthetic occlusion metadata may explain missingness without claiming native occluder sensing."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            observability="occluded",
            observability_reason="synthetic_rock_occluder_for_inspection",
        ),
    )

    assert row["observability"] == "occluded"
    assert "synthetic_rock_occluder" in row["observability_reason"]
    assert row["identity_support"] == "retained"
    assert row["localization_status"] == "predicted_region"
    assert row["localization_authoritative"] is False
    assert row["adapter_limitation"] == "native_runtime_observed_position_or_generic_unavailable_blackout_only"


def test_native_blackout_metadata_maps_only_to_generic_sensor_dropout() -> None:
    """The current environment blackout should not be mislabeled as true occlusion."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))

    row = _update_phase4c(
        ctx,
        _observation(
            maternal=None,
            time_value=1.0,
            step_index=1,
            proximity_predicate=None,
            blackout=True,
        ),
    )

    assert row["observability"] == "sensor_dropout"
    assert row["observability_reason"] == "newborn_observation_blackout:phase4c_test_dropout"
    assert row["observability"] != "occluded"


def test_missing_and_reappearance_do_not_bridge_phase4b_motion_history() -> None:
    """Identity may persist while the temporal decoder still requires new contiguous samples."""
    ctx = _ctx_with_bodymap()
    for index, distance in enumerate((5.0, 4.0, 3.0)):
        _update_phase4c(
            ctx,
            _observation(maternal=(distance, 0.0), time_value=float(index), step_index=index),
        )
    assert ctx.navmap_maternal_temporal_last_update["readout"]["trend"] == "approaching"

    missing = _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=3.0, step_index=3, proximity_predicate=None),
    )
    returned = _update_phase4c(
        ctx,
        _observation(maternal=(2.0, 0.0), time_value=4.0, step_index=4),
    )

    assert missing["identity_support"] == "retained"
    assert missing["track_status"] == "coasting"
    assert returned["reacquisition"] == "reacquired"
    temporal = ctx.navmap_maternal_temporal_last_update
    assert temporal["status"] == "insufficient_history"
    assert temporal["readout"]["valid_sample_count"] == 1
    assert temporal["readout"]["trend"] == "unknown"


def test_phase4c_transaction_creates_or_mutates_no_navmap_revision() -> None:
    """The external continuity overlay must not create or mutate immutable NavMaps."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    _update_dependencies(ctx, env_obs)
    evidence_before = ctx.navmap_maternal_evidence_map.to_bytes()
    stable_before = ctx.navmap_maternal_map.to_bytes()
    evidence_ref_before = ctx.navmap_maternal_state.evidence_ref
    stable_ref_before = ctx.navmap_maternal_state.stable_ref

    row = maternal_continuity_shadow_observation_step_v1(ctx, env_obs)

    assert row["creates_navmap_revision"] is False
    assert ctx.navmap_maternal_evidence_map.to_bytes() == evidence_before
    assert ctx.navmap_maternal_map.to_bytes() == stable_before
    assert ctx.navmap_maternal_state.evidence_ref == evidence_ref_before
    assert ctx.navmap_maternal_state.stable_ref == stable_ref_before


def test_phase4c_does_not_mutate_bodymap_or_follow_mom_gate() -> None:
    """The shadow must leave the compatibility body and policy-authority paths unchanged."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    _update_dependencies(ctx, env_obs)
    mom_id = ctx.body_ids["mom"]
    body_tags_before = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    world = WorldGraph()
    world.ensure_anchor("NOW")
    gate = _follow_mom_gate()
    gate_before = gate.trigger(world, Drives(), ctx)

    row = maternal_continuity_shadow_observation_step_v1(ctx, env_obs)

    body_tags_after = set(ctx.body_world._bindings[mom_id].tags)  # pylint: disable=protected-access
    gate_after = gate.trigger(world, Drives(), ctx)
    assert body_tags_after == body_tags_before
    assert gate_after == gate_before
    assert row["authority"] == "shadow_only"
    assert row["follow_mom_authority"] == "legacy_bodymap_policy_runtime"
    assert row["map_can_trigger_follow_mom"] is False


def test_disabled_phase4c_path_has_no_context_side_effects() -> None:
    """The explicit runtime flag should disable the new overlay cleanly."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    _update_dependencies(ctx, env_obs)
    ctx.navmap_maternal_continuity_shadow_enabled = False

    row = maternal_continuity_shadow_observation_step_v1(ctx, env_obs)

    assert row["status"] == "disabled"
    assert ctx.navmap_maternal_continuity_state is None
    assert ctx.navmap_maternal_continuity_last_update is None
    assert ctx.navmap_maternal_continuity_history == []


def test_history_is_bounded_and_strictly_json_safe() -> None:
    """Phase 4C traces should remain bounded and contain no non-JSON runtime objects."""
    ctx = _ctx_with_bodymap()
    ctx.navmap_maternal_continuity_history_limit = 2

    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
    )
    _update_phase4c(ctx, _observation(maternal=(2.0, 0.0), time_value=2.0, step_index=2))

    assert len(ctx.navmap_maternal_continuity_history) == 2
    json.dumps(ctx.navmap_maternal_continuity_history, allow_nan=False, sort_keys=True)
    assert ctx.navmap_maternal_continuity_history[-1]["status"] == "reacquired"


def test_state_record_is_frozen_and_enforces_current_location_authority_invariant() -> None:
    """The typed record should be immutable and reject a detached exact-coordinate claim."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    state = ctx.navmap_maternal_continuity_state
    assert isinstance(state, MaternalContinuityShadowStateV1)

    with pytest.raises(FrozenInstanceError):
        state.track_status = state.track_status  # type: ignore[misc]
    with pytest.raises(ValueError, match="non-authoritative continuity state"):
        replace(state, localization_authoritative=False)


def test_renderer_exposes_identity_localization_and_environment_limit() -> None:
    """The terminal trace should show the Phase 4C distinctions and authority boundary."""
    ctx = _ctx_with_bodymap()
    _update_phase4c(ctx, _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0))
    _update_phase4c(
        ctx,
        _observation(maternal=None, time_value=1.0, step_index=1, proximity_predicate=None),
    )

    text = "\n".join(render_maternal_continuity_shadow_lines_v1(ctx))

    assert "MATERNAL CONTINUITY PHASE 4C SHADOW:" in text
    assert "authority=shadow_only" in text
    assert "follow_mom_authority=legacy_bodymap_policy_runtime" in text
    assert "role_retained=True" in text
    assert "localization=predicted_region authoritative=False" in text
    assert "track=coasting" in text
    assert "creates_navmap_revision=False" in text
    assert "occlusion/out-of-field/negative evidence require explicit inspection metadata" in text


def test_live_navmap_observation_runtime_populates_phase4c_without_changing_v1_return() -> None:
    """The existing runtime callback should append Phase 4C after the Phase 4A/4B path."""
    ctx = _ctx_with_bodymap()
    env_obs = _observation(maternal=(3.0, 0.0), time_value=0.0, step_index=0)
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)

    v1_update = navmap_ctx_observation_update_step_v1(ctx, env_obs)

    assert v1_update["schema"] == "navmap_observation_update_v1"
    assert ctx.navmap_maternal_continuity_last_update is not None
    assert ctx.navmap_maternal_continuity_last_update["phase"] == "4C"
    assert ctx.navmap_maternal_continuity_last_update["status"] == "acquired"
    assert ctx.navmap_maternal_continuity_last_update["map_can_trigger_follow_mom"] is False


def test_cycle_json_exposes_phase4c_maternal_continuity_shadow(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """Machine-readable cycle output should include the Phase 4C shadow summary."""
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
    summary = ctx.cycle_json_records[-1]["maternal_continuity_shadow"]
    assert summary["schema"] == "maternal_continuity_shadow_summary_v1"
    assert summary["phase"] == "4C"
    assert summary["authority"] == "shadow_only"
    assert summary["map_can_trigger_follow_mom"] is False
    assert summary["tracked_identity_handle"] == "maternal_individual"


def test_phase4c_context_defaults_are_bounded_and_non_authoritative() -> None:
    """The context should expose explicit bounded configuration with no initial belief."""
    ctx = Ctx()

    assert ctx.navmap_maternal_continuity_shadow_enabled is True
    assert ctx.navmap_maternal_continuity_history_limit > 0
    assert ctx.navmap_maternal_continuity_max_coast_missing_observations >= 0
    assert (
        ctx.navmap_maternal_continuity_max_unlocalized_missing_observations
        >= ctx.navmap_maternal_continuity_max_coast_missing_observations
    )
    assert ctx.navmap_maternal_continuity_state is None
    assert ctx.navmap_maternal_continuity_last_update is None
    assert ctx.navmap_maternal_continuity_history == []
