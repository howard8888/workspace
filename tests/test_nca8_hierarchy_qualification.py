"""H6-B selective controls, fixed time, bounded owners and preserved H6-A semantics."""

from __future__ import annotations

import ast
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorWorldProfileV1
from nca8_body_targets import BodyMovementRequestV1, BodyTargetMapperV1, nominal_body_capabilities_v1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_hierarchy_demo import run_integrated_righting_v1
from nca8_hierarchy_qualification import (
    HIERARCHY_QUALIFICATION_CASES_V1, HIERARCHY_QUALIFICATION_GROUPS_V1,
    HierarchyQualificationProfileV1, hierarchy_contrast_v1, hierarchy_qualification_profile_v1,
    render_hierarchy_qualification_summary_v1, render_hierarchy_qualification_v1,
    run_hierarchy_qualification_group_v1, run_hierarchy_qualification_v1,
)
from nca8_prediction import Nca8PredictionRuntimeV1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, SensorimotorTargetKindV1, TargetOriginV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    before = random.getstate()
    completed = run_hierarchy_qualification_group_v1()
    assert random.getstate() == before
    return {item.profile.case: item for item in completed}


def drives(step):
    return (0.0, 0.0) if step.command is None else (step.command.orientation_drive, step.command.extension_drive)


def focal_at(result, tick):
    return next(focal for focal, _ in result.intervals if focal.calculation.cutoff_tick == tick)


def orientation_target(focal):
    return next(item.current.target for item in focal.reservations
                if item.current.target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST)


def bodies(result):
    return tuple(sample.body for sample in result.physical_samples)


@pytest.mark.parametrize("case", HIERARCHY_QUALIFICATION_CASES_V1)
def test_all_cases_have_fixed_horizon_actual_counts_and_finite_export(results, case):
    result = results[case]
    assert len(result.steps) == 80
    assert [step.tick for step in result.steps] == list(range(80))
    assert [sample.tick for sample in result.physical_samples] == list(range(81))
    assert result.final_cycle.calculation.cutoff_tick == 80
    assert result.profile.physical.dt_seconds == 0.05
    assert result.handoff_consumptions == len(result.intervals) + 1
    assert result.installation_count == sum(bool(focal.reservations) for focal, _ in result.intervals)
    assert result.metrics()["physical_ticks"] == 80
    assert result.metrics()["simulation_seconds"] == 4.0
    assert result.metrics()["nonnull_motor_commands"] == sum(step.command is not None for step in result.steps)
    assert result.metrics()["durable_learning_updates"] == 0
    assert result.metrics()["task_success_established"] is False
    assert not result.bound_violations
    exported = json.loads(json.dumps(result.as_dict(), allow_nan=False))
    assert exported["restores_live_permissions"] is False
    assert len(exported["physical_samples"]) == 81


@pytest.mark.parametrize("case", HIERARCHY_QUALIFICATION_CASES_V1)
def test_all_cases_preserve_evidence_time_single_task_and_memory_bounds(results, case):
    result = results[case]
    for sample in result.physical_samples:
        assert sample.feedback.event_tick <= sample.feedback.available_tick <= sample.tick
    task_ids = set()
    for focal in (*[item for item, _ in result.intervals], result.final_cycle):
        support = focal.calculation.source.motor_support
        if support is not None and support.feedback is not None:
            assert support.feedback.available_tick <= focal.calculation.cutoff_tick
        task = focal.calculation.task
        if task is not None:
            task_ids.add(task.task_id)
            assert task.applications <= 20
            assert task.started_tick == 0
            assert task.as_dict()["expires_at_tick"] == 80
        for reservation in focal.reservations:
            target = reservation.current.target
            assert target.lease_ticks <= 8
            assert reservation.current.expires_at_tick <= 80
            assert target.basis.available_tick <= reservation.current.committed_tick
    assert len(task_ids) <= 1
    counts = dict(result.peak_counts)
    assert counts["durable_maps"] == counts["current_source_states"] == 1
    assert counts["wnm"] <= 1 and counts["current_pnm"] <= 1
    assert counts["righting_applications"] <= 8 and counts["past_previews"] <= 8
    assert counts["lower_predictions_per_axis"] <= 4 and counts["lower_command_history"] <= 4
    assert counts["lower_events"] <= 4 and counts["body_reserved_records"] <= 2


