#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1G-A: bounded Righting evidence, not a universal evaluator or learner.

The opt-in hierarchy calls this domain-local service in C2 with already frozen
input. It compares the original sparse forecast with a matching physical event,
keeps the authorized body contribution distinct, and accumulates supported task
dwell from distinct focal samples. It cannot select a source/task, move a body,
read the world, tune a parameter or change durable knowledge. Rich causal
interpretation and mismatch-to-Attention remain 1G-B; the learning hook is 1G-C.

Profile righting_outcomes_v1 fixes three samples spanning eight .05-second ticks,
a maximum eight-tick supported gap, and unchanged activity criteria. Endpoint
PNM comparison requires an acquisition at the original cutoff+horizon; early
partial movement is not an endpoint failure. That event may arrive up to eight
ticks later. Missing evidence expires unresolved. Predictions use fixed residual
tolerances (1 degree, .02 extension, .10 loading, .10 destabilization); they are
engineering reference checks, not biological error constants or calibrated odds.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from nca8_body_targets import BodyMovementRequestV1, BodyTargetProposalV1
from nca8_maps import MotorSupportConfigurationV1
from nca8_prediction import SupportPreviewV1
from nca8_righting import RightingApplicationV1, RightingContextV1, RightingTaskV1, righting_support_adequacy_v1
from nca8_sensorimotor_contracts import (
    CommittedBodyTargetV1, LocalTargetDispositionV1, LocalTargetReportV1, SensorimotorTargetKindV1,
)

__version__ = "0.1.0"
__all__ = [
    "RightingIntervalEvidenceV1", "RightingClaimRegistrationV1", "RightingClaimOutcomeV1",
    "RightingTaskAssessmentV1", "RightingOutcomeRuntimeV1", "__version__",
]

_ORIENTATION = SensorimotorTargetKindV1.ORIENTATION_ADJUST
_EXTENSION = SensorimotorTargetKindV1.SUPPORT_EXTENSION
_RELATIONS = (
    ("tilt", "predicted_tilt", "body_tilt_degrees", 1.0),
    ("extension", "predicted_extension", "support_extension", 0.02),
    ("loading", "predicted_loading", "useful_loading", 0.10),
    ("destabilization", "predicted_destabilization", "destabilization", 0.10),
    ("contact", "expected_contact", "support_contact", 0.0),
)


def _tick(value: int, name: str = "tick") -> int:
    """Reject malformed physical indices without silently coercing values."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError(f"{name} must be a bounded nonnegative integer")
    return value


@dataclass(frozen=True, slots=True)
class RightingIntervalEvidenceV1:
    """Bookkeeping for one normally returned physical call, not an observed outcome.

    The outer driver constructs this only after its one physical interval returns
    and admission succeeds. Reports are the executor's pre-call immutable results;
    command is what was issued, not proof of movement. Deliveries contain only
    canonical agent-visible sensor packets available by this return boundary.
    No simulator state, evaluator answer or sensor-side action identifier exists.
    """

    tick: int
    command: MotorCommandV1 | None
    reports: tuple[LocalTargetReportV1, ...]
    deliveries: tuple[MotorFeedbackV1, ...]

    def __post_init__(self) -> None:
        _tick(self.tick)
        if self.command is not None and (not isinstance(self.command, MotorCommandV1) or self.command.issued_tick != self.tick):
            raise ValueError("returned interval must retain its original issued command")
        if not isinstance(self.reports, tuple) or len(self.reports) > 2 or any(
            not isinstance(item, LocalTargetReportV1) or item.reported_tick > self.tick for item in self.reports
        ):
            raise ValueError("returned interval needs at most two already available local reports")
        if not isinstance(self.deliveries, tuple) or len(self.deliveries) > 16 or any(
            not isinstance(item, MotorFeedbackV1) or item.available_tick > self.tick + 1 for item in self.deliveries
        ):
            raise ValueError("returned interval contains invalid or future deliveries")


@dataclass(frozen=True, slots=True)
class RightingClaimRegistrationV1:
    """Immutable pre-handoff comparison basis, with original and authorized meanings.

    A changed target does not edit the IP's forecast. Incompatible coordinates
    and their coupled support forecasts are explicitly unevaluable; an unchanged
    coordinate can remain comparable. This record grants no installation right.
    """

    preview: SupportPreviewV1
    request: BodyMovementRequestV1
    targets: tuple[CommittedBodyTargetV1, ...]
    compatible_relations: tuple[str, ...]
    unevaluable_relations: tuple[str, ...]

    @property
    def due_tick(self) -> int:
        """Read the original physical endpoint, independent of later focal cadence."""
        return self.preview.basis.cutoff_tick + self.preview.horizon_ticks

    @property
    def expires_at_tick(self) -> int:
        """Allow a finite eight-tick delivery delay, not an extended movement lease."""
        return self.due_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Export the exact old prediction and mapped target without hindsight repair."""
        return {
            "pnm_id": self.preview.pnm.pnm_id, "original_preview": self.preview.as_dict(),
            "proposed_request": self.request.as_dict(), "authorized_targets": [item.as_dict() for item in self.targets],
            "compatible_relations": list(self.compatible_relations), "unevaluable_relations": list(self.unevaluable_relations),
            "endpoint_event_tick": self.due_tick, "last_acceptable_availability_tick": self.expires_at_tick,
            "authorization_disposition": "not_applied" if not self.targets else (
                "partly_unevaluable" if self.unevaluable_relations else "compatible"
            ), "grants_motor_authority": False,
        }


