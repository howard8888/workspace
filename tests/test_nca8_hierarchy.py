"""H6-A causal integration, ownership, physical timing and bounded failure tests."""

from __future__ import annotations

import ast
import json
import random
from dataclasses import replace
from pathlib import Path

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1, admit_motor_feedback_batch_v1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1, MotorWorldV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_contracts import CyclePhase
from nca8_handoff import Nca8InternalHandoffV1
from nca8_hierarchy import IntegratedRightingCoreV1, IntegratedRightingTrialV1
from nca8_righting import RightingActivityV1, RightingContextV1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorProfileV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, SensorimotorTargetKindV1

ROOT = Path(__file__).resolve().parents[1]
STREAM = MotorStreamRefV1("h6_unit_body", 1)


def reading(tick=0, **changes):
    return replace(MotorFeedbackV1(STREAM, tick + 1, tick, tick, 30, 0.4, True, 0.5, 0.3), **changes)


def core_bundle():
    core = IntegratedRightingCoreV1(STREAM)
    controller = SensorimotorExecutorV1(core.cognition.mapper, installation_source=core.handoff)
    result = core.run_cycle(reading(), cutoff_tick=0)
    return core, controller, result


def test_core_runs_actual_a_to_f_without_any_physical_or_lower_call(monkeypatch):
    def prohibited(*args, **kwargs):
        raise AssertionError("a focal core called external/lower work")
    monkeypatch.setattr(MotorWorldV1, "step", prohibited)
    monkeypatch.setattr(SensorimotorExecutorV1, "step", prohibited)
    core, controller, result = core_bundle()
    assert result.scheduler.phases == tuple(CyclePhase)
    assert result.reservations and result.receipt.disposition == "ready"
    assert controller.next_tick == controller.installation_count == 0
    assert core.scheduler.last_completed_cycle == 1
    assert result.commitment.task_action == "RESTORE_VIABLE_SUPPORT"
    channels = [item.channel for item in core.trace.snapshot()]
    assert channels.index("hierarchy_commit") < channels.index("hierarchy_handoff") < channels.index("hierarchy_learning")
    assert channels.index("hierarchy_learning") < channels.index("hierarchy_close")


def test_hierarchy_core_contains_no_provider_or_executor_access():
    tree = ast.parse((ROOT / "nca8_hierarchy.py").read_text())
    core = next(item for item in tree.body if isinstance(item, ast.ClassDef) and item.name == "IntegratedRightingCoreV1")
    forbidden = {"_world", "observer_body", "step", "step_motor", "install_authorized", "advance_lower"}
    assert not any(isinstance(item, ast.Attribute) and item.attr in forbidden for item in ast.walk(core))


def test_first_selected_contribution_really_installs_and_drives_h2():
    trial = IntegratedRightingTrialV1()
    initial = trial.observer_body
    result = trial.focal_step()
    assert trial.tick == 0 and trial.observer_body == initial
    assert trial.controller.installation_count == 1
    assert trial.core.handoff.receipt.disposition == "consumed"
    assert result.calculation.navigation.selected_primitive_id == "ip:righting"
    assert result.calculation.source.motor_support.rates == (None, None, None)
    assert result.reservations[0].current.target.endpoint == pytest.approx(0.5)
    steps = tuple(trial.advance_lower() for _ in range(4))
    assert trial.tick == 4 and trial.controller.installation_count == 1
    assert [item.command is not None for item in steps] == [True, True, False, False]
    assert trial.observer_body.support_extension == pytest.approx(0.5)
    assert trial.snapshot()["handoff_consumptions"] == 1


def test_local_achievement_does_not_complete_persistent_righting_task():
    trial = IntegratedRightingTrialV1()
    first, lower = trial.step()
    assert lower[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert first.calculation.task.status == "active"
    assert trial.latest_feedback.useful_loading < first.calculation.task.context.criterion[1]
    second = trial.focal_step()
    assert second.calculation.task.task_id == first.calculation.task.task_id
    assert second.calculation.task.started_tick == first.calculation.task.started_tick
    assert second.calculation.task.applications == 2
    assert second.commitment.task_action_id != first.commitment.task_action_id
    assert trial.snapshot()["task_success_established"] is False


@pytest.mark.parametrize("tilt", [-35, -30, 30, 35])
def test_mirrored_current_evidence_changes_consumed_orientation_drive(tilt):
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(tilt, 0.9)))
    result = trial.focal_step()
    target = next(item.current.target for item in result.reservations if item.current.target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST)
    step = trial.advance_lower()
    assert step.command.orientation_drive * tilt < 0
    assert target.offset * tilt < 0
    assert abs(trial.observer_body.body_tilt_degrees) < abs(tilt)


