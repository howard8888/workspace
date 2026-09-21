#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Protected BodyMap state and task-to-body action handoff for NCA8.

Purpose
-------
The body-sensory circuit owns the current POSTURE-SUPPORT NavMap state. This
module maintains a separate egocentric BodyMap state derived from that evidence,
publishes one bounded POSTURE-SUPPORT candidate when focal escalation is needed,
and maps an already selected task action into a body-relative target, protected
action envelope, and lower-action request.

Authority boundary
------------------
BodyMap owns current body/peripersonal state, protected safety, and task-to-body
mapping. Its candidate is an Attention input, not an Attention selection. It may
authorize or reject a task selected by Navigation, but it never becomes WNM and
never invents ``STAND_UP`` or any other cognitive task on its own.

P18-H3 adds an opt-in local motor-target helper in nca8_body_targets.py. Its
current sensor basis is separate from the existing coarse A0 state. Configuring
it does not enable motor execution or change the A0 authorization path.
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from enum import Enum

from cca8_motor_contracts import MotorStreamRefV1
from nca8_body_targets import BodyAxisCapabilityV1, BodyTargetMapperV1

from nca8_maps import (
    DurableNavMapRefV1,
    Nca8ContactStateV1,
    Nca8PostureStateV1,
    Nca8SupportStateV1,
    NavMapStateV1,
)

from nca8_primitives import (
    ActionEnvelopeRequestV1,
    PrimitiveApplicationV1,
    TaskActionKindV1,
    TaskActionV1,
)

# Small validation helpers intentionally remain local so this module stays
# comprehensible without a generic state-management framework.
# pylint: disable=duplicate-code

__version__ = "0.4.2"
__all__ = [
    "AuthorizedActionEnvelopeV1",
    "BodyActionHandoffV1",
    "BodyMapStateV1",
    "BodyTaskTargetV1",
    "EnvelopeStatusV1",
    "LowerActionRequestV1",
    "Nca8BodyRuntimeV1",
    "Nca8BodyUpdateV1",
    "PostureSupportCandidateV1",
    "__version__",
]

_BODY_STATE_ID = "bodymap:self_support:current"
_POSTURE_SUPPORT_CANDIDATE_ID = "attention_candidate:posture_support"


