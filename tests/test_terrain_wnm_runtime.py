# -*- coding: utf-8 -*-
"""Phase 6 tests for terrain, hazards, lateral route sheets, and safety readouts."""

from __future__ import annotations

import json

import cca8_run
from cca8_context import Ctx
from cca8_controller import Drives
from cca8_env import EnvObservation, EnvState, PerceptionAdapter
from cca8_navmap_kernel import NavFrameV1, NavMapV2, NavProvenanceV1, NavSourceClassV1
from cca8_navpatch import CELL_UNKNOWN, SurfaceGridV1
from cca8_policy_runtime import (
    _follow_mom_legacy_gate_evaluation_v1,
    _gate_rest_trigger_body_space,
)
from cca8_reporting import mini_snapshot_text, snapshot_text
from cca8_terrain import (
    TerrainHazardInterpretationV1,
    TerrainLandmarkReacquisitionV1,
    TerrainLandmarkTrackStatusV1,
    TerrainRouteRelationV1,
    render_terrain_lines_v1,
    terrain_motion_veto_v1,
    terrain_policy_readout_v1,
    terrain_reset_v1,
    terrain_safe_to_rest_v1,
    terrain_summary_v1,
    terrain_wnm_observation_step_v1,
)
from cca8_wnm_runtime import (
    WNMTransitionTypeV1,
    wnm_commit_transition_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
)
from cca8_world_graph import WorldGraph


_OVERVIEW_ROLE = "self_maternal_scene"
_WEST_ROLE = "terrain_route_west"
_EAST_ROLE = "terrain_route_east"


def _overview() -> NavMapV2:
    """Return one minimal current overview suitable for route acquisition."""
    provenance = NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref="test:phase6_self_maternal_overview",
        quality=0.90,
    )
    return NavMapV2(
        map_id="test_self_maternal_overview",
        revision=1,
        role=_OVERVIEW_ROLE,
        frame=NavFrameV1(
            frame_id="test_overview_frame",
            x_axis="world_x",
            y_axis="world_y",
            units="m",
            min_x=-10.0,
            max_x=10.0,
            min_y=-10.0,
            max_y=10.0,
        ),
        provenance=provenance,
    )


def _ctx_with_overview() -> Ctx:
    """Return a context whose one operative WNM is the coarse overview."""
    ctx = Ctx()
    overview = _overview()
    ctx.feeding_overview_map_v1 = overview
    wnm_commit_transition_v1(
        ctx,
        overview,
        transition_type=WNMTransitionTypeV1.INITIALIZE,
        observation_no=1,
        reason="test_initialize_overview_before_phase6",
        identity_handle="self_individual",
        correspondence_basis="unit_test_current_overview",
        support=1.0,
    )
    return ctx


def _state(
    *,
    position: str = "cliff_edge",
    x: float = 0.0,
    stage: str = "first_stand",
    step_index: int = 1,
) -> EnvState:
    """Return one deterministic standing route-task environment state."""
    state = EnvState(
        kid_posture="standing",
        mom_distance="far",
        shelter_distance="far",
        cliff_distance="near" if position == "cliff_edge" else "far",
        nipple_state="hidden",
        scenario_stage=stage,
        kid_position=(x, 0.0),
        mom_position=(3.0, 0.0),
        step_index=step_index,
        position=position,
        zone="unsafe" if position == "cliff_edge" else "neutral",
    )
    return state


def _observe(state: EnvState) -> EnvObservation:
    """Return the current perception packet for one deterministic state."""
    return PerceptionAdapter().observe(state)


def _enter_west(ctx: Ctx, *, step_index: int = 1) -> EnvState:
    """Acquire the west route sheet and return its environment state."""
    state = _state(step_index=step_index)
    terrain_wnm_observation_step_v1(ctx, _observe(state))
    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _WEST_ROLE
    return state


def _shift_east(ctx: Ctx, state: EnvState, *, step_index: int = 2) -> EnvState:
    """Move SELF into overlap and commit the west-to-east lateral shift."""
    state.position = "open_field"
    state.zone = "neutral"
    state.cliff_distance = "far"
    state.kid_position = (0.80, 0.0)
    state.step_index = step_index
    terrain_wnm_observation_step_v1(ctx, _observe(state))
    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _EAST_ROLE
    return state


