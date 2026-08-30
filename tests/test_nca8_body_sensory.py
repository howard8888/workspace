#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Predicate-scaffold and body-sensory interpretation tests for Phase 1C."""

from __future__ import annotations

from cca8_env import EnvObservation
from nca8_adapters import NCA8_SCAFFOLD_LEDGER_V1, adapt_env_observation_v1
from nca8_maps import Nca8PostureStateV1, create_posture_support_map_library_v1
from nca8_sensory import Nca8BodySensoryModuleV1


def _observation_v1(predicates: list[str], *, env_meta: dict | None = None):
    """Return one filtered NCA8 observation for body-sensory tests."""
    return adapt_env_observation_v1(
        EnvObservation(
            raw_sensors={},
            predicates=predicates,
            cues=[],
            env_meta=env_meta or {},
        )
    )


def _apply_observation_v1(module: Nca8BodySensoryModuleV1, predicates: list[str], cycle_id: int):
    """Poll, mark applied, and consume one body-sensory result."""
    observation = _observation_v1(predicates)
    result = module.poll_observation(
        observation,
        cycle_id=cycle_id,
        observation_number=cycle_id,
    )
    return module.apply_result(result.mark_applied(cycle_id), cycle_id=cycle_id)


def test_posture_predicate_to_geometry_shortcut_is_explicitly_recorded() -> None:
    """The first current-state shortcut must remain visible as a retireable scaffold."""
    entries = {entry.source_field: entry for entry in NCA8_SCAFFOLD_LEDGER_V1}
    posture_entry = entries["EnvObservation.predicates[posture:fallen|posture:standing]"]

    assert "SELF-ground geometry" in posture_entry.cognitive_meaning
    assert posture_entry.first_phase.startswith("1C")
    assert "vestibular/proprioceptive/contact" in posture_entry.replacement_target
    assert posture_entry.status == "temporary explicit scaffold"


def test_fallen_scaffold_selects_lateral_geometry_and_current_fallen_state() -> None:
    """The explicit shortcut should produce transparent SELF-ground evidence."""
    module = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())

    application = _apply_observation_v1(module, ["posture:fallen"], 1)

    assert application.sample.posture is Nca8PostureStateV1.FALLEN
    assert application.sample.geometry_profile_id == "lateral_ground_profile_v1"
    assert application.evidence.posture is Nca8PostureStateV1.FALLEN
    assert application.evidence.body_ground_angle_degrees == 0.0
    assert application.evidence.foot_ground_contact is True
    assert application.evidence.lateral_contact_fraction == 1.0
    assert application.map_state.posture is Nca8PostureStateV1.FALLEN
    assert application.map_state.support.value == "inadequate"
    assert application.update_kind == "created"
    assert module.pending_sample_count == 0


def test_standing_scaffold_selects_upright_geometry_without_new_durable_map() -> None:
    """Standing should activate another configuration of the same durable map."""
    library = create_posture_support_map_library_v1()
    module = Nca8BodySensoryModuleV1(library)
    signature = library.durable_record_signature()

    first = _apply_observation_v1(module, ["posture:fallen"], 1)
    second = _apply_observation_v1(module, ["posture:standing"], 2)

    assert first.map_state.posture is Nca8PostureStateV1.FALLEN
    assert second.map_state.posture is Nca8PostureStateV1.STANDING
    assert second.sample.geometry_profile_id == "upright_support_profile_v1"
    assert second.map_state.source_map_ref == first.map_state.source_map_ref
    assert second.map_state.configuration_change_count == 1
    assert library.durable_map_count == 1
    assert library.durable_record_signature() == signature


def test_missing_posture_input_remains_unknown_without_fabricating_standing() -> None:
    """Absence of posture evidence must not be interpreted as the opposite state."""
    module = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())

    application = _apply_observation_v1(module, ["proximity:mom:far"], 1)

    assert application.sample.posture is Nca8PostureStateV1.UNKNOWN
    assert application.sample.geometry_profile_id is None
    assert application.evidence.posture is Nca8PostureStateV1.UNKNOWN
    assert application.evidence.active_element_ids == ()
    assert application.map_state.posture is Nca8PostureStateV1.UNKNOWN
    assert application.map_state.evidence_current is False
    assert application.map_state.activation == 0.0


def test_conflicting_posture_tokens_remain_ambiguous_without_selecting_geometry() -> None:
    """Mutually incompatible scaffold tokens should preserve ambiguity."""
    module = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())

    application = _apply_observation_v1(
        module,
        ["posture:fallen", "posture:standing"],
        1,
    )

    assert application.sample.posture is Nca8PostureStateV1.AMBIGUOUS
    assert application.sample.geometry_profile_id is None
    assert application.evidence.posture is Nca8PostureStateV1.AMBIGUOUS
    assert application.map_state.posture is Nca8PostureStateV1.AMBIGUOUS
    assert application.map_state.support.value == "ambiguous"
    assert application.map_state.activation == 0.5


def test_hidden_stage_and_milestone_metadata_cannot_change_body_interpretation() -> None:
    """The first NCA8 sensory circuit must depend only on filtered posture evidence."""
    first_module = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())
    second_module = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())
    first_observation = _observation_v1(
        ["posture:fallen"],
        env_meta={
            "scenario_stage": "rest",
            "milestones": ["stood_up", "rested"],
            "oracle_policy": "policy:stand_up",
        },
    )
    second_observation = _observation_v1(["posture:fallen"])

    first_result = first_module.poll_observation(first_observation, cycle_id=1, observation_number=1)
    second_result = second_module.poll_observation(second_observation, cycle_id=1, observation_number=1)
    first = first_module.apply_result(first_result.mark_applied(1), cycle_id=1)
    second = second_module.apply_result(second_result.mark_applied(1), cycle_id=1)

    assert first.sample.as_dict() == second.sample.as_dict()
    assert first.map_state.as_dict() == second.map_state.as_dict()