def test_same_current_sample_different_supported_history_changes_real_consumed_targets():
    owners = []
    for prior in (reading(body_tilt_degrees=34, useful_loading=0.4, destabilization=0.4),
                  reading(body_tilt_degrees=26, useful_loading=0.6, destabilization=0.2)):
        core = IntegratedRightingCoreV1(STREAM)
        first = core.run_cycle(prior, cutoff_tick=0)
        core.handoff.cancel(first.receipt, reason="unit_fixture_preview_not_executed")
        result = core.run_cycle(reading(4), cutoff_tick=4)
        controller = SensorimotorExecutorV1(core.cognition.mapper, start_tick=4, installation_source=core.handoff)
        core.handoff.consume_motor(result.receipt)
        controller.install_authorized(result.reservations, at_tick=4)
        step = controller.step(reading(4), at_tick=4)
        owners.append((result, step))
    good, bad = owners
    assert good[0].calculation.source.motor_support.feedback == bad[0].calculation.source.motor_support.feedback
    assert good[1].command.orientation_drive < 0
    assert bad[1].command.orientation_drive == 0
    assert good[0].commitment.action_envelope_id == bad[0].commitment.action_envelope_id  # IDs alone do not select values.
    assert good[0].receipt.dispatch.motor.targets != bad[0].receipt.dispatch.motor.targets


def test_actual_sensing_matches_independent_h2_replay_not_the_task_pnm():
    trial = IntegratedRightingTrialV1()
    replay = MotorWorldV1(trial.latest_feedback.stream)
    replay.observe()
    for _ in range(5):
        focal, steps = trial.step()
        for step in steps:
            replay.step(step.command)
        assert trial.observer_body == replay.body
        assert trial.latest_feedback == replay.observe()
        assert focal.calculation.source.motor_support.feedback.event_tick <= focal.calculation.cutoff_tick
    assert trial.latest_feedback.useful_loading != focal.calculation.navigation.application.projection.predicted_loading


def test_return_to_source_preserves_one_event_identity_and_old_focal_basis():
    trial = IntegratedRightingTrialV1()
    old, _ = trial.step()
    frozen = json.dumps(old.as_dict(), sort_keys=True)
    delivered = trial.latest_feedback
    new = trial.focal_step()
    source_feedback = new.calculation.source.motor_support.feedback
    assert source_feedback == delivered
    assert source_feedback.event_tick == 3 and source_feedback.available_tick == new.calculation.cutoff_tick == 4
    assert source_feedback.sample_id == 4
    assert json.dumps(old.as_dict(), sort_keys=True) == frozen
    assert old.calculation.source.motor_support.feedback.event_tick == 0
    assert trial.core.cognition.navigation.current_wnm.primary_source_state is new.calculation.source
    assert trial.core.cognition.maps.durable_map_count == trial.core.cognition.maps.current_state_count == 1


def test_later_external_disturbance_cannot_change_original_commitment():
    normal = IntegratedRightingTrialV1()
    disturbed = IntegratedRightingTrialV1(MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(8, 9, 160),)))
    first_normal = normal.focal_step()
    first_disturbed = disturbed.focal_step()
    assert first_normal.as_dict() == first_disturbed.as_dict()
    for _ in range(4):
        normal.advance_lower(); disturbed.advance_lower()
    assert normal.latest_feedback == disturbed.latest_feedback


