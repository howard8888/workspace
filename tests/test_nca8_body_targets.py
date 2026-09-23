#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H3: body-dependent mapping, local evidence and nonexecuting resource ownership."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

from cca8_env import HybridEnvironment
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import (
    BodyAxisCapabilityV1,
    BodyMovementRequestV1,
    BodyTargetBindingV1,
    BodyTargetMapperV1,
    BodyTargetProposalV1,
    BodyTargetReservationV1,
    nominal_body_capabilities_v1,
)
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1,
    CommittedBodyTargetV1,
    FocalMotorEvidenceV1,
    SensorimotorTargetKindV1,
    TargetOriginV1,
)

ROOT = Path(__file__).resolve().parents[1]
STREAM = MotorStreamRefV1("h3-test", 1)
ORIGIN = TargetOriginV1(STREAM, "task:fixture", "application:1", "envelope:1")
TILT = SensorimotorTargetKindV1.ORIENTATION_ADJUST
EXTEND = SensorimotorTargetKindV1.SUPPORT_EXTENSION
CAPABILITIES = nominal_body_capabilities_v1()


def _feedback(**changes):
    return replace(MotorFeedbackV1(STREAM, 1, 0, 0, 30.0, 0.4, True, 0.2, 0.3), **changes)


def _mapper(feedback=None, capabilities=CAPABILITIES, **options):
    mapper = BodyTargetMapperV1(STREAM, capabilities, **options)
    mapper.update_feedback(feedback if feedback is not None else _feedback(), at_tick=0)
    return mapper


def _request(**changes):
    return replace(BodyMovementRequestV1(ORIGIN, 0.0, 0.6), **changes)


def _targets(proposal):
    return {binding.target.kind: binding.target for binding in proposal.bindings}


def _reserved(mapper, **request_changes):
    proposal = mapper.propose(_request(**request_changes), at_tick=0)
    return mapper.reserve(proposal, execution_id="execution:1", at_tick=0)


def _snapshot(mapper, tick):
    return json.dumps({
        "body": mapper.body_view(at_tick=tick),
        "reserved": [item.as_dict() for item in mapper.reservations(at_tick=tick)],
    }, sort_keys=True, allow_nan=False)


@pytest.mark.parametrize("tilt, expected", [(30.0, 18.0), (-30.0, -18.0), (7.0, 0.0), (-7.0, 0.0), (0.0, 0.0)])
def test_same_requirement_uses_measured_pose_to_choose_direction_and_extent(tilt, expected):
    mapper = _mapper(_feedback(body_tilt_degrees=tilt))
    request = _request()
    proposal = mapper.propose(request, at_tick=0)
    targets = _targets(proposal)
    assert targets[TILT].endpoint == pytest.approx(expected)
    assert targets[TILT].offset == pytest.approx(expected - tilt)
    assert targets[EXTEND].endpoint == pytest.approx(0.6)
    assert proposal.request is request and not proposal.withheld
    assert mapper.reservations(at_tick=0) == ()


@pytest.mark.parametrize("goal, expected", [(45.0, 42.0), (35.0, 35.0), (20.0, 20.0), (-30.0, 18.0)])
def test_mapper_follows_supplied_requirement_not_a_hidden_upright_strategy(goal, expected):
    proposal = _mapper().propose(_request(desired_tilt_degrees=goal), at_tick=0)
    assert _targets(proposal)[TILT].endpoint == pytest.approx(expected)
    assert proposal.request.desired_tilt_degrees == goal


@pytest.mark.parametrize("extension, expected", [(0.0, 0.2), (0.4, 0.6), (0.55, 0.6), (0.9, 0.7)])
def test_extension_is_anchored_and_bounded_in_both_directions(extension, expected):
    mapper = _mapper(_feedback(support_extension=extension))
    target = _targets(mapper.propose(_request(), at_tick=0))[EXTEND]
    assert target.endpoint == pytest.approx(expected)
    assert target.basis_coordinate == extension
    assert target.max_displacement == 0.25


def test_capability_binding_is_canonical_and_not_registration_order_selection():
    first = _mapper().propose(_request(), at_tick=0)
    second = _mapper(capabilities=tuple(reversed(CAPABILITIES))).propose(_request(), at_tick=0)
    assert first.as_dict() == second.as_dict()
    assert [binding.capability.capability_id for binding in first.bindings] == [
        "smp:orientation_adjust:v1", "smp:support_extension:v1",
    ]


@pytest.mark.parametrize("capabilities, available", [((), set()), ((CAPABILITIES[0],), {TILT}), ((CAPABILITIES[1],), {EXTEND})])
def test_omitted_capability_withholds_only_that_family(capabilities, available):
    proposal = _mapper(capabilities=capabilities).propose(_request(), at_tick=0)
    assert set(_targets(proposal)) == available
    assert {reason for _, reason in proposal.withheld} <= {"capability_unavailable"}
    assert {kind for kind, _ in proposal.withheld} == {TILT, EXTEND} - available


