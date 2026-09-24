"""L-B: bounded extraction targets and original BodyMap authority, not a task IP."""
from dataclasses import FrozenInstanceError, replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralExtractionFeedbackV1
from nca8_body_targets import (
    BodyAxisCapabilityV1, BodyMovementRequestV1, BodyTargetBindingV1, BodyTargetMapperV1,
    BodyTargetReservationV1, OralExtractionRequestV1, OralClosureRequestV1, OralReachRequestV1,
    oral_extraction_capability_v1, oral_closure_capability_v1, oral_body_capability_v1, nominal_body_capabilities_v1,
)
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1, CommittedBodyTargetV1, OralExtractionTargetV1, LocalTargetReportV1,
    LocalTargetDispositionV1, SensorimotorTargetKindV1, scalar_motor_coordinate_v1,
)
from nca8_oral_extraction_control_demo import OralExtractionControlTrialV1, run_oral_extraction_control_v1

KIND = SensorimotorTargetKindV1.ORAL_EXTRACTION


def fresh():
    trial = OralExtractionControlTrialV1('preview_only')
    return trial, trial.body.motor_targets, trial.proposal.request


def target():
    return fresh()[0].proposal.bindings[0].target


@pytest.mark.parametrize('field,values', [
    ('outward_offset', [0.0, -0.1, 0.02, 0.3, float('nan'), float('inf'), True, '0.1']),
    ('tolerance', [0.0, -0.1, 0.05, 0.2, float('nan'), True]),
    ('max_displacement', [0.0, 0.09, 1.01, float('inf'), True]),
    ('max_rate', [0.0, -1.0, 2.01, float('nan'), True]),
    ('repetitions', [0, 3, -1, True, 1.5, '1']),
    ('lease_ticks', [0, 9, -1, True, 1.5]),
    ('max_corrections', [-1, 3, True, 1.5]),
    ('revision', [0, -1, True]),
])
def test_target_rejects_invalid_bounds(field, values):
    original = target()
    for value in values:
        with pytest.raises((ValueError, TypeError)):
            replace(original, **{field: value})


@pytest.mark.parametrize('field,value', [('outward_extent', 0.0), ('outward_extent', True), ('outward_extent', float('nan')),
                                        ('repetitions', 0), ('repetitions', 3), ('repetitions', True),
                                        ('lease_ticks', 0), ('lease_ticks', 9), ('lease_ticks', True)])
def test_request_rejects_invalid_pattern(field, value):
    request = fresh()[2]
    with pytest.raises((TypeError, ValueError)):
        replace(request, **{field: value})


@pytest.mark.parametrize('stroke', [0.0, 0.3, 0.6, 0.8])
def test_same_relative_request_is_anchored_to_actual_start(stroke):
    from nca8_oral_extraction_control_demo import oral_extraction_control_profile_v1
    settings = oral_extraction_control_profile_v1()
    trial = OralExtractionControlTrialV1(settings=replace(settings, extraction=replace(settings.extraction, initial_stroke=stroke)))
    item = trial.targets[0].current.target
    assert item.return_endpoint == stroke
    assert item.outward_endpoint == pytest.approx(stroke + .1)
    assert trial.world.oral_extraction_body.stroke == stroke
    assert item.as_dict()['milk_is_target'] is False
    with pytest.raises(FrozenInstanceError):
        item.repetitions = 2
    packet = item.as_dict()
    packet['basis']['oral_extraction']['stroke'] = .99
    assert item.basis_coordinate == stroke


@pytest.mark.parametrize('case,reason', [
    ('no_capability', 'capability_unavailable'), ('source_off', 'current_feeding_detail_unavailable'),
    ('no_touch', 'oral_extraction_seal_lost'), ('no_seal', 'oral_extraction_seal_lost'),
    ('missing_stroke', 'required_coordinate_missing'), ('missing_seal', 'required_seal_evidence_missing'),
])
def test_missing_physical_or_source_conditions_withhold(case, reason):
    trial = OralExtractionControlTrialV1(case)
    assert not trial.proposal.bindings
    assert trial.proposal.withheld == ((KIND, reason),)
    assert trial.controller.installation_count == 0
    assert trial.advance().command is None


