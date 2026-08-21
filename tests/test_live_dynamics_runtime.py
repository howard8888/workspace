# -*- coding: utf-8 -*-
"""Phase 7 tests for generalized temporal binding and source-linked live dynamics."""

from __future__ import annotations

import json

import pytest

import cca8_context
import cca8_env
import cca8_live_dynamics
import cca8_navmap_runtime
import cca8_reporting
import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, EnvState, PerceptionAdapter
from cca8_feeding import FeedingContactEventV1, FeedingReachabilityV1, FeedingRelationOverlayV1
from cca8_live_dynamics import (
    TemporalDistanceTrendV1,
    TemporalEnvelopeStatusV1,
    TemporalExpectedContinuationV1,
    TemporalMotionDirectionV1,
    TemporalPhaseV1,
    TemporalRelationV1,
    live_dynamics_observation_step_v1,
    live_dynamics_overlay_v1,
    live_dynamics_reset_v1,
    live_dynamics_summary_v1,
    render_live_dynamics_lines_v1,
)
from cca8_maternal_continuity import maternal_continuity_shadow_observation_step_v1
from cca8_maternal_geometry import maternal_geometry_shadow_observation_step_v1
from cca8_maternal_temporal import maternal_temporal_shadow_observation_step_v1
from cca8_navmap_kernel import NavPointV1
from cca8_navmap_runtime import navmap_ctx_observation_update_step_v1
from cca8_observation_runtime import init_body_world, seqerr_update_from_obs, update_body_world_from_obs
from cca8_reporting import mini_snapshot_text, snapshot_text
from cca8_terrain import TerrainDynamicOverlayV1
from cca8_world_graph import WorldGraph


def _state(
    step: int,
    *,
    kid_x: float = 0.0,
    kid_y: float = 0.0,
    mom_x: float = 3.0,
    mom_y: float = 0.0,
    posture: str = "standing",
    position: str = "open_field",
    action: str | None = None,
    progress: float | None = None,
    support: bool | None = None,
    slip: bool = False,
    error: str | None = None,
) -> EnvState:
    """Return one deterministic environment state with compact lower-motor feedback."""
    return EnvState(
        kid_posture=posture,
        mom_distance="near" if abs(mom_x - kid_x) <= 1.0 else "far",
        shelter_distance="near" if position == "shelter_area" else "far",
        cliff_distance="near" if position == "cliff_edge" else "far",
        nipple_state="hidden",
        scenario_stage="first_stand",
        kid_position=(kid_x, kid_y),
        mom_position=(mom_x, mom_y),
        time_since_birth=float(step),
        step_index=step,
        position=position,
        zone="unsafe" if position == "cliff_edge" else ("safe" if position == "shelter_area" else "neutral"),
        last_applied_action=action,
        lower_motor_progress_override=progress,
        lower_motor_support_override=support,
        lower_motor_slip_detected=slip,
        lower_motor_error_code=error,
    )


def _observe(state: EnvState) -> EnvObservation:
    """Return one current evidence packet."""
    return PerceptionAdapter().observe(state)


def _update_maternal(ctx: Ctx, obs: EnvObservation) -> None:
    """Run the retained Phase 4 maternal evidence/temporal/continuity sequence."""
    maternal_geometry_shadow_observation_step_v1(ctx, obs)
    maternal_temporal_shadow_observation_step_v1(ctx, obs)
    maternal_continuity_shadow_observation_step_v1(ctx, obs)


def _set_route_overlay(
    ctx: Ctx,
    state: EnvState,
    *,
    branch_offset: float = 0.0,
    material_event: bool = False,
    supported: bool = True,
) -> None:
    """Install one current Phase 6 route overlay without changing WNM authority."""
    point = NavPointV1(x=float(state.kid_position[0]), y=float(state.kid_position[1])) if supported else None
    ctx.terrain_dynamic_overlay_v1 = TerrainDynamicOverlayV1(
        observation_no=max(1, int(state.step_index)),
        source_packet_ref=f"test:phase7_route:{state.step_index}",
        self_world_point=point,
        self_west_local_point=point,
        self_east_local_point=point,
        position_label=state.position,
        stage=state.scenario_stage,
        current_evidence_supported=supported,
        vegetation_branch_offset=float(branch_offset) if supported else None,
        vegetation_motion_dynamic_only=True,
        tree_fallen=material_event,
        route_structure_materially_changed=material_event,
        backtrack_requested=False,
        reason="phase7_test_route_overlay",
    )


