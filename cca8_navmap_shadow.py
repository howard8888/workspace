# -*- coding: utf-8 -*-
"""Phase 2 NavMapV2 shadow construction and evidence maintenance.

Purpose
-------
This module provides CCA8's first runtime-facing ``NavMapV2`` bridge. It adapts
current interpreted ``EnvObservation`` posture evidence into a small SELF-ground
geometry, derives body-state evidence from that geometry, and maintains a
minimal root Working Navigation Map shadow that links to the SELF-ground map.

Phase 2A proved the basic runtime plumbing: interpreted standing/fallen inputs
selected deterministic canonical geometry, geometry produced body-state
readouts, meaningful changes produced immutable child revisions, and the
legacy BodyMap remained authoritative.

Phase 2B adds one deliberately small maintenance experiment. A transient
current-evidence map is now distinct from the maintained current shadow:

* compatible complete evidence refreshes support without revision churn;
* missing or conflicting evidence remains UNKNOWN and ages support;
* a bounded missing-evidence rule eventually invalidates the maintained shadow;
* reliable contradictory evidence produces a structured residual and a child
  revision of the maintained SELF-ground map;
* maintenance, freshness, and invalidation remain external to immutable
  ``NavMapV2`` content.

Adapter limitation
------------------
Current observations do not yet contain decoded biological-like body geometry.
The adapter therefore uses interpreted ``posture:standing`` and
``posture:fallen`` predicates only to select deterministic canonical geometry
for this engineering experiment. The downstream body-state result is derived
from geometry, but the upstream posture perception remains a temporary seam.

Authority boundary
------------------
Everything in this module is shadow-only. The legacy BodyMap remains the actual
runtime authority for safety and policy gating. No function here writes
WorldGraph truth, Columns, PolicyRuntime state, controller choices, or
environment state. A maintained shadow root is not an accepted authoritative
WNM.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Optional

from cca8_env import EnvObservation
from cca8_navmap_kernel import (
    NavActivationV1,
    NavBodyStateEvidenceV1,
    NavBodyStateInterpretationV1,
    NavBodyStateThresholdsV1,
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
    NavRevisionDecisionV1,
    NavRevisionProposalV1,
    NavRevisionThresholdsV1,
    NavSourceClassV1,
    NavStructuredResidualV1,
    apply_revision,
    body_state_evidence,
    match_navmaps,
    propose_revision,
    structured_residual,
)

__version__ = "0.2.0"

__all__ = [
    "NavMapV2ShadowStateV1",
    "NavMapV2ShadowStateV2",
    "navmap_v2_shadow_body_thresholds_v1",
    "navmap_v2_shadow_match_thresholds_v1",
    "navmap_v2_shadow_revision_thresholds_v1",
    "navmap_v2_body_ground_from_observation_v1",
    "navmap_v2_body_ground_evidence_from_observation_v1",
    "navmap_v2_root_shadow_from_body_ground_v1",
    "navmap_v2_shadow_observation_step_v1",
    "navmap_v2_shadow_summary_v1",
    "render_navmap_v2_shadow_lines_v1",
    "__version__",
]

_BODY_MAP_ID = "goat_self_ground_v2"
_ROOT_MAP_ID = "goat_root_scene_v2"
_EVIDENCE_MAP_ID_PREFIX = "goat_self_ground_evidence_v2"
_BODY_FRAME_ID = "shadow_self_ground_frame_v1"
_ROOT_FRAME_ID = "shadow_root_wnm_frame_v1"
_BODY_LINK_TYPE = "self_ground_submap"
_ADAPTER_SOURCE_REF = "adapter:env_observation_to_self_ground_v1"
_ROOT_SOURCE_REF = "runtime:shadow_root_from_self_ground_v1"
_DEFAULT_MAX_MISSING_OBSERVATIONS = 2


@dataclass(frozen=True, slots=True)
class NavMapV2ShadowStateV2:
    """One immutable Phase 2B evidence/maintenance transaction record.

    ``evidence_body_ground_map`` represents only the current observation packet.
    ``body_ground_map`` and ``root_map`` are the last stable decoded shadow
    content. ``maintained`` says whether those stable references currently
    participate in the provisional current shadow. This keeps current evidence,
    decoded content, freshness, and current participation separate.
    """

    evidence_body_ground_map: NavMapV2
    evidence_body_state: NavBodyStateEvidenceV1
    root_map: Optional[NavMapV2]
    body_ground_map: Optional[NavMapV2]
    stable_body_state: Optional[NavBodyStateEvidenceV1]
    maintained: bool
    support_status: str
    support_age_observations: int
    max_missing_observations: int
    last_supported_observation_no: Optional[int]
    maintenance_action: str
    evidence_relation: str
    residual: Optional[NavStructuredResidualV1]
    revision_proposal: Optional[NavRevisionProposalV1]
    legacy_bodymap_posture: Optional[str]
    evidence_comparison: str
    maintained_comparison: str
    changed: bool
    input_classification: str
    observation_no: int

    def __post_init__(self) -> None:
        if not isinstance(self.evidence_body_ground_map, NavMapV2):
            raise TypeError("evidence_body_ground_map must be NavMapV2")
        if not isinstance(self.evidence_body_state, NavBodyStateEvidenceV1):
            raise TypeError("evidence_body_state must be NavBodyStateEvidenceV1")
        if self.evidence_body_state.source_map_ref != _map_ref(self.evidence_body_ground_map):
            raise ValueError("evidence_body_state must describe evidence_body_ground_map")

        if (self.root_map is None) != (self.body_ground_map is None):
            raise ValueError("root_map and body_ground_map must be present or absent together")
        if self.body_ground_map is None:
            if self.stable_body_state is not None:
                raise ValueError("stable_body_state requires body_ground_map")
        else:
            if not isinstance(self.root_map, NavMapV2):
                raise TypeError("root_map must be NavMapV2 when body_ground_map is present")
            if not isinstance(self.stable_body_state, NavBodyStateEvidenceV1):
                raise TypeError("stable_body_state must be NavBodyStateEvidenceV1 when body_ground_map is present")
            if self.stable_body_state.source_map_ref != _map_ref(self.body_ground_map):
                raise ValueError("stable_body_state must describe body_ground_map")
            if not any(
                link.link_type == _BODY_LINK_TYPE and link.target_ref == _map_ref(self.body_ground_map)
                for link in self.root_map.links
            ):
                raise ValueError("root_map must link the stable body_ground_map")

        if not isinstance(self.maintained, bool):
            raise TypeError("maintained must be a bool")
        if self.maintained and self.body_ground_map is None:
            raise ValueError("maintained shadow requires stable root and body-ground maps")
        if not isinstance(self.changed, bool):
            raise TypeError("changed must be a bool")
        if self.legacy_bodymap_posture is not None and not isinstance(self.legacy_bodymap_posture, str):
            raise TypeError("legacy_bodymap_posture must be str or None")

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

        if self.residual is not None:
            if not isinstance(self.residual, NavStructuredResidualV1):
                raise TypeError("residual must be NavStructuredResidualV1 or None")
            if self.body_ground_map is None:
                raise ValueError("residual requires a stable body_ground_map")
        if self.revision_proposal is not None:
            if not isinstance(self.revision_proposal, NavRevisionProposalV1):
                raise TypeError("revision_proposal must be NavRevisionProposalV1 or None")
            if self.residual is None or self.revision_proposal.residual != self.residual:
                raise ValueError("revision_proposal must describe residual")

    @property
    def body_state(self) -> NavBodyStateEvidenceV1:
        """Compatibility alias for the current evidence-derived body state."""
        return self.evidence_body_state

    @property
    def evidence_body_ground_ref(self) -> NavMapRefV1:
        """Return the transient evidence-map reference for this observation."""
        return _map_ref(self.evidence_body_ground_map)

    @property
    def root_ref(self) -> Optional[NavMapRefV1]:
        """Return the maintained shadow-root reference, or None when invalidated."""
        if not self.maintained or self.root_map is None:
            return None
        return _map_ref(self.root_map)

    @property
    def body_ground_ref(self) -> Optional[NavMapRefV1]:
        """Return the maintained SELF-ground reference, or None when invalidated."""
        if not self.maintained or self.body_ground_map is None:
            return None
        return _map_ref(self.body_ground_map)

    @property
    def last_stable_root_ref(self) -> Optional[NavMapRefV1]:
        """Return the last stable root content reference, independent of maintenance."""
        return _map_ref(self.root_map) if self.root_map is not None else None

    @property
    def last_stable_body_ground_ref(self) -> Optional[NavMapRefV1]:
        """Return the last stable SELF-ground content reference."""
        return _map_ref(self.body_ground_map) if self.body_ground_map is not None else None

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe trace record for evidence and maintenance."""
        evidence_state = self.evidence_body_state.as_dict()
        stable_state = self.stable_body_state.as_dict() if self.stable_body_state is not None else None
        maintained_state = stable_state if self.maintained else None
        root_ref = _optional_ref_dict(self.root_ref)
        body_ref = _optional_ref_dict(self.body_ground_ref)
        last_root_ref = _optional_ref_dict(self.last_stable_root_ref)
        last_body_ref = _optional_ref_dict(self.last_stable_body_ground_ref)
        residual_dict = self.residual.as_dict() if self.residual is not None else None
        proposal_dict = _revision_proposal_summary(self.revision_proposal)
        return {
            "schema": "navmap_v2_shadow_state_v2",
            "authority": "shadow_only",
            "legacy_authority": "bodymap",
            "observation_no": self.observation_no,
            "evidence_body_ground_ref": self.evidence_body_ground_ref.as_dict(),
            "evidence_body_ground_content_signature": self.evidence_body_ground_map.content_signature(),
            "root_ref": root_ref,
            "body_ground_ref": body_ref,
            "last_stable_root_ref": last_root_ref,
            "last_stable_body_ground_ref": last_body_ref,
            "root_content_signature": self.root_map.content_signature() if self.root_map is not None else None,
            "body_ground_content_signature": (
                self.body_ground_map.content_signature() if self.body_ground_map is not None else None
            ),
            "body_state": evidence_state,
            "evidence_body_state": evidence_state,
            "maintained_body_state": maintained_state,
            "last_stable_body_state": stable_state,
            "current_shadow_maintained": self.maintained,
            "support_status": self.support_status,
            "support_age_observations": self.support_age_observations,
            "max_missing_observations": self.max_missing_observations,
            "last_supported_observation_no": self.last_supported_observation_no,
            "maintenance_action": self.maintenance_action,
            "evidence_relation": self.evidence_relation,
            "structured_residual": residual_dict,
            "revision_proposal": proposal_dict,
            "legacy_bodymap_posture": self.legacy_bodymap_posture,
            "comparison": self.evidence_comparison,
            "evidence_comparison": self.evidence_comparison,
            "maintained_comparison": self.maintained_comparison,
            "changed": self.changed,
            "input_classification": self.input_classification,
            "source_adapter": _ADAPTER_SOURCE_REF,
            "adapter_limitation": "canonical_geometry_selected_from_interpreted_observation",
            "evidence_lifecycle": "transient_observation_packet",
            "maintenance": {
                "action": self.maintenance_action,
                "maintained": self.maintained,
                "support_status": self.support_status,
                "support_age_observations": self.support_age_observations,
                "max_missing_observations": self.max_missing_observations,
                "last_supported_observation_no": self.last_supported_observation_no,
            },
        }