def test_phase6_defaults_and_registry_are_current() -> None:
    """Phase 6 context defaults and component-registry entries should agree."""
    ctx = Ctx()

    assert ctx.terrain_wnm_enabled_v1 is True
    assert ctx.terrain_state_v1 is None
    assert ctx.terrain_history_v1 == []
    assert ctx.terrain_route_claims_wnm_v1 is False

    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)  # pylint: disable=protected-access
    assert registry["terrain"] == "cca8_terrain"
    assert len(cca8_run.PRIMITIVES) == 8


def test_perception_packet_is_bounded_evidence_not_route_or_motor_authority() -> None:
    """The adapter should expose terrain evidence without route decisions or trajectories."""
    packet = _observe(_state()).env_meta["terrain_geometry_v1"]

    assert packet["schema"] == "terrain_geometry_v1"
    assert packet["self_world_point"] == {"x": 0.0, "y": 0.0}
    assert packet["landmark_world_point"] == {"x": 0.8, "y": 0.4}
    assert packet["periodic_vegetation_is_dynamic_only"] is True
    assert packet["lower_locomotor_trajectory_delegated"] is True
    assert "selected_route" not in packet
    assert "selected_policy" not in packet
    assert "motor_trajectory" not in packet
    json.dumps(packet, sort_keys=True)


def test_overview_to_west_route_acquisition_changes_real_operative_substrate() -> None:
    """An active route task should zoom from overview into the west route sheet."""
    ctx = _ctx_with_overview()
    summary = terrain_wnm_observation_step_v1(ctx, _observe(_state()))

    operative = wnm_operative_map_v1(ctx)
    assert operative is not None
    assert operative.role == _WEST_ROLE
    assert [item.role for item in wnm_ready_maps_v1(ctx)] == [_OVERVIEW_ROLE]
    assert summary["state"]["transition_attempted"] is True
    assert summary["state"]["transition_accepted"] is True
    assert summary["state"]["route_claims_wnm"] is True
    assert summary["wnm"]["operative_count"] == 1


def test_lateral_shift_uses_overlap_landmark_transform_and_preserves_self() -> None:
    """West-to-east shift should commit only through explicit overlap correspondence."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    state = _shift_east(ctx, state)

    summary = terrain_summary_v1(ctx)
    correspondence = summary["state"]["lateral_correspondence"]
    transition = summary["wnm"]["last_transition"]

    assert transition["transition_type"] == "lateral_shift"
    assert transition["accepted"] is True
    assert correspondence["source_and_destination_overlap"] is True
    assert correspondence["no_teleport_discontinuity"] is True
    assert correspondence["self_continuity_error"] == 0.0
    assert correspondence["landmark_continuity_error"] == 0.0
    assert correspondence["transform"]["translation_x"] == 0.75
    assert correspondence["self_world_point"] == {"x": 0.8, "y": 0.0}
    assert [item.role for item in wnm_ready_maps_v1(ctx)] == [_OVERVIEW_ROLE, _WEST_ROLE]


def test_ambiguous_lateral_correspondence_is_rejected_atomically() -> None:
    """Ambiguous correspondence must leave west operative and the ready set unchanged."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    ready_before = tuple(wnm_ready_maps_v1(ctx))
    state.position = "open_field"
    state.zone = "neutral"
    state.cliff_distance = "far"
    state.kid_position = (0.80, 0.0)
    state.step_index = 2
    state.terrain_route_correspondence_ambiguous = True

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))

    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _WEST_ROLE
    assert tuple(wnm_ready_maps_v1(ctx)) == ready_before
    assert summary["wnm"]["last_transition"]["accepted"] is False
    assert summary["wnm"]["last_transition"]["failure_reason"] == "cross_map_correspondence_ambiguous"