def test_feedback_corrects_a_fixed_time_disturbance_before_next_focal_decision():
    normal = IntegratedRightingTrialV1()
    disturbed = IntegratedRightingTrialV1(MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(8, 9, 160),)))
    normal.step(); normal.step()
    disturbed.step(); disturbed.step()
    normal.focal_step(); disturbed.focal_step()
    nominal_steps = tuple(normal.advance_lower() for _ in range(4))
    disturbed_steps = tuple(disturbed.advance_lower() for _ in range(4))
    assert normal.core.scheduler.last_completed_cycle == disturbed.core.scheduler.last_completed_cycle == 3
    assert any(report.reason == "bounded_anomalous_correction" for step in disturbed_steps for report in step.reports)
    assert disturbed_steps[2].tick == 10 < 12
    assert disturbed_steps[2].command.orientation_drive != nominal_steps[2].command.orientation_drive
    event = disturbed.controller.events[0]
    assert event.event_tick == 9 and event.noticed_tick == 10
    next_cycle = disturbed.focal_step()
    assert next_cycle.local_events[0] == event
    assert disturbed.controller.events == ()  # Explicit successful source-reader acknowledgment, not inspection.
    assert next_cycle.calculation.task.task_id == "righting:1:1"


def test_lower_calls_are_always_after_core_close_and_single_consumption(monkeypatch):
    trial = IntegratedRightingTrialV1()
    original = MotorWorldV1.step
    visits = []
    def observed(world, command=None):
        assert not trial.core.running
        assert trial.core.handoff.receipt.disposition == "consumed"
        assert trial.core.scheduler.last_completed_cycle >= 1
        visits.append((world.tick, trial.snapshot()["handoff_consumptions"]))
        return original(world, command)
    monkeypatch.setattr(MotorWorldV1, "step", observed)
    trial.step(); trial.step()
    assert visits == [(tick, 1 if tick < 4 else 2) for tick in range(8)]


@pytest.mark.parametrize("method", ["consume", "consume_motor"])
def test_receipt_cannot_be_consumed_twice_or_by_wrong_transport(method):
    core, _, result = core_bundle()
    if method == "consume":
        with pytest.raises(TypeError):
            core.handoff.consume(result.receipt)
        assert core.handoff.receipt is result.receipt
    core.handoff.consume_motor(result.receipt)
    with pytest.raises(RuntimeError):
        core.handoff.consume_motor(result.receipt)
    assert core.handoff.receipt.disposition == "consumed"


@pytest.mark.parametrize("foreign", ["copy", "other_owner", "old_generation"])
def test_foreign_copied_and_stale_receipts_never_install(foreign):
    core, _, result = core_bundle()
    if foreign == "copy":
        owner, receipt = core.handoff, replace(result.receipt)
    else:
        owner, receipt = Nca8InternalHandoffV1(generation=2 if foreign == "old_generation" else 1), result.receipt
    with pytest.raises(RuntimeError):
        owner.consume_motor(receipt)
    assert core.handoff.receipt.disposition == "ready"


def test_grant_unavailable_before_outer_consumption_and_failure_is_sticky():
    core, controller, result = core_bundle()
    with pytest.raises(RuntimeError):
        controller.install_authorized(result.reservations, at_tick=0)
    assert controller.fault is not None and controller.installation_count == 0
    assert core.handoff.receipt.disposition == "ready"
    with pytest.raises(RuntimeError):
        controller.step(reading(), at_tick=0)


def test_one_consumed_grant_can_install_once_not_per_motor_update():
    core, controller, result = core_bundle()
    core.handoff.consume_motor(result.receipt)
    controller.install_authorized(result.reservations, at_tick=0)
    assert controller.installation_count == 1
    controller.step(reading(), at_tick=0)
    with pytest.raises(RuntimeError):
        controller.install_authorized(result.reservations, at_tick=1)
    assert controller.installation_count == 1


def test_copied_reservation_fails_after_spending_grant_and_cannot_be_retried():
    core, controller, result = core_bundle()
    core.handoff.consume_motor(result.receipt)
    with pytest.raises(ValueError):
        controller.install_authorized(tuple(replace(item) for item in result.reservations), at_tick=0)
    assert controller.fault is not None
    with pytest.raises(RuntimeError):
        core.handoff.claim_motor_targets()
    assert controller.installation_count == 0