def test_narrower_step_range_and_rate_lease_budget_are_visible():
    reduced = replace(CAPABILITIES[0], maximum_step=4.0, maximum_excursion=6.0, maximum_rate=20.0)
    target = _targets(_mapper(capabilities=(reduced,)).propose(_request(desired_extension=None), at_tick=0))[TILT]
    assert target.endpoint == 26.0 and target.max_rate == 20.0 and target.max_displacement == 6.0
    limited = replace(CAPABILITIES[0], minimum_coordinate=-40.0, maximum_coordinate=35.0)
    proposal = _mapper(capabilities=(limited,)).propose(_request(desired_tilt_degrees=60.0, desired_extension=None), at_tick=0)
    assert proposal.request.desired_tilt_degrees == 60.0
    assert _targets(proposal)[TILT].endpoint == 35.0
    short = _mapper().propose(_request(lease_ticks=1), at_tick=0)
    assert _targets(short)[TILT].offset == -3.0
    assert _targets(short)[EXTEND].offset == pytest.approx(0.05)


def test_too_little_rate_time_to_leave_tolerance_withholds_pointless_movement():
    slow = replace(CAPABILITIES[0], maximum_rate=1.0)
    proposal = _mapper(capabilities=(slow, CAPABILITIES[1])).propose(_request(), at_tick=0)
    assert dict(proposal.withheld)[TILT] == "insufficient_motion_budget"
    assert set(_targets(proposal)) == {EXTEND}


@pytest.mark.parametrize("changes, available, reason", [
    ({"body_tilt_degrees": None}, {EXTEND}, "required_coordinate_missing"),
    ({"support_extension": None}, {TILT}, "required_coordinate_missing"),
    ({"support_contact": None}, {EXTEND}, "required_support_evidence_missing"),
    ({"useful_loading": None}, {EXTEND}, "required_support_evidence_missing"),
    ({"support_contact": False, "useful_loading": 0.0}, {EXTEND}, "loaded_support_unavailable"),
    ({"support_contact": True, "useful_loading": 0.0}, {EXTEND}, "loaded_support_unavailable"),
    ({"support_contact": False, "useful_loading": 0.2}, {EXTEND}, "inconsistent_support_evidence"),
])
def test_missing_or_inconsistent_evidence_refuses_only_affected_target(changes, available, reason):
    proposal = _mapper(_feedback(**changes)).propose(_request(), at_tick=0)
    assert set(_targets(proposal)) == available
    assert {value for _, value in proposal.withheld} == {reason}


def test_unknown_rate_or_destabilization_is_not_invented_or_a_first_attempt_deadlock():
    mapper = _mapper(_feedback(destabilization=None))
    proposal = mapper.propose(_request(), at_tick=0)
    assert len(proposal.bindings) == 2
    assert all(binding.target.basis.destabilization is None for binding in proposal.bindings)
    assert "rate" not in mapper.body_view(at_tick=0)


def test_outside_known_capability_coordinate_range_is_explicit():
    small = replace(CAPABILITIES[0], minimum_coordinate=-20.0, maximum_coordinate=20.0)
    proposal = _mapper(capabilities=(small, CAPABILITIES[1])).propose(_request(), at_tick=0)
    assert dict(proposal.withheld)[TILT] == "body_outside_capability_range"
    assert set(_targets(proposal)) == {EXTEND}


def test_one_fresh_sample_is_enough_for_mapping_without_previous_action():
    mapper = BodyTargetMapperV1(STREAM, CAPABILITIES)
    missing = mapper.propose(_request(), at_tick=0)
    assert not missing.bindings
    assert mapper.update_feedback(_feedback(), at_tick=0) == "accepted"
    assert len(mapper.propose(_request(), at_tick=0).bindings) == 2


def test_real_h2_sensor_reading_supplies_basis_but_mapper_does_not_advance_world():
    world = HybridEnvironment()
    feedback = world.reset_motor(stream_id=STREAM.stream_id)
    mapper = BodyTargetMapperV1(feedback.stream, CAPABILITIES)
    mapper.update_feedback(MotorFeedbackV1.from_dict(feedback.as_dict()), at_tick=0)
    before = world.motor_body, world.motor_elapsed_seconds, world.observe_motor()
    proposal = mapper.propose(_request(), at_tick=0)
    assert before == (world.motor_body, world.motor_elapsed_seconds, world.observe_motor())
    assert _targets(proposal)[TILT].endpoint == 18.0
    with pytest.raises(TypeError):
        world.step_motor(proposal.bindings[0].target)
    assert before == (world.motor_body, world.motor_elapsed_seconds, world.observe_motor())


