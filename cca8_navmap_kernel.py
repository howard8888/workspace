# -*- coding: utf-8 -*-
"""Pure relational-spatial Navigation Map records for CCA8.

Purpose
-------
This module defines the first immutable record kernel for the CCA8 NavMap-first
architecture.  It deliberately models the *decoded architecture-level content*
of a distributed cortical Column/NavMap.  It does not claim that biological
cortex literally stores Python objects, graph nodes, polygons, or JSON.

One conceptual Column is treated as a local distributed processing and memory
unit capable of representing many places, objects, regions, geometries, and
relationships.  ``NavMapV2`` is the explicit, inspectable interface exposed by
that assumed distributed representation so that CCA8 can test map operations
without first choosing a neuronal, ANN-like, attractor-like, or hippocampal-like
microimplementation.

Phase 1A scope
--------------
The module contains records, validation, canonical ordering, deterministic JSON
serialization, and content/record signatures only.  It does not:

- grant Working Navigation Map authority;
- integrate with ``Ctx``, WorkingMap, PolicyRuntime, BodyMap, or the runner;
- select or execute a policy;
- write WorldGraph or Column memory;
- perform geometry queries, rendering, alignment, matching, or revision;
- use raster cells as the fundamental map representation.

A later 6x6 or 12x12 display is only a diagnostic rendering of continuous map
geometry.  Rendering resolution must never change map identity or cognition.
The existing ``cca8_navmap.NavMapPayloadV1`` remains the compact slot-based
compatibility/predictive scaffold, and ``cca8_navpatch.SurfaceGridV1`` remains a
separate derived topology representation.

Design invariants
-----------------
- Records are frozen, slot-based dataclasses.
- Collections are immutable tuples and are normalized to deterministic order.
- Geometry uses explicit continuous reference frames and finite coordinates.
- Distances, bearings, contact, support, and posture-like readouts are derived
  later from geometry rather than stored as independent world-state shortcuts.
- Source provenance describes how content arose; current-world authority is a
  separate future WorkingMap relationship.
- Canonical bytes exclude runtime timestamps, generated UUIDs, absolute paths,
  counters, and arbitrary mutable metadata.
- ``content_signature()`` identifies decoded content while excluding map
  identity and lineage; ``record_signature()`` identifies the exact revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import hashlib
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Mapping, Optional, TypeVar

__version__ = "0.1.0"

NAVMAP_SCHEMA_V2 = "navmap_v2"
NAVMAP_KIND_V2 = "navmap"
NAVMAP_FORMAT_V2 = "navmap/relational-json-v1"

__all__ = [
    "NAVMAP_SCHEMA_V2",
    "NAVMAP_KIND_V2",
    "NAVMAP_FORMAT_V2",
    "NavSourceClassV1",
    "NavProvenanceV1",
    "NavMapRefV1",
    "NavPointV1",
    "NavFrameV1",
    "NavActivationV1",
    "NavGeometryKindV1",
    "NavGeometryV1",
    "NavElementV1",
    "NavRelationV1",
    "NavMapLinkV1",
    "NavMapV2",
    "__version__",
]

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_.:/-]*$")
_POLYGON_AREA_EPSILON = 1.0e-12
_EnumT = TypeVar("_EnumT", bound=Enum)


def _normalize_identifier(value: str, *, field_name: str) -> str:
    """Return one deterministic identifier or raise a descriptive error.

    Identifiers are deliberately modest rather than ontology-like.  Leading and
    trailing whitespace is removed, internal whitespace becomes underscores,
    and the identifier is lower-cased.  Colons, dots, slashes, and hyphens are
    retained because existing CCA8 names and future map addresses may use them.
    """
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = "_".join(value.strip().lower().split())
    if not normalized:
        raise ValueError(f"{field_name} must not be empty")
    if not _IDENTIFIER_RE.fullmatch(normalized):
        raise ValueError(f"{field_name} contains unsupported characters: {value!r}")
    return normalized


def _normalize_source_ref(value: str) -> str:
    """Return a stable non-path provenance reference.

    Source references may identify a sensor sample, operator, map, episode, or
    deterministic fixture.  Absolute filesystem paths are rejected because
    machine-specific paths must not alter NavMap content identity.
    """
    if not isinstance(value, str):
        raise TypeError("source_ref must be a string")
    normalized = " ".join(value.strip().split())
    if not normalized:
        raise ValueError("source_ref must not be empty")
    if any(ord(char) < 32 for char in normalized):
        raise ValueError("source_ref must not contain control characters")
    if PurePosixPath(normalized).is_absolute() or PureWindowsPath(normalized).is_absolute():
        raise ValueError("source_ref must not be an absolute filesystem path")
    return normalized


def _normalize_optional_identifier(value: Optional[str], *, field_name: str) -> Optional[str]:
    """Normalize an optional local identifier."""
    if value is None:
        return None
    return _normalize_identifier(value, field_name=field_name)


def _finite_float(value: float, *, field_name: str) -> float:
    """Return a finite float while rejecting booleans and non-numeric values."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be a real number")
    normalized = float(value)
    if not math.isfinite(normalized):
        raise ValueError(f"{field_name} must be finite")
    if normalized == 0.0:
        return 0.0
    return normalized