def test_known_occluder_retains_landmark_identity_and_bounded_shift_support() -> None:
    """One known occlusion may coast the stationary landmark without deleting identity."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    state.position = "open_field"
    state.zone = "neutral"
    state.cliff_distance = "far"
    state.kid_position = (0.80, 0.0)
    state.step_index = 2
    state.terrain_landmark_observability = "occluded"

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))
    landmark = summary["state"]["landmark_continuity"]

    assert landmark["identity_retained"] is True
    assert landmark["track_status"] == TerrainLandmarkTrackStatusV1.COASTING.value
    assert landmark["current_location_world"] is None
    assert landmark["last_supported_location_world"] == {"x": 0.8, "y": 0.4}
    assert landmark["correspondence_support"] == 0.70
    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _EAST_ROLE


def test_reliable_negative_landmark_evidence_blocks_shift_without_deleting_identity() -> None:
    """Reliable negative evidence should withdraw transition support and preserve identity history."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    state.position = "open_field"
    state.zone = "neutral"
    state.cliff_distance = "far"
    state.kid_position = (0.80, 0.0)
    state.step_index = 2
    state.terrain_landmark_negative_evidence = True

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))
    landmark = summary["state"]["landmark_continuity"]

    assert landmark["identity_retained"] is True
    assert landmark["negative_evidence_reliable"] is True
    assert landmark["track_status"] == TerrainLandmarkTrackStatusV1.LOST.value
    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _WEST_ROLE
    assert summary["wnm"]["last_transition"]["accepted"] is False


def test_landmark_reacquisition_restores_active_track_after_missingness() -> None:
    """Compatible reappearance should reacquire the same stationary landmark identity."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    state.stage = "birth"  # keep route sheet operative but suppress a lateral attempt
    state.terrain_landmark_observability = "occluded"
    state.step_index = 2
    terrain_wnm_observation_step_v1(ctx, _observe(state))

    state.terrain_landmark_observability = "observed"
    state.step_index = 3
    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))
    landmark = summary["state"]["landmark_continuity"]

    assert landmark["track_status"] == TerrainLandmarkTrackStatusV1.ACTIVE.value
    assert landmark["reacquisition"] == TerrainLandmarkReacquisitionV1.REACQUIRED.value
    assert landmark["identity_handle"] == "route_landmark_boulder_v1"


def test_backtrack_returns_from_east_to_ready_west_sheet() -> None:
    """A supported backtrack should promote the exact ready west map without teleportation."""
    ctx = _ctx_with_overview()
    state = _shift_east(ctx, _enter_west(ctx))
    state.terrain_backtrack_requested = True
    state.step_index = 3

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))

    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _WEST_ROLE
    assert summary["wnm"]["last_transition"]["transition_type"] == "return"
    assert summary["wnm"]["last_transition"]["accepted"] is True
    assert summary["state"]["lateral_correspondence"]["no_teleport_discontinuity"] is True


def test_periodic_vegetation_motion_does_not_create_route_revisions() -> None:
    """Harmless branch oscillation belongs to live dynamics, not immutable route history."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    west = ctx.terrain_route_west_map_v1
    east = ctx.terrain_route_east_map_v1
    assert west is not None and east is not None
    west_sig = west.content_signature()
    east_sig = east.content_signature()

    for step_index in range(2, 8):
        state.stage = "birth"  # suppress lateral handoff while keeping west operative
        state.step_index = step_index
        terrain_wnm_observation_step_v1(ctx, _observe(state))

    assert ctx.terrain_route_west_map_v1 is west
    assert ctx.terrain_route_east_map_v1 is east
    assert ctx.terrain_route_west_map_v1.content_signature() == west_sig
    assert ctx.terrain_route_east_map_v1.content_signature() == east_sig
    assert ctx.terrain_material_revision_history_v1 == []
    assert ctx.terrain_dynamic_overlay_v1.vegetation_motion_dynamic_only is True


