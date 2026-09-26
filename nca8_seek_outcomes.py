#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-D: original seeking predictions matched to authorized, observed effects.

This local correspondence owner reads immutable pre-handoff claims, actual oral
command exposure and paired motor/visual acquisitions. It does not read current
source state or private physics, select an operation, change a target, establish
latch, or assign causal credit. Matching the original endpoint and completing a
reach task are different questions. Default C experiments do not create this
owner. P16-2C-E can opt in to source-owned Attention/interpretation using the
canonical downstream validator; feeding learning remains separately deferred.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import BodyTargetProposalV1, OralReachRequestV1
from nca8_prediction import SeekNipplePreviewV1
from nca8_seek_nipple import SeekNippleApplicationV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, CommittedBodyTargetV1, LocalTargetReportV1, SensorimotorTargetKindV1
from nca8_visual import VisualObservationV1

__version__ = "0.4.0"
__all__ = ["SeekNippleEndpointV1", "SeekNippleIntervalEvidenceV1", "SeekNippleClaimV1", "SeekNippleOutcomeV1",
           "SeekNippleOutcomeFrameV1", "SeekNippleOutcomeRuntimeV1", "validate_seeking_outcome_v1", "validate_seeking_claim_v1", "__version__"]
_RELATIONS = ("mouth_position", "detail_anchor", "separation")
_TOLERANCE = 0.005


