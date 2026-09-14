#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1R-B single-slot internal handoff for the serialized NCA8 driver.

This is an embodiment-boundary service, not a cognitive module, resource
scheduler, actuator or distributed-delivery protocol. The core accepts one
immutable permitted request during E. After F and internal closure it releases
that request for one outer consumption. No method here calls the environment.

A receipt belongs to one owner incarnation. Identity checks reject copied,
foreign and stale receipts even when two sessions share a generation/action
number. These process-local checks intentionally do not claim persistence or
exactly-once delivery across a network. Consumption precedes the side effect;
uncertain execution must never lead to automatic reconsumption.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

from nca8_body import AuthorizedActionEnvelopeV1, BodyActionHandoffV1, BodyTaskTargetV1, EnvelopeStatusV1, LowerActionRequestV1
from nca8_contracts import CycleCommitmentV1
from nca8_prediction import ProjectedNavMapV1
from nca8_primitives import TaskActionV1

__version__ = "0.1.0"
__all__ = ["Nca8PhaseEDispatchV1", "Nca8HandoffReceiptV1", "Nca8InternalHandoffV1", "__version__"]


@dataclass(frozen=True, slots=True)
class Nca8PhaseEDispatchV1:
    """Immutable post-PNM request; acceptance is not external execution.

    Retained under its original name and re-exported by nca8_runtime for API
    compatibility. The internal handoff validates its links before accepting it.
    Only the authorized task, not the PNM or a desired world, reaches the bridge."""

    commitment: CycleCommitmentV1
    task_action: TaskActionV1 | None
    pnm: ProjectedNavMapV1 | None
    body_handoff: BodyActionHandoffV1 | None

    @property
    def authorized_task_action(self) -> TaskActionV1 | None:
        """Return the task action only when BodyMap authorized its handoff."""
        if self.body_handoff is None or not self.body_handoff.authorized:
            return None
        return self.task_action

    def as_dict(self) -> dict[str, object]:
        """Return a deterministic JSON-safe dispatch snapshot."""
        return {
            "commitment": self.commitment.as_dict(),
            "task_action": self.task_action.as_dict() if self.task_action is not None else None,
            "pnm": self.pnm.as_dict() if self.pnm is not None else None,
            "body_handoff": self.body_handoff.as_dict() if self.body_handoff is not None else None,
            "authorized_task_action": (
                self.authorized_task_action.as_dict() if self.authorized_task_action is not None else None
            ),
        }


@dataclass(frozen=True, slots=True)
class Nca8HandoffReceiptV1:
    """Immutable snapshot of one request's internal acceptance/consumption state.

    ``disposition`` is accepted, ready, consumed, cancelled or refused. None of
    these values establishes physical success. Old snapshots are history, not
    reusable permission. The owning slot alone supplies transition results.
    """

    generation: int
    dispatch: Nca8PhaseEDispatchV1
    disposition: str
    reason: str

    @property
    def receipt_id(self) -> str:
        """Return a diagnostic identifier; identity within the owner enforces use."""
        return f"handoff:g{self.generation}:a{self.dispatch.commitment.cycle_id}"

    def as_dict(self) -> dict[str, object]:
        """Return a detached diagnostic view, never a restorable permission."""
        return {
            "receipt_id": self.receipt_id,
            "generation": self.generation,
            "disposition": self.disposition,
            "reason": self.reason,
            "commitment": self.dispatch.commitment.as_dict(),
        }


def _validate_dispatch(dispatch: Nca8PhaseEDispatchV1) -> None:
    """Reject inconsistent action/PNM/body identities before granting acceptance."""
    if not isinstance(dispatch, Nca8PhaseEDispatchV1) or not isinstance(dispatch.commitment, CycleCommitmentV1):
        raise TypeError("handoff requires an Nca8PhaseEDispatchV1 with a CycleCommitmentV1")
    commitment = dispatch.commitment
    action = dispatch.task_action
    pnm = dispatch.pnm
    body = dispatch.body_handoff
    if pnm is not None:
        if not isinstance(pnm, ProjectedNavMapV1):
            raise TypeError("handoff PNM must be a ProjectedNavMapV1")
        if (pnm.pnm_id, pnm.application_id, pnm.source_wnm_id, pnm.primitive_id, pnm.created_cycle) != (
            commitment.pnm_id, commitment.focal_operation_id, commitment.wnm_id,
            commitment.selected_primitive_id, commitment.cycle_id,
        ):
            raise ValueError("handoff PNM does not match the immutable commitment")
    elif commitment.pnm_id is not None:
        raise ValueError("handoff is missing its committed PNM")
    if body is not None:
        if not isinstance(body, BodyActionHandoffV1):
            raise TypeError("handoff body result must be a BodyActionHandoffV1")
        if body.cycle_id != commitment.cycle_id or body.pnm_id != commitment.pnm_id:
            raise ValueError("handoff body result has the wrong cycle or PNM")
    if action is None:
        if commitment.task_action is not None or commitment.task_action_id is not None or commitment.action_envelope_id is not None:
            raise ValueError("null handoff cannot carry a committed movement")
        if body is not None and body.authorized:
            raise ValueError("null handoff cannot silently discard an authorized movement")
        return
    if not isinstance(action, TaskActionV1):
        raise TypeError("handoff task must be a TaskActionV1 or None")
    if (action.action_number, action.task_action_id, action.kind.value, action.source_application_id) != (
        commitment.cycle_id, commitment.task_action_id, commitment.task_action, commitment.focal_operation_id,
    ):
        raise ValueError("handoff action does not match the immutable commitment")
    if pnm is None or body is None or not body.authorized or body.envelope is None or body.lower_request is None:
        raise ValueError("movement handoff requires PNM and protected BodyMap permission")
    if not isinstance(body.envelope, AuthorizedActionEnvelopeV1) or not isinstance(body.lower_request, LowerActionRequestV1):
        raise TypeError("handoff requires typed envelope and lower request")
    target = body.task_target
    if not isinstance(target, BodyTaskTargetV1):
        raise TypeError("handoff requires a typed body target")
    if (target.target_id, target.task_action_id, target.source_application_id, target.created_cycle) != (
        body.lower_request.target_id, action.task_action_id, action.source_application_id, commitment.cycle_id,
    ):
        raise ValueError("handoff body target does not match its authorized movement")
    envelope = body.envelope
    if (envelope.envelope_id, envelope.task_action_id, envelope.source_application_id, envelope.authorized_cycle) != (
        commitment.action_envelope_id, action.task_action_id, action.source_application_id, commitment.cycle_id,
    ) or envelope.status is not EnvelopeStatusV1.AUTHORIZED:
        raise ValueError("handoff envelope does not authorize the committed movement")
    if body.lower_request.task_action != action or body.lower_request.envelope_id != envelope.envelope_id:
        raise ValueError("handoff lower request does not match its authorized movement")