def test_fallen_tree_revises_only_east_route_and_adds_motion_veto() -> None:
    """A material obstacle should create one east revision and block the forward route."""
    ctx = _ctx_with_overview()
    state = _shift_east(ctx, _enter_west(ctx))
    west_before = ctx.terrain_route_west_map_v1
    east_before = ctx.terrain_route_east_map_v1
    assert west_before is not None and east_before is not None
    west_signature = west_before.content_signature()
    state.terrain_tree_fallen = True
    state.step_index = 3

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))
    east_after = ctx.terrain_route_east_map_v1

    assert east_after is not None
    assert east_before.revision == 1
    assert east_after.revision == 2
    assert ctx.terrain_route_west_map_v1.content_signature() == west_signature
    assert summary["state"]["material_revision"]["creates_revision"] is True
    assert summary["state"]["material_revision"]["reason"] == "fallen_tree_changed_traversability"
    assert summary["policy_readout"]["route_clear"] is False
    assert summary["policy_readout"]["motion_veto"] is True
    assert summary["policy_readout"]["hazard_interpretation"] == TerrainHazardInterpretationV1.ROUTE_BLOCKED.value
    assert terrain_motion_veto_v1(ctx) is True


def test_wnm_surfacegrid_is_dual_run_and_does_not_replace_legacy_grid() -> None:
    """Phase 6 projection should compare with but never overwrite the current legacy grid."""
    ctx = _ctx_with_overview()
    legacy = SurfaceGridV1(16, 16, [CELL_UNKNOWN] * (16 * 16))
    ctx.wm_surfacegrid = legacy

    summary = terrain_wnm_observation_step_v1(ctx, _observe(_state()))
    comparison = summary["surfacegrid_comparison"]

    assert ctx.wm_surfacegrid is legacy
    assert ctx.terrain_surfacegrid_v1 is not legacy
    assert comparison["status"] == "compared"
    assert comparison["legacy_surfacegrid_replaced"] is False
    assert comparison["comparable_shape"] is True
    assert comparison["grid_overlap_fraction"] is not None


def test_blackout_preserves_unknown_and_forces_legacy_policy_fallback() -> None:
    """Missing current terrain evidence must not fabricate route or safety booleans."""
    ctx = _ctx_with_overview()
    state = _enter_west(ctx)
    state.newborn_obs_blackout_until_step = 5
    state.newborn_obs_blackout_kind = "transition"
    state.step_index = 2

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))
    readout = summary["policy_readout"]

    assert readout["current_evidence_supported"] is False
    assert readout["route_relation"] == TerrainRouteRelationV1.UNKNOWN.value
    assert readout["hazard_interpretation"] == TerrainHazardInterpretationV1.UNKNOWN.value
    assert readout["cliff_near"] is None
    assert readout["safe_to_rest"] is None
    assert readout["route_clear"] is None
    assert readout["motion_veto"] is None
    assert terrain_motion_veto_v1(ctx) is None
    assert terrain_safe_to_rest_v1(ctx) is None


def test_source_linked_readout_records_map_grid_frame_thresholds_and_freshness() -> None:
    """Authoritative terrain scalars should preserve their source and derivation contract."""
    ctx = _ctx_with_overview()
    terrain_wnm_observation_step_v1(ctx, _observe(_state()))
    readout = terrain_policy_readout_v1(ctx)

    assert readout is not None
    row = readout.as_dict()
    assert row["operative_map_ref"]["map_id"] == "goat_route_cliff_to_field_v2"
    assert row["source_grid_sig16"]
    assert row["source_frame_id"] == "route_west_sheet_frame_v1"
    assert row["freshness"] == "fresh"
    assert row["derivation_operator"] == "operative_route_navmap_plus_live_self_overlay_v1"
    assert row["thresholds"]["cliff_near_distance"] == 0.45
    assert row["source_linked"] is True
    assert row["protected_safety_can_be_weakened"] is False


def test_phase6_motion_veto_becomes_a_protected_followmom_false_result() -> None:
    """A current route obstruction may block FollowMom but never bypass protection."""
    ctx = _ctx_with_overview()
    state = _shift_east(ctx, _enter_west(ctx))
    state.terrain_tree_fallen = True
    state.step_index = 3
    terrain_wnm_observation_step_v1(ctx, _observe(state))
    world = WorldGraph()
    world.ensure_anchor("NOW")
    world.add_predicate("posture:standing", attach="now")

    result = _follow_mom_legacy_gate_evaluation_v1(world, ctx)

    assert result.triggered is False
    assert result.protected_veto is True
    assert result.reason == "phase6_terrain_route_safety_veto"


