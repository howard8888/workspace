"""Body-dependent geometry preview without accidental actuator authority."""
from dataclasses import replace
import math

import pytest

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1
from nca8_body_targets import BodyTargetMapperV1, PlanarBodyObservationV1, VisualApproachRequestV1
from nca8_sensorimotor_contracts import TargetOriginV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1

STREAM = MotorStreamRefV1("visual_body", 1)


def setup(heading=0, position=(0, 0), target=(2, 1), **kwargs):
    owner = VisualSourceV1(STREAM, **kwargs)
    source = owner.update(VisualObservationV1(STREAM, 1, 0, 0, "scene_xy:test", NavPointV1(0, 0),
                         (VisualDetectionV1("region_1", "object", None if target is None else NavPointV1(*target)),)),
                         cycle_id=1, cutoff_tick=0)
    mapper = BodyTargetMapperV1(STREAM, (), visual_preview_enabled=True)
    pose = PlanarBodyObservationV1(STREAM, 1, 0, 0, "scene_xy:test", None if position is None else NavPointV1(*position), heading)
    mapper.observe_planar_body(pose, at_tick=0)
    request = VisualApproachRequestV1(TargetOriginV1(STREAM, "fixture:t", "fixture:a", "fixture:e"), source.source_map_ref, "region_1")
    return owner, source, mapper, pose, request


@pytest.mark.parametrize("heading", [-180, -135, -90, -45, 0, 45, 90, 135, 180])
@pytest.mark.parametrize("target", [(2, 1), (-1, 3), (0, 0)])
def test_transform_preserves_real_scene_vector_and_enforces_step_bound(heading, target):
    _, source, mapper, pose, request = setup(heading=heading, target=target)
    result = mapper.preview_visual_approach(request, source, at_tick=0)
    vector = result.body_relative_target
    theta = math.radians(heading)
    reconstructed = (math.cos(theta) * vector.x - math.sin(theta) * vector.y,
                     math.sin(theta) * vector.x + math.cos(theta) * vector.y)
    assert reconstructed == pytest.approx(target, abs=1e-12)
    assert math.hypot(result.body_step.x, result.body_step.y) <= 0.25 + 1e-12
    assert result.body is pose and result.scene_target == NavPointV1(*target)
    assert result.as_dict()["motor_authority"] is False
    assert mapper.reservations(at_tick=0) == ()


def test_body_rotation_changes_relative_target_but_not_environmental_target():
    _, source, mapper, pose, request = setup()
    first = mapper.preview_visual_approach(request, source, at_tick=0)
    mapper.observe_planar_body(replace(pose, sample_id=2, event_tick=1, available_tick=1, heading_degrees=90), at_tick=1)
    second = mapper.preview_visual_approach(request, source, at_tick=1)
    assert first.body_relative_target == NavPointV1(2, 1)
    assert (second.body_relative_target.x, second.body_relative_target.y) == pytest.approx((1, -2))
    assert first.scene_target == second.scene_target == NavPointV1(2, 1)
    assert first.hypothetical_self == second.hypothetical_self
    assert first.body.heading_degrees == 0


@pytest.mark.parametrize("stand_off", [0, 0.1, 0.5, 5])
def test_bounded_prospective_step_is_not_written_as_current_self_or_region(stand_off):
    owner, source, mapper, pose, request = setup()
    before = source.as_dict(), mapper.retained_counts(), owner.durable_map.as_dict()
    request = replace(request, stand_off_metres=stand_off)
    result = mapper.preview_visual_approach(request, source, at_tick=0)
    assert (source.as_dict(), mapper.retained_counts(), owner.durable_map.as_dict()) == before
    assert source.self_position == pose.position == NavPointV1(0, 0)
    assert result.hypothetical_self != pose.position or stand_off >= math.sqrt(5)
    assert result.scene_target == source.guidance[0].position


@pytest.mark.parametrize("heading,position,kwargs,status", [
    (None, (0, 0), {}, "body_geometry_unknown"), (0, None, {}, "body_geometry_unknown"),
    (0, (0, 0), {"spatial_enabled": False}, "spatial_stream_disabled"),
])
def test_unknown_body_and_disabled_geometry_do_not_produce_targets(heading, position, kwargs, status):
    _, source, mapper, _, request = setup(heading=heading, position=position, **kwargs)
    result = mapper.preview_visual_approach(request, source, at_tick=0)
    assert result.status == status and result.body_step is None and result.hypothetical_self is None


def test_recognition_off_does_not_remove_geometric_guidance_for_supplied_region():
    _, source, mapper, _, request = setup(recognition_enabled=False)
    assert source.recognition == ()
    assert mapper.preview_visual_approach(request, source, at_tick=0).body_relative_target == NavPointV1(2, 1)


