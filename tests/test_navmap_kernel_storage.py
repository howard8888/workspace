# -*- coding: utf-8 -*-
"""Phase 1D proof for direct Column storage, map links, and kernel determinism.

This slice deliberately adds no runtime authority and no new storage mechanism.
``ColumnMemory`` stores ``NavMapV2`` through the existing ``FeaturePayload``
contract, while direct map links remain immutable ``NavMapRefV1`` addresses.
The tests also record two useful complexity properties of the explicit kernel:
serialization/storage size grows with represented element count, while geometry
query results depend on geometry rather than arbitrary frame extent.
"""

from __future__ import annotations

from dataclasses import replace

import pytest

from cca8_column import ColumnMemory
from cca8_features import FactMeta
from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapLinkV1,
    NavMapRefV1,
    NavMapV2,
    NavPointV1,
    NavProvenanceV1,
    NavSourceClassV1,
    element_centroid,
    follow_link,
    minimum_distance_between,
)


def _provenance(source_ref: str = "fixture:phase1d") -> NavProvenanceV1:
    """Return deterministic observed provenance for storage fixtures."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.OBSERVED,
        source_ref=source_ref,
        quality=0.95,
    )


def _frame(*, frame_id: str = "local_scene_v1", extent: float = 5.0) -> NavFrameV1:
    """Return a square continuous frame with explicit semantic axes."""
    return NavFrameV1(
        frame_id=frame_id,
        x_axis="right",
        y_axis="forward",
        units="normalized",
        min_x=-extent,
        max_x=extent,
        min_y=-extent,
        max_y=extent,
    )


def _geometry(kind: NavGeometryKindV1, *points: tuple[float, float]) -> NavGeometryV1:
    """Build compact immutable geometry for deterministic fixtures."""
    return NavGeometryV1(
        kind=kind,
        points=tuple(NavPointV1(x=x, y=y) for x, y in points),
    )


def _maternal_detail_map() -> NavMapV2:
    """Return a small maternal-body detail map stored independently of its root scene."""
    provenance = _provenance("fixture:maternal_detail")
    return NavMapV2(
        map_id="maternal_body_map",
        revision=3,
        role="maternal_body_detail",
        frame=_frame(frame_id="maternal_body_local_v1", extent=3.0),
        provenance=provenance,
        elements=(
            NavElementV1(
                element_id="maternal_body",
                role="maternal_body",
                geometry=_geometry(NavGeometryKindV1.SEGMENT, (-0.8, 0.0), (0.8, 0.0)),
                activations=(NavActivationV1("maternal_familiar", 0.95, provenance),),
                parent_element_id=None,
                provenance=provenance,
            ),
            NavElementV1(
                element_id="udder_region",
                role="udder_region",
                geometry=_geometry(NavGeometryKindV1.POINT, (0.4, -0.3)),
                activations=(NavActivationV1("feeding_relevant", 0.9, provenance),),
                parent_element_id="maternal_body",
                provenance=provenance,
            ),
        ),
    )


def _root_scene_map(detail_ref: NavMapRefV1) -> NavMapV2:
    """Return a root scene containing Mom geometry and one addressable detail link."""
    provenance = _provenance("fixture:root_scene")
    return NavMapV2(
        map_id="goat_root_scene",
        revision=1,
        role="root_scene",
        frame=_frame(frame_id="root_scene_v1", extent=5.0),
        provenance=provenance,
        elements=(
            NavElementV1(
                element_id="self_anchor",
                role="self_anchor",
                geometry=_geometry(NavGeometryKindV1.POINT, (0.0, 0.0)),
                activations=(NavActivationV1("self_related", 1.0, provenance),),
                parent_element_id=None,
                provenance=provenance,
            ),
            NavElementV1(
                element_id="mom",
                role="maternal_entity",
                geometry=_geometry(NavGeometryKindV1.POINT, (1.5, 0.5)),
                activations=(NavActivationV1("familiar_individual", 0.95, provenance),),
                parent_element_id=None,
                provenance=provenance,
            ),
        ),
        links=(
            NavMapLinkV1(
                link_type="detail",
                target_ref=detail_ref,
                source_element_id="mom",
                provenance=provenance,
            ),
        ),
    )


def _map_with_landmarks(*, map_id: str, count: int, reverse_input: bool = False) -> NavMapV2:
    """Return a deterministic map with ``count`` point elements inside a wide frame."""
    if count <= 0:
        raise ValueError("count must be positive")
    provenance = _provenance(f"fixture:{map_id}")
    elements = [
        NavElementV1(
            element_id=f"landmark_{index:03d}",
            role="landmark",
            geometry=_geometry(
                NavGeometryKindV1.POINT,
                ((index % 10) * 0.2, (index // 10) * 0.2),
            ),
            activations=(),
            parent_element_id=None,
            provenance=provenance,
        )
        for index in range(count)
    ]
    if reverse_input:
        elements.reverse()
    return NavMapV2(
        map_id=map_id,
        revision=1,
        role="landmark_scene",
        frame=_frame(frame_id="landmark_frame_v1", extent=25.0),
        provenance=provenance,
        elements=tuple(elements),
    )


def _resolve_map_ref(memory: ColumnMemory, target_ref: NavMapRefV1) -> NavMapV2:
    """Resolve one direct map reference by scanning this tiny Phase 1D test store.

    This is test-only proof of storage compatibility, not the future hippocampal
    associative retrieval mechanism.  It deliberately returns no activation,
    focus, candidate, acceptance, or root-WNM status.
    """
    matches: list[NavMapV2] = []
    for engram_id in memory.list_ids():
        record = memory.get(engram_id)
        payload = record.get("payload")
        if isinstance(payload, NavMapV2):
            if payload.map_id == target_ref.map_id and payload.revision == target_ref.revision:
                matches.append(payload)
    if len(matches) != 1:
        raise KeyError(f"expected exactly one stored map for {target_ref!r}, found {len(matches)}")
    return matches[0]


def test_navmap_stores_directly_through_existing_columnmemory_contract() -> None:
    """ColumnMemory should retain exact NavMap content without a special storage adapter."""
    memory = ColumnMemory(name="phase1d_column")
    navmap = _root_scene_map(NavMapRefV1("maternal_body_map", 3))
    before_bytes = navmap.to_bytes()
    before_content_signature = navmap.content_signature()
    before_record_signature = navmap.record_signature()

    engram_id = memory.assert_fact(
        "navmap:root_scene",
        navmap,
        FactMeta(name="navmap:root_scene", attrs={"phase": "1d"}),
    )
    stored = memory.get(engram_id)["payload"]

    assert stored is navmap
    assert stored.kind == "navmap"
    assert stored.fmt == "navmap/relational-json-v1"
    assert stored.shape == ()
    assert stored.meta()["map_id"] == "goat_root_scene"
    assert stored.to_bytes() == before_bytes
    assert stored.content_signature() == before_content_signature
    assert stored.record_signature() == before_record_signature

    decoded = NavMapV2.from_bytes(stored.to_bytes())
    assert decoded == navmap
    assert decoded.content_signature() == before_content_signature
    assert decoded.record_signature() == before_record_signature


def test_column_record_metadata_and_engram_ids_do_not_change_map_identity() -> None:
    """Storage UUIDs/timestamps belong to Column records, not immutable NavMap identity."""
    memory = ColumnMemory(name="phase1d_column")
    navmap = _root_scene_map(NavMapRefV1("maternal_body_map", 3))

    first_id = memory.assert_fact("navmap:first", navmap, FactMeta(name="navmap:first"))
    second_id = memory.assert_fact("navmap:second", navmap, FactMeta(name="navmap:second"))

    first_record = memory.get(first_id)
    second_record = memory.get(second_id)
    assert first_id != second_id
    assert first_record["meta"]["name"] != second_record["meta"]["name"]
    assert first_record["payload"].content_signature() == navmap.content_signature()
    assert second_record["payload"].content_signature() == navmap.content_signature()
    assert first_record["payload"].record_signature() == navmap.record_signature()
    assert second_record["payload"].record_signature() == navmap.record_signature()


def test_root_and_linked_detail_maps_are_separate_payloads_and_link_remains_reference() -> None:
    """A root scene can address a separately stored detail map without embedding or activating it."""
    memory = ColumnMemory(name="phase1d_column")
    detail = _maternal_detail_map()
    root = _root_scene_map(NavMapRefV1(detail.map_id, detail.revision))

    detail_engram_id = memory.assert_fact("navmap:maternal_detail", detail)
    root_engram_id = memory.assert_fact("navmap:root_scene", root)

    assert detail_engram_id != root_engram_id
    assert memory.get(detail_engram_id)["payload"] is detail
    assert memory.get(root_engram_id)["payload"] is root

    target_ref = follow_link(root, source_element_id="mom", link_type="detail")
    assert target_ref == NavMapRefV1("maternal_body_map", 3)
    assert isinstance(target_ref, NavMapRefV1)
    assert target_ref is not detail

    resolved = _resolve_map_ref(memory, target_ref)
    assert resolved is detail
    assert root.links[0].target_ref == target_ref
    assert root.content_signature() != detail.content_signature()


def test_direct_storage_and_resolution_do_not_confer_runtime_authority() -> None:
    """Stored/retrieved NavMaps remain content records rather than accepted current reality."""
    memory = ColumnMemory(name="phase1d_column")
    detail = _maternal_detail_map()
    root = _root_scene_map(NavMapRefV1(detail.map_id, detail.revision))
    memory.assert_fact("navmap:maternal_detail", detail)
    memory.assert_fact("navmap:root_scene", root)

    resolved = _resolve_map_ref(memory, follow_link(root, source_element_id="mom", link_type="detail"))

    for forbidden_attribute in ("candidate", "retrieved", "active", "focused", "accepted", "root_wnm"):
        assert not hasattr(root, forbidden_attribute)
        assert not hasattr(resolved, forbidden_attribute)
    assert resolved.provenance.source_class is NavSourceClassV1.OBSERVED
    assert resolved == detail


def test_storage_round_trip_preserves_constructor_order_independence() -> None:
    """Canonical map ordering remains deterministic before and after Column storage."""
    memory = ColumnMemory(name="phase1d_column")
    forward = _map_with_landmarks(map_id="ordering_map", count=40, reverse_input=False)
    reversed_input = _map_with_landmarks(map_id="ordering_map", count=40, reverse_input=True)

    assert forward.to_bytes() == reversed_input.to_bytes()
    assert forward.content_signature() == reversed_input.content_signature()
    assert forward.record_signature() == reversed_input.record_signature()

    first_id = memory.assert_fact("navmap:forward", forward)
    second_id = memory.assert_fact("navmap:reverse", reversed_input)
    first = NavMapV2.from_bytes(memory.get(first_id)["payload"].to_bytes())
    second = NavMapV2.from_bytes(memory.get(second_id)["payload"].to_bytes())
    assert first.to_bytes() == second.to_bytes()


def test_geometry_queries_are_deterministic_across_valid_frame_extents() -> None:
    """Changing only frame bounds changes map content identity, not geometry-derived measurements."""
    provenance = _provenance("fixture:frame_extent")
    elements = (
        NavElementV1(
            "point_a",
            "landmark",
            _geometry(NavGeometryKindV1.POINT, (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "point_b",
            "landmark",
            _geometry(NavGeometryKindV1.POINT, (3.0, 4.0)),
            (),
            None,
            provenance,
        ),
    )
    narrow = NavMapV2(
        map_id="frame_extent_map",
        revision=1,
        role="distance_scene",
        frame=_frame(frame_id="extent_frame", extent=5.0),
        provenance=provenance,
        elements=elements,
    )
    wide = replace(narrow, frame=_frame(frame_id="extent_frame", extent=50.0))

    narrow_distance = minimum_distance_between(narrow, "point_a", "point_b")
    wide_distance = minimum_distance_between(wide, "point_a", "point_b")
    assert narrow_distance.value == pytest.approx(5.0)
    assert wide_distance.value == pytest.approx(5.0)
    assert element_centroid(narrow, "point_b").point == element_centroid(wide, "point_b").point
    assert narrow.to_bytes() == narrow.to_bytes()
    assert wide.to_bytes() == wide.to_bytes()
    assert narrow.content_signature() != wide.content_signature()


def test_serialized_size_scales_with_represented_elements_not_frame_area() -> None:
    """Explicit-record storage grows with represented content rather than raster frame area."""
    one = _map_with_landmarks(map_id="size_one", count=1)
    ten = _map_with_landmarks(map_id="size_ten", count=10)
    hundred = _map_with_landmarks(map_id="size_hundred", count=100)

    assert len(one.to_bytes()) < len(ten.to_bytes()) < len(hundred.to_bytes())

    wide_one = replace(one, frame=_frame(frame_id=one.frame.frame_id, extent=1000.0))
    assert len(wide_one.elements) == len(one.elements) == 1
    assert len(wide_one.to_bytes()) - len(one.to_bytes()) < 20


def test_phase1d_storage_proof_uses_existing_columnmemory_without_special_adapter() -> None:
    """The storage proof uses the existing ColumnMemory API without a NavMap-specific adapter."""
    memory = ColumnMemory(name="phase1d_column")
    detail = _maternal_detail_map()
    root = _root_scene_map(NavMapRefV1(detail.map_id, detail.revision))

    memory.assert_fact("navmap:maternal_detail", detail)
    memory.assert_fact("navmap:root_scene", root)

    assert memory.count() == 2
    found = memory.find(name_contains="navmap:")
    assert len(found) == 2
    assert {record["name"] for record in found} == {"navmap:maternal_detail", "navmap:root_scene"}
    assert root.to_bytes() == NavMapV2.from_bytes(root.to_bytes()).to_bytes()
