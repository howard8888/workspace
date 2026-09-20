"""P18-H4 local execution, evidence, ownership, protection and boundedness tests."""

from __future__ import annotations

import ast
import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_body_targets import BodyMovementRequestV1, BodyTargetMapperV1, nominal_body_capabilities_v1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorProfileV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, LocalTargetDispositionV1, SensorimotorTargetKindV1, TargetOriginV1
from nca8_sensorimotor_demo import SensorimotorTrialV1, run_sensorimotor_experiment_v1

ROOT = Path(__file__).resolve().parents[1]
TILT = SensorimotorTargetKindV1.ORIENTATION_ADJUST
EXTEND = SensorimotorTargetKindV1.SUPPORT_EXTENSION
STREAM = MotorStreamRefV1("controller-test", 1)


def _feedback(event=0, **changes):
    return replace(MotorFeedbackV1(STREAM, event + 1, event, event, 30.0, 0.4, True, 0.3, 0.2), **changes)


def _setup(*, feedback=None, tilt=0.0, extension=0.6, profile=None, capabilities=None, corrections=None):
    feedback = _feedback() if feedback is None else feedback
    capabilities = nominal_body_capabilities_v1() if capabilities is None else capabilities
    mapper = BodyTargetMapperV1(STREAM, capabilities)
    mapper.update_feedback(feedback, at_tick=0)
    origin = TargetOriginV1(STREAM, "task:fixture", "application:fixture", "envelope:fixture")
    proposal = mapper.propose(BodyMovementRequestV1(origin, tilt, extension), at_tick=0)
    if corrections is not None:
        # A deliberately narrower originating envelope is injected as this test's fixture.
        bindings = tuple(replace(item, target=replace(item.target, max_corrections=corrections)) for item in proposal.bindings)
        proposal = replace(proposal, bindings=bindings)
        mapper._pending = proposal
    reservations = mapper.reserve(proposal, execution_id="execution:fixture", at_tick=0)
    controller = SensorimotorExecutorV1(mapper, profile=profile)
    return mapper, controller, reservations


def _installed(**options):
    mapper, controller, reservations = _setup(**options)
    controller.install(reservations, at_tick=0)
    return mapper, controller, reservations


def _by_kind(reports):
    return {item.committed_target.target.kind: item for item in reports}


def test_nominal_targets_are_consumed_by_commands_and_observed_before_expiry():
    trial = SensorimotorTrialV1()
    before = trial.world.body
    assert trial.world.tick == 0
    assert trial.controller.installation_count == 1
    steps = [trial.advance() for _ in range(12)]
    reports = _by_kind(trial.controller.reports)
    assert set(reports) == {TILT, EXTEND}
    assert all(item.disposition is LocalTargetDispositionV1.ACHIEVED for item in reports.values())
    assert trial.world.body != before
    for item in reports.values():
        target = item.committed_target.target
        actual = item.feedback.body_tilt_degrees if target.kind is TILT else item.feedback.support_extension
        assert abs(actual - target.endpoint) <= target.tolerance + 1e-12
        assert item.feedback.event_tick <= item.committed_target.expires_at_tick
        assert not item.as_dict()["establishes_task_success"]
        assert not item.as_dict()["establishes_action_causation"]
    assert any(item.command is not None for item in steps)
    assert all(item.command is None for item in steps[8:])
    assert trial.controller.installation_count == 1


@pytest.mark.parametrize("initial,goal", [(30.0, 0.0), (-30.0, 0.0), (30.0, 45.0), (-30.0, -45.0), (7.0, 0.0)])
def test_arbitrary_supplied_orientation_is_followed_without_hidden_upright_choice(initial, goal):
    trial = SensorimotorTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(initial, 0.5)), desired_tilt_degrees=goal)
    first = trial.advance()
    target = next(item.current.target for item in trial.targets if item.current.target.kind is TILT)
    assert first.command.orientation_drive * (target.endpoint - initial) > 0.0
    for _ in range(11):
        trial.advance()
    assert _by_kind(trial.controller.reports)[TILT].disposition is LocalTargetDispositionV1.ACHIEVED


