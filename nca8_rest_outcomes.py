#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-owned Rest correspondence, focal questions and trace-only participation.

These are concrete responsibilities of the existing body-sensory source and Rest
operation, not another comparator executive or central learning writer. Immutable
original applications and actual returned physical intervals are the only outcome
basis. A meaningful question competes through the existing Navigation allocator;
Phase F may reconcile its already-performed result but cannot interpret it. No
method here issues a target, advances the world, selects an IP or changes durable
knowledge. Diagnostic retention and evidence/eligibility lifetimes are separate.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
from collections import deque

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavMapRefV1
from nca8_executive import AttentionBidV1, NavigationDecisionV1, OutcomeInterpretationCandidateV1, WorkingNavMapStateV1
from nca8_maps import NavMapStateV1
from nca8_outcomes import RightingIntervalEvidenceV1
from nca8_rest import RestApplicationV1, RestProfileV1, RestTaskV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, CommittedBodyTargetV1, LocalTargetDispositionV1, scalar_motor_coordinate_v1

__version__ = "0.1.0"
__all__ = ["RestClaimV1", "RestOutcomeV1", "RestQuestionV1", "RestInterpretationV1", "RestFocalAllocationV1",
           "RestPhaseFReportV1", "RestParticipationV1", "RestOutcomeRuntimeV1", "RestCycleFrameV1", "validate_rest_outcome_v1", "__version__"]


def _tick(value: int, *, minimum: int = 0) -> int:
    """Keep supplied clocks finite, increasing where required and never Boolean."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value < 2**63 - 321:
        raise ValueError("Rest evidence requires a bounded integer clock")
    return value


def _drive(command: MotorCommandV1 | None, contribution: str) -> float:
    """Read the actual command channel; this observer never constructs a drive."""
    if command is None:
        return 0.0
    if contribution == "release":
        return (command.oral_closure_drive or 0.0)
    if contribution == "withdraw":
        return (command.oral_drive or 0.0)
    return command.extension_drive


@dataclass(frozen=True, slots=True)
class RestClaimV1:
    """Original selected application and separately authorized target, before movement."""

    application: RestApplicationV1
    target: CommittedBodyTargetV1 | None

    def __post_init__(self) -> None:
        if not isinstance(self.application, RestApplicationV1):
            raise TypeError("Rest claim requires an original selected application")
        target = self.target
        if target is not None:
            if not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyRelativeTargetV1):
                raise TypeError("Rest claim requires a canonical scalar target")
            app = self.application
            if (target.target.origin != app.contribution.origin or target.target.rest_constraint != app.contribution.contribution
                    or target.target.basis != app.projection.basis.feedback or target.committed_tick != app.projection.basis.cutoff_tick
                    or target.target.lease_ticks != app.projection.horizon_ticks):
                raise ValueError("Rest claim cannot substitute target origin, body basis or lease")

    @property
    def application_id(self) -> str:
        """Return the original application identity, not the latest active task."""
        return self.application.application_id

    @property
    def start_tick(self) -> int:
        """Return the immutable original focal boundary."""
        return self.application.projection.basis.cutoff_tick

    @property
    def due_tick(self) -> int:
        """Return the original observation event, not the publication time."""
        return self.start_tick + self.application.projection.horizon_ticks

    def as_dict(self) -> dict[str, object]:
        """Serialize original expectation and permission as distinct descriptions."""
        return {"application": self.application.as_dict(), "target": None if self.target is None else self.target.as_dict(),
                "due_tick": self.due_tick, "last_arrival_tick": self.due_tick + 8}


@dataclass(frozen=True, slots=True)
class RestOutcomeV1:
    """Immutable measured result of one original claim; never full Rest completion."""

    claim: RestClaimV1
    published_tick: int
    installed: bool
    ended_tick: int | None
    command_ticks: tuple[int, ...]
    evidence: MotorFeedbackV1 | None
    status: str
    relations: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Keep actual execution, relations and task completion explicitly separate."""
        return {"claim": self.claim.as_dict(), "published_tick": self.published_tick, "installed": self.installed,
                "ended_tick": self.ended_tick, "command_ticks": list(self.command_ticks),
                "evidence": None if self.evidence is None else self.evidence.as_dict(), "status": self.status,
                "relations": dict(self.relations), "task_success": "not_established", "causal_credit": "uncertain"}