def _set_feeding_overlay(
    ctx: Ctx,
    *,
    step: int,
    contact: bool | None,
    contact_event: FeedingContactEventV1,
    milk: bool | None = False,
    distance: float | None = 0.01,
    progress: int = 1,
) -> None:
    """Install one current Phase 5 feeding overlay for generalized binding tests."""
    ctx.feeding_overlay_v1 = FeedingRelationOverlayV1(
        observation_no=step,
        operative_map_ref=None,
        operative_role=None,
        source_evidence_map_ref=None,
        maternal_identity_handle="maternal_individual",
        nipple_identity_handle="maternal_nipple",
        observability="target_observed",
        stage="first_latch" if contact else "first_stand",
        target_localized=True,
        mouth_nipple_distance=distance,
        reachability=FeedingReachabilityV1.REACHABLE,
        contact=contact,
        latch_evidence=contact,
        milk_evidence=milk,
        contact_event=contact_event,
        contact_duration_observations=1 if contact else 0,
        milk_duration_observations=1 if milk else 0,
        search_progress=progress,
        suckle_progress=progress if contact else 0,
        micro_adjustment_required=False,
        closeup_query_authorized=False,
        freshness="fresh",
        support_status="supported",
        reason="phase7_test_feeding_overlay",
    )


def _update(
    ctx: Ctx,
    state: EnvState,
    *,
    maternal: bool = True,
    route: bool = True,
    branch_offset: float = 0.0,
    material_event: bool = False,
    feeding: tuple[bool | None, FeedingContactEventV1, bool | None] | None = None,
) -> dict[str, object]:
    """Run one deterministic Phase 7 observation with selected current dependencies."""
    ctx.controller_steps = max(ctx.controller_steps + 1, state.step_index)
    obs = _observe(state)
    if maternal:
        _update_maternal(ctx, obs)
    if route:
        _set_route_overlay(ctx, state, branch_offset=branch_offset, material_event=material_event)
    if feeding is not None:
        contact, event, milk = feeding
        _set_feeding_overlay(ctx, step=state.step_index, contact=contact, contact_event=event, milk=milk)
    return live_dynamics_observation_step_v1(ctx, obs, applied_policy=state.last_applied_action)


def test_phase7_versions_defaults_and_registry_are_current() -> None:
    """Phase 7 modules, context defaults, and the component registry should agree."""
    ctx = Ctx()

    assert cca8_run.__version__ == "0.23.0"
    assert cca8_context.__version__ == "0.17.0"
    assert cca8_env.__version__ == "0.5.0"
    assert cca8_navmap_runtime.__version__ == "0.14.0"
    assert cca8_reporting.__version__ == "0.5.0"
    assert cca8_live_dynamics.__version__ == "0.1.0"
    assert ctx.live_dynamics_enabled_v1 is True
    assert ctx.live_dynamics_state_v1 is None
    assert ctx.live_dynamics_event_history_v1 == []
    assert ctx.live_dynamics_persistent_residual_observations_v1 == 2

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)  # pylint: disable=protected-access
    assert registry["live_dynamics"] == "cca8_live_dynamics"
    assert list(registry).count("live_dynamics") == 1
    assert len(cca8_run._cca8_component_rows()) == 41  # pylint: disable=protected-access
    assert len(cca8_run.PRIMITIVES) == 8


def test_lower_motor_feedback_packet_is_bounded_and_json_safe() -> None:
    """The environment should expose compact progress/error products, never a trajectory."""
    state = _state(
        7,
        action="policy:follow_mom",
        position="open_field",
        progress=0.55,
        support=True,
        slip=True,
        error="test_slip",
    )
    packet = _observe(state).env_meta["lower_motor_feedback_v1"]

    assert packet["schema"] == "lower_motor_feedback_v1"
    assert packet["action_applied"] == "policy:follow_mom"
    assert packet["progress"] == 0.55
    assert packet["support_contact"] is True
    assert packet["slip_detected"] is True
    assert packet["phase"] == "interrupted"
    assert packet["error_code"] == "test_slip"
    assert packet["detailed_movement_delegated"] is True
    assert packet["lower_motor_trajectory_present"] is False
    assert packet["actuator_commands_present"] is False
    assert "trajectory" not in packet
    assert "joint" not in packet
    json.dumps(packet, sort_keys=True)