def _tick(value: int) -> int:
    """Reject Boolean/coerced or overflowing physical indices before owner mutation."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("seeking outcome tick must be a bounded nonnegative integer")
    return value


def _distance(left: NavPointV1, right: NavPointV1) -> float:
    """Measure already frame-compatible scene geometry without changing the source."""
    return math.hypot(left.x - right.x, left.y - right.y)


@dataclass(frozen=True, slots=True)
class SeekNippleEndpointV1:
    """Paired products of one acquisition, including explicitly missing visual data.

    The provider supplies position, heading and extension; this record derives
    the mouth point, not touch or identity. A historical endpoint can answer its
    old claim without replacing a newer source. No current-field fallback exists.
    """

    feedback: MotorFeedbackV1
    observation: VisualObservationV1 | None

    def __post_init__(self) -> None:
        if not isinstance(self.feedback, MotorFeedbackV1):
            raise TypeError("seeking endpoint requires canonical motor feedback")
        observation, sample = self.observation, self.feedback
        if observation is not None:
            if not isinstance(observation, VisualObservationV1) or sample.planar is None:
                raise ValueError("visual endpoint needs its paired planar acquisition")
            if (observation.stream, observation.sample_id, observation.event_tick, observation.available_tick, observation.frame_id) != (
                sample.stream, sample.sample_id, sample.event_tick, sample.available_tick, sample.planar.frame_id
            ):
                raise ValueError("paired seeking products disagree on identity, time or frame")
            position = None if observation.self_position is None else (observation.self_position.x, observation.self_position.y)
            if position != sample.planar.position:
                raise ValueError("visual SELF disagrees with the same original body acquisition")

    @property
    def mouth_position(self) -> NavPointV1 | None:
        """Derive a scene point only from complete measured body/heading/reach data."""
        planar, oral = self.feedback.planar, self.feedback.oral
        if planar is None or planar.position is None or planar.heading_degrees is None or oral is None or oral.extension_metres is None:
            return None
        angle = math.radians(planar.heading_degrees)
        return NavPointV1(planar.position[0] + oral.extension_metres * math.cos(angle),
                          planar.position[1] + oral.extension_metres * math.sin(angle))

    def as_dict(self) -> dict[str, object]:
        """Expose actual acquisition, derived point and unscored contact separately."""
        mouth = self.mouth_position
        return {"feedback": self.feedback.as_dict(), "visual": self.observation.as_dict() if self.observation is not None else None,
                "derived_mouth_position": mouth.as_dict() if mouth is not None else None,
                "contact_is_not_a_predicted_relation": True, "establishes_latch_or_milk": False}


@dataclass(frozen=True, slots=True)
class SeekNippleIntervalEvidenceV1:
    """One returned interval, pre-call reports and same-acquisition sensory products.

    Reports and commands describe exposure, not actual attainment. An absent
    visual product is permitted and is not an observed absent nipple. The fixed
    provider shares sample/event/availability identities across both products.
    The outer driver can withhold vision without manufacturing a new acquisition.
    """

    tick: int
    command: MotorCommandV1 | None
    reports: tuple[LocalTargetReportV1, ...]
    deliveries: tuple[MotorFeedbackV1, ...]
    observations: tuple[VisualObservationV1, ...]

    def __post_init__(self) -> None:
        _tick(self.tick)
        if self.command is not None and (not isinstance(self.command, MotorCommandV1) or self.command.issued_tick != self.tick):
            raise ValueError("seeking interval must retain its original command and time")
        if not isinstance(self.reports, tuple) or len(self.reports) > 2 or any(
            not isinstance(report, LocalTargetReportV1) or report.reported_tick > self.tick for report in self.reports
        ):
            raise ValueError("seeking interval requires at most two already available local reports")
        if not isinstance(self.deliveries, tuple) or len(self.deliveries) > 16 or any(
            not isinstance(sample, MotorFeedbackV1) or sample.available_tick > self.tick + 1 for sample in self.deliveries
        ):
            raise ValueError("seeking interval has invalid or future acquisitions")
        if len({sample.sample_id for sample in self.deliveries}) != len(self.deliveries):
            raise ValueError("seeking interval cannot repeat an acquisition")
        if not isinstance(self.observations, tuple) or len(self.observations) > 16 or any(
            not isinstance(item, VisualObservationV1) for item in self.observations
        ):
            raise ValueError("seeking interval needs a bounded immutable visual batch")
        if len({item.sample_id for item in self.observations}) != len(self.observations):
            raise ValueError("seeking interval cannot repeat a visual product")
        for observation in self.observations:
            sample = next((item for item in self.deliveries if item.sample_id == observation.sample_id), None)
            if sample is None:
                raise ValueError("visual product lacks its original motor acquisition")
            SeekNippleEndpointV1(sample, observation)

    def endpoints(self) -> tuple[SeekNippleEndpointV1, ...]:
        """Pair by original identity, never by list position or current source state."""
        return tuple(SeekNippleEndpointV1(sample, next((item for item in self.observations if item.sample_id == sample.sample_id), None))
                     for sample in self.deliveries)


@dataclass(frozen=True, slots=True)
class SeekNippleClaimV1:
    """Original prospective meaning and the exact pre-handoff authorized subset.

    A changed oral endpoint does not rewrite the forecast. It marks dependent
    mouth/separation relations unevaluable under that permission; the original
    stationary detail anchor remains independently testable. No record is a
    restorable actuator grant or a second current PNM.
    """

    preview: SeekNipplePreviewV1
    request: OralReachRequestV1
    targets: tuple[CommittedBodyTargetV1, ...]
    compatible_relations: tuple[str, ...]
    unevaluable_relations: tuple[str, ...]

    @property
    def due_tick(self) -> int:
        """Return the original endpoint occurrence, not touch or later focal time."""
        return self.preview.basis.cutoff_tick + self.preview.horizon_ticks

    @property
    def expires_at_tick(self) -> int:
        """Allow eight ticks of arrival delay without extending the actuator lease."""
        return self.due_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Keep the original prediction, permission and scoring limits inspectable."""
        return {"pnm_id": self.preview.pnm.pnm_id, "original_preview": self.preview.as_dict(),
                "proposed_request": self.request.as_dict(), "authorized_targets": [item.as_dict() for item in self.targets],
                "compatible_relations": list(self.compatible_relations), "unevaluable_relations": list(self.unevaluable_relations),
                "endpoint_event_tick": self.due_tick, "last_acceptable_availability_tick": self.expires_at_tick,
                "residual_tolerance_metres": _TOLERANCE, "grants_motor_authority": False}


@dataclass(frozen=True, slots=True)
class SeekNippleOutcomeV1:
    """One consumed endpoint obligation, not task completion or a causal verdict."""

    number: int
    claim: SeekNippleClaimV1
    status: str
    evaluated_tick: int
    evidence: SeekNippleEndpointV1 | None
    relations: tuple[tuple[str, str], ...]
    residuals: tuple[tuple[str, float], ...]
    command_intervals: int
    reason: str

    def as_dict(self) -> dict[str, object]:
        """Export immutable evidence without upgrading contact, task or learning status."""
        return {"number": self.number, "claim": self.claim.as_dict(), "status": self.status, "evaluated_tick": self.evaluated_tick,
                "evidence": self.evidence.as_dict() if self.evidence is not None else None,
                "relation_results": dict(self.relations), "residuals_metres": dict(self.residuals),
                "nonnull_oral_command_intervals": self.command_intervals, "reason": self.reason,
                "causal_credit": "not_established", "establishes_task_completion": False,
                "establishes_contact_latch_or_milk": False, "durable_learning_updates": 0}


