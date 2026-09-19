#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Behavior-neutral BodyMap target and local-execution contracts for P18-H1.

These records keep a proposed body-relative target, a committed description,
a low-level motor command and sensed consequences distinct. They describe the
future H3/H4/H6 interfaces; no executor, movement selector, clock, environment
access, source update or durable learner runs here. In particular, constructing
``CommittedBodyTargetV1`` does not grant live action permission. An owning
execution system must later validate the actual accepted handoff and maintain
its own installation/revision/expiry state.

Targets are offsets from an immutable admitted body basis. Their endpoints
never accumulate against newly sampled body poses. Local reports can establish
that a supplied target was observed achieved, but cannot establish Righting
completion, action causation or safe support. Task-level PNM is not local sensor
feedback. All exports are detached descriptions, not save/load actuator rights.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from enum import Enum

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1

__version__ = "0.1.0"
__all__ = [
    "BodyRelativeTargetV1",
    "CommittedBodyTargetV1",
    "FocalMotorEvidenceV1",
    "LocalTargetDispositionV1",
    "LocalTargetReportV1",
    "SensorimotorTargetKindV1",
    "TargetDirectiveV1",
    "TargetOriginV1",
    "__version__",
]

_MAX_COUNTER = 2**63 - 1
_MAX_LEASE_TICKS = 8
_MAX_CORRECTIONS = 2


def _counter(value: object, name: str, *, low: int = 0, high: int = _MAX_COUNTER) -> int:
    """Validate an integer identifier or finite budget without Boolean coercion."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{name} requires a non-Boolean integer")
    if value < low or value > high:
        raise ValueError(f"{name} is outside [{low}, {high}]")
    return value


def _text(value: object, name: str) -> str:
    """Return a bounded single-line origin/reason, retaining no external object."""
    if not isinstance(value, str):
        raise TypeError(f"{name} requires text")
    result = value.strip()
    if not 1 <= len(result) <= 120:
        raise ValueError(f"{name} requires 1-120 characters")
    if any(ord(char) < 32 for char in result):
        raise ValueError(f"{name} cannot contain control characters")
    return result


def _real(value: object, name: str) -> float:
    """Normalize a finite real parameter, rejecting Boolean, text and infinity."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{name} requires a numeric parameter")
    try:
        result = float(value)
    except OverflowError as exc:
        raise ValueError(f"{name} exceeds finite floating-point range") from exc
    if not math.isfinite(result):
        raise ValueError(f"{name} must be finite")
    return result


class SensorimotorTargetKindV1(str, Enum):
    """The two supplied-target families, not Navigation-selected task primitives."""

    ORIENTATION_ADJUST = "orientation_adjust"
    SUPPORT_EXTENSION = "support_extension"


class TargetDirectiveV1(str, Enum):
    """Vocabulary for the future owner; an enum value performs no operation.

    No-new-output is neither cancellation nor renewal. Replacement requires
    separate authorization and a new target revision. None retains its original
    meaning in the old runtime; these new names do not reinterpret that path.
    """

    NO_NEW_TASK_OUTPUT = "no_new_task_output"
    INSTALL_TARGET = "install_target"
    REPLACE_TARGET = "replace_target"
    CANCEL_TARGET = "cancel_target"


class LocalTargetDispositionV1(str, Enum):
    """Local execution descriptions, none of which means task-level success."""

    PENDING = "pending"
    ACTIVE = "active"
    PARTIAL = "partial"
    ACHIEVED = "achieved"
    BLOCKED = "blocked"
    UNAVAILABLE = "unavailable"
    CANCELLED = "cancelled"
    INTERRUPTED = "interrupted"
    EXPIRED = "expired"
    UNRESOLVED = "unresolved"