@pytest.mark.parametrize("case", ("nominal", "disturbed"))
def test_qualification_preserves_the_original_h6a_trajectory_and_commitments(results, case):
    original = run_integrated_righting_v1(case)
    qualified = results[case]
    assert original.intervals == qualified.intervals
    assert original.final_cycle == qualified.final_cycle
    assert original.final_feedback == qualified.physical_samples[-1].feedback
    assert original.final_body == qualified.physical_samples[-1].body
    assert original.installation_count == qualified.installation_count
    assert qualified.final_cycle.status == "budget_exhausted"
    assert qualified.physical_samples[-1].feedback.body_tilt_degrees > 12.0


@pytest.mark.parametrize("case", ("righting_off", "righting_off_disturbed"))
def test_righting_off_removes_task_organization_not_sensing_or_physics(results, case):
    result = results[case]
    assert result.installation_count == 0
    assert not result.registered_pnm_ticks
    assert all(step.command is None for step in result.steps)
    assert all(focal.calculation.task is None for focal, _ in result.intervals)
    assert all(focal.calculation.navigation.selected_primitive_id is None for focal, _ in result.intervals)
    assert result.physical_samples[-1].feedback.event_tick == 79
    assert result.physical_samples[-1].body.body_tilt_degrees > result.physical_samples[0].body.body_tilt_degrees
    assert result.profile.physical.orientation_motor_enabled and result.profile.physical.extension_motor_enabled


def test_reversed_mapping_changes_only_the_body_transform_at_first_divergence(results):
    correct, reversed_map = results["nominal"], results["mapping_reversed"]
    assert correct.physical_samples[:9] == reversed_map.physical_samples[:9]
    original, changed = focal_at(correct, 8), focal_at(reversed_map, 8)
    assert original.calculation.source == changed.calculation.source
    assert original.calculation.navigation.application == changed.calculation.navigation.application
    first, second = orientation_target(original), orientation_target(changed)
    assert first.offset == -second.offset
    assert first.basis == second.basis and first.origin == second.origin
    assert first.max_rate == second.max_rate and first.max_displacement == second.max_displacement
    assert first.lease_ticks == second.lease_ticks
    assert drives(correct.steps[8])[0] < 0 < drives(reversed_map.steps[8])[0]
    assert drives(correct.steps[8])[1] == drives(reversed_map.steps[8])[1]
    assert hierarchy_contrast_v1(correct, reversed_map)["first_drive_difference_tick"] == 8
    assert reversed_map.physical_samples[-1].body.body_tilt_degrees > correct.physical_samples[-1].body.body_tilt_degrees


def test_absent_smp_keeps_task_prediction_and_compatible_extension(results):
    correct, absent = results["nominal"], results["orientation_unavailable"]
    original, changed = focal_at(correct, 8), focal_at(absent, 8)
    assert original.calculation.navigation.application == changed.calculation.navigation.application
    assert (SensorimotorTargetKindV1.ORIENTATION_ADJUST, "capability_unavailable") in changed.calculation.proposal.withheld
    assert all(drives(step)[0] == 0.0 for step in absent.steps)
    assert any(drives(step)[1] > 0.0 for step in absent.steps)
    assert absent.registered_pnm_ticks
    assert absent.profile.physical == correct.profile.physical