def test_environment_derives_task_progress_without_detailed_motor_model() -> None:
    """The adapter should derive only a task-level progress scalar for known actions."""
    state = _state(2, action="policy:follow_mom", position="open_field", support=True)
    packet = _observe(state).env_meta["lower_motor_feedback_v1"]

    assert packet["progress"] == 0.5
    assert packet["phase"] == "active"
    assert packet["lower_motor_trajectory_present"] is False


def test_phase7_reuses_the_existing_seqerr_frame_and_preserves_phase4b() -> None:
    """Phase 7 should attach beside Phase 4B rather than create a second temporal clock."""
    ctx = Ctx()
    state = _state(1)
    _update(ctx, state)

    assert len(ctx.seqerr_history) == 1
    frame = ctx.seqerr_history[-1]
    assert "navmap_temporal" in frame
    assert "live_dynamics_v1" in frame
    assert set(frame["live_dynamics_v1"]) == {item.value for item in TemporalRelationV1}
    sample = frame["live_dynamics_v1"][TemporalRelationV1.SELF_MATERNAL.value]
    assert sample["contains_full_navmap"] is False
    assert sample["contains_motor_trajectory"] is False
    assert sample["episodic_memory_record"] is False


def test_shared_temporal_window_remains_bounded() -> None:
    """Repeated observations should retain only the configured shared-window capacity."""
    ctx = Ctx()
    ctx.seqerr_window = 4
    for step in range(1, 11):
        _update(ctx, _state(step, kid_x=float(step) * 0.1))

    assert len(ctx.seqerr_history) == 4
    assert all("live_dynamics_v1" in frame for frame in ctx.seqerr_history)
    assert ctx.live_dynamics_state_v1 is not None
    assert ctx.live_dynamics_state_v1.shared_window_capacity == 4
    assert ctx.live_dynamics_state_v1.shared_window_frame_count == 4


def test_first_supported_relation_preserves_insufficient_history() -> None:
    """A current relation can be valid before motion history is sufficient."""
    ctx = Ctx()
    _update(ctx, _state(1))

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    assert maternal is not None
    assert maternal.valid is True
    assert maternal.support_status == "insufficient_history"
    assert maternal.motion_supported is False
    assert maternal.distance_trend is TemporalDistanceTrendV1.UNKNOWN


def test_self_motion_compensation_keeps_stationary_mom_stationary() -> None:
    """SELF approach must not be misclassified as maternal object motion."""
    ctx = Ctx()
    _update(ctx, _state(1, kid_x=0.0, mom_x=3.0, action="policy:follow_mom"))
    _update(ctx, _state(2, kid_x=1.0, mom_x=3.0, action="policy:follow_mom"))

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    assert maternal is not None
    assert maternal.self_motion_compensated is True
    assert maternal.self_velocity_x == 1.0
    assert maternal.object_velocity_x == 0.0
    assert maternal.object_speed == 0.0
    assert maternal.motion_direction is TemporalMotionDirectionV1.STILL
    assert maternal.distance_trend is TemporalDistanceTrendV1.APPROACHING
    assert maternal.relative_distance_rate == -1.0


def test_object_specific_maternal_motion_is_separate_from_relative_trend() -> None:
    """Stationary SELF with moving Mom should expose object velocity and recession separately."""
    ctx = Ctx()
    _update(ctx, _state(1, kid_x=0.0, mom_x=3.0))
    _update(ctx, _state(2, kid_x=0.0, mom_x=4.0))

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    assert maternal is not None
    assert maternal.self_velocity_x == 0.0
    assert maternal.object_velocity_x == 1.0
    assert maternal.object_speed == 1.0
    assert maternal.motion_direction is TemporalMotionDirectionV1.EAST
    assert maternal.distance_trend is TemporalDistanceTrendV1.RECEDING


def test_both_self_and_mom_motion_are_decomposed() -> None:
    """Compensation should preserve distinct SELF, object, and relative rates."""
    ctx = Ctx()
    _update(ctx, _state(1, kid_x=0.0, mom_x=3.0))
    _update(ctx, _state(2, kid_x=1.0, mom_x=3.5))

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    assert maternal is not None
    assert maternal.self_velocity_x == 1.0
    assert maternal.object_velocity_x == 0.5
    assert maternal.relative_distance_rate == -0.5
    assert maternal.distance_trend is TemporalDistanceTrendV1.APPROACHING


