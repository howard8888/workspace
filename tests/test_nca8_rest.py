"""Rest ownership and full-path negative controls on the real hierarchy/provider."""
from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import BodyBearingFeedbackV1, MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1
from nca8_executive import NavigationRuntimeV1
from nca8_rest import RestApplicationV1, RestProfileV1, RestIPV1, rest_geometry_v1
from nca8_rest_demo import RestWalkthroughV1, create_rest_trial_v1, rest_profile_v1, run_rest_v1
from nca8_maps import MotorSupportConfigurationV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, LocalTargetDispositionV1
from nca8_suckle import SuckleExtractionApplicationV1


@pytest.fixture(scope="module")
def nominal():
    return run_rest_v1("nominal")


@pytest.fixture(scope="module")
def fed():
    return run_rest_v1("already_fed")


def test_nominal_is_one_real_overview_feeding_and_rest_run(nominal):
    selected=[c.commitment.selected_primitive_id for c in nominal.cycles if c.commitment.selected_primitive_id]
    assert selected[0]=='ip:follow_mom'
    assert 'ip:seek_nipple' in selected and 'ip:suckle' in selected and selected[-1]=='ip:rest'
    assert nominal.metrics()['first_completed_tick']==204
    assert len(nominal.applications())==7
    assert len([c for c in nominal.cycles if isinstance(c.calculation.navigation.application,SuckleExtractionApplicationV1)])==3
    assert nominal.physical_samples[-1].oral.extension_metres==pytest.approx(0)
    assert nominal.physical_samples[-1].seal.closure==pytest.approx(0)
    assert nominal.physical_samples[-1].seal.sealed is False
    assert nominal.physical_samples[-1].support.support_extension==pytest.approx(.2)
    assert all(c.commitment.cycle_id==i+1 for i,c in enumerate(nominal.cycles))
    assert nominal.handoff_consumptions==len(nominal.cycles)


def test_initial_adequacy_needs_no_m_completed_flag(fed):
    assert all(c.sustained_feeding is None or c.sustained_feeding.task is None for c in fed.cycles)
    assert fed.metrics()['first_completed_tick']==88
    assert fed.applications()[0].projection.basis.cutoff_tick==8


@pytest.mark.parametrize('case',['rest_off','tendency_off','attention_off','navigation_off','competing_source',
                                 'high_need','missing_need','missing_seal','missing_reach','missing_body','bearing_sensor_off','delayed'])
def test_missing_owner_need_or_evidence_never_creates_rest(case):
    result=run_rest_v1(case)
    assert result.applications()==()
    assert result.metrics()['first_completed_tick'] is None
    assert result.review_status=='PASS'


@pytest.mark.parametrize('case',['already_recumbent','lateral_left','lateral_right'])
def test_supported_recumbency_needs_no_forced_upright_or_invented_movement(case):
    result=run_rest_v1(case)
    assert [a.contribution.contribution for a in result.applications()]==['hold']
    assert not any(c.commitment.selected_primitive_id=='ip:righting' for c in result.cycles)
    assert result.physical_samples[0].support==result.physical_samples[-1].support
    assert not any(s.command and (s.command.orientation_drive or s.command.extension_drive or s.command.oral_drive or s.command.oral_closure_drive)
                   for s in result.local_steps)
    assert result.metrics()['first_completed_tick']>result.applications()[0].task.started_tick


def test_off_hook_preserves_every_nonhook_focal_and_physical_result(fed):
    off=run_rest_v1('hook_off')
    assert off.local_steps==fed.local_steps and off.physical_samples==fed.physical_samples
    for a,b in zip(fed.cycles,off.cycles):
        assert replace(a,rest=replace(a.rest,learning=None))==b
    assert fed.durable_before==fed.durable_after==off.durable_after


@pytest.mark.parametrize('case',['lower_motor_off','release_motor_off','withdraw_motor_off','no_capability','bearing_off','support_loss','cancelled'])
def test_request_install_movement_and_completion_do_not_collapse(case):
    result=run_rest_v1(case)
    assert result.applications() and result.metrics()['first_completed_tick'] is None
    assert result.cycles[-1].rest.task.status in {'outcome_unresolved','not_applied','support_interrupted','cancelled'}
    if case=='no_capability':
        assert result.installations<len(result.applications())
    if case=='release_motor_off':
        assert all(p.seal.closure==.6 for p in result.physical_samples)
    if case=='lower_motor_off':
        assert all(p.support.support_extension==1 for p in result.physical_samples)


def test_past_rest_completion_cannot_hide_current_support_loss_or_cancel_later_righting():
    result=run_rest_v1('post_rest_support_loss')
    completed=[c for c in result.cycles if c.rest.task and c.rest.task.status=='completed']
    assert completed[0].calculation.cutoff_tick==88
    assert completed[-1].rest.current_safe_rest is False
    rights=[c for c in result.cycles if c.commitment.selected_primitive_id=='ip:righting']
    assert rights and all(c.calculation.cutoff_tick>=240 for c in rights)
    targets={r.current for c in rights for r in c.reservations}
    assert any(s.command and s.command.extension_drive>0 and any(r.committed_target in targets for r in s.reports)
               for s in result.local_steps)
    assert all(c.rest.task==completed[0].rest.task for c in completed)