def test_fast_route_control_keeps_the_same_preintervention_target_and_prefix(results):
    intact, focal_only = results["disturbed"], results["fast_feedback_off"]
    assert intact.physical_samples[:11] == focal_only.physical_samples[:11]
    assert focal_at(intact, 8) == focal_at(focal_only, 8)
    assert [drives(step) for step in intact.steps[:10]] == [drives(step) for step in focal_only.steps[:10]]
    assert hierarchy_contrast_v1(intact, focal_only)["first_drive_difference_tick"] == 10
    assert intact.steps[10].feedback.event_tick == 9
    assert focal_only.steps[10].feedback is None  # event 7 has aged; it is not falsely refreshed.
    assert any(report.reason == "bounded_anomalous_correction" for report in intact.steps[10].reports)
    assert all(report.reason != "bounded_anomalous_correction" for report in focal_only.steps[10].reports)
    assert intact.steps[10].tick < focal_at(intact, 12).calculation.cutoff_tick
    assert focal_at(focal_only, 12).calculation.source.motor_support.feedback.event_tick == 11


def test_fast_correction_event_returns_with_original_identity(results):
    result = results["disturbed"]
    local = result.steps[10]
    comparison = next(item for item in local.comparisons if item.unexpected)
    assert comparison.feedback.event_tick == 9 and comparison.feedback.available_tick == 10
    returned = focal_at(result, 12).local_events
    assert any(item.sample_id == comparison.feedback.sample_id and item.event_tick == 9 and item.noticed_tick == 10 for item in returned)


def test_delayed_sensing_changes_both_paths_without_backdating(results):
    delayed = results["delayed_feedback"]
    assert delayed.profile.physical.sensor_delay_ticks == 4
    assert focal_at(delayed, 4).calculation.source_status == "current_source_unavailable"
    for sample in delayed.physical_samples[1:]:
        if sample.feedback.event_tick:
            assert sample.feedback.available_tick == sample.feedback.event_tick + 4
    assert any(report.reason == "current_feedback_timeout" for step in delayed.steps for report in step.reports)
    assert delayed.installation_count == 1
    pair = hierarchy_contrast_v1(results["disturbed"], delayed)
    assert pair["same_dt_and_horizon"] and pair["same_physical_forcing"]
    assert not pair["same_sensor_delay"]


def test_missing_acquisitions_keep_old_time_and_do_not_become_no_contact(results):
    missing = results["feedback_missing"]
    assert missing.physical_samples[:10] == results["disturbed"].physical_samples[:10]
    assert missing.physical_samples[-1].feedback.event_tick == 8
    assert missing.physical_samples[-1].feedback.support_contact is True
    assert missing.physical_samples[-1].feedback.body_tilt_degrees != missing.physical_samples[-1].body.body_tilt_degrees
    assert focal_at(missing, 12).calculation.source_status == "current_source_unavailable"
    assert missing.steps[10].feedback.event_tick == 8  # Last in-flight acquisition is still within the two-tick age limit.
    assert all(step.command is None for step in missing.steps[11:])
    assert missing.final_cycle.calculation.task.status == "budget_exhausted"


def test_local_prediction_off_preserves_reactive_feedback_and_can_have_same_endpoint(results):
    intact, reactive = results["disturbed"], results["local_prediction_off"]
    assert intact.physical_samples[:11] == reactive.physical_samples[:11]
    assert any(item.unexpected for item in reactive.steps[10].comparisons)
    assert any(item.reason == "reactive_target_following" for item in reactive.steps[10].reports)
    assert reactive.steps[10].command is not None
    assert not any(item.reason == "bounded_anomalous_correction" for step in reactive.steps for item in step.reports)
    pair = hierarchy_contrast_v1(intact, reactive)
    assert pair["first_drive_difference_tick"] == 10
    assert bodies(intact) != bodies(reactive)
    assert intact.physical_samples[-1].body.body_tilt_degrees == pytest.approx(reactive.physical_samples[-1].body.body_tilt_degrees)


