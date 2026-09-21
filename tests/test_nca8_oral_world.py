"""Independent oral physics and tactile sensing, below task/target authority."""

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, PlanarDriveV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, MotorWorldPerturbationV1,
    OralWorldStateV1, OralWorldProfileV1, OralWorldPerturbationV1,
    PlanarObjectV1, PlanarWorldProfileV1, PlanarPerturbationV1,
)

STREAM = MotorStreamRefV1("oral_world_fixture", 1)


def world(*, oral=None, planar=None, physical=None):
    return MotorWorldV1(STREAM, physical or MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0)),
                        planar_profile=planar or PlanarWorldProfileV1(frame_id="scene_xy:oral_world"),
                        oral_profile=oral or OralWorldProfileV1(surfaces=(PlanarObjectV1("tactile_surface", (0.1, 0.0), 0.004),)))


def snapshot(value):
    return (value.tick, value.body, value.planar_body, value.oral_body, value.observe(), value.pending_feedback_count)


@pytest.mark.parametrize("drive,expected", [(-1.0, 0.075), (0.0, 0.1), (0.5, 0.1125), (1.0, 0.125)])
def test_drive_integrates_metres_at_declared_finite_rate(drive, expected):
    value = world(oral=OralWorldProfileV1(initial_extension_metres=0.1))
    body_before = value.body
    value.step(MotorCommandV1(STREAM, 1, 0, oral_drive=drive))
    assert value.oral_body.extension_metres == pytest.approx(expected)
    assert value.body == body_before and value.tick == 1
    assert value.observe().event_tick == 0
    due = value.step(None)
    assert due[0].event_tick == 1 and due[0].available_tick == 2
    assert due[0].oral.extension_metres == pytest.approx(expected)
    assert MotorFeedbackV1.from_dict(due[0].as_dict()) == due[0]


@pytest.mark.parametrize("initial,drive,expected", [(0.0, -1.0, 0.0), (0.35, 1.0, 0.35)])
def test_physical_saturation_does_not_promise_a_task_result(initial, drive, expected):
    value = world(oral=OralWorldProfileV1(initial_extension_metres=initial))
    for tick in range(5):
        value.step(MotorCommandV1(STREAM, tick + 1, tick, oral_drive=drive))
    assert value.oral_body.extension_metres == expected and value.oral_body.contact is False


@pytest.mark.parametrize("drive", [0.0, 1.0])
def test_no_oral_profile_refuses_even_neutral_v3_before_state_changes(drive):
    value = MotorWorldV1(STREAM)
    before = (value.tick, value.body, value.observe())
    with pytest.raises(ValueError, match="oral"):
        value.step(MotorCommandV1(STREAM, 1, 0, oral_drive=drive))
    assert before == (value.tick, value.body, value.observe())
    value.step(None)
    assert value.tick == 1 and value.observe().as_dict()["schema"] == "body_motor_feedback_v1"


def test_oral_profile_needs_independent_planar_body_frame():
    with pytest.raises(TypeError):
        MotorWorldV1(STREAM, oral_profile=OralWorldProfileV1())


@pytest.mark.parametrize("contact_available,extension_available", [(True, True), (False, True), (True, False), (False, False)])
def test_valid_no_touch_and_unknown_channels_remain_distinct(contact_available, extension_available):
    value = world(oral=OralWorldProfileV1(contact_available=contact_available, extension_available=extension_available))
    reading = value.observe().oral
    assert reading.contact is (False if contact_available else None)
    assert reading.extension_metres == (0.0 if extension_available else None)
    value.step(MotorCommandV1(STREAM, 1, 0, oral_drive=1.0))
    assert value.oral_body.extension_metres == pytest.approx(0.025)


@pytest.mark.parametrize("surface,expected", [((0.10, 0.0), True), ((0.10, 0.02), False), ((0.20, 0.0), False)])
def test_touch_comes_from_independent_physical_tip_overlap(surface, expected):
    value = world(oral=OralWorldProfileV1(initial_extension_metres=0.1,
                                        surfaces=(PlanarObjectV1("anything_not_a_maternal_answer", surface, 0.004),)))
    assert value.oral_body.contact is expected and value.observe().oral.contact is expected


def test_sensor_disk_is_not_hidden_rigid_collision_latch_or_success():
    value = world()
    contacts = []
    for tick in range(6):
        value.step(MotorCommandV1(STREAM, tick + 1, tick, oral_drive=1.0))
        contacts.append(value.oral_body.contact)
    assert contacts == [False, False, False, True, False, False]
    assert value.oral_body.extension_metres == pytest.approx(0.15)
    assert not {"latch", "milk", "nourishment", "task", "target", "success"} & set(value.observe().as_dict())


def test_body_heading_and_translation_move_tip_without_resetting_reach():
    rotated = world(planar=PlanarWorldProfileV1(frame_id="scene_xy:oral_world", initial_heading=90.0),
                    oral=OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(PlanarObjectV1("touch", (0.0, 0.1), 0.004),)))
    assert rotated.observe().oral.contact is True
    rotated.step(MotorCommandV1(STREAM, 1, 0, translation=PlanarDriveV1(1.0, 0.0)))
    assert rotated.oral_body.extension_metres == 0.1
    assert rotated.oral_body.contact is False
    assert rotated.planar_body.position == pytest.approx((0.0, 0.05))


