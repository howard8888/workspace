"""P16-1G-A domain evidence, pre-handoff meaning, physical time and once-only claims.

Synthetic fixtures below supply explicit sensory/authorization records to the
real owners; they are not attributed to a physical world or a learned mechanism.
Live integration and observer/menu controls are tested separately.
"""

from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_maps import MotorSupportConfigurationV1
from nca8_outcomes import RightingIntervalEvidenceV1, RightingOutcomeRuntimeV1
from nca8_righting import RightingActivityV1, RightingContextV1, righting_support_adequacy_v1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, LocalTargetDispositionV1, LocalTargetReportV1

STREAM = MotorStreamRefV1("outcome_fixture", 1)


def sensor(event, *, delay=0, **changes):
    """Provide a named synthetic acquisition; the decoder does not grant authority."""
    result = MotorFeedbackV1(STREAM, event + 1, event, event + delay, 30.0, 0.5, True, 0.4, 0.3)
    return replace(result, **changes)


def supported(event, **changes):
    return sensor(event, body_tilt_degrees=10.0, useful_loading=0.9, destabilization=0.05, **changes)


def fixture(*, capabilities=None, install=True, compare=True):
    """Use actual Navigation, Righting and BodyMap to produce a supplied test grant."""
    session = Nca8RightingPreviewSessionV1(STREAM, capabilities=capabilities)
    result = session.preview(sensor(0), cutoff_tick=0)
    application, proposal = result.navigation.application, result.proposal
    assert proposal is not None
    reservations = session.mapper.reserve(proposal, execution_id="fixture_execution", at_tick=0) if proposal.bindings else ()
    targets = tuple(item.current for item in reservations)
    owner = RightingOutcomeRuntimeV1(STREAM, compare_predictions=compare)
    registration = owner.register(application, proposal, targets)
    if install and targets:
        owner.installed(registration, at_tick=0)
    return session, application, registration, owner


def source(task, feedback, cycle, cutoff=None):
    tick = feedback.event_tick if cutoff is None and feedback is not None else cutoff
    evidence = FocalMotorEvidenceV1(feedback, cycle, tick) if feedback is not None else None
    return MotorSupportConfigurationV1(task.source_map_ref, STREAM, evidence, None, cycle, tick)


def intervals(registration, stop, *, endpoint=None, drive=True, endpoint_return=None):
    """Return explicit synthetic normally-returned intervals, with one endpoint packet."""
    rows = []
    for tick in range(stop):
        targets = registration.targets
        reports = tuple(LocalTargetReportV1(
            target, LocalTargetDispositionV1.ACTIVE if tick < target.expires_at_tick else LocalTargetDispositionV1.EXPIRED,
            tick, "supplied_fixture_interval",
        ) for target in targets)
        command = MotorCommandV1(STREAM, tick + 1, tick, 0.2, 0.2) if drive and tick < registration.due_tick else None
        return_tick = endpoint.available_tick if endpoint_return is None and endpoint is not None else endpoint_return
        deliveries = (endpoint,) if endpoint is not None and tick + 1 == return_tick else ()
        rows.append(RightingIntervalEvidenceV1(tick, command, reports, deliveries))
    return tuple(rows)


def predicted_sensor(registration, *, delay=1, **changes):
    preview = registration.preview
    return sensor(registration.due_tick, delay=delay, body_tilt_degrees=preview.predicted_tilt,
                  support_extension=preview.predicted_extension, useful_loading=preview.predicted_loading,
                  destabilization=preview.predicted_destabilization, **changes)


@pytest.mark.parametrize("tilt,expected", [(12.0, True), (-12.0, True), (12.00001, False), (-12.00001, False), (0.0, True)])
def test_strict_activity_boundary_is_not_replaced_by_local_tolerance(tilt, expected):
    assert righting_support_adequacy_v1(replace(supported(1), body_tilt_degrees=tilt), RightingContextV1()) is expected


@pytest.mark.parametrize("field", ["body_tilt_degrees", "support_contact", "useful_loading", "destabilization"])
def test_missing_required_relation_remains_unknown(field):
    assert righting_support_adequacy_v1(replace(supported(1), **{field: None}), RightingContextV1()) is None