def test_delivered_measurements_change_next_mapping_not_previous_anchor_or_focal_sample():
    world = HybridEnvironment()
    first = world.reset_motor(stream_id=STREAM.stream_id)
    mapper = _mapper(first)
    prior_focal = FocalMotorEvidenceV1(first, 1, 0)
    prior_bytes = json.dumps(prior_focal.as_dict(), sort_keys=True)
    proposal = mapper.propose(_request(), at_tick=0)
    original = _targets(proposal)[TILT]
    world.step_motor(MotorCommandV1(first.stream, 1, 0, -0.5, 0.5))
    due = world.step_motor(None)
    assert len(due) == 1 and due[0].event_tick == 1 and due[0].available_tick == 2
    mapper.update_feedback(due[0], at_tick=2)
    newer = _targets(mapper.propose(_request(), at_tick=2))[TILT]
    assert original.endpoint == 18.0 and original.basis.event_tick == 0
    assert newer.endpoint == pytest.approx(due[0].body_tilt_degrees - 12.0)
    assert newer.basis.sample_id != original.basis.sample_id
    assert json.dumps(prior_focal.as_dict(), sort_keys=True) == prior_bytes


def test_absent_surface_fixture_still_permits_extension_but_never_fabricates_contact():
    world = HybridEnvironment()
    sensed = world.reset_motor(stream_id=STREAM.stream_id, profile=MotorWorldProfileV1(surface_present=False))
    proposal = _mapper(sensed).propose(_request(), at_tick=0)
    assert dict(proposal.withheld)[TILT] == "loaded_support_unavailable"
    target = _targets(proposal)[EXTEND]
    assert target.endpoint == pytest.approx(0.6)
    assert target.basis.support_contact is False and target.basis.useful_loading == 0.0


@pytest.mark.parametrize("age, status", [(0, "current"), (1, "current"), (2, "current"), (3, "stale"), (10, "stale")])
def test_currentness_is_acquisition_age_not_age_of_last_read(age, status):
    mapper = _mapper()
    mapper.update_feedback(_feedback(), at_tick=age)
    assert mapper.body_view(at_tick=age)["status"] == status
    assert mapper.body_view(at_tick=age)["age_ticks"] == age
    assert bool(mapper.propose(_request(), at_tick=age).bindings) == (status == "current")


def test_explicit_missing_report_withholds_instead_of_using_retained_coordinates():
    mapper = _mapper()
    assert mapper.update_feedback(None, at_tick=1) == "unavailable"
    view = mapper.body_view(at_tick=1)
    assert view["status"] == "unavailable" and view["feedback"]["event_tick"] == 0
    proposal = mapper.propose(_request(), at_tick=1)
    assert not proposal.bindings
    assert {reason for _, reason in proposal.withheld} == {"current_body_feedback_unavailable"}
    assert mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=2), at_tick=2) == "accepted"
    assert len(mapper.propose(_request(), at_tick=2).bindings) == 2


def test_partial_new_sample_does_not_backfill_missing_tilt_from_old_sample():
    mapper = _mapper()
    mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=2, body_tilt_degrees=None), at_tick=2)
    proposal = mapper.propose(_request(), at_tick=2)
    assert set(_targets(proposal)) == {EXTEND}
    assert mapper.body_view(at_tick=2)["feedback"]["body_tilt_degrees"] is None


@pytest.mark.parametrize("bad", [
    _feedback(available_tick=2),
    _feedback(stream=MotorStreamRefV1("foreign", 1)),
    _feedback(stream=MotorStreamRefV1(STREAM.stream_id, 2)),
    _feedback(body_tilt_degrees=25.0),
    _feedback(sample_id=2),
    {}, True, 3,
])
def test_invalid_future_foreign_or_conflicting_feedback_has_no_mutation(bad):
    mapper = _mapper()
    proposal = mapper.propose(_request(), at_tick=0)
    before = _snapshot(mapper, 0)
    with pytest.raises((ValueError, TypeError)):
        mapper.update_feedback(bad, at_tick=0)
    assert _snapshot(mapper, 0) == before
    assert len(mapper.reserve(proposal, execution_id="execution:1", at_tick=0)) == 2


def test_older_arrival_does_not_replace_newer_current_evidence():
    mapper = _mapper()
    newer = _feedback(sample_id=3, event_tick=2, available_tick=2, body_tilt_degrees=20.0)
    mapper.update_feedback(newer, at_tick=2)
    assert mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=2), at_tick=2) == "older_ignored"
    assert mapper.body_view(at_tick=2)["feedback"] == newer.as_dict()


def test_duplicate_does_not_invalidate_unchanged_pending_proposal():
    mapper = _mapper()
    proposal = mapper.propose(_request(), at_tick=0)
    assert mapper.update_feedback(_feedback(), at_tick=1) == "reread"
    assert len(mapper.reserve(proposal, execution_id="execution:1", at_tick=1)) == 2


