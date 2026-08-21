# -*- coding: utf-8 -*-
"""Phase 8 long-term NavMap memory, sparse retrieval, and consolidation.

Purpose
-------
Planning v13 requires a long-term map fabric that is richer than the sparse
WorldGraph index but cheaper than decoding every stored payload for every cue.
This module provides the first bounded implementation of that contract:

* immutable :class:`~cca8_navmap_kernel.NavMapV2` revisions are stored directly
  in the existing :class:`~cca8_column.ColumnMemory` payload store;
* lightweight index rows preserve map class, memory form, cue tokens, context,
  task bias, identity handles, transition metadata, support, and exceptions;
* sparse consolidation eligibility is local, transient, and distinct from
  content change, pending storage, and completed consolidation;
* associative activation returns only a bounded set of candidate references
  without loading every Column payload;
* only a few candidate payloads are reinstated and passed through the Phase 1C
  alignment, matching, ranking, and structured-residual operators;
* reliable current evidence can defeat a conflicting memory;
* retrieved maps remain RETRIEVED candidates until a separate ready-set or
  associative-jump authority transaction accepts them; and
* spontaneous cue-driven retrieval and strategic PFC-biased retrieval share
  one inspectable pipeline while preserving explicit UNKNOWN/AMBIGUOUS results.

Representation and authority boundary
-------------------------------------
The Column record is long-term content. The sparse index is addressability and
activation evidence. A candidate reference is not a loaded map. Reinstatement
is not present truth. A clear match is not automatically operative WNM
authority. Ready-set admission is explicitly non-authoritative; an associative
jump requires a separate WNM transaction and cannot proceed when current
reliable evidence conflicts with memory.

The implementation stores no movie of live dynamics and does not replay or
scan the complete library. Primitive, trajectory, and before-action-after maps
are compact map records that preserve task-level structure while detailed
motor trajectories remain below the CCA8/WNM boundary.
"""

from __future__ import annotations

# The module intentionally keeps the first complete Phase 8 vertical slice in
# one place so storage, index, eligibility, retrieval, and authority boundaries
# remain auditable together.
# pylint: disable=duplicate-code
# pylint: disable=too-many-arguments
# pylint: disable=too-many-branches
# pylint: disable=too-many-instance-attributes
# pylint: disable=too-many-lines
# pylint: disable=too-many-locals
# pylint: disable=too-many-return-statements
# pylint: disable=too-many-statements

from dataclasses import dataclass, replace
from enum import Enum
import math
from typing import Any, Iterable, Optional, Sequence, TypeVar

from cca8_column import ColumnMemory
from cca8_env import EnvObservation
from cca8_features import FactMeta
from cca8_navmap_kernel import (
    NavActivationV1,
    NavElementV1,
    NavFrameV1,
    NavGeometryKindV1,
    NavGeometryV1,
    NavMapLinkV1,
    NavMapMatchResultV1,
    NavMapRefV1,
    NavMapV2,
    NavMatchRankStatusV1,
    NavMatchThresholdsV1,
    NavPointV1,
    NavProvenanceV1,
    NavRelationV1,
    NavSourceClassV1,
    NavStructuredResidualV1,
    match_navmaps,
    match_rank,
    structured_residual,
)
from cca8_wnm_runtime import (
    WNMTransitionTypeV1,
    wnm_admit_ready_map_v1,
    wnm_commit_transition_v1,
    wnm_operative_map_v1,
    wnm_ready_maps_v1,
    wnm_summary_v1,
)

__version__ = "0.1.0"

__all__ = [
    "NavMapMemoryKindV1",
    "NavMapMemoryFormV1",
    "NavMapRetrievalModeV1",
    "NavMapRetrievalCommitModeV1",
    "NavMapRetrievalStatusV1",
    "NavMapMemoryIndexEntryV1",
    "NavMapConsolidationEligibilityV1",
    "NavMapConsolidationRecordV1",
    "NavMapCandidateRefV1",
    "NavMapReinstatementV1",
    "NavMapRetrievalRequestV1",
    "NavMapRetrievalTransactionV1",
    "navmap_memory_match_thresholds_v1",
    "navmap_memory_store_map_v1",
    "navmap_memory_request_strategic_retrieval_v1",
    "navmap_memory_retrieve_v1",
    "navmap_memory_observation_step_v1",
    "navmap_memory_replay_eligible_refs_v1",
    "navmap_memory_build_primitive_map_v1",
    "navmap_memory_build_trajectory_map_v1",
    "navmap_memory_build_before_action_after_map_v1",
    "navmap_memory_reset_episode_v1",
    "navmap_memory_summary_v1",
    "render_navmap_memory_lines_v1",
    "__version__",
]

_DEFAULT_CANDIDATE_REF_LIMIT = 8
_DEFAULT_REINSTATEMENT_LIMIT = 3
_DEFAULT_HISTORY_LIMIT = 25
_DEFAULT_ELIGIBILITY_LIMIT = 16
_DEFAULT_PENDING_MAP_LIMIT = 16
_DEFAULT_ELIGIBILITY_TTL = 8
_DEFAULT_ELIGIBILITY_DECAY = 0.10
_DEFAULT_CONSOLIDATION_THRESHOLD = 0.50
_DEFAULT_CONSOLIDATION_BUDGET = 2
_DEFAULT_MINIMUM_ACTIVATION_SCORE = 0.12
_DEFAULT_READY_ADMISSION_SCORE = 0.55
_DEFAULT_READY_ADMISSION_COVERAGE = 0.20
_DEFAULT_RELIABLE_EVIDENCE_QUALITY = 0.80
_MEMORY_INDEX_SCHEMA = "navmap_memory_index_entry_v1"
_MEMORY_FACT_PREFIX = "navmap_memory"

_EnumT = TypeVar("_EnumT", bound=Enum)


class NavMapMemoryKindV1(str, Enum):
    """Domain-level kinds supported by the first long-term NavMap fabric."""

    LOCAL = "local"
    MULTISENSORY = "multisensory"
    OBJECT = "object"
    TERRAIN = "terrain"
    BODY = "body"
    MATERNAL = "maternal"
    PRIMITIVE = "primitive"
    TRAJECTORY = "trajectory"
    BEFORE_ACTION_AFTER = "before_action_after"


class NavMapMemoryFormV1(str, Enum):
    """Distinct long-term memory forms carried by one indexed map record."""

    EPISODIC = "episodic"
    PROTOTYPE = "prototype"
    IDENTITY = "identity"
    TRANSITION = "transition"


class NavMapRetrievalModeV1(str, Enum):
    """How one bounded retrieval request was recruited."""

    SPONTANEOUS = "spontaneous"
    STRATEGIC = "strategic"


class NavMapRetrievalCommitModeV1(str, Enum):
    """Optional authority action after a clear evidence-compatible match."""

    NONE = "none"
    READY = "ready"
    ASSOCIATIVE_JUMP = "associative_jump"


class NavMapRetrievalStatusV1(str, Enum):
    """Open-world result of one complete sparse retrieval transaction."""

    NO_CANDIDATES = "no_candidates"
    CANDIDATE_REFS_ONLY = "candidate_refs_only"
    REINSTATEMENT_FAILED = "reinstatement_failed"
    UNKNOWN = "unknown"
    AMBIGUOUS = "ambiguous"
    CLEAR_WINNER = "clear_winner"
    EVIDENCE_DEFEATS_MEMORY = "evidence_defeats_memory"
    READY_ADMITTED = "ready_admitted"
    ASSOCIATIVE_JUMP_COMMITTED = "associative_jump_committed"
    AUTHORITY_REJECTED = "authority_rejected"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty text value."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _finite_float(value: Any, *, field_name: str) -> float:
    """Return one finite float without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not math.isfinite(number):
        raise ValueError(f"{field_name} must be finite")
    return number


def _unit_interval(value: Any, *, field_name: str) -> float:
    """Return one finite number in the inclusive unit interval."""
    number = _finite_float(value, field_name=field_name)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _optional_ref_dict(ref: Optional[NavMapRefV1]) -> Optional[dict[str, Any]]:
    """Return one optional JSON-safe map reference."""
    return ref.as_dict() if ref is not None else None


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the exact immutable reference of one map revision."""
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    return NavMapRefV1(navmap.map_id, navmap.revision)


def _ref_key(ref: NavMapRefV1) -> str:
    """Return one deterministic dictionary key for a map revision."""
    return f"{ref.map_id}@r{ref.revision}"


def _normalize_token(value: Any) -> Optional[str]:
    """Return one normalized sparse-index token or ``None``."""
    if not isinstance(value, str):
        return None
    text = value.strip().lower()
    if not text:
        return None
    return "_".join(text.split())


def _normalized_tokens(values: Iterable[Any]) -> tuple[str, ...]:
    """Return sorted unique non-empty sparse-index tokens."""
    tokens = {_normalize_token(value) for value in values}
    return tuple(sorted(token for token in tokens if token is not None))


def _identifier_fragment(value: str) -> str:
    """Return one conservative identifier fragment for generated map records."""
    text = _normalize_token(value) or "unknown"
    chars = [char if char.isalnum() else "_" for char in text]
    normalized = "".join(chars).strip("_") or "unknown"
    while "__" in normalized:
        normalized = normalized.replace("__", "_")
    return normalized[:80]


def _enum_tuple(
    values: Iterable[Any],
    enum_type: type[_EnumT],
    *,
    field_name: str,
) -> tuple[_EnumT, ...]:
    """Return sorted unique members of one string Enum class."""
    members: list[_EnumT] = []
    for value in values:
        if isinstance(value, enum_type):
            member = value
        else:
            try:
                member = enum_type(str(value))
            except ValueError as exc:
                raise ValueError(f"invalid {field_name}: {value!r}") from exc
        if member not in members:
            members.append(member)
    if not members:
        raise ValueError(f"{field_name} must contain at least one value")
    return tuple(sorted(members, key=lambda item: str(item.value)))


