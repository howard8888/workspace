#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H4: deterministic following of supplied BodyMap targets.

This ordinary local controller receives a BodyMap-owned reservation and admitted
motor feedback. It emits at most one bounded MotorCommandV1 per supplied tick.
It never calls a world, selects a task, reads a WNM/PNM, or learns a parameter.
The external driver owns time and physical side effects. A local ACHIEVED report
means an observed coordinate was within tolerance, not that Righting succeeded.

Reactive target-error tracking and command-conditioned prediction protection are
separate. Accounting for already-issued drives prevents blindly repeating an
increment while its measurement is in transit; it does not make predicted motion
observed evidence. The separate fixed prediction check can restrict a response to
an unexpected sensed consequence. All competence values are engineering fixtures.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1
from nca8_body_targets import BodyTargetMapperV1, BodyTargetReservationV1
from nca8_sensorimotor_contracts import (
    LocalTargetDispositionV1, LocalTargetReportV1, MotorInstallationSourceV1, SensorimotorTargetKindV1, TargetOriginV1,
)

__version__ = "0.2.1"
__all__ = [
    "LocalMotorPredictionV1", "LocalPredictionComparisonV1", "LocalControlEventV1",
    "SensorimotorProfileV1", "SensorimotorStepV1", "SensorimotorExecutorV1", "__version__",
]

_MAX_TICK = 2**63 - 3
_HISTORY_LIMIT = 4
_EVENT_LIMIT = 4
_EPSILON = 1e-12
_ORIENTATION = SensorimotorTargetKindV1.ORIENTATION_ADJUST
_EXTENSION = SensorimotorTargetKindV1.SUPPORT_EXTENSION
_TERMINAL = frozenset({
    LocalTargetDispositionV1.ACHIEVED, LocalTargetDispositionV1.BLOCKED,
    LocalTargetDispositionV1.UNAVAILABLE, LocalTargetDispositionV1.CANCELLED,
    LocalTargetDispositionV1.INTERRUPTED, LocalTargetDispositionV1.EXPIRED,
})
_MISSING_REASONS = frozenset({
    "current_body_feedback_unavailable", "required_coordinate_missing", "required_support_evidence_missing",
})


def _tick(value: object, label: str = "at_tick") -> int:
    """Reject invalid logical time instead of silently advancing or repairing it."""
    if isinstance(value, bool) or not isinstance(value, int):
        raise TypeError(f"{label} must be a non-Boolean integer")
    if not 0 <= value <= _MAX_TICK:
        raise ValueError(f"{label} is outside the finite local time range")
    return value


def _coordinate(feedback: MotorFeedbackV1, kind: SensorimotorTargetKindV1) -> float | None:
    """Read the measured coordinate for one family, preserving missingness."""
    return feedback.body_tilt_degrees if kind is _ORIENTATION else feedback.support_extension


def _drive(command: MotorCommandV1 | None, kind: SensorimotorTargetKindV1) -> float:
    """Read an actually issued drive, treating None as the provider's neutral input."""
    if command is None:
        return 0.0
    return command.orientation_drive if kind is _ORIENTATION else command.extension_drive


def _motor_rate(kind: SensorimotorTargetKindV1) -> float:
    """Return the declared motor calibration, not a private simulator reading."""
    return 90.0 if kind is _ORIENTATION else 1.0


@dataclass(frozen=True, slots=True)
class SensorimotorProfileV1:
    """Fixed H4 control settings, independently of the physical provider profile.

    Prediction protection can be disabled for a controlled reactive comparison.
    Thresholds remain the H1 design values: five degrees or 0.04 extension units.
    A permitted anomalous response is limited to half the target's normal rate.
    No current-evidence, resource, rate, lease or excursion check is disabled by
    this switch. Trace capacity affects diagnostics only; functional histories
    and four unresolved significant events have independent fixed bounds.
    """

    prediction_protection: bool = True
    trace_capacity: int = 256

    def __post_init__(self) -> None:
        if not isinstance(self.prediction_protection, bool):
            raise TypeError("prediction_protection must be Boolean")
        _tick(self.trace_capacity, "trace_capacity")
        if not 1 <= self.trace_capacity <= 256:
            raise ValueError("trace_capacity must be in [1, 256]")


    def as_dict(self) -> dict[str, object]:
        """Name the fixed engineering profile and disclose all local control limits."""
        return {
            "profile_id": "fixed_target_control_v1", "prediction_protection": self.prediction_protection,
            "orientation_residual_limit_degrees": 5.0, "extension_residual_limit": 0.04,
            "anomalous_response_rate_fraction": 0.5, "missing_feedback_grace_ticks": 2,
            "routine_history_capacity": _HISTORY_LIMIT, "significant_event_capacity": _EVENT_LIMIT,
            "trace_capacity": self.trace_capacity, "learning_enabled": False,
        }