def test_identity_mismatch_breaks_maternal_trajectory_continuity() -> None:
    """A different individual must not inherit the preceding maternal motion suffix."""
    ctx = Ctx()
    _update(ctx, _state(1, mom_x=3.0))
    _update(ctx, _state(2, mom_x=2.0))

    state = _state(3, mom_x=1.0)
    obs = _observe(state)
    obs.env_meta["maternal_identity_handle"] = "other_goat"
    obs.env_meta["maternal_identity_status"] = "mismatch"
    _update_maternal(ctx, obs)
    _set_route_overlay(ctx, state)
    live_dynamics_observation_step_v1(ctx, obs)

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    assert maternal is not None
    assert maternal.valid is False
    assert maternal.valid_sample_count == 0
    assert maternal.motion_supported is False
    assert maternal.distance_trend is TemporalDistanceTrendV1.UNKNOWN


def test_route_motion_direction_and_rate_are_decoded_from_current_world_points() -> None:
    """The route overlay should expose current SELF motion without immutable map churn."""
    ctx = Ctx()
    _update(ctx, _state(1, kid_x=0.0), maternal=False)
    _update(ctx, _state(2, kid_x=1.0), maternal=False)

    route = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_ROUTE)
    assert route is not None
    assert route.motion_supported is True
    assert route.velocity_x == 1.0
    assert route.speed == 1.0
    assert route.motion_direction is TemporalMotionDirectionV1.EAST
    assert route.material_event is False


def test_periodic_vegetation_remains_dynamic_and_non_material() -> None:
    """Harmless branch reversals should stay a scalar live overlay, not route revision advice."""
    ctx = Ctx()
    _update(ctx, _state(1), maternal=False, branch_offset=0.08)
    _update(ctx, _state(2), maternal=False, branch_offset=-0.08)
    _update(ctx, _state(3), maternal=False, branch_offset=0.08)

    vegetation = live_dynamics_overlay_v1(ctx, TemporalRelationV1.ROUTE_VEGETATION)
    assert vegetation is not None
    assert vegetation.motion_supported is True
    assert vegetation.scalar_rate == 0.0  # bounded three-sample mean endpoint rate
    assert vegetation.material_event is False
    assert ctx.live_dynamics_state_v1 is not None
    residual = next(
        item for item in ctx.live_dynamics_state_v1.residuals if item.relation is TemporalRelationV1.ROUTE_VEGETATION
    )
    assert residual.material_change_candidate is False
    assert TemporalRelationV1.ROUTE_VEGETATION not in ctx.live_dynamics_state_v1.materiality.material_change_relations


def test_feeding_contact_duration_is_compact_current_state() -> None:
    """Contact duration should increment without storing a separate feeding movie."""
    ctx = Ctx()
    _update(
        ctx,
        _state(1),
        maternal=False,
        route=False,
        feeding=(True, FeedingContactEventV1.ACQUIRED, False),
    )
    first = live_dynamics_overlay_v1(ctx, TemporalRelationV1.FEEDING_CONTACT)
    _update(
        ctx,
        _state(2),
        maternal=False,
        route=False,
        feeding=(True, FeedingContactEventV1.MAINTAINED, False),
    )
    second = live_dynamics_overlay_v1(ctx, TemporalRelationV1.FEEDING_CONTACT)

    assert first is not None and second is not None
    assert first.contact_duration_observations == 1
    assert second.contact_duration_observations == 2
    assert second.phase is TemporalPhaseV1.MAINTAINING
    assert TemporalExpectedContinuationV1.MAINTAIN_CONTACT in second.expected_continuations


