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
from dataclasses import dataclass, field
from enum import Enum
from typing import Protocol

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1

__version__ = "0.7.0"
__all__ = [
    "BodyRelativeTargetV1", "BodyTranslationTargetV1", "OralExtractionTargetV1",
    "CommittedBodyTargetV1",
    "FocalMotorEvidenceV1",
    "LocalTargetDispositionV1",
    "LocalTargetReportV1",
    "MotorInstallationSourceV1",
    "SensorimotorTargetKindV1",
    "TargetDirectiveV1",
    "TargetOriginV1", "scalar_motor_coordinate_v1", "oral_basis_compatible_v1", "oral_closure_basis_compatible_v1",
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
    """Supported body resources, not Navigation-selected task primitives.

    ORAL_REACH is the optional single body-forward reach coordinate. It grants
    neither a head-orientation strategy nor latch/suckling competence.
    ORAL_CLOSURE is an independent normalized closing/opening coordinate;
    attaining it cannot establish the separately measured physical seal.
    """

    ORIENTATION_ADJUST = "orientation_adjust"
    SUPPORT_EXTENSION = "support_extension"
    PLANAR_TRANSLATION = "planar_translation"
    ORAL_REACH = "oral_reach"
    ORAL_CLOSURE = "oral_closure"
    ORAL_EXTRACTION = "oral_extraction"


def scalar_motor_coordinate_v1(feedback: MotorFeedbackV1, kind: SensorimotorTargetKindV1) -> float | None:
    """Read one actually measured scalar resource; never synthesize missing reach.

    Mapper, contracts and executor share this dispatch so a new oral coordinate
    cannot accidentally be interpreted as support extension. Vector translation
    deliberately has no scalar fallback. This reader has no side effects.
    """
    if not isinstance(feedback, MotorFeedbackV1) or not isinstance(kind, SensorimotorTargetKindV1):
        raise TypeError("scalar coordinate needs canonical feedback and a typed target family")
    if kind is SensorimotorTargetKindV1.ORIENTATION_ADJUST:
        return feedback.body_tilt_degrees
    if kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION:
        return feedback.support_extension
    if kind is SensorimotorTargetKindV1.ORAL_REACH:
        return None if feedback.oral is None else feedback.oral.extension_metres
    if kind is SensorimotorTargetKindV1.ORAL_CLOSURE:
        return None if feedback.oral_seal is None else feedback.oral_seal.closure
    if kind is SensorimotorTargetKindV1.ORAL_EXTRACTION:
        return None if feedback.oral_extraction is None else feedback.oral_extraction.stroke
    raise ValueError("vector translation has no scalar motor coordinate")


def oral_basis_compatible_v1(basis: MotorFeedbackV1, feedback: MotorFeedbackV1) -> bool:
    """Check that the body-forward axis still denotes its original scene relation.

    The first oral executor cannot rotate its head or compensate for whole-body
    movement. More than 0.001 metres of translation or 0.5 degrees of yaw makes
    its old scene-directed target inappropriate. These are fixed engineering
    tolerances, not measured anatomy. Missing pose is not a compatible anchor;
    a new target/authorization is needed after an incompatible body change.
    """
    if not isinstance(basis, MotorFeedbackV1) or not isinstance(feedback, MotorFeedbackV1):
        raise TypeError("oral basis comparison requires canonical motor acquisitions")
    before, after = basis.planar, feedback.planar
    if (basis.stream != feedback.stream or before is None or after is None or before.frame_id != after.frame_id
            or before.position is None or after.position is None or before.heading_degrees is None or after.heading_degrees is None):
        return False
    distance = math.hypot(after.position[0] - before.position[0], after.position[1] - before.position[1])
    angle = (after.heading_degrees - before.heading_degrees + 180.0) % 360.0 - 180.0
    return distance <= 0.001 + 1e-12 and abs(angle) <= 0.5 + 1e-12


def oral_closure_basis_compatible_v1(basis: MotorFeedbackV1, feedback: MotorFeedbackV1) -> bool:
    """Keep closure at its original body/heading/reach anchor, not a new surface.

    Closure cannot compensate for more than 0.001 metres of reach change or the
    existing oral body-anchor limits. A lost anchor requires a new mapping and
    authorization; cached seal evidence cannot authorize pursuit at a new point.
    """
    if not oral_basis_compatible_v1(basis, feedback):
        return False
    before, after = basis.oral, feedback.oral
    return (before is not None and after is not None and before.extension_metres is not None
            and after.extension_metres is not None and abs(before.extension_metres - after.extension_metres) <= 0.001 + 1e-12)


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
    the corresponding family. ORAL_REACH uses metres and metres/second on a
    single body-forward axis, capped at 0.35 metres and 0.5 metres/second, with
    an independently retained horizontal body position/yaw basis. ORAL_CLOSURE
    uses normalized units with a 2 units/second ceiling and retains the original
    body/yaw/reach anchor. Its coordinate criterion is not a seal criterion.
    Tolerance is a local measurement criterion,
    not a probability or a task-success threshold. A caller cannot request
    missing starting geometry or silently clip an infeasible endpoint.

    The support axes permit at most 90 degrees/s or 1 extension unit/s. All
    scalar families share an eight-tick lease and two anomalous corrections. Smaller limits are
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
    rest_constraint: str | None = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        _counter(self.revision, "revision", low=1)
        if not isinstance(self.origin, TargetOriginV1):
            raise TypeError("origin requires TargetOriginV1")
        if not isinstance(self.kind, SensorimotorTargetKindV1):
            raise TypeError("kind requires SensorimotorTargetKindV1")
        if self.kind in {SensorimotorTargetKindV1.PLANAR_TRANSLATION, SensorimotorTargetKindV1.ORAL_EXTRACTION}:
            raise ValueError("translation and extraction require their dedicated target records")
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
        elif self.kind is SensorimotorTargetKindV1.ORAL_REACH:
            lower, upper, rate_limit = 0.0, 0.35, 0.5
            if not oral_basis_compatible_v1(self.basis, self.basis):
                raise ValueError("oral target requires a known original body position and heading")
        elif self.kind is SensorimotorTargetKindV1.ORAL_CLOSURE:
            lower, upper, rate_limit = 0.0, 1.0, 2.0
            if not oral_closure_basis_compatible_v1(self.basis, self.basis):
                raise ValueError("closure target requires a known original body and reach anchor")
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
        if self.rest_constraint is not None:
            expected = {"release": SensorimotorTargetKindV1.ORAL_CLOSURE,
                        "withdraw": SensorimotorTargetKindV1.ORAL_REACH,
                        "settle": SensorimotorTargetKindV1.SUPPORT_EXTENSION,
                        "hold": SensorimotorTargetKindV1.SUPPORT_EXTENSION}
            if not isinstance(self.rest_constraint, str) or self.rest_constraint not in expected:
                raise ValueError("unknown Rest constraint")
            if (self.kind is not expected[self.rest_constraint] or self.offset > 0.0
                    or not self.origin.application_id.startswith("rest_application:")
                    or not self.origin.task_id.startswith("rest:")):
                raise ValueError("Rest constraints require the original Rest family and nonpositive displacement")
            if self.rest_constraint == "hold" and self.offset != 0.0:
                raise ValueError("a Rest hold cannot request displacement")

    @property
    def basis_coordinate(self) -> float:
        """Return the required measured coordinate or reject missing geometry."""
        value = scalar_motor_coordinate_v1(self.basis, self.kind)
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
            **({"rest_constraint": self.rest_constraint} if self.rest_constraint is not None else {}),
            **({"coordinate_frame": "body_forward_oral_v1", "coordinate_units": "metres", "rate_units": "metres_per_second"}
               if self.kind is SensorimotorTargetKindV1.ORAL_REACH else {}),
        }