def test_support_loss_prediction_control_preserves_an_honest_null_drive_result(results):
    intact, reactive = results["support_loss"], results["support_loss_prediction_off"]
    assert any(sample.feedback.support_contact is False for sample in intact.physical_samples)
    assert hierarchy_contrast_v1(intact, reactive)["first_drive_difference_tick"] is None
    assert bodies(intact) == bodies(reactive)
    assert any(item.reason == "unexpected_contact_loss" for step in intact.steps for item in step.reports)
    assert not any(item.reason == "unexpected_contact_loss" for step in reactive.steps for item in step.reports)


def test_task_pnm_registration_off_is_not_a_missing_projection_dispatch_failure(results):
    intact, no_registration = results["disturbed"], results["task_pnm_consumer_off"]
    assert intact.registered_pnm_ticks and no_registration.registered_pnm_ticks == ()
    assert intact.intervals == no_registration.intervals
    assert intact.final_cycle == no_registration.final_cycle
    assert intact.physical_samples == no_registration.physical_samples
    assert intact.installation_count == no_registration.installation_count > 0
    for focal, _ in no_registration.intervals:
        if focal.reservations:
            assert focal.receipt.dispatch.motor.projection is not None
            assert focal.commitment.pnm_id is not None
    assert dict(no_registration.peak_counts)["current_pnm"] == 0
    assert dict(no_registration.peak_counts)["past_previews"] == 0
    assert hierarchy_contrast_v1(intact, no_registration)["first_drive_difference_tick"] is None