def test_mirrored_start_and_requirement_produce_mirrored_physical_control():
    positive = SensorimotorTrialV1()
    negative = SensorimotorTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(-30.0, 0.4)))
    for _ in range(12):
        left, right = positive.advance(), negative.advance()
        if left.command is None:
            assert right.command is None
        else:
            assert left.command.orientation_drive == pytest.approx(-right.command.orientation_drive)
            assert left.command.extension_drive == right.command.extension_drive
        assert positive.world.body.body_tilt_degrees == pytest.approx(-negative.world.body.body_tilt_degrees)
        assert positive.world.body.support_extension == negative.world.body.support_extension


@pytest.mark.parametrize("goal", [0.0, 0.2, 0.4, 0.6, 0.9])
def test_extension_can_follow_either_direction_or_an_already_met_target(goal):
    trial = SensorimotorTrialV1(desired_tilt_degrees=None, desired_extension=goal)
    for _ in range(12):
        trial.advance()
    report = trial.controller.reports[0]
    assert report.disposition is LocalTargetDispositionV1.ACHIEVED
    assert abs(trial.world.body.support_extension - report.committed_target.target.endpoint) <= 0.01 + 1e-12
    assert not report.as_dict()["establishes_task_success"]


def test_feedback_changes_response_before_the_next_reference_focal_marker():
    intact = run_sensorimotor_experiment_v1("perturbed")
    open_loop = run_sensorimotor_experiment_v1("feedback_off")
    nominal = run_sensorimotor_experiment_v1("nominal")
    assert intact.elapsed_ticks == open_loop.elapsed_ticks == nominal.elapsed_ticks == 12
    assert open_loop.commands == nominal.commands
    assert intact.commands[3] != open_loop.commands[3]
    assert intact.events[0].event_tick == 2
    assert intact.events[0].noticed_tick == 3 < intact.marker_stride
    target = next(item.current.target for item in intact.targets if item.current.target.kind is TILT)
    assert abs(intact.final_body.body_tilt_degrees - target.endpoint) < abs(open_loop.final_body.body_tilt_degrees - target.endpoint)
    assert intact.as_dict()["focal_calls"] == 0
    assert open_loop.reports == ()  # External observer sensing never becomes controller success.


def test_prediction_protection_off_preserves_reactive_feedback_and_can_still_achieve():
    intact = run_sensorimotor_experiment_v1("perturbed")
    reactive = run_sensorimotor_experiment_v1("prediction_off")
    assert intact.commands[3].orientation_drive == pytest.approx(reactive.commands[3].orientation_drive / 2.0)
    assert all(item.disposition is LocalTargetDispositionV1.ACHIEVED for item in reactive.reports)
    assert reactive.events == ()
    assert any(item.unexpected for step in reactive.steps for item in step.comparisons)
    assert _by_kind(intact.reports)[TILT].correction_count == 1
    assert _by_kind(reactive.reports)[TILT].correction_count == 0


def test_contact_prediction_has_a_real_consumer_separate_from_orientation_safety():
    intact = run_sensorimotor_experiment_v1("support_loss")
    reactive = run_sensorimotor_experiment_v1("support_loss_prediction_off")
    a, b = _by_kind(intact.reports), _by_kind(reactive.reports)
    assert a[EXTEND].disposition is LocalTargetDispositionV1.INTERRUPTED
    assert a[EXTEND].reason == "unexpected_contact_loss"
    assert b[EXTEND].disposition is LocalTargetDispositionV1.ACHIEVED
    assert b[TILT].disposition is LocalTargetDispositionV1.BLOCKED
    assert b[TILT].reason == "loaded_support_unavailable"
    assert intact.final_body.support_extension < reactive.final_body.support_extension
    assert all(item.noticed_tick == 3 for item in intact.events)


def test_absent_surface_does_not_prevent_actuator_achievement_or_create_support():
    result = run_sensorimotor_experiment_v1("no_surface")
    assert len(result.reports) == 1
    assert result.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert result.latest_feedback.support_contact is False
    assert result.latest_feedback.useful_loading == 0.0
    assert result.withheld == ((TILT, "loaded_support_unavailable"),)
    assert not result.as_dict()["establishes_righting_success"]


def test_missing_capability_leaves_other_installed_axis_functional():
    result = run_sensorimotor_experiment_v1("no_orientation")
    assert result.withheld == ((TILT, "capability_unavailable"),)
    assert result.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert all(item.command is None or item.command.orientation_drive == 0.0 for item in result.steps)


