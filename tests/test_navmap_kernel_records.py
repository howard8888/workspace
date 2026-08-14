# -*- coding: utf-8 -*-
"""Phase 1A tests for the pure relational-spatial NavMap record kernel."""

from __future__ import annotations

from dataclasses import FrozenInstanceError
import json
import math

import pytest

from cca8_features import FeaturePayload
from cca8_navmap_kernel import (
    NAVMAP_FORMAT_V2,
    NAVMAP_KIND_V2,
    NAVMAP_SCHEMA_V2,
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
    NavRelationV1,
    NavSourceClassV1,
)


def _provenance(
    source_class: NavSourceClassV1 = NavSourceClassV1.OBSERVED,
    source_ref: str = "fixture:self_ground:1",
    quality: float = 0.9,
) -> NavProvenanceV1:
    """Return deterministic provenance for record tests."""
    return NavProvenanceV1(source_class=source_class, source_ref=source_ref, quality=quality)


def _frame() -> NavFrameV1:
    """Return the continuous sagittal frame planned for the first demonstrator."""
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
    """Build geometry from concise coordinate tuples."""
    return NavGeometryV1(kind=kind, points=tuple(NavPointV1(x=x, y=y) for x, y in points))


def _elements(*, reverse: bool = False, body_end_x: float = 0.0) -> tuple[NavElementV1, ...]:
    """Return a small continuous SELF-ground-maternal map element set."""
    provenance = _provenance()
    body_activations = (
        NavActivationV1(name="body_axis", strength=0.95, provenance=provenance),
        NavActivationV1(name="self_related", strength=1.0, provenance=provenance),
    )
    elements = [
        NavElementV1(
            element_id="ground_surface",
            role="ground_surface",
            geometry=_geometry(NavGeometryKindV1.SEGMENT, (-3.0, 0.0), (3.0, 0.0)),
            activations=(),
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_body",
            role="self_body",
            geometry=_geometry(NavGeometryKindV1.SEGMENT, (0.0, 0.2), (body_end_x, 2.0)),
            activations=tuple(reversed(body_activations)) if reverse else body_activations,
            parent_element_id=None,
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_foot",
            role="self_foot",
            geometry=_geometry(NavGeometryKindV1.POINT, (0.0, 0.0)),
            activations=(),
            parent_element_id="self_body",
            provenance=provenance,
        ),
        NavElementV1(
            element_id="self_head",
            role="self_head",
            geometry=_geometry(NavGeometryKindV1.POINT, (body_end_x, 2.2)),
            activations=(),
            parent_element_id="self_body",
            provenance=provenance,
        ),
        NavElementV1(
            element_id="mom",
            role="mom",
            geometry=_geometry(NavGeometryKindV1.POINT, (2.0, 0.0)),
            activations=(NavActivationV1(name="maternal_cue", strength=0.8, provenance=provenance),),
            parent_element_id=None,
            provenance=provenance,
        ),
    ]
    if reverse:
        elements.reverse()
    return tuple(elements)


def _map(
    *,
    map_id: str = "goat_local_map",
    revision: int = 1,
    parent_ref: NavMapRefV1 | None = None,
    reverse: bool = False,
    body_end_x: float = 0.0,
) -> NavMapV2:
    """Return a representative Phase 1A NavMapV2 fixture."""
    provenance = _provenance()
    relations = [
        NavRelationV1(
            relation_type="connected_to",
            source_element_id="self_foot",
            target_element_id="self_body",
            provenance=provenance,
        ),
        NavRelationV1(
            relation_type="part_of",
            source_element_id="self_head",
            target_element_id="self_body",
            provenance=provenance,
        ),
    ]
    links = [
        NavMapLinkV1(
            link_type="detail",
            target_ref=NavMapRefV1(map_id="maternal_body_map", revision=1),
            source_element_id="mom",
            provenance=NavProvenanceV1(
                source_class=NavSourceClassV1.RETRIEVED,
                source_ref="fixture:maternal_link:1",
                quality=0.7,
            ),
        ),
        NavMapLinkV1(
            link_type="context",
            target_ref=NavMapRefV1(map_id="local_terrain_map", revision=3),
            source_element_id=None,
            provenance=provenance,
        ),
    ]
    if reverse:
        relations.reverse()
        links.reverse()
    return NavMapV2(
        map_id=map_id,
        revision=revision,
        parent_ref=parent_ref,
        role="body_ground_scene",
        frame=_frame(),
        elements=_elements(reverse=reverse, body_end_x=body_end_x),
        relations=tuple(relations),
        links=tuple(links),
        provenance=provenance,
    )