@dataclass(frozen=True, slots=True)
class LocalMotorPredictionV1:
    """One short expected coordinate/contact consequence, made before its event.

    The saved basis is a real sensor acquisition. The predicted coordinate is
    never installed in BodyMap or used to establish achievement. Contact=True
    means a short continuity expectation under non-withdrawing commands; None
    means this small model makes no contact claim. No private surface height,
    disturbance label, task success, or future measurement enters this record.
    """

    target_id: str
    target_revision: int
    kind: SensorimotorTargetKindV1
    basis_sample_id: int
    basis_event_tick: int
    issued_tick: int
    event_tick: int
    expected_coordinate: float
    tolerance: float
    expected_contact: bool | None

    def as_dict(self) -> dict[str, object]:
        """Export the original claim without altering its basis or event identity."""
        return {
            "target_id": self.target_id, "target_revision": self.target_revision, "kind": self.kind.value,
            "basis_sample_id": self.basis_sample_id, "basis_event_tick": self.basis_event_tick,
            "issued_tick": self.issued_tick, "event_tick": self.event_tick,
            "expected_coordinate": self.expected_coordinate, "tolerance": self.tolerance,
            "expected_contact": self.expected_contact, "is_task_pnm": False,
        }


@dataclass(frozen=True, slots=True)
class LocalPredictionComparisonV1:
    """A corresponding sensed result, kept separate from target error and protection."""

    prediction: LocalMotorPredictionV1
    feedback: MotorFeedbackV1
    residual: float | None
    contact_mismatch: bool | None

    @property
    def unexpected(self) -> bool:
        """Unknown channels cannot by themselves establish a prediction mismatch."""
        return (self.residual is not None and abs(self.residual) > self.prediction.tolerance + _EPSILON) or self.contact_mismatch is True

    def as_dict(self) -> dict[str, object]:
        """Return a detached comparison; even an accurate prediction is not success."""
        return {
            "prediction": self.prediction.as_dict(), "sample_id": self.feedback.sample_id,
            "event_tick": self.feedback.event_tick, "available_tick": self.feedback.available_tick,
            "residual": self.residual, "contact_mismatch": self.contact_mismatch, "unexpected": self.unexpected,
        }


@dataclass(frozen=True, slots=True)
class LocalControlEventV1:
    """One significant local event awaiting a later reader, not a chosen task.

    At most four are retained. The event records both the physical occurrence
    and the time local control noticed it. A future cortical reader must preserve
    that identity rather than count its later summary as a second occurrence.
    """

    number: int
    target_id: str
    target_revision: int
    kind: SensorimotorTargetKindV1
    noticed_tick: int
    reason: str
    sample_id: int | None
    event_tick: int | None
    residual: float | None = None

    def as_dict(self) -> dict[str, object]:
        """Return bounded diagnostics with no actuator or focal-selection authority."""
        return {
            "number": self.number, "target_id": self.target_id, "target_revision": self.target_revision,
            "kind": self.kind.value, "noticed_tick": self.noticed_tick, "reason": self.reason,
            "sample_id": self.sample_id, "event_tick": self.event_tick, "residual": self.residual,
            "selects_task": False,
        }


@dataclass(frozen=True, slots=True)
class SensorimotorStepV1:
    """One completed local calculation; the external caller has not yet moved a body."""

    tick: int
    feedback: MotorFeedbackV1 | None
    feedback_disposition: str
    command: MotorCommandV1 | None
    reports: tuple[LocalTargetReportV1, ...]
    predictions: tuple[LocalMotorPredictionV1, ...]
    comparisons: tuple[LocalPredictionComparisonV1, ...]
    significant_events_added: int
    event_overflow: bool

    def as_dict(self) -> dict[str, object]:
        """Describe an issued command separately from observed local target results."""
        return {
            "tick": self.tick, "feedback": self.feedback.as_dict() if self.feedback is not None else None,
            "feedback_disposition": self.feedback_disposition,
            "command": self.command.as_dict() if self.command is not None else None,
            "reports": [item.as_dict() for item in self.reports],
            "predictions": [item.as_dict() for item in self.predictions],
            "comparisons": [item.as_dict() for item in self.comparisons],
            "significant_events_added": self.significant_events_added, "event_overflow": self.event_overflow,
            "is_cognitive_cycle": False, "establishes_task_success": False,
        }


