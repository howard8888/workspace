#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finite, read-only cognitive oscilloscope snapshots for CCA8.

Purpose
-------
This module implements the first diagnostic-instrumentation slice for Main
Menu item 3.  It samples the architectural service points defined by
``CCA8 High-Level Architecture v03`` and stores compact, JSON-safe snapshots
in a bounded ring buffer on :class:`cca8_context.Ctx`.

The oscilloscope is external to cognition.  No policy, Working Navigation Map,
memory-retrieval path, or behavioral primitive reads these records.  The
module observes existing source-linked runtime state and must not manufacture
missing intermediate signals merely to make every conceptual stage appear
active.

Scope of v0.2
-------------
- Stable DP00-DP18 diagnostic-port registry.
- One compact snapshot envelope correlated to cognitive-cycle, controller-step,
  environment-step, selected-action, and applied-action identifiers.
- Bounded in-memory retention, defaulting to 128 snapshots.
- Compact front-panel rendering for the complete DP00-DP18 signal path.
- Full stored-signal drill-down for one selected diagnostic point.
- Read-only terminal renderers for retained-history and raw all-port views.
- Honest ``implemented``, ``partial``, ``collapsed``, ``idle``, ``missing``,
  and ``error`` states.

Signal injection is intentionally not implemented in this phase.
"""

from __future__ import annotations

# The collectors intentionally read many optional migration-era registers and
# degrade to explicit diagnostic states instead of allowing reporting to crash.
# pylint: disable=broad-exception-caught
# pylint: disable=duplicate-code
# pylint: disable=protected-access
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-statements
# pylint: disable=unnecessary-lambda

from collections.abc import Callable, Iterable, Mapping
from dataclasses import asdict, dataclass, is_dataclass
from datetime import datetime
from enum import Enum
import json
import math
import textwrap
from typing import Any, Optional

import cca8_column
import cca8_feeding
import cca8_followmom_authority
import cca8_followmom_compare
import cca8_live_dynamics
import cca8_maternal_continuity
import cca8_maternal_geometry
import cca8_maternal_temporal
import cca8_navmap_memory
import cca8_navmap_runtime
import cca8_predictive
import cca8_terrain
import cca8_wnm_runtime
from cca8_controller import (
    body_cliff_distance,
    body_mom_distance,
    body_nipple_state,
    body_posture,
    body_shelter_distance,
    body_space_zone,
    bodymap_is_stale,
    skill_readout,
    skills_to_dict,
)

__version__ = "0.2.1"

__all__ = [
    "COGNITIVE_SCOPE_PORTS_V1",
    "CognitiveScopePortDefinitionV1",
    "build_cognitive_scope_snapshot_v1",
    "capture_cognitive_scope_snapshot_v1",
    "cognitive_scope_clear_v1",
    "cognitive_scope_find_port_v1",
    "cognitive_scope_find_snapshot_v1",
    "cognitive_scope_latest_snapshot_v1",
    "cognitive_scope_normalize_port_id_v1",
    "cognitive_scope_trace_summary_v1",
    "render_cognitive_scope_compact_snapshot_lines_v1",
    "render_cognitive_scope_port_detail_lines_v1",
    "render_cognitive_scope_snapshot_lines_v1",
    "render_cognitive_scope_trace_index_lines_v1",
    "__version__",
]


@dataclass(frozen=True, slots=True)
class CognitiveScopePortDefinitionV1:  # pylint: disable=too-few-public-methods
    """Stable architectural definition for one cognitive-scope service point.

    ``implementation`` describes the present software status rather than the
    conceptual importance of the module.  DP00 is an external simulation
    reference.  DP01-DP18 are the eighteen cognitive/architectural service
    points currently exposed by the v03 schematic.
    """

    port_id: str
    name: str
    implementation: str
    authority: str
    source: str


COGNITIVE_SCOPE_PORTS_V1: tuple[CognitiveScopePortDefinitionV1, ...] = (
    CognitiveScopePortDefinitionV1(
        "DP00", "External World / Body", "implemented", "external_simulation_truth", "HybridEnvironment.state"
    ),
    CognitiveScopePortDefinitionV1(
        "DP01", "Sensors / Transduction / Adapter", "implemented", "observed_evidence", "EnvObservation"
    ),
    CognitiveScopePortDefinitionV1(
        "DP02", "Input Sensory Vector Shaping", "collapsed", "sensory_processing", "PerceptionAdapter products"
    ),
    CognitiveScopePortDefinitionV1(
        "DP03", "Modality-Specific Sensory Association", "partial", "sensory_processing", "NavPatch/domain matches"
    ),
    CognitiveScopePortDefinitionV1(
        "DP04", "Local Sensory NavMaps", "partial", "observed_or_candidate_evidence", "NavPatch/evidence-map registers"
    ),
    CognitiveScopePortDefinitionV1(
        "DP05", "Sequential / Error Temporal Processing", "implemented", "derived_temporal_state", "SeqErr/live dynamics"
    ),
    CognitiveScopePortDefinitionV1(
        "DP06", "Object/Scene Segmentation + Evidence Gateway", "partial", "observed_or_maintained_evidence", "NavMap observation update"
    ),
    CognitiveScopePortDefinitionV1(
        "DP07", "Protected BodyMap", "implemented", "protected_fast_path", "Ctx.body_world/body query helpers"
    ),
    CognitiveScopePortDefinitionV1(
        "DP08", "Sparse Memory Activation", "implemented_scaffold", "retrieval_index", "Phase-8 sparse indexes; WorldGraph target"
    ),
    CognitiveScopePortDefinitionV1(
        "DP09", "Columns / Rich NavMap Reinstatement", "implemented", "long_term_content_or_retrieved", "cca8_column.mem"
    ),
    CognitiveScopePortDefinitionV1(
        "DP10", "Alignment / Comparison / Structured Residual", "partial", "comparison_or_proposal", "NavMap comparison registers"
    ),
    CognitiveScopePortDefinitionV1(
        "DP11", "One Operative WNM + Ready Set", "implemented", "accepted_current", "WNM runtime"
    ),
    CognitiveScopePortDefinitionV1(
        "DP12", "Drives / Goal / Emotion / Development", "partial", "compact_biological_control_state", "Drives + Ctx"
    ),
    CognitiveScopePortDefinitionV1(
        "DP13", "Policy / Primitive Selection + Arbitration", "implemented", "executive_selection", "PolicyRuntime debug transaction"
    ),
    CognitiveScopePortDefinitionV1(
        "DP14", "Selected Primitive Operates on WNM", "partial", "wnm_operation_result", "Domain authority/transition records"
    ),
    CognitiveScopePortDefinitionV1(
        "DP15", "Output Association / Lower Motor / HAL", "implemented_seam", "lower_execution_boundary", "Env action/HAL seam"
    ),
    CognitiveScopePortDefinitionV1(
        "DP16", "Expected-Successor / Prediction Store", "partial", "expected_only", "Prediction and pending expectation records"
    ),
    CognitiveScopePortDefinitionV1(
        "DP17", "Expected vs Later Evidence / Internal Outcome", "partial", "internally_computed_outcome", "Prediction/outcome records"
    ),
    CognitiveScopePortDefinitionV1(
        "DP18", "Learning / Revision / Memory Writeback", "partial", "learning_or_long_term_writeback", "Skills/NavMap memory/WorldGraph"
    ),
)

_PORT_BY_ID_V1 = {item.port_id: item for item in COGNITIVE_SCOPE_PORTS_V1}


def _json_safe(value: Any, *, depth: int = 0) -> Any:
    """Return a bounded JSON-safe copy suitable for an external diagnostic trace."""
    if depth > 6:
        return repr(value)
    if value is None or isinstance(value, (str, int, bool)):
        return value
    if isinstance(value, float):
        return value if math.isfinite(value) else repr(value)
    if isinstance(value, Enum):
        return value.value
    if is_dataclass(value) and not isinstance(value, type):
        try:
            return _json_safe(asdict(value), depth=depth + 1)
        except Exception:
            return repr(value)
    if isinstance(value, Mapping):
        return {
            str(key): _json_safe(item, depth=depth + 1)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_json_safe(item, depth=depth + 1) for item in value]
    if isinstance(value, set):
        rows = [_json_safe(item, depth=depth + 1) for item in value]
        return sorted(rows, key=lambda item: repr(item))
    as_dict = getattr(value, "as_dict", None)
    if callable(as_dict):
        try:
            return _json_safe(as_dict(), depth=depth + 1)
        except Exception:
            return repr(value)
    return repr(value)


def _compact_mapping(value: Any, *, limit: int = 12) -> dict[str, Any]:
    """Return at most ``limit`` stable entries from one mapping-like value."""
    if not isinstance(value, Mapping):
        return {}
    out: dict[str, Any] = {}
    for key in sorted(value, key=lambda item: str(item))[: max(0, int(limit))]:
        out[str(key)] = _json_safe(value[key])
    if len(value) > limit:
        out["_omitted_count"] = len(value) - limit
    return out


def _safe_call(fn: Callable[[], Any], default: Any = None) -> Any:
    """Call one diagnostic getter without allowing observation to crash runtime."""
    try:
        return fn()
    except Exception:
        return default


def _map_ref_row(value: Any) -> Optional[dict[str, Any]]:
    """Return a compact map reference for one optional NavMap-like object."""
    if value is None:
        return None
    map_id = getattr(value, "map_id", None)
    revision = getattr(value, "revision", None)
    role = getattr(value, "role", None)
    frame = getattr(value, "frame", None)
    frame_id = getattr(frame, "frame_id", None)
    if not isinstance(map_id, str):
        return None
    return {
        "map_id": map_id,
        "revision": revision,
        "role": role,
        "frame_id": frame_id,
    }


def _state_attrs(value: Any, names: Iterable[str]) -> dict[str, Any]:
    """Read a stable set of scalar-ish attributes from one runtime object."""
    if value is None:
        return {}
    out: dict[str, Any] = {}
    for name in names:
        raw = getattr(value, name, None)
        if raw is not None:
            out[name] = _json_safe(raw)
    return out


def _signal_status(signal: Mapping[str, Any], *, idle_when_empty: bool = True) -> str:
    """Return ``active`` or ``idle`` from one compact signal mapping."""
    if not signal and idle_when_empty:
        return "idle"
    return "active"


def _port_sample(
    port_id: str,
    signal: Mapping[str, Any],
    *,
    signal_status: Optional[str] = None,
    note: Optional[str] = None,
) -> dict[str, Any]:
    """Build one JSON-safe port sample from the stable registry definition."""
    definition = _PORT_BY_ID_V1[port_id]
    return {
        "port_id": definition.port_id,
        "name": definition.name,
        "implementation": definition.implementation,
        "authority": definition.authority,
        "source": definition.source,
        "signal_status": signal_status or _signal_status(signal),
        "signal": _json_safe(dict(signal)),
        "note": note,
    }


def _dp00_external_world(env: Any) -> dict[str, Any]:
    """Sample simulation-only external world/body state for diagnostic reference."""
    state = getattr(env, "state", None)
    signal = _state_attrs(
        state,
        (
            "scenario_stage",
            "kid_posture",
            "mom_distance",
            "shelter_distance",
            "cliff_distance",
            "nipple_state",
            "kid_position",
            "mom_position",
            "kid_fatigue",
            "kid_temperature",
            "time_since_birth",
            "step_index",
            "position",
            "zone",
            "last_applied_action",
            "lower_motor_slip_detected",
            "lower_motor_error_code",
            "lower_motor_progress_override",
            "lower_motor_support_override",
        ),
    )
    return _port_sample("DP00", signal, signal_status="active" if signal else "missing")


def _dp01_observation(env_obs: Any) -> dict[str, Any]:
    """Sample the agent-visible observation packet produced by the adapter boundary."""
    if env_obs is None:
        return _port_sample("DP01", {}, signal_status="missing", note="No observation packet was supplied to this capture.")
    raw = getattr(env_obs, "raw_sensors", {})
    predicates = list(getattr(env_obs, "predicates", []) or [])
    cues = list(getattr(env_obs, "cues", []) or [])
    patches = list(getattr(env_obs, "nav_patches", []) or [])
    env_meta = getattr(env_obs, "env_meta", {})
    surface = getattr(env_obs, "surface_grid", {})
    signal = {
        "raw_sensors": _compact_mapping(raw, limit=12),
        "predicates": predicates[:16],
        "predicate_count": len(predicates),
        "cues": cues[:16],
        "cue_count": len(cues),
        "nav_patch_count": len(patches),
        "env_meta": _compact_mapping(env_meta, limit=14),
        "surface_grid_keys": sorted(str(key) for key in surface)[:12] if isinstance(surface, Mapping) else [],
    }
    return _port_sample("DP01", signal, signal_status="active")


def _dp02_shaping(env_obs: Any) -> dict[str, Any]:
    """Expose current adapter products standing in for the collapsed shaping stage."""
    if env_obs is None:
        return _port_sample(
            "DP02",
            {},
            signal_status="missing",
            note="No independent shaping module exists; no current adapter products were captured.",
        )
    raw = getattr(env_obs, "raw_sensors", {})
    patches = list(getattr(env_obs, "nav_patches", []) or [])
    surface = getattr(env_obs, "surface_grid", {})
    signal = {
        "adapter_proxy": True,
        "normalized_channel_keys": sorted(str(key) for key in raw)[:16] if isinstance(raw, Mapping) else [],
        "nav_patch_count": len(patches),
        "surface_grid_present": bool(surface),
    }
    return _port_sample(
        "DP02",
        signal,
        signal_status="active",
        note="Current software collapses shaping into PerceptionAdapter/HAL products; no fabricated intermediate value.",
    )


def _dp03_association(ctx: Any) -> dict[str, Any]:
    """Sample current domain association/matching records without inventing modalities."""
    matches = list(getattr(ctx, "navpatch_last_matches", []) or [])
    priors = getattr(ctx, "navpatch_last_priors", {})
    signal = {
        "domain_match_count": len(matches),
        "top_matches": _json_safe(matches[:3]),
        "prior_summary": _compact_mapping(priors, limit=8),
    }
    active = bool(matches or priors)
    return _port_sample(
        "DP03",
        signal if active else {},
        signal_status="active" if active else "idle",
        note="General modality-specific association is not yet a separate module; current domain matches are shown.",
    )


def _dp04_local_maps(ctx: Any, env_obs: Any) -> dict[str, Any]:
    """Sample the domain-specific evidence maps currently approximating local sensory maps."""
    patches = list(getattr(env_obs, "nav_patches", []) or []) if env_obs is not None else []
    map_rows = {
        "body_ground_evidence": _map_ref_row(getattr(ctx, "navmap_v2_shadow_evidence_body_ground", None)),
        "maternal_evidence": _map_ref_row(getattr(ctx, "navmap_maternal_evidence_map", None)),
        "feeding_evidence": _map_ref_row(getattr(ctx, "feeding_evidence_map_v1", None)),
        "terrain_west": _map_ref_row(getattr(ctx, "terrain_route_west_map_v1", None)),
        "terrain_east": _map_ref_row(getattr(ctx, "terrain_route_east_map_v1", None)),
    }
    map_rows = {key: value for key, value in map_rows.items() if value is not None}
    payload = getattr(ctx, "navmap_last_payload_v1", None)
    signal = {
        "nav_patch_count": len(patches),
        "evidence_maps": map_rows,
        "last_payload": _compact_mapping(payload, limit=12),
    }
    active = bool(patches or map_rows or payload)
    return _port_sample(
        "DP04",
        signal if active else {},
        signal_status="active" if active else "idle",
        note="CCA8 currently has domain-specific evidence maps rather than one generalized local-sensory-map layer.",
    )


def _dp05_temporal(ctx: Any) -> dict[str, Any]:
    """Sample bounded Sequential/Error and generalized live-dynamics state."""
    live = _safe_call(lambda: cca8_live_dynamics.live_dynamics_summary_v1(ctx), {})
    maternal = _safe_call(lambda: cca8_maternal_temporal.maternal_temporal_shadow_summary_v1(ctx), {})
    seqerr = getattr(ctx, "seqerr_last", {})
    signal = {
        "seqerr_last": _compact_mapping(seqerr, limit=14),
        "seqerr_history_count": len(getattr(ctx, "seqerr_history", []) or []),
        "maternal_temporal": _compact_mapping(maternal, limit=12),
        "live_dynamics_status": live.get("status") if isinstance(live, Mapping) else None,
        "live_dynamics_state": _json_safe(live.get("state")) if isinstance(live, Mapping) else None,
        "event_history_count": live.get("event_history_count") if isinstance(live, Mapping) else None,
    }
    active = bool(seqerr or maternal.get("status") == "active" or live.get("status") == "active")
    return _port_sample("DP05", signal if active else {}, signal_status="active" if active else "idle")


def _dp06_evidence_gateway(ctx: Any) -> dict[str, Any]:
    """Sample observation-update, continuity, and evidence-gateway records."""
    observation = _safe_call(lambda: cca8_navmap_runtime.navmap_observation_update_summary_v1(ctx), {})
    maternal = _safe_call(lambda: cca8_maternal_geometry.maternal_geometry_shadow_summary_v1(ctx), {})
    continuity = _safe_call(lambda: cca8_maternal_continuity.maternal_continuity_shadow_summary_v1(ctx), {})
    signal = {
        "observation_update": _compact_mapping(observation, limit=16),
        "candidate_store_count": len(getattr(ctx, "navmap_scene_body_candidates_v1", []) or []),
        "maternal_geometry": _compact_mapping(maternal, limit=10),
        "maternal_continuity": _compact_mapping(continuity, limit=10),
    }
    active = bool(observation.get("has_last_update") or maternal.get("status") == "active" or continuity.get("status") == "active")
    return _port_sample(
        "DP06",
        signal if active else {},
        signal_status="active" if active else "idle",
        note="General segmentation/evidence gateway remains partial; available map-family evidence is shown.",
    )


def _dp07_bodymap(ctx: Any) -> dict[str, Any]:
    """Sample protected BodyMap posture, proximity, safety, and freshness readouts."""
    body_world = getattr(ctx, "body_world", None)
    bindings = getattr(body_world, "_bindings", {}) if body_world is not None else {}
    signal = {
        "posture": _safe_call(lambda: body_posture(ctx)),
        "mom_distance": _safe_call(lambda: body_mom_distance(ctx)),
        "nipple_state": _safe_call(lambda: body_nipple_state(ctx)),
        "shelter_distance": _safe_call(lambda: body_shelter_distance(ctx)),
        "cliff_distance": _safe_call(lambda: body_cliff_distance(ctx)),
        "zone": _safe_call(lambda: body_space_zone(ctx)),
        "stale": bool(_safe_call(lambda: bodymap_is_stale(ctx), False)),
        "last_update_controller_step": getattr(ctx, "bodymap_last_update_step", None),
        "binding_count": len(bindings) if isinstance(bindings, Mapping) else 0,
    }
    active = body_world is not None
    return _port_sample("DP07", signal if active else {}, signal_status="active" if active else "missing")


def _dp08_memory_activation(ctx: Any, world: Any) -> dict[str, Any]:
    """Sample sparse candidate activation and its current scaffold/target ownership."""
    summary = _safe_call(lambda: cca8_navmap_memory.navmap_memory_summary_v1(ctx), {})
    retrieval = summary.get("last_retrieval") if isinstance(summary, Mapping) else None
    retrieval = retrieval if isinstance(retrieval, Mapping) else {}
    candidates = list(retrieval.get("candidate_refs") or [])
    signal = {
        "current_index_owner": "ctx_phase8_scaffold",
        "target_index_owner": "worldgraph",
        "indexed_count": summary.get("sparse_index_entry_count"),
        "token_count": summary.get("inverted_token_count"),
        "query_no": (retrieval.get("request") or {}).get("query_no") if isinstance(retrieval.get("request"), Mapping) else None,
        "retrieval_status": retrieval.get("status"),
        "candidate_count": len(candidates),
        "candidate_refs": _json_safe(candidates[:8]),
        "winner_ref": _json_safe(retrieval.get("winner_ref")),
        "reason": retrieval.get("reason"),
        "full_payload_scan": summary.get("candidate_generation_uses_full_payload_scan"),
        "worldgraph_binding_count": len(getattr(world, "_bindings", {}) or {}) if world is not None else 0,
    }
    active = bool(summary.get("sparse_index_entry_count") or retrieval)
    return _port_sample(
        "DP08",
        signal,
        signal_status="active" if active else "idle",
        note="Sparse retrieval is implemented; final ownership has not yet moved from ctx-local indexes into WorldGraph.",
    )


def _dp09_columns(ctx: Any) -> dict[str, Any]:
    """Sample durable Column content and any selectively reinstated NavMaps."""
    summary = _safe_call(lambda: cca8_navmap_memory.navmap_memory_summary_v1(ctx), {})
    retrieval = summary.get("last_retrieval") if isinstance(summary, Mapping) else None
    retrieval = retrieval if isinstance(retrieval, Mapping) else {}
    reinstatements = list(retrieval.get("reinstatements") or [])
    ids = cca8_column.mem.list_ids()
    signal = {
        "column": getattr(cca8_column.mem, "name", "column01"),
        "engram_count": cca8_column.mem.count(),
        "recent_engram_ids": ids[-5:],
        "reinstatement_count": len(reinstatements),
        "reinstatements": _json_safe(reinstatements[:3]),
        "last_consolidation": _compact_mapping(summary.get("last_consolidation"), limit=12),
    }
    return _port_sample("DP09", signal, signal_status="active" if signal["engram_count"] or reinstatements else "idle")


def _dp10_comparison(ctx: Any) -> dict[str, Any]:
    """Sample expected/current comparisons, residuals, and acceptance decisions."""
    expected = _safe_call(lambda: cca8_navmap_runtime.navmap_expected_current_summary_v1(ctx), {})
    accepted = _safe_call(lambda: cca8_navmap_runtime.navmap_accepted_current_summary_v1(ctx), {})
    signal = {
        "comparison_status": expected.get("status"),
        "action": expected.get("action"),
        "reason": expected.get("reason"),
        "residual_count": expected.get("residual_count"),
        "exact_match": expected.get("exact_match"),
        "context_shift_recommended": expected.get("context_shift_recommended"),
        "context_break_recommended": expected.get("context_break_recommended"),
        "safety_residual_slots": expected.get("safety_residual_slots"),
        "acceptance": accepted.get("acceptance"),
        "accepted_residual_count": accepted.get("residual_count"),
        "comparison_reason": accepted.get("comparison_reason"),
    }
    active = bool(expected.get("has_last_comparison") or accepted.get("has_last_accepted_current"))
    return _port_sample(
        "DP10",
        signal if active else {},
        signal_status="active" if active else "idle",
        note="Several comparison paths exist; CCA8 does not yet expose one universal cross-domain transaction.",
    )


def _dp11_wnm(ctx: Any) -> dict[str, Any]:
    """Sample the one operative WNM, ready set, and latest WNM transition."""
    summary = _safe_call(lambda: cca8_wnm_runtime.wnm_summary_v1(ctx), {})
    signal = {
        "status": summary.get("status"),
        "authority": summary.get("authority"),
        "operative_count": summary.get("operative_count"),
        "at_most_one_operative": summary.get("at_most_one_operative"),
        "operative_map": _json_safe(summary.get("operative_map")),
        "ready_count": summary.get("ready_count"),
        "ready_capacity": summary.get("ready_capacity"),
        "ready_set": _json_safe(summary.get("ready_set")),
        "last_transition": _json_safe(summary.get("last_transition")),
    }
    return _port_sample("DP11", signal, signal_status="active" if summary.get("status") == "active" else "idle")


def _dp12_drives(ctx: Any, drives: Any) -> dict[str, Any]:
    """Sample compact drives, developmental context, and goal/emotion status."""
    flags = _safe_call(lambda: list(drives.flags()), []) if drives is not None else []
    signal = {
        "hunger": getattr(drives, "hunger", None),
        "fatigue": getattr(drives, "fatigue", None),
        "warmth": getattr(drives, "warmth", None),
        "active_flags": _json_safe(flags),
        "age_days": getattr(ctx, "age_days", None),
        "developmental_profile": getattr(ctx, "profile", None),
        "goal_emotion_module_status": "partial_not_unified",
    }
    return _port_sample("DP12", signal, signal_status="active" if drives is not None else "missing")


def _dp13_policy(ctx: Any, policy_rt: Any, selected_policy: Optional[str]) -> dict[str, Any]:
    """Sample primitive eligibility, protected filtering, arbitration, and selection."""
    debug = getattr(ctx, "experiment_policy_debug_last", {})
    debug = debug if isinstance(debug, Mapping) else {}
    loaded = _safe_call(lambda: policy_rt.list_loaded_names(), []) if policy_rt is not None else []
    signal = {
        "loaded": list(loaded or []),
        "triggered": list(getattr(ctx, "ac_triggered_policies", []) or []),
        "matches_initial": _json_safe(debug.get("matches_initial")),
        "matches_after_safety": _json_safe(debug.get("matches_after_safety")),
        "matches_before_choice": _json_safe(debug.get("matches_before_choice")),
        "chosen": selected_policy or debug.get("chosen"),
        "selector_kind": debug.get("selector_kind"),
        "selection_reason": debug.get("selection_reason"),
        "tie_break_label": debug.get("tie_break_label"),
        "score_rows": _json_safe(debug.get("score_rows")),
        "winner_scores": _json_safe(debug.get("winner_scores")),
        "fallen_safety_filter": debug.get("fallen_safety_filter"),
        "legacy_fallen_safety_filter": debug.get("legacy_fallen_safety_filter"),
        "guarded_map_fallen_safety_filter": debug.get("guarded_map_fallen_safety_filter"),
        "protected_safety_filter": debug.get("fallen_safety_filter"),
        "authority_source": debug.get("selected_trigger_authority_source"),
        "authority_reason": debug.get("selected_trigger_authority_reason"),
    }
    active = bool(selected_policy or debug or loaded)
    return _port_sample("DP13", signal if active else {}, signal_status="active" if active else "idle")


def _dp14_primitive_operation(ctx: Any, selected_policy: Optional[str]) -> dict[str, Any]:
    """Sample domain-specific results of the selected primitive operating on the WNM."""
    transition = _safe_call(lambda: cca8_navmap_runtime.navmap_transition_summary_v1(ctx), {})
    followmom = _safe_call(lambda: cca8_followmom_authority.followmom_authority_summary_v1(ctx), {})
    feeding = _safe_call(lambda: cca8_feeding.feeding_summary_v1(ctx), {})
    terrain = _safe_call(lambda: cca8_terrain.terrain_summary_v1(ctx), {})
    signal = {
        "selected_primitive": selected_policy,
        "pending_action": getattr(ctx, "navmap_pending_action_v1", None),
        "next_action_for_environment": getattr(ctx, "env_last_action", None),
        "transition": _compact_mapping(transition, limit=12),
        "followmom_authority": _compact_mapping(followmom, limit=10),
        "feeding_status": feeding.get("status"),
        "feeding_pending_expectation": _json_safe(feeding.get("pending_expectation")),
        "terrain_status": terrain.get("status"),
        "terrain_policy_readout": _json_safe(terrain.get("policy_readout")),
        "last_policy_outcome": _compact_mapping(getattr(ctx, "navmap_last_policy_outcome_v1", {}), limit=10),
    }
    active = bool(selected_policy or transition.get("status") == "active" or followmom.get("decision"))
    return _port_sample(
        "DP14",
        signal if active else {},
        signal_status="active" if active else "idle",
        note="Primitive-on-WNM transactions are implemented by domain and are not yet one universal operation record.",
    )


def _dp15_lower_motor(env: Any, selected_policy: Optional[str], action_applied: Optional[str]) -> dict[str, Any]:
    """Sample the task-action handoff and lower-controller/environment acknowledgement."""
    state = getattr(env, "state", None)
    signal = {
        "selected_task_action": selected_policy,
        "action_applied_this_environment_step": action_applied,
        "environment_last_applied_action": getattr(state, "last_applied_action", None),
        "slip_detected": getattr(state, "lower_motor_slip_detected", None),
        "error_code": getattr(state, "lower_motor_error_code", None),
        "progress_override": getattr(state, "lower_motor_progress_override", None),
        "support_override": getattr(state, "lower_motor_support_override", None),
        "pipeline_relation": "selected_current_cycle_is_applied_on_next_environment_step",
        "handoff_ack_mismatch": bool(
            action_applied is not None
            and getattr(state, "last_applied_action", None) is not None
            and action_applied != getattr(state, "last_applied_action", None)
        ),
    }
    active = bool(selected_policy or action_applied or getattr(state, "last_applied_action", None))
    return _port_sample("DP15", signal if active else {}, signal_status="active" if active else "idle")


def _dp16_expectation(ctx: Any) -> dict[str, Any]:
    """Sample pending expected-successor and prediction records without granting truth."""
    feeding = _safe_call(lambda: cca8_feeding.feeding_summary_v1(ctx), {})
    followmom = _safe_call(lambda: cca8_followmom_compare.followmom_compare_summary_v1(ctx), {})
    signal = {
        "prediction_next_record": _compact_mapping(getattr(ctx, "prediction_next_record", {}), limit=16),
        "navmap_expected_payload": _compact_mapping(getattr(ctx, "navmap_last_expected_current_payload_v1", {}), limit=12),
        "pending_action": getattr(ctx, "navmap_pending_action_v1", None),
        "followmom_pending": _json_safe(followmom.get("pending")),
        "feeding_pending": _json_safe(feeding.get("pending_expectation")),
    }
    active = any(bool(value) for value in signal.values())
    return _port_sample("DP16", signal if active else {}, signal_status="active" if active else "idle")


def _dp17_outcome(ctx: Any) -> dict[str, Any]:
    """Sample internally computed expected-versus-evidence outcomes and residuals."""
    prediction = _safe_call(lambda: cca8_predictive.prediction_feedback_summary_v1(ctx), {})
    followmom = _safe_call(lambda: cca8_followmom_compare.followmom_compare_summary_v1(ctx), {})
    feeding = _safe_call(lambda: cca8_feeding.feeding_summary_v1(ctx), {})
    signal = {
        "prediction_feedback": _compact_mapping(prediction, limit=16),
        "prediction_error": _compact_mapping(getattr(ctx, "prediction_last_error_record", {}), limit=16),
        "pred_err_v0": _compact_mapping(getattr(ctx, "pred_err_v0_last", {}), limit=8),
        "followmom_outcome": _json_safe(followmom.get("observed_outcome")),
        "feeding_outcome": _json_safe(feeding.get("observed_outcome")),
    }
    active = bool(
        prediction.get("has_last_error")
        or int(prediction.get("history_count") or 0) > 0
        or signal["prediction_error"]
        or signal["pred_err_v0"]
        or signal["followmom_outcome"] is not None
        or signal["feeding_outcome"] is not None
    )
    return _port_sample("DP17", signal if active else {}, signal_status="active" if active else "idle")


def _dp18_learning(ctx: Any, world: Any) -> dict[str, Any]:
    """Sample skill, revision, consolidation, and long-term-memory writeback effects."""
    memory = _safe_call(lambda: cca8_navmap_memory.navmap_memory_summary_v1(ctx), {})
    skills = _safe_call(skill_readout, "")
    skill_stats = _safe_call(skills_to_dict, {})
    skill_stats = skill_stats if isinstance(skill_stats, Mapping) else {}
    skill_lines = skills.strip().splitlines()[-8:] if isinstance(skills, str) and skills.strip() else []
    if skill_lines == ["(no skill stats yet)"]:
        skill_lines = []
    signal = {
        "skill_ledger": skill_lines,
        "skill_stats": _json_safe(skill_stats),
        "last_policy_outcome": _compact_mapping(getattr(ctx, "navmap_last_policy_outcome_v1", {}), limit=12),
        "last_consolidation": _compact_mapping(memory.get("last_consolidation"), limit=14),
        "eligibility_count": memory.get("eligibility_count"),
        "consolidation_history_count": memory.get("consolidation_history_count"),
        "column_engram_count": cca8_column.mem.count(),
        "worldgraph_binding_count": len(getattr(world, "_bindings", {}) or {}) if world is not None else 0,
        "terrain_material_revision": _compact_mapping(getattr(ctx, "terrain_last_material_revision_v1", {}), limit=10),
    }
    active = bool(
        signal["skill_ledger"]
        or signal["skill_stats"]
        or signal["last_policy_outcome"]
        or signal["last_consolidation"]
        or int(signal["consolidation_history_count"] or 0) > 0
        or signal["terrain_material_revision"]
    )
    return _port_sample("DP18", signal, signal_status="active" if active else "idle")


def build_cognitive_scope_snapshot_v1(
    ctx: Any,
    *,
    env: Any,
    env_obs: Any,
    world: Any,
    drives: Any,
    policy_rt: Any,
    selected_policy: Optional[str],
    action_applied: Optional[str],
    env_step: Optional[int],
    capture_kind: str = "manual_live",
    snapshot_no: Optional[int] = None,
) -> dict[str, Any]:
    """Build one JSON-safe full-service-point snapshot without mutating runtime."""
    collectors: tuple[Callable[[], dict[str, Any]], ...] = (
        lambda: _dp00_external_world(env),
        lambda: _dp01_observation(env_obs),
        lambda: _dp02_shaping(env_obs),
        lambda: _dp03_association(ctx),
        lambda: _dp04_local_maps(ctx, env_obs),
        lambda: _dp05_temporal(ctx),
        lambda: _dp06_evidence_gateway(ctx),
        lambda: _dp07_bodymap(ctx),
        lambda: _dp08_memory_activation(ctx, world),
        lambda: _dp09_columns(ctx),
        lambda: _dp10_comparison(ctx),
        lambda: _dp11_wnm(ctx),
        lambda: _dp12_drives(ctx, drives),
        lambda: _dp13_policy(ctx, policy_rt, selected_policy),
        lambda: _dp14_primitive_operation(ctx, selected_policy),
        lambda: _dp15_lower_motor(env, selected_policy, action_applied),
        lambda: _dp16_expectation(ctx),
        lambda: _dp17_outcome(ctx),
        lambda: _dp18_learning(ctx, world),
    )

    ports: list[dict[str, Any]] = []
    for definition, collector in zip(COGNITIVE_SCOPE_PORTS_V1, collectors):
        try:
            sample = collector()
        except Exception as exc:  # pragma: no cover - defensive diagnostic boundary
            sample = _port_sample(
                definition.port_id,
                {"error_type": type(exc).__name__, "error": str(exc)},
                signal_status="error",
                note="Port collector failed; cognition continued unchanged.",
            )
        ports.append(sample)

    return {
        "schema": "cognitive_scope_snapshot_v1",
        "capture_kind": str(capture_kind),
        "snapshot_no": snapshot_no,
        "captured_at": datetime.now().isoformat(timespec="milliseconds"),
        "profile": getattr(ctx, "profile", None),
        "cognitive_cycle": int(getattr(ctx, "cog_cycles", 0) or 0),
        "controller_step": int(getattr(ctx, "controller_steps", 0) or 0),
        "environment_step": env_step,
        "action_applied": action_applied,
        "action_selected_for_next_step": selected_policy,
        "external_reference_port_count": 1,
        "cognitive_service_point_count": 18,
        "port_count": len(ports),
        "ports": ports,
        "sampling_model": "end_of_cycle_stable_register_snapshot_v1",
        "port_samples_are_exact_stage_timestamps": False,
        "trace_is_cognitive_memory": False,
        "measurement_only": True,
        "injection_enabled": False,
    }


def _trace_capacity(ctx: Any) -> int:
    """Return a safe bounded trace capacity from context configuration."""
    try:
        value = int(getattr(ctx, "cognitive_scope_capacity_v1", 128) or 128)
    except (TypeError, ValueError):
        value = 128
    return max(1, min(value, 4096))


def capture_cognitive_scope_snapshot_v1(
    ctx: Any,
    *,
    env: Any,
    env_obs: Any,
    world: Any,
    drives: Any,
    policy_rt: Any,
    selected_policy: Optional[str],
    action_applied: Optional[str],
    env_step: Optional[int],
    capture_kind: str = "cognitive_cycle",
) -> dict[str, Any]:
    """Capture and retain one bounded cognitive-scope snapshot.

    The function has no effect when ``ctx.cognitive_scope_enabled_v1`` is false.
    It stores JSON-safe diagnostics only and never grants cognitive authority.
    """
    if ctx is None or not bool(getattr(ctx, "cognitive_scope_enabled_v1", True)):
        return {
            "schema": "cognitive_scope_capture_v1",
            "status": "disabled",
            "captured": False,
        }

    next_no = int(getattr(ctx, "cognitive_scope_snapshot_no_v1", 0) or 0) + 1
    snapshot = build_cognitive_scope_snapshot_v1(
        ctx,
        env=env,
        env_obs=env_obs,
        world=world,
        drives=drives,
        policy_rt=policy_rt,
        selected_policy=selected_policy,
        action_applied=action_applied,
        env_step=env_step,
        capture_kind=capture_kind,
        snapshot_no=next_no,
    )

    trace_raw = getattr(ctx, "cognitive_scope_trace_v1", None)
    trace = trace_raw if isinstance(trace_raw, list) else []
    trace.append(snapshot)
    capacity = _trace_capacity(ctx)
    if len(trace) > capacity:
        del trace[: len(trace) - capacity]

    ctx.cognitive_scope_trace_v1 = trace
    ctx.cognitive_scope_snapshot_no_v1 = next_no
    ctx.cognitive_scope_last_capture_v1 = snapshot
    return snapshot


def cognitive_scope_latest_snapshot_v1(ctx: Any) -> Optional[dict[str, Any]]:
    """Return the newest retained snapshot without mutating the trace."""
    trace = getattr(ctx, "cognitive_scope_trace_v1", None)
    if isinstance(trace, list) and trace:
        latest = trace[-1]
        return latest if isinstance(latest, dict) else None
    last = getattr(ctx, "cognitive_scope_last_capture_v1", None)
    return last if isinstance(last, dict) and last else None


def cognitive_scope_find_snapshot_v1(ctx: Any, snapshot_no: int) -> Optional[dict[str, Any]]:
    """Return one retained snapshot by monotonic snapshot number."""
    trace = getattr(ctx, "cognitive_scope_trace_v1", None)
    if not isinstance(trace, list):
        return None
    for row in reversed(trace):
        if isinstance(row, dict) and row.get("snapshot_no") == snapshot_no:
            return row
    return None


def cognitive_scope_clear_v1(ctx: Any) -> int:
    """Clear retained diagnostic snapshots and return the number removed."""
    trace = getattr(ctx, "cognitive_scope_trace_v1", None)
    count = len(trace) if isinstance(trace, list) else 0
    ctx.cognitive_scope_trace_v1 = []
    ctx.cognitive_scope_last_capture_v1 = {}
    return count


def cognitive_scope_trace_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return compact bounded-trace status for menu and tests."""
    trace = getattr(ctx, "cognitive_scope_trace_v1", None)
    rows = trace if isinstance(trace, list) else []
    return {
        "schema": "cognitive_scope_trace_summary_v1",
        "status": "active" if bool(getattr(ctx, "cognitive_scope_enabled_v1", True)) else "disabled",
        "capacity": _trace_capacity(ctx),
        "retained_count": len(rows),
        "total_capture_count": int(getattr(ctx, "cognitive_scope_snapshot_no_v1", 0) or 0),
        "oldest_snapshot_no": rows[0].get("snapshot_no") if rows and isinstance(rows[0], dict) else None,
        "latest_snapshot_no": rows[-1].get("snapshot_no") if rows and isinstance(rows[-1], dict) else None,
        "trace_is_cognitive_memory": False,
        "injection_enabled": False,
    }


