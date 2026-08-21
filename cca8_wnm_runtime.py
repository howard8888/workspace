# -*- coding: utf-8 -*-
"""Single-operative WNM and bounded-ready-set runtime for CCA8 Phases 5 through 8.

Purpose
-------
Planning v13 requires the first genuine navigation among NavMaps rather than a
renderer-only focus change.  This module supplies the small authority record
needed by that experiment:

* at most one :class:`~cca8_navmap_kernel.NavMapV2` is operative;
* a bounded ready set keeps recently operative maps available for rapid return;
* zoom-in, zoom-out, lateral shift, return, and associative jump are atomic committed transitions;
* retrieved candidates may enter the bounded ready set through an explicit non-operative admission transaction;
* candidates and links never become operative merely by being addressable; and
* transition failures leave the source WNM and ready set unchanged.

The runtime is deliberately content-neutral. Phase 5 feeding code supplies
cross-scale correspondence evidence, Phase 6 terrain code supplies overlapping
route-sheet correspondence, and Phase 8 memory code supplies retrieved-map
admission or associative-jump requests. None of those domains is imported here.

Authority boundary
------------------
Operative-WNM authority determines which map substrate a map query may use.  It
does not itself select a behavioral primitive, write WorldGraph truth, store a
Column engram, mutate BodyMap, or command lower motor execution.  A revision
refresh within the same map family preserves operative status and is recorded
separately from a zoom/return transition.
"""

from __future__ import annotations

# Schema dataclasses are intentionally compact records.
# The validation helpers intentionally mirror other typed NavMap runtimes.
# pylint: disable=duplicate-code
# pylint: disable=too-few-public-methods

from dataclasses import dataclass, replace
from enum import Enum
from typing import Any, Optional

from cca8_navmap_kernel import NavMapRefV1, NavMapV2

__version__ = "0.3.0"

__all__ = [
    "WNMTransitionTypeV1",
    "WNMReadyEntryV1",
    "WNMTransitionRecordV1",
    "wnm_operative_map_v1",
    "wnm_ready_maps_v1",
    "wnm_map_by_role_v1",
    "wnm_refresh_map_v1",
    "wnm_admit_ready_map_v1",
    "wnm_commit_transition_v1",
    "wnm_return_to_ref_v1",
    "wnm_summary_v1",
    "render_wnm_lines_v1",
    "__version__",
]

_DEFAULT_READY_CAPACITY = 3
_DEFAULT_HISTORY_LIMIT = 25


class WNMTransitionTypeV1(str, Enum):
    """Committed ways the operative WNM may change in the first runtime."""

    INITIALIZE = "initialize"
    ZOOM_IN = "zoom_in"
    ZOOM_OUT = "zoom_out"
    LATERAL_SHIFT = "lateral_shift"
    RETURN = "return"
    READY_ADMISSION = "ready_admission"
    ASSOCIATIVE_JUMP = "associative_jump"


def _require_positive_int(value: int, *, field_name: str) -> None:
    """Require one positive integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ValueError(f"{field_name} must be a positive integer")


def _require_non_negative_int(value: int, *, field_name: str) -> None:
    """Require one non-negative integer without accepting bool."""
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{field_name} must be a non-negative integer")


def _require_nonempty_text(value: str, *, field_name: str) -> None:
    """Require one non-empty string."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field_name} must be a non-empty string")


