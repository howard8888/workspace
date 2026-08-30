#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Protected current BodyMap state and POSTURE-SUPPORT candidate for Phase 1C.

Purpose
-------
The body-sensory circuit owns the current POSTURE-SUPPORT NavMap state.  This
module maintains a separate egocentric BodyMap state derived from that current
body evidence.  When SELF is currently fallen with inadequate support, BodyMap
publishes one bounded POSTURE-SUPPORT map-state candidate for future Attention.

Authority boundary
------------------
BodyMap has current sensorimotor/body authority only.  Its candidate is an
Attention input, not an Attention selection, WNM, primitive recommendation, PNM,
or task action.  BodyMap itself never becomes WNM and cannot invent ``STAND_UP``
or any other cognitive task in Phase 1C.
"""

from __future__ import annotations

from dataclasses import dataclass

from nca8_maps import (
    DurableNavMapRefV1,
    Nca8ContactStateV1,
    Nca8PostureStateV1,
    Nca8SupportStateV1,
    NavMapStateV1,
)

# Small validation helpers intentionally remain local so this module stays
# comprehensible without a generic state-management framework.
# pylint: disable=duplicate-code

__version__ = "0.1.0"
__all__ = [
    "BodyMapStateV1",
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

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe candidate description."""
        return {
            "candidate_id": self.candidate_id,
            "source_map_state": self.source_map_state.as_dict(),
            "published_cycle": self.published_cycle,
            "reason": self.reason,
            "authority": self.authority,
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


class Nca8BodyRuntimeV1:
    """Own current BodyMap state and the single bounded candidate slot."""

    def __init__(self) -> None:
        self._current_state: BodyMapStateV1 | None = None
        self._posture_support_candidate: PostureSupportCandidateV1 | None = None
        self._last_update: Nca8BodyUpdateV1 | None = None

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