_COMPACT_PORT_LABELS_V1: dict[str, str] = {
    "DP00": "WORLD",
    "DP01": "SENSORS",
    "DP02": "SHAPING",
    "DP03": "ASSOCIATION",
    "DP04": "LOCAL MAPS",
    "DP05": "TEMPORAL",
    "DP06": "SEGMENT",
    "DP07": "BODYMAP",
    "DP08": "MEMORY IDX",
    "DP09": "COLUMNS",
    "DP10": "COMPARE",
    "DP11": "WNM",
    "DP12": "DRIVES",
    "DP13": "POLICY",
    "DP14": "WNM OP",
    "DP15": "MOTOR",
    "DP16": "EXPECTED",
    "DP17": "OUTCOME",
    "DP18": "LEARNING",
}


def _mapping_or_empty(value: Any) -> Mapping[str, Any]:
    """Return ``value`` as a mapping or an empty mapping for compact rendering."""
    return value if isinstance(value, Mapping) else {}


def _list_or_empty(value: Any) -> list[Any]:
    """Return ``value`` as a list or an empty list for compact rendering."""
    return list(value) if isinstance(value, (list, tuple)) else []


def _compact_text(value: Any, *, missing: str = "unknown") -> str:
    """Return one compact scalar-like terminal value."""
    if value is None:
        return missing
    if isinstance(value, bool):
        return "yes" if value else "no"
    if isinstance(value, float):
        return f"{value:.2f}"
    if isinstance(value, str):
        return value or missing
    return str(value)


