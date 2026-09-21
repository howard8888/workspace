"""Translation across the real source/selector/target/handoff/lower boundaries."""
from dataclasses import FrozenInstanceError, replace
import math

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_handoff import Nca8MotorEnvelopeV1
from nca8_hierarchy import IntegratedRightingCoreV1
from nca8_prediction import VisualTranslationPreviewV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, LocalTargetDispositionV1, SensorimotorTargetKindV1
from nca8_translation import TranslationFixtureV1, TranslationApplicationV1
from nca8_translation_demo import create_translation_trial_v1, run_translation_v1


def target(result):
    item = result.reservations[0].current.target
    assert isinstance(item, BodyTranslationTargetV1)
    return item


def test_same_a_to_f_core_precedes_installation_and_physical_effect():
    trial = create_translation_trial_v1('heading_0')
    before = trial.observer_planar_body
    first = trial.focal_step()
    assert trial.tick == 0 and trial.observer_planar_body == before
    assert first.scheduler.cycle_id == 1
    assert first.commitment.selected_primitive_id == 'fixture:translation'
    assert first.commitment.task_action == 'TRANSLATE_TO_VISIBLE_REGION'
    assert trial.handoff_consumptions == trial.controller.installation_count == 1
    assert trial.core.handoff.receipt.disposition == 'consumed'
    app = first.calculation.navigation.application
    assert isinstance(app, TranslationApplicationV1)
    assert trial.core.cognition.prediction.current_visual_preview is app.projection
    assert trial.core.cognition.prediction.current_support_preview is None
    names = [event.channel for event in trial.core.trace.snapshot()]
    assert names.index('hierarchy_commit') < names.index('hierarchy_handoff') < names.index('hierarchy_close')
    assert names.index('hierarchy_close') < names.index('hierarchy_consumed') < names.index('hierarchy_installed')
    source = first.visual_source
    trial.advance_lower()
    assert trial.observer_planar_body != before
    assert source.self_position.x == source.self_position.y == 0  # Frozen source not secretly advanced.
    assert app.projection.predicted_self.x > 0


def test_first_local_drive_does_not_contain_target_identity_or_world_destination():
    trial = create_translation_trial_v1('heading_0')
    trial.focal_step()
    step = trial.advance_lower()
    assert set(step.command.translation.as_dict()) == {'forward', 'left'}
    assert step.command.orientation_drive == step.command.extension_drive == 0
    assert step.predictions and all(isinstance(p.expected_coordinate, tuple) for p in step.predictions)


def test_fresh_returned_visual_evidence_changes_configuration_not_durable_identity():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    returned = trial.focal_step()
    assert first.visual_source.source_map_ref == returned.visual_source.source_map_ref
    assert returned.visual_source.self_position.x > first.visual_source.self_position.x
    assert returned.visual_source.guidance[0].position == first.visual_source.guidance[0].position
    assert returned.visual_source.event_tick == returned.calculation.source.motor_support.feedback.event_tick == 3
    assert returned.local_reports[0].feedback.event_tick == 2  # Prior local calculation; not another acquisition.
    assert returned.commitment.focal_operation_id is None and returned.commitment.pnm_id is None
    assert trial.controller.installation_count == 1  # No hidden following loop.


@pytest.mark.parametrize('field,value', [('offset',(float('nan'),0)),('offset',[.1,0]),('offset',(.4,0)),
                                        ('lease_ticks',9),('lease_ticks',True),('max_corrections',3),
                                        ('max_rate',1.1),('tolerance',0),('revision',0)])
def test_vector_target_validates_bounds_without_repair(field,value):
    original = target(create_translation_trial_v1('heading_0').focal_step())
    with pytest.raises((ValueError,TypeError)):
        replace(original, **{field:value})


def test_anchor_does_not_accumulate_offsets_as_body_and_heading_change():
    trial = create_translation_trial_v1('yaw_disturbed')
    first = trial.focal_step()
    original = target(first)
    endpoint = original.endpoint
    for _ in range(7):
        trial.advance_lower()
        assert original.endpoint == endpoint
    assert trial.observer_planar_body.heading_degrees == 18
    assert trial.observer_planar_body.position == pytest.approx(endpoint)
    with pytest.raises(FrozenInstanceError):
        original.offset = (0,0)