@pytest.mark.parametrize('missing', ['body_tilt_degrees', 'support_contact', 'useful_loading', 'destabilization'])
def test_missing_current_support_never_uses_target_as_sensor(missing):
    trial, mapper, request = fresh()
    # A new acquisition at the same mapping boundary is constructed in a fresh owner.
    body = replace(trial.latest_feedback, **{missing: None})
    mapper = BodyTargetMapperV1(body.stream, (oral_extraction_capability_v1(),))
    mapper.update_feedback(body, at_tick=0)
    result = mapper.propose_oral_extraction(request, replace(trial.source, oral_feedback=body), at_tick=0)
    assert result.withheld == ((KIND, 'required_support_evidence_missing'),)


@pytest.mark.parametrize('change', [{'body_tilt_degrees':13.0}, {'support_contact':False}, {'useful_loading':.7}, {'destabilization':.3}])
def test_unsafe_support_blocks_mapping(change):
    trial, _, request = fresh()
    body = replace(trial.latest_feedback, **change)
    mapper = BodyTargetMapperV1(body.stream, (oral_extraction_capability_v1(),))
    mapper.update_feedback(body, at_tick=0)
    assert mapper.propose_oral_extraction(request, None, at_tick=0).withheld == ((KIND,'oral_support_unavailable'),)


@pytest.mark.parametrize('change,reason', [
    ({'outward_extent':.11},'extraction_target_out_of_range'),
    ({'outward_extent':.02},'extraction_endpoint_bands_overlap'),
    ({'repetitions':2, 'lease_ticks':2},'insufficient_motion_budget'),
])
def test_infeasible_pattern_is_refused_not_silently_shortened(change,reason):
    trial, mapper, request = fresh()
    proposal = mapper.propose_oral_extraction(replace(request, **change), trial.source, at_tick=0)
    assert proposal.withheld == ((KIND,reason),)
    assert not mapper.reservations(at_tick=0)


def test_unpaired_and_mislocalized_source_cannot_authorize_extraction():
    trial, mapper, request = fresh()
    result = mapper.propose_oral_extraction(request, replace(trial.source, oral_feedback=None), at_tick=0)
    assert result.withheld == ((KIND,'oral_source_body_acquisition_mismatch'),)
    with pytest.raises(ValueError):
        mapper.propose_oral_extraction(replace(request, region_id='elsewhere'), trial.source, at_tick=0)
    with pytest.raises(ValueError):
        mapper.propose_oral_extraction(replace(request, origin=replace(request.origin, stream=MotorStreamRefV1('foreign',1))),
                                      trial.source, at_tick=0)


def test_copied_stale_or_consumed_proposals_never_restore_authority():
    trial, mapper, request = fresh()
    proposal = trial.proposal
    with pytest.raises(ValueError):
        mapper.reserve(replace(proposal), execution_id='fixture',at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id='fixture',at_tick=1)
    reserved = mapper.reserve(proposal, execution_id='fixture',at_tick=0)[0]
    assert mapper.owns_reservation(reserved)
    assert not mapper.owns_reservation(replace(reserved))
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id='fixture',at_tick=0)
    mapper.cancel(reserved,at_tick=0)
    assert not mapper.owns_reservation(reserved)


def test_endpoint_refinement_cannot_change_cycles_endpoints_or_lifetime():
    trial = OralExtractionControlTrialV1()
    mapper, reservation = trial.body.motor_targets, trial.targets[0]
    for change in ({'repetitions':2}, {'outward_offset':.08}, {'lease_ticks':7}):
        changed = replace(reservation.current.target, revision=2, **change)
        with pytest.raises(ValueError):
            BodyTargetReservationV1(reservation.initial, replace(reservation.current,target=changed), reservation.capability,1)
    with pytest.raises(ValueError):
        mapper.refine(reservation,endpoint=.04,at_tick=1)


def test_scalar_completion_schema_cannot_masquerade_as_extraction():
    item = target()
    with pytest.raises(ValueError):
        BodyRelativeTargetV1('scalar',1,item.origin,KIND,item.basis,.1,.01,.2,2.0)
    assert scalar_motor_coordinate_v1(item.basis,KIND)==0.0
    assert scalar_motor_coordinate_v1(replace(item.basis,oral_extraction=None),KIND) is None
    with pytest.raises(ValueError):
        LocalTargetReportV1(CommittedBodyTargetV1(item,'execution',0),LocalTargetDispositionV1.ACHIEVED,0,'not_performed',item.basis)


