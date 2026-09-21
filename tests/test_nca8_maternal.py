"""Source-owned maternal association, uncertainty and non-authoritative relevance."""

from dataclasses import FrozenInstanceError, replace

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1

STREAM = MotorStreamRefV1("maternal_unit", 1)


def pair(**kwargs):
    return VisualSourceV1(STREAM, **kwargs), MaternalSourceV1(STREAM, MaternalSeedV1())


def packet(tick=0, *, descriptor="object", target=(2.0, 1.0), position=(0.0, 0.0), region="region_1", frame="scene_xy:lab"):
    return VisualObservationV1(STREAM, tick + 1, tick, tick, frame,
                               None if position is None else NavPointV1(*position),
                               (VisualDetectionV1(region, descriptor, None if target is None else NavPointV1(*target)),))


def update(visual, maternal, tick, cycle, observation):
    return maternal.update(visual.update(observation, cycle_id=cycle, cutoff_tick=tick))


def test_source_is_a_distinct_association_map_not_posture_or_a_visual_alias():
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet())
    assert current.source_map_ref == NavMapRefV1("maternal_target", 1)
    assert current.visual.source_map_ref == NavMapRefV1("visual_scene", 1)
    assert current.owner_circuit == "maternal_association"
    assert not hasattr(current, "posture") and not hasattr(current, "motor_support")
    assert maternal.durable_map.map_id != visual.durable_map.map_id
    assert current.as_dict()["seed"]["learned_identity"] is False


@pytest.mark.parametrize("tick,target", [(0, (2, 1)), (4, (3, 2)), (8, (-2, 1)), (12, (1, -2))])
def test_current_relation_and_old_configuration_are_not_durable_map_revisions(tick, target):
    visual, maternal = pair()
    before = maternal.durable_map.as_dict()
    first = update(visual, maternal, 0, 1, packet())
    old = first.as_dict()
    current = first if tick == 0 else update(visual, maternal, tick, 2, packet(tick, target=target))
    assert current.target_position == NavPointV1(*target)
    assert maternal.durable_map.as_dict() == before and first.as_dict() == old
    assert current.state_id == first.state_id


@pytest.mark.parametrize("recognition,spatial,identity,localized", [
    (True, True, "supported", True), (False, True, "unestablished", False),
    (True, False, "supported", False), (False, False, "unestablished", False),
])
def test_recognition_association_and_spatial_products_have_separate_consumers(recognition, spatial, identity, localized):
    visual, maternal = pair(recognition_enabled=recognition, spatial_enabled=spatial)
    current = update(visual, maternal, 0, 1, packet())
    assert current.identity_status == identity and current.action_localized is localized
    assert len(visual.current.guidance) == int(spatial)
    assert len(visual.current.recognition) == int(recognition)
    assert current.as_dict()["motor_authority"] is False


@pytest.mark.parametrize("handle", ["mom", "MOM", "mother", "region_2", "nearest"])
def test_a_neutral_handle_or_another_object_is_not_a_maternal_identity_answer(handle):
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet(region=handle))
    assert current.identity_status == "unestablished" and current.separation is None
    assert maternal.candidate() is None


def test_seed_control_preserves_visual_products_without_promoting_the_association():
    visual = VisualSourceV1(STREAM)
    maternal = MaternalSourceV1(STREAM, MaternalSeedV1(), enabled=False)
    current = update(visual, maternal, 0, 1, packet())
    assert current.identity_status == "disabled" and maternal.candidate() is None
    assert len(visual.current.recognition) == len(visual.current.guidance) == 1


def test_other_closer_objects_do_not_replace_the_configured_region():
    visual, maternal = pair()
    observation = replace(packet(), detections=(VisualDetectionV1("distractor", "object", NavPointV1(0.1, 0)), *packet().detections))
    current = update(visual, maternal, 0, 1, observation)
    assert current.target_position == NavPointV1(2, 1)


@pytest.mark.parametrize("field", ["target", "position"])
def test_localization_is_not_inferred_from_identity_or_activation(field):
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet(**{field: None}))
    assert current.identity_status == "supported"
    assert current.focal_accessible and not current.action_localized and current.separation is None


def test_missing_duplicate_and_expiry_never_restore_an_exact_target():
    visual, maternal = pair()
    observation = packet()
    first = update(visual, maternal, 0, 1, observation)
    second = update(visual, maternal, 4, 2, None)
    third = update(visual, maternal, 8, 3, observation)
    expired = update(visual, maternal, 9, 4, None)
    assert first.action_localized
    assert second.identity_status == third.identity_status == "retained"
    assert second.uncertainty_radius == pytest.approx(0.1) and third.uncertainty_radius == pytest.approx(0.2)
    assert second.possible_center == NavPointV1(2, 1)
    assert not second.guidance and not third.guidance and second.last_supported_tick == third.last_supported_tick == 0
    assert expired.identity_status == "expired" and expired.possible_center is None and maternal.candidate() is None
    reacquired = update(visual, maternal, 12, 5, packet(12, target=(3, 2)))
    assert reacquired.action_localized and reacquired.target_position == NavPointV1(3, 2)
    assert reacquired.separation_rate is None