def test_mapping_and_body_side_reservation_are_explicitly_different():
    mapper = _mapper()
    proposal = mapper.propose(_request(), at_tick=0)
    assert mapper.reservations(at_tick=0) == ()
    reservations = mapper.reserve(proposal, execution_id="execution:1", at_tick=0)
    assert len(reservations) == 2
    assert {item.current.target.origin for item in reservations} == {ORIGIN}
    assert {item.current.execution_id for item in reservations} == {"execution:1"}
    for reservation in reservations:
        mapper.validate_reservation(reservation, at_tick=0)
        assert reservation.as_dict()["motor_executor_installed"] is False
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="execution:1", at_tick=0)


def test_copied_exported_superseded_or_foreign_proposals_cannot_reserve():
    mapper = _mapper()
    proposal = mapper.propose(_request(), at_tick=0)
    for wrong in (replace(proposal), proposal.as_dict(), _mapper().propose(_request(), at_tick=0)):
        with pytest.raises(ValueError):
            mapper.reserve(wrong, execution_id="execution:1", at_tick=0)
    newest = mapper.propose(_request(), at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="execution:1", at_tick=0)
    assert len(mapper.reserve(newest, execution_id="execution:1", at_tick=0)) == 2


@pytest.mark.parametrize("change", ["stale", "new_feedback", "missing_feedback"])
def test_pending_proposal_cannot_reserve_after_its_body_basis_is_lost(change):
    mapper = _mapper()
    proposal = mapper.propose(_request(), at_tick=0)
    tick = 3 if change == "stale" else 1
    if change == "new_feedback":
        mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=1), at_tick=1)
    elif change == "missing_feedback":
        mapper.update_feedback(None, at_tick=1)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="execution:1", at_tick=tick)
    assert mapper.reservations(at_tick=tick) == ()


def test_busy_axis_withholds_only_it_and_does_not_replace_reserved_target():
    mapper = _mapper()
    first = _reserved(mapper, desired_extension=None)[0]
    proposal = mapper.propose(_request(), at_tick=0)
    assert dict(proposal.withheld)[TILT] == "resource_already_reserved"
    assert set(_targets(proposal)) == {EXTEND}
    additional = mapper.reserve(proposal, execution_id="execution:1", at_tick=0)
    assert len(additional) == 1 and additional[0].current.target.kind is EXTEND
    assert mapper.reservations(at_tick=0)[0] is first


@pytest.mark.parametrize("changed_field", ["task_id", "application_id", "envelope_id"])
def test_compatible_axes_cannot_mix_task_or_envelope_owners(changed_field):
    mapper = _mapper()
    _reserved(mapper, desired_extension=None)
    foreign = replace(ORIGIN, **{changed_field: "different"})
    proposal = mapper.propose(_request(origin=foreign, desired_tilt_degrees=None), at_tick=0)
    assert not proposal.bindings
    assert dict(proposal.withheld)[EXTEND] == "different_task_envelope_reserved"


def test_same_task_second_axis_cannot_install_under_another_execution():
    mapper = _mapper()
    original = _reserved(mapper, desired_extension=None)
    proposal = mapper.propose(_request(desired_tilt_degrees=None), at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="execution:other", at_tick=0)
    assert mapper.reservations(at_tick=0) == original
    assert len(mapper.reserve(proposal, execution_id="execution:1", at_tick=0)) == 1


def test_all_withheld_proposal_is_not_an_empty_successful_reservation():
    mapper = _mapper(capabilities=())
    proposal = mapper.propose(_request(), at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="execution:1", at_tick=0)


def test_cancel_releases_only_named_resource_and_retained_copy_cannot_reactivate():
    mapper = _mapper()
    tilt, extension = _reserved(mapper)
    cancelled = mapper.cancel(tilt, at_tick=1)
    assert cancelled.status == "cancelled"
    assert mapper.reservations(at_tick=1) == (extension,)
    assert tilt.status == "reserved"  # An old immutable description is not live authority.
    for old in (tilt, cancelled, replace(extension)):
        with pytest.raises(ValueError):
            mapper.validate_reservation(old, at_tick=1)
    with pytest.raises(ValueError):
        mapper.cancel(tilt, at_tick=1)
    mapper.validate_reservation(extension, at_tick=1)


def test_expiry_is_half_open_and_rereading_does_not_extend_it():
    mapper = _mapper()
    reservations = _reserved(mapper)
    assert len(mapper.reservations(at_tick=7)) == 2
    assert mapper.reservations(at_tick=8) == ()
    for item in reservations:
        with pytest.raises(ValueError):
            mapper.validate_reservation(item, at_tick=8)
    expired = mapper.expire(at_tick=8)
    assert len(expired) == 2 and all(item.status == "expired" for item in expired)
    assert mapper.expire(at_tick=9) == ()
    mapper.update_feedback(_feedback(sample_id=2, event_tick=9, available_tick=9), at_tick=9)
    assert len(mapper.propose(_request(), at_tick=9).bindings) == 2
    assert mapper.reservations(at_tick=9) == ()


