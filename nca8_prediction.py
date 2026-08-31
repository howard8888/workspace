#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Current PNM and event-matched pending outcome support for NCA8 Gate A.

Purpose
-------
A Projected NavMap (PNM) is created only after Navigation applies one selected
focal primitive and before its task action reaches the environment boundary.
It contains only the minimum expected task-level relations for that concrete
application.  Later current body evidence closes the originating expectation as
success, failure, unresolved, expired, or not applied.

Authority boundary
------------------
Prediction records are prospective and never become present truth, WNM content,
or action authority.  The prediction runtime cannot dispatch an action or read
the physical environment.  It compares only a later NCA8-owned current
``NavMapStateV1`` whose sampled event follows the originating application.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum
from typing import Sequence

from nca8_maps import Nca8PostureStateV1, Nca8SupportStateV1, NavMapStateV1
from nca8_primitives import PrimitiveApplicationV1

# Small validators intentionally remain local for readable standalone modules.
# pylint: disable=duplicate-code

__version__ = "0.1.0"
__all__ = [
    "Nca8PredictionRuntimeV1",
    "PendingPredictionTraceV1",
    "PredictionOutcomeStatusV1",
    "PredictionOutcomeV1",
    "ProjectedNavMapV1",
    "__version__",
]

_MAX_RELATIONS = 16
_MAX_EVIDENCE = 8
_MAX_PENDING = 8
_MAX_OUTCOME_HISTORY = 32


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_identifier(value: str, *, field_name: str, maximum: int = 180) -> str:
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
) -> tuple[str, ...]:
    """Return one bounded unique tuple while preserving caller order."""
    if len(values) > maximum_items:
        raise ValueError(f"{field_name} may contain at most {maximum_items} items")
    out: list[str] = []
    seen: set[str] = set()
    for raw in values:
        item = _bounded_identifier(raw, field_name=field_name)
        if item in seen:
            raise ValueError(f"{field_name} must not contain duplicates")
        seen.add(item)
        out.append(item)
    return tuple(out)


class PredictionOutcomeStatusV1(str, Enum):
    """Terminal and nonterminal states of one operation-linked expectation."""

    PENDING = "pending"
    SUCCESS = "success"
    FAILURE = "failure"
    UNRESOLVED = "unresolved"
    EXPIRED = "expired"
    NOT_APPLIED = "not_applied"
    CANCELLED = "cancelled"
    SUPERSEDED = "superseded"


