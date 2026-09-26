"""N's optional physical bearing, timed body evidence and narrow Rest body authority."""
from dataclasses import replace
import json
import math

import pytest

from cca8_motor_contracts import BodyBearingFeedbackV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import BodyBearingProfileV1, MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, body_bearing_v1
from nca8_body_targets import BodyTargetMapperV1, RestBodyRequestV1, nominal_body_capabilities_v1, oral_body_capability_v1, oral_closure_capability_v1
from nca8_maps import create_posture_support_map_library_v1, MotorSupportConfigurationV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, SensorimotorTargetKindV1, TargetOriginV1
from nca8_righting import RightingActivityV1, RightingContextV1, righting_support_adequacy_v1
from nca8_rest_demo import create_rest_trial_v1, rest_profile_v1, RestWalkthroughV1

STREAM=MotorStreamRefV1('rest_body_fixture',1)


@pytest.mark.parametrize('clearance,expected',[(.4,0),(.3,0),(.275,.25),(.25,.5),(.225,.75),(.2,1),(.1,1)])
def test_body_bearing_comes_from_actual_clearance(clearance,expected):
    assert body_bearing_v1(MotorBodyStateV1(0,clearance),BodyBearingProfileV1(),surface_present=True)==pytest.approx(expected)


@pytest.mark.parametrize('tilt',[-90,-80,-45,0,45,80,90])
def test_geometry_is_mirrored_not_forced_upright(tilt):
    p=BodyBearingProfileV1()
    b=body_bearing_v1(MotorBodyStateV1(tilt,.4),p,surface_present=True)
    assert b==body_bearing_v1(MotorBodyStateV1(-tilt,.4),p,surface_present=True)
    assert b==pytest.approx(min(1,max(0,(.3-.4*math.cos(math.radians(tilt)))/.1)))


@pytest.mark.parametrize('surface,competence',[(False,True),(True,False),(False,False)])
def test_no_surface_or_competence_cannot_borrow_expected_bearing(surface,competence):
    profile=BodyBearingProfileV1(competence_enabled=competence)
    assert body_bearing_v1(MotorBodyStateV1(80,.2),profile,surface_present=surface)==0


@pytest.mark.parametrize('extension',[.2,.25,.3,1])
def test_old_limb_loading_is_not_rewritten_as_body_bearing(extension):
    profile=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0,extension))
    old=MotorWorldV1(STREAM,profile).observe()
    new=MotorWorldV1(STREAM,profile,body_bearing_profile=BodyBearingProfileV1()).observe()
    assert old.useful_loading==new.useful_loading and old.support_contact==new.support_contact
    assert old.body_bearing is None
    if extension==.2:
        assert new.body_bearing.bearing==pytest.approx(1) and new.useful_loading==0
        assert righting_support_adequacy_v1(new,RightingContextV1('rest',RightingActivityV1.REST)) is True
        assert righting_support_adequacy_v1(new,RightingContextV1('move',RightingActivityV1.MOBILITY)) is False


@pytest.mark.parametrize('bad',[True,'1',-0.01,1.01,float('nan'),float('inf')])
def test_bearing_measurement_rejects_coercion_and_invalid_numbers(bad):
    with pytest.raises((TypeError,ValueError)):
        BodyBearingFeedbackV1(True,bad)


@pytest.mark.parametrize('contact',[None,False,True])
@pytest.mark.parametrize('bearing',[None,0,.4,1])
def test_body_facet_roundtrip_keeps_unknown_and_contradiction_visible(contact,bearing):
    facet=BodyBearingFeedbackV1(contact,bearing)
    assert BodyBearingFeedbackV1.from_dict(facet.as_dict())==facet
    old=MotorFeedbackV1(STREAM,1,0,0,0,.2,False,0,.1)
    new=replace(old,body_bearing=facet)
    assert MotorFeedbackV1.from_dict(new.as_dict())==new
    assert old.as_dict()['schema']=='body_motor_feedback_v1'
    assert new.as_dict()['base_schema']=='body_motor_feedback_v1'
    assert new.as_dict()['schema']=='body_motor_feedback_v7'


@pytest.mark.parametrize('key,value',[('rest_ok',True),('nourished',True),('reward',1),('units','newtons'),('contact',1),('bearing','1')])
def test_body_wire_rejects_success_or_fake_units(key,value):
    data=BodyBearingFeedbackV1(True,1).as_dict();data[key]=value
    with pytest.raises((TypeError,ValueError)):BodyBearingFeedbackV1.from_dict(data)


@pytest.mark.parametrize('bad',[.15,.2,.3,.4])
def test_invalid_support_overlap_refuses_profile(bad):
    with pytest.raises(ValueError):
        MotorWorldV1(STREAM,MotorWorldProfileV1(surface_reach=bad),body_bearing_profile=BodyBearingProfileV1())


@pytest.mark.parametrize('bad',[(),[1],(True,),(2,1),(1,1),(321,),(-1,)])
def test_invalid_dropout_rejects_but_empty_tuple_is_valid(bad):
    if bad==():
        assert BodyBearingProfileV1(unavailable_ticks=bad).unavailable_ticks==()
    else:
        with pytest.raises((TypeError,ValueError)):BodyBearingProfileV1(unavailable_ticks=bad)