def _short_policy_name(value: Any) -> str:
    """Return a policy name without the repetitive ``policy:`` prefix."""
    text = _compact_text(value, missing="none")
    return text.removeprefix("policy:")


def _map_ref_text(value: Any, *, missing: str = "none") -> str:
    """Render a map reference from either a direct map-ref or containing row."""
    row = _mapping_or_empty(value)
    nested = _mapping_or_empty(row.get("map_ref"))
    if nested:
        row = nested
    map_id = row.get("map_id")
    revision = row.get("revision")
    if not isinstance(map_id, str) or not map_id:
        return missing
    if isinstance(revision, int):
        return f"{map_id}@r{revision}"
    return map_id


def _expected_slots_text(value: Any) -> str:
    """Return up to three expected key/value pairs for the front panel."""
    slots = _mapping_or_empty(value)
    if not slots:
        return "none"
    parts = [f"{key}={slots[key]}" for key in sorted(slots, key=str)[:3]]
    if len(slots) > 3:
        parts.append("...")
    return ",".join(parts)


def _implementation_marker(row: Mapping[str, Any]) -> str:
    """Return a compact marker for partial, collapsed, or scaffold modules."""
    implementation = str(row.get("implementation") or "")
    if implementation == "collapsed":
        return "COLLAPSED"
    if implementation == "partial":
        return "PARTIAL"
    if implementation == "implemented_scaffold":
        return "SCAFFOLD"
    if implementation == "implemented_seam":
        return "SEAM"
    return ""


