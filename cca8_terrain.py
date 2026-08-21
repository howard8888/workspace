# -*- coding: utf-8 -*-
"""Phase 6 terrain, hazards, lateral route sheets, and source-linked safety.

Purpose
-------
Phase 6 adds the first terrain/route domain to the single-operative Working
Navigation Map runtime introduced in Phase 5.  Two overlapping TripTik-like
route maps represent the exposed cliff-to-field segment and the field-to-shelter
segment.  A lateral transition is permitted only when the source and destination
share supported landmark/SELF correspondence and an explicit frame transform::

    SELF-maternal overview
        -> west route sheet
        -> lateral shift to east route sheet
        -> return/backtrack through the bounded ready set

The operative route map is projected into a second SurfaceGrid in dual-run with
the existing observation/NavPatch-derived grid.  The Phase 6 grid does not
silently replace ``ctx.wm_surfacegrid``.  It produces source-linked readouts for
cliff proximity, route relation, route clearance, hazard interpretation, and
safe-to-rest.  During migration those readouts may add a conservative safety
veto, but they may never weaken BodyMap, topology, fall, or other protected
legacy safety.

Continuity and revision economy
-------------------------------
The shared stationary route landmark has identity, observability, localization,
track status, negative evidence, and reacquisition represented separately.
Known occlusion may retain identity and a bounded last-supported localization;
reliable negative evidence withdraws transition support without deleting the
landmark identity.

A harmless vegetation branch oscillation is maintained in a compact live
overlay and does not revise either route map.  A fallen tree is a material
structural event: it adds a blocked segment, changes traversability/hazard, and
creates one newer east-route revision while leaving the unrelated west-route
signature unchanged.  No frame-by-frame movie of NavMaps is stored.

Authority boundary
------------------
This module may change which terrain map is operative and may add a protected
motion/rest veto through current source-linked readouts.  It does not choose a
behavioral primitive, weaken protected safety, mutate BodyMap, write WorldGraph
or Columns, model detailed locomotion, or fabricate current evidence from a
route prior.  The existing global single-winner PolicyRuntime remains intact.
"""

from __future__ import annotations

# The first route vertical slice intentionally keeps its typed records,
# deterministic map construction, projection, transitions, and renderer in one
# inspectable module.
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass
from enum import Enum
import math
from typing import Any, Optional

from cca8_env import EnvObservation
from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapRefV1,
    NavMapV2,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavSourceClassV1,
)
from cca8_navpatch import (
    CELL_BLOCKED,
    CELL_GOAL,
    CELL_HAZARD,
    CELL_TRAVERSABLE,
    CELL_UNKNOWN,
    SurfaceGridV1,
    derive_grid_slot_families_v1,
    grid_overlap_fraction_v1,
)
from cca8_working_memory import compute_navsummary_v1
from cca8_wnm_runtime import (
    WNMTransitionRecordV1,
    WNMTransitionTypeV1,
    wnm_commit_transition_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
    wnm_refresh_map_v1,
    wnm_return_to_ref_v1,
    wnm_summary_v1,
)

__version__ = "0.1.0"

__all__ = [
    "TerrainHazardInterpretationV1",
    "TerrainRouteRelationV1",
    "TerrainLandmarkObservabilityV1",
    "TerrainLandmarkTrackStatusV1",
    "TerrainLandmarkReacquisitionV1",
    "TerrainLandmarkContinuityV1",
    "TerrainDynamicOverlayV1",
    "TerrainRouteCorrespondenceV1",
    "TerrainPolicyReadoutV1",
    "TerrainWnmStateV1",
    "terrain_reset_v1",
    "terrain_wnm_observation_step_v1",
    "terrain_policy_readout_v1",
    "terrain_motion_veto_v1",
    "terrain_safe_to_rest_v1",
    "terrain_cliff_near_v1",
    "terrain_route_clear_v1",
    "terrain_summary_v1",
    "render_terrain_lines_v1",
    "__version__",
]

_WEST_ROLE = "terrain_route_west"
_EAST_ROLE = "terrain_route_east"
_OVERVIEW_ROLE = "self_maternal_scene"
_WEST_MAP_ID = "goat_route_cliff_to_field_v2"
_EAST_MAP_ID = "goat_route_field_to_shelter_v2"
_WEST_FRAME_ID = "route_west_sheet_frame_v1"
_EAST_FRAME_ID = "route_east_sheet_frame_v1"
_WORLD_FRAME_ID = "goat_route_world_frame_v1"
_SELF_IDENTITY = "self_individual"
_LANDMARK_IDENTITY = "route_landmark_boulder_v1"
_LANDMARK_ELEMENT = "shared_route_landmark"
_ROUTE_ELEMENT = "route_corridor"
_OVERLAP_ELEMENT = "route_overlap"
_CLIFF_ELEMENT = "cliff_boundary"
_SHELTER_ELEMENT = "shelter_goal"
_TREE_ELEMENT = "fallen_tree_obstacle"
_WEST_ORIGIN_WORLD_X = 0.0
_EAST_ORIGIN_WORLD_X = 0.75
_SHARED_LANDMARK_WORLD = NavPointV1(0.80, 0.40)
_CLIFF_WORLD_X = -0.25
_SHELTER_WORLD_X = 1.60
_TREE_WORLD_X = 1.20
_OVERLAP_WORLD_MIN_X = 0.65
_OVERLAP_WORLD_MAX_X = 1.00
_DEFAULT_HISTORY_LIMIT = 25
_DEFAULT_GRID_W = 16
_DEFAULT_GRID_H = 16
_DEFAULT_CELLS_PER_UNIT = 4.0
_DEFAULT_CLIFF_NEAR_DISTANCE = 0.45
_DEFAULT_SAFE_REST_DISTANCE = 0.30
_DEFAULT_NO_TELEPORT_TOLERANCE = 1.0e-9


class TerrainHazardInterpretationV1(str, Enum):
    """Current source-linked terrain hazard interpretation."""

    CLIFF_NEAR = "cliff_near"
    ROUTE_BLOCKED = "route_blocked"
    CLEAR = "clear"
    UNKNOWN = "unknown"


class TerrainRouteRelationV1(str, Enum):
    """Current SELF relation to the overlapping route-sheet sequence."""

    DEPARTING_CLIFF = "departing_cliff"
    OVERLAP_TRANSITION = "overlap_transition"
    APPROACHING_SHELTER = "approaching_shelter"
    SHELTER_REACHED = "shelter_reached"
    UNKNOWN = "unknown"


class TerrainLandmarkObservabilityV1(str, Enum):
    """Why current exact shared-landmark localization is or is not available."""

    OBSERVED = "observed"
    OCCLUDED = "occluded"
    UNAVAILABLE = "unavailable"
    AMBIGUOUS = "ambiguous"
    NEGATIVE_EXPECTED_LOCATION = "negative_expected_location"


class TerrainLandmarkTrackStatusV1(str, Enum):
    """Bounded active landmark-track lifecycle independent of identity."""

    ACTIVE = "active"
    COASTING = "coasting"
    UNLOCALIZED = "unlocalized"
    LOST = "lost"
    AMBIGUOUS = "ambiguous"
    UNINITIALIZED = "uninitialized"


class TerrainLandmarkReacquisitionV1(str, Enum):
    """How current landmark evidence relates to the preceding track."""

    INITIAL_ACQUISITION = "initial_acquisition"
    CONTINUING_TRACK = "continuing_track"
    REACQUIRED = "reacquired"
    NOT_OBSERVED = "not_observed"
    AMBIGUOUS = "ambiguous"
    NEGATIVE_EVIDENCE = "negative_evidence"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float while rejecting bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _finite_non_negative_float(value: Any, *, field_name: str) -> float:
    """Return one finite non-negative float."""
    number = _finite_float(value, field_name=field_name)
    if number < 0.0:
        raise ValueError(f"{field_name} must be non-negative")
    return number


