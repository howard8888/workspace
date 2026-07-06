# -*- coding: utf-8 -*-
"""Small NavMap payload helpers for CCA8.

Purpose
-------
This module defines the first tiny, JSON-safe map object for the CCA8
map-matching path. It does not integrate with the runner, WorldGraph, policy
selection, or memory write-back yet.

The near-term role is to give CCA8 a stable payload shape for a simple fused
``scene_body`` stream:

- posture
- mom_distance
- nipple_state
- zone

Design stance
-------------
- A NavMap payload is a hypothesis/working representation, not confirmed truth.
- Slot values are normalized into compact string tokens so matching code can
  compare maps without needing CCA8 runner objects.
- Malformed inputs are tolerated and normalized to empty/safe structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Iterable, Mapping, Optional
import math

__version__ = "0.9.0"
__all__ = [
    "NAVMAP_PAYLOAD_SCHEMA_V1",
    "NAVMAP_RESIDUAL_SCHEMA_V1",
    "NAVMAP_MATCH_SCHEMA_V1",
    "NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1",
    "NAVMAP_CYCLE_SCHEMA_V1",
    "NAVMAP_STORE_UPDATE_SCHEMA_V1",
    "NAVMAP_TRANSITION_SCHEMA_V1",
    "NAVMAP_POLICY_OUTCOME_SCHEMA_V1",
    "NavMapPayloadV1",
    "NavMapResidualV1",
    "NavMapMatchV1",
    "NavMapLearningProposalV1",
    "NavMapCycleV1",
    "NavMapStoreUpdateV1",
    "NavMapTransitionV1",
    "NavMapPolicyOutcomeV1",
    "make_navmap_payload_v1",
    "navmap_payload_slots_v1",
    "navmap_slots_from_env_obs_v1",
    "navmap_payload_from_env_obs_v1",
    "navmap_residual_v1",
    "match_navmap_payloads_v1",
    "navmap_learning_proposal_from_match_v1",
    "navmap_apply_learning_proposal_v1",
    "make_navmap_transition_v1",
    "navmap_policy_outcome_from_transition_v1",
    "navmap_scene_body_cycle_from_env_obs_v1",
    "NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1",
    "NavMapObservationUpdateV1",
    "navmap_observation_update_from_env_obs_v1",
    "__version__",
]

NAVMAP_PAYLOAD_SCHEMA_V1 = "navmap_payload_v1"
NAVMAP_RESIDUAL_SCHEMA_V1 = "navmap_residual_v1"
NAVMAP_MATCH_SCHEMA_V1 = "navmap_match_v1"
NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1 = "navmap_learning_proposal_v1"
NAVMAP_CYCLE_SCHEMA_V1 = "navmap_cycle_v1"
NAVMAP_STORE_UPDATE_SCHEMA_V1 = "navmap_store_update_v1"
NAVMAP_TRANSITION_SCHEMA_V1 = "navmap_transition_v1"
NAVMAP_POLICY_OUTCOME_SCHEMA_V1 = "navmap_policy_outcome_v1"
NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1 = "navmap_observation_update_v1"
_DEFAULT_MAP_KIND_V1 = "local_navmap"
_DEFAULT_MODALITY_V1 = "scene_body"
_DEFAULT_SOURCE_V1 = "WorkingMap.Scratch"


def _now_iso_v1() -> str:
    """Return a short local timestamp for JSON-safe trace records."""
    return datetime.now().isoformat(timespec="seconds")


def _token_v1(value: Any) -> str:
    """Normalize a slot-like token into a compact lowercase string."""
    if value is None:
        return ""
    text = str(value).strip().lower()
    return "_".join(text.split())


def _source_text_v1(value: Any) -> str:
    """Normalize a provenance/source label while preserving normal capitalization."""
    if value is None:
        return _DEFAULT_SOURCE_V1
    text = str(value).strip()
    return text or _DEFAULT_SOURCE_V1


def _confidence_float_v1(value: Any) -> float:
    """Return a best-effort float confidence value."""
    if isinstance(value, bool):
        return 1.0
    try:
        return float(value)
    except Exception:
        return 1.0


def _score_float_v1(value: Any) -> float:
    """Return a bounded 0.0..1.0 score-like float."""
    try:
        score = float(value)
    except Exception:
        return 0.0

    if math.isnan(score):
        return 0.0
    if score < 0.0:
        return 0.0
    if score > 1.0:
        return 1.0
    return score


def _finite_float_v1(value: Any, default: float = 0.0) -> float:
    """Return a finite float or a safe default."""
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except Exception:
        return default
    if math.isnan(number) or math.isinf(number):
        return default
    return number


def _ratio_v1(numer: int, denom: int) -> float:
    """Return a rounded ratio for small slot-count scores."""
    if denom <= 0:
        return 0.0
    return round(float(numer) / float(denom), 6)


def _json_safe_scalar_v1(value: Any) -> Any:
    """Return a small JSON-safe scalar representation for provenance fields."""
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    return str(value)


def _json_safe_dict_v1(value: Any) -> dict[str, Any]:
    """Return a shallow/nested JSON-safe dict with string keys."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, Any] = {}
    for key, val in value.items():
        if not isinstance(key, str):
            continue
        clean_key = key.strip()
        if not clean_key:
            continue
        if isinstance(val, Mapping):
            out[clean_key] = _json_safe_dict_v1(val)
        elif isinstance(val, (list, tuple)):
            out[clean_key] = [_json_safe_scalar_v1(item) for item in val]
        else:
            out[clean_key] = _json_safe_scalar_v1(val)
    return out