def _compact_dp00(signal: Mapping[str, Any]) -> str:
    return (
        f"stage={_compact_text(signal.get('scenario_stage'))} | "
        f"posture={_compact_text(signal.get('kid_posture'))} | "
        f"mom={_compact_text(signal.get('mom_distance'))} | "
        f"cliff={_compact_text(signal.get('cliff_distance'))} | "
        f"nipple={_compact_text(signal.get('nipple_state'))}"
    )


def _compact_dp01(signal: Mapping[str, Any]) -> str:
    raw = _mapping_or_empty(signal.get("raw_sensors"))
    return (
        f"preds={_compact_text(signal.get('predicate_count'), missing='0')} | "
        f"cues={_compact_text(signal.get('cue_count'), missing='0')} | "
        f"NavPatch={_compact_text(signal.get('nav_patch_count'), missing='0')} | "
        f"raw_channels={len(raw)}"
    )


def _compact_dp02(signal: Mapping[str, Any]) -> str:
    channels = _list_or_empty(signal.get("normalized_channel_keys"))
    return (
        f"COLLAPSED->adapter | channels={len(channels)} | "
        f"NavPatch={_compact_text(signal.get('nav_patch_count'), missing='0')} | "
        f"surface_grid={_compact_text(signal.get('surface_grid_present'))}"
    )


