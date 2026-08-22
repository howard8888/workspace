# -*- coding: utf-8 -*-
"""Phase 5 tests for feeding close-up maps and the first true WNM zoom round-trip."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
from types import SimpleNamespace

import pytest

import cca8_policy_runtime
import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, EnvState, HybridEnvironment, PerceptionAdapter
from cca8_feeding import (
    FeedingContactEventV1,
    FeedingExpectedSuccessorV1,
    FeedingExpectationKindV1,
    FeedingRelationOverlayV1,
    feeding_latch_evidence_v1,
    feeding_milk_evidence_v1,
    feeding_operative_readout_v1,
    feeding_reset_v1,
    feeding_selection_step_v1,
    feeding_summary_v1,
    feeding_wnm_observation_step_v1,
    render_feeding_lines_v1,
)
from cca8_maternal_continuity import maternal_continuity_shadow_observation_step_v1
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import maternal_temporal_shadow_observation_step_v1
from cca8_navmap_kernel import NavMapRefV1, NavMapV2
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1, navmap_expected_current_payload_from_ctx_v1
from cca8_navmap_shadow import navmap_v2_shadow_observation_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_policy_runtime import CATALOG_GATES, PolicyRuntime
from cca8_reporting import mini_snapshot_text, snapshot_text
from cca8_temporal import TemporalContext
from cca8_wnm_runtime import wnm_operative_map_v1, wnm_ready_maps_v1
from cca8_world_graph import WorldGraph


_OVERVIEW_ROLE = "self_maternal_scene"
_BODY_ROLE = "maternal_body_detail"
_CLOSEUP_ROLE = "nipple_mouth_feeding_closeup"


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return one exact immutable map reference for assertions."""
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _ctx() -> Ctx:
    """Return one context with the existing fast BodyMap initialized."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    return ctx


def _observation(
    *,
    stage: str,
    step_index: int,
    target_state: str = "hidden",
    search_progress: int = 0,
    suckle_progress: int = 0,
    milk: bool = False,
    include_target_predicate: bool = True,
    include_milk_predicate: bool = True,
    blackout: bool = False,
    identity_status: str | None = None,
    identity_candidates: list[str] | None = None,
) -> EnvObservation:
    """Return one deterministic Phase 4/5 observation with sensor-like feeding geometry.

    ``include_target_predicate=False`` models the generic observation mask: the
    environment-side geometry packet may have been constructed before masking,
    but the target is not accepted as current cognitive evidence unless the
    corresponding predicate survives on the packet presented to cognition.
    """
    if target_state not in {"hidden", "found", "latched"}:
        raise ValueError("target_state must be hidden, found, or latched")

    predicates = ["posture:standing", "proximity:mom:close"]
    if include_target_predicate and target_state == "found":
        predicates.append("nipple:found")
    elif include_target_predicate and target_state == "latched":
        predicates.append("nipple:latched")
    if milk and include_milk_predicate:
        predicates.append("milk:drinking")

    muzzle_point: dict[str, float] | None = {"x": -0.70, "y": -0.35}
    nipple_point: dict[str, float] | None = None
    if target_state == "found":
        muzzle_point = {"x": -0.16, "y": -0.35}
        nipple_point = {"x": 0.0, "y": -0.35}
    elif target_state == "latched":
        muzzle_point = {"x": 0.0, "y": -0.35}
        nipple_point = {"x": 0.0, "y": -0.35}
    if blackout:
        muzzle_point = None
        nipple_point = None

    feeding_geometry = {
        "schema": "feeding_geometry_v1",
        "source_class": "observed_adapter_evidence",
        "source_ref": "test:phase5_feeding_geometry",
        "quality": 0.90 if not blackout else 0.0,
        "frame_id": "maternal_body_feeding_frame_v1",
        "units": "m",
        "maternal_identity_handle": "maternal_individual",
        "self_muzzle_identity_handle": "self_muzzle",
        "nipple_identity_handle": "maternal_nipple",
        "observability": (
            "blackout"
            if blackout
            else ("target_observed" if target_state in {"found", "latched"} else "target_hidden")
        ),
        "muzzle_point": muzzle_point,
        "nipple_point": nipple_point,
        "reach_distance": 0.20,
        "contact_distance": 0.03,
        "latch_evidence": target_state == "latched",
        "milk_evidence": bool(milk),
        "search_progress": int(search_progress),
        "suckle_progress": int(suckle_progress),
        "lower_oral_head_timing_delegated": True,
    }
    env_meta: dict[str, object] = {
        "scenario_stage": stage,
        "time_since_birth": float(step_index),
        "step_index": int(step_index),
        "kid_position": {"x": 0.0, "y": 0.0},
        "mom_position": {"x": 0.5, "y": 0.0},
        "feeding_geometry_v1": feeding_geometry,
    }
    if blackout:
        env_meta["newborn_obs_blackout"] = True
        env_meta["newborn_obs_blackout_kind"] = "phase5_test_blackout"
    if identity_status is not None:
        env_meta["maternal_identity_status"] = identity_status
    if identity_candidates is not None:
        env_meta["maternal_identity_candidates"] = list(identity_candidates)

    return EnvObservation(
        raw_sensors={"distance_to_mom": 0.5},
        predicates=predicates,
        cues=[],
        env_meta=env_meta,
    )


def _update(
    ctx: Ctx,
    env_obs: EnvObservation,
    *,
    applied_policy: str | None = None,
) -> dict[str, object]:
    """Run existing dependencies followed by the Phase 5 observation step."""
    update_body_world_from_obs(ctx, env_obs)
    seqerr_update_from_obs(ctx, env_obs)
    navmap_v2_shadow_observation_step_v1(ctx, env_obs)
    maternal_geometry_shadow_observation_step_v1(ctx, env_obs)
    maternal_temporal_shadow_observation_step_v1(ctx, env_obs)
    maternal_continuity_shadow_observation_step_v1(ctx, env_obs)
    return feeding_wnm_observation_step_v1(ctx, env_obs, applied_policy=applied_policy)


def _initialize_overview(ctx: Ctx) -> dict[str, object]:
    """Initialize the operative WNM with a supported Phase 4 maternal overview."""
    return _update(ctx, _observation(stage="struggle", step_index=0))


def _zoom_to_body(ctx: Ctx) -> dict[str, object]:
    """Initialize and commit the overview-to-maternal-body zoom."""
    _initialize_overview(ctx)
    return _update(ctx, _observation(stage="first_stand", step_index=1))


def _zoom_to_closeup(
    ctx: Ctx,
    *,
    target_state: str = "found",
    search_progress: int = 1,
    include_target_predicate: bool = True,
) -> dict[str, object]:
    """Initialize and commit both Phase 5 zoom-in transitions."""
    _zoom_to_body(ctx)
    return _update(
        ctx,
        _observation(
            stage="first_stand",
            step_index=2,
            target_state=target_state,
            search_progress=search_progress,
            include_target_predicate=include_target_predicate,
        ),
    )


def test_phase5_context_defaults_and_registry_are_current() -> None:
    """Phase 5 runtime defaults and component-registry entries should remain current."""
    ctx = Ctx()

    assert ctx.wnm_operative_map_v1 is None
    assert ctx.wnm_ready_set_v1 == []
    assert ctx.wnm_ready_capacity_v1 == 3
    assert ctx.feeding_wnm_enabled_v1 is True

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)  # pylint: disable=protected-access
    assert registry["feeding"] == "cca8_feeding"
    assert registry["wnm_runtime"] == "cca8_wnm_runtime"
    assert len(cca8_run.PRIMITIVES) == 8


def test_perception_adapter_exposes_bounded_feeding_geometry_not_motor_trajectory() -> None:
    """The environment seam should expose task geometry and progress, not oral motor commands."""
    state = EnvState(
        kid_posture="standing",
        mom_distance="near",
        nipple_state="reachable",
        scenario_stage="first_stand",
        kid_position=(0.0, 0.0),
        mom_position=(0.5, 0.0),
        newborn_seek_attempts=2,
        newborn_suckle_ticks=0,
        step_index=7,
    )

    obs = PerceptionAdapter().observe(state)
    packet = obs.env_meta["feeding_geometry_v1"]

    assert packet["schema"] == "feeding_geometry_v1"
    assert packet["source_class"] == "observed_adapter_evidence"
    assert packet["observability"] == "target_observed"
    assert packet["muzzle_point"] == {"x": -0.16, "y": -0.35}
    assert packet["nipple_point"] == {"x": 0.0, "y": -0.35}
    assert packet["search_progress"] == 2
    assert packet["lower_oral_head_timing_delegated"] is True
    assert "trajectory" not in packet
    assert "joint" not in packet
    assert obs.env_meta["step_index"] == 7


def test_first_observation_initializes_phase4_overview_as_the_only_operative_wnm() -> None:
    """The maintained SELF-maternal map should become the initial operative substrate."""
    ctx = _ctx()

    summary = _initialize_overview(ctx)
    wnm = summary["wnm"]
    readout = summary["operative_readout"]

    assert wnm["operative_count"] == 1
    assert wnm["operative_map"]["role"] == _OVERVIEW_ROLE
    assert wnm["ready_count"] == 0
    assert wnm["last_transition"]["transition_type"] == "initialize"
    assert readout["detail_level"] == "overview"
    assert readout["target_localized"] is None
    assert readout["contact"] is None
    assert readout["reason"] == "feeding_detail_requires_zoom"


def test_overview_to_maternal_body_zoom_changes_the_real_query_substrate() -> None:
    """The first zoom should make maternal-body content operative and retain overview ready."""
    ctx = _ctx()

    summary = _zoom_to_body(ctx)
    readout = summary["operative_readout"]
    wnm = summary["wnm"]

    assert wnm_operative_map_v1(ctx).role == _BODY_ROLE
    assert [navmap.role for navmap in wnm_ready_maps_v1(ctx)] == [_OVERVIEW_ROLE]
    assert readout["detail_level"] == "maternal_body"
    assert readout["target_localized"] is False
    assert readout["contact"] is None
    assert readout["latch_evidence"] is None
    assert wnm["last_transition"]["transition_type"] == "zoom_in"
    assert wnm["last_transition"]["prior_wnm_disposition"] == "moved_to_ready_set"


def test_maternal_body_to_closeup_zoom_authorizes_destination_only_geometry_queries() -> None:
    """Distance/contact detail should become visible only after close-up commitment."""
    ctx = _ctx()

    summary = _zoom_to_closeup(ctx)
    readout = summary["operative_readout"]

    assert wnm_operative_map_v1(ctx).role == _CLOSEUP_ROLE
    assert [navmap.role for navmap in wnm_ready_maps_v1(ctx)] == [_OVERVIEW_ROLE, _BODY_ROLE]
    assert readout["detail_level"] == "feeding_closeup"
    assert readout["closeup_detail_authorized"] is True
    assert readout["target_localized"] is True
    assert readout["mouth_nipple_distance"] == pytest.approx(0.16)
    assert readout["reachability"] == "reachable"
    assert readout["contact"] is False
    assert readout["micro_adjustment_required"] is True
    assert readout["lower_oral_head_timing_delegated"] is True


def test_round_trip_returns_closeup_to_body_then_overview_without_reentry() -> None:
    """Rest should perform closeup -> body -> overview and then remain at overview."""
    ctx = _ctx()
    _zoom_to_closeup(ctx)

    body_summary = _update(
        ctx,
        _observation(stage="rest", step_index=3, target_state="latched", suckle_progress=1, milk=True),
        applied_policy="policy:suckle",
    )
    overview_summary = _update(
        ctx,
        _observation(stage="rest", step_index=4, target_state="latched", suckle_progress=2, milk=True),
    )
    transition_count = len(ctx.wnm_transition_history_v1)
    settled_summary = _update(
        ctx,
        _observation(stage="rest", step_index=5, target_state="latched", suckle_progress=3, milk=True),
    )

    assert body_summary["operative_readout"]["detail_level"] == "maternal_body"
    assert overview_summary["operative_readout"]["detail_level"] == "overview"
    assert settled_summary["operative_readout"]["detail_level"] == "overview"
    assert len(ctx.wnm_transition_history_v1) == transition_count
    assert [row["transition_type"] for row in ctx.wnm_transition_history_v1] == [
        "initialize",
        "zoom_in",
        "zoom_in",
        "return",
        "return",
    ]


def test_cross_scale_records_preserve_identity_frame_transform_and_explicit_support() -> None:
    """The two zoom edges should carry explicit identity and frame correspondence evidence."""
    ctx = _ctx()
    summary = _zoom_to_closeup(ctx)
    state = summary["state"]
    maternal = state["maternal_correspondence"]
    nipple = state["nipple_correspondence"]

    assert maternal["identity_handle"] == "maternal_individual"
    assert maternal["source_element_id"] == "maternal_individual"
    assert maternal["destination_element_id"] == "maternal_body"
    assert maternal["source_frame_id"] != maternal["destination_frame_id"]
    assert maternal["element_names_supply_identity"] is False
    assert maternal["support"] == pytest.approx(1.0)
    assert maternal["ambiguous"] is False
    assert nipple["identity_handle"] == "maternal_nipple"
    assert nipple["source_element_id"] == "maternal_nipple_region"
    assert nipple["destination_element_id"] == "nipple_target"
    assert nipple["transform"]["translation_y"] == pytest.approx(-0.35)


def test_ambiguous_maternal_identity_rejects_zoom_atomically() -> None:
    """Ambiguous cross-map identity must not replace the operative overview."""
    ctx = _ctx()
    _initialize_overview(ctx)
    operative_before = wnm_operative_map_v1(ctx)
    ready_before = wnm_ready_maps_v1(ctx)

    summary = _update(
        ctx,
        _observation(
            stage="first_stand",
            step_index=1,
            identity_status="ambiguous",
            identity_candidates=["maternal_individual", "other_goat"],
        ),
    )

    transition = summary["wnm"]["last_transition"]
    assert transition["accepted"] is False
    assert transition["failure_reason"] == "cross_map_correspondence_ambiguous"
    assert wnm_operative_map_v1(ctx) is operative_before
    assert wnm_ready_maps_v1(ctx) == ready_before
    assert summary["operative_readout"]["detail_level"] == "overview"


def test_masked_target_predicate_prevents_geometry_latch_and_milk_leakage() -> None:
    """Metadata built before masking must not recreate masked target or milk evidence."""
    ctx = _ctx()
    _zoom_to_closeup(ctx)

    summary = _update(
        ctx,
        _observation(
            stage="first_latch",
            step_index=3,
            target_state="latched",
            milk=True,
            include_target_predicate=False,
            include_milk_predicate=False,
        ),
    )
    overlay = summary["state"]["overlay"]

    assert overlay["target_localized"] is False
    assert overlay["latch_evidence"] is None
    assert overlay["milk_evidence"] is None
    assert overlay["observability"] == "masked_target_unavailable"


def test_geometry_operators_derive_reachability_contact_and_micro_adjustment() -> None:
    """Mouth-to-nipple relations should come from map geometry rather than nipple-state labels."""
    ctx = _ctx()
    summary = _zoom_to_closeup(ctx, target_state="found")
    overlay = summary["state"]["overlay"]

    assert overlay["mouth_nipple_distance"] == pytest.approx(0.16)
    assert overlay["reachability"] == "reachable"
    assert overlay["contact"] is False
    assert overlay["latch_evidence"] is False
    assert overlay["micro_adjustment_required"] is True
    assert overlay["source_evidence_map_ref"]["map_id"] == "goat_nipple_mouth_evidence_v2"


def test_contact_acquisition_maintenance_loss_and_duration_are_compact_overlay_state() -> None:
    """Contact events/durations should update without creating structural map revisions."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found")
    body_ref = _map_ref(ctx.feeding_maternal_body_map_v1)
    closeup_ref = _map_ref(ctx.feeding_closeup_map_v1)

    acquired = _update(
        ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", search_progress=2),
    )["state"]["overlay"]
    maintained = _update(
        ctx,
        _observation(stage="first_latch", step_index=4, target_state="latched", search_progress=2),
    )["state"]["overlay"]
    lost = _update(
        ctx,
        _observation(stage="first_latch", step_index=5, target_state="found", search_progress=2),
    )["state"]["overlay"]

    assert acquired["contact_event"] == FeedingContactEventV1.ACQUIRED.value
    assert acquired["contact_duration_observations"] == 1
    assert maintained["contact_event"] == FeedingContactEventV1.MAINTAINED.value
    assert maintained["contact_duration_observations"] == 2
    assert lost["contact_event"] == FeedingContactEventV1.LOST.value
    assert lost["contact_duration_observations"] == 0
    assert _map_ref(ctx.feeding_maternal_body_map_v1) == body_ref
    assert _map_ref(ctx.feeding_closeup_map_v1) == closeup_ref


