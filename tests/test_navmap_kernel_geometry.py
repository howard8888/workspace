# -*- coding: utf-8 -*-
"""Phase 1B-A tests for pure, revision-linked NavMap geometry primitives."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json

import pytest

from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapRefV1,
    NavMapV2,
    NavPointQueryResultV1,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavScalarQueryResultV1,
    NavSourceClassV1,
    bearing_between_centroids,
    centroid_distance_between,
    element_centroid,
    geometry_orientation_degrees,
    get_element,
)


def _provenance() -> NavProvenanceV1:
    """Return identical deterministic source provenance for both body configurations."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.OBSERVED,
        source_ref="fixture:self_ground_geometry:1",
        quality=0.95,
    )


def _frame() -> NavFrameV1:
    """Return the Planning v11 SELF-ground sagittal frame."""
    return NavFrameV1(
        frame_id="self_sagittal_v1",
        x_axis="forward",
        y_axis="up",
        units="normalized",
        min_x=-3.0,
        max_x=3.0,
        min_y=-0.5,
        max_y=3.0,
    )


def _geometry(kind: NavGeometryKindV1, *points: tuple[float, float]) -> NavGeometryV1:
    """Build one geometry record from compact coordinate pairs."""
    return NavGeometryV1(kind=kind, points=tuple(NavPointV1(x=x, y=y) for x, y in points))


def _self_ground_map(*, body_horizontal: bool, map_id: str) -> NavMapV2:
    """Build one SELF-ground map; only coordinates vary between the two cases."""
    provenance = _provenance()
    if body_horizontal:
        body_points = ((-1.0, 0.2), (1.0, 0.2))
        head_point = (-1.2, 0.2)
        foot_point = (1.2, 0.0)
    else:
        body_points = ((0.0, 0.2), (0.0, 2.0))
        head_point = (0.0, 2.2)
        foot_point = (0.0, 0.0)

    body_activations = (
        NavActivationV1(name="body_axis", strength=0.95, provenance=provenance),
        NavActivationV1(name="self_related", strength=1.0, provenance=provenance),
    )
    part_activation = (NavActivationV1(name="body_part", strength=0.9, provenance=provenance),)
    elements = (
        NavElementV1(
            element_id="ground_surface",
            role="ground_surface",
            geometry=_geometry(NavGeometryKindV1.SEGMENT, (-3.0, 0.0), (3.0, 0.0)),
            activations=(NavActivationV1(name="surface", strength=1.0, provenance=provenance),),
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_body",
            role="self_body",
            geometry=_geometry(NavGeometryKindV1.SEGMENT, *body_points),
            activations=body_activations,
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_foot",
            role="self_foot",
            geometry=_geometry(NavGeometryKindV1.POINT, foot_point),
            activations=part_activation,
            parent_element_id="self_body",
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_head",
            role="self_head",
            geometry=_geometry(NavGeometryKindV1.POINT, head_point),
            activations=part_activation,
            parent_element_id="self_body",
            provenance=provenance,
        ),
    )
    relations = (
        NavRelationV1("part_of", "self_foot", "self_body", provenance),
        NavRelationV1("part_of", "self_head", "self_body", provenance),
    )
    return NavMapV2(
        map_id=map_id,
        revision=1,
        role="self_ground_scene",
        frame=_frame(),
        provenance=provenance,
        elements=elements,
        relations=relations,
    )