@pytest.mark.parametrize("activity,tilt,load,instability,expected", [
    (RightingActivityV1.REST, 80.0, 0.0, 0.1, True),
    (RightingActivityV1.REST, None, 0.0, 0.1, True),
    (RightingActivityV1.REST, 80.0, 0.0, 0.2, False),
    (RightingActivityV1.CROUCH, 40.0, 0.45, 0.2, True),
    (RightingActivityV1.CROUCH, 40.01, 0.45, 0.2, False),
    (RightingActivityV1.MOBILITY, 10.0, 0.74, 0.1, False),
])
def test_activity_relative_predicate_preserves_existing_criteria(activity, tilt, load, instability, expected):
    feedback = sensor(1, body_tilt_degrees=tilt, useful_loading=load, destabilization=instability)
    assert righting_support_adequacy_v1(feedback, RightingContextV1("activity:fixture", activity)) is expected


def test_three_distinct_focal_samples_span_fixed_physical_duration():
    _, application, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    results = [owner.assess_task(application.task, source(application.task, supported(tick), index), application.task.context,
                                cutoff_tick=tick) for index, tick in enumerate((3, 7, 11), 1)]
    assert [item.status for item in results] == ["adequate_pending_dwell", "adequate_pending_dwell", "complete"]
    assert results[-1].as_dict()["supported_event_ticks"] == [3, 7, 11]
    assert application.task.status == "active"  # The evidence service itself cannot close the task.


@pytest.mark.parametrize("ticks", [(1, 2, 3), (1, 4, 7), (1, 10, 19)])
def test_short_or_gapped_dwell_cannot_complete(ticks):
    _, application, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    for cycle, tick in enumerate(ticks, 1):
        assessment = owner.assess_task(application.task, source(application.task, supported(tick), cycle),
                                       application.task.context, cutoff_tick=tick)
        assert not assessment.completion_supported


def test_fast_polling_retains_first_sample_instead_of_making_dwell_easier_or_impossible():
    _, application, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    for tick in range(1, 10):
        assessment = owner.assess_task(application.task, source(application.task, supported(tick), tick),
                                       application.task.context, cutoff_tick=tick)
        assert assessment.completion_supported is (tick == 9)
        assert len(assessment.supported_samples) <= 3
    assert [item.event_tick for item in assessment.supported_samples] == [1, 8, 9]


def test_cached_samples_do_not_accumulate_support_and_staleness_is_unknown():
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    feedback = supported(3)
    for cycle, cutoff in enumerate((3, 4, 5, 6), 1):
        assessment = owner.assess_task(app.task, source(app.task, feedback, cycle, cutoff), app.task.context, cutoff_tick=cutoff)
        assert not assessment.completion_supported
        assert len(assessment.supported_samples) <= 1
    assert assessment.status == "unknown" and not assessment.supported_samples


def test_one_supported_blip_followed_by_regression_restarts_dwell():
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    for cycle, feedback in enumerate((supported(3), sensor(7), supported(11), supported(15)), 1):
        assessment = owner.assess_task(app.task, source(app.task, feedback, cycle), app.task.context, cutoff_tick=feedback.event_tick)
        assert not assessment.completion_supported
    assert [item.event_tick for item in assessment.supported_samples] == [11, 15]


@pytest.mark.parametrize("bad", [sensor(5), replace(supported(5), support_contact=False),
                                  replace(supported(5), useful_loading=None), replace(supported(5), destabilization=None)])
def test_nonfocal_contradictory_or_unknown_feedback_breaks_dwell_without_adding_samples(bad):
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    owner.assess_task(app.task, source(app.task, supported(3), 1), app.task.context, cutoff_tick=3)
    rows = tuple(RightingIntervalEvidenceV1(tick, None, (), (bad,) if tick == 5 else ()) for tick in range(8))
    owner.consume_intervals(rows, cutoff_tick=8)
    result = owner.assess_task(app.task, source(app.task, supported(7), 2, 8), app.task.context, cutoff_tick=8)
    assert [item.event_tick for item in result.supported_samples] == [7]