def test_milk_duration_updates_live_overlay_without_revising_structural_maps() -> None:
    """Repeated milk evidence should update duration while structural map content remains stable."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found")
    body_bytes = ctx.feeding_maternal_body_map_v1.to_bytes()
    closeup_bytes = ctx.feeding_closeup_map_v1.to_bytes()

    first = _update(
        ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", milk=True),
    )["operative_readout"]
    second = _update(
        ctx,
        _observation(stage="first_latch", step_index=4, target_state="latched", milk=True),
    )["operative_readout"]

    assert first["milk_duration_observations"] == 1
    assert second["milk_duration_observations"] == 2
    assert ctx.feeding_maternal_body_map_v1.revision == 1
    assert ctx.feeding_closeup_map_v1.revision == 1
    assert ctx.feeding_maternal_body_map_v1.to_bytes() == body_bytes
    assert ctx.feeding_closeup_map_v1.to_bytes() == closeup_bytes


def test_overlay_history_is_bounded_json_safe_and_never_stores_full_navmaps() -> None:
    """Ordinary feeding dynamics should not create a frame-by-frame movie of maps."""
    ctx = _ctx()
    ctx.feeding_overlay_history_limit_v1 = 3
    _zoom_to_closeup(ctx)
    for step in range(3, 8):
        _update(
            ctx,
            _observation(stage="first_latch", step_index=step, target_state="latched", suckle_progress=step - 2),
        )

    assert len(ctx.feeding_overlay_history_v1) == 3
    json.dumps(ctx.feeding_overlay_history_v1, sort_keys=True)
    assert all(isinstance(row, dict) for row in ctx.feeding_overlay_history_v1)
    assert all("elements" not in row and "relations" not in row for row in ctx.feeding_overlay_history_v1)
    assert all(row["stores_full_navmap_history"] is False for row in ctx.feeding_overlay_history_v1)


def test_seek_nipple_from_hidden_target_arms_localize_expectation_and_observed_progress_succeeds() -> None:
    """SeekNipple should expect localization/reach from the operative close-up, not a detached slot."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="hidden", search_progress=0)

    selection = feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")
    expected = selection["pending_expectation"]
    outcome_summary = _update(
        ctx,
        _observation(stage="first_stand", step_index=3, target_state="found", search_progress=1),
        applied_policy="policy:seek_nipple",
    )

    assert expected["expectation_kind"] == FeedingExpectationKindV1.LOCALIZE_OR_REACH_NIPPLE.value
    assert expected["source_class"] == "expected"
    assert expected["current_truth"] is False
    assert expected["source_operative_map_ref"]["map_id"] == "goat_nipple_mouth_feeding_v2"
    assert outcome_summary["observed_outcome"]["outcome"] == "success"
    assert outcome_summary["observed_outcome"]["reason"] == "nipple_target_localized_or_reached"
    assert ctx.feeding_pending_expectation_v1 is None


