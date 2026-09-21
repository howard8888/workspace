#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Attention, source-linked WNM, and Navigation for NCA8 Gate A.

Purpose
-------
Phase 1D introduces the first focal cognitive commitment.  Attention selects
one currently available map-state candidate without selecting an action.
Navigation then constructs or refreshes one source-linked Working Navigation
Map (WNM), asks the available task-level primitives for explicit applicability
records, and deterministically selects/applies zero or one primitive.

Authority boundary
------------------
Attention owns focal source selection only.  It never names or applies a
primitive.  Navigation owns the WNM and focal primitive arbitration/application,
but it does not own sensory maps, durable learning, BodyMap execution, PNM
outcome truth, or the physical environment.  Domain knowledge belongs in the
candidate and primitive contracts rather than hidden ``if fallen then stand``
branches in these generic services.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import TYPE_CHECKING, Protocol, Sequence, TypeAlias

from nca8_maps import NavMapStateV1
from nca8_visual import VisualNavMapStateV1
from nca8_maternal import MaternalNavMapStateV1
from nca8_support_dynamics import SupportDynamicsV1

# Closed, typed domain union: visual content never acquires dummy posture fields.
SourceNavMapStateV1: TypeAlias = NavMapStateV1 | VisualNavMapStateV1 | MaternalNavMapStateV1

#pylint: disable=unnecessary-ellipsis

if TYPE_CHECKING:
    from nca8_primitives import PrimitiveApplicabilityV1, PrimitiveApplicationV1, PrimitiveRuntimeV1

# Small validators intentionally remain local so the module is readable without
# a generic validation framework.
# pylint: disable=duplicate-code

__version__ = "0.6.0"
__all__ = [
    "SourceNavMapStateV1",
    "AttentionBidV1",
    "AttentionCandidateV1",
    "AttentionDispositionV1",
    "AttentionSelectionV1",
    "AttentionRuntimeV1",
    "NavigationDecisionV1",
    "NavigationRuntimeV1",
    "WorkingNavMapStateV1",
    "__version__",
]

