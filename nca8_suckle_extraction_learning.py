#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-F: extraction-specific participation and an actual no-learning F consumer.

The existing feeding-detail source owns one participant for the one-contribution
extraction profile. Its eligibility ends before the original application cutoff
plus 24 physical ticks, independently of latch K, current focality, motor leases,
L-D arrival allowance and L-E questions. This is an engineering test profile, not
a biological time constant. Registration records selection/authorization BEFORE
outer installation; it cannot certify movement or anticipate the new action's
outcome. No old latch task is required for an already-sealed extraction.

The F callback supplies new canonical L-D publications and original L-E requests.
Only a performed current-opportunity Navigation interpretation can satisfy a
focal dependency. This owner neither determines significance/current relevance
nor consumes a question. Known relations survive an interrupted sequence; milk
quantity/coverage remains observational context, never reward or nourishment.
The hook changes only bounded temporary participation and detached diagnostics,
not sources, predictions, motor permission, learning parameters or RNG state.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math

from cca8_motor_contracts import MotorStreamRefV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSeedV1
from nca8_suckle_extraction_attention import ExtractionInterpretationV1, ExtractionMismatchRequestV1, ExtractionQuestionEvidenceV1
from nca8_suckle_extraction_outcomes import (
    SuckleExtractionClaimV1, SuckleExtractionOutcomeV1, validate_suckle_extraction_outcome_v1,
)

__version__ = "0.1.0"
__all__ = ["ExtractionParticipationV1", "ExtractionTeachingDispositionV1", "ExtractionLearningPhaseFReportV1",
           "SuckleExtractionLearningHookV1", "__version__"]
_ELIGIBILITY_TICKS = 24