# Compatibility name for the Phase 2A public import. The runtime record itself is
# now the Phase 2B V2 schema above.
NavMapV2ShadowStateV1 = NavMapV2ShadowStateV2


def navmap_v2_shadow_body_thresholds_v1() -> NavBodyStateThresholdsV1:
    """Return explicit engineering thresholds for the Phase 2 shadow fixture.

    These values describe normalized canonical geometry used by this adapter.
    They are inspectable software parameters, not goat biological constants.
    """
    return NavBodyStateThresholdsV1(
        contact_tolerance=0.05,
        lateral_distance_threshold=0.25,
        upright_angle_tolerance_degrees=20.0,
        parallel_angle_tolerance_degrees=20.0,
        minimum_standing_head_elevation=1.0,
        maximum_fallen_head_elevation=0.35,
        maximum_standing_lateral_fraction=0.25,
        minimum_fallen_lateral_fraction=0.75,
    )


def navmap_v2_shadow_match_thresholds_v1() -> NavMatchThresholdsV1:
    """Return explicit thresholds for maintained-map versus evidence matching."""
    return NavMatchThresholdsV1(
        maximum_alignment_rms_error=2.0,
        maximum_geometry_rms_error=0.05,
        maximum_geometry_point_error=0.08,
        maximum_activation_strength_delta=0.05,
        minimum_correspondence_coverage=0.25,
        minimum_rank_score=0.20,
        ambiguity_margin=0.05,
        maximum_candidate_count=8,
    )