def _payload_contract(payload: FeaturePayload) -> tuple[str, str, tuple[int, ...], bytes]:
    """Exercise the existing structural Column payload protocol."""
    return payload.kind, payload.fmt, payload.shape, payload.to_bytes()


def test_navmap_v2_satisfies_feature_payload_contract_and_meta() -> None:
    """The pure NavMap record should fit the existing non-tensor payload seam."""
    navmap = _map()

    kind, fmt, shape, payload_bytes = _payload_contract(navmap)
    meta = navmap.meta()

    assert kind == NAVMAP_KIND_V2 == "navmap"
    assert fmt == NAVMAP_FORMAT_V2 == "navmap/relational-json-v1"
    assert shape == ()
    assert payload_bytes == navmap.to_bytes()
    assert meta == {
        "kind": "navmap",
        "fmt": "navmap/relational-json-v1",
        "shape": (),
        "schema": NAVMAP_SCHEMA_V2,
        "map_id": "goat_local_map",
        "revision": 1,
        "role": "body_ground_scene",
        "frame_id": "self_sagittal_v1",
        "element_count": 5,
        "relation_count": 2,
        "link_count": 2,
    }
    json.dumps(meta)


def test_records_normalize_identifiers_floats_and_collection_order() -> None:
    """Construction should produce one immutable canonical representation."""
    provenance = NavProvenanceV1("OBSERVED", "fixture:source:1", 1)  # type: ignore[arg-type]
    point = NavPointV1(x=-0.0, y=1)
    frame = NavFrameV1(" SELF Sagittal V1 ", " Forward ", " UP ", " Normalized ", -3, 3, -0.5, 3)
    activation_a = NavActivationV1(" self related ", 1, provenance)
    activation_b = NavActivationV1("body axis", 0.5, provenance)
    element = NavElementV1(
        element_id=" SELF BODY ",
        role=" Self Body ",
        geometry=NavGeometryV1("segment", (NavPointV1(0, 0), NavPointV1(0, 1))),  # type: ignore[arg-type]
        activations=(activation_a, activation_b),
        parent_element_id=None,
        provenance=provenance,
    )

    assert provenance.source_class is NavSourceClassV1.OBSERVED
    assert provenance.quality == 1.0
    assert point.x == 0.0 and math.copysign(1.0, point.x) == 1.0
    assert frame.frame_id == "self_sagittal_v1"
    assert frame.x_axis == "forward" and frame.y_axis == "up"
    assert element.element_id == "self_body"
    assert element.role == "self_body"
    assert [activation.name for activation in element.activations] == ["body_axis", "self_related"]


@pytest.mark.parametrize("quality", [-0.01, 1.01, float("nan"), float("inf")])
def test_provenance_rejects_invalid_quality(quality: float) -> None:
    """Source quality must remain finite and within its declared engineering range."""
    with pytest.raises(ValueError):
        NavProvenanceV1(NavSourceClassV1.OBSERVED, "fixture:source:1", quality)


def test_provenance_rejects_absolute_paths_and_empty_references() -> None:
    """Machine-specific paths and empty provenance must not enter content identity."""
    with pytest.raises(ValueError):
        NavProvenanceV1(NavSourceClassV1.OBSERVED, "/tmp/private/sample.json", 1.0)
    with pytest.raises(ValueError):
        NavProvenanceV1(NavSourceClassV1.OBSERVED, r"C:\workspace\sample.json", 1.0)
    with pytest.raises(ValueError):
        NavProvenanceV1(NavSourceClassV1.OBSERVED, "   ", 1.0)


def test_map_reference_and_frame_validation_are_explicit() -> None:
    """Lineage and continuous-frame contracts should fail early and clearly."""
    with pytest.raises(ValueError):
        NavMapRefV1(map_id="map", revision=0)
    with pytest.raises(TypeError):
        NavMapRefV1(map_id="map", revision=True)  # type: ignore[arg-type]
    with pytest.raises(ValueError):
        NavFrameV1("frame", "forward", "forward", "m", 0, 1, 0, 1)
    with pytest.raises(ValueError):
        NavFrameV1("frame", "right", "forward", "m", 1, 1, 0, 1)
    with pytest.raises(ValueError):
        NavFrameV1("frame", "right", "forward", "m", 0, float("inf"), 0, 1)