def test_no_new_proposal_and_failed_proposal_cannot_renew_existing_lease():
    mapper = _mapper()
    reservations = _reserved(mapper)
    mapper.update_feedback(_feedback(sample_id=2, event_tick=5, available_tick=5), at_tick=5)
    assert not mapper.propose(_request(), at_tick=5).bindings  # Existing targets occupy both axes.
    assert mapper.reservations(at_tick=5) == reservations
    assert mapper.reservations(at_tick=8) == ()


def test_refinement_preserves_original_basis_bounds_and_expiry_with_explicit_revision_time():
    mapper = _mapper()
    original = _reserved(mapper, desired_extension=None)[0]
    mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=1, body_tilt_degrees=25.0), at_tick=1)
    revised = mapper.refine(original, endpoint=17.5, at_tick=1)
    assert revised.current.target.revision == 2 and revised.updated_tick == 1
    assert revised.current.target.basis is original.current.target.basis
    assert revised.current.target.offset == -12.5
    assert revised.current.target.endpoint == 17.5
    assert original.current.target.endpoint == 18.0
    assert revised.current.expires_at_tick == original.current.expires_at_tick == 8
    assert revised.current.committed_tick == 0
    assert revised.initial is original.initial
    assert revised.current.target.max_corrections == 2
    with pytest.raises(ValueError):
        mapper.validate_reservation(original, at_tick=1)
    mapper.validate_reservation(revised, at_tick=1)


def test_refinements_cannot_ratchet_the_original_band_or_change_twice_in_one_tick():
    mapper = _mapper()
    original = _reserved(mapper, desired_extension=None)[0]
    revised = mapper.refine(original, endpoint=17.0, at_tick=1)
    before = _snapshot(mapper, 1)
    with pytest.raises(ValueError):
        mapper.refine(revised, endpoint=17.5, at_tick=1)
    assert _snapshot(mapper, 1) == before
    with pytest.raises(ValueError):
        mapper.refine(revised, endpoint=16.5, at_tick=2)
    assert mapper.reservations(at_tick=2)[0] is revised
    valid = mapper.refine(revised, endpoint=18.0, at_tick=2)
    assert valid.current.target.revision == 3
    assert valid.current.expires_at_tick == 8


@pytest.mark.parametrize("issue", ["stale", "missing", "no_support", "excursion", "lease", "travel", "range"])
def test_refinement_refuses_lost_evidence_bounds_or_budget_without_partial_update(issue):
    caps = CAPABILITIES
    if issue == "range":
        caps = (replace(CAPABILITIES[0], minimum_coordinate=18.0), CAPABILITIES[1])
    mapper = _mapper(capabilities=caps)
    original = _reserved(mapper, desired_extension=None)[0]
    tick, endpoint = 1, 17.5
    if issue == "stale":
        tick = 3
    elif issue == "missing":
        mapper.update_feedback(None, at_tick=1)
    elif issue == "no_support":
        mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=1, support_contact=False, useful_loading=0.0), at_tick=1)
    elif issue == "excursion":
        mapper.update_feedback(_feedback(sample_id=2, event_tick=1, available_tick=1, body_tilt_degrees=60.0), at_tick=1)
    elif issue == "lease":
        tick = 8
    elif issue == "travel":
        tick = 7
        mapper.update_feedback(_feedback(sample_id=2, event_tick=7, available_tick=7, body_tilt_degrees=30.0), at_tick=7)
    before = _snapshot(mapper, tick)
    with pytest.raises(ValueError):
        mapper.refine(original, endpoint=endpoint, at_tick=tick)
    assert _snapshot(mapper, tick) == before


def test_noop_refinement_does_not_create_a_revision_or_renew_lease():
    mapper = _mapper()
    original = _reserved(mapper, desired_extension=None)[0]
    assert mapper.refine(original, endpoint=18.0, at_tick=1) is original
    assert original.current.target.revision == 1 and original.current.expires_at_tick == 8


def test_generation_replacement_requires_new_helper_and_rejects_old_references():
    old = _mapper()
    reservation = _reserved(old)[0]
    newer_stream = MotorStreamRefV1(STREAM.stream_id, 2)
    new = BodyTargetMapperV1(newer_stream, CAPABILITIES)
    for operation in (
        lambda: new.update_feedback(_feedback(), at_tick=0),
        lambda: new.propose(_request(), at_tick=0),
        lambda: new.validate_reservation(reservation, at_tick=0),
    ):
        with pytest.raises(ValueError):
            operation()
    assert new.reservations(at_tick=0) == ()
    assert new.body_view(at_tick=0)["feedback"] is None


