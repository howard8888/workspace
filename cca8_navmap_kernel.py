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

Phase 1A through Phase 1C scope
-------------------------------
Phase 1A provides records, validation, canonical ordering, deterministic JSON
serialization, and content/record signatures.  Phase 1B-A adds the first pure,
revision-linked geometry queries: element lookup, centroid, centroid distance,
bearing, and orientation.  Phase 1B-B1 adds minimum point/segment distance and
explicit-tolerance contact evidence.  Phase 1B-B2 adds a directional
body-axis proximity/contact fraction under an explicit threshold.  Phase 1B-B3
adds structured support evidence and an open-world body-state readout derived
only from geometry.  Phase 1B-C adds explicit stored-relation access, non-
authoritative map-link following, and diagnostic ASCII rendering.  Phase 1C
adds immutable rigid transforms, explicit frame alignment, structural matching,
candidate ranking, structured residuals, and pure revision proposals/application.
The module still does not:

- grant Working Navigation Map authority;
- integrate with ``Ctx``, WorkingMap, PolicyRuntime, BodyMap, or the runner;
- select or execute a policy;
- write WorldGraph or Column memory;
- store posture or any other derived readout as independent map truth;
- grant runtime activation, retrieval, policy, or WorkingMap authority to any transformed or matched map;
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
- Distances, bearings, orientations, contact, lateral contact fraction, support,
  and body-state evidence are pure revision-linked geometry queries.  Compact
  interpretations remain derived readouts rather than stored independent
  world-state shortcuts.
- Source provenance describes how content arose; current-world authority is a
  separate future WorkingMap relationship.
- Canonical bytes exclude runtime timestamps, generated UUIDs, absolute paths,
  counters, and arbitrary mutable metadata.
- ``content_signature()`` identifies decoded content while excluding map
  identity and lineage; ``record_signature()`` identifies the exact revision.
"""

from __future__ import annotations

from dataclasses import dataclass, field, replace
from enum import Enum
import hashlib
import json
import math
from pathlib import PurePosixPath, PureWindowsPath
import re
from typing import Any, Callable, Mapping, Optional, TypeVar

__version__ = "0.7.0"

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
    "NavPointQueryResultV1",
    "NavScalarQueryResultV1",
    "NavContactQueryResultV1",
    "NavLateralContactQueryResultV1",
    "NavBodyStateInterpretationV1",
    "NavBodyStateThresholdsV1",
    "NavSupportEvidenceV1",
    "NavBodyStateEvidenceV1",
    "NavFrameV1",
    "NavActivationV1",
    "NavGeometryKindV1",
    "NavGeometryV1",
    "NavElementV1",
    "NavRelationV1",
    "NavMapLinkV1",
    "NavMapV2",
    "get_element",
    "element_centroid",
    "centroid_distance_between",
    "bearing_between_centroids",
    "geometry_orientation_degrees",
    "minimum_distance_between",
    "geometries_contact",
    "lateral_contact_fraction",
    "support_evidence",
    "body_state_evidence",
    "stored_relation",
    "follow_link",
    "render_ascii",
    "NavAlignmentStatusV1",
    "NavMatchStatusV1",
    "NavMatchRankStatusV1",
    "NavRevisionDecisionV1",
    "NavRigidTransformV1",
    "NavMapTransformResultV1",
    "NavElementPairV1",
    "NavMatchThresholdsV1",
    "NavAlignmentResultV1",
    "NavElementCorrespondenceV1",
    "NavMapMatchResultV1",
    "NavMatchRankingV1",
    "NavElementResidualV1",
    "NavStructuredResidualV1",
    "NavRevisionThresholdsV1",
    "NavRevisionProposalV1",
    "transform_navmap",
    "translate_navmap",
    "rotate_navmap",
    "reframe_navmap",
    "align_navmaps",
    "match_navmaps",
    "match_rank",
    "structured_residual",
    "propose_revision",
    "apply_revision",
    "__version__",
]

_IDENTIFIER_RE = re.compile(r"^[a-z0-9][a-z0-9_.:/-]*$")
_POLYGON_AREA_EPSILON = 1.0e-12
_GEOMETRY_NUMERICAL_EPSILON = 1.0e-12
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


def _non_negative_float(value: float, *, field_name: str) -> float:
    """Return one finite non-negative float for distances and tolerances."""
    normalized = _finite_float(value, field_name=field_name)
    if normalized < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return normalized


def _positive_revision(value: int, *, field_name: str = "revision") -> int:
    """Return a positive integer revision while rejecting booleans."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _positive_integer(value: int, *, field_name: str) -> int:
    """Return one positive integer for bounded kernel work counts."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value <= 0:
        raise ValueError(f"{field_name} must be positive")
    return value


def _require_instance(value: object, expected_type: type[Any], *, field_name: str) -> None:
    """Raise TypeError when a nested record has the wrong runtime type."""
    if not isinstance(value, expected_type):
        raise TypeError(f"{field_name} must be {expected_type.__name__}")


def _normalize_query_element_ids(values: tuple[str, ...]) -> tuple[str, ...]:
    """Return a non-empty canonical tuple of element ids for a query result."""
    if isinstance(values, str):
        raise TypeError("element_ids must be a tuple or other iterable of strings")
    normalized = tuple(_normalize_identifier(value, field_name="query element_id") for value in values)
    if not normalized:
        raise ValueError("element_ids must not be empty")
    return normalized


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


class NavBodyStateInterpretationV1(str, Enum):
    """Open-world body-state interpretations derived from NavMap geometry."""

    STANDING_LIKE = "standing_like"
    FALLEN_LIKE = "fallen_like"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


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
class NavPointQueryResultV1:
    """Revision-linked point produced by one pure NavMap geometry query.

    The result keeps a derived coordinate attached to the exact map revision,
    frame, participating element ids, units, operator, and geometric method that
    produced it.  It is a read-only query product, not a new authoritative map
    fact and not an independent world model.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    point: NavPointV1
    units: str
    method: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.point, NavPointV1, field_name="point")
        element_ids = _normalize_query_element_ids(self.element_ids)
        object.__setattr__(self, "frame_id", _normalize_identifier(self.frame_id, field_name="frame_id"))
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)
        object.__setattr__(self, "units", _normalize_identifier(self.units, field_name="units"))
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe description for tests and traces."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "point": self.point.as_dict(),
            "units": self.units,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NavScalarQueryResultV1:
    """Revision-linked scalar produced by one pure NavMap geometry query.

    ``method`` makes the measurement convention explicit.  Examples in this
    slice include Euclidean centroid distance, counter-clockwise bearing from
    the positive x-axis, and undirected orientation from the positive x-axis.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    value: float
    units: str
    method: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        element_ids = _normalize_query_element_ids(self.element_ids)
        object.__setattr__(self, "frame_id", _normalize_identifier(self.frame_id, field_name="frame_id"))
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)
        object.__setattr__(self, "value", _finite_float(self.value, field_name="query value"))
        object.__setattr__(self, "units", _normalize_identifier(self.units, field_name="units"))
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe description for tests and traces."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "value": self.value,
            "units": self.units,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NavContactQueryResultV1:
    """Revision-linked evidence that two geometries contact within tolerance.

    Contact is defined exactly as ``minimum_distance <= tolerance``.  The
    measured distance and caller-supplied tolerance remain visible so the
    result never becomes an unexplained boolean or an independently updated
    world-state field.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    contact: bool
    minimum_distance: float
    tolerance: float
    units: str
    distance_method: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        element_ids = _normalize_query_element_ids(self.element_ids)
        if not isinstance(self.contact, bool):
            raise TypeError("contact must be a bool")
        minimum_distance = _non_negative_float(self.minimum_distance, field_name="minimum_distance")
        tolerance = _non_negative_float(self.tolerance, field_name="tolerance")
        expected_contact = minimum_distance <= tolerance
        if self.contact is not expected_contact:
            raise ValueError("contact must equal minimum_distance <= tolerance")
        object.__setattr__(self, "frame_id", _normalize_identifier(self.frame_id, field_name="frame_id"))
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)
        object.__setattr__(self, "minimum_distance", minimum_distance)
        object.__setattr__(self, "tolerance", tolerance)
        object.__setattr__(self, "units", _normalize_identifier(self.units, field_name="units"))
        object.__setattr__(
            self,
            "distance_method",
            _normalize_identifier(self.distance_method, field_name="distance_method"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe description for tests and traces."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "contact": self.contact,
            "minimum_distance": self.minimum_distance,
            "tolerance": self.tolerance,
            "units": self.units,
            "distance_method": self.distance_method,
        }


@dataclass(frozen=True, slots=True)
class NavLateralContactQueryResultV1:
    """Revision-linked fraction of one segment lying near another segment.

    The first element is the measured source axis and the second is the
    reference segment.  ``fraction`` is the proportion of source-axis length
    whose Euclidean distance to the reference segment is less than or equal to
    ``threshold``.  The threshold and component lengths remain visible so this
    result cannot become an unexplained posture or contact-state shortcut.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    fraction: float
    near_length: float
    source_length: float
    threshold: float
    units: str
    method: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        element_ids = _normalize_query_element_ids(self.element_ids)
        if len(element_ids) != 2:
            raise ValueError("lateral contact evidence requires exactly two element ids")
        fraction = _unit_interval(self.fraction, field_name="fraction")
        near_length = _non_negative_float(self.near_length, field_name="near_length")
        source_length = _non_negative_float(self.source_length, field_name="source_length")
        if source_length <= 0.0:
            raise ValueError("source_length must be positive")
        if near_length > source_length + _GEOMETRY_NUMERICAL_EPSILON:
            raise ValueError("near_length must not exceed source_length")
        threshold = _non_negative_float(self.threshold, field_name="threshold")
        expected_fraction = min(1.0, max(0.0, near_length / source_length))
        if not math.isclose(fraction, expected_fraction, rel_tol=1.0e-12, abs_tol=1.0e-12):
            raise ValueError("fraction must equal near_length / source_length")
        object.__setattr__(self, "frame_id", _normalize_identifier(self.frame_id, field_name="frame_id"))
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)
        object.__setattr__(self, "fraction", fraction)
        object.__setattr__(self, "near_length", min(source_length, near_length))
        object.__setattr__(self, "source_length", source_length)
        object.__setattr__(self, "threshold", threshold)
        object.__setattr__(self, "units", _normalize_identifier(self.units, field_name="units"))
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe description for tests and traces."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "fraction": self.fraction,
            "near_length": self.near_length,
            "source_length": self.source_length,
            "threshold": self.threshold,
            "units": self.units,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NavBodyStateThresholdsV1:
    """Explicit engineering thresholds for SELF-ground support interpretation.

    These values are inspectable test parameters.  They are not claimed as
    universal biological constants and they are never stored inside ``NavMapV2``.
    Callers must supply one complete threshold record explicitly.
    """

    contact_tolerance: float
    lateral_distance_threshold: float
    upright_angle_tolerance_degrees: float
    parallel_angle_tolerance_degrees: float
    minimum_standing_head_elevation: float
    maximum_fallen_head_elevation: float
    maximum_standing_lateral_fraction: float
    minimum_fallen_lateral_fraction: float

    def __post_init__(self) -> None:
        contact_tolerance = _non_negative_float(self.contact_tolerance, field_name="contact_tolerance")
        lateral_distance_threshold = _non_negative_float(
            self.lateral_distance_threshold,
            field_name="lateral_distance_threshold",
        )
        upright_tolerance = _non_negative_float(
            self.upright_angle_tolerance_degrees,
            field_name="upright_angle_tolerance_degrees",
        )
        parallel_tolerance = _non_negative_float(
            self.parallel_angle_tolerance_degrees,
            field_name="parallel_angle_tolerance_degrees",
        )
        if upright_tolerance > 90.0:
            raise ValueError("upright_angle_tolerance_degrees must not exceed 90 degrees")
        if parallel_tolerance > 90.0:
            raise ValueError("parallel_angle_tolerance_degrees must not exceed 90 degrees")
        object.__setattr__(self, "contact_tolerance", contact_tolerance)
        object.__setattr__(self, "lateral_distance_threshold", lateral_distance_threshold)
        object.__setattr__(self, "upright_angle_tolerance_degrees", upright_tolerance)
        object.__setattr__(self, "parallel_angle_tolerance_degrees", parallel_tolerance)
        object.__setattr__(
            self,
            "minimum_standing_head_elevation",
            _non_negative_float(
                self.minimum_standing_head_elevation,
                field_name="minimum_standing_head_elevation",
            ),
        )
        object.__setattr__(
            self,
            "maximum_fallen_head_elevation",
            _non_negative_float(
                self.maximum_fallen_head_elevation,
                field_name="maximum_fallen_head_elevation",
            ),
        )
        object.__setattr__(
            self,
            "maximum_standing_lateral_fraction",
            _unit_interval(
                self.maximum_standing_lateral_fraction,
                field_name="maximum_standing_lateral_fraction",
            ),
        )
        object.__setattr__(
            self,
            "minimum_fallen_lateral_fraction",
            _unit_interval(
                self.minimum_fallen_lateral_fraction,
                field_name="minimum_fallen_lateral_fraction",
            ),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return all explicit thresholds as a JSON-safe mapping."""
        return {
            "contact_tolerance": self.contact_tolerance,
            "lateral_distance_threshold": self.lateral_distance_threshold,
            "upright_angle_tolerance_degrees": self.upright_angle_tolerance_degrees,
            "parallel_angle_tolerance_degrees": self.parallel_angle_tolerance_degrees,
            "minimum_standing_head_elevation": self.minimum_standing_head_elevation,
            "maximum_fallen_head_elevation": self.maximum_fallen_head_elevation,
            "maximum_standing_lateral_fraction": self.maximum_standing_lateral_fraction,
            "minimum_fallen_lateral_fraction": self.minimum_fallen_lateral_fraction,
        }


@dataclass(frozen=True, slots=True)
class NavSupportEvidenceV1:
    """Structured SELF-ground support evidence derived from lower operators.

    The record exposes every component used by the body-state interpretation:
    body and ground orientation, their acute relative angle, foot contact, head
    distance from ground, and the fraction of the body axis near ground.  The
    boolean component flags are validated against those measurements and the
    caller-supplied threshold record.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    thresholds: NavBodyStateThresholdsV1
    body_orientation: NavScalarQueryResultV1
    ground_orientation: NavScalarQueryResultV1
    body_ground_angle: NavScalarQueryResultV1
    foot_ground_contact: NavContactQueryResultV1
    head_ground_distance: NavScalarQueryResultV1
    lateral_contact: NavLateralContactQueryResultV1
    body_perpendicular_to_ground: bool
    body_parallel_to_ground: bool
    head_elevated: bool
    head_low: bool
    lateral_contact_low: bool
    lateral_contact_high: bool
    upright_support_pattern: bool
    lateral_ground_pattern: bool

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.thresholds, NavBodyStateThresholdsV1, field_name="thresholds")
        _require_instance(self.body_orientation, NavScalarQueryResultV1, field_name="body_orientation")
        _require_instance(self.ground_orientation, NavScalarQueryResultV1, field_name="ground_orientation")
        _require_instance(self.body_ground_angle, NavScalarQueryResultV1, field_name="body_ground_angle")
        _require_instance(self.foot_ground_contact, NavContactQueryResultV1, field_name="foot_ground_contact")
        _require_instance(self.head_ground_distance, NavScalarQueryResultV1, field_name="head_ground_distance")
        _require_instance(self.lateral_contact, NavLateralContactQueryResultV1, field_name="lateral_contact")
        element_ids = _normalize_query_element_ids(self.element_ids)
        if len(element_ids) != 4:
            raise ValueError("support evidence requires body, head, foot, and ground element ids")
        body_id, head_id, foot_id, ground_id = element_ids
        frame_id = _normalize_identifier(self.frame_id, field_name="frame_id")
        nested_records = (
            self.body_orientation,
            self.ground_orientation,
            self.body_ground_angle,
            self.foot_ground_contact,
            self.head_ground_distance,
            self.lateral_contact,
        )
        if any(record.source_map_ref != self.source_map_ref for record in nested_records):
            raise ValueError("support component source map references must match")
        if any(record.frame_id != frame_id for record in nested_records):
            raise ValueError("support component frame ids must match")
        if self.body_orientation.element_ids != (body_id,):
            raise ValueError("body_orientation must reference the body element")
        if self.ground_orientation.element_ids != (ground_id,):
            raise ValueError("ground_orientation must reference the ground element")
        if self.body_ground_angle.element_ids != (body_id, ground_id):
            raise ValueError("body_ground_angle must reference body and ground")
        if self.foot_ground_contact.element_ids != (foot_id, ground_id):
            raise ValueError("foot_ground_contact must reference foot and ground")
        if self.head_ground_distance.element_ids != (head_id, ground_id):
            raise ValueError("head_ground_distance must reference head and ground")
        if self.lateral_contact.element_ids != (body_id, ground_id):
            raise ValueError("lateral_contact must reference body and ground")
        if not math.isclose(
            self.foot_ground_contact.tolerance,
            self.thresholds.contact_tolerance,
            rel_tol=0.0,
            abs_tol=_GEOMETRY_NUMERICAL_EPSILON,
        ):
            raise ValueError("foot contact tolerance must match the threshold record")
        if not math.isclose(
            self.lateral_contact.threshold,
            self.thresholds.lateral_distance_threshold,
            rel_tol=0.0,
            abs_tol=_GEOMETRY_NUMERICAL_EPSILON,
        ):
            raise ValueError("lateral distance threshold must match the threshold record")

        relative_angle = self.body_ground_angle.value
        if not 0.0 <= relative_angle <= 90.0:
            raise ValueError("body_ground_angle must lie between 0 and 90 degrees")
        orientation_difference = abs(self.body_orientation.value - self.ground_orientation.value) % 180.0
        expected_relative_angle = min(orientation_difference, 180.0 - orientation_difference)
        if not math.isclose(
            relative_angle,
            expected_relative_angle,
            rel_tol=0.0,
            abs_tol=_GEOMETRY_NUMERICAL_EPSILON,
        ):
            raise ValueError("body_ground_angle must match the two orientation measurements")
        expected_perpendicular = relative_angle >= 90.0 - self.thresholds.upright_angle_tolerance_degrees
        expected_parallel = relative_angle <= self.thresholds.parallel_angle_tolerance_degrees
        expected_head_elevated = (
            self.head_ground_distance.value >= self.thresholds.minimum_standing_head_elevation
        )
        expected_head_low = self.head_ground_distance.value <= self.thresholds.maximum_fallen_head_elevation
        expected_lateral_low = (
            self.lateral_contact.fraction <= self.thresholds.maximum_standing_lateral_fraction
        )
        expected_lateral_high = (
            self.lateral_contact.fraction >= self.thresholds.minimum_fallen_lateral_fraction
        )
        expected_upright = (
            self.foot_ground_contact.contact
            and expected_perpendicular
            and expected_head_elevated
            and expected_lateral_low
        )
        expected_lateral_ground = expected_parallel and expected_head_low and expected_lateral_high
        expected_flags = {
            "body_perpendicular_to_ground": expected_perpendicular,
            "body_parallel_to_ground": expected_parallel,
            "head_elevated": expected_head_elevated,
            "head_low": expected_head_low,
            "lateral_contact_low": expected_lateral_low,
            "lateral_contact_high": expected_lateral_high,
            "upright_support_pattern": expected_upright,
            "lateral_ground_pattern": expected_lateral_ground,
        }
        for field_name, expected in expected_flags.items():
            actual = getattr(self, field_name)
            if not isinstance(actual, bool):
                raise TypeError(f"{field_name} must be a bool")
            if actual is not expected:
                raise ValueError(f"{field_name} is inconsistent with support measurements and thresholds")

        object.__setattr__(self, "frame_id", frame_id)
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)

    def as_dict(self) -> dict[str, Any]:
        """Return complete JSON-safe component evidence."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "thresholds": self.thresholds.as_dict(),
            "body_orientation": self.body_orientation.as_dict(),
            "ground_orientation": self.ground_orientation.as_dict(),
            "body_ground_angle": self.body_ground_angle.as_dict(),
            "foot_ground_contact": self.foot_ground_contact.as_dict(),
            "head_ground_distance": self.head_ground_distance.as_dict(),
            "lateral_contact": self.lateral_contact.as_dict(),
            "body_perpendicular_to_ground": self.body_perpendicular_to_ground,
            "body_parallel_to_ground": self.body_parallel_to_ground,
            "head_elevated": self.head_elevated,
            "head_low": self.head_low,
            "lateral_contact_low": self.lateral_contact_low,
            "lateral_contact_high": self.lateral_contact_high,
            "upright_support_pattern": self.upright_support_pattern,
            "lateral_ground_pattern": self.lateral_ground_pattern,
        }