def test_feeding_contact_loss_creates_event_boundary_not_automatic_revision() -> None:
    """Contact loss should be explicit but not itself create an immutable NavMap revision."""
    ctx = Ctx()
    _update(
        ctx,
        _state(1),
        maternal=False,
        route=False,
        feeding=(True, FeedingContactEventV1.ACQUIRED, False),
    )
    _update(
        ctx,
        _state(2),
        maternal=False,
        route=False,
        feeding=(False, FeedingContactEventV1.LOST, False),
    )

    feeding = live_dynamics_overlay_v1(ctx, TemporalRelationV1.FEEDING_CONTACT)
    assert feeding is not None
    assert feeding.contact is False
    assert feeding.contact_duration_observations == 0
    assert "contact_lost" in feeding.event_labels
    assert ctx.live_dynamics_state_v1 is not None
    assert ctx.live_dynamics_state_v1.materiality.event_boundary is True
    assert ctx.live_dynamics_state_v1.materiality.material_change_recommended is False


def test_support_duration_and_loss_are_decoded_from_lower_controller_feedback() -> None:
    """Support duration should accumulate and reset when support is lost."""
    ctx = Ctx()
    _update(ctx, _state(1, support=True), maternal=False, route=False)
    _update(ctx, _state(2, support=True), maternal=False, route=False)
    supported = live_dynamics_overlay_v1(ctx, TemporalRelationV1.BODY_SUPPORT)
    _update(ctx, _state(3, support=False), maternal=False, route=False)
    lost = live_dynamics_overlay_v1(ctx, TemporalRelationV1.BODY_SUPPORT)

    assert supported is not None and lost is not None
    assert supported.support_duration_observations == 2
    assert lost.support_duration_observations == 0
    assert lost.phase is TemporalPhaseV1.INTERRUPTED
    assert "support_lost" in lost.event_labels


def test_slip_is_an_interruption_and_sparse_event() -> None:
    """Slip should interrupt the live phase and appear in sparse event history."""
    ctx = Ctx()
    _update(ctx, _state(1, support=True), maternal=False, route=False)
    _update(ctx, _state(2, support=True, slip=True), maternal=False, route=False)

    support = live_dynamics_overlay_v1(ctx, TemporalRelationV1.BODY_SUPPORT)
    motor = live_dynamics_overlay_v1(ctx, TemporalRelationV1.LOWER_MOTOR)
    assert support is not None and motor is not None
    assert support.slip is True
    assert support.phase is TemporalPhaseV1.INTERRUPTED
    assert motor.phase is TemporalPhaseV1.INTERRUPTED
    assert "slip_detected" in support.event_labels
    assert len(ctx.live_dynamics_event_history_v1) >= 1
    assert all(item["episodic_memory_record"] is False for item in ctx.live_dynamics_event_history_v1)


def test_lower_motor_progress_and_phase_are_consumed_without_trajectory() -> None:
    """Phase 7 should consume progress/phase/error products only."""
    ctx = Ctx()
    _update(
        ctx,
        _state(1, action="policy:follow_mom", progress=0.2, support=True),
        maternal=False,
        route=False,
    )
    _update(
        ctx,
        _state(2, action="policy:follow_mom", progress=0.6, support=True),
        maternal=False,
        route=False,
    )

    motor = live_dynamics_overlay_v1(ctx, TemporalRelationV1.LOWER_MOTOR)
    assert motor is not None
    assert motor.lower_motor_action == "policy:follow_mom"
    assert motor.lower_motor_progress == 0.6
    assert motor.scalar_rate == pytest.approx(0.4)
    assert motor.phase is TemporalPhaseV1.ACTIVE
    assert TemporalExpectedContinuationV1.PROGRESS_NONDECREASING in motor.expected_continuations
    assert live_dynamics_summary_v1(ctx)["lower_motor_trajectory_present"] is False


def test_lower_motor_action_change_resets_progress_rate_suffix() -> None:
    """Progress from different lower-controller tasks must not be spliced together."""
    ctx = Ctx()
    _update(
        ctx,
        _state(1, action="policy:follow_mom", progress=0.8, support=True),
        maternal=False,
        route=False,
    )
    _update(
        ctx,
        _state(2, action="policy:seek_nipple", progress=0.2, support=True),
        maternal=False,
        route=False,
    )

    motor = live_dynamics_overlay_v1(ctx, TemporalRelationV1.LOWER_MOTOR)
    assert motor is not None
    assert motor.lower_motor_action == "policy:seek_nipple"
    assert motor.valid_sample_count == 1
    assert motor.scalar_rate is None
    assert motor.support_status == "insufficient_history"