def test_phase6_unsafe_rest_readout_adds_veto_without_changing_drive_state() -> None:
    """Unsafe terrain may suppress Rest while leaving compact drives untouched."""
    ctx = _ctx_with_overview()
    terrain_wnm_observation_step_v1(ctx, _observe(_state()))
    world = WorldGraph()
    world.ensure_anchor("NOW")
    drives = Drives(fatigue=0.95)
    before = drives.to_dict()

    assert terrain_safe_to_rest_v1(ctx) is False
    assert _gate_rest_trigger_body_space(world, drives, ctx) is False
    assert drives.to_dict() == before


def test_route_completion_returns_to_ready_overview() -> None:
    """Reaching shelter should restore the coarse overview through a real return transition."""
    ctx = _ctx_with_overview()
    state = _shift_east(ctx, _enter_west(ctx))
    state.position = "shelter_area"
    state.zone = "safe"
    state.shelter_distance = "near"
    state.kid_position = (1.60, 0.0)
    state.step_index = 3

    summary = terrain_wnm_observation_step_v1(ctx, _observe(state))

    assert wnm_operative_map_v1(ctx) is not None
    assert wnm_operative_map_v1(ctx).role == _OVERVIEW_ROLE
    assert summary["wnm"]["last_transition"]["transition_type"] == "return"
    assert summary["wnm"]["last_transition"]["accepted"] is True


def test_histories_are_bounded_json_safe_and_do_not_store_navmap_movie() -> None:
    """Phase 6 histories should store compact rows under explicit limits."""
    ctx = _ctx_with_overview()
    ctx.terrain_history_limit_v1 = 3
    state = _enter_west(ctx)
    for step_index in range(2, 10):
        state.stage = "birth"
        state.step_index = step_index
        terrain_wnm_observation_step_v1(ctx, _observe(state))

    json.dumps(ctx.terrain_history_v1, sort_keys=True)
    json.dumps(terrain_summary_v1(ctx), sort_keys=True)
    assert len(ctx.terrain_history_v1) == 3
    assert all("west_route_map" not in row for row in ctx.terrain_history_v1)
    assert all("east_route_map" not in row for row in ctx.terrain_history_v1)
    assert all(row["dynamic_overlay"]["stores_full_navmap_history"] is False for row in ctx.terrain_history_v1)


def test_reset_clears_phase6_episode_state_without_destroying_generic_wnm() -> None:
    """Terrain reset should clear domain registers while preserving the shared WNM runtime."""
    ctx = _ctx_with_overview()
    _enter_west(ctx)
    operative_before = wnm_operative_map_v1(ctx)

    terrain_reset_v1(ctx)

    assert ctx.terrain_state_v1 is None
    assert ctx.terrain_route_west_map_v1 is None
    assert ctx.terrain_route_east_map_v1 is None
    assert ctx.terrain_history_v1 == []
    assert ctx.terrain_route_claims_wnm_v1 is False
    assert wnm_operative_map_v1(ctx) is operative_before


def test_full_mini_and_renderer_expose_route_authority_without_mutation() -> None:
    """Human-readable output should expose route role, hazard, and dual-run status."""
    ctx = _ctx_with_overview()
    terrain_wnm_observation_step_v1(ctx, _observe(_state()))
    world = WorldGraph()
    world.ensure_anchor("NOW")

    before = terrain_summary_v1(ctx)
    mini = mini_snapshot_text(world, ctx=ctx, limit=1)
    full = snapshot_text(world, drives=Drives(), ctx=ctx, policy_rt=None)
    rendered = render_terrain_lines_v1(ctx)
    after = terrain_summary_v1(ctx)

    assert "[terrain] role=terrain_route_west" in mini
    assert "PHASE 6 TERRAIN / LATERAL ROUTE WNM:" in full
    assert rendered[0] == "PHASE 6 TERRAIN / LATERAL ROUTE WNM:"
    assert before == after
