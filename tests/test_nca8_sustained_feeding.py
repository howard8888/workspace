"""M behavior/authority tests use the existing live task-to-body loop.

Additional need records are explicitly labeled owner-local completion fixtures;
they do not claim new physical observations from an unchanged simulation.
"""
from dataclasses import replace
from functools import lru_cache
import json

import pytest

from cca8_motor_contracts import FeedingDeficitFeedbackV1
from cca8_support_world import FeedingConsequenceProfileV1, MotorWorldPerturbationV1, PlanarPerturbationV1
from nca8_feeding_state import FeedingNeedStateV1
from nca8_suckle import SuckleProfileV1, SuckleExtractionApplicationV1
from nca8_suckle_extraction_learning_demo import _without_hook_reporting
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1, suckle_extraction_profile_v1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_sustained_feeding_demo import (
    SUSTAINED_FEEDING_CASES_V1, SustainedFeedingExperimentV1, create_sustained_feeding_trial_v1,
    run_sustained_feeding_v1, sustained_feeding_profile_v1,
)


@lru_cache(None)
def experiment(case):
    return run_sustained_feeding_v1(case)


def customized(p):
    trial = create_sustained_feeding_trial_v1(p)
    result = SustainedFeedingExperimentV1(p, collect_seek_nipple_evidence_v1(trial, p.extraction.latch.run))
    return trial, result


def advance(trial, count):
    return tuple(trial.advance_lower() for _ in range(count))


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "True", [], {}])
def test_explicit_opt_in_and_required_correspondence(bad):
    assert not SuckleProfileV1().sustained_feeding_enabled
    with pytest.raises(TypeError):
        SuckleProfileV1(sustained_feeding_enabled=bad)


def test_sustained_requires_real_physical_profile_but_not_old_latch_or_learning_owners():
    with pytest.raises(ValueError):
        SuckleProfileV1(sustained_feeding_enabled=True)
    p = sustained_feeding_profile_v1("already_sealed")
    with pytest.raises(ValueError):
        create_suckle_extraction_trial_v1(p.extraction)
    old = p.extraction.latch.suckle
    old = replace(old, outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False,
                  extraction_learning_hook_enabled=False, extraction_outcome_attention_enabled=False)
    p = replace(p, extraction=replace(p.extraction, latch=replace(p.extraction.latch, suckle=old)))
    trial, result = customized(p)
    assert trial.core.suckle.task is None and trial.core.suckle_outcomes is None
    assert trial.core.feeding_detail.extraction_learning_hook is None
    assert result.final.task.status == "completed" and len(result.applications()) > 1


@pytest.mark.parametrize("case", SUSTAINED_FEEDING_CASES_V1)
def test_shared_live_cases_have_real_evidence_and_no_hidden_success(case):
    result = experiment(case)
    assert result.review_status == "PASS", result.checks()
    assert len(result.checks()) >= 14
    assert result.run.durable_before == result.run.durable_after
    assert all(c.sustained_feeding is not None for c in result.run.cycles)
    assert all(c.commitment.selected_primitive_id != "ip:rest" for c in result.run.cycles)


def test_nominal_is_real_seek_latch_then_separate_repeated_extraction():
    r = experiment("nominal")
    kinds = [type(c.calculation.navigation.application).__name__ for c in r.run.cycles if c.calculation.navigation.application]
    assert kinds[:2] == ["SeekNippleApplicationV1", "SuckleApplicationV1"]
    assert kinds[2:] == ["SuckleExtractionApplicationV1"] * 3
    assert r.final.task.started_tick == 20 and r.final.task.expires_at_tick == 116
    latch = next(c.suckle_task.task for c in r.run.cycles if c.suckle_task and c.suckle_task.task)
    assert latch.started_tick == 8 and latch.started_tick + 48 == 56
    assert r.final.task.task_id != latch.task_id
    assert r.metrics()["completed_tick"] == 56
    assert all(a.task.latch.status == "latch_established" for a in r.applications())


def test_different_initial_need_changes_contribution_count_not_fixed_success_counter():
    small, ordinary, larger = (experiment(c) for c in ("small_need", "already_sealed", "larger_need"))
    assert [len(r.applications()) for r in (small, ordinary, larger)] == [1, 3, 5]
    assert all(r.final.task.status == "completed" for r in (small, ordinary, larger))
    assert all(r.final.need.deficit_units <= .01 for r in (small, ordinary, larger))
    already = experiment("already_adequate")
    assert not already.applications() and already.final.task is None
    assert already.final.reason == "feeding_not_required_at_entry"