def test_fixture_api_remains_single_use_and_cannot_mix_with_integrated_api():
    core, integrated, result = core_bundle()
    with pytest.raises(ValueError):
        integrated.install(result.reservations, at_tick=0)
    other = IntegratedRightingCoreV1(STREAM)
    result = other.run_cycle(reading(), cutoff_tick=0)
    fixture = SensorimotorExecutorV1(other.cognition.mapper)
    fixture.install(result.reservations, at_tick=0)
    with pytest.raises(ValueError):
        fixture.install(result.reservations, at_tick=0)
    with pytest.raises(ValueError):
        fixture.install_authorized(result.reservations, at_tick=0)


def test_one_body_generation_cannot_attach_a_second_lower_executor():
    core, _, _ = core_bundle()
    with pytest.raises(ValueError):
        SensorimotorExecutorV1(core.cognition.mapper, installation_source=core.handoff)


def test_material_replacement_has_new_authorization_and_immutable_old_envelope():
    trial = IntegratedRightingTrialV1()
    first, _ = trial.step()
    old = first.reservations[0].current
    second = trial.focal_step()
    new = second.reservations[0].current
    assert old in second.receipt.dispatch.motor.replaces
    assert new.execution_id != old.execution_id
    assert new.target.origin.application_id != old.target.origin.application_id
    assert old.expires_at_tick == 8 and new.expires_at_tick == 12
    assert trial.controller.installation_count == 2
    assert old.target.endpoint == 0.5 and new.target.endpoint == pytest.approx(0.7)
    assert first.receipt.dispatch.motor.targets == (old,)


def test_bounded_local_refinement_preserves_lease_and_original_commitment():
    trial = IntegratedRightingTrialV1()
    focal = trial.focal_step()
    original = focal.reservations[0]
    trial.advance_lower()
    refined = trial.core.cognition.mapper.refine(original, endpoint=0.505, at_tick=1)
    trial.controller.replace_target(refined, at_tick=1)
    next_step = trial.advance_lower()
    assert next_step.reports[0].committed_target.target.revision == 2
    assert refined.current.expires_at_tick == original.current.expires_at_tick == 8
    assert focal.receipt.dispatch.motor.targets[0].target.revision == 1
    assert original.current.target.endpoint == 0.5
    with pytest.raises(ValueError):
        trial.core.cognition.mapper.refine(refined, endpoint=0.52, at_tick=2)


def test_no_new_focal_output_continues_only_the_old_lease_without_cancelling_it():
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(30, 0.9)))
    first = trial.focal_step()
    trial.advance_lower()
    second = trial.focal_step(competing_bids=(competing_preview_bid_v1(2, persistence_rank=100),))
    assert second.receipt.dispatch.motor.directive == "no_new_task_output"
    assert second.calculation.navigation.application is None
    assert trial.controller.installation_count == 1
    assert trial.advance_lower().command is not None
    assert first.reservations[0].current.expires_at_tick == 8


def test_no_active_target_means_neutral_drive_but_passive_physics_still_advances():
    trial = IntegratedRightingTrialV1(righting_enabled=False)
    before = trial.observer_body
    focal, steps = trial.step()
    assert not focal.reservations
    assert all(step.command is None for step in steps)
    assert trial.tick == 4 and trial.observer_body.body_tilt_degrees > before.body_tilt_degrees
    assert trial.controller.installation_count == 0


def test_expiry_stops_pursuit_without_completing_or_resetting_task():
    trial = IntegratedRightingTrialV1(
        MotorWorldProfileV1(extension_motor_enabled=False),
        control_profile=SensorimotorProfileV1(prediction_protection=False),
    )
    original = trial.focal_step()
    for _ in range(10):
        result = trial.advance_lower()
    assert result.command is None
    assert any(item.disposition is LocalTargetDispositionV1.EXPIRED for item in result.reports)
    assert trial.controller.installation_count == 1
    assert trial.core.cognition.righting.task.task_id == original.calculation.task.task_id
    assert trial.core.cognition.righting.task.status == "active"
    before = trial.observer_body
    trial.advance_lower()
    assert trial.observer_body != before