@dataclass(frozen=True, slots=True)
class OralExtractionTargetV1:
    """One preauthorized extract/return pattern, not a scalar endpoint or task IP.

    Both endpoints are anchored to the original measured stroke and body/reach
    basis. One or two cycles require two or four distinct ordered acquisitions;
    the initial return coordinate cannot establish completion. The original
    eight-tick maximum lease and excursion/rate/correction limits apply to the
    WHOLE pattern, not separately to each leg. No implicit renewal is possible.
    These are deterministic engineering bounds, not physiological rhythm values.
    Milk is neither a target quantity nor evidence that a movement leg completed.
    """

    target_id: str
    revision: int
    origin: TargetOriginV1
    basis: MotorFeedbackV1
    outward_offset: float
    repetitions: int
    tolerance: float
    max_displacement: float
    max_rate: float
    lease_ticks: int = _MAX_LEASE_TICKS
    max_corrections: int = _MAX_CORRECTIONS
    kind: SensorimotorTargetKindV1 = field(default=SensorimotorTargetKindV1.ORAL_EXTRACTION, init=False)

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        _counter(self.revision, "revision", low=1)
        _counter(self.repetitions, "repetitions", low=1, high=2)
        _counter(self.lease_ticks, "lease_ticks", low=1, high=_MAX_LEASE_TICKS)
        _counter(self.max_corrections, "max_corrections", high=_MAX_CORRECTIONS)
        if not isinstance(self.origin, TargetOriginV1) or not isinstance(self.basis, MotorFeedbackV1):
            raise TypeError("extraction needs an original origin and motor acquisition")
        if self.basis.stream != self.origin.stream or not oral_closure_basis_compatible_v1(self.basis, self.basis):
            raise ValueError("extraction needs its original stream and body/reach anchor")
        for name in ("outward_offset", "tolerance", "max_displacement", "max_rate"):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        if not 0.0 < 2.0 * self.tolerance < self.outward_offset <= self.max_displacement <= 1.0:
            raise ValueError("extraction endpoints need distinct positive tolerance bands inside the excursion")
        if not 0.0 < self.max_rate <= 2.0 or self.outward_endpoint > 1.0:
            raise ValueError("extraction exceeds its physical stroke or rate range")

    @property
    def basis_coordinate(self) -> float:
        """Return original measured stroke; missing sensing is never filled in."""
        value = scalar_motor_coordinate_v1(self.basis, self.kind)
        if value is None:
            raise ValueError("extraction requires the original measured stroke")
        return value

    @property
    def outward_endpoint(self) -> float:
        """Return the fixed outward endpoint, without accumulating offsets."""
        return self.basis_coordinate + self.outward_offset

    @property
    def return_endpoint(self) -> float:
        """Return the original stroke, not proof of an already completed cycle."""
        return self.basis_coordinate

    def as_dict(self) -> dict[str, object]:
        """Describe the entire finite pattern; exported records grant no permission."""
        return {"schema": "oral_extraction_target_v1", "status": "proposed", "target_id": self.target_id,
                "revision": self.revision, "origin": self.origin.as_dict(), "kind": self.kind.value,
                "basis": self.basis.as_dict(), "outward_offset": self.outward_offset,
                "outward_endpoint": self.outward_endpoint, "return_endpoint": self.return_endpoint,
                "repetitions": self.repetitions, "tolerance": self.tolerance, "max_displacement": self.max_displacement,
                "max_rate": self.max_rate, "lease_ticks": self.lease_ticks, "max_corrections": self.max_corrections,
                "coordinate_units": "normalized_stroke", "milk_is_target": False}