@dataclass(slots=True)
class _Pursuit:
    """Private mutable execution of one fixed/explicitly refined supplied target."""

    reservation: BodyTargetReservationV1
    report: LocalTargetReportV1
    corrections: int = 0
    missing_since: int | None = None
    anomaly_pending: bool = False
    predictions: deque[LocalMotorPredictionV1] = field(default_factory=lambda: deque(maxlen=_HISTORY_LIMIT))


class SensorimotorExecutorV1:
    """Follow up to two compatible targets using only admitted local evidence.

    The H4 fixture has one single-use installation slot and one executor owner
    per BodyMap generation. install() is an explicit test-harness authorization,
    not a cognitive receipt or a result of Navigation. A second fixture install
    is rejected even after completion. H6 instead binds one installation_source
    and uses install_authorized() for each separately consumed focal envelope.
    Fixture and integrated installation modes cannot be mixed.
    H3 cancellation and explicit refinement remain authoritative before each
    drive; a copied reservation cannot restore permission.

    Call step() once at each consecutive external tick. It emits a command but
    never invokes physics. The caller must stop after a possible physical-call
    failure, call abort(), and never retry the old command. No zero drive promises
    balance: passive physical evolution continues in the external provider.
    """

    def __init__(
        self, mapper: BodyTargetMapperV1, *, profile: SensorimotorProfileV1 | None = None, start_tick: int = 0,
        installation_source: MotorInstallationSourceV1 | None = None,
    ) -> None:
        if not isinstance(mapper, BodyTargetMapperV1):
            raise TypeError("mapper must be the owning BodyTargetMapperV1")
        if profile is not None and not isinstance(profile, SensorimotorProfileV1):
            raise TypeError("profile must be SensorimotorProfileV1 or None")
        self._next_tick = _tick(start_tick, "start_tick")
        if installation_source is not None and not callable(getattr(installation_source, "claim_motor_targets", None)):
            raise TypeError("installation_source must expose the narrow consumed-handoff reader")
        self._installation_source = installation_source
        self._last_replaced_reports: tuple[LocalTargetReportV1, ...] = ()
        self._mapper = mapper
        self._profile = profile if profile is not None else SensorimotorProfileV1()
        self._owner = object()
        self._pursuits: dict[SensorimotorTargetKindV1, _Pursuit] = {}
        self._commands: deque[tuple[int, MotorCommandV1 | None]] = deque(maxlen=_HISTORY_LIMIT)
        self._events: list[LocalControlEventV1] = []
        self._event_number = 0
        self._event_overflow = False
        self._trace: deque[SensorimotorStepV1] = deque(maxlen=self._profile.trace_capacity)
        self._installation_attempted = False
        self._installation_count = 0
        self._fault: str | None = None
        mapper.claim_executor_slot(self._owner)

    @property
    def profile(self) -> SensorimotorProfileV1:
        """Return fixed controller settings, not the physical world's private profile."""
        return self._profile

    @property
    def next_tick(self) -> int:
        """Return the next expected caller-supplied boundary, not a running clock."""
        return self._next_tick

    @property
    def installation_count(self) -> int:
        """Count actual successful installations, not local updates or target axes."""
        return self._installation_count

    @property
    def fault(self) -> str | None:
        """Return a sticky fault requiring a fresh owner rather than a blind retry."""
        return self._fault

    @property
    def reports(self) -> tuple[LocalTargetReportV1, ...]:
        """Read immutable local results without advancing, renewing or actuating."""
        return tuple(self._pursuits[kind].report for kind in SensorimotorTargetKindV1 if kind in self._pursuits)

    @property
    def events(self) -> tuple[LocalControlEventV1, ...]:
        """Read unresolved significant events independently of diagnostic retention."""
        return tuple(self._events)

    def trace_snapshot(self) -> tuple[SensorimotorStepV1, ...]:
        """Return a read-only bounded local timeline; omitted rows affect no control."""
        return tuple(self._trace)

    def retained_counts(self) -> dict[str, int]:
        """Count fixed local storage without advancing or clearing any control.

        These are observer diagnostics, not an input to target selection. There
        are at most two pursuits, four commands, four unresolved events and four
        pending predictions per pursuit. Trace capacity is independently bounded.
        """
        return {
            "lower_pursuits": len(self._pursuits), "lower_command_history": len(self._commands),
            "lower_events": len(self._events), "lower_trace": len(self._trace),
            "lower_predictions_per_axis": max((len(item.predictions) for item in self._pursuits.values()), default=0),
            "lower_replaced_reports": len(self._last_replaced_reports),
        }

    def snapshot(self) -> dict[str, object]:
        """Export current ownership, results and finite buffers, without live rights."""
        return {
            "stream": self._mapper.stream.as_dict(), "next_tick": self._next_tick, "profile": self._profile.as_dict(),
            "installation_attempted": self._installation_attempted, "installation_count": self._installation_count,
            "fault": self._fault, "event_overflow": self._event_overflow,
            "reports": [item.as_dict() for item in self.reports], "events": [item.as_dict() for item in self._events],
            "command_history_count": len(self._commands),
            "pending_prediction_counts": {kind.value: len(item.predictions) for kind, item in self._pursuits.items()},
            "trace_retained": len(self._trace), "trace_capacity": self._profile.trace_capacity,
            "durable_learning_updates": 0, "restores_live_authority": False,
            **({"installation_mode": "consumed_handoff",
                "last_replaced_reports": [item.as_dict() for item in self._last_replaced_reports]}
               if self._installation_source is not None else {}),
        }

    def _require_tick(self, at_tick: int) -> int:
        """Reject repeated/skipped updates and prevent all reuse after a sticky fault."""
        tick = _tick(at_tick)
        if self._fault is not None:
            raise RuntimeError("local execution is stopped; create a fresh body/executor generation")
        if tick != self._next_tick:
            raise ValueError("local updates require the next consecutive external tick")
        return tick

    def install(self, reservations: tuple[BodyTargetReservationV1, ...], *, at_tick: int) -> None:
        """Consume the single fixture installation attempt, then validate its targets.

        At most two current original H3 reservations may be installed, with one
        execution/task/envelope and distinct resources. Invalid installation
        ownership consumes this attempt but sends no command. Current missing
        evidence is checked again during step(), not replaced by the target basis.
        The explicit caller is responsible for choosing this fixture experiment;
        merely decoding an H1 committed-target description never invokes install.
        """
        tick = self._require_tick(at_tick)
        if self._installation_source is not None:
            raise ValueError("integrated executors cannot use fixture installation")
        if self._installation_attempted:
            raise ValueError("this executor's installation slot was already consumed")
        self._installation_attempted = True
        self._pursuits = self._prepare_installation(reservations, tick)
        self._installation_count = 1

    def _prepare_installation(
        self, reservations: tuple[BodyTargetReservationV1, ...], tick: int,
    ) -> dict[SensorimotorTargetKindV1, _Pursuit]:
        """Validate original BodyMap ownership before changing local pursuits."""
        if not isinstance(reservations, tuple) or not 1 <= len(reservations) <= 2:
            raise ValueError("install requires one or two original BodyMap reservations")
        prepared: dict[SensorimotorTargetKindV1, _Pursuit] = {}
        execution: str | None = None
        origin: TargetOriginV1 | None = None
        for reservation in reservations:
            self._mapper.validate_reservation(reservation, at_tick=tick)
            committed = reservation.current
            target = committed.target
            if target.kind in prepared:
                raise ValueError("only one installed target per body resource")
            if execution is not None and (committed.execution_id != execution or target.origin != origin):
                raise ValueError("installed axes must share an execution and task envelope")
            execution, origin = committed.execution_id, target.origin
            report = LocalTargetReportV1(committed, LocalTargetDispositionV1.PENDING, tick, "installed_supplied_target")
            prepared[target.kind] = _Pursuit(reservation, report)
        return prepared

    @property
    def last_replaced_reports(self) -> tuple[LocalTargetReportV1, ...]:
        """Return at most two prior local results, without rewriting an old commitment."""
        return self._last_replaced_reports

    def install_authorized(self, reservations: tuple[BodyTargetReservationV1, ...], *, at_tick: int) -> None:
        """Install one newly consumed focal envelope through the bound handoff reader.

        The grant is spent before target/ownership validation. Failure stops this
        executor and cannot be retried. Successful replacement keeps prior local
        results separately, retains issued-command history for in-transit sensing,
        and starts fresh finite targets only under this new focal authorization.
        No PNM, task choice or physical provider is read here. Historical steps
        retain their original predictions; unresolved replaced forecasts are not
        reclassified as successful observations.
        """
        tick = self._require_tick(at_tick)
        if self._installation_source is None:
            raise ValueError("fixture executors have no cognitive installation source")
        try:
            authorized = self._installation_source.claim_motor_targets()
            self._installation_attempted = True
            prepared = self._prepare_installation(reservations, tick)
            if len(authorized) != len(reservations) or any(
                target is not reservation.current for target, reservation in zip(authorized, reservations)
            ):
                raise ValueError("installation does not carry the original consumed target objects")
            previous: list[LocalTargetReportV1] = []
            for pursuit in self._pursuits.values():
                if pursuit.report.disposition not in _TERMINAL:
                    self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, "replaced_by_focal_authorization", None)
                previous.append(pursuit.report)
            self._last_replaced_reports = tuple(previous)
            self._pursuits = prepared
            self._installation_count += 1
        except (TypeError, ValueError, RuntimeError, OverflowError):
            self.abort("authorized_installation_failed_no_retry", at_tick=tick)
            raise

    def cancel_execution(self, *, at_tick: int) -> tuple[LocalTargetReportV1, ...]:
        """Revoke this execution explicitly; neutral drive does not freeze the world.

        Terminal local results remain terminal. Expired or already superseded
        BodyMap reservations cannot be revived. This protected stop needs no new
        task selection and does not itself cancel a persistent cognitive task.
        """
        tick = self._require_tick(at_tick)
        for pursuit in self._pursuits.values():
            try:
                self._mapper.cancel(pursuit.reservation, at_tick=tick)
            except ValueError:
                pass  # Already expired/revoked: cancellation cannot restore it.
            if pursuit.report.disposition not in _TERMINAL:
                self._report(pursuit, LocalTargetDispositionV1.CANCELLED, tick, "explicit_execution_cancel", None)
            pursuit.predictions.clear()
        return self.reports

    def replace_target(self, reservation: BodyTargetReservationV1, *, at_tick: int) -> None:
        """Accept an explicit current H3 refinement without renewing original permission.

        Only the same live target and original reservation may be refined. A
        materially new target needs later task authorization, not this method.
        Old prediction records in prior step snapshots remain immutable; pending
        old-revision forecasts are discarded as superseded, never rewritten.
        """
        tick = self._require_tick(at_tick)
        self._mapper.validate_reservation(reservation, at_tick=tick)
        kind = reservation.current.target.kind
        pursuit = self._pursuits.get(kind)
        if pursuit is None or pursuit.report.disposition in _TERMINAL:
            raise ValueError("no live installed target on this resource")
        previous = pursuit.reservation
        if reservation.initial != previous.initial or reservation.current.target.revision <= previous.current.target.revision:
            raise ValueError("replacement is not a newer refinement of the installed target")
        pursuit.reservation = reservation
        pursuit.predictions.clear()
        pursuit.anomaly_pending = False
        pursuit.report = LocalTargetReportV1(
            reservation.current, LocalTargetDispositionV1.ACTIVE, tick, "accepted_bodymap_refinement",
            correction_count=pursuit.corrections,
        )

    def cancel_target(self, kind: SensorimotorTargetKindV1, *, at_tick: int) -> None:
        """Cancel the named live target before the next drive; past motion stays real."""
        tick = self._require_tick(at_tick)
        if not isinstance(kind, SensorimotorTargetKindV1) or kind not in self._pursuits:
            raise ValueError("no installed target for this family")
        pursuit = self._pursuits[kind]
        if pursuit.report.disposition in _TERMINAL:
            raise ValueError("target pursuit is already terminal")
        self._mapper.cancel(pursuit.reservation, at_tick=tick)
        self._report(pursuit, LocalTargetDispositionV1.CANCELLED, tick, "explicit_cancel", None)
        pursuit.predictions.clear()

    def acknowledge_events(self, through_number: int) -> None:
        """Explicitly consume already read events; inspection alone never clears them.

        This future source-reader seam changes only latch occupancy. It cannot
        undo a protective stop, reset an anomalous-correction budget, clear an
        overflow fault or restore an expired target. No source is updated here.
        """
        number = _tick(through_number, "through_number")
        if number > self._event_number:
            raise ValueError("cannot acknowledge an event that has not occurred")
        self._events = [item for item in self._events if item.number > number]

    def abort(self, reason: str, *, at_tick: int) -> None:
        """Latch a nonretryable execution fault, including uncertain physical effects.

        Called by the external runner after any failed advance/admission. This
        stops future command generation; it does not roll back physical motion
        or claim that an attempted command had no effect. No world is called.
        """
        tick = _tick(at_tick)
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("abort needs a nonempty reason")
        self._fault = reason.strip()[:100]
        for pursuit in self._pursuits.values():
            if pursuit.report.disposition not in _TERMINAL:
                self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, max(tick, pursuit.report.reported_tick),
                             "execution_fault_effects_unresolved", None)
            pursuit.predictions.clear()

    @staticmethod
    def _report(
        pursuit: _Pursuit, disposition: LocalTargetDispositionV1, tick: int,
        reason: str, feedback: MotorFeedbackV1 | None,
    ) -> None:
        """Save a local report without ever changing the supplied target or body facts."""
        pursuit.report = LocalTargetReportV1(
            pursuit.reservation.current, disposition, tick, reason, feedback, pursuit.corrections,
        )

    def _event(
        self, pursuit: _Pursuit, tick: int, reason: str, feedback: MotorFeedbackV1 | None, *, residual: float | None = None,
    ) -> None:
        """Latch one significant occurrence; overflow is sticky and forces neutral output."""
        target = pursuit.reservation.current.target
        sample = feedback.sample_id if feedback is not None else None
        if any(item.target_id == target.target_id and item.target_revision == target.revision and
               item.sample_id == sample and item.reason == reason for item in self._events):
            return
        if len(self._events) >= _EVENT_LIMIT or self._event_number >= _MAX_TICK:
            self._event_overflow = True
            return
        self._event_number += 1
        self._events.append(LocalControlEventV1(
            self._event_number, target.target_id, target.revision, target.kind, tick, reason,
            sample, feedback.event_tick if feedback is not None else None, residual,
        ))

    def _compare(self, pursuit: _Pursuit, feedback: MotorFeedbackV1 | None) -> LocalPredictionComparisonV1 | None:
        """Consume an event-matched forecast once; unknown channels stay unresolved."""
        if feedback is None:
            return None
        match = next((item for item in pursuit.predictions if item.event_tick == feedback.event_tick), None)
        # Older unseen predictions are unresolved/expired, not confirmed by this newer event.
        pursuit.predictions = deque((item for item in pursuit.predictions if item.event_tick > feedback.event_tick),
                                    maxlen=_HISTORY_LIMIT)
        if match is None:
            return None
        value = _coordinate(feedback, match.kind)
        residual = None if value is None else value - match.expected_coordinate
        contact_mismatch: bool | None = None
        if match.expected_contact is not None and feedback.support_contact is not None:
            contact_mismatch = feedback.support_contact is not match.expected_contact
        return LocalPredictionComparisonV1(match, feedback, residual, contact_mismatch)

    def _protect_prediction(
        self, pursuit: _Pursuit, comparison: LocalPredictionComparisonV1 | None, tick: int,
    ) -> None:
        """Apply the optional discrepancy consumer, separate from basic body protection."""
        if comparison is None or not comparison.unexpected or not self._profile.prediction_protection:
            return
        feedback = comparison.feedback
        reason = "unexpected_contact_loss" if comparison.contact_mismatch is True else "unexpected_local_motion"
        self._event(pursuit, tick, reason, feedback, residual=comparison.residual)
        # Forecasts spanning this already discovered disturbance must not count it again.
        pursuit.predictions = deque(
            (item for item in pursuit.predictions if item.basis_event_tick >= feedback.event_tick), maxlen=_HISTORY_LIMIT,
        )
        if comparison.contact_mismatch is True:
            self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, reason, feedback)
        else:
            pursuit.anomaly_pending = True

    def _known_commands(self, event_tick: int, tick: int) -> tuple[MotorCommandV1 | None, ...] | None:
        """Return every actually issued interval after a measurement, or no estimate.

        A missing command-history interval is not silently treated as zero. The
        normal two-tick evidence age fits inside this independent four-row buffer.
        """
        rows = tuple((index, command) for index, command in self._commands if event_tick <= index < tick)
        if tuple(index for index, _command in rows) != tuple(range(event_tick, tick)):
            return None
        return tuple(command for _index_value, command in rows)

    def _forecast(
        self, pursuit: _Pursuit, feedback: MotorFeedbackV1, command: MotorCommandV1 | None, tick: int,
    ) -> LocalMotorPredictionV1 | None:
        """Predict one near-term consequence from sensing and issued-command history.

        A fixed local gravity drift approximation holds measured loading constant
        across the short unseen interval. It is not a call to the plant or a claim
        of exact world knowledge. Its error is tested against H1's stated bounds.
        """
        target = pursuit.reservation.current.target
        value = _coordinate(feedback, target.kind)
        known = self._known_commands(feedback.event_tick, tick)
        if value is None or known is None:
            return None
        commands = (*known, command)
        loading = feedback.useful_loading
        if target.kind is _ORIENTATION and loading is None:
            return None
        initial_tilt = feedback.body_tilt_degrees
        contact: bool | None = True if feedback.support_contact is True else None
        for issued in commands:
            increment = _motor_rate(target.kind) * _drive(issued, target.kind)
            if target.kind is _ORIENTATION and loading is not None:
                increment += 12.0 * math.sin(math.radians(value)) * (1.0 - loading)
            value += self._mapper.tick_seconds * increment
            value = max(-90.0, min(90.0, value)) if target.kind is _ORIENTATION else max(0.0, min(1.0, value))
            if _drive(issued, _EXTENSION) < 0.0 or initial_tilt is None or initial_tilt * _drive(issued, _ORIENTATION) > 0.0:
                contact = None
        return LocalMotorPredictionV1(
            target.target_id, target.revision, target.kind, feedback.sample_id, feedback.event_tick,
            tick, tick + 1, value, 5.0 if target.kind is _ORIENTATION else 0.04, contact,
        )

    def _observed_achievement(self, pursuit: _Pursuit, feedback: MotorFeedbackV1 | None, tick: int) -> bool:
        """Recognize a corresponding measured endpoint, never infer it from a drive."""
        if feedback is None:
            return False
        reserved = pursuit.reservation
        target = reserved.current.target
        value = _coordinate(feedback, target.kind)
        if value is None or not reserved.updated_tick <= feedback.event_tick <= reserved.current.expires_at_tick:
            return False
        if abs(value - target.endpoint) > target.tolerance + _EPSILON:
            return False
        reason = "observed_target_achieved" if tick < reserved.current.expires_at_tick else "observed_achievement_before_expiry"
        self._report(pursuit, LocalTargetDispositionV1.ACHIEVED, tick, reason, feedback)
        pursuit.predictions.clear()
        return True

    def _axis_command(self, pursuit: _Pursuit, feedback: MotorFeedbackV1 | None, tick: int) -> float:
        """Calculate one axis's bounded reactive response or an explicit local stop."""
        reservation = pursuit.reservation
        committed = reservation.current
        target = committed.target
        disposition = pursuit.report.disposition
        if disposition in _TERMINAL:
            if disposition is LocalTargetDispositionV1.EXPIRED and tick <= committed.expires_at_tick + 2:
                self._observed_achievement(pursuit, feedback, tick)
            return 0.0
        if tick >= committed.expires_at_tick:
            if not self._observed_achievement(pursuit, feedback, tick):
                self._report(pursuit, LocalTargetDispositionV1.EXPIRED, tick, "lease_expired_no_new_pursuit", feedback)
            pursuit.predictions.clear()
            return 0.0
        try:
            refusal = self._mapper.execution_refusal(reservation, at_tick=tick)
        except (ValueError, TypeError):
            self._report(pursuit, LocalTargetDispositionV1.CANCELLED, tick, "bodymap_reservation_revoked_or_revised", None)
            pursuit.predictions.clear()
            return 0.0
        if refusal in _MISSING_REASONS or feedback is None:
            if pursuit.missing_since is None:
                pursuit.missing_since = tick
            if tick - pursuit.missing_since >= 2:
                self._report(pursuit, LocalTargetDispositionV1.UNAVAILABLE, tick, "current_feedback_timeout", None)
                self._event(pursuit, tick, "current_feedback_timeout", None)
                pursuit.predictions.clear()
            else:
                self._report(pursuit, LocalTargetDispositionV1.UNRESOLVED, tick, "current_feedback_unavailable", None)
            return 0.0
        pursuit.missing_since = None
        if refusal is not None:
            self._report(pursuit, LocalTargetDispositionV1.BLOCKED, tick, refusal, feedback)
            self._event(pursuit, tick, refusal, feedback)
            pursuit.predictions.clear()
            return 0.0
        value = _coordinate(feedback, target.kind)
        if value is None:
            raise RuntimeError("BodyMap permitted a target without its measured coordinate")
        if abs(value - target.basis_coordinate) > target.max_displacement + _EPSILON:
            self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, "original_excursion_exceeded", feedback)
            self._event(pursuit, tick, "original_excursion_exceeded", feedback)
            pursuit.predictions.clear()
            return 0.0
        if self._observed_achievement(pursuit, feedback, tick):
            return 0.0
        known = self._known_commands(feedback.event_tick, tick)
        if known is None:
            self._report(pursuit, LocalTargetDispositionV1.UNRESOLVED, tick, "command_history_unavailable", feedback)
            return 0.0
        # Pending drive accounting is not measured motion or evidence of achievement.
        scale = _motor_rate(target.kind)
        estimated = value + self._mapper.tick_seconds * scale * sum(_drive(item, target.kind) for item in known)
        permitted_rate = target.max_rate
        if pursuit.anomaly_pending:
            if pursuit.corrections >= target.max_corrections:
                self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, "anomalous_correction_budget_exhausted", feedback)
                pursuit.predictions.clear()
                return 0.0
            permitted_rate *= 0.5
        delta = max(-permitted_rate * self._mapper.tick_seconds,
                    min(permitted_rate * self._mapper.tick_seconds, target.endpoint - estimated))
        lower = max(reservation.capability.minimum_coordinate, target.basis_coordinate - target.max_displacement)
        upper = min(reservation.capability.maximum_coordinate, target.basis_coordinate + target.max_displacement)
        if not lower - _EPSILON <= estimated + delta <= upper + _EPSILON:
            self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, "command_would_exceed_original_bounds", feedback)
            self._event(pursuit, tick, "command_would_exceed_original_bounds", feedback)
            return 0.0
        response = max(-1.0, min(1.0, delta / (scale * self._mapper.tick_seconds)))
        reason = "reactive_target_following" if response != 0.0 else "awaiting_sensed_target_confirmation"
        if pursuit.anomaly_pending and response != 0.0:
            pursuit.corrections += 1
            pursuit.anomaly_pending = False
            reason = "bounded_anomalous_correction"
        progress = abs(value - target.endpoint) < abs(target.offset) - target.tolerance
        disposition = LocalTargetDispositionV1.PARTIAL if progress else LocalTargetDispositionV1.ACTIVE
        self._report(pursuit, disposition, tick, reason, feedback)
        return response

    def step(self, feedback: MotorFeedbackV1 | None, *, at_tick: int) -> SensorimotorStepV1:
        """Calculate one local update; the outer driver subsequently advances the body.

        Invalid/future/foreign sensing fails closed with a sticky fault. Valid
        cached evidence retains its acquisition time and must pass BodyMap's age
        rule. Missing channels withhold only the affected axis. Repeated calls at
        a used tick cannot issue another command. The output records predictions
        before the corresponding physical event; later sensing alone can score it.
        """
        tick = self._require_tick(at_tick)
        before_events = self._event_number
        try:
            disposition = self._mapper.update_feedback(feedback, at_tick=tick)
            current = self._mapper.current_feedback(at_tick=tick)
            comparisons: list[LocalPredictionComparisonV1] = []
            responses: dict[SensorimotorTargetKindV1, float] = {}
            for kind in SensorimotorTargetKindV1:
                pursuit = self._pursuits.get(kind)
                if pursuit is None:
                    continue
                comparison = self._compare(pursuit, current)
                if comparison is not None:
                    comparisons.append(comparison)
                if pursuit.report.disposition not in _TERMINAL and tick < pursuit.reservation.current.expires_at_tick:
                    try:
                        self._mapper.validate_reservation(pursuit.reservation, at_tick=tick)
                    except (ValueError, TypeError):
                        pass  # _axis_command records revocation; an old forecast cannot restore permission.
                    else:
                        self._protect_prediction(pursuit, comparison, tick)
                responses[kind] = self._axis_command(pursuit, current, tick)
            if self._event_overflow:
                responses.clear()
                for pursuit in self._pursuits.values():
                    if pursuit.report.disposition not in _TERMINAL:
                        self._report(pursuit, LocalTargetDispositionV1.INTERRUPTED, tick, "significant_event_overflow", current)
                        pursuit.predictions.clear()
            orientation = responses.get(_ORIENTATION, 0.0)
            extension = responses.get(_EXTENSION, 0.0)
            command: MotorCommandV1 | None = None
            if orientation != 0.0 or extension != 0.0:
                command = MotorCommandV1(self._mapper.stream, tick + 1, tick, orientation, extension)
            predictions: list[LocalMotorPredictionV1] = []
            if current is not None:
                for pursuit in self._pursuits.values():
                    if pursuit.report.disposition in _TERMINAL:
                        continue
                    prediction = self._forecast(pursuit, current, command, tick)
                    if prediction is not None:
                        if len(pursuit.predictions) >= _HISTORY_LIMIT:
                            raise RuntimeError("unresolved local prediction window overflow")
                        pursuit.predictions.append(prediction)
                        predictions.append(prediction)
            result = SensorimotorStepV1(
                tick, current, disposition, command, self.reports, tuple(predictions), tuple(comparisons),
                self._event_number - before_events, self._event_overflow,
            )
            self._commands.append((tick, command))
            self._trace.append(result)
            self._next_tick = tick + 1
            return result
        except (TypeError, ValueError, RuntimeError, OverflowError) as exc:
            self.abort(f"local_input_or_execution_fault:{type(exc).__name__}", at_tick=tick)
            raise