def test_explicit_cancel_stops_command_but_does_not_undo_physical_effect():
    trial = IntegratedRightingTrialV1()
    original = trial.focal_step()
    trial.advance_lower()
    extension = trial.observer_body.support_extension
    trial.cancel()
    assert trial.core.cognition.righting.task.status == "cancelled"
    assert trial.advance_lower().command is None
    assert trial.observer_body.support_extension == extension
    result = trial.focal_step()
    assert result.status == "cancelled" and not result.reservations
    assert original.calculation.task.status == "active"
    assert original.receipt.dispatch.motor.targets[0].target.endpoint == 0.5


def test_explicit_context_change_can_cancel_old_lower_activity_without_rewriting_criterion():
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(30, 0.9)))
    old = trial.focal_step()
    trial.advance_lower()
    new = trial.focal_step(context=RightingContextV1("activity:new_rest", RightingActivityV1.REST))
    assert new.receipt.dispatch.motor.cancel_previous is True
    assert old.calculation.task.context.activity is RightingActivityV1.MOBILITY
    assert new.calculation.task is None or new.calculation.task.context.activity is RightingActivityV1.REST
    assert not trial.snapshot()["task_success_established"]


@pytest.mark.parametrize("channels", [("body_tilt_degrees",), ("useful_loading",), ("support_contact",), ("destabilization",)])
def test_missing_input_never_becomes_fabricated_success(channels):
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(unavailable_channels=channels))
    focal, steps = trial.step()
    assert all(getattr(trial.latest_feedback, field) is None for field in channels)
    if channels == ("body_tilt_degrees",):
        assert focal.reservations
        assert all(item.current.target.kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION for item in focal.reservations)
    else:
        assert not focal.reservations and all(item.command is None for item in steps)
    assert not trial.snapshot()["task_success_established"]


def test_absent_entire_feedback_has_truthful_bounded_no_output_core():
    core = IntegratedRightingCoreV1(STREAM)
    result = core.run_cycle(None, cutoff_tick=0)
    assert result.calculation.source.motor_support.feedback is None
    assert not result.reservations and result.calculation.task is None
    assert result.receipt.dispatch.motor.directive == "no_new_task_output"


def test_dropouts_do_not_refresh_event_identity_or_renew_targets():
    profile = MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(0, 80, drop_feedback=True),))
    trial = IntegratedRightingTrialV1(profile)
    first, _ = trial.step()
    second, steps = trial.step()
    assert trial.latest_feedback.sample_id == 1 and trial.latest_feedback.event_tick == 0
    assert trial.controller.installation_count == 1
    assert first.calculation.task.task_id == second.calculation.task.task_id
    assert not second.reservations
    assert all(step.command is None for step in steps)


@pytest.mark.parametrize("capabilities", [(), nominal_body_capabilities_v1()[1:]])
def test_unavailable_lower_capability_is_refusal_or_partial_not_fake_completion(capabilities):
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(initial_body=MotorBodyStateV1(30, 0.9)), capabilities=capabilities)
    focal, steps = trial.step()
    if capabilities:
        assert focal.status == "partial_authorization"
        assert all(step.command is None or step.command.orientation_drive == 0 for step in steps)
    else:
        assert focal.status == "refused_no_usable_target"
        assert all(step.command is None for step in steps)
    assert any(reason == "capability_unavailable" for _, reason in focal.calculation.proposal.withheld)


def test_external_help_is_not_credited_as_agent_command_or_success():
    trial = IntegratedRightingTrialV1(
        MotorWorldProfileV1(initial_body=MotorBodyStateV1(30, 0.95), perturbations=(MotorWorldPerturbationV1(0, 4, -180),)),
        righting_enabled=False,
    )
    steps = [step for _ in range(2) for step in trial.step()[1]]
    assert all(step.command is None for step in steps)
    assert abs(trial.observer_body.body_tilt_degrees) < 12
    assert trial.controller.installation_count == 0
    assert trial.core.cognition.righting.task is None
    assert not trial.snapshot()["task_success_established"]


