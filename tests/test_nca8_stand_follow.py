"""Continuous Righting/Follow-Mom: source readiness, single focus and lower authority."""

from __future__ import annotations

import ast
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_contracts import CyclePhase
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_followmom import FollowMomIPV1, FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingCoreV1, IntegratedRightingTrialV1
from nca8_maternal import MaternalCandidateV1, MaternalSeedV1, MaternalSourceV1
from nca8_outcomes import RightingIntervalEvidenceV1
from nca8_righting import RightingActivityV1, RightingContextV1, RightingIPV1, righting_support_adequacy_v1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_sensorimotor import SensorimotorExecutorV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, LocalTargetDispositionV1, SensorimotorTargetKindV1
from nca8_stand_follow_demo import create_stand_follow_trial_v1, run_stand_follow_v1, STAND_FOLLOW_CASES_V1
from nca8_translation import TranslationFixtureV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1

ROOT = Path(__file__).resolve().parents[1]
STREAM = MotorStreamRefV1("stand_follow_unit", 1)


@pytest.fixture(scope="module")
def runs():
    return {case: run_stand_follow_v1(case) for case in STAND_FOLLOW_CASES_V1}


def at(result, tick):
    return result.cycles[tick // 4]


def advance_to(trial, tick):
    """Fixed-time harness only; never branch on a task or source result."""
    while trial.tick < tick:
        if trial.tick % 4 == 0:
            trial.focal_step()
        trial.advance_lower()


def maternal_opportunity():
    visual, maternal = VisualSourceV1(STREAM), MaternalSourceV1(STREAM, MaternalSeedV1())
    operation = FollowMomIPV1(maternal, FollowMomProfileV1())
    observation = VisualObservationV1(STREAM, 1, 0, 0, "scene_xy:lab", NavPointV1(0, 0),
                                      (VisualDetectionV1("region_1", "object", NavPointV1(2, 1)),))
    source = maternal.update(visual.update(observation, cycle_id=1, cutoff_tick=0))
    body = MotorFeedbackV1(STREAM, 1, 0, 0, 0, 1, True, 1, 0)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    wnm = navigation.update_wnm(attention.select((attention.build_bid(maternal.candidate(), cycle_id=1),),
                                                current_wnm=None, cycle_id=1))
    return operation, source, body, wnm


def test_nominal_is_one_continuous_body_clock_and_two_evidence_backed_tasks(runs):
    result = runs["nominal"]
    assert result.metrics()["stood_and_reached"]
    assert result.metrics()["righting_supported_at_tick"] == 36
    assert result.metrics()["maternal_proximity_completed_at_tick"] == 104
    assert result.metrics()["support_to_follow_authority_transition"]
    assert len({c.calculation.task.task_id for c in result.cycles}) == 1
    maternal = [c.maternal_task.task for c in result.cycles if c.maternal_task.task is not None]
    assert len({task.task_id for task in maternal}) == 1
    assert maternal[0].started_tick == 40 and maternal[-1].applications == 7
    assert len({c.calculation.source.motor_support.stream for c in result.cycles}) == 1
    assert result.physical_samples[0].support == MotorBodyStateV1(30, 0.4)
    assert result.physical_samples[40].planar.position == (0, 0)
    assert result.physical_samples[-1].planar.position == pytest.approx((1.5652475842498528, 0.7826237921249264))


def test_actual_supported_dwell_not_one_adequate_frame_releases_recovery(runs):
    result = runs["nominal"]
    for tick, count in ((28, 1), (32, 2)):
        cycle = at(result, tick)
        assert cycle.task_outcome.status == "adequate_pending_dwell"
        assert len(cycle.task_outcome.supported_samples) == count
        assert cycle.calculation.task.status == "active"
        assert cycle.maternal_task.support_recovery_pending
        assert cycle.maternal_task.task is None and not cycle.reservations
        assert cycle.commitment.pnm_id is None and cycle.commitment.selected_primitive_id is None
        assert cycle.calculation.navigation.wnm.primary_source_state is cycle.calculation.source
        assert cycle.receipt.dispatch.motor.directive == "no_new_task_output"
    complete = at(result, 36)
    samples = complete.calculation.task.completion_samples
    assert [item.event_tick for item in samples] == [27, 31, 35]
    assert len({item.sample_id for item in samples}) == 3
    assert all(righting_support_adequacy_v1(item, complete.calculation.task.context) for item in samples)
    assert samples[-1].event_tick - samples[0].event_tick == 8


def test_terminal_handoff_disposes_old_rights_before_next_follow_application(runs):
    result = runs["nominal"]
    complete, first, continuing = (at(result, tick) for tick in (36, 40, 44))
    assert complete.receipt.dispatch.motor.directive == "cancel"
    assert complete.maternal_task.support_recovery_pending and complete.maternal_task.task is None
    assert complete.commitment.selected_primitive_id is None and not complete.reservations
    assert first.calculation.task.status == "completed" and not first.maternal_task.support_recovery_pending
    assert first.commitment.selected_primitive_id == "ip:follow_mom"
    assert first.receipt.dispatch.motor.directive == "install"
    target = first.reservations[0].current
    assert isinstance(target.target, BodyTranslationTargetV1)
    assert target.expires_at_tick == 48
    assert continuing.receipt.dispatch.motor.directive == "no_new_task_output"
    assert not continuing.receipt.dispatch.motor.cancel_previous and not continuing.reservations
    assert continuing.commitment.selected_primitive_id is None and continuing.commitment.pnm_id is None
    assert any(step.command is not None and step.command.translation is not None for step in result.local_steps[44:48])
    assert all(step.command is None for step in result.local_steps[36:40])


def test_maternal_source_updates_while_support_is_the_single_wnm(runs):
    result = runs["nominal"]
    for cycle in result.cycles[:9]:
        source, maternal = cycle.calculation.source, cycle.maternal_source
        assert maternal.identity_status == "supported" and maternal.action_localized
        assert maternal.source_map_ref.map_id == "maternal_target"
        assert maternal.visual is cycle.visual_source
        assert cycle.calculation.navigation.wnm.primary_source_state is source
        assert source.source_map_ref.map_id == "posture_support"
        assert maternal.cutoff_tick == cycle.calculation.cutoff_tick
        assert cycle.maternal_task.task is None
    assert at(result, 40).calculation.navigation.wnm.primary_source_state is at(result, 40).maternal_source


def test_attention_can_choose_mom_during_dwell_without_granting_follow_authority(monkeypatch):
    trial = create_stand_follow_trial_v1()
    advance_to(trial, 28)
    monkeypatch.setattr(MaternalCandidateV1, "new_task_need_rank", 100)
    cycle = trial.focal_step()
    assert cycle.calculation.navigation.wnm.primary_source_state is cycle.maternal_source
    assert cycle.calculation.task.status == "active" and cycle.task_outcome.status == "adequate_pending_dwell"
    assert cycle.maternal_task.reason == "support_recovery_pending"
    assert cycle.commitment.selected_primitive_id is None and not cycle.reservations


@pytest.mark.parametrize("pending", [False, True])
def test_recovery_constraint_changes_applicability_without_rewriting_maternal_evidence(pending):
    operation, source, body, wnm = maternal_opportunity()
    before = source.as_dict()
    operation.prepare(source, body, support_recovery_pending=pending)
    assert operation.evaluate_applicability(wnm, cycle_id=1).eligible is not pending
    assert operation.assessment().support_recovery_pending is pending
    assert operation.task is None and source.as_dict() == before
    assert ("support_recovery_pending" in operation.assessment().as_dict()) is pending


@pytest.mark.parametrize("bad", [None, 0, 1, "false", [], 1.0])
def test_recovery_constraint_rejects_nonboolean_before_any_owner_mutation(bad):
    operation, source, body, _ = maternal_opportunity()
    before = operation.snapshot()
    with pytest.raises(TypeError):
        operation.prepare(source, body, support_recovery_pending=bad)
    assert operation.snapshot() == before
    operation.prepare(source, body)  # The invalid call did not consume this opportunity.


@pytest.mark.parametrize("change", [
    {"support_contact": False}, {"support_contact": None}, {"body_tilt_degrees": 12.1},
    {"body_tilt_degrees": None}, {"useful_loading": 0.74}, {"destabilization": 0.16},
])
def test_completed_recovery_does_not_replace_current_body_requirements(change):
    operation, source, body, wnm = maternal_opportunity()
    operation.prepare(source, replace(body, **change), support_recovery_pending=False)
    assert not operation.evaluate_applicability(wnm, cycle_id=1).eligible
    assert operation.reason == "body_support_unavailable" and operation.task is None


def test_already_supported_start_can_follow_without_a_righting_stage(runs):
    result = runs["already_supported"]
    assert all(cycle.calculation.task is None for cycle in result.cycles)
    assert result.cycles[0].commitment.selected_primitive_id == "ip:follow_mom"
    assert result.metrics()["first_translation_install_at_tick"] == 0
    assert result.metrics()["maternal_proximity_completed_at_tick"] == 64
    assert not result.metrics()["support_to_follow_authority_transition"]
    assert not result.metrics()["stood_and_reached"]


def test_boundary_aim_control_neither_relaxes_criterion_nor_unlocks_following(runs):
    old, new = runs["boundary_aim"], runs["nominal"]
    assert old.profile.target_inset_degrees == 0 and new.profile.target_inset_degrees == 2
    assert old.cycles[-1].calculation.task.status == "budget_exhausted"
    assert old.cycles[-1].maternal_task.task is None
    assert old.cycles[-1].maternal_task.support_recovery_pending
    assert all(sample.planar.position == (0, 0) for sample in old.physical_samples)
    assert old.cycles[-1].calculation.task.context == new.cycles[-1].calculation.task.context
    assert old.cycles[-1].calculation.task.context.criterion == (12, 0.75, 0.15)
    assert old.final_feedback.body_tilt_degrees > 12
    for result in (old, new):
        targets = [r.current.target for c in result.cycles for r in c.reservations
                   if r.current.target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST]
        assert all(target.tolerance == 1 for target in targets)


@pytest.mark.parametrize("inset", [0, 1.0, 2, 3.0])
@pytest.mark.parametrize("sign", [-1, 1])
def test_inset_changes_only_target_aim_inside_same_signed_support_criterion(inset, sign):
    owner = Nca8RightingPreviewSessionV1(STREAM, righting_target_inset_degrees=inset)
    body = MotorFeedbackV1(STREAM, 1, 0, 0, sign * 13, 0.9, True, 0.9, 0.05)
    result = owner.preview(body, cutoff_tick=0)
    application = result.navigation.application
    assert application.contribution.desired_tilt_degrees == pytest.approx(sign * (12 - inset))
    assert application.task.context.criterion == (12, 0.75, 0.15)
    assert abs(application.contribution.desired_tilt_degrees - body.body_tilt_degrees) <= 4.5
    assert result.source.motor_support.feedback is body
    assert owner.righting.target_inset_degrees == inset


@pytest.mark.parametrize("bad", [True, False, None, "2", [], float("nan"), float("inf"), -0.1, 3.01, 10**500])
def test_inset_is_validated_as_small_finite_fixed_calibration(bad):
    with pytest.raises(ValueError):
        RightingIPV1(target_inset_degrees=bad)


@pytest.mark.parametrize("activity,tilt", [(RightingActivityV1.REST, 70), (RightingActivityV1.CROUCH, 35)])
def test_target_inset_does_not_make_safe_rest_or_crouch_inapplicable(activity, tilt):
    context = RightingContextV1("context:fixture", activity)
    body = MotorFeedbackV1(STREAM, 1, 0, 0, tilt, 0.8, True, 0.8, 0.05)
    for inset in (0, 2):
        owner = Nca8RightingPreviewSessionV1(STREAM, context=context, righting_target_inset_degrees=inset)
        result = owner.preview(body, cutoff_tick=0)
        assert result.navigation.application is None and result.task is None
        assert righting_support_adequacy_v1(body, context)


def test_zero_inset_is_the_exact_existing_default_preview():
    body = MotorFeedbackV1(STREAM, 1, 0, 0, 13, 0.9, True, 0.9, 0.05)
    default, explicit = Nca8RightingPreviewSessionV1(STREAM), Nca8RightingPreviewSessionV1(STREAM, righting_target_inset_degrees=0)
    assert default.preview(body, cutoff_tick=0).as_dict() == explicit.preview(body, cutoff_tick=0).as_dict()


@pytest.mark.parametrize("kwargs", [
    {"stand_follow_enabled": 1},
    {"stand_follow_enabled": True},
    {"stand_follow_enabled": True, "task_outcomes_enabled": True},
    {"stand_follow_enabled": True, "follow_mom_profile": FollowMomProfileV1(outcomes_enabled=True)},
    {"stand_follow_enabled": True, "task_outcomes_enabled": True, "follow_mom_profile": FollowMomProfileV1()},
    {"stand_follow_enabled": True, "task_outcomes_enabled": True, "translation_fixture": TranslationFixtureV1()},
    {"task_outcomes_enabled": True, "follow_mom_profile": FollowMomProfileV1(outcomes_enabled=True)},
])
def test_domain_integration_is_explicit_and_requires_both_correspondence_consumers(kwargs):
    with pytest.raises((ValueError, TypeError)):
        IntegratedRightingCoreV1(STREAM, **kwargs)


def test_existing_default_does_not_silently_enable_monitoring_or_new_consumers():
    trial = IntegratedRightingTrialV1()
    assert not trial.core.stand_follow_enabled
    assert not trial.core.cognition.monitor_support_completion
    assert trial.core.cognition.righting.target_inset_degrees == 0
    assert trial.core.outcomes is None and trial.core.maternal_outcomes is None
    assert trial.snapshot()["profile"] == "integrated_righting_v1"


def test_original_domain_claims_have_disjoint_task_and_command_attribution(runs):
    result = runs["nominal"]
    support_claims = [c.claim_registration for c in result.cycles if c.claim_registration is not None]
    maternal_claims = [c.maternal_correspondence.registration for c in result.cycles
                       if c.maternal_correspondence.registration is not None]
    assert len(support_claims) == len(maternal_claims) == 7
    assert all(claim.preview.task_id.startswith("righting:") for claim in support_claims)
    assert all(claim.preview.task_id.startswith("follow_mom:") for claim in maternal_claims)
    assert all(not isinstance(target.target, BodyTranslationTargetV1) for claim in support_claims for target in claim.targets)
    maternal_outcomes = [o for c in result.cycles for o in c.maternal_correspondence.outcomes]
    assert len(maternal_outcomes) == 7
    assert all(o.command_intervals == 5 and o.status == "matched" for o in maternal_outcomes)
    assert all(not c.claim_outcomes for c in result.cycles if c.calculation.cutoff_tick >= 40)
    assert all(c.learning_report is None for c in result.cycles)


def test_outer_routing_retains_original_command_and_sensor_objects_but_separates_reports():
    trial = create_stand_follow_trial_v1()
    advance_to(trial, 40)
    first = trial.focal_step()
    step = trial.advance_lower()
    support, maternal = trial._outcome_intervals[-1], trial._maternal_intervals[-1]
    assert support.command is maternal.command is step.command
    assert support.command.translation is not None
    assert support.reports == () and maternal.reports == step.reports
    assert len(maternal.reports) == 1 and maternal.reports[0].committed_target is first.reservations[0].current
    assert support.deliveries == maternal.deliveries
    assert all(left is right for left, right in zip(support.deliveries, maternal.deliveries))
    assert trial.core.outcomes.pending() == ()


def test_wrong_domain_reports_are_still_rejected_by_righting_not_reinterpreted():
    trial = create_stand_follow_trial_v1()
    advance_to(trial, 40)
    trial.focal_step()
    step = trial.advance_lower()
    staged = trial._outcome_intervals[-1]
    wrong = RightingIntervalEvidenceV1(staged.tick, staged.command, step.reports, staged.deliveries)
    with pytest.raises(ValueError):
        trial.core.outcomes.consume_intervals((wrong,), cutoff_tick=41)


def test_reset_preserves_profile_but_destroys_old_permissions_tasks_and_claims():
    trial = create_stand_follow_trial_v1()
    advance_to(trial, 40)
    cycle = trial.focal_step()
    old_righting, old_maternal = trial.core.outcomes, trial.core.maternal_outcomes
    trial.advance_lower()
    trial.reset()
    assert trial.tick == 0 and trial.handoff_consumptions == 0 and trial.controller.installation_count == 0
    assert trial.core.outcomes is not old_righting and trial.core.maternal_outcomes is not old_maternal
    assert trial.core.cognition.righting.task is None and trial.core.follow_mom.task is None
    assert trial.core.stand_follow_enabled and trial.core.cognition.monitor_support_completion
    assert trial.core.cognition.righting.target_inset_degrees == 2
    assert not trial.core.outcomes.pending() and not trial.core.maternal_outcomes.pending()
    fresh = trial.focal_step()
    assert fresh.commitment.selected_primitive_id == "ip:righting"
    assert fresh.reservations[0].current.target.origin.stream.generation == 2
    assert cycle.reservations[0].current.target.origin.stream.generation == 1
    with pytest.raises((RuntimeError, ValueError)):
        trial.core.handoff.consume_motor(cycle.receipt)


def test_new_profile_preserves_no_physical_call_inside_the_focal_core(monkeypatch):
    trial = create_stand_follow_trial_v1()
    feedback = trial.latest_feedback
    visual = admit_motor_visual_surface_v1(trial._world.visual_surface(), feedback)
    def forbidden(*args, **kwargs):
        raise AssertionError("core attempted a lower/world step")
    monkeypatch.setattr(MotorWorldV1, "step", forbidden)
    monkeypatch.setattr(SensorimotorExecutorV1, "step", forbidden)
    cycle = trial.core.run_cycle(feedback, cutoff_tick=0, visual_observation=visual)
    assert cycle.scheduler.phases == tuple(CyclePhase)
    assert cycle.receipt.disposition == "ready"
    assert trial.tick == trial.controller.installation_count == trial.handoff_consumptions == 0
    channels = [event.channel for event in trial.core.trace.snapshot()]
    assert channels.index("hierarchy_commit") < channels.index("hierarchy_handoff") < channels.index("hierarchy_close")


def test_core_has_no_stage_or_private_physics_access_and_new_driver_never_reads_results_to_choose_tasks():
    tree = ast.parse((ROOT / "nca8_hierarchy.py").read_text())
    core = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "IntegratedRightingCoreV1")
    forbidden = {"_world", "observer_body", "observer_planar_body", "milestones", "stage", "scenario_stage", "stood_up", "reached_mom"}
    assert not any(isinstance(node, ast.Attribute) and node.attr in forbidden for node in ast.walk(core))
    demo_tree = ast.parse((ROOT / "nca8_stand_follow_demo.py").read_text())
    run = next(node for node in demo_tree.body if isinstance(node, ast.FunctionDef) and node.name == "run_stand_follow_v1")
    for node in ast.walk(run):
        if isinstance(node, ast.If):
            assert not any(isinstance(item, ast.Attribute) and item.attr in {"status", "task", "metrics", "completed"}
                           for item in ast.walk(node.test))
    assert not any(isinstance(node, ast.Attribute) and node.attr in {"reset", "apply", "commit", "install_authorized"}
                   for node in ast.walk(run))