def test_seek_nipple_from_reachable_target_arms_latch_expectation() -> None:
    """A localized reachable target should produce the next modest contact/latch expectation."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found", search_progress=1)

    selection = feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")
    outcome_summary = _update(
        ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", search_progress=2),
        applied_policy="policy:seek_nipple",
    )

    assert selection["pending_expectation"]["expectation_kind"] == FeedingExpectationKindV1.ACQUIRE_LATCH.value
    assert outcome_summary["observed_outcome"]["outcome"] == "success"
    assert outcome_summary["observed_outcome"]["reason"] == "feeding_contact_or_latch_acquired"


def test_seek_nipple_expected_outcome_reports_supported_failure_without_progress() -> None:
    """Current supported evidence with no search progress should close SeekNipple as failure."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="hidden", search_progress=0)
    feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")

    summary = _update(
        ctx,
        _observation(stage="first_stand", step_index=3, target_state="hidden", search_progress=0),
        applied_policy="policy:seek_nipple",
    )

    assert summary["observed_outcome"]["outcome"] == "failure"
    assert summary["observed_outcome"]["reason"] == "supported_observation_showed_no_search_progress"


def test_suckle_arms_milk_expectation_and_motor_command_does_not_count_as_success() -> None:
    """Suckle should arm one map-native milk expectation closed by later evidence."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found", search_progress=1)
    _update(
        ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", search_progress=2),
    )

    selection = feeding_selection_step_v1(ctx, selected_policy="policy:suckle")
    expected = selection["pending_expectation"]

    assert expected["expectation_kind"] == FeedingExpectationKindV1.MAINTAIN_CONTACT_AND_OBTAIN_MILK.value
    assert selection["observed_outcome"] is None

    outcome_summary = _update(
        ctx,
        _observation(
            stage="first_latch",
            step_index=4,
            target_state="latched",
            search_progress=2,
            suckle_progress=1,
            milk=True,
        ),
        applied_policy="policy:suckle",
    )
    outcome = outcome_summary["observed_outcome"]

    assert outcome["outcome"] == "success"
    assert outcome["observed_milk_evidence"] is True
    assert outcome["reason"] == "current_milk_evidence_observed"
    assert outcome["motor_command_is_outcome"] is False


def test_pending_expectation_closes_not_applied_when_another_primitive_reaches_environment() -> None:
    """An armed feeding expectation must not claim application when another action was applied."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="hidden", search_progress=0)
    feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")

    summary = _update(
        ctx,
        _observation(stage="first_stand", step_index=3, target_state="hidden", search_progress=0),
        applied_policy="policy:rest",
    )

    assert summary["observed_outcome"]["outcome"] == "not_applied"
    assert summary["observed_outcome"]["reason"] == "armed_feeding_primitive_was_not_the_applied_action"