def test_blocked_physical_motor_is_not_a_hidden_completion_flag():
    result = run_sensorimotor_experiment_v1("blocked_motor")
    reports = _by_kind(result.reports)
    assert reports[TILT].disposition is LocalTargetDispositionV1.EXPIRED
    assert reports[EXTEND].disposition is LocalTargetDispositionV1.ACHIEVED
    assert result.final_body.body_tilt_degrees > 30.0
    assert reports[TILT].correction_count <= 2


@pytest.mark.parametrize("case,first_neutral,terminal_tick", [("dropout", 4, 6), ("delayed", 3, 5)])
def test_missing_or_too_old_feedback_withholds_then_stops_without_false_contact(case, first_neutral, terminal_tick):
    result = run_sensorimotor_experiment_v1(case)
    assert all(item.command is None for item in result.steps[first_neutral:])
    assert all(item.disposition is LocalTargetDispositionV1.UNAVAILABLE for item in result.reports)
    assert all(item.reason == "current_feedback_timeout" and item.feedback is None for item in result.reports)
    assert all(item.noticed_tick == terminal_tick for item in result.events)
    assert not any(item.reason == "unexpected_contact_loss" for item in result.events)


def test_explicit_absence_cannot_be_replaced_by_the_target_starting_sample():
    _mapper, controller, _reservations = _installed()
    for tick in range(3):
        step = controller.step(None, at_tick=tick)
        assert step.command is None
    assert all(item.disposition is LocalTargetDispositionV1.UNAVAILABLE for item in controller.reports)


@pytest.mark.parametrize("missing,affected", [("body_tilt_degrees", TILT), ("support_extension", EXTEND),
                                               ("support_contact", TILT), ("useful_loading", TILT)])
def test_missing_channel_withholds_only_its_affected_family(missing, affected):
    _mapper, controller, _reserved = _installed()
    # Keep sensor identity valid while introducing a new partial acquisition.
    controller.step(_feedback(), at_tick=0)
    changed = _feedback(1, **{missing: None})
    result = controller.step(changed, at_tick=1)
    reports = _by_kind(result.reports)
    assert reports[affected].disposition is LocalTargetDispositionV1.UNRESOLVED
    other = EXTEND if affected is TILT else TILT
    assert reports[other].disposition is LocalTargetDispositionV1.ACTIVE
    assert result.command is not None
    if affected is TILT:
        assert result.command.orientation_drive == 0.0
    else:
        assert result.command.extension_drive == 0.0


def test_missing_destabilization_does_not_invent_a_rate_or_block_a_first_attempt():
    feedback = _feedback(destabilization=None)
    _mapper, controller, _targets = _installed(feedback=feedback)
    assert controller.step(feedback, at_tick=0).command is not None


def test_short_feedback_gap_can_resume_before_the_finite_missing_limit():
    _mapper, controller, _targets = _installed()
    assert controller.step(None, at_tick=0).command is None
    result = controller.step(_feedback(1), at_tick=1)
    assert result.command is not None
    assert not controller.events


def test_current_feedback_age_is_acquisition_age_not_last_read_time():
    _mapper, controller, _targets = _installed()
    initial = _feedback()
    for tick in range(6):
        result = controller.step(initial, at_tick=tick)
        if tick >= 3:
            assert result.feedback is None and result.command is None
    assert all(item.disposition is LocalTargetDispositionV1.UNAVAILABLE for item in controller.reports)


def test_older_arrival_does_not_replace_the_newer_current_body():
    mapper, controller, _targets = _installed()
    controller.step(_feedback(), at_tick=0)
    controller.step(_feedback(1, body_tilt_degrees=27.0, support_extension=0.45), at_tick=1)
    result = controller.step(_feedback(), at_tick=2)
    assert result.feedback_disposition == "older_ignored"
    assert result.feedback.sample_id == 2
    assert mapper.current_feedback(at_tick=2).sample_id == 2


@pytest.mark.parametrize("bad", [True, 0, {}, "feedback", _feedback(stream=MotorStreamRefV1("foreign", 1)),
                                  _feedback(stream=MotorStreamRefV1(STREAM.stream_id, 2)),
                                  _feedback(1), _feedback(available_tick=3), _feedback(body_tilt_degrees=31.0)])
def test_bad_input_stops_the_executor_without_issuing_or_retrying_a_command(bad):
    _mapper, controller, _targets = _installed()
    with pytest.raises((TypeError, ValueError)):
        controller.step(bad, at_tick=0)
    assert controller.fault is not None
    assert controller.trace_snapshot() == ()
    with pytest.raises(RuntimeError, match="stopped"):
        controller.step(_feedback(), at_tick=0)


