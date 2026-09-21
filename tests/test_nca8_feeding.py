"""Independent feeding-detail evidence, geometric association and ordinary focal access."""
from dataclasses import FrozenInstanceError, replace
import json
import math

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1, NavPointV1
from nca8_contracts import CircuitValidityV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_feeding import (
    FeedingDetailCandidateV1, FeedingDetailNavMapStateV1, FeedingDetailProfileV1,
    FeedingDetailSeedV1, FeedingDetailSourceV1,
)
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1

STREAM = MotorStreamRefV1("feeding_unit", 1)


def packet(tick=0, *, detail=(1.82, 1.0), parent=(2.0, 1.0), body=(1.58, 0.79),
           category="feeding", parent_category="object", include_detail=True, include_parent=True, stream=STREAM):
    detections = []
    if include_parent:
        detections.append(VisualDetectionV1("region_1", parent_category, None if parent is None else NavPointV1(*parent)))
    if include_detail:
        detections.append(VisualDetectionV1("region_2", category, None if detail is None else NavPointV1(*detail)))
    return VisualObservationV1(stream, tick + 1, tick, tick, "scene_xy:feeding", None if body is None else NavPointV1(*body),
                               tuple(detections))


def owners(profile=None, *, stream=STREAM, **visual_options):
    return (VisualSourceV1(stream, **visual_options), MaternalSourceV1(stream, MaternalSeedV1()),
            FeedingDetailSourceV1(stream, FeedingDetailProfileV1() if profile is None else profile))


def apply(group, observation, *, tick=0, cycle=1):
    visual, maternal, feeding = group
    return feeding.update(maternal.update(visual.update(observation, cycle_id=cycle, cutoff_tick=tick)))


@pytest.mark.parametrize("field,value", [
    ("maximum_parent_distance", True), ("maximum_parent_distance", 10**1000), ("maximum_parent_distance", 0), ("maximum_parent_distance", -1),
    ("maximum_parent_distance", math.inf), ("maximum_parent_distance", math.nan), ("maximum_parent_distance", 2.01),
    ("maximum_parent_distance", "0.3"), ("maximum_self_distance", False), ("maximum_self_distance", 0),
    ("maximum_self_distance", -1), ("maximum_self_distance", math.inf), ("maximum_self_distance", math.nan),
    ("maximum_self_distance", 2.01), ("parent_region_id", ""), ("detail_region_id", ""),
    ("detail_region_id", "region_1"),
])
def test_seed_rejects_invalid_or_aliased_part_contract(field, value):
    with pytest.raises((ValueError, TypeError)):
        FeedingDetailSeedV1(**{field: value})


@pytest.mark.parametrize("field", ["source_enabled", "attention_enabled", "feeding_need"])
@pytest.mark.parametrize("value", [0, 1, "true", None])
def test_profile_switches_are_not_numeric_or_missing(field, value):
    with pytest.raises(TypeError):
        FeedingDetailProfileV1(**{field: value})


def test_declared_seed_is_bounded_substrate_not_current_position_or_learned_identity():
    group = owners()
    owner = group[2]
    assert owner.current is owner.candidate() is None
    assert owner.retained_counts() == {"durable_maps": 1, "current_configurations": 0}
    source = apply(group, packet())
    assert source.source_map_ref == NavMapRefV1("feeding_detail", 1)
    assert source.source_map_ref != source.maternal.source_map_ref != source.maternal.visual.source_map_ref
    assert owner.durable_map.map_id == source.source_map_ref.map_id
    assert len(owner.durable_map.elements) == 2 and len(owner.durable_map.relations) == 1
    assert source.detail_position == NavPointV1(1.82, 1)
    assert source.parent_distance == pytest.approx(.18)
    assert source.self_distance == pytest.approx(math.hypot(.24, .21))
    assert source.stream == STREAM and source.frame_id == "scene_xy:feeding"
    assert source.as_dict()["seed"]["learned_identity"] is False
    assert source.owner_circuit == "feeding_association"
    assert source.validity is CircuitValidityV1.VALID