def test_body_owner_configures_once_and_old_runtime_remains_opt_in():
    body = Nca8BodyRuntimeV1()
    assert body.motor_targets is None
    before = body.current_state, body.current_envelope, body.last_handoff, body.posture_support_candidate
    mapper = body.configure_motor_targets(STREAM, CAPABILITIES)
    assert body.motor_targets is mapper
    mapper.update_feedback(_feedback(), at_tick=0)
    _reserved(mapper)
    assert before == (body.current_state, body.current_envelope, body.last_handoff, body.posture_support_candidate)
    with pytest.raises(ValueError):
        body.configure_motor_targets(MotorStreamRefV1("new", 2), CAPABILITIES)
    assert body.motor_targets is mapper


def test_bodymap_ablation_also_disables_new_target_formation():
    body = Nca8BodyRuntimeV1(action_handoff_enabled=False)
    mapper = body.configure_motor_targets(STREAM, CAPABILITIES)
    mapper.update_feedback(_feedback(), at_tick=0)
    proposal = mapper.propose(_request(), at_tick=0)
    assert not proposal.bindings
    assert {reason for _, reason in proposal.withheld} == {"bodymap_disabled"}


def test_existing_gate_a_results_are_equal_even_with_unrelated_configured_local_body():
    from nca8_runtime import Nca8CognitiveRuntimeV1
    from nca8_adapters import adapt_env_observation_v1
    from cca8_env import EnvObservation
    from nca8_scheduler import Nca8DeterministicSchedulerV1
    from nca8_trace import Nca8TraceBufferV1
    plain = Nca8CognitiveRuntimeV1(trace=Nca8TraceBufferV1(), scheduler=Nca8DeterministicSchedulerV1())
    body = Nca8BodyRuntimeV1()
    mapper = body.configure_motor_targets(STREAM, CAPABILITIES)
    mapper.update_feedback(_feedback(body_tilt_degrees=-60.0, support_contact=False, useful_loading=0.0), at_tick=0)
    mapper.propose(_request(), at_tick=0)
    configured = Nca8CognitiveRuntimeV1(
        body_runtime=body, trace=Nca8TraceBufferV1(), scheduler=Nca8DeterministicSchedulerV1(),
    )
    observation = adapt_env_observation_v1(EnvObservation(predicates=["posture:fallen"]))
    first = plain.run_cycle(observation, observation_number=1)
    second = configured.run_cycle(observation, observation_number=1)
    assert first.as_dict() == second.as_dict()
    assert body.motor_targets is mapper


def test_all_h3_values_are_frozen_and_diagnostics_do_not_alias_state():
    mapper = _mapper()
    request = _request()
    proposal = mapper.propose(request, at_tick=0)
    reserved = mapper.reserve(proposal, execution_id="execution:1", at_tick=0)[0]
    for record, attribute in (
        (CAPABILITIES[0], "maximum_step"), (request, "desired_tilt_degrees"),
        (proposal, "created_tick"), (reserved, "status"), (proposal.bindings[0], "target"),
    ):
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(record, attribute, None)
    before = _snapshot(mapper, 0)
    export = reserved.as_dict()
    export["current"]["target"]["offset"] = 1000.0
    view = mapper.body_view(at_tick=0)
    view["feedback"]["body_tilt_degrees"] = -90.0
    assert _snapshot(mapper, 0) == before
    json.dumps(proposal.as_dict(), allow_nan=False)
    json.dumps(reserved.as_dict(), allow_nan=False)


@pytest.mark.parametrize("field, bad", [
    ("desired_tilt_degrees", True), ("desired_tilt_degrees", "0"), ("desired_tilt_degrees", float("nan")),
    ("desired_tilt_degrees", float("inf")), ("desired_tilt_degrees", 90.1), ("desired_tilt_degrees", 10**400),
    ("desired_extension", -0.1), ("desired_extension", 1.1), ("desired_extension", False),
    ("lease_ticks", 0), ("lease_ticks", 9), ("lease_ticks", True), ("lease_ticks", 2.5),
    ("origin", {}),
])
def test_request_validation_does_not_coerce_malformed_inputs(field, bad):
    with pytest.raises((ValueError, TypeError)):
        _request(**{field: bad})


def test_empty_request_is_not_an_implicit_cancel_or_new_task():
    with pytest.raises(ValueError):
        BodyMovementRequestV1(ORIGIN)