def _unit_interval(value: Any, *, field_name: str) -> float:
    """Return one finite number in the inclusive unit interval."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{field_name} must be numeric")
    number = float(value)
    if not 0.0 <= number <= 1.0:
        raise ValueError(f"{field_name} must be in [0, 1]")
    return number


def _map_ref(navmap: NavMapV2) -> NavMapRefV1:
    """Return the immutable reference of one validated map."""
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    return NavMapRefV1(map_id=navmap.map_id, revision=navmap.revision)


def _same_family(left: NavMapV2, right: NavMapV2) -> bool:
    """Return whether two revisions belong to one stable map family."""
    return left.map_id == right.map_id


@dataclass(frozen=True, slots=True)
class WNMReadyEntryV1:
    """One non-authoritative map retained for bounded rapid exchange.

    ``admitted_transition_no`` records when the map entered the ready set.
    ``last_used_transition_no`` gives deterministic least-recently-used
    eviction without relying on wall-clock time or list accident.
    """

    navmap: NavMapV2
    admitted_transition_no: int
    last_used_transition_no: int
    reason: str

    def __post_init__(self) -> None:
        if not isinstance(self.navmap, NavMapV2):
            raise TypeError("navmap must be NavMapV2")
        _require_positive_int(self.admitted_transition_no, field_name="admitted_transition_no")
        _require_positive_int(self.last_used_transition_no, field_name="last_used_transition_no")
        if self.last_used_transition_no < self.admitted_transition_no:
            raise ValueError("last_used_transition_no must not precede admission")
        _require_nonempty_text(self.reason, field_name="reason")

    @property
    def map_ref(self) -> NavMapRefV1:
        """Return the exact ready-map reference."""
        return _map_ref(self.navmap)

    def as_dict(self) -> dict[str, Any]:
        """Return a JSON-safe ready-set record."""
        return {
            "map_ref": self.map_ref.as_dict(),
            "role": self.navmap.role,
            "frame_id": self.navmap.frame.frame_id,
            "admitted_transition_no": self.admitted_transition_no,
            "last_used_transition_no": self.last_used_transition_no,
            "reason": self.reason,
            "operative_authority": False,
        }


@dataclass(frozen=True, slots=True)
class WNMTransitionRecordV1:
    """One attempted or committed change of the operative map substrate."""

    transition_no: int
    observation_no: int
    controller_step: int
    transition_type: WNMTransitionTypeV1
    source_ref: Optional[NavMapRefV1]
    destination_ref: NavMapRefV1
    source_role: Optional[str]
    destination_role: str
    source_frame_id: Optional[str]
    destination_frame_id: str
    reason: str
    identity_handle: str
    correspondence_basis: str
    support: float
    correspondence_ambiguous: bool
    accepted: bool
    acceptance_result: str
    prior_wnm_disposition: str
    ready_before: tuple[NavMapRefV1, ...]
    ready_after: tuple[NavMapRefV1, ...]
    evicted_ref: Optional[NavMapRefV1]
    failure_reason: Optional[str]

    def __post_init__(self) -> None:
        _require_positive_int(self.transition_no, field_name="transition_no")
        _require_positive_int(self.observation_no, field_name="observation_no")
        _require_non_negative_int(self.controller_step, field_name="controller_step")
        if not isinstance(self.transition_type, WNMTransitionTypeV1):
            raise TypeError("transition_type must be WNMTransitionTypeV1")
        if self.source_ref is not None and not isinstance(self.source_ref, NavMapRefV1):
            raise TypeError("source_ref must be NavMapRefV1 or None")
        if not isinstance(self.destination_ref, NavMapRefV1):
            raise TypeError("destination_ref must be NavMapRefV1")
        for field_name in (
            "destination_role",
            "destination_frame_id",
            "reason",
            "identity_handle",
            "correspondence_basis",
            "acceptance_result",
            "prior_wnm_disposition",
        ):
            _require_nonempty_text(getattr(self, field_name), field_name=field_name)
        for field_name in ("source_role", "source_frame_id", "failure_reason"):
            value = getattr(self, field_name)
            if value is not None:
                _require_nonempty_text(value, field_name=field_name)
        object.__setattr__(self, "support", _unit_interval(self.support, field_name="support"))
        if not isinstance(self.correspondence_ambiguous, bool):
            raise TypeError("correspondence_ambiguous must be bool")
        if not isinstance(self.accepted, bool):
            raise TypeError("accepted must be bool")
        for ref in self.ready_before + self.ready_after:
            if not isinstance(ref, NavMapRefV1):
                raise TypeError("ready-set entries must be NavMapRefV1")
        if self.evicted_ref is not None and not isinstance(self.evicted_ref, NavMapRefV1):
            raise TypeError("evicted_ref must be NavMapRefV1 or None")
        if self.accepted and self.failure_reason is not None:
            raise ValueError("accepted transition cannot carry failure_reason")
        if not self.accepted and self.failure_reason is None:
            raise ValueError("rejected transition requires failure_reason")
        source_optional_types = {
            WNMTransitionTypeV1.INITIALIZE,
            WNMTransitionTypeV1.READY_ADMISSION,
        }
        if self.transition_type is WNMTransitionTypeV1.INITIALIZE and self.source_ref is not None:
            raise ValueError("initialize transition must not have a source_ref")
        if self.accepted and self.transition_type not in source_optional_types and self.source_ref is None:
            raise ValueError("accepted operative transition requires a source_ref")

    def as_dict(self) -> dict[str, Any]:
        """Return the complete JSON-safe transition and authority contract."""
        return {
            "schema": "wnm_transition_record_v1",
            "phase": "5-8",
            "authority": "operative_wnm_runtime",
            "one_operative_wnm": True,
            "ready_set_has_equal_authority": False,
            "candidate_or_link_grants_authority": False,
            "behavioral_selection_mutation_allowed": False,
            "worldgraph_write_allowed": False,
            "column_write_allowed": False,
            "bodymap_mutation_allowed": False,
            "transition_no": self.transition_no,
            "observation_no": self.observation_no,
            "controller_step": self.controller_step,
            "transition_type": self.transition_type.value,
            "source_ref": self.source_ref.as_dict() if self.source_ref is not None else None,
            "destination_ref": self.destination_ref.as_dict(),
            "source_role": self.source_role,
            "destination_role": self.destination_role,
            "source_frame_id": self.source_frame_id,
            "destination_frame_id": self.destination_frame_id,
            "reason": self.reason,
            "identity_handle": self.identity_handle,
            "correspondence_basis": self.correspondence_basis,
            "support": self.support,
            "correspondence_ambiguous": self.correspondence_ambiguous,
            "accepted": self.accepted,
            "acceptance_result": self.acceptance_result,
            "prior_wnm_disposition": self.prior_wnm_disposition,
            "ready_before": [ref.as_dict() for ref in self.ready_before],
            "ready_after": [ref.as_dict() for ref in self.ready_after],
            "evicted_ref": self.evicted_ref.as_dict() if self.evicted_ref is not None else None,
            "failure_reason": self.failure_reason,
        }


def _controller_step(ctx: Any) -> int:
    """Return a defensive non-negative controller-step value."""
    try:
        return max(0, int(getattr(ctx, "controller_steps", 0) or 0))
    except (TypeError, ValueError):
        return 0


def _next_transition_no(ctx: Any) -> int:
    """Advance and return the deterministic transition-attempt counter."""
    try:
        current = int(getattr(ctx, "wnm_transition_no_v1", 0) or 0)
    except (TypeError, ValueError):
        current = 0
    value = max(0, current) + 1
    ctx.wnm_transition_no_v1 = value
    return value


def _ready_capacity(ctx: Any) -> int:
    """Return the configured small positive ready-set capacity."""
    try:
        value = int(getattr(ctx, "wnm_ready_capacity_v1", _DEFAULT_READY_CAPACITY) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_READY_CAPACITY
    return value if value > 0 else _DEFAULT_READY_CAPACITY


def _history_limit(ctx: Any) -> int:
    """Return the configured positive transition-history bound."""
    try:
        value = int(getattr(ctx, "wnm_transition_history_limit_v1", _DEFAULT_HISTORY_LIMIT) or 0)
    except (TypeError, ValueError):
        value = _DEFAULT_HISTORY_LIMIT
    return value if value > 0 else _DEFAULT_HISTORY_LIMIT


def _clean_ready_entries(ctx: Any) -> list[WNMReadyEntryV1]:
    """Return only valid ready entries, de-duplicated by map family."""
    raw = getattr(ctx, "wnm_ready_set_v1", [])
    entries = [item for item in raw if isinstance(item, WNMReadyEntryV1)] if isinstance(raw, list) else []
    newest_by_family: dict[str, WNMReadyEntryV1] = {}
    for entry in entries:
        previous = newest_by_family.get(entry.navmap.map_id)
        if previous is None or entry.navmap.revision > previous.navmap.revision:
            newest_by_family[entry.navmap.map_id] = entry
        elif entry.navmap.revision == previous.navmap.revision:
            if entry.last_used_transition_no > previous.last_used_transition_no:
                newest_by_family[entry.navmap.map_id] = entry
    return sorted(
        newest_by_family.values(),
        key=lambda item: (
            item.last_used_transition_no,
            item.admitted_transition_no,
            item.navmap.map_id,
            item.navmap.revision,
        ),
    )


def _ready_refs(entries: list[WNMReadyEntryV1]) -> tuple[NavMapRefV1, ...]:
    """Return deterministic ready references in stored order."""
    return tuple(entry.map_ref for entry in entries)


def _store_transition(ctx: Any, record: WNMTransitionRecordV1) -> dict[str, Any]:
    """Store one transition attempt and bounded history on ctx."""
    row = record.as_dict()
    ctx.wnm_last_transition_v1 = record
    ctx.wnm_last_update_v1 = dict(row)
    history = getattr(ctx, "wnm_transition_history_v1", [])
    clean = [dict(item) for item in history if isinstance(item, dict)] if isinstance(history, list) else []
    clean.append(dict(row))
    ctx.wnm_transition_history_v1 = clean[-_history_limit(ctx):]
    return wnm_summary_v1(ctx)


def wnm_operative_map_v1(ctx: Any) -> Optional[NavMapV2]:
    """Return the one operative map or ``None`` during initialization/invalidity."""
    value = getattr(ctx, "wnm_operative_map_v1", None) if ctx is not None else None
    return value if isinstance(value, NavMapV2) else None


def wnm_ready_maps_v1(ctx: Any) -> tuple[NavMapV2, ...]:
    """Return current bounded ready maps without granting operative authority."""
    return tuple(entry.navmap for entry in _clean_ready_entries(ctx)) if ctx is not None else ()


def wnm_map_by_role_v1(ctx: Any, role: str, *, include_ready: bool = True) -> Optional[NavMapV2]:
    """Return an operative or ready map with one exact role.

    The function is an addressability helper only.  A map returned from the
    ready set remains non-authoritative until a transition commits it.
    """
    _require_nonempty_text(role, field_name="role")
    operative = wnm_operative_map_v1(ctx)
    if operative is not None and operative.role == role:
        return operative
    if include_ready:
        for navmap in reversed(wnm_ready_maps_v1(ctx)):
            if navmap.role == role:
                return navmap
    return None


def wnm_refresh_map_v1(
    ctx: Any,
    navmap: NavMapV2,
    *,
    observation_no: int,
    reason: str,
) -> dict[str, Any]:
    """Refresh one known map family without changing the operative-map role.

    A higher immutable revision replaces the current revision in whichever
    activation tier already owns that family.  It does not promote a candidate,
    create a zoom event, or reorder unrelated ready maps.
    """
    if ctx is None:
        return {"schema": "wnm_refresh_v1", "phase": "5-8", "status": "ctx_unavailable"}
    if not isinstance(navmap, NavMapV2):
        raise TypeError("navmap must be NavMapV2")
    _require_positive_int(observation_no, field_name="observation_no")
    _require_nonempty_text(reason, field_name="reason")

    old_ref: Optional[NavMapRefV1] = None
    location = "untracked"
    updated = False
    operative = wnm_operative_map_v1(ctx)
    if operative is not None and _same_family(operative, navmap):
        old_ref = _map_ref(operative)
        location = "operative"
        if navmap.revision > operative.revision:
            ctx.wnm_operative_map_v1 = navmap
            updated = True
    else:
        entries = _clean_ready_entries(ctx)
        refreshed: list[WNMReadyEntryV1] = []
        for entry in entries:
            if entry.navmap.map_id == navmap.map_id:
                old_ref = entry.map_ref
                location = "ready"
                if navmap.revision > entry.navmap.revision:
                    entry = replace(entry, navmap=navmap)
                    updated = True
            refreshed.append(entry)
        ctx.wnm_ready_set_v1 = refreshed

    row = {
        "schema": "wnm_refresh_v1",
        "phase": "5-8",
        "status": "updated" if updated else ("unchanged" if location != "untracked" else "untracked"),
        "location": location,
        "observation_no": observation_no,
        "reason": reason,
        "old_ref": old_ref.as_dict() if old_ref is not None else None,
        "new_ref": _map_ref(navmap).as_dict(),
        "operative_role_changed": False,
        "transition_created": False,
    }
    ctx.wnm_last_refresh_v1 = dict(row)
    return dict(row)


def _rejected_transition(
    ctx: Any,
    *,
    transition_no: int,
    observation_no: int,
    transition_type: WNMTransitionTypeV1,
    source: Optional[NavMapV2],
    destination: NavMapV2,
    reason: str,
    identity_handle: str,
    correspondence_basis: str,
    support: float,
    correspondence_ambiguous: bool,
    ready_before: list[WNMReadyEntryV1],
    failure_reason: str,
) -> dict[str, Any]:
    """Store one failed atomic transition without mutating activation tiers."""
    record = WNMTransitionRecordV1(
        transition_no=transition_no,
        observation_no=observation_no,
        controller_step=_controller_step(ctx),
        transition_type=transition_type,
        source_ref=_map_ref(source) if source is not None else None,
        destination_ref=_map_ref(destination),
        source_role=source.role if source is not None else None,
        destination_role=destination.role,
        source_frame_id=source.frame.frame_id if source is not None else None,
        destination_frame_id=destination.frame.frame_id,
        reason=reason,
        identity_handle=identity_handle,
        correspondence_basis=correspondence_basis,
        support=support,
        correspondence_ambiguous=correspondence_ambiguous,
        accepted=False,
        acceptance_result="rejected_source_remains_operative",
        prior_wnm_disposition="unchanged",
        ready_before=_ready_refs(ready_before),
        ready_after=_ready_refs(ready_before),
        evicted_ref=None,
        failure_reason=failure_reason,
    )
    return _store_transition(ctx, record)



def wnm_admit_ready_map_v1(
    ctx: Any,
    destination: NavMapV2,
    *,
    observation_no: int,
    reason: str,
    identity_handle: str,
    correspondence_basis: str,
    support: float,
    correspondence_ambiguous: bool = False,
    expected_source_ref: Optional[NavMapRefV1] = None,
) -> dict[str, Any]:
    """Admit one map to the bounded ready set without changing the operative WNM.

    This is the Phase 8 authority seam between retrieval and current cognition.
    A reinstated map remains non-authoritative after admission; it is merely
    available for a later explicit zoom, lateral shift, return, or associative
    jump. Candidate generation, payload reinstatement, and matching alone never
    call this function implicitly.

    The transaction is atomic. Ambiguous/unsupported correspondence, stale
    source assumptions, or an attempt to admit the operative map family leaves
    both activation tiers unchanged. Re-admitting the exact ready revision is
    idempotent except for deterministic recency bookkeeping.
    """
    if ctx is None:
        return {"schema": "wnm_summary_v1", "phase": "5-8", "status": "ctx_unavailable"}
    if not isinstance(destination, NavMapV2):
        raise TypeError("destination must be NavMapV2")
    _require_positive_int(observation_no, field_name="observation_no")
    _require_nonempty_text(reason, field_name="reason")
    _require_nonempty_text(identity_handle, field_name="identity_handle")
    _require_nonempty_text(correspondence_basis, field_name="correspondence_basis")
    support_value = _unit_interval(support, field_name="support")
    if not isinstance(correspondence_ambiguous, bool):
        raise TypeError("correspondence_ambiguous must be bool")
    if expected_source_ref is not None and not isinstance(expected_source_ref, NavMapRefV1):
        raise TypeError("expected_source_ref must be NavMapRefV1 or None")

    transition_no = _next_transition_no(ctx)
    source = wnm_operative_map_v1(ctx)
    ready_before = _clean_ready_entries(ctx)

    if expected_source_ref is not None:
        if source is None or _map_ref(source) != expected_source_ref:
            return _rejected_transition(
                ctx,
                transition_no=transition_no,
                observation_no=observation_no,
                transition_type=WNMTransitionTypeV1.READY_ADMISSION,
                source=source,
                destination=destination,
                reason=reason,
                identity_handle=identity_handle,
                correspondence_basis=correspondence_basis,
                support=support_value,
                correspondence_ambiguous=correspondence_ambiguous,
                ready_before=ready_before,
                failure_reason="operative_source_reference_mismatch",
            )

    if source is not None and source.map_id == destination.map_id:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=WNMTransitionTypeV1.READY_ADMISSION,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=correspondence_ambiguous,
            ready_before=ready_before,
            failure_reason="destination_family_already_operative",
        )

    if correspondence_ambiguous:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=WNMTransitionTypeV1.READY_ADMISSION,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=True,
            ready_before=ready_before,
            failure_reason="cross_map_correspondence_ambiguous",
        )

    if support_value <= 0.0:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=WNMTransitionTypeV1.READY_ADMISSION,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=False,
            ready_before=ready_before,
            failure_reason="cross_map_correspondence_unsupported",
        )

    existing = next(
        (entry for entry in ready_before if entry.navmap.map_id == destination.map_id),
        None,
    )
    if existing is not None and existing.navmap.revision > destination.revision:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=WNMTransitionTypeV1.READY_ADMISSION,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=False,
            ready_before=ready_before,
            failure_reason="newer_ready_revision_already_present",
        )

    ready_after = [entry for entry in ready_before if entry.navmap.map_id != destination.map_id]
    admitted_transition_no = (
        existing.admitted_transition_no
        if existing is not None and existing.navmap.revision == destination.revision
        else transition_no
    )
    ready_after.append(
        WNMReadyEntryV1(
            navmap=destination,
            admitted_transition_no=admitted_transition_no,
            last_used_transition_no=transition_no,
            reason=reason,
        )
    )
    ready_after.sort(
        key=lambda item: (
            item.last_used_transition_no,
            item.admitted_transition_no,
            item.navmap.map_id,
            item.navmap.revision,
        )
    )

    evicted: Optional[WNMReadyEntryV1] = None
    capacity = _ready_capacity(ctx)
    while len(ready_after) > capacity:
        removed = ready_after.pop(0)
        if evicted is None:
            evicted = removed

    ctx.wnm_ready_set_v1 = ready_after
    acceptance_result = (
        "destination_ready_membership_refreshed"
        if existing is not None and existing.navmap.revision == destination.revision
        else "destination_admitted_ready_non_authoritative"
    )
    record = WNMTransitionRecordV1(
        transition_no=transition_no,
        observation_no=observation_no,
        controller_step=_controller_step(ctx),
        transition_type=WNMTransitionTypeV1.READY_ADMISSION,
        source_ref=_map_ref(source) if source is not None else None,
        destination_ref=_map_ref(destination),
        source_role=source.role if source is not None else None,
        destination_role=destination.role,
        source_frame_id=source.frame.frame_id if source is not None else None,
        destination_frame_id=destination.frame.frame_id,
        reason=reason,
        identity_handle=identity_handle,
        correspondence_basis=correspondence_basis,
        support=support_value,
        correspondence_ambiguous=False,
        accepted=True,
        acceptance_result=acceptance_result,
        prior_wnm_disposition="unchanged",
        ready_before=_ready_refs(ready_before),
        ready_after=_ready_refs(ready_after),
        evicted_ref=evicted.map_ref if evicted is not None else None,
        failure_reason=None,
    )
    return _store_transition(ctx, record)

def wnm_commit_transition_v1(
    ctx: Any,
    destination: NavMapV2,
    *,
    transition_type: WNMTransitionTypeV1,
    observation_no: int,
    reason: str,
    identity_handle: str,
    correspondence_basis: str,
    support: float,
    correspondence_ambiguous: bool = False,
    expected_source_ref: Optional[NavMapRefV1] = None,
) -> dict[str, Any]:
    """Atomically commit one initialize/zoom/lateral/return/jump transition.

    Failed source, correspondence, or same-destination checks leave both the
    operative WNM and ready set exactly as they were.  A successful non-initial
    transition places the prior operative map into the ready set, removes the
    destination family from ready status, and evicts at most one deterministic
    least-recently-used entry when the configured bound is exceeded.
    """
    if ctx is None:
        return {"schema": "wnm_summary_v1", "phase": "5-8", "status": "ctx_unavailable"}
    if not isinstance(destination, NavMapV2):
        raise TypeError("destination must be NavMapV2")
    if not isinstance(transition_type, WNMTransitionTypeV1):
        raise TypeError("transition_type must be WNMTransitionTypeV1")
    if transition_type is WNMTransitionTypeV1.READY_ADMISSION:
        raise ValueError("use wnm_admit_ready_map_v1 for non-operative ready admission")
    _require_positive_int(observation_no, field_name="observation_no")
    _require_nonempty_text(reason, field_name="reason")
    _require_nonempty_text(identity_handle, field_name="identity_handle")
    _require_nonempty_text(correspondence_basis, field_name="correspondence_basis")
    support_value = _unit_interval(support, field_name="support")
    if not isinstance(correspondence_ambiguous, bool):
        raise TypeError("correspondence_ambiguous must be bool")
    if expected_source_ref is not None and not isinstance(expected_source_ref, NavMapRefV1):
        raise TypeError("expected_source_ref must be NavMapRefV1 or None")

    transition_no = _next_transition_no(ctx)
    source = wnm_operative_map_v1(ctx)
    ready_before = _clean_ready_entries(ctx)

    if transition_type is WNMTransitionTypeV1.INITIALIZE:
        if source is not None:
            return _rejected_transition(
                ctx,
                transition_no=transition_no,
                observation_no=observation_no,
                transition_type=transition_type,
                source=None,
                destination=destination,
                reason=reason,
                identity_handle=identity_handle,
                correspondence_basis=correspondence_basis,
                support=support_value,
                correspondence_ambiguous=correspondence_ambiguous,
                ready_before=ready_before,
                failure_reason="operative_wnm_already_initialized",
            )
    elif source is None:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=transition_type,
            source=None,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=correspondence_ambiguous,
            ready_before=ready_before,
            failure_reason="operative_source_unavailable",
        )

    if source is not None and expected_source_ref is not None and _map_ref(source) != expected_source_ref:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=transition_type,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=correspondence_ambiguous,
            ready_before=ready_before,
            failure_reason="operative_source_reference_mismatch",
        )

    if transition_type is WNMTransitionTypeV1.RETURN:
        destination_is_ready = any(entry.map_ref == _map_ref(destination) for entry in ready_before)
        if not destination_is_ready:
            return _rejected_transition(
                ctx,
                transition_no=transition_no,
                observation_no=observation_no,
                transition_type=transition_type,
                source=source,
                destination=destination,
                reason=reason,
                identity_handle=identity_handle,
                correspondence_basis=correspondence_basis,
                support=support_value,
                correspondence_ambiguous=correspondence_ambiguous,
                ready_before=ready_before,
                failure_reason="return_destination_not_in_ready_set",
            )

    if source is not None and _map_ref(source) == _map_ref(destination):
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=transition_type,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=correspondence_ambiguous,
            ready_before=ready_before,
            failure_reason="destination_already_operative",
        )

    if correspondence_ambiguous:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=transition_type,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=True,
            ready_before=ready_before,
            failure_reason="cross_map_correspondence_ambiguous",
        )

    if support_value <= 0.0:
        return _rejected_transition(
            ctx,
            transition_no=transition_no,
            observation_no=observation_no,
            transition_type=transition_type,
            source=source,
            destination=destination,
            reason=reason,
            identity_handle=identity_handle,
            correspondence_basis=correspondence_basis,
            support=support_value,
            correspondence_ambiguous=correspondence_ambiguous,
            ready_before=ready_before,
            failure_reason="cross_map_correspondence_unsupported",
        )

    ready_after = [entry for entry in ready_before if entry.navmap.map_id != destination.map_id]
    if source is not None:
        ready_after = [entry for entry in ready_after if entry.navmap.map_id != source.map_id]
        ready_after.append(
            WNMReadyEntryV1(
                navmap=source,
                admitted_transition_no=transition_no,
                last_used_transition_no=transition_no,
                reason=f"prior_operative_after_{transition_type.value}",
            )
        )

    ready_after.sort(
        key=lambda item: (
            item.last_used_transition_no,
            item.admitted_transition_no,
            item.navmap.map_id,
            item.navmap.revision,
        )
    )
    evicted: Optional[WNMReadyEntryV1] = None
    capacity = _ready_capacity(ctx)
    while len(ready_after) > capacity:
        removed = ready_after.pop(0)
        if evicted is None:
            evicted = removed

    ctx.wnm_operative_map_v1 = destination
    ctx.wnm_ready_set_v1 = ready_after
    record = WNMTransitionRecordV1(
        transition_no=transition_no,
        observation_no=observation_no,
        controller_step=_controller_step(ctx),
        transition_type=transition_type,
        source_ref=_map_ref(source) if source is not None else None,
        destination_ref=_map_ref(destination),
        source_role=source.role if source is not None else None,
        destination_role=destination.role,
        source_frame_id=source.frame.frame_id if source is not None else None,
        destination_frame_id=destination.frame.frame_id,
        reason=reason,
        identity_handle=identity_handle,
        correspondence_basis=correspondence_basis,
        support=support_value,
        correspondence_ambiguous=False,
        accepted=True,
        acceptance_result="destination_committed_operative",
        prior_wnm_disposition="none" if source is None else "moved_to_ready_set",
        ready_before=_ready_refs(ready_before),
        ready_after=_ready_refs(ready_after),
        evicted_ref=evicted.map_ref if evicted is not None else None,
        failure_reason=None,
    )
    return _store_transition(ctx, record)


def wnm_return_to_ref_v1(
    ctx: Any,
    destination_ref: NavMapRefV1,
    *,
    observation_no: int,
    reason: str,
    identity_handle: str,
    correspondence_basis: str,
    support: float,
    correspondence_ambiguous: bool = False,
) -> dict[str, Any]:
    """Promote one exact ready-set map through a committed RETURN transition."""
    if not isinstance(destination_ref, NavMapRefV1):
        raise TypeError("destination_ref must be NavMapRefV1")
    destination = next(
        (navmap for navmap in wnm_ready_maps_v1(ctx) if _map_ref(navmap) == destination_ref),
        None,
    )
    if destination is None:
        # A typed placeholder is unavailable, so preserve state and expose a
        # direct summary-level failure without fabricating a map or transition.
        row = {
            "schema": "wnm_return_request_v1",
            "phase": "5-8",
            "status": "rejected",
            "destination_ref": destination_ref.as_dict(),
            "reason": reason,
            "failure_reason": "destination_not_in_ready_set",
            "operative_wnm_unchanged": True,
        }
        if ctx is not None:
            ctx.wnm_last_update_v1 = dict(row)
        return wnm_summary_v1(ctx)
    operative = wnm_operative_map_v1(ctx)
    return wnm_commit_transition_v1(
        ctx,
        destination,
        transition_type=WNMTransitionTypeV1.RETURN,
        observation_no=observation_no,
        reason=reason,
        identity_handle=identity_handle,
        correspondence_basis=correspondence_basis,
        support=support,
        correspondence_ambiguous=correspondence_ambiguous,
        expected_source_ref=_map_ref(operative) if operative is not None else None,
    )


def wnm_summary_v1(ctx: Any) -> dict[str, Any]:
    """Return a defensive JSON-safe single-operative-WNM summary."""
    if ctx is None:
        return {"schema": "wnm_summary_v1", "phase": "5-8", "status": "ctx_unavailable"}
    operative = wnm_operative_map_v1(ctx)
    ready = _clean_ready_entries(ctx)
    last = getattr(ctx, "wnm_last_transition_v1", None)
    last_row = last.as_dict() if isinstance(last, WNMTransitionRecordV1) else None
    return {
        "schema": "wnm_summary_v1",
        "phase": "5-8",
        "status": "active" if operative is not None else "idle",
        "authority": "single_operative_wnm",
        "operative_count": 1 if operative is not None else 0,
        "at_most_one_operative": True,
        "ready_capacity": _ready_capacity(ctx),
        "ready_count": len(ready),
        "ready_has_equal_authority": False,
        "operative_map": (
            {
                "map_ref": _map_ref(operative).as_dict(),
                "role": operative.role,
                "frame_id": operative.frame.frame_id,
            }
            if operative is not None
            else None
        ),
        "ready_set": [entry.as_dict() for entry in ready],
        "last_transition": last_row,
        "last_refresh": dict(getattr(ctx, "wnm_last_refresh_v1", {}) or {}),
        "transition_history_count": len(getattr(ctx, "wnm_transition_history_v1", []) or []),
    }


def render_wnm_lines_v1(ctx: Any) -> list[str]:
    """Return concise human-readable Phase 5 WNM/ready-set lines."""
    summary = wnm_summary_v1(ctx)
    lines = ["PHASE 5 OPERATIVE WNM:"]
    operative = summary.get("operative_map")
    if not isinstance(operative, dict):
        lines.append(
            "  "
            f"status={summary.get('status')} operative=none ready={summary.get('ready_count', 0)}/"
            f"{summary.get('ready_capacity', 0)}"
        )
        return lines
    ref = operative.get("map_ref")
    ref = ref if isinstance(ref, dict) else {}
    lines.append(
        "  "
        f"status=active operative={operative.get('role')} "
        f"{ref.get('map_id')}@r{ref.get('revision')} frame={operative.get('frame_id')}"
    )
    ready_parts: list[str] = []
    for item in summary.get("ready_set", []):
        if not isinstance(item, dict):
            continue
        item_ref = item.get("map_ref")
        item_ref = item_ref if isinstance(item_ref, dict) else {}
        ready_parts.append(f"{item.get('role')}:{item_ref.get('map_id')}@r{item_ref.get('revision')}")
    lines.append(
        "  "
        f"ready={len(ready_parts)}/{summary.get('ready_capacity')} "
        f"[{', '.join(ready_parts) if ready_parts else '(empty)'}] equal_authority=False"
    )
    last = summary.get("last_transition")
    if isinstance(last, dict):
        lines.append(
            "  "
            f"transition={last.get('transition_type')} accepted={last.get('accepted')} "
            f"reason={last.get('reason')} failure={last.get('failure_reason')}"
        )
    return lines