def test_lower_motor_error_is_structured_interruption_evidence() -> None:
    """A compact controller error should be preserved without modelling movement details."""
    ctx = Ctx()
    _update(
        ctx,
        _state(1, action="policy:follow_mom", progress=0.4, support=True),
        maternal=False,
        route=False,
    )
    _update(
        ctx,
        _state(2, action="policy:follow_mom", progress=0.4, support=True, error="blocked"),
        maternal=False,
        route=False,
    )

    motor = live_dynamics_overlay_v1(ctx, TemporalRelationV1.LOWER_MOTOR)
    assert motor is not None
    assert motor.lower_motor_error == "blocked"
    assert motor.phase is TemporalPhaseV1.INTERRUPTED
    assert "lower_motor_error" in motor.event_labels
    residual = next(item for item in ctx.live_dynamics_state_v1.residuals if item.relation is TemporalRelationV1.LOWER_MOTOR)
    assert residual.residual_fields["lower_motor_error"]["observed"] == "blocked"


def test_dynamic_envelope_is_expected_not_current_truth() -> None:
    """A current overlay may create a compact expected continuation without changing evidence."""
    ctx = Ctx()
    _update(ctx, _state(1, kid_x=0.0), maternal=False)
    _update(ctx, _state(2, kid_x=1.0), maternal=False)

    summary = live_dynamics_summary_v1(ctx)
    envelope = summary["state"]["pending_envelopes"][TemporalRelationV1.SELF_ROUTE.value]
    assert envelope["source_class"] == "expected"
    assert envelope["current_truth"] is False
    assert envelope["creates_navmap_revision"] is False
    assert envelope["contains_motor_trajectory"] is False


def test_constant_route_velocity_remains_within_dynamic_envelope() -> None:
    """A supported continuation should close as within the prior uncertainty envelope."""
    ctx = Ctx()
    ctx.seqerr_window = 2
    _update(ctx, _state(1, kid_x=0.0), maternal=False)
    _update(ctx, _state(2, kid_x=1.0), maternal=False)
    _update(ctx, _state(3, kid_x=2.0), maternal=False)

    residual = next(item for item in ctx.live_dynamics_state_v1.residuals if item.relation is TemporalRelationV1.SELF_ROUTE)
    assert residual.status is TemporalEnvelopeStatusV1.WITHIN_ENVELOPE
    assert residual.mismatch_count == 0
    assert residual.persistent_residual_count == 0
    assert residual.material_change_candidate is False


def test_abrupt_route_velocity_change_produces_structured_residual() -> None:
    """Evidence outside the prior speed/direction envelope should retain local mismatch structure."""
    ctx = Ctx()
    ctx.seqerr_window = 2
    _update(ctx, _state(1, kid_x=0.0), maternal=False)
    _update(ctx, _state(2, kid_x=1.0), maternal=False)
    _update(ctx, _state(3, kid_x=4.0), maternal=False)

    residual = next(item for item in ctx.live_dynamics_state_v1.residuals if item.relation is TemporalRelationV1.SELF_ROUTE)
    assert residual.status is TemporalEnvelopeStatusV1.OUTSIDE_ENVELOPE
    assert residual.mismatch_count >= 1
    assert "speed" in residual.residual_fields
    assert residual.residual_fields["speed"]["mismatch"] is True
    assert residual.persistent_residual_count == 1
    assert residual.material_change_candidate is False


def test_persistent_nonvegetation_residual_crosses_materiality_gate() -> None:
    """Repeated route-envelope violations may become a local material-change candidate."""
    ctx = Ctx()
    ctx.seqerr_window = 2
    ctx.live_dynamics_persistent_residual_observations_v1 = 2
    for step, x in ((1, 0.0), (2, 1.0), (3, 4.0), (4, 8.0)):
        _update(ctx, _state(step, kid_x=x), maternal=False)

    residual = next(item for item in ctx.live_dynamics_state_v1.residuals if item.relation is TemporalRelationV1.SELF_ROUTE)
    assert residual.status is TemporalEnvelopeStatusV1.OUTSIDE_ENVELOPE
    assert residual.persistent_residual_count >= 2
    assert residual.material_change_candidate is True
    assert ctx.live_dynamics_state_v1.materiality.material_change_recommended is True
    assert TemporalRelationV1.SELF_ROUTE in ctx.live_dynamics_state_v1.materiality.persistent_residual_relations