def navmap_v2_shadow_revision_thresholds_v1() -> NavRevisionThresholdsV1:
    """Return explicit KEEP/REVISE thresholds for the Phase 2B shadow."""
    return NavRevisionThresholdsV1(
        minimum_keep_score=0.99,
        minimum_revise_score=0.30,
        minimum_revise_coverage=0.50,
        maximum_reject_all_score=0.10,
    )


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Validate one non-empty text field."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Validate one non-negative integer field."""
    if not isinstance(value, int) or isinstance(value, bool) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Validate one positive integer field."""
    if not isinstance(value, int) or isinstance(value, bool) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the stable reference for one immutable map revision."""
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return a JSON-safe optional map reference."""
    return ref.as_dict() if ref is not None else None


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


def _provenance(*, source_ref: str, quality: float) -> NavProvenanceV1:
    """Return deterministic inferred provenance for one shadow map."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=source_ref,
        quality=quality,
    )


def _frame(frame_id: str) -> NavFrameV1:
    """Return the normalized sagittal frame used by the first shadow slices."""
    return NavFrameV1(
        frame_id=frame_id,
        x_axis="forward",
        y_axis="up",
        units="normalized",
        min_x=-3.0,
        max_x=3.0,
        min_y=-0.5,
        max_y=2.5,
    )


