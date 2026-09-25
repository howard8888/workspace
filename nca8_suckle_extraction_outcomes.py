#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-D: original extraction correspondence and independently measured interval milk.

This one-contribution, operation-local reader consumes the existing C2 interval
lane. It cannot see a plant, current WNM, private supply, or diagnostic history.
It has no route to Attention, IP selection, BodyMap permission or learning. The
original prediction concerns sampled sealed contact and finite reciprocation;
milk yield was not predicted. Known measured quantity and interval coverage are
therefore independent of prediction agreement and do not establish causation.

All event/availability limits are fixed before dispatch. A target lease is not an
evidence deadline: acquisitions ending inside the original horizon may arrive up
to eight ticks later. The entire frozen batch is validated and accounted before
expiry. At most eight acquisition records and four references to ordered endpoint
acquisitions accompany one claim/result. A terminal result is never rewritten.
"""
from __future__ import annotations

from dataclasses import dataclass, replace
import math

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_body_targets import BodyTargetProposalV1
from nca8_sensorimotor_contracts import CommittedBodyTargetV1, LocalTargetDispositionV1, LocalTargetReportV1, OralExtractionTargetV1
from nca8_suckle import SuckleExtractionApplicationV1
from nca8_suckle_outcomes import SuckleEndpointV1, SuckleIntervalEvidenceV1

__version__ = "0.1.2"
__all__ = ["SuckleExtractionClaimV1", "SuckleExtractionOutcomeV1", "SuckleExtractionOutcomeFrameV1",
           "SuckleExtractionOutcomeRuntimeV1", "validate_suckle_extraction_outcome_v1", "__version__"]
_GEOMETRY_TOLERANCE = 0.005
_RELATIONS = ("mouth_position", "detail_anchor", "sealed_contact", "finite_reciprocation")
_ENDS = frozenset({LocalTargetDispositionV1.CANCELLED, LocalTargetDispositionV1.INTERRUPTED,
                  LocalTargetDispositionV1.UNAVAILABLE, LocalTargetDispositionV1.BLOCKED, LocalTargetDispositionV1.EXPIRED})


def _tick(value: int) -> int:
    """Reject coercion, Boolean time and overflow before any state mutation."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("extraction correspondence requires bounded nonnegative physical time")
    return value


