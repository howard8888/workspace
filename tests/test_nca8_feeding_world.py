"""Ranged detail uses original physical acquisition; no target/stage or feeding physics."""
from dataclasses import asdict, replace
import math

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorStreamRefV1, PlanarDriveV1
from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, PlanarDetailObjectV1, PlanarObjectV1, PlanarWorldProfileV1
from nca8_adapters import admit_motor_visual_surface_v1

STREAM = MotorStreamRefV1("detail_world", 1)


def world(*, position=(0, 0), detail_position=(.4, 0), **kwargs):
    planar = PlanarWorldProfileV1(initial_position=position, objects=(PlanarObjectV1("region_1", (2, 1)),
                                 PlanarDetailObjectV1("region_2", detail_position)), **kwargs)
    return MotorWorldV1(STREAM, MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1)), planar_profile=planar)


def regions(provider, feedback=None):
    return [item["entity"] for item in provider.visual_surface(feedback=feedback)["objects"]]


@pytest.mark.parametrize("field,value", [
    ("descriptor", None), ("descriptor", "nipple:found"), ("descriptor", "latched"), ("descriptor", 1),
    ("visibility_radius", 0), ("visibility_radius", -1), ("visibility_radius", True), ("visibility_radius", math.inf),
    ("visibility_radius", math.nan), ("visibility_radius", 100.1), ("radius", -1), ("position", (math.nan, 0)),
])
def test_invalid_detail_profile_never_becomes_sensor_evidence(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(PlanarDetailObjectV1("region_2", (1.82, 1)), **{field: value})


@pytest.mark.parametrize("descriptor", ["object", "landmark", "hazard", "social", "feeding"])
def test_detail_uses_only_existing_surface_category_vocabulary(descriptor):
    assert PlanarDetailObjectV1("region_2", (0, 0), descriptor=descriptor).descriptor == descriptor


def test_original_object_schema_and_unlimited_visual_behavior_are_preserved():
    item = PlanarObjectV1("region_1", (20, 10))
    assert asdict(item) == {"region_id": "region_1", "position": (20., 10.), "radius": 0.}
    provider = world(position=(-10, -10))
    assert regions(provider) == ["region_1"]


@pytest.mark.parametrize("distance,visible", [(.399, True), (.4, True), (.40001, False)])
def test_visibility_uses_declared_range_without_maternal_or_task_status(distance, visible):
    provider = world(detail_position=(distance, 0))
    assert ("region_2" in regions(provider)) is visible
    assert provider.tick == 0


def test_returning_detail_is_whitelisted_under_original_sample_and_contains_no_outcome_flags():
    provider = world()
    surface = provider.visual_surface()
    observation = admit_motor_visual_surface_v1(surface, provider.observe())
    assert observation.detections[1].descriptor == "feeding"
    assert observation.detections[1].position.x == .4
    assert observation.event_tick == provider.observe().event_tick == 0
    assert observation.sample_id == provider.observe().sample_id
    assert set(surface["objects"][1]) == {"entity", "kind", "x", "y"}
    assert not {"parent", "part_of", "found", "latched", "milk", "success", "stage"} & surface["objects"][1].keys()


def test_missing_self_localization_cannot_reveal_ranged_detail():
    provider = world(position_available=False)
    assert provider.observe().planar.position is None
    assert regions(provider) == ["region_1"]


def test_visibility_uses_delivered_event_not_newer_body_and_historical_read_stays_old():
    provider = world(detail_position=(.43, 0))
    initial = provider.observe()
    command = MotorCommandV1(STREAM, 1, 0, 0, 0, translation=PlanarDriveV1(1, 0))
    provider.step(command)
    assert provider.planar_body.position[0] > .03  # Physical body is inside range now.
    assert provider.observe() is initial and regions(provider) == ["region_1"]
    provider.step(None)
    assert provider.observe().event_tick == 1 and "region_2" in regions(provider)
    before = provider.tick, provider.body, provider.planar_body, provider.observe(), provider.pending_feedback_count
    assert regions(provider, initial) == ["region_1"]
    assert (provider.tick, provider.body, provider.planar_body, provider.observe(), provider.pending_feedback_count) == before


def test_zero_radius_detail_changes_sensation_not_existing_physical_evolution():
    detail = world()
    ordinary = MotorWorldV1(STREAM, detail.profile, planar_profile=PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2, 1)),)))
    for tick in range(10):
        command = MotorCommandV1(STREAM, tick + 1, tick, 0, 0, translation=PlanarDriveV1(.5, .2))
        assert detail.step(command) == ordinary.step(command)
        assert detail.body == ordinary.body and detail.planar_body == ordinary.planar_body
