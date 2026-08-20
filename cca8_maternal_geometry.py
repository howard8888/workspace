# -*- coding: utf-8 -*-
"""Phase 4A SELF-maternal common-frame geometry shadow for CCA8.

Purpose
-------
Phase 4A begins the second NavMap behavioral domain by representing SELF and
one maternal individual in a shared continuous frame.  The module deliberately
stops before FollowMom authority.  It proves that CCA8 can:

* construct a transient evidence NavMap from current observed positions;
* derive SELF-maternal distance and bearing from geometry rather than from the
  symbolic ``proximity:mom:*`` predicate family;
* keep maternal identity, the non-geometric maternal role, and provenance as
  separate architectural concepts;
* maintain a stable SELF-maternal map across equivalent, changed, and missing
  observations without revision churn;
* create a root-scene shadow view that preserves the existing SELF-ground link
  and adds an addressable link to the maternal scene map; and
* compare the geometry-derived proximity with legacy BodyMap telemetry while
  leaving BodyMap and FollowMom behavior completely unchanged.

Scope boundary
--------------
This slice is shadow-only.  It does not derive approach/recession, route safety,
or reachability; those require temporal and terrain evidence in later Phase 4
slices.  It does not trigger, advise, gate, select, or execute FollowMom.  The
current ``EnvObservation`` adapter exposes simulated kid and maternal positions
in ``env_meta``.  Those values are useful engineering evidence, but they are not
yet a biological perception model.  Phase 4C adds one narrow optional identity
inspection seam: a position explicitly marked as a different or ambiguous
individual is excluded before the maternal element and caregiver relation are
constructed.  This prevents coordinate coincidence from granting maternal
identity/role while leaving ordinary Phase 4A observations unchanged.

Authority boundary
------------------
All records produced here state ``authority=shadow_only``.  The existing
BodyMap/PolicyRuntime path remains authoritative for FollowMom.  The Phase 4A
root view is a diagnostic candidate and never replaces the accepted Phase 2/3
root reference in ``ctx.navmap_v2_shadow_root``.
"""

from __future__ import annotations

# This self-contained migration slice intentionally keeps its immutable records,
# bounded maintenance transaction, root-view construction, and terminal renderer
# together so the Phase 4A authority boundary remains inspectable.
# pylint: disable=duplicate-code
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
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
    NavMapLinkV1,
    NavMapRefV1,
    NavMapV2,
    NavMatchThresholdsV1,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavRevisionDecisionV1,
    NavRevisionProposalV1,
    NavRevisionThresholdsV1,
    NavScalarQueryResultV1,
    NavSourceClassV1,
    NavStructuredResidualV1,
    apply_revision,
    bearing_between_centroids,
    centroid_distance_between,
    follow_link,
    match_navmaps,
    propose_revision,
    structured_residual,
)

__version__ = "0.2.0"

__all__ = [
    "MaternalProximityV1",
    "MaternalGeometryThresholdsV1",
    "MaternalGeometryReadoutV1",
    "MaternalGeometryShadowStateV1",
    "maternal_geometry_thresholds_v1",
    "maternal_geometry_match_thresholds_v1",
    "maternal_geometry_revision_thresholds_v1",
    "maternal_geometry_evidence_from_observation_v1",
    "maternal_geometry_readout_v1",
    "maternal_root_view_from_maps_v1",
    "maternal_geometry_shadow_observation_step_v1",
    "maternal_geometry_shadow_summary_v1",
    "render_maternal_geometry_shadow_lines_v1",
    "__version__",
]

_SELF_MATERNAL_MAP_ID = "goat_self_maternal_v2"
_EVIDENCE_MAP_ID_PREFIX = "goat_self_maternal_evidence_v2"
_ROOT_VIEW_MAP_ID = "goat_root_scene_maternal_shadow_v2"
_SELF_MATERNAL_FRAME_ID = "self_centered_maternal_frame_v1"
_ROOT_FALLBACK_FRAME_ID = "phase4a_root_view_frame_v1"
_SELF_ELEMENT_ID = "self_anchor"
_MATERNAL_ELEMENT_ID = "maternal_individual"
_ROOT_SELF_ELEMENT_ID = "self_context"
_MATERNAL_ROLE_RELATION = "maternal_caregiver_of"
_MATERNAL_LINK_TYPE = "self_maternal_submap"
_BODY_LINK_TYPE = "self_ground_submap"
_ADAPTER_SOURCE_REF = "adapter:env_observation_positions_to_self_maternal_v1"
_ROLE_SOURCE_REF = "runtime:known_maternal_role_v1"
_ROOT_VIEW_SOURCE_REF = "runtime:phase4a_maternal_root_view_v1"
_DEFAULT_MAX_MISSING_OBSERVATIONS = 2
_DEFAULT_HISTORY_LIMIT = 25


class MaternalProximityV1(str, Enum):
    """Geometry-derived SELF-maternal proximity classification."""

    TOUCHING = "touching"
    NEAR = "near"
    FAR = "far"
    UNKNOWN = "unknown"


@dataclass(frozen=True, slots=True)
class MaternalGeometryThresholdsV1:
    """Explicit engineering thresholds for geometry-derived proximity.

    These values are simulation parameters, not biological constants.  They
    remain attached to every readout so ``near`` cannot become an unexplained
    independent state.
    """

    touching_distance: float
    near_distance: float

    def __post_init__(self) -> None:
        touching = _finite_non_negative_float(self.touching_distance, field_name="touching_distance")
        near = _finite_non_negative_float(self.near_distance, field_name="near_distance")
        if near <= touching:
            raise ValueError("near_distance must be greater than touching_distance")
        object.__setattr__(self, "touching_distance", touching)
        object.__setattr__(self, "near_distance", near)

    def as_dict(self) -> dict[str, float]:
        """Return a JSON-safe threshold record."""
        return {
            "touching_distance": self.touching_distance,
            "near_distance": self.near_distance,
        }


