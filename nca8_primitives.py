#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Task-level primitive contracts and the developmental StandUp IP for NCA8.

Purpose
-------
Phase 1D introduces one genuine focal operation.  The common primitive contract
keeps applicability, operation, and expected consequence separate and visible.
The developmental ``StandUpIPV1`` evaluates only the current source-linked WNM;
it never reads the environment, scenario stage, milestones, legacy policy
selection, BodyMap internals, or trace output.

Authority boundary
------------------
A primitive can report applicability and, only after Navigation selects it,
return one bounded application.  It cannot select itself, create the PNM,
authorize lower body execution, dispatch an environment token, or declare its
own outcome successful.  Those authorities remain with Navigation, Prediction,
BodyMap, the action adapter, and later evidence respectively.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Protocol, Sequence

from nca8_executive import WorkingNavMapStateV1
from nca8_maps import NavMapStateV1

# Small validators intentionally remain local for readable standalone modules.
# pylint: disable=duplicate-code

__version__ = "0.1.1"
__all__ = [
    "ActionEnvelopeRequestV1",
    "PrimitiveApplicabilityV1",
    "PrimitiveApplicationV1",
    "PrimitiveKindV1",
    "PrimitiveRuntimeV1",
    "StandUpIPV1",
    "TaskActionKindV1",
    "TaskActionV1",
    "create_gate_a_primitives_v1",
    "__version__",
]

_MAX_RELATIONS = 16
_MAX_REASONS = 8
_MAX_RESOURCES = 8
_MAX_ENVELOPE_RULES = 8


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
    return value