def test_missing_source_is_unknown_and_does_not_count_as_stall():
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    result = owner.assess_task(app.task, source(app.task, None, 1, 4), app.task.context, cutoff_tick=4)
    assert result.status == "unknown" and result.relation_changes == ()


@pytest.mark.parametrize("change,expected", [
    ({"body_tilt_degrees": 25.0}, "progress"), ({"body_tilt_degrees": 35.0}, "regression"),
    ({"useful_loading": 0.5, "body_tilt_degrees": 35.0}, "mixed"), ({}, "unchanged"),
])
def test_progress_keeps_distinct_relational_changes(change, expected):
    _, app, _, owner = fixture()
    feedback = sensor(4, **change)
    result = owner.assess_task(app.task, source(app.task, feedback, 2), app.task.context, cutoff_tick=4)
    assert result.status == expected and not result.completion_supported


@pytest.mark.parametrize("drive,expected", [(True, "stall"), (False, "unchanged")])
def test_stall_requires_actual_command_opportunity_not_installation(drive, expected):
    _, app, reg, owner = fixture()
    owner.consume_intervals(intervals(reg, 4, drive=drive), cutoff_tick=4)
    result = owner.assess_task(app.task, source(app.task, sensor(4), 2), app.task.context, cutoff_tick=4)
    assert result.status == expected


def test_partial_improvement_does_not_prematurely_reject_endpoint_forecast():
    _, _, reg, owner = fixture()
    early = sensor(3, delay=1, body_tilt_degrees=29)
    assert owner.consume_intervals(intervals(reg, 4, endpoint=early), cutoff_tick=4) == ()
    assert owner.pending() == (reg,) and not owner.history()


def test_matching_original_endpoint_consumed_once_even_after_source_changes():
    _, _, reg, owner = fixture()
    original = json.dumps(reg.as_dict(), sort_keys=True)
    endpoint = predicted_sensor(reg)
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=endpoint), cutoff_tick=5)
    assert outcome.status == "matched" and outcome.evidence == endpoint and outcome.command_intervals == 4
    assert not owner.pending()
    replay = RightingIntervalEvidenceV1(5, None, (), (endpoint,))
    assert owner.consume_intervals((replay,), cutoff_tick=6) == ()
    assert len(owner.history()) == 1 and json.dumps(reg.as_dict(), sort_keys=True) == original
    assert outcome.as_dict()["action_causation"] == "uncertain"


@pytest.mark.parametrize("field,delta,expected", [
    ("body_tilt_degrees", 1.0, "matched"), ("body_tilt_degrees", 1.01, "mismatch"),
    ("support_extension", 0.02, "matched"), ("support_extension", 0.03, "mismatch"),
    ("useful_loading", 0.1, "matched"), ("useful_loading", 0.11, "mismatch"),
    ("destabilization", 0.1, "matched"), ("destabilization", 0.11, "mismatch"),
])
def test_declared_prediction_residual_tolerances_are_fixed(field, delta, expected):
    _, _, reg, owner = fixture()
    endpoint = predicted_sensor(reg)
    endpoint = replace(endpoint, **{field: getattr(endpoint, field) + delta})
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=endpoint), cutoff_tick=5)
    assert outcome.status == expected


@pytest.mark.parametrize("field", ["body_tilt_degrees", "support_extension", "useful_loading", "destabilization", "support_contact"])
def test_unobserved_predicted_relation_is_unknown_not_automatically_mismatch(field):
    _, _, reg, owner = fixture()
    endpoint = replace(predicted_sensor(reg), **{field: None})
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=endpoint), cutoff_tick=5)
    assert outcome.status == "unknown" and "unknown" in dict(outcome.relations).values()


def test_known_absent_contact_is_a_mismatch_not_missing_sensing():
    _, _, reg, owner = fixture()
    endpoint = replace(predicted_sensor(reg), support_contact=False, useful_loading=0.0)
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=endpoint), cutoff_tick=5)
    assert dict(outcome.relations)["contact"] == "mismatch" and outcome.status == "mismatch"