@dataclass(frozen=True, slots=True)
class MaternalGeometryReadoutV1:
    """Revision-linked distance, bearing, and proximity derived from one map."""

    source_map_ref: NavMapRefV1
    self_element_id: str
    maternal_element_id: str
    distance: Optional[NavScalarQueryResultV1]
    bearing: Optional[NavScalarQueryResultV1]
    proximity: MaternalProximityV1
    thresholds: MaternalGeometryThresholdsV1
    valid: bool
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.source_map_ref, NavMapRefV1):
            raise TypeError("source_map_ref must be NavMapRefV1")
        _require_nonempty_text(self.self_element_id, field_name="self_element_id")
        _require_nonempty_text(self.maternal_element_id, field_name="maternal_element_id")
        if self.distance is not None and not isinstance(self.distance, NavScalarQueryResultV1):
            raise TypeError("distance must be NavScalarQueryResultV1 or None")
        if self.bearing is not None and not isinstance(self.bearing, NavScalarQueryResultV1):
            raise TypeError("bearing must be NavScalarQueryResultV1 or None")
        if not isinstance(self.proximity, MaternalProximityV1):
            raise TypeError("proximity must be MaternalProximityV1")
        if not isinstance(self.thresholds, MaternalGeometryThresholdsV1):
            raise TypeError("thresholds must be MaternalGeometryThresholdsV1")
        if not isinstance(self.valid, bool):
            raise TypeError("valid must be bool")
        _require_nonempty_text(self.reason, field_name="reason")
        if self.valid and self.distance is None:
            raise ValueError("valid maternal readout requires distance")
        if not self.valid and self.proximity is not MaternalProximityV1.UNKNOWN:
            raise ValueError("invalid maternal readout must preserve UNKNOWN proximity")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe geometry readout."""
        return {
            "source_map_ref": self.source_map_ref.as_dict(),
            "self_element_id": self.self_element_id,
            "maternal_element_id": self.maternal_element_id,
            "distance": self.distance.as_dict() if self.distance is not None else None,
            "bearing": self.bearing.as_dict() if self.bearing is not None else None,
            "proximity": self.proximity.value,
            "thresholds": self.thresholds.as_dict(),
            "valid": self.valid,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class MaternalGeometryShadowStateV1:
    """One immutable Phase 4A evidence/maintenance/root-view transaction."""

    evidence_map: NavMapV2
    evidence_readout: MaternalGeometryReadoutV1
    stable_map: Optional[NavMapV2]
    stable_readout: Optional[MaternalGeometryReadoutV1]
    root_view_map: Optional[NavMapV2]
    maintained: bool
    support_status: str
    support_age_observations: int
    max_missing_observations: int
    last_supported_observation_no: Optional[int]
    maintenance_action: str
    evidence_relation: str
    residual: Optional[NavStructuredResidualV1]
    revision_proposal: Optional[NavRevisionProposalV1]
    legacy_mom_distance: Optional[str]
    evidence_comparison: str
    maintained_comparison: str
    changed: bool
    root_view_changed: bool
    input_classification: str
    observation_no: int

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_map, NavMapV2):
            raise TypeError("evidence_map must be NavMapV2")
        if not isinstance(self.evidence_readout, MaternalGeometryReadoutV1):
            raise TypeError("evidence_readout must be MaternalGeometryReadoutV1")
        if self.evidence_readout.source_map_ref != _map_ref(self.evidence_map):
            raise ValueError("evidence_readout must describe evidence_map")
        if self.stable_map is None:
            if self.stable_readout is not None or self.root_view_map is not None:
                raise ValueError("stable_readout/root_view_map require stable_map")
        else:
            if not isinstance(self.stable_readout, MaternalGeometryReadoutV1):
                raise TypeError("stable_readout must be MaternalGeometryReadoutV1 when stable_map exists")
            if self.stable_readout.source_map_ref != _map_ref(self.stable_map):
                raise ValueError("stable_readout must describe stable_map")
            if not isinstance(self.root_view_map, NavMapV2):
                raise TypeError("root_view_map must be NavMapV2 when stable_map exists")
            target = follow_link(
                self.root_view_map,
                link_type=_MATERNAL_LINK_TYPE,
                source_element_id=_ROOT_SELF_ELEMENT_ID,
            )
            if target != _map_ref(self.stable_map):
                raise ValueError("root_view_map must link stable_map")
        if not isinstance(self.maintained, bool):
            raise TypeError("maintained must be bool")
        if self.maintained and self.stable_map is None:
            raise ValueError("maintained maternal shadow requires stable map")
        for field_name in ("changed", "root_view_changed"):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        _require_nonempty_text(self.support_status, field_name="support_status")
        _require_nonempty_text(self.maintenance_action, field_name="maintenance_action")
        _require_nonempty_text(self.evidence_relation, field_name="evidence_relation")
        _require_nonempty_text(self.evidence_comparison, field_name="evidence_comparison")
        _require_nonempty_text(self.maintained_comparison, field_name="maintained_comparison")
        _require_nonempty_text(self.input_classification, field_name="input_classification")
        _require_non_negative_int(self.support_age_observations, field_name="support_age_observations")
        _require_non_negative_int(self.max_missing_observations, field_name="max_missing_observations")
        _require_positive_int(self.observation_no, field_name="observation_no")
        if self.last_supported_observation_no is not None:
            _require_positive_int(self.last_supported_observation_no, field_name="last_supported_observation_no")
            if self.last_supported_observation_no > self.observation_no:
                raise ValueError("last_supported_observation_no cannot exceed observation_no")
        if self.residual is not None and not isinstance(self.residual, NavStructuredResidualV1):
            raise TypeError("residual must be NavStructuredResidualV1 or None")
        if self.revision_proposal is not None:
            if not isinstance(self.revision_proposal, NavRevisionProposalV1):
                raise TypeError("revision_proposal must be NavRevisionProposalV1 or None")
            if self.residual is None or self.revision_proposal.residual != self.residual:
                raise ValueError("revision_proposal must describe residual")
        if self.legacy_mom_distance is not None and self.legacy_mom_distance not in {"near", "far"}:
            raise ValueError("legacy_mom_distance must be near, far, or None")

    @property
    def evidence_ref(self) -> NavMapRefV1:
        """Return the current transient evidence-map reference."""
        return _map_ref(self.evidence_map)

    @property
    def stable_ref(self) -> Optional[NavMapRefV1]:
        """Return the current maintained stable-map reference."""
        if not self.maintained or self.stable_map is None:
            return None
        return _map_ref(self.stable_map)

    @property
    def last_stable_ref(self) -> Optional[NavMapRefV1]:
        """Return the last stable maternal-map reference independent of maintenance."""
        return _map_ref(self.stable_map) if self.stable_map is not None else None

    @property
    def root_view_ref(self) -> Optional[NavMapRefV1]:
        """Return the current maintained Phase 4A root-view reference."""
        if not self.maintained or self.root_view_map is None:
            return None
        return _map_ref(self.root_view_map)

    @property
    def last_stable_root_view_ref(self) -> Optional[NavMapRefV1]:
        """Return the last stable root-view reference independent of maintenance."""
        return _map_ref(self.root_view_map) if self.root_view_map is not None else None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe authority-explicit Phase 4A trace record."""
        stable_readout = self.stable_readout.as_dict() if self.stable_readout is not None else None
        maintained_readout = stable_readout if self.maintained else None
        return {
            "schema": "maternal_geometry_shadow_state_v1",
            "phase": "4A",
            "authority_level": "shadow",
            "authority": "shadow_only",
            "legacy_authority": "bodymap_policy_runtime",
            "follow_mom_authority": "legacy_bodymap_policy_runtime",
            "map_can_trigger_follow_mom": False,
            "root_view_is_accepted_wnm": False,
            "observation_no": self.observation_no,
            "evidence_map_ref": self.evidence_ref.as_dict(),
            "evidence_content_signature": self.evidence_map.content_signature(),
            "stable_map_ref": _optional_ref_dict(self.stable_ref),
            "last_stable_map_ref": _optional_ref_dict(self.last_stable_ref),
            "root_view_ref": _optional_ref_dict(self.root_view_ref),
            "last_stable_root_view_ref": _optional_ref_dict(self.last_stable_root_view_ref),
            "stable_content_signature": self.stable_map.content_signature() if self.stable_map is not None else None,
            "root_view_content_signature": (
                self.root_view_map.content_signature() if self.root_view_map is not None else None
            ),
            "evidence_readout": self.evidence_readout.as_dict(),
            "maintained_readout": maintained_readout,
            "last_stable_readout": stable_readout,
            "current_shadow_maintained": self.maintained,
            "support_status": self.support_status,
            "support_age_observations": self.support_age_observations,
            "max_missing_observations": self.max_missing_observations,
            "last_supported_observation_no": self.last_supported_observation_no,
            "maintenance_action": self.maintenance_action,
            "evidence_relation": self.evidence_relation,
            "structured_residual": self.residual.as_dict() if self.residual is not None else None,
            "revision_proposal": _revision_proposal_summary(self.revision_proposal),
            "legacy_mom_distance": self.legacy_mom_distance,
            "evidence_comparison": self.evidence_comparison,
            "maintained_comparison": self.maintained_comparison,
            "changed": self.changed,
            "root_view_changed": self.root_view_changed,
            "input_classification": self.input_classification,
            "identity_handle": _MATERNAL_ELEMENT_ID,
            "maternal_role_relation": _MATERNAL_ROLE_RELATION,
            "geometry_source": _ADAPTER_SOURCE_REF,
            "role_source": _ROLE_SOURCE_REF,
            "adapter_limitation": "simulated_positions_from_env_observation_metadata",
            "deferred_phase4_capabilities": [
                "approach_recession",
                "safe_reachability",
                "follow_mom_trigger_authority",
                "expected_follow_mom_successor",
            ],
        }