def _bounded_int(value: int, *, field_name: str, minimum: int = 0, maximum: int = 1000) -> int:
    """Return one bounded non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{field_name} must be an integer between {minimum} and {maximum}")
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
    maximum_length: int = 180,
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


class PrimitiveKindV1(str, Enum):
    """Developmental origin of one task-level primitive."""

    INSTINCTIVE = "instinctive"
    LEARNED = "learned"


class TaskActionKindV1(str, Enum):
    """Internal NCA8 task-action kinds introduced through Gate A."""

    STAND_UP = "STAND_UP"
    NO_ACTION = "NO_ACTION"


@dataclass(frozen=True, slots=True)
class PrimitiveApplicabilityV1:
    """One inspectable applicability result produced before Navigation chooses.

    Separate rank components are a deterministic engineering baseline rather
    than a claim that biology computes one literal scalar utility.  Vetoes are
    explicit and always defeat eligibility.
    """

    primitive_id: str
    primitive_kind: PrimitiveKindV1
    cycle_id: int
    source_wnm_id: str
    eligible: bool
    safety_rank: int
    fit_rank: int
    drive_rank: int
    persistence_rank: int
    learned_success_rank: int
    vetoes: tuple[str, ...]
    reasons: tuple[str, ...]
    stable_tie_key: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "primitive_id", _bounded_identifier(self.primitive_id, field_name="primitive_id"))
        if not isinstance(self.primitive_kind, PrimitiveKindV1):
            raise TypeError("primitive_kind must be a PrimitiveKindV1")
        _positive_int(self.cycle_id, field_name="cycle_id")
        object.__setattr__(
            self,
            "source_wnm_id",
            _bounded_identifier(self.source_wnm_id, field_name="source_wnm_id"),
        )
        if not isinstance(self.eligible, bool):
            raise TypeError("eligible must be Boolean")
        for field_name in (
            "safety_rank",
            "fit_rank",
            "drive_rank",
            "persistence_rank",
            "learned_success_rank",
        ):
            _bounded_int(getattr(self, field_name), field_name=field_name)
        object.__setattr__(
            self,
            "vetoes",
            _bounded_unique_strings(self.vetoes, field_name="primitive veto", maximum_items=_MAX_REASONS),
        )
        object.__setattr__(
            self,
            "reasons",
            _bounded_unique_strings(self.reasons, field_name="applicability reason", maximum_items=_MAX_REASONS),
        )
        if self.vetoes and self.eligible:
            raise ValueError("a vetoed primitive cannot be eligible")
        object.__setattr__(
            self,
            "stable_tie_key",
            _bounded_identifier(self.stable_tie_key, field_name="stable_tie_key"),
        )

    def deterministic_sort_key(self) -> tuple[int, int, int, int, int, str]:
        """Return an ascending key whose first value is Navigation's winner."""
        return (
            -self.safety_rank,
            -self.fit_rank,
            -self.drive_rank,
            -self.persistence_rank,
            -self.learned_success_rank,
            self.stable_tie_key,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe applicability snapshot."""
        return {
            "primitive_id": self.primitive_id,
            "primitive_kind": self.primitive_kind.value,
            "cycle_id": self.cycle_id,
            "source_wnm_id": self.source_wnm_id,
            "eligible": self.eligible,
            "safety_rank": self.safety_rank,
            "fit_rank": self.fit_rank,
            "drive_rank": self.drive_rank,
            "persistence_rank": self.persistence_rank,
            "learned_success_rank": self.learned_success_rank,
            "vetoes": list(self.vetoes),
            "reasons": list(self.reasons),
            "stable_tie_key": self.stable_tie_key,
        }


@dataclass(frozen=True, slots=True)
class TaskActionV1:
    """One internal task-level command produced by a selected application."""

    task_action_id: str
    action_number: int
    kind: TaskActionKindV1
    source_application_id: str
    action_relevant_relations: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "task_action_id",
            _bounded_identifier(self.task_action_id, field_name="task_action_id"),
        )
        _positive_int(self.action_number, field_name="action_number")
        if not isinstance(self.kind, TaskActionKindV1):
            raise TypeError("kind must be a TaskActionKindV1")
        object.__setattr__(
            self,
            "source_application_id",
            _bounded_identifier(self.source_application_id, field_name="source_application_id"),
        )
        object.__setattr__(
            self,
            "action_relevant_relations",
            _bounded_unique_strings(
                self.action_relevant_relations,
                field_name="action-relevant relation",
                maximum_items=_MAX_RELATIONS,
            ),
        )
        if self.kind is TaskActionKindV1.NO_ACTION and self.action_relevant_relations:
            raise ValueError("NO_ACTION must not carry action-relevant relations")

    @property
    def is_null(self) -> bool:
        """Return whether this task output explicitly requests no new task action."""
        return self.kind is TaskActionKindV1.NO_ACTION

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe task-action snapshot."""
        return {
            "task_action_id": self.task_action_id,
            "action_number": self.action_number,
            "kind": self.kind.value,
            "source_application_id": self.source_application_id,
            "action_relevant_relations": list(self.action_relevant_relations),
            "is_null": self.is_null,
        }


@dataclass(frozen=True, slots=True)
class ActionEnvelopeRequestV1:
    """Primitive-requested bounds for a later BodyMap authorization decision."""

    request_id: str
    task_action_id: str
    permitted_resources: tuple[str, ...]
    local_bounds: tuple[str, ...]
    safety_constraints: tuple[str, ...]
    continuation_conditions: tuple[str, ...]
    completion_conditions: tuple[str, ...]
    escalation_conditions: tuple[str, ...]

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _bounded_identifier(self.request_id, field_name="request_id"))
        object.__setattr__(
            self,
            "task_action_id",
            _bounded_identifier(self.task_action_id, field_name="task_action_id"),
        )
        for field_name, maximum in (
            ("permitted_resources", _MAX_RESOURCES),
            ("local_bounds", _MAX_ENVELOPE_RULES),
            ("safety_constraints", _MAX_ENVELOPE_RULES),
            ("continuation_conditions", _MAX_ENVELOPE_RULES),
            ("completion_conditions", _MAX_ENVELOPE_RULES),
            ("escalation_conditions", _MAX_ENVELOPE_RULES),
        ):
            object.__setattr__(
                self,
                field_name,
                _bounded_unique_strings(
                    getattr(self, field_name),
                    field_name=field_name.replace("_", " "),
                    maximum_items=maximum,
                ),
            )
        if not self.permitted_resources:
            raise ValueError("an action-envelope request requires at least one permitted resource")
        if not self.completion_conditions:
            raise ValueError("an action-envelope request requires a completion condition")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe request snapshot."""
        return {
            "request_id": self.request_id,
            "task_action_id": self.task_action_id,
            "permitted_resources": list(self.permitted_resources),
            "local_bounds": list(self.local_bounds),
            "safety_constraints": list(self.safety_constraints),
            "continuation_conditions": list(self.continuation_conditions),
            "completion_conditions": list(self.completion_conditions),
            "escalation_conditions": list(self.escalation_conditions),
        }


@dataclass(frozen=True, slots=True)
class PrimitiveApplicationV1:
    """One concrete operation produced only after Navigation selects a primitive."""

    application_id: str
    primitive_id: str
    primitive_kind: PrimitiveKindV1
    cycle_id: int
    source_wnm_id: str
    transformed_working_relations: tuple[str, ...]
    expected_relations: tuple[str, ...]
    observation_condition: str
    task_action: TaskActionV1
    envelope_request: ActionEnvelopeRequestV1 | None

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "application_id",
            _bounded_identifier(self.application_id, field_name="application_id"),
        )
        object.__setattr__(self, "primitive_id", _bounded_identifier(self.primitive_id, field_name="primitive_id"))
        if not isinstance(self.primitive_kind, PrimitiveKindV1):
            raise TypeError("primitive_kind must be a PrimitiveKindV1")
        cycle = _positive_int(self.cycle_id, field_name="cycle_id")
        object.__setattr__(
            self,
            "source_wnm_id",
            _bounded_identifier(self.source_wnm_id, field_name="source_wnm_id"),
        )
        object.__setattr__(
            self,
            "transformed_working_relations",
            _bounded_unique_strings(
                self.transformed_working_relations,
                field_name="transformed working relation",
                maximum_items=_MAX_RELATIONS,
            ),
        )
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
            raise ValueError("a focal primitive application requires expected relations")
        object.__setattr__(
            self,
            "observation_condition",
            _bounded_identifier(self.observation_condition, field_name="observation_condition"),
        )
        if not isinstance(self.task_action, TaskActionV1):
            raise TypeError("task_action must be a TaskActionV1")
        if self.task_action.action_number != cycle:
            raise ValueError("task action number must equal the primitive application cycle")
        if self.task_action.source_application_id != self.application_id:
            raise ValueError("task action must reference the originating application")
        if self.envelope_request is not None:
            if not isinstance(self.envelope_request, ActionEnvelopeRequestV1):
                raise TypeError("envelope_request must be ActionEnvelopeRequestV1 or None")
            if self.envelope_request.task_action_id != self.task_action.task_action_id:
                raise ValueError("envelope request must reference the application's task action")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe application snapshot."""
        return {
            "application_id": self.application_id,
            "primitive_id": self.primitive_id,
            "primitive_kind": self.primitive_kind.value,
            "cycle_id": self.cycle_id,
            "source_wnm_id": self.source_wnm_id,
            "transformed_working_relations": list(self.transformed_working_relations),
            "expected_relations": list(self.expected_relations),
            "observation_condition": self.observation_condition,
            "task_action": self.task_action.as_dict(),
            "envelope_request": self.envelope_request.as_dict() if self.envelope_request is not None else None,
        }