def test_current_heading_is_not_the_gravity_tilt_field():
    _, source, mapper, _, request = setup(heading=90)
    mapper.update_feedback(MotorFeedbackV1(STREAM, 1, 0, 0, -30, 1, True, 0.95, 0.05), at_tick=0)
    result = mapper.preview_visual_approach(request, source, at_tick=0)
    assert (result.body_relative_target.x, result.body_relative_target.y) == pytest.approx((1, -2))
    assert mapper.current_feedback(at_tick=0).body_tilt_degrees == -30


@pytest.mark.parametrize("kind", ["source", "body", "frame", "region", "missing"])
def test_unavailable_stale_or_incompatible_geometry_has_explicit_disposition(kind):
    owner, source, mapper, pose, request = setup()
    tick = 0
    if kind == "source":
        tick = 3
        mapper.observe_planar_body(replace(pose, sample_id=2, event_tick=3, available_tick=3), at_tick=3)
    elif kind == "body":
        tick = 3
        source = owner.update(VisualObservationV1(STREAM, 2, 3, 3, "scene_xy:test", NavPointV1(0, 0),
                               (VisualDetectionV1("region_1", "object", NavPointV1(2, 1)),)), cycle_id=2, cutoff_tick=3)
    elif kind == "frame":
        mapper, new_pose = BodyTargetMapperV1(STREAM, (), visual_preview_enabled=True), replace(pose, frame_id="scene_xy:other")
        mapper.observe_planar_body(new_pose, at_tick=0)
    elif kind == "region":
        request = replace(request, region_id="not_observed")
    else:
        mapper.observe_planar_body(None, at_tick=0)
    result = mapper.preview_visual_approach(request, source, at_tick=tick)
    expected = {"source": "visual_stale", "body": "body_pose_unavailable", "frame": "frame_incompatible",
                "region": "target_unlocalized", "missing": "body_pose_unavailable"}
    assert result.status == expected[kind] and result.body_relative_target is None


def test_body_gap_rejects_old_duplicate_without_refreshing_its_time():
    _, source, mapper, pose, request = setup()
    mapper.observe_planar_body(None, at_tick=1)
    mapper.observe_planar_body(pose, at_tick=2)
    assert mapper.preview_visual_approach(request, source, at_tick=2).status == "body_pose_unavailable"
    assert mapper.retained_counts()["planar_body_records"] == 1


@pytest.mark.parametrize("change", [{"heading_degrees": 181}, {"heading_degrees": True}, {"heading_degrees": float("nan")},
                                   {"event_tick": -1}, {"event_tick": 2}, {"sample_id": False}, {"position": {}}, {"frame_id": "body"}])
def test_invalid_planar_body_contract_never_becomes_valid_sensor_evidence(change):
    _, _, _, pose, _ = setup()
    with pytest.raises((ValueError, TypeError)):
        replace(pose, **change)


@pytest.mark.parametrize("change", [dict(sample_id=2, event_tick=1, available_tick=2), dict(heading_degrees=45),
                                   dict(sample_id=2), dict(stream=MotorStreamRefV1("visual_body", 2))])
def test_bad_body_admission_is_atomic(change):
    _, source, mapper, pose, request = setup()
    original = mapper.preview_visual_approach(request, source, at_tick=0)
    with pytest.raises((ValueError, TypeError)):
        mapper.observe_planar_body(replace(pose, **change), at_tick=1)
    assert mapper.preview_visual_approach(request, source, at_tick=0) == original


def test_old_mapper_profiles_do_not_admit_planar_input_or_change_counts():
    _, source, _, pose, request = setup()
    mapper = BodyTargetMapperV1(STREAM, ())
    assert "planar_body_records" not in mapper.retained_counts()
    with pytest.raises(RuntimeError):
        mapper.observe_planar_body(pose, at_tick=0)
    with pytest.raises(RuntimeError):
        mapper.preview_visual_approach(request, source, at_tick=0)


def test_wrong_source_or_generation_cannot_borrow_visual_geometry():
    _, source, mapper, _, request = setup()
    with pytest.raises(ValueError):
        mapper.preview_visual_approach(replace(request, source_map_ref=NavMapRefV1("posture_support", 1)), source, at_tick=0)
    foreign = replace(request.origin, stream=MotorStreamRefV1("visual_body", 2))
    with pytest.raises(ValueError):
        mapper.preview_visual_approach(replace(request, origin=foreign), source, at_tick=0)


def test_nonactuating_result_is_not_an_h1_proposal_that_can_be_reserved():
    _, source, mapper, _, request = setup()
    preview = mapper.preview_visual_approach(request, source, at_tick=0)
    with pytest.raises((ValueError, TypeError)):
        mapper.reserve(preview, execution_id="illegal", at_tick=0)
    assert mapper.reservations(at_tick=0) == ()