def maternal_geometry_thresholds_v1() -> MaternalGeometryThresholdsV1:
    """Return explicit Phase 4A proximity thresholds.

    The near threshold matches the current PerceptionAdapter's raw-distance
    engineering threshold.  The result remains map-linked and does not consume
    the symbolic BodyMap proximity label.
    """
    return MaternalGeometryThresholdsV1(
        touching_distance=0.15,
        near_distance=1.0,
    )


def maternal_geometry_match_thresholds_v1() -> NavMatchThresholdsV1:
    """Return explicit thresholds for stable-map versus evidence matching."""
    return NavMatchThresholdsV1(
        maximum_alignment_rms_error=20.0,
        maximum_geometry_rms_error=0.02,
        maximum_geometry_point_error=0.03,
        maximum_activation_strength_delta=0.05,
        minimum_correspondence_coverage=0.50,
        minimum_rank_score=0.20,
        ambiguity_margin=0.05,
        maximum_candidate_count=8,
    )


def maternal_geometry_revision_thresholds_v1() -> NavRevisionThresholdsV1:
    """Return explicit KEEP/REVISE thresholds for the Phase 4A shadow."""
    return NavRevisionThresholdsV1(
        minimum_keep_score=0.99,
        minimum_revise_score=0.30,
        minimum_revise_coverage=0.50,
        maximum_reject_all_score=0.10,
    )