def test_installed_target_without_command_does_not_earn_executed_action_credit():
    _, _, reg, owner = fixture()
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=predicted_sensor(reg), drive=False), cutoff_tick=5)
    assert outcome.status == "observed_without_command" and outcome.command_intervals == 0
    assert dict(outcome.relations)["tilt"] == "matched"


def test_missing_exact_endpoint_expires_unresolved_not_with_a_later_substitute():
    _, _, reg, owner = fixture()
    later = sensor(5, delay=1)
    assert owner.consume_intervals(intervals(reg, 6, endpoint=later), cutoff_tick=6) == ()
    assert owner.consume_intervals((), cutoff_tick=12) == ()  # Inclusive availability deadline.
    expired, = owner.consume_intervals((), cutoff_tick=13)
    assert expired.status == "expired_unresolved" and expired.evidence is None
    assert owner.consume_intervals((), cutoff_tick=14) == ()


@pytest.mark.parametrize("delay,cutoff,expected", [(4, 8, "matched"), (8, 16, "matched"), (9, 13, "expired_unresolved")])
def test_delayed_endpoint_uses_original_event_and_availability_not_polling_time(delay, cutoff, expected):
    _, _, reg, owner = fixture()
    endpoint = predicted_sensor(reg, delay=delay)
    outcome, = owner.consume_intervals(intervals(reg, endpoint.available_tick, endpoint=endpoint), cutoff_tick=cutoff)
    assert outcome.status == expected
    if outcome.evidence is not None:
        assert outcome.evidence.event_tick == 4 and outcome.evaluated_tick == cutoff


def test_material_narrowing_preserves_original_forecast_and_only_compares_unchanged_relations():
    caps = nominal_body_capabilities_v1()
    _, _, reg, owner = fixture(capabilities=(replace(caps[0], maximum_step=2.0), caps[1]))
    assert set(reg.unevaluable_relations) == {"tilt", "loading", "destabilization", "contact"}
    assert reg.compatible_relations == ("extension",)
    original = reg.preview.predicted_tilt
    assert reg.targets[0].target.endpoint != original
    outcome, = owner.consume_intervals(intervals(reg, 5, endpoint=predicted_sensor(reg)), cutoff_tick=5)
    assert outcome.status == "partly_matched" and dict(outcome.relations)["tilt"] == "unevaluable_authorization"
    assert reg.preview.predicted_tilt == original


def test_pre_execution_veto_is_not_an_executed_prediction_failure():
    _, _, reg, owner = fixture(capabilities=())
    assert not reg.targets and not owner.pending()
    outcome, = owner.history()
    assert outcome.status == "not_applied" and outcome.command_intervals == 0 and outcome.evidence is None


def test_independent_prediction_comparison_off_preserves_registration_and_authority():
    _, _, reg, owner = fixture(compare=False)
    outcome, = owner.history()
    assert outcome.status == "comparison_disabled" and reg.targets
    owner.consume_intervals(intervals(reg, 5, endpoint=predicted_sensor(reg)), cutoff_tick=5)
    assert len(owner.history()) == 1 and not owner.pending()


def test_uninstalled_preview_cannot_accept_command_evidence():
    _, _, reg, owner = fixture(install=False)
    with pytest.raises(ValueError):
        owner.consume_intervals(intervals(reg, 1), cutoff_tick=1)
    owner.reject_uninstalled()
    assert owner.history()[-1].status == "not_applied" and not owner.pending()


def test_duplicate_installation_and_copied_registration_are_rejected():
    _, _, reg, owner = fixture(install=False)
    with pytest.raises(ValueError):
        owner.installed(replace(reg), at_tick=0)
    owner.installed(reg, at_tick=0)
    with pytest.raises(ValueError):
        owner.installed(reg, at_tick=0)