def _compact_dp03(signal: Mapping[str, Any]) -> str:
    matches = _list_or_empty(signal.get("top_matches"))
    top = _mapping_or_empty(matches[0]) if matches else {}
    best = _mapping_or_empty(top.get("best"))
    score = best.get("score")
    score_text = f"{float(score):.2f}" if isinstance(score, (int, float)) else "n/a"
    return (
        f"PARTIAL | matches={_compact_text(signal.get('domain_match_count'), missing='0')} | "
        f"decision={_compact_text(top.get('decision'))} | commit={_compact_text(top.get('commit'))} | score={score_text}"
    )


def _compact_dp04(signal: Mapping[str, Any]) -> str:
    maps = _mapping_or_empty(signal.get("evidence_maps"))
    maternal = _mapping_or_empty(maps.get("maternal_evidence"))
    return (
        f"PARTIAL | maps={len(maps)} | patches={_compact_text(signal.get('nav_patch_count'), missing='0')} | "
        f"maternal={_map_ref_text(maternal)}"
    )


def _compact_dp05(signal: Mapping[str, Any]) -> str:
    live = _mapping_or_empty(signal.get("live_dynamics_state"))
    overlays = _mapping_or_empty(live.get("overlays"))
    maternal = _mapping_or_empty(overlays.get("self_maternal"))
    route = _mapping_or_empty(overlays.get("self_route"))
    motor = _mapping_or_empty(overlays.get("lower_motor"))
    materiality = _mapping_or_empty(live.get("materiality"))

    maternal_trend = maternal.get("distance_trend")
    if maternal_trend in (None, "", "unknown"):
        maternal_summary = _mapping_or_empty(signal.get("maternal_temporal"))
        maternal_trend = maternal_summary.get("trend")

    return (
        f"maternal={_compact_text(maternal_trend)} | route={_compact_text(route.get('motion_direction'))} | "
        f"motor={_compact_text(motor.get('phase_detail') or motor.get('phase'))} | "
        f"events={_compact_text(signal.get('event_history_count'), missing='0')} | "
        f"material={_compact_text(materiality.get('material_change_recommended'))}"
    )