_MAX_ATTENTION_CANDIDATES = 8
_MAX_ATTENTION_REASONS = 8
_MAX_WNM_RELATIONS = 16
_MAX_WNM_CONTEXT_REFS = 4


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _non_negative_int(value: int, *, field_name: str, maximum: int = 1000) -> int:
    """Return one bounded non-negative non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= maximum:
        raise ValueError(f"{field_name} must be an integer between 0 and {maximum}")
    return value


def _bounded_identifier(value: str, *, field_name: str, maximum: int = 160) -> str:
    """Return one non-empty bounded identifier."""
    if not isinstance(value, str):
        raise TypeError(f"{field_name} must be a string")
    normalized = value.strip()
    if not normalized:
        raise ValueError(f"{field_name} must not be blank")
    if len(normalized) > maximum:
        raise ValueError(f"{field_name} exceeds the {maximum}-character limit")
    return normalized


def _bounded_unique_strings(
    values: Sequence[str],
    *,
    field_name: str,
    maximum_items: int,
    maximum_length: int = 160,
) -> tuple[str, ...]:
    """Return one bounded unique tuple while preserving caller order."""
    if len(values) > maximum_items:
        raise ValueError(f"{field_name} may contain at most {maximum_items} items")
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = _bounded_identifier(raw, field_name=field_name, maximum=maximum_length)
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(item)
        out.append(item)
    return tuple(out)


# This Protocol intentionally defines a read-only structural contract.
# Attention accepts candidates without depending on their concrete owning class.
class AttentionCandidateV1(Protocol):
    """Structural contract for a map-state candidate submitted to Attention."""

    @property
    def candidate_id(self) -> str:
        """Return the candidate identifier."""
        ...

    @property
    def source_map_state(self) -> SourceNavMapStateV1:
        """Return the current source NavMap state."""
        ...

    @property
    def published_cycle(self) -> int:
        """Return the cycle in which the candidate was published."""
        ...

    @property
    def reason(self) -> str:
        """Return the candidate publication reason."""
        ...

    @property
    def protected_safety_rank(self) -> int:
        """Return the protected-safety Attention component."""
        ...

    @property
    def new_task_need_rank(self) -> int:
        """Return the new-task-need Attention component."""
        ...

    @property
    def prediction_or_envelope_failure_rank(self) -> int:
        """Return the prediction/envelope-failure Attention component."""
        ...

    @property
    def novelty_or_ambiguity_rank(self) -> int:
        """Return the novelty/ambiguity Attention component."""
        ...

    @property
    def current_task_persistence_rank(self) -> int:
        """Return the current-task-persistence Attention component."""
        ...

    @property
    def activation_rank(self) -> int:
        """Return the activation Attention component."""
        ...

    @property
    def stable_tie_key(self) -> str:
        """Return the deterministic Attention tie key."""
        ...


class AttentionDispositionV1(str, Enum):
    """The three possible focal-source decisions made by Attention."""

    MAINTAIN = "maintain"
    SWITCH = "switch"
    RELEASE = "release"


@dataclass(frozen=True, slots=True)
class AttentionBidV1:
    """One explicit bid from a current map-state candidate.

    Priority components remain separate and inspectable.  This is a deterministic
    engineering baseline, not a claim that the mammalian brain computes one
    literal tuple or global utility value.
    """

    bid_id: str
    candidate_id: str
    source_map_state: SourceNavMapStateV1
    source: str
    cycle_id: int
    protected_safety_rank: int
    new_task_need_rank: int
    prediction_or_envelope_failure_rank: int
    novelty_or_ambiguity_rank: int
    current_task_persistence_rank: int
    activation_rank: int
    reasons: tuple[str, ...]
    safety_escalation: bool
    stable_tie_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "bid_id", _bounded_identifier(self.bid_id, field_name="bid_id"))
        object.__setattr__(
            self,
            "candidate_id",
            _bounded_identifier(self.candidate_id, field_name="candidate_id"),
        )
        if not isinstance(self.source_map_state, (NavMapStateV1, VisualNavMapStateV1, MaternalNavMapStateV1)):
            raise TypeError("source_map_state must be a supported posture, visual or maternal source configuration")
        object.__setattr__(self, "source", _bounded_identifier(self.source, field_name="source"))
        _positive_int(self.cycle_id, field_name="cycle_id")
        if self.source_map_state.applied_cycle != self.cycle_id:
            raise ValueError("Attention bid must reference a state applied in the same cycle")
        if isinstance(self.source_map_state, VisualNavMapStateV1) and not self.source_map_state.evidence_current:
            raise ValueError("unavailable visual content cannot gain focal access through a fabricated bid")
        if isinstance(self.source_map_state, MaternalNavMapStateV1) and not self.source_map_state.focal_accessible:
            raise ValueError("inaccessible maternal content cannot gain focus through a fabricated bid")
        for field_name in (
            "protected_safety_rank",
            "new_task_need_rank",
            "prediction_or_envelope_failure_rank",
            "novelty_or_ambiguity_rank",
            "current_task_persistence_rank",
            "activation_rank",
        ):
            _non_negative_int(getattr(self, field_name), field_name=field_name)
        object.__setattr__(
            self,
            "reasons",
            _bounded_unique_strings(
                self.reasons,
                field_name="attention reason",
                maximum_items=_MAX_ATTENTION_REASONS,
            ),
        )
        if not isinstance(self.safety_escalation, bool):
            raise TypeError("safety_escalation must be Boolean")
        object.__setattr__(
            self,
            "stable_tie_key",
            _bounded_identifier(self.stable_tie_key, field_name="stable_tie_key"),
        )

    @property
    def priority_components(self) -> tuple[int, int, int, int, int, int]:
        """Return the visible lexicographic priority components."""
        return (
            self.protected_safety_rank,
            self.new_task_need_rank,
            self.prediction_or_envelope_failure_rank,
            self.novelty_or_ambiguity_rank,
            self.current_task_persistence_rank,
            self.activation_rank,
        )

    def deterministic_sort_key(self) -> tuple[int, int, int, int, int, int, str]:
        """Return an ascending key whose first item is the winning bid."""
        return (
            -self.protected_safety_rank,
            -self.new_task_need_rank,
            -self.prediction_or_envelope_failure_rank,
            -self.novelty_or_ambiguity_rank,
            -self.current_task_persistence_rank,
            -self.activation_rank,
            self.stable_tie_key,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe bid snapshot."""
        return {
            "bid_id": self.bid_id,
            "candidate_id": self.candidate_id,
            "source_map_state_id": self.source_map_state.state_id,
            "source_map_ref": self.source_map_state.source_map_ref.as_dict(),
            "source": self.source,
            "cycle_id": self.cycle_id,
            "protected_safety_rank": self.protected_safety_rank,
            "new_task_need_rank": self.new_task_need_rank,
            "prediction_or_envelope_failure_rank": self.prediction_or_envelope_failure_rank,
            "novelty_or_ambiguity_rank": self.novelty_or_ambiguity_rank,
            "current_task_persistence_rank": self.current_task_persistence_rank,
            "activation_rank": self.activation_rank,
            "reasons": list(self.reasons),
            "safety_escalation": self.safety_escalation,
            "stable_tie_key": self.stable_tie_key,
            "primitive_id": None,
        }


