"""L-B: actual sensed phases, one original lease, and no implicit task authority."""
from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralExtractionFeedbackV1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorProfileV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, SensorimotorTargetKindV1
from nca8_oral_extraction_control_demo import (
    OralExtractionControlTrialV1, oral_extraction_control_profile_v1, run_oral_extraction_control_v1,
)

KIND=SensorimotorTargetKindV1.ORAL_EXTRACTION


def sample(trial,event,stroke,*,available=None,**changes):
    return replace(trial.latest_feedback,sample_id=event+1,event_tick=event,
                   available_tick=event if available is None else available,
                   oral_extraction=OralExtractionFeedbackV1(stroke=stroke,milk_transferred_units=0.0,interval_start_tick=event-1),
                   **changes)


@pytest.mark.parametrize('repetitions',[1,2])
def test_actual_distinct_endpoint_acquisitions_not_final_position(repetitions):
    result=run_oral_extraction_control_v1('twice' if repetitions==2 else 'nominal')
    assert result.steps[0].reports[0].disposition is not LocalTargetDispositionV1.ACHIEVED
    assert result.installation_count==1
    final=result.steps[-1].reports[0]
    assert final.disposition is LocalTargetDispositionV1.ACHIEVED
    rows=final.extraction_confirmations
    assert len(rows)==2*repetitions
    assert [row.oral_extraction.stroke for row in rows]==pytest.approx([.1,0.0]*repetitions)
    assert len({row.sample_id for row in rows})==2*repetitions
    assert [row.event_tick for row in rows]==sorted({row.event_tick for row in rows})
    assert all(step.command is None for step in result.steps[8:])
    assert all(report.committed_target is final.committed_target for step in result.steps for report in step.reports)


def test_predicted_endpoint_and_reread_do_not_advance_the_pattern():
    trial=OralExtractionControlTrialV1('twice')
    first=trial.advance()
    assert first.command.oral_extraction_drive==1.0
    assert first.predictions[0].expected_coordinate==pytest.approx(.1)
    second=trial.advance()
    assert second.feedback == first.feedback
    assert second.feedback.sample_id == first.feedback.sample_id
    assert second.command is None
    assert second.reports[0].extraction_confirmations==()
    third=trial.advance()
    assert len(third.reports[0].extraction_confirmations)==1
    assert third.command.oral_extraction_drive==-1.0
    fourth=trial.advance()
    assert fourth.command is None
    assert len(fourth.reports[0].extraction_confirmations)==1


@pytest.mark.parametrize('case',['blocked_motor','blocked_prediction_off','delayed','dropout','short_lease','slow_capability'])
def test_unperformed_or_unobserved_pattern_never_becomes_achieved(case):
    result=run_oral_extraction_control_v1(case)
    assert result.review_status=='PASS'
    assert result.steps[-1].reports[0].disposition is not LocalTargetDispositionV1.ACHIEVED
    assert all(step.command is None for step in result.steps if step.tick>=result.target.lease_ticks)
    assert all(len(report.extraction_confirmations)<2*result.target.repetitions for step in result.steps for report in step.reports)


@pytest.mark.parametrize('case,reason',[('body_shift','oral_extraction_seal_lost'),('reach_shift','oral_extraction_seal_lost'),
                                      ('seal_loss','oral_extraction_seal_lost'),('support_loss','unexpected_contact_loss')])
def test_protection_stops_without_selecting_a_remedy(case,reason):
    result=run_oral_extraction_control_v1(case)
    assert any(report.reason==reason for step in result.steps for report in step.reports)
    assert result.steps[-1].command is None
    for step in result.steps:
        if step.command:
            assert step.command.oral_closure_drive is None and step.command.oral_drive is None
            assert step.command.translation is None and step.command.orientation_drive==0.0 and step.command.extension_drive==0.0