@pytest.mark.parametrize("field, bad", [
    ("kind", "orientation_adjust"), ("capability_id", ""), ("capability_id", "a\nb"), ("capability_id", 2),
    ("minimum_coordinate", -91.0), ("maximum_coordinate", 91.0), ("minimum_coordinate", 90.0),
    ("maximum_step", 0.0), ("maximum_step", True), ("maximum_step", 19.0),
    ("maximum_excursion", 11.0), ("maximum_rate", 0.0), ("maximum_rate", 91.0),
    ("tolerance", 0.0), ("tolerance", 13.0), ("tolerance", float("inf")),
])
def test_capability_validation_enforces_physical_units_and_consistent_bounds(field, bad):
    with pytest.raises((ValueError, TypeError)):
        replace(CAPABILITIES[0], **{field: bad})


@pytest.mark.parametrize("options", [
    {"tick_seconds": 0.0}, {"tick_seconds": 0.051}, {"tick_seconds": True},
    {"maximum_feedback_age": -1}, {"maximum_feedback_age": 3}, {"maximum_feedback_age": True},
    {"enabled": 1},
])
def test_mapper_configuration_rejects_invalid_time_freshness_and_enable_parameters(options):
    with pytest.raises((ValueError, TypeError)):
        BodyTargetMapperV1(STREAM, CAPABILITIES, **options)


@pytest.mark.parametrize("caps", [
    list(CAPABILITIES), (CAPABILITIES[0], CAPABILITIES[0]),
    (CAPABILITIES[0], replace(CAPABILITIES[1], capability_id=CAPABILITIES[0].capability_id)),
    CAPABILITIES + (CAPABILITIES[0],), ("fake",),
])
def test_bad_or_duplicate_capability_inventory_is_rejected(caps):
    with pytest.raises((ValueError, TypeError)):
        BodyTargetMapperV1(STREAM, caps)


@pytest.mark.parametrize("tick", [-1, True, 0.5, 2**63])
def test_logical_tick_validation_rejects_invalid_values(tick):
    mapper = _mapper()
    with pytest.raises((ValueError, TypeError)):
        mapper.propose(_request(), at_tick=tick)


def test_clock_reversal_and_counter_overflow_fail_before_state_changes():
    mapper = _mapper()
    mapper.update_feedback(_feedback(), at_tick=1)
    with pytest.raises(ValueError):
        mapper.propose(_request(), at_tick=0)
    before = _snapshot(mapper, 1)
    mapper._proposal_number = 2**63 - 1  # Explicit fault injection; no public counter writer.
    with pytest.raises(ValueError):
        mapper.propose(_request(), at_tick=1)
    assert _snapshot(mapper, 1) == before
    mapper._proposal_number = 0
    with pytest.raises(ValueError):
        mapper.propose(_request(), at_tick=2**63 - 5)
    assert _snapshot(mapper, 1) == before


def test_proposal_validation_requires_one_outcome_per_requested_axis():
    proposal = _mapper().propose(_request(), at_tick=0)
    with pytest.raises(ValueError):
        replace(proposal, bindings=proposal.bindings + (proposal.bindings[0],))
    with pytest.raises(ValueError):
        replace(proposal, bindings=proposal.bindings[:1])
    with pytest.raises(TypeError):
        replace(proposal, bindings=list(proposal.bindings))
    with pytest.raises(ValueError):
        BodyTargetBindingV1(proposal.bindings[0].target, CAPABILITIES[1])


def test_reservation_record_rejects_changed_basis_lease_bounds_or_original_band():
    reservation = _reserved(_mapper())[0]
    for changed in (
        replace(reservation.current, committed_tick=1),
        replace(reservation.current, target=replace(reservation.current.target, lease_ticks=7)),
        replace(reservation.current, target=replace(reservation.current.target, max_rate=30.0)),
        replace(reservation.current, target=replace(reservation.current.target, offset=-14.0)),
    ):
        with pytest.raises(ValueError):
            replace(reservation, current=changed)
    with pytest.raises(ValueError):
        replace(reservation, status="achieved")


def test_long_mapping_run_keeps_only_one_proposal_and_two_reservations():
    mapper = _mapper()
    rng = random.getstate()
    for tick in range(200):
        mapper.update_feedback(_feedback(sample_id=tick + 1, event_tick=tick, available_tick=tick), at_tick=tick)
        mapper.expire(at_tick=tick)
        proposal = mapper.propose(_request(), at_tick=tick)
        if proposal.bindings:
            mapper.reserve(proposal, execution_id="execution:1", at_tick=tick)
        assert len(mapper.reservations(at_tick=tick)) <= 2
        assert len(mapper._reservations) <= 2
        assert mapper._pending is None or mapper._pending is proposal
    assert random.getstate() == rng
    assert len(_snapshot(mapper, 199)) < 16000