@pytest.mark.parametrize("kwargs,status,recognized,localized", [
    ({"include_detail": False}, "detail_unrecognized", "unavailable", False),
    ({"category": None}, "detail_unrecognized", "unavailable", True),
    ({"category": "landmark"}, "detail_category_contradicted", "contradicted", True),
    ({"detail": None}, "detail_unlocalized", "supported", False),
    ({"parent": None}, "parent_unlocalized", "supported", True),
    ({"include_parent": False}, "maternal_unavailable", "supported", True),
    ({"parent_category": "landmark"}, "maternal_unavailable", "supported", True),
    ({"detail": (1.1, .7)}, "part_geometry_contradicted", "supported", True),
])
def test_missing_contradictory_identity_and_geometry_do_not_supply_a_task_answer(kwargs, status, recognized, localized):
    group = owners()
    source = apply(group, packet(**kwargs))
    assert source.association_status == status
    assert source.recognition_status == recognized
    assert (source.detail_position is not None) is localized
    assert not source.focal_accessible and group[2].candidate() is None


@pytest.mark.parametrize("recognition,spatial,status", [
    (False, True, "maternal_unavailable"), (True, False, "detail_unlocalized"), (False, False, "maternal_unavailable"),
])
def test_parallel_visual_streams_remain_distinct(recognition, spatial, status):
    group = owners(recognition_enabled=recognition, spatial_enabled=spatial)
    source = apply(group, packet())
    assert len(source.maternal.visual.recognition) == (2 if recognition else 0)
    assert len(source.maternal.visual.guidance) == (2 if spatial else 0)
    assert source.association_status == status and group[2].candidate() is None


@pytest.mark.parametrize("distance,compatible", [(.299, True), (.3, True), (.30001, False)])
def test_part_relation_uses_actual_parent_geometry_with_declared_boundary(distance, compatible):
    source = apply(owners(), packet(parent=(0, 0), detail=(distance, 0), body=(distance, 0)))
    assert (source.association_status == "compatible") is compatible
    assert source.focal_accessible is compatible


@pytest.mark.parametrize("distance,accessible", [(.649, True), (.65, True), (.65001, False)])
def test_self_distance_changes_access_not_part_identity(distance, accessible):
    source = apply(owners(), packet(parent=(0, 0), detail=(0, 0), body=(-distance, 0)))
    assert source.association_status == "compatible"
    assert source.focal_accessible is accessible


def test_unknown_self_position_is_not_zero_separation_or_motor_permission():
    group = owners()
    source = apply(group, packet(body=None))
    assert source.recognition_status == "supported" and source.detail_position is not None
    assert source.association_status == "compatible" and source.self_distance is None
    assert group[2].candidate() is None


@pytest.mark.parametrize("seed", [FeedingDetailSeedV1(parent_region_id="region_3"), FeedingDetailSeedV1(detail_region_id="region_3")])
def test_seed_handles_do_not_search_for_an_alternate_successful_part(seed):
    group = owners(FeedingDetailProfileV1(seed=seed))
    source = apply(group, packet())
    assert source.association_status in {"parent_seed_mismatch", "detail_unrecognized"}
    assert group[2].candidate() is None


@pytest.mark.parametrize("field", ["attention_enabled", "feeding_need"])
def test_access_route_controls_preserve_actual_representation_and_activation(field):
    on = owners()
    off = owners(FeedingDetailProfileV1(**{field: False}))
    current_on, current_off = apply(on, packet()), apply(off, packet())
    assert current_on == current_off and current_off.activation == .6
    assert on[2].candidate() is not None and off[2].candidate() is None
    assert on[2].durable_map == off[2].durable_map


def test_source_off_retains_raw_visual_input_but_no_feeding_access():
    group = owners(FeedingDetailProfileV1(source_enabled=False))
    source = apply(group, packet())
    assert source.association_status == "disabled" and source.detail_position is None
    assert len(source.maternal.visual.guidance) == 2
    assert source.validity is CircuitValidityV1.STALE and group[2].candidate() is None