def test_received_milk_without_downstream_uptake_is_not_satisfaction():
    r = experiment("uptake_off")
    assert r.metrics()["physical_receipt_units"] > 1
    assert r.final.need.deficit_units == .5 and r.final.task.status == "budget_exhausted"
    assert r.final.task.applications == 8 and r.metrics()["completed_tick"] is None


def test_unavailable_internal_evidence_cannot_be_backfilled_from_measured_milk():
    r = experiment("internal_loss_after_receipt")
    assert len(r.applications()) == 1
    assert r.outcomes()[0].milk_evidence()["exact_observed_total"] == pytest.approx(.2)
    assert r.final.need.deficit_units is None and r.final.task.status == "budget_exhausted"
    assert not any(c.sustained_feeding.task and c.sustained_feeding.task.status == "completed" for c in r.run.cycles)


def test_absent_oral_milk_sensing_does_not_erase_independent_bodily_satisfaction():
    r = experiment("milk_sensor_off")
    assert r.final.task.status == "completed"
    assert all(o.milk_evidence()["coverage"] == "unavailable" and o.milk_evidence()["exact_observed_total"] is None for o in r.outcomes())
    assert all(o.milk_evidence()["quantity_status"] == "unknown_total" for o in r.outcomes())
    assert r.metrics()["physical_receipt_units"] == pytest.approx(.6)


def test_dry_and_depleted_are_local_success_without_feeding_success_or_retry_forever():
    dry, depleted = experiment("dry"), experiment("depleted")
    assert len(dry.applications()) == 1 and len(depleted.applications()) == 2
    assert all(o.status == "local_sequence_observed" for r in (dry,depleted) for o in r.outcomes())
    assert all(value == "matched" for o in dry.outcomes() for _, value in o.relations)
    assert dry.final.task.status == depleted.final.task.status == "budget_exhausted"
    assert any(c.sustained_feeding.reason == "feeding_no_yield_waiting_for_body_consequence" for c in dry.run.cycles)


def test_lower_execution_does_not_self_select_a_second_contribution_without_focal_call():
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    first = trial.focal_step()
    advance(trial, 16)
    assert trial.handoff_consumptions == 1 and trial.controller.installation_count == 1
    assert len(trial.core.suckle.extraction_applications()) == 1
    assert trial.observer_oral_extraction_body.transferred_milk_units == pytest.approx(.2)
    second = trial.focal_step()
    assert isinstance(second.calculation.navigation.application, SuckleExtractionApplicationV1)
    assert first.calculation.navigation.application.application_id != second.calculation.navigation.application.application_id
    assert trial.tick == 16  # selection/installation did not run physics


@pytest.mark.parametrize("cadence,complete_tick", [(1,28),(4,36),(8,48)])
def test_same_physical_threshold_deadline_and_confirmation_across_focal_cadence(cadence, complete_tick):
    r = experiment({1:"cadence_1",4:"already_sealed",8:"cadence_8"}[cadence])
    assert r.metrics()["completed_tick"] == complete_tick and len(r.applications()) == 3
    completed = next(c.sustained_feeding for c in r.run.cycles if c.sustained_feeding.task and c.sustained_feeding.task.status=="completed")
    assert completed.task.expires_at_tick == 96
    a,b = completed.confirmation
    assert a.sample_id != b.sample_id and b.event_tick-a.event_tick>=4
    assert a.deficit_units<=.01 and b.deficit_units<=.01


def test_eight_application_cap_can_end_before_physical_deadline_and_never_restart():
    p = sustained_feeding_profile_v1("uptake_off")
    p = replace(p, extraction=replace(p.extraction,latch=replace(p.extraction.latch,run=replace(p.extraction.latch.run,cadence=1))))
    _,r = customized(p)
    first_terminal = next(c for c in r.run.cycles if c.sustained_feeding.task and c.sustained_feeding.task.status=="budget_exhausted")
    assert first_terminal.calculation.cutoff_tick == 72 < first_terminal.sustained_feeding.task.expires_at_tick
    assert len(r.applications()) == 8 and r.final.task.applications == 8