def _index(value: int, name: str, *, minimum: int = 0) -> int:
    """Reject Boolean/coerced or overflowing time, leaving room for fixed expiry."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value < 2**63 - 25:
        raise ValueError(f"{name} must be a bounded integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class ExtractionParticipationV1:
    """One original source/application recipient, never a live actuator grant.

    claim retains the exact original source sample, PNM, body basis and authorized
    target. outcome/request refer to publishers, not reconstructed history. These
    references are an engineering approximation to participation, not perfect
    biological causal credit. Losing focality does not erase this eligibility.
    """

    recipient_id: str
    claim: SuckleExtractionClaimV1
    created_cycle: int
    outcome: SuckleExtractionOutcomeV1 | None = None
    request: ExtractionMismatchRequestV1 | None = None
    awaiting_interpretation: bool = False

    @property
    def expires_before_tick(self) -> int:
        """Return exclusive original-application expiry; reads never renew it."""
        return self.claim.start_tick + _ELIGIBILITY_TICKS

    @property
    def pnm_id(self) -> str:
        """Identify the earlier claim independently of the current projection."""
        return self.claim.application.projection.pnm.pnm_id

    def as_dict(self) -> dict[str, object]:
        """Detach provenance without making source history current or actionable."""
        app = self.claim.application
        basis = app.projection.basis
        return {"recipient_id": self.recipient_id, "application_id": app.application_id, "pnm_id": self.pnm_id,
                "source_map_ref": basis.source_map_ref.as_dict(), "seed": basis.seed.as_dict(),
                "origin": app.contribution.origin.as_dict(), "created_cycle": self.created_cycle,
                "source_sample_id": basis.maternal.visual.sample_id, "source_cutoff_tick": self.claim.start_tick,
                "oral_sample_id": basis.oral_feedback.sample_id if basis.oral_feedback is not None else None,
                "authorized_target_ids": [item.target.target_id for item in self.claim.targets],
                "expires_before_tick": self.expires_before_tick, "eligibility_lifetime_ticks": _ELIGIBILITY_TICKS,
                "registration_scope": "selected_authorized_not_execution", "maturity": "eligibility_only",
                "outcome_evaluated_tick": self.outcome.evaluated_tick if self.outcome is not None else None,
                "interpretation_request_id": self.request.request_id if self.request is not None else None,
                "awaiting_interpretation": self.awaiting_interpretation, "grants_motor_authority": False}


@dataclass(frozen=True, slots=True)
class ExtractionTeachingDispositionV1:
    """One no-update disposition with execution and relation knowledge kept apart.

    accepted_relations are only canonical known comparisons, not a task verdict.
    An interrupted sequence can retain matched/mismatched context while its
    finite-reciprocation relation remains interrupted. Milk is not a forecasted
    quantity, nourishment, reinforcement or established action causation.
    """

    pnm_id: str
    status: str
    cycle_id: int
    cutoff_tick: int
    outcome: SuckleExtractionOutcomeV1 | None = None
    accepted_relations: tuple[tuple[str, str], ...] = ()
    interpretation: ExtractionInterpretationV1 | None = None

    def as_dict(self) -> dict[str, object]:
        """Report original evidence and actual interpretation times without rescoring."""
        result = self.outcome
        return {"pnm_id": self.pnm_id, "status": self.status, "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "original_outcome_status": result.status if result is not None else None,
                "outcome_evaluated_tick": result.evaluated_tick if result is not None else None,
                "original_relations": dict(result.relations) if result is not None else {},
                "accepted_relations": dict(self.accepted_relations),
                "evidence_sample_ids": [item.feedback.sample_id for item in result.samples] if result is not None else [],
                "milk_evidence": result.milk_evidence() if result is not None else None,
                "installation_reported": result.installed if result is not None else False,
                "command_ticks": list(result.command_ticks) if result is not None else [],
                "interpretation_status": self.interpretation.status if self.interpretation is not None else None,
                "interpretation_cycle": self.interpretation.cycle_id if self.interpretation is not None else None,
                "interpretation_tick": self.interpretation.cutoff_tick if self.interpretation is not None else None,
                "action_causation": "uncertain", "durable_learning_updates": 0}


@dataclass(frozen=True, slots=True)
class ExtractionLearningPhaseFReportV1:
    """The actual F visit, not a second focal operation or a scan of all learners."""

    recipient_id: str
    cycle_id: int
    cutoff_tick: int
    new_participation: ExtractionParticipationV1 | None
    dispositions: tuple[ExtractionTeachingDispositionV1, ...]
    pending: tuple[ExtractionParticipationV1, ...]
    offered_outcomes: int
    inspected_participants: int

    def as_dict(self) -> dict[str, object]:
        """Separate temporary eligibility, current source refresh and durable change."""
        return {"profile": "suckle_extraction_no_learning_v1", "recipient_id": self.recipient_id,
                "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick, "maturity": "eligibility_only",
                "new_participation": self.new_participation.as_dict() if self.new_participation is not None else None,
                "dispositions": [item.as_dict() for item in self.dispositions],
                "pending": [item.as_dict() for item in self.pending], "offered_outcomes": self.offered_outcomes,
                "inspected_participants": self.inspected_participants,
                "due_owners_visited": int(bool(self.new_participation or self.dispositions or self.inspected_participants)),
                "current_source_refresh_is_learning": False, "new_action_outcome_available": False,
                "already_effective_durable_changes": 0, "due_durable_changes": 0, "durable_learning_updates": 0,
                "ledger_rows_executed": 0, "restores_motor_permission": False}


class SuckleExtractionLearningHookV1:
    """One source-owned extraction recipient, independent of K and diagnostics.

    reconcile validates the complete bounded batch before committing temporary
    state. Foreign/altered dependencies raise without a partial transaction. Valid
    unregistered, duplicate, unknown and expired evidence gets an explicit no-update
    disposition. One original registration, result and request reference remain as
    bounded replay guards even after eligibility ends; they cannot teach again.
    Diagnostic history is disposable and never consulted by the mechanism.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: FeedingDetailSeedV1, *, diagnostic_capacity: int = 8) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, FeedingDetailSeedV1):
            raise TypeError("extraction participation requires its typed stream and feeding seed")
        _index(diagnostic_capacity, "diagnostic_capacity", minimum=1)
        if diagnostic_capacity > 8:
            raise ValueError("extraction participation diagnostics cannot exceed eight entries")
        self.stream, self.seed = stream, seed
        self.recipient_id = "feeding_detail_association:feeding_detail:extraction_consequence"
        self._registration: SuckleExtractionClaimV1 | None = None
        self._participant: ExtractionParticipationV1 | None = None
        self._seen: SuckleExtractionOutcomeV1 | None = None
        self._dependency: ExtractionMismatchRequestV1 | None = None
        self._interpretation_seen = False
        self._history: deque[ExtractionTeachingDispositionV1] = deque(maxlen=diagnostic_capacity)
        self._last_cycle, self._last_tick = 0, -1
        self._closed = False

    def pending(self) -> tuple[ExtractionParticipationV1, ...]:
        """Read at most one immutable participant without renewing eligibility."""
        return () if self._participant is None else (self._participant,)

    def history(self) -> tuple[ExtractionTeachingDispositionV1, ...]:
        """Read the separate bounded diagnostic ring; it is never replay input."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Count live eligibility separately from fixed-size replay guards/history."""
        return {"extraction_learning_participants": int(self._participant is not None),
                "extraction_learning_registrations": int(self._registration is not None),
                "extraction_learning_seen_outcomes": int(self._seen is not None),
                "extraction_learning_dependencies": int(self._dependency is not None),
                "extraction_learning_dispositions": len(self._history)}

    def close(self) -> None:
        """Permanently revoke this generation on reset/fault, not undo physical work."""
        self._participant, self._dependency = None, None
        self._closed = True

    def _claim(self, claim: SuckleExtractionClaimV1) -> None:
        """Reuse original prospective/permission validation for this source recipient."""
        if not isinstance(claim, SuckleExtractionClaimV1):
            raise TypeError("extraction participation requires its original claim, not a latch task")
        replace(claim)
        basis = claim.application.projection.basis
        if basis.stream != self.stream or basis.seed != self.seed:
            raise ValueError("extraction participation belongs to another stream, generation or feeding source")
        _index(claim.start_tick, "original_cutoff_tick")
        if self._registration is not None and claim is not self._registration:
            raise ValueError("copied or altered claim cannot replace original extraction participation")

    def _outcome(self, outcome: SuckleExtractionOutcomeV1, cycle: int, tick: int) -> None:
        """Validate canonical earlier publication, never read intervals or republish it."""
        validate_suckle_extraction_outcome_v1(outcome, stream=self.stream, cutoff_tick=tick)
        self._claim(outcome.claim)
        if outcome.claim.application.cycle_id >= cycle:
            raise ValueError("a just-selected extraction has no physical outcome at F")
        if self._seen is not None and outcome is not self._seen:
            raise ValueError("conflicting or copied extraction result cannot replace canonical evidence")
        if self._seen is None and outcome.evaluated_tick != tick:
            raise ValueError("new extraction evidence must arrive at its actual C2 publication")

    def _request(self, request: ExtractionMismatchRequestV1, outcome: SuckleExtractionOutcomeV1) -> None:
        """Check original dependency structure, not significance or current relevance.

        Witnesses must be references to the canonical acquisitions and to known
        mismatches. Thresholding/classifying significance remains L-E's job. These
        checks establish consistency, not authentication of arbitrary caller objects;
        the actual core routes the original publication and Navigation result.
        """
        if not isinstance(request, ExtractionMismatchRequestV1) or request.outcome is not outcome:
            raise ValueError("extraction dependency must retain its actual original outcome")
        if (request.request_id != f"extraction_mismatch:{outcome.claim.application.application_id}"
                or _index(request.admitted_tick, "request_admitted_tick") != outcome.evaluated_tick):
            raise ValueError("extraction dependency changed identity or original publication time")
        if (not isinstance(request.evidence, tuple) or not 1 <= len(request.evidence) <= 3
                or not outcome.installed or not outcome.command_ticks or outcome.status == "execution_unknown_after_fault"):
            raise ValueError("extraction dependency requires bounded executed discrepancy evidence")
        reasons = {"sealed_contact": {"measured_touch_loss", "measured_seal_loss"},
                   "mouth_position": {"mouth_displaced"}, "detail_anchor": {"part_context_contradicted", "detail_displaced"}}
        names: set[str] = set()
        for witness in request.evidence:
            if (not isinstance(witness, ExtractionQuestionEvidenceV1) or not isinstance(witness.relation, str)
                    or not isinstance(witness.reason, str) or witness.reason not in reasons.get(witness.relation, set())
                    or witness.relation in names or (witness.relation, "mismatch") not in outcome.relations
                    or not any(witness.endpoint is item for item in outcome.samples)):
                raise ValueError("extraction dependency lost its original relation/acquisition witness")
            distance = witness.displacement_metres
            if witness.reason in {"mouth_displaced", "detail_displaced"}:
                if isinstance(distance, bool) or not isinstance(distance, (int, float)) or not math.isfinite(distance) or distance < 0:
                    raise ValueError("displacement witness requires a finite nonnegative measurement")
            elif distance is not None:
                raise ValueError("contact/part witness cannot invent a displacement measurement")
            names.add(witness.relation)

    def _interpretation(self, result: ExtractionInterpretationV1, dependency: ExtractionMismatchRequestV1 | None,
                        cycle: int, tick: int) -> None:
        """Require current performed D work on the exact original dependency.

        A later response_reconsideration can retain the old result; its old cycle
        does not become another interpretation. Known current recovery does not
        rewrite the historical error, and expired eligibility can reject genuine
        later focal work without changing that work's meaning.
        """
        if (not isinstance(result, ExtractionInterpretationV1) or result.cycle_id != cycle or result.cutoff_tick != tick
                or self._interpretation_seen):
            raise ValueError("extraction F requires one actually performed current-opportunity interpretation")
        _index(result.cycle_id, "interpretation_cycle", minimum=1)
        _index(result.cutoff_tick, "interpretation_tick")
        if dependency is None or result.request is not dependency or not dependency.admitted_tick <= tick < dependency.expires_at_tick:
            raise ValueError("extraction interpretation replaced, invented or outlived its original question")
        self._request(dependency, dependency.outcome)
        source = result.current_source
        basis = dependency.outcome.claim.application.projection.basis
        if (not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.source_map_ref != basis.source_map_ref or source.maternal.seed != basis.maternal.seed
                or source.applied_cycle != cycle or source.cutoff_tick != tick or not source.focal_accessible):
            raise ValueError("extraction interpretation lacks the actual current accessible source")
        if (not isinstance(result.working_id, str) or not 1 <= len(result.working_id) <= 100
                or not isinstance(result.relation_relevance, tuple)
                or any(not isinstance(row, tuple) or len(row) != 2 or row[1] not in
                       {"unknown", "still_relevant", "currently_supported"} for row in result.relation_relevance)
                or tuple(name for name, _ in result.relation_relevance) != dependency.relations):
            raise ValueError("extraction interpretation changed its requested relation set")
        values = {value for _, value in result.relation_relevance}
        if "unknown" in values:
            expected = "unresolved_current_relevance"
        elif "still_relevant" in values:
            expected = "still_relevant"
        else:
            expected = "historical_resolved"
        if not values or result.status != expected:
            raise ValueError("extraction interpretation status contradicts its reported relevance")

    def reconcile(
        self, *, cycle_id: int, cutoff_tick: int, registration: SuckleExtractionClaimV1 | None = None,
        outcomes: tuple[SuckleExtractionOutcomeV1, ...] = (), requests: tuple[ExtractionMismatchRequestV1, ...] = (),
        interpretation: ExtractionInterpretationV1 | None = None, comparison_enabled: bool = True, attention_enabled: bool = True,
    ) -> ExtractionLearningPhaseFReportV1:
        """Atomically reconcile one actual F opportunity without durable learning.

        Validate the bounded input, expire eligibility before admitting evidence,
        retain original dependencies, consume known relations only when permitted,
        then register this opportunity's selected/authorized contribution. No new
        action outcome can be used here. With L-E disabled, known discrepancies
        await interpretation conservatively; F cannot buy free demanding work.
        Unresolved interpretation does not renew eligibility or request lifetime.
        """
        cycle, tick = _index(cycle_id, "cycle_id", minimum=1), _index(cutoff_tick, "cutoff_tick")
        if self._closed or cycle <= self._last_cycle or tick <= self._last_tick:
            raise RuntimeError("extraction participation is closed or F was already reconciled")
        if not isinstance(comparison_enabled, bool) or not isinstance(attention_enabled, bool):
            raise TypeError("extraction teaching settings must be Boolean")
        if not isinstance(outcomes, tuple) or len(outcomes) > 1 or not isinstance(requests, tuple) or len(requests) > 1:
            raise ValueError("one extraction result and dependency per original contribution")
        for outcome in outcomes:
            self._outcome(outcome, cycle, tick)
            if outcome.comparison_enabled != comparison_enabled:
                raise ValueError("extraction teaching cannot change the original comparison setting")
        dependency = self._dependency
        for request in requests:
            if not outcomes or self._seen is not None:
                raise ValueError("extraction dependency requires this opportunity's new C2 publication")
            self._request(request, outcomes[0])
            dependency = request
        if not attention_enabled and (requests or interpretation is not None):
            raise ValueError("disabled extraction Attention cannot supply focal interpretation")
        if registration is not None:
            self._claim(registration)
            if self._registration is not None or self._seen is not None or outcomes:
                raise ValueError("one original extraction registration per generation; no replacement or late participation")
            if registration.application.cycle_id != cycle or registration.start_tick != tick:
                raise ValueError("extraction participation belongs to its original application opportunity")
        if interpretation is not None:
            self._interpretation(interpretation, dependency, cycle, tick)

        participant = self._participant
        inspected = int(participant is not None)
        dispositions: list[ExtractionTeachingDispositionV1] = []

        def report(claim: SuckleExtractionClaimV1, status: str, outcome: SuckleExtractionOutcomeV1 | None = None, *,
                   accepted: tuple[tuple[str, str], ...] = (), result: ExtractionInterpretationV1 | None = None) -> None:
            """Accumulate only detached no-update decisions before the atomic commit."""
            dispositions.append(ExtractionTeachingDispositionV1(claim.application.projection.pnm.pnm_id,
                                                               status, cycle, tick, outcome, accepted, result))

        if participant is not None and tick >= participant.expires_before_tick:
            report(participant.claim, "eligibility_expired", participant.outcome)
            participant = None
        seen = self._seen
        for outcome in outcomes:
            if seen is not None:
                report(outcome.claim, "duplicate_ignored", outcome)
                continue
            seen = outcome
            if participant is None:
                expired = tick >= outcome.claim.start_tick + _ELIGIBILITY_TICKS
                status = "rejected_expired_eligibility" if expired else "rejected_unregistered_operation"
                report(outcome.claim, status, outcome)
                continue
            needs_focal = dependency is not None or (not attention_enabled and any(value == "mismatch" for _, value in outcome.relations))
            participant = replace(participant, outcome=outcome, request=dependency, awaiting_interpretation=needs_focal)
            if needs_focal:
                report(participant.claim, "pending_interpretation", outcome)
        handled = False
        if participant is not None and participant.outcome is not None:
            outcome = participant.outcome
            ready = not participant.awaiting_interpretation
            if participant.awaiting_interpretation and interpretation is not None:
                handled = True
                ready = interpretation.status != "unresolved_current_relevance"
                if not ready:
                    report(participant.claim, "pending_unresolved_interpretation", outcome, result=interpretation)
            if ready:
                known = tuple((name, value) for name, value in outcome.relations if value in {"matched", "mismatch"})
                if not comparison_enabled:
                    report(participant.claim, "comparison_disabled_no_teaching", outcome, result=interpretation)
                elif (outcome.installed and outcome.command_ticks and outcome.status != "execution_unknown_after_fault" and known):
                    report(participant.claim, "accepted_no_update", outcome, accepted=known, result=interpretation)
                else:
                    report(participant.claim, f"rejected_{outcome.status}", outcome, result=interpretation)
                participant = None
        if interpretation is not None and not handled:
            outcome = interpretation.request.outcome
            expired = tick >= outcome.claim.start_tick + _ELIGIBILITY_TICKS
            status = "rejected_expired_interpretation" if expired else "rejected_unregistered_interpretation"
            report(outcome.claim, status, outcome, result=interpretation)
        new_participation: ExtractionParticipationV1 | None = None
        if registration is not None:
            if not registration.targets:
                report(registration, "not_applied")
            elif not comparison_enabled:
                report(registration, "comparison_disabled_no_teaching")
            else:
                new_participation = ExtractionParticipationV1(self.recipient_id, registration, cycle)
                participant = new_participation
        result_report = ExtractionLearningPhaseFReportV1(
            self.recipient_id, cycle, tick, new_participation, tuple(dispositions),
            () if participant is None else (participant,), len(outcomes), inspected,
        )
        if registration is not None:
            self._registration = registration
        self._participant, self._seen, self._dependency = participant, seen, dependency
        self._interpretation_seen = self._interpretation_seen or interpretation is not None
        self._last_cycle, self._last_tick = cycle, tick
        self._history.extend(dispositions)
        return result_report