@pytest.mark.parametrize('case',['dry_surface','exhausted_supply','missing_milk'])
def test_private_supply_and_milk_sensing_do_not_choose_movements(case):
    nominal=run_oral_extraction_control_v1()
    variant=run_oral_extraction_control_v1(case)
    assert [step.command for step in nominal.steps]==[step.command for step in variant.steps]
    assert [step.reports[0].disposition for step in nominal.steps]==[step.reports[0].disposition for step in variant.steps]
    assert variant.steps[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    if case=='missing_milk':
        assert all(step.feedback.oral_extraction.milk_transferred_units is None for step in variant.steps)
    elif case=='dry_surface': assert variant.physical[-1].transferred_milk_units==0.0
    else: assert variant.physical[-1].transferred_milk_units==.05


@pytest.mark.parametrize('method',['install','install_authorized','replace_target'])
def test_no_duplicate_install_or_implicit_pattern_restart(method):
    trial=OralExtractionControlTrialV1()
    with pytest.raises((ValueError,TypeError)):
        if method=='replace_target': trial.controller.replace_target(trial.targets[0],at_tick=0)
        else: getattr(trial.controller,method)(trial.targets,at_tick=0)
    assert trial.world.tick==0
    assert trial.world.oral_extraction_body.transferred_milk_units==0.0


def test_no_permission_from_copied_reservation():
    trial=OralExtractionControlTrialV1('preview_only')
    mapper=trial.body.motor_targets
    reserved=mapper.reserve(trial.proposal,execution_id='x',at_tick=0)
    with pytest.raises(ValueError):
        trial.controller.install((replace(reserved[0]),),at_tick=0)
    assert trial.controller.installation_count==0
    with pytest.raises(ValueError):
        trial.controller.install(reserved,at_tick=0)
    assert trial.controller.step(trial.latest_feedback,at_tick=0).command is None


def test_cancelled_original_cannot_receive_late_achievement():
    trial=OralExtractionControlTrialV1()
    for _ in range(3): trial.advance()
    # Outward confirmed, return commanded but not yet delivered.
    assert len(trial.controller.reports[0].extraction_confirmations)==1
    mapper=trial.body.motor_targets
    mapper.cancel(trial.targets[0],at_tick=3)
    steps=[trial.advance() for _ in range(9)]
    assert all(step.command is None for step in steps)
    assert steps[-1].reports[0].disposition is LocalTargetDispositionV1.CANCELLED


def test_late_final_observation_is_descriptive_only_under_original_lease():
    trial=OralExtractionControlTrialV1()
    controller=trial.controller
    controller.step(trial.latest_feedback,at_tick=0)
    controller.step(sample(trial,1,.1),at_tick=1)
    for tick in range(2,8):
        controller.step(sample(trial,tick,.03),at_tick=tick)
    last=sample(trial,8,0.0,available=9)
    expired=controller.step(sample(trial,7,.03),at_tick=8)
    assert expired.reports[0].disposition is LocalTargetDispositionV1.EXPIRED
    achieved=controller.step(last,at_tick=9)
    assert achieved.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert achieved.command is None
    assert achieved.reports[0].committed_target.expires_at_tick==8


def test_late_outward_evidence_cannot_start_a_missing_return_phase():
    trial=OralExtractionControlTrialV1()
    # Prediction protection off isolates timing from the blocked-motion response.
    settings=replace(oral_extraction_control_profile_v1(),prediction_protection=False)
    trial=OralExtractionControlTrialV1(settings=settings)
    controller=trial.controller
    for tick in range(8):
        controller.step(trial.latest_feedback if tick==0 else sample(trial,tick,0.0),at_tick=tick)
    step=controller.step(sample(trial,8,.1),at_tick=8)
    assert step.command is None and step.reports[0].disposition is LocalTargetDispositionV1.EXPIRED
    assert step.reports[0].extraction_confirmations==()


@pytest.mark.parametrize('channel',['stroke','seal','touch','reach','position','heading','closure'])
def test_missing_required_sensing_withholds_and_times_out(channel):
    trial=OralExtractionControlTrialV1()
    controller=trial.controller
    controller.step(trial.latest_feedback,at_tick=0)
    def changed(event):
        row=sample(trial,event,.1)
        if channel=='stroke': return replace(row,oral_extraction=replace(row.oral_extraction,stroke=None))
        if channel in {'seal','closure'}: return replace(row,oral_seal=replace(row.oral_seal,**{'sealed' if channel=='seal' else 'closure':None}))
        if channel in {'touch','reach'}: return replace(row,oral=replace(row.oral,**{'contact' if channel=='touch' else 'extension_metres':None}))
        return replace(row,planar=replace(row.planar,**{'position' if channel=='position' else 'heading_degrees':None}))
    steps=[controller.step(changed(tick),at_tick=tick) for tick in range(1,4)]
    assert all(step.command is None for step in steps)
    assert steps[-1].reports[0].disposition is LocalTargetDispositionV1.UNAVAILABLE
    assert steps[-1].reports[0].extraction_confirmations==()


@pytest.mark.parametrize('fault',['generation','reused_content','future'])
def test_invalid_input_faults_without_a_second_command(fault):
    trial=OralExtractionControlTrialV1()
    first=trial.advance()
    body=trial.latest_feedback
    if fault=='generation': body=replace(body,stream=MotorStreamRefV1(body.stream.stream_id,body.stream.generation+1))
    elif fault=='future': body=sample(trial,1,.1,available=2)
    else: body=replace(body,oral_extraction=replace(body.oral_extraction,stroke=.5))
    with pytest.raises((ValueError,TypeError)):
        trial.controller.step(body,at_tick=1)
    assert trial.controller.fault is not None
    assert first.command.oral_extraction_drive==1.0
    with pytest.raises(RuntimeError): trial.controller.step(trial.latest_feedback,at_tick=1)


def test_single_provider_advance_and_reset_isolation(monkeypatch):
    trial=OralExtractionControlTrialV1('twice')
    original=trial.world.step
    calls=[]
    def counted(command):
        calls.append(trial.world.tick)
        return original(command)
    monkeypatch.setattr(trial.world,'step',counted)
    for _ in range(5): trial.advance()
    assert calls==list(range(5)) and trial.controller.installation_count==1
    old=trial.targets[0]
    trial.reset()
    assert trial.world.tick==0 and trial.controller.installation_count==1
    assert trial.controller.reports[0].extraction_confirmations==()
    assert old.current.target.origin.stream != trial.targets[0].current.target.origin.stream
    with pytest.raises(ValueError): trial.body.motor_targets.validate_reservation(old,at_tick=0)


def test_physical_exception_after_side_effect_never_retries(monkeypatch):
    trial=OralExtractionControlTrialV1()
    original=trial.world.step
    def broken(command):
        original(command)
        raise RuntimeError('failed after movement')
    monkeypatch.setattr(trial.world,'step',broken)
    with pytest.raises(RuntimeError): trial.advance()
    assert trial.stopped and trial.world.tick==1
    assert trial.world.oral_extraction_body.transferred_milk_units==pytest.approx(.1)
    with pytest.raises(RuntimeError): trial.advance()
    assert trial.world.tick==1


def test_controller_does_not_call_ip_or_infer_task_success(monkeypatch):
    from nca8_suckle import SuckleIPV1
    from nca8_seek_nipple import SeekNippleIPV1
    def forbidden(*_args,**_kwargs): raise AssertionError('unexpected IP application')
    monkeypatch.setattr(SuckleIPV1,'apply',forbidden)
    monkeypatch.setattr(SeekNippleIPV1,'apply',forbidden)
    state=random.getstate()
    result=run_oral_extraction_control_v1('twice')
    assert result.review_status=='PASS' and random.getstate()==state
    assert result.source_before==result.source_after
    assert not result.as_dict()['is_navigation_selected_suckle']


def test_truncating_diagnostics_does_not_change_any_execution():
    tiny=run_oral_extraction_control_v1('twice',trace_capacity=1)
    full=run_oral_extraction_control_v1('twice',trace_capacity=256)
    assert tiny.steps==full.steps and tiny.physical==full.physical
    assert tiny.trace_retained==1 and full.trace_retained==12
    exported=tiny.as_dict()
    exported['steps'][0]['reports'][0]['extraction_progress']['confirmed_endpoints'].append('fake')
    assert tiny.steps[0].reports[0].extraction_confirmations==()


@pytest.mark.parametrize('anchor',['position','heading','reach'])
def test_anchor_change_alone_blocks_even_when_contact_and_seal_stay_true(anchor):
    trial=OralExtractionControlTrialV1()
    trial.controller.step(trial.latest_feedback,at_tick=0)
    row=sample(trial,1,.1)
    if anchor=='position': row=replace(row,planar=replace(row.planar,position=(.01,0.0)))
    elif anchor=='heading': row=replace(row,planar=replace(row.planar,heading_degrees=1.0))
    else: row=replace(row,oral=replace(row.oral,extension_metres=.11))
    result=trial.controller.step(row,at_tick=1)
    assert result.command is None
    assert result.reports[0].reason=='oral_extraction_anchor_changed'
    assert result.reports[0].extraction_confirmations==()