def test_completed_task_records_remain_immutable_during_later_following(runs):
    result = runs["nominal"]
    task = at(result, 36).calculation.task
    assert all(replace(c.calculation.task, last_cycle=task.last_cycle) == task for c in result.cycles[9:])
    assert task.last_cycle == 10
    assert task.completion_samples[-1].event_tick == 35
    with pytest.raises(FrozenInstanceError):
        task.status = "active"


def test_current_prediction_is_not_created_for_passive_monitoring(runs):
    result = runs["nominal"]
    for cycle in result.cycles:
        if cycle.commitment.selected_primitive_id is None:
            assert cycle.commitment.pnm_id is None
            assert cycle.receipt.dispatch.motor.projection is None
    assert len({c.commitment.pnm_id for c in result.cycles if c.commitment.pnm_id is not None}) == 14


def test_missing_new_support_acquisitions_cannot_fill_dwell_or_unlock_maternal_movement():
    from cca8_support_world import MotorWorldPerturbationV1
    from nca8_stand_follow_demo import stand_follow_profile_v1
    profile = stand_follow_profile_v1()
    physical = replace(profile.physical, perturbations=(MotorWorldPerturbationV1(27, 161, drop_feedback=True),))
    trial = IntegratedRightingTrialV1(physical, stream_id="stand_follow_reference_body", planar_profile=profile.planar,
                                     follow_mom_profile=profile.maternal, translation_capability=profile.translation,
                                     righting_target_inset_degrees=2, task_outcomes_enabled=True, stand_follow_enabled=True)
    observed = []
    for tick in range(100):
        if tick % 4 == 0:
            observed.append(trial.focal_step())
        trial.advance_lower()
    assert observed[7].task_outcome.status == "adequate_pending_dwell"
    assert len(observed[7].task_outcome.supported_samples) == 1
    assert all(c.calculation.task.status != "completed" for c in observed)
    assert all(c.maternal_task.task is None for c in observed)
    assert observed[-1].calculation.task.status == "budget_exhausted"
    assert trial.observer_planar_body.position == (0, 0)
    assert trial.latest_feedback.event_tick == 27
