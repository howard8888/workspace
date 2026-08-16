# -*- coding: utf-8 -*-
"""Phase 2 shadow construction for the relational-spatial NavMapV2 kernel.

Purpose
-------
This module provides the first runtime-facing ``NavMapV2`` bridge.  It adapts
CCA8's current interpreted ``EnvObservation`` posture evidence into a small
SELF-ground geometry, derives body-state evidence from that geometry, and
constructs a minimal root Working Navigation Map shadow that links to the
SELF-ground submap.

The adapter is deliberately honest about its limits.  Current observations do
not yet contain decoded body geometry, so standing/fallen predicates are used
to select one deterministic canonical geometry for the shadow experiment.  The
result proves runtime plumbing and map-derived readout behavior; it is not
presented as a model of biological perception.

Authority boundary
------------------
Everything in this module is shadow-only.  The legacy BodyMap remains the
current authority for safety and policy gating.  A root shadow reference is not
an accepted root WNM, and no function here writes WorldGraph truth, Columns,
PolicyRuntime state, controller choices, or environment state.
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
    NavPointV1,
    NavProvenanceV1,
    NavSourceClassV1,
    body_state_evidence,
)

__version__ = "0.1.0"

__all__ = [
    "NavMapV2ShadowStateV1",
    "navmap_v2_shadow_body_thresholds_v1",
    "navmap_v2_body_ground_from_observation_v1",
    "navmap_v2_root_shadow_from_body_ground_v1",
    "navmap_v2_shadow_observation_step_v1",
    "navmap_v2_shadow_summary_v1",
    "render_navmap_v2_shadow_lines_v1",
    "__version__",
]

_BODY_MAP_ID = "goat_self_ground_v2"
_ROOT_MAP_ID = "goat_root_scene_v2"
_BODY_FRAME_ID = "shadow_self_ground_frame_v1"
_ROOT_FRAME_ID = "shadow_root_wnm_frame_v1"
_BODY_LINK_TYPE = "self_ground_submap"
_ADAPTER_SOURCE_REF = "adapter:env_observation_to_self_ground_v1"
_ROOT_SOURCE_REF = "runtime:shadow_root_from_self_ground_v1"


@dataclass(frozen=True, slots=True)
class NavMapV2ShadowStateV1:
    """One immutable Phase 2 shadow state for the current observation.

    ``root_map`` and ``body_ground_map`` are current shadow records only.  They
    carry no policy, focus, accepted-current, or root-authority flag.  The
    legacy BodyMap comparison is diagnostic and cannot change either map.
    """

    root_map: NavMapV2
    body_ground_map: NavMapV2
    body_state: NavBodyStateEvidenceV1
    legacy_bodymap_posture: Optional[str]
    comparison: str
    changed: bool
    input_classification: str

    def __post_init__(self) -> None:
        if not isinstance(self.root_map, NavMapV2):
            raise TypeError("root_map must be NavMapV2")
        if not isinstance(self.body_ground_map, NavMapV2):
            raise TypeError("body_ground_map must be NavMapV2")
        if not isinstance(self.body_state, NavBodyStateEvidenceV1):
            raise TypeError("body_state must be NavBodyStateEvidenceV1")
        if self.body_state.source_map_ref != NavMapRefV1(
            self.body_ground_map.map_id,
            self.body_ground_map.revision,
        ):
            raise ValueError("body_state must describe body_ground_map")
        if not isinstance(self.changed, bool):
            raise TypeError("changed must be a bool")
        if self.legacy_bodymap_posture is not None and not isinstance(self.legacy_bodymap_posture, str):
            raise TypeError("legacy_bodymap_posture must be str or None")
        if not isinstance(self.comparison, str) or not self.comparison:
            raise ValueError("comparison must be a non-empty string")
        if not isinstance(self.input_classification, str) or not self.input_classification:
            raise ValueError("input_classification must be a non-empty string")

    @property
    def root_ref(self) -> NavMapRefV1:
        """Return the current shadow root reference without granting authority."""
        return NavMapRefV1(self.root_map.map_id, self.root_map.revision)

    @property
    def body_ground_ref(self) -> NavMapRefV1:
        """Return the current SELF-ground shadow reference."""
        return NavMapRefV1(self.body_ground_map.map_id, self.body_ground_map.revision)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe trace record for the shadow state."""
        return {
            "schema": "navmap_v2_shadow_state_v1",
            "authority": "shadow_only",
            "legacy_authority": "bodymap",
            "root_ref": self.root_ref.as_dict(),
            "body_ground_ref": self.body_ground_ref.as_dict(),
            "root_content_signature": self.root_map.content_signature(),
            "body_ground_content_signature": self.body_ground_map.content_signature(),
            "body_state": self.body_state.as_dict(),
            "legacy_bodymap_posture": self.legacy_bodymap_posture,
            "comparison": self.comparison,
            "changed": self.changed,
            "input_classification": self.input_classification,
            "source_adapter": _ADAPTER_SOURCE_REF,
            "adapter_limitation": "canonical_geometry_selected_from_interpreted_observation",
        }