def _calculate_outcome(
    claim: RestClaimV1, *, published_tick: int, installed: bool, ended_tick: int | None,
    command_ticks: tuple[int, ...], evidence: MotorFeedbackV1 | None,
) -> RestOutcomeV1:
    """Canonical pure relation calculation shared by publication and validation."""
    if not isinstance(claim, RestClaimV1) or not isinstance(installed, bool):
        raise TypeError("Rest outcome requires original claim and real installation flag")
    _tick(published_tick, minimum=claim.start_tick + 1)
    if ended_tick is not None:
        _tick(ended_tick, minimum=claim.start_tick)
        if ended_tick > published_tick:
            raise ValueError("Rest outcome cannot know a future cancellation")
    if (not isinstance(command_ticks, tuple) or len(command_ticks) > 8
            or any(isinstance(t, bool) or not isinstance(t, int) or not claim.start_tick <= t < claim.due_tick for t in command_ticks)
            or tuple(sorted(set(command_ticks))) != command_ticks):
        raise ValueError("Rest outcome requires bounded distinct actual command intervals")
    if evidence is not None:
        if not isinstance(evidence, MotorFeedbackV1) or evidence.event_tick != claim.due_tick:
            raise ValueError("Rest result needs the original exact due acquisition")
        evidence.validate_available(stream=claim.application.task.stream, at_tick=published_tick)
        original = claim.application.projection.basis.feedback
        if original is None or evidence.sample_id <= original.sample_id:
            raise ValueError("Rest endpoint must be a new original body acquisition")
        if evidence.available_tick > claim.due_tick + 8:
            raise ValueError("too-late evidence cannot replace the original arrival window")
    if ended_tick is not None and any(t >= ended_tick for t in command_ticks):
        raise ValueError("Rest cannot execute after its original permission ended")
    if installed and claim.target is None:
        raise ValueError("a vetoed Rest request cannot be installed")
    if command_ticks and (not installed or claim.target is None):
        raise ValueError("uninstalled Rest cannot claim executed commands")
    coordinate, support = "unknown", "unknown"
    if claim.target is None:
        status = "not_applied"
    elif not installed:
        status = "expired_unresolved"
    elif ended_tick is not None and ended_tick < claim.due_tick:
        status = "interrupted" if command_ticks else "cancelled"
    elif evidence is None:
        status = "expired_unresolved"
    else:
        target = claim.target.target
        actual = scalar_motor_coordinate_v1(evidence, target.kind)
        if actual is not None:
            tolerance = .005 if claim.application.contribution.contribution == "withdraw" else .025
            coordinate = "matched" if abs(actual - claim.application.projection.predicted_coordinate) <= tolerance + 1e-12 else "mismatch"
        bearing = evidence.body_bearing
        limb_known = evidence.support_contact is not None and evidence.useful_loading is not None
        body_known = bearing is not None and bearing.contact is not None and bearing.bearing is not None
        if ((limb_known and evidence.support_contact and evidence.useful_loading is not None and evidence.useful_loading > 0)
                or (body_known and bearing is not None and bearing.contact and bearing.bearing is not None and bearing.bearing > 0)):
            support = "matched"
        elif limb_known and body_known:
            support = "mismatch"
        status = "mismatch" if "mismatch" in (coordinate, support) else "unknown" if "unknown" in (coordinate, support) else "matched"
    if status == "expired_unresolved" and published_tick <= claim.due_tick + 8:
        raise ValueError("unresolved Rest claim cannot expire before its arrival allowance")
    return RestOutcomeV1(claim, published_tick, installed, ended_tick, command_ticks, evidence, status,
                         (("coordinate", coordinate), ("support", support)))


def validate_rest_outcome_v1(outcome: RestOutcomeV1) -> None:
    """Reject forged verdicts without consuming, refreshing or rescoring as a new event."""
    if not isinstance(outcome, RestOutcomeV1):
        raise TypeError("Rest evidence must be a canonical outcome")
    actual = _calculate_outcome(outcome.claim, published_tick=outcome.published_tick, installed=outcome.installed,
                                ended_tick=outcome.ended_tick, command_ticks=outcome.command_ticks, evidence=outcome.evidence)
    if actual != outcome:
        raise ValueError("Rest verdict differs from its original canonical evidence")