@dataclass(frozen=True, slots=True)
class NavBodyStateEvidenceV1:
    """Open-world body-state readout linked to one NavMap revision.

    ``STANDING_LIKE`` and ``FALLEN_LIKE`` are derived interpretations only.
    ``UNKNOWN`` preserves missing or unsupported geometry, while ``AMBIGUOUS``
    preserves complete but conflicting or non-diagnostic evidence.
    """

    source_map_ref: NavMapRefV1
    frame_id: str
    operator: str
    element_ids: tuple[str, ...]
    thresholds: NavBodyStateThresholdsV1
    interpretation: NavBodyStateInterpretationV1
    support: Optional[NavSupportEvidenceV1]
    missing_element_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.thresholds, NavBodyStateThresholdsV1, field_name="thresholds")
        interpretation = _enum_member(
            NavBodyStateInterpretationV1,
            self.interpretation,
            field_name="interpretation",
        )
        element_ids = _normalize_query_element_ids(self.element_ids)
        if len(element_ids) != 4:
            raise ValueError("body-state evidence requires body, head, foot, and ground element ids")
        missing_ids = tuple(sorted(_normalize_query_element_ids(self.missing_element_ids))) if self.missing_element_ids else ()
        reason = _normalize_identifier(self.reason, field_name="reason")
        frame_id = _normalize_identifier(self.frame_id, field_name="frame_id")

        if interpretation is NavBodyStateInterpretationV1.UNKNOWN:
            if self.support is not None:
                raise ValueError("UNKNOWN body-state evidence must not contain complete support evidence")
        else:
            support = self.support
            if support is None:
                raise TypeError("support must be NavSupportEvidenceV1")
            _require_instance(support, NavSupportEvidenceV1, field_name="support")
            if missing_ids:
                raise ValueError("complete body-state evidence must not list missing elements")
            if support.source_map_ref != self.source_map_ref:
                raise ValueError("body-state and support source map references must match")
            if support.frame_id != frame_id:
                raise ValueError("body-state and support frame ids must match")
            if support.element_ids != element_ids:
                raise ValueError("body-state and support element ids must match")
            if support.thresholds != self.thresholds:
                raise ValueError("body-state and support thresholds must match")
            upright = support.upright_support_pattern
            lateral = support.lateral_ground_pattern
            if interpretation is NavBodyStateInterpretationV1.STANDING_LIKE and not (upright and not lateral):
                raise ValueError("STANDING_LIKE requires only the upright support pattern")
            if interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE and not (lateral and not upright):
                raise ValueError("FALLEN_LIKE requires only the lateral ground pattern")
            if interpretation is NavBodyStateInterpretationV1.AMBIGUOUS and upright is not lateral:
                raise ValueError("AMBIGUOUS requires both support patterns or neither support pattern")

        object.__setattr__(self, "frame_id", frame_id)
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)
        object.__setattr__(self, "interpretation", interpretation)
        object.__setattr__(self, "missing_element_ids", missing_ids)
        object.__setattr__(self, "reason", reason)

    def as_dict(self) -> dict[str, Any]:
        """Return the interpretation, thresholds, and complete supporting evidence."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "frame_id": self.frame_id,
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "thresholds": self.thresholds.as_dict(),
            "interpretation": self.interpretation.value,
            "support": self.support.as_dict() if self.support is not None else None,
            "missing_element_ids": list(self.missing_element_ids),
            "reason": self.reason,
        }


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

# --- Phase 1B-A pure geometry queries -----------------------------------------------


def _source_map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the immutable identity of the map revision used by a query."""
    return NavMapRefV1(map_id=navmap.map_id, revision=navmap.revision)


def get_element(navmap: NavMapV2, element_id: str) -> NavElementV1:
    """Return one local element by canonical id or fail explicitly.

    Lookup is intentionally pure and linear for the small Phase 1 kernel.  A
    future backend may add an index without changing this public contract.

    Raises
    ------
    TypeError
        If ``navmap`` is not a :class:`NavMapV2` or ``element_id`` is not a
        string accepted by the identifier contract.
    KeyError
        If the normalized element id is not present in this map revision.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    normalized_id = _normalize_identifier(element_id, field_name="element_id")
    for element in navmap.elements:
        if element.element_id == normalized_id:
            return element
    raise KeyError(f"element {normalized_id!r} does not exist in {navmap.map_id}@r{navmap.revision}")


def _geometry_centroid(geometry: NavGeometryV1) -> tuple[NavPointV1, str]:
    """Return a geometry centroid and the explicit method used to derive it."""
    points = geometry.points
    if geometry.kind is NavGeometryKindV1.POINT:
        return points[0], "point_coordinate"

    if geometry.kind is NavGeometryKindV1.SEGMENT:
        start, end = points
        return NavPointV1(x=(start.x + end.x) / 2.0, y=(start.y + end.y) / 2.0), "segment_midpoint"

    if geometry.kind is NavGeometryKindV1.POLYLINE:
        total_length = 0.0
        weighted_x_terms: list[float] = []
        weighted_y_terms: list[float] = []
        for start, end in zip(points, points[1:]):
            segment_length = math.hypot(end.x - start.x, end.y - start.y)
            if segment_length == 0.0:
                continue
            total_length += segment_length
            weighted_x_terms.append(((start.x + end.x) / 2.0) * segment_length)
            weighted_y_terms.append(((start.y + end.y) / 2.0) * segment_length)
        if total_length == 0.0:
            raise ValueError("polyline centroid is undefined for zero total length")
        return (
            NavPointV1(
                x=math.fsum(weighted_x_terms) / total_length,
                y=math.fsum(weighted_y_terms) / total_length,
            ),
            "length_weighted_segment_midpoints",
        )

    twice_area = _polygon_twice_signed_area(points)
    x_terms: list[float] = []
    y_terms: list[float] = []
    for index, point in enumerate(points):
        next_point = points[(index + 1) % len(points)]
        cross = point.x * next_point.y - next_point.x * point.y
        x_terms.append((point.x + next_point.x) * cross)
        y_terms.append((point.y + next_point.y) * cross)
    denominator = 3.0 * twice_area
    return (
        NavPointV1(
            x=math.fsum(x_terms) / denominator,
            y=math.fsum(y_terms) / denominator,
        ),
        "area_centroid",
    )


def element_centroid(navmap: NavMapV2, element_id: str) -> NavPointQueryResultV1:
    """Return the geometric centroid of one element in the map's declared frame.

    Point geometry returns its coordinate, segment geometry returns its midpoint,
    polyline geometry uses segment-length-weighted midpoints, and polygon
    geometry uses the standard signed-area centroid.  The source map is not
    mutated and the result remains linked to its exact revision and frame.
    """
    element = get_element(navmap, element_id)
    point, method = _geometry_centroid(element.geometry)
    return NavPointQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="element_centroid",
        element_ids=(element.element_id,),
        point=point,
        units=navmap.frame.units,
        method=method,
    )


def centroid_distance_between(
    navmap: NavMapV2,
    source_element_id: str,
    target_element_id: str,
) -> NavScalarQueryResultV1:
    """Return Euclidean distance between two element centroids.

    This operator deliberately does not claim minimum geometric distance.  That
    distinct contact-oriented operation belongs to the next Phase 1B slice.
    """
    source = element_centroid(navmap, source_element_id)
    target = element_centroid(navmap, target_element_id)
    value = math.hypot(target.point.x - source.point.x, target.point.y - source.point.y)
    return NavScalarQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="centroid_distance_between",
        element_ids=(source.element_ids[0], target.element_ids[0]),
        value=value,
        units=navmap.frame.units,
        method="euclidean",
    )


def bearing_between_centroids(
    navmap: NavMapV2,
    source_element_id: str,
    target_element_id: str,
) -> NavScalarQueryResultV1:
    """Return directed bearing from source centroid to target centroid.

    Bearing is measured counter-clockwise from the frame's positive x-axis and
    normalized to ``[0, 360)`` degrees.  Coincident centroids have no defined
    bearing and therefore fail explicitly rather than returning an arbitrary
    value.
    """
    source = element_centroid(navmap, source_element_id)
    target = element_centroid(navmap, target_element_id)
    delta_x = target.point.x - source.point.x
    delta_y = target.point.y - source.point.y
    if delta_x == 0.0 and delta_y == 0.0:
        raise ValueError("bearing is undefined for coincident element centroids")
    value = math.degrees(math.atan2(delta_y, delta_x)) % 360.0
    return NavScalarQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="bearing_between_centroids",
        element_ids=(source.element_ids[0], target.element_ids[0]),
        value=value,
        units="degrees",
        method="counterclockwise_from_positive_x",
    )


def geometry_orientation_degrees(navmap: NavMapV2, element_id: str) -> NavScalarQueryResultV1:
    """Return one undirected segment/polyline axis orientation in degrees.

    Orientation is measured from the frame's positive x-axis and normalized to
    ``[0, 180)`` because reversing an undirected body or ground axis does not
    change its orientation.  A polyline uses its first-to-last endpoint chord;
    the returned ``method`` records this convention.  Points and polygons do not
    have one unambiguous axis in this initial operator and fail explicitly.
    """
    element = get_element(navmap, element_id)
    geometry = element.geometry
    if geometry.kind not in (NavGeometryKindV1.SEGMENT, NavGeometryKindV1.POLYLINE):
        raise ValueError("orientation requires segment or polyline geometry")
    start = geometry.points[0]
    end = geometry.points[-1]
    delta_x = end.x - start.x
    delta_y = end.y - start.y
    if delta_x == 0.0 and delta_y == 0.0:
        raise ValueError("orientation is undefined when geometry endpoints coincide")
    value = math.degrees(math.atan2(delta_y, delta_x)) % 180.0
    method = "undirected_segment_axis_from_positive_x"
    if geometry.kind is NavGeometryKindV1.POLYLINE:
        method = "undirected_endpoint_chord_from_positive_x"
    return NavScalarQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="geometry_orientation_degrees",
        element_ids=(element.element_id,),
        value=value,
        units="degrees",
        method=method,
    )

# --- Phase 1B-B1 minimum distance and contact ---------------------------------------


def _point_distance(first: NavPointV1, second: NavPointV1) -> float:
    """Return Euclidean distance between two points."""
    return math.hypot(second.x - first.x, second.y - first.y)


def _point_segment_distance(point: NavPointV1, start: NavPointV1, end: NavPointV1) -> float:
    """Return minimum Euclidean distance from one point to one finite segment."""
    delta_x = end.x - start.x
    delta_y = end.y - start.y
    length_squared = delta_x * delta_x + delta_y * delta_y
    if length_squared == 0.0:
        raise ValueError("segment distance is undefined for coincident endpoints")
    projection = ((point.x - start.x) * delta_x + (point.y - start.y) * delta_y) / length_squared
    projection = max(0.0, min(1.0, projection))
    closest = NavPointV1(x=start.x + projection * delta_x, y=start.y + projection * delta_y)
    return _point_distance(point, closest)


def _cross_product(first: NavPointV1, second: NavPointV1, third: NavPointV1) -> float:
    """Return the signed 2-D cross product for vectors first->second and first->third."""
    return (second.x - first.x) * (third.y - first.y) - (second.y - first.y) * (third.x - first.x)


def _point_on_segment(point: NavPointV1, start: NavPointV1, end: NavPointV1) -> bool:
    """Return whether a nearly collinear point lies within a finite segment's bounds."""
    epsilon = _GEOMETRY_NUMERICAL_EPSILON
    if abs(_cross_product(start, end, point)) > epsilon:
        return False
    return (
        min(start.x, end.x) - epsilon <= point.x <= max(start.x, end.x) + epsilon
        and min(start.y, end.y) - epsilon <= point.y <= max(start.y, end.y) + epsilon
    )


def _segments_intersect(
    first_start: NavPointV1,
    first_end: NavPointV1,
    second_start: NavPointV1,
    second_end: NavPointV1,
) -> bool:
    """Return whether two finite segments intersect or overlap.

    The tiny internal epsilon only stabilizes the line-intersection calculation;
    it is not the caller-visible contact tolerance.  Near but non-intersecting
    geometries remain separated and are handled by ``geometries_contact``.
    """
    epsilon = _GEOMETRY_NUMERICAL_EPSILON
    cross_1 = _cross_product(first_start, first_end, second_start)
    cross_2 = _cross_product(first_start, first_end, second_end)
    cross_3 = _cross_product(second_start, second_end, first_start)
    cross_4 = _cross_product(second_start, second_end, first_end)

    opposite_first = (cross_1 > epsilon and cross_2 < -epsilon) or (cross_1 < -epsilon and cross_2 > epsilon)
    opposite_second = (cross_3 > epsilon and cross_4 < -epsilon) or (cross_3 < -epsilon and cross_4 > epsilon)
    if opposite_first and opposite_second:
        return True

    return (
        (abs(cross_1) <= epsilon and _point_on_segment(second_start, first_start, first_end))
        or (abs(cross_2) <= epsilon and _point_on_segment(second_end, first_start, first_end))
        or (abs(cross_3) <= epsilon and _point_on_segment(first_start, second_start, second_end))
        or (abs(cross_4) <= epsilon and _point_on_segment(first_end, second_start, second_end))
    )


def _segment_segment_distance(
    first_start: NavPointV1,
    first_end: NavPointV1,
    second_start: NavPointV1,
    second_end: NavPointV1,
) -> float:
    """Return minimum Euclidean distance between two finite segments."""
    if _segments_intersect(first_start, first_end, second_start, second_end):
        return 0.0
    return min(
        _point_segment_distance(first_start, second_start, second_end),
        _point_segment_distance(first_end, second_start, second_end),
        _point_segment_distance(second_start, first_start, first_end),
        _point_segment_distance(second_end, first_start, first_end),
    )


def _minimum_geometry_distance(
    first: NavGeometryV1,
    second: NavGeometryV1,
) -> tuple[float, str]:
    """Return minimum distance and method for supported Phase 1B-B1 geometry pairs."""
    if first.kind is NavGeometryKindV1.POINT and second.kind is NavGeometryKindV1.POINT:
        return _point_distance(first.points[0], second.points[0]), "euclidean_point_point"

    if first.kind is NavGeometryKindV1.POINT and second.kind is NavGeometryKindV1.SEGMENT:
        start, end = second.points
        return _point_segment_distance(first.points[0], start, end), "euclidean_point_segment"

    if first.kind is NavGeometryKindV1.SEGMENT and second.kind is NavGeometryKindV1.POINT:
        start, end = first.points
        return _point_segment_distance(second.points[0], start, end), "euclidean_point_segment"

    if first.kind is NavGeometryKindV1.SEGMENT and second.kind is NavGeometryKindV1.SEGMENT:
        first_start, first_end = first.points
        second_start, second_end = second.points
        return (
            _segment_segment_distance(first_start, first_end, second_start, second_end),
            "euclidean_segment_segment",
        )

    raise ValueError("minimum distance currently supports POINT and SEGMENT geometry only")