def _positive_int(value: int, *, field_name: str) -> int:
    """Return one positive non-Boolean integer."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")
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


@dataclass(frozen=True, slots=True)
class BodyMapStateV1:
    """Current egocentric body/support state kept separate from cortical maps.

    Repeated equivalent evidence refreshes this one stable BodyMap slot.  A
    posture change replaces its transient content without modifying the durable
    source NavMap revision.
    """

    state_id: str
    source_map_ref: DurableNavMapRefV1
    source_map_state_id: str
    source_owner_circuit: str
    posture: Nca8PostureStateV1
    support: Nca8SupportStateV1
    contact: Nca8ContactStateV1
    evidence_current: bool
    sampled_event_cycle: int
    applied_cycle: int
    last_supported_cycle: int | None
    update_count: int
    equivalent_refresh_count: int
    configuration_change_count: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "state_id", _bounded_identifier(self.state_id, field_name="state_id"))
        if not isinstance(self.source_map_ref, DurableNavMapRefV1):
            raise TypeError("source_map_ref must be a DurableNavMapRefV1")
        object.__setattr__(
            self,
            "source_map_state_id",
            _bounded_identifier(self.source_map_state_id, field_name="source_map_state_id"),
        )
        object.__setattr__(
            self,
            "source_owner_circuit",
            _bounded_identifier(self.source_owner_circuit, field_name="source_owner_circuit"),
        )
        if not isinstance(self.posture, Nca8PostureStateV1):
            raise TypeError("posture must be an Nca8PostureStateV1")
        if not isinstance(self.support, Nca8SupportStateV1):
            raise TypeError("support must be an Nca8SupportStateV1")
        if not isinstance(self.contact, Nca8ContactStateV1):
            raise TypeError("contact must be an Nca8ContactStateV1")
        if not isinstance(self.evidence_current, bool):
            raise TypeError("evidence_current must be Boolean")
        sampled = _positive_int(self.sampled_event_cycle, field_name="sampled_event_cycle")
        applied = _positive_int(self.applied_cycle, field_name="applied_cycle")
        if applied < sampled:
            raise ValueError("applied_cycle cannot precede sampled_event_cycle")
        if self.last_supported_cycle is not None:
            supported = _positive_int(self.last_supported_cycle, field_name="last_supported_cycle")
            if supported > applied:
                raise ValueError("last_supported_cycle cannot follow applied_cycle")
        if self.evidence_current and self.last_supported_cycle != applied:
            raise ValueError("current BodyMap evidence must update last_supported_cycle")

        update_count = _positive_int(self.update_count, field_name="update_count")
        for field_name in ("equivalent_refresh_count", "configuration_change_count"):
            value = getattr(self, field_name)
            if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                raise ValueError(f"{field_name} must be a non-negative integer")
        if self.equivalent_refresh_count + self.configuration_change_count > update_count - 1:
            raise ValueError("refresh/change counts cannot exceed prior BodyMap updates")

    @property
    def authority(self) -> str:
        """Return the fixed architectural authority of this state."""
        return "protected_current_body_state"

    def semantic_key(self) -> tuple[object, ...]:
        """Return timing-independent body content used to detect refreshes."""
        return (
            self.source_map_ref,
            self.source_map_state_id,
            self.source_owner_circuit,
            self.posture,
            self.support,
            self.contact,
            self.evidence_current,
        )

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe BodyMap snapshot."""
        return {
            "state_id": self.state_id,
            "source_map_ref": self.source_map_ref.as_dict(),
            "source_map_state_id": self.source_map_state_id,
            "source_owner_circuit": self.source_owner_circuit,
            "posture": self.posture.value,
            "support": self.support.value,
            "contact": self.contact.value,
            "evidence_current": self.evidence_current,
            "sampled_event_cycle": self.sampled_event_cycle,
            "applied_cycle": self.applied_cycle,
            "last_supported_cycle": self.last_supported_cycle,
            "update_count": self.update_count,
            "equivalent_refresh_count": self.equivalent_refresh_count,
            "configuration_change_count": self.configuration_change_count,
            "authority": self.authority,
            "is_wnm": False,
        }