def _slot_map_v1(value: Any) -> dict[str, str]:
    """Return a normalized string->string slot map from a mapping-like object."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, str] = {}
    for key, val in value.items():
        if not isinstance(key, str):
            continue
        norm_key = _token_v1(key)
        if not norm_key or val is None:
            continue
        if isinstance(val, (Mapping, list, tuple, set)):
            continue
        norm_val = _token_v1(val)
        if not norm_val:
            continue
        out[norm_key] = norm_val
    return out


@dataclass(slots=True)
class NavMapPayloadV1:
    """A tiny JSON-safe payload for one local CCA8 NavMap hypothesis."""

    map_kind: str = _DEFAULT_MAP_KIND_V1
    modality: str = _DEFAULT_MODALITY_V1
    slots: dict[str, str] = field(default_factory=dict)
    confidence: float = 1.0
    source: str = _DEFAULT_SOURCE_V1
    basis: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_PAYLOAD_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize direct dataclass construction as well as helper construction."""
        self.map_kind = _token_v1(self.map_kind) or _DEFAULT_MAP_KIND_V1
        self.modality = _token_v1(self.modality) or _DEFAULT_MODALITY_V1
        self.slots = _slot_map_v1(self.slots)
        self.confidence = _confidence_float_v1(self.confidence)
        self.source = _source_text_v1(self.source)
        self.basis = _json_safe_dict_v1(self.basis)
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_PAYLOAD_SCHEMA_V1)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "map_kind": self.map_kind,
            "modality": self.modality,
            "slots": dict(self.slots),
            "confidence": float(self.confidence),
            "source": self.source,
            "basis": _json_safe_dict_v1(self.basis),
            "created_at": self.created_at,
        }

    @classmethod
    def from_dict(cls, data: Mapping[str, Any]) -> "NavMapPayloadV1":
        """Build a NavMapPayloadV1 from a JSON-safe dict."""
        return cls(
            map_kind=str(data.get("map_kind") or _DEFAULT_MAP_KIND_V1),
            modality=str(data.get("modality") or _DEFAULT_MODALITY_V1),
            slots=_slot_map_v1(data.get("slots")),
            confidence=_confidence_float_v1(data.get("confidence")),
            source=_source_text_v1(data.get("source")),
            basis=_json_safe_dict_v1(data.get("basis")),
            created_at=str(data.get("created_at") or _now_iso_v1()),
            schema=str(data.get("schema") or NAVMAP_PAYLOAD_SCHEMA_V1),
        )


def make_navmap_payload_v1(
    slots: Mapping[str, Any],
    *,
    map_kind: str = _DEFAULT_MAP_KIND_V1,
    modality: str = _DEFAULT_MODALITY_V1,
    confidence: float = 1.0,
    source: str = _DEFAULT_SOURCE_V1,
    basis: Optional[Mapping[str, Any]] = None,
) -> NavMapPayloadV1:
    """Create a normalized NavMapPayloadV1."""
    return NavMapPayloadV1(
        map_kind=map_kind,
        modality=modality,
        slots=_slot_map_v1(slots),
        confidence=_confidence_float_v1(confidence),
        source=_source_text_v1(source),
        basis=_json_safe_dict_v1(basis or {}),
    )


def navmap_payload_slots_v1(payload: NavMapPayloadV1 | Mapping[str, Any]) -> dict[str, str]:
    """Return a normalized copy of the slot map from a payload-like object."""
    if isinstance(payload, NavMapPayloadV1):
        return dict(payload.slots)
    if isinstance(payload, Mapping):
        if any(key in payload for key in ("schema", "map_kind", "modality", "slots", "confidence", "source", "basis")):
            return _slot_map_v1(payload.get("slots"))
        return _slot_map_v1(payload)
    return {}


def _payload_from_any_v1(value: Any) -> NavMapPayloadV1:
    """Return a normalized payload from a payload object, payload dict, or raw slot dict."""
    if isinstance(value, NavMapPayloadV1):
        return value
    if isinstance(value, Mapping):
        if any(key in value for key in ("schema", "map_kind", "modality", "slots", "confidence", "source", "basis")):
            return NavMapPayloadV1.from_dict(value)
        return make_navmap_payload_v1(value)
    return NavMapPayloadV1(slots={})


def _obs_field_v1(env_obs: Any, name: str, default: Any) -> Any:
    """Read a field from an EnvObservation-like object or dict."""
    if env_obs is None:
        return default
    if isinstance(env_obs, Mapping):
        return env_obs.get(name, default)
    return getattr(env_obs, name, default)


def _obs_predicate_set_v1(env_obs: Any) -> set[str]:
    """Return normalized predicate tokens from an EnvObservation-like object."""
    raw = _obs_field_v1(env_obs, "predicates", [])
    if not isinstance(raw, Iterable) or isinstance(raw, (str, bytes)):
        return set()
    return {str(item).strip().lower() for item in raw if isinstance(item, str) and item.strip()}


def _obs_meta_v1(env_obs: Any) -> dict[str, Any]:
    """Return a shallow metadata dict from an EnvObservation-like object."""
    raw = _obs_field_v1(env_obs, "env_meta", {})
    return dict(raw) if isinstance(raw, Mapping) else {}


def _near_far_from_value_v1(value: Any) -> str:
    """Normalize near/far-ish observation values for scene_body slots."""
    token = _token_v1(value)
    if token in ("near", "close", "touching"):
        return "near"
    if token == "far":
        return "far"
    return ""


def _nipple_state_from_value_v1(value: Any) -> str:
    """Normalize nipple-state-ish observation values for scene_body slots."""
    token = _token_v1(value)
    if token in ("latched", "latch", "milk_drinking", "drinking"):
        return "latched"
    if token in ("found", "visible", "reachable"):
        return "found"
    if token in ("hidden", "none", "not_found"):
        return "hidden"
    return ""