def _unit_interval(value: Any, *, field_name: str) -> float:
    """Return one finite value in the closed unit interval."""
    number = _finite_float(value, field_name=field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the exact immutable reference of one NavMap revision."""
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _optional_ref_dict(value: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return one JSON-safe optional NavMap reference."""
    return value.as_dict() if value is not None else None


def _point_dict(value: Optional[NavPointV1]) -> Optional[dict[str, float]]:
    """Return one JSON-safe optional point."""
    return value.as_dict() if value is not None else None


def _optional_point(value: Any) -> Optional[NavPointV1]:
    """Decode one finite ``{x, y}`` point or return ``None``."""
    if not isinstance(value, dict):
        return None
    x_value = value.get("x")
    y_value = value.get("y")
    if isinstance(x_value, bool) or not isinstance(x_value, (int, float)):
        return None
    if isinstance(y_value, bool) or not isinstance(y_value, (int, float)):
        return None
    try:
        return NavPointV1(float(x_value), float(y_value))
    except (TypeError, ValueError):
        return None


def _controller_step(ctx: Any) -> int:
    """Return a defensive non-negative controller-step value."""
    try:
        return max(0, int(getattr(ctx, "controller_steps", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _history_limit(ctx: Any, field_name: str) -> int:
    """Return one configured positive bounded-history limit."""
    try:
        value = int(getattr(ctx, field_name, _DEFAULT_HISTORY_LIMIT) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_history(ctx: Any, *, field_name: str, limit_field_name: str, row: dict[str, Any]) -> None:
    """Append one defensive JSON-safe row to a bounded context history."""
    raw = getattr(ctx, field_name, [])
    clean = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    clean.append(dict(row))
    setattr(ctx, field_name, clean[-_history_limit(ctx, limit_field_name):])


@dataclass(frozen=True, slots=True)
class TerrainLandmarkContinuityV1:
    """One bounded identity/localization state for the shared route landmark."""

    observation_no: int
    identity_handle: str
    identity_retained: bool
    observability: TerrainLandmarkObservabilityV1
    current_location_world: Optional[NavPointV1]
    last_supported_location_world: Optional[NavPointV1]
    track_status: TerrainLandmarkTrackStatusV1
    missing_age_observations: int
    negative_evidence_reliable: bool
    reacquisition: TerrainLandmarkReacquisitionV1
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        _require_nonempty_text(self.identity_handle, field_name="identity_handle")
        if not isinstance(self.identity_retained, bool):
            raise TypeError("identity_retained must be bool")
        if not isinstance(self.observability, TerrainLandmarkObservabilityV1):
            raise TypeError("observability must be TerrainLandmarkObservabilityV1")
        for field_name in ("current_location_world", "last_supported_location_world"):
            point = getattr(self, field_name)
            if point is not None and not isinstance(point, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        if not isinstance(self.track_status, TerrainLandmarkTrackStatusV1):
            raise TypeError("track_status must be TerrainLandmarkTrackStatusV1")
        _require_non_negative_int(self.missing_age_observations, field_name="missing_age_observations")
        if not isinstance(self.negative_evidence_reliable, bool):
            raise TypeError("negative_evidence_reliable must be bool")
        if not isinstance(self.reacquisition, TerrainLandmarkReacquisitionV1):
            raise TypeError("reacquisition must be TerrainLandmarkReacquisitionV1")
        _require_nonempty_text(self.reason, field_name="reason")
        if self.track_status is TerrainLandmarkTrackStatusV1.ACTIVE:
            if self.current_location_world is None:
                raise ValueError("ACTIVE landmark track requires current exact location")
            if self.observability is not TerrainLandmarkObservabilityV1.OBSERVED:
                raise ValueError("ACTIVE landmark track requires observed evidence")
        elif self.current_location_world is not None:
            raise ValueError("non-active landmark track cannot expose current exact location")
        if self.negative_evidence_reliable:
            if self.observability is not TerrainLandmarkObservabilityV1.NEGATIVE_EXPECTED_LOCATION:
                raise ValueError("reliable negative evidence requires NEGATIVE_EXPECTED_LOCATION")

    @property
    def correspondence_supported(self) -> bool:
        """Return whether landmark continuity may support a route-sheet handoff."""
        if not self.identity_retained or self.negative_evidence_reliable:
            return False
        return self.track_status in {
            TerrainLandmarkTrackStatusV1.ACTIVE,
            TerrainLandmarkTrackStatusV1.COASTING,
        }

    @property
    def correspondence_support(self) -> float:
        """Return transparent engineering support for a route-sheet handoff."""
        if self.track_status is TerrainLandmarkTrackStatusV1.ACTIVE:
            return 1.0
        if self.track_status is TerrainLandmarkTrackStatusV1.COASTING and self.identity_retained:
            return 0.70
        return 0.0

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe continuity and permanence record."""
        return {
            "schema": "terrain_landmark_continuity_v1",
            "phase": "6",
            "observation_no": self.observation_no,
            "identity_handle": self.identity_handle,
            "identity_retained": self.identity_retained,
            "observability": self.observability.value,
            "current_location_world": _point_dict(self.current_location_world),
            "last_supported_location_world": _point_dict(self.last_supported_location_world),
            "track_status": self.track_status.value,
            "missing_age_observations": self.missing_age_observations,
            "negative_evidence_reliable": self.negative_evidence_reliable,
            "reacquisition": self.reacquisition.value,
            "correspondence_supported": self.correspondence_supported,
            "correspondence_support": self.correspondence_support,
            "lost_track_deletes_identity": False,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TerrainDynamicOverlayV1:
    """Compact live SELF/vegetation/material-event state outside immutable maps."""

    observation_no: int
    source_packet_ref: str
    self_world_point: Optional[NavPointV1]
    self_west_local_point: Optional[NavPointV1]
    self_east_local_point: Optional[NavPointV1]
    position_label: str
    stage: str
    current_evidence_supported: bool
    vegetation_branch_offset: Optional[float]
    vegetation_motion_dynamic_only: bool
    tree_fallen: bool
    route_structure_materially_changed: bool
    backtrack_requested: bool
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("source_packet_ref", "position_label", "stage", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in ("self_world_point", "self_west_local_point", "self_east_local_point"):
            point = getattr(self, field_name)
            if point is not None and not isinstance(point, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        for field_name in (
            "current_evidence_supported",
            "vegetation_motion_dynamic_only",
            "tree_fallen",
            "route_structure_materially_changed",
            "backtrack_requested",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if self.vegetation_branch_offset is not None:
            object.__setattr__(
                self,
                "vegetation_branch_offset",
                _finite_float(self.vegetation_branch_offset, field_name="vegetation_branch_offset"),
            )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe compact dynamic overlay."""
        return {
            "schema": "terrain_dynamic_overlay_v1",
            "phase": "6",
            "observation_no": self.observation_no,
            "source_packet_ref": self.source_packet_ref,
            "self_world_point": _point_dict(self.self_world_point),
            "self_west_local_point": _point_dict(self.self_west_local_point),
            "self_east_local_point": _point_dict(self.self_east_local_point),
            "position_label": self.position_label,
            "stage": self.stage,
            "current_evidence_supported": self.current_evidence_supported,
            "vegetation_branch_offset": self.vegetation_branch_offset,
            "vegetation_motion_dynamic_only": self.vegetation_motion_dynamic_only,
            "vegetation_created_navmap_revision": False,
            "tree_fallen": self.tree_fallen,
            "route_structure_materially_changed": self.route_structure_materially_changed,
            "backtrack_requested": self.backtrack_requested,
            "stores_full_navmap_history": False,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TerrainRouteCorrespondenceV1:
    """Explicit shared-landmark/frame/SELF evidence for one lateral handoff."""

    observation_no: int
    source_map_ref: NavMapRefV1
    destination_map_ref: NavMapRefV1
    source_frame_id: str
    destination_frame_id: str
    identity_handle: str
    shared_landmark_element_id: str
    source_landmark_local: NavPointV1
    destination_landmark_local: NavPointV1
    self_world_point: NavPointV1
    self_source_local: NavPointV1
    self_destination_local: NavPointV1
    translation_x: float
    translation_y: float
    rotation_degrees: float
    scale: float
    self_continuity_error: float
    landmark_continuity_error: float
    support: float
    ambiguous: bool
    no_teleport_discontinuity: bool
    source_and_destination_overlap: bool
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("source_map_ref", "destination_map_ref"):
            if not isinstance(getattr(self, field_name), NavMapRefV1):
                raise TypeError(f"{field_name} must be NavMapRefV1")
        for field_name in (
            "source_frame_id",
            "destination_frame_id",
            "identity_handle",
            "shared_landmark_element_id",
            "reason",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in (
            "source_landmark_local",
            "destination_landmark_local",
            "self_world_point",
            "self_source_local",
            "self_destination_local",
        ):
            if not isinstance(getattr(self, field_name), NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1")
        for field_name in (
            "translation_x",
            "translation_y",
            "rotation_degrees",
            "scale",
            "self_continuity_error",
            "landmark_continuity_error",
        ):
            number = _finite_float(getattr(self, field_name), field_name=field_name)
            if field_name in {"scale", "self_continuity_error", "landmark_continuity_error"} and number < 0.0:
                raise ValueError(f"{field_name} must be non-negative")
            object.__setattr__(self, field_name, number)
        if self.scale <= 0.0:
            raise ValueError("scale must be positive")
        object.__setattr__(self, "support", _unit_interval(self.support, field_name="support"))
        for field_name in ("ambiguous", "no_teleport_discontinuity", "source_and_destination_overlap"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")

    @property
    def can_commit(self) -> bool:
        """Return whether the explicit lateral correspondence is safe to commit."""
        return bool(
            not self.ambiguous
            and self.support > 0.0
            and self.no_teleport_discontinuity
            and self.source_and_destination_overlap
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe lateral-transition trace."""
        return {
            "schema": "terrain_route_correspondence_v1",
            "phase": "6",
            "observation_no": self.observation_no,
            "source_map_ref": self.source_map_ref.as_dict(),
            "destination_map_ref": self.destination_map_ref.as_dict(),
            "source_frame_id": self.source_frame_id,
            "destination_frame_id": self.destination_frame_id,
            "identity_handle": self.identity_handle,
            "shared_landmark_element_id": self.shared_landmark_element_id,
            "source_landmark_local": self.source_landmark_local.as_dict(),
            "destination_landmark_local": self.destination_landmark_local.as_dict(),
            "self_world_point": self.self_world_point.as_dict(),
            "self_source_local": self.self_source_local.as_dict(),
            "self_destination_local": self.self_destination_local.as_dict(),
            "transform": {
                "translation_x": self.translation_x,
                "translation_y": self.translation_y,
                "rotation_degrees": self.rotation_degrees,
                "scale": self.scale,
            },
            "self_continuity_error": self.self_continuity_error,
            "landmark_continuity_error": self.landmark_continuity_error,
            "support": self.support,
            "ambiguous": self.ambiguous,
            "no_teleport_discontinuity": self.no_teleport_discontinuity,
            "source_and_destination_overlap": self.source_and_destination_overlap,
            "can_commit": self.can_commit,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TerrainPolicyReadoutV1:
    """Source-linked route/hazard readouts derived from the operative terrain WNM."""

    observation_no: int
    operative_map_ref: Optional[NavMapRefV1]
    operative_role: Optional[str]
    source_grid_sig16: Optional[str]
    source_frame_id: Optional[str]
    current_evidence_supported: bool
    freshness: str
    cliff_near: Optional[bool]
    safe_to_rest: Optional[bool]
    route_clear: Optional[bool]
    motion_veto: Optional[bool]
    route_relation: TerrainRouteRelationV1
    hazard_interpretation: TerrainHazardInterpretationV1
    hazard_distance: Optional[float]
    shelter_distance: Optional[float]
    tree_blocking_route: Optional[bool]
    derivation_operator: str
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.operative_map_ref is not None and not isinstance(self.operative_map_ref, NavMapRefV1):
            raise TypeError("operative_map_ref must be NavMapRefV1 or None")
        for field_name in ("operative_role", "source_grid_sig16", "source_frame_id"):
            value = getattr(self, field_name)
            if value is not None:
                _require_nonempty_text(value, field_name=field_name)
        if not isinstance(self.current_evidence_supported, bool):
            raise TypeError("current_evidence_supported must be bool")
        for field_name in ("freshness", "derivation_operator", "reason"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in ("cliff_near", "safe_to_rest", "route_clear", "motion_veto", "tree_blocking_route"):
            value = getattr(self, field_name)
            if value is not None and not isinstance(value, bool):
                raise TypeError(f"{field_name} must be bool or None")
        if not isinstance(self.route_relation, TerrainRouteRelationV1):
            raise TypeError("route_relation must be TerrainRouteRelationV1")
        if not isinstance(self.hazard_interpretation, TerrainHazardInterpretationV1):
            raise TypeError("hazard_interpretation must be TerrainHazardInterpretationV1")
        for field_name in ("hazard_distance", "shelter_distance"):
            value = getattr(self, field_name)
            if value is not None:
                object.__setattr__(
                    self,
                    field_name,
                    _finite_non_negative_float(value, field_name=field_name),
                )
        if not self.current_evidence_supported:
            if any(
                value is not None
                for value in (self.cliff_near, self.safe_to_rest, self.route_clear, self.motion_veto)
            ):
                raise ValueError("unsupported current evidence must preserve UNKNOWN policy booleans")

    @property
    def operative_terrain_authority(self) -> bool:
        """Return whether the readout came from a currently operative route map."""
        return bool(
            self.operative_map_ref is not None
            and self.operative_role in {_WEST_ROLE, _EAST_ROLE}
            and self.current_evidence_supported
        )

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe source/threshold/safety contract."""
        return {
            "schema": "terrain_policy_readout_v1",
            "phase": "6",
            "observation_no": self.observation_no,
            "operative_map_ref": _optional_ref_dict(self.operative_map_ref),
            "operative_role": self.operative_role,
            "source_grid_sig16": self.source_grid_sig16,
            "source_frame_id": self.source_frame_id,
            "current_evidence_supported": self.current_evidence_supported,
            "operative_terrain_authority": self.operative_terrain_authority,
            "freshness": self.freshness,
            "cliff_near": self.cliff_near,
            "safe_to_rest": self.safe_to_rest,
            "route_clear": self.route_clear,
            "motion_veto": self.motion_veto,
            "route_relation": self.route_relation.value,
            "hazard_interpretation": self.hazard_interpretation.value,
            "hazard_distance": self.hazard_distance,
            "shelter_distance": self.shelter_distance,
            "tree_blocking_route": self.tree_blocking_route,
            "derivation_operator": self.derivation_operator,
            "thresholds": {
                "cliff_near_distance": _DEFAULT_CLIFF_NEAR_DISTANCE,
                "safe_rest_distance": _DEFAULT_SAFE_REST_DISTANCE,
            },
            "source_linked": True,
            "protected_safety_can_be_weakened": False,
            "map_may_add_protected_veto": self.motion_veto is True or self.safe_to_rest is False,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class TerrainWnmStateV1:
    """One complete Phase 6 terrain/WNM observation transaction."""

    observation_no: int
    west_route_map_ref: NavMapRefV1
    east_route_map_ref: NavMapRefV1
    operative_route_map_ref: Optional[NavMapRefV1]
    operative_role: Optional[str]
    route_claims_wnm: bool
    transition_attempted: bool
    transition_accepted: bool
    landmark_continuity: TerrainLandmarkContinuityV1
    lateral_correspondence: Optional[TerrainRouteCorrespondenceV1]
    dynamic_overlay: TerrainDynamicOverlayV1
    policy_readout: TerrainPolicyReadoutV1
    wnm_surfacegrid_sig16: Optional[str]
    surfacegrid_comparison: dict[str, Any]
    material_revision: dict[str, Any]

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("west_route_map_ref", "east_route_map_ref"):
            if not isinstance(getattr(self, field_name), NavMapRefV1):
                raise TypeError(f"{field_name} must be NavMapRefV1")
        if self.operative_route_map_ref is not None and not isinstance(self.operative_route_map_ref, NavMapRefV1):
            raise TypeError("operative_route_map_ref must be NavMapRefV1 or None")
        if self.operative_role is not None:
            _require_nonempty_text(self.operative_role, field_name="operative_role")
        for field_name in ("route_claims_wnm", "transition_attempted", "transition_accepted"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if not isinstance(self.landmark_continuity, TerrainLandmarkContinuityV1):
            raise TypeError("landmark_continuity must be TerrainLandmarkContinuityV1")
        if self.lateral_correspondence is not None and not isinstance(
            self.lateral_correspondence,
            TerrainRouteCorrespondenceV1,
        ):
            raise TypeError("lateral_correspondence must be TerrainRouteCorrespondenceV1 or None")
        if not isinstance(self.dynamic_overlay, TerrainDynamicOverlayV1):
            raise TypeError("dynamic_overlay must be TerrainDynamicOverlayV1")
        if not isinstance(self.policy_readout, TerrainPolicyReadoutV1):
            raise TypeError("policy_readout must be TerrainPolicyReadoutV1")
        if self.wnm_surfacegrid_sig16 is not None:
            _require_nonempty_text(self.wnm_surfacegrid_sig16, field_name="wnm_surfacegrid_sig16")
        if not isinstance(self.surfacegrid_comparison, dict):
            raise TypeError("surfacegrid_comparison must be dict")
        if not isinstance(self.material_revision, dict):
            raise TypeError("material_revision must be dict")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe Phase 6 route, revision, and safety trace."""
        return {
            "schema": "terrain_wnm_state_v1",
            "phase": "6",
            "authority": "single_operative_wnm_terrain_domain",
            "one_operative_wnm": True,
            "ready_set_has_equal_authority": False,
            "global_single_winner_unchanged": True,
            "policy_selection_mutation_allowed": False,
            "protected_safety_can_be_overridden": False,
            "legacy_surfacegrid_replaced": False,
            "observation_no": self.observation_no,
            "west_route_map_ref": self.west_route_map_ref.as_dict(),
            "east_route_map_ref": self.east_route_map_ref.as_dict(),
            "operative_route_map_ref": _optional_ref_dict(self.operative_route_map_ref),
            "operative_role": self.operative_role,
            "route_claims_wnm": self.route_claims_wnm,
            "transition_attempted": self.transition_attempted,
            "transition_accepted": self.transition_accepted,
            "landmark_continuity": self.landmark_continuity.as_dict(),
            "lateral_correspondence": (
                self.lateral_correspondence.as_dict() if self.lateral_correspondence is not None else None
            ),
            "dynamic_overlay": self.dynamic_overlay.as_dict(),
            "policy_readout": self.policy_readout.as_dict(),
            "wnm_surfacegrid_sig16": self.wnm_surfacegrid_sig16,
            "surfacegrid_comparison": dict(self.surfacegrid_comparison),
            "material_revision": dict(self.material_revision),
        }


@dataclass(frozen=True, slots=True)
class _TerrainEvidenceV1:
    """Internal validated terrain evidence packet decoded from EnvObservation."""

    observation_no: int
    source_ref: str
    stage: str
    position_label: str
    posture_standing: bool
    self_world_point: Optional[NavPointV1]
    landmark_identity_handle: str
    landmark_observability: TerrainLandmarkObservabilityV1
    landmark_world_point: Optional[NavPointV1]
    landmark_identity_ambiguous: bool
    landmark_negative_evidence: bool
    tree_fallen: bool
    vegetation_branch_offset: Optional[float]
    route_correspondence_ambiguous: bool
    backtrack_requested: bool
    blackout_active: bool
    quality: float

    def __post_init__(self) -> None:
        _require_positive_int(self.observation_no, field_name="observation_no")
        for field_name in ("source_ref", "stage", "position_label", "landmark_identity_handle"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.posture_standing, bool):
            raise TypeError("posture_standing must be bool")
        for field_name in ("self_world_point", "landmark_world_point"):
            point = getattr(self, field_name)
            if point is not None and not isinstance(point, NavPointV1):
                raise TypeError(f"{field_name} must be NavPointV1 or None")
        if not isinstance(self.landmark_observability, TerrainLandmarkObservabilityV1):
            raise TypeError("landmark_observability must be TerrainLandmarkObservabilityV1")
        for field_name in (
            "landmark_identity_ambiguous",
            "landmark_negative_evidence",
            "tree_fallen",
            "route_correspondence_ambiguous",
            "backtrack_requested",
            "blackout_active",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if self.vegetation_branch_offset is not None:
            object.__setattr__(
                self,
                "vegetation_branch_offset",
                _finite_float(self.vegetation_branch_offset, field_name="vegetation_branch_offset"),
            )
        object.__setattr__(self, "quality", _unit_interval(self.quality, field_name="quality"))

    @property
    def current_structure_supported(self) -> bool:
        """Return whether current SELF/terrain evidence supports projection."""
        return bool(not self.blackout_active and self.self_world_point is not None)

    @property
    def route_task_active(self) -> bool:
        """Return whether route cognition should own the WNM this observation."""
        return bool(
            self.posture_standing
            and self.stage in {"first_stand", "struggle"}
            and self.position_label in {"cliff_edge", "open_field"}
        )


def _decode_observability(value: Any, *, negative: bool, ambiguous: bool) -> TerrainLandmarkObservabilityV1:
    """Return one explicit landmark observability enum from adapter metadata."""
    if negative:
        return TerrainLandmarkObservabilityV1.NEGATIVE_EXPECTED_LOCATION
    if ambiguous:
        return TerrainLandmarkObservabilityV1.AMBIGUOUS
    raw = str(value or "unavailable").strip().lower()
    aliases = {
        "observed": TerrainLandmarkObservabilityV1.OBSERVED,
        "occluded": TerrainLandmarkObservabilityV1.OCCLUDED,
        "known_occluded": TerrainLandmarkObservabilityV1.OCCLUDED,
        "unavailable": TerrainLandmarkObservabilityV1.UNAVAILABLE,
        "missing": TerrainLandmarkObservabilityV1.UNAVAILABLE,
        "ambiguous": TerrainLandmarkObservabilityV1.AMBIGUOUS,
        "negative_expected_location": TerrainLandmarkObservabilityV1.NEGATIVE_EXPECTED_LOCATION,
    }
    return aliases.get(raw, TerrainLandmarkObservabilityV1.UNAVAILABLE)


def _decode_evidence(ctx: Any, env_obs: EnvObservation) -> tuple[Optional[_TerrainEvidenceV1], str]:
    """Decode one bounded Phase 6 terrain packet or return a dependency reason."""
    if not isinstance(env_obs, EnvObservation):
        return None, "env_observation_unavailable"
    meta = env_obs.env_meta if isinstance(env_obs.env_meta, dict) else {}
    packet = meta.get("terrain_geometry_v1")
    if not isinstance(packet, dict) or packet.get("schema") != "terrain_geometry_v1":
        return None, "terrain_geometry_packet_unavailable"

    try:
        current = int(getattr(ctx, "terrain_observation_no_v1", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    observation_no = max(0, current) + 1
    ctx.terrain_observation_no_v1 = observation_no

    negative = bool(packet.get("landmark_negative_evidence", False))
    ambiguous_identity = bool(packet.get("landmark_identity_ambiguous", False))
    observability = _decode_observability(
        packet.get("landmark_observability"),
        negative=negative,
        ambiguous=ambiguous_identity,
    )
    predicates = env_obs.predicates if isinstance(env_obs.predicates, list) else []
    source_ref = str(packet.get("source_ref") or f"adapter:terrain_geometry_v1:o{observation_no}")
    stage = str(packet.get("stage") or meta.get("scenario_stage") or "unknown")
    position_label = str(packet.get("position_label") or meta.get("position") or "unknown")
    identity_handle = str(packet.get("landmark_identity_handle") or _LANDMARK_IDENTITY)
    quality_raw = packet.get("quality", 0.85)
    try:
        quality = _unit_interval(quality_raw, field_name="terrain quality")
    except (TypeError, ValueError):
        quality = 0.50
    branch_raw = packet.get("vegetation_branch_offset")
    branch_offset: Optional[float] = None
    if isinstance(branch_raw, (int, float)) and not isinstance(branch_raw, bool):
        number = float(branch_raw)
        if math.isfinite(number):
            branch_offset = number

    evidence = _TerrainEvidenceV1(
        observation_no=observation_no,
        source_ref=source_ref,
        stage=stage,
        position_label=position_label,
        posture_standing="posture:standing" in predicates,
        self_world_point=_optional_point(packet.get("self_world_point")),
        landmark_identity_handle=identity_handle,
        landmark_observability=observability,
        landmark_world_point=_optional_point(packet.get("landmark_world_point")),
        landmark_identity_ambiguous=ambiguous_identity,
        landmark_negative_evidence=negative,
        tree_fallen=bool(packet.get("tree_fallen", False)),
        vegetation_branch_offset=branch_offset,
        route_correspondence_ambiguous=bool(packet.get("route_correspondence_ambiguous", False)),
        backtrack_requested=bool(packet.get("backtrack_requested", False)),
        blackout_active=bool(packet.get("blackout_active", False)),
        quality=quality,
    )
    return evidence, "available"


def _world_to_west(point: NavPointV1) -> NavPointV1:
    """Transform one world point into the west route-sheet frame."""
    return NavPointV1(point.x - _WEST_ORIGIN_WORLD_X, point.y)


def _world_to_east(point: NavPointV1) -> NavPointV1:
    """Transform one world point into the east route-sheet frame."""
    return NavPointV1(point.x - _EAST_ORIGIN_WORLD_X, point.y)


def _west_to_world(point: NavPointV1) -> NavPointV1:
    """Transform one west-sheet point into the common world frame."""
    return NavPointV1(point.x + _WEST_ORIGIN_WORLD_X, point.y)


def _east_to_world(point: NavPointV1) -> NavPointV1:
    """Transform one east-sheet point into the common world frame."""
    return NavPointV1(point.x + _EAST_ORIGIN_WORLD_X, point.y)


def _route_provenance(source_ref: str, *, quality: float = 0.85) -> NavProvenanceV1:
    """Return inferred provenance for one maintained terrain structure."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=source_ref,
        quality=quality,
    )


def _observed_provenance(source_ref: str, *, quality: float) -> NavProvenanceV1:
    """Return observed provenance for one current terrain contribution."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.OBSERVED,
        source_ref=source_ref,
        quality=quality,
    )


def _activation(name: str, provenance: NavProvenanceV1) -> tuple[NavActivationV1, ...]:
    """Return one concise decoded activation tuple."""
    return (NavActivationV1(name=name, strength=1.0, provenance=provenance),)


def _element(
    element_id: str,
    role: str,
    kind: NavGeometryKindV1,
    points: tuple[NavPointV1, ...],
    provenance: NavProvenanceV1,
    *,
    activation: str,
) -> NavElementV1:
    """Build one deterministic terrain element."""
    return NavElementV1(
        element_id=element_id,
        role=role,
        geometry=NavGeometryV1(kind=kind, points=points),
        activations=_activation(activation, provenance),
        parent_element_id=None,
        provenance=provenance,
    )


def _west_frame() -> NavFrameV1:
    """Return the first overlapping TripTik route-sheet frame."""
    return NavFrameV1(
        frame_id=_WEST_FRAME_ID,
        x_axis="route_progress_east",
        y_axis="route_lateral_north",
        units="simulated_distance_units",
        min_x=-0.50,
        max_x=1.10,
        min_y=-1.00,
        max_y=1.00,
    )


def _east_frame() -> NavFrameV1:
    """Return the second overlapping TripTik route-sheet frame."""
    return NavFrameV1(
        frame_id=_EAST_FRAME_ID,
        x_axis="route_progress_east",
        y_axis="route_lateral_north",
        units="simulated_distance_units",
        min_x=-0.20,
        max_x=1.10,
        min_y=-1.00,
        max_y=1.00,
    )


def _build_west_map(evidence: _TerrainEvidenceV1) -> NavMapV2:
    """Build the stable cliff-to-overlap route sheet."""
    provenance = _route_provenance("runtime:phase6_west_route_structure_v1")
    observed = _observed_provenance(evidence.source_ref, quality=evidence.quality)
    elements = (
        _element(
            _ROUTE_ELEMENT,
            "traversable_route_corridor",
            NavGeometryKindV1.POLYLINE,
            (NavPointV1(-0.10, 0.0), NavPointV1(0.45, 0.0), NavPointV1(1.00, 0.0)),
            provenance,
            activation="terrain_traversable",
        ),
        _element(
            _CLIFF_ELEMENT,
            "hazard_boundary",
            NavGeometryKindV1.SEGMENT,
            (NavPointV1(-0.25, -0.80), NavPointV1(-0.25, 0.80)),
            observed,
            activation="hazard_cliff_boundary",
        ),
        _element(
            _LANDMARK_ELEMENT,
            "stationary_shared_landmark",
            NavGeometryKindV1.POINT,
            (_world_to_west(_SHARED_LANDMARK_WORLD),),
            provenance,
            activation="route_shared_anchor",
        ),
        _element(
            _OVERLAP_ELEMENT,
            "route_sheet_overlap",
            NavGeometryKindV1.SEGMENT,
            (NavPointV1(_OVERLAP_WORLD_MIN_X, 0.0), NavPointV1(_OVERLAP_WORLD_MAX_X, 0.0)),
            provenance,
            activation="route_overlap_supported",
        ),
    )
    relations = (
        NavRelationV1("anchors_route_sheet", _LANDMARK_ELEMENT, _ROUTE_ELEMENT, provenance),
        NavRelationV1("route_leads_to_overlap", _ROUTE_ELEMENT, _OVERLAP_ELEMENT, provenance),
        NavRelationV1("hazard_borders_route", _CLIFF_ELEMENT, _ROUTE_ELEMENT, observed),
    )
    return NavMapV2(
        map_id=_WEST_MAP_ID,
        revision=1,
        role=_WEST_ROLE,
        frame=_west_frame(),
        provenance=provenance,
        elements=elements,
        relations=relations,
    )


def _build_east_map(evidence: _TerrainEvidenceV1, *, revision: int) -> NavMapV2:
    """Build the overlap-to-shelter route sheet, optionally with a fallen tree."""
    provenance = _route_provenance("runtime:phase6_east_route_structure_v1")
    observed = _observed_provenance(evidence.source_ref, quality=evidence.quality)
    elements: list[NavElementV1] = [
        _element(
            _ROUTE_ELEMENT,
            "traversable_route_corridor",
            NavGeometryKindV1.POLYLINE,
            (NavPointV1(-0.10, 0.0), NavPointV1(0.40, 0.0), NavPointV1(0.95, 0.0)),
            provenance,
            activation="terrain_traversable",
        ),
        _element(
            _LANDMARK_ELEMENT,
            "stationary_shared_landmark",
            NavGeometryKindV1.POINT,
            (_world_to_east(_SHARED_LANDMARK_WORLD),),
            provenance,
            activation="route_shared_anchor",
        ),
        _element(
            _OVERLAP_ELEMENT,
            "route_sheet_overlap",
            NavGeometryKindV1.SEGMENT,
            (
                NavPointV1(_OVERLAP_WORLD_MIN_X - _EAST_ORIGIN_WORLD_X, 0.0),
                NavPointV1(_OVERLAP_WORLD_MAX_X - _EAST_ORIGIN_WORLD_X, 0.0),
            ),
            provenance,
            activation="route_overlap_supported",
        ),
        _element(
            _SHELTER_ELEMENT,
            "safe_rest_goal",
            NavGeometryKindV1.POINT,
            (NavPointV1(_SHELTER_WORLD_X - _EAST_ORIGIN_WORLD_X, 0.0),),
            provenance,
            activation="shelter_goal",
        ),
    ]
    relations: list[NavRelationV1] = [
        NavRelationV1("anchors_route_sheet", _LANDMARK_ELEMENT, _ROUTE_ELEMENT, provenance),
        NavRelationV1("route_starts_in_overlap", _OVERLAP_ELEMENT, _ROUTE_ELEMENT, provenance),
        NavRelationV1("route_leads_to_shelter", _ROUTE_ELEMENT, _SHELTER_ELEMENT, provenance),
    ]
    if evidence.tree_fallen or revision > 1:
        elements.append(
            _element(
                _TREE_ELEMENT,
                "material_route_obstacle",
                NavGeometryKindV1.SEGMENT,
                (
                    NavPointV1(_TREE_WORLD_X - _EAST_ORIGIN_WORLD_X, -0.35),
                    NavPointV1(_TREE_WORLD_X - _EAST_ORIGIN_WORLD_X, 0.35),
                ),
                observed,
                activation="route_blocked_fallen_tree",
            )
        )
        relations.append(NavRelationV1("blocks_route", _TREE_ELEMENT, _ROUTE_ELEMENT, observed))
    return NavMapV2(
        map_id=_EAST_MAP_ID,
        revision=revision,
        role=_EAST_ROLE,
        frame=_east_frame(),
        provenance=provenance,
        parent_ref=NavMapRefV1(_EAST_MAP_ID, revision - 1) if revision > 1 else None,
        elements=tuple(elements),
        relations=tuple(relations),
    )


def _maintain_route_maps(
    ctx: Any,
    evidence: _TerrainEvidenceV1,
) -> tuple[NavMapV2, NavMapV2, dict[str, Any]]:
    """Maintain route-map families and revise only one material tree event."""
    west_raw = getattr(ctx, "terrain_route_west_map_v1", None)
    west = west_raw if isinstance(west_raw, NavMapV2) else _build_west_map(evidence)

    east_raw = getattr(ctx, "terrain_route_east_map_v1", None)
    prior_east = east_raw if isinstance(east_raw, NavMapV2) else None
    desired_revision = 2 if evidence.tree_fallen else 1
    if prior_east is not None and prior_east.revision > desired_revision:
        desired_revision = prior_east.revision
    if prior_east is None or prior_east.revision != desired_revision:
        east = _build_east_map(evidence, revision=desired_revision)
    else:
        east = prior_east

    west_created = not isinstance(west_raw, NavMapV2)
    east_created = prior_east is None
    material_changed = bool(prior_east is not None and prior_east.revision == 1 and east.revision == 2)
    revision_row = {
        "schema": "terrain_material_revision_v1",
        "phase": "6",
        "observation_no": evidence.observation_no,
        "status": "revised" if material_changed else ("created" if west_created or east_created else "unchanged"),
        "reason": "fallen_tree_changed_traversability" if material_changed else "no_material_route_change",
        "affected_map_ref": _map_ref(east).as_dict() if material_changed else None,
        "old_east_ref": _map_ref(prior_east).as_dict() if prior_east is not None else None,
        "new_east_ref": _map_ref(east).as_dict(),
        "west_ref": _map_ref(west).as_dict(),
        "west_signature_unchanged": (
            isinstance(west_raw, NavMapV2) and west_raw.content_signature() == west.content_signature()
        ),
        "vegetation_motion_created_revision": False,
        "creates_revision": material_changed,
    }
    ctx.terrain_route_west_map_v1 = west
    ctx.terrain_route_east_map_v1 = east
    ctx.terrain_last_material_revision_v1 = dict(revision_row)
    if material_changed:
        _append_history(
            ctx,
            field_name="terrain_material_revision_history_v1",
            limit_field_name="terrain_material_revision_history_limit_v1",
            row=revision_row,
        )
    return west, east, revision_row


def _update_landmark_continuity(
    ctx: Any,
    evidence: _TerrainEvidenceV1,
) -> TerrainLandmarkContinuityV1:
    """Update bounded stationary-landmark permanence without fabricating location."""
    previous_raw = getattr(ctx, "terrain_landmark_continuity_v1", None)
    previous = previous_raw if isinstance(previous_raw, TerrainLandmarkContinuityV1) else None
    previous_age = previous.missing_age_observations if previous is not None else 0
    last_location = previous.last_supported_location_world if previous is not None else None
    identity_retained = evidence.landmark_identity_handle == _LANDMARK_IDENTITY

    if evidence.landmark_observability is TerrainLandmarkObservabilityV1.OBSERVED:
        current = evidence.landmark_world_point
        if current is None:
            observability = TerrainLandmarkObservabilityV1.UNAVAILABLE
        else:
            observability = TerrainLandmarkObservabilityV1.OBSERVED
        if current is not None and identity_retained:
            if previous is None:
                reacquisition = TerrainLandmarkReacquisitionV1.INITIAL_ACQUISITION
            elif previous.track_status is TerrainLandmarkTrackStatusV1.ACTIVE:
                reacquisition = TerrainLandmarkReacquisitionV1.CONTINUING_TRACK
            else:
                reacquisition = TerrainLandmarkReacquisitionV1.REACQUIRED
            state = TerrainLandmarkContinuityV1(
                observation_no=evidence.observation_no,
                identity_handle=_LANDMARK_IDENTITY,
                identity_retained=True,
                observability=observability,
                current_location_world=current,
                last_supported_location_world=current,
                track_status=TerrainLandmarkTrackStatusV1.ACTIVE,
                missing_age_observations=0,
                negative_evidence_reliable=False,
                reacquisition=reacquisition,
                reason="stationary_landmark_currently_observed",
            )
            ctx.terrain_landmark_continuity_v1 = state
            return state

    if evidence.landmark_observability is TerrainLandmarkObservabilityV1.AMBIGUOUS:
        state = TerrainLandmarkContinuityV1(
            observation_no=evidence.observation_no,
            identity_handle=_LANDMARK_IDENTITY,
            identity_retained=bool(previous is not None and previous.identity_retained),
            observability=TerrainLandmarkObservabilityV1.AMBIGUOUS,
            current_location_world=None,
            last_supported_location_world=last_location,
            track_status=TerrainLandmarkTrackStatusV1.AMBIGUOUS,
            missing_age_observations=previous_age + 1,
            negative_evidence_reliable=False,
            reacquisition=TerrainLandmarkReacquisitionV1.AMBIGUOUS,
            reason="landmark_correspondence_ambiguous",
        )
        ctx.terrain_landmark_continuity_v1 = state
        return state

    if evidence.landmark_observability is TerrainLandmarkObservabilityV1.NEGATIVE_EXPECTED_LOCATION:
        state = TerrainLandmarkContinuityV1(
            observation_no=evidence.observation_no,
            identity_handle=_LANDMARK_IDENTITY,
            identity_retained=bool(previous is not None and previous.identity_retained),
            observability=TerrainLandmarkObservabilityV1.NEGATIVE_EXPECTED_LOCATION,
            current_location_world=None,
            last_supported_location_world=last_location,
            track_status=TerrainLandmarkTrackStatusV1.LOST,
            missing_age_observations=previous_age + 1,
            negative_evidence_reliable=True,
            reacquisition=TerrainLandmarkReacquisitionV1.NEGATIVE_EVIDENCE,
            reason="reliable_negative_evidence_at_expected_landmark_location",
        )
        ctx.terrain_landmark_continuity_v1 = state
        return state

    effective_observability = evidence.landmark_observability
    if (
        effective_observability is TerrainLandmarkObservabilityV1.OBSERVED
        and evidence.landmark_world_point is None
    ):
        effective_observability = TerrainLandmarkObservabilityV1.UNAVAILABLE

    age = previous_age + 1
    if effective_observability is TerrainLandmarkObservabilityV1.OCCLUDED and previous is not None:
        status = TerrainLandmarkTrackStatusV1.COASTING
        reason = "known_occluder_retains_landmark_identity_and_last_supported_location"
    elif previous is None:
        status = TerrainLandmarkTrackStatusV1.UNINITIALIZED
        reason = "landmark_never_supported"
    elif age <= 1:
        status = TerrainLandmarkTrackStatusV1.COASTING
        reason = "brief_missing_landmark_packet"
    elif age == 2:
        status = TerrainLandmarkTrackStatusV1.UNLOCALIZED
        reason = "landmark_exact_localization_unlocalized"
    else:
        status = TerrainLandmarkTrackStatusV1.LOST
        reason = "landmark_track_lost_identity_retained"

    state = TerrainLandmarkContinuityV1(
        observation_no=evidence.observation_no,
        identity_handle=_LANDMARK_IDENTITY,
        identity_retained=bool(previous is not None and previous.identity_retained),
        observability=effective_observability,
        current_location_world=None,
        last_supported_location_world=last_location,
        track_status=status,
        missing_age_observations=age,
        negative_evidence_reliable=False,
        reacquisition=TerrainLandmarkReacquisitionV1.NOT_OBSERVED,
        reason=reason,
    )
    ctx.terrain_landmark_continuity_v1 = state
    return state


def _route_correspondence(
    evidence: _TerrainEvidenceV1,
    west: NavMapV2,
    east: NavMapV2,
    continuity: TerrainLandmarkContinuityV1,
    *,
    reverse: bool = False,
) -> Optional[TerrainRouteCorrespondenceV1]:
    """Build explicit west/east lateral correspondence from shared anchors."""
    self_world = evidence.self_world_point
    if self_world is None:
        return None
    west_self = _world_to_west(self_world)
    east_self = _world_to_east(self_world)
    west_landmark = _world_to_west(_SHARED_LANDMARK_WORLD)
    east_landmark = _world_to_east(_SHARED_LANDMARK_WORLD)

    west_self_world = _west_to_world(west_self)
    east_self_world = _east_to_world(east_self)
    west_landmark_world = _west_to_world(west_landmark)
    east_landmark_world = _east_to_world(east_landmark)
    self_error = math.hypot(west_self_world.x - east_self_world.x, west_self_world.y - east_self_world.y)
    landmark_error = math.hypot(
        west_landmark_world.x - east_landmark_world.x,
        west_landmark_world.y - east_landmark_world.y,
    )
    no_teleport = bool(
        self_error <= _DEFAULT_NO_TELEPORT_TOLERANCE
        and landmark_error <= _DEFAULT_NO_TELEPORT_TOLERANCE
    )
    overlap = bool(
        _OVERLAP_WORLD_MIN_X <= self_world.x <= _OVERLAP_WORLD_MAX_X
        and west.frame.contains(west_self)
        and east.frame.contains(east_self)
    )
    ambiguous = bool(
        evidence.route_correspondence_ambiguous
        or evidence.landmark_identity_ambiguous
        or continuity.track_status is TerrainLandmarkTrackStatusV1.AMBIGUOUS
        or continuity.negative_evidence_reliable
    )
    support = min(continuity.correspondence_support, evidence.quality) if overlap and no_teleport else 0.0
    source = east if reverse else west
    destination = west if reverse else east
    source_landmark = east_landmark if reverse else west_landmark
    destination_landmark = west_landmark if reverse else east_landmark
    source_self = east_self if reverse else west_self
    destination_self = west_self if reverse else east_self
    translation_x = _EAST_ORIGIN_WORLD_X - _WEST_ORIGIN_WORLD_X
    if reverse:
        translation_x = -translation_x
    reason = "shared_stationary_landmark_and_explicit_frame_transform"
    if ambiguous:
        reason = "route_correspondence_ambiguous_or_negative"
    elif not overlap:
        reason = "self_not_in_route_sheet_overlap"
    elif not no_teleport:
        reason = "self_or_landmark_transform_discontinuity"
    elif support <= 0.0:
        reason = "landmark_continuity_unsupported"
    return TerrainRouteCorrespondenceV1(
        observation_no=evidence.observation_no,
        source_map_ref=_map_ref(source),
        destination_map_ref=_map_ref(destination),
        source_frame_id=source.frame.frame_id,
        destination_frame_id=destination.frame.frame_id,
        identity_handle=_SELF_IDENTITY,
        shared_landmark_element_id=_LANDMARK_ELEMENT,
        source_landmark_local=source_landmark,
        destination_landmark_local=destination_landmark,
        self_world_point=self_world,
        self_source_local=source_self,
        self_destination_local=destination_self,
        translation_x=translation_x,
        translation_y=0.0,
        rotation_degrees=0.0,
        scale=1.0,
        self_continuity_error=self_error,
        landmark_continuity_error=landmark_error,
        support=support,
        ambiguous=ambiguous,
        no_teleport_discontinuity=no_teleport,
        source_and_destination_overlap=overlap,
        reason=reason,
    )


def _transition_accepted_this_observation(ctx: Any, observation_no: int) -> bool:
    """Return whether the most recent WNM transition committed this observation."""
    record = getattr(ctx, "wnm_last_transition_v1", None)
    return bool(
        isinstance(record, WNMTransitionRecordV1)
        and record.observation_no == observation_no
        and record.accepted
    )


def _ready_map_by_role(ctx: Any, role: str) -> Optional[NavMapV2]:
    """Return one ready map by role without changing authority."""
    for navmap in reversed(wnm_ready_maps_v1(ctx)):
        if navmap.role == role:
            return navmap
    return None


def _overview_map(ctx: Any) -> Optional[NavMapV2]:
    """Return the current/ready Phase 4/5 SELF-maternal overview map."""
    operative = wnm_operative_map_v1(ctx)
    if operative is not None and operative.role == _OVERVIEW_ROLE:
        return operative
    ready = _ready_map_by_role(ctx, _OVERVIEW_ROLE)
    if ready is not None:
        return ready
    value = getattr(ctx, "feeding_overview_map_v1", None)
    return value if isinstance(value, NavMapV2) else None


def _commit_route_transition(
    ctx: Any,
    destination: NavMapV2,
    *,
    transition_type: WNMTransitionTypeV1,
    evidence: _TerrainEvidenceV1,
    reason: str,
    support: float,
    ambiguous: bool,
    correspondence_basis: str,
) -> dict[str, Any]:
    """Commit one route transition through the generic atomic WNM runtime."""
    source = wnm_operative_map_v1(ctx)
    return wnm_commit_transition_v1(
        ctx,
        destination,
        transition_type=transition_type,
        observation_no=evidence.observation_no,
        reason=reason,
        identity_handle=_SELF_IDENTITY,
        correspondence_basis=correspondence_basis,
        support=support,
        correspondence_ambiguous=ambiguous,
        expected_source_ref=_map_ref(source) if source is not None else None,
    )


def _route_transition_step(
    ctx: Any,
    evidence: _TerrainEvidenceV1,
    west: NavMapV2,
    east: NavMapV2,
    continuity: TerrainLandmarkContinuityV1,
) -> tuple[bool, Optional[TerrainRouteCorrespondenceV1]]:
    """Attempt at most one route acquisition/lateral/return/backtrack transition."""
    operative = wnm_operative_map_v1(ctx)
    if operative is None:
        ctx.terrain_route_claims_wnm_v1 = False
        return False, None

    operative_route = operative.role in {_WEST_ROLE, _EAST_ROLE}
    route_claims = bool(evidence.route_task_active or operative_route or evidence.backtrack_requested)
    ctx.terrain_route_claims_wnm_v1 = route_claims
    if not route_claims:
        return False, None

    # If feeding detail happened to remain operative while a route task begins,
    # first return to the overview; route acquisition can occur on the next cycle.
    if evidence.route_task_active and operative.role not in {_OVERVIEW_ROLE, _WEST_ROLE, _EAST_ROLE}:
        overview = _overview_map(ctx)
        if overview is not None and any(item.map_id == overview.map_id for item in wnm_ready_maps_v1(ctx)):
            wnm_return_to_ref_v1(
                ctx,
                _map_ref(overview),
                observation_no=evidence.observation_no,
                reason="phase6_route_task_return_to_overview_before_lateral_navigation",
                identity_handle=_SELF_IDENTITY,
                correspondence_basis="self_identity_preserved_across_ready_overview_return",
                support=1.0,
            )
            return True, None
        return False, None

    if evidence.route_task_active and operative.role == _OVERVIEW_ROLE:
        support = evidence.quality if evidence.current_structure_supported else 0.0
        _commit_route_transition(
            ctx,
            west,
            transition_type=WNMTransitionTypeV1.ZOOM_IN,
            evidence=evidence,
            reason="phase6_enter_cliff_to_field_route_sheet",
            support=support,
            ambiguous=evidence.route_correspondence_ambiguous,
            correspondence_basis="self_world_position_to_west_route_frame",
        )
        return True, None

    if operative.role == _WEST_ROLE and evidence.backtrack_requested:
        return False, None

    if operative.role == _WEST_ROLE and evidence.route_task_active and evidence.position_label == "open_field":
        correspondence = _route_correspondence(evidence, west, east, continuity)
        if correspondence is None:
            return False, None
        _commit_route_transition(
            ctx,
            east,
            transition_type=WNMTransitionTypeV1.LATERAL_SHIFT,
            evidence=evidence,
            reason="phase6_lateral_shift_west_to_east_route_sheet",
            support=correspondence.support,
            ambiguous=correspondence.ambiguous,
            correspondence_basis=(
                "shared_landmark_explicit_translation_self_continuity:"
                f"self_error={correspondence.self_continuity_error:.12f}:"
                f"landmark_error={correspondence.landmark_continuity_error:.12f}"
            ),
        )
        return True, correspondence

    if operative.role == _EAST_ROLE and evidence.backtrack_requested:
        west_ready = _ready_map_by_role(ctx, _WEST_ROLE)
        correspondence = _route_correspondence(evidence, west, east, continuity, reverse=True)
        if west_ready is None or correspondence is None:
            return False, correspondence
        wnm_return_to_ref_v1(
            ctx,
            _map_ref(west_ready),
            observation_no=evidence.observation_no,
            reason="phase6_backtrack_east_to_west_route_sheet",
            identity_handle=_SELF_IDENTITY,
            correspondence_basis=(
                "shared_landmark_reverse_transform_self_continuity:"
                f"self_error={correspondence.self_continuity_error:.12f}"
            ),
            support=correspondence.support,
            correspondence_ambiguous=correspondence.ambiguous,
        )
        return True, correspondence

    route_complete = bool(
        operative_route
        and (
            evidence.position_label == "shelter_area"
            or evidence.stage in {"first_latch", "rest"}
        )
    )
    if route_complete:
        overview = _overview_map(ctx)
        if overview is not None and any(item.map_id == overview.map_id for item in wnm_ready_maps_v1(ctx)):
            wnm_return_to_ref_v1(
                ctx,
                _map_ref(overview),
                observation_no=evidence.observation_no,
                reason="phase6_route_complete_return_to_self_maternal_overview",
                identity_handle=_SELF_IDENTITY,
                correspondence_basis="self_identity_and_world_position_preserved_on_route_return",
                support=1.0 if evidence.current_structure_supported else 0.0,
            )
            return True, None
    return False, None


def _grid_dimensions(ctx: Any) -> tuple[int, int, float]:
    """Return bounded deterministic Phase 6 grid dimensions and scale."""
    try:
        width = int(getattr(ctx, "terrain_surfacegrid_w_v1", _DEFAULT_GRID_W) or 0)
    except (TypeError, ValueError):
        width = _DEFAULT_GRID_W
    try:
        height = int(getattr(ctx, "terrain_surfacegrid_h_v1", _DEFAULT_GRID_H) or 0)
    except (TypeError, ValueError):
        height = _DEFAULT_GRID_H
    try:
        scale = float(getattr(ctx, "terrain_surfacegrid_cells_per_unit_v1", _DEFAULT_CELLS_PER_UNIT))
    except (TypeError, ValueError):
        scale = _DEFAULT_CELLS_PER_UNIT
    width = max(5, min(64, width))
    height = max(5, min(64, height))
    if not math.isfinite(scale) or scale <= 0.0:
        scale = _DEFAULT_CELLS_PER_UNIT
    return width, height, scale


def _cell_priority(value: int) -> int:
    """Return conservative overlay priority for one SurfaceGrid cell code."""
    return {
        CELL_UNKNOWN: 0,
        CELL_TRAVERSABLE: 1,
        CELL_GOAL: 2,
        CELL_HAZARD: 3,
        CELL_BLOCKED: 4,
    }.get(value, -1)

#pylint: disable=too-many-positional-arguments
def _set_cell(cells: list[int], width: int, height: int, x: int, y: int, value: int) -> None:
    """Safely overlay one cell using conservative hazard priority."""
    if not 0 <= x < width or not 0 <= y < height:
        return
    index = y * width + x
    if _cell_priority(value) > _cell_priority(cells[index]):
        cells[index] = value


def _local_to_cell(
    point: NavPointV1,
    self_local: NavPointV1,
    *,
    width: int,
    height: int,
    scale: float,
) -> tuple[int, int]:
    """Project one route-sheet point into a SELF-centered SurfaceGrid cell."""
    center_x = width // 2
    center_y = height // 2
    dx = point.x - self_local.x
    dy = point.y - self_local.y
    return center_x + int(round(dx * scale)), center_y - int(round(dy * scale))


def _paint_point(
    cells: list[int],
    width: int,
    height: int,
    x: int,
    y: int,
    value: int,
    *,
    radius: int = 0,
) -> None:
    """Paint one small square footprint around a projected point."""
    for yy in range(y - radius, y + radius + 1):
        for xx in range(x - radius, x + radius + 1):
            _set_cell(cells, width, height, xx, yy, value)

#pylint: enable=too-many-positional-arguments
def _sample_segment(start: NavPointV1, end: NavPointV1, *, step: float = 0.05) -> tuple[NavPointV1, ...]:
    """Return deterministic samples along one finite segment."""
    length = math.hypot(end.x - start.x, end.y - start.y)
    count = max(1, int(math.ceil(length / max(step, 1.0e-6))))
    return tuple(
        NavPointV1(
            start.x + (end.x - start.x) * (index / count),
            start.y + (end.y - start.y) * (index / count),
        )
        for index in range(count + 1)
    )


def _geometry_samples(element: NavElementV1) -> tuple[NavPointV1, ...]:
    """Return deterministic projection samples for one route-map element."""
    points = element.geometry.points
    if element.geometry.kind is NavGeometryKindV1.POINT:
        return points
    samples: list[NavPointV1] = []
    for index in range(len(points) - 1):
        samples.extend(_sample_segment(points[index], points[index + 1]))
    return tuple(samples)


def _project_operative_route_grid(
    ctx: Any,
    evidence: _TerrainEvidenceV1,
    overlay: TerrainDynamicOverlayV1,
) -> tuple[Optional[SurfaceGridV1], dict[str, Any]]:
    """Project only the operative route WNM plus current SELF overlay into a grid."""
    operative = wnm_operative_map_v1(ctx)
    if operative is None or operative.role not in {_WEST_ROLE, _EAST_ROLE}:
        return None, {
            "schema": "terrain_surfacegrid_summary_v1",
            "phase": "6",
            "status": "terrain_route_not_operative",
            "legacy_surfacegrid_replaced": False,
        }
    if not evidence.current_structure_supported:
        width, height, _scale = _grid_dimensions(ctx)
        grid = SurfaceGridV1(width, height, [CELL_UNKNOWN] * (width * height))
        return grid, {
            "schema": "terrain_surfacegrid_summary_v1",
            "phase": "6",
            "status": "current_evidence_unknown",
            "source_map_ref": _map_ref(operative).as_dict(),
            "grid_sig16": grid.sig16_v1(),
            "legacy_surfacegrid_replaced": False,
            "unknown_preserved": True,
        }

    self_local = overlay.self_west_local_point if operative.role == _WEST_ROLE else overlay.self_east_local_point
    if self_local is None:
        return None, {
            "schema": "terrain_surfacegrid_summary_v1",
            "phase": "6",
            "status": "self_localization_unavailable",
            "source_map_ref": _map_ref(operative).as_dict(),
            "legacy_surfacegrid_replaced": False,
        }

    width, height, scale = _grid_dimensions(ctx)
    cells = [CELL_UNKNOWN] * (width * height)
    for element in operative.elements:
        if element.element_id == _ROUTE_ELEMENT:
            cell_value = CELL_TRAVERSABLE
            radius = 1
        elif element.element_id == _CLIFF_ELEMENT:
            cell_value = CELL_HAZARD
            radius = 0
        elif element.element_id == _SHELTER_ELEMENT:
            cell_value = CELL_GOAL
            radius = 0
        elif element.element_id == _TREE_ELEMENT:
            cell_value = CELL_BLOCKED
            radius = 0
        else:
            continue
        for point in _geometry_samples(element):
            x_cell, y_cell = _local_to_cell(
                point,
                self_local,
                width=width,
                height=height,
                scale=scale,
            )
            _paint_point(cells, width, height, x_cell, y_cell, cell_value, radius=radius)

    center_x = width // 2
    center_y = height // 2
    _set_cell(cells, width, height, center_x, center_y, CELL_TRAVERSABLE)
    grid = SurfaceGridV1(width, height, cells)
    slots = derive_grid_slot_families_v1(grid, self_xy=(center_x, center_y), r=2)
    navsummary = compute_navsummary_v1(grid, slots=slots, self_xy=(center_x, center_y), local_radius=2)
    summary = {
        "schema": "terrain_surfacegrid_summary_v1",
        "phase": "6",
        "status": "active",
        "source_map_ref": _map_ref(operative).as_dict(),
        "source_role": operative.role,
        "source_frame_id": operative.frame.frame_id,
        "projection_operator": "operative_route_navmap_to_self_centered_surfacegrid_v1",
        "grid_sig16": grid.sig16_v1(),
        "grid_w": width,
        "grid_h": height,
        "cells_per_unit": scale,
        "slots": dict(slots),
        "navsummary": dict(navsummary),
        "legacy_surfacegrid_replaced": False,
        "current_evidence_supported": True,
    }
    return grid, summary


def _compare_surfacegrids(ctx: Any, wnm_grid: Optional[SurfaceGridV1]) -> dict[str, Any]:
    """Compare the WNM-derived grid with the existing legacy grid in dual-run."""
    if wnm_grid is None:
        return {
            "schema": "terrain_surfacegrid_dual_run_v1",
            "phase": "6",
            "status": "wnm_grid_unavailable",
            "legacy_surfacegrid_replaced": False,
        }
    legacy_raw = getattr(ctx, "wm_surfacegrid", None)
    legacy = legacy_raw if isinstance(legacy_raw, SurfaceGridV1) else None
    wnm_slots = derive_grid_slot_families_v1(wnm_grid, r=2)
    if legacy is None:
        return {
            "schema": "terrain_surfacegrid_dual_run_v1",
            "phase": "6",
            "status": "legacy_grid_unavailable",
            "wnm_grid_sig16": wnm_grid.sig16_v1(),
            "wnm_slots": dict(wnm_slots),
            "legacy_surfacegrid_replaced": False,
        }
    legacy_slots = derive_grid_slot_families_v1(legacy, r=2)
    comparable_shape = bool(legacy.grid_w == wnm_grid.grid_w and legacy.grid_h == wnm_grid.grid_h)
    overlap = (
        grid_overlap_fraction_v1(wnm_grid.grid_cells, legacy.grid_cells)
        if comparable_shape
        else None
    )
    hazard_agreement = wnm_slots.get("hazard:near") == legacy_slots.get("hazard:near")
    traversable_agreement = (
        wnm_slots.get("terrain:traversable_near") == legacy_slots.get("terrain:traversable_near")
    )
    return {
        "schema": "terrain_surfacegrid_dual_run_v1",
        "phase": "6",
        "status": "compared",
        "wnm_grid_sig16": wnm_grid.sig16_v1(),
        "legacy_grid_sig16": legacy.sig16_v1(),
        "comparable_shape": comparable_shape,
        "grid_overlap_fraction": overlap,
        "wnm_slots": dict(wnm_slots),
        "legacy_slots": dict(legacy_slots),
        "hazard_near_agreement": hazard_agreement,
        "traversable_near_agreement": traversable_agreement,
        "legacy_surfacegrid_replaced": False,
        "behavioral_authority": "wnm_may_add_safety_veto_legacy_remains_protected",
    }


def _forward_route_clear(grid: SurfaceGridV1) -> bool:
    """Return whether a short eastward route from SELF is visible and unblocked."""
    width = grid.grid_w
    height = grid.grid_h
    center_x = width // 2
    center_y = height // 2
    traversable_seen = False
    for x_cell in range(center_x, min(width, center_x + 5)):
        for y_cell in range(max(0, center_y - 1), min(height, center_y + 2)):
            value = grid.grid_cells[y_cell * width + x_cell]
            if value in {CELL_HAZARD, CELL_BLOCKED}:
                return False
            if value in {CELL_TRAVERSABLE, CELL_GOAL}:
                traversable_seen = True
    return traversable_seen


def _route_relation(self_world: NavPointV1) -> TerrainRouteRelationV1:
    """Return a transparent route relation from current world-coordinate geometry."""
    if self_world.x <= 0.30:
        return TerrainRouteRelationV1.DEPARTING_CLIFF
    if self_world.x <= _OVERLAP_WORLD_MAX_X:
        return TerrainRouteRelationV1.OVERLAP_TRANSITION
    if self_world.x < _SHELTER_WORLD_X - _DEFAULT_SAFE_REST_DISTANCE:
        return TerrainRouteRelationV1.APPROACHING_SHELTER
    return TerrainRouteRelationV1.SHELTER_REACHED


def _derive_policy_readout(
    ctx: Any,
    evidence: _TerrainEvidenceV1,
    overlay: TerrainDynamicOverlayV1,
    grid: Optional[SurfaceGridV1],
) -> TerrainPolicyReadoutV1:
    """Derive source-linked cliff/rest/route/hazard values from operative terrain."""
    operative = wnm_operative_map_v1(ctx)
    route_operative = operative is not None and operative.role in {_WEST_ROLE, _EAST_ROLE}
    operative_ref = _map_ref(operative) if route_operative and operative is not None else None
    operative_role = operative.role if route_operative and operative is not None else None
    frame_id = operative.frame.frame_id if route_operative and operative is not None else None

    if not route_operative or not evidence.current_structure_supported or overlay.self_world_point is None or grid is None:
        return TerrainPolicyReadoutV1(
            observation_no=evidence.observation_no,
            operative_map_ref=operative_ref,
            operative_role=operative_role,
            source_grid_sig16=grid.sig16_v1() if grid is not None else None,
            source_frame_id=frame_id,
            current_evidence_supported=False,
            freshness="unknown",
            cliff_near=None,
            safe_to_rest=None,
            route_clear=None,
            motion_veto=None,
            route_relation=TerrainRouteRelationV1.UNKNOWN,
            hazard_interpretation=TerrainHazardInterpretationV1.UNKNOWN,
            hazard_distance=None,
            shelter_distance=None,
            tree_blocking_route=None,
            derivation_operator="operative_route_geometry_query_v1",
            reason="operative_route_or_current_self_evidence_unavailable",
        )

    self_world = overlay.self_world_point
    cliff_distance = abs(self_world.x - _CLIFF_WORLD_X)
    shelter_distance = abs(self_world.x - _SHELTER_WORLD_X)
    cliff_near = cliff_distance <= _DEFAULT_CLIFF_NEAR_DISTANCE
    route_clear = _forward_route_clear(grid)
    tree_blocking = bool(overlay.tree_fallen and not route_clear)
    safe_to_rest = bool(
        shelter_distance <= _DEFAULT_SAFE_REST_DISTANCE
        and not cliff_near
        and route_clear
        and not tree_blocking
    )
    motion_veto = bool(not route_clear or tree_blocking)
    if tree_blocking:
        hazard = TerrainHazardInterpretationV1.ROUTE_BLOCKED
    elif cliff_near:
        hazard = TerrainHazardInterpretationV1.CLIFF_NEAR
    elif route_clear:
        hazard = TerrainHazardInterpretationV1.CLEAR
    else:
        hazard = TerrainHazardInterpretationV1.UNKNOWN
    return TerrainPolicyReadoutV1(
        observation_no=evidence.observation_no,
        operative_map_ref=operative_ref,
        operative_role=operative_role,
        source_grid_sig16=grid.sig16_v1(),
        source_frame_id=frame_id,
        current_evidence_supported=True,
        freshness="fresh",
        cliff_near=cliff_near,
        safe_to_rest=safe_to_rest,
        route_clear=route_clear,
        motion_veto=motion_veto,
        route_relation=_route_relation(self_world),
        hazard_interpretation=hazard,
        hazard_distance=cliff_distance,
        shelter_distance=shelter_distance,
        tree_blocking_route=tree_blocking,
        derivation_operator="operative_route_navmap_plus_live_self_overlay_v1",
        reason="source_linked_policy_readout_from_current_operative_route_wnm",
    )


def _dynamic_overlay(
    evidence: _TerrainEvidenceV1,
    *,
    material_changed: bool,
) -> TerrainDynamicOverlayV1:
    """Build one compact live overlay without creating a map movie."""
    self_world = evidence.self_world_point
    return TerrainDynamicOverlayV1(
        observation_no=evidence.observation_no,
        source_packet_ref=evidence.source_ref,
        self_world_point=self_world,
        self_west_local_point=_world_to_west(self_world) if self_world is not None else None,
        self_east_local_point=_world_to_east(self_world) if self_world is not None else None,
        position_label=evidence.position_label,
        stage=evidence.stage,
        current_evidence_supported=evidence.current_structure_supported,
        vegetation_branch_offset=evidence.vegetation_branch_offset,
        vegetation_motion_dynamic_only=True,
        tree_fallen=evidence.tree_fallen,
        route_structure_materially_changed=material_changed,
        backtrack_requested=evidence.backtrack_requested,
        reason=(
            "fallen_tree_material_revision"
            if material_changed
            else "self_and_periodic_vegetation_updated_in_live_overlay"
        ),
    )


def terrain_reset_v1(ctx: Any) -> None:
    """Clear episode-local Phase 6 terrain registers without touching WNM itself."""
    if ctx is None:
        return
    ctx.terrain_observation_no_v1 = 0
    ctx.terrain_route_west_map_v1 = None
    ctx.terrain_route_east_map_v1 = None
    ctx.terrain_state_v1 = None
    ctx.terrain_landmark_continuity_v1 = None
    ctx.terrain_dynamic_overlay_v1 = None
    ctx.terrain_policy_readout_v1 = None
    ctx.terrain_surfacegrid_v1 = None
    ctx.terrain_surfacegrid_summary_v1 = {}
    ctx.terrain_surfacegrid_comparison_v1 = {}
    ctx.terrain_last_material_revision_v1 = {}
    ctx.terrain_last_update_v1 = {}
    ctx.terrain_history_v1 = []
    ctx.terrain_material_revision_history_v1 = []
    ctx.terrain_route_claims_wnm_v1 = False


def terrain_wnm_observation_step_v1(ctx: Any, env_obs: EnvObservation) -> dict[str, Any]:
    """Process one terrain observation and attempt at most one WNM transition.

    The function runs after Phase 4 maternal processing and before Phase 5
    feeding transition logic.  It may claim the WNM for an active route task,
    but it does not select or execute a behavioral primitive.
    """
    if ctx is None:
        return {"schema": "terrain_summary_v1", "phase": "6", "status": "ctx_unavailable"}
    ctx.terrain_route_claims_wnm_v1 = False
    if not bool(getattr(ctx, "terrain_wnm_enabled_v1", True)):
        ctx.terrain_state_v1 = None
        ctx.terrain_policy_readout_v1 = None
        ctx.terrain_surfacegrid_v1 = None
        ctx.terrain_last_update_v1 = {
            "schema": "terrain_summary_v1",
            "phase": "6",
            "status": "disabled",
            "authority": "single_operative_wnm_terrain_domain",
            "protected_safety_can_be_overridden": False,
        }
        return dict(ctx.terrain_last_update_v1)

    evidence, dependency_reason = _decode_evidence(ctx, env_obs)
    if evidence is None:
        ctx.terrain_state_v1 = None
        ctx.terrain_policy_readout_v1 = None
        ctx.terrain_surfacegrid_v1 = None
        ctx.terrain_last_update_v1 = {
            "schema": "terrain_summary_v1",
            "phase": "6",
            "status": "dependency_error",
            "authority": "single_operative_wnm_terrain_domain",
            "reason": dependency_reason,
            "protected_safety_can_be_overridden": False,
        }
        return dict(ctx.terrain_last_update_v1)

    west, east, revision_row = _maintain_route_maps(ctx, evidence)
    material_changed = revision_row.get("status") == "revised"
    continuity = _update_landmark_continuity(ctx, evidence)
    overlay = _dynamic_overlay(evidence, material_changed=material_changed)
    ctx.terrain_dynamic_overlay_v1 = overlay

    # Refresh a newer material revision in whichever activation tier already owns
    # that family.  This is not a lateral transition.
    wnm_refresh_map_v1(
        ctx,
        west,
        observation_no=evidence.observation_no,
        reason="phase6_refresh_west_route_family_without_role_change",
    )
    wnm_refresh_map_v1(
        ctx,
        east,
        observation_no=evidence.observation_no,
        reason="phase6_refresh_east_route_family_after_materiality_check",
    )

    transition_attempted, correspondence = _route_transition_step(
        ctx,
        evidence,
        west,
        east,
        continuity,
    )
    transition_accepted = _transition_accepted_this_observation(ctx, evidence.observation_no)

    grid, grid_summary = _project_operative_route_grid(ctx, evidence, overlay)
    comparison = _compare_surfacegrids(ctx, grid)
    readout = _derive_policy_readout(ctx, evidence, overlay, grid)
    ctx.terrain_surfacegrid_v1 = grid
    ctx.terrain_surfacegrid_summary_v1 = dict(grid_summary)
    ctx.terrain_surfacegrid_comparison_v1 = dict(comparison)
    ctx.terrain_policy_readout_v1 = readout

    operative = wnm_operative_map_v1(ctx)
    operative_route_ref = (
        _map_ref(operative)
        if operative is not None and operative.role in {_WEST_ROLE, _EAST_ROLE}
        else None
    )
    state = TerrainWnmStateV1(
        observation_no=evidence.observation_no,
        west_route_map_ref=_map_ref(west),
        east_route_map_ref=_map_ref(east),
        operative_route_map_ref=operative_route_ref,
        operative_role=operative.role if operative is not None else None,
        route_claims_wnm=bool(getattr(ctx, "terrain_route_claims_wnm_v1", False)),
        transition_attempted=transition_attempted,
        transition_accepted=transition_accepted,
        landmark_continuity=continuity,
        lateral_correspondence=correspondence,
        dynamic_overlay=overlay,
        policy_readout=readout,
        wnm_surfacegrid_sig16=grid.sig16_v1() if grid is not None else None,
        surfacegrid_comparison=comparison,
        material_revision=revision_row,
    )
    ctx.terrain_state_v1 = state
    row = state.as_dict()
    ctx.terrain_last_update_v1 = dict(row)
    _append_history(
        ctx,
        field_name="terrain_history_v1",
        limit_field_name="terrain_history_limit_v1",
        row=row,
    )
    return terrain_summary_v1(ctx)


def terrain_policy_readout_v1(ctx: Any) -> Optional[TerrainPolicyReadoutV1]:
    """Return the current typed terrain policy readout when available."""
    value = getattr(ctx, "terrain_policy_readout_v1", None) if ctx is not None else None
    return value if isinstance(value, TerrainPolicyReadoutV1) else None


def terrain_motion_veto_v1(ctx: Any) -> Optional[bool]:
    """Return a current operative-terrain motion veto or ``None`` for fallback."""
    readout = terrain_policy_readout_v1(ctx)
    if readout is None or not readout.operative_terrain_authority:
        return None
    return readout.motion_veto


def terrain_safe_to_rest_v1(ctx: Any) -> Optional[bool]:
    """Return current operative-terrain safe-to-rest or ``None`` for fallback."""
    readout = terrain_policy_readout_v1(ctx)
    if readout is None or not readout.operative_terrain_authority:
        return None
    return readout.safe_to_rest


def terrain_cliff_near_v1(ctx: Any) -> Optional[bool]:
    """Return current operative-terrain cliff proximity or ``None`` for fallback."""
    readout = terrain_policy_readout_v1(ctx)
    if readout is None or not readout.operative_terrain_authority:
        return None
    return readout.cliff_near


def terrain_route_clear_v1(ctx: Any) -> Optional[bool]:
    """Return current operative-terrain route clearance or ``None`` for fallback."""
    readout = terrain_policy_readout_v1(ctx)
    if readout is None or not readout.operative_terrain_authority:
        return None
    return readout.route_clear


def terrain_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe Phase 6 terrain/WNM summary."""
    if ctx is None:
        return {"schema": "terrain_summary_v1", "phase": "6", "status": "ctx_unavailable"}
    state = getattr(ctx, "terrain_state_v1", None)
    last_update = getattr(ctx, "terrain_last_update_v1", None)
    if not isinstance(state, TerrainWnmStateV1) and isinstance(last_update, dict):
        status = last_update.get("status")
        if status in {"disabled", "dependency_error", "error"}:
            out = dict(last_update)
            out.setdefault("schema", "terrain_summary_v1")
            out.setdefault("phase", "6")
            out.setdefault("authority", "single_operative_wnm_terrain_domain")
            out["wnm"] = wnm_summary_v1(ctx)
            return out
    surfacegrid = getattr(ctx, "terrain_surfacegrid_v1", None)
    return {
        "schema": "terrain_summary_v1",
        "phase": "6",
        "status": "active" if isinstance(state, TerrainWnmStateV1) else "idle",
        "authority": "single_operative_wnm_terrain_domain",
        "policy_selection_mutation_allowed": False,
        "protected_safety_can_be_overridden": False,
        "legacy_surfacegrid_replaced": False,
        "state": state.as_dict() if isinstance(state, TerrainWnmStateV1) else None,
        "policy_readout": (
            state.policy_readout.as_dict() if isinstance(state, TerrainWnmStateV1) else None
        ),
        "wnm_surfacegrid": (
            surfacegrid.to_dict()
            if isinstance(surfacegrid, SurfaceGridV1)
            else None
        ),
        "surfacegrid_summary": dict(getattr(ctx, "terrain_surfacegrid_summary_v1", {}) or {}),
        "surfacegrid_comparison": dict(getattr(ctx, "terrain_surfacegrid_comparison_v1", {}) or {}),
        "wnm": wnm_summary_v1(ctx),
        "history_count": len(getattr(ctx, "terrain_history_v1", []) or []),
        "material_revision_count": len(getattr(ctx, "terrain_material_revision_history_v1", []) or []),
    }


def _ref_text(value: Any) -> str:
    """Return compact text for one optional map reference dictionary."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id')}@r{value.get('revision')}"


def render_terrain_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 6 route/safety/dual-run lines."""
    summary = terrain_summary_v1(ctx)
    lines = ["PHASE 6 TERRAIN / LATERAL ROUTE WNM:"]
    if summary.get("status") != "active":
        lines.append(
            "  "
            f"status={summary.get('status')} protected_safety_can_be_overridden=False "
            "legacy_surfacegrid_replaced=False"
        )
        return lines
    state = summary.get("state")
    state = state if isinstance(state, dict) else {}
    readout = state.get("policy_readout")
    readout = readout if isinstance(readout, dict) else {}
    landmark = state.get("landmark_continuity")
    landmark = landmark if isinstance(landmark, dict) else {}
    correspondence = state.get("lateral_correspondence")
    correspondence = correspondence if isinstance(correspondence, dict) else {}
    revision = state.get("material_revision")
    revision = revision if isinstance(revision, dict) else {}
    comparison = state.get("surfacegrid_comparison")
    comparison = comparison if isinstance(comparison, dict) else {}
    lines.append(
        "  "
        f"operative={state.get('operative_role')} map={_ref_text(state.get('operative_route_map_ref'))} "
        f"route_claims_wnm={state.get('route_claims_wnm')} ready_has_equal_authority=False"
    )
    lines.append(
        "  "
        f"route={readout.get('route_relation')} clear={readout.get('route_clear')} "
        f"cliff_near={readout.get('cliff_near')} hazard={readout.get('hazard_interpretation')} "
        f"safe_to_rest={readout.get('safe_to_rest')} motion_veto={readout.get('motion_veto')}"
    )
    lines.append(
        "  "
        f"landmark={landmark.get('track_status')} observability={landmark.get('observability')} "
        f"identity_retained={landmark.get('identity_retained')} reacquisition={landmark.get('reacquisition')}"
    )
    lines.append(
        "  "
        f"lateral_support={correspondence.get('support')} overlap={correspondence.get('source_and_destination_overlap')} "
        f"no_teleport={correspondence.get('no_teleport_discontinuity')} "
        f"transition_attempted={state.get('transition_attempted')} accepted={state.get('transition_accepted')}"
    )
    lines.append(
        "  "
        f"grid_dual_run={comparison.get('status')} overlap_fraction={comparison.get('grid_overlap_fraction')} "
        f"legacy_replaced={comparison.get('legacy_surfacegrid_replaced')} "
        f"material_revision={revision.get('status')} reason={revision.get('reason')}"
    )
    return lines
