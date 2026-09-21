"""Visual admission, ownership, domain separation and independent stream tests."""
from dataclasses import FrozenInstanceError, replace
import json
import random
from types import MappingProxyType

import pytest

from cca8_env import EnvObservation
from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1, NavMapRefV1
from nca8_adapters import adapt_env_observation_v1, admit_visual_surface_v1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1, AttentionBidV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualNavMapStateV1, VisualSourceV1

STREAM = MotorStreamRefV1("visual_test", 1)


def observation(sample=1, event=0, available=0, target=(2.0, 1.0), **kwargs):
    values = dict(stream=STREAM, sample_id=sample, event_tick=event, available_tick=available,
                  frame_id="scene_xy:test", self_position=NavPointV1(0, 0),
                  detections=(VisualDetectionV1("region_1", "object", None if target is None else NavPointV1(*target)),))
    values.update(kwargs)
    return VisualObservationV1(**values)


def raw_observation(**kwargs):
    values = dict(raw_sensors={}, predicates=[], cues=[], nav_patches=[], env_meta={"step_index": 0},
                  surface_grid={"schema": "surface_grid_v1", "frame": "scene_xy:test", "anchor": {"x": 0, "y": 0},
                                "objects": [{"entity": "region_1", "kind": "object", "x": 2, "y": 1}], "landmarks": []})
    values.update(kwargs)
    return EnvObservation(**values)


def admit(raw):
    return admit_visual_surface_v1(adapt_env_observation_v1(raw), stream=STREAM, sample_id=1, event_tick=0, available_tick=0)


def test_geometry_enters_the_existing_whitelist_without_copying_private_answers():
    raw = raw_observation()
    expected = admit(raw)
    raw.raw_sensors.update({"oracle_policy": "follow_mom", "distance_to_mom": 0})
    raw.predicates.extend(["posture:fallen", "milk:drinking"])
    raw.cues.append("vision:silhouette:mom")
    raw.env_meta.update({"scenario_stage": "rest", "milestones": ["reached_mom"], "reward": 10})
    raw.surface_grid.update({"affordances": {"mom_near": True}, "focus_candidates": ["region_1"], "success": True})
    raw.surface_grid["objects"][0].update({"priority_hint": 999, "focused": True, "policy": "stand_up", "dist": 0})
    assert admit(raw) == expected


def test_input_is_detached_and_missing_coordinates_are_not_repaired_from_relative_hints():
    raw = raw_observation()
    safe = adapt_env_observation_v1(raw)
    raw.surface_grid["objects"][0]["x"] = 100
    value = admit_visual_surface_v1(safe, stream=STREAM, sample_id=1, event_tick=0, available_tick=0)
    assert value.detections[0].position == NavPointV1(2, 1)
    raw.surface_grid["objects"][0] = {"entity": "region_1", "kind": "object", "x": 2, "dx": 2, "dy": 1, "dist": 3}
    assert admit(raw).detections[0].position is None


@pytest.mark.parametrize("frame", ["body", "ego_schematic_v1", "scene_xy:", "scene xy:test"])
def test_legacy_or_unnamed_frames_are_not_relabelled_allocentric(frame):
    raw = raw_observation()
    raw.surface_grid["frame"] = frame
    with pytest.raises(ValueError):
        admit(raw)


def test_absent_surface_and_valid_empty_acquisition_remain_different():
    assert admit(raw_observation(surface_grid={})) is None
    raw = raw_observation()
    raw.surface_grid["objects"] = []
    value = admit(raw)
    assert value is not None and value.detections == ()
    owner = VisualSourceV1(STREAM)
    source = owner.update(value, cycle_id=1, cutoff_tick=0)
    assert source.evidence_current and owner.candidate() is None


@pytest.mark.parametrize("change", ["duplicate", "nine", "missing_handle", "wrong_event", "wrong_schema", "missing_schema"])
def test_visual_consumer_rejects_malformed_or_overflowing_whitelisted_input(change):
    raw = raw_observation()
    if change == "duplicate":
        raw.surface_grid["objects"] *= 2
    elif change == "nine":
        raw.surface_grid["objects"] = [{"entity": f"region_{i}", "x": i, "y": 0} for i in range(9)]
    elif change == "missing_handle":
        del raw.surface_grid["objects"][0]["entity"]
    elif change == "wrong_event":
        raw.env_meta["step_index"] = 1
    elif change == "missing_schema":
        del raw.surface_grid["schema"]
    else:
        raw.surface_grid["schema"] = "unknown"
    with pytest.raises((ValueError, TypeError)):
        admit(raw)