def _compact_dp06(signal: Mapping[str, Any]) -> str:
    update = _mapping_or_empty(signal.get("observation_update"))
    return (
        f"PARTIAL | action={_compact_text(update.get('action'))} | "
        f"candidates={_compact_text(signal.get('candidate_store_count'), missing='0')} | "
        f"residuals={_compact_text(update.get('residual_count'), missing='0')} | "
        f"matched={_compact_text(update.get('matched'))}"
    )


def _compact_dp07(signal: Mapping[str, Any]) -> str:
    freshness = "stale" if signal.get("stale") is True else "fresh"
    return (
        f"posture={_compact_text(signal.get('posture'))} | mom={_compact_text(signal.get('mom_distance'))} | "
        f"cliff={_compact_text(signal.get('cliff_distance'))} | zone={_compact_text(signal.get('zone'))} | {freshness}"
    )


def _compact_dp08(signal: Mapping[str, Any]) -> str:
    return (
        f"SCAFFOLD | candidates={_compact_text(signal.get('candidate_count'), missing='0')} | "
        f"winner={_map_ref_text(signal.get('winner_ref'))} | "
        f"status={_compact_text(signal.get('retrieval_status'))} | "
        f"full_scan={_compact_text(signal.get('full_payload_scan'))}"
    )


def _compact_dp09(signal: Mapping[str, Any]) -> str:
    reinstatements = _list_or_empty(signal.get("reinstatements"))
    conflict_count = 0
    exact_count = 0
    for item in reinstatements:
        row = _mapping_or_empty(item)
        status = str(row.get("status") or "")
        if "conflict" in status:
            conflict_count += 1
        match = _mapping_or_empty(row.get("match_result"))
        if match.get("status") == "exact" or row.get("reason") == "exact_structural_match":
            exact_count += 1
    consolidation = _mapping_or_empty(signal.get("last_consolidation"))
    return (
        f"engrams={_compact_text(signal.get('engram_count'), missing='0')} | "
        f"reinstated={_compact_text(signal.get('reinstatement_count'), missing='0')} | "
        f"exact={exact_count} | conflicts={conflict_count} | "
        f"consolidated={_compact_text(consolidation.get('consolidated'))}"
    )


