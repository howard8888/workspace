"""Neutral translation wire/provider tests: no cognitive fixture supplies motion."""
from dataclasses import replace
import inspect
import math

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, PlanarDriveV1, PlanarFeedbackV1
from cca8_support_world import (
    MotorWorldV1, MotorWorldProfileV1, MotorBodyStateV1, PlanarWorldProfileV1, PlanarObjectV1, PlanarPerturbationV1,
)


def world(**changes):
    return MotorWorldV1(MotorStreamRefV1('wire_body', 1), MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1)),
                        planar_profile=PlanarWorldProfileV1(**changes))


def drive(plant, forward=1.0, left=0.0):
    return MotorCommandV1(plant.stream, plant.tick + 1, plant.tick, translation=PlanarDriveV1(forward, left))


@pytest.mark.parametrize('values', [(True, 0), (0, False), (float('nan'), 0), (0, float('inf')), (1.1, 0), (1, 1), ('1', 0)])
def test_drive_requires_bounded_euclidean_vector(values):
    with pytest.raises((ValueError, TypeError)):
        PlanarDriveV1(*values)


@pytest.mark.parametrize('change', [{'position': [0, 0]}, {'position': (True, 0)}, {'position': (10001, 0)},
                                   {'heading_degrees': float('nan')}, {'heading_degrees': 181},
                                   {'obstacle_contact': 1}, {'frame_id': 'body'}, {'frame_id': 'scene_xy:'}])
def test_planar_feedback_cannot_invent_valid_geometry(change):
    with pytest.raises((ValueError, TypeError)):
        replace(PlanarFeedbackV1('scene_xy:lab', (0, 0), 0, False), **change)


def test_wire_v1_unchanged_and_v2_companion_explicit_and_detached():
    plant = world()
    v2 = plant.observe()
    packet = v2.as_dict()
    assert packet['schema'] == 'body_motor_feedback_v2'
    decoded = MotorFeedbackV1.from_dict(packet)
    assert decoded == v2 and decoded is not v2
    packet['planar']['position'][0] = 9
    assert v2.planar.position == (0, 0)
    v1 = replace(v2, planar=None)
    assert v1.as_dict()['schema'] == 'body_motor_feedback_v1' and 'planar' not in v1.as_dict()
    assert MotorFeedbackV1.from_dict(v1.as_dict()) == v1
    command = drive(plant)
    assert MotorCommandV1.from_dict(command.as_dict()) == command
    assert command.as_dict()['schema'] == 'body_motor_command_v2'
    old = replace(command, translation=None)
    assert old.as_dict()['schema'] == 'body_motor_command_v1' and 'translation' not in old.as_dict()
    assert set(inspect.signature(PlanarDriveV1).parameters) == {'forward', 'left'}


@pytest.mark.parametrize('kind', ['command', 'feedback'])
@pytest.mark.parametrize('tamper', ['old_schema', 'unknown', 'missing'])
def test_wire_versions_cannot_silently_drop_or_smuggle_planar_payload(kind, tamper):
    plant = world()
    record = drive(plant) if kind == 'command' else plant.observe()
    payload = record.as_dict()
    field = 'translation' if kind == 'command' else 'planar'
    if tamper == 'old_schema':
        payload['schema'] = payload['schema'].replace('_v2', '_v1')
    elif tamper == 'unknown':
        payload[field]['desired_target'] = [2, 1]
    else:
        del payload[field]
    with pytest.raises((ValueError, TypeError)):
        type(record).from_dict(payload)


@pytest.mark.parametrize('heading', [-180, -90, 0, 45, 90, 180])
@pytest.mark.parametrize('movement', [(1.0, 0.0), (0.0, -1.0), (0.6, 0.8)])
def test_actual_heading_controls_signed_increment_not_hidden_destination(heading, movement):
    plant = world(initial_heading=heading, objects=(PlanarObjectV1('unrelated', (-40, 31)),))
    before = plant.observe()
    assert plant.step(drive(plant, *movement)) == ()
    a = math.radians(heading)
    expected = (0.05*(math.cos(a)*movement[0]-math.sin(a)*movement[1]),
                0.05*(math.sin(a)*movement[0]+math.cos(a)*movement[1]))
    assert plant.planar_body.position == pytest.approx(expected)
    assert plant.observe() == before  # Post-step sensing is not available early.
    delivered = plant.step(None)
    assert delivered[0].event_tick == 1 and delivered[0].available_tick == 2
    assert delivered[0].planar.position == pytest.approx(expected)