@pytest.mark.parametrize("field,value", [("sample_id", 0), ("sample_id", True), ("event_tick", -1), ("event_tick", "0"),
                                        ("available_tick", False), ("available_tick", -1), ("event_tick", 2**63),
                                        ("sample_id", 1.0), ("stream", None), ("frame_id", "body")])
def test_acquisition_contract_rejects_invalid_identity_and_time(field, value):
    with pytest.raises((ValueError, TypeError)):
        observation(**{field: value})


@pytest.mark.parametrize("point", [NavPointV1(10001, 0), NavPointV1(0, -10001), True, {"x": 1, "y": 2}])
def test_coordinate_limit_and_typed_points_are_enforced(point):
    with pytest.raises((ValueError, TypeError)):
        observation(self_position=point)


@pytest.mark.parametrize("switch", ["recognition_enabled", "spatial_enabled"])
@pytest.mark.parametrize("value", [None, 0, 1, "true"])
def test_stream_enablement_is_explicit_boolean(switch, value):
    with pytest.raises(TypeError):
        VisualSourceV1(STREAM, **{switch: value})


def test_real_source_has_no_posture_fields_or_automatic_executive_authority():
    source = VisualSourceV1(STREAM)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    current = source.update(observation(), cycle_id=1, cutoff_tick=0)
    assert isinstance(current, VisualNavMapStateV1)
    assert not hasattr(current, "posture") and not hasattr(current, "motor_support")
    assert attention.last_selection is None and navigation.current_wnm is None
    bid = attention.build_bid(source.candidate(), cycle_id=1)
    assert bid.source == "visual_candidate" and navigation.current_wnm is None
    choice = attention.select((bid,), current_wnm=None, cycle_id=1)
    working = navigation.update_wnm(choice)
    assert working.primary_source_state is current
    assert navigation.commit(working, (), cycle_id=1).application is None


def test_source_identity_and_durable_content_stay_fixed_across_changes_and_nonfocal_updates():
    owner = VisualSourceV1(STREAM)
    signature = owner.durable_map.record_signature()
    first = owner.update(observation(), cycle_id=1, cutoff_tick=0)
    second = owner.update(observation(2, 1, 2, (4, 3)), cycle_id=2, cutoff_tick=2)
    assert first.state_id == second.state_id and first.source_map_ref == second.source_map_ref
    assert first.guidance[0].position == NavPointV1(2, 1)
    assert second.guidance[0].relative_to_self == NavPointV1(4, 3)
    assert owner.durable_map.record_signature() == signature
    assert second.update_count == 2


def test_recognition_and_spatial_guidance_are_independent_consumed_products():
    acquisition = observation()
    intact, no_identity, no_geometry = (
        owner.update(acquisition, cycle_id=1, cutoff_tick=0) for owner in
        (VisualSourceV1(STREAM), VisualSourceV1(STREAM, recognition_enabled=False), VisualSourceV1(STREAM, spatial_enabled=False))
    )
    assert no_identity.recognition == () and no_identity.guidance == intact.guidance
    assert no_geometry.guidance == () and no_geometry.self_position is None
    assert no_geometry.recognition == intact.recognition
    assert "position" not in no_geometry.recognition[0].as_dict()
    assert "descriptor" not in no_identity.guidance[0].as_dict()


def test_duplicate_read_keeps_original_age_then_expires_without_new_facts():
    owner = VisualSourceV1(STREAM)
    acquisition = observation()
    first = owner.update(acquisition, cycle_id=1, cutoff_tick=0)
    held = owner.update(acquisition, cycle_id=2, cutoff_tick=2)
    stale = owner.update(acquisition, cycle_id=3, cutoff_tick=3)
    assert held.input_status == "reread" and held.event_tick == first.event_tick == 0
    assert stale.input_status == "stale" and stale.recognition == stale.guidance == ()
    assert owner.candidate() is None and stale.event_tick == 0


def test_missing_input_cannot_be_repaired_by_rereading_its_old_sample():
    owner = VisualSourceV1(STREAM)
    acquisition = observation()
    owner.update(acquisition, cycle_id=1, cutoff_tick=0)
    owner.update(None, cycle_id=2, cutoff_tick=1)
    repeated = owner.update(acquisition, cycle_id=3, cutoff_tick=2)
    assert repeated.input_status == "unavailable_after_gap" and not repeated.evidence_current
    fresh = owner.update(observation(2, 3, 3), cycle_id=4, cutoff_tick=3)
    assert fresh.input_status == "current" and owner.candidate() is not None