@dataclass(frozen=True, slots=True)
class RestQuestionV1:
    """One bounded source question; its creation grants no focal work or action."""

    outcome: RestOutcomeV1
    admitted_tick: int

    def __post_init__(self) -> None:
        validate_rest_outcome_v1(self.outcome)
        _tick(self.admitted_tick)
        if self.outcome.status != "mismatch" or self.admitted_tick != self.outcome.published_tick:
            raise ValueError("Rest question requires its actual significant original publication")

    @property
    def request_id(self) -> str:
        """Stable tie key inside Navigation's existing same-source allocation."""
        return f"rest_question:{self.outcome.claim.application_id}"

    @property
    def expires_at_tick(self) -> int:
        """Exclusive original expiry unaffected by rereads or losing attention."""
        return self.admitted_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Render provenance only, never a selected source or motor request."""
        return {"request_id": self.request_id, "application_id": self.outcome.claim.application_id,
                "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick}


@dataclass(frozen=True, slots=True)
class RestInterpretationV1:
    """An actually Navigation-granted current-relevance result with its original question."""

    request: RestQuestionV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    status: str
    evidence: MotorFeedbackV1 | None
    current_relations: tuple[tuple[str, str], ...]

    def __post_init__(self) -> None:
        if not isinstance(self.request, RestQuestionV1):
            raise TypeError("Rest interpretation requires its original question")
        _tick(self.cycle_id, minimum=1)
        _tick(self.cutoff_tick, minimum=self.request.admitted_tick)
        if self.cutoff_tick >= self.request.expires_at_tick or not isinstance(self.working_id, str) or not self.working_id:
            raise ValueError("Rest interpretation requires current focal identity before expiry")
        if self.status not in {"still_relevant", "historical_resolved", "unresolved_current_relevance"}:
            raise ValueError("unknown Rest interpretation")
        if self.evidence is not None:
            self.evidence.validate_available(stream=self.request.outcome.claim.application.task.stream, at_tick=self.cutoff_tick)
        expected_names = tuple(name for name, status in self.request.outcome.relations if status == "mismatch")
        if (not isinstance(self.current_relations, tuple) or tuple(name for name, _ in self.current_relations) != expected_names
                or any(status not in {"still_relevant", "historical_resolved", "unresolved_current_relevance"}
                       for _, status in self.current_relations)):
            raise ValueError("Rest interpretation witnesses must name the original mismatching relations")
        statuses = tuple(status for _, status in self.current_relations)
        overall = ("still_relevant" if "still_relevant" in statuses else "unresolved_current_relevance"
                   if "unresolved_current_relevance" in statuses else "historical_resolved")
        if self.status != overall or self.evidence is None and any(status != "unresolved_current_relevance" for status in statuses):
            raise ValueError("Rest interpretation summary must agree with its actually computed witnesses")

    def as_dict(self) -> dict[str, object]:
        """Separate current relevance from unchanged historical prediction evidence."""
        return {"request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "working_id": self.working_id, "status": self.status,
                "current_evidence": None if self.evidence is None else self.evidence.as_dict(),
                "current_relations": dict(self.current_relations), "demanding_allocations": 1, "durable_learning_updates": 0}


@dataclass(frozen=True, slots=True)
class RestFocalAllocationV1:
    """This opportunity's allocation; a retained prior result is not newly performed work."""

    kind: str
    interpretation: RestInterpretationV1 | None = None

    def __post_init__(self) -> None:
        if self.kind not in {"ordinary", "other_source", "navigation_disabled", "deferred_other_question", "interpretation",
                             "dependent_unresolved", "response_reconsideration"}:
            raise ValueError("unknown Rest focal allocation")
        requires_result = self.kind in {"interpretation", "dependent_unresolved", "response_reconsideration"}
        if requires_result != isinstance(self.interpretation, RestInterpretationV1):
            raise ValueError("Rest allocation result does not match its performed/retained kind")

    @property
    def permits_primitive_selection(self) -> bool:
        """Report whether a demanding question/dependency already occupies this opportunity."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Read the allocation without repeating an interpretation."""
        return {"kind": self.kind, "interpretation": None if self.interpretation is None else self.interpretation.as_dict(),
                "interpretations_this_opportunity": int(self.kind == "interpretation"),
                "permits_primitive_selection": self.permits_primitive_selection}