def test_target_transfer_really_crosses_physical_bearing_overlap(fed):
    lower=[s for s in fed.local_steps if s.command and s.command.extension_drive<0]
    assert lower and all(s.command.orientation_drive==0 for s in lower)
    readings=[s.feedback for s in fed.local_steps if s.feedback is not None]
    assert any(f.body_bearing and .01<f.body_bearing.bearing<.99 for f in readings)
    assert all((f.support_contact and f.useful_loading>0) or f.body_bearing.bearing>0 for f in readings)


@pytest.mark.parametrize('field',['enabled','tendency_enabled','attention_enabled','outcome_attention_enabled','learning_hook_enabled'])
@pytest.mark.parametrize('bad',[None,1,0,'true'])
def test_profile_is_strict_opt_in(field,bad):
    with pytest.raises(TypeError): RestProfileV1(**{field:bad})


@pytest.mark.parametrize('change',[{'cycle_id':True},{'cycle_id':0},{'cutoff_tick':True},{'cutoff_tick':-1},
                                    {'movement_blocked':1}])
def test_bad_opportunity_cannot_mutate_rest_owner(change):
    w=RestWalkthroughV1(rest_profile_v1('already_fed'));w.advance();c=w.snapshot().cycles[-1]
    owner=w.trial.core.rest
    before=json.dumps(owner.as_dict(),sort_keys=True)
    need=w.trial.core.cognition.sensory.feeding_need
    kwargs=dict(cycle_id=c.calculation.cycle_id+1,cutoff_tick=4,movement_blocked=False)
    kwargs.update(change)
    with pytest.raises((TypeError,ValueError)):
        owner.prepare(c.calculation.source.motor_support,need,**kwargs)
    assert json.dumps(owner.as_dict(),sort_keys=True)==before


def test_need_loss_expires_original_episode_then_return_cannot_restart():
    result=run_rest_v1('need_loss')
    assert len(result.applications())==1
    assert result.cycles[-1].rest.task.status=='budget_exhausted'
    assert result.cycles[-1].rest.task.expires_at_tick==136
    assert result.cycles[-1].sustained_feeding.need.current
    assert result.metrics()['first_completed_tick'] is None


def test_application_cap_is_not_completion_or_a_new_budget():
    p=rest_profile_v1('already_fed');latch=p.feeding.latch
    run=replace(latch.run,oral=replace(latch.run.oral,initial_extension_metres=.35))
    p=replace(p,feeding=replace(p.feeding,latch=replace(latch,run=run,seal=replace(latch.seal,initial_closure=1.0))))
    result=RestWalkthroughV1(p).run_to_end()
    assert len(result.applications())==8
    first=next(c for c in result.cycles if c.rest.task and c.rest.task.status=='budget_exhausted')
    assert first.calculation.cutoff_tick<first.rest.task.expires_at_tick
    assert result.metrics()['first_completed_tick'] is None
    assert all(a.task.started_tick==8 for a in result.applications())


@pytest.mark.parametrize('case',['cadence_1','cadence_8'])
def test_cadence_holds_physics_conditions_and_original_clock(case):
    result=run_rest_v1(case)
    assert result.review_status=='PASS'
    assert result.applications()[0].task.expires_at_tick-result.applications()[0].task.started_tick==128
    assert len(result.local_steps)==320 and result.profile.feeding.latch.run.physical.dt_seconds==.05
    assert all(a.contribution.lease_ticks<=8 for a in result.applications())


def test_forecast_cannot_be_rewritten_after_observation(fed):
    p=fed.applications()[0].projection
    with pytest.raises(ValueError): replace(p,predicted_coordinate=.7)
    with pytest.raises(ValueError): replace(p,horizon_ticks=0)
    assert p.predicted_coordinate==0


def test_actual_body_changes_do_not_rebase_original_targets(fed):
    first=fed.applications()[0]
    assert first.projection.basis.feedback.oral_seal.closure==.6
    assert fed.physical_samples[-1].seal.closure==pytest.approx(0)
    outcomes=[r for c in fed.cycles for r in c.rest.outcomes]
    assert outcomes[0].claim.application is first
    assert outcomes[0].claim.target.target.basis==first.projection.basis.feedback
    assert outcomes[0].published_tick>outcomes[0].claim.due_tick


def test_closed_episode_and_sensor_history_not_changed_by_reading(fed):
    rng=random.getstate();before=fed.as_dict()
    assert before==fed.as_dict()
    before['metrics']['current_safe_rest']=False
    assert fed.metrics()['current_safe_rest'] is True
    assert random.getstate()==rng