class PrimitiveRuntimeV1(Protocol):
    """Structural contract consumed by the generic Navigation runtime."""

    primitive_id: str

    def evaluate_applicability(
        self,
        wnm: WorkingNavMapStateV1,
        *,
        cycle_id: int,
    ) -> PrimitiveApplicabilityV1:
        """Return one read-only applicability record."""

    def apply(
        self,
        wnm: WorkingNavMapStateV1,
        applicability: PrimitiveApplicabilityV1,
        *,
        cycle_id: int,
    ) -> PrimitiveApplicationV1:
        """Return one selected focal application."""


class StandUpIPV1:
    """Minimal developmentally supplied righting primitive used for Gate A.

    The hard newborn environment ignores task progress during its initial birth
    setup and requires repeated StandUp commands once struggle begins.  A bound
    of eight focal applications therefore permits honest retries without reading
    hidden stage or outcome fields.  Later body evidence, not this counter,
    determines whether standing actually occurred.
    """

    primitive_id = "ip:stand_up"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, *, maximum_applications: int = 8) -> None:
        self._maximum_applications = _positive_int(maximum_applications, field_name="maximum_applications")
        self._application_count = 0

    @property
    def application_count(self) -> int:
        """Return how many times Navigation has applied this primitive."""
        return self._application_count

    @property
    def maximum_applications(self) -> int:
        """Return the bounded retry/application limit."""
        return self._maximum_applications

    def evaluate_applicability(
        self,
        wnm: WorkingNavMapStateV1,
        *,
        cycle_id: int,
    ) -> PrimitiveApplicabilityV1:
        """Evaluate the StandUp configuration using only WNM relations."""
        if not isinstance(wnm, WorkingNavMapStateV1):
            raise TypeError("wnm must be a WorkingNavMapStateV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        relations = frozenset(wnm.working_relations) if isinstance(wnm.primary_source_state, NavMapStateV1) else frozenset()
        fallen = "posture:fallen" in relations
        inadequate = "support:inadequate" in relations
        retry_available = self._application_count < self._maximum_applications

        vetoes: list[str] = []
        if not retry_available:
            vetoes.append("bounded_application_limit_reached")
        eligible = fallen and inadequate and not vetoes
        reasons: list[str] = []
        if fallen:
            reasons.append("wnm_contains_current_fallen_relation")
        if inadequate:
            reasons.append("wnm_contains_current_inadequate_support_relation")
        if not fallen:
            reasons.append("fallen_relation_missing")
        if not inadequate:
            reasons.append("inadequate_support_relation_missing")

        return PrimitiveApplicabilityV1(
            primitive_id=self.primitive_id,
            primitive_kind=self.primitive_kind,
            cycle_id=cycle,
            source_wnm_id=wnm.working_id,
            eligible=eligible,
            safety_rank=100 if fallen and inadequate else 0,
            fit_rank=100 if fallen and inadequate else 0,
            drive_rank=0,
            persistence_rank=10 if self._application_count > 0 else 0,
            learned_success_rank=0,
            vetoes=tuple(vetoes),
            reasons=tuple(reasons),
            stable_tie_key=self.primitive_id,
        )

    def apply(
        self,
        wnm: WorkingNavMapStateV1,
        applicability: PrimitiveApplicabilityV1,
        *,
        cycle_id: int,
    ) -> PrimitiveApplicationV1:
        """Organize recovery toward upright and instantiate one task action."""
        if not isinstance(wnm, WorkingNavMapStateV1):
            raise TypeError("wnm must be a WorkingNavMapStateV1")
        if not isinstance(applicability, PrimitiveApplicabilityV1):
            raise TypeError("applicability must be a PrimitiveApplicabilityV1")
        cycle = _positive_int(cycle_id, field_name="cycle_id")
        if applicability.primitive_id != self.primitive_id:
            raise ValueError("StandUp can apply only its own applicability record")
        if applicability.cycle_id != cycle or applicability.source_wnm_id != wnm.working_id:
            raise ValueError("applicability record does not belong to this WNM/cycle")
        if not applicability.eligible:
            raise ValueError("an ineligible primitive cannot be applied")

        application_id = f"application:stand_up:{cycle}"
        task_action = TaskActionV1(
            task_action_id=f"task_action:stand_up:{cycle}",
            action_number=cycle,
            kind=TaskActionKindV1.STAND_UP,
            source_application_id=application_id,
            action_relevant_relations=(
                "target_posture:upright",
                "target_support:stable",
            ),
        )
        envelope_request = ActionEnvelopeRequestV1(
            request_id=f"envelope_request:stand_up:{cycle}",
            task_action_id=task_action.task_action_id,
            permitted_resources=("whole_body_posture", "balance_support"),
            local_bounds=("righting_recovery_only", "no_locomotor_route_change"),
            safety_constraints=("stop_on_current_support_contradiction",),
            continuation_conditions=("current_posture_remains_fallen",),
            completion_conditions=("posture:standing", "support:stable"),
            escalation_conditions=("bounded_attempt_window_exhausted", "support_evidence_missing"),
        )
        self._application_count += 1
        return PrimitiveApplicationV1(
            application_id=application_id,
            primitive_id=self.primitive_id,
            primitive_kind=self.primitive_kind,
            cycle_id=cycle,
            source_wnm_id=wnm.working_id,
            transformed_working_relations=(
                "operation:recover_toward_upright",
                "target_posture:upright",
                "target_support:stable",
            ),
            expected_relations=("posture:standing", "support:stable"),
            observation_condition="next_current_body_support_evidence",
            task_action=task_action,
            envelope_request=envelope_request,
        )


def create_gate_a_primitives_v1() -> tuple[PrimitiveRuntimeV1, ...]:
    """Return the explicit minimal developmental primitive repertoire for Gate A."""
    return (StandUpIPV1(),)