@dataclass(frozen=True, slots=True)
class TargetOriginV1:
    """Associate a target with one task application and envelope in one body stream.

    These are bounded diagnostic references. They do not copy a primitive,
    instantiate a task or replace actual receipt/envelope ownership checks.
    Task and envelope lifetimes may exceed a single target's finite lease.
    """

    stream: MotorStreamRefV1
    task_id: str
    application_id: str
    envelope_id: str

    def __post_init__(self) -> None:
        if not isinstance(self.stream, MotorStreamRefV1):
            raise TypeError("target origin requires MotorStreamRefV1")
        for name in ("task_id", "application_id", "envelope_id"):
            object.__setattr__(self, name, _text(getattr(self, name), name))

    def as_dict(self) -> dict[str, object]:
        """Return a detached origin description without live task authority."""
        return {
            "stream": self.stream.as_dict(),
            "task_id": self.task_id,
            "application_id": self.application_id,
            "envelope_id": self.envelope_id,
        }


@dataclass(frozen=True, slots=True)
class BodyRelativeTargetV1:
    """One proposed target anchored to a specific immutable body acquisition.

    ``offset`` is added to that acquisition's tilt or extension, never to a
    later measurement. ``max_displacement`` bounds permitted excursions from
    the original basis; ``max_rate`` is in degrees/s or normalized units/s for
    the corresponding family. Tolerance is a local measurement criterion,
    not a probability or a task-success threshold. A caller cannot request
    missing starting geometry or silently clip an infeasible endpoint.

    The initial interface permits at most 90 degrees/s or 1 extension unit/s,
    an eight-tick lease and two anomalous corrections. Smaller limits are
    allowed. Actual feasibility under sensing delay, coupling and disturbance
    must be qualified by H2-H4; nominal range validation does not prove it.
    This record does not grant permission and does not contain a motor command.
    """

    target_id: str
    revision: int
    origin: TargetOriginV1
    kind: SensorimotorTargetKindV1
    basis: MotorFeedbackV1
    offset: float
    tolerance: float
    max_displacement: float
    max_rate: float
    lease_ticks: int = _MAX_LEASE_TICKS
    max_corrections: int = _MAX_CORRECTIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        _counter(self.revision, "revision", low=1)
        if not isinstance(self.origin, TargetOriginV1):
            raise TypeError("origin requires TargetOriginV1")
        if not isinstance(self.kind, SensorimotorTargetKindV1):
            raise TypeError("kind requires SensorimotorTargetKindV1")
        if not isinstance(self.basis, MotorFeedbackV1):
            raise TypeError("basis requires MotorFeedbackV1")
        if self.basis.stream != self.origin.stream:
            raise ValueError("target basis belongs to another stream or generation")
        for name in ("offset", "tolerance", "max_displacement", "max_rate"):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        _counter(self.lease_ticks, "lease_ticks", low=1, high=_MAX_LEASE_TICKS)
        _counter(self.max_corrections, "max_corrections", high=_MAX_CORRECTIONS)
        if self.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
            lower, upper, rate_limit = -90.0, 90.0, 90.0
        else:
            lower, upper, rate_limit = 0.0, 1.0, 1.0
        if not 0.0 < self.max_displacement <= upper - lower:
            raise ValueError("max_displacement is outside the target coordinate range")
        if abs(self.offset) > self.max_displacement:
            raise ValueError("target offset exceeds its permitted displacement")
        if not 0.0 < self.tolerance <= self.max_displacement:
            raise ValueError("tolerance must be positive and no larger than the displacement bound")
        if not 0.0 < self.max_rate <= rate_limit:
            raise ValueError("max_rate exceeds the declared motor capability or is not positive")
        if not lower <= self.endpoint <= upper:
            raise ValueError("anchored target endpoint is outside the physical coordinate range")

    @property
    def basis_coordinate(self) -> float:
        """Return the required measured coordinate or reject missing geometry."""
        if self.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
            value = self.basis.body_tilt_degrees
        else:
            value = self.basis.support_extension
        if value is None:
            raise ValueError("the target's required starting body coordinate is missing")
        return value

    @property
    def endpoint(self) -> float:
        """Return the fixed endpoint from the saved body basis, with no mutation."""
        return self.basis_coordinate + self.offset

    def as_dict(self) -> dict[str, object]:
        """Render a proposed target and its anchor; never serialize live permission."""
        return {
            "schema": "body_relative_target_v1",
            "status": "proposed",
            "target_id": self.target_id,
            "revision": self.revision,
            "origin": self.origin.as_dict(),
            "kind": self.kind.value,
            "basis": self.basis.as_dict(),
            "offset": self.offset,
            "endpoint": self.endpoint,
            "tolerance": self.tolerance,
            "max_displacement": self.max_displacement,
            "max_rate": self.max_rate,
            "lease_ticks": self.lease_ticks,
            "max_corrections": self.max_corrections,
        }


