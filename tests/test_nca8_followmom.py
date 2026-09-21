"""Persistent Follow-Mom, selection authority and finite evidence-dependent execution."""

from dataclasses import replace

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_followmom import FollowMomIPV1, FollowMomProfileV1, FollowMomTaskV1
from nca8_followmom_demo import create_follow_mom_trial_v1, run_follow_mom_v1, run_maternal_source_replay_v1
from nca8_primitives import PrimitiveKindV1
from nca8_maternal import MaternalCandidateV1, MaternalSeedV1, MaternalSourceV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1


def prepared():
    stream = MotorStreamRefV1("follow_unit", 1)
    visual, maternal = VisualSourceV1(stream), MaternalSourceV1(stream, MaternalSeedV1())
    profile = FollowMomProfileV1()
    operation = FollowMomIPV1(maternal, profile)
    observation = VisualObservationV1(stream, 1, 0, 0, "scene_xy:lab", NavPointV1(0, 0),
                                      (VisualDetectionV1("region_1", "object", NavPointV1(2, 1)),))
    basis = maternal.update(visual.update(observation, cycle_id=1, cutoff_tick=0))
    feedback = MotorFeedbackV1(stream, 1, 0, 0, 0.0, 1.0, True, 1.0, 0.0)
    operation.prepare(basis, feedback)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    wnm = navigation.update_wnm(attention.select((attention.build_bid(maternal.candidate(), cycle_id=1),),
                                                current_wnm=None, cycle_id=1))
    return operation, basis, feedback, wnm


def test_applicability_is_readonly_and_selection_creates_one_target_specific_pnm():
    operation, basis, _, wnm = prepared()
    before = basis.as_dict()
    applicability = operation.evaluate_applicability(wnm, cycle_id=1)
    assert applicability.eligible and operation.task is None and not operation.history()
    application = operation.apply(wnm, applicability, cycle_id=1)
    assert application.primitive_id == "ip:follow_mom" and application.primitive_kind is PrimitiveKindV1.INSTINCTIVE
    assert application.projection.basis is basis and application.projection.scene_target == basis.target_position
    assert application.projection.predicted_separation == pytest.approx(basis.separation - 0.25)
    assert application.contribution.origin_status == "selected_follow_mom"
    assert basis.as_dict() == before and len(operation.history()) == 1
    with pytest.raises(ValueError):
        operation.apply(wnm, applicability, cycle_id=1)


def test_foreign_or_copied_focal_source_cannot_borrow_current_operation():
    operation, basis, _, wnm = prepared()
    copied = replace(wnm, primary_source_state=replace(basis))
    assert not operation.evaluate_applicability(copied, cycle_id=1).eligible
    assert operation.task is None


def test_prepare_cannot_be_repeated_or_accept_a_copy_of_the_owner_sample():
    operation, basis, feedback, _ = prepared()
    before = operation.snapshot()
    for source in (basis, replace(basis)):
        with pytest.raises(ValueError):
            operation.prepare(source, feedback)
    assert operation.snapshot() == before


@pytest.mark.parametrize("name", ["association_enabled", "recognition_enabled", "spatial_enabled", "following_enabled", "influence_enabled"])
@pytest.mark.parametrize("bad", [None, 0, 1, "true"])
def test_profile_controls_are_explicit_boolean_not_truthiness(name, bad):
    with pytest.raises(TypeError):
        replace(FollowMomProfileV1(), **{name: bad})


@pytest.mark.parametrize("change", [
    {"started_cycle": 0}, {"started_cycle": True}, {"started_tick": -1}, {"started_tick": 2**63 - 1},
    {"applications": 21}, {"applications": True}, {"status": "magic_success"}, {"region_id": "bad handle"},
])
def test_task_record_bounds_are_explicit(change):
    with pytest.raises((TypeError, ValueError)):
        replace(FollowMomTaskV1("task:1", "region_1", 1, 0), **change)


def test_nominal_uses_one_task_many_finite_targets_and_later_proximity_evidence():
    result = run_follow_mom_v1()
    tasks = [cycle.maternal_task.task for cycle in result.cycles if cycle.maternal_task.task is not None]
    assert len({task.task_id for task in tasks}) == 1 and tasks[-1].applications == 7 and tasks[-1].status == "completed"
    completed = next(cycle for cycle in result.cycles if cycle.maternal_task.task.status == "completed")
    assert completed.calculation.cutoff_tick == 64
    assert [sample.event_tick for sample in completed.maternal_task.supported_samples] == [55, 59, 63]
    assert all(sample.separation <= 0.5 for sample in completed.maternal_task.supported_samples)
    assert all(step.command is None or step.command.translation is None for step in result.local_steps[64:])
    assert all(cycle.commitment.task_action in {None, "FOLLOW_MOM"} for cycle in result.cycles)
    assert any(cycle.maternal_source.separation_rate < 0 and cycle.commitment.selected_primitive_id == "ip:follow_mom"
               for cycle in result.cycles if cycle.maternal_source.separation_rate is not None)