@pytest.mark.parametrize("bad_tick", [-1, True, 0.5, 2**63, 2])
def test_invalid_or_skipped_clock_cannot_create_a_command(bad_tick):
    _mapper, controller, _targets = _installed()
    before = controller.snapshot()
    with pytest.raises((TypeError, ValueError)):
        controller.step(_feedback(), at_tick=bad_tick)
    assert controller.snapshot() == before


def test_duplicate_tick_cannot_issue_a_second_command_or_refresh_any_evidence():
    _mapper, controller, _targets = _installed()
    controller.step(_feedback(), at_tick=0)
    before = controller.snapshot()
    with pytest.raises(ValueError):
        controller.step(_feedback(), at_tick=0)
    assert controller.snapshot() == before


def test_no_installation_means_neutral_updates_not_an_implicit_task():
    mapper = BodyTargetMapperV1(STREAM, nominal_body_capabilities_v1())
    controller = SensorimotorExecutorV1(mapper)
    result = controller.step(_feedback(), at_tick=0)
    assert result.command is None and result.reports == ()
    assert controller.installation_count == 0


def test_installation_is_single_use_and_does_not_move_or_generate_commands():
    _mapper, controller, reservations = _setup()
    controller.install(reservations, at_tick=0)
    assert controller.trace_snapshot() == ()
    assert controller.installation_count == 1
    assert all(item.disposition is LocalTargetDispositionV1.PENDING for item in controller.reports)
    with pytest.raises(ValueError, match="consumed"):
        controller.install(reservations, at_tick=0)


def test_two_executors_cannot_control_one_bodymap_generation():
    mapper, _controller, _reservations = _setup()
    with pytest.raises(ValueError, match="executor owner"):
        SensorimotorExecutorV1(mapper)


@pytest.mark.parametrize("variant", ["copy", "foreign", "empty", "too_many", "dict", "duplicate"])
def test_malformed_or_replayed_installation_has_no_partial_effect(variant):
    _mapper, controller, reservations = _setup()
    if variant == "copy":
        supplied = (replace(reservations[0]),)
    elif variant == "foreign":
        supplied = _setup()[2]
    elif variant == "empty":
        supplied = ()
    elif variant == "too_many":
        supplied = reservations + reservations
    elif variant == "dict":
        supplied = (reservations[0].as_dict(),)
    else:
        supplied = (reservations[0], reservations[0])
    with pytest.raises((TypeError, ValueError)):
        controller.install(supplied, at_tick=0)
    assert controller.installation_count == 0 and controller.reports == ()
    assert controller.step(_feedback(), at_tick=0).command is None
    with pytest.raises(ValueError):
        controller.install(reservations, at_tick=1)


def test_bodymap_direct_revocation_stops_only_the_named_installed_resource():
    mapper, controller, reservations = _installed()
    tilt = next(item for item in reservations if item.current.target.kind is TILT)
    mapper.cancel(tilt, at_tick=0)
    result = controller.step(_feedback(), at_tick=0)
    assert result.command.orientation_drive == 0.0
    assert result.command.extension_drive > 0.0
    assert _by_kind(result.reports)[TILT].disposition is LocalTargetDispositionV1.CANCELLED


def test_explicit_controller_cancel_releases_body_resource_and_never_reinstalls():
    mapper, controller, _targets = _installed()
    controller.cancel_target(TILT, at_tick=0)
    assert all(item.current.target.kind is not TILT for item in mapper.reservations(at_tick=0))
    result = controller.step(_feedback(), at_tick=0)
    assert result.command.orientation_drive == 0.0
    with pytest.raises(ValueError):
        controller.cancel_target(TILT, at_tick=1)


def test_refinement_is_explicit_preserves_original_anchor_expiry_and_old_forecast():
    mapper, controller, targets = _installed()
    first = controller.step(_feedback(), at_tick=0)
    forecast = next(item for item in first.predictions if item.kind is TILT)
    saved = forecast.as_dict()
    mapper.update_feedback(_feedback(1, body_tilt_degrees=27.0), at_tick=1)
    original = next(item for item in targets if item.current.target.kind is TILT)
    refined = mapper.refine(original, endpoint=17.5, at_tick=1)
    controller.replace_target(refined, at_tick=1)
    step = controller.step(_feedback(1, body_tilt_degrees=27.0), at_tick=1)
    report = _by_kind(step.reports)[TILT]
    assert report.committed_target.target.revision == 2
    assert report.committed_target.target.basis_coordinate == 30.0
    assert report.committed_target.target.endpoint == 17.5
    assert report.committed_target.expires_at_tick == 8
    assert forecast.as_dict() == saved
    assert report.correction_count == 0