def navmap_v2_shadow_body_thresholds_v1() -> NavBodyStateThresholdsV1:
    """Return explicit engineering thresholds for the Phase 2 shadow fixture.

    These values describe the normalized canonical geometry used by this
    adapter.  They are inspectable software parameters, not goat biological
    constants.
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


def _provenance(*, source_ref: str, quality: float) -> NavProvenanceV1:
    """Return deterministic inferred provenance for one shadow map."""
    return NavProvenanceV1(
        source_class=NavSourceClassV1.INFERRED,
        source_ref=source_ref,
        quality=quality,
    )


def _frame(frame_id: str) -> NavFrameV1:
    """Return the normalized sagittal frame used by the first shadow slice."""
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
    Conflicting or absent evidence remains ``unknown`` rather than being forced
    into one body configuration.
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


def navmap_v2_body_ground_from_observation_v1(
    env_obs: EnvObservation,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1] = None,
) -> tuple[NavMapV2, str]:
    """Adapt interpreted EnvObservation posture evidence into SELF-ground geometry.

    The returned map contains no authoritative posture, standing, or fallen
    field/activation.  Recognized inputs select one canonical geometry; missing
    or conflicting posture evidence yields an incomplete map whose later
    body-state interpretation is ``UNKNOWN``.
    """
    if not isinstance(env_obs, EnvObservation):
        raise TypeError("env_obs must be EnvObservation")
    classification = _observation_classification(env_obs)
    quality = 0.75 if classification in {"upright_input", "lateral_input"} else 0.25
    provenance = _provenance(source_ref=_ADAPTER_SOURCE_REF, quality=quality)
    navmap = NavMapV2(
        map_id=_BODY_MAP_ID,
        revision=revision,
        parent_ref=parent_ref,
        role="self_ground_evidence",
        frame=_frame(_BODY_FRAME_ID),
        provenance=provenance,
        elements=_body_elements(classification, provenance),
    )
    return navmap, classification


def navmap_v2_root_shadow_from_body_ground_v1(
    body_ground_map: NavMapV2,
    *,
    revision: int,
    parent_ref: Optional[NavMapRefV1] = None,
) -> NavMapV2:
    """Create a minimal root-WNM shadow linking the SELF-ground submap.

    The root is an addressable diagnostic record only.  Its link does not
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
                target_ref=NavMapRefV1(body_ground_map.map_id, body_ground_map.revision),
                source_element_id="self_context",
                provenance=provenance,
            ),
        ),
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


