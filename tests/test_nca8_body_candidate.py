#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Protected BodyMap and candidate-publication tests for NCA8 Phase 1C."""

from __future__ import annotations

from nca8_body import Nca8BodyRuntimeV1
from nca8_maps import Nca8PostureStateV1, create_posture_support_map_library_v1
from nca8_runtime import Nca8SessionV1


def _map_state_v1(profile_id: str, cycle_id: int):
    """Return one canonical current map state for BodyMap tests."""
    library = create_posture_support_map_library_v1()
    evidence = library.evaluate_profile(profile_id)
    return library.update_current_state(
        evidence,
        sampled_event_cycle=cycle_id,
        available_cycle=cycle_id,
        applied_cycle=cycle_id,
    )


def test_bodymap_publishes_candidate_only_for_current_fallen_inadequate_support() -> None:
    """Fallen body evidence may create a candidate but not an executive decision."""
    runtime = Nca8BodyRuntimeV1()
    fallen_state = _map_state_v1("lateral_ground_profile_v1", 1)

    update = runtime.update_from_map_state(fallen_state)
    candidate = update.posture_support_candidate

    assert update.body_state.posture is Nca8PostureStateV1.FALLEN
    assert update.body_state.support.value == "inadequate"
    assert update.body_state.authority == "protected_current_body_state"
    assert update.body_state.as_dict()["is_wnm"] is False
    assert candidate is not None
    assert candidate.source_map_state is fallen_state
    assert candidate.authority == "attention_candidate_only"
    assert candidate.as_dict()["attention_selected"] is False
    assert candidate.as_dict()["primitive_id"] is None
    assert candidate.as_dict()["task_action"] is None


def test_standing_body_state_clears_candidate_without_selecting_a_task() -> None:
    """Standing evidence should remove the body problem candidate, not choose behavior."""
    runtime = Nca8BodyRuntimeV1()
    fallen_state = _map_state_v1("lateral_ground_profile_v1", 1)
    standing_state = _map_state_v1("upright_support_profile_v1", 2)

    first = runtime.update_from_map_state(fallen_state)
    second = runtime.update_from_map_state(standing_state)

    assert first.posture_support_candidate is not None
    assert second.posture_support_candidate is None
    assert second.candidate_event == "cleared"
    assert second.body_state.posture is Nca8PostureStateV1.STANDING
    assert second.body_state.support.value == "stable"
    assert second.body_state.configuration_change_count == 1


def test_unknown_body_evidence_clears_candidate_and_preserves_last_support_time() -> None:
    """Loss of posture evidence should become unknown, not preserve a stale task candidate."""
    library = create_posture_support_map_library_v1()
    runtime = Nca8BodyRuntimeV1()
    fallen_evidence = library.evaluate_profile("lateral_ground_profile_v1")
    fallen_state = library.update_current_state(
        fallen_evidence,
        sampled_event_cycle=1,
        available_cycle=1,
        applied_cycle=1,
    )
    unknown_evidence = library.open_world_evidence(
        Nca8PostureStateV1.UNKNOWN,
        reason="missing_posture_predicate_scaffold",
    )
    unknown_state = library.update_current_state(
        unknown_evidence,
        sampled_event_cycle=2,
        available_cycle=2,
        applied_cycle=2,
    )

    runtime.update_from_map_state(fallen_state)
    update = runtime.update_from_map_state(unknown_state)

    assert update.body_state.posture is Nca8PostureStateV1.UNKNOWN
    assert update.body_state.evidence_current is False
    assert update.body_state.last_supported_cycle == 1
    assert update.posture_support_candidate is None
    assert update.candidate_event == "cleared"


def test_full_session_updates_body_representation_and_reaches_gate_a_commitment() -> None:
    """The integrated Phase-1D cycle should represent fallen posture and commit StandUp."""
    session = Nca8SessionV1()

    result = session.run_cognitive_cycle()

    assert result.posture_support_state.posture is Nca8PostureStateV1.FALLEN
    assert result.body_map_state.posture is Nca8PostureStateV1.FALLEN
    assert result.posture_support_candidate is not None
    assert result.output == "STAND_UP"
    assert result.commitment.focal_operation_id == "application:stand_up:1"
    assert result.commitment.pnm_id == "pnm:application:stand_up:1"
    assert result.commitment.task_action == "STAND_UP"
    assert session.status().current_map_state_count == 1
    assert session.status().posture_support_map_revision == 1


def test_repeated_integrated_cycles_refresh_one_map_and_body_state_slot() -> None:
    """Stable fallen input must not create state, map, or candidate collections per cycle."""
    session = Nca8SessionV1()
    durable = session.durable_posture_support_map

    first = session.run_cognitive_cycle()
    second = session.run_cognitive_cycle()

    assert first.posture_support_state.state_id == second.posture_support_state.state_id
    assert second.posture_support_state.update_count == 2
    assert second.posture_support_state.equivalent_refresh_count == 1
    assert second.body_map_state.update_count == 2
    assert second.body_map_state.equivalent_refresh_count == 1
    assert first.posture_support_candidate is not None
    assert second.posture_support_candidate is not None
    assert first.posture_support_candidate.candidate_id == second.posture_support_candidate.candidate_id
    assert session.durable_posture_support_map is durable
    assert session._map_library.durable_map_count == 1  # pylint: disable=protected-access
    assert session._map_library.current_state_count == 1  # pylint: disable=protected-access