def test_geometry_kinds_enforce_point_counts_and_non_degeneracy() -> None:
    """Point, segment, polyline, and polygon records should preserve real geometry."""
    with pytest.raises(ValueError):
        NavGeometryV1(NavGeometryKindV1.POINT, (NavPointV1(0, 0), NavPointV1(1, 1)))
    with pytest.raises(ValueError):
        NavGeometryV1(NavGeometryKindV1.SEGMENT, (NavPointV1(0, 0), NavPointV1(0, 0)))
    with pytest.raises(ValueError):
        NavGeometryV1(NavGeometryKindV1.POLYLINE, (NavPointV1(0, 0),))
    with pytest.raises(ValueError):
        NavGeometryV1(
            NavGeometryKindV1.POLYGON,
            (NavPointV1(0, 0), NavPointV1(1, 1), NavPointV1(2, 2)),
        )

    polygon = NavGeometryV1(
        NavGeometryKindV1.POLYGON,
        (NavPointV1(0, 0), NavPointV1(2, 0), NavPointV1(1, 1)),
    )
    assert polygon.kind is NavGeometryKindV1.POLYGON
    assert len(polygon.points) == 3


def test_navmap_rejects_geometry_outside_declared_frame() -> None:
    """A map may not silently contain coordinates from an undeclared spatial extent."""
    provenance = _provenance()
    outside = NavElementV1(
        element_id="outside",
        role="landmark",
        geometry=_geometry(NavGeometryKindV1.POINT, (4.0, 0.0)),
        activations=(),
        parent_element_id=None,
        provenance=provenance,
    )
    with pytest.raises(ValueError, match="outside the declared frame"):
        NavMapV2(
            map_id="bad_map",
            revision=1,
            role="scene",
            frame=_frame(),
            provenance=provenance,
            elements=(outside,),
        )


def test_navmap_validates_element_parents_relations_links_and_duplicates() -> None:
    """Every local reference should resolve and every structural row should be unique."""
    provenance = _provenance()
    element = _elements()[0]

    missing_parent = NavElementV1(
        element_id="child",
        role="object_part",
        geometry=_geometry(NavGeometryKindV1.POINT, (0.0, 0.0)),
        activations=(),
        parent_element_id="missing",
        provenance=provenance,
    )
    with pytest.raises(ValueError, match="does not exist"):
        NavMapV2("bad_parent", 1, "scene", _frame(), provenance, elements=(missing_parent,))

    relation = NavRelationV1("connected_to", element.element_id, "missing", provenance)
    with pytest.raises(ValueError, match="relation endpoints"):
        NavMapV2("bad_relation", 1, "scene", _frame(), provenance, elements=(element,), relations=(relation,))

    link = NavMapLinkV1("detail", NavMapRefV1("other", 1), "missing", provenance)
    with pytest.raises(ValueError, match="source_element_id"):
        NavMapV2("bad_link", 1, "scene", _frame(), provenance, elements=(element,), links=(link,))

    with pytest.raises(ValueError, match="element ids"):
        NavMapV2("duplicate_elements", 1, "scene", _frame(), provenance, elements=(element, element))


def test_parent_hierarchy_rejects_cycles() -> None:
    """Part hierarchies may have several roots but cannot contain loops."""
    provenance = _provenance()
    element_a = NavElementV1(
        "a",
        "object_part",
        _geometry(NavGeometryKindV1.POINT, (0, 0)),
        (),
        "b",
        provenance,
    )
    element_b = NavElementV1(
        "b",
        "object_part",
        _geometry(NavGeometryKindV1.POINT, (1, 0)),
        (),
        "a",
        provenance,
    )
    with pytest.raises(ValueError, match="cycle"):
        NavMapV2("cyclic_map", 1, "object", _frame(), provenance, elements=(element_a, element_b))


def test_duplicate_activations_relations_and_links_are_rejected() -> None:
    """Canonical tuples must not hide duplicate structural content."""
    provenance = _provenance()
    activation = NavActivationV1("shape", 0.8, provenance)
    with pytest.raises(ValueError, match="duplicate activation"):
        NavElementV1(
            "object",
            "object",
            _geometry(NavGeometryKindV1.POINT, (0, 0)),
            (activation, activation),
            None,
            provenance,
        )

    navmap = _map()
    with pytest.raises(ValueError, match="duplicate relations"):
        NavMapV2(
            "duplicate_relations",
            1,
            navmap.role,
            navmap.frame,
            navmap.provenance,
            elements=navmap.elements,
            relations=(navmap.relations[0], navmap.relations[0]),
        )
    with pytest.raises(ValueError, match="duplicate map links"):
        NavMapV2(
            "duplicate_links",
            1,
            navmap.role,
            navmap.frame,
            navmap.provenance,
            elements=navmap.elements,
            links=(navmap.links[0], navmap.links[0]),
        )