def test_satisfaction_after_original_deadline_never_repairs_expired_task():
    p = sustained_feeding_profile_v1("already_sealed")
    p = replace(p, physiology=FeedingConsequenceProfileV1(initial_pending_units=.5,uptake_units_per_second=.1))
    _,r = customized(p)
    assert r.final.need.deficit_units == pytest.approx(0)
    assert r.final.task.status=="budget_exhausted" and r.metrics()["completed_tick"] is None
    at96 = next(c for c in r.run.cycles if c.calculation.cutoff_tick==96)
    assert at96.sustained_feeding.task.status=="budget_exhausted"


def test_early_satisfaction_retires_only_existing_oral_permission_without_repairing_unfinished_claim():
    p = sustained_feeding_profile_v1("cadence_1")
    p = replace(p,physiology=replace(p.physiology,initial_deficit_units=.03))
    trial,r = customized(p)
    end = next(c for c in r.run.cycles if c.sustained_feeding.task and c.sustained_feeding.task.status=="completed")
    assert end.calculation.cutoff_tick == 7
    assert end.sustained_feeding.retirement_requested and end.receipt.dispatch.motor.cancel_previous
    assert all(s.command.oral_extraction_drive in (None,0) for s in r.run.local_steps if s.tick>=7 and s.command)
    assert r.outcomes()[0].status=="interrupted" and r.outcomes()[0].termination=="cancelled"
    assert trial.core.cognition.mapper.reservations(at_tick=trial.tick)==()


def test_later_righting_target_not_cancelled_by_old_completed_feeding_record():
    p = sustained_feeding_profile_v1("already_sealed")
    run=p.extraction.latch.run
    run=replace(run,physical=replace(run.physical,perturbations=(MotorWorldPerturbationV1(40,44,angular_rate_degrees_s=90),)))
    p=replace(p,extraction=replace(p.extraction,latch=replace(p.extraction.latch,run=run)))
    _,r=customized(p)
    later=tuple(c for c in r.run.cycles if c.calculation.cutoff_tick>=40)
    rights=[t.current for c in later for t in c.reservations if c.commitment.selected_primitive_id=="ip:righting"]
    assert rights, [(c.calculation.cutoff_tick,c.commitment.selected_primitive_id,c.calculation.navigation.reason) for c in later]
    assert all(t.target.origin.task_id!=r.final.task.task_id for t in rights)
    assert any(s.command and s.command.orientation_drive not in (None,0) for s in r.run.local_steps if s.tick>=40)
    assert r.final.task.status=="completed"


@pytest.mark.parametrize("case", ["already_sealed","nominal","dry","uptake_off","body_shift"])
def test_LF_removal_preserves_every_non_hook_decision_and_physical_sample(case):
    p=sustained_feeding_profile_v1(case)
    off=replace(p,extraction=replace(p.extraction,latch=replace(p.extraction.latch,
         suckle=replace(p.extraction.latch.suckle,extraction_learning_hook_enabled=False))))
    _,a=customized(p); _,b=customized(off)
    assert tuple(_without_hook_reporting(c) for c in a.run.cycles)==b.run.cycles
    assert a.run.local_steps==b.run.local_steps and a.run.physical_samples==b.run.physical_samples
    assert a.run.durable_before==a.run.durable_after==b.run.durable_after


def test_current_satisfaction_does_not_delete_independent_mismatch_question():
    p=sustained_feeding_profile_v1("body_shift")
    p=replace(p,physiology=replace(p.physiology,initial_deficit_units=.02,initial_pending_units=.02))
    _,r=customized(p)
    queried=[c for c in r.run.cycles if c.extraction_attention and c.extraction_attention.created]
    assert queried
    c=queried[0]
    assert c.feeding_detail_source.feeding_need.deficit_units==0
    assert c.extraction_attention.source_bid is not None
    assert c.extraction_attention.source_bid.new_task_need_rank == 0
    # The question competes; satisfaction must not force its source to win.
    assert c.extraction_attention.allocation.kind == "other_source"
    question = c.extraction_attention.created[0]
    assert question in c.extraction_attention.pending
    assert not isinstance(c.calculation.navigation.application, SuckleExtractionApplicationV1)
    assert any(d.status == "pending_interpretation" for d in c.extraction_learning_report.dispositions)