def test_blackout_after_applied_feeding_action_closes_outcome_as_unknown() -> None:
    """Missing current evidence should preserve uncertainty rather than fabricate success/failure."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="hidden", search_progress=0)
    feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")

    summary = _update(
        ctx,
        _observation(stage="first_stand", step_index=3, target_state="hidden", blackout=True),
        applied_policy="policy:seek_nipple",
    )

    assert summary["observed_outcome"]["outcome"] == "unknown"
    assert summary["observed_outcome"]["reason"] == "current_feeding_evidence_unavailable"
    assert summary["state"]["overlay"]["freshness"] == "missing"


def test_suckle_expected_outcome_distinguishes_contact_loss_from_progress_without_milk() -> None:
    """Contact loss is failure, while maintained contact/progress without milk remains UNKNOWN."""
    failed_ctx = _ctx()
    _zoom_to_closeup(failed_ctx, target_state="found")
    _update(
        failed_ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", suckle_progress=0),
    )
    feeding_selection_step_v1(failed_ctx, selected_policy="policy:suckle")
    failed = _update(
        failed_ctx,
        _observation(stage="first_latch", step_index=4, target_state="found", suckle_progress=0),
        applied_policy="policy:suckle",
    )["observed_outcome"]

    unknown_ctx = _ctx()
    _zoom_to_closeup(unknown_ctx, target_state="found")
    _update(
        unknown_ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", suckle_progress=0),
    )
    feeding_selection_step_v1(unknown_ctx, selected_policy="policy:suckle")
    unknown = _update(
        unknown_ctx,
        _observation(stage="first_latch", step_index=4, target_state="latched", suckle_progress=1),
        applied_policy="policy:suckle",
    )["observed_outcome"]

    assert failed["outcome"] == "failure"
    assert failed["reason"] == "feeding_contact_or_latch_lost"
    assert unknown["outcome"] == "unknown"
    assert unknown["reason"] == "contact_or_lower_controller_progress_without_milk_yet"


def test_feeding_expectation_defers_when_required_detail_map_is_not_operative() -> None:
    """A policy name alone must not fabricate an expected relation from overview content."""
    ctx = _ctx()
    _initialize_overview(ctx)

    summary = feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")

    assert ctx.feeding_pending_expectation_v1 is None
    assert summary["pending_expectation"] is None
    assert ctx.feeding_last_expectation_update_v1["status"] == "deferred"
    assert ctx.feeding_last_expectation_update_v1["policy_selection_mutation_allowed"] is False


def test_current_latch_and_milk_helpers_require_closeup_operability() -> None:
    """Current evidence helpers should disappear after the map round-trip leaves close-up detail."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found")
    _update(
        ctx,
        _observation(stage="first_latch", step_index=3, target_state="latched", milk=True),
    )

    assert feeding_latch_evidence_v1(ctx) is True
    assert feeding_milk_evidence_v1(ctx) is True

    _update(ctx, _observation(stage="rest", step_index=4, target_state="latched", milk=True))

    assert wnm_operative_map_v1(ctx).role == _BODY_ROLE
    assert feeding_latch_evidence_v1(ctx) is None
    assert feeding_milk_evidence_v1(ctx) is None