@dataclass(frozen=True, slots=True)
class BodyTranslationTargetV1:
    """One finite forward/left offset anchored to an original horizontal pose.

    The scene endpoint is derived once from the saved measured position/yaw.
    New feedback can remap pursuit into a new body heading, but never adds the
    original offset again. The displacement bound is radial, not per-axis;
    rate and tolerance are metres/second and metres. One translation resource
    excludes incompatible support manipulation in this initial conservative
    profile. This record itself grants no installation or motion authority.
    """

    target_id: str
    revision: int
    origin: TargetOriginV1
    basis: MotorFeedbackV1
    offset: tuple[float, float]
    tolerance: float = 0.01
    max_displacement: float = 0.35
    max_rate: float = 1.0
    lease_ticks: int = _MAX_LEASE_TICKS
    max_corrections: int = _MAX_CORRECTIONS

    def __post_init__(self) -> None:
        object.__setattr__(self, "target_id", _text(self.target_id, "target_id"))
        _counter(self.revision, "revision", low=1)
        if not isinstance(self.origin, TargetOriginV1) or not isinstance(self.basis, MotorFeedbackV1):
            raise TypeError("translation target needs its typed origin and measured body basis")
        if self.basis.stream != self.origin.stream:
            raise ValueError("translation basis belongs to another generation")
        planar = self.basis.planar
        if planar is None or planar.position is None or planar.heading_degrees is None:
            raise ValueError("translation cannot invent missing starting position or heading")
        if not isinstance(self.offset, tuple) or len(self.offset) != 2:
            raise TypeError("translation offset must be an immutable forward/left pair")
        object.__setattr__(self, "offset", (_real(self.offset[0], "forward offset"), _real(self.offset[1], "left offset")))
        for name in ("tolerance", "max_displacement", "max_rate"):
            object.__setattr__(self, name, _real(getattr(self, name), name))
        if not 0.0 < self.tolerance <= self.max_displacement <= 0.5 or not 0.0 < self.max_rate <= 1.0:
            raise ValueError("translation exceeds the fixed tolerance/excursion/rate contract")
        if math.hypot(*self.offset) > self.max_displacement + 1e-12:
            raise ValueError("translation offset exceeds the original radial excursion")
        _counter(self.lease_ticks, "lease_ticks", low=1, high=_MAX_LEASE_TICKS)
        _counter(self.max_corrections, "max_corrections", high=_MAX_CORRECTIONS)
        if max(abs(value) for value in self.endpoint) > 10000.0:
            raise ValueError("translation endpoint exceeds the supported scene coordinates")

    @property
    def kind(self) -> SensorimotorTargetKindV1:
        """Identify the single vector resource; it is not two unrelated tasks."""
        return SensorimotorTargetKindV1.PLANAR_TRANSLATION

    @property
    def endpoint(self) -> tuple[float, float]:
        """Return the same anchored scene endpoint after any subsequent body motion."""
        planar = self.basis.planar
        if planar is None or planar.position is None or planar.heading_degrees is None:
            raise ValueError("translation target lost its required original geometry")
        cosine, sine = math.cos(math.radians(planar.heading_degrees)), math.sin(math.radians(planar.heading_degrees))
        forward, left = self.offset
        return planar.position[0] + cosine * forward - sine * left, planar.position[1] + sine * forward + cosine * left

    def as_dict(self) -> dict[str, object]:
        """Export a proposal with immutable anchors, not a replayable motor right."""
        return {"schema": "body_translation_target_v1", "status": "proposed", "target_id": self.target_id,
                "revision": self.revision, "origin": self.origin.as_dict(), "kind": self.kind.value,
                "basis": self.basis.as_dict(), "offset": list(self.offset), "endpoint": list(self.endpoint),
                "tolerance": self.tolerance, "max_displacement": self.max_displacement, "max_rate": self.max_rate,
                "lease_ticks": self.lease_ticks, "max_corrections": self.max_corrections}