def _compact_dp10(signal: Mapping[str, Any]) -> str:
    return (
        f"action={_short_policy_name(signal.get('action'))} | "
        f"residuals={_compact_text(signal.get('residual_count'), missing='0')} | "
        f"acceptance={_compact_text(signal.get('acceptance'))} | exact={_compact_text(signal.get('exact_match'))}"
    )


def _compact_dp11(signal: Mapping[str, Any]) -> str:
    operative = _mapping_or_empty(signal.get("operative_map"))
    role = _compact_text(operative.get("role"))
    ready_count = _compact_text(signal.get("ready_count"), missing="0")
    ready_capacity = _compact_text(signal.get("ready_capacity"), missing="0")
    transition = _mapping_or_empty(signal.get("last_transition"))
    transition_result = transition.get("acceptance_result") or transition.get("failure_reason") or "none"
    return (
        f"operative={role}:{_map_ref_text(operative)} | ready={ready_count}/{ready_capacity} | "
        f"transition={_compact_text(transition_result)}"
    )


def _compact_dp12(signal: Mapping[str, Any]) -> str:
    flags = _list_or_empty(signal.get("active_flags"))
    return (
        f"hunger={_compact_text(signal.get('hunger'))} | fatigue={_compact_text(signal.get('fatigue'))} | "
        f"warmth={_compact_text(signal.get('warmth'))} | flags={len(flags)} | age={_compact_text(signal.get('age_days'))}d"
    )


def _compact_dp13(signal: Mapping[str, Any]) -> str:
    triggered = _list_or_empty(signal.get("triggered"))
    reason = _compact_text(signal.get("selection_reason"))
    if reason.startswith("rl_exploit(") and reason.endswith(")"):
        reason = reason[len("rl_exploit("):-1]
    elif "; tie_break=" in reason:
        reason = reason.split("; tie_break=", 1)[1]
    if reason.startswith("non_drive_priority("):
        reason = "non_drive_tiebreak"
    elif reason.startswith("stable_order("):
        reason = "stable_order"
    return (
        f"chosen={_short_policy_name(signal.get('chosen'))} | reason={reason} | cand={len(triggered)} | "
        f"safety={_compact_text(signal.get('protected_safety_filter'))} | "
        f"source={_compact_text(signal.get('authority_source'))}"
    )


def _compact_dp14(signal: Mapping[str, Any]) -> str:
    transition = _mapping_or_empty(signal.get("transition"))
    outcome = _mapping_or_empty(signal.get("last_policy_outcome"))
    reward = outcome.get("reward")
    reward_text = f"{float(reward):+.2f}" if isinstance(reward, (int, float)) else "n/a"
    return (
        f"selected={_short_policy_name(signal.get('selected_primitive'))} | "
        f"next={_short_policy_name(signal.get('next_action_for_environment'))} | "
        f"map_changed={_compact_text(transition.get('changed'))} | reward={reward_text}"
    )


def _compact_dp15(signal: Mapping[str, Any]) -> str:
    acknowledgement = "MISMATCH" if signal.get("handoff_ack_mismatch") is True else "ok"
    return (
        f"selected={_short_policy_name(signal.get('selected_task_action'))} | "
        f"applied={_short_policy_name(signal.get('action_applied_this_environment_step'))} | "
        f"ack={acknowledgement} | slip={_compact_text(signal.get('slip_detected'))} | "
        f"error={_compact_text(signal.get('error_code'), missing='none')}"
    )


def _compact_dp16(signal: Mapping[str, Any]) -> str:
    prediction = _mapping_or_empty(signal.get("prediction_next_record"))
    expected = _mapping_or_empty(prediction.get("expected"))
    if not expected:
        payload = _mapping_or_empty(signal.get("navmap_expected_payload"))
        expected = _mapping_or_empty(payload.get("slots"))
    pending = bool(signal.get("pending_action") or signal.get("followmom_pending") or signal.get("feeding_pending"))
    return (
        f"policy={_short_policy_name(prediction.get('policy'))} | expected={_expected_slots_text(expected)} | "
        f"pending={_compact_text(pending)}"
    )


def _compact_dp17(signal: Mapping[str, Any]) -> str:
    error = _mapping_or_empty(signal.get("prediction_error"))
    prediction = _mapping_or_empty(error.get("prediction"))
    expected = _mapping_or_empty(prediction.get("expected"))
    observed = _mapping_or_empty(error.get("observed"))
    by_slot = _mapping_or_empty(error.get("error_by_slot"))
    changed = "none"
    if by_slot:
        slot = sorted(by_slot, key=str)[0]
        changed = f"{slot}={_compact_text(expected.get(slot))}->{_compact_text(observed.get(slot))}"
    matched = error.get("matched")
    status = "match" if matched is True else "mismatch" if matched is False else "idle"
    severity = error.get("severity")
    severity_text = f"{float(severity):.2f}" if isinstance(severity, (int, float)) else "n/a"
    return (
        f"{status} | policy={_short_policy_name(prediction.get('policy'))} | {changed} | severity={severity_text}"
    )


def _compact_dp18(signal: Mapping[str, Any]) -> str:
    skills = _list_or_empty(signal.get("skill_ledger"))
    stats = _mapping_or_empty(signal.get("skill_stats"))
    consolidation = _mapping_or_empty(signal.get("last_consolidation"))
    outcome = _mapping_or_empty(signal.get("last_policy_outcome"))
    last_action = outcome.get("action")
    last_stat = _mapping_or_empty(stats.get(last_action)) if isinstance(last_action, str) else {}
    execution_count = last_stat.get("execution_count")
    learning_updates = last_stat.get("learning_update_count", last_stat.get("n"))
    skill_count = len(stats) if stats else len(skills)
    return (
        f"skills={skill_count} | last={_short_policy_name(last_action)} "
        f"exec={_compact_text(execution_count, missing='n/a')} updates={_compact_text(learning_updates, missing='n/a')} | "
        f"consolidated={_compact_text(consolidation.get('consolidated'))} | "
        f"eligible={_compact_text(signal.get('eligibility_count'), missing='0')} | "
        f"Columns={_compact_text(signal.get('column_engram_count'), missing='0')} | "
        f"WG={_compact_text(signal.get('worldgraph_binding_count'), missing='0')}"
    )


def _compact_port_signal_v1(row: Mapping[str, Any]) -> str:
    """Return the technician-facing one-line summary for one DP service point."""
    status = str(row.get("signal_status") or "unknown")
    if status != "active":
        marker = _implementation_marker(row)
        prefix = f"{marker} | " if marker else ""
        return f"{prefix}{status.upper()}"

    signal = _mapping_or_empty(row.get("signal"))
    port_id = str(row.get("port_id") or "")
    formatters: dict[str, Callable[[Mapping[str, Any]], str]] = {
        "DP00": _compact_dp00,
        "DP01": _compact_dp01,
        "DP02": _compact_dp02,
        "DP03": _compact_dp03,
        "DP04": _compact_dp04,
        "DP05": _compact_dp05,
        "DP06": _compact_dp06,
        "DP07": _compact_dp07,
        "DP08": _compact_dp08,
        "DP09": _compact_dp09,
        "DP10": _compact_dp10,
        "DP11": _compact_dp11,
        "DP12": _compact_dp12,
        "DP13": _compact_dp13,
        "DP14": _compact_dp14,
        "DP15": _compact_dp15,
        "DP16": _compact_dp16,
        "DP17": _compact_dp17,
        "DP18": _compact_dp18,
    }
    formatter = formatters.get(port_id)
    if formatter is None:
        return "ACTIVE"
    try:
        return formatter(signal)
    except Exception as exc:  # pragma: no cover - display must not break diagnostics
        return f"COMPACT_RENDER_ERROR {type(exc).__name__}: {exc}"


def cognitive_scope_normalize_port_id_v1(value: Any) -> Optional[str]:
    """Normalize ``13``, ``DP13``, or ``dp13`` to one valid registry port id."""
    text = str(value or "").strip().upper()
    if text.startswith("DP"):
        text = text[2:]
    if not text.isdigit():
        return None
    number = int(text)
    port_id = f"DP{number:02d}"
    return port_id if port_id in _PORT_BY_ID_V1 else None