def test_sensor_ablation_changes_only_observability_not_physical_drift():
    p=MotorWorldProfileV1(initial_body=MotorBodyStateV1(80,1))
    a=MotorWorldV1(STREAM,p,body_bearing_profile=BodyBearingProfileV1())
    b=MotorWorldV1(STREAM,p,body_bearing_profile=BodyBearingProfileV1(sensor_available=False))
    for _ in range(32):
        a.step();b.step()
        x,y=a.observe(),b.observe()
        assert x.body_tilt_degrees==y.body_tilt_degrees==80
        assert x.support_extension==y.support_extension==1
        assert x.destabilization==y.destabilization
        assert x.body_bearing.bearing==1 and y.body_bearing.bearing is None
        assert y.body_bearing.contact is None


def _mapping_fixture(contribution='withdraw',**feedback_changes):
    trial=create_rest_trial_v1(rest_profile_v1('already_fed'))
    feedback=trial.latest_feedback
    feedback=replace(feedback,oral_seal=replace(feedback.oral_seal,closure=0,sealed=False),**feedback_changes)
    stream=feedback.stream;maps=create_posture_support_map_library_v1()
    source=MotorSupportConfigurationV1(maps.posture_support_ref,stream,FocalMotorEvidenceV1(feedback,1,0),None,1,0)
    mapper=BodyTargetMapperV1(stream,(*nominal_body_capabilities_v1(),oral_body_capability_v1(),oral_closure_capability_v1()))
    mapper.update_feedback(feedback,at_tick=0)
    origin=TargetOriginV1(stream,'rest:1:1','rest_application:1:1','rest_envelope:1:1')
    request=RestBodyRequestV1(origin,maps.posture_support_ref,contribution)
    proposal=mapper.propose_rest(request,source,at_tick=0)
    return mapper,proposal,source


def test_only_rest_withdrawal_can_leave_an_actual_contact():
    mapper,proposal,source=_mapping_fixture()
    reservation=mapper.reserve(proposal,execution_id='real_rest_binding',at_tick=0)[0]
    assert proposal.bindings[0].target.offset<0
    assert source.feedback.oral.contact is True
    assert mapper.execution_refusal(reservation,at_tick=0) is None
    # Removing Rest's explicit constraint restores the original ordinary contact stop.
    ordinary=replace(reservation.current,target=replace(reservation.current.target,rest_constraint=None))
    with pytest.raises(ValueError):
        mapper.execution_refusal(replace(reservation,current=ordinary),at_tick=0)


def test_withdrawal_refuses_still_sealed_or_missing_release_evidence():
    mapper,proposal,source=_mapping_fixture()
    for seal in (replace(source.feedback.oral_seal,closure=.6,sealed=True),replace(source.feedback.oral_seal,sealed=None)):
        mapper,proposal,source=_mapping_fixture()
        feedback=replace(source.feedback,sample_id=2,event_tick=1,available_tick=1,oral_seal=seal,
                         oral_extraction=replace(source.feedback.oral_extraction,interval_start_tick=0,milk_transferred_units=0))
        mapper.update_feedback(feedback,at_tick=1)
        current=replace(source,evidence=FocalMotorEvidenceV1(feedback,2,1),applied_cycle=2,cutoff_tick=1)
        p=mapper.propose_rest(proposal.request,current,at_tick=1)
        assert not p.bindings and p.withheld


@pytest.mark.parametrize('marker',['release','settle','hold'])
def test_target_marker_cannot_borrow_another_effector(marker):
    _,proposal,_=_mapping_fixture()
    with pytest.raises(ValueError):replace(proposal.bindings[0].target,rest_constraint=marker)


def test_copying_description_cannot_install_without_a_consumed_handoff():
    trial=create_rest_trial_v1(rest_profile_v1('already_fed'))
    mapper,proposal,_=_mapping_fixture()
    reservations=mapper.reserve(proposal,execution_id='description_only',at_tick=0)
    with pytest.raises((ValueError,RuntimeError)):trial.controller.install_authorized(reservations,at_tick=0)
    assert trial.tick==0


def test_context_is_changed_only_by_selected_accepted_installed_rest():
    w=RestWalkthroughV1(rest_profile_v1('already_fed'))
    initial=w.trial.core.cognition.context
    w.advance();w.advance()
    assert w.trial.core.cognition.context==initial
    first=w.advance()
    assert isinstance(first.calculation.navigation.application, __import__('nca8_rest').RestApplicationV1)
    assert first.receipt.dispatch.motor.targets
    assert w.trial.core.cognition.context.activity==RightingActivityV1.REST
    target=first.reservations[0].current
    # At tick 12 the previous activity transition must not cancel its own first target.
    next_cycle=w.advance()
    assert next_cycle.receipt.dispatch.motor.cancel_previous is False
    assert target.target.origin.task_id==w.trial.core.rest.task.task_id