@dataclass(frozen=True, slots=True)
class CommittedBodyTargetV1:
    """Describe a committed target's finite execution association, without installing it.

    The future owner obtains a real accepted handoff, creates an execution and
    records this immutable description. Merely constructing or copying one is
    not authorization. Its lease is half-open: [committed_tick, expires_at_tick).
    New sensing, repeated reads or NO_NEW_TASK_OUTPUT cannot extend it. There is
    intentionally no decoder that restores live targets from exported diagnostics.
    """

    target: BodyRelativeTargetV1 | BodyTranslationTargetV1 | OralExtractionTargetV1
    execution_id: str
    committed_tick: int

    def __post_init__(self) -> None:
        if not isinstance(self.target, (BodyRelativeTargetV1, BodyTranslationTargetV1, OralExtractionTargetV1)):
            raise TypeError("committed target requires a typed scalar or translation target")
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
    extraction_confirmations: tuple[MotorFeedbackV1, ...] = field(default=(), kw_only=True)

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
        if isinstance(target, OralExtractionTargetV1):
            self._validate_extraction_progress()
        elif self.extraction_confirmations != ():
            raise ValueError("only extraction can carry ordered stroke evidence")
        if self.disposition in {LocalTargetDispositionV1.ACHIEVED, LocalTargetDispositionV1.PARTIAL}:
            self._validate_observed_result()

    def _validate_extraction_progress(self) -> None:
        """Validate a bounded ordered prefix; no predicted or duplicated endpoints.

        A late final confirmation may describe a measurement by the lease end,
        but this descriptive record cannot grant another movement or extend time.
        Live ownership and once-only phase advancement belong to the executor.
        """
        target = self.committed_target.target
        if not isinstance(target, OralExtractionTargetV1):
            raise TypeError("ordered progress requires an extraction target")
        confirmations = self.extraction_confirmations
        if not isinstance(confirmations, tuple) or len(confirmations) > 2 * target.repetitions:
            raise ValueError("extraction evidence must be a bounded immutable prefix")
        previous = target.basis
        for index, sample in enumerate(confirmations):
            if not isinstance(sample, MotorFeedbackV1):
                raise TypeError("stroke confirmation requires actual motor feedback")
            sample.validate_available(stream=target.origin.stream, at_tick=self.reported_tick)
            if (sample.sample_id <= previous.sample_id or sample.event_tick <= previous.event_tick
                    or not self.committed_target.committed_tick < sample.event_tick <= self.committed_target.expires_at_tick):
                raise ValueError("stroke confirmation must be a distinct ordered event within the original lease")
            value = scalar_motor_coordinate_v1(sample, target.kind)
            endpoint = target.outward_endpoint if index % 2 == 0 else target.return_endpoint
            if value is None or abs(value - endpoint) > target.tolerance + 1e-12:
                raise ValueError("sensed endpoint does not confirm this ordered extraction leg")
            if (not oral_closure_basis_compatible_v1(target.basis, sample) or sample.oral is None
                    or sample.oral.contact is not True or sample.oral_seal is None or sample.oral_seal.sealed is not True
                    or sample.oral_seal.closure is None or sample.oral_seal.closure < 0.5
                    or sample.support_contact is not True or sample.useful_loading is None or sample.useful_loading < 0.75
                    or sample.body_tilt_degrees is None or abs(sample.body_tilt_degrees) > 12.0
                    or sample.destabilization is None or sample.destabilization > 0.25):
                raise ValueError("stroke confirmation lacks its supported sealed body/reach context")
            previous = sample
        if self.disposition is LocalTargetDispositionV1.ACHIEVED:
            if len(confirmations) != 2 * target.repetitions or self.feedback != confirmations[-1]:
                raise ValueError("extraction achievement requires the whole ordered sensed sequence")

    def _validate_observed_result(self) -> None:
        """Validate a claimed observation without assigning task or causal credit."""
        feedback = self.feedback
        if feedback is None:
            raise ValueError("observed local achievement/progress requires actual feedback")
        target = self.committed_target.target
        if isinstance(target, OralExtractionTargetV1):
            if (scalar_motor_coordinate_v1(feedback, target.kind) is None
                    or not oral_closure_basis_compatible_v1(target.basis, feedback)):
                raise ValueError("extraction progress lacks its measured coordinate or original anchor")
            return  # Whole-pattern achievement was checked against ordered confirmations.
        if isinstance(target, BodyTranslationTargetV1):
            planar = feedback.planar
            anchor = target.basis.planar
            if planar is None or anchor is None or planar.position is None or planar.frame_id != anchor.frame_id:
                raise ValueError("translation result needs compatible observed position")
            distance = math.hypot(planar.position[0] - target.endpoint[0], planar.position[1] - target.endpoint[1])
        else:
            coordinate = scalar_motor_coordinate_v1(feedback, target.kind)
            if target.kind is SensorimotorTargetKindV1.ORAL_REACH and not oral_basis_compatible_v1(target.basis, feedback):
                raise ValueError("oral result lacks the original compatible body-forward anchor")
            if target.kind is SensorimotorTargetKindV1.ORAL_CLOSURE and not oral_closure_basis_compatible_v1(target.basis, feedback):
                raise ValueError("closure result lacks its original body and reach anchor")
            if coordinate is None:
                raise ValueError("the target's measured result is unavailable")
            distance = abs(coordinate - target.endpoint)
        if self.disposition is LocalTargetDispositionV1.ACHIEVED:
            if feedback.event_tick > self.committed_target.expires_at_tick:
                raise ValueError("achievement was not observed by the target lease endpoint")
            if distance > target.tolerance + 1e-12:
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
            **({"extraction_progress": {
                "confirmed_endpoints": [item.as_dict() for item in self.extraction_confirmations],
                "completed_cycles": len(self.extraction_confirmations) // 2,
                "required_endpoints": 2 * target.repetitions,
                "next_leg": "complete" if len(self.extraction_confirmations) == 2 * target.repetitions else
                            "outward" if len(self.extraction_confirmations) % 2 == 0 else "return",
                "milk_is_movement_criterion": False,
            }} if isinstance(target, OralExtractionTargetV1) else {}),
        }


class MotorInstallationSourceV1(Protocol): # pylint: disable=too-few-public-methods
    """Narrow lower reader of a consumed cognitive handoff, not a task selector.

    The owning handoff must reject a claim before closure/consumption and every
    second claim. Returned original target objects identify the authorized
    BodyMap reservations; reconstructing their serialized descriptions grants
    no rights. The executor sees neither WNM, PNM nor the physical provider.
    A Protocol declares this seam; it does not implement or grant permission.
    """

    def claim_motor_targets(self) -> tuple[CommittedBodyTargetV1, ...]:
        """Spend the current installation grant once and return its original targets."""
        ... # pylint: disable=unnecessary-ellipsis