def cognitive_scope_find_port_v1(snapshot: Mapping[str, Any], port_id: Any) -> Optional[Mapping[str, Any]]:
    """Return one stored DP row by normalized identifier without mutating the snapshot."""
    normalized = cognitive_scope_normalize_port_id_v1(port_id)
    if normalized is None:
        return None
    ports = snapshot.get("ports")
    if not isinstance(ports, list):
        return None
    for row in ports:
        if isinstance(row, Mapping) and row.get("port_id") == normalized:
            return row
    return None


def render_cognitive_scope_compact_snapshot_lines_v1(snapshot: Mapping[str, Any]) -> list[str]:
    """Render the complete DP00-DP18 circuit as a concise technician front panel."""
    lines = [
        "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- COMPACT SIGNAL PATH",
        "=" * 78,
        (
            f"snapshot={snapshot.get('snapshot_no') or 'live'} capture={snapshot.get('capture_kind')} "
            f"cycle={snapshot.get('cognitive_cycle')} controller_step={snapshot.get('controller_step')} "
            f"environment_step={snapshot.get('environment_step')}"
        ),
        (
            f"applied={snapshot.get('action_applied')!r} "
            f"selected_for_next_step={snapshot.get('action_selected_for_next_step')!r}"
        ),
        "One compact reading per architectural service point; full stored signal is available by DP drill-down.",
        "The trace is diagnostic-only, outside goat cognition, and signal injection remains disabled.",
        "-" * 78,
    ]

    ports = snapshot.get("ports")
    if not isinstance(ports, list):
        lines.append("(no port samples)")
        lines.append("=" * 78)
        return lines

    for row in ports:
        if not isinstance(row, Mapping):
            continue
        port_id = str(row.get("port_id") or "????")
        label = _COMPACT_PORT_LABELS_V1.get(port_id, str(row.get("name") or "UNKNOWN").upper())
        prefix = f"{port_id} {label:<13} "
        summary = _compact_port_signal_v1(row)
        wrapped = textwrap.wrap(
            prefix + summary,
            width=132,
            subsequent_indent=" " * len(prefix),
            break_long_words=False,
            break_on_hyphens=False,
        )
        lines.extend(wrapped or [prefix.rstrip()])

    lines.extend(
        [
            "-" * 78,
            "Inspect one stored diagnostic point for full details: DP00-DP18.",
            "=" * 78,
        ]
    )
    return lines


def render_cognitive_scope_port_detail_lines_v1(snapshot: Mapping[str, Any], port_id: Any) -> list[str]:
    """Render the complete stored signal for one selected diagnostic point."""
    normalized = cognitive_scope_normalize_port_id_v1(port_id)
    row = cognitive_scope_find_port_v1(snapshot, normalized) if normalized is not None else None
    lines = [
        "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- DIAGNOSTIC-POINT DETAIL",
        "=" * 78,
        (
            f"snapshot={snapshot.get('snapshot_no') or 'live'} cycle={snapshot.get('cognitive_cycle')} "
            f"controller_step={snapshot.get('controller_step')} environment_step={snapshot.get('environment_step')}"
        ),
    ]
    if row is None or normalized is None:
        lines.extend(
            [
                f"Requested diagnostic point {port_id!r} is not available. Use DP00-DP18.",
                "=" * 78,
            ]
        )
        return lines

    lines.extend(
        [
            f"{normalized}  {row.get('name')}",
            f"implementation={row.get('implementation')}  signal_status={row.get('signal_status')}",
            f"authority={row.get('authority')}",
            f"source={row.get('source')}",
            "-" * 78,
            "signal:",
        ]
    )
    signal = row.get("signal")
    if isinstance(signal, Mapping) and signal:
        rendered = json.dumps(_json_safe(signal), indent=2, sort_keys=True, ensure_ascii=True)
        lines.extend("  " + line for line in rendered.splitlines())
    else:
        lines.append("  (no active signal captured)")

    note = row.get("note")
    if isinstance(note, str) and note:
        lines.extend(["", "note:"])
        lines.extend(
            textwrap.wrap(
                "  " + note,
                width=132,
                subsequent_indent="  ",
                break_long_words=False,
                break_on_hyphens=False,
            )
        )
    lines.append("=" * 78)
    return lines


def _one_line_value(value: Any) -> str:
    """Return a deterministic compact value for one terminal signal field."""
    if isinstance(value, str):
        return value
    return json.dumps(_json_safe(value), sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def render_cognitive_scope_snapshot_lines_v1(snapshot: Mapping[str, Any]) -> list[str]:
    """Render one complete cognitive-scope snapshot in circuit order."""
    lines = [
        "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- SNAPSHOT",
        "=" * 78,
        (
            f"snapshot={snapshot.get('snapshot_no') or 'live'} capture={snapshot.get('capture_kind')} "
            f"cognitive_cycle={snapshot.get('cognitive_cycle')} controller_step={snapshot.get('controller_step')} "
            f"environment_step={snapshot.get('environment_step')}"
        ),
        (
            f"action_applied={snapshot.get('action_applied')!r} "
            f"action_selected_for_next_step={snapshot.get('action_selected_for_next_step')!r}"
        ),
        "DP00 is the external simulation reference; DP01-DP18 are the eighteen cognitive/architectural service points.",
        "The retained trace is diagnostic-only and cannot be read by CCA8 cognition. Injection is disabled.",
        "Phase 1 samples each port's latest stable register at cycle end; exact per-stage timestamps are future work.",
        "-" * 78,
    ]

    ports = snapshot.get("ports")
    if not isinstance(ports, list):
        lines.append("(no port samples)")
        return lines

    for row in ports:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"{row.get('port_id')}  {row.get('name')}  "
            f"[{row.get('implementation')} | {row.get('signal_status')} | {row.get('authority')}]"
        )
        signal = row.get("signal")
        if isinstance(signal, Mapping) and signal:
            pieces = [f"{key}={_one_line_value(value)}" for key, value in signal.items()]
            wrapped = textwrap.wrap(
                "  " + "  ".join(pieces),
                width=132,
                subsequent_indent="    ",
                break_long_words=False,
                break_on_hyphens=False,
            )
            lines.extend(wrapped or ["  (empty signal)"])
        else:
            lines.append("  (no active signal captured)")
        note = row.get("note")
        if isinstance(note, str) and note:
            lines.extend(
                textwrap.wrap(
                    "  note: " + note,
                    width=132,
                    subsequent_indent="        ",
                    break_long_words=False,
                    break_on_hyphens=False,
                )
            )
        lines.append("")

    lines.append("=" * 78)
    return lines


def render_cognitive_scope_trace_index_lines_v1(ctx: Any, *, limit: int = 20) -> list[str]:
    """Render a compact index of retained digital-storage scope snapshots."""
    summary = cognitive_scope_trace_summary_v1(ctx)
    lines = [
        "CCA8 COGNITIVE STORAGE OSCILLOSCOPE -- RETAINED SNAPSHOTS",
        "=" * 78,
        (
            f"status={summary['status']} retained={summary['retained_count']}/{summary['capacity']} "
            f"total_captured={summary['total_capture_count']} oldest={summary['oldest_snapshot_no']} "
            f"latest={summary['latest_snapshot_no']}"
        ),
        "Diagnostic trace only; not cognitive memory. Injection is disabled.",
        "-" * 78,
    ]
    trace = getattr(ctx, "cognitive_scope_trace_v1", None)
    rows = trace if isinstance(trace, list) else []
    if not rows:
        lines.append("(no retained cognitive-cycle snapshots; run Menu 35 or 37 first)")
        lines.append("=" * 78)
        return lines

    safe_limit = max(1, int(limit))
    for row in rows[-safe_limit:]:
        if not isinstance(row, Mapping):
            continue
        lines.append(
            f"snapshot={row.get('snapshot_no')} cycle={row.get('cognitive_cycle')} "
            f"controller_step={row.get('controller_step')} env_step={row.get('environment_step')} "
            f"applied={row.get('action_applied')!r} selected={row.get('action_selected_for_next_step')!r}"
        )
    if len(rows) > safe_limit:
        lines.append(f"... {len(rows) - safe_limit} older retained snapshot(s) not shown")
    lines.append("=" * 78)
    return lines