@dataclass(frozen=True, slots=True)
class PostureSupportCandidateV1:
    """One bounded body-state map candidate published for future Attention.

    The candidate preserves the exact current source map state.  It does not
    contain a primitive, task action, priority score, or selection result.
    """

    candidate_id: str
    source_map_state: NavMapStateV1
    published_cycle: int
    reason: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self,
            "candidate_id",
            _bounded_identifier(self.candidate_id, field_name="candidate_id"),
        )
        if not isinstance(self.source_map_state, NavMapStateV1):
            raise TypeError("source_map_state must be a NavMapStateV1")
        cycle = _positive_int(self.published_cycle, field_name="published_cycle")
        if self.source_map_state.applied_cycle != cycle:
            raise ValueError("candidate must be published from a state applied in the same cycle")
        if self.source_map_state.posture is not Nca8PostureStateV1.FALLEN:
            raise ValueError("POSTURE-SUPPORT candidate requires current fallen posture")
        if self.source_map_state.support is not Nca8SupportStateV1.INADEQUATE:
            raise ValueError("POSTURE-SUPPORT candidate requires inadequate support")
        if not self.source_map_state.evidence_current:
            raise ValueError("POSTURE-SUPPORT candidate requires current body evidence")
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))

    @property
    def authority(self) -> str:
        """Return the fixed nonexecutive status of this candidate."""
        return "attention_candidate_only"

    @property
    def protected_safety_rank(self) -> int:
        """Return the visible protected-body urgency component for Attention."""
        return 100

    @property
    def new_task_need_rank(self) -> int:
        """Return the visible need for a new focal body-support task."""
        return 100

    @property
    def prediction_or_envelope_failure_rank(self) -> int:
        """Return the current failure-escalation component; none in the first candidate."""
        return 0

    @property
    def novelty_or_ambiguity_rank(self) -> int:
        """Return the current novelty/ambiguity component; none for recognized fallen posture."""
        return 0

    @property
    def current_task_persistence_rank(self) -> int:
        """Return the current task-persistence component; Gate A starts a new task."""
        return 0

    @property
    def activation_rank(self) -> int:
        """Return bounded source activation as an inspectable Attention component."""
        return max(0, min(100, int(round(self.source_map_state.activation * 100.0))))

    @property
    def stable_tie_key(self) -> str:
        """Return the deterministic candidate tie key."""
        return self.candidate_id

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe candidate description."""
        return {
            "candidate_id": self.candidate_id,
            "source_map_state": self.source_map_state.as_dict(),
            "published_cycle": self.published_cycle,
            "reason": self.reason,
            "authority": self.authority,
            "protected_safety_rank": self.protected_safety_rank,
            "new_task_need_rank": self.new_task_need_rank,
            "prediction_or_envelope_failure_rank": self.prediction_or_envelope_failure_rank,
            "novelty_or_ambiguity_rank": self.novelty_or_ambiguity_rank,
            "current_task_persistence_rank": self.current_task_persistence_rank,
            "activation_rank": self.activation_rank,
            "stable_tie_key": self.stable_tie_key,
            "attention_selected": False,
            "is_wnm": False,
            "primitive_id": None,
            "task_action": None,
        }


@dataclass(frozen=True, slots=True)
class Nca8BodyUpdateV1:
    """One complete BodyMap update and optional candidate publication."""

    body_state: BodyMapStateV1
    posture_support_candidate: PostureSupportCandidateV1 | None
    body_update_kind: str
    candidate_event: str

    def __post_init__(self) -> None:
        if not isinstance(self.body_state, BodyMapStateV1):
            raise TypeError("body_state must be a BodyMapStateV1")
        if self.posture_support_candidate is not None:
            if not isinstance(self.posture_support_candidate, PostureSupportCandidateV1):
                raise TypeError("posture_support_candidate must be PostureSupportCandidateV1 or None")
            if self.posture_support_candidate.published_cycle != self.body_state.applied_cycle:
                raise ValueError("candidate and BodyMap state must belong to the same applied cycle")
        if self.body_update_kind not in {"created", "refreshed", "changed"}:
            raise ValueError("body_update_kind must be created, refreshed, or changed")
        if self.candidate_event not in {"published", "refreshed", "cleared", "none"}:
            raise ValueError("candidate_event has an unsupported value")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic diagnostic representation."""
        return {
            "body_state": self.body_state.as_dict(),
            "posture_support_candidate": (
                self.posture_support_candidate.as_dict() if self.posture_support_candidate is not None else None
            ),
            "body_update_kind": self.body_update_kind,
            "candidate_event": self.candidate_event,
        }


class EnvelopeStatusV1(str, Enum):
    """Lifecycle of one BodyMap-authorized task envelope."""

    AUTHORIZED = "authorized"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