def test_constructor_order_does_not_change_canonical_bytes_or_signatures() -> None:
    """Semantic content should not depend on caller list ordering."""
    forward = _map(reverse=False)
    reversed_input = _map(reverse=True)

    assert forward == reversed_input
    assert forward.to_bytes() == reversed_input.to_bytes()
    assert forward.content_signature() == reversed_input.content_signature()
    assert forward.record_signature() == reversed_input.record_signature()
    assert [element.element_id for element in forward.elements] == sorted(
        element.element_id for element in forward.elements
    )


def test_canonical_json_round_trip_is_exact_and_deterministic() -> None:
    """Canonical bytes should decode to the same immutable map and re-encode exactly."""
    original = _map()
    encoded = original.to_bytes()
    restored = NavMapV2.from_bytes(encoded)

    assert restored == original
    assert restored.to_bytes() == encoded
    assert restored.as_dict() == original.as_dict()
    assert json.loads(encoded.decode("utf-8"))["schema"] == NAVMAP_SCHEMA_V2
    assert b" " not in encoded and b"\n" not in encoded


def test_content_signature_excludes_identity_and_lineage_but_record_signature_does_not() -> None:
    """Equivalent decoded maps may have different stored identities and revisions."""
    first = _map(map_id="map_a", revision=1)
    second_identity = _map(map_id="map_b", revision=1)
    later_revision = _map(map_id="map_a", revision=2, parent_ref=NavMapRefV1("map_a", 1))

    assert first.content_signature() == second_identity.content_signature() == later_revision.content_signature()
    assert first.record_signature() != second_identity.record_signature()
    assert first.record_signature() != later_revision.record_signature()


def test_geometry_changes_content_signature_without_symbolic_posture_fields() -> None:
    """Geometry itself must affect map identity before any posture query exists."""
    vertical = _map(body_end_x=0.0)
    slanted = _map(body_end_x=1.5)

    assert vertical.content_signature() != slanted.content_signature()
    assert not hasattr(vertical, "posture")
    assert not hasattr(vertical, "fallen")
    assert not hasattr(vertical, "standing")
    assert not hasattr(vertical, "cells")
    assert not hasattr(vertical, "grid_w")
    assert not hasattr(vertical, "accepted")


def test_frozen_records_do_not_alias_caller_owned_lists() -> None:
    """Normalization should detach immutable tuples from mutable constructor inputs."""
    provenance = _provenance()
    points = [NavPointV1(0, 0), NavPointV1(0, 1)]
    activations = [NavActivationV1("body_axis", 1.0, provenance)]
    geometry = NavGeometryV1(NavGeometryKindV1.SEGMENT, points)  # type: ignore[arg-type]
    element = NavElementV1("self_body", "self_body", geometry, activations, None, provenance)  # type: ignore[arg-type]
    elements = [element]
    navmap = NavMapV2("immutable_map", 1, "body_ground", _frame(), provenance, elements=elements)  # type: ignore[arg-type]

    points.append(NavPointV1(1, 1))
    activations.clear()
    elements.clear()

    assert len(navmap.elements) == 1
    assert len(navmap.elements[0].geometry.points) == 2
    assert len(navmap.elements[0].activations) == 1
    with pytest.raises(FrozenInstanceError):
        navmap.revision = 2  # type: ignore[misc]


def test_lineage_validation_requires_matching_earlier_parent() -> None:
    """A parent reference must belong to the same map family and precede the child."""
    with pytest.raises(ValueError, match="map_id"):
        _map(map_id="child", revision=2, parent_ref=NavMapRefV1("different", 1))
    with pytest.raises(ValueError, match="lower"):
        _map(map_id="child", revision=2, parent_ref=NavMapRefV1("child", 2))


def test_deserialization_rejects_bad_schema_unknown_fields_and_invalid_json() -> None:
    """Versioned payload decoding should fail instead of silently accepting drift."""
    data = _map().as_dict()
    bad_schema = dict(data)
    bad_schema["schema"] = "navmap_v999"
    with pytest.raises(ValueError, match="unsupported"):
        NavMapV2.from_dict(bad_schema)

    unknown_field = dict(data)
    unknown_field["accepted"] = True
    with pytest.raises(ValueError, match="unknown fields"):
        NavMapV2.from_dict(unknown_field)

    with pytest.raises(ValueError, match="invalid"):
        NavMapV2.from_bytes(b"not-json")
    with pytest.raises(TypeError):
        NavMapV2.from_bytes("not-bytes")  # type: ignore[arg-type]
