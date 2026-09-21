#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Execution-sensitive maternal PNM correspondence, not task or causal evaluation.

The optional P16-2B-B consumer retains the original Follow-Mom projection before
handoff, its actual authorized translation, and a bounded pending obligation.
The existing core calls it in C2 with frozen returned intervals and canonical
paired motor/visual acquisitions. It compares the original physical endpoint,
not whichever source happens to be focal or newest. It owns no current NavMap,
selects no task, performs no demanding interpretation and changes no learner.

``maternal_correspondence_v1`` compares SELF position, the stationary maternal
anchor, and separation with fixed 0.02-metre residual tolerances. The event is
cutoff + the original projection horizon; its acquisition may become available
up to eight ticks later. These are engineering assumptions, not biological
constants. Missing/ambiguous association is not a fabricated failed forecast.
An authorized endpoint different from the proposal leaves incompatible forecast
relations unevaluable rather than rewriting them. Prediction fit, local target
achievement, supported proximity and action causation remain separate questions.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import BodyTargetProposalV1, VisualApproachRequestV1
from nca8_followmom import FollowMomApplicationV1
from nca8_prediction import MaternalApproachPreviewV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, CommittedBodyTargetV1, LocalTargetReportV1
from nca8_visual import VisualObservationV1

__version__ = "0.1.2"
__all__ = [
    "MaternalIntervalEvidenceV1", "MaternalClaimV1", "MaternalOutcomeV1", "MaternalOutcomeFrameV1",
    "MaternalOutcomeRuntimeV1", "__version__",
]
_RELATIONS = ("self_position", "maternal_anchor", "separation")
_TOLERANCE = 0.02