@dataclass(frozen=True, slots=True)
class AttentionSelectionV1:
    """One maintain/switch/release result produced only by Attention."""

    selection_id: str
    cycle_id: int
    disposition: AttentionDispositionV1
    selected_bid: AttentionBidV1 | None
    previous_wnm_id: str | None
    reasons: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "selection_id",
            _bounded_identifier(self.selection_id, field_name="selection_id"),
        )
        _positive_int(self.cycle_id, field_name="cycle_id")
        if not isinstance(self.disposition, AttentionDispositionV1):
            raise TypeError("disposition must be an AttentionDispositionV1")
        if self.selected_bid is not None:
            if not isinstance(self.selected_bid, AttentionBidV1):
                raise TypeError("selected_bid must be AttentionBidV1 or None")
            if self.selected_bid.cycle_id != self.cycle_id:
                raise ValueError("selected bid and Attention selection must share one cycle")
        if self.disposition is AttentionDispositionV1.RELEASE and self.selected_bid is not None:
            raise ValueError("RELEASE cannot carry a selected bid")
        if self.disposition is not AttentionDispositionV1.RELEASE and self.selected_bid is None:
            raise ValueError("MAINTAIN/SWITCH requires one selected bid")
        if self.previous_wnm_id is not None:
            object.__setattr__(
                self,
                "previous_wnm_id",
                _bounded_identifier(self.previous_wnm_id, field_name="previous_wnm_id"),
            )
        object.__setattr__(
            self,
            "reasons",
            _bounded_unique_strings(
                self.reasons,
                field_name="selection reason",
                maximum_items=_MAX_ATTENTION_REASONS,
            ),
        )

    @property
    def selected_source_state(self) -> SourceNavMapStateV1 | None:
        """Return the selected source state without granting it WNM authority."""
        return self.selected_bid.source_map_state if self.selected_bid is not None else None

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe Attention decision."""
        return {
            "selection_id": self.selection_id,
            "cycle_id": self.cycle_id,
            "disposition": self.disposition.value,
            "selected_bid": self.selected_bid.as_dict() if self.selected_bid is not None else None,
            "previous_wnm_id": self.previous_wnm_id,
            "reasons": list(self.reasons),
            "selected_primitive_id": None,
        }


@dataclass(frozen=True, slots=True)
class WorkingNavMapStateV1:
    """Zero-or-one source-linked bounded working state owned by Navigation.

    The record copies only minimum-sufficient active relation labels and bounded
    context references.  It never writes transformed content back to the durable
    source map or its current sensory state. The optional P16-1E-C support facet
    is actual bounded working content from the same source, not renderer data.
    It is not added to working_relations and is omitted from the A0 primitive's
    argument view. Old immutable WNM snapshots do not refresh themselves.
    """

    working_id: str
    primary_source_state: SourceNavMapStateV1
    source_candidate_id: str
    working_relations: tuple[str, ...]
    context_refs: tuple[str, ...]
    created_cycle: int
    refreshed_cycle: int
    focus_age: int
    support_dynamics: SupportDynamicsV1 | None = None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "working_id",
            _bounded_identifier(self.working_id, field_name="working_id"),
        )
        if not isinstance(self.primary_source_state, (NavMapStateV1, VisualNavMapStateV1, MaternalNavMapStateV1)):
            raise TypeError("primary_source_state must be a supported posture, visual or maternal source configuration")
        object.__setattr__(
            self,
            "source_candidate_id",
            _bounded_identifier(self.source_candidate_id, field_name="source_candidate_id"),
        )
        object.__setattr__(
            self,
            "working_relations",
            _bounded_unique_strings(
                self.working_relations,
                field_name="working relation",
                maximum_items=_MAX_WNM_RELATIONS,
            ),
        )
        object.__setattr__(
            self,
            "context_refs",
            _bounded_unique_strings(
                self.context_refs,
                field_name="WNM context reference",
                maximum_items=_MAX_WNM_CONTEXT_REFS,
            ),
        )
        created = _positive_int(self.created_cycle, field_name="created_cycle")
        refreshed = _positive_int(self.refreshed_cycle, field_name="refreshed_cycle")
        if refreshed < created:
            raise ValueError("refreshed_cycle cannot precede created_cycle")
        age = _positive_int(self.focus_age, field_name="focus_age")
        if age != refreshed - created + 1:
            raise ValueError("focus_age must equal the inclusive source-linked focus duration")
        if self.primary_source_state.applied_cycle != refreshed:
            raise ValueError("WNM must refresh from a source state applied in the current cycle")
        dynamics = self.support_dynamics
        if dynamics is not None:
            if not isinstance(dynamics, SupportDynamicsV1):
                raise TypeError("support_dynamics must be SupportDynamicsV1 or None")
            configuration = dynamics.configuration
            if configuration.source_map_ref != self.primary_source_state.source_map_ref:
                raise ValueError("measured working content must belong to the selected source revision")
            if configuration.applied_cycle != refreshed or configuration.owner_circuit != self.primary_source_state.owner_circuit:
                raise ValueError("measured working content must be refreshed from this cycle's selected source owner")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic snapshot; omit the optional facet for historical A0 compatibility."""
        out: dict[str, object] = {
            "working_id": self.working_id,
            "primary_source_state_id": self.primary_source_state.state_id,
            "primary_source_map_ref": self.primary_source_state.source_map_ref.as_dict(),
            "source_candidate_id": self.source_candidate_id,
            "working_relations": list(self.working_relations),
            "context_refs": list(self.context_refs),
            "created_cycle": self.created_cycle,
            "refreshed_cycle": self.refreshed_cycle,
            "focus_age": self.focus_age,
            "automatic_writeback": False,
            "authority": "navigation_owned_working_state",
        }
        if self.support_dynamics is not None:
            out["support_dynamics"] = self.support_dynamics.as_dict()
        return out


