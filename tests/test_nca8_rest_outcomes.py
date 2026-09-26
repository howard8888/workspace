"""Original Rest evidence, independently bounded F and the single shared support grant.

Tests deliberately corrupt returned records to exercise integrity. Such mutations
are test fixtures only, never alternate cognitive input or a physical experiment.
"""
from dataclasses import replace
from collections import deque

import pytest

from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_rest import RestProfileV1
from nca8_rest_demo import RestWalkthroughV1, rest_profile_v1, run_rest_v1
from nca8_rest_outcomes import (
    RestClaimV1, RestOutcomeRuntimeV1, RestParticipationV1, RestQuestionV1,
    RestInterpretationV1, RestFocalAllocationV1, validate_rest_outcome_v1,
)


@pytest.fixture(scope='module')
def fed():
    return run_rest_v1('already_fed')


@pytest.fixture(scope='module')
def blocked():
    return run_rest_v1('release_drift')


def original_frames(result):
    return [c for c in result.cycles if c.rest.registration is not None]


def original_results(result):
    return [o for c in result.cycles for o in c.rest.outcomes]


def pending():
    w=RestWalkthroughV1(rest_profile_v1('already_fed'))
    for _ in range(3): w.advance()
    owner=w.trial.core.cognition.sensory.rest_outcomes
    return w,owner,tuple(w.trial._rest_intervals)


def test_each_original_claim_keeps_its_exact_application_and_real_target(fed):
    frames=original_frames(fed);outcomes=original_results(fed)
    assert len(frames)==len(outcomes)==6
    for frame,outcome in zip(frames,outcomes):
        assert outcome.claim is frame.rest.registration
        assert outcome.claim.application is frame.calculation.navigation.application
        assert outcome.claim.target is frame.reservations[0].current
        assert outcome.evidence.event_tick==outcome.claim.due_tick
        assert outcome.published_tick>outcome.evidence.event_tick
        validate_rest_outcome_v1(outcome)
        assert outcome.as_dict()['task_success']=='not_established'


@pytest.mark.parametrize('field,value',[('status','completed'),('status','mismatch'),('installed',False),('installed',1),
    ('published_tick',0),('ended_tick',999),('command_ticks',(True,)),('command_ticks',(8,8)),('command_ticks',(17,)),
    ('relations',(('coordinate','mismatch'),('support','matched'))),('evidence',None)])
def test_canonical_verdict_rejects_corrupt_original_evidence(fed,field,value):
    outcome=original_results(fed)[0]
    with pytest.raises((ValueError,TypeError)):
        validate_rest_outcome_v1(replace(outcome,**{field:value}))


@pytest.mark.parametrize('field,value',[('event_tick',17),('available_tick',100),('sample_id',1)])
def test_later_or_old_acquisition_cannot_replace_original_endpoint(fed,field,value):
    outcome=original_results(fed)[0];evidence=outcome.evidence
    changes={field:value}
    if field=='event_tick':
        changes['oral_extraction']=replace(evidence.oral_extraction,interval_start_tick=16)
    with pytest.raises((ValueError,TypeError)):
        validate_rest_outcome_v1(replace(outcome,evidence=replace(evidence,**changes)))


@pytest.mark.parametrize('change',['order','missing','copy_target','old_report','foreign_command','duplicate_command','bad_cutoff','mutable'])
def test_whole_returned_interval_transaction_rejects_atomically(change):
    w,owner,rows=pending();before=owner.__dict__.copy();before_counts=owner.retained_counts()
    if change=='order': rows=tuple(reversed(rows))
    elif change=='missing': rows=rows[1:]
    elif change in {'copy_target','old_report'}:
        index=0 if change=='copy_target' else 1
        reports=rows[index].reports;report=reports[0]
        report=replace(report,committed_target=replace(report.committed_target)) if change=='copy_target' else rows[0].reports[0]
        rows=(*rows[:index],replace(rows[index],reports=(report,*reports[1:])),*rows[index+1:])
    elif change=='foreign_command':
        command=rows[0].command
        rows=(replace(rows[0],command=replace(command,stream=replace(command.stream,generation=2))),*rows[1:])
    elif change=='duplicate_command': rows=(rows[0],replace(rows[1],command=replace(rows[1].command,command_id=rows[0].command.command_id)),*rows[2:])
    elif change=='mutable': rows=list(rows)
    with pytest.raises((ValueError,TypeError)):
        owner.consume(rows,cutoff_tick=True if change=='bad_cutoff' else 12)
    assert owner.__dict__==before and owner.retained_counts()==before_counts
    assert w.trial.tick==12