@dataclass(frozen=True, slots=True)
class CommittedBodyTargetV1:
    """Describe a committed target's finite execution association, without installing it.

    The future owner obtains a real accepted handoff, creates an execution and
    records this immutable description. Merely constructing or copying one is
    not authorization. Its lease is half-open: [committed_tick, expires_at_tick).
    New sensing, repeated reads or NO_NEW_TASK_OUTPUT cannot extend it. There is
    intentionally no decoder that restores live targets from exported diagnostics.
    """

    target: BodyRelativeTargetV1
    execution_id: str
    committed_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.target, BodyRelativeTargetV1):
            raise TypeError("committed target requires BodyRelativeTargetV1")
        object.__setattr__(self, "execution_id", _text(self.execution_id, "execution_id"))
        tick = _counter(self.committed_tick, "committed_tick")
        if tick > _MAX_COUNTER - self.target.lease_ticks:
            raise ValueError("target expiry exceeds the bounded tick range")
        self.target.basis.validate_available(stream=self.target.origin.stream, at_tick=tick)

    @property
    def expires_at_tick(self) -> int:
        """Return the first tick at which this permission no longer permits pursuit."""
        return self.committed_tick + self.target.lease_ticks

    def validate_current(
        self,
        *,
        stream: MotorStreamRefV1,
        execution_id: str,
        envelope_id: str,
        target_id: str,
        target_revision: int,
        now_tick: int,
    ) -> None:
        """Check the caller's actual installed context and lease without creating one.

        H4 must supply its owned, current execution/target values and independently
        reject duplicate installations. This function checks correspondence only;
        a forged matching description or caller-supplied stale watermark is not
        prevented by a pure record. No clock, installation or command is changed.
        """
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("current stream requires MotorStreamRefV1")
        tick = _counter(now_tick, "now_tick")
        revision = _counter(target_revision, "target_revision", low=1)
        expected = (
            stream, _text(execution_id, "execution_id"), _text(envelope_id, "envelope_id"),
            _text(target_id, "target_id"), revision,
        )
        actual = (
            self.target.origin.stream, self.execution_id, self.target.origin.envelope_id,
            self.target.target_id, self.target.revision,
        )
        if expected != actual:
            raise ValueError("wrong target stream, generation, execution, envelope, identity or revision")
        if not self.committed_tick <= tick < self.expires_at_tick:
            raise ValueError("target is not current: uncommitted or expired at this tick")

    def as_dict(self) -> dict[str, object]:
        """Return a committed description, explicitly not a replayable receipt."""
        return {
            "schema": "committed_body_target_v1",
            "status": "committed_description",
            "target": self.target.as_dict(),
            "execution_id": self.execution_id,
            "committed_tick": self.committed_tick,
            "expires_at_tick": self.expires_at_tick,
            "restores_live_authority": False,
        }


@dataclass(frozen=True, slots=True)
class FocalMotorEvidenceV1:
    """Describe the same sensor occurrence at a declared focal evidence cutoff.

    The immutable feedback object may safely be shared; exported dictionaries
    are detached. This is not a second sensor, source owner, WNM or observation.
    It cannot admit itself to an existing runtime. H6 must select a stream-owned,
    due sample and apply the ordinary source/focal eligibility rules. No history
    or event_cycle is synthesized from local ticks here.
    """

    feedback: MotorFeedbackV1
    focal_cycle: int
    cutoff_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.feedback, MotorFeedbackV1):
            raise TypeError("focal evidence requires MotorFeedbackV1")
        _counter(self.focal_cycle, "focal_cycle", low=1)
        tick = _counter(self.cutoff_tick, "cutoff_tick")
        self.feedback.validate_available(stream=self.feedback.stream, at_tick=tick)

    def as_dict(self) -> dict[str, object]:
        """Preserve physical identity and both times without manufacturing an event."""
        return {
            "schema": "focal_motor_evidence_v1",
            "focal_cycle": self.focal_cycle,
            "cutoff_tick": self.cutoff_tick,
            "feedback": self.feedback.as_dict(),
            "independent_sensor_event": False,
            "is_wnm": False,
        }