def test_unannounced_bodymap_revision_prevents_old_target_pursuit():
    mapper, controller, targets = _installed()
    controller.step(_feedback(), at_tick=0)
    mapper.update_feedback(_feedback(1), at_tick=1)
    mapper.refine(targets[0], endpoint=17.5, at_tick=1)
    result = controller.step(_feedback(1), at_tick=1)
    assert result.command.orientation_drive == 0.0
    assert _by_kind(result.reports)[TILT].disposition is LocalTargetDispositionV1.CANCELLED


def test_copied_or_nonnew_refinement_is_rejected_without_renewing():
    mapper, controller, targets = _installed()
    controller.step(_feedback(), at_tick=0)
    mapper.update_feedback(_feedback(1), at_tick=1)
    refined = mapper.refine(targets[0], endpoint=17.5, at_tick=1)
    before = controller.snapshot()
    with pytest.raises(ValueError):
        controller.replace_target(replace(refined), at_tick=1)
    assert controller.snapshot() == before
    controller.replace_target(refined, at_tick=1)
    with pytest.raises(ValueError):
        controller.replace_target(refined, at_tick=1)


def test_target_and_old_focal_sample_never_follow_new_body_position():
    mapper, controller, targets = _installed()
    focal = FocalMotorEvidenceV1(_feedback(), 1, 0)
    before = focal.as_dict()
    controller.step(_feedback(), at_tick=0)
    controller.step(_feedback(1, body_tilt_degrees=25.0), at_tick=1)
    assert mapper.current_feedback(at_tick=1).body_tilt_degrees == 25.0
    assert targets[0].current.target.endpoint == 18.0
    assert focal.as_dict() == before


def test_already_achieved_fixture_needs_no_motor_command_or_causal_credit():
    _mapper, controller, _targets = _installed(tilt=30.0, extension=0.4)
    result = controller.step(_feedback(), at_tick=0)
    assert result.command is None
    assert all(item.disposition is LocalTargetDispositionV1.ACHIEVED for item in result.reports)
    assert all(not item.as_dict()["establishes_action_causation"] for item in result.reports)


def test_achieved_target_does_not_restart_when_later_body_drifts():
    _mapper, controller, _targets = _installed(tilt=30.0, extension=None)
    controller.step(_feedback(), at_tick=0)
    result = controller.step(_feedback(1, body_tilt_degrees=34.0), at_tick=1)
    assert result.command is None
    assert result.reports[0].feedback.event_tick == 0
    assert result.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED


def test_original_excursion_violation_stops_despite_remaining_lease():
    _mapper, controller, _targets = _installed(profile=SensorimotorProfileV1(prediction_protection=False))
    controller.step(_feedback(), at_tick=0)
    result = controller.step(_feedback(1, body_tilt_degrees=55.0), at_tick=1)
    assert result.command.orientation_drive == 0.0
    assert _by_kind(result.reports)[TILT].reason == "original_excursion_exceeded"


@pytest.mark.parametrize("limit", [0, 1, 2])
def test_only_anomalous_correction_attempts_consume_the_fixed_budget(limit):
    _mapper, controller, _targets = _installed(extension=None, corrections=limit)
    controller.step(_feedback(), at_tick=0)
    readings = (33.4, 38.5, 44.0)
    for tick, value in enumerate(readings, 1):
        result = controller.step(_feedback(tick, body_tilt_degrees=value), at_tick=tick)
    report = result.reports[0]
    assert report.disposition is LocalTargetDispositionV1.INTERRUPTED
    assert report.reason == "anomalous_correction_budget_exhausted"
    assert report.correction_count == limit
    assert result.command is None


def test_repeated_observation_and_overlapping_forecasts_do_not_recount_one_disturbance():
    result = run_sensorimotor_experiment_v1("perturbed")
    assert len(result.events) == 1
    assert _by_kind(result.reports)[TILT].correction_count == 1
    assert result.events[0].event_tick == 2