@pytest.mark.parametrize("enabled", [True, False])
def test_fixed_oral_forcing_acts_at_physical_time_even_without_command_or_motor(enabled):
    oral = OralWorldProfileV1(motor_enabled=enabled, perturbations=(OralWorldPerturbationV1(1, 2, 0.4),))
    value = world(oral=oral)
    value.step(None)
    assert value.oral_body.extension_metres == 0.0
    value.step(None)
    assert value.oral_body.extension_metres == pytest.approx(0.02)
    value.step(None)
    assert value.oral_body.extension_metres == pytest.approx(0.02)


@pytest.mark.parametrize("body,surface,enabled", [(MotorBodyStateV1(0.0, 1.0), True, False),
                                                 (MotorBodyStateV1(0.0, 1.0), False, True),
                                                 (MotorBodyStateV1(30.0, 1.0), True, True),
                                                 (MotorBodyStateV1(0.0, 0.2), True, True)])
def test_motor_competence_is_conditional_not_guaranteed_feeding(body, surface, enabled):
    value = world(physical=MotorWorldProfileV1(initial_body=body, surface_present=surface), oral=OralWorldProfileV1(motor_enabled=enabled))
    value.step(MotorCommandV1(STREAM, 1, 0, oral_drive=1.0))
    assert value.oral_body.extension_metres == 0.0


def test_dropout_leaves_real_touch_unobserved_without_fabricating_no_touch():
    profile = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0),
                                 perturbations=(MotorWorldPerturbationV1(0, 8, drop_feedback=True),))
    value = world(physical=profile)
    first = value.observe()
    for tick in range(4):
        assert value.step(MotorCommandV1(STREAM, tick + 1, tick, oral_drive=1.0)) == ()
    assert value.oral_body.contact is True
    assert value.observe() is first and value.observe().event_tick == 0
    assert value.pending_feedback_count == 0


def test_reset_clears_oral_state_and_inflight_sensing_and_rejects_old_command():
    value = world()
    old = MotorCommandV1(STREAM, 1, 0, oral_drive=1.0)
    value.step(old)
    assert value.pending_feedback_count == 1
    reset = value.reset()
    assert reset.stream.generation == 2 and reset.oral.extension_metres == 0.0
    assert value.tick == 0 and value.pending_feedback_count == 0
    before = snapshot(value)
    with pytest.raises(ValueError):
        value.step(old)
    assert snapshot(value) == before


@pytest.mark.parametrize("change", [{"issued_tick": 1}, {"stream": MotorStreamRefV1("other", 1)},
                                    {"stream": MotorStreamRefV1(STREAM.stream_id, 2)}])
def test_wrong_time_or_generation_cannot_change_any_physical_facet(change):
    value = world()
    before = snapshot(value)
    command = replace(MotorCommandV1(STREAM, 1, 0, oral_drive=1.0), **change)
    with pytest.raises(ValueError):
        value.step(command)
    assert snapshot(value) == before


@pytest.mark.parametrize("change", [{"initial_extension_metres": True}, {"initial_extension_metres": 0.36},
                                    {"motor_enabled": 1}, {"contact_available": 0}, {"extension_available": "yes"},
                                    {"surfaces": []}, {"perturbations": []},
                                    {"surfaces": (PlanarObjectV1("too_large", (0, 0), 0.1),)},
                                    {"surfaces": (PlanarObjectV1("zero", (0, 0), 0),)}])
def test_profile_refuses_invalid_units_types_and_surface_contracts(change):
    with pytest.raises((TypeError, ValueError)):
        OralWorldProfileV1(**change)


@pytest.mark.parametrize("args", [(1, 1, 0.0), (-1, 2, 0.0), (True, 2, 0.0), (1, 2, 1.01), (1, 2, float("nan")), (1, 2, True)])
def test_perturbation_schedule_is_finite_typed_and_task_independent(args):
    with pytest.raises((TypeError, ValueError)):
        OralWorldPerturbationV1(*args)


def test_profile_rejects_duplicate_surfaces_overlapping_forcing_and_excess_retention():
    surface = PlanarObjectV1("one", (0.1, 0.0), 0.004)
    for kwargs in ({"surfaces": (surface, surface)},
                   {"surfaces": tuple(replace(surface, region_id=str(i)) for i in range(9))},
                   {"perturbations": (OralWorldPerturbationV1(1, 3, 0.1), OralWorldPerturbationV1(2, 4, -0.1))}):
        with pytest.raises(ValueError):
            OralWorldProfileV1(**kwargs)


def test_fixed_provider_replay_is_exact_and_exports_do_not_mutate_it():
    values = [world(), world()]
    for tick in range(12):
        for value in values:
            value.step(MotorCommandV1(STREAM, tick + 1, tick, oral_drive=1.0 if tick < 4 else 0.0))
            json.dumps(value.observe().as_dict(), allow_nan=False)
        assert snapshot(values[0]) == snapshot(values[1])
    assert values[0].oral_body.contact