def test_handoff_closes_before_install_and_lower_work_does_not_reconsume_it():
    trial = create_follow_mom_trial_v1("nominal")
    first = trial.focal_step()
    assert trial.tick == 0 and trial.controller.installation_count == trial.handoff_consumptions == 1
    assert first.scheduler.cycle_id == 1 and first.reservations[0].current.expires_at_tick == 8
    for _ in range(4):
        trial.advance_lower()
    second = trial.focal_step()
    assert second.commitment.selected_primitive_id is None and second.commitment.pnm_id is None
    assert trial.controller.installation_count == 1 and trial.handoff_consumptions == 2


def test_no_duplicate_authorization_or_copied_target_report_can_restore_rights():
    trial = create_follow_mom_trial_v1("nominal")
    first = trial.focal_step()
    operation = trial.core.follow_mom
    app = operation.history()[-1]
    with pytest.raises(ValueError):
        operation.authorized(app, (first.reservations[0].current,))
    assert trial.handoff_consumptions == 1


def test_cancel_before_first_selection_prevents_a_task_from_starting():
    trial = create_follow_mom_trial_v1("nominal")
    trial.cancel()
    first = trial.focal_step()
    assert first.commitment.selected_primitive_id is None and first.maternal_task.task is None
    assert first.maternal_task.reason == "cancelled"


def test_reset_destroys_old_task_permissions_but_rebuilds_the_declared_seed():
    trial = create_follow_mom_trial_v1("nominal")
    old = trial.focal_step()
    owner = trial.core.follow_mom
    seed = trial.core.maternal.durable_map.as_dict()
    trial.advance_lower()
    trial.reset()
    assert trial.core.follow_mom is not owner and trial.core.follow_mom.task is None
    assert trial.core.maternal.durable_map.as_dict() == seed
    fresh = trial.focal_step()
    assert fresh.reservations[0].current.target.origin.stream.generation == 2
    assert old.reservations[0].current.target.origin.stream.generation == 1


def test_missing_sensing_withdraws_exact_pursuit_but_reacquisition_keeps_task_identity():
    result = run_follow_mom_v1("brief_gap")
    gap = next(cycle for cycle in result.cycles if cycle.calculation.cutoff_tick == 12)
    assert gap.maternal_source.identity_status == "retained"
    assert gap.maternal_source.uncertainty_radius is not None and gap.maternal_source.target_position is None
    assert gap.receipt.dispatch.motor.cancel_previous and not gap.reservations and gap.commitment.pnm_id is None
    assert result.cycles[-1].maternal_task.task.status == "completed"
    assert len({cycle.maternal_task.task.task_id for cycle in result.cycles}) == 1


def test_prolonged_gap_ends_original_task_without_auto_restarting_on_reacquisition():
    result = run_follow_mom_v1("prolonged_gap")
    ended = next(cycle for cycle in result.cycles if cycle.maternal_task.task.status == "target_unavailable")
    assert ended.calculation.cutoff_tick == 16
    assert result.cycles[-1].maternal_source.action_localized
    assert result.cycles[-1].maternal_task.task.status == "target_unavailable"
    assert all(not cycle.reservations for cycle in result.cycles if cycle.calculation.cutoff_tick >= 16)


def test_support_interruption_selects_support_and_prevents_incompatible_translation():
    result = run_follow_mom_v1("support_interruption")
    for cycle in result.cycles:
        if cycle.calculation.cutoff_tick in (12, 16):
            assert cycle.maternal_source.identity_status == "supported"
            assert cycle.commitment.selected_primitive_id != "ip:follow_mom"
            assert cycle.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == "posture_support"
    assert all(step.command is None or step.command.translation is None for step in result.local_steps[12:17])
    assert result.cycles[-1].maternal_task.task.status == "completed"