def _next_revision(previous: Optional[NavMapV2]) -> tuple[int, Optional[NavMapRefV1]]:
    """Return the next revision and parent reference for one stable map family."""
    if previous is None:
        return 1, None
    return previous.revision + 1, NavMapRefV1(previous.map_id, previous.revision)


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
    """Update the current root/SELF-ground NavMapV2 shadows from one observation.

    New immutable revisions are created only when decoded map content changes.
    Repeated equivalent observations reuse the previous revisions.  All state is
    stored on ``ctx`` for diagnostics; the BodyMap remains authoritative.
    """
    if ctx is None or env_obs is None:
        return {}
    if not bool(getattr(ctx, "navmap_v2_shadow_enabled", True)):
        return {
            "schema": "navmap_v2_shadow_update_v1",
            "status": "disabled",
            "authority": "shadow_only",
            "legacy_authority": "bodymap",
        }

    previous_body = getattr(ctx, "navmap_v2_shadow_body_ground", None)
    if not isinstance(previous_body, NavMapV2):
        previous_body = None
    body_revision, body_parent = _next_revision(previous_body)
    body_candidate, classification = navmap_v2_body_ground_from_observation_v1(
        env_obs,
        revision=body_revision,
        parent_ref=body_parent,
    )
    if previous_body is None or body_candidate.content_signature() != previous_body.content_signature():
        body_map = body_candidate
        body_changed = True
    else:
        body_map = previous_body
        body_changed = False

    previous_root = getattr(ctx, "navmap_v2_shadow_root", None)
    if not isinstance(previous_root, NavMapV2):
        previous_root = None
    root_revision, root_parent = _next_revision(previous_root)
    root_candidate = navmap_v2_root_shadow_from_body_ground_v1(
        body_map,
        revision=root_revision,
        parent_ref=root_parent,
    )
    if previous_root is None or root_candidate.content_signature() != previous_root.content_signature():
        root_map = root_candidate
        root_changed = True
    else:
        root_map = previous_root
        root_changed = False

    thresholds = navmap_v2_shadow_body_thresholds_v1()
    body_state = body_state_evidence(
        body_map,
        body_element_id="self_body",
        head_element_id="self_head",
        foot_element_id="self_foot",
        ground_element_id="ground_surface",
        thresholds=thresholds,
    )
    legacy_posture = _bodymap_posture_from_ctx(ctx)
    comparison = _comparison(body_state.interpretation, legacy_posture)
    changed = body_changed or root_changed
    state = NavMapV2ShadowStateV1(
        root_map=root_map,
        body_ground_map=body_map,
        body_state=body_state,
        legacy_bodymap_posture=legacy_posture,
        comparison=comparison,
        changed=changed,
        input_classification=classification,
    )
    row = state.as_dict()
    row.update(
        {
            "schema": "navmap_v2_shadow_update_v1",
            "status": "created" if previous_body is None else ("revised" if changed else "reused"),
            "controller_steps": getattr(ctx, "controller_steps", None),
            "ticks": getattr(ctx, "ticks", None),
        }
    )

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
            "schema": "navmap_v2_shadow_summary_v1",
            "status": "ctx_unavailable",
        }
    row = getattr(ctx, "navmap_v2_shadow_last_update", None)
    if not isinstance(row, dict):
        return {
            "schema": "navmap_v2_shadow_summary_v1",
            "status": "idle",
            "history_count": len(getattr(ctx, "navmap_v2_shadow_history", []) or []),
        }
    out = dict(row)
    out["schema"] = "navmap_v2_shadow_summary_v1"
    out["history_count"] = len(getattr(ctx, "navmap_v2_shadow_history", []) or [])
    return out


def render_navmap_v2_shadow_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable lines for the current Phase 2 shadow."""
    summary = navmap_v2_shadow_summary_v1(ctx)
    lines = ["NAVMAP V2 SHADOW:"]
    status = summary.get("status")
    if status in {"ctx_unavailable", "idle"}:
        lines.append(f"  status={status}")
        return lines
    if status == "disabled":
        lines.append("  status=disabled authority=shadow_only legacy_authority=bodymap")
        return lines

    root_ref = summary.get("root_ref")
    if not isinstance(root_ref, dict):
        root_ref = {}
    body_ref = summary.get("body_ground_ref")
    if not isinstance(body_ref, dict):
        body_ref = {}
    body_state = summary.get("body_state")
    if not isinstance(body_state, dict):
        body_state = {}
    lines.append(
        "  "
        f"status={status} changed={summary.get('changed')} "
        "authority=shadow_only legacy_authority=bodymap"
    )
    lines.append(
        "  "
        f"root={root_ref.get('map_id', '?')}@r{root_ref.get('revision', '?')} "
        f"body={body_ref.get('map_id', '?')}@r{body_ref.get('revision', '?')}"
    )
    lines.append(
        "  "
        f"derived={body_state.get('interpretation', 'unknown')} "
        f"legacy={summary.get('legacy_bodymap_posture')} "
        f"comparison={summary.get('comparison')} "
        f"input={summary.get('input_classification')}"
    )
    return lines