def _finite_non_negative_float(value: Any, *, field_name: str) -> float:
    """Return one finite non-negative float without accepting bool."""
    if isinstance(value, bool):
        raise TypeError(f"{field_name} must be a finite non-negative number")
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise TypeError(f"{field_name} must be a finite non-negative number") from exc
    if not math.isfinite(number) or number < 0.0:
        raise ValueError(f"{field_name} must be finite and non-negative")
    return number


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Validate one non-empty text field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Validate one non-negative integer without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Validate one positive integer without accepting bool."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the stable reference of one immutable map revision."""
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return a JSON-safe optional map reference."""
    return ref.as_dict() if ref is not None else None


def _point(x: float, y: float) -> NavPointV1:
    """Return one concise immutable point."""
    return NavPointV1(x=x, y=y)


def _point_geometry(point: NavPointV1) -> NavGeometryV1:
    """Return one POINT geometry record."""
    return NavGeometryV1(kind=NavGeometryKindV1.POINT, points=(point,))


def _geometry_provenance(observation_no: int, *, complete: bool) -> NavProvenanceV1:
    """Return OBSERVED provenance for the simulated position adapter."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.OBSERVED,
        source_ref=f"{_ADAPTER_SOURCE_REF}:observation:{observation_no}",
        quality=0.85 if complete else 0.30,
    )


def _role_provenance() -> NavProvenanceV1:
    """Return separate inferred provenance for the non-geometric maternal role."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=_ROLE_SOURCE_REF,
        quality=0.80,
    )


def _root_view_provenance() -> NavProvenanceV1:
    """Return stable inferred provenance for the diagnostic root view."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=_ROOT_VIEW_SOURCE_REF,
        quality=0.75,
    )


def _activation(name: str, provenance: NavProvenanceV1) -> tuple[NavActivationV1, ...]:
    """Return one stable decoded activation tuple."""
    return (NavActivationV1(name=name, strength=1.0, provenance=provenance),)


def _relation_frame() -> NavFrameV1:
    """Return the fixed SELF-centered horizontal frame used by Phase 4A."""
    return NavFrameV1(
        frame_id=_SELF_MATERNAL_FRAME_ID,
        x_axis="environment_x_relative_to_self",
        y_axis="environment_y_relative_to_self",
        units="simulated_distance_units",
        min_x=-20.0,
        max_x=20.0,
        min_y=-20.0,
        max_y=20.0,
    )


def _root_fallback_frame() -> NavFrameV1:
    """Return a tiny root-view frame when the Phase 2 root is unavailable."""
    return NavFrameV1(
        frame_id=_ROOT_FALLBACK_FRAME_ID,
        x_axis="context_x",
        y_axis="context_y",
        units="normalized",
        min_x=-1.0,
        max_x=1.0,
        min_y=-1.0,
        max_y=1.0,
    )


def _meta_point(env_obs: EnvObservation, key: str) -> Optional[NavPointV1]:
    """Decode one finite ``{x, y}`` point from observation metadata."""
    meta = getattr(env_obs, "env_meta", None)
    if not isinstance(meta, dict):
        return None
    value = meta.get(key)
    if not isinstance(value, dict):
        return None
    x = value.get("x")
    y = value.get("y")
    if isinstance(x, bool) or not isinstance(x, (int, float)):
        return None
    if isinstance(y, bool) or not isinstance(y, (int, float)):
        return None
    try:
        point = NavPointV1(x=float(x), y=float(y))
    except (TypeError, ValueError):
        return None
    return point


def _phase4c_identity_exclusion_reason(env_obs: EnvObservation) -> Optional[str]:
    """Return why current position cannot represent the known maternal individual.

    Phase 4A predates explicit identity-continuity inspection. Phase 4C adds a
    narrow optional metadata seam so a known different or ambiguous individual
    is not inserted into the maternal geometry map merely because it occupies
    ``mom_position``. With no explicit identity metadata, Phase 4A behavior is
    unchanged.
    """
    meta = getattr(env_obs, "env_meta", None)
    if not isinstance(meta, dict):
        return None

    status_raw = meta.get("maternal_identity_status")
    status = str(status_raw).strip().lower() if isinstance(status_raw, str) else ""
    if status in {"ambiguous", "unknown", "uncertain"}:
        return "maternal_identity_ambiguous"
    if status in {"mismatch", "different", "substituted"}:
        return "maternal_identity_mismatch"

    observed_identity: Optional[str]
    candidates_raw = meta.get("maternal_identity_candidates")
    if isinstance(candidates_raw, (list, tuple)):
        candidates = sorted(
            {
                item.strip()
                for item in candidates_raw
                if isinstance(item, str) and item.strip()
            }
        )
        if len(candidates) != 1:
            return "maternal_identity_ambiguous"
        observed_identity = candidates[0]
    else:
        identity_raw = meta.get("maternal_identity_handle")
        observed_identity = (
            identity_raw.strip()
            if isinstance(identity_raw, str) and identity_raw.strip()
            else None
        )

    if observed_identity is not None and observed_identity != _MATERNAL_ELEMENT_ID:
        return "maternal_identity_mismatch"
    return None


def _observation_classification(env_obs: EnvObservation) -> tuple[str, Optional[NavPointV1]]:
    """Return adapter status and identity-eligible maternal position relative to SELF."""
    self_position = _meta_point(env_obs, "kid_position")
    maternal_position = _meta_point(env_obs, "mom_position")
    if self_position is None:
        return "self_position_missing", None
    if maternal_position is None:
        return "maternal_position_missing", None
    identity_exclusion = _phase4c_identity_exclusion_reason(env_obs)
    if identity_exclusion is not None:
        return identity_exclusion, None
    relative = NavPointV1(
        x=maternal_position.x - self_position.x,
        y=maternal_position.y - self_position.y,
    )
    return "position_input", relative