def test_explicit_fallen_tree_event_is_material_but_phase7_does_not_revise_map() -> None:
    """Phase 7 should recommend materiality while leaving actual map revision to the owning domain."""
    ctx = Ctx()
    _update(ctx, _state(1), maternal=False, material_event=True)

    route = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_ROUTE)
    assert route is not None
    assert route.material_event is True
    assert ctx.live_dynamics_state_v1.materiality.material_change_recommended is True
    summary = live_dynamics_summary_v1(ctx)
    assert summary["state"]["materiality"]["phase7_creates_navmap_revision"] is False


def test_phase4b_and_phase7_maternal_trends_are_dual_run_not_replacement() -> None:
    """The generalized relation should compare with and preserve the Phase 4B result."""
    ctx = Ctx()
    for step, kid_x in ((1, 0.0), (2, 0.5), (3, 1.0)):
        _update(ctx, _state(step, kid_x=kid_x, mom_x=3.0))

    comparison = ctx.live_dynamics_state_v1.phase4b_comparison
    assert comparison["status"] == "agreement"
    assert comparison["phase4b_replaced"] is False
    assert comparison["generalized_trend"] == TemporalDistanceTrendV1.APPROACHING.value
    assert comparison["phase4b_trend"] == "approaching"
    assert comparison["agreement"] is True


def test_blackout_preserves_unknown_instead_of_fabricating_motion() -> None:
    """Missing current maternal points must invalidate the trajectory rather than freeze a stale point."""
    ctx = Ctx()
    _update(ctx, _state(1, mom_x=3.0))

    state = _state(2, mom_x=2.5)
    obs = _observe(state)
    obs.env_meta["mom_position"] = None
    obs.env_meta["newborn_obs_blackout"] = True
    obs.env_meta["newborn_obs_blackout_kind"] = "phase7_test"
    _update_maternal(ctx, obs)
    _set_route_overlay(ctx, state, supported=False)
    live_dynamics_observation_step_v1(ctx, obs)

    maternal = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_MATERNAL)
    route = live_dynamics_overlay_v1(ctx, TemporalRelationV1.SELF_ROUTE)
    assert maternal is not None and route is not None
    assert maternal.valid is False
    assert maternal.motion_direction is TemporalMotionDirectionV1.UNKNOWN
    assert maternal.object_speed is None
    assert route.valid is False
    assert route.motion_direction is TemporalMotionDirectionV1.UNKNOWN


def test_sparse_event_history_is_bounded_and_not_per_cycle() -> None:
    """Only event boundaries should enter the bounded Phase 7 event register."""
    ctx = Ctx()
    ctx.live_dynamics_event_history_limit_v1 = 2
    _update(ctx, _state(1, support=True), maternal=False, route=False)
    assert ctx.live_dynamics_event_history_v1 == []

    _update(ctx, _state(2, support=True, slip=True), maternal=False, route=False)
    _update(ctx, _state(3, support=True, error="blocked"), maternal=False, route=False)
    _update(ctx, _state(4, support=False), maternal=False, route=False)

    assert len(ctx.live_dynamics_event_history_v1) == 2
    assert all(item["stores_full_navmap"] is False for item in ctx.live_dynamics_event_history_v1)
    assert all(item["episodic_memory_record"] is False for item in ctx.live_dynamics_event_history_v1)


def test_reset_clears_only_phase7_episode_registers() -> None:
    """Reset should clear live dynamics without deleting shared WNM or other domain maps."""
    ctx = Ctx()
    marker = object()
    ctx.wnm_operative_map_v1 = marker  # type: ignore[assignment]
    _update(ctx, _state(1), maternal=False)
    assert ctx.live_dynamics_state_v1 is not None

    live_dynamics_reset_v1(ctx)

    assert ctx.live_dynamics_observation_no_v1 == 0
    assert ctx.live_dynamics_state_v1 is None
    assert ctx.live_dynamics_pending_envelopes_v1 == {}
    assert ctx.live_dynamics_residual_streak_v1 == {}
    assert ctx.live_dynamics_event_history_v1 == []
    assert ctx.wnm_operative_map_v1 is marker