def test_registration_off_really_disconnects_the_named_consumer(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("disabled registration consumer was called")
    monkeypatch.setattr(Nca8PredictionRuntimeV1, "adopt_support_preview", prohibited)
    result = run_hierarchy_qualification_v1("task_pnm_consumer_off")
    assert result.installation_count > 0


@pytest.mark.parametrize("case,k,reads,exit_tick", [("disturbed", 4, 21, 80), ("cadence_1", 1, 81, 20), ("cadence_8", 8, 11, 80)])
def test_cadence_keeps_physical_time_and_both_task_budgets(results, case, k, reads, exit_tick):
    result = results[case]
    assert result.profile.focal_interval_ticks == k
    assert len(result.intervals) + 1 == reads
    assert result.first_task_budget_exit_tick == exit_tick
    assert all(len(lower) == k for _, lower in result.intervals)
    assert result.final_cycle.calculation.cutoff_tick == 80
    assert result.profile.physical == results["disturbed"].profile.physical
    assert result.final_cycle.calculation.task.applications <= 20
    assert result.metrics()["tick16_observer_tilt"] == result.physical_samples[16].body.body_tilt_degrees
    assert all(step.command is None for step in result.steps[exit_tick:])


def test_assistance_changes_the_world_without_inventing_agent_action_or_credit(results):
    off, on = results["assistance_off"], results["assistance_on"]
    assert off.physical_samples[:9] == on.physical_samples[:9]
    assert off.profile.physical.initial_body == on.profile.physical.initial_body
    assert off.installation_count == on.installation_count == 0
    assert all(step.command is None for item in (off, on) for step in item.steps)
    assert on.final_cycle.calculation.source_status == "currently_adequate_not_dwell"
    assert off.final_cycle.calculation.source_status == "support_needed"
    assert on.final_cycle.calculation.task is None
    assert on.metrics()["task_success_established"] is False
    assert hierarchy_contrast_v1(off, on)["first_drive_difference_tick"] is None
    assert not hierarchy_contrast_v1(off, on)["same_physical_forcing"]


@pytest.mark.parametrize("case", ("disturbed", "fast_feedback_off", "cadence_1", "task_pnm_consumer_off"))
def test_trace_retention_rendering_and_exports_cannot_change_the_run(results, case):
    small = run_hierarchy_qualification_v1(case, trace_capacity=1)
    full = results[case]
    assert small.metrics() == full.metrics()
    assert small.intervals == full.intervals and small.physical_samples == full.physical_samples
    assert len(small.trace) == 1
    assert dict(small.peak_counts)["focal_trace"] == dict(small.peak_counts)["lower_trace"] == 1
    for name, count in small.peak_counts:
        if name not in {"focal_trace", "lower_trace"}:
            assert count == dict(full.peak_counts)[name]
    before = json.dumps(small.as_dict(), sort_keys=True)
    rng = random.getstate()
    compact = render_hierarchy_qualification_v1(small)
    detail = render_hierarchy_qualification_v1(small, detail=True)
    assert "Task completion NOT established" in compact
    assert detail.count("    LOWER tick=") == 80
    assert "event=" in detail and "available=" in detail
    exported = small.as_dict()
    exported["profile"]["righting_enabled"] = "changed diagnostic only"
    assert json.dumps(small.as_dict(), sort_keys=True) == before
    assert random.getstate() == rng


@pytest.mark.parametrize("k", (1, 4, 8))
def test_shared_step_api_matches_explicit_boundary_scheduling(k):
    combined, explicit = IntegratedRightingTrialV1(), IntegratedRightingTrialV1()
    for _ in range(3):
        focal, steps = combined.step(local_updates=k)
        other = explicit.focal_step()
        other_steps = tuple(explicit.advance_lower() for _ in range(k))
        assert focal == other and steps == other_steps
    assert combined.snapshot() == explicit.snapshot()
    assert combined.handoff_consumptions == 3


@pytest.mark.parametrize("bad", (True, False, 0, -1, 2, 3, 5, 9, None, "4", 4.0))
def test_invalid_cadence_is_rejected_before_a_focal_or_physical_side_effect(bad):
    trial = IntegratedRightingTrialV1()
    before = trial.snapshot()
    with pytest.raises(ValueError):
        trial.step(local_updates=bad)
    assert trial.snapshot() == before


@pytest.mark.parametrize("bad", (True, -1, 81, 1.5, "8"))
def test_invalid_fast_route_cutoff_does_not_construct_a_trial(bad):
    with pytest.raises(ValueError):
        IntegratedRightingTrialV1(focal_only_feedback_from_tick=bad)


@pytest.mark.parametrize("bad", (True, False, 0, 2, -2, None, "-1", 1.0))
def test_invalid_mapping_sign_is_rejected_in_the_body_owner(bad):
    with pytest.raises((TypeError, ValueError)):
        BodyTargetMapperV1(MotorStreamRefV1("mapping_validation", 1), nominal_body_capabilities_v1(), orientation_mapping_sign=bad)


@pytest.mark.parametrize("tilt", (-90, -89, -30, 0, 30, 89, 90))
def test_mapping_fault_remains_inside_original_capability_and_preserves_sensor(tilt):
    stream = MotorStreamRefV1("mapping_bounds", 1)
    feedback = MotorFeedbackV1(stream, 1, 0, 0, tilt, 0.5, True, 0.5, 0.2)
    origin = TargetOriginV1(stream, "task", "application", "envelope")
    request = BodyMovementRequestV1(origin, 0.0, 0.6)
    proposals = []
    for sign in (1, -1):
        mapper = BodyTargetMapperV1(stream, nominal_body_capabilities_v1(), orientation_mapping_sign=sign)
        mapper.update_feedback(feedback, at_tick=0)
        proposals.append(mapper.propose(request, at_tick=0))
    for proposal in proposals:
        assert proposal.request is request
        assert len(proposal.bindings) == 2
        for binding in proposal.bindings:
            target = binding.target
            assert target.basis is feedback
            assert abs(target.offset) <= binding.capability.maximum_step
            assert binding.capability.minimum_coordinate <= target.endpoint <= binding.capability.maximum_coordinate
    assert proposals[0].bindings[1] == proposals[1].bindings[1]  # Extension is not lesioned.


@pytest.mark.parametrize("bad", (None, "", "success", "a0", 1, [], {}))
def test_unknown_profile_is_never_a_legacy_or_nominal_fallback(bad):
    with pytest.raises(ValueError):
        hierarchy_qualification_profile_v1(bad)
    with pytest.raises(ValueError):
        run_hierarchy_qualification_v1(bad)


@pytest.mark.parametrize("bad", (None, "", "success", "ALL", 1, [], {}))
def test_unknown_group_is_rejected(bad):
    with pytest.raises(ValueError):
        run_hierarchy_qualification_group_v1(bad)


@pytest.mark.parametrize("field,value", [
    ("focal_interval_ticks", True), ("focal_interval_ticks", 3), ("orientation_mapping_sign", False),
    ("orientation_mapping_sign", 0), ("righting_enabled", 1), ("orientation_available", 0),
    ("local_prediction_enabled", None), ("task_pnm_consumer_enabled", "false"),
    ("focal_only_feedback_from_tick", 81), ("physical", MotorWorldProfileV1(dt_seconds=0.025)),
])
def test_profile_rejects_coercion_or_changed_timebase(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(hierarchy_qualification_profile_v1("nominal"), **{field: value})


@pytest.mark.parametrize("bad", (None, "false", 0, 1))
def test_task_pnm_flag_is_boolean_not_a_truthy_configuration(bad):
    with pytest.raises(TypeError):
        Nca8RightingPreviewSessionV1(MotorStreamRefV1("flag", 1), task_pnm_consumer_enabled=bad)


def test_reset_preserves_explicit_profile_but_revokes_old_generation():
    trial = IntegratedRightingTrialV1(orientation_mapping_sign=-1, task_pnm_consumer_enabled=False, focal_only_feedback_from_tick=8)
    before, lower = trial.step()
    old_controller = trial.controller
    old_stream = trial.latest_feedback.stream
    trial.reset()
    assert old_controller.fault is not None
    assert trial.latest_feedback.stream.generation == old_stream.generation + 1
    assert trial.snapshot()["orientation_mapping_sign"] == -1
    assert trial.snapshot()["task_pnm_registration_enabled"] is False
    assert trial.snapshot()["focal_only_feedback_from_tick"] == 8
    assert trial.handoff_consumptions == 0
    assert trial.retained_counts()["current_pnm"] == 0
    assert trial.controller.installation_count == 0
    assert before.receipt.dispatch.motor.stream == old_stream
    assert lower[0].feedback.stream == old_stream


def test_summary_discloses_null_prediction_effect_and_cadence_budget_confound(results):
    summary = render_hierarchy_qualification_summary_v1(tuple(results.values()))
    assert "NULL motor effect" in summary
    assert "20-opportunity budget at tick 20" in summary
    assert "task prediction is useful or useless" in summary
    assert "cmd=nonneutral motor commands" in summary
    assert "first drive difference=None" in summary
    assert "task completion" in summary
    assert "P16-1G and A99 remain open" in summary


def test_experiment_reports_are_not_imported_by_cognitive_or_lower_owners():
    for name in ("nca8_righting.py", "nca8_body_targets.py", "nca8_sensorimotor.py", "nca8_sensory.py", "nca8_hierarchy.py", "nca8_hierarchy_demo.py"):
        tree = ast.parse((ROOT / name).read_text(encoding="utf-8"))
        assert not any(isinstance(node, ast.ImportFrom) and node.module == "nca8_hierarchy_qualification" for node in ast.walk(tree))


def test_group_and_case_inventory_is_finite_and_unambiguous():
    assert len(HIERARCHY_QUALIFICATION_CASES_V1) == len(set(HIERARCHY_QUALIFICATION_CASES_V1)) == 17
    assert set(HIERARCHY_QUALIFICATION_GROUPS_V1) == {"all", "righting", "mapping", "feedback", "prediction", "cadence", "assistance"}
    profile = hierarchy_qualification_profile_v1("nominal")
    assert isinstance(profile, HierarchyQualificationProfileV1)
    assert profile.as_dict()["lower_target_tolerance_degrees"] == 1.0
    assert profile.as_dict()["mobility_maximum_absolute_tilt_degrees"] == 12.0