@dataclass(frozen=True, slots=True)
class RightingClaimOutcomeV1:
    """One terminal correspondence disposition; never a whole-task or learning verdict."""

    number: int
    registration: RightingClaimRegistrationV1
    status: str
    evaluated_tick: int
    evidence: MotorFeedbackV1 | None
    relations: tuple[tuple[str, str], ...]
    command_intervals: int
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Keep prediction fit, execution exposure and uncertain causation separate."""
        return {
            "number": self.number, "registration": self.registration.as_dict(), "status": self.status,
            "evaluated_tick": self.evaluated_tick, "evidence": self.evidence.as_dict() if self.evidence else None,
            "relation_results": dict(self.relations), "nonnull_command_intervals": self.command_intervals,
            "reason": self.reason, "action_causation": "uncertain", "establishes_task_completion": False,
            "durable_learning_updates": 0,
        }


@dataclass(frozen=True, slots=True)
class RightingTaskAssessmentV1:
    """Current evidential progress and bounded dwell under one fixed task requirement.

    Progress is a relation-wise measured change, not credit for a particular
    command. supported_samples are genuine focal acquisitions, not rereads or
    all intermediate motor samples. The task owner rechecks a complete proof
    before changing lifecycle; this service cannot install a task or a target.
    """

    task_id: str | None
    context: RightingContextV1
    cutoff_tick: int
    feedback: MotorFeedbackV1 | None
    status: str
    relation_changes: tuple[tuple[str, str], ...]
    supported_samples: tuple[MotorFeedbackV1, ...]
    reason: str

    @property
    def completion_supported(self) -> bool:
        """Expose a supported completion proposal, not authority to actuate."""
        return self.task_id is not None and self.status == "complete"

    def as_dict(self) -> dict[str, object]:
        """Export current evidence while retaining the original physical sample times."""
        samples = self.supported_samples
        return {
            "task_id": self.task_id, "context": self.context.as_dict(), "cutoff_tick": self.cutoff_tick,
            "status": self.status, "feedback": self.feedback.as_dict() if self.feedback else None,
            "relation_changes": dict(self.relation_changes), "supported_sample_ids": [item.sample_id for item in samples],
            "supported_event_ticks": [item.event_tick for item in samples],
            "supported_span_ticks": samples[-1].event_tick - samples[0].event_tick if samples else 0,
            "completion_supported": self.completion_supported, "reason": self.reason, "action_causation": "uncertain",
        }


@dataclass(slots=True)
class _PendingClaim:
    """Small owner-local lifecycle; it is not another current PNM."""

    registration: RightingClaimRegistrationV1
    installed: bool = False
    command_intervals: int = 0
    ended_tick: int | None = None
    end_reason: str | None = None


class RightingOutcomeRuntimeV1:
    """Retain at most eight claims, one execution basis and three dwell samples.

    register() runs before handoff; installed() records a consumed, successful
    installation, not movement. consume_intervals() runs on frozen C2 input.
    assess_task() examines only the eligible source, and returns a completion
    proposal that Righting itself must validate. No ranking, learned update,
    provider call or hidden interpretation occurs. Overflow fails explicitly.
    A new generation constructs a new owner; diagnostic export is not restoration.
    """

    def __init__(self, stream: MotorStreamRefV1, *, compare_predictions: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(compare_predictions, bool):
            raise TypeError("outcomes require a typed stream and Boolean comparison setting")
        self.stream = stream
        self.compare_predictions = compare_predictions
        self._pending: dict[str, _PendingClaim] = {}
        self._history: deque[RightingClaimOutcomeV1] = deque(maxlen=32)
        self._last_registration_cycle = 0
        self._outcome_number = 0
        self._last_interval = -1
        self._last_command_id = 0
        self._last_consumption_cutoff = -1
        self._recent_feedback: deque[MotorFeedbackV1] = deque(maxlen=16)
        self._installed_targets: tuple[CommittedBodyTargetV1, ...] = ()
        self._awaiting: str | None = None
        self._task: RightingTaskV1 | None = None
        self._previous: MotorFeedbackV1 | None = None
        self._last_delivery: MotorFeedbackV1 | None = None
        self._dwell: tuple[MotorFeedbackV1, ...] = ()
        self._command_ticks: deque[int] = deque(maxlen=16)
        self._last_assessment_tick = -1
        self.last_assessment: RightingTaskAssessmentV1 | None = None

    def retained_counts(self) -> dict[str, int]:
        """Read actual bounded owner storage independently of trace retention."""
        return {
            "outcome_pending_claims": len(self._pending), "outcome_terminal_history": len(self._history),
            "outcome_installed_targets": len(self._installed_targets), "outcome_dwell_samples": len(self._dwell),
            "outcome_recent_feedback": len(self._recent_feedback), "outcome_command_ticks": len(self._command_ticks),
        }

    def history(self) -> tuple[RightingClaimOutcomeV1, ...]:
        """Return immutable terminal correspondence records, never replay instructions."""
        return tuple(self._history)

    def pending(self) -> tuple[RightingClaimRegistrationV1, ...]:
        """Return preserved original sparse claims; no current future is selected here."""
        return tuple(item.registration for item in self._pending.values())

    def _bind_task(self, task: RightingTaskV1 | None) -> None:
        """Clear task-specific temporary evidence on a genuine context/task change."""
        if task is not None and (not isinstance(task, RightingTaskV1) or task.stream != self.stream):
            raise ValueError("outcome task belongs to another stream or generation")
        if (task.task_id if task else None) != (self._task.task_id if self._task else None):
            self._dwell, self._previous = (), None
            self._command_ticks.clear()
        elif task is not None and self._task is not None and (task.context != self._task.context or task.source_map_ref != self._task.source_map_ref):
            raise ValueError("a continuing task cannot change its criterion or source")
        self._task = task

    def register(
        self, application: RightingApplicationV1, proposal: BodyTargetProposalV1, targets: tuple[CommittedBodyTargetV1, ...],
    ) -> RightingClaimRegistrationV1:
        """Preserve a new forecast and reconcile mapped meaning before handoff.

        Check actual origin, original reservation payload and physical cutoff.
        A veto closes as not-applied. Narrowing never replaces the forecast with
        an easier one; changed/coupled relations are marked unevaluable before
        any installation. Eight unresolved claims is a hard capacity, not a
        silent eviction policy. Disabled comparison still preserves this integrity
        record while suppressing only the substantive endpoint comparison.
        """
        if not isinstance(application, RightingApplicationV1) or not isinstance(proposal, BodyTargetProposalV1):
            raise TypeError("registration requires the selected application and BodyMap proposal")
        preview, request = application.projection, application.contribution
        if request.origin.stream != self.stream or proposal.request != request or application.task.stream != self.stream:
            raise ValueError("claim and authorization have different task/action/generation identities")
        if preview.basis.stream != self.stream or preview.task_id != application.task.task_id:
            raise ValueError("forecast does not belong to the originating task")
        if preview.basis.source_map_ref != application.task.source_map_ref or preview.context_id != application.task.context.context_id:
            raise ValueError("forecast source or fixed task requirement changed")
        if preview.basis.cutoff_tick != proposal.created_tick or preview.pnm.created_cycle <= self._last_registration_cycle:
            raise ValueError("claim registration is stale, duplicate or uses a different cutoff")
        if not isinstance(targets, tuple) or len(targets) != len(proposal.bindings) or any(
            not isinstance(target, CommittedBodyTargetV1) or target.target is not binding.target
            or target.committed_tick != proposal.created_tick for target, binding in zip(targets, proposal.bindings)
        ):
            raise ValueError("claim must retain the exact authorized target objects")
        if len({target.execution_id for target in targets}) > 1:
            raise ValueError("authorized axes must share one execution identity")
        if self._awaiting is not None:
            raise RuntimeError("previous claim still awaits installation disposition")
        if len(self._pending) >= 8:
            raise OverflowError("eight unresolved task claims; no silent eviction or additional dispatch")
        self._bind_task(application.task)
        if self._previous is None:
            self._previous = preview.basis.feedback
        changed: set[str] = set()
        endpoints = {target.target.kind: target.target.endpoint for target in targets}
        for kind, name, requested in ((_ORIENTATION, "tilt", request.desired_tilt_degrees),
                                      (_EXTENSION, "extension", request.desired_extension)):
            if requested is not None and (kind not in endpoints or abs(endpoints[kind] - requested) > 1e-12):
                changed.add(name)
        if changed:
            changed.update(("loading", "destabilization", "contact"))
        predicted = tuple(name for name, field, _, _ in _RELATIONS if getattr(preview, field) is not None)
        registration = RightingClaimRegistrationV1(
            preview, request, targets, tuple(name for name in predicted if name not in changed),
            tuple(name for name in predicted if name in changed),
        )
        claim_id = preview.pnm.pnm_id
        self._pending[claim_id] = _PendingClaim(registration)
        self._last_registration_cycle = preview.pnm.created_cycle
        if targets:
            self._awaiting = claim_id
        else:
            self._finish(claim_id, "not_applied", proposal.created_tick, None, (), "BodyMap vetoed every requested contribution")
        return registration

    def installed(self, registration: RightingClaimRegistrationV1, *, at_tick: int) -> None:
        """Record one completed installation, without inferring any physical effect."""
        tick = _tick(at_tick)
        if not isinstance(registration, RightingClaimRegistrationV1):
            raise TypeError("installation requires an original claim registration")
        claim_id = registration.preview.pnm.pnm_id
        pending = self._pending.get(claim_id)
        if claim_id != self._awaiting or pending is None or pending.registration is not registration or pending.installed:
            raise ValueError("installation does not name this owner's one awaiting original claim")
        if tick != registration.preview.basis.cutoff_tick:
            raise ValueError("installation occurred outside the original handoff boundary")
        self.end_execution(at_tick=tick, reason="replacement")
        pending.installed = True
        self._installed_targets = registration.targets
        self._awaiting = None
        if not registration.compatible_relations:
            self._finish(claim_id, "unevaluable_authorization", tick, None, (), "mapped contribution changed every predicted relation")
        elif not self.compare_predictions:
            self._finish(claim_id, "comparison_disabled", tick, None, (), "only endpoint prediction comparison is disabled")

    def reject_uninstalled(self) -> None:
        """Close a failed/cancelled internal handoff known not to have installed anything.

        Only the one awaiting grant is affected; earlier installed claims and
        possible physical consequences are not relabelled as unapplied.
        """
        claim_id = self._awaiting
        if claim_id is not None:
            pending = self._pending[claim_id]
            self._finish(claim_id, "not_applied", pending.registration.preview.basis.cutoff_tick, None, (),
                         "internal handoff ended before lower installation")
            self._awaiting = None

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """End a prior execution without erasing already realized endpoint obligations.

        Replacement/cancellation exactly at the endpoint permits its delayed
        sensor result. Ending earlier makes the uncompleted forecast interrupted,
        not an observed failure. Actual past movement remains in the history.
        """
        tick = _tick(at_tick)
        if reason not in {"cancelled", "replacement", "execution_unknown", "not_applied"}:
            raise ValueError("unsupported execution disposition")
        origin = self._installed_targets[0].target.origin if self._installed_targets else None
        for claim_id, pending in tuple(self._pending.items()):
            registration = pending.registration
            if not pending.installed:
                if reason in {"not_applied", "execution_unknown"}:
                    self._finish(claim_id, "not_applied", tick, None, (), "no physical interval was attempted before installation failed")
                    self._awaiting = None
                continue
            if registration.request.origin != origin:
                continue
            if reason == "execution_unknown":
                self._finish(claim_id, "execution_unknown", tick, None, (), "physical call may have had effects; no retry or attribution")
            elif tick < registration.due_tick:
                pending.ended_tick, pending.end_reason = tick, reason
                if tick <= self._last_interval + 1:
                    self._finish(claim_id, "interrupted" if pending.command_intervals else "cancelled", tick, None, (),
                                 f"{reason} before the original predicted physical endpoint")

    def _validate_intervals(self, intervals: tuple[RightingIntervalEvidenceV1, ...], cutoff: int) -> None:
        """Check all interval identities before any claim or dwell bookkeeping changes."""
        if not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("at most sixteen frozen returned intervals are permitted")
        previous_command_id = self._last_command_id
        known = {item.sample_id: item for item in self._recent_feedback}
        for index, interval in enumerate(intervals):
            if not isinstance(interval, RightingIntervalEvidenceV1) or interval.tick != self._last_interval + index + 1:
                raise ValueError("returned physical intervals must be contiguous and consumed exactly once")
            if interval.tick + 1 > cutoff:
                raise ValueError("a future physical interval cannot enter this frozen cycle")
            command = interval.command
            if command is not None:
                command.validate_for_update(stream=self.stream, now_tick=interval.tick, previous_command_id=previous_command_id)
                previous_command_id = command.command_id
            report_kinds: set[SensorimotorTargetKindV1] = set()
            for report in interval.reports:
                committed = report.committed_target
                if committed.target.origin.stream != self.stream or not any(committed is target for target in self._installed_targets):
                    raise ValueError("execution report names the wrong action/target/generation")
                if committed.target.kind in report_kinds:
                    raise ValueError("a returned interval repeats a body resource")
                report_kinds.add(committed.target.kind)
                drive = 0.0 if command is None else (
                    command.orientation_drive if committed.target.kind is _ORIENTATION else command.extension_drive
                )
                if drive != 0.0 and (report.reported_tick != interval.tick or interval.tick >= committed.expires_at_tick
                                     or report.disposition not in {LocalTargetDispositionV1.ACTIVE, LocalTargetDispositionV1.PARTIAL}):
                    raise ValueError("issued drive requires a current live execution report inside its original lease")
            if command is not None and ((_ORIENTATION not in report_kinds and command.orientation_drive != 0)
                                        or (_EXTENSION not in report_kinds and command.extension_drive != 0)):
                raise ValueError("issued motor drive has no corresponding authorized target")
            for feedback in interval.deliveries:
                feedback.validate_available(stream=self.stream, at_tick=cutoff)
                if feedback.sample_id in known and feedback != known[feedback.sample_id]:
                    raise ValueError("one sensor identity cannot describe changed evidence")
                for pending in self._pending.values():
                    registration = pending.registration
                    basis = registration.preview.basis.feedback
                    if (pending.installed and pending.ended_tick is None and feedback.event_tick == registration.due_tick
                            and basis is not None and feedback.sample_id <= basis.sample_id):
                        raise ValueError("a corresponding endpoint needs a distinct later acquisition")
                known[feedback.sample_id] = feedback

    def consume_intervals(
        self, intervals: tuple[RightingIntervalEvidenceV1, ...], *, cutoff_tick: int,
    ) -> tuple[RightingClaimOutcomeV1, ...]:
        """Consume frozen execution/evidence once, then expire unresolved old claims.

        Only normally returned commands are counted as executed opportunities.
        They still do not prove displacement or causation. Original sensor event
        times, rather than focal read time, identify each endpoint; the current
        source is not overwritten by an older corresponding event.
        """
        cutoff = _tick(cutoff_tick)
        if cutoff <= self._last_consumption_cutoff:
            raise ValueError("outcome admission requires a new increasing frozen cutoff")
        self._validate_intervals(intervals, cutoff)
        first_number = self._outcome_number
        for interval in intervals:
            command = interval.command
            if command is not None:
                self._last_command_id = command.command_id
            if command is not None and (command.orientation_drive != 0 or command.extension_drive != 0):
                self._command_ticks.append(interval.tick)
                for pending in self._pending.values():
                    registration = pending.registration
                    if pending.installed and registration.preview.basis.cutoff_tick <= interval.tick < registration.due_tick:
                        if any(report.committed_target.target.origin == registration.request.origin for report in interval.reports):
                            pending.command_intervals += 1
            for feedback in interval.deliveries:
                self._consume_feedback(feedback, cutoff)
            self._last_interval = interval.tick
        for claim_id, pending in tuple(self._pending.items()):
            if pending.ended_tick is not None:
                self._finish(claim_id, "interrupted" if pending.command_intervals else "cancelled", cutoff, None, (),
                             f"{pending.end_reason} before the original predicted physical endpoint")
            elif cutoff > pending.registration.expires_at_tick:
                self._finish(claim_id, "expired_unresolved", cutoff, None, (), "matching endpoint acquisition did not arrive within its window")
        self._last_consumption_cutoff = cutoff
        return tuple(item for item in self._history if item.number > first_number)

    def _consume_feedback(self, feedback: MotorFeedbackV1, cutoff: int) -> None:
        """Compare historical claims and check continuity without adding focal dwell."""
        if any(feedback.sample_id == item.sample_id for item in self._recent_feedback):
            return
        self._recent_feedback.append(feedback)
        previous = self._last_delivery
        if previous is not None and feedback.sample_id == previous.sample_id:
            if feedback != previous:
                raise ValueError("one sensor identity cannot describe changed evidence")
            return
        if previous is None or feedback.event_tick > previous.event_tick:
            self._last_delivery = feedback
        if self._task is not None and self._dwell and feedback.event_tick >= self._dwell[0].event_tick:
            if righting_support_adequacy_v1(feedback, self._task.context) is not True:
                self._dwell = ()
        for claim_id, pending in tuple(self._pending.items()):
            registration = pending.registration
            if not pending.installed or pending.ended_tick is not None or feedback.event_tick != registration.due_tick:
                continue
            basis = registration.preview.basis.feedback
            if basis is None or feedback.sample_id <= basis.sample_id:
                raise ValueError("a corresponding endpoint needs a distinct later acquisition")
            if feedback.available_tick > registration.expires_at_tick:
                continue
            results: list[tuple[str, str]] = [(name, "unevaluable_authorization") for name in registration.unevaluable_relations]
            for name, predicted_field, observed_field, tolerance in _RELATIONS:
                if name not in registration.compatible_relations:
                    continue
                predicted, observed = getattr(registration.preview, predicted_field), getattr(feedback, observed_field)
                if observed is None:
                    comparison = "unknown"
                elif name == "contact":
                    comparison = "matched" if predicted is observed else "mismatch"
                else:
                    comparison = "matched" if abs(predicted - observed) <= tolerance + 1e-12 else "mismatch"
                results.append((name, comparison))
            values = {value for _, value in results}
            status = "mismatch" if "mismatch" in values else "unknown" if "unknown" in values else "matched"
            if status == "matched" and registration.unevaluable_relations:
                status = "partly_matched"
            if pending.command_intervals == 0:
                status = "observed_without_command"
            self._finish(claim_id, status, cutoff, feedback, tuple(results), "original endpoint evidence; causal contribution remains uncertain")

    #pylint: disable=too-many-positional-arguments
    def _finish(
        self, claim_id: str, status: str, tick: int, feedback: MotorFeedbackV1 | None,
        relations: tuple[tuple[str, str], ...], reason: str,
    ) -> None:
        """Retain one terminal result; removing a claim cannot restore actuator rights."""
        pending = self._pending.pop(claim_id)
        self._outcome_number += 1
        self._history.append(RightingClaimOutcomeV1(
            self._outcome_number, pending.registration, status, tick, feedback, relations, pending.command_intervals, reason,
        ))
    #pylint: enable=too-many-positional-arguments

    @staticmethod
    def _changes(
        before: MotorFeedbackV1, after: MotorFeedbackV1, context: RightingContextV1,
    ) -> tuple[tuple[str, str], ...]:
        """Compare separate unmet relation deficits; do not invent a universal score."""
        max_tilt, min_load, max_instability = context.criterion
        changes: list[tuple[str, str]] = []
        for name, old, new, limit, deadband, minimum in (
            ("tilt", before.body_tilt_degrees, after.body_tilt_degrees, max_tilt, 1.0, False),
            ("loading", before.useful_loading, after.useful_loading, min_load, 0.02, True),
            ("destabilization", before.destabilization, after.destabilization, max_instability, 0.02, False),
        ):
            if old is None or new is None:
                changes.append((name, "unknown"))
                continue
            if name == "tilt":
                old, new = abs(old), abs(new)
            old_deficit = max(0.0, limit - old if minimum else old - limit)
            new_deficit = max(0.0, limit - new if minimum else new - limit)
            delta = old_deficit - new_deficit
            changes.append((name, "progress" if delta > deadband else "regression" if delta < -deadband else "unchanged"))
        return tuple(changes)

    def assess_task(
        self, task: RightingTaskV1 | None, source: MotorSupportConfigurationV1 | None,
        context: RightingContextV1, *, cutoff_tick: int,
    ) -> RightingTaskAssessmentV1:
        """Assess one current source sample and propose evidence-supported task closure.

        A missing/held sample never counts as progress or another dwell sample.
        Three retained genuine focal acquisitions must span eight ticks; all
        intermediate delivered physical contradictions break their continuity.
        Completed/cancelled tasks retain their historical disposition. Changing
        context cannot turn an old unmet requirement into success.
        """
        cutoff = _tick(cutoff_tick)
        if cutoff <= self._last_assessment_tick:
            raise ValueError("one task assessment is allowed at each increasing focal cutoff")
        if not isinstance(context, RightingContextV1):
            raise TypeError("task assessment requires its explicit activity context")
        if source is not None and (not isinstance(source, MotorSupportConfigurationV1) or source.stream != self.stream
                                   or source.cutoff_tick != cutoff):
            raise ValueError("task assessment needs this stream's frozen source at the current cutoff")
        if task is not None and (task.context != context or source is not None and task.source_map_ref != source.source_map_ref):
            raise ValueError("task evidence has the wrong original source or requirement")
        self._bind_task(task)
        feedback = source.feedback if source is not None and source.current else None
        old = self._previous
        changes: tuple[tuple[str, str], ...] = ()
        adequacy = righting_support_adequacy_v1(feedback, context)
        fresh = feedback is not None and (old is None or feedback.sample_id > old.sample_id and feedback.event_tick > old.event_tick)
        if old is not None and feedback is not None and feedback.sample_id == old.sample_id and feedback != old:
            raise ValueError("cached focal evidence changed without a new acquisition")
        if self._dwell and cutoff - self._dwell[-1].event_tick > 8:
            self._dwell = ()
        if task is None:
            status, reason = "no_task", "current requirement may be adequate; no Righting task was selected"
        elif task.status in {"cancelled", "completed"}:
            status, reason = task.status, "historical task lifecycle; no renewed actuator authority"
        elif feedback is None or adequacy is None:
            self._dwell = ()
            status, reason = "unknown", "required current sensory support is unavailable"
        elif not fresh:
            status, reason = "unchanged", "cached sample consumed previously; no progress or extra dwell"
        else:
            if old is not None and 0 < feedback.event_tick - old.event_tick <= 8:
                changes = self._changes(old, feedback, context)
            if adequacy:
                if self._dwell and feedback.event_tick - self._dwell[-1].event_tick > 8:
                    self._dwell = ()
                self._dwell = (*self._dwell, feedback)
                if len(self._dwell) > 3:
                    self._dwell = (self._dwell[0], self._dwell[-2], self._dwell[-1])
                complete = len(self._dwell) == 3 and self._dwell[-1].event_tick - self._dwell[0].event_tick >= 8
                within_budget = cutoff <= task.started_tick + 80 and task.last_cycle - task.started_cycle <= 20
                status = "complete" if complete and within_budget else "adequate_pending_dwell"
                reason = "distinct focal samples under fixed physical-time dwell; causation uncertain"
            else:
                self._dwell = ()
                values = {value for _, value in changes}
                if "progress" in values and "regression" in values:
                    status = "mixed"
                elif "regression" in values:
                    status = "regression"
                elif "progress" in values:
                    status = "progress"
                elif changes and "unknown" not in values and old is not None and any(
                    old.event_tick <= command_tick < feedback.event_tick for command_tick in self._command_ticks
                ):
                    status = "stall"
                else:
                    status = "unchanged"
                reason = "separate observed task deficits; a local target result is not task completion"
        if fresh:
            self._previous = feedback
        samples = task.completion_samples if task is not None and task.status == "completed" else self._dwell
        assessment = RightingTaskAssessmentV1(task.task_id if task else None, context, cutoff, feedback, status, changes, samples, reason)
        self._last_assessment_tick, self.last_assessment = cutoff, assessment
        return assessment