@dataclass(frozen=True, slots=True)
class LocalTargetReportV1:
    """A bounded local disposition, not a task outcome or a stateful executor.

    ACHIEVED/PARTIAL require matching available measured target coordinates.
    ACHIEVED additionally requires the supplied target tolerance. Contact/load
    may disagree with the task's needs even when an extension is achieved.
    A delayed report can describe achievement observed by the lease endpoint;
    it cannot reactivate pursuit or establish that the command caused it.
    Execution ownership, freshness policy, actual correction accounting and
    transitions still belong to H4. There is no hidden success flag or learner.
    """

    committed_target: CommittedBodyTargetV1
    disposition: LocalTargetDispositionV1
    reported_tick: int
    reason: str
    feedback: MotorFeedbackV1 | None = None
    correction_count: int = 0

    def __post_init__(self) -> None:
        if not isinstance(self.committed_target, CommittedBodyTargetV1):
            raise TypeError("local report requires CommittedBodyTargetV1")
        if not isinstance(self.disposition, LocalTargetDispositionV1):
            raise TypeError("disposition requires LocalTargetDispositionV1")
        tick = _counter(self.reported_tick, "reported_tick")
        target = self.committed_target.target
        _counter(self.correction_count, "correction_count", high=target.max_corrections)
        object.__setattr__(self, "reason", _text(self.reason, "reason"))
        if tick < self.committed_target.committed_tick:
            raise ValueError("local disposition cannot precede commitment")
        if self.disposition is LocalTargetDispositionV1.EXPIRED and tick < self.committed_target.expires_at_tick:
            raise ValueError("target lease has not expired")
        if self.disposition in {LocalTargetDispositionV1.PENDING, LocalTargetDispositionV1.ACTIVE}:
            if tick >= self.committed_target.expires_at_tick:
                raise ValueError("expired targets cannot be pending or active")
        if self.feedback is not None:
            if not isinstance(self.feedback, MotorFeedbackV1):
                raise TypeError("local feedback requires MotorFeedbackV1 or None")
            self.feedback.validate_available(stream=target.origin.stream, at_tick=tick)
            if self.feedback.sample_id < target.basis.sample_id or self.feedback.event_tick < target.basis.event_tick:
                raise ValueError("local feedback predates the target's body basis")
            if self.feedback.sample_id == target.basis.sample_id and self.feedback != target.basis:
                raise ValueError("one sensor sample identity cannot describe changed content or time")
        if self.disposition in {LocalTargetDispositionV1.ACHIEVED, LocalTargetDispositionV1.PARTIAL}:
            self._validate_observed_result()

    def _validate_observed_result(self) -> None:
        """Validate a claimed observation without assigning task or causal credit."""
        feedback = self.feedback
        if feedback is None:
            raise ValueError("observed local achievement/progress requires actual feedback")
        target = self.committed_target.target
        coordinate = (
            feedback.body_tilt_degrees
            if target.kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST
            else feedback.support_extension
        )
        if coordinate is None:
            raise ValueError("the target's measured result is unavailable")
        if self.disposition is LocalTargetDispositionV1.ACHIEVED:
            if feedback.event_tick > self.committed_target.expires_at_tick:
                raise ValueError("achievement was not observed by the target lease endpoint")
            if abs(coordinate - target.endpoint) > target.tolerance + 1e-12:
                raise ValueError("measured coordinate does not achieve the target tolerance")

    def as_dict(self) -> dict[str, object]:
        """Export local evidence/status only; this description is not task completion."""
        target = self.committed_target.target
        return {
            "schema": "local_target_report_v1",
            "origin": target.origin.as_dict(),
            "target_id": target.target_id,
            "target_revision": target.revision,
            "execution_id": self.committed_target.execution_id,
            "disposition": self.disposition.value,
            "reported_tick": self.reported_tick,
            "correction_count": self.correction_count,
            "reason": self.reason,
            "feedback": self.feedback.as_dict() if self.feedback is not None else None,
            "establishes_task_success": False,
            "establishes_action_causation": False,
        }