def test_full_task_budget_never_renews_from_local_achievement_or_new_sample():
    trial = IntegratedRightingTrialV1()
    initial_id = None
    for _ in range(20):
        focal, _ = trial.step()
        initial_id = initial_id or focal.calculation.task.task_id
        assert focal.calculation.task.task_id == initial_id
        assert all(item.current.expires_at_tick <= 80 for item in focal.reservations)
    final = trial.focal_step()
    assert final.status == "budget_exhausted" and final.calculation.task.applications == 20
    assert not final.reservations and trial.tick == 80
    for _ in range(4):
        assert trial.advance_lower().command is None
    again = trial.focal_step()
    assert again.status == "budget_exhausted" and again.calculation.task.task_id == initial_id


@pytest.mark.parametrize("failure", ["after_physics", "malformed_return", "wrong_tick"])
def test_possible_physical_side_effects_stop_both_owners_without_retry(monkeypatch, failure):
    trial = IntegratedRightingTrialV1()
    trial.focal_step()
    original = MotorWorldV1.step
    calls = []
    def broken(world, command=None):
        calls.append(command)
        result = original(world, command)
        if failure == "after_physics":
            raise RuntimeError("link failed after movement")
        if failure == "malformed_return":
            return ({"task_success": True},)
        original(world, None)
        return result
    monkeypatch.setattr(MotorWorldV1, "step", broken)
    with pytest.raises((RuntimeError, TypeError)):
        trial.advance_lower()
    assert trial.stopped and trial.core.handoff.receipt.disposition == "consumed"
    assert trial.tick >= 1
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert len(calls) == 1


def test_f_phase_failure_prevents_installation_and_all_world_calls(monkeypatch):
    trial = IntegratedRightingTrialV1()
    def fail(*args):
        raise RuntimeError("F failed")
    monkeypatch.setattr(trial.core.scheduler, "phase_f_finish", fail)
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert trial.tick == trial.controller.installation_count == 0
    assert trial.core.last_commitment is not None
    assert trial.core.handoff.receipt.disposition == "cancelled"
    assert trial.stopped


def test_disabled_handoff_never_installs_or_silently_uses_a0():
    trial = IntegratedRightingTrialV1(handoff_enabled=False)
    with pytest.raises(RuntimeError):
        trial.focal_step()
    assert trial.tick == trial.controller.installation_count == 0 and trial.stopped
    assert trial.core.handoff.receipt.disposition == "refused"


def test_reset_invalidates_old_executor_receipt_current_source_and_sensor_queue():
    trial = IntegratedRightingTrialV1()
    old = trial.focal_step()
    trial.advance_lower()
    core, controller = trial.core, trial.controller
    assert trial.snapshot()["pending_sensor_count"] == 1
    trial.reset()
    assert trial.tick == 0 and trial.latest_feedback.stream.generation == 2
    assert trial.controller.installation_count == 0 and trial.core.cognition.righting.task is None
    assert trial.snapshot()["pending_sensor_count"] == 0 and trial.history() == ()
    assert core.fault is not None and controller.fault is not None
    with pytest.raises(RuntimeError):
        trial.core.handoff.consume_motor(old.receipt)
    assert trial.focal_step().calculation.task.task_id == "righting:2:1"


def test_reentrant_physical_or_focal_calls_are_rejected_before_another_effect(monkeypatch):
    trial = IntegratedRightingTrialV1()
    trial.focal_step()
    original = MotorWorldV1.step
    def checked(world, command=None):
        with pytest.raises(RuntimeError): trial.advance_lower()
        with pytest.raises(RuntimeError): trial.focal_step()
        with pytest.raises(RuntimeError): trial.reset()
        return original(world, command)
    monkeypatch.setattr(MotorWorldV1, "step", checked)
    trial.advance_lower()
    assert trial.tick == 1


def test_new_core_call_cannot_skip_unconsumed_handoff():
    core, _, _ = core_bundle()
    with pytest.raises(RuntimeError):
        core.run_cycle(reading(4), cutoff_tick=4)
    assert core.scheduler.last_completed_cycle == 1


def test_detached_exports_and_diagnostics_do_not_mutate_control_or_rng():
    before = random.getstate()
    trial = IntegratedRightingTrialV1()
    trial.step()
    baseline = trial.snapshot()
    for _ in range(3):
        exported = trial.snapshot()
        exported["controller"]["reports"].clear()
        json.dumps(trial.history()[0].as_dict(), allow_nan=False)
        trial.core.trace.render_lines()
    assert trial.snapshot() == baseline
    assert random.getstate() == before