@dataclass(frozen=True, slots=True)
class NavMapMemoryIndexEntryV1:
    """One lightweight long-term index row addressing a Column NavMap payload.

    The row deliberately contains no full map payload. It is sufficient for
    cheap associative activation and selective payload reinstatement by exact
    ``engram_id``. Support and exception evidence remain separate counters.
    """

    engram_id: str
    column_name: str
    map_ref: NavMapRefV1
    map_role: str
    frame_id: str
    content_signature: str
    record_signature: str
    memory_kinds: tuple[NavMapMemoryKindV1, ...]
    memory_forms: tuple[NavMapMemoryFormV1, ...]
    cue_tokens: tuple[str, ...]
    context_tokens: tuple[str, ...]
    task_tokens: tuple[str, ...]
    structure_tokens: tuple[str, ...]
    identity_handles: tuple[str, ...]
    source_classes: tuple[str, ...]
    transition_from_ref: Optional[NavMapRefV1]
    transition_action: Optional[str]
    transition_to_ref: Optional[NavMapRefV1]
    support_count: int
    exception_count: int
    stored_observation_no: int
    last_supported_observation_no: int
    stored_controller_step: int
    retrieval_count: int = 0
    last_retrieved_query_no: Optional[int] = None

    def __post_init__(self) -> None:
        for field_name in (
            "engram_id",
            "column_name",
            "map_role",
            "frame_id",
            "content_signature",
            "record_signature",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if not isinstance(self.map_ref, NavMapRefV1):
            raise TypeError("map_ref must be NavMapRefV1")
        kinds = _enum_tuple(self.memory_kinds, NavMapMemoryKindV1, field_name="memory_kinds")
        forms = _enum_tuple(self.memory_forms, NavMapMemoryFormV1, field_name="memory_forms")
        object.__setattr__(self, "memory_kinds", kinds)
        object.__setattr__(self, "memory_forms", forms)
        for field_name in (
            "cue_tokens",
            "context_tokens",
            "task_tokens",
            "structure_tokens",
            "identity_handles",
            "source_classes",
        ):
            object.__setattr__(self, field_name, _normalized_tokens(getattr(self, field_name)))
        if self.transition_from_ref is not None and not isinstance(self.transition_from_ref, NavMapRefV1):
            raise TypeError("transition_from_ref must be NavMapRefV1 or None")
        if self.transition_to_ref is not None and not isinstance(self.transition_to_ref, NavMapRefV1):
            raise TypeError("transition_to_ref must be NavMapRefV1 or None")
        if self.transition_action is not None:
            _require_nonempty_text(self.transition_action, field_name="transition_action")
        _require_non_negative_int(self.support_count, field_name="support_count")
        _require_non_negative_int(self.exception_count, field_name="exception_count")
        _require_positive_int(self.stored_observation_no, field_name="stored_observation_no")
        _require_positive_int(self.last_supported_observation_no, field_name="last_supported_observation_no")
        if self.last_supported_observation_no < self.stored_observation_no:
            raise ValueError("last_supported_observation_no cannot precede storage")
        _require_non_negative_int(self.stored_controller_step, field_name="stored_controller_step")
        _require_non_negative_int(self.retrieval_count, field_name="retrieval_count")
        if self.last_retrieved_query_no is not None:
            _require_positive_int(self.last_retrieved_query_no, field_name="last_retrieved_query_no")

    @property
    def all_index_tokens(self) -> tuple[str, ...]:
        """Return every lightweight token used by the inverted sparse index."""
        tokens: list[str] = [
            f"map:{self.map_ref.map_id}",
            f"role:{self.map_role}",
            f"frame:{self.frame_id}",
        ]
        tokens.extend(f"kind:{item.value}" for item in self.memory_kinds)
        tokens.extend(f"form:{item.value}" for item in self.memory_forms)
        tokens.extend(self.cue_tokens)
        tokens.extend(self.context_tokens)
        tokens.extend(self.task_tokens)
        tokens.extend(self.structure_tokens)
        tokens.extend(f"identity:{item}" for item in self.identity_handles)
        tokens.extend(f"source:{item}" for item in self.source_classes)
        if self.transition_action is not None:
            tokens.append(f"action:{self.transition_action}")
        return _normalized_tokens(tokens)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe sparse index row without the Column payload."""
        return {
            "schema": _MEMORY_INDEX_SCHEMA,
            "phase": "8",
            "engram_id": self.engram_id,
            "column_name": self.column_name,
            "map_ref": self.map_ref.as_dict(),
            "map_role": self.map_role,
            "frame_id": self.frame_id,
            "content_signature": self.content_signature,
            "record_signature": self.record_signature,
            "memory_kinds": [item.value for item in self.memory_kinds],
            "memory_forms": [item.value for item in self.memory_forms],
            "cue_tokens": list(self.cue_tokens),
            "context_tokens": list(self.context_tokens),
            "task_tokens": list(self.task_tokens),
            "structure_tokens": list(self.structure_tokens),
            "identity_handles": list(self.identity_handles),
            "source_classes": list(self.source_classes),
            "transition_from_ref": _optional_ref_dict(self.transition_from_ref),
            "transition_action": self.transition_action,
            "transition_to_ref": _optional_ref_dict(self.transition_to_ref),
            "support_count": self.support_count,
            "exception_count": self.exception_count,
            "stored_observation_no": self.stored_observation_no,
            "last_supported_observation_no": self.last_supported_observation_no,
            "stored_controller_step": self.stored_controller_step,
            "retrieval_count": self.retrieval_count,
            "last_retrieved_query_no": self.last_retrieved_query_no,
            "index_tokens": list(self.all_index_tokens),
            "contains_payload": False,
            "operative_authority": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapConsolidationEligibilityV1:
    """One transient local eligibility signal for sparse consolidation."""

    eligibility_key: str
    map_ref: NavMapRefV1
    source_role: str
    memory_kinds: tuple[NavMapMemoryKindV1, ...]
    memory_forms: tuple[NavMapMemoryFormV1, ...]
    created_observation_no: int
    last_signal_observation_no: int
    expires_after_observation_no: int
    strength: float
    reasons: tuple[str, ...]
    content_changed: bool
    plasticity_eligible: bool
    consolidation_pending: bool
    consolidated: bool
    unresolved_mismatch: bool

    def __post_init__(self) -> None:
        _require_nonempty_text(self.eligibility_key, field_name="eligibility_key")
        if not isinstance(self.map_ref, NavMapRefV1):
            raise TypeError("map_ref must be NavMapRefV1")
        _require_nonempty_text(self.source_role, field_name="source_role")
        object.__setattr__(
            self,
            "memory_kinds",
            _enum_tuple(self.memory_kinds, NavMapMemoryKindV1, field_name="memory_kinds"),
        )
        object.__setattr__(
            self,
            "memory_forms",
            _enum_tuple(self.memory_forms, NavMapMemoryFormV1, field_name="memory_forms"),
        )
        _require_positive_int(self.created_observation_no, field_name="created_observation_no")
        _require_positive_int(self.last_signal_observation_no, field_name="last_signal_observation_no")
        _require_positive_int(self.expires_after_observation_no, field_name="expires_after_observation_no")
        if self.last_signal_observation_no < self.created_observation_no:
            raise ValueError("last_signal_observation_no cannot precede creation")
        if self.expires_after_observation_no < self.last_signal_observation_no:
            raise ValueError("expires_after_observation_no cannot precede the last signal")
        object.__setattr__(self, "strength", _unit_interval(self.strength, field_name="strength"))
        object.__setattr__(self, "reasons", _normalized_tokens(self.reasons))
        if not self.reasons:
            raise ValueError("reasons must contain at least one signal")
        for field_name in (
            "content_changed",
            "plasticity_eligible",
            "consolidation_pending",
            "consolidated",
            "unresolved_mismatch",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        if self.consolidated and self.consolidation_pending:
            raise ValueError("consolidated and consolidation_pending cannot both be true")

    def as_dict(self) -> dict[str, Any]:
        """Return the four distinct learning/consolidation states explicitly."""
        return {
            "schema": "navmap_consolidation_eligibility_v1",
            "phase": "8",
            "eligibility_key": self.eligibility_key,
            "map_ref": self.map_ref.as_dict(),
            "source_role": self.source_role,
            "memory_kinds": [item.value for item in self.memory_kinds],
            "memory_forms": [item.value for item in self.memory_forms],
            "created_observation_no": self.created_observation_no,
            "last_signal_observation_no": self.last_signal_observation_no,
            "expires_after_observation_no": self.expires_after_observation_no,
            "strength": self.strength,
            "reasons": list(self.reasons),
            "content_changed": self.content_changed,
            "plasticity_eligible": self.plasticity_eligible,
            "consolidation_pending": self.consolidation_pending,
            "consolidated": self.consolidated,
            "unresolved_mismatch": self.unresolved_mismatch,
            "local_transient_signal": True,
            "permanent_activation_history": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapConsolidationRecordV1:
    """One completed or deduplicated Column consolidation transaction."""

    transaction_no: int
    observation_no: int
    controller_step: int
    map_ref: NavMapRefV1
    eligibility_key: Optional[str]
    status: str
    reason: str
    engram_id: Optional[str]
    column_name: str
    content_changed: bool
    plasticity_eligible: bool
    consolidation_pending: bool
    consolidated: bool
    payload_stored: bool
    duplicate_payload_avoided: bool
    support_recorded: bool
    exception_recorded: bool
    eligibility_strength: float

    def __post_init__(self) -> None:
        _require_positive_int(self.transaction_no, field_name="transaction_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        _require_non_negative_int(self.controller_step, field_name="controller_step")
        if not isinstance(self.map_ref, NavMapRefV1):
            raise TypeError("map_ref must be NavMapRefV1")
        if self.eligibility_key is not None:
            _require_nonempty_text(self.eligibility_key, field_name="eligibility_key")
        for field_name in ("status", "reason", "column_name"):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        if self.engram_id is not None:
            _require_nonempty_text(self.engram_id, field_name="engram_id")
        for field_name in (
            "content_changed",
            "plasticity_eligible",
            "consolidation_pending",
            "consolidated",
            "payload_stored",
            "duplicate_payload_avoided",
            "support_recorded",
            "exception_recorded",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        object.__setattr__(
            self,
            "eligibility_strength",
            _unit_interval(self.eligibility_strength, field_name="eligibility_strength"),
        )

    def as_dict(self) -> dict[str, Any]:
        """Return one JSON-safe sparse-consolidation audit record."""
        return {
            "schema": "navmap_consolidation_record_v1",
            "phase": "8",
            "transaction_no": self.transaction_no,
            "observation_no": self.observation_no,
            "controller_step": self.controller_step,
            "map_ref": self.map_ref.as_dict(),
            "eligibility_key": self.eligibility_key,
            "status": self.status,
            "reason": self.reason,
            "engram_id": self.engram_id,
            "column_name": self.column_name,
            "content_changed": self.content_changed,
            "plasticity_eligible": self.plasticity_eligible,
            "consolidation_pending": self.consolidation_pending,
            "consolidated": self.consolidated,
            "payload_stored": self.payload_stored,
            "duplicate_payload_avoided": self.duplicate_payload_avoided,
            "support_recorded": self.support_recorded,
            "exception_recorded": self.exception_recorded,
            "eligibility_strength": self.eligibility_strength,
            "automatic_storage_of_every_activation": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapCandidateRefV1:
    """One cheap candidate reference produced without loading its payload."""

    query_no: int
    engram_id: str
    map_ref: NavMapRefV1
    map_role: str
    memory_kinds: tuple[NavMapMemoryKindV1, ...]
    memory_forms: tuple[NavMapMemoryFormV1, ...]
    activation_score: float
    cue_score: float
    context_score: float
    task_score: float
    structure_score: float
    support_score: float
    exception_penalty: float
    matched_tokens: tuple[str, ...]
    activation_reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        _require_positive_int(self.query_no, field_name="query_no")
        _require_nonempty_text(self.engram_id, field_name="engram_id")
        if not isinstance(self.map_ref, NavMapRefV1):
            raise TypeError("map_ref must be NavMapRefV1")
        _require_nonempty_text(self.map_role, field_name="map_role")
        object.__setattr__(
            self,
            "memory_kinds",
            _enum_tuple(self.memory_kinds, NavMapMemoryKindV1, field_name="memory_kinds"),
        )
        object.__setattr__(
            self,
            "memory_forms",
            _enum_tuple(self.memory_forms, NavMapMemoryFormV1, field_name="memory_forms"),
        )
        for field_name in (
            "activation_score",
            "cue_score",
            "context_score",
            "task_score",
            "structure_score",
            "support_score",
            "exception_penalty",
        ):
            object.__setattr__(self, field_name, _unit_interval(getattr(self, field_name), field_name=field_name))
        object.__setattr__(self, "matched_tokens", _normalized_tokens(self.matched_tokens))
        object.__setattr__(self, "activation_reasons", _normalized_tokens(self.activation_reasons))

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe reference-only activation result."""
        return {
            "schema": "navmap_candidate_ref_v1",
            "phase": "8",
            "query_no": self.query_no,
            "engram_id": self.engram_id,
            "map_ref": self.map_ref.as_dict(),
            "map_role": self.map_role,
            "memory_kinds": [item.value for item in self.memory_kinds],
            "memory_forms": [item.value for item in self.memory_forms],
            "activation_score": self.activation_score,
            "cue_score": self.cue_score,
            "context_score": self.context_score,
            "task_score": self.task_score,
            "structure_score": self.structure_score,
            "support_score": self.support_score,
            "exception_penalty": self.exception_penalty,
            "matched_tokens": list(self.matched_tokens),
            "activation_reasons": list(self.activation_reasons),
            "payload_reinstated": False,
            "current_truth": False,
            "operative_authority": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapReinstatementV1:
    """One selectively loaded RETRIEVED map and detailed comparison result."""

    candidate_ref: NavMapCandidateRefV1
    navmap: NavMapV2
    match_result: Optional[NavMapMatchResultV1]
    structured_residual: Optional[NavStructuredResidualV1]
    evidence_conflict: bool
    status: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.candidate_ref, NavMapCandidateRefV1):
            raise TypeError("candidate_ref must be NavMapCandidateRefV1")
        if not isinstance(self.navmap, NavMapV2):
            raise TypeError("navmap must be NavMapV2")
        if _map_ref(self.navmap) != self.candidate_ref.map_ref:
            raise ValueError("reinstated map must match candidate_ref")
        if self.match_result is not None and not isinstance(self.match_result, NavMapMatchResultV1):
            raise TypeError("match_result must be NavMapMatchResultV1 or None")
        if self.structured_residual is not None and not isinstance(
            self.structured_residual,
            NavStructuredResidualV1,
        ):
            raise TypeError("structured_residual must be NavStructuredResidualV1 or None")
        if not isinstance(self.evidence_conflict, bool):
            raise TypeError("evidence_conflict must be bool")
        _require_nonempty_text(self.status, field_name="status")
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return reinstatement telemetry without serializing the full map again."""
        return {
            "schema": "navmap_reinstatement_v1",
            "phase": "8",
            "candidate_ref": self.candidate_ref.as_dict(),
            "map_ref": _map_ref(self.navmap).as_dict(),
            "map_role": self.navmap.role,
            "payload_reinstated": True,
            "payload_bytes_loaded": len(self.navmap.to_bytes()),
            "source_class": "retrieved",
            "payload_provenance_preserved": True,
            "current_truth": False,
            "operative_authority": False,
            "match_result": self.match_result.as_dict() if self.match_result is not None else None,
            "structured_residual": (
                self.structured_residual.as_dict() if self.structured_residual is not None else None
            ),
            "evidence_conflict": self.evidence_conflict,
            "status": self.status,
            "reason": self.reason,
        }


@dataclass(frozen=True, slots=True)
class NavMapRetrievalRequestV1:
    """One bounded spontaneous or strategic sparse-retrieval request."""

    query_no: int
    mode: NavMapRetrievalModeV1
    query_map_ref: Optional[NavMapRefV1]
    source_evidence_ref: Optional[NavMapRefV1]
    cue_tokens: tuple[str, ...]
    context_tokens: tuple[str, ...]
    task_bias_tokens: tuple[str, ...]
    requested_memory_kinds: tuple[NavMapMemoryKindV1, ...]
    requested_memory_forms: tuple[NavMapMemoryFormV1, ...]
    candidate_ref_limit: int
    reinstatement_limit: int
    commit_mode: NavMapRetrievalCommitModeV1
    reason: str

    def __post_init__(self) -> None:
        _require_positive_int(self.query_no, field_name="query_no")
        if not isinstance(self.mode, NavMapRetrievalModeV1):
            raise TypeError("mode must be NavMapRetrievalModeV1")
        if self.query_map_ref is not None and not isinstance(self.query_map_ref, NavMapRefV1):
            raise TypeError("query_map_ref must be NavMapRefV1 or None")
        if self.source_evidence_ref is not None and not isinstance(self.source_evidence_ref, NavMapRefV1):
            raise TypeError("source_evidence_ref must be NavMapRefV1 or None")
        for field_name in ("cue_tokens", "context_tokens", "task_bias_tokens"):
            object.__setattr__(self, field_name, _normalized_tokens(getattr(self, field_name)))
        kinds = tuple(self.requested_memory_kinds)
        forms = tuple(self.requested_memory_forms)
        for kind_item in kinds:
            if not isinstance(kind_item, NavMapMemoryKindV1):
                raise TypeError("requested_memory_kinds must contain NavMapMemoryKindV1")
        for form_item in forms:
            if not isinstance(form_item, NavMapMemoryFormV1):
                raise TypeError("requested_memory_forms must contain NavMapMemoryFormV1")
        object.__setattr__(self, "requested_memory_kinds", tuple(sorted(set(kinds), key=lambda item: item.value)))
        object.__setattr__(self, "requested_memory_forms", tuple(sorted(set(forms), key=lambda item: item.value)))
        _require_positive_int(self.candidate_ref_limit, field_name="candidate_ref_limit")
        _require_positive_int(self.reinstatement_limit, field_name="reinstatement_limit")
        if self.reinstatement_limit > self.candidate_ref_limit:
            raise ValueError("reinstatement_limit cannot exceed candidate_ref_limit")
        if not isinstance(self.commit_mode, NavMapRetrievalCommitModeV1):
            raise TypeError("commit_mode must be NavMapRetrievalCommitModeV1")
        _require_nonempty_text(self.reason, field_name="reason")

    def as_dict(self) -> dict[str, Any]:
        """Return one JSON-safe retrieval request contract."""
        return {
            "schema": "navmap_retrieval_request_v1",
            "phase": "8",
            "query_no": self.query_no,
            "mode": self.mode.value,
            "query_map_ref": _optional_ref_dict(self.query_map_ref),
            "source_evidence_ref": _optional_ref_dict(self.source_evidence_ref),
            "cue_tokens": list(self.cue_tokens),
            "context_tokens": list(self.context_tokens),
            "task_bias_tokens": list(self.task_bias_tokens),
            "requested_memory_kinds": [item.value for item in self.requested_memory_kinds],
            "requested_memory_forms": [item.value for item in self.requested_memory_forms],
            "candidate_ref_limit": self.candidate_ref_limit,
            "reinstatement_limit": self.reinstatement_limit,
            "commit_mode": self.commit_mode.value,
            "reason": self.reason,
            "full_payload_scan_allowed": False,
        }


@dataclass(frozen=True, slots=True)
class NavMapRetrievalTransactionV1:
    """One complete sparse activation, reinstatement, comparison, and authority result."""

    request: NavMapRetrievalRequestV1
    candidate_refs: tuple[NavMapCandidateRefV1, ...]
    reinstatements: tuple[NavMapReinstatementV1, ...]
    rank_status: Optional[str]
    winner_ref: Optional[NavMapRefV1]
    winner_engram_id: Optional[str]
    status: NavMapRetrievalStatusV1
    evidence_defeats_memory: bool
    ready_admitted: bool
    associative_jump_committed: bool
    authority_result: str
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.request, NavMapRetrievalRequestV1):
            raise TypeError("request must be NavMapRetrievalRequestV1")
        for candidate_ref in self.candidate_refs:
            if not isinstance(candidate_ref, NavMapCandidateRefV1):
                raise TypeError("candidate_refs must contain NavMapCandidateRefV1")
        for reinstatement in self.reinstatements:
            if not isinstance(reinstatement, NavMapReinstatementV1):
                raise TypeError("reinstatements must contain NavMapReinstatementV1")
        if len(self.candidate_refs) > self.request.candidate_ref_limit:
            raise ValueError("candidate_refs exceeds request bound")
        if len(self.reinstatements) > self.request.reinstatement_limit:
            raise ValueError("reinstatements exceeds request bound")
        if self.rank_status is not None:
            _require_nonempty_text(self.rank_status, field_name="rank_status")
        if self.winner_ref is not None and not isinstance(self.winner_ref, NavMapRefV1):
            raise TypeError("winner_ref must be NavMapRefV1 or None")
        if self.winner_engram_id is not None:
            _require_nonempty_text(self.winner_engram_id, field_name="winner_engram_id")
        if not isinstance(self.status, NavMapRetrievalStatusV1):
            raise TypeError("status must be NavMapRetrievalStatusV1")
        for field_name in (
            "evidence_defeats_memory",
            "ready_admitted",
            "associative_jump_committed",
        ):
            if not isinstance(getattr(self, field_name), bool):
                raise TypeError(f"{field_name} must be bool")
        _require_nonempty_text(self.authority_result, field_name="authority_result")
        _require_nonempty_text(self.reason, field_name="reason")
        if self.evidence_defeats_memory and (self.ready_admitted or self.associative_jump_committed):
            raise ValueError("conflicting memory cannot be admitted or committed")
        if self.associative_jump_committed and not self.ready_admitted:
            # The jump itself moves the prior operative map into ready status; the
            # retrieved destination need not remain ready, but it passed the same
            # authority guard. ``ready_admitted`` therefore means the guard/admit
            # stage succeeded, not that the winner remains in the ready set.
            raise ValueError("associative jump requires an accepted admission guard")

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe retrieval transaction without duplicated payloads."""
        return {
            "schema": "navmap_retrieval_transaction_v1",
            "phase": "8",
            "authority": "retrieval_candidate_layer",
            "request": self.request.as_dict(),
            "candidate_refs": [item.as_dict() for item in self.candidate_refs],
            "reinstatements": [item.as_dict() for item in self.reinstatements],
            "rank_status": self.rank_status,
            "winner_ref": _optional_ref_dict(self.winner_ref),
            "winner_engram_id": self.winner_engram_id,
            "status": self.status.value,
            "evidence_defeats_memory": self.evidence_defeats_memory,
            "ready_admitted": self.ready_admitted,
            "associative_jump_committed": self.associative_jump_committed,
            "authority_result": self.authority_result,
            "reason": self.reason,
            "candidate_refs_generated_without_payload_scan": True,
            "only_bounded_candidates_reinstated": True,
            "retrieved_content_is_observed": False,
            "candidate_or_retrieval_grants_truth": False,
            "protected_safety_can_be_overridden": False,
        }


@dataclass(frozen=True, slots=True)
class _RuntimeMapDescriptorV1:
    """Internal current-map descriptor used by sparse eligibility generation."""

    navmap: NavMapV2
    memory_kinds: tuple[NavMapMemoryKindV1, ...]
    memory_forms: tuple[NavMapMemoryFormV1, ...]
    cue_tokens: tuple[str, ...]
    context_tokens: tuple[str, ...]
    task_tokens: tuple[str, ...]
    identity_handles: tuple[str, ...]
    transition_from_ref: Optional[NavMapRefV1]
    transition_action: Optional[str]
    transition_to_ref: Optional[NavMapRefV1]
    support: bool
    exception: bool
    reason: str


def _ctx_int(ctx: Any, name: str, default: int) -> int:
    """Return one context integer or deterministic default."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def _ctx_float(ctx: Any, name: str, default: float) -> float:
    """Return one finite context float or deterministic default."""
    value = getattr(ctx, name, default)
    if isinstance(value, bool):
        return default
    try:
        number = float(value)
    except (TypeError, ValueError):
        return default
    return number if math.isfinite(number) else default


def _controller_step(ctx: Any) -> int:
    """Return one defensive non-negative controller-step value."""
    return max(0, _ctx_int(ctx, "controller_steps", 0))


def _next_observation_no(ctx: Any) -> int:
    """Advance and return the Phase 8 observation counter."""
    current = max(0, _ctx_int(ctx, "navmap_memory_observation_no_v1", 0))
    value = current + 1
    ctx.navmap_memory_observation_no_v1 = value
    return value


def _next_store_transaction_no(ctx: Any) -> int:
    """Advance and return the sparse-consolidation transaction counter."""
    current = max(0, _ctx_int(ctx, "navmap_memory_consolidation_transaction_no_v1", 0))
    value = current + 1
    ctx.navmap_memory_consolidation_transaction_no_v1 = value
    return value


def _next_query_no(ctx: Any) -> int:
    """Advance and return the retrieval-query counter."""
    current = max(0, _ctx_int(ctx, "navmap_memory_query_no_v1", 0))
    value = current + 1
    ctx.navmap_memory_query_no_v1 = value
    return value


def _history_limit(ctx: Any, field_name: str, default: int = _DEFAULT_HISTORY_LIMIT) -> int:
    """Return one positive bounded history limit."""
    value = _ctx_int(ctx, field_name, default)
    return value if value > 0 else default


def _column_memory(column_memory: Optional[ColumnMemory]) -> ColumnMemory:
    """Return the supplied Column or the normal module-level CCA8 Column."""
    if column_memory is not None:
        if not isinstance(column_memory, ColumnMemory):
            raise TypeError("column_memory must be ColumnMemory or None")
        return column_memory
    # Delayed import keeps tests free to supply isolated stores and avoids a
    # module-import dependency on the runner.
    from cca8_column import mem  # pylint: disable=import-outside-toplevel

    return mem


def _memory_index(ctx: Any) -> dict[str, NavMapMemoryIndexEntryV1]:
    """Return only valid typed memory-index entries keyed by engram id."""
    raw = getattr(ctx, "navmap_memory_index_v1", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, NavMapMemoryIndexEntryV1)
    }


def _ref_index(ctx: Any) -> dict[str, str]:
    """Return the lightweight map-ref-to-engram index."""
    raw = getattr(ctx, "navmap_memory_ref_index_v1", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): str(value)
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, str) and value
    }


def _structure_tokens(navmap: NavMapV2) -> tuple[str, ...]:
    """Return cheap decoded structure tokens stored beside, not inside, payload scans."""
    values: list[str] = [
        f"role:{navmap.role}",
        f"frame:{navmap.frame.frame_id}",
        f"source:{navmap.provenance.source_class.value}",
    ]
    values.extend(f"element_role:{element.role}" for element in navmap.elements)
    for element in navmap.elements:
        values.extend(f"activation:{activation.name}" for activation in element.activations)
    values.extend(f"relation:{relation.relation_type}" for relation in navmap.relations)
    values.extend(f"link:{link.link_type}" for link in navmap.links)
    return _normalized_tokens(values)


def _source_classes(navmap: NavMapV2) -> tuple[str, ...]:
    """Return all source classes represented in one map revision."""
    values: list[str] = [navmap.provenance.source_class.value]
    values.extend(element.provenance.source_class.value for element in navmap.elements)
    for element in navmap.elements:
        values.extend(activation.provenance.source_class.value for activation in element.activations)
    values.extend(relation.provenance.source_class.value for relation in navmap.relations)
    values.extend(link.provenance.source_class.value for link in navmap.links)
    return _normalized_tokens(values)


def _rebuild_sparse_indexes(ctx: Any, entries: dict[str, NavMapMemoryIndexEntryV1]) -> None:
    """Rebuild lightweight inverted/ref indexes without touching Column payloads."""
    token_index: dict[str, list[str]] = {}
    ref_index: dict[str, str] = {}
    for engram_id, entry in sorted(entries.items()):
        ref_index[_ref_key(entry.map_ref)] = engram_id
        for token in entry.all_index_tokens:
            token_index.setdefault(token, []).append(engram_id)
    ctx.navmap_memory_index_v1 = dict(entries)
    ctx.navmap_memory_ref_index_v1 = ref_index
    ctx.navmap_memory_token_index_v1 = {
        token: sorted(set(ids))
        for token, ids in token_index.items()
    }


def _append_history(ctx: Any, field_name: str, limit_field_name: str, row: dict[str, Any]) -> None:
    """Append one defensive row to a bounded JSON-safe history."""
    raw = getattr(ctx, field_name, None)
    history = [dict(item) for item in raw if isinstance(item, dict)] if isinstance(raw, list) else []
    history.append(dict(row))
    setattr(ctx, field_name, history[-_history_limit(ctx, limit_field_name):])


def navmap_memory_match_thresholds_v1(ctx: Any = None, *, maximum_candidates: Optional[int] = None) -> NavMatchThresholdsV1:
    """Return explicit Phase 8 detailed-match thresholds.

    These thresholds are engineering parameters for a bounded first experiment,
    not claims about biological recognition constants. Candidate-reference
    activation remains separate and cheaper than this detailed map comparison.
    """
    max_count = maximum_candidates if isinstance(maximum_candidates, int) and maximum_candidates > 0 else _DEFAULT_REINSTATEMENT_LIMIT
    if ctx is not None:
        max_count = max(1, _ctx_int(ctx, "navmap_memory_reinstatement_limit_v1", max_count))
    return NavMatchThresholdsV1(
        maximum_alignment_rms_error=max(0.0, _ctx_float(ctx, "navmap_memory_alignment_rms_v1", 2.0)) if ctx is not None else 2.0,
        maximum_geometry_rms_error=max(0.0, _ctx_float(ctx, "navmap_memory_geometry_rms_v1", 0.50)) if ctx is not None else 0.50,
        maximum_geometry_point_error=max(0.0, _ctx_float(ctx, "navmap_memory_geometry_point_v1", 1.00)) if ctx is not None else 1.00,
        maximum_activation_strength_delta=min(
            1.0,
            max(0.0, _ctx_float(ctx, "navmap_memory_activation_delta_v1", 0.50)) if ctx is not None else 0.50,
        ),
        minimum_correspondence_coverage=min(
            1.0,
            max(0.0, _ctx_float(ctx, "navmap_memory_minimum_coverage_v1", 0.20)) if ctx is not None else 0.20,
        ),
        minimum_rank_score=min(
            1.0,
            max(0.0, _ctx_float(ctx, "navmap_memory_minimum_rank_score_v1", 0.35)) if ctx is not None else 0.35,
        ),
        ambiguity_margin=min(
            1.0,
            max(0.0, _ctx_float(ctx, "navmap_memory_ambiguity_margin_v1", 0.05)) if ctx is not None else 0.05,
        ),
        maximum_candidate_count=max_count,
    )


def _merge_index_entry(
    entry: NavMapMemoryIndexEntryV1,
    *,
    memory_kinds: tuple[NavMapMemoryKindV1, ...],
    memory_forms: tuple[NavMapMemoryFormV1, ...],
    cue_tokens: tuple[str, ...],
    context_tokens: tuple[str, ...],
    task_tokens: tuple[str, ...],
    structure_tokens: tuple[str, ...],
    identity_handles: tuple[str, ...],
    source_classes: tuple[str, ...],
    observation_no: int,
    support: bool,
    exception: bool,
    transition_from_ref: Optional[NavMapRefV1],
    transition_action: Optional[str],
    transition_to_ref: Optional[NavMapRefV1],
) -> NavMapMemoryIndexEntryV1:
    """Return one updated support/exception/index classification row."""
    return replace(
        entry,
        memory_kinds=tuple(sorted(set(entry.memory_kinds + memory_kinds), key=lambda item: item.value)),
        memory_forms=tuple(sorted(set(entry.memory_forms + memory_forms), key=lambda item: item.value)),
        cue_tokens=_normalized_tokens(entry.cue_tokens + cue_tokens),
        context_tokens=_normalized_tokens(entry.context_tokens + context_tokens),
        task_tokens=_normalized_tokens(entry.task_tokens + task_tokens),
        structure_tokens=_normalized_tokens(entry.structure_tokens + structure_tokens),
        identity_handles=_normalized_tokens(entry.identity_handles + identity_handles),
        source_classes=_normalized_tokens(entry.source_classes + source_classes),
        transition_from_ref=entry.transition_from_ref or transition_from_ref,
        transition_action=entry.transition_action or transition_action,
        transition_to_ref=entry.transition_to_ref or transition_to_ref,
        support_count=entry.support_count + (1 if support else 0),
        exception_count=entry.exception_count + (1 if exception else 0),
        last_supported_observation_no=max(entry.last_supported_observation_no, observation_no),
    )


def navmap_memory_store_map_v1(
    ctx: Any,
    navmap: NavMapV2,
    *,
    memory_kinds: Sequence[NavMapMemoryKindV1],
    memory_forms: Sequence[NavMapMemoryFormV1],
    observation_no: int,
    reason: str,
    column_memory: Optional[ColumnMemory] = None,
    cue_tokens: Sequence[str] = (),
    context_tokens: Sequence[str] = (),
    task_tokens: Sequence[str] = (),
    identity_handles: Sequence[str] = (),
    transition_from_ref: Optional[NavMapRefV1] = None,
    transition_action: Optional[str] = None,
    transition_to_ref: Optional[NavMapRefV1] = None,
    support: bool = True,
    exception: bool = False,
    eligibility: Optional[NavMapConsolidationEligibilityV1] = None,
) -> NavMapConsolidationRecordV1:
    """Store or strengthen one exact versioned NavMap through ColumnMemory.

    Repeated support for the same exact map revision updates the lightweight
    index rather than writing a duplicate payload. A different revision remains
    a distinct long-term record. The storage operation never grants candidate,
    ready-set, or operative-WNM authority.
    """
    if ctx is None:
        raise ValueError("ctx is required")
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    _require_positive_int(observation_no, field_name="observation_no")
    _require_nonempty_text(reason, field_name="reason")
    if not isinstance(support, bool) or not isinstance(exception, bool):
        raise TypeError("support and exception must be bool")
    kinds = _enum_tuple(memory_kinds, NavMapMemoryKindV1, field_name="memory_kinds")
    forms = _enum_tuple(memory_forms, NavMapMemoryFormV1, field_name="memory_forms")
    cues = _normalized_tokens(cue_tokens)
    contexts = _normalized_tokens(context_tokens)
    tasks = _normalized_tokens(task_tokens)
    identities = _normalized_tokens(identity_handles)
    structure = _structure_tokens(navmap)
    sources = _source_classes(navmap)
    memory = _column_memory(column_memory)
    ref = _map_ref(navmap)
    ref_key = _ref_key(ref)
    entries = _memory_index(ctx)
    refs = _ref_index(ctx)
    existing_engram_id = refs.get(ref_key)
    existing = entries.get(existing_engram_id) if existing_engram_id is not None else None
    payload_stored = False
    duplicate_avoided = False
    status = "stored_new"

    if existing is not None:
        if existing.record_signature != navmap.record_signature():
            raise ValueError("same map reference cannot index incompatible immutable content")
        updated_entry = _merge_index_entry(
            existing,
            memory_kinds=kinds,
            memory_forms=forms,
            cue_tokens=cues,
            context_tokens=contexts,
            task_tokens=tasks,
            structure_tokens=structure,
            identity_handles=identities,
            source_classes=sources,
            observation_no=observation_no,
            support=support,
            exception=exception,
            transition_from_ref=transition_from_ref,
            transition_action=transition_action,
            transition_to_ref=transition_to_ref,
        )
        entries[existing.engram_id] = updated_entry
        engram_id = existing.engram_id
        duplicate_avoided = True
        status = "supported_existing"
    else:
        attrs = {
            "schema": _MEMORY_INDEX_SCHEMA,
            "phase": "8",
            "map_ref": ref.as_dict(),
            "map_role": navmap.role,
            "frame_id": navmap.frame.frame_id,
            "content_signature": navmap.content_signature(),
            "record_signature": navmap.record_signature(),
            "memory_kinds": [item.value for item in kinds],
            "memory_forms": [item.value for item in forms],
            "cue_tokens": list(cues),
            "context_tokens": list(contexts),
            "task_tokens": list(tasks),
            "structure_tokens": list(structure),
            "identity_handles": list(identities),
            "source_classes": list(sources),
            "transition_from_ref": _optional_ref_dict(transition_from_ref),
            "transition_action": transition_action,
            "transition_to_ref": _optional_ref_dict(transition_to_ref),
            "support_count": 1 if support else 0,
            "exception_count": 1 if exception else 0,
            "stored_observation_no": observation_no,
            "stored_controller_step": _controller_step(ctx),
            "consolidation_reason": reason,
        }
        fact_name = f"{_MEMORY_FACT_PREFIX}:{navmap.role}"
        engram_id = memory.assert_fact(
            fact_name,
            navmap,
            FactMeta(name=fact_name, links=[ref_key], attrs=attrs),
        )
        updated_entry = NavMapMemoryIndexEntryV1(
            engram_id=engram_id,
            column_name=memory.name,
            map_ref=ref,
            map_role=navmap.role,
            frame_id=navmap.frame.frame_id,
            content_signature=navmap.content_signature(),
            record_signature=navmap.record_signature(),
            memory_kinds=kinds,
            memory_forms=forms,
            cue_tokens=cues,
            context_tokens=contexts,
            task_tokens=tasks,
            structure_tokens=structure,
            identity_handles=identities,
            source_classes=sources,
            transition_from_ref=transition_from_ref,
            transition_action=transition_action,
            transition_to_ref=transition_to_ref,
            support_count=1 if support else 0,
            exception_count=1 if exception else 0,
            stored_observation_no=observation_no,
            last_supported_observation_no=observation_no,
            stored_controller_step=_controller_step(ctx),
        )
        entries[engram_id] = updated_entry
        payload_stored = True

    _rebuild_sparse_indexes(ctx, entries)
    strength = eligibility.strength if isinstance(eligibility, NavMapConsolidationEligibilityV1) else 1.0
    record = NavMapConsolidationRecordV1(
        transaction_no=_next_store_transaction_no(ctx),
        observation_no=observation_no,
        controller_step=_controller_step(ctx),
        map_ref=ref,
        eligibility_key=eligibility.eligibility_key if eligibility is not None else None,
        status=status,
        reason=reason,
        engram_id=engram_id,
        column_name=memory.name,
        content_changed=eligibility.content_changed if eligibility is not None else True,
        plasticity_eligible=eligibility.plasticity_eligible if eligibility is not None else True,
        consolidation_pending=False,
        consolidated=True,
        payload_stored=payload_stored,
        duplicate_payload_avoided=duplicate_avoided,
        support_recorded=support,
        exception_recorded=exception,
        eligibility_strength=strength,
    )
    row = record.as_dict()
    ctx.navmap_memory_last_consolidation_v1 = dict(row)
    _append_history(
        ctx,
        "navmap_memory_consolidation_history_v1",
        "navmap_memory_consolidation_history_limit_v1",
        row,
    )
    return record


def _request_kinds(values: Sequence[Any]) -> tuple[NavMapMemoryKindV1, ...]:
    """Return optional requested kinds without requiring a non-empty sequence."""
    if not values:
        return ()
    return tuple(_enum_tuple(values, NavMapMemoryKindV1, field_name="requested_memory_kinds"))


def _request_forms(values: Sequence[Any]) -> tuple[NavMapMemoryFormV1, ...]:
    """Return optional requested forms without requiring a non-empty sequence."""
    if not values:
        return ()
    return tuple(_enum_tuple(values, NavMapMemoryFormV1, field_name="requested_memory_forms"))


def navmap_memory_request_strategic_retrieval_v1(
    ctx: Any,
    *,
    cue_tokens: Sequence[str] = (),
    context_tokens: Sequence[str] = (),
    task_bias_tokens: Sequence[str] = (),
    requested_memory_kinds: Sequence[NavMapMemoryKindV1] = (),
    requested_memory_forms: Sequence[NavMapMemoryFormV1] = (),
    commit_mode: NavMapRetrievalCommitModeV1 = NavMapRetrievalCommitModeV1.READY,
    candidate_ref_limit: Optional[int] = None,
    reinstatement_limit: Optional[int] = None,
    reason: str = "strategic_pfc_biased_retrieval",
) -> dict[str, Any]:
    """Install one one-shot strategic retrieval intent on ``ctx``.

    The intent biases candidate activation but does not itself access Column
    payloads or confer authority. The next Phase 8 observation transaction
    consumes and clears it.
    """
    if ctx is None:
        return {"schema": "navmap_strategic_retrieval_intent_v1", "phase": "8", "status": "ctx_unavailable"}
    if not isinstance(commit_mode, NavMapRetrievalCommitModeV1):
        raise TypeError("commit_mode must be NavMapRetrievalCommitModeV1")
    _require_nonempty_text(reason, field_name="reason")
    candidate_limit = candidate_ref_limit or _ctx_int(
        ctx,
        "navmap_memory_candidate_ref_limit_v1",
        _DEFAULT_CANDIDATE_REF_LIMIT,
    )
    reinstate_limit = reinstatement_limit or _ctx_int(
        ctx,
        "navmap_memory_reinstatement_limit_v1",
        _DEFAULT_REINSTATEMENT_LIMIT,
    )
    candidate_limit = max(1, candidate_limit)
    reinstate_limit = max(1, min(candidate_limit, reinstate_limit))
    row = {
        "schema": "navmap_strategic_retrieval_intent_v1",
        "phase": "8",
        "status": "pending",
        "mode": "strategic",
        "cue_tokens": list(_normalized_tokens(cue_tokens)),
        "context_tokens": list(_normalized_tokens(context_tokens)),
        "task_bias_tokens": list(_normalized_tokens(task_bias_tokens)),
        "requested_memory_kinds": [item.value for item in _request_kinds(requested_memory_kinds)],
        "requested_memory_forms": [item.value for item in _request_forms(requested_memory_forms)],
        "commit_mode": commit_mode.value,
        "candidate_ref_limit": candidate_limit,
        "reinstatement_limit": reinstate_limit,
        "reason": reason,
        "grants_authority": False,
    }
    ctx.navmap_memory_strategic_request_v1 = dict(row)
    return dict(row)


def _query_tokens_from_map(navmap: Optional[NavMapV2]) -> tuple[str, ...]:
    """Return structure tokens contributed by a current partial WNM/evidence map."""
    if navmap is None:
        return ()
    values = list(_structure_tokens(navmap))
    values.extend((f"map:{navmap.map_id}", f"role:{navmap.role}", f"frame:{navmap.frame.frame_id}"))
    return _normalized_tokens(values)


def _candidate_ids_from_sparse_index(ctx: Any, query_tokens: tuple[str, ...]) -> tuple[str, ...]:
    """Return candidate engram ids through inverted-token lookup only."""
    raw = getattr(ctx, "navmap_memory_token_index_v1", None)
    if not isinstance(raw, dict):
        return ()
    ids: set[str] = set()
    for token in query_tokens:
        values = raw.get(token)
        if isinstance(values, list):
            ids.update(item for item in values if isinstance(item, str) and item)
    return tuple(sorted(ids))


def _fraction_overlap(query: tuple[str, ...], stored: tuple[str, ...]) -> tuple[float, tuple[str, ...]]:
    """Return bounded query-token coverage and exact matched tokens."""
    if not query:
        return 0.0, ()
    query_set = set(query)
    stored_set = set(stored)
    matched = tuple(sorted(query_set.intersection(stored_set)))
    return len(matched) / len(query_set), matched


def _candidate_score(
    entry: NavMapMemoryIndexEntryV1,
    *,
    cue_tokens: tuple[str, ...],
    context_tokens: tuple[str, ...],
    task_tokens: tuple[str, ...],
    structure_tokens: tuple[str, ...],
    strategic: bool,
) -> tuple[float, float, float, float, float, float, float, tuple[str, ...], tuple[str, ...]]:
    """Return cheap associative activation components for one index entry."""
    cue_score, cue_match = _fraction_overlap(cue_tokens, entry.cue_tokens + entry.structure_tokens)
    context_score, context_match = _fraction_overlap(context_tokens, entry.context_tokens + entry.structure_tokens)
    task_score, task_match = _fraction_overlap(task_tokens, entry.task_tokens + entry.structure_tokens)
    structure_score, structure_match = _fraction_overlap(structure_tokens, entry.structure_tokens)
    support_score = min(1.0, math.log2(entry.support_count + 1) / 4.0) if entry.support_count > 0 else 0.0
    exception_penalty = min(1.0, entry.exception_count / max(1, entry.support_count + entry.exception_count))
    if strategic:
        activation = (
            0.20 * cue_score
            + 0.15 * context_score
            + 0.35 * task_score
            + 0.20 * structure_score
            + 0.10 * support_score
        )
    else:
        activation = (
            0.35 * cue_score
            + 0.20 * context_score
            + 0.10 * task_score
            + 0.25 * structure_score
            + 0.10 * support_score
        )
    activation = min(1.0, max(0.0, activation * (1.0 - 0.50 * exception_penalty)))
    matched = _normalized_tokens(cue_match + context_match + task_match + structure_match)
    reasons: list[str] = []
    if cue_match:
        reasons.append("cue_overlap")
    if context_match:
        reasons.append("context_overlap")
    if task_match:
        reasons.append("task_bias_overlap")
    if structure_match:
        reasons.append("partial_structure_overlap")
    if support_score > 0.0:
        reasons.append("prior_support")
    if exception_penalty > 0.0:
        reasons.append("exception_penalty")
    return (
        activation,
        cue_score,
        context_score,
        task_score,
        structure_score,
        support_score,
        exception_penalty,
        matched,
        _normalized_tokens(reasons),
    )


def _candidate_refs(
    ctx: Any,
    request: NavMapRetrievalRequestV1,
    *,
    query_map: Optional[NavMapV2],
) -> tuple[NavMapCandidateRefV1, ...]:
    """Generate a bounded candidate-reference set without payload access."""
    entries = _memory_index(ctx)
    structure_tokens = _query_tokens_from_map(query_map)
    kind_tokens = tuple(f"kind:{item.value}" for item in request.requested_memory_kinds)
    form_tokens = tuple(f"form:{item.value}" for item in request.requested_memory_forms)
    query_tokens = _normalized_tokens(
        request.cue_tokens
        + request.context_tokens
        + request.task_bias_tokens
        + structure_tokens
        + kind_tokens
        + form_tokens
    )
    candidate_ids = _candidate_ids_from_sparse_index(ctx, query_tokens)
    minimum_score = max(
        0.0,
        min(1.0, _ctx_float(ctx, "navmap_memory_minimum_activation_score_v1", _DEFAULT_MINIMUM_ACTIVATION_SCORE)),
    )
    candidates: list[NavMapCandidateRefV1] = []
    for engram_id in candidate_ids:
        entry = entries.get(engram_id)
        if entry is None:
            continue
        if request.requested_memory_kinds and not set(request.requested_memory_kinds).intersection(entry.memory_kinds):
            continue
        if request.requested_memory_forms and not set(request.requested_memory_forms).intersection(entry.memory_forms):
            continue
        values = _candidate_score(
            entry,
            cue_tokens=request.cue_tokens,
            context_tokens=request.context_tokens,
            task_tokens=request.task_bias_tokens,
            structure_tokens=structure_tokens,
            strategic=request.mode is NavMapRetrievalModeV1.STRATEGIC,
        )
        activation = values[0]
        if activation < minimum_score:
            continue
        candidates.append(
            NavMapCandidateRefV1(
                query_no=request.query_no,
                engram_id=entry.engram_id,
                map_ref=entry.map_ref,
                map_role=entry.map_role,
                memory_kinds=entry.memory_kinds,
                memory_forms=entry.memory_forms,
                activation_score=activation,
                cue_score=values[1],
                context_score=values[2],
                task_score=values[3],
                structure_score=values[4],
                support_score=values[5],
                exception_penalty=values[6],
                matched_tokens=values[7],
                activation_reasons=values[8],
            )
        )
    candidates.sort(
        key=lambda item: (
            -item.activation_score,
            -item.task_score,
            -item.structure_score,
            item.map_ref.map_id,
            item.map_ref.revision,
            item.engram_id,
        )
    )
    return tuple(candidates[: request.candidate_ref_limit])


def _reliable_current_evidence(query_map: Optional[NavMapV2], ctx: Any) -> bool:
    """Return whether current query content carries protected reliable evidence."""
    if query_map is None:
        return False
    threshold = max(
        0.0,
        min(1.0, _ctx_float(ctx, "navmap_memory_reliable_evidence_quality_v1", _DEFAULT_RELIABLE_EVIDENCE_QUALITY)),
    )
    return bool(
        query_map.provenance.source_class is NavSourceClassV1.OBSERVED
        and query_map.provenance.quality >= threshold
    )


def _evidence_conflict_from_residual(
    query_map: Optional[NavMapV2],
    residual: Optional[NavStructuredResidualV1],
    ctx: Any,
) -> bool:
    """Return True only when reliable current evidence contradicts memory.

    Missing expected elements in a partial cue are not treated as contradiction.
    Explicit element conflicts, role changes, or novel current relations/links are
    sufficient when the query map is reliable observed evidence.
    """
    if residual is None or not _reliable_current_evidence(query_map, ctx):
        return False
    element_conflict = any(item.content_difference for item in residual.element_residuals)
    return bool(
        residual.map_role_changed
        or element_conflict
        or residual.novel_relations
        or residual.novel_links
    )


def _load_candidate(
    memory: ColumnMemory,
    candidate: NavMapCandidateRefV1,
) -> Optional[NavMapV2]:
    """Load one exact candidate payload by engram id, never by store scan."""
    record = memory.try_get(candidate.engram_id)
    if not isinstance(record, dict):
        return None
    payload = record.get("payload")
    if not isinstance(payload, NavMapV2):
        return None
    if _map_ref(payload) != candidate.map_ref:
        return None
    return payload


def _reinstatements(
    ctx: Any,
    request: NavMapRetrievalRequestV1,
    candidates: tuple[NavMapCandidateRefV1, ...],
    *,
    query_map: Optional[NavMapV2],
    column_memory: ColumnMemory,
) -> tuple[NavMapReinstatementV1, ...]:
    """Selectively load only the bounded candidate subset needed for inspection."""
    selected = candidates[: request.reinstatement_limit]
    loaded: list[tuple[NavMapCandidateRefV1, NavMapV2]] = []
    for candidate in selected:
        navmap = _load_candidate(column_memory, candidate)
        if navmap is not None:
            loaded.append((candidate, navmap))
    if not loaded:
        return ()
    if query_map is None:
        return tuple(
            NavMapReinstatementV1(
                candidate_ref=candidate,
                navmap=navmap,
                match_result=None,
                structured_residual=None,
                evidence_conflict=False,
                status="reinstated_without_query_map",
                reason="payload_loaded_but_current_map_unavailable_for_comparison",
            )
            for candidate, navmap in loaded
        )

    thresholds = navmap_memory_match_thresholds_v1(ctx, maximum_candidates=len(loaded))
    ranking = match_rank(query_map, tuple(navmap for _candidate, navmap in loaded), thresholds=thresholds)
    match_by_ref = {item.target_map_ref: item for item in ranking.ranked_matches}
    results: list[NavMapReinstatementV1] = []
    for candidate, navmap in loaded:
        forward = match_by_ref.get(candidate.map_ref)
        residual: Optional[NavStructuredResidualV1] = None
        conflict = False
        reason = "detailed_match_unavailable"
        status = "reinstated"
        if forward is not None:
            reason = forward.reason
            reverse = match_navmaps(navmap, query_map, thresholds=thresholds)
            residual = structured_residual(navmap, query_map, match_result=reverse)
            conflict = _evidence_conflict_from_residual(query_map, residual, ctx)
            if conflict:
                status = "reinstated_but_conflicts_with_current_evidence"
                reason = "reliable_current_evidence_conflicts_with_memory"
        results.append(
            NavMapReinstatementV1(
                candidate_ref=candidate,
                navmap=navmap,
                match_result=forward,
                structured_residual=residual,
                evidence_conflict=conflict,
                status=status,
                reason=reason,
            )
        )
    return tuple(results)


def _winner_from_ranking(
    ctx: Any,
    query_map: Optional[NavMapV2],
    reinstatements: tuple[NavMapReinstatementV1, ...],
) -> tuple[Optional[NavMapRefV1], Optional[str], Optional[str]]:
    """Return winner ref, rank status, and rank reason from reinstated maps."""
    if query_map is None or not reinstatements:
        return None, None, None
    thresholds = navmap_memory_match_thresholds_v1(ctx, maximum_candidates=len(reinstatements))
    ranking = match_rank(
        query_map,
        tuple(item.navmap for item in reinstatements),
        thresholds=thresholds,
    )
    return ranking.winner_ref, ranking.status.value, ranking.reason


def _update_retrieval_counts(ctx: Any, transaction: NavMapRetrievalTransactionV1) -> None:
    """Update lightweight retrieval counts without modifying payload content."""
    entries = _memory_index(ctx)
    changed = False
    reinstated_ids = {item.candidate_ref.engram_id for item in transaction.reinstatements}
    for engram_id in reinstated_ids:
        entry = entries.get(engram_id)
        if entry is None:
            continue
        entries[engram_id] = replace(
            entry,
            retrieval_count=entry.retrieval_count + 1,
            last_retrieved_query_no=transaction.request.query_no,
        )
        changed = True
    if changed:
        _rebuild_sparse_indexes(ctx, entries)


def _store_retrieval(ctx: Any, transaction: NavMapRetrievalTransactionV1) -> dict[str, Any]:
    """Store one current retrieval, bounded history, and compact counters."""
    ctx.navmap_memory_retrieval_attempt_count_v1 = (
        max(0, _ctx_int(ctx, "navmap_memory_retrieval_attempt_count_v1", 0)) + 1
    )
    if transaction.winner_ref is not None:
        ctx.navmap_memory_clear_winner_count_v1 = (
            max(0, _ctx_int(ctx, "navmap_memory_clear_winner_count_v1", 0)) + 1
        )
    if transaction.evidence_defeats_memory:
        ctx.navmap_memory_evidence_defeat_count_v1 = (
            max(0, _ctx_int(ctx, "navmap_memory_evidence_defeat_count_v1", 0)) + 1
        )
    if transaction.ready_admitted:
        ctx.navmap_memory_ready_admission_count_v1 = (
            max(0, _ctx_int(ctx, "navmap_memory_ready_admission_count_v1", 0)) + 1
        )
    if transaction.associative_jump_committed:
        ctx.navmap_memory_associative_jump_count_v1 = (
            max(0, _ctx_int(ctx, "navmap_memory_associative_jump_count_v1", 0)) + 1
        )
    ctx.navmap_memory_last_retrieval_v1 = transaction
    row = transaction.as_dict()
    ctx.navmap_memory_last_retrieval_update_v1 = dict(row)
    _append_history(
        ctx,
        "navmap_memory_retrieval_history_v1",
        "navmap_memory_retrieval_history_limit_v1",
        row,
    )
    _update_retrieval_counts(ctx, transaction)
    return navmap_memory_summary_v1(ctx)


def _authority_after_winner(
    ctx: Any,
    request: NavMapRetrievalRequestV1,
    winner: NavMapReinstatementV1,
    *,
    observation_no: int,
) -> tuple[NavMapRetrievalStatusV1, bool, bool, str, str]:
    """Apply optional ready admission or associative jump after all guards pass."""
    if request.commit_mode is NavMapRetrievalCommitModeV1.NONE:
        return (
            NavMapRetrievalStatusV1.CLEAR_WINNER,
            False,
            False,
            "winner_remains_retrieved_candidate",
            "clear_match_no_authority_requested",
        )
    match = winner.match_result
    if match is None:
        return (
            NavMapRetrievalStatusV1.AUTHORITY_REJECTED,
            False,
            False,
            "authority_rejected",
            "detailed_match_unavailable",
        )
    minimum_score = max(
        0.0,
        min(1.0, _ctx_float(ctx, "navmap_memory_ready_admission_score_v1", _DEFAULT_READY_ADMISSION_SCORE)),
    )
    minimum_coverage = max(
        0.0,
        min(1.0, _ctx_float(ctx, "navmap_memory_ready_admission_coverage_v1", _DEFAULT_READY_ADMISSION_COVERAGE)),
    )
    if match.score < minimum_score or match.coverage < minimum_coverage:
        return (
            NavMapRetrievalStatusV1.AUTHORITY_REJECTED,
            False,
            False,
            "authority_rejected",
            "match_support_below_ready_admission_threshold",
        )
    if winner.evidence_conflict:
        return (
            NavMapRetrievalStatusV1.EVIDENCE_DEFEATS_MEMORY,
            False,
            False,
            "current_evidence_retains_authority",
            "reliable_current_evidence_conflicts_with_memory",
        )

    support = min(1.0, max(0.0, 0.5 * match.score + 0.5 * match.coverage))
    admission = wnm_admit_ready_map_v1(
        ctx,
        winner.navmap,
        observation_no=observation_no,
        reason=f"phase8_retrieval:{request.reason}",
        identity_handle=(winner.candidate_ref.map_ref.map_id),
        correspondence_basis="phase8_sparse_retrieval_plus_phase1c_match",
        support=support,
        correspondence_ambiguous=False,
    )
    last = admission.get("last_transition") if isinstance(admission, dict) else None
    last = last if isinstance(last, dict) else {}
    ready_accepted = bool(last.get("accepted") and last.get("transition_type") == "ready_admission")
    already_ready = any(_map_ref(item) == winner.candidate_ref.map_ref for item in wnm_ready_maps_v1(ctx))
    ready_guard_passed = ready_accepted or already_ready
    if not ready_guard_passed:
        return (
            NavMapRetrievalStatusV1.AUTHORITY_REJECTED,
            False,
            False,
            "ready_admission_rejected",
            str(last.get("failure_reason") or "ready_admission_not_accepted"),
        )
    if request.commit_mode is NavMapRetrievalCommitModeV1.READY:
        return (
            NavMapRetrievalStatusV1.READY_ADMITTED,
            True,
            False,
            "winner_admitted_to_bounded_ready_set",
            "retrieved_candidate_ready_non_authoritative",
        )

    operative = wnm_operative_map_v1(ctx)
    jump = wnm_commit_transition_v1(
        ctx,
        winner.navmap,
        transition_type=WNMTransitionTypeV1.ASSOCIATIVE_JUMP,
        observation_no=observation_no,
        reason=f"phase8_strategic_associative_jump:{request.reason}",
        identity_handle=winner.candidate_ref.map_ref.map_id,
        correspondence_basis="phase8_clear_retrieval_match_and_explicit_strategic_request",
        support=support,
        correspondence_ambiguous=False,
        expected_source_ref=_map_ref(operative) if operative is not None else None,
    )
    jump_last = jump.get("last_transition") if isinstance(jump, dict) else None
    jump_last = jump_last if isinstance(jump_last, dict) else {}
    committed = bool(jump_last.get("accepted") and jump_last.get("transition_type") == "associative_jump")
    if not committed:
        return (
            NavMapRetrievalStatusV1.AUTHORITY_REJECTED,
            True,
            False,
            "ready_guard_passed_but_jump_rejected",
            str(jump_last.get("failure_reason") or "associative_jump_not_accepted"),
        )
    return (
        NavMapRetrievalStatusV1.ASSOCIATIVE_JUMP_COMMITTED,
        True,
        True,
        "retrieved_map_committed_as_operative_wnm",
        "explicit_strategic_associative_jump_committed",
    )


def navmap_memory_retrieve_v1(
    ctx: Any,
    *,
    query_map: Optional[NavMapV2],
    mode: NavMapRetrievalModeV1,
    cue_tokens: Sequence[str] = (),
    context_tokens: Sequence[str] = (),
    task_bias_tokens: Sequence[str] = (),
    requested_memory_kinds: Sequence[NavMapMemoryKindV1] = (),
    requested_memory_forms: Sequence[NavMapMemoryFormV1] = (),
    commit_mode: NavMapRetrievalCommitModeV1 = NavMapRetrievalCommitModeV1.NONE,
    reason: str,
    observation_no: Optional[int] = None,
    source_evidence_ref: Optional[NavMapRefV1] = None,
    candidate_ref_limit: Optional[int] = None,
    reinstatement_limit: Optional[int] = None,
    column_memory: Optional[ColumnMemory] = None,
) -> dict[str, Any]:
    """Run one bounded sparse retrieval and optional WNM authority transaction."""
    if ctx is None:
        return {"schema": "navmap_memory_summary_v1", "phase": "8", "status": "ctx_unavailable"}
    if query_map is not None and not isinstance(query_map, NavMapV2):
        raise TypeError("query_map must be NavMapV2 or None")
    if not isinstance(mode, NavMapRetrievalModeV1):
        raise TypeError("mode must be NavMapRetrievalModeV1")
    if not isinstance(commit_mode, NavMapRetrievalCommitModeV1):
        raise TypeError("commit_mode must be NavMapRetrievalCommitModeV1")
    _require_nonempty_text(reason, field_name="reason")
    obs_no = observation_no if isinstance(observation_no, int) and observation_no > 0 else max(
        1,
        _ctx_int(ctx, "navmap_memory_observation_no_v1", 1),
    )
    candidate_limit = candidate_ref_limit or _ctx_int(
        ctx,
        "navmap_memory_candidate_ref_limit_v1",
        _DEFAULT_CANDIDATE_REF_LIMIT,
    )
    reinstate_limit = reinstatement_limit or _ctx_int(
        ctx,
        "navmap_memory_reinstatement_limit_v1",
        _DEFAULT_REINSTATEMENT_LIMIT,
    )
    candidate_limit = max(1, candidate_limit)
    reinstate_limit = max(1, min(candidate_limit, reinstate_limit))
    request = NavMapRetrievalRequestV1(
        query_no=_next_query_no(ctx),
        mode=mode,
        query_map_ref=_map_ref(query_map) if query_map is not None else None,
        source_evidence_ref=source_evidence_ref,
        cue_tokens=_normalized_tokens(cue_tokens),
        context_tokens=_normalized_tokens(context_tokens),
        task_bias_tokens=_normalized_tokens(task_bias_tokens),
        requested_memory_kinds=_request_kinds(requested_memory_kinds),
        requested_memory_forms=_request_forms(requested_memory_forms),
        candidate_ref_limit=candidate_limit,
        reinstatement_limit=reinstate_limit,
        commit_mode=commit_mode,
        reason=reason,
    )
    candidates = _candidate_refs(ctx, request, query_map=query_map)
    if not candidates:
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=(),
            reinstatements=(),
            rank_status=None,
            winner_ref=None,
            winner_engram_id=None,
            status=NavMapRetrievalStatusV1.NO_CANDIDATES,
            evidence_defeats_memory=False,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="unknown_preserved",
            reason="sparse_index_returned_no_candidate_references",
        )
        return _store_retrieval(ctx, transaction)

    memory = _column_memory(column_memory)
    reinstated = _reinstatements(
        ctx,
        request,
        candidates,
        query_map=query_map,
        column_memory=memory,
    )
    if not reinstated:
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=candidates,
            reinstatements=(),
            rank_status=None,
            winner_ref=None,
            winner_engram_id=None,
            status=NavMapRetrievalStatusV1.REINSTATEMENT_FAILED,
            evidence_defeats_memory=False,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="unknown_preserved",
            reason="candidate_payloads_missing_or_invalid",
        )
        return _store_retrieval(ctx, transaction)

    if query_map is None:
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=candidates,
            reinstatements=reinstated,
            rank_status=None,
            winner_ref=None,
            winner_engram_id=None,
            status=NavMapRetrievalStatusV1.CANDIDATE_REFS_ONLY,
            evidence_defeats_memory=False,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="comparison_deferred",
            reason="reinstated_candidates_require_current_map_for_detailed_comparison",
        )
        return _store_retrieval(ctx, transaction)

    winner_ref, rank_status, rank_reason = _winner_from_ranking(ctx, query_map, reinstated)
    if winner_ref is None:
        status = NavMapRetrievalStatusV1.UNKNOWN
        if rank_status == NavMatchRankStatusV1.AMBIGUOUS.value:
            status = NavMapRetrievalStatusV1.AMBIGUOUS
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=candidates,
            reinstatements=reinstated,
            rank_status=rank_status,
            winner_ref=None,
            winner_engram_id=None,
            status=status,
            evidence_defeats_memory=False,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="unknown_preserved",
            reason=rank_reason or "detailed_match_did_not_produce_clear_winner",
        )
        return _store_retrieval(ctx, transaction)

    winner = next((item for item in reinstated if _map_ref(item.navmap) == winner_ref), None)
    if winner is None:
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=candidates,
            reinstatements=reinstated,
            rank_status=rank_status,
            winner_ref=None,
            winner_engram_id=None,
            status=NavMapRetrievalStatusV1.REINSTATEMENT_FAILED,
            evidence_defeats_memory=False,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="unknown_preserved",
            reason="ranked_winner_not_present_in_reinstated_set",
        )
        return _store_retrieval(ctx, transaction)

    if winner.evidence_conflict:
        transaction = NavMapRetrievalTransactionV1(
            request=request,
            candidate_refs=candidates,
            reinstatements=reinstated,
            rank_status=rank_status,
            winner_ref=winner_ref,
            winner_engram_id=winner.candidate_ref.engram_id,
            status=NavMapRetrievalStatusV1.EVIDENCE_DEFEATS_MEMORY,
            evidence_defeats_memory=True,
            ready_admitted=False,
            associative_jump_committed=False,
            authority_result="current_evidence_retains_authority",
            reason="reliable_current_evidence_conflicts_with_ranked_memory",
        )
        return _store_retrieval(ctx, transaction)

    authority = _authority_after_winner(
        ctx,
        request,
        winner,
        observation_no=obs_no,
    )
    transaction = NavMapRetrievalTransactionV1(
        request=request,
        candidate_refs=candidates,
        reinstatements=reinstated,
        rank_status=rank_status,
        winner_ref=winner_ref,
        winner_engram_id=winner.candidate_ref.engram_id,
        status=authority[0],
        evidence_defeats_memory=False,
        ready_admitted=authority[1],
        associative_jump_committed=authority[2],
        authority_result=authority[3],
        reason=authority[4],
    )
    return _store_retrieval(ctx, transaction)


def _point_geometry(x: float, y: float) -> NavGeometryV1:
    """Return one concise point geometry for generated memory maps."""
    return NavGeometryV1(
        kind=NavGeometryKindV1.POINT,
        points=(NavPointV1(x=float(x), y=float(y)),),
    )


def _memory_frame(frame_id: str) -> NavFrameV1:
    """Return the normalized task/episode frame used by compact Phase 8 maps."""
    return NavFrameV1(
        frame_id=frame_id,
        x_axis="task_progress",
        y_axis="context_relation",
        units="normalized",
        min_x=-1.0,
        max_x=3.0,
        min_y=-2.0,
        max_y=2.0,
    )


def _memory_provenance(source_ref: str, *, source_class: NavSourceClassV1, quality: float) -> NavProvenanceV1:
    """Return explicit provenance for a generated compact memory map."""
    return NavProvenanceV1(source_class=source_class, source_ref=source_ref, quality=quality)


def _activation(name: str, provenance: NavProvenanceV1, strength: float = 1.0) -> NavActivationV1:
    """Return one generated activation with conservative identifier normalization."""
    return NavActivationV1(_identifier_fragment(name), strength, provenance)


def navmap_memory_build_primitive_map_v1(policy_name: str) -> NavMapV2:
    """Return one compact task-level primitive map without motor trajectory detail."""
    _require_nonempty_text(policy_name, field_name="policy_name")
    fragment = _identifier_fragment(policy_name)
    provenance = _memory_provenance(
        f"runtime:phase8_primitive_map:{policy_name}",
        source_class=NavSourceClassV1.INFERRED,
        quality=0.75,
    )
    elements = (
        # The geometry is a task-order rendering, not a claim of cortical raster
        # storage or a detailed movement trajectory.
        _memory_element("precondition_pattern", "primitive_precondition", 0.0, 0.0, provenance, activation_names=("precondition",)),
        _memory_element("action_intent", "primitive_action_intent", 1.0, 0.0, provenance, activation_names=(policy_name,)),
        _memory_element("expected_outcome", "primitive_expected_outcome", 2.0, 0.0, provenance, activation_names=("expected_outcome",)),
    )
    return NavMapV2(
        map_id=f"primitive_{fragment}_v1",
        revision=1,
        role="behavioral_primitive_map",
        frame=_memory_frame(f"primitive_{fragment}_frame_v1"),
        provenance=provenance,
        elements=elements,
        relations=(
            NavRelationV1("enables", "precondition_pattern", "action_intent", provenance),
            NavRelationV1("predicts", "action_intent", "expected_outcome", provenance),
        ),
    )


def _memory_element(
    element_id: str,
    role: str,
    x: float,
    y: float,
    provenance: NavProvenanceV1,
    *,
    activation_names: Sequence[str],
) -> NavElementV1:
    """Return one compact generated element while avoiding a long constructor at call sites."""
    return NavElementV1(
        element_id=element_id,
        role=role,
        geometry=_point_geometry(x, y),
        activations=tuple(_activation(name, provenance) for name in activation_names),
        parent_element_id=None,
        provenance=provenance,
    )


def navmap_memory_build_trajectory_map_v1(ctx: Any, *, observation_no: int) -> Optional[NavMapV2]:
    """Build one sparse event-level trajectory map from Phase 7, never a movie."""
    state = getattr(ctx, "live_dynamics_state_v1", None)
    if state is None:
        return None
    materiality = getattr(state, "materiality", None)
    event_boundary = bool(getattr(materiality, "event_boundary", False))
    if not event_boundary:
        return None
    overlays = getattr(state, "overlays", ())
    chosen = None
    for overlay in overlays if isinstance(overlays, tuple) else ():
        labels = getattr(overlay, "event_labels", ())
        if labels or bool(getattr(overlay, "material_event", False)):
            chosen = overlay
            break
    if chosen is None and isinstance(overlays, tuple) and overlays:
        chosen = overlays[0]
    if chosen is None:
        return None
    relation = str(getattr(getattr(chosen, "relation", None), "value", "unknown"))
    velocity_x = getattr(chosen, "velocity_x", None)
    velocity_y = getattr(chosen, "velocity_y", None)
    scalar_rate = getattr(chosen, "scalar_rate", None)
    progress = getattr(chosen, "lower_motor_progress", None)
    dx = float(velocity_x) if isinstance(velocity_x, (int, float)) and not isinstance(velocity_x, bool) else 0.0
    dy = float(velocity_y) if isinstance(velocity_y, (int, float)) and not isinstance(velocity_y, bool) else 0.0
    if dx == 0.0 and dy == 0.0:
        if isinstance(scalar_rate, (int, float)) and not isinstance(scalar_rate, bool):
            dx = max(-1.0, min(1.0, float(scalar_rate)))
        elif isinstance(progress, (int, float)) and not isinstance(progress, bool):
            dx = max(0.0, min(1.0, float(progress)))
    provenance = _memory_provenance(
        f"runtime:phase8_trajectory:{relation}:{observation_no}",
        source_class=NavSourceClassV1.HISTORICAL,
        quality=0.80,
    )
    event_labels = tuple(str(item) for item in getattr(chosen, "event_labels", ()) if isinstance(item, str))
    phase_value = str(getattr(getattr(chosen, "phase", None), "value", "unknown"))
    end_activations = _normalized_tokens((relation, phase_value) + event_labels)
    source_map_ref = getattr(chosen, "source_map_ref", None)
    links: tuple[NavMapLinkV1, ...] = ()
    if isinstance(source_map_ref, NavMapRefV1):
        links = (NavMapLinkV1("trajectory_source_map", source_map_ref, "trajectory_start", provenance),)
    return NavMapV2(
        map_id=f"trajectory_{_identifier_fragment(relation)}_{observation_no:06d}",
        revision=1,
        role="temporal_trajectory_episode",
        frame=_memory_frame(f"trajectory_{observation_no:06d}_frame_v1"),
        provenance=provenance,
        elements=(
            _memory_element("trajectory_start", "trajectory_start", 0.0, 0.0, provenance, activation_names=(relation,)),
            _memory_element("trajectory_end", "trajectory_end", dx, dy, provenance, activation_names=end_activations or ("event",)),
        ),
        relations=(NavRelationV1("trajectory_progression", "trajectory_start", "trajectory_end", provenance),),
        links=links,
    )


def navmap_memory_build_before_action_after_map_v1(
    *,
    action: str,
    observation_no: int,
    before_ref: NavMapRefV1,
    after_ref: NavMapRefV1,
    outcome: str,
    support: bool,
    exception: bool,
) -> NavMapV2:
    """Build one compact before-action-after episode with explicit map links."""
    _require_nonempty_text(action, field_name="action")
    _require_positive_int(observation_no, field_name="observation_no")
    if not isinstance(before_ref, NavMapRefV1) or not isinstance(after_ref, NavMapRefV1):
        raise TypeError("before_ref and after_ref must be NavMapRefV1")
    _require_nonempty_text(outcome, field_name="outcome")
    if not isinstance(support, bool) or not isinstance(exception, bool):
        raise TypeError("support and exception must be bool")
    fragment = _identifier_fragment(action)
    provenance = _memory_provenance(
        f"runtime:phase8_baa:{action}:{observation_no}",
        source_class=NavSourceClassV1.HISTORICAL,
        quality=0.85 if support and not exception else 0.70,
    )
    outcome_tokens = (outcome, "support" if support else "no_support", "exception" if exception else "ordinary")
    return NavMapV2(
        map_id=f"baa_{fragment}_{observation_no:06d}",
        revision=1,
        role="before_action_after_episode",
        frame=_memory_frame(f"baa_{observation_no:06d}_frame_v1"),
        provenance=provenance,
        elements=(
            _memory_element("before_state", "before_action_state", 0.0, 0.0, provenance, activation_names=(before_ref.map_id,)),
            _memory_element("action_intent", "action_intent", 1.0, 0.0, provenance, activation_names=(action,)),
            _memory_element("after_state", "after_action_state", 2.0, 0.0, provenance, activation_names=outcome_tokens),
        ),
        relations=(
            NavRelationV1("before_action", "before_state", "action_intent", provenance),
            NavRelationV1("action_after", "action_intent", "after_state", provenance),
        ),
        links=(
            NavMapLinkV1("before_map", before_ref, "before_state", provenance),
            NavMapLinkV1("after_map", after_ref, "after_state", provenance),
        ),
    )


def _obs_tokens(env_obs: EnvObservation) -> tuple[str, ...]:
    """Return current cue/predicate tokens for sparse associative activation."""
    predicates = getattr(env_obs, "predicates", None)
    cues = getattr(env_obs, "cues", None)
    values: list[str] = []
    if isinstance(predicates, list):
        values.extend(str(item) for item in predicates if isinstance(item, str))
    if isinstance(cues, list):
        values.extend(str(item) for item in cues if isinstance(item, str))
    meta = getattr(env_obs, "env_meta", None)
    if isinstance(meta, dict):
        for key in ("scenario_stage", "position", "zone", "context_label"):
            value = meta.get(key)
            if isinstance(value, str) and value:
                values.append(f"context:{key}:{value}")
    return _normalized_tokens(values)


def _context_tokens_from_obs(env_obs: EnvObservation) -> tuple[str, ...]:
    """Return current context-only tokens from observation metadata."""
    meta = getattr(env_obs, "env_meta", None)
    if not isinstance(meta, dict):
        return ()
    values: list[str] = []
    for key in ("scenario_stage", "position", "zone", "context_label", "episode_index"):
        value = meta.get(key)
        if isinstance(value, (str, int)) and not isinstance(value, bool):
            values.append(f"context:{key}:{value}")
    return _normalized_tokens(values)


def _milestone_tokens(env_obs: EnvObservation) -> tuple[str, ...]:
    """Return sparse milestone tokens from current metadata."""
    meta = getattr(env_obs, "env_meta", None)
    if not isinstance(meta, dict):
        return ()
    raw = meta.get("milestones")
    if raw is None:
        raw = meta.get("milestone")
    if isinstance(raw, str):
        return _normalized_tokens((f"milestone:{raw}",))
    if isinstance(raw, list):
        return _normalized_tokens(f"milestone:{item}" for item in raw if isinstance(item, str))
    return ()


def _policy_outcome(ctx: Any, action: Optional[str]) -> tuple[str, bool, bool]:
    """Return a compact support/exception interpretation for one applied action."""
    if not isinstance(action, str) or not action:
        return "not_applicable", False, False
    for attr in ("feeding_last_outcome_v1", "navmap_followmom_compare_last_outcome"):
        outcome = getattr(ctx, attr, None)
        action_applied = getattr(outcome, "action_applied", None)
        outcome_value = getattr(outcome, "outcome", None)
        if action_applied == action and isinstance(outcome_value, str):
            if outcome_value == "success":
                return outcome_value, True, False
            if outcome_value == "failure":
                return outcome_value, False, True
            return outcome_value, False, False
    state = getattr(ctx, "live_dynamics_state_v1", None)
    overlays = getattr(state, "overlays", ())
    if isinstance(overlays, tuple):
        for overlay in overlays:
            if getattr(overlay, "lower_motor_action", None) != action:
                continue
            error = getattr(overlay, "lower_motor_error", None)
            phase = str(getattr(getattr(overlay, "phase", None), "value", "unknown"))
            if isinstance(error, str) and error:
                return f"lower_motor_error:{error}", False, True
            if phase == "completed":
                return "lower_motor_completed", True, False
    return "outcome_unknown", False, False


def _descriptor(
    navmap: Optional[NavMapV2],
    *,
    kinds: Sequence[NavMapMemoryKindV1],
    forms: Sequence[NavMapMemoryFormV1],
    cue_tokens: Sequence[str],
    context_tokens: Sequence[str],
    task_tokens: Sequence[str],
    identity_handles: Sequence[str],
    reason: str,
    transition_from_ref: Optional[NavMapRefV1] = None,
    transition_action: Optional[str] = None,
    transition_to_ref: Optional[NavMapRefV1] = None,
    support: bool = True,
    exception: bool = False,
) -> Optional[_RuntimeMapDescriptorV1]:
    """Return one internal descriptor or ``None`` for unavailable map content."""
    if not isinstance(navmap, NavMapV2):
        return None
    return _RuntimeMapDescriptorV1(
        navmap=navmap,
        memory_kinds=tuple(_enum_tuple(kinds, NavMapMemoryKindV1, field_name="memory_kinds")),
        memory_forms=tuple(_enum_tuple(forms, NavMapMemoryFormV1, field_name="memory_forms")),
        cue_tokens=_normalized_tokens(cue_tokens),
        context_tokens=_normalized_tokens(context_tokens),
        task_tokens=_normalized_tokens(task_tokens),
        identity_handles=_normalized_tokens(identity_handles),
        transition_from_ref=transition_from_ref,
        transition_action=transition_action,
        transition_to_ref=transition_to_ref,
        support=support,
        exception=exception,
        reason=reason,
    )


def _collect_runtime_descriptors(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    observation_no: int,
    applied_policy: Optional[str],
) -> tuple[_RuntimeMapDescriptorV1, ...]:
    """Collect current map families and sparse generated event/transition maps."""
    cues = _obs_tokens(env_obs)
    contexts = _context_tokens_from_obs(env_obs)
    task_tokens = _normalized_tokens((applied_policy or "",))
    descriptors: list[Optional[_RuntimeMapDescriptorV1]] = []
    operative = wnm_operative_map_v1(ctx)
    if operative is not None:
        descriptors.append(
            _descriptor(
                operative,
                kinds=(NavMapMemoryKindV1.MULTISENSORY,),
                forms=(NavMapMemoryFormV1.EPISODIC,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=task_tokens + (f"operative_role:{operative.role}",),
                identity_handles=(),
                reason="current_operative_wnm",
            )
        )
    descriptors.extend(
        (
            _descriptor(
                getattr(ctx, "navmap_v2_shadow_body_ground", None),
                kinds=(NavMapMemoryKindV1.BODY,),
                forms=(NavMapMemoryFormV1.PROTOTYPE,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("posture", "support"),
                identity_handles=("self",),
                reason="maintained_body_ground_map",
            ),
            _descriptor(
                getattr(ctx, "navmap_maternal_map", None),
                kinds=(NavMapMemoryKindV1.MATERNAL, NavMapMemoryKindV1.OBJECT),
                forms=(NavMapMemoryFormV1.IDENTITY, NavMapMemoryFormV1.PROTOTYPE),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("maternal", "follow_mom"),
                identity_handles=("maternal_individual",),
                reason="maintained_maternal_identity_map",
            ),
            _descriptor(
                getattr(ctx, "feeding_maternal_body_map_v1", None),
                kinds=(NavMapMemoryKindV1.OBJECT,),
                forms=(NavMapMemoryFormV1.PROTOTYPE,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("feeding", "seek_nipple"),
                identity_handles=("maternal_individual",),
                reason="maternal_body_object_map",
            ),
            _descriptor(
                getattr(ctx, "feeding_closeup_map_v1", None),
                kinds=(NavMapMemoryKindV1.LOCAL,),
                forms=(NavMapMemoryFormV1.EPISODIC,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("feeding_closeup", "suckle"),
                identity_handles=("maternal_individual", "maternal_nipple"),
                reason="nipple_mouth_local_map",
            ),
            _descriptor(
                getattr(ctx, "terrain_route_west_map_v1", None),
                kinds=(NavMapMemoryKindV1.TERRAIN,),
                forms=(NavMapMemoryFormV1.PROTOTYPE,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("route", "terrain", "west"),
                identity_handles=("shared_route_landmark",),
                reason="west_route_terrain_map",
            ),
            _descriptor(
                getattr(ctx, "terrain_route_east_map_v1", None),
                kinds=(NavMapMemoryKindV1.TERRAIN,),
                forms=(NavMapMemoryFormV1.PROTOTYPE,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=("route", "terrain", "east", "shelter"),
                identity_handles=("shared_route_landmark",),
                reason="east_route_terrain_map",
            ),
        )
    )

    if isinstance(applied_policy, str) and applied_policy:
        primitive = navmap_memory_build_primitive_map_v1(applied_policy)
        descriptors.append(
            _descriptor(
                primitive,
                kinds=(NavMapMemoryKindV1.PRIMITIVE,),
                forms=(NavMapMemoryFormV1.PROTOTYPE,),
                cue_tokens=(applied_policy,),
                context_tokens=contexts,
                task_tokens=(applied_policy, "behavioral_primitive"),
                identity_handles=(),
                reason="applied_primitive_template",
            )
        )

    trajectory = navmap_memory_build_trajectory_map_v1(ctx, observation_no=observation_no)
    if trajectory is not None:
        descriptors.append(
            _descriptor(
                trajectory,
                kinds=(NavMapMemoryKindV1.TRAJECTORY,),
                forms=(NavMapMemoryFormV1.EPISODIC,),
                cue_tokens=cues,
                context_tokens=contexts,
                task_tokens=(applied_policy or "", "trajectory"),
                identity_handles=(),
                reason="phase7_sparse_event_trajectory",
            )
        )

    previous_ref = getattr(ctx, "navmap_memory_previous_operative_ref_v1", None)
    current_ref = _map_ref(operative) if operative is not None else None
    outcome, support, exception = _policy_outcome(ctx, applied_policy)
    meaningful_baa = bool(
        isinstance(applied_policy, str)
        and isinstance(previous_ref, NavMapRefV1)
        and isinstance(current_ref, NavMapRefV1)
        and (support or exception or trajectory is not None or previous_ref != current_ref)
    )
    if meaningful_baa and isinstance(applied_policy, str) and previous_ref is not None and current_ref is not None:
        baa = navmap_memory_build_before_action_after_map_v1(
            action=applied_policy,
            observation_no=observation_no,
            before_ref=previous_ref,
            after_ref=current_ref,
            outcome=outcome,
            support=support,
            exception=exception,
        )
        descriptors.append(
            _descriptor(
                baa,
                kinds=(NavMapMemoryKindV1.BEFORE_ACTION_AFTER,),
                forms=(NavMapMemoryFormV1.TRANSITION, NavMapMemoryFormV1.EPISODIC),
                cue_tokens=(applied_policy, outcome),
                context_tokens=contexts,
                task_tokens=(applied_policy, "before_action_after"),
                identity_handles=(),
                transition_from_ref=previous_ref,
                transition_action=applied_policy,
                transition_to_ref=current_ref,
                support=support,
                exception=exception,
                reason="meaningful_before_action_after_episode",
            )
        )
    ctx.navmap_memory_previous_operative_ref_v1 = current_ref

    dedup: dict[str, _RuntimeMapDescriptorV1] = {}
    for item in descriptors:
        if item is None:
            continue
        key = _ref_key(_map_ref(item.navmap))
        existing = dedup.get(key)
        if existing is None:
            dedup[key] = item
            continue
        dedup[key] = replace(
            existing,
            memory_kinds=tuple(sorted(set(existing.memory_kinds + item.memory_kinds), key=lambda value: value.value)),
            memory_forms=tuple(sorted(set(existing.memory_forms + item.memory_forms), key=lambda value: value.value)),
            cue_tokens=_normalized_tokens(existing.cue_tokens + item.cue_tokens),
            context_tokens=_normalized_tokens(existing.context_tokens + item.context_tokens),
            task_tokens=_normalized_tokens(existing.task_tokens + item.task_tokens),
            identity_handles=_normalized_tokens(existing.identity_handles + item.identity_handles),
            support=existing.support or item.support,
            exception=existing.exception or item.exception,
            reason=f"{existing.reason}+{item.reason}",
        )
    return tuple(dedup[key] for key in sorted(dedup))


def _active_eligibility(ctx: Any) -> dict[str, NavMapConsolidationEligibilityV1]:
    """Return only valid typed eligibility rows."""
    raw = getattr(ctx, "navmap_memory_eligibility_v1", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, NavMapConsolidationEligibilityV1)
    }


def _pending_maps(ctx: Any) -> dict[str, NavMapV2]:
    """Return only valid bounded pending-map payloads."""
    raw = getattr(ctx, "navmap_memory_pending_maps_v1", None)
    if not isinstance(raw, dict):
        return {}
    return {
        str(key): value
        for key, value in raw.items()
        if isinstance(key, str) and isinstance(value, NavMapV2)
    }


def _signal_strengths(
    ctx: Any,
    env_obs: EnvObservation,
    descriptor: _RuntimeMapDescriptorV1,
    *,
    applied_policy: Optional[str],
) -> tuple[float, tuple[str, ...], bool, bool]:
    """Return strength, reasons, content-change, and unresolved flags."""
    ref_key = _ref_key(_map_ref(descriptor.navmap))
    already_indexed = ref_key in _ref_index(ctx)
    reasons: list[str] = []
    strength = 0.0
    content_changed = False
    unresolved = False
    if not already_indexed:
        reasons.append("new_map_revision")
        strength += 0.55
        content_changed = True
    operative = wnm_operative_map_v1(ctx)
    if operative is descriptor.navmap or (
        operative is not None and _map_ref(operative) == _map_ref(descriptor.navmap)
    ):
        reasons.append("current_task_relevance")
        strength += 0.15
    milestones = _milestone_tokens(env_obs)
    if milestones:
        reasons.append("milestone")
        strength += 0.25
    pred_err = getattr(ctx, "pred_err_v0_last", None)
    if isinstance(pred_err, dict) and any(
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        for value in pred_err.values()
    ):
        reasons.append("prediction_error")
        strength += 0.15
    live_state = getattr(ctx, "live_dynamics_state_v1", None)
    materiality = getattr(live_state, "materiality", None)
    if bool(getattr(materiality, "event_boundary", False)):
        reasons.append("temporal_event_boundary")
        strength += 0.20
    if bool(getattr(materiality, "material_change_recommended", False)):
        reasons.append("unresolved_material_mismatch")
        strength += 0.30
        unresolved = True
    if descriptor.memory_kinds in (
        (NavMapMemoryKindV1.TRAJECTORY,),
        (NavMapMemoryKindV1.BEFORE_ACTION_AFTER,),
    ):
        reasons.append("sparse_episode_structure")
        strength += 0.35
    if NavMapMemoryKindV1.PRIMITIVE in descriptor.memory_kinds and not already_indexed:
        reasons.append("primitive_first_use")
        strength += 0.20
    if descriptor.support:
        outcome, supported, _exception = _policy_outcome(ctx, applied_policy)
        if supported:
            reasons.append(f"rewarded_or_successful_outcome:{outcome}")
            strength += 0.20
    if descriptor.exception:
        reasons.append("exception_or_failure")
        strength += 0.25
        unresolved = True
    return min(1.0, strength), _normalized_tokens(reasons), content_changed, unresolved


def _decay_eligibility(ctx: Any, *, observation_no: int) -> tuple[dict[str, NavMapConsolidationEligibilityV1], dict[str, NavMapV2]]:
    """Decay transient eligibility and remove expired/consolidated pending rows."""
    rows = _active_eligibility(ctx)
    maps = _pending_maps(ctx)
    decay = max(0.0, min(1.0, _ctx_float(ctx, "navmap_memory_eligibility_decay_v1", _DEFAULT_ELIGIBILITY_DECAY)))
    retained: dict[str, NavMapConsolidationEligibilityV1] = {}
    retained_maps: dict[str, NavMapV2] = {}
    for key, row in rows.items():
        if row.consolidated:
            continue
        if observation_no > row.expires_after_observation_no and not row.unresolved_mismatch:
            continue
        strength = row.strength if row.unresolved_mismatch else max(0.0, row.strength - decay)
        if strength <= 0.0 and not row.unresolved_mismatch:
            continue
        pending = strength >= max(
            0.0,
            min(1.0, _ctx_float(ctx, "navmap_memory_consolidation_threshold_v1", _DEFAULT_CONSOLIDATION_THRESHOLD)),
        )
        retained[key] = replace(
            row,
            strength=strength,
            plasticity_eligible=strength > 0.0,
            consolidation_pending=pending,
        )
        navmap = maps.get(key)
        if navmap is not None:
            retained_maps[key] = navmap
    return retained, retained_maps


def _strengthen_eligibility(
    ctx: Any,
    env_obs: EnvObservation,
    descriptors: tuple[_RuntimeMapDescriptorV1, ...],
    *,
    observation_no: int,
    applied_policy: Optional[str],
) -> None:
    """Create or strengthen only meaningful local eligibility rows."""
    rows, maps = _decay_eligibility(ctx, observation_no=observation_no)
    ttl = max(1, _ctx_int(ctx, "navmap_memory_eligibility_ttl_v1", _DEFAULT_ELIGIBILITY_TTL))
    threshold = max(
        0.0,
        min(1.0, _ctx_float(ctx, "navmap_memory_consolidation_threshold_v1", _DEFAULT_CONSOLIDATION_THRESHOLD)),
    )
    for descriptor in descriptors:
        key = _ref_key(_map_ref(descriptor.navmap))
        strength, reasons, content_changed, unresolved = _signal_strengths(
            ctx,
            env_obs,
            descriptor,
            applied_policy=applied_policy,
        )
        if strength <= 0.0 or not reasons:
            continue
        previous = rows.get(key)
        if previous is None:
            combined_strength = strength
            combined_reasons = reasons
            created = observation_no
        else:
            combined_strength = min(1.0, max(previous.strength, previous.strength + 0.50 * strength))
            combined_reasons = _normalized_tokens(previous.reasons + reasons)
            created = previous.created_observation_no
            content_changed = previous.content_changed or content_changed
            unresolved = previous.unresolved_mismatch or unresolved
        rows[key] = NavMapConsolidationEligibilityV1(
            eligibility_key=key,
            map_ref=_map_ref(descriptor.navmap),
            source_role=descriptor.navmap.role,
            memory_kinds=descriptor.memory_kinds,
            memory_forms=descriptor.memory_forms,
            created_observation_no=created,
            last_signal_observation_no=observation_no,
            expires_after_observation_no=observation_no + ttl,
            strength=combined_strength,
            reasons=combined_reasons,
            content_changed=content_changed,
            plasticity_eligible=True,
            consolidation_pending=combined_strength >= threshold,
            consolidated=False,
            unresolved_mismatch=unresolved,
        )
        maps[key] = descriptor.navmap

    max_entries = max(1, _ctx_int(ctx, "navmap_memory_eligibility_limit_v1", _DEFAULT_ELIGIBILITY_LIMIT))
    ordered = sorted(
        rows.items(),
        key=lambda item: (
            -item[1].strength,
            -item[1].last_signal_observation_no,
            item[0],
        ),
    )[:max_entries]
    kept_keys = {key for key, _row in ordered}
    ctx.navmap_memory_eligibility_v1 = dict(ordered)
    pending_limit = max(1, _ctx_int(ctx, "navmap_memory_pending_map_limit_v1", _DEFAULT_PENDING_MAP_LIMIT))
    pending_ordered = [
        (key, maps[key])
        for key, _row in ordered
        if key in maps and key in kept_keys
    ][:pending_limit]
    ctx.navmap_memory_pending_maps_v1 = dict(pending_ordered)


def _descriptor_by_key(descriptors: tuple[_RuntimeMapDescriptorV1, ...]) -> dict[str, _RuntimeMapDescriptorV1]:
    """Return descriptors keyed by exact map revision."""
    return {_ref_key(_map_ref(item.navmap)): item for item in descriptors}


def _consolidate_pending(
    ctx: Any,
    descriptors: tuple[_RuntimeMapDescriptorV1, ...],
    *,
    observation_no: int,
    column_memory: Optional[ColumnMemory],
) -> tuple[NavMapConsolidationRecordV1, ...]:
    """Consolidate only the strongest bounded eligible subset."""
    if not bool(getattr(ctx, "navmap_memory_auto_consolidate_v1", True)):
        return ()
    budget = max(0, _ctx_int(ctx, "navmap_memory_consolidation_budget_v1", _DEFAULT_CONSOLIDATION_BUDGET))
    if budget <= 0:
        return ()
    rows = _active_eligibility(ctx)
    maps = _pending_maps(ctx)
    descriptors_by_key = _descriptor_by_key(descriptors)
    pending = [row for row in rows.values() if row.consolidation_pending and not row.consolidated]
    pending.sort(
        key=lambda row: (
            -row.strength,
            row.created_observation_no,
            row.map_ref.map_id,
            row.map_ref.revision,
        )
    )
    records: list[NavMapConsolidationRecordV1] = []
    for row in pending[:budget]:
        key = row.eligibility_key
        navmap = maps.get(key)
        descriptor = descriptors_by_key.get(key)
        if navmap is None:
            continue
        if descriptor is None:
            descriptor = _RuntimeMapDescriptorV1(
                navmap=navmap,
                memory_kinds=row.memory_kinds,
                memory_forms=row.memory_forms,
                cue_tokens=(),
                context_tokens=(),
                task_tokens=(),
                identity_handles=(),
                transition_from_ref=None,
                transition_action=None,
                transition_to_ref=None,
                support=True,
                exception=row.unresolved_mismatch,
                reason="pending_eligibility_replay",
            )
        record = navmap_memory_store_map_v1(
            ctx,
            navmap,
            memory_kinds=descriptor.memory_kinds,
            memory_forms=descriptor.memory_forms,
            observation_no=observation_no,
            reason=f"sparse_consolidation:{descriptor.reason}",
            column_memory=column_memory,
            cue_tokens=descriptor.cue_tokens,
            context_tokens=descriptor.context_tokens,
            task_tokens=descriptor.task_tokens,
            identity_handles=descriptor.identity_handles,
            transition_from_ref=descriptor.transition_from_ref,
            transition_action=descriptor.transition_action,
            transition_to_ref=descriptor.transition_to_ref,
            support=descriptor.support,
            exception=descriptor.exception,
            eligibility=row,
        )
        records.append(record)
        rows[key] = replace(
            row,
            consolidation_pending=False,
            consolidated=True,
        )
        maps.pop(key, None)
    ctx.navmap_memory_eligibility_v1 = rows
    ctx.navmap_memory_pending_maps_v1 = maps
    return tuple(records)


def navmap_memory_replay_eligible_refs_v1(ctx: Any, *, limit: int = 5) -> tuple[NavMapRefV1, ...]:
    """Return a sparse eligible subset for offline replay without library scan."""
    if ctx is None:
        return ()
    limit_value = max(1, int(limit))
    rows = [
        row
        for row in _active_eligibility(ctx).values()
        if row.plasticity_eligible and not row.consolidated
    ]
    rows.sort(key=lambda row: (-row.strength, row.map_ref.map_id, row.map_ref.revision))
    return tuple(row.map_ref for row in rows[:limit_value])


def _strategic_request(ctx: Any) -> Optional[dict[str, Any]]:
    """Consume and clear one pending strategic request specification."""
    raw = getattr(ctx, "navmap_memory_strategic_request_v1", None)
    ctx.navmap_memory_strategic_request_v1 = None
    return dict(raw) if isinstance(raw, dict) and raw.get("status") == "pending" else None


def _current_query_map(ctx: Any) -> Optional[NavMapV2]:
    """Return the current operative WNM or the best current evidence map."""
    operative = wnm_operative_map_v1(ctx)
    if operative is not None:
        return operative
    for attr in (
        "navmap_maternal_evidence_map",
        "navmap_v2_shadow_evidence_body_ground",
        "feeding_evidence_map_v1",
    ):
        value = getattr(ctx, attr, None)
        if isinstance(value, NavMapV2):
            return value
    return None


def _spontaneous_signature(
    query_map: Optional[NavMapV2],
    cue_tokens: tuple[str, ...],
    context_tokens: tuple[str, ...],
) -> str:
    """Return one deterministic recognition-settling signature."""
    ref = _ref_key(_map_ref(query_map)) if query_map is not None else "none"
    return "|".join((ref, ",".join(cue_tokens), ",".join(context_tokens)))


def _should_run_spontaneous(ctx: Any, signature: str, cue_tokens: tuple[str, ...]) -> bool:
    """Return whether cheap cue activation should expand into a new retrieval."""
    if not bool(getattr(ctx, "navmap_memory_spontaneous_retrieval_v1", True)):
        return False
    if not cue_tokens:
        return False
    previous = getattr(ctx, "navmap_memory_last_spontaneous_signature_v1", None)
    if previous == signature:
        return False
    ctx.navmap_memory_last_spontaneous_signature_v1 = signature
    return True


def _strategic_commit_mode(value: Any) -> NavMapRetrievalCommitModeV1:
    """Decode a strategic commit mode with a safe non-authoritative fallback."""
    try:
        return NavMapRetrievalCommitModeV1(str(value))
    except ValueError:
        return NavMapRetrievalCommitModeV1.NONE


def navmap_memory_observation_step_v1(
    ctx: Any,
    env_obs: EnvObservation,
    *,
    applied_policy: Optional[str] = None,
    column_memory: Optional[ColumnMemory] = None,
) -> dict[str, Any]:
    """Run one Phase 8 eligibility, consolidation, and retrieval transaction.

    The function must run after current WNM, terrain, feeding, and Phase 7 live
    dynamics have been updated. It may write only explicitly eligible maps to
    ColumnMemory and may admit a clear retrieval winner to the bounded ready set.
    Spontaneous retrieval never performs an associative jump; strategic requests
    may request one behind the full evidence/match guard.
    """
    if ctx is None or env_obs is None:
        return {"schema": "navmap_memory_summary_v1", "phase": "8", "status": "ctx_or_observation_unavailable"}
    if not bool(getattr(ctx, "navmap_memory_enabled_v1", True)):
        ctx.navmap_memory_last_update_v1 = {
            "schema": "navmap_memory_summary_v1",
            "phase": "8",
            "status": "disabled",
            "authority": "long_term_navmap_memory",
        }
        return dict(ctx.navmap_memory_last_update_v1)

    observation_no = _next_observation_no(ctx)
    policy = applied_policy if isinstance(applied_policy, str) and applied_policy else None
    descriptors = _collect_runtime_descriptors(
        ctx,
        env_obs,
        observation_no=observation_no,
        applied_policy=policy,
    )
    _strengthen_eligibility(
        ctx,
        env_obs,
        descriptors,
        observation_no=observation_no,
        applied_policy=policy,
    )
    consolidated = _consolidate_pending(
        ctx,
        descriptors,
        observation_no=observation_no,
        column_memory=column_memory,
    )

    query_map = _current_query_map(ctx)
    cues = _obs_tokens(env_obs)
    contexts = _context_tokens_from_obs(env_obs)
    strategic = _strategic_request(ctx)
    retrieval_ran = False
    retrieval_summary: Optional[dict[str, Any]] = None
    if strategic is not None:
        retrieval_summary = navmap_memory_retrieve_v1(
            ctx,
            query_map=query_map,
            mode=NavMapRetrievalModeV1.STRATEGIC,
            cue_tokens=tuple(str(item) for item in strategic.get("cue_tokens", []) if isinstance(item, str)),
            context_tokens=tuple(str(item) for item in strategic.get("context_tokens", []) if isinstance(item, str)),
            task_bias_tokens=tuple(
                str(item) for item in strategic.get("task_bias_tokens", []) if isinstance(item, str)
            ),
            requested_memory_kinds=tuple(
                NavMapMemoryKindV1(item)
                for item in strategic.get("requested_memory_kinds", [])
                if isinstance(item, str) and item in {kind.value for kind in NavMapMemoryKindV1}
            ),
            requested_memory_forms=tuple(
                NavMapMemoryFormV1(item)
                for item in strategic.get("requested_memory_forms", [])
                if isinstance(item, str) and item in {form.value for form in NavMapMemoryFormV1}
            ),
            commit_mode=_strategic_commit_mode(strategic.get("commit_mode")),
            reason=str(strategic.get("reason") or "strategic_pfc_biased_retrieval"),
            observation_no=observation_no,
            source_evidence_ref=_map_ref(query_map) if query_map is not None else None,
            candidate_ref_limit=int(strategic.get("candidate_ref_limit") or _DEFAULT_CANDIDATE_REF_LIMIT),
            reinstatement_limit=int(strategic.get("reinstatement_limit") or _DEFAULT_REINSTATEMENT_LIMIT),
            column_memory=column_memory,
        )
        retrieval_ran = True
    else:
        signature = _spontaneous_signature(query_map, cues, contexts)
        if _should_run_spontaneous(ctx, signature, cues):
            retrieval_summary = navmap_memory_retrieve_v1(
                ctx,
                query_map=query_map,
                mode=NavMapRetrievalModeV1.SPONTANEOUS,
                cue_tokens=cues,
                context_tokens=contexts,
                task_bias_tokens=(),
                commit_mode=(
                    NavMapRetrievalCommitModeV1.READY
                    if bool(getattr(ctx, "navmap_memory_spontaneous_ready_admission_v1", True))
                    else NavMapRetrievalCommitModeV1.NONE
                ),
                reason="spontaneous_cue_driven_retrieval",
                observation_no=observation_no,
                source_evidence_ref=_map_ref(query_map) if query_map is not None else None,
                column_memory=column_memory,
            )
            retrieval_ran = True

    summary = navmap_memory_summary_v1(ctx)
    summary["observation_no"] = observation_no
    summary["runtime_map_descriptor_count"] = len(descriptors)
    summary["consolidated_this_observation"] = [item.as_dict() for item in consolidated]
    summary["retrieval_ran"] = retrieval_ran
    summary["recognition_settled_without_requery"] = bool(not retrieval_ran and strategic is None)
    if retrieval_summary is not None:
        summary["retrieval_summary"] = retrieval_summary
    ctx.navmap_memory_last_update_v1 = dict(summary)
    return dict(summary)


def navmap_memory_reset_episode_v1(ctx: Any) -> None:
    """Clear episode-local retrieval state while preserving long-term Column/index memory."""
    if ctx is None:
        return
    ctx.navmap_memory_observation_no_v1 = 0
    ctx.navmap_memory_last_update_v1 = {}
    ctx.navmap_memory_last_retrieval_v1 = None
    ctx.navmap_memory_last_retrieval_update_v1 = {}
    ctx.navmap_memory_strategic_request_v1 = None
    ctx.navmap_memory_last_spontaneous_signature_v1 = None
    ctx.navmap_memory_previous_operative_ref_v1 = None
    ctx.navmap_memory_eligibility_v1 = {}
    ctx.navmap_memory_pending_maps_v1 = {}


def navmap_memory_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe Phase 8 long-term-memory summary."""
    if ctx is None:
        return {"schema": "navmap_memory_summary_v1", "phase": "8", "status": "ctx_unavailable"}
    index = _memory_index(ctx)
    eligibility = _active_eligibility(ctx)
    last = getattr(ctx, "navmap_memory_last_retrieval_v1", None)
    last_row = last.as_dict() if isinstance(last, NavMapRetrievalTransactionV1) else None
    forms: dict[str, int] = {item.value: 0 for item in NavMapMemoryFormV1}
    kinds: dict[str, int] = {item.value: 0 for item in NavMapMemoryKindV1}
    for entry in index.values():
        for memory_form in entry.memory_forms:
            forms[memory_form.value] += 1
        for memory_kind in entry.memory_kinds:
            kinds[memory_kind.value] += 1
    return {
        "schema": "navmap_memory_summary_v1",
        "phase": "8",
        "status": "active" if bool(getattr(ctx, "navmap_memory_enabled_v1", True)) else "disabled",
        "authority": "long_term_navmap_memory",
        "column_payload_count_indexed": len(index),
        "sparse_index_entry_count": len(index),
        "inverted_token_count": len(getattr(ctx, "navmap_memory_token_index_v1", {}) or {}),
        "memory_kind_counts": kinds,
        "memory_form_counts": forms,
        "eligibility_count": len(eligibility),
        "eligibility_pending_count": sum(1 for item in eligibility.values() if item.consolidation_pending),
        "eligibility_rows": [
            item.as_dict()
            for item in sorted(
                eligibility.values(),
                key=lambda row: (-row.strength, row.map_ref.map_id, row.map_ref.revision),
            )
        ],
        "replay_eligible_refs": [ref.as_dict() for ref in navmap_memory_replay_eligible_refs_v1(ctx)],
        "last_consolidation": dict(getattr(ctx, "navmap_memory_last_consolidation_v1", {}) or {}),
        "consolidation_history_count": len(getattr(ctx, "navmap_memory_consolidation_history_v1", []) or []),
        "last_retrieval": last_row,
        "retrieval_history_count": len(getattr(ctx, "navmap_memory_retrieval_history_v1", []) or []),
        "retrieval_attempt_count": max(0, _ctx_int(ctx, "navmap_memory_retrieval_attempt_count_v1", 0)),
        "clear_winner_count": max(0, _ctx_int(ctx, "navmap_memory_clear_winner_count_v1", 0)),
        "evidence_defeat_count": max(0, _ctx_int(ctx, "navmap_memory_evidence_defeat_count_v1", 0)),
        "ready_admission_count": max(0, _ctx_int(ctx, "navmap_memory_ready_admission_count_v1", 0)),
        "associative_jump_count": max(0, _ctx_int(ctx, "navmap_memory_associative_jump_count_v1", 0)),
        "candidate_generation_uses_full_payload_scan": False,
        "reinstatement_bounded": True,
        "retrieval_grants_truth": False,
        "ready_set_has_equal_authority": False,
        "protected_safety_can_be_overridden": False,
        "wnm": wnm_summary_v1(ctx),
    }


def render_navmap_memory_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 8 storage/retrieval lines."""
    summary = navmap_memory_summary_v1(ctx)
    lines = ["PHASE 8 LONG-TERM NAVMAP MEMORY / SPARSE RETRIEVAL:"]
    if summary.get("status") != "active":
        lines.append(f"  status={summary.get('status')} authority=long_term_navmap_memory")
        return lines
    lines.append(
        "  "
        f"status=active indexed={summary.get('sparse_index_entry_count')} "
        f"tokens={summary.get('inverted_token_count')} "
        f"eligibility={summary.get('eligibility_count')} "
        f"pending={summary.get('eligibility_pending_count')} "
        "full_payload_scan=False"
    )
    kinds = summary.get("memory_kind_counts")
    kinds = kinds if isinstance(kinds, dict) else {}
    nonzero_kinds = [f"{key}={value}" for key, value in sorted(kinds.items()) if isinstance(value, int) and value > 0]
    lines.append("  memory_kinds " + (" ".join(nonzero_kinds) if nonzero_kinds else "(none)"))
    retrieval = summary.get("last_retrieval")
    if not isinstance(retrieval, dict):
        lines.append("  retrieval=(none) candidate_or_retrieval_grants_truth=False")
        return lines
    request = retrieval.get("request")
    request = request if isinstance(request, dict) else {}
    lines.append(
        "  "
        f"retrieval query={request.get('query_no')} mode={request.get('mode')} "
        f"status={retrieval.get('status')} candidates={len(retrieval.get('candidate_refs') or [])} "
        f"reinstated={len(retrieval.get('reinstatements') or [])} "
        f"winner={retrieval.get('winner_ref')}"
    )
    lines.append(
        "  "
        f"evidence_defeats_memory={retrieval.get('evidence_defeats_memory')} "
        f"ready_admitted={retrieval.get('ready_admitted')} "
        f"associative_jump={retrieval.get('associative_jump_committed')} "
        f"reason={retrieval.get('reason')}"
    )
    return lines