def _unit_interval(value: float, *, field_name: str) -> float:
    """Return a finite value in the inclusive interval 0.0 through 1.0."""
    normalized = _finite_float(value, field_name=field_name)
    if not 0.0 <= normalized <= 1.0:
        raise ValueError(f"{field_name} must be between 0.0 and 1.0")
    return normalized


def _positive_revision(value: int, *, field_name: str = "revision") -> int:
    """Return a positive integer revision while rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _require_instance(value: object, expected_type: type[Any], *, field_name: str) -> None:
    """Raise TypeError when a nested record has the wrong runtime type."""
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be {expected_type.__name__}")


def _require_exact_keys(data: Mapping[str, Any], *, expected: set[str], record_name: str) -> None:
    """Reject missing or unknown serialized fields for a versioned record."""
    actual = set(data.keys())
    missing = expected - actual
    unknown = actual - expected
    if missing:
        raise ValueError(f"{record_name} is missing fields: {sorted(missing)}")
    if unknown:
        raise ValueError(f"{record_name} has unknown fields: {sorted(unknown)}")


def _as_mapping(value: Any, *, record_name: str) -> Mapping[str, Any]:
    """Return a mapping decoded from JSON or raise a clear error."""
    if not isinstance(value, Mapping):
        raise ValueError(f"{record_name} must decode to a JSON object")
    for key in value:
        if not isinstance(key, str):
            raise ValueError(f"{record_name} keys must be strings")
    return value


def _canonical_json_bytes(data: Mapping[str, Any]) -> bytes:
    """Encode one JSON-safe mapping in the canonical NavMap byte form."""
    text = json.dumps(
        data,
        ensure_ascii=False,
        allow_nan=False,
        sort_keys=True,
        separators=(",", ":"),
    )
    return text.encode("utf-8")


def _sha256_hex(data: bytes) -> str:
    """Return the lowercase SHA-256 hexadecimal digest of bytes."""
    return hashlib.sha256(data).hexdigest()


def _enum_member(enum_type: type[_EnumT], value: object, *, field_name: str) -> _EnumT:
    """Normalize an enum instance or serialized enum value."""
    if isinstance(value, enum_type):
        return value
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be {enum_type.__name__} or str")
    normalized = value.strip().lower()
    try:
        return enum_type(normalized)
    except ValueError as exc:
        choices = sorted(str(member.value) for member in enum_type)
        raise ValueError(f"{field_name} must be one of {choices}") from exc


def _polygon_twice_signed_area(points: tuple["NavPointV1", ...]) -> float:
    """Return twice the signed area of an ordered polygon point sequence."""
    area = 0.0
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        area += point.x * next_point.y - next_point.x * point.y
    return area


class NavSourceClassV1(str, Enum):
    """Describe how decoded NavMap content arose, not its current authority."""

    OBSERVED = "observed"
    EXPECTED = "expected"
    INFERRED = "inferred"
    RETRIEVED = "retrieved"
    IMAGINED = "imagined"
    HISTORICAL = "historical"
    UNKNOWN = "unknown"


class NavGeometryKindV1(str, Enum):
    """Supported continuous geometry forms for the Phase 1 NavMap kernel."""

    POINT = "point"
    SEGMENT = "segment"
    POLYLINE = "polyline"
    POLYGON = "polygon"


@dataclass(frozen=True, slots=True)
class NavProvenanceV1:
    """Immutable source and quality descriptor for decoded map content.

    ``quality`` is a bounded engineering value whose semantics must be stated by
    the producing source.  It is not automatically a probability, confidence,
    firing rate, or authority score.
    """

    source_class: NavSourceClassV1
    source_ref: str
    quality: float

    def __post_init__(self) -> None:
        source_class = _enum_member(NavSourceClassV1, self.source_class, field_name="source_class")
        object.__setattr__(self, "source_class", source_class)
        object.__setattr__(self, "source_ref", _normalize_source_ref(self.source_ref))
        object.__setattr__(self, "quality", _unit_interval(self.quality, field_name="quality"))

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "source_class": self.source_class.value,
            "source_ref": self.source_ref,
            "quality": self.quality,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavProvenanceV1":
        """Decode one exact provenance record from a mapping."""
        _require_exact_keys(data, expected={"source_class", "source_ref", "quality"}, record_name=cls.__name__)
        return cls(
            source_class=_enum_member(NavSourceClassV1, data["source_class"], field_name="source_class"),
            source_ref=str(data["source_ref"]),
            quality=data["quality"],
        )


@dataclass(frozen=True, slots=True)
class NavMapRefV1:
    """Address one immutable revision within a stable NavMap family."""

    map_id: str
    revision: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "map_id", _normalize_identifier(self.map_id, field_name="map_id"))
        object.__setattr__(self, "revision", _positive_revision(self.revision))

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {"map_id": self.map_id, "revision": self.revision}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavMapRefV1":
        """Decode one exact NavMap reference from a mapping."""
        _require_exact_keys(data, expected={"map_id", "revision"}, record_name=cls.__name__)
        return cls(map_id=str(data["map_id"]), revision=data["revision"])


@dataclass(frozen=True, slots=True)
class NavPointV1:
    """One finite continuous coordinate in a declared NavMap frame."""

    x: float
    y: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x", _finite_float(self.x, field_name="x"))
        object.__setattr__(self, "y", _finite_float(self.y, field_name="y"))

    def as_dict(self) -> dict[str, float]:
        """Return the canonical JSON-safe coordinate."""
        return {"x": self.x, "y": self.y}

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavPointV1":
        """Decode one exact point from a mapping."""
        _require_exact_keys(data, expected={"x", "y"}, record_name=cls.__name__)
        return cls(x=data["x"], y=data["y"])


@dataclass(frozen=True, slots=True)
class NavFrameV1:
    """Continuous two-dimensional reference frame for one NavMap revision.

    Bounds validate geometry and support later diagnostic rendering.  They do
    not divide the map into cortical cells or make a raster the storage model.
    """

    frame_id: str
    x_axis: str
    y_axis: str
    units: str
    min_x: float
    max_x: float
    min_y: float
    max_y: float

    def __post_init__(self) -> None:
        frame_id = _normalize_identifier(self.frame_id, field_name="frame_id")
        x_axis = _normalize_identifier(self.x_axis, field_name="x_axis")
        y_axis = _normalize_identifier(self.y_axis, field_name="y_axis")
        units = _normalize_identifier(self.units, field_name="units")
        min_x = _finite_float(self.min_x, field_name="min_x")
        max_x = _finite_float(self.max_x, field_name="max_x")
        min_y = _finite_float(self.min_y, field_name="min_y")
        max_y = _finite_float(self.max_y, field_name="max_y")
        if x_axis == y_axis:
            raise ValueError("x_axis and y_axis must be distinct")
        if min_x >= max_x:
            raise ValueError("min_x must be less than max_x")
        if min_y >= max_y:
            raise ValueError("min_y must be less than max_y")
        object.__setattr__(self, "frame_id", frame_id)
        object.__setattr__(self, "x_axis", x_axis)
        object.__setattr__(self, "y_axis", y_axis)
        object.__setattr__(self, "units", units)
        object.__setattr__(self, "min_x", min_x)
        object.__setattr__(self, "max_x", max_x)
        object.__setattr__(self, "min_y", min_y)
        object.__setattr__(self, "max_y", max_y)

    def contains(self, point: NavPointV1) -> bool:
        """Return whether a point lies within the inclusive declared bounds."""
        _require_instance(point, NavPointV1, field_name="point")
        return self.min_x <= point.x <= self.max_x and self.min_y <= point.y <= self.max_y

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe frame record."""
        return {
            "frame_id": self.frame_id,
            "x_axis": self.x_axis,
            "y_axis": self.y_axis,
            "units": self.units,
            "min_x": self.min_x,
            "max_x": self.max_x,
            "min_y": self.min_y,
            "max_y": self.max_y,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavFrameV1":
        """Decode one exact frame record from a mapping."""
        expected = {"frame_id", "x_axis", "y_axis", "units", "min_x", "max_x", "min_y", "max_y"}
        _require_exact_keys(data, expected=expected, record_name=cls.__name__)
        return cls(
            frame_id=str(data["frame_id"]),
            x_axis=str(data["x_axis"]),
            y_axis=str(data["y_axis"]),
            units=str(data["units"]),
            min_x=data["min_x"],
            max_x=data["max_x"],
            min_y=data["min_y"],
            max_y=data["max_y"],
        )


@dataclass(frozen=True, slots=True)
class NavActivationV1:
    """One decoded local feature activation within a distributed Column map.

    The activation is an architecture-level description.  It is not a physical
    subcell, a claimed firing rate, or an independent symbolic world state.
    """

    name: str
    strength: float
    provenance: NavProvenanceV1

    def __post_init__(self) -> None:
        _require_instance(self.provenance, NavProvenanceV1, field_name="provenance")
        object.__setattr__(self, "name", _normalize_identifier(self.name, field_name="activation name"))
        object.__setattr__(self, "strength", _unit_interval(self.strength, field_name="strength"))

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe activation record."""
        return {
            "name": self.name,
            "strength": self.strength,
            "provenance": self.provenance.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavActivationV1":
        """Decode one exact activation record from a mapping."""
        _require_exact_keys(data, expected={"name", "strength", "provenance"}, record_name=cls.__name__)
        provenance_data = _as_mapping(data["provenance"], record_name="NavProvenanceV1")
        return cls(
            name=str(data["name"]),
            strength=data["strength"],
            provenance=NavProvenanceV1.from_dict(provenance_data),
        )


@dataclass(frozen=True, slots=True)
class NavGeometryV1:
    """Ordered continuous geometry for one decoded NavMap element."""

    kind: NavGeometryKindV1
    points: tuple[NavPointV1, ...]

    def __post_init__(self) -> None:
        kind = _enum_member(NavGeometryKindV1, self.kind, field_name="geometry kind")
        points = tuple(self.points)
        for point in points:
            _require_instance(point, NavPointV1, field_name="geometry point")

        if kind is NavGeometryKindV1.POINT and len(points) != 1:
            raise ValueError("point geometry requires exactly one point")
        if kind is NavGeometryKindV1.SEGMENT:
            if len(points) != 2:
                raise ValueError("segment geometry requires exactly two points")
            if points[0] == points[1]:
                raise ValueError("segment geometry points must be distinct")
        if kind is NavGeometryKindV1.POLYLINE:
            if len(points) < 2:
                raise ValueError("polyline geometry requires at least two points")
            if len(set(points)) < 2:
                raise ValueError("polyline geometry requires at least two distinct points")
        if kind is NavGeometryKindV1.POLYGON:
            if len(points) < 3:
                raise ValueError("polygon geometry requires at least three points")
            if len(set(points)) < 3:
                raise ValueError("polygon geometry requires at least three distinct points")
            if abs(_polygon_twice_signed_area(points)) <= _POLYGON_AREA_EPSILON:
                raise ValueError("polygon geometry points must not be collinear")

        object.__setattr__(self, "kind", kind)
        object.__setattr__(self, "points", points)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe geometry record."""
        return {
            "kind": self.kind.value,
            "points": [point.as_dict() for point in self.points],
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavGeometryV1":
        """Decode one exact geometry record from a mapping."""
        _require_exact_keys(data, expected={"kind", "points"}, record_name=cls.__name__)
        raw_points = data["points"]
        if not isinstance(raw_points, list):
            raise ValueError("NavGeometryV1 points must be a JSON list")
        points = tuple(NavPointV1.from_dict(_as_mapping(row, record_name="NavPointV1")) for row in raw_points)
        return cls(
            kind=_enum_member(NavGeometryKindV1, data["kind"], field_name="geometry kind"),
            points=points,
        )


@dataclass(frozen=True, slots=True)
class NavElementV1:
    """One decoded object, part, place, region, surface, or boundary.

    An element is an inspectable software handle inside one map revision.  It is
    not a neuron, cortical compartment, raster cell, or giant-ontology class.
    """

    element_id: str
    role: str
    geometry: NavGeometryV1
    activations: tuple[NavActivationV1, ...]
    parent_element_id: Optional[str]
    provenance: NavProvenanceV1

    def __post_init__(self) -> None:
        _require_instance(self.geometry, NavGeometryV1, field_name="geometry")
        _require_instance(self.provenance, NavProvenanceV1, field_name="provenance")
        element_id = _normalize_identifier(self.element_id, field_name="element_id")
        role = _normalize_identifier(self.role, field_name="role")
        parent_element_id = _normalize_optional_identifier(self.parent_element_id, field_name="parent_element_id")
        if parent_element_id == element_id:
            raise ValueError("an element cannot be its own parent")

        activations = tuple(self.activations)
        for activation in activations:
            _require_instance(activation, NavActivationV1, field_name="activation")
        activations = tuple(sorted(activations, key=lambda item: item.name))
        names = [activation.name for activation in activations]
        if len(names) != len(set(names)):
            raise ValueError(f"element {element_id!r} has duplicate activation names")

        object.__setattr__(self, "element_id", element_id)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "parent_element_id", parent_element_id)
        object.__setattr__(self, "activations", activations)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe element record."""
        return {
            "element_id": self.element_id,
            "role": self.role,
            "geometry": self.geometry.as_dict(),
            "activations": [activation.as_dict() for activation in self.activations],
            "parent_element_id": self.parent_element_id,
            "provenance": self.provenance.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavElementV1":
        """Decode one exact element record from a mapping."""
        expected = {"element_id", "role", "geometry", "activations", "parent_element_id", "provenance"}
        _require_exact_keys(data, expected=expected, record_name=cls.__name__)
        raw_activations = data["activations"]
        if not isinstance(raw_activations, list):
            raise ValueError("NavElementV1 activations must be a JSON list")
        geometry_data = _as_mapping(data["geometry"], record_name="NavGeometryV1")
        provenance_data = _as_mapping(data["provenance"], record_name="NavProvenanceV1")
        parent_value = data["parent_element_id"]
        if parent_value is not None and not isinstance(parent_value, str):
            raise ValueError("parent_element_id must be a string or null")
        return cls(
            element_id=str(data["element_id"]),
            role=str(data["role"]),
            geometry=NavGeometryV1.from_dict(geometry_data),
            activations=tuple(
                NavActivationV1.from_dict(_as_mapping(row, record_name="NavActivationV1")) for row in raw_activations
            ),
            parent_element_id=parent_value,
            provenance=NavProvenanceV1.from_dict(provenance_data),
        )


@dataclass(frozen=True, slots=True)
class NavRelationV1:
    """Explicit topological or learned relation not safely derived from geometry."""

    relation_type: str
    source_element_id: str
    target_element_id: str
    provenance: NavProvenanceV1

    def __post_init__(self) -> None:
        _require_instance(self.provenance, NavProvenanceV1, field_name="provenance")
        object.__setattr__(self, "relation_type", _normalize_identifier(self.relation_type, field_name="relation_type"))
        object.__setattr__(
            self,
            "source_element_id",
            _normalize_identifier(self.source_element_id, field_name="source_element_id"),
        )
        object.__setattr__(
            self,
            "target_element_id",
            _normalize_identifier(self.target_element_id, field_name="target_element_id"),
        )

    def structural_key(self) -> tuple[str, str, str]:
        """Return the relation identity used for duplicate detection and ordering."""
        return (self.relation_type, self.source_element_id, self.target_element_id)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe relation record."""
        return {
            "relation_type": self.relation_type,
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "provenance": self.provenance.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavRelationV1":
        """Decode one exact relation record from a mapping."""
        expected = {"relation_type", "source_element_id", "target_element_id", "provenance"}
        _require_exact_keys(data, expected=expected, record_name=cls.__name__)
        provenance_data = _as_mapping(data["provenance"], record_name="NavProvenanceV1")
        return cls(
            relation_type=str(data["relation_type"]),
            source_element_id=str(data["source_element_id"]),
            target_element_id=str(data["target_element_id"]),
            provenance=NavProvenanceV1.from_dict(provenance_data),
        )


@dataclass(frozen=True, slots=True)
class NavMapLinkV1:
    """Address another NavMap revision without retrieving or activating it."""

    link_type: str
    target_ref: NavMapRefV1
    source_element_id: Optional[str]
    provenance: NavProvenanceV1

    def __post_init__(self) -> None:
        _require_instance(self.target_ref, NavMapRefV1, field_name="target_ref")
        _require_instance(self.provenance, NavProvenanceV1, field_name="provenance")
        object.__setattr__(self, "link_type", _normalize_identifier(self.link_type, field_name="link_type"))
        object.__setattr__(
            self,
            "source_element_id",
            _normalize_optional_identifier(self.source_element_id, field_name="source_element_id"),
        )

    def structural_key(self) -> tuple[str, str, int, str]:
        """Return the link identity used for duplicate detection and ordering."""
        return (
            self.link_type,
            self.target_ref.map_id,
            self.target_ref.revision,
            self.source_element_id or "",
        )

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe link record."""
        return {
            "link_type": self.link_type,
            "target_ref": self.target_ref.as_dict(),
            "source_element_id": self.source_element_id,
            "provenance": self.provenance.as_dict(),
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavMapLinkV1":
        """Decode one exact map-link record from a mapping."""
        expected = {"link_type", "target_ref", "source_element_id", "provenance"}
        _require_exact_keys(data, expected=expected, record_name=cls.__name__)
        target_data = _as_mapping(data["target_ref"], record_name="NavMapRefV1")
        provenance_data = _as_mapping(data["provenance"], record_name="NavProvenanceV1")
        source_value = data["source_element_id"]
        if source_value is not None and not isinstance(source_value, str):
            raise ValueError("source_element_id must be a string or null")
        return cls(
            link_type=str(data["link_type"]),
            target_ref=NavMapRefV1.from_dict(target_data),
            source_element_id=source_value,
            provenance=NavProvenanceV1.from_dict(provenance_data),
        )


@dataclass(frozen=True, slots=True)
class NavMapV2:
    """Immutable decoded relational-spatial content of one distributed Column.

    ``NavMapV2`` is intentionally authority-neutral.  The same revision may be
    used later as observed evidence, an expected successor, a retrieved map, a
    prototype, a comparison target, or a WorkingMap-selected WNM.  Acceptance,
    focus, activation, and root status remain separate runtime relationships.
    """

    map_id: str
    revision: int
    role: str
    frame: NavFrameV1
    provenance: NavProvenanceV1
    parent_ref: Optional[NavMapRefV1] = None
    elements: tuple[NavElementV1, ...] = field(default_factory=tuple)
    relations: tuple[NavRelationV1, ...] = field(default_factory=tuple)
    links: tuple[NavMapLinkV1, ...] = field(default_factory=tuple)
    schema: str = NAVMAP_SCHEMA_V2

    kind: str = field(default=NAVMAP_KIND_V2, init=False, repr=False, compare=False)
    fmt: str = field(default=NAVMAP_FORMAT_V2, init=False, repr=False, compare=False)
    shape: tuple[int, ...] = field(default=(), init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        _require_instance(self.frame, NavFrameV1, field_name="frame")
        _require_instance(self.provenance, NavProvenanceV1, field_name="provenance")
        map_id = _normalize_identifier(self.map_id, field_name="map_id")
        revision = _positive_revision(self.revision)
        role = _normalize_identifier(self.role, field_name="role")
        if self.schema != NAVMAP_SCHEMA_V2:
            raise ValueError(f"schema must be {NAVMAP_SCHEMA_V2!r}")

        parent_ref = self.parent_ref
        if parent_ref is not None:
            _require_instance(parent_ref, NavMapRefV1, field_name="parent_ref")
            if parent_ref.map_id != map_id:
                raise ValueError("parent_ref map_id must match the child map_id")
            if parent_ref.revision >= revision:
                raise ValueError("parent_ref revision must be lower than the child revision")

        elements = tuple(self.elements)
        for element in elements:
            _require_instance(element, NavElementV1, field_name="element")
        elements = tuple(sorted(elements, key=lambda item: item.element_id))
        element_ids = [element.element_id for element in elements]
        if len(element_ids) != len(set(element_ids)):
            raise ValueError("element ids must be unique within a NavMap")
        element_id_set = set(element_ids)

        for element in elements:
            if element.parent_element_id is not None and element.parent_element_id not in element_id_set:
                raise ValueError(
                    f"parent element {element.parent_element_id!r} for {element.element_id!r} does not exist"
                )
            for point in element.geometry.points:
                if not self.frame.contains(point):
                    raise ValueError(f"element {element.element_id!r} contains geometry outside the declared frame")
        self._validate_parent_cycles(elements)

        relations = tuple(self.relations)
        for relation in relations:
            _require_instance(relation, NavRelationV1, field_name="relation")
        relations = tuple(sorted(relations, key=lambda item: item.structural_key()))
        relation_keys = [relation.structural_key() for relation in relations]
        if len(relation_keys) != len(set(relation_keys)):
            raise ValueError("duplicate relations are not permitted")
        for relation in relations:
            if relation.source_element_id not in element_id_set or relation.target_element_id not in element_id_set:
                raise ValueError("relation endpoints must reference local elements")

        links = tuple(self.links)
        for link in links:
            _require_instance(link, NavMapLinkV1, field_name="link")
        links = tuple(sorted(links, key=lambda item: item.structural_key()))
        link_keys = [link.structural_key() for link in links]
        if len(link_keys) != len(set(link_keys)):
            raise ValueError("duplicate map links are not permitted")
        for link in links:
            if link.source_element_id is not None and link.source_element_id not in element_id_set:
                raise ValueError("map-link source_element_id must reference a local element")

        object.__setattr__(self, "map_id", map_id)
        object.__setattr__(self, "revision", revision)
        object.__setattr__(self, "role", role)
        object.__setattr__(self, "parent_ref", parent_ref)
        object.__setattr__(self, "elements", elements)
        object.__setattr__(self, "relations", relations)
        object.__setattr__(self, "links", links)
        object.__setattr__(self, "schema", NAVMAP_SCHEMA_V2)

    @staticmethod
    def _validate_parent_cycles(elements: tuple[NavElementV1, ...]) -> None:
        """Reject cyclic local part-of chains while allowing multiple roots."""
        parent_by_id = {element.element_id: element.parent_element_id for element in elements}
        for start_id in parent_by_id:
            visited: set[str] = set()
            current_id: Optional[str] = start_id
            while current_id is not None:
                if current_id in visited:
                    raise ValueError(f"element parent hierarchy contains a cycle at {current_id!r}")
                visited.add(current_id)
                current_id = parent_by_id.get(current_id)

    def as_dict(self) -> dict[str, Any]:
        """Return the complete canonical JSON-safe revision record."""
        return {
            "schema": self.schema,
            "map_id": self.map_id,
            "revision": self.revision,
            "parent_ref": self.parent_ref.as_dict() if self.parent_ref is not None else None,
            "role": self.role,
            "frame": self.frame.as_dict(),
            "elements": [element.as_dict() for element in self.elements],
            "relations": [relation.as_dict() for relation in self.relations],
            "links": [link.as_dict() for link in self.links],
            "provenance": self.provenance.as_dict(),
        }

    def content_dict(self) -> dict[str, Any]:
        """Return canonical decoded content without map identity or lineage."""
        return {
            "role": self.role,
            "frame": self.frame.as_dict(),
            "elements": [element.as_dict() for element in self.elements],
            "relations": [relation.as_dict() for relation in self.relations],
            "links": [link.as_dict() for link in self.links],
            "provenance": self.provenance.as_dict(),
        }

    def to_bytes(self) -> bytes:
        """Serialize the exact revision to deterministic canonical UTF-8 JSON."""
        return _canonical_json_bytes(self.as_dict())

    @classmethod
    def from_bytes(cls, data: bytes) -> "NavMapV2":
        """Decode and validate one record produced by :meth:`to_bytes`."""
        if not isinstance(data, bytes):
            raise TypeError("NavMapV2.from_bytes requires bytes")
        try:
            decoded = json.loads(data.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("invalid NavMapV2 UTF-8 JSON payload") from exc
        return cls.from_dict(_as_mapping(decoded, record_name=cls.__name__))

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavMapV2":
        """Decode one exact NavMapV2 record from a JSON-safe mapping."""
        expected = {
            "schema",
            "map_id",
            "revision",
            "parent_ref",
            "role",
            "frame",
            "elements",
            "relations",
            "links",
            "provenance",
        }
        _require_exact_keys(data, expected=expected, record_name=cls.__name__)
        if data["schema"] != NAVMAP_SCHEMA_V2:
            raise ValueError(f"unsupported NavMapV2 schema: {data['schema']!r}")

        raw_parent = data["parent_ref"]
        if raw_parent is not None:
            parent_ref = NavMapRefV1.from_dict(_as_mapping(raw_parent, record_name="NavMapRefV1"))
        else:
            parent_ref = None

        raw_elements = data["elements"]
        raw_relations = data["relations"]
        raw_links = data["links"]
        if not isinstance(raw_elements, list):
            raise ValueError("NavMapV2 elements must be a JSON list")
        if not isinstance(raw_relations, list):
            raise ValueError("NavMapV2 relations must be a JSON list")
        if not isinstance(raw_links, list):
            raise ValueError("NavMapV2 links must be a JSON list")

        frame = NavFrameV1.from_dict(_as_mapping(data["frame"], record_name="NavFrameV1"))
        provenance = NavProvenanceV1.from_dict(_as_mapping(data["provenance"], record_name="NavProvenanceV1"))
        return cls(
            map_id=str(data["map_id"]),
            revision=data["revision"],
            parent_ref=parent_ref,
            role=str(data["role"]),
            frame=frame,
            elements=tuple(NavElementV1.from_dict(_as_mapping(row, record_name="NavElementV1")) for row in raw_elements),
            relations=tuple(
                NavRelationV1.from_dict(_as_mapping(row, record_name="NavRelationV1")) for row in raw_relations
            ),
            links=tuple(NavMapLinkV1.from_dict(_as_mapping(row, record_name="NavMapLinkV1")) for row in raw_links),
            provenance=provenance,
            schema=str(data["schema"]),
        )

    def content_signature(self) -> str:
        """Return SHA-256 for decoded content, excluding identity and lineage."""
        return _sha256_hex(_canonical_json_bytes(self.content_dict()))

    def record_signature(self) -> str:
        """Return SHA-256 for the complete exact map revision record."""
        return _sha256_hex(self.to_bytes())

    def meta(self) -> dict[str, Any]:
        """Return a lightweight JSON-safe descriptor for Column indexing."""
        return {
            "kind": self.kind,
            "fmt": self.fmt,
            "shape": self.shape,
            "schema": self.schema,
            "map_id": self.map_id,
            "revision": self.revision,
            "role": self.role,
            "frame_id": self.frame.frame_id,
            "element_count": len(self.elements),
            "relation_count": len(self.relations),
            "link_count": len(self.links),
        }