def maternal_geometry_evidence_from_observation_v1(
    env_obs: EnvObservation,
    *,
    observation_no: int,
) -> tuple[NavMapV2, str]:
    """Build one transient SELF-maternal evidence map from current positions.

    The function intentionally ignores symbolic ``proximity:mom:*`` predicates
    and the precomputed ``distance_to_mom`` scalar.  Distance and bearing are
    derived later from the two points in the common frame.
    """
    if not isinstance(env_obs, EnvObservation):
        raise TypeError("env_obs must be EnvObservation")
    _require_positive_int(observation_no, field_name="observation_no")
    classification, relative_maternal = _observation_classification(env_obs)
    complete = relative_maternal is not None
    geometry_provenance = _geometry_provenance(observation_no, complete=complete)
    role_provenance = _role_provenance()

    elements = [
        NavElementV1(
            element_id=_SELF_ELEMENT_ID,
            role="self_position",
            geometry=_point_geometry(_point(0.0, 0.0)),
            activations=_activation("self_related", geometry_provenance),
            parent_element_id=None,
            provenance=geometry_provenance,
        )
    ]
    relations: tuple[NavRelationV1, ...] = ()
    if relative_maternal is not None:
        elements.append(
            NavElementV1(
                element_id=_MATERNAL_ELEMENT_ID,
                role="individual_entity",
                geometry=_point_geometry(relative_maternal),
                activations=_activation("social_individual", geometry_provenance),
                parent_element_id=None,
                provenance=geometry_provenance,
            )
        )
        relations = (
            NavRelationV1(
                relation_type=_MATERNAL_ROLE_RELATION,
                source_element_id=_MATERNAL_ELEMENT_ID,
                target_element_id=_SELF_ELEMENT_ID,
                provenance=role_provenance,
            ),
        )

    navmap = NavMapV2(
        map_id=f"{_EVIDENCE_MAP_ID_PREFIX}_o{observation_no:06d}",
        revision=1,
        parent_ref=None,
        role="self_maternal_scene",
        frame=_relation_frame(),
        provenance=geometry_provenance,
        elements=tuple(elements),
        relations=relations,
    )
    return navmap, classification


def maternal_geometry_readout_v1(
    navmap: NavMapV2,
    *,
    thresholds: Optional[MaternalGeometryThresholdsV1] = None,
) -> MaternalGeometryReadoutV1:
    """Derive distance, bearing, and proximity from one SELF-maternal map."""
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    threshold_record = thresholds or maternal_geometry_thresholds_v1()
    element_ids = {element.element_id for element in navmap.elements}
    if _SELF_ELEMENT_ID not in element_ids or _MATERNAL_ELEMENT_ID not in element_ids:
        return MaternalGeometryReadoutV1(
            source_map_ref=_map_ref(navmap),
            self_element_id=_SELF_ELEMENT_ID,
            maternal_element_id=_MATERNAL_ELEMENT_ID,
            distance=None,
            bearing=None,
            proximity=MaternalProximityV1.UNKNOWN,
            thresholds=threshold_record,
            valid=False,
            reason="missing_required_elements",
        )

    distance = centroid_distance_between(navmap, _SELF_ELEMENT_ID, _MATERNAL_ELEMENT_ID)
    if distance.value <= threshold_record.touching_distance:
        proximity = MaternalProximityV1.TOUCHING
    elif distance.value <= threshold_record.near_distance:
        proximity = MaternalProximityV1.NEAR
    else:
        proximity = MaternalProximityV1.FAR

    bearing: Optional[NavScalarQueryResultV1]
    if distance.value == 0.0:
        bearing = None
        reason = "coincident_positions_bearing_undefined"
    else:
        bearing = bearing_between_centroids(navmap, _SELF_ELEMENT_ID, _MATERNAL_ELEMENT_ID)
        reason = "complete_common_frame_geometry"
    return MaternalGeometryReadoutV1(
        source_map_ref=_map_ref(navmap),
        self_element_id=_SELF_ELEMENT_ID,
        maternal_element_id=_MATERNAL_ELEMENT_ID,
        distance=distance,
        bearing=bearing,
        proximity=proximity,
        thresholds=threshold_record,
        valid=True,
        reason=reason,
    )


def _stable_map_from_evidence(
    evidence_map: NavMapV2,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1],
) -> NavMapV2:
    """Copy complete evidence content into the stable maternal map family."""
    return NavMapV2(
        map_id=_SELF_MATERNAL_MAP_ID,
        revision=revision,
        parent_ref=parent_ref,
        role=evidence_map.role,
        frame=evidence_map.frame,
        provenance=evidence_map.provenance,
        elements=evidence_map.elements,
        relations=evidence_map.relations,
        links=evidence_map.links,
        schema=evidence_map.schema,
    )


def _root_base_content(base_root: Optional[NavMapV2]) -> tuple[NavFrameV1, tuple[NavElementV1, ...], tuple[NavMapLinkV1, ...]]:
    """Return root-view frame/elements/links while preserving Phase 2 content."""
    if isinstance(base_root, NavMapV2):
        return base_root.frame, base_root.elements, base_root.links
    provenance = _root_view_provenance()
    element = NavElementV1(
        element_id=_ROOT_SELF_ELEMENT_ID,
        role="self_context_anchor",
        geometry=_point_geometry(_point(0.0, 0.0)),
        activations=_activation("self_related", provenance),
        parent_element_id=None,
        provenance=provenance,
    )
    return _root_fallback_frame(), (element,), ()


def maternal_root_view_from_maps_v1(
    maternal_map: NavMapV2,
    *,
    base_root: Optional[NavMapV2],
    revision: int,
    parent_ref: Optional[NavMapRefV1] = None,
) -> NavMapV2:
    """Build a diagnostic root view linking SELF-ground and maternal content.

    The returned map is a separate Phase 4A shadow family.  It copies the
    current Phase 2 root elements/links, adds one addressable maternal link, and
    never replaces ``ctx.navmap_v2_shadow_root`` or grants accepted-WNM status.
    """
    if not isinstance(maternal_map, NavMapV2):
        raise TypeError("maternal_map must be NavMapV2")
    _require_positive_int(revision, field_name="revision")
    frame, elements, base_links = _root_base_content(base_root)
    if _ROOT_SELF_ELEMENT_ID not in {element.element_id for element in elements}:
        raise ValueError("base root must expose self_context for the maternal link")
    provenance = _root_view_provenance()
    links = tuple(
        link
        for link in base_links
        if not (
            link.link_type == _MATERNAL_LINK_TYPE
            and link.source_element_id == _ROOT_SELF_ELEMENT_ID
        )
    ) + (
        NavMapLinkV1(
            link_type=_MATERNAL_LINK_TYPE,
            target_ref=_map_ref(maternal_map),
            source_element_id=_ROOT_SELF_ELEMENT_ID,
            provenance=provenance,
        ),
    )
    return NavMapV2(
        map_id=_ROOT_VIEW_MAP_ID,
        revision=revision,
        parent_ref=parent_ref,
        role="root_scene",
        frame=frame,
        provenance=provenance,
        elements=elements,
        relations=(),
        links=links,
    )