def test_known_contradiction_withdraws_target_and_cannot_keep_old_possible_region():
    visual, maternal = pair()
    update(visual, maternal, 0, 1, packet())
    contradicted = update(visual, maternal, 4, 2, packet(4, descriptor="hazard"))
    assert contradicted.identity_status == "contradicted"
    assert contradicted.target_position is contradicted.possible_center is contradicted.last_supported_tick is None
    missing = update(visual, maternal, 8, 3, None)
    assert missing.identity_status == "unestablished"


def test_new_frame_does_not_relabel_the_old_possible_region():
    visual, maternal = pair()
    update(visual, maternal, 0, 1, packet())
    changed = update(visual, maternal, 4, 2, packet(4, descriptor=None, target=None, frame="scene_xy:other"))
    assert changed.identity_status == "retained" and changed.possible_center is None


@pytest.mark.parametrize("target,position,self_rate,target_rate", [
    ((2, 1), (0.2, 0.1), 1.118033988749895, 0.0),
    ((1.8, 0.9), (0, 0), 0.0, 1.118033988749895),
    ((2, 1), (0, 0), 0.0, 0.0),
])
def test_two_acquisitions_separate_self_motion_from_target_motion(target, position, self_rate, target_rate):
    visual, maternal = pair()
    first = update(visual, maternal, 0, 1, packet())
    second = update(visual, maternal, 4, 2, packet(4, target=target, position=position))
    assert first.separation_rate is first.self_closing_rate is first.target_closing_rate is None
    assert second.self_closing_rate == pytest.approx(self_rate) and second.target_closing_rate == pytest.approx(target_rate)
    assert second.separation_rate == pytest.approx((second.separation - first.separation) / 0.2)


def test_reread_is_not_another_rate_sample():
    visual, maternal = pair()
    observation = packet()
    update(visual, maternal, 0, 1, observation)
    reread = update(visual, maternal, 1, 2, observation)
    assert reread.evidence_current and reread.event_tick == 0 and reread.separation_rate is None


@pytest.mark.parametrize("tick,frame", [(9, "scene_xy:lab"), (4, "scene_xy:other")])
def test_large_time_gap_or_incompatible_frame_cannot_supply_a_rate(tick, frame):
    visual, maternal = pair()
    update(visual, maternal, 0, 1, packet())
    current = update(visual, maternal, tick, 2, packet(tick, position=(0.1, 0.1), frame=frame))
    assert current.action_localized and current.separation_rate is None


@pytest.mark.parametrize("change", [
    {"identity_status": "invented"}, {"identity_status": "retained"}, {"target_position": NavPointV1(4, 1)},
    {"last_supported_tick": 1}, {"possible_center": NavPointV1(2, 1)}, {"separation_rate": float("nan")},
    {"self_closing_rate": True}, {"target_closing_rate": float("inf")},
])
def test_fabricated_maternal_state_cannot_launder_unsupported_geometry(change):
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet())
    with pytest.raises((TypeError, ValueError)):
        replace(current, **change)


def test_foreign_or_repeated_update_is_atomic():
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet())
    before = maternal.retained_counts(), current.as_dict()
    with pytest.raises(ValueError):
        maternal.update(current.visual)
    other = VisualSourceV1(MotorStreamRefV1(STREAM.stream_id, 2))
    observation = replace(packet(4), stream=MotorStreamRefV1(STREAM.stream_id, 2))
    with pytest.raises(ValueError):
        maternal.update(other.update(observation, cycle_id=2, cutoff_tick=4))
    assert before == (maternal.retained_counts(), maternal.current.as_dict())


def test_selected_influence_is_source_owned_finite_and_separate_from_facts():
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet())
    before = current.as_dict()
    maternal.retain_influence("task:1", cycle_id=1, expires_at_tick=8)
    assert maternal.candidate(task_id="task:1").current_task_persistence_rank == 20
    assert maternal.candidate(task_id="task:other").current_task_persistence_rank == 0
    assert current.as_dict() == before
    update(visual, maternal, 8, 2, packet(8))
    assert maternal.candidate(task_id="task:1").current_task_persistence_rank == 0


@pytest.mark.parametrize("cycle,expiry", [(1, 0), (1, 9), (2, 8), (True, 8), (1, True)])
def test_influence_cannot_expand_its_declared_window_or_borrow_a_cycle(cycle, expiry):
    visual, maternal = pair()
    update(visual, maternal, 0, 1, packet())
    with pytest.raises(ValueError):
        maternal.retain_influence("task:1", cycle_id=cycle, expires_at_tick=expiry)
    assert maternal.retained_counts()["influence_requests"] == 0


def test_the_common_selector_uses_the_real_mom_source_without_selecting_a_task():
    visual, maternal = pair()
    current = update(visual, maternal, 0, 1, packet())
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    selection = attention.select((attention.build_bid(maternal.candidate(), cycle_id=1),), current_wnm=None, cycle_id=1)
    wnm = navigation.update_wnm(selection)
    assert wnm.primary_source_state is current
    assert selection.selected_bid.as_dict()["primitive_id"] is None
    with pytest.raises(FrozenInstanceError):
        current.identity_status = "completed"
    exported = current.as_dict()
    exported["seed"]["region_id"] = "changed"
    assert current.seed.region_id == "region_1"