@dataclass(frozen=True, slots=True)
class SuckleExtractionClaimV1:
    """One original selected application and exact authorized pattern, not a grant.

    Registration checks the real proposal's binding identity separately. The
    record itself preserves the original source/body/scene, permission and fixed
    observation window. A veto has no target and no applied-outcome obligation.
    """

    application: SuckleExtractionApplicationV1
    targets: tuple[CommittedBodyTargetV1, ...]

    def __post_init__(self) -> None:
        if not isinstance(self.application, SuckleExtractionApplicationV1):
            raise TypeError("extraction claim needs its original selected application")
        application = self.application
        replace(application.projection)
        replace(application)
        preview, request = application.projection, application.contribution
        if not isinstance(self.targets, tuple) or len(self.targets) > 1:
            raise ValueError("extraction claim retains exactly one authorized pattern or veto")
        _tick(self.last_acceptable_availability_tick)
        for committed in self.targets:
            if not isinstance(committed, CommittedBodyTargetV1) or not isinstance(committed.target, OralExtractionTargetV1):
                raise TypeError("extraction correspondence cannot consume another target family")
            target = committed.target
            replace(target)
            replace(committed)
            if (target.origin != request.origin or target.basis is not preview.basis.oral_feedback
                    or target.outward_offset != request.outward_extent or target.repetitions != request.repetitions
                    or target.lease_ticks != request.lease_ticks or committed.committed_tick != self.start_tick
                    or committed.expires_at_tick != self.due_tick):
                raise ValueError("extraction permission changed original origin, body, pattern or horizon")

    @property
    def start_tick(self) -> int:
        """Original focal basis cutoff, not the time at which it is later read."""
        return self.application.projection.basis.cutoff_tick

    @property
    def due_tick(self) -> int:
        """First tick without command authority for this original contribution."""
        return self.start_tick + self.application.projection.horizon_ticks

    @property
    def last_acceptable_availability_tick(self) -> int:
        """Eight ticks of sensing-arrival allowance, never a renewed motor lease."""
        return self.due_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Describe the original claim, immutable evidence policy and absent grants."""
        return {"original_application": self.application.as_dict(),
                "authorized_targets": [target.as_dict() for target in self.targets],
                "authorization_status": "authorized" if self.targets else "not_applied",
                "start_tick": self.start_tick, "original_end_tick": self.due_tick,
                "last_acceptable_availability_tick": self.last_acceptable_availability_tick,
                "geometry_tolerance_metres": _GEOMETRY_TOLERANCE,
                "contact_policy": "paired_sampled_support_not_continuous_unobserved_contact",
                "grants_motor_authority": False, "milk_yield_predicted": False}


def _context_relations(claim: SuckleExtractionClaimV1, endpoint: SuckleEndpointV1) -> tuple[str, str, str]:
    """Compare sampled original mouth/detail/seal, without current-source access.

    An absent product is unknown; a known wrong frame/category/part or displaced
    original anchor is a mismatch. Milk sensing remains valid even if scene
    association cannot be established. This is not a new recognition algorithm.
    """
    preview, sample, observation = claim.application.projection, endpoint.feedback, endpoint.observation
    planar = sample.planar
    if planar is not None and planar.frame_id != preview.basis.frame_id:
        return ("mismatch", "mismatch", "unknown")
    mouth, original = endpoint.mouth_position, preview.basis.mouth_position
    mouth_status = "unknown"
    if mouth is not None and original is not None:
        mouth_status = "matched" if math.hypot(mouth.x - original.x, mouth.y - original.y) <= _GEOMETRY_TOLERANCE + 1e-12 else "mismatch"
    detail = None if observation is None else next((d for d in observation.detections if d.region_id == preview.region_id), None)
    parent = None if observation is None else next((d for d in observation.detections
                                                  if d.region_id == preview.basis.seed.parent_region_id), None)
    detail_status = "unknown"
    if detail is not None and detail.descriptor is not None:
        if detail.descriptor != "feeding" or (parent is not None and parent.descriptor is not None
                                             and parent.descriptor != preview.basis.maternal.seed.descriptor):
            detail_status = "mismatch"
        elif parent is not None and parent.descriptor is not None and parent.position is not None and detail.position is not None:
            anchored = math.hypot(detail.position.x - preview.scene_target.x, detail.position.y - preview.scene_target.y)
            separation = math.hypot(detail.position.x - parent.position.x, detail.position.y - parent.position.y)
            detail_status = ("matched" if anchored <= _GEOMETRY_TOLERANCE + 1e-12
                             and separation <= preview.basis.seed.maximum_parent_distance + 1e-12 else "mismatch")
    seal_status = "unknown"
    if (sample.oral is not None and sample.oral.contact is False) or (sample.oral_seal is not None and sample.oral_seal.sealed is False):
        seal_status = "mismatch"
    elif (sample.oral is not None and sample.oral.contact is True and sample.oral_seal is not None
          and sample.oral_seal.sealed is True and detail_status == "matched" and mouth is not None
          and detail is not None and detail.position is not None):
        seal_status = ("matched" if math.hypot(mouth.x - detail.position.x, mouth.y - detail.position.y)
                       <= _GEOMETRY_TOLERANCE + 1e-12 else "mismatch")
    return mouth_status, detail_status, seal_status


@dataclass(frozen=True, slots=True)
class SuckleExtractionOutcomeV1:
    """One terminal original-claim result with quantity AND coverage, never reward.

    The known sum is not asserted to be the physical total when an interval is
    missing. Observed quantities do not disappear because visual association is
    unknown. Execution and relation dispositions remain separate; neither one
    grants a next action or diagnoses the cause of a discrepancy.
    """

    claim: SuckleExtractionClaimV1
    evaluated_tick: int
    end_tick: int
    status: str
    installed: bool
    command_ticks: tuple[int, ...]
    termination: str | None
    samples: tuple[SuckleEndpointV1, ...]
    confirmations: tuple[MotorFeedbackV1, ...]
    relations: tuple[tuple[str, str], ...]
    comparison_enabled: bool

    def milk_evidence(self) -> dict[str, object]:
        """Account original, nonoverlapping intervals; never consult physical totals."""
        expected = tuple(range(self.claim.start_tick + 1, self.end_tick + 1)) if self.claim.targets else ()
        known = tuple(item for item in self.samples if item.feedback.oral_extraction is not None
                      and item.feedback.oral_extraction.milk_transferred_units is not None)
        known_events = {item.feedback.event_tick for item in known}
        missing = tuple(tick for tick in expected if tick not in known_events)
        total = math.fsum(item.feedback.oral_extraction.milk_transferred_units for item in known
                          if item.feedback.oral_extraction is not None and item.feedback.oral_extraction.milk_transferred_units is not None)
        coverage = "not_applicable" if not expected else "complete" if not missing else "partial" if known else "unavailable"
        associated = tuple(item.feedback.event_tick for item in known if _context_relations(self.claim, item)[1:] == ("matched", "matched"))
        return {"units": "model_volume_units", "known_interval_sum": total, "coverage": coverage,
                "exact_observed_total": total if coverage == "complete" else None,
                "expected_event_ticks": list(expected), "known_event_ticks": sorted(known_events),
                "missing_event_ticks": list(missing), "original_detail_associated_event_ticks": list(associated),
                "unassociated_known_event_ticks": sorted(known_events - set(associated)),
                "quantity_status": "observed_positive" if total > 0 else "known_zero" if coverage == "complete" else "unknown_total",
                "causal_credit": "not_established", "milk_yield_predicted": False, "nourishment": "not_established"}

    def as_dict(self) -> dict[str, object]:
        """Serialize immutable evidence; no field can restore a target or participant."""
        return {"claim": self.claim.as_dict(), "evaluated_tick": self.evaluated_tick, "accounted_end_tick": self.end_tick,
                "status": self.status, "installation_reported": self.installed, "command_ticks": list(self.command_ticks),
                "termination": self.termination, "samples": [item.as_dict() for item in self.samples],
                "ordered_endpoint_sample_ids": [item.sample_id for item in self.confirmations],
                "relations": dict(self.relations), "comparison_enabled": self.comparison_enabled,
                "milk_evidence": self.milk_evidence(), "full_suckle_complete": False, "durable_updates": 0,
                "attention_route": "unimplemented_for_extraction", "learning_route": "unimplemented_for_extraction"}


@dataclass(frozen=True, slots=True)
class SuckleExtractionOutcomeFrameV1:
    """Read-only C2 publication and current E registration, not a second focal task."""

    cutoff_tick: int
    registration: SuckleExtractionClaimV1 | None
    outcomes: tuple[SuckleExtractionOutcomeV1, ...]
    pending: SuckleExtractionClaimV1 | None
    comparison_enabled: bool
    attention_enabled: bool = False
    learning_hook_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Expose new results once; retained history is a separate diagnostic read."""
        return {"profile": "suckle_extraction_correspondence_v1", "cutoff_tick": self.cutoff_tick,
                "registration": self.registration.as_dict() if self.registration else None,
                "outcomes": [item.as_dict() for item in self.outcomes], "pending": self.pending.as_dict() if self.pending else None,
                "comparison_enabled": self.comparison_enabled, "durable_updates": 0,
                "attention_route": "suckle_extraction_attention_v1" if self.attention_enabled else "unimplemented_for_extraction",
                "learning_route": "suckle_extraction_no_learning_v1" if self.learning_hook_enabled else "unimplemented_for_extraction"}