def test_conflicting_acquisition_does_not_partly_advance_watermarks():
    w,owner,rows=pending()
    known=owner._known[-1]
    altered=replace(known,body_tilt_degrees=1)
    rows=(replace(rows[0],deliveries=(altered,)),*rows[1:])
    before=(owner._last_interval,owner._last_command,owner._cutoff,owner.retained_counts())
    with pytest.raises(ValueError): owner.consume(rows,cutoff_tick=12)
    assert (owner._last_interval,owner._last_command,owner._cutoff,owner.retained_counts())==before


def test_registration_and_installation_cannot_be_reconsumed():
    w,owner,_=pending();claim=owner._pending
    with pytest.raises(ValueError): owner.register(claim.application,claim.target)
    with pytest.raises(ValueError): owner.installed(claim,at_tick=claim.start_tick)
    with pytest.raises(ValueError): owner.installed(replace(claim),at_tick=claim.start_tick)


def test_old_outcome_and_new_registration_share_F_without_sharing_identity(fed):
    simultaneous=[c.rest.learning for c in fed.cycles if c.rest.registration and c.rest.outcomes]
    assert len(simultaneous)==5
    for report in simultaneous:
        assert report.registration.application_id not in {key for key,_ in report.dispositions}
        assert report.registration.application_id in report.pending
        assert all(status=='accepted_no_update' for _,status in report.dispositions)


@pytest.mark.parametrize('elapsed,accepted',[(23,True),(24,False),(25,False)])
def test_eligibility_is_exclusive_original_physical_window(fed,elapsed,accepted):
    outcome=original_results(fed)[0];claim=outcome.claim
    owner=RestParticipationV1(claim.application.task.stream)
    owner.reconcile(cycle_id=claim.application.cycle_id,cutoff_tick=claim.start_tick,registration=claim,outcomes=(),allocation=None)
    delayed=replace(outcome,published_tick=claim.start_tick+elapsed)
    report=owner.reconcile(cycle_id=20,cutoff_tick=delayed.published_tick,registration=None,outcomes=(delayed,),allocation=None)
    assert report.dispositions==((claim.application_id,'accepted_no_update' if accepted else 'eligibility_expired'),)
    assert report.as_dict()['durable_learning_updates']==0
    assert delayed.evidence==outcome.evidence


def test_mismatch_waits_for_real_focal_interpretation_then_accepts_once(blocked):
    frame=next(c for c in blocked.cycles if c.rest.outcomes)
    outcome=frame.rest.outcomes[0];claim=outcome.claim
    assert outcome.status=='mismatch'
    owner=RestParticipationV1(claim.application.task.stream)
    owner.reconcile(cycle_id=claim.application.cycle_id,cutoff_tick=claim.start_tick,registration=claim,outcomes=(),allocation=None)
    report=owner.reconcile(cycle_id=frame.calculation.cycle_id,cutoff_tick=outcome.published_tick,
                           registration=None,outcomes=(outcome,),allocation=None)
    assert report.dispositions==((claim.application_id,'pending_interpretation'),)
    original=frame.rest.allocation.interpretation
    actual=replace(original,cycle_id=original.cycle_id+1,cutoff_tick=original.cutoff_tick+1)
    report=owner.reconcile(cycle_id=actual.cycle_id,cutoff_tick=actual.cutoff_tick,registration=None,outcomes=(),
                           allocation=RestFocalAllocationV1('interpretation',actual))
    assert report.dispositions==((claim.application_id,'accepted_no_update'),)
    later=owner.reconcile(cycle_id=actual.cycle_id+1,cutoff_tick=actual.cutoff_tick+1,registration=None,outcomes=(),
                          allocation=RestFocalAllocationV1('response_reconsideration',actual))
    assert later.dispositions==()