def test_zero_and_none_are_neutral_but_forcing_still_moves_body():
    profile = {'perturbations': (PlanarPerturbationV1(0, 3, velocity=(0, 1)),)}
    zero, none = world(**profile), world(**profile)
    for _ in range(3):
        assert zero.step(drive(zero, 0, 0)) == none.step(None)
    assert zero.planar_body.position == pytest.approx((0, .15))


def test_old_provider_refuses_new_drive_before_any_effect():
    plant = MotorWorldV1(MotorStreamRefV1('wire_body', 1))
    before = plant.body, plant.observe(), plant.tick
    with pytest.raises(ValueError):
        plant.step(drive(plant))
    assert (plant.body, plant.observe(), plant.tick) == before


@pytest.mark.parametrize('wrong', ['stream', 'tick', 'id'])
def test_bad_command_rejected_before_body_or_clock_change(wrong):
    plant = world()
    plant.step(drive(plant))
    command = drive(plant)
    command = replace(command, **({'stream': MotorStreamRefV1('foreign',1)} if wrong == 'stream'
                                 else {'issued_tick': 5} if wrong == 'tick' else {'command_id': 1}))
    before = plant.tick, plant.body, plant.planar_body, plant.observe()
    with pytest.raises(ValueError):
        plant.step(command)
    assert (plant.tick, plant.body, plant.planar_body, plant.observe()) == before


def test_swept_contact_prevents_tunnelling_and_valid_contact_is_not_dropout():
    plant = world(objects=(PlanarObjectV1('disk', (.025, 0), .005),))
    plant.step(drive(plant))
    assert plant.planar_body.position == pytest.approx((.02, 0))
    assert plant.planar_body.obstacle_contact
    reading = plant.step(drive(plant))[0]
    assert reading.planar.obstacle_contact is True
    assert plant.planar_body.position == pytest.approx((.02, 0))
    plant.step(drive(plant, -1, 0))
    assert not plant.planar_body.obstacle_contact  # Fixed lower provider can leave; no route planner.


def test_blocked_drive_does_not_disable_external_forcing():
    plant = world(motor_enabled=False, perturbations=(PlanarPerturbationV1(0, 1, velocity=(0, 1)),))
    plant.step(drive(plant))
    assert plant.planar_body.position == pytest.approx((0, .05))


def test_support_traction_is_observed_geometry_not_a_task_label():
    profile = MotorWorldProfileV1(initial_body=MotorBodyStateV1(30, .4))
    plant = MotorWorldV1(MotorStreamRefV1('wire_body', 1), profile, planar_profile=PlanarWorldProfileV1())
    plant.step(drive(plant))
    assert plant.planar_body.position == (0, 0)


def test_visual_surface_uses_original_delivered_event_and_fixed_scene():
    plant = world(objects=(PlanarObjectV1('region_1', (2, 1)),))
    before = plant.visual_surface()
    plant.step(drive(plant))
    assert plant.visual_surface() == before
    plant.step(None)
    surface = plant.visual_surface()
    assert surface['anchor']['x'] == .05
    assert surface['objects'][0]['x'] == 2
    surface['objects'][0]['x'] = 99
    assert plant.visual_surface()['objects'][0]['x'] == 2


def test_reset_discards_planar_sensing_and_old_commands():
    plant = world(initial_heading=90)
    plant.step(drive(plant))
    old = drive(plant)
    fresh = plant.reset()
    assert fresh.stream.generation == 2 and fresh.planar.position == (0, 0)
    assert plant.pending_feedback_count == 0
    with pytest.raises(ValueError):
        plant.step(old)


@pytest.mark.parametrize('options', [dict(initial_position=[0,0]), dict(motor_enabled=1), dict(initial_heading=True),
                                     dict(objects=(PlanarObjectV1('same',(1,0)),PlanarObjectV1('same',(2,0)))),
                                     dict(objects=(PlanarObjectV1('inside',(0,0),.1),)), dict(vision_available='false')])
def test_invalid_physical_profile_cannot_start_a_body(options):
    with pytest.raises((ValueError, TypeError)):
        world(**options)