def _point(x: float, y: float) -> NavPointV1:
    """Return one concise immutable point."""
    return NavPointV1(x=x, y=y)


def _geometry(kind: NavGeometryKindV1, *points: NavPointV1) -> NavGeometryV1:
    """Return one immutable geometry record."""
    return NavGeometryV1(kind=kind, points=tuple(points))


def _activation(name: str, provenance: NavProvenanceV1) -> tuple[NavActivationV1, ...]:
    """Return one stable decoded activation tuple for a fixture element."""
    return (NavActivationV1(name=name, strength=1.0, provenance=provenance),)


def _observation_classification(env_obs: EnvObservation) -> str:
    """Classify currently interpreted posture evidence without creating belief.

    The result selects canonical geometry for this engineering adapter only.
    Conflicting or absent evidence remains unknown rather than being forced into
    one body configuration.
    """
    predicates = set(getattr(env_obs, "predicates", []) or [])
    has_standing = "posture:standing" in predicates
    has_fallen = "posture:fallen" in predicates
    if has_standing and not has_fallen:
        return "upright_input"
    if has_fallen and not has_standing:
        return "lateral_input"
    if has_standing and has_fallen:
        return "conflicting_input"
    return "unknown_input"


def _body_elements(
    classification: str,
    provenance: NavProvenanceV1,
) -> tuple[NavElementV1, ...]:
    """Return the canonical SELF-ground element set for one input class."""
    ground = NavElementV1(
        element_id="ground_surface",
        role="support_surface",
        geometry=_geometry(NavGeometryKindV1.SEGMENT, _point(-3.0, 0.0), _point(3.0, 0.0)),
        activations=_activation("support_surface", provenance),
        parent_element_id=None,
        provenance=provenance,
    )
    if classification == "upright_input":
        body_geometry = _geometry(NavGeometryKindV1.SEGMENT, _point(0.0, 0.2), _point(0.0, 2.0))
        head_geometry = _geometry(NavGeometryKindV1.POINT, _point(0.0, 2.2))
        foot_geometry = _geometry(NavGeometryKindV1.POINT, _point(0.0, 0.0))
    elif classification == "lateral_input":
        body_geometry = _geometry(NavGeometryKindV1.SEGMENT, _point(-1.0, 0.2), _point(1.0, 0.2))
        head_geometry = _geometry(NavGeometryKindV1.POINT, _point(-1.2, 0.2))
        foot_geometry = _geometry(NavGeometryKindV1.POINT, _point(1.2, 0.0))
    else:
        return (ground,)

    body = NavElementV1(
        element_id="self_body",
        role="self_body_axis",
        geometry=body_geometry,
        activations=_activation("self_structure", provenance),
        parent_element_id=None,
        provenance=provenance,
    )
    head = NavElementV1(
        element_id="self_head",
        role="self_head_part",
        geometry=head_geometry,
        activations=_activation("self_structure", provenance),
        parent_element_id="self_body",
        provenance=provenance,
    )
    foot = NavElementV1(
        element_id="self_foot",
        role="self_foot_part",
        geometry=foot_geometry,
        activations=_activation("self_structure", provenance),
        parent_element_id="self_body",
        provenance=provenance,
    )
    return (body, head, foot, ground)


def _body_ground_map_from_observation(
    env_obs: EnvObservation,
    *,
    map_id: str,
    revision: int,
    parent_ref: Optional[NavMapRefV1],
    source_ref: str,
) -> tuple[NavMapV2, str]:
    """Build one authority-neutral SELF-ground map from interpreted input."""
    if not isinstance(env_obs, EnvObservation):
        raise TypeError("env_obs must be EnvObservation")
    classification = _observation_classification(env_obs)
    quality = 0.75 if classification in {"upright_input", "lateral_input"} else 0.25
    provenance = _provenance(source_ref=source_ref, quality=quality)
    navmap = NavMapV2(
        map_id=map_id,
        revision=revision,
        parent_ref=parent_ref,
        role="self_ground",
        frame=_frame(_BODY_FRAME_ID),
        provenance=provenance,
        elements=_body_elements(classification, provenance),
    )
    return navmap, classification