def _mismatched_slot_map_v1(value: Any) -> dict[str, dict[str, str]]:
    """Normalize the residual's slot mismatch map."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, dict[str, str]] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, Mapping):
            continue
        norm_key = _token_v1(key)
        if not norm_key:
            continue
        current = _token_v1(val.get("current"))
        candidate = _token_v1(val.get("candidate"))
        if current or candidate:
            out[norm_key] = {"current": current, "candidate": candidate}
    return out


def _candidate_sequence_v1(candidates: Any) -> list[Any]:
    """Return a stable candidate sequence from a list/tuple or dict-like store."""
    if candidates is None or isinstance(candidates, (str, bytes)):
        return []
    if isinstance(candidates, Mapping):
        return list(candidates.values())
    if isinstance(candidates, Iterable):
        return list(candidates)
    return []


def _payload_dict_with_slots_v1(value: Any) -> dict[str, Any]:
    """Return a normalized payload dict only when it contains at least one slot."""
    if not isinstance(value, (NavMapPayloadV1, Mapping)):
        return {}
    payload = _payload_from_any_v1(value).as_dict()
    return payload if payload.get("slots") else {}


def _candidate_payload_dicts_v1(candidates: Any) -> list[dict[str, Any]]:
    """Return normalized, non-empty candidate payload dicts from a candidate store."""
    out: list[dict[str, Any]] = []
    for raw_candidate in _candidate_sequence_v1(candidates):
        payload = _payload_dict_with_slots_v1(raw_candidate)
        if payload:
            out.append(payload)
    return out


def _candidate_index_int_v1(value: Any) -> Optional[int]:
    """Return a non-negative candidate index or None."""
    if value is None or isinstance(value, bool):
        return None
    try:
        index = int(value)
    except Exception:
        return None
    return index if index >= 0 else None


def _max_candidates_int_v1(value: Any) -> int:
    """Return a positive candidate-store bound."""
    if isinstance(value, bool):
        return 50
    try:
        count = int(value)
    except Exception:
        return 50
    return count if count > 0 else 50


def _proposal_field_v1(proposal: Any, name: str, default: Any) -> Any:
    """Read a field from a proposal object or proposal-like dict."""
    if isinstance(proposal, NavMapLearningProposalV1):
        return getattr(proposal, name, default)
    if isinstance(proposal, Mapping):
        return proposal.get(name, default)
    return default


def _drive_delta_map_v1(value: Any) -> dict[str, float]:
    """Return a normalized drive-delta map such as hunger=-0.2."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, float] = {}
    for key, val in value.items():
        if not isinstance(key, str) or isinstance(val, bool):
            continue
        norm_key = _token_v1(key)
        if not norm_key:
            continue
        try:
            delta = float(val)
        except Exception:
            continue
        if math.isnan(delta) or math.isinf(delta):
            continue
        out[norm_key] = delta
    return out


def _slot_signature_v1(slots: Any) -> str:
    """Return a stable signature string for a normalized slot map."""
    slot_map = _slot_map_v1(slots)
    return "|".join(f"{key}={slot_map[key]}" for key in sorted(slot_map))


def _slot_change_map_v1(value: Any) -> dict[str, dict[str, str]]:
    """Normalize a slot-change map with before/after values."""
    if not isinstance(value, Mapping):
        return {}

    out: dict[str, dict[str, str]] = {}
    for key, val in value.items():
        if not isinstance(key, str) or not isinstance(val, Mapping):
            continue
        norm_key = _token_v1(key)
        if not norm_key:
            continue
        before = _token_v1(val.get("before"))
        after = _token_v1(val.get("after"))
        if before or after:
            out[norm_key] = {"before": before, "after": after}
    return out


def _slot_changes_from_residual_v1(residual: Any) -> dict[str, dict[str, str]]:
    """Return before/after slot changes from an after-vs-before residual."""
    if not isinstance(residual, NavMapResidualV1):
        return {}

    out: dict[str, dict[str, str]] = {}
    for key, mismatch_val in residual.mismatched_slots.items():
        before = _token_v1(mismatch_val.get("candidate"))
        after = _token_v1(mismatch_val.get("current"))
        if before or after:
            out[key] = {"before": before, "after": after}
    for key, novel_val in residual.novel_slots.items():
        after = _token_v1(novel_val)
        if after:
            out[key] = {"before": "", "after": after}
    for key, missing_val in residual.missing_slots.items():
        before = _token_v1(missing_val)
        if before:
            out[key] = {"before": before, "after": ""}
    return out


def _transition_field_v1(transition: Any, name: str, default: Any) -> Any:
    """Read a field from a transition object or transition-like dict."""
    if isinstance(transition, NavMapTransitionV1):
        return getattr(transition, name, default)
    if isinstance(transition, Mapping):
        return transition.get(name, default)
    return default


def navmap_slots_from_env_obs_v1(env_obs: Any) -> dict[str, str]:
    """Extract the first scene_body NavMap slots from an EnvObservation-like object.

    This helper is deliberately runner-neutral. It accepts any object or dict
    with ``predicates`` and ``env_meta`` fields and returns the same first goat
    slot vocabulary used by the current prediction bridge: posture,
    mom_distance, nipple_state, and zone.
    """
    if env_obs is None:
        return {}

    preds = _obs_predicate_set_v1(env_obs)
    meta = _obs_meta_v1(env_obs)
    out: dict[str, str] = {}

    if "posture:standing" in preds:
        out["posture"] = "standing"
    elif "posture:fallen" in preds:
        out["posture"] = "fallen"
    elif "resting" in preds or "posture:resting" in preds or "state:resting" in preds:
        out["posture"] = "resting"
    else:
        posture = _token_v1(meta.get("posture") or meta.get("kid_posture"))
        if posture in ("standing", "fallen", "resting"):
            out["posture"] = posture
        elif posture == "latched":
            out["posture"] = "standing"

    if "proximity:mom:close" in preds or "proximity:mom:near" in preds:
        out["mom_distance"] = "near"
    elif "proximity:mom:far" in preds:
        out["mom_distance"] = "far"
    else:
        mom_distance = _near_far_from_value_v1(meta.get("mom_distance"))
        if not mom_distance:
            mom_distance = _near_far_from_value_v1(meta.get("mom_proximity_from_raw"))
        if mom_distance:
            out["mom_distance"] = mom_distance

    if "nipple:latched" in preds or "milk:drinking" in preds:
        out["nipple_state"] = "latched"
    elif "nipple:found" in preds:
        out["nipple_state"] = "found"
    elif "nipple:hidden" in preds:
        out["nipple_state"] = "hidden"
    else:
        nipple_state = _nipple_state_from_value_v1(meta.get("nipple_state"))
        if nipple_state:
            out["nipple_state"] = nipple_state

    zone_val = meta.get("zone")
    if isinstance(zone_val, str) and zone_val.strip():
        out["zone"] = zone_val.strip()

    return out