def test_narrowed_target_does_not_rewrite_source_or_preceding_forecast():
    result = run_translation_v1('narrowed')
    first = result.cycles[0]
    mapped = target(first)
    projected = first.calculation.navigation.application.projection
    assert math.hypot(mapped.offset[0], mapped.offset[1]) == pytest.approx(.1)
    assert math.hypot(projected.predicted_self.x, projected.predicted_self.y) == pytest.approx(.25)
    assert first.visual_source.self_position.x == 0
    assert math.hypot(*result.physical_samples[-1].position) == pytest.approx(.1)
    assert result.local_steps[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED


def test_wrong_mapping_is_really_consumed_and_local_success_is_not_task_success():
    normal, reversed_run = run_translation_v1(), run_translation_v1('mapping_reversed')
    original = normal.cycles[0].calculation.navigation.application
    reversed_app = reversed_run.cycles[0].calculation.navigation.application
    assert original.contribution == reversed_app.contribution
    assert original.projection == reversed_app.projection
    assert reversed_run.physical_samples[-1].position == pytest.approx(tuple(-v for v in normal.physical_samples[-1].position))
    assert reversed_run.local_steps[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert not reversed_run.as_dict()['maternal_identity_or_following']


def test_bodymap_refuses_scalar_refinement_of_a_translation_target():
    trial = create_translation_trial_v1('heading_0')
    result = trial.focal_step()
    trial.advance_lower()
    with pytest.raises(ValueError, match='translation'):
        trial.core.cognition.mapper.refine(result.reservations[0], endpoint=.1, at_tick=1)


def test_original_consumed_grant_cannot_install_twice_or_through_a_copied_receipt():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    with pytest.raises(RuntimeError):
        trial.core.handoff.consume_motor(replace(first.receipt))
    with pytest.raises(RuntimeError):
        trial.core.handoff.claim_motor_targets()
    assert trial.tick == 0 and trial.controller.installation_count == 1


def test_installation_attempt_failure_stays_spent_and_stops_before_motion(monkeypatch):
    trial = create_translation_trial_v1('heading_0')
    def fail(_reservations, _tick):
        raise ValueError('installation fault')
    monkeypatch.setattr(trial.controller, '_prepare_installation', fail)
    with pytest.raises(ValueError):
        trial.focal_step()
    assert trial.stopped and trial.tick == 0
    assert trial.core.handoff.receipt.disposition == 'consumed'
    with pytest.raises(RuntimeError):
        trial.advance_lower()


def test_physical_failure_after_motion_is_not_retried(monkeypatch):
    trial = create_translation_trial_v1('heading_0')
    trial.focal_step()
    real_step = trial._world.step
    def fail(command):
        real_step(command)
        raise RuntimeError('return failed after physical effect')
    monkeypatch.setattr(trial._world, 'step', fail)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1 and trial.observer_planar_body.position[0] > 0 and trial.stopped
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.tick == 1


def test_future_visual_sidecar_cannot_cross_freeze_or_create_an_application():
    trial = create_translation_trial_v1('heading_0')
    observation = admit_motor_visual_surface_v1(trial._world.visual_surface(), trial.latest_feedback)
    future = replace(observation, available_tick=1)
    with pytest.raises(ValueError):
        trial.core.run_cycle(trial.latest_feedback, cutoff_tick=0, visual_observation=future)
    assert trial.core.scheduler.last_completed_cycle == 0 and trial.controller.installation_count == 0
    trial.focal_step()  # Pre-admission validation failed atomically, not a partial core.


def test_visual_and_body_source_can_disagree_without_pnm_becoming_body_truth():
    trial = create_translation_trial_v1('heading_0')
    observation = admit_motor_visual_surface_v1(trial._world.visual_surface(), trial.latest_feedback)
    from cca8_navmap_kernel import NavPointV1
    shifted = replace(observation, self_position=NavPointV1(1,0))
    result = trial.core.run_cycle(trial.latest_feedback, cutoff_tick=0, visual_observation=shifted)
    assert result.visual_source.self_position.x == 1
    assert target(result).basis.planar.position == (0,0)
    assert target(result).endpoint != (result.receipt.dispatch.motor.projection.predicted_self.x,
                                       result.receipt.dispatch.motor.projection.predicted_self.y)


def test_wrong_projection_type_or_frame_cannot_authorize_a_target():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    motor = first.receipt.dispatch.motor
    with pytest.raises(TypeError):
        replace(motor, projection={})
    shifted_basis = replace(motor.projection.basis, frame_id='scene_xy:other')
    bad_projection = replace(motor.projection, basis=shifted_basis)
    with pytest.raises(ValueError):
        replace(motor, projection=bad_projection)
    with pytest.raises(ValueError):
        Nca8MotorEnvelopeV1(motor.stream,motor.cutoff_tick,None,motor.targets)


def test_observed_support_loss_stops_translation_before_next_focal_choice():
    trial = create_translation_trial_v1('support_loss')
    trial.focal_step()
    steps = [trial.advance_lower() for _ in range(4)]
    assert steps[0].command.translation is not None
    assert steps[3].command is None
    assert trial.core.scheduler.last_completed_cycle == 1
    assert steps[3].reports[0].disposition in {LocalTargetDispositionV1.INTERRUPTED,LocalTargetDispositionV1.BLOCKED}


def test_support_source_can_win_without_installing_incompatible_translation():
    trial = create_translation_trial_v1('support_priority')
    first = trial.focal_step()
    assert first.commitment.selected_primitive_id == 'ip:righting'
    assert all(x.current.target.kind is not SensorimotorTargetKindV1.PLANAR_TRANSLATION for x in first.reservations)
    assert first.visual_source.evidence_current  # Not achieved by disabling vision.


def test_reset_revokes_old_vector_permissions_and_starts_fresh_supplied_fixture():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    trial.advance_lower()
    old_controller, old_core = trial.controller, trial.core
    trial.reset()
    assert trial.tick == 0 and trial.observer_planar_body.position == (0,0)
    assert old_controller.fault and old_core.fault
    with pytest.raises(ValueError):
        trial.core.cognition.mapper.validate_reservation(first.reservations[0],at_tick=0)
    new = trial.focal_step()
    assert new.commitment.task_action == 'TRANSLATE_TO_VISIBLE_REGION'
    assert target(new).origin.stream.generation == 2


def test_righting_outcome_learner_cannot_be_repurposed_for_visual_claims():
    with pytest.raises(ValueError):
        IntegratedRightingCoreV1(MotorStreamRefV1('test',1),translation_fixture=TranslationFixtureV1(),task_outcomes_enabled=True)


@pytest.mark.parametrize('options',[{'region_id':''},{'maximum_step_metres':.3},{'maximum_step_metres':True},
                                    {'stand_off_metres':float('inf')},{'spatial_enabled':1},{'recognition_enabled':None}])
def test_fixture_has_frozen_finite_scope(options):
    with pytest.raises((ValueError,TypeError)):
        TranslationFixtureV1(**options)


def test_translation_reservation_excludes_incompatible_scalar_work_without_replacement():
    from nca8_body_targets import BodyMovementRequestV1
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    original = target(first)
    mapper = trial.core.cognition.mapper
    proposal = mapper.propose(BodyMovementRequestV1(original.origin, desired_extension=.8), at_tick=0)
    assert not proposal.bindings
    assert proposal.withheld == ((SensorimotorTargetKindV1.SUPPORT_EXTENSION, 'incompatible_body_resource_reserved'),)
    assert mapper.reservations(at_tick=0) == first.reservations
    assert trial.controller.installation_count == 1


def test_copied_vector_reservation_never_becomes_owned_permission():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    mapper = trial.core.cognition.mapper
    with pytest.raises(ValueError, match='owned'):
        mapper.validate_reservation(replace(first.reservations[0]), at_tick=0)
    assert trial.controller.installation_count == 1 and trial.tick == 0


def test_registration_off_keeps_projection_integrity_and_actual_motor_execution():
    from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1, PlanarWorldProfileV1, PlanarObjectV1
    from nca8_body_targets import BodyTranslationCapabilityV1
    from nca8_hierarchy import IntegratedRightingTrialV1
    options = dict(
        physical_profile=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0,1)),
        planar_profile=PlanarWorldProfileV1(objects=(PlanarObjectV1('region_1',(2,1)),)),
        translation_fixture=TranslationFixtureV1(), translation_capability=BodyTranslationCapabilityV1(),
    )
    on = IntegratedRightingTrialV1(**options)
    off = IntegratedRightingTrialV1(**options, task_pnm_consumer_enabled=False)
    first_on, first_off = on.focal_step(), off.focal_step()
    assert first_on.commitment == first_off.commitment
    assert first_on.receipt.dispatch.motor.projection == first_off.receipt.dispatch.motor.projection
    assert on.core.cognition.prediction.current_visual_preview is not None
    assert off.core.cognition.prediction.current_visual_preview is None
    for _ in range(12):
        assert on.advance_lower() == off.advance_lower()
        assert on.observer_planar_body == off.observer_planar_body


def test_losing_visual_focus_does_not_renew_or_invent_another_installed_target():
    trial = create_translation_trial_v1('heading_0')
    first = trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    no_vision = trial.focal_step(visual_input_enabled=False)
    assert not no_vision.visual_source.evidence_current
    assert no_vision.commitment.selected_primitive_id is None
    assert target(first).lease_ticks == 8
    for _ in range(8):
        trial.advance_lower()
    assert trial.controller.installation_count == 1
    assert trial.controller.reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert trial.controller.reports[0].committed_target.expires_at_tick == 8


@pytest.mark.parametrize('offset',[(.5,0),(-.5,0)])
def test_visual_projection_cannot_enlarge_its_original_quarter_metre_scope(offset):
    from cca8_navmap_kernel import NavPointV1
    first = create_translation_trial_v1('heading_0').focal_step()
    preview = first.calculation.navigation.application.projection
    with pytest.raises(ValueError):
        replace(preview, predicted_self=NavPointV1(*offset))