def test_phase5_current_false_milk_evidence_defeats_historical_cycle_record() -> None:
    """A historical JSON trace must not masquerade as current feeding evidence after migration."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found")
    ctx.cycle_json_records = [
        {
            "obs": {
                "predicates": ["milk:drinking"],
                "env_meta": {"milestone": "milk_drinking"},
            }
        }
    ]

    result = cca8_policy_runtime._newborn_milk_drinking_current_v1(  # pylint: disable=protected-access
        SimpleNamespace(_bindings={}),
        ctx,
    )

    assert feeding_milk_evidence_v1(ctx) is False
    assert result is False


def test_feeding_structural_maps_remain_stable_while_current_evidence_revision_advances() -> None:
    """Per-cycle motion should revise transient evidence only, not structural detail maps."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="found")
    body_ref = _map_ref(ctx.feeding_maternal_body_map_v1)
    closeup_ref = _map_ref(ctx.feeding_closeup_map_v1)
    evidence_refs = [_map_ref(ctx.feeding_evidence_map_v1)]

    for step in range(3, 6):
        _update(
            ctx,
            _observation(stage="first_latch", step_index=step, target_state="latched", suckle_progress=step - 2),
        )
        evidence_refs.append(_map_ref(ctx.feeding_evidence_map_v1))

    assert _map_ref(ctx.feeding_maternal_body_map_v1) == body_ref
    assert _map_ref(ctx.feeding_closeup_map_v1) == closeup_ref
    assert [ref.revision for ref in evidence_refs] == [3, 4, 5, 6]
    assert len({ref.map_id for ref in evidence_refs}) == 1