def test_unknown_interpretation_is_not_teaching_or_free_F_work(blocked):
    frame=next(c for c in blocked.cycles if c.rest.outcomes);outcome=frame.rest.outcomes[0];claim=outcome.claim
    owner=RestParticipationV1(claim.application.task.stream)
    owner.reconcile(cycle_id=claim.application.cycle_id,cutoff_tick=claim.start_tick,registration=claim,outcomes=(),allocation=None)
    known=frame.rest.allocation.interpretation
    unknown=replace(known,status='unresolved_current_relevance',evidence=None,
                     current_relations=tuple((name,'unresolved_current_relevance') for name,_ in known.current_relations))
    report=owner.reconcile(cycle_id=known.cycle_id,cutoff_tick=known.cutoff_tick,registration=None,outcomes=(outcome,),
                           allocation=RestFocalAllocationV1('interpretation',unknown))
    assert report.dispositions==((claim.application_id,'pending_interpretation'),)
    owner._history=deque(maxlen=1)
    expiry=owner.reconcile(cycle_id=30,cutoff_tick=claim.start_tick+24,registration=None,outcomes=(),allocation=None)
    assert expiry.dispositions==((claim.application_id,'eligibility_expired'),)


@pytest.mark.parametrize('change',['unregistered','copied_claim','copied_outcome','same_cycle','old_time','foreign','same_action_result'])
def test_F_whole_transaction_integrity(fed,change):
    outcome=original_results(fed)[0];claim=outcome.claim
    owner=RestParticipationV1(claim.application.task.stream)
    if change!='unregistered':
        owner.reconcile(cycle_id=claim.application.cycle_id,cutoff_tick=claim.start_tick,registration=claim,outcomes=(),allocation=None)
    if change=='copied_claim': outcome=replace(outcome,claim=replace(claim))
    if change=='copied_outcome':
        owner.reconcile(cycle_id=6,cutoff_tick=20,registration=None,outcomes=(outcome,),allocation=None)
        outcome=replace(outcome,published_tick=21)
    if change=='foreign':
        owner=RestParticipationV1(replace(claim.application.task.stream,generation=2))
    before=owner.__dict__.copy()
    with pytest.raises((ValueError,TypeError)):
        owner.reconcile(cycle_id=claim.application.cycle_id if change=='same_cycle' else 7,
                        cutoff_tick=claim.start_tick if change in {'old_time','same_action_result'} else outcome.published_tick,
                        registration=claim if change=='same_action_result' else None,outcomes=(outcome,),allocation=None)
    assert owner.__dict__==before


def test_closed_owner_cannot_admit_restart_or_teach():
    w,owner,rows=pending();source=w.snapshot().cycles[-1].calculation.source
    owner.close();before=owner.__dict__.copy()
    with pytest.raises(ValueError): owner.admit(source,(),at_tick=8)
    with pytest.raises(ValueError): owner.consume(rows,cutoff_tick=12)
    with pytest.raises(ValueError): owner.participation.reconcile(cycle_id=10,cutoff_tick=12,registration=None,outcomes=(),allocation=None)
    assert owner.__dict__==before


def test_storage_is_bounded_after_long_observation_and_diagnostics_do_not_keep_permission():
    w=RestWalkthroughV1(rest_profile_v1('already_fed'))
    maxima={}
    while not w.finished:
        w.advance()
        for key,value in w.trial.retained_counts().items(): maxima[key]=max(maxima.get(key,0),value)
    assert maxima['rest_applications']<=8 and maxima['rest_claims']<=8 and maxima['rest_outcomes']<=8
    assert maxima['rest_pending_claims']<=1 and maxima['rest_questions']<=8
    assert maxima['rest_learning_claims']<=8 and maxima['rest_learning_history']<=8
    assert maxima['rest_dwell_samples']<=3 and maxima['rest_readiness_samples']<=2
    assert maxima['rest_staged_intervals']<=16 and maxima['rest_recent_acquisitions']<=16