def navmap_v2_body_ground_from_observation_v1(
    env_obs: EnvObservation,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1] = None,
) -> tuple[NavMapV2, str]:
    """Adapt interpreted posture evidence into a stable-family map candidate.

    This compatibility helper retains the Phase 2A public API. Runtime Phase 2B
    uses a separate transient evidence-map identity before deciding whether the
    stable maintained family should be created, reused, revised, or invalidated.
    """
    return _body_ground_map_from_observation(
        env_obs,
        map_id=_BODY_MAP_ID,
        revision=revision,
        parent_ref=parent_ref,
        source_ref=_ADAPTER_SOURCE_REF,
    )


def navmap_v2_body_ground_evidence_from_observation_v1(
    env_obs: EnvObservation,
    *,
    observation_no: int,
) -> tuple[NavMapV2, str]:
    """Create one uniquely addressable transient evidence map.

    Each observation packet receives a deterministic map identity and revision
    1. Equivalent evidence packets may therefore be distinct source events while
    the maintained stable map revision remains unchanged. The evidence maps are
    retained only as the latest packet plus bounded JSON trace telemetry.
    """
    _require_positive_int(observation_no, field_name="observation_no")
    map_id = f"{_EVIDENCE_MAP_ID_PREFIX}_o{observation_no:06d}"
    source_ref = f"{_ADAPTER_SOURCE_REF}:observation:{observation_no}"
    return _body_ground_map_from_observation(
        env_obs,
        map_id=map_id,
        revision=1,
        parent_ref=None,
        source_ref=source_ref,
    )


def _stable_body_map_from_evidence(
    evidence_map: NavMapV2,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1],
) -> NavMapV2:
    """Copy evidence content into the stable maintained map family."""
    return NavMapV2(
        map_id=_BODY_MAP_ID,
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


def navmap_v2_root_shadow_from_body_ground_v1(
    body_ground_map: NavMapV2,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1] = None,
) -> NavMapV2:
    """Create a minimal root-WNM shadow linking the SELF-ground submap.

    The root is an addressable diagnostic record only. Its link does not
    retrieve, focus, accept, or authorize the target map.
    """
    if not isinstance(body_ground_map, NavMapV2):
        raise TypeError("body_ground_map must be NavMapV2")
    provenance = _provenance(source_ref=_ROOT_SOURCE_REF, quality=body_ground_map.provenance.quality)
    self_anchor = NavElementV1(
        element_id="self_context",
        role="self_context_anchor",
        geometry=_geometry(NavGeometryKindV1.POINT, _point(0.0, 0.0)),
        activations=_activation("self_related", provenance),
        parent_element_id=None,
        provenance=provenance,
    )
    return NavMapV2(
        map_id=_ROOT_MAP_ID,
        revision=revision,
        parent_ref=parent_ref,
        role="root_scene",
        frame=_frame(_ROOT_FRAME_ID),
        provenance=provenance,
        elements=(self_anchor,),
        links=(
            NavMapLinkV1(
                link_type=_BODY_LINK_TYPE,
                target_ref=_map_ref(body_ground_map),
                source_element_id="self_context",
                provenance=provenance,
            ),
        ),
    )


def _body_state(navmap: NavMapV2) -> NavBodyStateEvidenceV1:
    """Derive body-state evidence from one SELF-ground map."""
    return body_state_evidence(
        navmap,
        body_element_id="self_body",
        head_element_id="self_head",
        foot_element_id="self_foot",
        ground_element_id="ground_surface",
        thresholds=navmap_v2_shadow_body_thresholds_v1(),
    )


def _bodymap_posture_from_ctx(ctx: Any) -> Optional[str]:
    """Read the legacy BodyMap posture slot without importing controller code."""
    body_world = getattr(ctx, "body_world", None)
    body_ids = getattr(ctx, "body_ids", {}) or {}
    if body_world is None or not isinstance(body_ids, dict):
        return None
    posture_id = body_ids.get("posture")
    if not isinstance(posture_id, str):
        return None
    binding = getattr(body_world, "_bindings", {}).get(posture_id)  # pylint: disable=protected-access
    if binding is None:
        return None
    tags = set(getattr(binding, "tags", ()) or ())
    standing = "pred:posture:standing" in tags
    fallen = "pred:posture:fallen" in tags
    resting = "pred:resting" in tags or "resting" in tags
    if standing and fallen:
        return "ambiguous"
    if standing:
        return "standing"
    if fallen:
        return "fallen"
    if resting:
        return "resting"
    return None