def test_navmap_runtime_integration_updates_feeding_after_phase4_dependencies() -> None:
    """The ordinary runner-facing observation bridge should invoke Phase 5 after Phase 4A/4C."""
    ctx = _ctx()
    obs = _observation(stage="struggle", step_index=0)
    update_body_world_from_obs(ctx, obs)
    seqerr_update_from_obs(ctx, obs)

    navmap_ctx_observation_update_step_v1(ctx, obs)

    summary = feeding_summary_v1(ctx)
    assert summary["status"] == "active"
    assert summary["wnm"]["operative_map"]["role"] == _OVERVIEW_ROLE
    assert ctx.feeding_last_update_v1["schema"] == "feeding_wnm_state_v1"


def test_disabled_and_dependency_error_paths_do_not_leave_stale_current_readout() -> None:
    """Disabled or missing-dependency states should be explicit and never expose stale close-up truth."""
    ctx = _ctx()
    _zoom_to_closeup(ctx)
    ctx.feeding_wnm_enabled_v1 = False

    disabled = feeding_wnm_observation_step_v1(
        ctx,
        _observation(stage="first_stand", step_index=3, target_state="found"),
    )

    assert disabled["status"] == "disabled"
    assert ctx.feeding_state_v1 is None
    assert ctx.feeding_overlay_v1 is None
    assert feeding_operative_readout_v1(ctx)["status"] == "unavailable"

    missing_ctx = _ctx()
    dependency = feeding_wnm_observation_step_v1(
        missing_ctx,
        _observation(stage="struggle", step_index=0),
    )
    assert dependency["status"] == "dependency_error"
    assert feeding_summary_v1(missing_ctx)["status"] == "dependency_error"