@dataclass(frozen=True, slots=True)
class BodyTaskTargetV1:
    """One body-relative target derived from a Navigation-authorized task action."""

    target_id: str
    task_action_id: str
    source_application_id: str
    created_cycle: int
    body_frame: str
    target_relations: tuple[str, ...]

    def __post_init__(self) -> None:
        for field_name in ("target_id", "task_action_id", "source_application_id", "body_frame"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        _positive_int(self.created_cycle, field_name="created_cycle")
        if not self.target_relations:
            raise ValueError("BodyMap task target requires target_relations")
        if len(set(self.target_relations)) != len(self.target_relations):
            raise ValueError("BodyMap task target relations must be unique")
        for relation in self.target_relations:
            _bounded_identifier(relation, field_name="target relation")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe task-target snapshot."""
        return {
            "target_id": self.target_id,
            "task_action_id": self.task_action_id,
            "source_application_id": self.source_application_id,
            "created_cycle": self.created_cycle,
            "body_frame": self.body_frame,
            "target_relations": list(self.target_relations),
        }


@dataclass(frozen=True, slots=True)
class AuthorizedActionEnvelopeV1:
    """BodyMap authorization for bounded lower execution of one selected task."""

    envelope_id: str
    task_action_id: str
    source_application_id: str
    authorized_cycle: int
    expires_after_cycle: int
    permitted_resources: tuple[str, ...]
    local_bounds: tuple[str, ...]
    safety_constraints: tuple[str, ...]
    continuation_conditions: tuple[str, ...]
    completion_conditions: tuple[str, ...]
    escalation_conditions: tuple[str, ...]
    status: EnvelopeStatusV1
    status_reason: str

    def __post_init__(self) -> None:
        for field_name in ("envelope_id", "task_action_id", "source_application_id", "status_reason"):
            object.__setattr__(
                self,
                field_name,
                _bounded_identifier(getattr(self, field_name), field_name=field_name),
            )
        authorized = _positive_int(self.authorized_cycle, field_name="authorized_cycle")
        expiry = _positive_int(self.expires_after_cycle, field_name="expires_after_cycle")
        if expiry < authorized:
            raise ValueError("envelope expiry cannot precede authorization")
        for field_name in (
            "permitted_resources",
            "local_bounds",
            "safety_constraints",
            "continuation_conditions",
            "completion_conditions",
            "escalation_conditions",
        ):
            values = getattr(self, field_name)
            if len(set(values)) != len(values):
                raise ValueError(f"{field_name} must contain unique values")
            for item in values:
                _bounded_identifier(item, field_name=field_name.replace("_", " "))
        if not isinstance(self.status, EnvelopeStatusV1):
            raise TypeError("status must be an EnvelopeStatusV1")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe action-envelope snapshot."""
        return {
            "envelope_id": self.envelope_id,
            "task_action_id": self.task_action_id,
            "source_application_id": self.source_application_id,
            "authorized_cycle": self.authorized_cycle,
            "expires_after_cycle": self.expires_after_cycle,
            "permitted_resources": list(self.permitted_resources),
            "local_bounds": list(self.local_bounds),
            "safety_constraints": list(self.safety_constraints),
            "continuation_conditions": list(self.continuation_conditions),
            "completion_conditions": list(self.completion_conditions),
            "escalation_conditions": list(self.escalation_conditions),
            "status": self.status.value,
            "status_reason": self.status_reason,
            "may_create_new_task": False,
        }


@dataclass(frozen=True, slots=True)
class LowerActionRequestV1:
    """Minimal body-relative request passed toward the lower physical boundary."""

    request_id: str
    task_action: TaskActionV1
    target_id: str
    envelope_id: str
    created_cycle: int

    def __post_init__(self) -> None:
        object.__setattr__(self, "request_id", _bounded_identifier(self.request_id, field_name="request_id"))
        if not isinstance(self.task_action, TaskActionV1):
            raise TypeError("task_action must be a TaskActionV1")
        object.__setattr__(self, "target_id", _bounded_identifier(self.target_id, field_name="target_id"))
        object.__setattr__(self, "envelope_id", _bounded_identifier(self.envelope_id, field_name="envelope_id"))
        cycle = _positive_int(self.created_cycle, field_name="created_cycle")
        if self.task_action.action_number != cycle:
            raise ValueError("lower-action request cycle must match TaskAction_n")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe lower-action request."""
        return {
            "request_id": self.request_id,
            "task_action": self.task_action.as_dict(),
            "target_id": self.target_id,
            "envelope_id": self.envelope_id,
            "created_cycle": self.created_cycle,
            "detailed_movement_delegated": True,
        }


@dataclass(frozen=True, slots=True)
class BodyActionHandoffV1:
    """Complete BodyMap authorization result for one selected application."""

    handoff_id: str
    cycle_id: int
    authorized: bool
    reason: str
    task_target: BodyTaskTargetV1 | None
    envelope: AuthorizedActionEnvelopeV1 | None
    lower_request: LowerActionRequestV1 | None
    pnm_id: str

    def __post_init__(self) -> None:
        object.__setattr__(self, "handoff_id", _bounded_identifier(self.handoff_id, field_name="handoff_id"))
        _positive_int(self.cycle_id, field_name="cycle_id")
        if not isinstance(self.authorized, bool):
            raise TypeError("authorized must be Boolean")
        object.__setattr__(self, "reason", _bounded_identifier(self.reason, field_name="reason"))
        object.__setattr__(self, "pnm_id", _bounded_identifier(self.pnm_id, field_name="pnm_id"))
        components = (self.task_target, self.envelope, self.lower_request)
        if self.authorized and any(component is None for component in components):
            raise ValueError("authorized BodyMap handoff requires target, envelope, and lower request")
        if not self.authorized and any(component is not None for component in components):
            raise ValueError("rejected BodyMap handoff must not expose executable components")

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe BodyMap handoff."""
        return {
            "handoff_id": self.handoff_id,
            "cycle_id": self.cycle_id,
            "authorized": self.authorized,
            "reason": self.reason,
            "task_target": self.task_target.as_dict() if self.task_target is not None else None,
            "envelope": self.envelope.as_dict() if self.envelope is not None else None,
            "lower_request": self.lower_request.as_dict() if self.lower_request is not None else None,
            "pnm_id": self.pnm_id,
        }


class Nca8BodyRuntimeV1:
    """Own current BodyMap state, candidate publication, and task-to-body handoff."""

    def __init__(self, *, action_handoff_enabled: bool = True) -> None:
        if not isinstance(action_handoff_enabled, bool):
            raise TypeError("action_handoff_enabled must be Boolean")
        self._action_handoff_enabled = action_handoff_enabled
        self._current_state: BodyMapStateV1 | None = None
        self._posture_support_candidate: PostureSupportCandidateV1 | None = None
        self._last_update: Nca8BodyUpdateV1 | None = None
        self._current_task_target: BodyTaskTargetV1 | None = None
        self._current_envelope: AuthorizedActionEnvelopeV1 | None = None
        self._current_lower_request: LowerActionRequestV1 | None = None
        self._last_handoff: BodyActionHandoffV1 | None = None
        self._motor_targets: BodyTargetMapperV1 | None = None

    @property
    def motor_targets(self) -> BodyTargetMapperV1 | None:
        """Return the explicitly configured H3 local mapping helper, or None.

        This is part of the same BodyMap owner, not a second cortical source.
        Existing A0 calls never configure or consume it. The helper produces
        proposed/reserved body targets only; H4 adds their motor execution.
        """
        return self._motor_targets

    def configure_motor_targets(
        self, stream: MotorStreamRefV1, capabilities: tuple[BodyAxisCapabilityV1, ...], *,
        tick_seconds: float = 0.05, maximum_feedback_age: int = 2, orientation_mapping_sign: int = 1, visual_preview_enabled: bool = False,
    ) -> BodyTargetMapperV1:
        """Configure one H3 body stream using explicitly supplied capabilities.

        The caller admits canonical MotorFeedbackV1 readings to the returned
        helper. No environment or private body state is accessed here. The
        existing BodyMap ablation also disables target formation. Reconfiguration
        is rejected rather than silently dropping resource reservations; a reset
        constructs a fresh owning BodyMap with a fresh stream generation. No A0
        fields, action envelope, handoff, current WNM or learner are modified.
        The optional -1 orientation mapping sign is an explicitly selected H6-B
        calibration-fault control; +1 preserves the normal body transformation.
        visual_preview_enabled admits a separate non-actuating horizontal-pose
        field; it does not add a live target family or change existing targets.
        """
        if self._motor_targets is not None:
            raise ValueError("motor targets already configured; reset the owning BodyMap for a new stream")
        mapper = BodyTargetMapperV1(
            stream, capabilities, tick_seconds=tick_seconds,
            maximum_feedback_age=maximum_feedback_age, enabled=self._action_handoff_enabled,
            orientation_mapping_sign=orientation_mapping_sign, visual_preview_enabled=visual_preview_enabled,
        )
        self._motor_targets = mapper
        return mapper

    @property
    def current_state(self) -> BodyMapStateV1 | None:
        """Return the immutable current BodyMap state."""
        return self._current_state

    @property
    def posture_support_candidate(self) -> PostureSupportCandidateV1 | None:
        """Return the one current POSTURE-SUPPORT candidate, when published."""
        return self._posture_support_candidate

    @property
    def last_update(self) -> Nca8BodyUpdateV1 | None:
        """Return the most recent immutable BodyMap update."""
        return self._last_update

    @property
    def action_handoff_enabled(self) -> bool:
        """Return whether BodyMap task-to-body handoff is enabled for ablation."""
        return self._action_handoff_enabled

    @property
    def current_task_target(self) -> BodyTaskTargetV1 | None:
        """Return the current body-relative task target, when authorized."""
        return self._current_task_target

    @property
    def current_envelope(self) -> AuthorizedActionEnvelopeV1 | None:
        """Return the current bounded action envelope, when present."""
        return self._current_envelope

    @property
    def current_lower_request(self) -> LowerActionRequestV1 | None:
        """Return the latest lower-action request authorized by BodyMap."""
        return self._current_lower_request

    @property
    def last_handoff(self) -> BodyActionHandoffV1 | None:
        """Return the most recent BodyMap task authorization result."""
        return self._last_handoff

    def revoke_action_permission(self, envelope_id: str, *, reason: str) -> AuthorizedActionEnvelopeV1:
        """Revoke the named current permission without rewriting action history.

        This is the narrow P16-1R-B cancellation/protected-stop seam. It does not
        select another task or change current body evidence. CANCELLED describes
        permission, not proof that a prior physical action did not occur. An
        unknown/returned world attempt keeps its separate execution disposition.
        Previously returned handoff/commitment snapshots remain immutable.
        """
        target = _bounded_identifier(envelope_id, field_name="envelope_id")
        why = _bounded_identifier(reason, field_name="reason")
        envelope = self._current_envelope
        if envelope is None or envelope.envelope_id != target:
            raise ValueError("cannot revoke a different or missing action envelope")
        if envelope.status is EnvelopeStatusV1.AUTHORIZED:
            envelope = replace(envelope, status=EnvelopeStatusV1.CANCELLED, status_reason=why)
            self._current_envelope = envelope
        self._current_lower_request = None
        self._current_task_target = None
        return envelope

    def update_from_map_state(self, map_state: NavMapStateV1) -> Nca8BodyUpdateV1:
        """Update current body state and publish/clear the bounded candidate.

        This operation copies current posture/support/contact relations into the
        protected BodyMap state.  It does not select the candidate, form a WNM,
        or choose an IP/LP.
        """
        if not isinstance(map_state, NavMapStateV1):
            raise TypeError("map_state must be a NavMapStateV1")
        existing = self._current_state
        last_supported_cycle = map_state.applied_cycle if map_state.evidence_current else None
        if existing is not None and not map_state.evidence_current:
            last_supported_cycle = existing.last_supported_cycle

        candidate_state = BodyMapStateV1(
            state_id=_BODY_STATE_ID,
            source_map_ref=map_state.source_map_ref,
            source_map_state_id=map_state.state_id,
            source_owner_circuit=map_state.owner_circuit,
            posture=map_state.posture,
            support=map_state.support,
            contact=map_state.contact,
            evidence_current=map_state.evidence_current,
            sampled_event_cycle=map_state.sampled_event_cycle,
            applied_cycle=map_state.applied_cycle,
            last_supported_cycle=last_supported_cycle,
            update_count=1,
            equivalent_refresh_count=0,
            configuration_change_count=0,
        )
        if existing is None:
            body_update_kind = "created"
        else:
            same_content = candidate_state.semantic_key() == existing.semantic_key()
            body_update_kind = "refreshed" if same_content else "changed"
            candidate_state = BodyMapStateV1(
                state_id=existing.state_id,
                source_map_ref=candidate_state.source_map_ref,
                source_map_state_id=candidate_state.source_map_state_id,
                source_owner_circuit=candidate_state.source_owner_circuit,
                posture=candidate_state.posture,
                support=candidate_state.support,
                contact=candidate_state.contact,
                evidence_current=candidate_state.evidence_current,
                sampled_event_cycle=candidate_state.sampled_event_cycle,
                applied_cycle=candidate_state.applied_cycle,
                last_supported_cycle=candidate_state.last_supported_cycle,
                update_count=existing.update_count + 1,
                equivalent_refresh_count=existing.equivalent_refresh_count + int(same_content),
                configuration_change_count=existing.configuration_change_count + int(not same_content),
            )

        previous_candidate = self._posture_support_candidate
        should_publish = (
            map_state.posture is Nca8PostureStateV1.FALLEN
            and map_state.support is Nca8SupportStateV1.INADEQUATE
            and map_state.evidence_current
        )
        if should_publish:
            next_candidate = PostureSupportCandidateV1(
                candidate_id=_POSTURE_SUPPORT_CANDIDATE_ID,
                source_map_state=map_state,
                published_cycle=map_state.applied_cycle,
                reason="current_fallen_posture_with_inadequate_support",
            )
            candidate_event = "refreshed" if previous_candidate is not None else "published"
        else:
            next_candidate = None
            candidate_event = "cleared" if previous_candidate is not None else "none"

        update = Nca8BodyUpdateV1(
            body_state=candidate_state,
            posture_support_candidate=next_candidate,
            body_update_kind=body_update_kind,
            candidate_event=candidate_event,
        )
        self._current_state = candidate_state
        self._posture_support_candidate = next_candidate
        self._last_update = update
        return update

    def reconcile_envelope_from_current_state(self) -> AuthorizedActionEnvelopeV1 | None:
        """Update the current envelope status from later current body evidence.

        This method cannot choose a new task.  It only closes or retains the
        envelope previously authorized from a Navigation-selected application.
        """
        envelope = self._current_envelope
        state = self._current_state
        if envelope is None or state is None or envelope.status is not EnvelopeStatusV1.AUTHORIZED:
            return envelope
        if not state.evidence_current:
            return envelope
        if state.posture is Nca8PostureStateV1.STANDING and state.support is Nca8SupportStateV1.STABLE:
            envelope = replace(
                envelope,
                status=EnvelopeStatusV1.COMPLETED,
                status_reason="later_body_evidence_reports_upright_stable_support",
            )
        elif state.posture is Nca8PostureStateV1.FALLEN and state.support is Nca8SupportStateV1.INADEQUATE:
            envelope = replace(
                envelope,
                status=EnvelopeStatusV1.FAILED,
                status_reason="later_body_evidence_reports_fallen_inadequate_support",
            )
        self._current_envelope = envelope
        return envelope

    def authorize_application(
        self,
        application: PrimitiveApplicationV1,
        *,
        pnm_id: str,
    ) -> BodyActionHandoffV1:
        """Map one selected task action to a protected body-relative request.

        BodyMap validates the currently represented body state and may reject
        the handoff.  It never substitutes another task or invokes a legacy
        controller when authorization is unavailable.
        """
        if not isinstance(application, PrimitiveApplicationV1):
            raise TypeError("application must be a PrimitiveApplicationV1")
        pnm_ref = _bounded_identifier(pnm_id, field_name="pnm_id")
        cycle = application.cycle_id
        state = self._current_state
        reason = "authorized_current_fallen_body_recovery"
        authorized = True
        if not self._action_handoff_enabled:
            authorized = False
            reason = "bodymap_action_handoff_ablation_disabled"
        elif state is None:
            authorized = False
            reason = "bodymap_current_state_missing"
        elif not state.evidence_current:
            authorized = False
            reason = "bodymap_current_evidence_not_supported"
        elif application.task_action.kind is not TaskActionKindV1.STAND_UP:
            authorized = False
            reason = "bodymap_gate_a_supports_only_stand_up"
        elif state.posture is not Nca8PostureStateV1.FALLEN:
            authorized = False
            reason = "bodymap_current_posture_is_not_fallen"
        elif state.support is not Nca8SupportStateV1.INADEQUATE:
            authorized = False
            reason = "bodymap_current_support_is_not_inadequate"
        elif application.envelope_request is None:
            authorized = False
            reason = "primitive_application_has_no_envelope_request"

        if not authorized:
            handoff = BodyActionHandoffV1(
                handoff_id=f"body_handoff:{cycle}",
                cycle_id=cycle,
                authorized=False,
                reason=reason,
                task_target=None,
                envelope=None,
                lower_request=None,
                pnm_id=pnm_ref,
            )
            self._last_handoff = handoff
            return handoff

        envelope_request = application.envelope_request
        if not isinstance(envelope_request, ActionEnvelopeRequestV1):  # pragma: no cover - guarded above
            raise RuntimeError("authorized application lost its action-envelope request")
        task_target = BodyTaskTargetV1(
            target_id=f"body_target:stand_up:{cycle}",
            task_action_id=application.task_action.task_action_id,
            source_application_id=application.application_id,
            created_cycle=cycle,
            body_frame="self_ground_egocentric_v1",
            target_relations=application.task_action.action_relevant_relations,
        )
        envelope = AuthorizedActionEnvelopeV1(
            envelope_id=f"authorized_envelope:stand_up:{cycle}",
            task_action_id=application.task_action.task_action_id,
            source_application_id=application.application_id,
            authorized_cycle=cycle,
            expires_after_cycle=cycle + 2,
            permitted_resources=envelope_request.permitted_resources,
            local_bounds=envelope_request.local_bounds,
            safety_constraints=envelope_request.safety_constraints,
            continuation_conditions=envelope_request.continuation_conditions,
            completion_conditions=envelope_request.completion_conditions,
            escalation_conditions=envelope_request.escalation_conditions,
            status=EnvelopeStatusV1.AUTHORIZED,
            status_reason=reason,
        )
        lower_request = LowerActionRequestV1(
            request_id=f"lower_action_request:stand_up:{cycle}",
            task_action=application.task_action,
            target_id=task_target.target_id,
            envelope_id=envelope.envelope_id,
            created_cycle=cycle,
        )
        handoff = BodyActionHandoffV1(
            handoff_id=f"body_handoff:{cycle}",
            cycle_id=cycle,
            authorized=True,
            reason=reason,
            task_target=task_target,
            envelope=envelope,
            lower_request=lower_request,
            pnm_id=pnm_ref,
        )
        self._current_task_target = task_target
        self._current_envelope = envelope
        self._current_lower_request = lower_request
        self._last_handoff = handoff
        return handoff