@pytest.mark.parametrize("kind", ["command_generation", "target_action", "copied_target", "feedback_generation", "command_order"])
def test_wrong_action_generation_or_command_evidence_rejected_before_consumption(kind):
    _, _, reg, owner = fixture()
    rows = list(intervals(reg, 2))
    row = rows[0]
    if kind == "command_generation":
        row = replace(row, command=replace(row.command, stream=MotorStreamRefV1(STREAM.stream_id, 2)))
    elif kind == "target_action":
        target = row.reports[0].committed_target
        origin = replace(target.target.origin, application_id="another_application")
        foreign = replace(target, target=replace(target.target, origin=origin))
        row = replace(row, reports=(replace(row.reports[0], committed_target=foreign), *row.reports[1:]))
    elif kind == "copied_target":
        row = replace(row, reports=(replace(row.reports[0], committed_target=replace(row.reports[0].committed_target)), *row.reports[1:]))
    elif kind == "feedback_generation":
        row = replace(row, deliveries=(replace(sensor(0), stream=MotorStreamRefV1(STREAM.stream_id, 2)),))
    else:
        rows[1] = replace(rows[1], command=replace(rows[1].command, command_id=rows[0].command.command_id))
    rows[0] = row
    before = owner.retained_counts(), owner.history(), owner.pending()
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(rows), cutoff_tick=2)
    assert (owner.retained_counts(), owner.history(), owner.pending()) == before


def test_duplicate_interval_and_conflicting_sensor_id_are_not_reapplied():
    _, _, reg, owner = fixture()
    owner.consume_intervals(intervals(reg, 1), cutoff_tick=1)
    with pytest.raises(ValueError):
        owner.consume_intervals(intervals(reg, 1), cutoff_tick=2)
    with pytest.raises(ValueError):
        owner.consume_intervals((), cutoff_tick=1)
    a, b = sensor(1), sensor(1, body_tilt_degrees=31)
    row = RightingIntervalEvidenceV1(1, None, (), (a, b))
    with pytest.raises(ValueError):
        owner.consume_intervals((row,), cutoff_tick=2)


@pytest.mark.parametrize("tick", [-1, True, 1.5, "4", 2**63])
def test_interval_requires_a_bounded_physical_tick(tick):
    with pytest.raises((ValueError, TypeError)):
        RightingIntervalEvidenceV1(tick, None, (), ())


def test_future_return_or_feedback_cannot_enter_the_frozen_cycle():
    _, _, reg, owner = fixture()
    with pytest.raises(ValueError):
        owner.consume_intervals(intervals(reg, 4), cutoff_tick=3)
    with pytest.raises(ValueError):
        RightingIntervalEvidenceV1(0, None, (), (sensor(2),))


@pytest.mark.parametrize("cancel_tick,expected", [(0, "cancelled"), (2, "interrupted"), (4, "matched")])
def test_cancellation_preserves_realized_endpoint_and_distinguishes_unfinished_horizon(cancel_tick, expected):
    _, _, reg, owner = fixture()
    if cancel_tick:
        owner.consume_intervals(intervals(reg, cancel_tick), cutoff_tick=cancel_tick)
    owner.end_execution(at_tick=cancel_tick)
    if cancel_tick == 4:
        row = intervals(reg, 5, endpoint=predicted_sensor(reg))[-1]
        owner.consume_intervals((row,), cutoff_tick=5)
    assert owner.history()[-1].status == expected


def test_cancellation_before_focal_admission_waits_for_already_returned_execution_bookkeeping():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    trial.focal_step()
    trial.advance_lower()
    trial.advance_lower()
    trial.cancel()
    result = trial.focal_step()
    assert result.task_outcome.status == "cancelled"
    outcome, = trial.core.outcomes.history()
    assert outcome.status == "interrupted" and outcome.command_intervals > 0


def test_uncertain_physical_execution_is_never_not_applied_or_automatically_retried(monkeypatch):
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    trial.focal_step()
    calls = []
    def failing_step(_command):
        calls.append("attempt")
        raise RuntimeError("possible effects")
    monkeypatch.setattr(trial._world, "step", failing_step)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.core.outcomes.history()[-1].status == "execution_unknown"
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert calls == ["attempt"] and trial.stopped