def _tick(value: int) -> int:
    """Require the same finite non-Boolean physical indices as the execution seam."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("maternal outcome tick must be a bounded nonnegative integer")
    return value


def _distance(left: NavPointV1, right: NavPointV1) -> float:
    """Measure distance in an already checked common scene frame, without remapping."""
    return math.hypot(left.x - right.x, left.y - right.y)


@dataclass(frozen=True, slots=True)
class MaternalIntervalEvidenceV1:
    """One returned physical interval and admitted products of actual acquisitions.

    Reports describe the pre-call controller; command is exposure, not achieved
    motion. Visual products share the motor sample/event/availability in this
    fixed-scene provider. They are not extra independent observations. A subset
    may be absent, including an entire withheld visual batch. No private world
    snapshot, scenario label, task verdict or action ID is added to sensing.
    """

    # Keep the canonical interval header aligned with the independent Righting lane.
    # These are transport fields, not a reason to couple the domain comparators.
    # pylint: disable=duplicate-code
    tick: int
    command: MotorCommandV1 | None
    reports: tuple[LocalTargetReportV1, ...]
    deliveries: tuple[MotorFeedbackV1, ...]
    # pylint: enable=duplicate-code
    observations: tuple[VisualObservationV1, ...]

    def __post_init__(self) -> None:
        _tick(self.tick)
        if self.command is not None and (not isinstance(self.command, MotorCommandV1) or self.command.issued_tick != self.tick):
            raise ValueError("interval must retain its original command and time")
        if not isinstance(self.reports, tuple) or len(self.reports) > 2 or any(
            not isinstance(report, LocalTargetReportV1) or report.reported_tick > self.tick for report in self.reports
        ):
            raise ValueError("interval requires at most two already available local reports")
        if not isinstance(self.deliveries, tuple) or len(self.deliveries) > 16 or any(
            not isinstance(sample, MotorFeedbackV1) or sample.available_tick > self.tick + 1 for sample in self.deliveries
        ):
            raise ValueError("interval has invalid or future motor acquisitions")
        if len({sample.sample_id for sample in self.deliveries}) != len(self.deliveries):
            raise ValueError("one returned interval cannot duplicate an acquisition identity")
        if not isinstance(self.observations, tuple) or len(self.observations) > 16:
            raise ValueError("interval requires at most sixteen admitted visual products")
        identities: set[int] = set()
        for observation in self.observations:
            if not isinstance(observation, VisualObservationV1) or observation.sample_id in identities:
                raise ValueError("visual products must be canonical and unique within their interval")
            identities.add(observation.sample_id)
            paired = next((sample for sample in self.deliveries if sample.sample_id == observation.sample_id), None)
            if paired is None or paired.planar is None:
                raise ValueError("visual product lacks its original planar acquisition")
            if (observation.stream, observation.event_tick, observation.available_tick, observation.frame_id) != (
                paired.stream, paired.event_tick, paired.available_tick, paired.planar.frame_id
            ):
                raise ValueError("paired products disagree on original stream, time or frame")
            xy = None if observation.self_position is None else (observation.self_position.x, observation.self_position.y)
            if xy != paired.planar.position:
                raise ValueError("visual SELF does not describe its paired original acquisition")


@dataclass(frozen=True, slots=True)
class MaternalClaimV1:
    """Pre-handoff projection, proposed request and exact original permission records.

    Diagnostic exports confer no execution rights. An unchanged maternal anchor
    can remain testable after BodyMap narrows the SELF contribution; neither the
    original projection nor the authorized target is replaced with a nicer one.
    """

    preview: MaternalApproachPreviewV1
    request: VisualApproachRequestV1
    # The same physical lifetime convention is intentional; the domain payload
    # and comparison policy remain independent of the Righting implementation.
    # pylint: disable=duplicate-code
    targets: tuple[CommittedBodyTargetV1, ...]
    compatible_relations: tuple[str, ...]
    unevaluable_relations: tuple[str, ...]

    @property
    def due_tick(self) -> int:
        """Return the original endpoint occurrence, not its later admission time."""
        return self.preview.basis.cutoff_tick + self.preview.horizon_ticks

    @property
    def expires_at_tick(self) -> int:
        """Allow eight ticks of delivery delay independently of any actuator lease."""
        return self.due_tick + 8

    # pylint: enable=duplicate-code

    def as_dict(self) -> dict[str, object]:
        """Keep original meaning, compatible subset and observation window inspectable."""
        return {
            "pnm_id": self.preview.pnm.pnm_id, "original_preview": self.preview.as_dict(),
            "proposed_request": self.request.as_dict(), "authorized_targets": [target.as_dict() for target in self.targets],
            "compatible_relations": list(self.compatible_relations), "unevaluable_relations": list(self.unevaluable_relations),
            "endpoint_event_tick": self.due_tick, "last_acceptable_availability_tick": self.expires_at_tick,
            "residual_tolerance_metres": _TOLERANCE, "grants_motor_authority": False,
        }


@dataclass(frozen=True, slots=True)
class MaternalOutcomeV1:
    """One terminal claim disposition, never whole-task completion or causal credit."""

    number: int
    claim: MaternalClaimV1
    status: str
    evaluated_tick: int
    evidence: VisualObservationV1 | None
    relations: tuple[tuple[str, str], ...]
    residuals: tuple[tuple[str, float], ...]
    command_intervals: int
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Export original evidence with explicit limits on its downstream interpretation."""
        return {
            "number": self.number, "claim": self.claim.as_dict(), "status": self.status, "evaluated_tick": self.evaluated_tick,
            "evidence": None if self.evidence is None else self.evidence.as_dict(), "relation_results": dict(self.relations),
            "residuals_metres": dict(self.residuals), "nonnull_command_intervals": self.command_intervals, "reason": self.reason,
            "causal_credit": "not_established", "establishes_task_completion": False, "durable_learning_updates": 0,
        }