def test_five_available_capabilities_do_not_authorize_concurrent_movement():
    trial, _, request = fresh()
    capabilities=(*nominal_body_capabilities_v1(),oral_body_capability_v1(),oral_closure_capability_v1(),oral_extraction_capability_v1())
    mapper=BodyTargetMapperV1(trial.world.stream,capabilities)
    mapper.update_feedback(trial.latest_feedback,at_tick=0)
    proposal=mapper.propose_oral_extraction(request,trial.source,at_tick=0)
    first=mapper.reserve(proposal,execution_id='x',at_tick=0)[0]
    body_request=BodyMovementRequestV1(request.origin,0.0,1.0)
    blocked=mapper.propose(body_request,at_tick=0)
    assert not blocked.bindings
    assert {reason for _,reason in blocked.withheld}=={'incompatible_body_resource_reserved'}
    mapper.cancel(first,at_tick=0)
    support=mapper.reserve(mapper.propose(body_request,at_tick=0),execution_id='x',at_tick=0)
    assert len(support)==2
    assert mapper.propose_oral_extraction(request,trial.source,at_tick=0).withheld==((KIND,'incompatible_body_resource_reserved'),)


@pytest.mark.parametrize('kind', ['closure', 'reach'])
def test_oral_conflicts_are_checked_in_both_directions(kind):
    trial, _, request=fresh()
    mapper=BodyTargetMapperV1(trial.world.stream,(oral_body_capability_v1(),oral_closure_capability_v1(),oral_extraction_capability_v1()))
    mapper.update_feedback(trial.latest_feedback,at_tick=0)
    if kind=='closure':
        other=OralClosureRequestV1(request.origin,request.source_map_ref,request.region_id,.6)
        make=lambda: mapper.propose_oral_closure(other,trial.source,at_tick=0)
    else:
        other=OralReachRequestV1(request.origin,request.source_map_ref,request.region_id)
        make=lambda: mapper.propose_oral_reach(other,trial.source,at_tick=0)
    earlier=mapper.reserve(make(),execution_id='x',at_tick=0)
    assert earlier
    assert not mapper.propose_oral_extraction(request,trial.source,at_tick=0).bindings
    mapper.cancel(earlier[0],at_tick=0)
    mapper.reserve(mapper.propose_oral_extraction(request,trial.source,at_tick=0),execution_id='x',at_tick=0)
    assert not make().bindings


@pytest.mark.parametrize('mutation', ['empty','duplicate','reverse','wrong_stream','outside_tolerance','unsealed','after_lease','too_many'])
def test_achievement_requires_an_original_ordered_sequence(mutation):
    result=run_oral_extraction_control_v1('twice')
    report=result.steps[-1].reports[0]
    rows=report.extraction_confirmations
    changed=rows
    if mutation=='empty': changed=()
    elif mutation=='duplicate': changed=(rows[0],rows[0],*rows[2:])
    elif mutation=='reverse': changed=rows[::-1]
    elif mutation=='too_many': changed=(*rows,rows[-1])
    else:
        one=rows[-1]
        if mutation=='wrong_stream': one=replace(one,stream=MotorStreamRefV1('wrong',1))
        elif mutation=='outside_tolerance': one=replace(one,oral_extraction=replace(one.oral_extraction,stroke=.3))
        elif mutation=='unsealed': one=replace(one,oral_seal=replace(one.oral_seal,sealed=False))
        elif mutation=='after_lease': one=replace(one,sample_id=20,event_tick=9,available_tick=9,
                                                oral_extraction=replace(one.oral_extraction,interval_start_tick=8))
        changed=(*rows[:-1],one)
    with pytest.raises((TypeError,ValueError)):
        replace(report, extraction_confirmations=changed, feedback=changed[-1] if changed else report.feedback, reported_tick=11)


def test_capability_binding_rejects_foreign_axis_and_changed_bounds():
    item=target()
    with pytest.raises(TypeError):
        BodyTargetBindingV1(item,oral_closure_capability_v1())
    for changes in ({'maximum_step':.05},{'maximum_rate':1.0},{'maximum_excursion':.15},{'tolerance':.005}):
        with pytest.raises(ValueError):
            BodyTargetBindingV1(item,replace(oral_extraction_capability_v1(),**changes))
    packet=CommittedBodyTargetV1(item,'execution',0).as_dict()
    assert packet['restores_live_authority'] is False
    assert json.loads(json.dumps(packet))==packet