def test_old_pending_claim_survives_new_pnm_and_resolves_original_event():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    first, _ = trial.step()
    old = json.dumps(first.claim_registration.as_dict(), sort_keys=True)
    second, _ = trial.step()
    assert len(trial.core.outcomes.pending()) == 2
    third = trial.focal_step()
    outcome, = third.claim_outcomes
    assert outcome.registration is first.claim_registration and outcome.evidence.event_tick == 4
    assert third.calculation.navigation.application.projection.pnm != outcome.registration.preview.pnm
    assert json.dumps(first.claim_registration.as_dict(), sort_keys=True) == old
    assert first.calculation.task.status == second.calculation.task.status == "active"


def test_pending_capacity_refuses_new_obligations_instead_of_erasing_old_claims():
    session = Nca8RightingPreviewSessionV1(STREAM)
    owner = RightingOutcomeRuntimeV1(STREAM)
    for index in range(9):
        tick = index * 4
        prepared = session.prepare_source(sensor(tick), cutoff_tick=tick)
        result = session.project_selected(session.select_prepared(prepared), replace_existing=True)
        targets = tuple(item.current for item in session.mapper.reserve(result.proposal, execution_id=f"exec:{index}", at_tick=tick))
        if index < 8:
            reg = owner.register(result.navigation.application, result.proposal, targets)
            owner.installed(reg, at_tick=tick)
        else:
            with pytest.raises(OverflowError):
                owner.register(result.navigation.application, result.proposal, targets)
    assert len(owner.pending()) == 8 and not owner.history()


def test_ingress_overflow_stops_before_another_world_interval():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    trial.focal_step()
    for _ in range(16):
        trial.advance_lower()
    before = trial.observer_body, trial.tick
    with pytest.raises(OverflowError):
        trial.advance_lower()
    assert (trial.observer_body, trial.tick) == before and trial.stopped


def test_reset_revokes_old_owners_and_outcome_evidence():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    first, _ = trial.step()
    owner = trial.core.outcomes
    trial.reset()
    assert trial.core.outcomes is not owner and not trial.core.outcomes.pending()
    assert trial.core.outcomes.stream.generation == 2 and trial.tick == 0
    assert trial.core.cognition.righting.task is None
    with pytest.raises(ValueError):
        trial.core.cognition.mapper.update_feedback(first.calculation.source.motor_support.feedback, at_tick=0)


@pytest.mark.parametrize("option", ["task_outcomes_enabled", "task_prediction_comparison_enabled"])
@pytest.mark.parametrize("value", [None, 0, 1, "yes"])
def test_outcome_enablement_is_explicit_boolean(option, value):
    with pytest.raises(TypeError):
        IntegratedRightingTrialV1(**{option: value})


def test_task_source_context_and_generation_are_not_exchangeable():
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    different_context = RightingContextV1("activity:rest", RightingActivityV1.REST)
    with pytest.raises(ValueError):
        owner.assess_task(app.task, source(app.task, supported(3), 1), different_context, cutoff_tick=3)
    wrong = replace(app.task, stream=MotorStreamRefV1(STREAM.stream_id, 2))
    with pytest.raises(ValueError):
        owner.assess_task(wrong, source(app.task, supported(3), 1), app.task.context, cutoff_tick=3)


def test_new_requirement_cannot_inherit_old_dwell():
    _, app, _, _ = fixture()
    owner = RightingOutcomeRuntimeV1(STREAM)
    for cycle, tick in enumerate((3, 7), 1):
        owner.assess_task(app.task, source(app.task, supported(tick), cycle), app.task.context, cutoff_tick=tick)
    context = RightingContextV1("new_context", RightingActivityV1.REST)
    task = replace(app.task, task_id="new_task", context=context, started_tick=8)
    result = owner.assess_task(task, source(task, supported(11), 3), context, cutoff_tick=11)
    assert len(result.supported_samples) == 1 and not result.completion_supported


def test_completion_requires_current_last_sample_and_rechecks_proof_in_task_owner():
    session, app, _, _ = fixture()
    samples = tuple(supported(tick) for tick in (3, 7, 11))
    prepared = session.prepare_source(samples[-1], cutoff_tick=11)
    with pytest.raises(ValueError):
        session.complete_prepared_task(prepared, (samples[0], samples[0], samples[-1]), task_id=app.task.task_id)
    with pytest.raises(ValueError):
        session.complete_prepared_task(prepared, samples, task_id="wrong_task")
    completed = session.complete_prepared_task(prepared, samples, task_id=app.task.task_id)
    result = session.project_selected(session.select_prepared(completed))
    assert result.task.status == "completed" and result.proposal is None
    assert app.task.status == "active" and not app.task.completion_samples