def test_missing_evidence_clears_detail_immediately_without_deleting_parent_continuity():
    group = owners()
    first = apply(group, packet())
    old = first.as_dict()
    missing = apply(group, None, tick=4, cycle=2)
    assert missing.association_status == "visual_unavailable" and missing.detail_position is None
    assert missing.maternal.identity_status == "retained" and missing.maternal.possible_center is not None
    assert missing.maternal.visual.event_tick == 0 and group[2].candidate() is None
    duplicate = apply(group, packet(), tick=5, cycle=3)
    assert duplicate.association_status == "visual_unavailable" and duplicate.detail_position is None
    fresh = apply(group, packet(6, detail=(1.9, 1)), tick=6, cycle=4)
    assert fresh.focal_accessible and fresh.detail_position == NavPointV1(1.9, 1)
    assert first.as_dict() == old and first.cutoff_tick == 0


def test_reread_keeps_original_event_and_does_not_create_a_new_measurement():
    group = owners()
    first = apply(group, packet())
    reread = apply(group, packet(), tick=1, cycle=2)
    assert first.maternal.visual.sample_id == reread.maternal.visual.sample_id == 1
    assert reread.applied_cycle == 2 and reread.cutoff_tick == 1 and reread.maternal.visual.event_tick == 0
    stale = apply(group, packet(), tick=3, cycle=3)
    assert stale.detail_position is None and not stale.focal_accessible


def test_wrong_generation_or_repeated_opportunity_is_rejected_before_mutation():
    group = owners()
    source = apply(group, packet())
    other_stream = MotorStreamRefV1(STREAM.stream_id, 2)
    foreign = apply(owners(stream=other_stream), packet(stream=other_stream))
    for basis in (source.maternal, foreign.maternal, None):
        with pytest.raises(ValueError):
            group[2].update(basis)
        assert group[2].current is source


def test_source_and_export_are_immutable_and_counts_do_not_grow_with_samples():
    group = owners()
    first = apply(group, packet())
    before = group[2].durable_map.as_dict()
    for tick in range(4, 401, 4):
        current = apply(group, packet(tick, detail=(1.81 + (tick % 12) * .001, 1)), tick=tick, cycle=tick // 4 + 1)
        assert current.state_id == first.state_id and current.source_map_ref == first.source_map_ref
    assert group[2].retained_counts() == {"durable_maps": 1, "current_configurations": 1}
    assert group[2].durable_map.as_dict() == before
    export = first.as_dict()
    export["seed"]["detail_region_id"] = "fabricated"
    assert first.seed.detail_region_id == "region_2"
    with pytest.raises(FrozenInstanceError):
        first.enabled = False
    for field in ("detail_position", "association_status", "contact", "milk"):
        with pytest.raises(TypeError):
            replace(first, **{field: True})
    json.dumps(first.as_dict(), allow_nan=False)


def test_actual_attention_and_navigation_select_one_source_without_a_feeding_primitive():
    group = owners()
    source = apply(group, packet())
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1()
    bid = attention.build_bid(group[2].candidate(), cycle_id=1)
    selection = attention.select((bid,), current_wnm=None, cycle_id=1)
    working = navigation.update_wnm(selection)
    decision = navigation.commit(working, (), cycle_id=1)
    assert selection.selected_source_state is source and working.primary_source_state is source
    assert working.working_relations == source.active_relation_labels
    assert decision.application is None and decision.selected_primitive_id is None
    assert bid.source == "feeding_candidate" and bid.priority_components == (0, 10, 0, 0, 0, 60)
    with pytest.raises(ValueError):
        attention.build_bid(group[2].candidate(), cycle_id=2)
    incompatible = apply(owners(), packet(category="landmark"))
    with pytest.raises(ValueError):
        FeedingDetailCandidateV1(incompatible)
    with pytest.raises(ValueError):
        replace(bid, source_map_state=incompatible)


@pytest.mark.parametrize("factory,args", [
    (FeedingDetailProfileV1, (None,)), (FeedingDetailSourceV1, (None, FeedingDetailProfileV1())),
    (FeedingDetailSourceV1, (STREAM, None)), (FeedingDetailNavMapStateV1, (None, FeedingDetailSeedV1())),
])
def test_wrong_contract_types_fail_at_owner_boundary(factory, args):
    with pytest.raises((TypeError, ValueError)):
        factory(*args)