def minimum_distance_between(
    navmap: NavMapV2,
    source_element_id: str,
    target_element_id: str,
) -> NavScalarQueryResultV1:
    """Return the minimum Euclidean distance between two element geometries.

    This is a boundary/extent measurement, not a centroid measurement.  The
    initial Phase 1B-B1 contract intentionally supports POINT/POINT,
    POINT/SEGMENT, and SEGMENT/SEGMENT pairs required by the SELF-ground
    demonstrator.  Polyline and polygon support is deferred until a concrete
    task requires the additional computational-geometry surface.
    """
    source = get_element(navmap, source_element_id)
    target = get_element(navmap, target_element_id)
    value, method = _minimum_geometry_distance(source.geometry, target.geometry)
    # Remove only machine-scale residue from projection/intersection arithmetic.
    # The biologically/engineering-relevant contact tolerance remains explicit.
    normalized_value = 0.0 if value <= _GEOMETRY_NUMERICAL_EPSILON else value
    return NavScalarQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="minimum_distance_between",
        element_ids=(source.element_id, target.element_id),
        value=normalized_value,
        units=navmap.frame.units,
        method=method,
    )


def geometries_contact(
    navmap: NavMapV2,
    source_element_id: str,
    target_element_id: str,
    *,
    tolerance: float,
) -> NavContactQueryResultV1:
    """Return structured evidence that two geometries contact within tolerance.

    ``tolerance`` is required and keyword-only so callers cannot accidentally
    depend on exact floating-point equality or an invisible global threshold.
    Contact is true exactly when the measured minimum distance is less than or
    equal to that explicit non-negative tolerance.
    """
    normalized_tolerance = _non_negative_float(tolerance, field_name="tolerance")
    distance = minimum_distance_between(navmap, source_element_id, target_element_id)
    return NavContactQueryResultV1(
        source_map_ref=distance.source_map_ref,
        frame_id=distance.frame_id,
        operator="geometries_contact",
        element_ids=distance.element_ids,
        contact=distance.value <= normalized_tolerance,
        minimum_distance=distance.value,
        tolerance=normalized_tolerance,
        units=distance.units,
        distance_method=distance.method,
    )

def _linear_value_interval(
    start_value: float,
    delta_value: float,
    lower: float,
    upper: float,
) -> Optional[tuple[float, float]]:
    """Return the parameter interval where one linear value lies inside bounds."""
    epsilon = _GEOMETRY_NUMERICAL_EPSILON
    if abs(delta_value) <= epsilon:
        if lower - epsilon <= start_value <= upper + epsilon:
            return (0.0, 1.0)
        return None
    first = (lower - start_value) / delta_value
    second = (upper - start_value) / delta_value
    interval_start = max(0.0, min(first, second))
    interval_end = min(1.0, max(first, second))
    if interval_start > interval_end + epsilon:
        return None
    return (max(0.0, interval_start), min(1.0, interval_end))


def _intersect_parameter_intervals(
    first: Optional[tuple[float, float]],
    second: Optional[tuple[float, float]],
) -> Optional[tuple[float, float]]:
    """Return the overlap of two parameter intervals, if any."""
    if first is None or second is None:
        return None
    start = max(first[0], second[0])
    end = min(first[1], second[1])
    if start > end + _GEOMETRY_NUMERICAL_EPSILON:
        return None
    return (max(0.0, start), min(1.0, end))


def _segment_circle_parameter_interval(
    source_start: NavPointV1,
    source_end: NavPointV1,
    center: NavPointV1,
    radius: float,
) -> Optional[tuple[float, float]]:
    """Return source-segment parameters lying inside or on one circle."""
    delta_x = source_end.x - source_start.x
    delta_y = source_end.y - source_start.y
    offset_x = source_start.x - center.x
    offset_y = source_start.y - center.y
    coefficient_a = delta_x * delta_x + delta_y * delta_y
    coefficient_b = 2.0 * (offset_x * delta_x + offset_y * delta_y)
    coefficient_c = offset_x * offset_x + offset_y * offset_y - radius * radius
    discriminant = coefficient_b * coefficient_b - 4.0 * coefficient_a * coefficient_c
    epsilon = _GEOMETRY_NUMERICAL_EPSILON
    if discriminant < -epsilon:
        return None
    discriminant = max(0.0, discriminant)
    root = math.sqrt(discriminant)
    first = (-coefficient_b - root) / (2.0 * coefficient_a)
    second = (-coefficient_b + root) / (2.0 * coefficient_a)
    start = max(0.0, min(first, second))
    end = min(1.0, max(first, second))
    if start > end + epsilon:
        return None
    return (max(0.0, start), min(1.0, end))


def _segment_rectangle_parameter_interval(
    source_start: NavPointV1,
    source_end: NavPointV1,
    target_start: NavPointV1,
    target_end: NavPointV1,
    threshold: float,
) -> Optional[tuple[float, float]]:
    """Return source parameters inside the rectangular body of a target capsule."""
    target_dx = target_end.x - target_start.x
    target_dy = target_end.y - target_start.y
    target_length = math.hypot(target_dx, target_dy)
    unit_x = target_dx / target_length
    unit_y = target_dy / target_length
    perpendicular_x = -unit_y
    perpendicular_y = unit_x

    source_relative_x = source_start.x - target_start.x
    source_relative_y = source_start.y - target_start.y
    source_delta_x = source_end.x - source_start.x
    source_delta_y = source_end.y - source_start.y

    along_start = source_relative_x * unit_x + source_relative_y * unit_y
    along_delta = source_delta_x * unit_x + source_delta_y * unit_y
    perpendicular_start = source_relative_x * perpendicular_x + source_relative_y * perpendicular_y
    perpendicular_delta = source_delta_x * perpendicular_x + source_delta_y * perpendicular_y

    along_interval = _linear_value_interval(along_start, along_delta, 0.0, target_length)
    perpendicular_interval = _linear_value_interval(
        perpendicular_start,
        perpendicular_delta,
        -threshold,
        threshold,
    )
    return _intersect_parameter_intervals(along_interval, perpendicular_interval)


def _merge_parameter_intervals(intervals: list[tuple[float, float]]) -> list[tuple[float, float]]:
    """Return sorted merged intervals in the source-segment parameter domain."""
    if not intervals:
        return []
    epsilon = _GEOMETRY_NUMERICAL_EPSILON
    ordered = sorted(intervals)
    merged: list[tuple[float, float]] = [ordered[0]]
    for start, end in ordered[1:]:
        previous_start, previous_end = merged[-1]
        if start <= previous_end + epsilon:
            merged[-1] = (previous_start, max(previous_end, end))
        else:
            merged.append((start, end))
    return merged


def _segment_capsule_fraction(
    source_start: NavPointV1,
    source_end: NavPointV1,
    target_start: NavPointV1,
    target_end: NavPointV1,
    threshold: float,
) -> tuple[float, float, float]:
    """Return fraction, near length, and source length within threshold of a target segment.

    The region within ``threshold`` of a finite target segment is a capsule: a
    rectangle around the segment plus one circular cap at each endpoint.  The
    source segment is clipped against those three convex pieces, their parameter
    intervals are merged, and the resulting fraction is independent of raster
    resolution or arbitrary sampling density.
    """
    source_length = _point_distance(source_start, source_end)
    intervals: list[tuple[float, float]] = []
    rectangle = _segment_rectangle_parameter_interval(
        source_start, source_end, target_start, target_end, threshold
    )
    if rectangle is not None:
        intervals.append(rectangle)
    for center in (target_start, target_end):
        circle = _segment_circle_parameter_interval(source_start, source_end, center, threshold)
        if circle is not None:
            intervals.append(circle)

    merged = _merge_parameter_intervals(intervals)
    parameter_fraction = sum(max(0.0, end - start) for start, end in merged)
    fraction = min(1.0, max(0.0, parameter_fraction))
    near_length = min(source_length, source_length * fraction)
    return fraction, near_length, source_length


def lateral_contact_fraction(
    navmap: NavMapV2,
    source_element_id: str,
    target_element_id: str,
    *,
    threshold: float,
) -> NavLateralContactQueryResultV1:
    """Return the fraction of one segment lying within threshold of another.

    The operator is directional: the first element is the measured source axis
    and the second is the reference segment.  In the SELF-ground demonstrator,
    this means the fraction of ``self_body`` lying within a declared distance
    band of ``ground_surface``.  It therefore distinguishes a body whose single
    closest point is near ground from a body whose broad lateral extent is near
    ground.

    Both geometries must be ``SEGMENT`` in this bounded Phase 1B-B2 contract.
    ``threshold`` is required and keyword-only.  It is an engineering/sensor
    tolerance, not a hidden biological constant and not an authoritative
    posture label.
    """
    normalized_threshold = _non_negative_float(threshold, field_name="threshold")
    source = get_element(navmap, source_element_id)
    target = get_element(navmap, target_element_id)
    if source.geometry.kind is not NavGeometryKindV1.SEGMENT or target.geometry.kind is not NavGeometryKindV1.SEGMENT:
        raise ValueError("lateral contact fraction currently requires SEGMENT geometry for both elements")
    source_start, source_end = source.geometry.points
    target_start, target_end = target.geometry.points
    fraction, near_length, source_length = _segment_capsule_fraction(
        source_start,
        source_end,
        target_start,
        target_end,
        normalized_threshold,
    )
    return NavLateralContactQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="lateral_contact_fraction",
        element_ids=(source.element_id, target.element_id),
        fraction=fraction,
        near_length=near_length,
        source_length=source_length,
        threshold=normalized_threshold,
        units=navmap.frame.units,
        method="segment_capsule_length_fraction",
    )


# --- Phase 1B-B3 support and open-world body-state evidence -------------------------


def _acute_axis_angle_difference(first_degrees: float, second_degrees: float) -> float:
    """Return the acute difference between two undirected axes in degrees."""
    difference = abs(first_degrees - second_degrees) % 180.0
    return min(difference, 180.0 - difference)


def support_evidence(
    navmap: NavMapV2,
    *,
    body_element_id: str,
    head_element_id: str,
    foot_element_id: str,
    ground_element_id: str,
    thresholds: NavBodyStateThresholdsV1,
) -> NavSupportEvidenceV1:
    """Return structured SELF-ground support evidence from pure geometry queries.

    Support is not equated with touch.  The operator combines foot-ground
    contact, body orientation relative to ground, head distance from ground, and
    the fraction of the body axis near ground.  Every threshold is supplied in
    one explicit immutable record and remains visible in the result.

    Missing elements raise ``KeyError`` and unsupported geometry raises
    ``ValueError``.  :func:`body_state_evidence` converts those open-world cases
    into ``UNKNOWN`` rather than forcing a poor interpretation.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    _require_instance(thresholds, NavBodyStateThresholdsV1, field_name="thresholds")
    body = get_element(navmap, body_element_id)
    head = get_element(navmap, head_element_id)
    foot = get_element(navmap, foot_element_id)
    ground = get_element(navmap, ground_element_id)

    body_orientation = geometry_orientation_degrees(navmap, body.element_id)
    ground_orientation = geometry_orientation_degrees(navmap, ground.element_id)
    relative_angle_value = _acute_axis_angle_difference(body_orientation.value, ground_orientation.value)
    body_ground_angle = NavScalarQueryResultV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="body_ground_angle_degrees",
        element_ids=(body.element_id, ground.element_id),
        value=relative_angle_value,
        units="degrees",
        method="acute_undirected_axis_difference",
    )
    foot_contact = geometries_contact(
        navmap,
        foot.element_id,
        ground.element_id,
        tolerance=thresholds.contact_tolerance,
    )
    head_distance = minimum_distance_between(navmap, head.element_id, ground.element_id)
    lateral_contact = lateral_contact_fraction(
        navmap,
        body.element_id,
        ground.element_id,
        threshold=thresholds.lateral_distance_threshold,
    )

    perpendicular = relative_angle_value >= 90.0 - thresholds.upright_angle_tolerance_degrees
    parallel = relative_angle_value <= thresholds.parallel_angle_tolerance_degrees
    head_elevated = head_distance.value >= thresholds.minimum_standing_head_elevation
    head_low = head_distance.value <= thresholds.maximum_fallen_head_elevation
    lateral_low = lateral_contact.fraction <= thresholds.maximum_standing_lateral_fraction
    lateral_high = lateral_contact.fraction >= thresholds.minimum_fallen_lateral_fraction
    upright_pattern = foot_contact.contact and perpendicular and head_elevated and lateral_low
    lateral_ground_pattern = parallel and head_low and lateral_high

    return NavSupportEvidenceV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="support_evidence",
        element_ids=(body.element_id, head.element_id, foot.element_id, ground.element_id),
        thresholds=thresholds,
        body_orientation=body_orientation,
        ground_orientation=ground_orientation,
        body_ground_angle=body_ground_angle,
        foot_ground_contact=foot_contact,
        head_ground_distance=head_distance,
        lateral_contact=lateral_contact,
        body_perpendicular_to_ground=perpendicular,
        body_parallel_to_ground=parallel,
        head_elevated=head_elevated,
        head_low=head_low,
        lateral_contact_low=lateral_low,
        lateral_contact_high=lateral_high,
        upright_support_pattern=upright_pattern,
        lateral_ground_pattern=lateral_ground_pattern,
    )


def body_state_evidence(
    navmap: NavMapV2,
    *,
    body_element_id: str,
    head_element_id: str,
    foot_element_id: str,
    ground_element_id: str,
    thresholds: NavBodyStateThresholdsV1,
) -> NavBodyStateEvidenceV1:
    """Derive an open-world body-state interpretation from SELF-ground geometry.

    ``STANDING_LIKE`` requires a coherent upright support pattern.
    ``FALLEN_LIKE`` requires a coherent lateral-ground pattern.  Complete but
    mixed evidence returns ``AMBIGUOUS``.  Missing elements or unsupported
    geometry return ``UNKNOWN``.  No result is written back into ``NavMapV2``.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    _require_instance(thresholds, NavBodyStateThresholdsV1, field_name="thresholds")
    element_ids = (
        _normalize_identifier(body_element_id, field_name="body_element_id"),
        _normalize_identifier(head_element_id, field_name="head_element_id"),
        _normalize_identifier(foot_element_id, field_name="foot_element_id"),
        _normalize_identifier(ground_element_id, field_name="ground_element_id"),
    )
    available_ids = {element.element_id for element in navmap.elements}
    missing_ids = tuple(element_id for element_id in element_ids if element_id not in available_ids)
    if missing_ids:
        return NavBodyStateEvidenceV1(
            source_map_ref=_source_map_ref(navmap),
            frame_id=navmap.frame.frame_id,
            operator="body_state_evidence",
            element_ids=element_ids,
            thresholds=thresholds,
            interpretation=NavBodyStateInterpretationV1.UNKNOWN,
            support=None,
            missing_element_ids=missing_ids,
            reason="missing_required_elements",
        )

    body = get_element(navmap, element_ids[0])
    head = get_element(navmap, element_ids[1])
    foot = get_element(navmap, element_ids[2])
    ground = get_element(navmap, element_ids[3])
    expected_kinds = (
        (body.geometry.kind, NavGeometryKindV1.SEGMENT),
        (head.geometry.kind, NavGeometryKindV1.POINT),
        (foot.geometry.kind, NavGeometryKindV1.POINT),
        (ground.geometry.kind, NavGeometryKindV1.SEGMENT),
    )
    if any(actual is not expected for actual, expected in expected_kinds):
        return NavBodyStateEvidenceV1(
            source_map_ref=_source_map_ref(navmap),
            frame_id=navmap.frame.frame_id,
            operator="body_state_evidence",
            element_ids=element_ids,
            thresholds=thresholds,
            interpretation=NavBodyStateInterpretationV1.UNKNOWN,
            support=None,
            missing_element_ids=(),
            reason="unsupported_geometry",
        )

    support = support_evidence(
        navmap,
        body_element_id=element_ids[0],
        head_element_id=element_ids[1],
        foot_element_id=element_ids[2],
        ground_element_id=element_ids[3],
        thresholds=thresholds,
    )
    upright = support.upright_support_pattern
    lateral = support.lateral_ground_pattern
    if upright and not lateral:
        interpretation = NavBodyStateInterpretationV1.STANDING_LIKE
        reason = "upright_support_pattern"
    elif lateral and not upright:
        interpretation = NavBodyStateInterpretationV1.FALLEN_LIKE
        reason = "lateral_ground_pattern"
    elif upright and lateral:
        interpretation = NavBodyStateInterpretationV1.AMBIGUOUS
        reason = "conflicting_support_patterns"
    else:
        interpretation = NavBodyStateInterpretationV1.AMBIGUOUS
        reason = "mixed_or_non_diagnostic_evidence"

    return NavBodyStateEvidenceV1(
        source_map_ref=_source_map_ref(navmap),
        frame_id=navmap.frame.frame_id,
        operator="body_state_evidence",
        element_ids=element_ids,
        thresholds=thresholds,
        interpretation=interpretation,
        support=support,
        missing_element_ids=(),
        reason=reason,
    )

# --- Phase 1B-C stored relations, links, and diagnostic renderer -------------------