def navmap_payload_from_env_obs_v1(
    env_obs: Any,
    *,
    confidence: float = 1.0,
    source: str = "EnvObservation.scene_body",
    basis: Optional[Mapping[str, Any]] = None,
) -> NavMapPayloadV1:
    """Build a scene_body NavMapPayloadV1 from an EnvObservation-like object.

    This is a read-only conversion. It does not perform matching, update memory,
    write WorldGraph facts, or affect policy selection.
    """
    slots = navmap_slots_from_env_obs_v1(env_obs)
    predicates = _obs_predicate_set_v1(env_obs)
    meta = _obs_meta_v1(env_obs)

    payload_basis = _json_safe_dict_v1(basis or {})
    payload_basis["payload_source"] = "navmap_payload_from_env_obs_v1"
    payload_basis["predicate_count"] = len(predicates)

    for key in ("scenario_stage", "time_since_birth", "position"):
        value = meta.get(key)
        if value is not None:
            payload_basis[key] = _json_safe_scalar_v1(value)

    return make_navmap_payload_v1(
        slots,
        map_kind=_DEFAULT_MAP_KIND_V1,
        modality=_DEFAULT_MODALITY_V1,
        confidence=confidence,
        source=source,
        basis=payload_basis,
    )


def _basis_with_update_note_v1(
    original_basis: Any,
    *,
    action: str,
    match: "NavMapMatchV1",
    residual: "NavMapResidualV1",
) -> dict[str, Any]:
    """Return JSON-safe provenance for a proposed learned/updated NavMap."""
    basis = _json_safe_dict_v1(original_basis)
    basis["proposal_source"] = NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1
    basis["proposal_action"] = str(action or "")
    basis["match_score"] = float(match.score)
    basis["candidate_index"] = match.candidate_index
    basis["residual_count"] = int(residual.residual_count)
    return basis