def test_kinematic_independent_approach_does_not_stop_self_closing_following():
    independent = run_maternal_source_replay_v1("independent_approach")
    own = run_maternal_source_replay_v1("own_closing")
    assert independent.dispositions[-1] == "independently_approaching_target_wait"
    assert own.dispositions[-1] == "initiate_following"
    assert own.sources[-1].separation == pytest.approx(independent.sources[-1].separation)
    relocated = run_maternal_source_replay_v1("relocated_target")
    assert relocated.dispositions[-1] == "initiate_following"


def test_contradiction_ends_a_live_task_without_an_invented_precise_target():
    operation, basis, feedback, wnm = prepared()
    operation.apply(wnm, operation.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    visual = VisualSourceV1(basis.stream)
    bad = VisualObservationV1(basis.stream, 5, 4, 4, "scene_xy:lab", NavPointV1(0, 0),
                              (VisualDetectionV1("region_1", "hazard", NavPointV1(2, 1)),))
    source = operation.source.update(visual.update(bad, cycle_id=2, cutoff_tick=4))
    operation.prepare(source, replace(feedback, sample_id=5, event_tick=4, available_tick=4))
    assert operation.task.status == "identity_contradicted" and source.target_position is None


def test_completed_local_target_is_not_sufficient_for_maternal_completion():
    result = run_follow_mom_v1("mapping_reversed")
    assert any(report.disposition.value == "achieved" for step in result.local_steps for report in step.reports)
    assert result.cycles[-1].maternal_task.task.status == "budget_exhausted"
    assert result.cycles[-1].maternal_source.separation > result.cycles[0].maternal_source.separation


def test_external_assistance_without_a_selected_task_does_not_claim_task_completion():
    result = run_follow_mom_v1("assisted_no_task")
    assert result.cycles[-1].maternal_source.separation < 0.5
    assert all(cycle.maternal_task.task is None and not cycle.reservations for cycle in result.cycles)
    assert all(step.command is None or step.command.translation is None for step in result.local_steps)


@pytest.mark.parametrize("name", ["fast_cadence", "far_target", "narrowed", "motor_blocked"])
def test_finite_noncompletion_never_expands_the_original_task_or_target_budget(name):
    result = run_follow_mom_v1(name)
    task = result.cycles[-1].maternal_task.task
    assert task.status in {"budget_exhausted", "execution_exhausted"} and task.applications <= 20
    assert len(result.local_steps) == 80
    for cycle in result.cycles:
        for reservation in cycle.reservations:
            assert reservation.current.expires_at_tick <= task.started_tick + 80


class _IntegerSubclass(int):
    """Numerically valid values must still fail exact built-in integer contracts."""


@pytest.mark.parametrize("field", ["started_cycle", "started_tick", "applications"])
@pytest.mark.parametrize("bad", [True, 1.0, _IntegerSubclass(1)], ids=["bool", "float", "int-subclass"])
def test_lint_cleanup_preserves_exact_task_counter_types(field, bad):
    """Every original task counter rejects Boolean, floating and subclassed integers."""
    task = FollowMomTaskV1("task:lint-regression", "region_1", 1, 0)
    with pytest.raises(ValueError):
        replace(task, **{field: bad})


@pytest.mark.parametrize("bad", [True, 1.0, _IntegerSubclass(1)], ids=["bool", "float", "int-subclass"])
def test_lint_cleanup_preserves_exact_focal_cycle_type(bad):
    """A numeric lookalike cannot borrow the currently prepared focal opportunity."""
    operation, _, _, wnm = prepared()
    before = operation.snapshot()
    with pytest.raises(ValueError, match="current focal opportunity"):
        operation.evaluate_applicability(wnm, cycle_id=bad)
    assert operation.snapshot() == before


@pytest.mark.parametrize("bad", [True, 1.0, _IntegerSubclass(1)], ids=["bool", "float", "int-subclass"])
def test_lint_cleanup_preserves_exact_prediction_horizon_type(bad):
    """The maternal preview keeps its original exact-integer physical-tick contract."""
    operation, _, _, wnm = prepared()
    application = operation.apply(wnm, operation.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    with pytest.raises(ValueError, match="one to eight physical ticks"):
        replace(application.projection, horizon_ticks=bad)


@pytest.mark.parametrize("bad", [False, 20.0, _IntegerSubclass(20)], ids=["bool", "float", "int-subclass"])
def test_lint_cleanup_preserves_exact_maternal_rank_type(bad):
    """A rank equal to zero or twenty is insufficient without its canonical type."""
    operation, basis, _, _ = prepared()
    before = operation.source.retained_counts()
    with pytest.raises(ValueError, match="continuation rank"):
        MaternalCandidateV1(basis, bad)
    assert operation.source.retained_counts() == before