def test_reset_clears_episode_local_wnm_feeding_and_expectation_registers() -> None:
    """Episode reset should clear Phase 5 runtime without touching unrelated state."""
    ctx = _ctx()
    _zoom_to_closeup(ctx, target_state="hidden")
    feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")
    jump_before = ctx.jump

    feeding_reset_v1(ctx)

    assert ctx.wnm_operative_map_v1 is None
    assert ctx.wnm_ready_set_v1 == []
    assert ctx.wnm_transition_history_v1 == []
    assert ctx.feeding_state_v1 is None
    assert ctx.feeding_overlay_v1 is None
    assert ctx.feeding_pending_expectation_v1 is None
    assert ctx.feeding_expectation_history_v1 == []
    assert ctx.jump == jump_before


def test_phase5_records_are_frozen_json_safe_and_human_readable() -> None:
    """Core records and renderers should remain deterministic and inspection-friendly."""
    ctx = _ctx()
    summary = _zoom_to_closeup(ctx)
    state = ctx.feeding_state_v1
    overlay = ctx.feeding_overlay_v1

    assert state is not None
    assert isinstance(overlay, FeedingRelationOverlayV1)
    with pytest.raises(FrozenInstanceError):
        overlay.reason = "mutated"  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        state.transition_attempted = False  # type: ignore[misc]

    selection = feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")
    pending = ctx.feeding_pending_expectation_v1
    assert pending is not None
    assert isinstance(pending.expected_successor, FeedingExpectedSuccessorV1)

    json.dumps(summary, sort_keys=True)
    json.dumps(selection, sort_keys=True)
    lines = render_feeding_lines_v1(ctx)
    assert lines[0] == "PHASE 5 FEEDING CLOSE-UP / WNM ZOOM:"
    assert any("operative=feeding_closeup" in line for line in lines)
    assert any("lower_motor_timing=delegated" in line for line in lines)


def test_phase6_route_claim_prevents_a_second_feeding_wnm_transition_in_the_same_cycle() -> None:
    """An active terrain route must keep the sole operative substrate until its transition cycle completes."""
    ctx = _ctx()
    _initialize_overview(ctx)
    operative_before = wnm_operative_map_v1(ctx)
    ready_before = wnm_ready_maps_v1(ctx)
    ctx.terrain_route_claims_wnm_v1 = True

    summary = _update(ctx, _observation(stage="first_stand", step_index=1))

    state = summary["state"]
    assert isinstance(state, dict)
    assert state["transition_attempted"] is False
    assert wnm_operative_map_v1(ctx) is operative_before
    assert wnm_ready_maps_v1(ctx) == ready_before
    assert summary["wnm"]["operative_count"] == 1
    assert summary["wnm"]["at_most_one_operative"] is True