@dataclass(frozen=True, slots=True)
class SeekNippleOutcomeFrameV1:
    """This C2/E opportunity's original claims/results; installation follows closure."""

    cutoff_tick: int
    outcomes: tuple[SeekNippleOutcomeV1, ...]
    registration: SeekNippleClaimV1 | None
    pending: tuple[SeekNippleClaimV1, ...]
    comparison_enabled: bool
    attention_enabled: bool = False
    learning_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Report implemented correspondence and explicitly absent downstream routes."""
        return {"profile": "seek_nipple_correspondence_v1", "cutoff_tick": self.cutoff_tick,
                "comparison_enabled": self.comparison_enabled, "outcomes": [item.as_dict() for item in self.outcomes],
                "registration": self.registration.as_dict() if self.registration is not None else None,
                "pending": [item.as_dict() for item in self.pending], "attention_route": "seeking_outcome_attention_v1" if self.attention_enabled else "deferred_seeking_attention",
                "learning_route": "seeking_no_learning_v1" if self.learning_enabled else "unimplemented_no_participation", "durable_updates": 0}


@dataclass(slots=True)
class _Pending:
    """Finite original obligation and exposure; no current geometry or task policy."""

    claim: SeekNippleClaimV1
    installed: bool = False
    command_intervals: int = 0
    ended_tick: int | None = None
    end_reason: str | None = None


class SeekNippleOutcomeRuntimeV1:
    """Consume original seeking claims once using bounded execution correspondence.

    Call consume_intervals at C2 and register at E. Only after core closure and
    actual successful installation call installed with the identical claim.
    Maximum ownership is eight pending claims, 32 terminal results, sixteen
    recent paired acquisitions, one awaiting claim and one installed reference.
    Incoming batches are wholly validated before mutation. A fault closes the
    owner; a new generation requires a new owner. No method selects a task, changes
    current source facts, body permission, reference parameters or task budgets,
    or applies a durable learned update.
    """

    def __init__(self, stream: MotorStreamRefV1, *, compare_predictions: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(compare_predictions, bool):
            raise TypeError("seeking correspondence requires its stream and Boolean comparison switch")
        self.stream = stream
        self.compare_predictions = compare_predictions
        self._pending: dict[str, _Pending] = {}
        self._history: deque[SeekNippleOutcomeV1] = deque(maxlen=32)
        self._recent: deque[SeekNippleEndpointV1] = deque(maxlen=16)
        self._awaiting: SeekNippleClaimV1 | None = None
        self._installed_target: CommittedBodyTargetV1 | None = None
        self._rest_target: CommittedBodyTargetV1 | None = None
        self._rest_end_tick: int | None = None
        self._execution_end_tick: int | None = None
        self._last_interval = -1
        self._last_cutoff = -1
        self._last_command_id = 0
        self._last_registration_cycle = 0
        self._number = 0
        self._closed = False

    def pending(self) -> tuple[SeekNippleClaimV1, ...]:
        """Read old immutable obligations without refreshing their evidence lifetime."""
        return tuple(item.claim for item in self._pending.values())

    def history(self) -> tuple[SeekNippleOutcomeV1, ...]:
        """Read bounded terminal results; diagnostics cannot restore consumed claims."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual storage independently of external trace/history retention."""
        return {"seeking_pending_claims": len(self._pending), "seeking_outcome_history": len(self._history),
                "seeking_recent_acquisitions": len(self._recent), "seeking_awaiting_installation": int(self._awaiting is not None),
                "seeking_execution_reference": int(self._installed_target is not None)}

    def register(
        self, application: SeekNippleApplicationV1, proposal: BodyTargetProposalV1, targets: tuple[CommittedBodyTargetV1, ...],
    ) -> SeekNippleClaimV1:
        """Reconcile selected forecast with exact BodyMap permission before dispatch.

        Missing capability creates a not_applied result, not a failed executed
        forecast. Narrowing excludes only dependent movement relations. Neither
        copied target descriptions nor a different request pass this boundary.
        Overflow is refused before a new unanswered obligation can be installed.
        """
        if self._closed or self._awaiting is not None:
            raise RuntimeError("seeking correspondence is closed or awaiting installation disposition")
        if not isinstance(application, SeekNippleApplicationV1) or not isinstance(proposal, BodyTargetProposalV1):
            raise TypeError("register the selected seeking application and its actual BodyMap proposal")
        preview, request = application.projection, application.contribution
        if proposal.request is not request or request.origin.stream != self.stream or preview.basis.stream != self.stream:
            raise ValueError("seeking proposal changed its original request or stream")
        if preview.pnm.created_cycle <= self._last_registration_cycle or preview.basis.cutoff_tick != self._last_cutoff:
            raise ValueError("seeking registration must follow this new frozen opportunity")
        if proposal.created_tick != self._last_cutoff:
            raise ValueError("seeking permission and prediction have different cutoffs")
        if not isinstance(targets, tuple) or len(targets) != len(proposal.bindings) or len(targets) > 1:
            raise ValueError("seeking permission must preserve the sole oral binding or veto")
        compatible: tuple[str, ...] = _RELATIONS
        unevaluable: tuple[str, ...] = ()
        for target, binding in zip(targets, proposal.bindings):
            if not isinstance(target, CommittedBodyTargetV1) or target.target is not binding.target:
                raise ValueError("seeking permission must retain the identical BodyMap binding")
            local = target.target
            if not isinstance(local, BodyRelativeTargetV1) or local.kind is not SensorimotorTargetKindV1.ORAL_REACH:
                raise ValueError("seeking correspondence requires the oral target family")
            if local.origin != request.origin or target.committed_tick != proposal.created_tick:
                raise ValueError("seeking permission changed origin or commitment time")
            if local.basis is not preview.basis.oral_feedback or target.expires_at_tick > self._last_cutoff + preview.horizon_ticks:
                raise ValueError("seeking target must preserve the original paired body basis and finite horizon")
            planar = local.basis.planar
            if planar is None or planar.position is None or planar.heading_degrees is None or planar.frame_id != preview.basis.frame_id:
                raise ValueError("seeking target lacks the original scene/body anchor")
            angle = math.radians(planar.heading_degrees)
            endpoint = NavPointV1(planar.position[0] + local.endpoint * math.cos(angle), planar.position[1] + local.endpoint * math.sin(angle))
            if _distance(endpoint, preview.predicted_mouth) > 1e-12:
                compatible, unevaluable = ("detail_anchor",), ("mouth_position", "separation")
        if preview.pnm.pnm_id in self._pending or any(item.claim.preview.pnm.pnm_id == preview.pnm.pnm_id for item in self._history):
            raise ValueError("seeking claim identity has already been registered")
        if len(self._pending) >= 8:
            raise OverflowError("eight unanswered seeking claims; no silent eviction or extra dispatch")
        claim = SeekNippleClaimV1(preview, request, targets, compatible, unevaluable)
        self._pending[preview.pnm.pnm_id] = _Pending(claim)
        self._last_registration_cycle = preview.pnm.created_cycle
        if targets:
            self._awaiting = claim
        else:
            self._finish(preview.pnm.pnm_id, "not_applied", self._last_cutoff, reason="BodyMap vetoed the original oral contribution")
        return claim

    def installed(self, claim: SeekNippleClaimV1, *, at_tick: int) -> None:
        """Record once-consumed successful installation, not a physical outcome."""
        tick = _tick(at_tick)
        if self._closed or not isinstance(claim, SeekNippleClaimV1) or claim is not self._awaiting or tick != self._last_cutoff:
            raise ValueError("installation must answer the exact awaiting seeking registration")
        self.end_execution(at_tick=tick, reason="replacement")
        self._pending[claim.preview.pnm.pnm_id].installed = True
        self._installed_target, self._execution_end_tick, self._awaiting = claim.targets[0], None, None

    def observe_rest_installation(self, target: CommittedBodyTargetV1, *, at_tick: int) -> None:
        """Record an actually accepted foreign Rest target, never attribute its action here.

        Rest reuses support/closure/reach resources. Preserve the full real command
        and sensor batch rather than manufacture neutral copies. Only the exact
        installation witnessed at this cutoff may explain its foreign reports.
        This method creates no claim, source relevance, participant or permission.
        """
        tick = _tick(at_tick)
        if (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyRelativeTargetV1)
                or target.target.rest_constraint is None or target.target.origin.stream != self.stream
                or target.committed_tick != tick or tick != self._last_cutoff):
            raise ValueError("foreign Rest evidence requires its actual current body installation")
        if self._rest_target is not None and target.committed_tick <= self._rest_target.committed_tick:
            raise ValueError("foreign Rest installation cannot be replayed or moved backward")
        self._rest_target, self._rest_end_tick = target, None

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """End pursuit, preserving already realized endpoint and buffered exposure.

        Cancellation before the original endpoint makes that forecast interrupted
        or cancelled after prior intervals are consumed. Cancellation at/after
        the endpoint cannot erase its already realized observation obligation.
        """
        tick = _tick(at_tick)
        if reason not in {"cancelled", "replacement"} or tick < self._last_cutoff:
            raise ValueError("seeking execution end has an invalid reason or historical time")
        if self._rest_target is not None and self._rest_end_tick is None:
            self._rest_end_tick = tick
        if self._installed_target is not None and self._execution_end_tick is None:
            self._execution_end_tick = tick
        for item in self._pending.values():
            if item.installed and item.ended_tick is None and tick < item.claim.due_tick:
                item.ended_tick, item.end_reason = tick, reason

    def close(self, *, reason: str) -> None:
        """Stop permanently after uncertainty without reporting invented nonapplication."""
        if not isinstance(reason, str) or not reason or len(reason) > 100:
            raise ValueError("seeking closure needs a bounded reason")
        if self._closed:
            return
        for claim_id in tuple(self._pending):
            self._finish(claim_id, "unresolved_stopped", max(0, self._last_cutoff), reason=reason)
        self._awaiting, self._installed_target, self._closed = None, None, True

    def _validate_batch(self, intervals: tuple[SeekNippleIntervalEvidenceV1, ...], cutoff: int) -> None:
        """Validate the entire frozen batch before modifying exposure or obligations."""
        if not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("at most sixteen frozen seeking intervals are permitted")
        previous_command = self._last_command_id
        known = {item.feedback.sample_id: item for item in self._recent}
        ended_at, rest_ended = self._execution_end_tick, self._rest_end_tick
        for index, interval in enumerate(intervals):
            if not isinstance(interval, SeekNippleIntervalEvidenceV1) or interval.tick != self._last_interval + index + 1:
                raise ValueError("seeking intervals must be contiguous and consumed once")
            if interval.tick + 1 > cutoff:
                raise ValueError("a future interval cannot enter the seeking frozen input")
            command = interval.command
            if command is not None:
                command.validate_for_update(stream=self.stream, now_tick=interval.tick, previous_command_id=previous_command)
                previous_command = command.command_id
            oral_reports = tuple(report for report in interval.reports if report.committed_target.target.kind is SensorimotorTargetKindV1.ORAL_REACH)
            if len(oral_reports) > 1:
                raise ValueError("one interval cannot repeat an oral resource")
            for report in interval.reports:
                if report.committed_target.target.origin.stream != self.stream:
                    raise ValueError("seeking execution evidence belongs to a foreign generation")
            if any(report.committed_target is not self._installed_target and report.committed_target is not self._rest_target for report in oral_reports):
                raise ValueError("oral report does not describe the original installed target")
            if command is not None and command.oral_drive not in (None, 0.0):
                if not oral_reports:
                    raise ValueError("oral command lacks its original authorized report")
                report = oral_reports[0]
                if (not report.committed_target.committed_tick <= interval.tick < report.committed_target.expires_at_tick
                        or report.reported_tick != interval.tick or report.disposition.value not in {"active", "partial"}):
                    raise ValueError("oral command lacks current live permission inside the original lease")
                end = rest_ended if report.committed_target is self._rest_target else ended_at
                if end is not None and interval.tick >= end:
                    raise ValueError("oral command follows explicit cancellation")
                if any(item.ended_tick is not None and interval.tick >= item.ended_tick for item in self._pending.values()
                       if item.claim.targets and item.claim.targets[0] is report.committed_target):
                    raise ValueError("oral command follows revoked seeking execution")
            for report in oral_reports:
                if report.disposition.value in {"cancelled", "interrupted", "unavailable", "blocked"}:
                    if report.committed_target is self._rest_target:
                        rest_ended = report.reported_tick if rest_ended is None else min(rest_ended, report.reported_tick)
                    else:
                        ended_at = report.reported_tick if ended_at is None else min(ended_at, report.reported_tick)
            for endpoint in interval.endpoints():
                sample = endpoint.feedback
                sample.validate_available(stream=self.stream, at_tick=cutoff)
                if sample.sample_id in known and known[sample.sample_id] != endpoint:
                    raise ValueError("one seeking acquisition cannot contain conflicting paired evidence")
                known[sample.sample_id] = endpoint
                for item in self._pending.values():
                    basis = item.claim.preview.basis
                    if sample.event_tick == item.claim.due_tick and (basis.oral_feedback is None or sample.sample_id <= basis.oral_feedback.sample_id):
                        raise ValueError("a seeking endpoint requires a distinct later acquisition")

    def consume_intervals(
        self, intervals: tuple[SeekNippleIntervalEvidenceV1, ...], *, cutoff_tick: int,
    ) -> tuple[SeekNippleOutcomeV1, ...]:
        """At C2 consume returned evidence once, then expire missing original endpoints.

        Comparison-off preserves registration, actual exposure, endpoint identity
        and all control paths. It disables only relational scoring. This owner
        performs bounded local comparisons, not demanding causal interpretation;
        no new task, focal allocation or learner is invoked.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_cutoff:
            raise ValueError("seeking consumption requires an open owner and a new cutoff")
        self._validate_batch(intervals, cutoff)
        before = self._number
        for interval in intervals:
            command = interval.command
            if command is not None:
                self._last_command_id = command.command_id
            if command is not None and command.oral_drive not in (None, 0.0):
                for item in self._pending.values():
                    if (item.installed and interval.tick < item.claim.due_tick
                            and (item.ended_tick is None or interval.tick < item.ended_tick)
                            and any(report.committed_target is item.claim.targets[0] for report in interval.reports)):
                        item.command_intervals += 1
            for report in interval.reports:
                if report.disposition.value not in {"cancelled", "interrupted", "unavailable", "blocked"}:
                    continue
                if report.committed_target is self._rest_target and self._rest_end_tick is None:
                    self._rest_end_tick = report.reported_tick
                if report.committed_target is self._installed_target and self._execution_end_tick is None:
                    self._execution_end_tick = report.reported_tick
                for item in self._pending.values():
                    if (item.installed and report.committed_target is item.claim.targets[0]
                            and item.ended_tick is None and report.reported_tick < item.claim.due_tick):
                        item.ended_tick, item.end_reason = report.reported_tick, report.reason
            for endpoint in interval.endpoints():
                self._consume_endpoint(endpoint, cutoff)
            self._last_interval = interval.tick
        for claim_id, item in tuple(self._pending.items()):
            if item.ended_tick is not None and self._last_interval + 1 >= item.ended_tick:
                self._finish(claim_id, "interrupted" if item.command_intervals else "cancelled", cutoff,
                             reason=f"{item.end_reason} before the original endpoint")
            elif cutoff > item.claim.expires_at_tick:
                self._finish(claim_id, "expired_unresolved", cutoff, reason="no exact endpoint within the original availability window")
        self._last_cutoff = cutoff
        return tuple(item for item in self._history if item.number > before)

    def _consume_endpoint(self, endpoint: SeekNippleEndpointV1, cutoff: int) -> None:
        """Match original event time, never substitute a later/current success sample."""
        sample = endpoint.feedback
        if any(item.feedback.sample_id == sample.sample_id for item in self._recent):
            return
        self._recent.append(endpoint)
        for claim_id, item in tuple(self._pending.items()):
            claim = item.claim
            if (not item.installed or item.ended_tick is not None or sample.event_tick != claim.due_tick
                    or sample.available_tick > claim.expires_at_tick):
                continue
            if not self.compare_predictions:
                self._finish(claim_id, "comparison_disabled", cutoff, evidence=endpoint,
                             reason="only original-endpoint scoring disabled; registration and execution retained")
                continue
            relations, residuals, identity = _compare(claim, endpoint)
            values = {value for _, value in relations}
            status = "mismatch" if "mismatch" in values else "unknown" if "unknown" in values else "matched"
            if status == "matched" and claim.unevaluable_relations:
                status = "partly_matched"
            if identity == "contradicted":
                status = "identity_contradicted"
            if item.command_intervals == 0:
                status = "observed_without_command"
            self._finish(claim_id, status, cutoff, evidence=endpoint, relations=relations, residuals=residuals,
                         reason="original seeking endpoint; neither task completion nor causal credit")

    def _finish(
        self, claim_id: str, status: str, tick: int, *, reason: str, evidence: SeekNippleEndpointV1 | None = None,
        relations: tuple[tuple[str, str], ...] = (), residuals: tuple[tuple[str, float], ...] = (),
    ) -> None:
        """Retire one obligation once and retain only a bounded immutable description."""
        item = self._pending.pop(claim_id)
        if self._awaiting is item.claim:
            self._awaiting = None
        self._number += 1
        self._history.append(SeekNippleOutcomeV1(self._number, item.claim, status, tick, evidence,
                                               relations, residuals, item.command_intervals, reason))


def _compare(
    claim: SeekNippleClaimV1, endpoint: SeekNippleEndpointV1,
) -> tuple[tuple[tuple[str, str], ...], tuple[tuple[str, float], ...], str]:
    """Compare fixed original mouth/detail relations using only this acquisition.

    Recognition/part support is a declared seeded scaffold, not learned identity.
    Unknown/absent visual products are not contradictions. Same-region category
    or part-geometry contradiction does not become a known nipple location.
    Touch is deliberately unscored: the original preview did not predict it.
    """
    preview, observation, sample = claim.preview, endpoint.observation, endpoint.feedback
    detail = next((item for item in observation.detections if item.region_id == preview.region_id), None) if observation is not None else None
    parent = (next((item for item in observation.detections if item.region_id == preview.basis.seed.parent_region_id), None)
              if observation is not None else None)
    identity = "unknown"
    if detail is not None and detail.descriptor is not None:
        if detail.descriptor != "feeding":
            identity = "contradicted"
        elif parent is not None and parent.descriptor is not None:
            if parent.descriptor != preview.basis.maternal.seed.descriptor:
                identity = "contradicted"
            elif parent.position is not None and detail.position is not None:
                identity = ("supported" if _distance(parent.position, detail.position) <= preview.basis.seed.maximum_parent_distance + 1e-12
                            else "contradicted")
    mouth = endpoint.mouth_position
    same_frame = sample.planar is not None and sample.planar.frame_id == preview.basis.frame_id
    residuals: dict[str, float] = {}
    if same_frame and mouth is not None:
        residuals["mouth_position"] = _distance(mouth, preview.predicted_mouth)
    if same_frame and identity == "supported" and detail is not None and detail.position is not None:
        residuals["detail_anchor"] = _distance(detail.position, preview.scene_target)
        if mouth is not None:
            residuals["separation"] = abs(_distance(detail.position, mouth) - preview.predicted_separation)
    relations = tuple((name, "unevaluable_authorization" if name in claim.unevaluable_relations else
                       "unknown" if name not in residuals else "matched" if residuals[name] <= _TOLERANCE + 1e-12 else "mismatch")
                      for name in _RELATIONS)
    return relations, tuple(residuals.items()), identity


def validate_seeking_claim_v1(claim: SeekNippleClaimV1, *, stream: MotorStreamRefV1) -> None:
    """Validate original prospective meaning and permission without inventing an outcome.

    The same read-only check serves the original outcome boundary and optional
    pre-execution participation. It neither publishes nor consumes evidence and
    cannot authorize installation. BodyMap narrowing preserves its original
    relation subset; a copied target cannot supply the original body basis.
    """
    if not isinstance(claim, SeekNippleClaimV1):
        raise TypeError("seeking participation requires a canonical seeking claim")
    if not isinstance(claim.preview, SeekNipplePreviewV1) or not isinstance(claim.request, OralReachRequestV1):
        raise TypeError("seeking outcome requires the original typed preview and request")
    preview, request = claim.preview, claim.request
    origin = request.origin
    if (preview.basis.stream != stream or origin.stream != stream or origin.task_id != preview.task_id
            or origin.application_id != preview.pnm.application_id or preview.pnm.primitive_id != "ip:seek_nipple"
            or request.source_map_ref != preview.basis.source_map_ref or request.region_id != preview.region_id
            or request.origin_status != "selected_seek_nipple" or request.lease_ticks != preview.horizon_ticks):
        raise ValueError("seeking outcome changed its original domain, source, task or stream")
    if not isinstance(claim.targets, tuple) or len(claim.targets) > 1:
        raise ValueError("seeking permission must be the original sole oral target or veto")
    for target in claim.targets:
        if (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyRelativeTargetV1)
                or target.target.kind is not SensorimotorTargetKindV1.ORAL_REACH or target.target.origin != origin
                or target.target.basis is not preview.basis.oral_feedback or target.committed_tick != preview.basis.cutoff_tick
                or target.expires_at_tick > claim.due_tick):
            raise ValueError("seeking permission does not retain the original body and horizon")
    expected_compatible: tuple[str, ...] = _RELATIONS
    expected_unevaluable: tuple[str, ...] = ()
    if claim.targets:
        local = claim.targets[0].target
        if not isinstance(local, BodyRelativeTargetV1):
            raise ValueError("seeking target must retain its oral-relative type")
        planar = local.basis.planar
        if planar is None or planar.position is None or planar.heading_degrees is None or planar.frame_id != preview.basis.frame_id:
            raise ValueError("seeking target lacks its original scene anchor")
        angle = math.radians(planar.heading_degrees)
        endpoint = NavPointV1(planar.position[0] + local.endpoint * math.cos(angle), planar.position[1] + local.endpoint * math.sin(angle))
        if _distance(endpoint, preview.predicted_mouth) > 1e-12:
            expected_compatible, expected_unevaluable = ("detail_anchor",), ("mouth_position", "separation")
    if claim.compatible_relations != expected_compatible or claim.unevaluable_relations != expected_unevaluable:
        raise ValueError("seeking relation subset disagrees with actual original BodyMap narrowing")
    for names in (claim.compatible_relations, claim.unevaluable_relations):
        if not isinstance(names, tuple) or any(name not in _RELATIONS for name in names) or len(set(names)) != len(names):
            raise ValueError("seeking authorization relation set is malformed")
    if (set(claim.compatible_relations) & set(claim.unevaluable_relations)
            or set(claim.compatible_relations) | set(claim.unevaluable_relations) != set(_RELATIONS)):
        raise ValueError("seeking permission must classify every original relation once")


def validate_seeking_outcome_v1(outcome: SeekNippleOutcomeV1, *, stream: MotorStreamRefV1, cutoff_tick: int) -> None:
    """Check a downstream description against its original canonical evidence.

    Used by the optional source relevance consumer, not by the physical driver.
    This read-only boundary rejects wrong domains, fabricated geometry scores,
    malformed permission subsets and future evidence. It reuses the original
    fixed comparison; it neither republishes an outcome nor consumes a claim.
    The actual publisher still owns exposure provenance and at-most-once
    consumption. A serialized/copied description never restores motor rights.
    """
    cutoff = _tick(cutoff_tick)
    if not isinstance(outcome, SeekNippleOutcomeV1) or not isinstance(outcome.claim, SeekNippleClaimV1):
        raise TypeError("seeking relevance requires a canonical seeking outcome")
    claim = outcome.claim
    validate_seeking_claim_v1(claim, stream=stream)
    preview = claim.preview
    if isinstance(outcome.number, bool) or not isinstance(outcome.number, int) or not 1 <= outcome.number < 2**63:
        raise ValueError("seeking outcome number must be a bounded positive integer")
    if not preview.basis.cutoff_tick <= _tick(outcome.evaluated_tick) <= cutoff:
        raise ValueError("seeking outcome cannot precede its original claim or arrive from the future")
    if (isinstance(outcome.command_intervals, bool) or not isinstance(outcome.command_intervals, int)
            or not 0 <= outcome.command_intervals <= preview.horizon_ticks):
        raise ValueError("seeking exposure must fit its original finite horizon")
    for rows in (outcome.relations, outcome.residuals):
        if not isinstance(rows, tuple) or len(rows) > 3 or any(not isinstance(row, tuple) or len(row) != 2 for row in rows):
            raise ValueError("seeking results require bounded immutable relation rows")
        if any(row[0] not in _RELATIONS for row in rows) or len({row[0] for row in rows}) != len(rows):
            raise ValueError("seeking results cannot contain unknown or duplicate relations")
    for _, residual in outcome.residuals:
        if isinstance(residual, bool) or not isinstance(residual, (int, float)) or not math.isfinite(residual) or residual < 0:
            raise ValueError("seeking residual must be finite and nonnegative")
    evidence = outcome.evidence
    if evidence is not None:
        if not isinstance(evidence, SeekNippleEndpointV1):
            raise TypeError("seeking result requires its original paired endpoint")
        evidence.feedback.validate_available(stream=stream, at_tick=outcome.evaluated_tick)
        if (evidence.feedback.event_tick != claim.due_tick or evidence.feedback.available_tick > claim.expires_at_tick
                or preview.basis.oral_feedback is None or evidence.feedback.sample_id <= preview.basis.oral_feedback.sample_id):
            raise ValueError("seeking result lacks the original distinct later acquisition")
    scored = {"matched", "partly_matched", "mismatch", "identity_contradicted", "unknown", "observed_without_command"}
    unscored = {"not_applied", "cancelled", "interrupted", "expired_unresolved", "unresolved_stopped", "comparison_disabled"}
    if outcome.status not in scored | unscored:
        raise ValueError("unknown seeking outcome disposition")
    if outcome.status in scored:
        if evidence is None or not claim.targets:
            raise ValueError("scored seeking outcome requires original permission and corresponding evidence")
        relations, residuals, identity = _compare(claim, evidence)
        values = {value for _, value in relations}
        status = "mismatch" if "mismatch" in values else "unknown" if "unknown" in values else "matched"
        if status == "matched" and claim.unevaluable_relations:
            status = "partly_matched"
        if identity == "contradicted":
            status = "identity_contradicted"
        if outcome.command_intervals == 0:
            status = "observed_without_command"
        if outcome.relations != relations or outcome.residuals != residuals or outcome.status != status:
            raise ValueError("seeking result disagrees with its original canonical endpoint comparison")
    elif outcome.relations or outcome.residuals:
        raise ValueError("unscored seeking outcome cannot contain geometric verdicts")
    if outcome.status == "not_applied" and (claim.targets or outcome.command_intervals or evidence is not None):
        raise ValueError("nonapplication cannot hide authorized execution or scored evidence")