@dataclass(frozen=True, slots=True)
class ProjectedNavMapV1:
    """One sparse current task-level prospective layer for one application."""

    pnm_id: str
    application_id: str
    primitive_id: str
    source_wnm_id: str
    created_cycle: int
    expected_relations: tuple[str, ...]
    observation_condition: str
    eligible_from_cycle: int
    expires_after_cycle: int

    def __post_init__(self) -> None:
        for field_name in ("pnm_id", "application_id", "primitive_id", "source_wnm_id"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        created = _positive_int(self.created_cycle, field_name="created_cycle")
        eligible = _positive_int(self.eligible_from_cycle, field_name="eligible_from_cycle")
        expiry = _positive_int(self.expires_after_cycle, field_name="expires_after_cycle")
        if eligible <= created:
            raise ValueError("PNM evidence cannot be eligible in its creation cycle")
        if expiry < eligible:
            raise ValueError("PNM expiry cannot precede its first evidence cycle")
        object.__setattr__(
            self,
            "expected_relations",
            _bounded_unique_strings(
                self.expected_relations,
                field_name="expected relation",
                maximum_items=_MAX_RELATIONS,
            ),
        )
        if not self.expected_relations:
            raise ValueError("PNM requires at least one expected relation")
        object.__setattr__(
            self,
            "observation_condition",
            _bounded_identifier(self.observation_condition, field_name="observation_condition"),
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe PNM snapshot."""
        return {
            "pnm_id": self.pnm_id,
            "application_id": self.application_id,
            "primitive_id": self.primitive_id,
            "source_wnm_id": self.source_wnm_id,
            "created_cycle": self.created_cycle,
            "expected_relations": list(self.expected_relations),
            "observation_condition": self.observation_condition,
            "eligible_from_cycle": self.eligible_from_cycle,
            "expires_after_cycle": self.expires_after_cycle,
            "present_state_authority": False,
        }


@dataclass(frozen=True, slots=True)
class PendingPredictionTraceV1:
    """One bounded operation-linked expectation awaiting matching evidence."""

    trace_id: str
    pnm: ProjectedNavMapV1
    status: PredictionOutcomeStatusV1 = PredictionOutcomeStatusV1.PENDING
    matching_evidence: tuple[str, ...] = ()
    evaluated_cycle: int | None = None
    reason: str = "awaiting_matching_current_body_evidence"

    def __post_init__(self) -> None:
        object.__setattr__(self, "trace_id", _bounded_identifier(self.trace_id, field_name="trace_id"))
        if not isinstance(self.pnm, ProjectedNavMapV1):
            raise TypeError("pnm must be a ProjectedNavMapV1")
        if not isinstance(self.status, PredictionOutcomeStatusV1):
            raise TypeError("status must be a PredictionOutcomeStatusV1")
        object.__setattr__(
            self,
            "matching_evidence",
            _bounded_unique_strings(
                self.matching_evidence,
                field_name="matching evidence",
                maximum_items=_MAX_EVIDENCE,
            ),
        )
        if self.evaluated_cycle is not None:
            evaluated = _positive_int(self.evaluated_cycle, field_name="evaluated_cycle")
            if evaluated <= self.pnm.created_cycle:
                raise ValueError("prediction outcome evidence must follow the originating application")
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    @property
    def is_terminal(self) -> bool:
        """Return whether this prediction no longer awaits evidence."""
        return self.status in {
            PredictionOutcomeStatusV1.SUCCESS,
            PredictionOutcomeStatusV1.FAILURE,
            PredictionOutcomeStatusV1.EXPIRED,
            PredictionOutcomeStatusV1.NOT_APPLIED,
            PredictionOutcomeStatusV1.CANCELLED,
            PredictionOutcomeStatusV1.SUPERSEDED,
        }

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe pending-trace snapshot."""
        return {
            "trace_id": self.trace_id,
            "pnm": self.pnm.as_dict(),
            "status": self.status.value,
            "matching_evidence": list(self.matching_evidence),
            "evaluated_cycle": self.evaluated_cycle,
            "reason": self.reason,
            "is_terminal": self.is_terminal,
            "action_authority": False,
        }


@dataclass(frozen=True, slots=True)
class PredictionOutcomeV1:
    """One explicit evaluation result linked to its originating PNM/application."""

    outcome_id: str
    pnm_id: str
    application_id: str
    primitive_id: str
    status: PredictionOutcomeStatusV1
    evaluated_cycle: int
    evidence_sampled_cycle: int | None
    matching_evidence: tuple[str, ...]
    reason: str

    def __post_init__(self) -> None:
        for field_name in ("outcome_id", "pnm_id", "application_id", "primitive_id"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        if self.status in {PredictionOutcomeStatusV1.PENDING, PredictionOutcomeStatusV1.UNRESOLVED}:
            raise ValueError("PredictionOutcomeV1 records only terminal or explicit not-applied outcomes")
        _positive_int(self.evaluated_cycle, field_name="evaluated_cycle")
        if self.evidence_sampled_cycle is not None:
            _positive_int(self.evidence_sampled_cycle, field_name="evidence_sampled_cycle")
        object.__setattr__(
            self,
            "matching_evidence",
            _bounded_unique_strings(
                self.matching_evidence,
                field_name="matching evidence",
                maximum_items=_MAX_EVIDENCE,
            ),
        )
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe outcome snapshot."""
        return {
            "outcome_id": self.outcome_id,
            "pnm_id": self.pnm_id,
            "application_id": self.application_id,
            "primitive_id": self.primitive_id,
            "status": self.status.value,
            "evaluated_cycle": self.evaluated_cycle,
            "evidence_sampled_cycle": self.evidence_sampled_cycle,
            "matching_evidence": list(self.matching_evidence),
            "reason": self.reason,
        }


class Nca8PredictionRuntimeV1:
    """Own one current PNM, bounded pending traces, and outcome history."""

    def __init__(self, *, pending_capacity: int = _MAX_PENDING) -> None:
        if isinstance(pending_capacity, bool) or not isinstance(pending_capacity, int) or pending_capacity <= 0:
            raise ValueError("pending_capacity must be a positive integer")
        self._pending_capacity = pending_capacity
        self._current: PendingPredictionTraceV1 | None = None
        self._pending: list[PendingPredictionTraceV1] = []
        self._outcome_history: list[PredictionOutcomeV1] = []

    @property
    def current_pnm(self) -> ProjectedNavMapV1 | None:
        """Return the current PNM, when one application awaits evidence."""
        return self._current.pnm if self._current is not None else None

    @property
    def current_trace(self) -> PendingPredictionTraceV1 | None:
        """Return the current application-linked pending prediction trace."""
        return self._current

    def pending_snapshot(self) -> tuple[PendingPredictionTraceV1, ...]:
        """Return all unresolved prediction traces in deterministic order."""
        traces = list(self._pending)
        if self._current is not None:
            traces.append(self._current)
        return tuple(sorted(traces, key=lambda item: (item.pnm.created_cycle, item.pnm.pnm_id)))

    def outcome_history(self) -> tuple[PredictionOutcomeV1, ...]:
        """Return bounded terminal outcome history in causal order."""
        return tuple(self._outcome_history)

    def create_current(
        self,
        application: PrimitiveApplicationV1,
        *,
        expiry_cycles: int = 2,
    ) -> ProjectedNavMapV1:
        """Create one PNM before dispatch and preserve any displaced expectation."""
        if not isinstance(application, PrimitiveApplicationV1):
            raise TypeError("application must be a PrimitiveApplicationV1")
        expiry_window = _positive_int(expiry_cycles, field_name="expiry_cycles")
        if self._current is not None:
            if len(self._pending) >= self._pending_capacity:
                raise OverflowError("bounded pending-prediction capacity would be exceeded")
            self._pending.append(self._current)

        pnm = ProjectedNavMapV1(
            pnm_id=f"pnm:{application.application_id}",
            application_id=application.application_id,
            primitive_id=application.primitive_id,
            source_wnm_id=application.source_wnm_id,
            created_cycle=application.cycle_id,
            expected_relations=application.expected_relations,
            observation_condition=application.observation_condition,
            eligible_from_cycle=application.cycle_id + 1,
            expires_after_cycle=application.cycle_id + expiry_window,
        )
        self._current = PendingPredictionTraceV1(
            trace_id=f"pending:{pnm.pnm_id}",
            pnm=pnm,
        )
        return pnm

    def evaluate_ready(
        self,
        evidence: NavMapStateV1,
        *,
        cycle_id: int,
    ) -> tuple[PredictionOutcomeV1, ...]:
        """Evaluate event-matched later body evidence and retain unresolved traces."""
        if not isinstance(evidence, NavMapStateV1):
            raise TypeError("evidence must be a NavMapStateV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if evidence.applied_cycle != cycle:
            raise ValueError("prediction evaluation requires current-cycle applied evidence")

        current = self._current
        traces = list(self._pending)
        if current is not None:
            traces.append(current)
        self._pending = []
        self._current = None

        outcomes: list[PredictionOutcomeV1] = []
        retained: list[PendingPredictionTraceV1] = []
        for trace in sorted(traces, key=lambda item: (item.pnm.created_cycle, item.pnm.pnm_id)):
            evaluated, outcome = self._evaluate_one(trace, evidence=evidence, cycle_id=cycle)
            if outcome is not None:
                outcomes.append(outcome)
                self._append_outcome(outcome)
            elif evaluated.is_terminal:
                raise RuntimeError("terminal prediction trace did not produce an outcome")
            else:
                retained.append(evaluated)

        if retained:
            self._current = retained[-1]
            self._pending = retained[:-1]
        return tuple(outcomes)

    def _evaluate_one(
        self,
        trace: PendingPredictionTraceV1,
        *,
        evidence: NavMapStateV1,
        cycle_id: int,
    ) -> tuple[PendingPredictionTraceV1, PredictionOutcomeV1 | None]:
        """Evaluate one trace only when its event window and sample time match."""
        pnm = trace.pnm
        if cycle_id < pnm.eligible_from_cycle:
            return trace, None
        if evidence.sampled_event_cycle <= pnm.created_cycle:
            return trace, None

        evidence_relations = tuple(evidence.active_relation_labels)
        if evidence.posture is Nca8PostureStateV1.STANDING and evidence.support is Nca8SupportStateV1.STABLE:
            status = PredictionOutcomeStatusV1.SUCCESS
            reason = "later_current_body_evidence_matches_upright_stable_expectation"
        elif evidence.posture is Nca8PostureStateV1.FALLEN and evidence.support is Nca8SupportStateV1.INADEQUATE:
            status = PredictionOutcomeStatusV1.FAILURE
            reason = "later_current_body_evidence_contradicts_upright_stable_expectation"
        elif cycle_id > pnm.expires_after_cycle:
            status = PredictionOutcomeStatusV1.EXPIRED
            reason = "matching_current_body_evidence_not_resolved_before_expiry"
        else:
            updated = replace(
                trace,
                status=PredictionOutcomeStatusV1.UNRESOLVED,
                matching_evidence=evidence_relations,
                evaluated_cycle=cycle_id,
                reason="current_body_evidence_missing_or_ambiguous",
            )
            return updated, None

        updated = replace(
            trace,
            status=status,
            matching_evidence=evidence_relations,
            evaluated_cycle=cycle_id,
            reason=reason,
        )
        outcome = PredictionOutcomeV1(
            outcome_id=f"outcome:{pnm.pnm_id}:{cycle_id}",
            pnm_id=pnm.pnm_id,
            application_id=pnm.application_id,
            primitive_id=pnm.primitive_id,
            status=status,
            evaluated_cycle=cycle_id,
            evidence_sampled_cycle=evidence.sampled_event_cycle,
            matching_evidence=evidence_relations,
            reason=reason,
        )
        return updated, outcome

    def mark_not_applied(
        self,
        pnm_id: str,
        *,
        cycle_id: int,
        reason: str,
    ) -> PredictionOutcomeV1:
        """Close a just-created PNM when BodyMap cannot authorize its task action."""
        target = _bounded_identifier(pnm_id, field_name="pnm_id")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        trace = self._remove_trace(target)
        if trace is None:
            raise KeyError(f"unknown pending PNM: {target!r}")
        outcome = PredictionOutcomeV1(
            outcome_id=f"outcome:{target}:{cycle}:not_applied",
            pnm_id=target,
            application_id=trace.pnm.application_id,
            primitive_id=trace.pnm.primitive_id,
            status=PredictionOutcomeStatusV1.NOT_APPLIED,
            evaluated_cycle=cycle,
            evidence_sampled_cycle=None,
            matching_evidence=(),
            reason=_bounded_identifier(reason, field_name="reason"),
        )
        self._append_outcome(outcome)
        return outcome

    def _remove_trace(self, pnm_id: str) -> PendingPredictionTraceV1 | None:
        """Remove and return one trace from the current/pending bounded stores."""
        if self._current is not None and self._current.pnm.pnm_id == pnm_id:
            result = self._current
            self._current = None
            return result
        for index, trace in enumerate(self._pending):
            if trace.pnm.pnm_id == pnm_id:
                return self._pending.pop(index)
        return None

    def _append_outcome(self, outcome: PredictionOutcomeV1) -> None:
        """Append one terminal outcome to bounded causal history."""
        self._outcome_history.append(outcome)
        if len(self._outcome_history) > _MAX_OUTCOME_HISTORY:
            del self._outcome_history[:-_MAX_OUTCOME_HISTORY]