def test_feeding_selection_hook_preserves_hunger_and_existing_global_authority() -> None:
    """Phase 5 migrates feeding expectations, not hunger or the selected primitive."""
    ctx = _ctx()
    _zoom_to_body(ctx)
    drives = Drives(hunger=0.73, fatigue=0.20, warmth=0.60)
    hunger_before = drives.hunger
    operative_before = wnm_operative_map_v1(ctx)
    ready_before = wnm_ready_maps_v1(ctx)

    summary = feeding_selection_step_v1(ctx, selected_policy="policy:seek_nipple")

    assert drives.hunger == hunger_before
    assert wnm_operative_map_v1(ctx) is operative_before
    assert wnm_ready_maps_v1(ctx) == ready_before
    assert summary["policy_selection_mutation_allowed"] is False
    assert summary["seek_nipple_authority_changed"] is False
    assert summary["suckle_authority_changed"] is False
    assert summary["hunger_remains_compact_drive"] is True


def test_full_and_mini_snapshots_expose_the_phase5_operative_substrate() -> None:
    """Human-readable output should make the real WNM zoom and close-up readout visible."""
    ctx = _ctx()
    _zoom_to_closeup(ctx)
    world = WorldGraph()
    world.ensure_anchor("NOW")

    mini = mini_snapshot_text(world, ctx=ctx, limit=2)
    full = snapshot_text(world, drives=Drives(), ctx=ctx, policy_rt=None)

    assert "[wnm] status=active operative=nipple_mouth_feeding_closeup" in mini
    assert "[feeding] detail=feeding_closeup" in mini
    assert "PHASE 5 OPERATIVE WNM:" in full
    assert "PHASE 5 FEEDING CLOSE-UP / WNM ZOOM:" in full


def test_cycle_json_exposes_phase5_feeding_phase6_terrain_and_single_operative_wnm(
    capsys: pytest.CaptureFixture[str],
) -> None:
    """One ordinary closed-loop record should expose the Phase 5/6 machine-readable summaries."""
    ctx = _ctx()
    ctx.working_world = cca8_run.init_working_world()
    ctx.temporal = TemporalContext()
    ctx.tvec_last_boundary = ctx.temporal.vector()
    ctx.cycle_json_enabled = True
    ctx.cycle_json_path = None
    ctx.env_loop_cycle_summary = False
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

    record = ctx.cycle_json_records[-1]
    assert record["feeding"]["schema"] == "feeding_summary_v1"
    assert record["feeding"]["phase"] == "5"
    assert record["feeding"]["policy_selection_mutation_allowed"] is False
    assert record["terrain"]["schema"] == "terrain_summary_v1"
    assert record["terrain"]["phase"] == "6"
    assert record["terrain"]["protected_safety_can_be_overridden"] is False
    assert record["wnm"]["schema"] == "wnm_summary_v1"
    assert record["wnm"]["operative_count"] == 1
    assert record["wnm"]["at_most_one_operative"] is True



def test_generic_scene_body_prediction_does_not_recreate_detached_feeding_expectations() -> None:
    """Learned/default scene slots must not compete with the Phase 5 map-native feeding expectation."""
    ctx = Ctx()
    ctx.navmap_last_payload_v1 = {
        "schema": "navmap_payload_v1",
        "slots": {"posture": "standing", "nipple_state": "hidden"},
        "confidence": 1.0,
        "source": "test_previous_scene",
        "basis": {},
    }
    ctx.navmap_pending_action_v1 = "policy:seek_nipple"
    context_signature = "nipple_state=hidden|posture=standing"
    policy_key = f"{context_signature}::policy:seek_nipple"
    ctx.navmap_policy_outcome_index_v1 = {
        policy_key: {
            "policy_key": policy_key,
            "sample_count": 9,
            "expected_slots": {"nipple_state": "found", "mom_distance": "near"},
        }
    }

    payload = navmap_expected_current_payload_from_ctx_v1(ctx)

    assert payload["slots"] == {"posture": "standing", "nipple_state": "hidden"}
    assert payload["basis"]["sources"] == [
        "previous_payload_continuity",
        "phase5_feeding_expectation_external",
    ]
    assert "learned_policy_key" not in payload["basis"]
    assert "learned_sample_count" not in payload["basis"]