class RestOutcomeRuntimeV1:
    """Bounded correspondence/relevance owned by the existing body-sensory source.

    A single pending endpoint and at most eight original applications suffice for
    the first Rest task. Acquisition/command watermarks survive replacement. The
    diagnostic deque is never read to admit evidence, choose work or renew clocks.
    """

    def __init__(self, stream: MotorStreamRefV1, source_ref: NavMapRefV1, profile: RestProfileV1) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(source_ref, NavMapRefV1) or not isinstance(profile, RestProfileV1):
            raise TypeError("Rest source correspondence needs original typed owners/profile")
        self.stream, self.source_ref, self.profile = stream, source_ref, profile
        self._claims: dict[str, RestClaimV1] = {}
        self._outcomes: dict[str, RestOutcomeV1] = {}
        self._pending: RestClaimV1 | None = None
        self._installed: CommittedBodyTargetV1 | None = None
        self._installed_claim: RestClaimV1 | None = None
        self._ended_tick: int | None = None
        self._commands: tuple[int, ...] = ()
        self._evidence: MotorFeedbackV1 | None = None
        self._last_interval, self._last_command, self._cutoff, self._last_registration = -1, 0, -1, 0
        self._known: deque[MotorFeedbackV1] = deque(maxlen=16)
        self._questions: list[RestQuestionV1] = []
        self._dependency: RestInterpretationV1 | None = None
        self._source: NavMapStateV1 | None = None
        self._last_admission, self._last_allocation = -1, 0
        self._history: deque[tuple[str, str, int]] = deque(maxlen=8)
        self._closed = False
        self.participation = RestParticipationV1(stream) if profile.learning_hook_enabled else None

    def register(self, application: RestApplicationV1, target: CommittedBodyTargetV1 | None) -> RestClaimV1:
        """Register actual selected work before execution, never reconstruct it on arrival."""
        if self._closed or self._pending is not None or len(self._claims) >= 8:
            raise ValueError("Rest claim capacity or lifecycle prohibits another original")
        claim = RestClaimV1(application, target)
        if (application.task.stream != self.stream or application.task.source_map_ref != self.source_ref
                or application.cycle_id <= self._last_registration or claim.start_tick != self._cutoff):
            raise ValueError("Rest claim requires current original source/generation/cutoff")
        if self._claims:
            first = next(iter(self._claims.values())).application.task
            current = application.task
            if ((first.task_id, first.started_tick, first.started_cycle) != (current.task_id, current.started_tick, current.started_cycle)
                    or current.applications != len(self._claims) + 1):
                raise ValueError("Rest episode basis or contribution count cannot drift")
        elif application.task.applications != 1:
            raise ValueError("Rest first registration must be its first application")
        self._claims[claim.application_id] = claim
        self._pending, self._last_registration = claim, application.cycle_id
        self._commands, self._evidence, self._ended_tick = (), None, None
        return claim

    def installed(self, claim: RestClaimV1, *, at_tick: int) -> None:
        """Observe the actual outer handoff installation once, not a command or movement."""
        tick = _tick(at_tick)
        if self._closed or self._pending is not claim or claim.target is None or tick != claim.start_tick:
            raise ValueError("Rest install must name its awaiting original claim and cutoff")
        if self._installed_claim is claim:
            raise ValueError("Rest installation cannot be consumed twice")
        self._installed, self._installed_claim = claim.target, claim

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """End current pursuit, preserving any already-realized endpoint obligation."""
        tick = _tick(at_tick, minimum=max(0, self._cutoff))
        if self._closed:
            raise ValueError("closed Rest source cannot change execution disposition")
        if reason not in {"cancelled", "replacement", "execution_unknown", "not_applied"}:
            raise ValueError("unknown Rest execution disposition")
        if self._pending is self._installed_claim and self._ended_tick is None:
            self._ended_tick = tick

    def _validate_intervals(self, intervals: tuple[RightingIntervalEvidenceV1, ...], cutoff: int) -> None:
        """Validate a whole frozen batch before any watermark or outcome mutation."""
        if not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("Rest accepts at most sixteen actual returned intervals")
        known = {f.sample_id: f for f in self._known}
        last_command = self._last_command
        ended = self._ended_tick
        for offset, interval in enumerate(intervals, 1):
            if not isinstance(interval, RightingIntervalEvidenceV1) or interval.tick != self._last_interval + offset or interval.tick >= cutoff:
                raise ValueError("Rest intervals must be contiguous, original and already returned")
            command = interval.command
            if command is not None:
                if command.stream != self.stream or command.command_id <= last_command:
                    raise ValueError("Rest command stream/watermark mismatch")
                last_command = command.command_id
            for feedback in interval.deliveries:
                feedback.validate_available(stream=self.stream, at_tick=interval.tick + 1)
                if feedback.sample_id in known and feedback != known[feedback.sample_id]:
                    raise ValueError("conflicting original Rest acquisition")
                known[feedback.sample_id] = feedback
            rest_reports = tuple(item for item in interval.reports if isinstance(item.committed_target.target, BodyRelativeTargetV1)
                                 and item.committed_target.target.rest_constraint is not None)
            for report in rest_reports:
                if self._installed is None or report.committed_target is not self._installed or report.reported_tick > interval.tick:
                    raise ValueError("Rest report must belong to the actually installed original target")
            if self._installed_claim is not None and self._installed is not None:
                drive = _drive(command, self._installed_claim.application.contribution.contribution)
                other_owns_channel = any(item.committed_target.target.kind == self._installed.target.kind
                                         and item.committed_target is not self._installed for item in interval.reports)
                if drive and not other_owns_channel:
                    if not rest_reports:
                        raise ValueError("Rest drive cannot omit its original permission report")
                    report = rest_reports[0]
                    if (len(rest_reports) != 1 or report.reported_tick != interval.tick or report.disposition not in
                            {LocalTargetDispositionV1.ACTIVE, LocalTargetDispositionV1.PARTIAL}
                            or interval.tick >= report.committed_target.expires_at_tick
                            or ended is not None and interval.tick >= ended):
                        raise ValueError("Rest drive requires current active unexpired original permission")
            for report in rest_reports:
                if report.disposition in {LocalTargetDispositionV1.BLOCKED, LocalTargetDispositionV1.UNAVAILABLE,
                                          LocalTargetDispositionV1.CANCELLED, LocalTargetDispositionV1.INTERRUPTED,
                                          LocalTargetDispositionV1.EXPIRED, LocalTargetDispositionV1.UNRESOLVED}:
                    ended = report.reported_tick if ended is None else min(ended, report.reported_tick)

    def consume(self, intervals: tuple[RightingIntervalEvidenceV1, ...], *, cutoff_tick: int) -> tuple[RestOutcomeV1, ...]:
        """Publish at most one due original result, with no extra physical sampling."""
        cutoff = _tick(cutoff_tick, minimum=self._cutoff + 1)
        if self._closed:
            raise ValueError("closed Rest source cannot consume new evidence")
        self._validate_intervals(intervals, cutoff)
        claim = self._pending
        commands = list(self._commands)
        evidence, ended = self._evidence, self._ended_tick
        for interval in intervals:
            if claim is not None:
                report_matches = any(item.committed_target is claim.target for item in interval.reports)
                if report_matches and claim.start_tick <= interval.tick < claim.due_tick and _drive(interval.command, claim.application.contribution.contribution):
                    commands.append(interval.tick)
                for report in interval.reports:
                    if report.committed_target is claim.target and report.disposition in {
                            LocalTargetDispositionV1.BLOCKED, LocalTargetDispositionV1.UNAVAILABLE,
                            LocalTargetDispositionV1.CANCELLED, LocalTargetDispositionV1.INTERRUPTED,
                            LocalTargetDispositionV1.EXPIRED, LocalTargetDispositionV1.UNRESOLVED}:
                        ended = report.reported_tick if ended is None else min(ended, report.reported_tick)
                for feedback in interval.deliveries:
                    if feedback.event_tick == claim.due_tick and feedback.available_tick <= claim.due_tick + 8:
                        evidence = feedback
        result: RestOutcomeV1 | None = None
        if claim is not None and cutoff > claim.start_tick:
            installed = self._installed_claim is claim
            due = (claim.target is None or evidence is not None or cutoff > claim.due_tick + 8
                   or installed and ended is not None and ended < claim.due_tick)
            if due:
                result = _calculate_outcome(claim, published_tick=cutoff, installed=installed, ended_tick=ended,
                                            command_ticks=tuple(commands), evidence=evidence)
        # Commit watermarks only after the entire prospective publication validates.
        for interval in intervals:
            if interval.command is not None:
                self._last_command = interval.command.command_id
            self._known.extend(interval.deliveries)
            self._last_interval = interval.tick
        self._commands, self._evidence, self._ended_tick, self._cutoff = tuple(commands), evidence, ended, cutoff
        if result is None:
            return ()
        self._outcomes[result.claim.application_id] = result
        self._pending = None
        self._history.append((result.claim.application_id, result.status, cutoff))
        return (result,)

    def admit(self, source: NavMapStateV1, outcomes: tuple[RestOutcomeV1, ...], *, at_tick: int) -> None:
        """Retain significant questions under this source, without performing interpretation."""
        tick = _tick(at_tick, minimum=self._last_admission + 1)
        if (self._closed or not isinstance(source, NavMapStateV1) or source.source_map_ref != self.source_ref
                or source.motor_support is None or source.motor_support.stream != self.stream or source.motor_support.cutoff_tick != tick):
            raise ValueError("Rest relevance needs the actual body source/cutoff")
        if not isinstance(outcomes, tuple) or len(outcomes) > 1:
            raise ValueError("Rest relevance consumes at most one actual new publication")
        for outcome in outcomes:
            validate_rest_outcome_v1(outcome)
            if self._outcomes.get(outcome.claim.application_id) is not outcome or outcome.published_tick != tick:
                raise ValueError("Rest relevance cannot read unregistered or diagnostic outcomes")
        questions = [item for item in self._questions if tick < item.expires_at_tick]
        if self.profile.outcome_attention_enabled:
            for outcome in outcomes:
                if outcome.status == "mismatch" and all(item.outcome is not outcome for item in questions):
                    questions.append(RestQuestionV1(outcome, tick))
        if len(questions) > 8:
            raise OverflowError("Rest question capacity exceeded; no silent eviction")
        self._questions, self._source, self._last_admission = questions, source, tick
        if self._dependency is not None and tick >= self._dependency.request.expires_at_tick:
            self._dependency = None

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Add only an outcome-related source rank; no source choice or motor authority."""
        source = self._source
        if source is None:
            raise ValueError("Rest relevance requires source admission first")
        if ordinary is not None and ordinary.source_map_state is not source:
            raise ValueError("Rest relevance cannot change the source object")
        if not self._questions or not self.profile.attention_enabled:
            return ordinary
        if ordinary is None:
            ordinary = AttentionBidV1(f"support_bid:{source.applied_cycle}", "source:posture_support", source, "body_sensory",
                                      source.applied_cycle, 0, 0, 0, 0, 0, 20, (), False, "source:posture_support")
        return replace(ordinary, prediction_or_envelope_failure_rank=max(40, ordinary.prediction_or_envelope_failure_rank),
                        reasons=(*ordinary.reasons, "rest_original_outcome_question"))

    def interpretation_candidate(self, working: WorkingNavMapStateV1 | None, *, cycle_id: int) -> OutcomeInterpretationCandidateV1 | None:
        """Offer one pending head without consuming a question or running its interpretation."""
        _tick(cycle_id, minimum=1)
        if self._closed or self._source is None or cycle_id != self._source.applied_cycle:
            raise ValueError("Rest candidacy needs this admitted open opportunity")
        if not self._questions or working is None or working.primary_source_state.source_map_ref != self.source_ref:
            return None
        if working.refreshed_cycle != cycle_id or working.primary_source_state is not self._source:
            raise ValueError("Rest question requires this exact source in WNM")
        item = self._questions[0]
        return OutcomeInterpretationCandidateV1(item.request_id, self._source, item.admitted_tick, item.expires_at_tick)

    def allocate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int, grant: NavigationDecisionV1 | None = None,
        deferred: bool = False,
    ) -> RestFocalAllocationV1:
        """Interpret only after an actual Navigation grant; preserve losing requests."""
        candidate = self.interpretation_candidate(working, cycle_id=cycle_id)
        if cycle_id <= self._last_allocation or not isinstance(deferred, bool):
            raise ValueError("Rest allocation must be one increasing opportunity")
        if candidate is not None and not deferred:
            if (not isinstance(grant, NavigationDecisionV1) or grant.cycle_id != cycle_id or grant.wnm is not working
                    or grant.application is not None or grant.reason != f"outcome_interpretation:{candidate.request_id}"):
                raise ValueError("Rest interpretation requires Navigation's matching original grant")
        self._last_allocation = cycle_id
        if candidate is not None and deferred:
            return RestFocalAllocationV1("deferred_other_question")
        source = self._source
        if working is None or source is None or working.primary_source_state is not source:
            return RestFocalAllocationV1("other_source")
        if candidate is not None:
            question = self._questions.pop(0)
            facet = source.motor_support
            f = None if facet is None or not facet.current else facet.feedback
            target = question.outcome.claim.target
            value = None if f is None or target is None else scalar_motor_coordinate_v1(f, target.target.kind)
            tolerance = .005 if question.outcome.claim.application.contribution.contribution == "withdraw" else .025
            witnesses: list[tuple[str, str]] = []
            for relation, old_result in question.outcome.relations:
                if old_result != "mismatch":
                    continue
                relevant: bool | None = None
                if relation == "coordinate" and value is not None:
                    relevant = abs(value - question.outcome.claim.application.projection.predicted_coordinate) > tolerance
                elif relation == "support" and f is not None:
                    body = f.body_bearing
                    if (f.support_contact is True and f.useful_loading is not None and f.useful_loading > 0
                            or body is not None and body.contact is True and body.bearing is not None and body.bearing > 0):
                        relevant = False
                    elif (f.support_contact is not None and f.useful_loading is not None and body is not None
                          and body.contact is not None and body.bearing is not None):
                        relevant = True
                witnesses.append((relation, "unresolved_current_relevance" if relevant is None else
                                  "still_relevant" if relevant else "historical_resolved"))
            statuses = tuple(status for _, status in witnesses)
            status = ("still_relevant" if "still_relevant" in statuses else "unresolved_current_relevance"
                      if "unresolved_current_relevance" in statuses else "historical_resolved")
            interpretation = RestInterpretationV1(question, cycle_id, self._last_admission, working.working_id, status, f, tuple(witnesses))
            self._dependency = interpretation
            self._history.append((question.request_id, "interpreted", self._last_admission))
            return RestFocalAllocationV1("interpretation", interpretation)
        dependency = self._dependency
        if dependency is None:
            return RestFocalAllocationV1("ordinary")
        if dependency.status == "unresolved_current_relevance":
            return RestFocalAllocationV1("dependent_unresolved", dependency)
        self._dependency = None
        return RestFocalAllocationV1("response_reconsideration", dependency)

    def retained_counts(self) -> dict[str, int]:
        """Read bounded functional catalogs separately from disposable diagnostic history."""
        return {"rest_claims": len(self._claims), "rest_pending_claims": int(self._pending is not None),
                "rest_outcomes": len(self._outcomes), "rest_questions": len(self._questions),
                "rest_dependency": int(self._dependency is not None), "rest_recent_acquisitions": len(self._known),
                "rest_diagnostic_history": len(self._history),
                **(self.participation.retained_counts() if self.participation is not None else {})}

    def outcomes(self) -> tuple[RestOutcomeV1, ...]:
        """Return immutable actual publications, not independently manufactured verdicts."""
        return tuple(self._outcomes.values())

    def questions(self) -> tuple[RestQuestionV1, ...]:
        """Read current original questions without renewing their lifetimes."""
        return tuple(self._questions)

    def close(self) -> None:
        """End input/interpretation while retaining only read-only original history."""
        self._closed = True
        self._questions.clear()
        self._dependency = None
        if self.participation is not None:
            self.participation.close()


@dataclass(frozen=True, slots=True)
class RestPhaseFReportV1:
    """One source-owned no-update reconciliation; F is a checkpoint, not an evaluator."""

    cycle_id: int
    cutoff_tick: int
    registration: RestClaimV1 | None
    dispositions: tuple[tuple[str, str], ...]
    pending: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """Report actual reconciliation without a reward, motor grant or learned value."""
        return {"owner": "body_sensory/rest_participation", "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "registration": None if self.registration is None else self.registration.application_id,
                "dispositions": [{"application_id": key, "status": value} for key, value in self.dispositions],
                "pending": list(self.pending), "durable_learning_updates": 0}


class RestParticipationV1:
    """Bounded trace-only local participation, independent of Rest task and permission.

    Register at F before execution. Later canonical relations and actually allocated
    interpretations can be reconciled before that original application's +24 cutoff.
    This branch can be absent without changing need, task, bids, targets or physics.
    """

    def __init__(self, stream: MotorStreamRefV1) -> None:
        if not isinstance(stream, MotorStreamRefV1):
            raise TypeError("Rest participation requires its actual stream")
        self.stream = stream
        self._claims: dict[str, RestClaimV1] = {}
        self._outcomes: dict[str, RestOutcomeV1] = {}
        self._done: set[str] = set()
        self._history: deque[tuple[str, str]] = deque(maxlen=8)
        self._cycle, self._tick, self._closed = 0, -1, False

    def reconcile(
        self, *, cycle_id: int, cutoff_tick: int, registration: RestClaimV1 | None,
        outcomes: tuple[RestOutcomeV1, ...], allocation: RestFocalAllocationV1 | None,
    ) -> RestPhaseFReportV1:
        """Validate the complete old-outcome/new-registration transaction before mutation."""
        cycle, tick = _tick(cycle_id, minimum=self._cycle + 1), _tick(cutoff_tick, minimum=self._tick + 1)
        if self._closed or not isinstance(outcomes, tuple) or len(outcomes) > 1:
            raise ValueError("invalid or closed Rest reconciliation")
        if allocation is not None and not isinstance(allocation, RestFocalAllocationV1):
            raise TypeError("Rest reconciliation needs a typed actual allocation")
        claims = dict(self._claims)
        received = dict(self._outcomes)
        if registration is not None:
            if (not isinstance(registration, RestClaimV1) or registration.application.task.stream != self.stream
                    or registration.start_tick != tick or registration.application.cycle_id != cycle
                    or registration.application_id in claims or len(claims) >= 8):
                raise ValueError("Rest participation needs actual new E registration before execution")
            if claims:
                first = next(iter(claims.values())).application.task
                current = registration.application.task
                if ((first.task_id, first.started_tick, first.started_cycle, first.source_map_ref) !=
                        (current.task_id, current.started_tick, current.started_cycle, current.source_map_ref)
                        or current.applications != len(claims) + 1):
                    raise ValueError("Rest participation cannot rebase the originating episode")
            elif registration.application.task.applications != 1:
                raise ValueError("Rest participation requires its actual first application")
            claims[registration.application_id] = registration
        for outcome in outcomes:
            validate_rest_outcome_v1(outcome)
            key = outcome.claim.application_id
            if (self._claims.get(key) is not outcome.claim or outcome.published_tick != tick
                    or outcome.claim.start_tick >= tick):
                raise ValueError("Rest outcome cannot invent old participation or use a new registration")
            if key in received and received[key] is not outcome:
                raise ValueError("Rest outcome replay cannot change identity or evidence")
            received[key] = outcome
        interpreted_key: str | None = None
        if allocation is not None and allocation.kind == "interpretation":
            interpretation = allocation.interpretation
            if not isinstance(interpretation, RestInterpretationV1):
                raise ValueError("performed Rest allocation needs its actual result")
            outcome = interpretation.request.outcome
            interpreted_key = outcome.claim.application_id
            if (received.get(interpreted_key) is not outcome or interpretation.cycle_id != cycle
                    or interpretation.cutoff_tick != tick or tick >= interpretation.request.expires_at_tick
                    or not interpretation.working_id or interpretation.status not in
                    {"still_relevant", "historical_resolved", "unresolved_current_relevance"}
                    or outcome.status != "mismatch" or interpretation.request.admitted_tick != outcome.published_tick):
                raise ValueError("Rest F cannot borrow an old, foreign or unperformed interpretation")
            if interpretation.evidence is not None:
                interpretation.evidence.validate_available(stream=self.stream, at_tick=tick)
            if interpretation.status == "unresolved_current_relevance":
                interpreted_key = None
        done = set(self._done)
        dispositions: list[tuple[str, str]] = []
        for key, claim in claims.items():
            if key in done:
                continue
            current_outcome = received.get(key)
            if tick >= claim.start_tick + 24:
                dispositions.append((key, "eligibility_expired"))
                done.add(key)
            elif current_outcome is not None:
                if current_outcome.status == "mismatch" and interpreted_key != key:
                    dispositions.append((key, "pending_interpretation"))
                else:
                    status = ("accepted_no_update" if current_outcome.status in {"matched", "mismatch"}
                              else f"rejected_{current_outcome.status}")
                    dispositions.append((key, status))
                    done.add(key)
        self._claims, self._outcomes, self._done = claims, received, done
        self._cycle, self._tick = cycle, tick
        self._history.extend(dispositions)
        return RestPhaseFReportV1(cycle, tick, registration, tuple(dispositions), tuple(key for key in claims if key not in done))

    def retained_counts(self) -> dict[str, int]:
        """Read participant/replay bounds without letting diagnostics extend eligibility."""
        return {"rest_learning_claims": len(self._claims), "rest_learning_outcomes": len(self._outcomes),
                "rest_learning_done": len(self._done), "rest_learning_history": len(self._history)}

    def close(self) -> None:
        """Revoke input forever for this generation without deleting past reports."""
        self._closed = True


@dataclass(frozen=True, slots=True)
class RestCycleFrameV1:
    """Read-only closed-cycle evidence assembled from named owners, not another actor."""

    task: RestTaskV1 | None
    reason: str
    current_safe_rest: bool | None
    registration: RestClaimV1 | None
    outcomes: tuple[RestOutcomeV1, ...]
    allocation: RestFocalAllocationV1 | None
    learning: RestPhaseFReportV1 | None

    def as_dict(self) -> dict[str, object]:
        """Detach task, current safety, original outcomes and no-learning reconciliation."""
        return {"task": None if self.task is None else self.task.as_dict(), "reason": self.reason,
                "current_safe_rest": self.current_safe_rest, "registration": None if self.registration is None else self.registration.as_dict(),
                "outcomes": [item.as_dict() for item in self.outcomes],
                "allocation": None if self.allocation is None else self.allocation.as_dict(),
                "learning": None if self.learning is None else self.learning.as_dict()}