def test_F_cannot_supply_interpretation_when_another_source_wins():
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("body_shift"))
    cycles = [trial.focal_step()]
    # Explicit fixed stronger-source fixture; no outcome-dependent scheduler.
    for tick in range(1, 29):
        trial.advance_lower()
        if tick % 4 == 0:
            cycles.append(trial.focal_step(visual_bid_priority=(100, 100)))
    ds = [d for c in cycles for d in c.extraction_learning_report.dispositions]
    queried = [c for c in cycles if c.extraction_attention.created or c.extraction_attention.pending]
    assert queried and all(c.extraction_attention.allocation.kind == "other_source" for c in queried)
    assert any(d.status == "pending_interpretation" for d in ds)
    assert any(d.status == "eligibility_expired" for d in ds)
    assert not any(d.status == "accepted_no_update" for d in ds)
    assert not any(d.interpretation for d in ds)
    assert len(trial.core.suckle.extraction_applications()) == 1


def test_completion_owner_rejects_cached_or_missing_samples_without_spurious_dwell():
    trial=create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    trial.focal_step(); owner=trial.core.suckle
    def context(sample,event,cutoff,new=True,value=0):
        return FeedingNeedStateV1(trial.latest_feedback.stream,cutoff+1,cutoff,sample,event,event,value,new)
    # Isolated owner-local threshold fixture, not fabricated live sensing.
    owner._observe_feeding_satisfaction(context(6,5,5))
    owner._observe_feeding_satisfaction(context(6,5,9,new=False))
    assert owner.feeding_assessment().task.status=="active" and owner._feeding_proof==[]
    owner._observe_feeding_satisfaction(context(11,10,10))
    owner._observe_feeding_satisfaction(context(12,11,11,value=None))
    owner._observe_feeding_satisfaction(context(16,15,15))
    assert owner.feeding_assessment().task.status=="active" and len(owner._feeding_proof)==1
    owner._observe_feeding_satisfaction(context(20,19,19))
    assert owner.feeding_assessment().task.status=="completed"


def test_reset_and_fault_close_old_generational_rights_and_participation():
    p=sustained_feeding_profile_v1("already_sealed")
    trial=create_sustained_feeding_trial_v1(p); c=trial.focal_step(); old=trial.core
    old_hook=old.feeding_detail.extraction_learning_hook
    assert old_hook.pending()
    trial.reset()
    assert old.fault and old_hook._closed and old_hook.pending()==()
    assert trial.core is not old and trial.core.suckle.feeding_assessment().task is None
    assert trial.observer_feeding_consequence.deficit_units==.5 and trial.observer_feeding_consequence.pending_units==0
    with pytest.raises((RuntimeError,ValueError)):
        old_hook.reconcile(cycle_id=2,cutoff_tick=4,registration=c.extraction_correspondence.registration)


def test_need_is_applied_in_C1_before_operations_and_F_has_no_physical_or_need_effect(monkeypatch):
    trial=create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    owner=trial.core.cognition.sensory
    source=trial.core.feeding_detail
    hook=source.extraction_learning_hook
    update=source.update; reconcile=hook.reconcile
    def updated(*args,**kwargs):
        assert owner.feeding_need is kwargs["feeding_need"]
        return update(*args,**kwargs)
    def reconciled(**kwargs):
        before=(owner.feeding_need,trial.observer_feeding_consequence,trial.core.suckle.feeding_assessment(),trial.tick)
        result=reconcile(**kwargs)
        assert before==(owner.feeding_need,trial.observer_feeding_consequence,trial.core.suckle.feeding_assessment(),trial.tick)
        return result
    monkeypatch.setattr(source,"update",updated);monkeypatch.setattr(hook,"reconcile",reconciled)
    for i in range(37):
        if i%4==0:trial.focal_step()
        if i<36:trial.advance_lower()


def test_missing_internal_acquisition_breaks_low_need_confirmation():
    r = experiment("internal_gap")
    missing = next(c.sustained_feeding for c in r.run.cycles if c.calculation.cutoff_tick == 32)
    assert missing.need.deficit_units is None and missing.confirmation == ()
    assert missing.task.status == "active" and r.metrics()["completed_tick"] == 40
    assert len(r.applications()) == 3


def test_confirmation_uses_recent_pair_when_earliest_low_reading_is_too_old():
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    trial.focal_step()
    owner = trial.core.suckle
    # Owner-local nonuniform evidence fixture; no artificial live sensor injection.
    for event in (1, 4, 11):
        owner._observe_feeding_satisfaction(FeedingNeedStateV1(
            trial.latest_feedback.stream, event + 1, event, event + 1, event, event, 0.0, True))
    assessment = owner.feeding_assessment()
    assert assessment.task.status == "completed"
    assert tuple(n.event_tick for n in assessment.confirmation) == (4, 11)
    assert assessment.confirmation[1].event_tick - assessment.confirmation[0].event_tick <= 8