def _updated_root_view(
    *,
    stable_map: NavMapV2,
    base_root: Optional[NavMapV2],
    previous_root_view: Optional[NavMapV2],
) -> tuple[NavMapV2, bool]:
    """Return a reused or revised root view for current target references."""
    probe = maternal_root_view_from_maps_v1(
        stable_map,
        base_root=base_root,
        revision=1,
        parent_ref=None,
    )
    if previous_root_view is not None and probe.content_signature() == previous_root_view.content_signature():
        return previous_root_view, False
    if previous_root_view is None:
        return probe, True
    return (
        maternal_root_view_from_maps_v1(
            stable_map,
            base_root=base_root,
            revision=previous_root_view.revision + 1,
            parent_ref=_map_ref(previous_root_view),
        ),
        True,
    )


def _bodymap_mom_distance_from_ctx(ctx: Any) -> Optional[str]:
    """Read the legacy BodyMap mom slot without importing controller code."""
    body_world = getattr(ctx, "body_world", None)
    body_ids = getattr(ctx, "body_ids", None)
    if body_world is None or not isinstance(body_ids, dict):
        return None
    mom_id = body_ids.get("mom")
    if not isinstance(mom_id, str):
        return None
    binding = getattr(body_world, "_bindings", {}).get(mom_id)  # pylint: disable=protected-access
    if binding is None:
        return None
    tags = set(getattr(binding, "tags", ()) or ())
    if "pred:proximity:mom:close" in tags:
        return "near"
    if "pred:proximity:mom:far" in tags:
        return "far"
    return None


def _comparison(readout: MaternalGeometryReadoutV1, legacy_distance: Optional[str]) -> str:
    """Compare a geometry-derived proximity with the legacy BodyMap readout."""
    if legacy_distance not in {"near", "far"}:
        return "not_comparable"
    if not readout.valid or readout.proximity is MaternalProximityV1.UNKNOWN:
        return "map_unknown"
    map_distance = "near" if readout.proximity in {MaternalProximityV1.NEAR, MaternalProximityV1.TOUCHING} else "far"
    return "agree" if map_distance == legacy_distance else "disagree"