def stored_relation(
    navmap: NavMapV2,
    relation_type: str,
    source_element_id: str,
    target_element_id: str,
) -> NavRelationV1:
    """Return one exact explicit relation stored in a NavMap revision.

    This operator is intentionally distinct from geometry-derived relations.
    It performs no spatial inference: callers must name the relation type and
    its directed local endpoints, and the operator returns only a matching
    ``NavRelationV1`` already present in ``navmap.relations``.  Absence is an
    explicit ``KeyError`` rather than an inferred negative fact.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    normalized_type = _normalize_identifier(relation_type, field_name="relation_type")
    normalized_source = _normalize_identifier(source_element_id, field_name="source_element_id")
    normalized_target = _normalize_identifier(target_element_id, field_name="target_element_id")
    for relation in navmap.relations:
        if relation.structural_key() == (normalized_type, normalized_source, normalized_target):
            return relation
    raise KeyError(
        f"stored relation {(normalized_type, normalized_source, normalized_target)!r} "
        f"does not exist in {navmap.map_id}@r{navmap.revision}"
    )


def follow_link(
    navmap: NavMapV2,
    *,
    link_type: str,
    source_element_id: Optional[str] = None,
) -> NavMapRefV1:
    """Return one addressable target reference without retrieving or activating it.

    The selector is the normalized link type plus an optional local source
    element.  Exactly one stored link must match.  Returning a ``NavMapRefV1``
    does not reinstate the target map, focus it, accept it, or switch the WNM.

    Raises
    ------
    KeyError
        If no stored link matches the selector.
    ValueError
        If more than one target matches and the selector is therefore
        insufficiently specific.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    normalized_type = _normalize_identifier(link_type, field_name="link_type")
    normalized_source = _normalize_optional_identifier(source_element_id, field_name="source_element_id")
    if normalized_source is not None:
        get_element(navmap, normalized_source)
    matches = tuple(
        link
        for link in navmap.links
        if link.link_type == normalized_type and link.source_element_id == normalized_source
    )
    if not matches:
        raise KeyError(
            f"link type {normalized_type!r} from source {normalized_source!r} "
            f"does not exist in {navmap.map_id}@r{navmap.revision}"
        )
    if len(matches) > 1:
        raise ValueError(
            f"link selector type={normalized_type!r}, source={normalized_source!r} "
            f"is ambiguous in {navmap.map_id}@r{navmap.revision}"
        )
    return matches[0].target_ref


def _renderer_dimension(value: int, *, field_name: str) -> int:
    """Return one usable diagnostic raster dimension."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{field_name} must be an integer")
    if value < 2:
        raise ValueError(f"{field_name} must be at least 2")
    return value


def _point_to_raster(
    frame: NavFrameV1,
    point: NavPointV1,
    *,
    width: int,
    height: int,
) -> tuple[int, int]:
    """Map one continuous point to a deterministic diagnostic raster cell."""
    x_fraction = (point.x - frame.min_x) / (frame.max_x - frame.min_x)
    y_fraction = (point.y - frame.min_y) / (frame.max_y - frame.min_y)
    column = int(math.floor(x_fraction * (width - 1) + 0.5))
    row_from_bottom = int(math.floor(y_fraction * (height - 1) + 0.5))
    column = max(0, min(width - 1, column))
    row_from_bottom = max(0, min(height - 1, row_from_bottom))
    return height - 1 - row_from_bottom, column


def _raster_line_cells(start: tuple[int, int], end: tuple[int, int]) -> tuple[tuple[int, int], ...]:
    """Return Bresenham cells joining two diagnostic raster coordinates."""
    start_row, start_column = start
    end_row, end_column = end
    delta_column = abs(end_column - start_column)
    step_column = 1 if start_column < end_column else -1
    delta_row = -abs(end_row - start_row)
    step_row = 1 if start_row < end_row else -1
    error = delta_column + delta_row
    row = start_row
    column = start_column
    cells: list[tuple[int, int]] = []
    while True:
        cells.append((row, column))
        if row == end_row and column == end_column:
            return tuple(cells)
        doubled_error = 2 * error
        if doubled_error >= delta_row:
            error += delta_row
            column += step_column
        if doubled_error <= delta_column:
            error += delta_column
            row += step_row


def _geometry_raster_cells(
    frame: NavFrameV1,
    geometry: NavGeometryV1,
    *,
    width: int,
    height: int,
) -> tuple[tuple[int, int], ...]:
    """Return deterministic raster cells touched by one geometry boundary."""
    raster_points = tuple(
        _point_to_raster(frame, point, width=width, height=height)
        for point in geometry.points
    )
    if geometry.kind is NavGeometryKindV1.POINT:
        return raster_points

    cells: set[tuple[int, int]] = set()
    for start, end in zip(raster_points, raster_points[1:]):
        cells.update(_raster_line_cells(start, end))
    if geometry.kind is NavGeometryKindV1.POLYGON:
        cells.update(_raster_line_cells(raster_points[-1], raster_points[0]))
    return tuple(sorted(cells))


def _renderer_symbol_and_priority(element: NavElementV1) -> tuple[str, int]:
    """Return a deterministic diagnostic symbol and overlap priority."""
    known = {
        "ground_surface": ("G", 10),
        "self_body": ("B", 30),
        "self_head": ("H", 40),
        "self_foot": ("F", 40),
    }
    if element.role in known:
        return known[element.role]
    geometry_priority = {
        NavGeometryKindV1.POINT: 30,
        NavGeometryKindV1.SEGMENT: 20,
        NavGeometryKindV1.POLYLINE: 20,
        NavGeometryKindV1.POLYGON: 10,
    }
    return element.role[0].upper(), geometry_priority[element.geometry.kind]


def render_ascii(navmap: NavMapV2, *, width: int = 6, height: int = 6) -> str:
    """Render continuous NavMap geometry as a diagnostic ASCII projection.

    Rendering is downstream of the canonical map.  The function rasterizes
    geometry only for human inspection and never alters coordinates, elements,
    relations, links, signatures, or query results.  Higher-priority point/body
    symbols overwrite lower-priority surface symbols when several geometries
    land in the same display cell.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    normalized_width = _renderer_dimension(width, field_name="width")
    normalized_height = _renderer_dimension(height, field_name="height")
    grid = [["." for _ in range(normalized_width)] for _ in range(normalized_height)]

    render_items: list[tuple[int, str, str, tuple[tuple[int, int], ...]]] = []
    for element in navmap.elements:
        symbol, priority = _renderer_symbol_and_priority(element)
        cells = _geometry_raster_cells(
            navmap.frame,
            element.geometry,
            width=normalized_width,
            height=normalized_height,
        )
        render_items.append((priority, element.element_id, symbol, cells))

    for _priority, _element_id, symbol, cells in sorted(render_items):
        for row, column in cells:
            grid[row][column] = symbol
    return "\n".join("".join(row) for row in grid)

# --- Phase 1C immutable transforms, alignment, matching, residuals, and revision ---


class NavAlignmentStatusV1(str, Enum):
    """Outcome of an explicit frame-compatible map-alignment attempt."""

    ALIGNED = "aligned"
    UNKNOWN = "unknown"


class NavMatchStatusV1(str, Enum):
    """Pairwise structural-match status without granting acceptance authority."""

    EXACT = "exact"
    PARTIAL = "partial"
    UNKNOWN = "unknown"


class NavMatchRankStatusV1(str, Enum):
    """Open-world outcome of ranking a bounded set of candidate NavMaps."""

    RANKED = "ranked"
    AMBIGUOUS = "ambiguous"
    UNKNOWN = "unknown"


class NavRevisionDecisionV1(str, Enum):
    """Pure proposal outcomes for evidence relative to one stored map family."""

    KEEP = "keep"
    REVISE = "revise"
    CREATE = "create"
    UNKNOWN = "unknown"
    REJECT_ALL = "reject_all"


def _normalized_rotation_degrees(value: float) -> float:
    """Return a finite rotation normalized to the half-open interval [-180, 180)."""
    normalized = _finite_float(value, field_name="rotation_degrees")
    normalized = (normalized + 180.0) % 360.0 - 180.0
    if normalized == 0.0:
        return 0.0
    return normalized


def _optional_non_negative_float(value: Optional[float], *, field_name: str) -> Optional[float]:
    """Normalize one optional finite non-negative measurement."""
    if value is None:
        return None
    return _non_negative_float(value, field_name=field_name)


def _normalize_identifier_tuple(values: tuple[str, ...], *, field_name: str) -> tuple[str, ...]:
    """Return a canonical tuple of unique identifiers while preserving order."""
    if isinstance(values, str):
        raise TypeError(f"{field_name} must be an iterable of strings")
    normalized = tuple(_normalize_identifier(value, field_name=field_name) for value in values)
    if len(normalized) != len(set(normalized)):
        raise ValueError(f"{field_name} must not contain duplicates")
    return normalized


@dataclass(frozen=True, slots=True)
class NavRigidTransformV1:
    """One explicit two-dimensional rigid transform between declared frames.

    Points are first rotated counter-clockwise about ``pivot`` and are then
    translated.  The record is architecture-level geometry, not a motor command
    and not an assertion that biological circuits use this exact formula.
    """

    source_frame_id: str
    target_frame_id: str
    rotation_degrees: float
    translation_x: float
    translation_y: float
    pivot: NavPointV1
    method: str

    def __post_init__(self) -> None:
        _require_instance(self.pivot, NavPointV1, field_name="pivot")
        object.__setattr__(
            self,
            "source_frame_id",
            _normalize_identifier(self.source_frame_id, field_name="source_frame_id"),
        )
        object.__setattr__(
            self,
            "target_frame_id",
            _normalize_identifier(self.target_frame_id, field_name="target_frame_id"),
        )
        object.__setattr__(self, "rotation_degrees", _normalized_rotation_degrees(self.rotation_degrees))
        object.__setattr__(self, "translation_x", _finite_float(self.translation_x, field_name="translation_x"))
        object.__setattr__(self, "translation_y", _finite_float(self.translation_y, field_name="translation_y"))
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))

    def apply_point(self, point: NavPointV1) -> NavPointV1:
        """Return one point transformed into the target frame."""
        _require_instance(point, NavPointV1, field_name="point")
        radians = math.radians(self.rotation_degrees)
        cosine = math.cos(radians)
        sine = math.sin(radians)
        offset_x = point.x - self.pivot.x
        offset_y = point.y - self.pivot.y
        return NavPointV1(
            x=self.pivot.x + cosine * offset_x - sine * offset_y + self.translation_x,
            y=self.pivot.y + sine * offset_x + cosine * offset_y + self.translation_y,
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe transform trace."""
        return {
            "source_frame_id": self.source_frame_id,
            "target_frame_id": self.target_frame_id,
            "rotation_degrees": self.rotation_degrees,
            "translation_x": self.translation_x,
            "translation_y": self.translation_y,
            "pivot": self.pivot.as_dict(),
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NavMapTransformResultV1:
    """One immutable child-map result produced by an explicit rigid transform."""

    source_map_ref: NavMapRefV1
    result_map: NavMapV2
    operator: str
    element_ids: tuple[str, ...]
    transform: NavRigidTransformV1

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.result_map, NavMapV2, field_name="result_map")
        _require_instance(self.transform, NavRigidTransformV1, field_name="transform")
        element_ids = _normalize_identifier_tuple(self.element_ids, field_name="transform element_id")
        if not element_ids:
            raise ValueError("transform result requires at least one transformed element")
        if self.result_map.map_id != self.source_map_ref.map_id:
            raise ValueError("transformed child must remain in the source map family")
        if self.result_map.parent_ref != self.source_map_ref:
            raise ValueError("transformed child parent_ref must identify the source revision")
        if self.result_map.revision <= self.source_map_ref.revision:
            raise ValueError("transformed child revision must be newer than its source")
        if self.transform.target_frame_id != self.result_map.frame.frame_id:
            raise ValueError("transform target frame must equal the result map frame")
        result_ids = {element.element_id for element in self.result_map.elements}
        if not set(element_ids).issubset(result_ids):
            raise ValueError("transformed element ids must exist in the result map")
        object.__setattr__(self, "operator", _normalize_identifier(self.operator, field_name="operator"))
        object.__setattr__(self, "element_ids", element_ids)

    def as_dict(self) -> dict[str, Any]:
        """Return a compact JSON-safe transformation trace."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "result_map_ref": NavMapRefV1(self.result_map.map_id, self.result_map.revision).as_dict(),
            "operator": self.operator,
            "element_ids": list(self.element_ids),
            "transform": self.transform.as_dict(),
            "content_signature": self.result_map.content_signature(),
            "record_signature": self.result_map.record_signature(),
        }


@dataclass(frozen=True, slots=True)
class NavElementPairV1:
    """One bounded correspondence hypothesis used for alignment and matching."""

    source_element_id: str
    target_element_id: str
    method: str

    def __post_init__(self) -> None:
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
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))

    def as_dict(self) -> dict[str, str]:
        """Return a JSON-safe correspondence hypothesis."""
        return {
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "method": self.method,
        }


@dataclass(frozen=True, slots=True)
class NavMatchThresholdsV1:
    """Explicit engineering thresholds for alignment, matching, and ranking."""

    maximum_alignment_rms_error: float
    maximum_geometry_rms_error: float
    maximum_geometry_point_error: float
    maximum_activation_strength_delta: float
    minimum_correspondence_coverage: float
    minimum_rank_score: float
    ambiguity_margin: float
    maximum_candidate_count: int

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "maximum_alignment_rms_error",
            _non_negative_float(self.maximum_alignment_rms_error, field_name="maximum_alignment_rms_error"),
        )
        object.__setattr__(
            self,
            "maximum_geometry_rms_error",
            _non_negative_float(self.maximum_geometry_rms_error, field_name="maximum_geometry_rms_error"),
        )
        object.__setattr__(
            self,
            "maximum_geometry_point_error",
            _non_negative_float(self.maximum_geometry_point_error, field_name="maximum_geometry_point_error"),
        )
        object.__setattr__(
            self,
            "maximum_activation_strength_delta",
            _unit_interval(self.maximum_activation_strength_delta, field_name="maximum_activation_strength_delta"),
        )
        object.__setattr__(
            self,
            "minimum_correspondence_coverage",
            _unit_interval(self.minimum_correspondence_coverage, field_name="minimum_correspondence_coverage"),
        )
        object.__setattr__(
            self,
            "minimum_rank_score",
            _unit_interval(self.minimum_rank_score, field_name="minimum_rank_score"),
        )
        object.__setattr__(
            self,
            "ambiguity_margin",
            _unit_interval(self.ambiguity_margin, field_name="ambiguity_margin"),
        )
        object.__setattr__(
            self,
            "maximum_candidate_count",
            _positive_integer(self.maximum_candidate_count, field_name="maximum_candidate_count"),
        )

    def as_dict(self) -> dict[str, float]:
        """Return all explicit thresholds as a JSON-safe mapping."""
        return {
            "maximum_alignment_rms_error": self.maximum_alignment_rms_error,
            "maximum_geometry_rms_error": self.maximum_geometry_rms_error,
            "maximum_geometry_point_error": self.maximum_geometry_point_error,
            "maximum_activation_strength_delta": self.maximum_activation_strength_delta,
            "minimum_correspondence_coverage": self.minimum_correspondence_coverage,
            "minimum_rank_score": self.minimum_rank_score,
            "ambiguity_margin": self.ambiguity_margin,
            "maximum_candidate_count": self.maximum_candidate_count,
        }