@pytest.mark.parametrize("capacity", [1, 8, 256, 4096])
def test_diagnostic_capacity_changes_retention_not_dynamics(capacity):
    trial = IntegratedRightingTrialV1(trace_capacity=capacity)
    signature = trial.core.cognition.maps.durable_record_signature()
    for _ in range(20): trial.step()
    trial.focal_step()
    baseline = IntegratedRightingTrialV1()
    for _ in range(20): baseline.step()
    baseline.focal_step()
    assert trial.latest_feedback == baseline.latest_feedback
    assert trial.controller.installation_count == baseline.controller.installation_count
    snap = trial.snapshot()
    assert snap["durable_map_count"] == 1 and snap["wnm_count"] <= 1 and snap["current_task_pnm_count"] <= 1
    assert len(trial.history()) <= 8 and trial.core.trace.retained_count <= capacity
    assert len(trial.core.cognition.righting.history()) <= 8
    assert len(trial.core.cognition.prediction.preview_history()) <= 8
    assert snap["controller"]["command_history_count"] <= 4 and len(trial.controller.events) <= 4
    assert trial.core.cognition.maps.durable_record_signature() == signature
    assert snap["durable_learning_updates"] == 0


@pytest.mark.parametrize("invalid", [True, -1, 2**63, 0.5, "0"])
def test_bad_cutoffs_fail_before_source_or_physics(invalid):
    core = IntegratedRightingCoreV1(STREAM)
    with pytest.raises(ValueError): core.run_cycle(reading(), cutoff_tick=invalid)
    assert core.scheduler.last_completed_cycle == 0


@pytest.mark.parametrize("change", [dict(event_tick=1, available_tick=1), dict(available_tick=1),
                                    dict(stream=MotorStreamRefV1("foreign", 1)), dict(stream=MotorStreamRefV1("h6_unit_body", 2))])
def test_future_or_foreign_focal_feedback_cannot_authorize_targets(change):
    core = IntegratedRightingCoreV1(STREAM)
    with pytest.raises(ValueError): core.run_cycle(replace(reading(), **change), cutoff_tick=0)
    assert core.last_commitment is None


@pytest.mark.parametrize("batch", [None, [], (None,), tuple(reading() for _ in range(17))])
def test_shared_motor_admission_rejects_malformed_batches(batch):
    with pytest.raises(TypeError): admit_motor_feedback_batch_v1(batch, reading(), stream=STREAM, at_tick=0)


def test_shared_admission_preserves_duplicate_age_and_rejects_changed_identity():
    current = reading(2)
    assert admit_motor_feedback_batch_v1((), current, stream=STREAM, at_tick=4) == current
    assert admit_motor_feedback_batch_v1((reading(), current), current, stream=STREAM, at_tick=4) == current
    with pytest.raises(ValueError):
        admit_motor_feedback_batch_v1((replace(current, useful_loading=0.9),), current, stream=STREAM, at_tick=4)


def test_proposed_replacement_cannot_cancel_old_target_until_reserved():
    trial = IntegratedRightingTrialV1()
    focal = trial.focal_step()
    mapper = trial.core.cognition.mapper
    old = mapper.reservations(at_tick=0)
    request = focal.calculation.navigation.application.contribution
    proposal = mapper.propose(request, at_tick=0, replace_existing=True)
    assert mapper.reservations(at_tick=0) == old
    assert proposal.replaces == old
    with pytest.raises(ValueError): mapper.reserve(replace(proposal), execution_id="copy", at_tick=0)
    assert mapper.reservations(at_tick=0) == old


def test_refused_replacement_keeps_old_permission_until_normal_safety_or_expiry():
    trial = IntegratedRightingTrialV1()
    focal = trial.focal_step()
    mapper = trial.core.cognition.mapper
    mapper.update_feedback(None, at_tick=0)
    proposal = mapper.propose(focal.calculation.navigation.application.contribution, at_tick=0, replace_existing=True)
    assert not proposal.bindings
    with pytest.raises(ValueError): mapper.reserve(proposal, execution_id="refused", at_tick=0)
    assert mapper.reservations(at_tick=0) == focal.reservations