def test_disabled_and_missing_shared_window_paths_are_explicit() -> None:
    """Disabled/dependency-failure states should be inspectable and non-authoritative."""
    ctx = Ctx()
    obs = _observe(_state(1))
    ctx.live_dynamics_enabled_v1 = False
    disabled = live_dynamics_observation_step_v1(ctx, obs)
    assert disabled["status"] == "disabled"
    assert disabled["policy_selection_mutation_allowed"] is False

    ctx.live_dynamics_enabled_v1 = True
    ctx.seqerr_enabled = False
    dependency = live_dynamics_observation_step_v1(ctx, obs)
    assert dependency["status"] == "dependency_error"
    assert dependency["reason"] == "shared_seqerr_window_disabled"


def test_summary_and_renderers_are_json_safe_and_authority_explicit() -> None:
    """Public Phase 7 diagnostics should serialize and state their authority boundaries."""
    ctx = Ctx()
    _update(ctx, _state(1, support=True))
    summary = live_dynamics_summary_v1(ctx)
    lines = render_live_dynamics_lines_v1(ctx)

    assert summary["authority"] == "source_linked_live_dynamics"
    assert summary["policy_selection_mutation_allowed"] is False
    assert summary["protected_safety_can_be_overridden"] is False
    assert summary["rolling_history_bounded"] is True
    assert summary["separate_from_episodic_memory"] is True
    assert summary["stores_full_navmap_history"] is False
    assert lines[0] == "PHASE 7 GENERAL TEMPORAL BINDING / LIVE DYNAMICS:"
    json.dumps(summary, sort_keys=True)


def test_reporting_includes_full_and_compact_phase7_lines() -> None:
    """Full and mini snapshots should expose the current generalized dynamics readout."""
    ctx = Ctx()
    _update(ctx, _state(1, support=True))
    world = WorldGraph()
    world.ensure_anchor("NOW")

    full = snapshot_text(world, Drives(), ctx)
    mini = mini_snapshot_text(world, ctx)

    assert "PHASE 7 GENERAL TEMPORAL BINDING / LIVE DYNAMICS:" in full
    assert "[dynamics]" in mini
    assert "material=" in mini


def test_phase7_does_not_mutate_drives_or_select_a_policy() -> None:
    """Observation processing should leave behavioral authority and compact drives unchanged."""
    ctx = Ctx()
    drives = Drives(hunger=0.73, fatigue=0.41, warmth=0.62)
    before = drives.to_dict()
    ctx.ac_triggered_policies = ["policy:stand_up"]

    _update(ctx, _state(1, action="policy:follow_mom", support=True))

    assert drives.to_dict() == before
    assert ctx.ac_triggered_policies == ["policy:stand_up"]
    assert live_dynamics_summary_v1(ctx)["policy_selection_mutation_allowed"] is False


def test_navmap_runtime_invokes_phase7_after_current_domain_updates() -> None:
    """The integrated NavMap observation bridge should leave a current Phase 7 state."""
    ctx = Ctx()
    ctx.body_world, ctx.body_ids = init_body_world()
    state = _state(1, action="policy:follow_mom", support=True)
    obs = _observe(state)
    update_body_world_from_obs(ctx, obs)
    seqerr_update_from_obs(ctx, obs)
    ctx.navmap_pending_action_v1 = "policy:follow_mom"

    navmap_ctx_observation_update_step_v1(ctx, obs)

    assert ctx.live_dynamics_state_v1 is not None
    assert ctx.live_dynamics_state_v1.observation_no == 1
    assert ctx.live_dynamics_last_update_v1["schema"] == "temporal_binding_state_v1"
    assert live_dynamics_overlay_v1(ctx, TemporalRelationV1.LOWER_MOTOR) is not None


def test_cycle_summary_contract_contains_no_full_map_movie() -> None:
    """The public state should carry refs/scalars only and reject a serialized full-map history."""
    ctx = Ctx()
    for step in range(1, 4):
        _update(ctx, _state(step, kid_x=float(step - 1)))

    encoded = json.dumps(live_dynamics_summary_v1(ctx), sort_keys=True)
    assert '"stores_full_navmap_history": false' in encoded
    assert '"episodic_memory_record": false' in json.dumps(ctx.seqerr_history, sort_keys=True)
    assert "elements" not in ctx.seqerr_history[-1]["live_dynamics_v1"]["self_route"]
    assert "relations" not in ctx.seqerr_history[-1]["live_dynamics_v1"]["self_route"]