def _next_observation_no(ctx: Any) -> int:
    """Advance and return the deterministic Phase 4A observation counter."""
    try:
        current = int(getattr(ctx, "navmap_maternal_observation_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    observation_no = max(0, current) + 1
    ctx.navmap_maternal_observation_no = observation_no
    return observation_no


def _max_missing_observations(ctx: Any) -> int:
    """Return the declared maternal maintenance limit from the context."""
    try:
        value = int(
            getattr(
                ctx,
                "navmap_maternal_max_missing_observations",
                _DEFAULT_MAX_MISSING_OBSERVATIONS,
            )
        )
    except (TypeError, ValueError):
        return _DEFAULT_MAX_MISSING_OBSERVATIONS
    return value if value >= 0 else _DEFAULT_MAX_MISSING_OBSERVATIONS


def _previous_state(ctx: Any) -> Optional[MaternalGeometryShadowStateV1]:
    """Return the previous Phase 4A state when available."""
    value = getattr(ctx, "navmap_maternal_state", None)
    return value if isinstance(value, MaternalGeometryShadowStateV1) else None


def _previous_maps(ctx: Any) -> tuple[Optional[NavMapV2], Optional[NavMapV2]]:
    """Return valid prior stable maternal and root-view maps."""
    stable_map = getattr(ctx, "navmap_maternal_map", None)
    root_view = getattr(ctx, "navmap_maternal_root_view", None)
    if not isinstance(stable_map, NavMapV2):
        stable_map = None
    if not isinstance(root_view, NavMapV2):
        root_view = None
    if stable_map is None:
        return None, None
    return stable_map, root_view


def _compare_complete_evidence(
    base_map: NavMapV2,
    evidence_map: NavMapV2,
) -> tuple[NavStructuredResidualV1, NavRevisionProposalV1]:
    """Match complete maternal evidence to the stable map and propose change."""
    match_result = match_navmaps(
        base_map,
        evidence_map,
        thresholds=maternal_geometry_match_thresholds_v1(),
    )
    residual = structured_residual(
        base_map,
        evidence_map,
        match_result=match_result,
    )
    proposal = propose_revision(
        base_map,
        evidence_map,
        residual=residual,
        thresholds=maternal_geometry_revision_thresholds_v1(),
    )
    return residual, proposal


def _last_supported_observation_no(
    previous_state: Optional[MaternalGeometryShadowStateV1],
    *,
    previous_map: Optional[NavMapV2],
    observation_no: int,
) -> Optional[int]:
    """Recover the last support marker, including a defensive migration bridge."""
    if previous_state is not None:
        return previous_state.last_supported_observation_no
    if previous_map is not None:
        return max(1, observation_no - 1)
    return None


def _missing_maintenance_result(
    *,
    previous_map: Optional[NavMapV2],
    previous_state: Optional[MaternalGeometryShadowStateV1],
    observation_no: int,
    max_missing: int,
) -> tuple[bool, str, int, Optional[int], str, str]:
    """Apply the bounded missing-position support-aging rule."""
    last_supported = _last_supported_observation_no(
        previous_state,
        previous_map=previous_map,
        observation_no=observation_no,
    )
    if previous_map is None or last_supported is None:
        return False, "uninitialized", 0, None, "defer_missing", "deferred"
    support_age = max(1, observation_no - last_supported)
    if support_age > max_missing:
        return False, "invalidated", support_age, last_supported, "invalidate_missing", "invalidated"
    support_status = "stale" if support_age == max_missing else "aging"
    return True, support_status, support_age, last_supported, "maintain_missing", "maintained"


def _revision_proposal_summary(proposal: Optional[NavRevisionProposalV1]) -> Optional[dict[str, Any]]:
    """Return a compact proposal trace without duplicating the full residual."""
    if proposal is None:
        return None
    return {
        "decision": proposal.decision.value,
        "base_map_ref": proposal.base_map_ref.as_dict(),
        "evidence_map_ref": proposal.evidence_map_ref.as_dict(),
        "changed_element_ids": list(proposal.changed_element_ids),
        "reason": proposal.reason,
        "thresholds": proposal.thresholds.as_dict(),
    }


def _history_limit(ctx: Any) -> int:
    """Return one bounded positive maternal history limit."""
    try:
        value = int(getattr(ctx, "navmap_maternal_history_limit", _DEFAULT_HISTORY_LIMIT) or _DEFAULT_HISTORY_LIMIT)
    except (TypeError, ValueError):
        return _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _append_history(ctx: Any, row: dict[str, Any]) -> None:
    """Append one bounded JSON-safe Phase 4A trace."""
    history = getattr(ctx, "navmap_maternal_history", [])
    if not isinstance(history, list):
        history = []
    clean = [dict(item) for item in history if isinstance(item, dict)]
    clean.append(dict(row))
    ctx.navmap_maternal_history = clean[-_history_limit(ctx):]


def maternal_geometry_shadow_observation_step_v1(ctx: Any, env_obs: EnvObservation) -> dict[str, Any]:
    """Process one observation through the Phase 4A maternal geometry shadow.

    Complete equivalent evidence refreshes support and reuses the stable map.
    Changed maternal position creates a local child revision.  Missing position
    evidence remains UNKNOWN, ages external support, and eventually invalidates
    current shadow participation.  FollowMom and BodyMap authority are unchanged.
    """
    if ctx is None or env_obs is None:
        return {}
    if not bool(getattr(ctx, "navmap_maternal_shadow_enabled", True)):
        return {
            "schema": "maternal_geometry_shadow_update_v1",
            "phase": "4A",
            "status": "disabled",
            "authority": "shadow_only",
            "legacy_authority": "bodymap_policy_runtime",
        }

    observation_no = _next_observation_no(ctx)
    max_missing = _max_missing_observations(ctx)
    evidence_map, classification = maternal_geometry_evidence_from_observation_v1(
        env_obs,
        observation_no=observation_no,
    )
    evidence_readout = maternal_geometry_readout_v1(evidence_map)
    legacy_distance = _bodymap_mom_distance_from_ctx(ctx)
    evidence_comparison = _comparison(evidence_readout, legacy_distance)

    previous_map, previous_root_view = _previous_maps(ctx)
    previous_state = _previous_state(ctx)
    stable_map = previous_map
    root_view = previous_root_view
    residual: Optional[NavStructuredResidualV1] = None
    proposal: Optional[NavRevisionProposalV1] = None
    changed = False
    root_view_changed = False
    last_supported: Optional[int]

    if evidence_readout.valid and previous_map is None:
        stable_map = _stable_map_from_evidence(evidence_map, revision=1, parent_ref=None)
        maintained = True
        support_status = "fresh"
        support_age = 0
        last_supported = observation_no
        maintenance_action = "create"
        evidence_relation = "initial_support"
        status = "created"
        changed = True
    elif evidence_readout.valid and previous_map is not None:
        residual, proposal = _compare_complete_evidence(previous_map, evidence_map)
        if proposal.decision is NavRevisionDecisionV1.KEEP:
            stable_map = previous_map
            maintained = True
            support_status = "fresh"
            support_age = 0
            last_supported = observation_no
            previously_maintained = previous_state.maintained if previous_state is not None else True
            maintenance_action = "refresh" if previously_maintained else "reinstate"
            evidence_relation = "compatible"
            status = "reused" if previously_maintained else "reinstated"
        elif proposal.decision is NavRevisionDecisionV1.REVISE:
            stable_map = apply_revision(
                previous_map,
                evidence_map,
                proposal,
                new_revision=previous_map.revision + 1,
            )
            maintained = True
            support_status = "fresh"
            support_age = 0
            last_supported = observation_no
            maintenance_action = "revise"
            evidence_relation = "changed_geometry"
            status = "revised"
            changed = True
        else:
            stable_map = previous_map
            maintained = False
            support_status = "unresolved"
            support_age = 0
            last_supported = _last_supported_observation_no(
                previous_state,
                previous_map=previous_map,
                observation_no=observation_no,
            )
            maintenance_action = "defer_unresolved"
            evidence_relation = "unresolved"
            status = "deferred"
    else:
        (
            maintained,
            support_status,
            support_age,
            last_supported,
            maintenance_action,
            status,
        ) = _missing_maintenance_result(
            previous_map=previous_map,
            previous_state=previous_state,
            observation_no=observation_no,
            max_missing=max_missing,
        )
        evidence_relation = "missing"

    stable_readout = maternal_geometry_readout_v1(stable_map) if stable_map is not None else None
    if stable_map is not None:
        base_root = getattr(ctx, "navmap_v2_shadow_root", None)
        base_root = base_root if isinstance(base_root, NavMapV2) else None
        root_view, root_view_changed = _updated_root_view(
            stable_map=stable_map,
            base_root=base_root,
            previous_root_view=previous_root_view,
        )
    else:
        root_view = None

    if maintained and stable_readout is not None:
        maintained_comparison = _comparison(stable_readout, legacy_distance)
    else:
        maintained_comparison = "not_maintained"

    state = MaternalGeometryShadowStateV1(
        evidence_map=evidence_map,
        evidence_readout=evidence_readout,
        stable_map=stable_map,
        stable_readout=stable_readout,
        root_view_map=root_view,
        maintained=maintained,
        support_status=support_status,
        support_age_observations=support_age,
        max_missing_observations=max_missing,
        last_supported_observation_no=last_supported,
        maintenance_action=maintenance_action,
        evidence_relation=evidence_relation,
        residual=residual,
        revision_proposal=proposal,
        legacy_mom_distance=legacy_distance,
        evidence_comparison=evidence_comparison,
        maintained_comparison=maintained_comparison,
        changed=changed,
        root_view_changed=root_view_changed,
        input_classification=classification,
        observation_no=observation_no,
    )
    row = state.as_dict()
    row.update(
        {
            "schema": "maternal_geometry_shadow_update_v1",
            "status": status,
            "controller_steps": getattr(ctx, "controller_steps", None),
            "ticks": getattr(ctx, "ticks", None),
        }
    )

    ctx.navmap_maternal_evidence_map = evidence_map
    ctx.navmap_maternal_map = stable_map
    ctx.navmap_maternal_root_view = root_view
    ctx.navmap_maternal_state = state
    ctx.navmap_maternal_last_update = dict(row)
    _append_history(ctx, row)
    return row


def maternal_geometry_shadow_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest Phase 4A update."""
    if ctx is None:
        return {
            "schema": "maternal_geometry_shadow_summary_v1",
            "phase": "4A",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_maternal_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "maternal_geometry_shadow_summary_v1",
            "phase": "4A",
            "status": "idle",
            "authority": "shadow_only",
            "history_count": len(getattr(ctx, "navmap_maternal_history", []) or []),
        }
    out = dict(row)
    out["schema"] = "maternal_geometry_shadow_summary_v1"
    out["history_count"] = len(getattr(ctx, "navmap_maternal_history", []) or [])
    return out


def _ref_text(value: Any) -> str:
    """Render one optional JSON map reference."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id', '?')}@r{value.get('revision', '?')}"


def _distance_text(readout: dict[str, Any]) -> str:
    """Return compact distance text for one JSON-safe readout."""
    distance = readout.get("distance")
    if not isinstance(distance, dict):
        return "unknown"
    value = distance.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    try:
        return f"{float(value):.3f}"
    except (TypeError, ValueError):
        return "unknown"


def _bearing_text(readout: dict[str, Any]) -> str:
    """Return compact bearing text for one JSON-safe readout."""
    bearing = readout.get("bearing")
    if not isinstance(bearing, dict):
        return "unknown"
    value = bearing.get("value")
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return "unknown"
    try:
        return f"{float(value):.1f}deg"
    except (TypeError, ValueError):
        return "unknown"


def render_maternal_geometry_shadow_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 4A maternal geometry lines."""
    summary = maternal_geometry_shadow_summary_v1(ctx)
    lines = ["MATERNAL GEOMETRY PHASE 4A SHADOW:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle", "disabled", "error"}:
        lines.append(
            "  "
            f"status={status} authority=shadow_only legacy_authority=bodymap_policy_runtime "
            "map_can_trigger_follow_mom=False"
        )
        if status == "error":
            lines.append(f"  error_type={summary.get('error_type')} error={summary.get('error')}")
        return lines

    evidence = summary.get("evidence_readout")
    evidence = evidence if isinstance(evidence, dict) else {}
    maintained = summary.get("maintained_readout")
    maintained = maintained if isinstance(maintained, dict) else {}
    last_stable = summary.get("last_stable_readout")
    last_stable = last_stable if isinstance(last_stable, dict) else {}

    lines.append(
        "  "
        f"status={status} changed={summary.get('changed')} root_changed={summary.get('root_view_changed')} "
        "authority=shadow_only follow_mom_authority=legacy_bodymap_policy_runtime"
    )
    lines.append(
        "  "
        f"evidence={_ref_text(summary.get('evidence_map_ref'))} "
        f"distance={_distance_text(evidence)} bearing={_bearing_text(evidence)} "
        f"proximity={evidence.get('proximity', 'unknown')} input={summary.get('input_classification')}"
    )
    lines.append(
        "  "
        f"maintained={summary.get('current_shadow_maintained')} action={summary.get('maintenance_action')} "
        f"support={summary.get('support_status')} "
        f"age={summary.get('support_age_observations')}/{summary.get('max_missing_observations')}"
    )
    lines.append(
        "  "
        f"current map={_ref_text(summary.get('stable_map_ref'))} "
        f"root_view={_ref_text(summary.get('root_view_ref'))} "
        f"distance={_distance_text(maintained)} bearing={_bearing_text(maintained)} "
        f"proximity={maintained.get('proximity', 'unknown')}"
    )
    if not summary.get("current_shadow_maintained") and summary.get("last_stable_map_ref") is not None:
        lines.append(
            "  "
            f"last_stable map={_ref_text(summary.get('last_stable_map_ref'))} "
            f"root_view={_ref_text(summary.get('last_stable_root_view_ref'))} "
            f"distance={_distance_text(last_stable)} bearing={_bearing_text(last_stable)} "
            f"proximity={last_stable.get('proximity', 'unknown')}"
        )
    lines.append(
        "  "
        f"legacy mom_distance={summary.get('legacy_mom_distance')} "
        f"evidence_comparison={summary.get('evidence_comparison')} "
        f"maintained_comparison={summary.get('maintained_comparison')}"
    )
    lines.append(
        "  "
        f"identity={summary.get('identity_handle')} role_relation={summary.get('maternal_role_relation')} "
        "role_and_provenance_separate=True root_view_is_accepted_wnm=False"
    )
    proposal = summary.get("revision_proposal")
    residual = summary.get("structured_residual")
    if isinstance(proposal, dict):
        changed_ids = proposal.get("changed_element_ids")
        changed_text = ",".join(str(item) for item in changed_ids) if isinstance(changed_ids, list) else ""
        residual_reason = residual.get("reason") if isinstance(residual, dict) else None
        lines.append(
            "  "
            f"proposal={proposal.get('decision')} residual={residual_reason} "
            f"changed_elements={changed_text or '(none)'}"
        )
    return lines