@pytest.mark.parametrize("at_tick,accepted", [(80, True), (81, False)])
def test_due_completion_at_exact_budget_boundary_does_not_extend_future_authority(at_tick, accepted):
    session, app, _, _ = fixture()
    samples = tuple(supported(tick) for tick in (71, 75, 79))
    prepared = session.prepare_source(samples[-1], cutoff_tick=at_tick)
    if accepted:
        result = session.complete_prepared_task(prepared, samples, task_id=app.task.task_id)
        assert result.source_status == "completed"
    else:
        with pytest.raises(ValueError):
            session.complete_prepared_task(prepared, samples, task_id=app.task.task_id)


def test_no_durable_learning_or_rng_change_and_inspection_cannot_replay_execution():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    signature = trial.core.cognition.maps.durable_record_signature()
    rng = random.getstate()
    for _ in range(12):
        trial.step()
    before = trial.snapshot(), trial.tick, trial.handoff_consumptions
    json.dumps(trial.snapshot(), sort_keys=True)
    trial.core.outcomes.history()
    trial.core.outcomes.pending()
    assert (trial.snapshot(), trial.tick, trial.handoff_consumptions) == before
    assert trial.core.cognition.maps.durable_record_signature() == signature and random.getstate() == rng
    assert trial.retained_counts()["durable_maps"] == 1 and trial.retained_counts()["current_pnm"] <= 1


@pytest.mark.parametrize("case", ("stale_report", "cancelled_report", "expired_lease"))
def test_nonzero_command_requires_its_current_live_authorization(case):
    _, _, registration, owner = fixture()
    rows = list(intervals(registration, 9 if case == "expired_lease" else 2))
    index = len(rows) - 1
    if case == "expired_lease":
        rows[index] = replace(rows[index], command=MotorCommandV1(STREAM, 9, 8, 0.2, 0.2))
    else:
        reports = tuple(replace(report, reported_tick=0) if case == "stale_report" else
                        replace(report, disposition=LocalTargetDispositionV1.CANCELLED) for report in rows[index].reports)
        rows[index] = replace(rows[index], reports=reports)
    before = owner.retained_counts()
    with pytest.raises(ValueError, match="current live"):
        owner.consume_intervals(tuple(rows), cutoff_tick=len(rows))
    assert owner.retained_counts() == before and not owner.history()


def test_endpoint_acquisition_identity_is_validated_before_any_batch_mutation():
    _, _, registration, owner = fixture()
    wrong = replace(predicted_sensor(registration), sample_id=registration.preview.basis.feedback.sample_id)
    before = owner.retained_counts()
    with pytest.raises(ValueError, match="distinct later"):
        owner.consume_intervals(intervals(registration, 5, endpoint=wrong), cutoff_tick=5)
    assert owner.retained_counts() == before and not owner.history()
    owner.consume_intervals(intervals(registration, 5, endpoint=predicted_sensor(registration)), cutoff_tick=5)
    assert owner.history()[0].status == "matched"


def test_terminal_history_truncation_does_not_change_pending_claims_or_live_owner_bounds():
    # A finite multi-context storage stress, not an extended-horizon recovery success experiment.
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, trace_capacity=1)
    for index in range(42):
        trial.step(context=RightingContextV1(f"activity:storage_stress:{index}"))
        assert trial.retained_counts()["outcome_pending_claims"] <= 8
        assert trial.retained_counts()["outcome_terminal_history"] <= 32
    owner = trial.core.outcomes
    assert len(owner.history()) == 32 and owner.history()[0].number > 1
    assert len(owner.pending()) <= 2
    assert trial.retained_counts()["durable_maps"] == 1
    assert trial.retained_counts()["outcome_recent_feedback"] == 16
    before = owner.pending()
    owner.history()
    assert owner.pending() == before