def test_no_grant_no_interpretation_then_navigation_allocates_actual_question(monkeypatch):
    w=RestWalkthroughV1(rest_profile_v1('release_drift'))
    runtime=w.trial.core.cognition;owner=runtime.sensory.rest_outcomes
    real=owner.allocate
    monkeypatch.setattr(owner,'allocate',lambda working,**kwargs: RestFocalAllocationV1('deferred_other_question'))
    while not owner.questions(): w.advance()
    frame=w.snapshot().cycles[-1];working=frame.calculation.navigation.wnm;cycle=frame.calculation.cycle_id
    before=owner.questions()
    with pytest.raises(ValueError): real(working,cycle_id=cycle)
    assert owner.questions()==before
    nav=NavigationRuntimeV1(motor_preview_enabled=True)
    choice=AttentionRuntimeV1().select((owner.contribute_bid(None),),current_wnm=None,cycle_id=cycle)
    working=nav.update_wnm(choice)
    candidate=owner.interpretation_candidate(working,cycle_id=cycle)
    nav.allocate_outcome_interpretation(working,(candidate,),cycle_id=cycle,at_tick=frame.calculation.cutoff_tick)
    allocation=real(working,cycle_id=cycle,grant=nav.last_decision)
    assert allocation.kind=='interpretation' and not allocation.permits_primitive_selection
    assert owner.questions()==()


@pytest.mark.parametrize('righting_first',[False,True])
def test_two_real_same_source_questions_have_one_grant_and_preserve_the_loser(monkeypatch,righting_first):
    # The Rest question comes from a live externally disturbed closure actuator. The Righting question
    # is an explicitly synthetic endpoint fixture with a delayed C2 invocation;
    # both original forecasts precede their own evidence. This is allocator QA,
    # not a claim that this constructed pair occurred in the nominal organism.
    import test_nca8_outcome_attention as old
    w=RestWalkthroughV1(rest_profile_v1('release_drift'))
    runtime=w.trial.core.cognition;rest=runtime.sensory.rest_outcomes
    real=rest.allocate
    monkeypatch.setattr(rest,'allocate',lambda working,**kwargs: RestFocalAllocationV1('deferred_other_question'))
    while not rest.questions(): w.advance()
    if not righting_first:
        w.advance()  # Retained Rest admission is now older than the new Righting question.
    monkeypatch.setattr(rest,'allocate',real)
    frame=w.snapshot().cycles[-1];source=frame.calculation.source;tick=frame.calculation.cutoff_tick;cycle=frame.calculation.cycle_id
    monkeypatch.setattr(old,'STREAM',rest.stream)
    harness=old.EndpointHarness();consume=harness.publisher.consume_intervals
    publication=tick-4 if righting_first else tick
    monkeypatch.setattr(harness.publisher,'consume_intervals',lambda rows,**kwargs: consume(rows,cutoff_tick=publication))
    outcome=harness.endpoint(support_contact=False)
    righting=old.owner_for(harness)
    earlier=old.source_at(publication,cycle=cycle-1) if righting_first else source
    righting.admit((outcome,),earlier,harness.task,harness.task.context,cutoff_tick=publication)
    if righting_first: righting.admit((),source,harness.task,harness.task.context,cutoff_tick=tick)
    assert len(righting.pending())==len(rest.questions())==1
    runtime.sensory._outcome_attention=righting
    runtime.navigation=NavigationRuntimeV1(motor_preview_enabled=True)
    choice=AttentionRuntimeV1().select((old.ordinary_bid(source),),current_wnm=None,cycle_id=cycle)
    working=runtime.navigation.update_wnm(choice)
    a,b,grant=runtime._allocate_support_outcome_work(working,cycle_id=cycle,cutoff_tick=tick)
    assert sum(x is not None and x.kind=='interpretation' for x in (a,b))==1
    assert grant.application is None and grant.wnm is working
    assert len(righting.pending())+len(rest.questions())==1
    assert a.kind=='interpretation' if righting_first else b.kind=='interpretation'