@dataclass(slots=True)
class NavMapResidualV1:
    """Slot-level residual between a current NavMap and one candidate NavMap."""

    current_slots: dict[str, str]
    candidate_slots: dict[str, str]
    matched_slots: dict[str, str] = field(default_factory=dict)
    mismatched_slots: dict[str, dict[str, str]] = field(default_factory=dict)
    missing_slots: dict[str, str] = field(default_factory=dict)
    novel_slots: dict[str, str] = field(default_factory=dict)
    score: float = 0.0
    current_coverage: float = 0.0
    candidate_coverage: float = 0.0
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_RESIDUAL_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize direct construction as well as helper construction."""
        self.current_slots = _slot_map_v1(self.current_slots)
        self.candidate_slots = _slot_map_v1(self.candidate_slots)
        self.matched_slots = _slot_map_v1(self.matched_slots)
        self.mismatched_slots = _mismatched_slot_map_v1(self.mismatched_slots)
        self.missing_slots = _slot_map_v1(self.missing_slots)
        self.novel_slots = _slot_map_v1(self.novel_slots)
        self.score = _score_float_v1(self.score)
        self.current_coverage = _score_float_v1(self.current_coverage)
        self.candidate_coverage = _score_float_v1(self.candidate_coverage)
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_RESIDUAL_SCHEMA_V1)

    @property
    def residual_count(self) -> int:
        """Number of non-matching residual slots."""
        return len(self.mismatched_slots) + len(self.missing_slots) + len(self.novel_slots)

    @property
    def exact_match(self) -> bool:
        """True when both maps contain at least one slot and all slots agree."""
        return bool(self.current_slots or self.candidate_slots) and self.residual_count == 0 and self.score == 1.0

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "current_slots": dict(self.current_slots),
            "candidate_slots": dict(self.candidate_slots),
            "matched_slots": dict(self.matched_slots),
            "mismatched_slots": {key: dict(val) for key, val in self.mismatched_slots.items()},
            "missing_slots": dict(self.missing_slots),
            "novel_slots": dict(self.novel_slots),
            "score": float(self.score),
            "current_coverage": float(self.current_coverage),
            "candidate_coverage": float(self.candidate_coverage),
            "residual_count": int(self.residual_count),
            "exact_match": bool(self.exact_match),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapMatchV1:
    """Best candidate match for a current NavMap payload."""

    current: dict[str, Any]
    candidate: dict[str, Any]
    residual: NavMapResidualV1
    candidate_index: Optional[int] = None
    score: float = 0.0
    matched: bool = False
    reason: str = ""
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_MATCH_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize simple scalar fields."""
        self.score = _score_float_v1(self.score)
        self.matched = bool(self.matched)
        self.reason = str(self.reason or "")
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_MATCH_SCHEMA_V1)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "candidate_index": self.candidate_index,
            "score": float(self.score),
            "matched": bool(self.matched),
            "reason": self.reason,
            "current": dict(self.current),
            "candidate": dict(self.candidate),
            "residual": self.residual.as_dict(),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapLearningProposalV1:
    """Pure proposal for keeping, updating, or creating a NavMap candidate.

    This record is intentionally not a memory write. It is the map-learning
    bridge between matching and future storage/policy association code.
    """

    action: str
    current: dict[str, Any]
    candidate: dict[str, Any]
    proposed_payload: dict[str, Any]
    residual: NavMapResidualV1
    candidate_index: Optional[int] = None
    score: float = 0.0
    accepted_match: bool = False
    reason: str = ""
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize scalar proposal fields."""
        self.action = _token_v1(self.action)
        self.score = _score_float_v1(self.score)
        self.accepted_match = bool(self.accepted_match)
        self.reason = str(self.reason or "")
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "action": self.action,
            "candidate_index": self.candidate_index,
            "score": float(self.score),
            "accepted_match": bool(self.accepted_match),
            "reason": self.reason,
            "current": dict(self.current),
            "candidate": dict(self.candidate),
            "proposed_payload": dict(self.proposed_payload),
            "residual": self.residual.as_dict(),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapCycleV1:
    """One read-only scene_body NavMap cycle result."""

    current_payload: dict[str, Any]
    match: NavMapMatchV1
    proposal: NavMapLearningProposalV1
    candidate_count: int = 0
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_CYCLE_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize scalar cycle fields."""
        try:
            self.candidate_count = max(0, int(self.candidate_count))
        except Exception:
            self.candidate_count = 0
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_CYCLE_SCHEMA_V1)

    @property
    def action(self) -> str:
        """Learning proposal action for quick diagnostics."""
        return self.proposal.action

    @property
    def matched(self) -> bool:
        """Whether the cycle accepted a candidate match."""
        return bool(self.match.matched)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "candidate_count": int(self.candidate_count),
            "matched": bool(self.matched),
            "action": self.action,
            "current_payload": dict(self.current_payload),
            "match": self.match.as_dict(),
            "proposal": self.proposal.as_dict(),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapStoreUpdateV1:
    """Pure result of applying one learning proposal to a candidate list."""

    action: str
    candidates: list[dict[str, Any]] = field(default_factory=list)
    before_count: int = 0
    after_count: int = 0
    changed: bool = False
    candidate_index: Optional[int] = None
    reason: str = ""
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_STORE_UPDATE_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize scalar fields and candidate payloads."""
        self.action = _token_v1(self.action) or "ignore"
        self.candidates = _candidate_payload_dicts_v1(self.candidates)
        try:
            self.before_count = max(0, int(self.before_count))
        except Exception:
            self.before_count = 0
        try:
            self.after_count = max(0, int(self.after_count))
        except Exception:
            self.after_count = len(self.candidates)
        self.changed = bool(self.changed)
        self.candidate_index = _candidate_index_int_v1(self.candidate_index)
        self.reason = str(self.reason or "")
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_STORE_UPDATE_SCHEMA_V1)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "action": self.action,
            "changed": bool(self.changed),
            "candidate_index": self.candidate_index,
            "before_count": int(self.before_count),
            "after_count": int(self.after_count),
            "reason": self.reason,
            "candidates": _candidate_payload_dicts_v1(self.candidates),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapTransitionV1:
    """Pure action-conditioned transition between two NavMap payloads."""

    before_payload: dict[str, Any]
    after_payload: dict[str, Any]
    action: str = ""
    residual: Optional[NavMapResidualV1] = None
    reward: float = 0.0
    drive_delta: dict[str, float] = field(default_factory=dict)
    basis: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_TRANSITION_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize transition fields and recompute missing residuals."""
        self.before_payload = _payload_from_any_v1(self.before_payload).as_dict()
        self.after_payload = _payload_from_any_v1(self.after_payload).as_dict()
        self.action = _token_v1(self.action)
        if not isinstance(self.residual, NavMapResidualV1):
            self.residual = navmap_residual_v1(self.after_payload, self.before_payload)
        self.reward = _finite_float_v1(self.reward)
        self.drive_delta = _drive_delta_map_v1(self.drive_delta)
        self.basis = _json_safe_dict_v1(self.basis)
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_TRANSITION_SCHEMA_V1)

    @property
    def changed(self) -> bool:
        """True when the after-map differs from the before-map."""
        residual = self.residual
        return bool(isinstance(residual, NavMapResidualV1) and residual.residual_count > 0)

    @property
    def changed_slots(self) -> int:
        """Number of slot changes in the after-vs-before residual."""
        residual = self.residual
        if not isinstance(residual, NavMapResidualV1):
            return 0
        return int(residual.residual_count)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        residual = self.residual
        if not isinstance(residual, NavMapResidualV1):
            residual = navmap_residual_v1(self.after_payload, self.before_payload)
        return {
            "schema": self.schema,
            "action": self.action,
            "reward": float(self.reward),
            "drive_delta": dict(self.drive_delta),
            "changed": bool(self.changed),
            "changed_slots": int(self.changed_slots),
            "before_payload": dict(self.before_payload),
            "after_payload": dict(self.after_payload),
            "residual": residual.as_dict(),
            "basis": _json_safe_dict_v1(self.basis),
            "created_at": self.created_at,
        }



