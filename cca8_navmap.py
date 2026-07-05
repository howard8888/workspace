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

__version__ = "0.3.0"
__all__ = [
    "NAVMAP_PAYLOAD_SCHEMA_V1",
    "NAVMAP_RESIDUAL_SCHEMA_V1",
    "NAVMAP_MATCH_SCHEMA_V1",
    "NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1",
    "NavMapPayloadV1",
    "NavMapResidualV1",
    "NavMapMatchV1",
    "NavMapLearningProposalV1",
    "make_navmap_payload_v1",
    "navmap_payload_slots_v1",
    "navmap_residual_v1",
    "match_navmap_payloads_v1",
    "navmap_learning_proposal_from_match_v1",
    "__version__",
]

NAVMAP_PAYLOAD_SCHEMA_V1 = "navmap_payload_v1"
NAVMAP_RESIDUAL_SCHEMA_V1 = "navmap_residual_v1"
NAVMAP_MATCH_SCHEMA_V1 = "navmap_match_v1"
NAVMAP_LEARNING_PROPOSAL_SCHEMA_V1 = "navmap_learning_proposal_v1"
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