def test_final_authorization_cannot_outlive_original_physical_task_budget():
    trial = IntegratedRightingTrialV1(
        MotorWorldProfileV1(extension_motor_enabled=False),
        control_profile=SensorimotorProfileV1(prediction_protection=False),
    )
    first = trial.focal_step()
    for _ in range(79):
        trial.advance_lower()
    last = trial.focal_step()
    assert first.calculation.task.task_id == last.calculation.task.task_id
    assert last.calculation.navigation.application.contribution.lease_ticks == 1
    assert last.reservations
    assert all(item.current.expires_at_tick == 80 for item in last.reservations)
    assert last.calculation.proposal.request.lease_ticks == 1
    trial.advance_lower()
    expired = trial.advance_lower()
    assert expired.tick == 80 and expired.command is None
    assert all(item.disposition is LocalTargetDispositionV1.EXPIRED for item in expired.reports)
    assert trial.tick == 81  # No further focal call was needed to enforce the deadline.


def test_focal_budget_exhaustion_explicitly_cancels_still_live_targets():
    trial = IntegratedRightingTrialV1(
        MotorWorldProfileV1(extension_motor_enabled=False),
        control_profile=SensorimotorProfileV1(prediction_protection=False),
    )
    for _ in range(20):
        trial.focal_step()
        trial.advance_lower()
    final = trial.focal_step()
    assert final.status == "budget_exhausted"
    assert final.receipt.dispatch.motor.directive == "cancel"
    assert trial.tick == 20
    assert trial.advance_lower().command is None


def test_cancellation_remains_cancellation_after_both_budgets_pass():
    trial = IntegratedRightingTrialV1()
    trial.focal_step()
    trial.cancel()
    for _ in range(81):
        trial.advance_lower()
    assert trial.focal_step().calculation.task.status == "cancelled"


@pytest.mark.parametrize("method", ["select_prepared", "project_selected"])
def test_stage_api_rejects_none_before_any_source_preparation(method):
    core = IntegratedRightingCoreV1(STREAM)
    with pytest.raises(ValueError):
        getattr(core.cognition, method)(None)
    assert core.cognition.last_result is None


@pytest.mark.parametrize("changes", [
    {"stream": MotorStreamRefV1("other", 1)}, {"cutoff_tick": 1}, {"cutoff_tick": True},
    {"projection": None}, {"projection": "not_pnm"}, {"cancel_previous": 1}, {"targets": []},
])
def test_motor_envelope_rejects_foreign_time_or_malformed_authority(changes):
    _, _, result = core_bundle()
    with pytest.raises((ValueError, TypeError)):
        replace(result.receipt.dispatch.motor, **changes)


def test_motor_envelope_rejects_duplicate_targets_and_detached_replacement_only():
    _, _, result = core_bundle()
    motor = result.receipt.dispatch.motor
    with pytest.raises(ValueError):
        replace(motor, targets=(motor.targets[0], motor.targets[0]))
    with pytest.raises(ValueError):
        replace(motor, targets=(), replaces=motor.targets)


@pytest.mark.parametrize("field,value", [("task_action", "stand_up"), ("task_action_id", "other"),
                                         ("action_envelope_id", "other"), ("focal_operation_id", "other")])
def test_handoff_rejects_rich_target_misaligned_with_historical_commitment(field, value):
    _, _, result = core_bundle()
    invalid = replace(result.receipt.dispatch, commitment=replace(result.commitment, **{field: value}))
    with pytest.raises(ValueError):
        Nca8InternalHandoffV1(generation=1).accept(invalid)


def test_handoff_cannot_mix_enhanced_targets_with_old_a0_task():
    from nca8_primitives import TaskActionKindV1, TaskActionV1
    _, _, result = core_bundle()
    invalid = replace(result.receipt.dispatch, task_action=TaskActionV1("fixture", 1, TaskActionKindV1.NO_ACTION, "mixed", ()))
    with pytest.raises(ValueError):
        Nca8InternalHandoffV1(generation=1).accept(invalid)