@dataclass(slots=True)
class _Evidence:
    """At most one contribution; copying for a transaction preserves original objects."""

    installed: bool = False
    end_tick: int | None = None
    termination: str | None = None
    command_ticks: tuple[int, ...] = ()
    samples: tuple[SuckleEndpointV1, ...] = ()
    confirmations: tuple[MotorFeedbackV1, ...] = ()
    achieved: bool = False


class SuckleExtractionOutcomeRuntimeV1:
    """One bounded original-extraction reader, independent of old I/J/K owners.

    Register at E; acknowledge the identical installed claim after outer handoff;
    consume contiguous returned intervals at C2. Validation and calculations use
    a temporary bounded copy, committed only when the complete batch succeeds.
    Reset constructs another owner. Fault closure retains partial known evidence
    with explicit execution uncertainty, never manufacturing nonapplication.
    """

    def __init__(self, stream: MotorStreamRefV1, *, compare_predictions: bool = True) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(compare_predictions, bool):
            raise TypeError("extraction correspondence requires a stream and Boolean comparison option")
        self.stream, self.compare_predictions = stream, compare_predictions
        self._claim: SuckleExtractionClaimV1 | None = None
        self._evidence = _Evidence()
        self._result: SuckleExtractionOutcomeV1 | None = None
        self._last_cutoff, self._last_interval, self._last_command = -1, -1, 0
        self._closed = False

    def pending(self) -> SuckleExtractionClaimV1 | None:
        """Read the one original claim; reading cannot renew any lifetime."""
        return self._claim if self._result is None else None

    def history(self) -> tuple[SuckleExtractionOutcomeV1, ...]:
        """Read the sole frozen result without republishing or rescoring it."""
        return () if self._result is None else (self._result,)

    def retained_counts(self) -> dict[str, int]:
        """Report actual bounded state, counting endpoint references separately."""
        return {"extraction_pending_claims": int(self.pending() is not None), "extraction_outcome_history": int(self._result is not None),
                "extraction_outcome_samples": len(self._evidence.samples),
                "extraction_outcome_endpoint_refs": len(self._evidence.confirmations),
                "extraction_outcome_command_ticks": len(self._evidence.command_ticks)}

    def register(
        self, application: SuckleExtractionApplicationV1, proposal: BodyTargetProposalV1, targets: tuple[CommittedBodyTargetV1, ...],
    ) -> SuckleExtractionClaimV1:
        """Bind actual selected request/proposal/permission before physical dispatch."""
        if self._closed or self._claim is not None:
            raise RuntimeError("one extraction claim per generation; closed/repeated registration is forbidden")
        if not isinstance(application, SuckleExtractionApplicationV1) or not isinstance(proposal, BodyTargetProposalV1):
            raise TypeError("register only the distinct selected extraction application and BodyMap proposal")
        if (application.contribution.origin.stream != self.stream or proposal.request is not application.contribution
                or application.projection.basis.cutoff_tick != self._last_cutoff or proposal.created_tick != self._last_cutoff):
            raise ValueError("registration lacks its original request, stream or current frozen opportunity")
        if not isinstance(targets, tuple) or len(targets) != len(proposal.bindings):
            raise ValueError("registration must preserve the actual proposal bindings or veto")
        for committed, binding in zip(targets, proposal.bindings):
            if not isinstance(committed, CommittedBodyTargetV1) or committed.target is not binding.target:
                raise ValueError("registration cannot substitute a copied or different target")
        claim = SuckleExtractionClaimV1(application, targets)
        self._claim = claim
        if not targets:
            self._result = self._finish(self._evidence, self._last_cutoff, forced_status="not_applied")
        return claim

    def installed(self, claim: SuckleExtractionClaimV1, *, at_tick: int) -> None:
        """Acknowledge successful installation once; permission alone was insufficient."""
        tick = _tick(at_tick)
        if (self._closed or not isinstance(claim, SuckleExtractionClaimV1) or claim is not self._claim or self._result is not None or not claim.targets
                or tick != claim.start_tick or tick != self._last_cutoff or self._evidence.installed):
            raise ValueError("installation must answer the identical awaiting extraction claim once")
        self._evidence = replace(self._evidence, installed=True)

    def end_execution(self, *, at_tick: int, reason: str = "cancelled") -> None:
        """Record explicit cancellation/replacement without discarding in-transit sensing."""
        tick = _tick(at_tick)
        if reason not in {"cancelled", "replacement"} or tick < self._last_cutoff:
            raise ValueError("extraction end needs its actual nonhistorical disposition")
        if self._closed or self._claim is None or self._result is not None or not self._evidence.installed:
            return
        if self._evidence.termination is None:
            self._evidence = replace(self._evidence, end_tick=min(tick, self._claim.due_tick), termination=reason)

    def close(self, *, reason: str) -> None:
        """Freeze partial evidence with unknown possible effects; never infer a veto."""
        if not isinstance(reason, str) or not reason or len(reason) > 100:
            raise ValueError("fault closure needs a bounded reason")
        if not self._closed and self._claim is not None and self._result is None:
            self._result = self._finish(self._evidence, max(0, self._last_cutoff), forced_status="execution_unknown_after_fault")
        self._closed = True

    def consume_intervals(
        self, intervals: tuple[SuckleIntervalEvidenceV1, ...], *, cutoff_tick: int,
    ) -> tuple[SuckleExtractionOutcomeV1, ...]:
        """Validate/account a complete frozen batch, then publish or expire exactly once.

        The cutoff is a legal C2 opportunity, not an acquisition. Timely historical
        samples in this batch are processed before expiry even at a later cutoff.
        There is deliberately no current-source/plant argument or callback.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_cutoff or not isinstance(intervals, tuple) or len(intervals) > 16:
            raise ValueError("extraction C2 needs a new cutoff and at most sixteen immutable intervals")
        if self._last_interval + len(intervals) + 1 != cutoff:
            raise ValueError("account every elapsed interval once, including neutral physical evolution")
        evidence, command_id = replace(self._evidence), self._last_command
        for index, interval in enumerate(intervals):
            if not isinstance(interval, SuckleIntervalEvidenceV1) or interval.tick != self._last_interval + index + 1:
                raise ValueError("extraction interval batch is noncontiguous or replayed")
            replace(interval)
            command = interval.command
            if command is not None:
                command.validate_for_update(stream=self.stream, now_tick=interval.tick, previous_command_id=command_id)
                command_id = command.command_id
            reports = tuple(r for r in interval.reports if isinstance(r.committed_target.target, OralExtractionTargetV1))
            if len(reports) > 1:
                raise ValueError("an interval cannot contain two extraction-resource reports")
            for report in interval.reports:
                if report.committed_target.target.origin.stream != self.stream:
                    raise ValueError("local evidence belongs to a different stream or generation")
            for report in reports:
                self._read_report(evidence, report)
            if command is not None and command.oral_extraction_drive not in (None, 0.0):
                self._read_command(evidence, interval, reports)
            for endpoint in interval.endpoints():
                endpoint.feedback.validate_available(stream=self.stream, at_tick=cutoff)
                self._read_sample(evidence, endpoint)
        result = self._result
        if result is None and self._claim is not None:
            end = self._effective_end(evidence)
            complete_acquisitions = all(any(s.feedback.event_tick == tick for s in evidence.samples)
                                        for tick in range(self._claim.start_tick + 1, end + 1))
            if (cutoff >= self._claim.due_tick and complete_acquisitions
                    and (evidence.achieved or evidence.termination is not None)) or cutoff > self._claim.last_acceptable_availability_tick:
                result = self._finish(evidence, cutoff)
        published = (result,) if result is not None and self._result is None else ()
        # No validation or calculation below this line can fail: batch commit.
        if self._result is None:
            self._evidence, self._result = evidence, result
        self._last_interval, self._last_cutoff, self._last_command = cutoff - 1, cutoff, command_id
        return published

    def _read_command(
        self, evidence: _Evidence, interval: SuckleIntervalEvidenceV1, reports: tuple[LocalTargetReportV1, ...],
    ) -> None:
        """Returned nonzero drive is exposure only, requiring the identical live target."""
        claim = self._claim
        if (claim is None or not evidence.installed or not reports or reports[0].committed_target is not claim.targets[0]
                or not claim.start_tick <= interval.tick < claim.due_tick or reports[0].reported_tick != interval.tick
                or reports[0].disposition not in {LocalTargetDispositionV1.ACTIVE, LocalTargetDispositionV1.PARTIAL}
                or (evidence.end_tick is not None and interval.tick >= evidence.end_tick)):
            raise ValueError("extraction drive lacks its original installed, unrevoked and live permission")
        if len(evidence.command_ticks) >= 8:
            raise OverflowError("extraction exposure exceeds the original maximum eight-tick window")
        evidence.command_ticks += (interval.tick,)

    def _read_report(self, evidence: _Evidence, report: LocalTargetReportV1) -> None:
        """Consume the existing validated endpoint prefix; never recalculate motor phases."""
        claim = self._claim
        if claim is None or not evidence.installed or not claim.targets or report.committed_target is not claim.targets[0]:
            raise ValueError("extraction report lacks its identical original installed target")
        replace(report)  # Validate its actual endpoint evidence, not just local_achieved.
        confirmations = report.extraction_confirmations
        old = evidence.confirmations
        if confirmations[:min(len(old), len(confirmations))] != old[:min(len(old), len(confirmations))]:
            raise ValueError("ordered endpoint evidence conflicts with its original prefix")
        if len(confirmations) > len(old):
            if evidence.termination not in (None, "expired") or (evidence.termination == "expired" and not len(old) + 1 == len(confirmations) == 2 * claim.application.projection.repetitions):
                raise ValueError("terminated execution cannot acquire an unobserved new pattern")
            evidence.confirmations = confirmations
        for sample in (*confirmations, *((report.feedback,) if report.feedback is not None else ())):
            self._read_sample(evidence, SuckleEndpointV1(sample, None))
        if report.disposition is LocalTargetDispositionV1.ACHIEVED:
            if evidence.termination not in (None, "expired"):
                raise ValueError("cancelled execution cannot be revived as achieved")
            evidence.achieved = True
            evidence.end_tick = confirmations[-1].event_tick
        elif report.disposition in _ENDS and evidence.termination is None and not evidence.achieved:
            evidence.termination = report.disposition.value
            evidence.end_tick = min(report.reported_tick, claim.due_tick)

    def _read_sample(self, evidence: _Evidence, endpoint: SuckleEndpointV1) -> None:
        """Coalesce report/delivery references; enrich absent paired scene only once."""
        claim, sample = self._claim, endpoint.feedback
        if claim is None:
            return
        basis = claim.application.projection.basis.oral_feedback
        if basis is None:
            raise RuntimeError("validated original claim lost its body basis")
        if sample.sample_id == basis.sample_id and sample != basis:
            raise ValueError("original body sample identity has conflicting contents")
        same_id = next((item for item in evidence.samples if item.feedback.sample_id == sample.sample_id), None)
        if same_id is not None and same_id.feedback != sample:
            raise ValueError("one extraction acquisition has conflicting body contents")
        if not claim.start_tick < sample.event_tick <= claim.due_tick:
            return
        if sample.sample_id <= basis.sample_id:
            raise ValueError("post-selection evidence cannot reuse a prior sample identity")
        same_event = next((item for item in evidence.samples if item.feedback.event_tick == sample.event_tick), None)
        if same_event is not None and same_event.feedback.sample_id != sample.sample_id:
            raise ValueError("one physical interval cannot become two independent acquisitions")
        if sample.available_tick > claim.last_acceptable_availability_tick:
            return
        if same_id is not None:
            if same_id.observation is not None and endpoint.observation is not None and same_id.observation != endpoint.observation:
                raise ValueError("one acquisition has contradictory visual products")
            if same_id.observation is None and endpoint.observation is not None:
                evidence.samples = tuple(endpoint if item is same_id else item for item in evidence.samples)
        else:
            if len(evidence.samples) >= 8:
                raise OverflowError("extraction original window admits at most eight acquisitions")
            evidence.samples = tuple(sorted((*evidence.samples, endpoint), key=lambda item: item.feedback.event_tick))

    def _effective_end(self, evidence: _Evidence) -> int:
        """Bound the contribution by actual termination; never demand endless contact."""
        if self._claim is None:
            raise RuntimeError("no original extraction window")
        return min(self._claim.due_tick, evidence.end_tick if evidence.end_tick is not None else self._claim.due_tick)

    def _finish(self, evidence: _Evidence, cutoff: int, *, forced_status: str | None = None) -> SuckleExtractionOutcomeV1:
        """Calculate a frozen multidimensional result from original admitted evidence."""
        claim = self._claim
        if claim is None:
            raise RuntimeError("cannot publish without an original selected claim")
        end = self._effective_end(evidence) if claim.targets else claim.start_tick
        samples = tuple(item for item in evidence.samples if item.feedback.event_tick <= end)
        if forced_status is not None:
            status = forced_status
        elif not evidence.installed:
            status = "uninstalled_unresolved"
        elif not evidence.command_ticks:
            status = "observed_without_command" if samples else "no_command_evidence"
        elif evidence.achieved:
            status = "local_sequence_observed"
        elif evidence.termination is not None and evidence.termination != "expired":
            status = "interrupted"
        else:
            status = "expired_unresolved"
        if not self.compare_predictions:
            relations = tuple((name, "comparison_disabled") for name in _RELATIONS)
        elif forced_status is not None or not evidence.installed or not evidence.command_ticks:
            relations = tuple((name, "not_applied" if not claim.targets else "unresolved_execution") for name in _RELATIONS)
        else:
            context = tuple(_context_relations(claim, item) for item in samples)
            complete = len(samples) == end - claim.start_tick and bool(samples)
            verdicts = tuple("mismatch" if any(row[index] == "mismatch" for row in context) else
                             "matched" if complete and all(row[index] == "matched" for row in context) else "unknown"
                             for index in range(3))
            movement = "matched" if evidence.achieved else "interrupted" if status == "interrupted" else "unknown"
            relations = tuple(zip(_RELATIONS, (*verdicts, movement)))
        return SuckleExtractionOutcomeV1(claim, cutoff, end, status, evidence.installed, evidence.command_ticks,
                                         evidence.termination, samples, evidence.confirmations, relations, self.compare_predictions)



def validate_suckle_extraction_outcome_v1(
    outcome: SuckleExtractionOutcomeV1, *, stream: MotorStreamRefV1, cutoff_tick: int,
) -> None:
    """Validate original evidence before a downstream relevance contribution.

    This is a bounded consistency check, not authentication, perfect causal credit,
    or a second result publication. Existing claim, endpoint and local-report
    validators check the original immutable objects. A private temporary reader
    reuses the UNCHANGED original finish calculation; it does not consume input,
    access a current source or alter the real publisher. Historical milk and
    relation records therefore cannot gain behavioral influence from forged scores.
    Actual provenance still comes from the core routing the new publication tuple.
    """
    cutoff = _tick(cutoff_tick)
    if not isinstance(outcome, SuckleExtractionOutcomeV1) or not isinstance(stream, MotorStreamRefV1):
        raise TypeError("extraction relevance requires a typed original result and stream")
    claim = outcome.claim
    if not isinstance(claim, SuckleExtractionClaimV1):
        raise TypeError("extraction result lost its original claim")
    replace(claim)
    preview = claim.application.projection
    if preview.basis.stream != stream or preview.pnm.primitive_id != "ip:suckle":
        raise ValueError("extraction result belongs to another stream, generation or operation")
    evaluated, end = _tick(outcome.evaluated_tick), _tick(outcome.end_tick)
    if not claim.start_tick <= evaluated <= cutoff or not claim.start_tick <= end <= claim.due_tick:
        raise ValueError("extraction result changed its original event or publication window")
    if not isinstance(outcome.installed, bool) or not isinstance(outcome.comparison_enabled, bool):
        raise TypeError("extraction installation and comparison flags must be Boolean")
    statuses = {"not_applied", "execution_unknown_after_fault", "uninstalled_unresolved", "observed_without_command",
                "no_command_evidence", "local_sequence_observed", "interrupted", "expired_unresolved"}
    if not isinstance(outcome.status, str) or outcome.status not in statuses:
        raise ValueError("unknown original extraction disposition")
    if outcome.termination is not None and outcome.termination not in {item.value for item in _ENDS} | {"replacement"}:
        raise ValueError("unknown original extraction termination")
    for values, bound in ((outcome.command_ticks, 8), (outcome.samples, 8), (outcome.confirmations, 4), (outcome.relations, 4)):
        if not isinstance(values, tuple) or len(values) > bound:
            raise ValueError("extraction result exceeds its immutable bounded evidence contract")
    if (len(outcome.relations) != 4 or any(not isinstance(row, tuple) or len(row) != 2 for row in outcome.relations)
            or tuple(row[0] for row in outcome.relations) != _RELATIONS):
        raise ValueError("extraction result changed its original relation vocabulary or order")
    for tick in outcome.command_ticks:
        if not claim.start_tick <= _tick(tick) < end:
            raise ValueError("extraction exposure is outside its accounted original contribution")
    if tuple(sorted(set(outcome.command_ticks))) != outcome.command_ticks:
        raise ValueError("extraction exposure must be distinct and ordered")
    if (outcome.command_ticks or outcome.confirmations) and (not outcome.installed or not claim.targets):
        raise ValueError("extraction exposure/progress requires reported original installation")
    if outcome.installed and not claim.targets:
        raise ValueError("nonapplication cannot claim installation")
    if not claim.targets and (outcome.samples or outcome.termination is not None or end != claim.start_tick):
        raise ValueError("veto cannot contain an applied outcome")
    original_body = preview.basis.oral_feedback
    if original_body is None:
        raise ValueError("original extraction claim lacks its body acquisition")
    previous_event, previous_id = claim.start_tick, original_body.sample_id
    for endpoint in outcome.samples:
        if not isinstance(endpoint, SuckleEndpointV1):
            raise TypeError("extraction result requires its original typed acquisitions")
        replace(endpoint)
        sample = endpoint.feedback
        sample.validate_available(stream=stream, at_tick=evaluated)
        if (not previous_event < sample.event_tick <= end or sample.sample_id <= previous_id
                or sample.available_tick > claim.last_acceptable_availability_tick):
            raise ValueError("extraction acquisition changed identity, order or original timing")
        previous_event, previous_id = sample.event_tick, sample.sample_id
    achieved = outcome.status == "local_sequence_observed"
    if claim.targets:
        LocalTargetReportV1(claim.targets[0], LocalTargetDispositionV1.ACHIEVED if achieved else LocalTargetDispositionV1.UNRESOLVED,
                            evaluated, "original_result_validation", outcome.confirmations[-1] if outcome.confirmations else None,
                            extraction_confirmations=outcome.confirmations)
    for sample in outcome.confirmations:
        if not any(endpoint.feedback == sample for endpoint in outcome.samples):
            raise ValueError("endpoint reference is not the original accounted acquisition")
    if achieved and (end != outcome.confirmations[-1].event_tick or outcome.termination not in (None, "expired")):
        raise ValueError("achieved extraction changed its endpoint or revived a cancellation")
    forced = outcome.status if outcome.status in {"not_applied", "execution_unknown_after_fault"} else None
    if outcome.status == "not_applied" and (claim.targets or evaluated != claim.start_tick):
        raise ValueError("nonapplication must retain its original veto opportunity")
    if forced is None:
        complete = len(outcome.samples) == end - claim.start_tick
        if not ((evaluated >= claim.due_tick and complete and (achieved or outcome.termination is not None))
                or evaluated > claim.last_acceptable_availability_tick):
            raise ValueError("extraction result published before its original evidence policy allowed")
    # Reuse the publisher's pure calculation on a private snapshot, never its live state.
    reader = SuckleExtractionOutcomeRuntimeV1(stream, compare_predictions=outcome.comparison_enabled)
    reader._claim = claim
    evidence = _Evidence(outcome.installed, end, outcome.termination, outcome.command_ticks,
                         outcome.samples, outcome.confirmations, achieved)
    if reader._finish(evidence, evaluated, forced_status=forced) != outcome:
        raise ValueError("extraction result disagrees with its original canonical evidence and comparison")