def _geometry_kind_map() -> NavMapV2:
    """Return a map containing each Phase 1 geometry kind for centroid tests."""
    provenance = _provenance()
    elements = (
        NavElementV1(
            "point",
            "landmark",
            _geometry(NavGeometryKindV1.POINT, (2.0, 1.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "segment",
            "boundary",
            _geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.0), (2.0, 2.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "polyline",
            "route",
            _geometry(NavGeometryKindV1.POLYLINE, (0.0, 0.0), (2.0, 0.0), (2.0, 2.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "polygon",
            "region",
            _geometry(NavGeometryKindV1.POLYGON, (0.0, 0.0), (3.0, 0.0), (0.0, 3.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "polygon_clockwise",
            "region",
            _geometry(NavGeometryKindV1.POLYGON, (0.0, 3.0), (3.0, 0.0), (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
    )
    return NavMapV2("geometry_kinds", 1, "geometry_test", _frame(), provenance, elements=elements)


def _semantic_skeleton(navmap: NavMapV2) -> tuple[object, ...]:
    """Return all content except element geometry and map record identity."""
    element_rows = tuple(
        (
            element.element_id,
            element.role,
            element.activations,
            element.parent_element_id,
            element.provenance,
        )
        for element in navmap.elements
    )
    return (
        navmap.schema,
        navmap.role,
        navmap.frame,
        navmap.provenance,
        element_rows,
        navmap.relations,
        navmap.links,
    )


def test_get_element_normalizes_ids_and_fails_explicitly() -> None:
    """Local lookup should be convenient but never silently return a poor match."""
    navmap = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")

    assert get_element(navmap, " SELF BODY ").element_id == "self_body"
    with pytest.raises(KeyError, match="missing_element"):
        get_element(navmap, "missing element")
    with pytest.raises(TypeError, match="navmap"):
        get_element(object(), "self_body")  # type: ignore[arg-type]


def test_element_centroid_uses_geometry_specific_centroids() -> None:
    """Centroids should reflect point, line-length, and polygon-area geometry."""
    navmap = _geometry_kind_map()

    point = element_centroid(navmap, "point")
    segment = element_centroid(navmap, "segment")
    polyline = element_centroid(navmap, "polyline")
    polygon = element_centroid(navmap, "polygon")
    polygon_clockwise = element_centroid(navmap, "polygon_clockwise")

    assert point.point == NavPointV1(2.0, 1.0)
    assert segment.point == NavPointV1(1.0, 1.0)
    assert polyline.point.x == pytest.approx(1.5)
    assert polyline.point.y == pytest.approx(0.5)
    assert polygon.point == NavPointV1(1.0, 1.0)
    assert polygon_clockwise.point == NavPointV1(1.0, 1.0)
    assert point.method == "point_coordinate"
    assert segment.method == "segment_midpoint"
    assert polyline.method == "length_weighted_segment_midpoints"
    assert polygon.method == "area_centroid"


def test_centroid_distance_is_euclidean_and_revision_linked() -> None:
    """A scalar distance should retain its source revision, frame, units, and metric."""
    navmap = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")

    result = centroid_distance_between(navmap, "ground_surface", "self_body")

    assert result.source_map_ref == NavMapRefV1("self_ground_case_a", 1)
    assert result.frame_id == "self_sagittal_v1"
    assert result.operator == "centroid_distance_between"
    assert result.element_ids == ("ground_surface", "self_body")
    assert result.value == pytest.approx(1.1)
    assert result.units == "normalized"
    assert result.method == "euclidean"


def test_bearing_uses_frame_axis_convention_and_rejects_coincident_centroids() -> None:
    """Bearing should be directed, counter-clockwise from +x, and undefined at zero displacement."""
    navmap = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")
    geometry_map = _geometry_kind_map()

    upward = bearing_between_centroids(navmap, "self_foot", "self_head")
    downward = bearing_between_centroids(navmap, "self_head", "self_foot")
    eastward = bearing_between_centroids(geometry_map, "polygon", "point")
    westward = bearing_between_centroids(geometry_map, "point", "polygon")

    assert upward.value == pytest.approx(90.0)
    assert downward.value == pytest.approx(270.0)
    assert eastward.value == pytest.approx(0.0)
    assert westward.value == pytest.approx(180.0)
    assert upward.method == "counterclockwise_from_positive_x"
    with pytest.raises(ValueError, match="coincident"):
        bearing_between_centroids(navmap, "self_foot", "self_foot")


def test_orientation_is_undirected_and_requires_an_axis_geometry() -> None:
    """Reversing an axis should preserve orientation; unsupported or degenerate axes should fail explicitly."""
    provenance = _provenance()
    elements = (
        NavElementV1(
            "vertical_up",
            "axis",
            _geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.0), (0.0, 2.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "vertical_down",
            "axis",
            _geometry(NavGeometryKindV1.SEGMENT, (0.0, 2.0), (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "horizontal_reverse",
            "axis",
            _geometry(NavGeometryKindV1.SEGMENT, (2.0, 0.0), (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "polyline",
            "route_axis",
            _geometry(NavGeometryKindV1.POLYLINE, (0.0, 0.0), (1.0, 1.0), (2.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "closed_polyline",
            "route_axis",
            _geometry(NavGeometryKindV1.POLYLINE, (0.0, 0.0), (1.0, 0.0), (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "point",
            "landmark",
            _geometry(NavGeometryKindV1.POINT, (0.0, 0.0)),
            (),
            None,
            provenance,
        ),
        NavElementV1(
            "polygon",
            "region",
            _geometry(NavGeometryKindV1.POLYGON, (0.0, 0.0), (1.0, 0.0), (0.0, 1.0)),
            (),
            None,
            provenance,
        ),
    )
    navmap = NavMapV2("orientation_map", 1, "orientation_test", _frame(), provenance, elements=elements)

    assert geometry_orientation_degrees(navmap, "vertical_up").value == pytest.approx(90.0)
    assert geometry_orientation_degrees(navmap, "vertical_down").value == pytest.approx(90.0)
    assert geometry_orientation_degrees(navmap, "horizontal_reverse").value == pytest.approx(0.0)
    polyline = geometry_orientation_degrees(navmap, "polyline")
    assert polyline.value == pytest.approx(0.0)
    assert polyline.method == "undirected_endpoint_chord_from_positive_x"
    with pytest.raises(ValueError, match="endpoints coincide"):
        geometry_orientation_degrees(navmap, "closed_polyline")
    with pytest.raises(ValueError, match="segment or polyline"):
        geometry_orientation_degrees(navmap, "point")
    with pytest.raises(ValueError, match="segment or polyline"):
        geometry_orientation_degrees(navmap, "polygon")


def test_two_body_configurations_differ_only_in_geometry_content() -> None:
    """The demonstrator inputs should share identities, roles, activations, relations, and provenance."""
    vertical = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")
    horizontal = _self_ground_map(body_horizontal=True, map_id="self_ground_case_b")

    assert _semantic_skeleton(vertical) == _semantic_skeleton(horizontal)
    assert tuple(element.element_id for element in vertical.elements) == tuple(
        element.element_id for element in horizontal.elements
    )
    assert tuple(element.geometry for element in vertical.elements) != tuple(
        element.geometry for element in horizontal.elements
    )
    assert vertical.content_signature() != horizontal.content_signature()

    encoded_content = vertical.to_bytes().decode("utf-8") + horizontal.to_bytes().decode("utf-8")
    for forbidden in ("posture", "standing", "fallen", "is_standing", "is_fallen"):
        assert forbidden not in encoded_content


def test_geometry_alone_changes_body_orientation_and_ground_distance() -> None:
    """The first map computation should change when only the spatial arrangement changes."""
    vertical = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")
    horizontal = _self_ground_map(body_horizontal=True, map_id="self_ground_case_b")

    vertical_orientation = geometry_orientation_degrees(vertical, "self_body")
    horizontal_orientation = geometry_orientation_degrees(horizontal, "self_body")
    vertical_distance = centroid_distance_between(vertical, "self_body", "ground_surface")
    horizontal_distance = centroid_distance_between(horizontal, "self_body", "ground_surface")

    assert vertical_orientation.value == pytest.approx(90.0)
    assert horizontal_orientation.value == pytest.approx(0.0)
    assert vertical_distance.value == pytest.approx(1.1)
    assert horizontal_distance.value == pytest.approx(0.2)


def test_query_results_are_immutable_and_json_safe() -> None:
    """Derived measurements should be inspectable records rather than contextless mutable numbers."""
    navmap = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")
    point_result = element_centroid(navmap, "self_body")
    scalar_result = geometry_orientation_degrees(navmap, "self_body")

    assert isinstance(point_result, NavPointQueryResultV1)
    assert isinstance(scalar_result, NavScalarQueryResultV1)
    assert json.loads(json.dumps(point_result.as_dict()))["point"] == {"x": 0.0, "y": 1.1}
    assert json.loads(json.dumps(scalar_result.as_dict()))["value"] == 90.0
    with pytest.raises(FrozenInstanceError):
        scalar_result.value = 0.0  # type: ignore[misc]


def test_geometry_queries_do_not_mutate_maps_or_signatures() -> None:
    """Pure query execution must leave canonical bytes and both signatures unchanged."""
    navmap = _self_ground_map(body_horizontal=False, map_id="self_ground_case_a")
    before_bytes = navmap.to_bytes()
    before_content_signature = navmap.content_signature()
    before_record_signature = navmap.record_signature()

    element_centroid(navmap, "self_body")
    centroid_distance_between(navmap, "self_body", "ground_surface")
    bearing_between_centroids(navmap, "self_foot", "self_head")
    geometry_orientation_degrees(navmap, "self_body")

    assert navmap.to_bytes() == before_bytes
    assert navmap.content_signature() == before_content_signature
    assert navmap.record_signature() == before_record_signature