@dataclass(slots=True)
class NavMapPolicyOutcomeV1:
    """One learned action outcome sample for a NavMap context."""

    action: str
    context_slots: dict[str, str]
    expected_slots: dict[str, str]
    slot_changes: dict[str, dict[str, str]] = field(default_factory=dict)
    reward: float = 0.0
    drive_delta: dict[str, float] = field(default_factory=dict)
    success: bool = False
    confidence: float = 1.0
    sample_count: int = 1
    context_signature: str = ""
    policy_key: str = ""
    basis: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_POLICY_OUTCOME_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize policy-outcome fields."""
        self.action = _token_v1(self.action)
        self.context_slots = _slot_map_v1(self.context_slots)
        self.expected_slots = _slot_map_v1(self.expected_slots)
        self.slot_changes = _slot_change_map_v1(self.slot_changes)
        if not self.slot_changes:
            residual = navmap_residual_v1(self.expected_slots, self.context_slots)
            self.slot_changes = _slot_changes_from_residual_v1(residual)
        self.reward = _finite_float_v1(self.reward)
        self.drive_delta = _drive_delta_map_v1(self.drive_delta)
        self.success = bool(self.success)
        self.confidence = _score_float_v1(self.confidence)
        try:
            self.sample_count = max(0, int(self.sample_count))
        except Exception:
            self.sample_count = 0
        self.context_signature = self.context_signature or _slot_signature_v1(self.context_slots)
        self.policy_key = self.policy_key or self._make_policy_key()
        self.basis = _json_safe_dict_v1(self.basis)
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_POLICY_OUTCOME_SCHEMA_V1)

    def _make_policy_key(self) -> str:
        """Return the stable context/action key for later policy indexing."""
        if self.context_signature and self.action:
            return f"{self.context_signature}::{self.action}"
        if self.action:
            return self.action
        return self.context_signature

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "action": self.action,
            "context_signature": self.context_signature,
            "policy_key": self.policy_key,
            "context_slots": dict(self.context_slots),
            "expected_slots": dict(self.expected_slots),
            "slot_changes": {key: dict(val) for key, val in self.slot_changes.items()},
            "reward": float(self.reward),
            "drive_delta": dict(self.drive_delta),
            "success": bool(self.success),
            "confidence": float(self.confidence),
            "sample_count": int(self.sample_count),
            "basis": _json_safe_dict_v1(self.basis),
            "created_at": self.created_at,
        }


@dataclass(slots=True)
class NavMapObservationUpdateV1:
    """One pure observation-to-candidate-store NavMap update result."""

    current_payload: dict[str, Any]
    cycle: Any
    store_update: Any
    created_at: str = field(default_factory=_now_iso_v1)
    schema: str = NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1

    def __post_init__(self) -> None:
        """Normalize payload and guard against malformed direct construction."""
        self.current_payload = _payload_from_any_v1(self.current_payload).as_dict()
        if not isinstance(self.cycle, NavMapCycleV1):
            match = match_navmap_payloads_v1(self.current_payload, [])
            proposal = navmap_learning_proposal_from_match_v1(match)
            self.cycle = NavMapCycleV1(
                current_payload=self.current_payload,
                match=match,
                proposal=proposal,
                candidate_count=0,
            )
        if not isinstance(self.store_update, NavMapStoreUpdateV1):
            self.store_update = NavMapStoreUpdateV1(
                action="ignore",
                candidates=[],
                before_count=0,
                after_count=0,
                changed=False,
                reason="invalid_store_update",
            )
        self.created_at = str(self.created_at or _now_iso_v1())
        self.schema = str(self.schema or NAVMAP_OBSERVATION_UPDATE_SCHEMA_V1)

    @property
    def action(self) -> str:
        """Learning/store action chosen for this observation update."""
        return str(self.store_update.action or self.cycle.action)

    @property
    def matched(self) -> bool:
        """Whether the observation matched an existing candidate."""
        return bool(self.cycle.matched)

    @property
    def changed(self) -> bool:
        """Whether applying the proposal changed the candidate store."""
        return bool(self.store_update.changed)

    def as_dict(self) -> dict[str, Any]:
        """Return the canonical JSON-safe representation."""
        return {
            "schema": self.schema,
            "action": self.action,
            "matched": bool(self.matched),
            "changed": bool(self.changed),
            "candidate_count_before": int(self.store_update.before_count),
            "candidate_count_after": int(self.store_update.after_count),
            "current_payload": dict(self.current_payload),
            "cycle": self.cycle.as_dict(),
            "store_update": self.store_update.as_dict(),
            "created_at": self.created_at,
        }


def navmap_residual_v1(
    current: NavMapPayloadV1 | Mapping[str, Any],
    candidate: NavMapPayloadV1 | Mapping[str, Any],
) -> NavMapResidualV1:
    """Compare one current NavMap payload with one candidate and return the residual."""
    current_slots = navmap_payload_slots_v1(current)
    candidate_slots = navmap_payload_slots_v1(candidate)
    current_keys = set(current_slots)
    candidate_keys = set(candidate_slots)
    all_keys = sorted(current_keys | candidate_keys)

    matched_slots: dict[str, str] = {}
    mismatched_slots: dict[str, dict[str, str]] = {}
    missing_slots: dict[str, str] = {}
    novel_slots: dict[str, str] = {}

    for key in all_keys:
        current_val = current_slots.get(key)
        candidate_val = candidate_slots.get(key)
        if current_val is None and candidate_val is not None:
            missing_slots[key] = candidate_val
        elif current_val is not None and candidate_val is None:
            novel_slots[key] = current_val
        elif current_val == candidate_val and current_val is not None:
            matched_slots[key] = current_val
        elif current_val is not None and candidate_val is not None:
            mismatched_slots[key] = {"current": current_val, "candidate": candidate_val}

    matched_count = len(matched_slots)
    score = _ratio_v1(matched_count, len(all_keys))
    current_coverage = _ratio_v1(matched_count, len(current_slots))
    candidate_coverage = _ratio_v1(matched_count, len(candidate_slots))

    return NavMapResidualV1(
        current_slots=current_slots,
        candidate_slots=candidate_slots,
        matched_slots=matched_slots,
        mismatched_slots=mismatched_slots,
        missing_slots=missing_slots,
        novel_slots=novel_slots,
        score=score,
        current_coverage=current_coverage,
        candidate_coverage=candidate_coverage,
    )


def match_navmap_payloads_v1(
    current: NavMapPayloadV1 | Mapping[str, Any],
    candidates: Iterable[NavMapPayloadV1 | Mapping[str, Any]] | Mapping[str, Any],
    *,
    min_score: float = 0.01,
    same_modality_only: bool = True,
) -> NavMapMatchV1:
    """Return the best matching candidate NavMap for the current payload."""
    current_payload = _payload_from_any_v1(current)
    current_dict = current_payload.as_dict()
    candidate_items = _candidate_sequence_v1(candidates)

    best_index: Optional[int] = None
    best_payload: Optional[NavMapPayloadV1] = None
    best_residual: Optional[NavMapResidualV1] = None
    min_score_f = _score_float_v1(min_score)

    for index, raw_candidate in enumerate(candidate_items):
        candidate_payload = _payload_from_any_v1(raw_candidate)
        if same_modality_only and candidate_payload.modality != current_payload.modality:
            continue

        residual = navmap_residual_v1(current_payload, candidate_payload)
        if best_residual is None or residual.score > best_residual.score:
            best_index = index
            best_payload = candidate_payload
            best_residual = residual

    if best_residual is None or best_payload is None:
        return NavMapMatchV1(
            current=current_dict,
            candidate={},
            residual=navmap_residual_v1(current_payload, {}),
            candidate_index=None,
            score=0.0,
            matched=False,
            reason="no_candidates",
        )

    matched = bool(best_residual.score >= min_score_f and best_residual.score > 0.0)
    return NavMapMatchV1(
        current=current_dict,
        candidate=best_payload.as_dict(),
        residual=best_residual,
        candidate_index=best_index,
        score=best_residual.score,
        matched=matched,
        reason="matched" if matched else "below_threshold",
    )

def navmap_learning_proposal_from_match_v1(match: NavMapMatchV1) -> NavMapLearningProposalV1:
    """Return a pure keep/update/create proposal from one NavMap match result.

    The proposed payload is still only a hypothesis:

    - exact match: keep the matched candidate as-is
    - partial accepted match: overlay current slots onto candidate slots
    - no accepted match: create a new candidate from the current payload

    Later code can decide whether and where to store the proposed payload.
    """
    if not isinstance(match, NavMapMatchV1):
        empty_current = NavMapPayloadV1(slots={}).as_dict()
        empty_residual = navmap_residual_v1(empty_current, {})
        return NavMapLearningProposalV1(
            action="ignore",
            current=empty_current,
            candidate={},
            proposed_payload={},
            residual=empty_residual,
            candidate_index=None,
            score=0.0,
            accepted_match=False,
            reason="invalid_match",
        )

    current_payload = _payload_from_any_v1(match.current)
    current_slots = navmap_payload_slots_v1(current_payload)
    candidate_payload = _payload_from_any_v1(match.candidate) if match.candidate else None
    residual = match.residual

    if not match.matched or candidate_payload is None:
        proposed_basis = _basis_with_update_note_v1(
            current_payload.basis,
            action="create_candidate",
            match=match,
            residual=residual,
        )
        proposed = make_navmap_payload_v1(
            current_slots,
            map_kind=current_payload.map_kind,
            modality=current_payload.modality,
            confidence=current_payload.confidence,
            source="NavMapCandidate.New",
            basis=proposed_basis,
        ).as_dict()
        return NavMapLearningProposalV1(
            action="create_candidate",
            current=current_payload.as_dict(),
            candidate=dict(match.candidate),
            proposed_payload=proposed,
            residual=residual,
            candidate_index=match.candidate_index,
            score=match.score,
            accepted_match=False,
            reason=match.reason or "no_accepted_match",
        )

    if residual.exact_match:
        return NavMapLearningProposalV1(
            action="keep_candidate",
            current=current_payload.as_dict(),
            candidate=candidate_payload.as_dict(),
            proposed_payload=candidate_payload.as_dict(),
            residual=residual,
            candidate_index=match.candidate_index,
            score=match.score,
            accepted_match=True,
            reason="exact_match",
        )

    proposed_slots = dict(candidate_payload.slots)
    proposed_slots.update(current_slots)
    proposed_basis = _basis_with_update_note_v1(
        candidate_payload.basis,
        action="update_candidate",
        match=match,
        residual=residual,
    )
    proposed = make_navmap_payload_v1(
        proposed_slots,
        map_kind=candidate_payload.map_kind,
        modality=candidate_payload.modality,
        confidence=max(candidate_payload.confidence, current_payload.confidence),
        source="NavMapCandidate.Update",
        basis=proposed_basis,
    ).as_dict()

    return NavMapLearningProposalV1(
        action="update_candidate",
        current=current_payload.as_dict(),
        candidate=candidate_payload.as_dict(),
        proposed_payload=proposed,
        residual=residual,
        candidate_index=match.candidate_index,
        score=match.score,
        accepted_match=True,
        reason="residual_update",
    )


def navmap_apply_learning_proposal_v1(
    candidates: Iterable[NavMapPayloadV1 | Mapping[str, Any]] | Mapping[str, Any],
    proposal: NavMapLearningProposalV1 | Mapping[str, Any],
    *,
    max_candidates: int = 50,
) -> NavMapStoreUpdateV1:
    """Return a new candidate list after applying one pure learning proposal.

    This helper is still not memory integration. It does not mutate the caller's
    candidate list and does not decide what long-term memory should retain. It
    only materializes the proposed keep/update/create action as JSON-safe data.
    """
    before_candidates = _candidate_payload_dicts_v1(candidates)
    before_count = len(before_candidates)

    if not isinstance(proposal, (NavMapLearningProposalV1, Mapping)):
        return NavMapStoreUpdateV1(
            action="ignore",
            candidates=before_candidates,
            before_count=before_count,
            after_count=before_count,
            changed=False,
            candidate_index=None,
            reason="invalid_proposal",
        )

    action = _token_v1(_proposal_field_v1(proposal, "action", "ignore")) or "ignore"
    candidate_index = _candidate_index_int_v1(_proposal_field_v1(proposal, "candidate_index", None))
    proposed_payload = _payload_dict_with_slots_v1(_proposal_field_v1(proposal, "proposed_payload", {}))

    if action == "keep_candidate":
        return NavMapStoreUpdateV1(
            action=action,
            candidates=before_candidates,
            before_count=before_count,
            after_count=before_count,
            changed=False,
            candidate_index=candidate_index,
            reason="kept_existing_candidate",
        )

    if action == "update_candidate":
        if candidate_index is None or candidate_index >= before_count or not proposed_payload:
            return NavMapStoreUpdateV1(
                action="ignore",
                candidates=before_candidates,
                before_count=before_count,
                after_count=before_count,
                changed=False,
                candidate_index=candidate_index,
                reason="invalid_update_candidate",
            )

        after_candidates = list(before_candidates)
        after_candidates[candidate_index] = proposed_payload
        return NavMapStoreUpdateV1(
            action=action,
            candidates=after_candidates,
            before_count=before_count,
            after_count=len(after_candidates),
            changed=True,
            candidate_index=candidate_index,
            reason="updated_candidate",
        )

    if action == "create_candidate":
        if not proposed_payload:
            return NavMapStoreUpdateV1(
                action="ignore",
                candidates=before_candidates,
                before_count=before_count,
                after_count=before_count,
                changed=False,
                candidate_index=None,
                reason="invalid_create_candidate",
            )

        cap = _max_candidates_int_v1(max_candidates)
        after_candidates = list(before_candidates)
        after_candidates.append(proposed_payload)
        reason = "created_candidate"
        if len(after_candidates) > cap:
            after_candidates = after_candidates[-cap:]
            reason = "created_candidate_capped"

        return NavMapStoreUpdateV1(
            action=action,
            candidates=after_candidates,
            before_count=before_count,
            after_count=len(after_candidates),
            changed=True,
            candidate_index=len(after_candidates) - 1,
            reason=reason,
        )

    return NavMapStoreUpdateV1(
        action="ignore",
        candidates=before_candidates,
        before_count=before_count,
        after_count=before_count,
        changed=False,
        candidate_index=candidate_index,
        reason="unsupported_proposal_action",
    )


def navmap_scene_body_cycle_from_env_obs_v1(
    env_obs: Any,
    candidates: Iterable[NavMapPayloadV1 | Mapping[str, Any]] | Mapping[str, Any],
    *,
    min_score: float = 0.01,
    same_modality_only: bool = True,
    confidence: float = 1.0,
    source: str = "EnvObservation.scene_body",
    basis: Optional[Mapping[str, Any]] = None,
) -> NavMapCycleV1:
    """Run one pure scene_body NavMap cycle from an EnvObservation-like object."""
    candidate_items = _candidate_sequence_v1(candidates)
    current_payload = navmap_payload_from_env_obs_v1(
        env_obs,
        confidence=confidence,
        source=source,
        basis=basis,
    )
    match = match_navmap_payloads_v1(
        current_payload,
        candidate_items,
        min_score=min_score,
        same_modality_only=same_modality_only,
    )
    proposal = navmap_learning_proposal_from_match_v1(match)

    return NavMapCycleV1(
        current_payload=current_payload.as_dict(),
        match=match,
        proposal=proposal,
        candidate_count=len(candidate_items),
    )

def make_navmap_transition_v1(
    before_payload: NavMapPayloadV1 | Mapping[str, Any],
    after_payload: NavMapPayloadV1 | Mapping[str, Any],
    *,
    action: str = "",
    reward: float = 0.0,
    drive_delta: Optional[Mapping[str, Any]] = None,
    basis: Optional[Mapping[str, Any]] = None,
) -> NavMapTransitionV1:
    """Create a pure action-conditioned transition between two NavMap payloads.

    The residual is computed as ``after_payload`` compared with ``before_payload``.
    This makes mismatched slot records read as after/current versus before/prior.
    """
    before_map = _payload_from_any_v1(before_payload)
    after_map = _payload_from_any_v1(after_payload)
    residual = navmap_residual_v1(after_map, before_map)

    transition_basis = _json_safe_dict_v1(basis or {})
    transition_basis["transition_source"] = "make_navmap_transition_v1"

    return NavMapTransitionV1(
        before_payload=before_map.as_dict(),
        after_payload=after_map.as_dict(),
        action=action,
        residual=residual,
        reward=_finite_float_v1(reward),
        drive_delta=_drive_delta_map_v1(drive_delta or {}),
        basis=transition_basis,
    )

def navmap_policy_outcome_from_transition_v1(
    transition: NavMapTransitionV1 | Mapping[str, Any],
    *,
    success_threshold: float = 0.0,
    confidence: float = 1.0,
    basis: Optional[Mapping[str, Any]] = None,
) -> NavMapPolicyOutcomeV1:
    """Create a policy-outcome sample from one action-conditioned transition."""
    before_payload = _payload_from_any_v1(_transition_field_v1(transition, "before_payload", {}))
    after_payload = _payload_from_any_v1(_transition_field_v1(transition, "after_payload", {}))
    action = _token_v1(_transition_field_v1(transition, "action", ""))
    reward = _finite_float_v1(_transition_field_v1(transition, "reward", 0.0))
    drive_delta = _drive_delta_map_v1(_transition_field_v1(transition, "drive_delta", {}))
    residual = navmap_residual_v1(after_payload, before_payload)

    outcome_basis = _json_safe_dict_v1(_transition_field_v1(transition, "basis", {}))
    outcome_basis.update(_json_safe_dict_v1(basis or {}))
    outcome_basis["outcome_source"] = "navmap_policy_outcome_from_transition_v1"
    outcome_basis["transition_changed_slots"] = int(residual.residual_count)

    valid_sample = bool(action or before_payload.slots or after_payload.slots)
    threshold = _finite_float_v1(success_threshold)
    return NavMapPolicyOutcomeV1(
        action=action,
        context_slots=before_payload.slots,
        expected_slots=after_payload.slots,
        slot_changes=_slot_changes_from_residual_v1(residual),
        reward=reward,
        drive_delta=drive_delta,
        success=bool(valid_sample and reward > threshold),
        confidence=_score_float_v1(confidence) if valid_sample else 0.0,
        sample_count=1 if valid_sample else 0,
        basis=outcome_basis,
    )

def navmap_observation_update_from_env_obs_v1(
    env_obs: Any,
    candidates: Iterable[NavMapPayloadV1 | Mapping[str, Any]] | Mapping[str, Any],
    *,
    min_score: float = 0.01,
    same_modality_only: bool = True,
    confidence: float = 1.0,
    source: str = "EnvObservation.scene_body",
    basis: Optional[Mapping[str, Any]] = None,
    max_candidates: int = 50,
) -> NavMapObservationUpdateV1:
    """Run one pure observation-to-updated-candidate-store NavMap update."""
    candidate_items = _candidate_sequence_v1(candidates)
    cycle = navmap_scene_body_cycle_from_env_obs_v1(
        env_obs,
        candidate_items,
        min_score=min_score,
        same_modality_only=same_modality_only,
        confidence=confidence,
        source=source,
        basis=basis,
    )
    store_update = navmap_apply_learning_proposal_v1(
        candidate_items,
        cycle.proposal,
        max_candidates=max_candidates,
    )
    return NavMapObservationUpdateV1(
        current_payload=cycle.current_payload,
        cycle=cycle,
        store_update=store_update,
    )