def _comparison(
    interpretation: NavBodyStateInterpretationV1,
    legacy_posture: Optional[str],
) -> str:
    """Compare a map-derived body state with the authoritative BodyMap readout."""
    if legacy_posture is None or legacy_posture in {"ambiguous", "resting"}:
        return "not_comparable"
    if interpretation is NavBodyStateInterpretationV1.UNKNOWN:
        return "map_unknown"
    if interpretation is NavBodyStateInterpretationV1.AMBIGUOUS:
        return "map_ambiguous"
    if interpretation is NavBodyStateInterpretationV1.STANDING_LIKE:
        return "agree" if legacy_posture == "standing" else "disagree"
    if interpretation is NavBodyStateInterpretationV1.FALLEN_LIKE:
        return "agree" if legacy_posture == "fallen" else "disagree"
    return "not_comparable"


def _next_observation_no(ctx: Any) -> int:
    """Advance and return the deterministic Phase 2B observation counter."""
    try:
        current = int(getattr(ctx, "navmap_v2_shadow_observation_no", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    observation_no = max(0, current) + 1
    ctx.navmap_v2_shadow_observation_no = observation_no
    return observation_no


def _max_missing_observations(ctx: Any) -> int:
    """Return the declared bounded maintenance limit from the context."""
    try:
        value = int(
            getattr(
                ctx,
                "navmap_v2_shadow_max_missing_observations",
                _DEFAULT_MAX_MISSING_OBSERVATIONS,
            )
        )
    except (TypeError, ValueError):
        return _DEFAULT_MAX_MISSING_OBSERVATIONS
    return value if value >= 0 else _DEFAULT_MAX_MISSING_OBSERVATIONS


def _previous_stable_maps(ctx: Any) -> tuple[Optional[NavMapV2], Optional[NavMapV2]]:
    """Return valid prior stable body/root maps from the runtime context."""
    body_map = getattr(ctx, "navmap_v2_shadow_body_ground", None)
    root_map = getattr(ctx, "navmap_v2_shadow_root", None)
    if not isinstance(body_map, NavMapV2):
        body_map = None
    if not isinstance(root_map, NavMapV2):
        root_map = None
    if body_map is None or root_map is None:
        return None, None
    return body_map, root_map


def _previous_state(ctx: Any) -> Optional[NavMapV2ShadowStateV2]:
    """Return the previous Phase 2B transaction record when available."""
    value = getattr(ctx, "navmap_v2_shadow_state", None)
    return value if isinstance(value, NavMapV2ShadowStateV2) else None


def _compare_complete_evidence(
    base_map: NavMapV2,
    evidence_map: NavMapV2,
) -> tuple[NavStructuredResidualV1, NavRevisionProposalV1]:
    """Match complete evidence to the stable map and produce a pure proposal."""
    match_result = match_navmaps(
        base_map,
        evidence_map,
        thresholds=navmap_v2_shadow_match_thresholds_v1(),
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
        thresholds=navmap_v2_shadow_revision_thresholds_v1(),
    )
    return residual, proposal


def _new_root_for_body(
    body_map: NavMapV2,
    previous_root: Optional[NavMapV2],
) -> NavMapV2:
    """Create the first root or a child root linking a revised body map."""
    if previous_root is None:
        return navmap_v2_root_shadow_from_body_ground_v1(body_map, revision=1)
    return navmap_v2_root_shadow_from_body_ground_v1(
        body_map,
        revision=previous_root.revision + 1,
        parent_ref=_map_ref(previous_root),
    )


def _last_supported_observation_no(
    previous_state: Optional[NavMapV2ShadowStateV2],
    *,
    previous_body: Optional[NavMapV2],
    observation_no: int,
) -> Optional[int]:
    """Recover the prior support marker, including a defensive Phase 2A bridge."""
    if previous_state is not None:
        return previous_state.last_supported_observation_no
    if previous_body is not None:
        return max(1, observation_no - 1)
    return None


def _missing_maintenance_result(
    *,
    classification: str,
    previous_body: Optional[NavMapV2],
    previous_state: Optional[NavMapV2ShadowStateV2],
    observation_no: int,
    max_missing: int,
) -> tuple[bool, str, int, Optional[int], str, str]:
    """Apply the bounded missing/ambiguous support-aging rule.

    Returns ``maintained``, ``support_status``, ``support_age``,
    ``last_supported``, ``maintenance_action``, and public update ``status``.
    """
    evidence_kind = "ambiguous" if classification == "conflicting_input" else "missing"
    last_supported = _last_supported_observation_no(
        previous_state,
        previous_body=previous_body,
        observation_no=observation_no,
    )
    if previous_body is None or last_supported is None:
        return False, "uninitialized", 0, None, f"defer_{evidence_kind}", "deferred"

    support_age = max(1, observation_no - last_supported)
    if support_age > max_missing:
        return (
            False,
            "invalidated",
            support_age,
            last_supported,
            f"invalidate_{evidence_kind}",
            "invalidated",
        )
    support_status = "stale" if support_age == max_missing else "aging"
    return (
        True,
        support_status,
        support_age,
        last_supported,
        f"maintain_{evidence_kind}",
        "maintained",
    )


def _append_history(ctx: Any, row: dict[str, Any]) -> None:
    """Append one bounded JSON-safe shadow trace to the runtime context."""
    history = getattr(ctx, "navmap_v2_shadow_history", [])
    if not isinstance(history, list):
        history = []
    history = [dict(item) for item in history if isinstance(item, dict)]
    history.append(dict(row))
    try:
        limit = int(getattr(ctx, "navmap_v2_shadow_history_limit", 25) or 25)
    except (TypeError, ValueError):
        limit = 25
    if limit <= 0:
        limit = 25
    ctx.navmap_v2_shadow_history = history[-limit:]


def navmap_v2_shadow_observation_step_v1(ctx: Any, env_obs: EnvObservation) -> dict[str, Any]:
    """Process one observation through the Phase 2B shadow-maintenance path.

    Complete compatible evidence refreshes support and reuses the stable map
    revision. Complete contradictory evidence is matched structurally, produces
    a revision proposal, and revises the stable SELF-ground/root map families.
    Missing or conflicting evidence remains UNKNOWN, ages external support, and
    eventually invalidates current shadow participation under the declared
    bounded rule. BodyMap remains authoritative throughout.
    """
    if ctx is None or env_obs is None:
        return {}
    if not bool(getattr(ctx, "navmap_v2_shadow_enabled", True)):
        return {
            "schema": "navmap_v2_shadow_update_v2",
            "status": "disabled",
            "authority": "shadow_only",
            "legacy_authority": "bodymap",
        }

    observation_no = _next_observation_no(ctx)
    max_missing = _max_missing_observations(ctx)
    evidence_map, classification = navmap_v2_body_ground_evidence_from_observation_v1(
        env_obs,
        observation_no=observation_no,
    )
    evidence_state = _body_state(evidence_map)
    legacy_posture = _bodymap_posture_from_ctx(ctx)
    evidence_comparison = _comparison(evidence_state.interpretation, legacy_posture)

    previous_body, previous_root = _previous_stable_maps(ctx)
    previous_shadow_state = _previous_state(ctx)
    body_map = previous_body
    root_map = previous_root
    residual: Optional[NavStructuredResidualV1] = None
    proposal: Optional[NavRevisionProposalV1] = None
    changed = False
    last_supported: Optional[int]

    complete_interpretations = {
        NavBodyStateInterpretationV1.STANDING_LIKE,
        NavBodyStateInterpretationV1.FALLEN_LIKE,
    }
    evidence_complete = evidence_state.interpretation in complete_interpretations

    if evidence_complete and previous_body is None:
        body_map = _stable_body_map_from_evidence(
            evidence_map,
            revision=1,
            parent_ref=None,
        )
        root_map = _new_root_for_body(body_map, None)
        maintained = True
        support_status = "fresh"
        support_age = 0
        last_supported = observation_no
        maintenance_action = "create"
        evidence_relation = "initial_support"
        status = "created"
        changed = True
    elif evidence_complete and previous_body is not None:
        residual, proposal = _compare_complete_evidence(previous_body, evidence_map)
        if proposal.decision is NavRevisionDecisionV1.KEEP:
            body_map = previous_body
            root_map = previous_root
            maintained = True
            support_status = "fresh"
            support_age = 0
            last_supported = observation_no
            previously_maintained = previous_shadow_state.maintained if previous_shadow_state is not None else True
            maintenance_action = "refresh" if previously_maintained else "reinstate"
            evidence_relation = "compatible"
            status = "reused" if previously_maintained else "reinstated"
        elif proposal.decision is NavRevisionDecisionV1.REVISE:
            body_map = apply_revision(
                previous_body,
                evidence_map,
                proposal,
                new_revision=previous_body.revision + 1,
            )
            root_map = _new_root_for_body(body_map, previous_root)
            maintained = True
            support_status = "fresh"
            support_age = 0
            last_supported = observation_no
            maintenance_action = "revise"
            evidence_relation = "contradictory"
            status = "revised"
            changed = True
        else:
            body_map = previous_body
            root_map = previous_root
            maintained = False
            support_status = "unresolved"
            support_age = 0
            last_supported = _last_supported_observation_no(
                previous_shadow_state,
                previous_body=previous_body,
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
            classification=classification,
            previous_body=previous_body,
            previous_state=previous_shadow_state,
            observation_no=observation_no,
            max_missing=max_missing,
        )
        evidence_relation = "ambiguous" if classification == "conflicting_input" else "missing"

    stable_state = _body_state(body_map) if body_map is not None else None
    if maintained and stable_state is not None:
        maintained_comparison = _comparison(stable_state.interpretation, legacy_posture)
    else:
        maintained_comparison = "not_maintained"

    state = NavMapV2ShadowStateV2(
        evidence_body_ground_map=evidence_map,
        evidence_body_state=evidence_state,
        root_map=root_map,
        body_ground_map=body_map,
        stable_body_state=stable_state,
        maintained=maintained,
        support_status=support_status,
        support_age_observations=support_age,
        max_missing_observations=max_missing,
        last_supported_observation_no=last_supported,
        maintenance_action=maintenance_action,
        evidence_relation=evidence_relation,
        residual=residual,
        revision_proposal=proposal,
        legacy_bodymap_posture=legacy_posture,
        evidence_comparison=evidence_comparison,
        maintained_comparison=maintained_comparison,
        changed=changed,
        input_classification=classification,
        observation_no=observation_no,
    )
    row = state.as_dict()
    row.update(
        {
            "schema": "navmap_v2_shadow_update_v2",
            "status": status,
            "controller_steps": getattr(ctx, "controller_steps", None),
            "ticks": getattr(ctx, "ticks", None),
        }
    )

    ctx.navmap_v2_shadow_evidence_body_ground = evidence_map
    ctx.navmap_v2_shadow_body_ground = body_map
    ctx.navmap_v2_shadow_root = root_map
    ctx.navmap_v2_shadow_state = state
    ctx.navmap_v2_shadow_last_update = dict(row)
    _append_history(ctx, row)
    return row


def navmap_v2_shadow_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe summary of the latest V2 shadow update."""
    if ctx is None:
        return {
            "schema": "navmap_v2_shadow_summary_v2",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_v2_shadow_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "navmap_v2_shadow_summary_v2",
            "status": "idle",
            "history_count": len(getattr(ctx, "navmap_v2_shadow_history", []) or []),
        }
    out = dict(row)
    out["schema"] = "navmap_v2_shadow_summary_v2"
    out["history_count"] = len(getattr(ctx, "navmap_v2_shadow_history", []) or [])
    return out


def _ref_text(value: Any) -> str:
    """Render one optional JSON map-reference dictionary."""
    if not isinstance(value, dict):
        return "(none)"
    return f"{value.get('map_id', '?')}@r{value.get('revision', '?')}"


def render_navmap_v2_shadow_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 2B evidence/maintenance lines."""
    summary = navmap_v2_shadow_summary_v1(ctx)
    lines = ["NAVMAP V2 SHADOW:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle"}:
        lines.append(f"  status={status}")
        return lines
    if status == "disabled":
        lines.append("  status=disabled authority=shadow_only legacy_authority=bodymap")
        return lines

    evidence_state = summary.get("evidence_body_state")
    if not isinstance(evidence_state, dict):
        evidence_state = {}
    maintained_state = summary.get("maintained_body_state")
    if not isinstance(maintained_state, dict):
        maintained_state = {}
    last_stable_state = summary.get("last_stable_body_state")
    if not isinstance(last_stable_state, dict):
        last_stable_state = {}

    lines.append(
        "  "
        f"status={status} changed={summary.get('changed')} "
        "authority=shadow_only legacy_authority=bodymap"
    )
    lines.append(
        "  "
        f"evidence={_ref_text(summary.get('evidence_body_ground_ref'))} "
        f"derived={evidence_state.get('interpretation', 'unknown')} "
        f"input={summary.get('input_classification')}"
    )
    lines.append(
        "  "
        f"maintained={summary.get('current_shadow_maintained')} "
        f"action={summary.get('maintenance_action')} "
        f"support={summary.get('support_status')} "
        f"age={summary.get('support_age_observations')}/{summary.get('max_missing_observations')}"
    )
    lines.append(
        "  "
        f"current root={_ref_text(summary.get('root_ref'))} "
        f"body={_ref_text(summary.get('body_ground_ref'))} "
        f"derived={maintained_state.get('interpretation', 'unknown')}"
    )
    if not summary.get("current_shadow_maintained") and summary.get("last_stable_body_ground_ref") is not None:
        lines.append(
            "  "
            f"last_stable root={_ref_text(summary.get('last_stable_root_ref'))} "
            f"body={_ref_text(summary.get('last_stable_body_ground_ref'))} "
            f"derived={last_stable_state.get('interpretation', 'unknown')}"
        )
    lines.append(
        "  "
        f"legacy={summary.get('legacy_bodymap_posture')} "
        f"comparison={summary.get('evidence_comparison')} "
        f"maintained_comparison={summary.get('maintained_comparison')}"
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