def test_prediction_claim_precedes_matched_event_and_is_not_future_feedback():
    result = run_sensorimotor_experiment_v1("perturbed")
    for step in result.steps:
        for prediction in step.predictions:
            assert prediction.issued_tick == step.tick
            assert prediction.event_tick == step.tick + 1
            assert prediction.basis_event_tick <= prediction.issued_tick
            assert prediction.expected_coordinate != float("nan")
        for comparison in step.comparisons:
            assert comparison.prediction.event_tick == comparison.feedback.event_tick
            assert comparison.prediction.issued_tick < comparison.feedback.event_tick
            assert comparison.feedback.available_tick <= step.tick


def test_unknown_contact_does_not_become_a_negative_prediction_result():
    _mapper, controller, _targets = _installed(tilt=None)
    controller.step(_feedback(), at_tick=0)
    result = controller.step(_feedback(1, support_extension=0.45, support_contact=None), at_tick=1)
    assert result.comparisons[0].contact_mismatch is None
    assert not result.comparisons[0].unexpected
    assert result.command is not None


@pytest.mark.parametrize("maximum_rate", [10.0, 30.0, 60.0, 90.0])
def test_supplied_commanded_rate_limit_is_respected(maximum_rate):
    capabilities = nominal_body_capabilities_v1()
    narrowed = (replace(capabilities[0], maximum_rate=maximum_rate), capabilities[1])
    trial = SensorimotorTrialV1(capabilities=narrowed)
    for _ in range(12):
        step = trial.advance()
        if step.command is not None:
            assert abs(step.command.orientation_drive) * 90.0 <= maximum_rate + 1e-12
            assert abs(step.command.extension_drive) <= 1.0


def test_expiry_prevents_new_pursuit_even_when_later_evidence_can_resolve_old_achievement():
    _mapper, controller, _targets = _installed(extension=None, profile=SensorimotorProfileV1(prediction_protection=False))
    for tick in range(9):
        result = controller.step(_feedback(tick), at_tick=tick)
    assert result.command is None
    assert result.reports[0].disposition is LocalTargetDispositionV1.EXPIRED
    # Same event index cannot be changed, so use an older not-yet-seen physical event 8 via a separate run.
    mapper, other, _targets = _installed(extension=None, profile=SensorimotorProfileV1(prediction_protection=False))
    for tick in range(9):
        event = max(0, tick - 1)
        other.step(_feedback(event, available_tick=event + (1 if event else 0)), at_tick=tick)
    late = _feedback(8, body_tilt_degrees=18.0, available_tick=9)
    final = other.step(late, at_tick=9)
    assert final.command is None
    assert final.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert final.reports[0].reason == "observed_achievement_before_expiry"
    assert mapper.reservations(at_tick=9) == ()


def test_postexpiry_physical_achievement_cannot_satisfy_the_expired_local_target():
    _mapper, controller, _targets = _installed(extension=None, profile=SensorimotorProfileV1(prediction_protection=False))
    for tick in range(9):
        controller.step(_feedback(tick), at_tick=tick)
    result = controller.step(_feedback(9, body_tilt_degrees=18.0), at_tick=9)
    assert result.command is None
    assert result.reports[0].disposition is LocalTargetDispositionV1.EXPIRED


def test_cancelled_pursuit_cannot_be_relabelled_achieved_by_later_feedback():
    _mapper, controller, _targets = _installed(extension=None)
    controller.cancel_target(TILT, at_tick=0)
    controller.step(_feedback(), at_tick=0)
    result = controller.step(_feedback(1, body_tilt_degrees=18.0), at_tick=1)
    assert result.command is None
    assert result.reports[0].disposition is LocalTargetDispositionV1.CANCELLED


def test_event_overflow_is_reported_and_stops_without_dropping_the_first_four():
    _mapper, controller, _targets = _installed()
    pursuit = controller._pursuits[TILT]
    for index in range(5):
        controller._event(pursuit, 0, f"fixture_event_{index}", _feedback())
    assert len(controller.events) == 4
    first_four = controller.events
    result = controller.step(_feedback(), at_tick=0)
    assert result.event_overflow and result.command is None
    assert controller.events == first_four
    assert all(item.disposition is LocalTargetDispositionV1.INTERRUPTED for item in controller.reports)
    controller.acknowledge_events(4)
    assert not controller.events
    assert controller.step(_feedback(1), at_tick=1).command is None