@dataclass(frozen=True, slots=True)
class NavigationDecisionV1:
    """One complete Navigation arbitration result for a selected WNM."""

    decision_id: str
    cycle_id: int
    wnm: WorkingNavMapStateV1 | None
    applicability_records: tuple[PrimitiveApplicabilityV1, ...]
    application: PrimitiveApplicationV1 | None
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "decision_id",
            _bounded_identifier(self.decision_id, field_name="decision_id"),
        )
        _positive_int(self.cycle_id, field_name="cycle_id")
        if self.wnm is not None:
            if not isinstance(self.wnm, WorkingNavMapStateV1):
                raise TypeError("wnm must be WorkingNavMapStateV1 or None")
            if self.wnm.refreshed_cycle != self.cycle_id:
                raise ValueError("Navigation decision must use the current cycle's WNM")
        primitive_ids = tuple(record.primitive_id for record in self.applicability_records)
        if len(set(primitive_ids)) != len(primitive_ids):
            raise ValueError("applicability records must use unique primitive IDs")
        if self.application is not None:
            if self.wnm is None:
                raise ValueError("a primitive application requires one WNM")
            if self.application.cycle_id != self.cycle_id:
                raise ValueError("primitive application must belong to the Navigation cycle")
            if self.application.source_wnm_id != self.wnm.working_id:
                raise ValueError("primitive application must reference the selected WNM")
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    @property
    def selected_primitive_id(self) -> str | None:
        """Return the selected primitive ID, when one application exists."""
        return self.application.primitive_id if self.application is not None else None

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe Navigation decision."""
        return {
            "decision_id": self.decision_id,
            "cycle_id": self.cycle_id,
            "wnm": self.wnm.as_dict() if self.wnm is not None else None,
            "applicability_records": [record.as_dict() for record in self.applicability_records],
            "application": self.application.as_dict() if self.application is not None else None,
            "selected_primitive_id": self.selected_primitive_id,
            "reason": self.reason,
        }


class AttentionRuntimeV1:
    """Select one current map-state source using visible deterministic priorities."""

    def __init__(self, *, enabled: bool = True) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be Boolean")
        self._enabled = enabled
        self._last_selection: AttentionSelectionV1 | None = None

    @property
    def enabled(self) -> bool:
        """Return whether Attention is available for the current ablation condition."""
        return self._enabled

    @property
    def last_selection(self) -> AttentionSelectionV1 | None:
        """Return the most recent immutable Attention result."""
        return self._last_selection

    def build_bid(self, candidate: AttentionCandidateV1, *, cycle_id: int) -> AttentionBidV1:
        """Convert one candidate's generic priority components into a bid."""
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if candidate.published_cycle != cycle:
            raise ValueError("Attention candidate must be current in the bidding cycle")
        return AttentionBidV1(
            bid_id=f"attention_bid:{candidate.candidate_id}:{cycle}",
            candidate_id=candidate.candidate_id,
            source_map_state=candidate.source_map_state,
            source=("maternal_candidate" if isinstance(candidate.source_map_state, MaternalNavMapStateV1) else
                    "visual_candidate" if isinstance(candidate.source_map_state, VisualNavMapStateV1) else "bodymap_candidate"),
            cycle_id=cycle,
            protected_safety_rank=candidate.protected_safety_rank,
            new_task_need_rank=candidate.new_task_need_rank,
            prediction_or_envelope_failure_rank=candidate.prediction_or_envelope_failure_rank,
            novelty_or_ambiguity_rank=candidate.novelty_or_ambiguity_rank,
            current_task_persistence_rank=candidate.current_task_persistence_rank,
            activation_rank=candidate.activation_rank,
            reasons=(candidate.reason,),
            safety_escalation=candidate.protected_safety_rank > 0,
            stable_tie_key=candidate.stable_tie_key,
        )

    def select(
        self,
        bids: Sequence[AttentionBidV1],
        *,
        current_wnm: WorkingNavMapStateV1 | None,
        cycle_id: int,
    ) -> AttentionSelectionV1:
        """Maintain, switch, or release the WNM source without selecting an IP/LP."""
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if len(bids) > _MAX_ATTENTION_CANDIDATES:
            raise ValueError(f"Attention supports at most {_MAX_ATTENTION_CANDIDATES} candidates")
        if len({bid.bid_id for bid in bids}) != len(bids):
            raise ValueError("Attention bid IDs must be unique")
        for bid in bids:
            if not isinstance(bid, AttentionBidV1):
                raise TypeError("bids must contain AttentionBidV1 values")
            if bid.cycle_id != cycle:
                raise ValueError("all Attention bids must belong to the current cycle")

        previous_id = current_wnm.working_id if current_wnm is not None else None
        if not self._enabled:
            selection = AttentionSelectionV1(
                selection_id=f"attention_selection:{cycle}",
                cycle_id=cycle,
                disposition=AttentionDispositionV1.RELEASE,
                selected_bid=None,
                previous_wnm_id=previous_id,
                reasons=("attention_ablation_disabled",),
            )
        elif not bids:
            selection = AttentionSelectionV1(
                selection_id=f"attention_selection:{cycle}",
                cycle_id=cycle,
                disposition=AttentionDispositionV1.RELEASE,
                selected_bid=None,
                previous_wnm_id=previous_id,
                reasons=("no_current_map_state_candidate_requires_focal_access",),
            )
        else:
            winner = sorted(bids, key=lambda item: item.deterministic_sort_key())[0]
            maintain = (
                current_wnm is not None
                and current_wnm.primary_source_state.state_id == winner.source_map_state.state_id
                and current_wnm.primary_source_state.source_map_ref == winner.source_map_state.source_map_ref
            )
            disposition = AttentionDispositionV1.MAINTAIN if maintain else AttentionDispositionV1.SWITCH
            selection = AttentionSelectionV1(
                selection_id=f"attention_selection:{cycle}",
                cycle_id=cycle,
                disposition=disposition,
                selected_bid=winner,
                previous_wnm_id=previous_id,
                reasons=(
                    "highest_visible_lexicographic_priority",
                    "map_state_selected_without_primitive_selection",
                ),
            )
        self._last_selection = selection
        return selection