@dataclass(frozen=True, slots=True)
class MaternalOutcomeFrameV1:
    """Immutable report of this C2/E opportunity; no installation or future evidence."""

    cutoff_tick: int
    outcomes: tuple[MaternalOutcomeV1, ...]
    registration: MaternalClaimV1 | None
    pending: tuple[MaternalClaimV1, ...]
    comparison_enabled: bool
    attention_enabled: bool = False
    learning_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Report only completed bookkeeping, preserving separate later installation."""
        return {
            "profile": "maternal_correspondence_v1", "cutoff_tick": self.cutoff_tick,
            "comparison_enabled": self.comparison_enabled, "outcomes": [item.as_dict() for item in self.outcomes],
            "registration": None if self.registration is None else self.registration.as_dict(),
            "pending": [item.as_dict() for item in self.pending],
            "attention_route": "separate_maternal_attention_v1" if self.attention_enabled else "not_implemented_for_maternal",
            "learning_route": "maternal_no_learning_v1" if self.learning_enabled else "not_implemented_for_maternal", "durable_updates": 0,
        }


@dataclass(slots=True)
class _Pending:
    """An old claim and execution exposure, not another WNM or current PNM."""

    claim: MaternalClaimV1
    installed: bool = False
    command_intervals: int = 0
    ended_tick: int | None = None
    end_reason: str | None = None


class MaternalOutcomeRuntimeV1:
    """Bounded local correspondence with no access to current-world or task authority.

    Call consume_intervals at C2, register at E before handoff, and installed only
    after closed receipt consumption and successful target installation. Retain
    at most eight pending claims, 32 terminal reports, sixteen recent acquisition
    identities, one installed target reference and one awaiting registration.
    Overflow or malformed evidence raises before that input batch is consumed;
    the enclosing core then stops. Reset uses a new owner/generation. No method
    renews a task, claim, lease, or already consumed evidence.
    """

    def __init__(self, stream: MotorStreamRefV1, *, compare_predictions: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(compare_predictions, bool):
            raise TypeError("maternal correspondence requires its stream and a Boolean comparison switch")
        self.stream = stream
        self.compare_predictions = compare_predictions
        self._pending: dict[str, _Pending] = {}
        self._history: deque[MaternalOutcomeV1] = deque(maxlen=32)
        self._recent: deque[VisualObservationV1] = deque(maxlen=16)
        self._awaiting: MaternalClaimV1 | None = None
        self._installed_target: CommittedBodyTargetV1 | None = None
        self._execution_end_tick: int | None = None
        self._last_interval = -1
        self._last_cutoff = -1
        self._last_command_id = 0
        self._last_registration_cycle = 0
        self._number = 0
        self._closed = False

    def pending(self) -> tuple[MaternalClaimV1, ...]:
        """Read immutable old claims; reading cannot renew them or install a target."""
        return tuple(item.claim for item in self._pending.values())

    def history(self) -> tuple[MaternalOutcomeV1, ...]:
        """Read at most 32 terminal reports, independent of live task/source retention."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure real owned storage, not an expected or reconstructed bound."""
        return {"maternal_pending_claims": len(self._pending), "maternal_outcome_history": len(self._history),
                "maternal_recent_acquisitions": len(self._recent), "maternal_awaiting_installation": int(self._awaiting is not None),
                "maternal_execution_reference": int(self._installed_target is not None)}

    def register(
        self, application: FollowMomApplicationV1, proposal: BodyTargetProposalV1, targets: tuple[CommittedBodyTargetV1, ...],
    ) -> MaternalClaimV1:
        """Reconcile original forecast with actual permission before any handoff.

        Only the exact binding/commit records are admitted. A copied description
        cannot grant eligibility. This method neither installs nor infers motion.
        It refuses overflow rather than silently evicting an unanswered claim.
        """
        if self._closed or self._awaiting is not None:
            raise RuntimeError("maternal correspondence is closed or awaits an installation disposition")
        if not isinstance(application, FollowMomApplicationV1) or not isinstance(proposal, BodyTargetProposalV1):
            raise TypeError("register a selected maternal application and its actual BodyMap proposal")
        preview, request = application.projection, application.contribution
        if proposal.request is not request or request.origin.stream != self.stream:
            raise ValueError("maternal proposal changed its original request or stream")
        if preview.pnm.created_cycle <= self._last_registration_cycle or preview.basis.cutoff_tick != self._last_cutoff:
            raise ValueError("maternal registration must follow this new frozen opportunity")
        if proposal.created_tick != self._last_cutoff or preview.basis.stream != self.stream:
            raise ValueError("maternal prediction and permission do not share the current stream/cutoff")
        if not isinstance(targets, tuple) or len(targets) != len(proposal.bindings) or len(targets) > 1:
            raise ValueError("maternal permission must preserve the sole translation binding or veto")
        for target, binding in zip(targets, proposal.bindings):
            if not isinstance(target, CommittedBodyTargetV1) or target.target is not binding.target:
                raise ValueError("maternal permission must retain the exact original binding")
            if target.target.origin != request.origin or target.committed_tick != proposal.created_tick:
                raise ValueError("authorized translation has a different origin or commitment time")
            if not isinstance(target.target, BodyTranslationTargetV1):
                raise ValueError("maternal correspondence requires the original translation family")
            planar_basis = target.target.basis.planar
            if planar_basis is None or planar_basis.frame_id != preview.basis.frame_id:
                raise ValueError("maternal correspondence needs a translation in the original scene frame")
        if len(self._pending) >= 8:
            raise OverflowError("eight unanswered maternal claims; no eviction or extra dispatch")
        compatible: tuple[str, ...] = _RELATIONS
        unevaluable: tuple[str, ...] = ()
        if targets:
            local_target = targets[0].target
            if not isinstance(local_target, BodyTranslationTargetV1):
                raise TypeError("maternal local target must be a translation")
            if math.hypot(local_target.endpoint[0] - preview.predicted_self.x, local_target.endpoint[1] - preview.predicted_self.y) > 1e-12:
                compatible, unevaluable = ("maternal_anchor",), ("self_position", "separation")
        claim = MaternalClaimV1(preview, request, targets, compatible, unevaluable)
        self._pending[preview.pnm.pnm_id] = _Pending(claim)
        self._last_registration_cycle = preview.pnm.created_cycle
        if targets:
            self._awaiting = claim
        else:
            self._finish(preview.pnm.pnm_id, "not_applied", self._last_cutoff, reason="BodyMap vetoed the requested contribution")
        return claim

    def installed(self, claim: MaternalClaimV1, *, at_tick: int) -> None:
        """Record a once-consumed successfully installed original target, not success."""
        tick = _tick(at_tick)
        if not isinstance(claim, MaternalClaimV1) or self._closed or claim is not self._awaiting or tick != self._last_cutoff:
            raise ValueError("installation must answer the original awaiting maternal registration")
        self.end_execution(at_tick=tick, reason="replacement")
        pending = self._pending[claim.preview.pnm.pnm_id]
        pending.installed = True
        self._installed_target = claim.targets[0]
        self._execution_end_tick = None
        self._awaiting = None

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """End future pursuit without erasing endpoints already physically reached.

        Buffered pre-cancellation intervals still need C2 admission. Finalizing
        interruption waits for that admission, so command exposure is not lost.
        An endpoint at/before the end time can still receive its delayed report.
        """
        tick = _tick(at_tick)
        if not isinstance(reason, str) or reason not in {"cancelled", "replacement"}:
            raise ValueError("unknown maternal execution end disposition")
        if tick < self._last_cutoff:
            raise ValueError("an execution end cannot precede admitted physical time")
        if self._installed_target is not None and self._execution_end_tick is None:
            self._execution_end_tick = tick
        for pending in self._pending.values():
            if pending.installed and pending.ended_tick is None and tick < pending.claim.due_tick:
                pending.ended_tick, pending.end_reason = tick, reason

    def close(self, *, reason: str) -> None:
        """Stop this owner permanently; no unresolved observation becomes a failure.

        A fault can follow partial installation or a physical call with unknown
        effects. It therefore reports unresolved_stopped, not not_applied or an
        automatic failed prediction. A new generation needs a new owner.
        """
        if not isinstance(reason, str) or not reason or len(reason) > 100:
            raise ValueError("outcome closure needs a bounded reason")
        if self._closed:
            return
        for claim_id in tuple(self._pending):
            self._finish(claim_id, "unresolved_stopped", max(0, self._last_cutoff), reason=reason)
        self._awaiting = None
        self._installed_target = None
        self._closed = True

    def _validate_batch(self, intervals: tuple[MaternalIntervalEvidenceV1, ...], cutoff: int) -> None:
        """Validate every interval and acquisition before changing any claim state."""
        if not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("at most sixteen frozen maternal intervals are permitted")
        previous_command = self._last_command_id
        known = {sample.sample_id: sample for sample in self._recent}
        for index, interval in enumerate(intervals):
            if not isinstance(interval, MaternalIntervalEvidenceV1) or interval.tick != self._last_interval + index + 1:
                raise ValueError("maternal intervals must be contiguous and consumed once")
            if interval.tick + 1 > cutoff:
                raise ValueError("a future interval cannot enter frozen maternal input")
            command = interval.command
            if command is not None:
                command.validate_for_update(stream=self.stream, now_tick=interval.tick, previous_command_id=previous_command)
                previous_command = command.command_id
            translation_reports = tuple(report for report in interval.reports if isinstance(report.committed_target.target, BodyTranslationTargetV1))
            if len(translation_reports) > 1:
                raise ValueError("one interval cannot repeat a translation resource")
            for report in interval.reports:
                if report.committed_target.target.origin.stream != self.stream:
                    raise ValueError("execution evidence belongs to a foreign stream/generation")
            for report in translation_reports:
                if report.committed_target is not self._installed_target:
                    raise ValueError("translation report does not describe the current original installed target")
            if command is not None and command.translation is not None and (
                command.translation.forward != 0 or command.translation.left != 0
            ):
                if not translation_reports:
                    raise ValueError("translation drive lacks its authorized report")
                live_report = translation_reports[0]
                if not live_report.committed_target.committed_tick <= interval.tick < live_report.committed_target.expires_at_tick:
                    raise ValueError("translation drive is outside its original authorization interval")
                if self._execution_end_tick is not None and interval.tick >= self._execution_end_tick:
                    raise ValueError("translation drive follows explicit cancellation")
                if live_report.reported_tick != interval.tick or live_report.disposition.value not in {"active", "partial"}:
                    raise ValueError("translation drive lacks live permission inside the original lease")
                for pending in self._pending.values():
                    if pending.claim.targets and pending.claim.targets[0] is live_report.committed_target:
                        if pending.ended_tick is not None and interval.tick >= pending.ended_tick:
                            raise ValueError("translation drive follows revoked maternal execution")
            for feedback in interval.deliveries:
                feedback.validate_available(stream=self.stream, at_tick=cutoff)
            for observation in interval.observations:
                observation.validate_available(stream=self.stream, at_tick=cutoff)
                if observation.sample_id in known and observation != known[observation.sample_id]:
                    raise ValueError("one visual acquisition identity cannot contain conflicting evidence")
                known[observation.sample_id] = observation
                for pending in self._pending.values():
                    basis = pending.claim.preview.basis
                    if observation.event_tick == pending.claim.due_tick and basis.sample_id is not None:
                        if observation.sample_id <= basis.sample_id:
                            raise ValueError("a later endpoint requires a distinct later acquisition")

    def consume_intervals(
        self, intervals: tuple[MaternalIntervalEvidenceV1, ...], *, cutoff_tick: int,
    ) -> tuple[MaternalOutcomeV1, ...]:
        """At C2 consume only frozen returned intervals, then expire unanswered claims.

        The comparison-off control retains identical obligations and execution
        bookkeeping, but emits comparison_disabled for a corresponding endpoint.
        No source, task, drive, gain, or completion evidence is changed here.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_cutoff:
            raise ValueError("maternal outcome consumption needs an open owner and a new cutoff")
        self._validate_batch(intervals, cutoff)
        previous_number = self._number
        for interval in intervals:
            command = interval.command
            if command is not None:
                self._last_command_id = command.command_id
            if command is not None and command.translation is not None and (
                command.translation.forward != 0 or command.translation.left != 0
            ):
                for pending in self._pending.values():
                    if not pending.installed or interval.tick >= pending.claim.due_tick:
                        continue
                    if pending.ended_tick is not None and interval.tick >= pending.ended_tick:
                        continue
                    if any(report.committed_target is pending.claim.targets[0] for report in interval.reports):
                        pending.command_intervals += 1
            for report in interval.reports:
                if report.disposition.value not in {"cancelled", "interrupted", "unavailable", "blocked"}:
                    continue
                for pending in self._pending.values():
                    if not pending.installed or report.committed_target is not pending.claim.targets[0]:
                        continue
                    if pending.ended_tick is None and report.reported_tick < pending.claim.due_tick:
                        pending.ended_tick, pending.end_reason = report.reported_tick, report.reason
            for observation in interval.observations:
                self._consume_observation(observation, cutoff)
            self._last_interval = interval.tick
        for claim_id, pending in tuple(self._pending.items()):
            if pending.ended_tick is not None and self._last_interval + 1 >= pending.ended_tick:
                status = "interrupted" if pending.command_intervals else "cancelled"
                self._finish(claim_id, status, cutoff, reason=f"{pending.end_reason} before original endpoint")
            elif cutoff > pending.claim.expires_at_tick:
                self._finish(claim_id, "expired_unresolved", cutoff, reason="no corresponding endpoint within the original availability window")
        self._last_cutoff = cutoff
        return tuple(item for item in self._history if item.number > previous_number)

    def _consume_observation(self, observation: VisualObservationV1, cutoff: int) -> None:
        """Answer old claims without installing historical evidence as current truth."""
        if any(sample.sample_id == observation.sample_id for sample in self._recent):
            return
        self._recent.append(observation)
        for claim_id, pending in tuple(self._pending.items()):
            claim = pending.claim
            if not pending.installed or pending.ended_tick is not None or observation.event_tick != claim.due_tick:
                continue
            if observation.available_tick > claim.expires_at_tick:
                continue
            if not self.compare_predictions:
                self._finish(claim_id, "comparison_disabled", cutoff, evidence=observation,
                             reason="only endpoint comparison disabled; registration and execution retained")
                continue
            values, residuals, identity = _compare(claim, observation)
            statuses = {value for _, value in values}
            status = "mismatch" if "mismatch" in statuses else "unknown" if "unknown" in statuses else "matched"
            if status == "matched" and claim.unevaluable_relations:
                status = "partly_matched"
            if identity == "contradicted":
                status = "identity_contradicted"
            if pending.command_intervals == 0:
                status = "observed_without_command"
            self._finish(claim_id, status, cutoff, evidence=observation, relations=values, residuals=residuals,
                         reason="original endpoint correspondence; neither task completion nor causal credit")

    def _finish(
        self, claim_id: str, status: str, tick: int, *, reason: str,
        evidence: VisualObservationV1 | None = None, relations: tuple[tuple[str, str], ...] = (),
        residuals: tuple[tuple[str, float], ...] = (),
    ) -> None:
        """Consume one obligation once, keeping a bounded immutable terminal report."""
        pending = self._pending.pop(claim_id)
        self._number += 1
        self._history.append(MaternalOutcomeV1(self._number, pending.claim, status, tick, evidence, relations, residuals,
                                              pending.command_intervals, reason))


def _compare(claim: MaternalClaimV1, observation: VisualObservationV1) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, float], ...], str]:
    """Compare only supported original relations in their original frame and identity.

    An empty detection set does not prove absence. Descriptor contradiction is
    an association problem, not a known new maternal position. The raw residuals
    are reported even for authorization-incompatible coordinates, but do not
    turn those coordinates into scored executed forecasts.
    """
    preview = claim.preview
    found = next((item for item in observation.detections if item.region_id == preview.region_id), None)
    identity = "unknown" if found is None or found.descriptor is None else (
        "supported" if found.descriptor == preview.basis.seed.descriptor else "contradicted"
    )
    same_frame = observation.frame_id == preview.basis.frame_id
    residuals: dict[str, float] = {}
    if same_frame and observation.self_position is not None:
        residuals["self_position"] = _distance(observation.self_position, preview.predicted_self)
    if same_frame and identity == "supported" and found is not None and found.position is not None:
        residuals["maternal_anchor"] = _distance(found.position, preview.scene_target)
        if observation.self_position is not None:
            residuals["separation"] = abs(_distance(found.position, observation.self_position) - preview.predicted_separation)
    results: list[tuple[str, str]] = []
    for name in _RELATIONS:
        if name in claim.unevaluable_relations:
            result = "unevaluable_authorization"
        elif name not in residuals:
            result = "unknown"
        else:
            result = "matched" if residuals[name] <= _TOLERANCE + 1e-12 else "mismatch"
        results.append((name, result))
    return tuple(results), tuple(residuals.items()), identity