def test_reading_events_does_not_consume_them_and_acknowledgment_does_not_reset_corrections():
    trial = SensorimotorTrialV1(MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(1, 2, angular_rate_degrees_s=120.0),)))
    for _ in range(4):
        trial.advance()
    events = trial.controller.events
    assert events and trial.controller.events == events
    before = trial.controller.reports
    trial.controller.acknowledge_events(events[-1].number)
    assert trial.controller.events == ()
    assert trial.controller.reports == before
    with pytest.raises(ValueError):
        trial.controller.acknowledge_events(99)


@pytest.mark.parametrize("capacity", [1, 2, 16, 256])
def test_diagnostic_capacity_cannot_change_physics_predictions_events_or_control(capacity):
    reference = run_sensorimotor_experiment_v1("perturbed", trace_capacity=256)
    limited = run_sensorimotor_experiment_v1("perturbed", trace_capacity=capacity)
    assert reference.as_dict() == limited.as_dict()


def test_long_neutral_run_keeps_all_local_storage_bounded_and_rng_unchanged():
    _mapper, controller, _targets = _installed()
    before_rng = random.getstate()
    for tick in range(100):
        feedback = _feedback(tick, body_tilt_degrees=18.0 if tick else 30.0, support_extension=0.6 if tick else 0.4)
        controller.step(feedback, at_tick=tick)
    snapshot = controller.snapshot()
    assert snapshot["command_history_count"] <= 4
    assert max(snapshot["pending_prediction_counts"].values()) <= 4
    assert len(snapshot["events"]) <= 4
    assert snapshot["trace_retained"] <= 256
    assert snapshot["durable_learning_updates"] == 0
    assert random.getstate() == before_rng


def test_exported_records_are_detached_and_immutable():
    _mapper, controller, _targets = _installed()
    step = controller.step(_feedback(), at_tick=0)
    before = step.as_dict()
    external = step.as_dict()
    external["feedback"]["body_tilt_degrees"] = -80.0
    external["reports"].clear()
    assert step.as_dict() == before
    for item, attribute in [(step, "tick"), (step.predictions[0], "expected_coordinate"), (step.reports[0], "reason")]:
        with pytest.raises((FrozenInstanceError, AttributeError)):
            setattr(item, attribute, None)
    json.dumps(controller.snapshot(), allow_nan=False)
    json.dumps(step.as_dict(), allow_nan=False)


@pytest.mark.parametrize("bad", [0, -1, 257, True, 1.5, "4"])
def test_trace_capacity_is_finite_and_typed(bad):
    with pytest.raises((TypeError, ValueError)):
        SensorimotorProfileV1(trace_capacity=bad)


@pytest.mark.parametrize("bad", [1, "true", None])
def test_prediction_switch_is_boolean_not_a_probability(bad):
    with pytest.raises(TypeError):
        SensorimotorProfileV1(prediction_protection=bad)


def test_controller_imports_no_physics_task_or_focal_runtime_and_starts_nothing():
    tree = ast.parse((ROOT / "nca8_sensorimotor.py").read_text(encoding="utf-8"))
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert modules <= {"__future__", "collections", "dataclasses", "cca8_motor_contracts", "nca8_body_targets", "nca8_sensorimotor_contracts"}
    forbidden = {"world", "scenario", "milestones", "pnm", "oracle_policy", "private_state", "_state"}
    assert not {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)} & forbidden
    result = subprocess.run([
        sys.executable, "-c",
        "import random,sys; before=random.getstate(); import nca8_sensorimotor; "
        "assert random.getstate()==before; "
        "assert not ({'cca8_env','cca8_support_world','nca8_runtime','nca8_primitives','nca8_prediction'} & set(sys.modules))",
    ], cwd=ROOT, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr


def test_profile_names_fixed_nonlearned_controls_without_mutable_aliases():
    profile = SensorimotorProfileV1()
    exported = profile.as_dict()
    assert exported["profile_id"] == "fixed_target_control_v1"
    assert exported["orientation_residual_limit_degrees"] == 5.0
    assert exported["extension_residual_limit"] == 0.04
    assert exported["routine_history_capacity"] == exported["significant_event_capacity"] == 4
    assert exported["missing_feedback_grace_ticks"] == 2
    assert not exported["learning_enabled"]
    exported["prediction_protection"] = False
    assert profile.prediction_protection is True