@dataclass(frozen=True, slots=True)
class NavAlignmentResultV1:
    """Explicit best-fit rigid alignment with coverage and uncertainty evidence."""

    source_map_ref: NavMapRefV1
    target_map_ref: NavMapRefV1
    status: NavAlignmentStatusV1
    transform: Optional[NavRigidTransformV1]
    element_pairs: tuple[NavElementPairV1, ...]
    inlier_pairs: tuple[NavElementPairV1, ...]
    rms_error: Optional[float]
    maximum_error: Optional[float]
    overlap_fraction: float
    inlier_fraction: float
    rotation_determined: bool
    uncertainty: float
    reason: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.target_map_ref, NavMapRefV1, field_name="target_map_ref")
        status = _enum_member(NavAlignmentStatusV1, self.status, field_name="alignment status")
        pairs = tuple(self.element_pairs)
        for pair in pairs:
            _require_instance(pair, NavElementPairV1, field_name="element_pair")
        if len({pair.source_element_id for pair in pairs}) != len(pairs):
            raise ValueError("alignment source element ids must be unique")
        if len({pair.target_element_id for pair in pairs}) != len(pairs):
            raise ValueError("alignment target element ids must be unique")
        inlier_pairs = tuple(self.inlier_pairs)
        for pair in inlier_pairs:
            _require_instance(pair, NavElementPairV1, field_name="inlier_pair")
        if not set(inlier_pairs).issubset(set(pairs)):
            raise ValueError("alignment inlier pairs must be a subset of element_pairs")
        if self.transform is not None:
            _require_instance(self.transform, NavRigidTransformV1, field_name="transform")
        rms_error = _optional_non_negative_float(self.rms_error, field_name="rms_error")
        maximum_error = _optional_non_negative_float(self.maximum_error, field_name="maximum_error")
        if (rms_error is None) != (maximum_error is None):
            raise ValueError("rms_error and maximum_error must both be present or both be absent")
        if status is NavAlignmentStatusV1.ALIGNED and self.transform is None:
            raise ValueError("aligned result requires a transform")
        if status is NavAlignmentStatusV1.ALIGNED and rms_error is None:
            raise ValueError("aligned result requires error measurements")
        if not isinstance(self.rotation_determined, bool):
            raise TypeError("rotation_determined must be a bool")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "element_pairs", pairs)
        object.__setattr__(self, "inlier_pairs", inlier_pairs)
        object.__setattr__(self, "rms_error", rms_error)
        object.__setattr__(self, "maximum_error", maximum_error)
        object.__setattr__(self, "overlap_fraction", _unit_interval(self.overlap_fraction, field_name="overlap_fraction"))
        object.__setattr__(self, "inlier_fraction", _unit_interval(self.inlier_fraction, field_name="inlier_fraction"))
        object.__setattr__(self, "uncertainty", _unit_interval(self.uncertainty, field_name="uncertainty"))
        object.__setattr__(self, "reason", _normalize_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe alignment trace."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "target_map_ref": self.target_map_ref.as_dict(),
            "status": self.status.value,
            "transform": self.transform.as_dict() if self.transform is not None else None,
            "element_pairs": [pair.as_dict() for pair in self.element_pairs],
            "inlier_pairs": [pair.as_dict() for pair in self.inlier_pairs],
            "rms_error": self.rms_error,
            "maximum_error": self.maximum_error,
            "overlap_fraction": self.overlap_fraction,
            "inlier_fraction": self.inlier_fraction,
            "rotation_determined": self.rotation_determined,
            "uncertainty": self.uncertainty,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NavElementCorrespondenceV1:
    """One inspected element correspondence after source-to-target alignment."""

    source_element_id: str
    target_element_id: str
    method: str
    role_match: bool
    geometry_kind_match: bool
    geometry_rms_error: Optional[float]
    geometry_maximum_error: Optional[float]
    geometry_within_tolerance: bool
    activation_names_match: bool
    maximum_activation_strength_delta: float
    activations_within_tolerance: bool
    parent_match: bool
    matched: bool

    def __post_init__(self) -> None:
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
        object.__setattr__(self, "method", _normalize_identifier(self.method, field_name="method"))
        bool_fields = (
            "role_match",
            "geometry_kind_match",
            "geometry_within_tolerance",
            "activation_names_match",
            "activations_within_tolerance",
            "parent_match",
            "matched",
        )
        for field_name in bool_fields:
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")
        rms_error = _optional_non_negative_float(self.geometry_rms_error, field_name="geometry_rms_error")
        maximum_error = _optional_non_negative_float(
            self.geometry_maximum_error,
            field_name="geometry_maximum_error",
        )
        if (rms_error is None) != (maximum_error is None):
            raise ValueError("geometry errors must both be present or both be absent")
        maximum_delta = _unit_interval(
            self.maximum_activation_strength_delta,
            field_name="maximum_activation_strength_delta",
        )
        expected_match = (
            self.role_match
            and self.geometry_kind_match
            and self.geometry_within_tolerance
            and self.activation_names_match
            and self.activations_within_tolerance
            and self.parent_match
        )
        if self.matched is not expected_match:
            raise ValueError("matched must equal the conjunction of correspondence component checks")
        object.__setattr__(self, "geometry_rms_error", rms_error)
        object.__setattr__(self, "geometry_maximum_error", maximum_error)
        object.__setattr__(self, "maximum_activation_strength_delta", maximum_delta)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe correspondence trace."""
        return {
            "source_element_id": self.source_element_id,
            "target_element_id": self.target_element_id,
            "method": self.method,
            "role_match": self.role_match,
            "geometry_kind_match": self.geometry_kind_match,
            "geometry_rms_error": self.geometry_rms_error,
            "geometry_maximum_error": self.geometry_maximum_error,
            "geometry_within_tolerance": self.geometry_within_tolerance,
            "activation_names_match": self.activation_names_match,
            "maximum_activation_strength_delta": self.maximum_activation_strength_delta,
            "activations_within_tolerance": self.activations_within_tolerance,
            "parent_match": self.parent_match,
            "matched": self.matched,
        }


@dataclass(frozen=True, slots=True)
class NavMapMatchResultV1:
    """Structured pairwise NavMap match; ranking is not acceptance or belief."""

    source_map_ref: NavMapRefV1
    target_map_ref: NavMapRefV1
    status: NavMatchStatusV1
    alignment: NavAlignmentResultV1
    thresholds: NavMatchThresholdsV1
    correspondences: tuple[NavElementCorrespondenceV1, ...]
    missing_source_element_ids: tuple[str, ...]
    novel_target_element_ids: tuple[str, ...]
    conflicted_element_pairs: tuple[tuple[str, str], ...]
    map_role_match: bool
    coverage: float
    element_score: float
    relation_score: float
    link_score: float
    score: float
    score_semantics: str
    reason: str

    def __post_init__(self) -> None:
        _require_instance(self.source_map_ref, NavMapRefV1, field_name="source_map_ref")
        _require_instance(self.target_map_ref, NavMapRefV1, field_name="target_map_ref")
        _require_instance(self.alignment, NavAlignmentResultV1, field_name="alignment")
        _require_instance(self.thresholds, NavMatchThresholdsV1, field_name="thresholds")
        status = _enum_member(NavMatchStatusV1, self.status, field_name="match status")
        if self.alignment.source_map_ref != self.source_map_ref:
            raise ValueError("match source map must equal alignment source map")
        if self.alignment.target_map_ref != self.target_map_ref:
            raise ValueError("match target map must equal alignment target map")
        correspondences = tuple(self.correspondences)
        for correspondence in correspondences:
            _require_instance(correspondence, NavElementCorrespondenceV1, field_name="correspondence")
        missing = tuple(sorted(_normalize_identifier_tuple(
            self.missing_source_element_ids,
            field_name="missing source element_id",
        )))
        novel = tuple(sorted(_normalize_identifier_tuple(
            self.novel_target_element_ids,
            field_name="novel target element_id",
        )))
        conflicts: list[tuple[str, str]] = []
        for source_id, target_id in self.conflicted_element_pairs:
            conflicts.append(
                (
                    _normalize_identifier(source_id, field_name="conflicted source element_id"),
                    _normalize_identifier(target_id, field_name="conflicted target element_id"),
                )
            )
        if len(conflicts) != len(set(conflicts)):
            raise ValueError("conflicted element pairs must be unique")
        if not isinstance(self.map_role_match, bool):
            raise TypeError("map_role_match must be a bool")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "correspondences", correspondences)
        object.__setattr__(self, "missing_source_element_ids", missing)
        object.__setattr__(self, "novel_target_element_ids", novel)
        object.__setattr__(self, "conflicted_element_pairs", tuple(sorted(conflicts)))
        object.__setattr__(self, "coverage", _unit_interval(self.coverage, field_name="coverage"))
        object.__setattr__(self, "element_score", _unit_interval(self.element_score, field_name="element_score"))
        object.__setattr__(self, "relation_score", _unit_interval(self.relation_score, field_name="relation_score"))
        object.__setattr__(self, "link_score", _unit_interval(self.link_score, field_name="link_score"))
        object.__setattr__(self, "score", _unit_interval(self.score, field_name="score"))
        object.__setattr__(
            self,
            "score_semantics",
            _normalize_identifier(self.score_semantics, field_name="score_semantics"),
        )
        object.__setattr__(self, "reason", _normalize_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe structural match trace."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "target_map_ref": self.target_map_ref.as_dict(),
            "status": self.status.value,
            "alignment": self.alignment.as_dict(),
            "thresholds": self.thresholds.as_dict(),
            "correspondences": [item.as_dict() for item in self.correspondences],
            "missing_source_element_ids": list(self.missing_source_element_ids),
            "novel_target_element_ids": list(self.novel_target_element_ids),
            "conflicted_element_pairs": [list(pair) for pair in self.conflicted_element_pairs],
            "map_role_match": self.map_role_match,
            "coverage": self.coverage,
            "element_score": self.element_score,
            "relation_score": self.relation_score,
            "link_score": self.link_score,
            "score": self.score,
            "score_semantics": self.score_semantics,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NavMatchRankingV1:
    """Bounded candidate ranking with explicit margin and open-world outcome."""

    query_map_ref: NavMapRefV1
    status: NavMatchRankStatusV1
    ranked_matches: tuple[NavMapMatchResultV1, ...]
    best_candidate_ref: Optional[NavMapRefV1]
    winner_ref: Optional[NavMapRefV1]
    margin: Optional[float]
    ambiguity_margin: float
    reason: str

    def __post_init__(self) -> None:
        _require_instance(self.query_map_ref, NavMapRefV1, field_name="query_map_ref")
        status = _enum_member(NavMatchRankStatusV1, self.status, field_name="rank status")
        ranked_matches = tuple(self.ranked_matches)
        for result in ranked_matches:
            _require_instance(result, NavMapMatchResultV1, field_name="ranked match")
            if result.source_map_ref != self.query_map_ref:
                raise ValueError("all ranked matches must use the query map as source")
        if self.best_candidate_ref is not None:
            _require_instance(self.best_candidate_ref, NavMapRefV1, field_name="best_candidate_ref")
        if self.winner_ref is not None:
            _require_instance(self.winner_ref, NavMapRefV1, field_name="winner_ref")
        margin = None if self.margin is None else _unit_interval(self.margin, field_name="margin")
        ambiguity_margin = _unit_interval(self.ambiguity_margin, field_name="ambiguity_margin")
        candidate_refs = {result.target_map_ref for result in ranked_matches}
        if self.best_candidate_ref is not None and self.best_candidate_ref not in candidate_refs:
            raise ValueError("best_candidate_ref must identify a ranked candidate")
        if self.winner_ref is not None and self.winner_ref not in candidate_refs:
            raise ValueError("winner_ref must identify a ranked candidate")
        if status is NavMatchRankStatusV1.RANKED and self.winner_ref is None:
            raise ValueError("ranked outcome requires a winner_ref")
        if status is not NavMatchRankStatusV1.RANKED and self.winner_ref is not None:
            raise ValueError("ambiguous/unknown ranking must not claim a winner_ref")
        if status is NavMatchRankStatusV1.RANKED and self.winner_ref != self.best_candidate_ref:
            raise ValueError("ranked winner_ref must equal best_candidate_ref")
        object.__setattr__(self, "status", status)
        object.__setattr__(self, "ranked_matches", ranked_matches)
        object.__setattr__(self, "margin", margin)
        object.__setattr__(self, "ambiguity_margin", ambiguity_margin)
        object.__setattr__(self, "reason", _normalize_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe candidate-ranking trace."""
        return {
            "query_map_ref": self.query_map_ref.as_dict(),
            "status": self.status.value,
            "ranked_matches": [match.as_dict() for match in self.ranked_matches],
            "best_candidate_ref": self.best_candidate_ref.as_dict() if self.best_candidate_ref else None,
            "winner_ref": self.winner_ref.as_dict() if self.winner_ref else None,
            "margin": self.margin,
            "ambiguity_margin": self.ambiguity_margin,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NavElementResidualV1:
    """Map-local difference record for one expected/evidence correspondence."""

    expected_element_id: str
    evidence_element_id: str
    correspondence_method: str
    role_changed: bool
    parent_changed: bool
    geometry_kind_changed: bool
    geometry_rms_error: Optional[float]
    geometry_maximum_error: Optional[float]
    geometry_outside_tolerance: bool
    missing_activation_names: tuple[str, ...]
    novel_activation_names: tuple[str, ...]
    activation_strength_deltas: tuple[tuple[str, float], ...]
    provenance_changed: bool
    content_difference: bool
    source_difference: bool

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "expected_element_id",
            _normalize_identifier(self.expected_element_id, field_name="expected_element_id"),
        )
        object.__setattr__(
            self,
            "evidence_element_id",
            _normalize_identifier(self.evidence_element_id, field_name="evidence_element_id"),
        )
        object.__setattr__(
            self,
            "correspondence_method",
            _normalize_identifier(self.correspondence_method, field_name="correspondence_method"),
        )
        bool_fields = (
            "role_changed",
            "parent_changed",
            "geometry_kind_changed",
            "geometry_outside_tolerance",
            "provenance_changed",
            "content_difference",
            "source_difference",
        )
        for field_name in bool_fields:
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be a bool")
        object.__setattr__(
            self,
            "geometry_rms_error",
            _optional_non_negative_float(self.geometry_rms_error, field_name="geometry_rms_error"),
        )
        object.__setattr__(
            self,
            "geometry_maximum_error",
            _optional_non_negative_float(self.geometry_maximum_error, field_name="geometry_maximum_error"),
        )
        missing = tuple(sorted(_normalize_identifier_tuple(
            self.missing_activation_names,
            field_name="missing activation name",
        )))
        novel = tuple(sorted(_normalize_identifier_tuple(
            self.novel_activation_names,
            field_name="novel activation name",
        )))
        deltas: list[tuple[str, float]] = []
        for name, delta in self.activation_strength_deltas:
            deltas.append(
                (
                    _normalize_identifier(name, field_name="activation delta name"),
                    _finite_float(delta, field_name="activation strength delta"),
                )
            )
        if len(deltas) != len({name for name, _delta in deltas}):
            raise ValueError("activation strength delta names must be unique")
        object.__setattr__(self, "missing_activation_names", missing)
        object.__setattr__(self, "novel_activation_names", novel)
        object.__setattr__(self, "activation_strength_deltas", tuple(sorted(deltas)))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe element residual."""
        return {
            "expected_element_id": self.expected_element_id,
            "evidence_element_id": self.evidence_element_id,
            "correspondence_method": self.correspondence_method,
            "role_changed": self.role_changed,
            "parent_changed": self.parent_changed,
            "geometry_kind_changed": self.geometry_kind_changed,
            "geometry_rms_error": self.geometry_rms_error,
            "geometry_maximum_error": self.geometry_maximum_error,
            "geometry_outside_tolerance": self.geometry_outside_tolerance,
            "missing_activation_names": list(self.missing_activation_names),
            "novel_activation_names": list(self.novel_activation_names),
            "activation_strength_deltas": [list(row) for row in self.activation_strength_deltas],
            "provenance_changed": self.provenance_changed,
            "content_difference": self.content_difference,
            "source_difference": self.source_difference,
        }


@dataclass(frozen=True, slots=True)
class NavStructuredResidualV1:
    """Expected-versus-evidence residual preserving structure and source differences."""

    expected_map_ref: NavMapRefV1
    evidence_map_ref: NavMapRefV1
    match_result: NavMapMatchResultV1
    element_residuals: tuple[NavElementResidualV1, ...]
    missing_expected_element_ids: tuple[str, ...]
    novel_evidence_element_ids: tuple[str, ...]
    missing_relations: tuple[tuple[str, str, str], ...]
    novel_relations: tuple[tuple[str, str, str], ...]
    changed_relation_provenance: tuple[tuple[str, str, str], ...]
    missing_links: tuple[tuple[str, str, int, str], ...]
    novel_links: tuple[tuple[str, str, int, str], ...]
    changed_link_provenance: tuple[tuple[str, str, int, str], ...]
    map_role_changed: bool
    map_provenance_changed: bool
    has_content_difference: bool
    has_source_difference: bool
    reason: str

    def __post_init__(self) -> None:
        _require_instance(self.expected_map_ref, NavMapRefV1, field_name="expected_map_ref")
        _require_instance(self.evidence_map_ref, NavMapRefV1, field_name="evidence_map_ref")
        _require_instance(self.match_result, NavMapMatchResultV1, field_name="match_result")
        if self.match_result.source_map_ref != self.expected_map_ref:
            raise ValueError("residual expected map must equal match source map")
        if self.match_result.target_map_ref != self.evidence_map_ref:
            raise ValueError("residual evidence map must equal match target map")
        residuals = tuple(self.element_residuals)
        for residual in residuals:
            _require_instance(residual, NavElementResidualV1, field_name="element_residual")
        object.__setattr__(self, "element_residuals", residuals)
        object.__setattr__(
            self,
            "missing_expected_element_ids",
            tuple(sorted(_normalize_identifier_tuple(
                self.missing_expected_element_ids,
                field_name="missing expected element_id",
            ))),
        )
        object.__setattr__(
            self,
            "novel_evidence_element_ids",
            tuple(sorted(_normalize_identifier_tuple(
                self.novel_evidence_element_ids,
                field_name="novel evidence element_id",
            ))),
        )
        if not isinstance(self.map_role_changed, bool):
            raise TypeError("map_role_changed must be a bool")
        if not isinstance(self.map_provenance_changed, bool):
            raise TypeError("map_provenance_changed must be a bool")
        if not isinstance(self.has_content_difference, bool):
            raise TypeError("has_content_difference must be a bool")
        if not isinstance(self.has_source_difference, bool):
            raise TypeError("has_source_difference must be a bool")
        object.__setattr__(self, "missing_relations", tuple(sorted(self.missing_relations)))
        object.__setattr__(self, "novel_relations", tuple(sorted(self.novel_relations)))
        object.__setattr__(
            self,
            "changed_relation_provenance",
            tuple(sorted(self.changed_relation_provenance)),
        )
        object.__setattr__(self, "missing_links", tuple(sorted(self.missing_links)))
        object.__setattr__(self, "novel_links", tuple(sorted(self.novel_links)))
        object.__setattr__(self, "changed_link_provenance", tuple(sorted(self.changed_link_provenance)))
        object.__setattr__(self, "reason", _normalize_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe structured residual trace."""
        return {
            "expected_map_ref": self.expected_map_ref.as_dict(),
            "evidence_map_ref": self.evidence_map_ref.as_dict(),
            "match_result": self.match_result.as_dict(),
            "element_residuals": [residual.as_dict() for residual in self.element_residuals],
            "missing_expected_element_ids": list(self.missing_expected_element_ids),
            "novel_evidence_element_ids": list(self.novel_evidence_element_ids),
            "missing_relations": [list(row) for row in self.missing_relations],
            "novel_relations": [list(row) for row in self.novel_relations],
            "changed_relation_provenance": [list(row) for row in self.changed_relation_provenance],
            "missing_links": [list(row) for row in self.missing_links],
            "novel_links": [list(row) for row in self.novel_links],
            "changed_link_provenance": [list(row) for row in self.changed_link_provenance],
            "map_role_changed": self.map_role_changed,
            "map_provenance_changed": self.map_provenance_changed,
            "has_content_difference": self.has_content_difference,
            "has_source_difference": self.has_source_difference,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NavRevisionThresholdsV1:
    """Explicit thresholds for pure KEEP/REVISE/CREATE/REJECT proposals."""

    minimum_keep_score: float
    minimum_revise_score: float
    minimum_revise_coverage: float
    maximum_reject_all_score: float

    def __post_init__(self) -> None:
        keep = _unit_interval(self.minimum_keep_score, field_name="minimum_keep_score")
        revise = _unit_interval(self.minimum_revise_score, field_name="minimum_revise_score")
        coverage = _unit_interval(self.minimum_revise_coverage, field_name="minimum_revise_coverage")
        reject = _unit_interval(self.maximum_reject_all_score, field_name="maximum_reject_all_score")
        if keep < revise:
            raise ValueError("minimum_keep_score must be greater than or equal to minimum_revise_score")
        if reject > revise:
            raise ValueError("maximum_reject_all_score must not exceed minimum_revise_score")
        object.__setattr__(self, "minimum_keep_score", keep)
        object.__setattr__(self, "minimum_revise_score", revise)
        object.__setattr__(self, "minimum_revise_coverage", coverage)
        object.__setattr__(self, "maximum_reject_all_score", reject)

    def as_dict(self) -> dict[str, float]:
        """Return the proposal thresholds as a JSON-safe mapping."""
        return {
            "minimum_keep_score": self.minimum_keep_score,
            "minimum_revise_score": self.minimum_revise_score,
            "minimum_revise_coverage": self.minimum_revise_coverage,
            "maximum_reject_all_score": self.maximum_reject_all_score,
        }


@dataclass(frozen=True, slots=True)
class NavRevisionProposalV1:
    """Authority-neutral proposal derived from one structured residual."""

    decision: NavRevisionDecisionV1
    base_map_ref: NavMapRefV1
    evidence_map_ref: NavMapRefV1
    residual: NavStructuredResidualV1
    thresholds: NavRevisionThresholdsV1
    changed_element_ids: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        decision = _enum_member(NavRevisionDecisionV1, self.decision, field_name="revision decision")
        _require_instance(self.base_map_ref, NavMapRefV1, field_name="base_map_ref")
        _require_instance(self.evidence_map_ref, NavMapRefV1, field_name="evidence_map_ref")
        _require_instance(self.residual, NavStructuredResidualV1, field_name="residual")
        _require_instance(self.thresholds, NavRevisionThresholdsV1, field_name="thresholds")
        if self.residual.expected_map_ref != self.base_map_ref:
            raise ValueError("proposal base map must equal residual expected map")
        if self.residual.evidence_map_ref != self.evidence_map_ref:
            raise ValueError("proposal evidence map must equal residual evidence map")
        changed = tuple(sorted(_normalize_identifier_tuple(
            self.changed_element_ids,
            field_name="changed element_id",
        )))
        object.__setattr__(self, "decision", decision)
        object.__setattr__(self, "changed_element_ids", changed)
        object.__setattr__(self, "reason", _normalize_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe revision proposal trace."""
        return {
            "decision": self.decision.value,
            "base_map_ref": self.base_map_ref.as_dict(),
            "evidence_map_ref": self.evidence_map_ref.as_dict(),
            "residual": self.residual.as_dict(),
            "thresholds": self.thresholds.as_dict(),
            "changed_element_ids": list(self.changed_element_ids),
            "reason": self.reason,
        }


def _selected_element_ids(navmap: NavMapV2, element_ids: Optional[tuple[str, ...]]) -> tuple[str, ...]:
    """Return a validated deterministic transform selection."""
    if element_ids is None:
        selected = tuple(element.element_id for element in navmap.elements)
    else:
        selected = _normalize_identifier_tuple(tuple(element_ids), field_name="transform element_id")
    if not selected:
        raise ValueError("at least one element must be selected for transformation")
    for element_id in selected:
        get_element(navmap, element_id)
    return tuple(sorted(selected))


def _transform_geometry(geometry: NavGeometryV1, transform: NavRigidTransformV1) -> NavGeometryV1:
    """Return geometry transformed point-by-point without changing its kind."""
    return NavGeometryV1(
        kind=geometry.kind,
        points=tuple(transform.apply_point(point) for point in geometry.points),
    )


def transform_navmap(
    navmap: NavMapV2,
    transform: NavRigidTransformV1,
    *,
    new_revision: int,
    element_ids: Optional[tuple[str, ...]] = None,
    target_frame: Optional[NavFrameV1] = None,
    result_provenance: Optional[NavProvenanceV1] = None,
    operator: str = "transform_navmap",
) -> NavMapTransformResultV1:
    """Create one immutable child revision by rigidly transforming named elements.

    Selection is explicit.  Transforming a parent element does not silently
    transform its children.  Changing frames requires all elements to be
    transformed so that no geometry is left in the old coordinate system.
    """
    _require_instance(navmap, NavMapV2, field_name="navmap")
    _require_instance(transform, NavRigidTransformV1, field_name="transform")
    revision = _positive_revision(new_revision, field_name="new_revision")
    if revision <= navmap.revision:
        raise ValueError("new_revision must be greater than the source revision")
    if transform.source_frame_id != navmap.frame.frame_id:
        raise ValueError("transform source_frame_id must match the source map frame")
    destination_frame = target_frame or navmap.frame
    _require_instance(destination_frame, NavFrameV1, field_name="target_frame")
    if transform.target_frame_id != destination_frame.frame_id:
        raise ValueError("transform target_frame_id must match the destination frame")
    if destination_frame.units != navmap.frame.units:
        raise ValueError("rigid reframing requires identical source and target units")
    if (
        destination_frame.x_axis != navmap.frame.x_axis
        or destination_frame.y_axis != navmap.frame.y_axis
    ):
        raise ValueError("rigid reframing requires identical source and target axis semantics")
    selected = _selected_element_ids(navmap, element_ids)
    all_ids = tuple(element.element_id for element in navmap.elements)
    if destination_frame != navmap.frame and set(selected) != set(all_ids):
        raise ValueError("reframing requires every map element to be transformed")
    selected_set = set(selected)
    provenance = result_provenance or navmap.provenance
    _require_instance(provenance, NavProvenanceV1, field_name="result_provenance")
    transformed_elements = tuple(
        replace(
            element,
            geometry=_transform_geometry(element.geometry, transform),
            provenance=provenance,
        )
        if element.element_id in selected_set
        else element
        for element in navmap.elements
    )
    result_map = NavMapV2(
        map_id=navmap.map_id,
        revision=revision,
        parent_ref=_source_map_ref(navmap),
        role=navmap.role,
        frame=destination_frame,
        elements=transformed_elements,
        relations=navmap.relations,
        links=navmap.links,
        provenance=provenance,
        schema=navmap.schema,
    )
    return NavMapTransformResultV1(
        source_map_ref=_source_map_ref(navmap),
        result_map=result_map,
        operator=operator,
        element_ids=selected,
        transform=transform,
    )


def translate_navmap(
    navmap: NavMapV2,
    *,
    delta_x: float,
    delta_y: float,
    new_revision: int,
    element_ids: Optional[tuple[str, ...]] = None,
    result_provenance: Optional[NavProvenanceV1] = None,
) -> NavMapTransformResultV1:
    """Translate named elements within the existing declared frame."""
    transform = NavRigidTransformV1(
        source_frame_id=navmap.frame.frame_id,
        target_frame_id=navmap.frame.frame_id,
        rotation_degrees=0.0,
        translation_x=delta_x,
        translation_y=delta_y,
        pivot=NavPointV1(0.0, 0.0),
        method="explicit_translation",
    )
    return transform_navmap(
        navmap,
        transform,
        new_revision=new_revision,
        element_ids=element_ids,
        result_provenance=result_provenance,
        operator="translate_navmap",
    )


def rotate_navmap(
    navmap: NavMapV2,
    *,
    angle_degrees: float,
    pivot: NavPointV1,
    new_revision: int,
    element_ids: Optional[tuple[str, ...]] = None,
    result_provenance: Optional[NavProvenanceV1] = None,
) -> NavMapTransformResultV1:
    """Rotate named elements within the existing frame about an explicit pivot."""
    transform = NavRigidTransformV1(
        source_frame_id=navmap.frame.frame_id,
        target_frame_id=navmap.frame.frame_id,
        rotation_degrees=angle_degrees,
        translation_x=0.0,
        translation_y=0.0,
        pivot=pivot,
        method="explicit_rotation",
    )
    return transform_navmap(
        navmap,
        transform,
        new_revision=new_revision,
        element_ids=element_ids,
        result_provenance=result_provenance,
        operator="rotate_navmap",
    )


def reframe_navmap(
    navmap: NavMapV2,
    *,
    target_frame: NavFrameV1,
    transform: NavRigidTransformV1,
    new_revision: int,
    result_provenance: Optional[NavProvenanceV1] = None,
) -> NavMapTransformResultV1:
    """Transform every element into an explicitly declared compatible target frame."""
    return transform_navmap(
        navmap,
        transform,
        new_revision=new_revision,
        element_ids=tuple(element.element_id for element in navmap.elements),
        target_frame=target_frame,
        result_provenance=result_provenance,
        operator="reframe_navmap",
    )


def _parent_role(navmap: NavMapV2, element: NavElementV1) -> Optional[str]:
    """Return the role of an element's local parent, if any."""
    if element.parent_element_id is None:
        return None
    return get_element(navmap, element.parent_element_id).role


def _feature_structure_key(navmap: NavMapV2, element: NavElementV1) -> tuple[str, tuple[str, ...], str]:
    """Return a coarse non-geometric correspondence key for bounded matching."""
    return (
        element.geometry.kind.value,
        tuple(activation.name for activation in element.activations),
        _parent_role(navmap, element) or "",
    )


def _unique_group_pairs(
    source_items: tuple[NavElementV1, ...],
    target_items: tuple[NavElementV1, ...],
    *,
    source_key: Callable[[NavElementV1], Any],
    target_key: Callable[[NavElementV1], Any],
    method: str,
) -> tuple[NavElementPairV1, ...]:
    """Return pairs whose key occurs exactly once on each remaining side."""
    source_groups: dict[Any, list[NavElementV1]] = {}
    target_groups: dict[Any, list[NavElementV1]] = {}
    for item in source_items:
        source_groups.setdefault(source_key(item), []).append(item)
    for item in target_items:
        target_groups.setdefault(target_key(item), []).append(item)
    pairs: list[NavElementPairV1] = []
    for key in sorted(set(source_groups).intersection(target_groups), key=repr):
        source_group = source_groups[key]
        target_group = target_groups[key]
        if len(source_group) == 1 and len(target_group) == 1:
            pairs.append(
                NavElementPairV1(
                    source_element_id=source_group[0].element_id,
                    target_element_id=target_group[0].element_id,
                    method=method,
                )
            )
    return tuple(pairs)


def _element_pairs(source_map: NavMapV2, target_map: NavMapV2) -> tuple[NavElementPairV1, ...]:
    """Build bounded deterministic correspondence hypotheses without graph expansion."""
    source_remaining = {element.element_id: element for element in source_map.elements}
    target_remaining = {element.element_id: element for element in target_map.elements}
    pairs: list[NavElementPairV1] = []

    for element_id in sorted(set(source_remaining).intersection(target_remaining)):
        pairs.append(NavElementPairV1(element_id, element_id, "exact_local_id"))
        del source_remaining[element_id]
        del target_remaining[element_id]

    role_pairs = _unique_group_pairs(
        tuple(source_remaining.values()),
        tuple(target_remaining.values()),
        source_key=lambda item: item.role,
        target_key=lambda item: item.role,
        method="unique_role",
    )
    for pair in role_pairs:
        pairs.append(pair)
        del source_remaining[pair.source_element_id]
        del target_remaining[pair.target_element_id]

    feature_pairs = _unique_group_pairs(
        tuple(source_remaining.values()),
        tuple(target_remaining.values()),
        source_key=lambda item: _feature_structure_key(source_map, item),
        target_key=lambda item: _feature_structure_key(target_map, item),
        method="unique_feature_structure",
    )
    pairs.extend(feature_pairs)
    return tuple(sorted(pairs, key=lambda item: (item.source_element_id, item.target_element_id)))


def _mean_point(points: tuple[NavPointV1, ...]) -> NavPointV1:
    """Return the arithmetic mean of a non-empty point tuple."""
    if not points:
        raise ValueError("mean point requires at least one point")
    return NavPointV1(
        x=math.fsum(point.x for point in points) / len(points),
        y=math.fsum(point.y for point in points) / len(points),
    )


def _alignment_unknown(
    source_map: NavMapV2,
    target_map: NavMapV2,
    *,
    pairs: tuple[NavElementPairV1, ...],
    reason: str,
    overlap_fraction: float,
    inlier_pairs: tuple[NavElementPairV1, ...] = (),
    transform: Optional[NavRigidTransformV1] = None,
    rms_error: Optional[float] = None,
    maximum_error: Optional[float] = None,
    rotation_determined: bool = False,
    uncertainty: float = 1.0,
) -> NavAlignmentResultV1:
    """Construct one consistent UNKNOWN alignment result."""
    inlier_fraction = 0.0 if not pairs else len(inlier_pairs) / len(pairs)
    return NavAlignmentResultV1(
        source_map_ref=_source_map_ref(source_map),
        target_map_ref=_source_map_ref(target_map),
        status=NavAlignmentStatusV1.UNKNOWN,
        transform=transform,
        element_pairs=pairs,
        inlier_pairs=inlier_pairs,
        rms_error=rms_error,
        maximum_error=maximum_error,
        overlap_fraction=overlap_fraction,
        inlier_fraction=inlier_fraction,
        rotation_determined=rotation_determined,
        uncertainty=uncertainty,
        reason=reason,
    )


def _fit_rigid_transform(
    source_map: NavMapV2,
    target_map: NavMapV2,
    source_points: tuple[NavPointV1, ...],
    target_points: tuple[NavPointV1, ...],
    indices: tuple[int, ...],
    *,
    method: str,
) -> tuple[NavRigidTransformV1, bool]:
    """Fit one least-squares rigid transform to a selected correspondence subset."""
    selected_source = tuple(source_points[index] for index in indices)
    selected_target = tuple(target_points[index] for index in indices)
    source_mean = _mean_point(selected_source)
    target_mean = _mean_point(selected_target)
    centered_source = tuple((point.x - source_mean.x, point.y - source_mean.y) for point in selected_source)
    centered_target = tuple((point.x - target_mean.x, point.y - target_mean.y) for point in selected_target)
    source_spread = math.fsum(x * x + y * y for x, y in centered_source)
    target_spread = math.fsum(x * x + y * y for x, y in centered_target)
    rotation_determined = (
        len(indices) >= 2
        and source_spread > _GEOMETRY_NUMERICAL_EPSILON
        and target_spread > _GEOMETRY_NUMERICAL_EPSILON
    )
    if rotation_determined:
        dot_sum = math.fsum(
            source_x * target_x + source_y * target_y
            for (source_x, source_y), (target_x, target_y) in zip(centered_source, centered_target)
        )
        cross_sum = math.fsum(
            source_x * target_y - source_y * target_x
            for (source_x, source_y), (target_x, target_y) in zip(centered_source, centered_target)
        )
        rotation_degrees = math.degrees(math.atan2(cross_sum, dot_sum))
    else:
        rotation_degrees = 0.0
    transform = NavRigidTransformV1(
        source_frame_id=source_map.frame.frame_id,
        target_frame_id=target_map.frame.frame_id,
        rotation_degrees=rotation_degrees,
        translation_x=target_mean.x - source_mean.x,
        translation_y=target_mean.y - source_mean.y,
        pivot=source_mean,
        method=method,
    )
    return transform, rotation_determined


def _alignment_errors(
    transform: NavRigidTransformV1,
    source_points: tuple[NavPointV1, ...],
    target_points: tuple[NavPointV1, ...],
) -> tuple[float, ...]:
    """Return centroid errors for all current correspondence hypotheses."""
    return tuple(
        _point_distance(transform.apply_point(source_point), target_point)
        for source_point, target_point in zip(source_points, target_points)
    )


def _median(values: tuple[float, ...]) -> float:
    """Return the deterministic median of a non-empty numeric tuple."""
    ordered = sorted(values)
    midpoint = len(ordered) // 2
    if len(ordered) % 2:
        return ordered[midpoint]
    return (ordered[midpoint - 1] + ordered[midpoint]) / 2.0


def _robust_alignment_fit(
    source_map: NavMapV2,
    target_map: NavMapV2,
    pairs: tuple[NavElementPairV1, ...],
    source_points: tuple[NavPointV1, ...],
    target_points: tuple[NavPointV1, ...],
    *,
    inlier_tolerance: float,
) -> tuple[NavRigidTransformV1, bool, tuple[int, ...], tuple[float, ...]]:
    """Return a bounded deterministic robust fit over fixed correspondence hypotheses.

    Candidate transforms are fit from all pairs, each single pair, and every
    two-pair subset.  The fixed correspondence hypotheses are never permuted.
    The winning transform maximizes inlier count before minimizing median and
    RMS error.  This prevents one genuinely changed element from dragging the
    whole frame and making every otherwise stable element appear different.
    """
    count = len(pairs)
    index_sets: list[tuple[int, ...]] = [tuple(range(count))]
    index_sets.extend((index,) for index in range(count))
    index_sets.extend((first, second) for first in range(count) for second in range(first + 1, count))
    unique_index_sets = tuple(dict.fromkeys(index_sets))
    candidates: list[
        tuple[
            tuple[float, ...],
            NavRigidTransformV1,
            bool,
            tuple[int, ...],
            tuple[float, ...],
        ]
    ] = []
    for indices in unique_index_sets:
        method = "candidate_rigid_subset" if len(indices) >= 2 else "candidate_translation_subset"
        transform, rotation_determined = _fit_rigid_transform(
            source_map,
            target_map,
            source_points,
            target_points,
            indices,
            method=method,
        )
        errors = _alignment_errors(transform, source_points, target_points)
        inliers = tuple(index for index, error in enumerate(errors) if error <= inlier_tolerance)
        if not inliers:
            continue
        inlier_errors = tuple(errors[index] for index in inliers)
        inlier_rms = math.sqrt(math.fsum(error * error for error in inlier_errors) / len(inlier_errors))
        total_rms = math.sqrt(math.fsum(error * error for error in errors) / len(errors))
        key = (
            -float(len(inliers)),
            _median(errors),
            inlier_rms,
            total_rms,
            abs(transform.rotation_degrees),
            float(len(indices)),
        )
        candidates.append((key, transform, rotation_determined, inliers, errors))
    if not candidates:
        transform, rotation_determined = _fit_rigid_transform(
            source_map,
            target_map,
            source_points,
            target_points,
            tuple(range(count)),
            method="least_squares_rigid_2d",
        )
        errors = _alignment_errors(transform, source_points, target_points)
        return transform, rotation_determined, (), errors
    _key, _transform, _rotation_determined, inliers, _errors = min(candidates, key=lambda row: row[0])
    method = "robust_inlier_rigid_2d" if len(inliers) >= 2 else "robust_inlier_translation_only"
    transform, rotation_determined = _fit_rigid_transform(
        source_map,
        target_map,
        source_points,
        target_points,
        inliers,
        method=method,
    )
    errors = _alignment_errors(transform, source_points, target_points)
    refined_inliers = tuple(index for index, error in enumerate(errors) if error <= inlier_tolerance)
    if refined_inliers and refined_inliers != inliers:
        method = "robust_inlier_rigid_2d" if len(refined_inliers) >= 2 else "robust_inlier_translation_only"
        transform, rotation_determined = _fit_rigid_transform(
            source_map,
            target_map,
            source_points,
            target_points,
            refined_inliers,
            method=method,
        )
        errors = _alignment_errors(transform, source_points, target_points)
        inliers = tuple(index for index, error in enumerate(errors) if error <= inlier_tolerance)
    else:
        inliers = refined_inliers or inliers
    return transform, rotation_determined, inliers, errors


def _finalize_alignment(
    source_map: NavMapV2,
    target_map: NavMapV2,
    *,
    pairs: tuple[NavElementPairV1, ...],
    transform: NavRigidTransformV1,
    rotation_determined: bool,
    inlier_indices: tuple[int, ...],
    errors: tuple[float, ...],
    overlap: float,
    union_count: int,
    thresholds: NavMatchThresholdsV1,
    success_reason: str,
) -> NavAlignmentResultV1:
    """Return one validated ALIGNED/UNKNOWN result from explicit fit evidence."""
    inlier_pairs = tuple(pairs[index] for index in inlier_indices)
    rms_error = math.sqrt(math.fsum(error * error for error in errors) / len(errors))
    maximum_error = max(errors)
    inlier_fraction = len(inlier_pairs) / len(pairs)
    effective_coverage = 0.0 if union_count == 0 else len(inlier_pairs) / union_count
    normalized_error = (
        0.0
        if thresholds.maximum_alignment_rms_error == 0.0 and rms_error == 0.0
        else 1.0
        if thresholds.maximum_alignment_rms_error == 0.0
        else min(1.0, rms_error / thresholds.maximum_alignment_rms_error)
    )
    uncertainty = max(
        normalized_error,
        1.0 - overlap,
        1.0 - inlier_fraction,
        0.0 if rotation_determined else 0.5,
    )
    if effective_coverage < thresholds.minimum_correspondence_coverage:
        return _alignment_unknown(
            source_map,
            target_map,
            pairs=pairs,
            inlier_pairs=inlier_pairs,
            reason="inlier_coverage_below_threshold",
            overlap_fraction=overlap,
            transform=transform,
            rms_error=rms_error,
            maximum_error=maximum_error,
            rotation_determined=rotation_determined,
            uncertainty=uncertainty,
        )
    if rms_error > thresholds.maximum_alignment_rms_error:
        return _alignment_unknown(
            source_map,
            target_map,
            pairs=pairs,
            inlier_pairs=inlier_pairs,
            reason="alignment_error_above_threshold",
            overlap_fraction=overlap,
            transform=transform,
            rms_error=rms_error,
            maximum_error=maximum_error,
            rotation_determined=rotation_determined,
            uncertainty=uncertainty,
        )
    return NavAlignmentResultV1(
        source_map_ref=_source_map_ref(source_map),
        target_map_ref=_source_map_ref(target_map),
        status=NavAlignmentStatusV1.ALIGNED,
        transform=transform,
        element_pairs=pairs,
        inlier_pairs=inlier_pairs,
        rms_error=rms_error,
        maximum_error=maximum_error,
        overlap_fraction=overlap,
        inlier_fraction=inlier_fraction,
        rotation_determined=rotation_determined,
        uncertainty=uncertainty,
        reason=success_reason,
    )


def align_navmaps(
    source_map: NavMapV2,
    target_map: NavMapV2,
    *,
    thresholds: NavMatchThresholdsV1,
) -> NavAlignmentResultV1:
    """Return explicit alignment evidence between compatible map frames.

    Maps declaring the same frame id use the identity transform so genuine world
    changes cannot be aligned away.  Different frame ids with the same units and
    axis semantics receive a bounded robust rigid fit.  Correspondences are
    deterministic: exact local identity first, then unique roles and unique
    feature/parent structure.  There is no exhaustive element permutation or
    silent frame conversion.
    """
    _require_instance(source_map, NavMapV2, field_name="source_map")
    _require_instance(target_map, NavMapV2, field_name="target_map")
    _require_instance(thresholds, NavMatchThresholdsV1, field_name="thresholds")
    pairs = _element_pairs(source_map, target_map)
    union_count = len(source_map.elements) + len(target_map.elements) - len(pairs)
    overlap = 1.0 if union_count == 0 else len(pairs) / union_count
    if source_map.frame.units != target_map.frame.units:
        return _alignment_unknown(
            source_map,
            target_map,
            pairs=pairs,
            reason="incompatible_frame_units",
            overlap_fraction=overlap,
        )
    if source_map.frame.x_axis != target_map.frame.x_axis or source_map.frame.y_axis != target_map.frame.y_axis:
        return _alignment_unknown(
            source_map,
            target_map,
            pairs=pairs,
            reason="incompatible_frame_axes",
            overlap_fraction=overlap,
        )
    if not pairs:
        return _alignment_unknown(
            source_map,
            target_map,
            pairs=pairs,
            reason="no_correspondences",
            overlap_fraction=0.0,
        )

    source_points = tuple(
        _geometry_centroid(get_element(source_map, pair.source_element_id).geometry)[0]
        for pair in pairs
    )
    target_points = tuple(
        _geometry_centroid(get_element(target_map, pair.target_element_id).geometry)[0]
        for pair in pairs
    )
    inlier_tolerance = max(thresholds.maximum_geometry_point_error, _GEOMETRY_NUMERICAL_EPSILON)
    if source_map.frame.frame_id == target_map.frame.frame_id:
        transform = NavRigidTransformV1(
            source_frame_id=source_map.frame.frame_id,
            target_frame_id=target_map.frame.frame_id,
            rotation_degrees=0.0,
            translation_x=0.0,
            translation_y=0.0,
            pivot=NavPointV1(0.0, 0.0),
            method="declared_same_frame_identity",
        )
        errors = _alignment_errors(transform, source_points, target_points)
        inlier_indices = tuple(
            index
            for index, error in enumerate(errors)
            if error <= inlier_tolerance
        )
        return _finalize_alignment(
            source_map,
            target_map,
            pairs=pairs,
            transform=transform,
            rotation_determined=True,
            inlier_indices=inlier_indices,
            errors=errors,
            overlap=overlap,
            union_count=union_count,
            thresholds=thresholds,
            success_reason="aligned_declared_frame_identity",
        )

    transform, rotation_determined, inlier_indices, errors = _robust_alignment_fit(
        source_map,
        target_map,
        pairs,
        source_points,
        target_points,
        inlier_tolerance=inlier_tolerance,
    )
    return _finalize_alignment(
        source_map,
        target_map,
        pairs=pairs,
        transform=transform,
        rotation_determined=rotation_determined,
        inlier_indices=inlier_indices,
        errors=errors,
        overlap=overlap,
        union_count=union_count,
        thresholds=thresholds,
        success_reason=(
            "aligned_robust_rigid"
            if rotation_determined
            else "aligned_robust_translation_only"
        ),
    )


def _ordered_point_error(
    source_points: tuple[NavPointV1, ...],
    target_points: tuple[NavPointV1, ...],
) -> tuple[float, float]:
    """Return RMS and maximum pointwise distance for equal-length sequences."""
    errors = tuple(_point_distance(source, target) for source, target in zip(source_points, target_points))
    return math.sqrt(math.fsum(error * error for error in errors) / len(errors)), max(errors)


def _geometry_errors(
    source_geometry: NavGeometryV1,
    target_geometry: NavGeometryV1,
    transform: NavRigidTransformV1,
) -> tuple[Optional[float], Optional[float]]:
    """Return order-aware geometry errors after alignment, or ``(None, None)``."""
    if source_geometry.kind is not target_geometry.kind:
        return None, None
    if len(source_geometry.points) != len(target_geometry.points):
        return None, None
    transformed = tuple(transform.apply_point(point) for point in source_geometry.points)
    target_points = target_geometry.points
    candidates: list[tuple[NavPointV1, ...]] = [target_points]
    if source_geometry.kind in (NavGeometryKindV1.SEGMENT, NavGeometryKindV1.POLYLINE):
        candidates.append(tuple(reversed(target_points)))
    if source_geometry.kind is NavGeometryKindV1.POLYGON:
        point_count = len(target_points)
        for reverse in (False, True):
            ordered = tuple(reversed(target_points)) if reverse else target_points
            for offset in range(point_count):
                candidates.append(ordered[offset:] + ordered[:offset])
    return min((_ordered_point_error(transformed, candidate) for candidate in candidates), key=lambda row: row)


def _activation_differences(
    source: NavElementV1,
    target: NavElementV1,
) -> tuple[tuple[str, ...], tuple[str, ...], tuple[tuple[str, float], ...], float]:
    """Return activation-name and strength differences without comparing provenance."""
    source_by_name = {activation.name: activation for activation in source.activations}
    target_by_name = {activation.name: activation for activation in target.activations}
    source_names = set(source_by_name)
    target_names = set(target_by_name)
    missing = tuple(sorted(source_names - target_names))
    novel = tuple(sorted(target_names - source_names))
    deltas = tuple(
        sorted(
            (
                name,
                target_by_name[name].strength - source_by_name[name].strength,
            )
            for name in source_names.intersection(target_names)
        )
    )
    maximum_delta = max((abs(delta) for _name, delta in deltas), default=0.0)
    return missing, novel, deltas, maximum_delta


def _mapped_parent_matches(
    source: NavElementV1,
    target: NavElementV1,
    source_to_target: Mapping[str, str],
) -> bool:
    """Return whether local parent structure agrees under the correspondence map."""
    if source.parent_element_id is None:
        return target.parent_element_id is None
    mapped_parent = source_to_target.get(source.parent_element_id)
    return mapped_parent is not None and mapped_parent == target.parent_element_id


def _mapped_relation_key(relation: NavRelationV1, source_to_target: Mapping[str, str]) -> tuple[str, str, str]:
    """Map source relation endpoints into the target id namespace when possible."""
    source_id = source_to_target.get(relation.source_element_id, f"unmapped:{relation.source_element_id}")
    target_id = source_to_target.get(relation.target_element_id, f"unmapped:{relation.target_element_id}")
    return relation.relation_type, source_id, target_id


def _mapped_link_key(link: NavMapLinkV1, source_to_target: Mapping[str, str]) -> tuple[str, str, int, str]:
    """Map a source link's local origin into the target id namespace."""
    if link.source_element_id is None:
        source_id = ""
    else:
        source_id = source_to_target.get(link.source_element_id, f"unmapped:{link.source_element_id}")
    return link.link_type, link.target_ref.map_id, link.target_ref.revision, source_id


def _jaccard_score(first: set[Any], second: set[Any]) -> float:
    """Return Jaccard agreement, treating two empty sets as complete agreement."""
    union = first.union(second)
    if not union:
        return 1.0
    return len(first.intersection(second)) / len(union)


def _weighted_match_score(
    map_role_score: float,
    element_score: float,
    relation_score: float,
    link_score: float,
    *,
    relations_present: bool,
    links_present: bool,
) -> float:
    """Return a normalized score whose active components remain separately visible."""
    components: list[tuple[float, float]] = [(0.10, map_role_score), (0.65, element_score)]
    if relations_present:
        components.append((0.15, relation_score))
    if links_present:
        components.append((0.10, link_score))
    total_weight = math.fsum(weight for weight, _value in components)
    return math.fsum(weight * value for weight, value in components) / total_weight


def _unknown_match(
    source_map: NavMapV2,
    target_map: NavMapV2,
    *,
    alignment: NavAlignmentResultV1,
    thresholds: NavMatchThresholdsV1,
) -> NavMapMatchResultV1:
    """Return a pairwise UNKNOWN match without manufacturing correspondences."""
    return NavMapMatchResultV1(
        source_map_ref=_source_map_ref(source_map),
        target_map_ref=_source_map_ref(target_map),
        status=NavMatchStatusV1.UNKNOWN,
        alignment=alignment,
        thresholds=thresholds,
        correspondences=(),
        missing_source_element_ids=tuple(element.element_id for element in source_map.elements),
        novel_target_element_ids=tuple(element.element_id for element in target_map.elements),
        conflicted_element_pairs=(),
        map_role_match=source_map.role == target_map.role,
        coverage=0.0,
        element_score=0.0,
        relation_score=0.0,
        link_score=0.0,
        score=0.0,
        score_semantics="weighted_active_components_v1",
        reason=alignment.reason,
    )


def match_navmaps(
    source_map: NavMapV2,
    target_map: NavMapV2,
    *,
    thresholds: NavMatchThresholdsV1,
) -> NavMapMatchResultV1:
    """Align and structurally compare two maps without granting acceptance.

    The scalar score is only a ranking convenience.  Correspondences, component
    checks, missing/novel elements, conflicts, coverage, and alignment remain
    first-class outputs and are required for later residual and revision logic.
    """
    alignment = align_navmaps(source_map, target_map, thresholds=thresholds)
    alignment_transform = alignment.transform
    if alignment.status is NavAlignmentStatusV1.UNKNOWN or alignment_transform is None:
        return _unknown_match(
            source_map,
            target_map,
            alignment=alignment,
            thresholds=thresholds,
        )
    source_to_target = {
        pair.source_element_id: pair.target_element_id
        for pair in alignment.element_pairs
    }
    correspondences: list[NavElementCorrespondenceV1] = []
    for pair in alignment.element_pairs:
        source = get_element(source_map, pair.source_element_id)
        target = get_element(target_map, pair.target_element_id)
        rms_error, maximum_error = _geometry_errors(source.geometry, target.geometry, alignment_transform)
        geometry_kind_match = source.geometry.kind is target.geometry.kind
        geometry_within = (
            geometry_kind_match
            and rms_error is not None
            and maximum_error is not None
            and rms_error <= thresholds.maximum_geometry_rms_error
            and maximum_error <= thresholds.maximum_geometry_point_error
        )
        missing_activations, novel_activations, _deltas, maximum_delta = _activation_differences(source, target)
        activation_names_match = not missing_activations and not novel_activations
        activations_within = (
            activation_names_match
            and maximum_delta <= thresholds.maximum_activation_strength_delta
        )
        role_match = source.role == target.role
        parent_match = _mapped_parent_matches(source, target, source_to_target)
        matched = role_match and geometry_within and activations_within and parent_match
        correspondences.append(
            NavElementCorrespondenceV1(
                source_element_id=source.element_id,
                target_element_id=target.element_id,
                method=pair.method,
                role_match=role_match,
                geometry_kind_match=geometry_kind_match,
                geometry_rms_error=rms_error,
                geometry_maximum_error=maximum_error,
                geometry_within_tolerance=geometry_within,
                activation_names_match=activation_names_match,
                maximum_activation_strength_delta=maximum_delta,
                activations_within_tolerance=activations_within,
                parent_match=parent_match,
                matched=matched,
            )
        )
    paired_source_ids = set(source_to_target)
    paired_target_ids = set(source_to_target.values())
    missing = tuple(element.element_id for element in source_map.elements if element.element_id not in paired_source_ids)
    novel = tuple(element.element_id for element in target_map.elements if element.element_id not in paired_target_ids)
    conflicts = tuple(
        (item.source_element_id, item.target_element_id)
        for item in correspondences
        if not item.matched
    )
    union_count = len(source_map.elements) + len(target_map.elements) - len(correspondences)
    coverage = 1.0 if union_count == 0 else len(correspondences) / union_count
    matched_count = sum(1 for item in correspondences if item.matched)
    element_score = 1.0 if union_count == 0 else matched_count / union_count
    source_relation_keys = {
        _mapped_relation_key(relation, source_to_target)
        for relation in source_map.relations
    }
    target_relation_keys = {relation.structural_key() for relation in target_map.relations}
    relation_score = _jaccard_score(source_relation_keys, target_relation_keys)
    source_link_keys = {
        _mapped_link_key(link, source_to_target)
        for link in source_map.links
    }
    target_link_keys = {link.structural_key() for link in target_map.links}
    link_score = _jaccard_score(source_link_keys, target_link_keys)
    map_role_match = source_map.role == target_map.role
    score = _weighted_match_score(
        1.0 if map_role_match else 0.0,
        element_score,
        relation_score,
        link_score,
        relations_present=bool(source_relation_keys or target_relation_keys),
        links_present=bool(source_link_keys or target_link_keys),
    )
    exact = (
        map_role_match
        and not missing
        and not novel
        and not conflicts
        and relation_score == 1.0
        and link_score == 1.0
    )
    return NavMapMatchResultV1(
        source_map_ref=_source_map_ref(source_map),
        target_map_ref=_source_map_ref(target_map),
        status=NavMatchStatusV1.EXACT if exact else NavMatchStatusV1.PARTIAL,
        alignment=alignment,
        thresholds=thresholds,
        correspondences=tuple(correspondences),
        missing_source_element_ids=missing,
        novel_target_element_ids=novel,
        conflicted_element_pairs=conflicts,
        map_role_match=map_role_match,
        coverage=coverage,
        element_score=element_score,
        relation_score=relation_score,
        link_score=link_score,
        score=score,
        score_semantics="weighted_active_components_v1",
        reason="exact_structural_match" if exact else "partial_structural_match",
    )


def match_rank(
    query_map: NavMapV2,
    candidates: tuple[NavMapV2, ...],
    *,
    thresholds: NavMatchThresholdsV1,
) -> NavMatchRankingV1:
    """Rank a bounded candidate set and preserve AMBIGUOUS/UNKNOWN outcomes."""
    _require_instance(query_map, NavMapV2, field_name="query_map")
    _require_instance(thresholds, NavMatchThresholdsV1, field_name="thresholds")
    candidate_tuple = tuple(candidates)
    for candidate in candidate_tuple:
        _require_instance(candidate, NavMapV2, field_name="candidate")
    if len(candidate_tuple) > thresholds.maximum_candidate_count:
        raise ValueError(
            "candidate count exceeds thresholds.maximum_candidate_count "
            f"({len(candidate_tuple)} > {thresholds.maximum_candidate_count})"
        )
    candidate_refs = tuple(_source_map_ref(candidate) for candidate in candidate_tuple)
    if len(candidate_refs) != len(set(candidate_refs)):
        raise ValueError("candidate map references must be unique")
    if not candidate_tuple:
        return NavMatchRankingV1(
            query_map_ref=_source_map_ref(query_map),
            status=NavMatchRankStatusV1.UNKNOWN,
            ranked_matches=(),
            best_candidate_ref=None,
            winner_ref=None,
            margin=None,
            ambiguity_margin=thresholds.ambiguity_margin,
            reason="no_candidates",
        )
    matches = tuple(match_navmaps(query_map, candidate, thresholds=thresholds) for candidate in candidate_tuple)
    ranked = tuple(
        sorted(
            matches,
            key=lambda result: (
                result.status is NavMatchStatusV1.UNKNOWN,
                -result.score,
                result.target_map_ref.map_id,
                result.target_map_ref.revision,
            ),
        )
    )
    valid = tuple(result for result in ranked if result.status is not NavMatchStatusV1.UNKNOWN)
    if not valid:
        return NavMatchRankingV1(
            query_map_ref=_source_map_ref(query_map),
            status=NavMatchRankStatusV1.UNKNOWN,
            ranked_matches=ranked,
            best_candidate_ref=None,
            winner_ref=None,
            margin=None,
            ambiguity_margin=thresholds.ambiguity_margin,
            reason="no_alignable_candidates",
        )
    best = valid[0]
    margin = 1.0 if len(valid) == 1 else max(0.0, best.score - valid[1].score)
    if best.score < thresholds.minimum_rank_score:
        return NavMatchRankingV1(
            query_map_ref=_source_map_ref(query_map),
            status=NavMatchRankStatusV1.UNKNOWN,
            ranked_matches=ranked,
            best_candidate_ref=best.target_map_ref,
            winner_ref=None,
            margin=margin,
            ambiguity_margin=thresholds.ambiguity_margin,
            reason="best_score_below_threshold",
        )
    if len(valid) > 1 and margin <= thresholds.ambiguity_margin:
        return NavMatchRankingV1(
            query_map_ref=_source_map_ref(query_map),
            status=NavMatchRankStatusV1.AMBIGUOUS,
            ranked_matches=ranked,
            best_candidate_ref=best.target_map_ref,
            winner_ref=None,
            margin=margin,
            ambiguity_margin=thresholds.ambiguity_margin,
            reason="top_margin_ambiguous",
        )
    return NavMatchRankingV1(
        query_map_ref=_source_map_ref(query_map),
        status=NavMatchRankStatusV1.RANKED,
        ranked_matches=ranked,
        best_candidate_ref=best.target_map_ref,
        winner_ref=best.target_map_ref,
        margin=margin,
        ambiguity_margin=thresholds.ambiguity_margin,
        reason="clear_ranked_winner",
    )


def _relation_residuals(
    expected_map: NavMapV2,
    evidence_map: NavMapV2,
    source_to_target: Mapping[str, str],
) -> tuple[
    tuple[tuple[str, str, str], ...],
    tuple[tuple[str, str, str], ...],
    tuple[tuple[str, str, str], ...],
]:
    """Return missing, novel, and source-provenance-changed relation keys."""
    evidence_by_key = {relation.structural_key(): relation for relation in evidence_map.relations}
    matched_target_keys: set[tuple[str, str, str]] = set()
    missing: list[tuple[str, str, str]] = []
    changed_provenance: list[tuple[str, str, str]] = []
    for relation in expected_map.relations:
        mapped_key = _mapped_relation_key(relation, source_to_target)
        evidence_relation = evidence_by_key.get(mapped_key)
        if evidence_relation is None:
            missing.append(relation.structural_key())
            continue
        matched_target_keys.add(mapped_key)
        if evidence_relation.provenance != relation.provenance:
            changed_provenance.append(mapped_key)
    novel = tuple(key for key in evidence_by_key if key not in matched_target_keys)
    return tuple(sorted(missing)), tuple(sorted(novel)), tuple(sorted(changed_provenance))


def _link_residuals(
    expected_map: NavMapV2,
    evidence_map: NavMapV2,
    source_to_target: Mapping[str, str],
) -> tuple[
    tuple[tuple[str, str, int, str], ...],
    tuple[tuple[str, str, int, str], ...],
    tuple[tuple[str, str, int, str], ...],
]:
    """Return missing, novel, and source-provenance-changed map-link keys."""
    evidence_by_key = {link.structural_key(): link for link in evidence_map.links}
    matched_target_keys: set[tuple[str, str, int, str]] = set()
    missing: list[tuple[str, str, int, str]] = []
    changed_provenance: list[tuple[str, str, int, str]] = []
    for link in expected_map.links:
        mapped_key = _mapped_link_key(link, source_to_target)
        evidence_link = evidence_by_key.get(mapped_key)
        if evidence_link is None:
            missing.append(link.structural_key())
            continue
        matched_target_keys.add(mapped_key)
        if evidence_link.provenance != link.provenance:
            changed_provenance.append(mapped_key)
    novel = tuple(key for key in evidence_by_key if key not in matched_target_keys)
    return tuple(sorted(missing)), tuple(sorted(novel)), tuple(sorted(changed_provenance))


def structured_residual(
    expected_map: NavMapV2,
    evidence_map: NavMapV2,
    *,
    match_result: NavMapMatchResultV1,
) -> NavStructuredResidualV1:
    """Return map-local expected-versus-evidence differences linked to a match."""
    _require_instance(expected_map, NavMapV2, field_name="expected_map")
    _require_instance(evidence_map, NavMapV2, field_name="evidence_map")
    _require_instance(match_result, NavMapMatchResultV1, field_name="match_result")
    if match_result.source_map_ref != _source_map_ref(expected_map):
        raise ValueError("match_result source does not identify expected_map")
    if match_result.target_map_ref != _source_map_ref(evidence_map):
        raise ValueError("match_result target does not identify evidence_map")
    source_to_target = {
        correspondence.source_element_id: correspondence.target_element_id
        for correspondence in match_result.correspondences
    }
    element_residuals: list[NavElementResidualV1] = []
    for correspondence in match_result.correspondences:
        expected = get_element(expected_map, correspondence.source_element_id)
        evidence = get_element(evidence_map, correspondence.target_element_id)
        missing, novel, deltas, _maximum_delta = _activation_differences(expected, evidence)
        role_changed = not correspondence.role_match
        parent_changed = not correspondence.parent_match
        geometry_kind_changed = not correspondence.geometry_kind_match
        geometry_outside = not correspondence.geometry_within_tolerance
        expected_activations = {activation.name: activation for activation in expected.activations}
        evidence_activations = {activation.name: activation for activation in evidence.activations}
        shared_activation_names = set(expected_activations).intersection(evidence_activations)
        provenance_changed = expected.provenance != evidence.provenance or any(
            expected_activations[name].provenance != evidence_activations[name].provenance
            for name in shared_activation_names
        )
        content_difference = (
            role_changed
            or parent_changed
            or geometry_kind_changed
            or geometry_outside
            or bool(missing)
            or bool(novel)
            or not correspondence.activations_within_tolerance
        )
        element_residuals.append(
            NavElementResidualV1(
                expected_element_id=expected.element_id,
                evidence_element_id=evidence.element_id,
                correspondence_method=correspondence.method,
                role_changed=role_changed,
                parent_changed=parent_changed,
                geometry_kind_changed=geometry_kind_changed,
                geometry_rms_error=correspondence.geometry_rms_error,
                geometry_maximum_error=correspondence.geometry_maximum_error,
                geometry_outside_tolerance=geometry_outside,
                missing_activation_names=missing,
                novel_activation_names=novel,
                activation_strength_deltas=deltas,
                provenance_changed=provenance_changed,
                content_difference=content_difference,
                source_difference=provenance_changed,
            )
        )
    missing_relations, novel_relations, changed_relation_provenance = _relation_residuals(
        expected_map,
        evidence_map,
        source_to_target,
    )
    missing_links, novel_links, changed_link_provenance = _link_residuals(
        expected_map,
        evidence_map,
        source_to_target,
    )
    map_role_changed = not match_result.map_role_match
    content_difference = (
        map_role_changed
        or bool(match_result.missing_source_element_ids)
        or bool(match_result.novel_target_element_ids)
        or any(residual.content_difference for residual in element_residuals)
        or bool(missing_relations)
        or bool(novel_relations)
        or bool(missing_links)
        or bool(novel_links)
    )
    map_provenance_changed = expected_map.provenance != evidence_map.provenance
    source_difference = (
        map_provenance_changed
        or any(residual.source_difference for residual in element_residuals)
        or bool(changed_relation_provenance)
        or bool(changed_link_provenance)
    )
    if match_result.status is NavMatchStatusV1.UNKNOWN:
        reason = "alignment_unknown"
        content_difference = False
    elif content_difference:
        reason = "content_changed"
    elif source_difference:
        reason = "content_equal_source_changed"
    else:
        reason = "content_and_source_equal"
    return NavStructuredResidualV1(
        expected_map_ref=_source_map_ref(expected_map),
        evidence_map_ref=_source_map_ref(evidence_map),
        match_result=match_result,
        element_residuals=tuple(element_residuals),
        missing_expected_element_ids=match_result.missing_source_element_ids,
        novel_evidence_element_ids=match_result.novel_target_element_ids,
        missing_relations=missing_relations,
        novel_relations=novel_relations,
        changed_relation_provenance=changed_relation_provenance,
        missing_links=missing_links,
        novel_links=novel_links,
        changed_link_provenance=changed_link_provenance,
        map_role_changed=map_role_changed,
        map_provenance_changed=map_provenance_changed,
        has_content_difference=content_difference,
        has_source_difference=source_difference,
        reason=reason,
    )


def propose_revision(
    base_map: NavMapV2,
    evidence_map: NavMapV2,
    *,
    residual: NavStructuredResidualV1,
    thresholds: NavRevisionThresholdsV1,
) -> NavRevisionProposalV1:
    """Return a pure open-world revision proposal; do not mutate or accept a map."""
    _require_instance(base_map, NavMapV2, field_name="base_map")
    _require_instance(evidence_map, NavMapV2, field_name="evidence_map")
    _require_instance(residual, NavStructuredResidualV1, field_name="residual")
    _require_instance(thresholds, NavRevisionThresholdsV1, field_name="thresholds")
    if residual.expected_map_ref != _source_map_ref(base_map):
        raise ValueError("residual expected map does not identify base_map")
    if residual.evidence_map_ref != _source_map_ref(evidence_map):
        raise ValueError("residual evidence map does not identify evidence_map")
    match_result = residual.match_result
    changed_ids = {
        element_residual.expected_element_id
        for element_residual in residual.element_residuals
        if element_residual.content_difference
    }
    changed_ids.update(residual.missing_expected_element_ids)
    changed_ids.update(residual.novel_evidence_element_ids)
    if match_result.status is NavMatchStatusV1.UNKNOWN:
        if match_result.reason == "no_correspondences" and evidence_map.elements:
            decision = NavRevisionDecisionV1.CREATE
            reason = "novel_map_without_correspondence"
        else:
            decision = NavRevisionDecisionV1.UNKNOWN
            reason = "insufficient_alignment_evidence"
    elif not residual.has_content_difference and match_result.score >= thresholds.minimum_keep_score:
        decision = NavRevisionDecisionV1.KEEP
        reason = "content_equivalent"
    elif residual.map_role_changed and evidence_map.elements:
        decision = NavRevisionDecisionV1.CREATE
        reason = "map_role_changed_create_new_family"
    elif (
        match_result.coverage >= thresholds.minimum_revise_coverage
        and match_result.score >= thresholds.minimum_revise_score
    ):
        decision = NavRevisionDecisionV1.REVISE
        reason = "related_content_requires_revision"
    elif (
        match_result.coverage >= thresholds.minimum_revise_coverage
        and match_result.score <= thresholds.maximum_reject_all_score
    ):
        decision = NavRevisionDecisionV1.REJECT_ALL
        reason = "high_overlap_but_incompatible_content"
    elif match_result.coverage < thresholds.minimum_revise_coverage and evidence_map.elements:
        decision = NavRevisionDecisionV1.CREATE
        reason = "insufficient_overlap_create_new_family"
    else:
        decision = NavRevisionDecisionV1.UNKNOWN
        reason = "borderline_revision_evidence"
    return NavRevisionProposalV1(
        decision=decision,
        base_map_ref=_source_map_ref(base_map),
        evidence_map_ref=_source_map_ref(evidence_map),
        residual=residual,
        thresholds=thresholds,
        changed_element_ids=tuple(sorted(changed_ids)),
        reason=reason,
    )


def _revised_evidence_content(
    evidence_map: NavMapV2,
    match_result: NavMapMatchResultV1,
) -> tuple[tuple[NavElementV1, ...], tuple[NavRelationV1, ...], tuple[NavMapLinkV1, ...]]:
    """Return evidence content remapped onto stable base ids for a child revision."""
    evidence_to_base = {
        correspondence.target_element_id: correspondence.source_element_id
        for correspondence in match_result.correspondences
    }
    remapped_ids: dict[str, str] = {}
    used_ids: set[str] = set()
    for element in evidence_map.elements:
        remapped_id = evidence_to_base.get(element.element_id, element.element_id)
        if remapped_id in used_ids:
            raise ValueError("evidence-to-base id remapping would create duplicate element ids")
        remapped_ids[element.element_id] = remapped_id
        used_ids.add(remapped_id)
    elements = tuple(
        replace(
            element,
            element_id=remapped_ids[element.element_id],
            parent_element_id=(
                remapped_ids[element.parent_element_id]
                if element.parent_element_id is not None
                else None
            ),
        )
        for element in evidence_map.elements
    )
    relations = tuple(
        replace(
            relation,
            source_element_id=remapped_ids[relation.source_element_id],
            target_element_id=remapped_ids[relation.target_element_id],
        )
        for relation in evidence_map.relations
    )
    links = tuple(
        replace(
            link,
            source_element_id=(
                remapped_ids[link.source_element_id]
                if link.source_element_id is not None
                else None
            ),
        )
        for link in evidence_map.links
    )
    return elements, relations, links


def apply_revision(
    base_map: NavMapV2,
    evidence_map: NavMapV2,
    proposal: NavRevisionProposalV1,
    *,
    new_revision: Optional[int] = None,
    new_map_id: Optional[str] = None,
) -> NavMapV2:
    """Apply only an authorized pure proposal to create a child or new map family.

    ``KEEP`` returns the original immutable base record.  ``REVISE`` creates a
    child in the base family and preserves stable base element ids where a
    correspondence exists.  ``CREATE`` requires an explicit new map id and
    starts at revision 1.  UNKNOWN and REJECT_ALL cannot be applied.
    """
    _require_instance(base_map, NavMapV2, field_name="base_map")
    _require_instance(evidence_map, NavMapV2, field_name="evidence_map")
    _require_instance(proposal, NavRevisionProposalV1, field_name="proposal")
    if proposal.base_map_ref != _source_map_ref(base_map):
        raise ValueError("proposal base map does not identify base_map")
    if proposal.evidence_map_ref != _source_map_ref(evidence_map):
        raise ValueError("proposal evidence map does not identify evidence_map")
    if proposal.decision is NavRevisionDecisionV1.KEEP:
        if new_revision is not None or new_map_id is not None:
            raise ValueError("KEEP does not create a revision or a new map family")
        return base_map
    if proposal.decision in (NavRevisionDecisionV1.UNKNOWN, NavRevisionDecisionV1.REJECT_ALL):
        raise ValueError(f"cannot apply {proposal.decision.value} revision proposal")
    if proposal.decision is NavRevisionDecisionV1.CREATE:
        if new_map_id is None:
            raise ValueError("CREATE requires new_map_id")
        normalized_map_id = _normalize_identifier(new_map_id, field_name="new_map_id")
        if normalized_map_id == base_map.map_id:
            raise ValueError("CREATE new_map_id must differ from the base map_id")
        if new_revision not in (None, 1):
            raise ValueError("CREATE begins a new map family at revision 1")
        return NavMapV2(
            map_id=normalized_map_id,
            revision=1,
            parent_ref=None,
            role=evidence_map.role,
            frame=evidence_map.frame,
            elements=evidence_map.elements,
            relations=evidence_map.relations,
            links=evidence_map.links,
            provenance=evidence_map.provenance,
            schema=evidence_map.schema,
        )
    if proposal.residual.map_role_changed:
        raise ValueError("REVISE cannot apply evidence with a changed map role")
    if new_map_id is not None:
        raise ValueError("REVISE retains the base map_id and must not receive new_map_id")
    if new_revision is None:
        raise ValueError("REVISE requires new_revision")
    revision = _positive_revision(new_revision, field_name="new_revision")
    if revision <= base_map.revision:
        raise ValueError("new_revision must be greater than the base revision")
    elements, relations, links = _revised_evidence_content(
        evidence_map,
        proposal.residual.match_result,
    )
    return NavMapV2(
        map_id=base_map.map_id,
        revision=revision,
        parent_ref=_source_map_ref(base_map),
        role=base_map.role,
        frame=evidence_map.frame,
        elements=elements,
        relations=relations,
        links=links,
        provenance=evidence_map.provenance,
        schema=base_map.schema,
    )