def test_mapping_replay_and_interleaved_instances_are_deterministic():
    first, second = _mapper(), _mapper()
    for tick in range(10):
        sensed = _feedback(sample_id=tick + 1, event_tick=tick, available_tick=tick, body_tilt_degrees=30.0 - tick)
        first.update_feedback(sensed, at_tick=tick)
        second.update_feedback(sensed, at_tick=tick)
        first_proposal = first.propose(_request(), at_tick=tick)
        second_proposal = second.propose(_request(), at_tick=tick)
        assert first_proposal.as_dict() == second_proposal.as_dict()
    first.reserve(first_proposal, execution_id="execution:1", at_tick=9)
    assert second.reservations(at_tick=9) == ()


def test_helper_import_and_source_have_no_cognitive_executor_or_world_dependency():
    script = (
        "import sys,random; before=random.getstate(); import nca8_body_targets; "
        "assert random.getstate()==before; "
        "assert not ({'cca8_env','cca8_support_world','nca8_runtime','nca8_primitives','nca8_prediction'} & set(sys.modules))"
    )
    result = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    tree = ast.parse((ROOT / "nca8_body_targets.py").read_text(encoding="utf-8"))
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert imports <= {"__future__", "dataclasses", "cca8_motor_contracts", "nca8_sensorimotor_contracts",
                       "cca8_navmap_kernel", "nca8_visual", "nca8_maternal", "nca8_feeding"}
    names = {node.id for node in ast.walk(tree) if isinstance(node, ast.Name)}
    assert "MotorCommandV1" not in names
    constructed = {node.func.id for node in ast.walk(tree) if isinstance(node, ast.Call) and isinstance(node.func, ast.Name)}
    assert not constructed & {"VisualSourceV1", "AttentionRuntimeV1", "NavigationRuntimeV1", "MotorWorldV1"}


def test_component_versions_and_inventory_are_accurate():
    import cca8_run
    import nca8_body
    import nca8_body_targets
    assert cca8_run.__version__ == "0.30.36"
    assert nca8_body.__version__ == "0.5.0"
    assert nca8_body_targets.__version__ == "0.11.0"
    assert dict(cca8_run._CCA8_COMPONENT_REGISTRY)["nca8_body_targets"] == "nca8_body_targets"
    assert len(cca8_run._cca8_component_rows()) == 108
    assert len(cca8_run.PRIMITIVES) == 8


def test_h3_manual_review_is_repeatable_and_explicitly_nonexecuting():
    from scripts.review_nca8_body_targets import main
    from contextlib import redirect_stdout
    from io import StringIO
    outputs = []
    for _ in range(2):
        stream = StringIO()
        with redirect_stdout(stream):
            assert main() == 0
        outputs.append(stream.getvalue())
    assert outputs[0] == outputs[1]
    assert "BODYMAP TARGET CHECKS PASSED" in outputs[0]
    assert "motor commands issued: 0" in outputs[0]


def test_seeded_capability_ranges_do_not_reject_subtraction_roundoff_at_endpoints():
    rng = random.Random(27)
    for _ in range(400):
        coordinate = rng.uniform(0.01, 0.99)
        lower, upper = rng.uniform(0.0, coordinate), rng.uniform(coordinate, 1.0)
        capability = BodyAxisCapabilityV1(
            EXTEND, "bounded-extension", lower, upper, 0.9, 1.0, 1.0, min(0.001, (upper - lower) / 2),
        )
        mapper = _mapper(_feedback(support_extension=coordinate), capabilities=(capability,))
        goal = rng.choice((0.0, 1.0, rng.random()))
        proposal = mapper.propose(_request(desired_tilt_degrees=None, desired_extension=goal), at_tick=0)
        target = _targets(proposal)[EXTEND]
        assert lower - 1e-12 <= target.endpoint <= upper + 1e-12
        assert abs(target.offset) <= 0.4  # Nominal 8 * 0.05 * 1.0 rate/time limit.
        assert abs(target.endpoint - goal) <= abs(coordinate - goal) + 1e-12


def test_reservation_cannot_relabel_changed_endpoint_as_an_older_revision():
    original = _reserved(_mapper(), desired_extension=None)[0]
    changed = replace(original.current, target=replace(original.current.target, offset=-12.5))
    with pytest.raises(ValueError, match="new revision"):
        replace(original, current=changed)
    revised = replace(changed, target=replace(changed.target, revision=2))
    with pytest.raises(ValueError, match="distinct later"):
        replace(original, current=revised, updated_tick=0)
    assert replace(original, current=revised, updated_tick=1).current.target.revision == 2


def test_primitive_origin_labels_do_not_change_the_body_calculation():
    ip = _mapper().propose(_request(origin=replace(ORIGIN, task_id="ip:righting")), at_tick=0)
    lp = _mapper().propose(_request(origin=replace(ORIGIN, task_id="lp:supplied-fixture")), at_tick=0)
    assert [(b.target.kind, b.target.offset) for b in ip.bindings] == [(b.target.kind, b.target.offset) for b in lp.bindings]
    assert lp.request.origin.task_id == "lp:supplied-fixture"  # Interface parity, not acquired LP learning.