class NavigationRuntimeV1:
    """Own the zero-or-one WNM and select/apply one focal primitive."""

    def __init__(self, *, enabled: bool = True, motor_preview_enabled: bool = False) -> None:
        if not isinstance(enabled, bool):
            raise TypeError("enabled must be Boolean")
        if not isinstance(motor_preview_enabled, bool):
            raise TypeError("motor_preview_enabled must be Boolean")
        self._motor_preview_enabled = motor_preview_enabled
        self._enabled = enabled
        self._current_wnm: WorkingNavMapStateV1 | None = None
        self._last_decision: NavigationDecisionV1 | None = None
        self._focal_hold_cycle = 0

    @property
    def enabled(self) -> bool:
        """Return whether focal Navigation arbitration is enabled."""
        return self._enabled

    @property
    def current_wnm(self) -> WorkingNavMapStateV1 | None:
        """Return the current immutable source-linked WNM, when present."""
        return self._current_wnm

    @property
    def last_decision(self) -> NavigationDecisionV1 | None:
        """Return the most recent immutable Navigation result."""
        return self._last_decision

    def update_wnm(
        self, selection: AttentionSelectionV1, *, support_dynamics: SupportDynamicsV1 | None = None,
    ) -> WorkingNavMapStateV1 | None:
        """Refresh one selected source, including optional read-only measured content.

        The source owner supplies an already applied immutable facet. Its source,
        owner and application cycle must agree with the chosen WNM. A missing
        facet clears older content rather than reusing a stale working snapshot.
        Release creates no WNM even if nonfocal source dynamics continue updating.
        """
        if not isinstance(selection, AttentionSelectionV1):
            raise TypeError("selection must be an AttentionSelectionV1")
        if selection.disposition is AttentionDispositionV1.RELEASE:
            self._current_wnm = None
            return None

        bid = selection.selected_bid
        if bid is None:  # pragma: no cover - guarded by AttentionSelectionV1
            raise RuntimeError("non-release Attention selection has no bid")
        source = bid.source_map_state
        existing = self._current_wnm
        if (
            existing is not None
            and existing.primary_source_state.state_id == source.state_id
            and existing.primary_source_state.source_map_ref == source.source_map_ref
        ):
            created_cycle = existing.created_cycle
        else:
            created_cycle = selection.cycle_id
        next_wnm = WorkingNavMapStateV1(
            working_id="wnm:current",
            primary_source_state=source,
            source_candidate_id=bid.candidate_id,
            working_relations=source.active_relation_labels,
            context_refs=(),
            created_cycle=created_cycle,
            refreshed_cycle=selection.cycle_id,
            focus_age=selection.cycle_id - created_cycle + 1,
            support_dynamics=replace(support_dynamics) if support_dynamics is not None else None,
        )
        self._current_wnm = next_wnm
        return next_wnm

    def record_focal_hold(self, wnm: WorkingNavMapStateV1, *, cycle_id: int, reason: str) -> NavigationDecisionV1:
        """Record a nonprimitive allocation without secretly evaluating a task.

        The approved domain coordinator supplies the reason after establishing
        this very WNM. A demanding interpretation, or its unresolved dependency,
        excludes a simultaneous ordinary primitive application. This service
        does not interpret the outcome itself and names no domain or primitive.
        The hold cannot later be relabelled as a new task in the same opportunity.
        """
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if not isinstance(wnm, WorkingNavMapStateV1) or wnm is not self._current_wnm or wnm.refreshed_cycle != cycle:
            raise ValueError("focal hold requires Navigation's current source-linked WNM")
        if self._last_decision is not None and self._last_decision.cycle_id >= cycle:
            raise ValueError("one Navigation allocation is permitted per focal opportunity")
        decision = NavigationDecisionV1(f"navigation_decision:{cycle}", cycle, wnm, (), None, reason)
        self._focal_hold_cycle = cycle
        self._last_decision = decision
        return decision

    def commit(
        self,
        wnm: WorkingNavMapStateV1 | None,
        primitives: Sequence[PrimitiveRuntimeV1],
        *,
        cycle_id: int,
    ) -> NavigationDecisionV1:
        """Evaluate all primitives unless this opportunity was allocated elsewhere."""
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if cycle <= self._focal_hold_cycle:
            raise ValueError("a focal hold cannot also execute an ordinary primitive")
        if wnm is None or not self._enabled:
            decision = NavigationDecisionV1(
                decision_id=f"navigation_decision:{cycle}",
                cycle_id=cycle,
                wnm=wnm,
                applicability_records=(),
                application=None,
                reason="navigation_ablation_disabled" if not self._enabled else "no_wnm",
            )
            self._last_decision = decision
            return decision

        # P16-1E-C grants representation, not richer selector authority. The
        # argument view is not stored or selected as another WNM. Both primitive
        # queries and apply() receive only the pre-existing A0 content.
        primitive_view = replace(wnm, support_dynamics=None) if wnm.support_dynamics is not None else wnm
        # H5 explicitly admits the enhanced facet only to an opt-in preview
        # selector. A0 continues to receive no motor/support-dynamics authority.
        if (not self._motor_preview_enabled and isinstance(primitive_view.primary_source_state, NavMapStateV1)
                and primitive_view.primary_source_state.motor_support is not None):
            primitive_view = replace(
                primitive_view, primary_source_state=replace(primitive_view.primary_source_state, motor_support=None),
            )

        primitive_ids = [primitive.primitive_id for primitive in primitives]
        if len(set(primitive_ids)) != len(primitive_ids):
            raise ValueError("primitive IDs must be unique")
        ordered_primitives = tuple(sorted(primitives, key=lambda item: item.primitive_id))
        records = tuple(
            primitive.evaluate_applicability(primitive_view, cycle_id=cycle)
            for primitive in ordered_primitives
        )
        eligible = tuple(record for record in records if record.eligible)
        if not eligible:
            decision = NavigationDecisionV1(
                decision_id=f"navigation_decision:{cycle}",
                cycle_id=cycle,
                wnm=wnm,
                applicability_records=records,
                application=None,
                reason="no_eligible_primitive",
            )
            self._last_decision = decision
            return decision

        winner_record = sorted(eligible, key=lambda item: item.deterministic_sort_key())[0]
        by_id = {primitive.primitive_id: primitive for primitive in ordered_primitives}
        winner = by_id[winner_record.primitive_id]
        application = winner.apply(primitive_view, winner_record, cycle_id=cycle)
        decision = NavigationDecisionV1(
            decision_id=f"navigation_decision:{cycle}",
            cycle_id=cycle,
            wnm=wnm,
            applicability_records=records,
            application=application,
            reason="selected_by_visible_navigation_components",
        )
        self._last_decision = decision
        return decision