class Nca8InternalHandoffV1:
    """Own one bounded, process-local request through E, closure and consumption.

    A disabled boundary refuses acceptance, including a null time-step request.
    BodyMap veto is different: the core can still commit and hand off a null
    output. Only a ready receipt can be consumed, once, before the outer side
    effect. Cancellation is allowed only while execution has not been released
    to the outer caller. There is no queue, retry, callback or environment access.
    """

    def __init__(self, *, generation: int = 1, enabled: bool = True) -> None:
        if isinstance(generation, bool) or not isinstance(generation, int) or generation < 1:
            raise ValueError("handoff generation must be a positive integer")
        if not isinstance(enabled, bool):
            raise TypeError("handoff enabled must be Boolean")
        self._generation = generation
        self._enabled = enabled
        self._receipt: Nca8HandoffReceiptV1 | None = None
        self._last_action_number = 0

    @property
    def generation(self) -> int:
        """Return the reset-created owner incarnation, not an environment step."""
        return self._generation

    @property
    def receipt(self) -> Nca8HandoffReceiptV1 | None:
        """Return the current immutable lifecycle snapshot, without copying it."""
        return self._receipt

    @property
    def has_pending_request(self) -> bool:
        """Return whether an accepted/ready request still needs a disposition."""
        return self._receipt is not None and self._receipt.disposition in {"accepted", "ready"}

    def accept(self, dispatch: Nca8PhaseEDispatchV1) -> Nca8HandoffReceiptV1:
        """Validate and accept one new output during E, without issuing a side effect.

        Refusal stores a truthful receipt and raises RuntimeError. Duplicate or
        inconsistent requests raise before replacing the existing slot. The
        caller must abort the cycle rather than invent a substitute body action.
        """
        _validate_dispatch(dispatch)
        if self.has_pending_request:
            raise RuntimeError("the previous handoff still requires consumption or cancellation")
        if dispatch.commitment.cycle_id != self._last_action_number + 1:
            raise RuntimeError("handoff action number must be the next unaccepted number")
        self._last_action_number = dispatch.commitment.cycle_id
        disposition = "accepted" if self._enabled else "refused"
        reason = "awaiting_internal_cycle_close" if self._enabled else "internal_handoff_disabled"
        self._receipt = Nca8HandoffReceiptV1(self._generation, dispatch, disposition, reason)
        if not self._enabled:
            raise RuntimeError("internal handoff refused acceptance")
        return self._receipt

    def release_after_close(self, receipt: Nca8HandoffReceiptV1) -> Nca8HandoffReceiptV1:
        """Release the exact accepted request after the core's successful internal close.

        The core calls this only after F, scheduler completion and its closure
        record. This does not consume the request and cannot call an actuator.
        """
        self._require(receipt, "accepted")
        self._receipt = replace(receipt, disposition="ready", reason="internal_cycle_closed")
        return self._receipt

    def consume(self, receipt: Nca8HandoffReceiptV1) -> TaskActionV1 | None:
        """Claim a ready request once, before the outer caller attempts world evolution.

        Return None for a null output: physical time can still advance once.
        A second call, a copied receipt or another owner's receipt raises before
        a second effect can be issued. Failure after this point cannot make this
        receipt ready again; the outer driver reports uncertainty and stops.
        """
        self._require(receipt, "ready")
        self._receipt = replace(receipt, disposition="consumed", reason="claimed_once_by_outer_driver")
        return receipt.dispatch.authorized_task_action

    def cancel(self, receipt: Nca8HandoffReceiptV1, *, reason: str) -> Nca8HandoffReceiptV1:
        """Cancel an unconsumed serialized request, without claiming that it moved."""
        if not isinstance(reason, str) or not reason.strip() or len(reason) > 160:
            raise ValueError("cancellation reason must be a nonempty string of at most 160 characters")
        self._require(receipt, "accepted", "ready")
        self._receipt = replace(receipt, disposition="cancelled", reason=reason)
        return self._receipt

    def _require(self, receipt: Nca8HandoffReceiptV1, *dispositions: str) -> None:
        """Enforce owner identity as well as generation, number and lifecycle state."""
        if not isinstance(receipt, Nca8HandoffReceiptV1) or receipt is not self._receipt or receipt.generation != self._generation:
            raise RuntimeError("foreign, stale or copied handoff receipt")
        if receipt.disposition not in dispositions:
            raise RuntimeError(f"handoff cannot be used while {receipt.disposition}")