@pytest.mark.parametrize("bad", [observation(2, 1, 3), observation(2, 0, 1), observation(1, 0, 0, (4, 5)),
                                  observation(stream=MotorStreamRefV1("visual_test", 2)), {"state": "good"}])
def test_bad_input_rejects_atomically_without_replacing_valid_source(bad):
    owner = VisualSourceV1(STREAM)
    good = owner.update(observation(), cycle_id=1, cutoff_tick=0)
    counts = owner.retained_counts()
    with pytest.raises((ValueError, TypeError)):
        owner.update(bad, cycle_id=2, cutoff_tick=2)
    assert owner.current is good and owner.retained_counts() == counts
    assert owner.update(observation(2, 1, 2), cycle_id=2, cutoff_tick=2).evidence_current


@pytest.mark.parametrize("cycle,tick", [(1, 1), (2, 0), (True, 1), (2, -1), (2, 2**63)])
def test_focal_and_physical_clock_order_are_separate_and_bounded(cycle, tick):
    owner = VisualSourceV1(STREAM)
    first = owner.update(observation(), cycle_id=1, cutoff_tick=0)
    with pytest.raises(ValueError):
        owner.update(None, cycle_id=cycle, cutoff_tick=tick)
    assert owner.current is first


def test_renderable_exports_are_detached_and_owner_storage_stays_bounded():
    rng = random.getstate()
    owner = VisualSourceV1(STREAM)
    for tick in range(100):
        current = owner.update(observation(tick + 1, tick, tick), cycle_id=tick + 1, cutoff_tick=tick)
    before = current.as_dict()
    exported = current.as_dict()
    exported["guidance"][0]["position"]["x"] = 99
    assert current.as_dict() == before and json.loads(json.dumps(before)) == before
    with pytest.raises(FrozenInstanceError):
        current.input_status = "missing"
    assert owner.retained_counts() == {"durable_maps": 1, "acquisitions": 1, "current_configurations": 1,
                                       "retained_detections": 1, "recognition_contributions": 1, "guidance_contributions": 1}
    assert random.getstate() == rng


def test_visual_concrete_type_cannot_carry_posture_facts_into_standup():
    from nca8_primitives import StandUpIPV1
    owner = VisualSourceV1(STREAM)
    owner.update(observation(), cycle_id=1, cutoff_tick=0)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    selection = attention.select((attention.build_bid(owner.candidate(), cycle_id=1),), current_wnm=None, cycle_id=1)
    working = navigation.update_wnm(selection)
    # Even a test-supplied misleading relation list is not a posture-domain source.
    spoof = replace(working, working_relations=("posture:fallen", "support:inadequate"))
    assert not StandUpIPV1().evaluate_applicability(spoof, cycle_id=1).eligible


def test_pretend_source_object_does_not_pass_the_new_closed_union():
    owner = VisualSourceV1(STREAM)
    owner.update(observation(), cycle_id=1, cutoff_tick=0)
    bid = AttentionRuntimeV1().build_bid(owner.candidate(), cycle_id=1)
    with pytest.raises(TypeError):
        replace(bid, source_map_state=MappingProxyType(owner.current.as_dict()))


@pytest.mark.parametrize("foreign", [False, True])
def test_preview_refuses_foreign_or_future_visual_bid_before_source_mutation(foreign):
    from cca8_motor_contracts import MotorFeedbackV1
    from nca8_runtime import Nca8RightingPreviewSessionV1
    stream = MotorStreamRefV1("foreign_visual", 2) if foreign else STREAM
    owner = VisualSourceV1(stream)
    owner.update(observation(stream=stream), cycle_id=1, cutoff_tick=0 if foreign else 1)
    session = Nca8RightingPreviewSessionV1(STREAM, visual_preview_enabled=True)
    bid = session.attention.build_bid(owner.candidate(), cycle_id=1)
    feedback = MotorFeedbackV1(STREAM, 1, 0, 0, 5, 1, True, 0.95, 0.05)
    with pytest.raises(ValueError):
        session.preview(feedback, cutoff_tick=0, competing_bids=(bid,))
    assert session.last_result is None and session.attention.last_selection is None
    assert session.mapper.current_feedback(at_tick=0) is None


def test_a_direct_bid_cannot_promote_missing_visual_content():
    owner = VisualSourceV1(STREAM)
    owner.update(observation(), cycle_id=1, cutoff_tick=0)
    original = AttentionRuntimeV1().build_bid(owner.candidate(), cycle_id=1)
    unavailable = owner.update(None, cycle_id=2, cutoff_tick=1)
    with pytest.raises(ValueError):
        replace(original, cycle_id=2, source_map_state=unavailable)
