#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-K: original suckle participation and a called no-learning F path.

The feeding-detail source owns this optional extension. Eight participants can
retain the original selected task, source sample, PNM and authorized closure target.
Eligibility expires before creation cycle + 4, independently of source access,
prediction arrival, relevance, task lifetime and motor permission. These are the
existing short-delay hook's engineering bounds, not biological time constants.

The real Phase-F callback receives canonical earlier C2 results and the actual D
interpretation, if any. It performs no rich interpretation, task selection, body
execution or durable learning. With the Attention route disabled, discrepancies
wait conservatively for eligibility expiry rather than buying free focal work.
Registration records selection and permission before outer installation; it is
not proof of execution. Accepted known relations remain evidence-only: no cause,
latch proof, milk, nourishment, calibration or acquired primitive is inferred.
F uses the already performed J interpretation; it never recomputes relevance,
consumes an Attention question or extends that question's independent lifetime.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSeedV1
from nca8_suckle_attention import SuckleInterpretationV1, SuckleMismatchRequestV1
from nca8_suckle import SuckleTaskV1
from nca8_suckle_outcomes import (
    SuckleClaimV1, SuckleOutcomeV1, validate_suckle_claim_v1, validate_suckle_outcome_v1,
)

__version__ = "0.1.0"
__all__ = ["SuckleParticipationV1", "SuckleTeachingDispositionV1", "SuckleLearningPhaseFReportV1",
           "SuckleLearningHookV1", "__version__"]


def _index(value: int, name: str, *, minimum: int = 0) -> int:
    """Reject coerced/Boolean and overflowing indices before mutating an owner."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value < 2**63 - 17:
        raise ValueError(f"{name} must be a bounded integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class SuckleParticipationV1:
    """Original source/application candidate with an independent short eligibility.

    The immutable task and claim identify participation, not a live execution
    grant. outcome/request refer to actual publishers within this generation.
    Retained descriptions never restore a source's current sensory accessibility.
    """

    recipient_id: str
    claim: SuckleClaimV1
    task: SuckleTaskV1
    created_cycle: int
    outcome: SuckleOutcomeV1 | None = None
    request: SuckleMismatchRequestV1 | None = None
    awaiting_interpretation: bool = False

    @property
    def expires_before_cycle(self) -> int:
        """Return exclusive expiry; rereading or later evidence cannot renew it."""
        return self.created_cycle + 4

    @property
    def pnm_id(self) -> str:
        """Identify the original forecast independently of the current PNM."""
        return self.claim.preview.pnm.pnm_id

    def as_dict(self) -> dict[str, object]:
        """Detach source/task/evidence provenance without granting learned authority."""
        basis = self.claim.preview.basis
        visual = basis.maternal.visual
        return {"recipient_id": self.recipient_id, "source_map_ref": basis.source_map_ref.as_dict(),
                "origin": self.claim.request.origin.as_dict(), "pnm_id": self.pnm_id, "task": self.task.as_dict(),
                "source_sample_id": visual.sample_id, "source_event_tick": visual.event_tick,
                "source_cutoff_tick": basis.cutoff_tick, "seed": basis.seed.as_dict(),
                "oral_sample_id": basis.oral_feedback.sample_id if basis.oral_feedback is not None else None,
                "oral_event_tick": basis.oral_feedback.event_tick if basis.oral_feedback is not None else None,
                "registration_scope": "selected_authorized_not_execution",
                "created_cycle": self.created_cycle, "expires_before_cycle": self.expires_before_cycle,
                "compatible_relations": list(self.claim.compatible_relations),
                "unevaluable_relations": list(self.claim.unevaluable_relations),
                "authorized_target_ids": [item.target.target_id for item in self.claim.targets],
                "outcome_number": self.outcome.number if self.outcome is not None else None,
                "interpretation_request_id": self.request.request_id if self.request is not None else None,
                "awaiting_interpretation": self.awaiting_interpretation,
                "maturity": "eligibility_only", "grants_motor_authority": False}


@dataclass(frozen=True, slots=True)
class SuckleTeachingDispositionV1:
    """One admission, waiting, expiry or rejection with exactly zero learned updates.

    Known compatible closure/contact relations may be accepted without assuming correct
    action attribution. Missing evidence, observed seal and current recovery do
    not rewrite the original forecast or establish latch, milk or task success.
    """

    pnm_id: str
    status: str
    cycle_id: int
    cutoff_tick: int
    outcome: SuckleOutcomeV1 | None = None
    accepted_relations: tuple[tuple[str, str], ...] = ()
    interpretation: SuckleInterpretationV1 | None = None

    def as_dict(self) -> dict[str, object]:
        """Keep original acquisition, interpretation and reconciliation times separate."""
        evidence = self.outcome.evidence if self.outcome is not None else None
        sample = evidence.feedback if evidence is not None else None
        return {"pnm_id": self.pnm_id, "status": self.status, "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "outcome_number": self.outcome.number if self.outcome is not None else None,
                "original_outcome_status": self.outcome.status if self.outcome is not None else None,
                "evidence_sample_id": sample.sample_id if sample is not None else None,
                "evidence_event_tick": sample.event_tick if sample is not None else None,
                "evidence_available_tick": sample.available_tick if sample is not None else None,
                "accepted_relations": dict(self.accepted_relations),
                "interpretation_status": self.interpretation.status if self.interpretation is not None else None,
                "interpretation_cycle": self.interpretation.cycle_id if self.interpretation is not None else None,
                "command_intervals": self.outcome.command_intervals if self.outcome is not None else 0,
                "installation_reported": self.outcome.installed if self.outcome is not None else False,
                "action_causation": "uncertain", "durable_learning_updates": 0}


@dataclass(frozen=True, slots=True)
class SuckleLearningPhaseFReportV1:
    """Actual F work for one configured recipient, not a scan of all learning areas.

    The new E contribution cannot have its future physical outcome here. Offered
    outcomes concern older original claims. Current source refresh, eligibility
    and accepted_no_update are not durable plasticity or causal action credit.
    """

    recipient_id: str
    cycle_id: int
    cutoff_tick: int
    new_participation: SuckleParticipationV1 | None
    dispositions: tuple[SuckleTeachingDispositionV1, ...]
    pending: tuple[SuckleParticipationV1, ...]
    offered_outcomes: int
    inspected_participants: int

    def as_dict(self) -> dict[str, object]:
        """Expose bounded reconciliation without inventing effective learned change."""
        return {"profile": "suckle_no_learning_v1", "recipient_id": self.recipient_id,
                "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick, "maturity": "eligibility_only",
                "new_participation": self.new_participation.as_dict() if self.new_participation is not None else None,
                "dispositions": [item.as_dict() for item in self.dispositions],
                "pending": [item.as_dict() for item in self.pending], "offered_outcomes": self.offered_outcomes,
                "inspected_participants": self.inspected_participants,
                "due_owners_visited": int(bool(self.new_participation or self.dispositions or self.inspected_participants)),
                "current_source_refresh_is_learning": False, "new_action_outcome_available": False,
                "already_effective_durable_changes": 0, "due_durable_changes": 0, "durable_learning_updates": 0,
                "ledger_rows_executed": 0, "restores_motor_permission": False}


class SuckleLearningHookV1:
    """Own original suckle eligibility independently of WNM and diagnostic history.

    reconcile() validates the complete bounded batch before committing temporary
    state. Foreign or malformed dependencies raise. Valid unknown, duplicate,
    unregistered and expired results receive explicit no-update dispositions.
    This owner cannot read a physical provider, change a source, select a task,
    interpret current relevance, publish an outcome or access RNG. close()
    permanently revokes this generation's eligibility, retaining diagnostics only.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: FeedingDetailSeedV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, FeedingDetailSeedV1):
            raise TypeError("suckle participation requires its typed stream and feeding seed")
        _index(diagnostic_capacity, "diagnostic_capacity", minimum=1)
        if diagnostic_capacity > 32:
            raise ValueError("suckle participation diagnostic capacity cannot exceed 32")
        self.stream, self.seed = stream, seed
        self.recipient_id = "feeding_detail_association:feeding_detail:suckle_consequence"
        self._pending: dict[str, SuckleParticipationV1] = {}
        self._history: deque[SuckleTeachingDispositionV1] = deque(maxlen=diagnostic_capacity)
        self._last_cycle, self._last_tick, self._last_outcome = 0, -1, 0
        self._closed = False

    def retained_counts(self) -> dict[str, int]:
        """Measure live participants separately from the bounded diagnostic window."""
        return {"suckle_learning_participants": len(self._pending), "suckle_learning_dispositions": len(self._history)}

    def pending(self) -> tuple[SuckleParticipationV1, ...]:
        """Read immutable participants without extending eligibility or source access."""
        return tuple(self._pending.values())

    def history(self) -> tuple[SuckleTeachingDispositionV1, ...]:
        """Read diagnostics; no functional decision uses this disposable history."""
        return tuple(self._history)

    def close(self) -> None:
        """Revoke processing on reset/fault without undoing earlier physical effects."""
        self._pending.clear()
        self._closed = True

    def _claim(self, claim: SuckleClaimV1) -> None:
        """Reuse the canonical prospective/permission check, with this recipient seed."""
        validate_suckle_claim_v1(claim, stream=self.stream)
        if claim.preview.basis.seed != self.seed:
            raise ValueError("suckle participation has foreign feeding-part organization")

    def _outcome(self, outcome: SuckleOutcomeV1, cycle: int, tick: int) -> None:
        """Validate earlier evidence without republishing or consuming its claim."""
        validate_suckle_outcome_v1(outcome, stream=self.stream, cutoff_tick=tick)
        self._claim(outcome.claim)
        if outcome.claim.preview.pnm.created_cycle >= cycle:
            raise ValueError("a just-issued suckle action has no physical outcome at F")
        if outcome.number > self._last_outcome and outcome.evaluated_tick != tick:
            raise ValueError("new suckle teaching must arrive at its original C2 publication")
        participant = self._pending.get(outcome.claim.preview.pnm.pnm_id)
        if participant is not None and participant.claim is not outcome.claim:
            raise ValueError("copied or changed claim cannot replace original suckle participation")
        if participant is not None and participant.outcome is not None and participant.outcome is not outcome:
            raise ValueError("another outcome cannot replace original suckle evidence")

    def _request(self, request: SuckleMismatchRequestV1) -> None:
        """Check published dependency identity, not its current-world significance."""
        if not isinstance(request, SuckleMismatchRequestV1):
            raise TypeError("suckle dependency must be the typed published request")
        self._claim(request.outcome.claim)
        _index(request.admitted_tick, "request_admitted_tick")
        if request.admitted_tick != request.outcome.evaluated_tick:
            raise ValueError("Suckle dependency must retain its original publication time")
        if (request.request_id != f"suckle_mismatch:g{self.stream.generation}:o{request.outcome.number}"
                or request.significance not in {"feeding_part_identity_contradiction", "expected_seal_not_supported",
                                               "consequential_suckle_relation_discrepancy"}
                or not isinstance(request.relations, tuple) or not 1 <= len(request.relations) <= 4
                or len(set(request.relations)) != len(request.relations)):
            raise ValueError("suckle dependency has invalid identity or relation metadata")
        if request.outcome.status == "identity_contradicted":
            if request.relations != ("identity",) or request.significance != "feeding_part_identity_contradiction":
                raise ValueError("identity contradiction has its own suckle dependency")
        elif (request.outcome.status != "mismatch" or request.significance == "feeding_part_identity_contradiction"
              or any((name, "mismatch") not in request.outcome.relations for name in request.relations)):
            raise ValueError("suckle dependency requires an executed corresponding discrepancy")
        elif (request.significance == "expected_seal_not_supported" and request.relations != ("seal",)
              or request.significance == "consequential_suckle_relation_discrepancy" and "seal" in request.relations):
            raise ValueError("Suckle dependency changed its original relation family")

    def _interpretation(
        self, result: SuckleInterpretationV1, requests: tuple[SuckleMismatchRequestV1, ...], cycle: int, tick: int,
    ) -> None:
        """Require an actual current focal result linked to the original dependency.

        Check structural consistency, not current geometric relevance. An actual
        result arriving after eligibility expiry is valid but cannot revive its
        participant. Current-source resolution never edits the historical error.
        """
        if not isinstance(result, SuckleInterpretationV1) or result.cycle_id != cycle or result.cutoff_tick != tick:
            raise ValueError("suckle F accepts interpretation actually performed this opportunity")
        _index(result.cycle_id, "interpretation_cycle", minimum=1)
        _index(result.cutoff_tick, "interpretation_cutoff")
        dependency, source = result.request, result.current_source
        if not isinstance(dependency, SuckleMismatchRequestV1) or not dependency.admitted_tick <= tick < dependency.expires_at_tick:
            raise ValueError("suckle interpretation used an invalid or expired request")
        self._request(dependency)
        self._outcome(dependency.outcome, cycle, tick)
        if (not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.applied_cycle != cycle or source.cutoff_tick != tick or not source.focal_accessible
                or source.maternal.seed != dependency.outcome.claim.preview.basis.maternal.seed):
            raise ValueError("suckle interpretation lacks this opportunity's selected source")
        participant = self._pending.get(dependency.outcome.claim.preview.pnm.pnm_id)
        if not any(item is dependency for item in requests) and (
            participant is None or participant.request is not dependency
        ):
            # Expired/unregistered eligibility may coexist with a later real D
            # result. A live participant, however, must keep its original request.
            if participant is not None:
                raise ValueError("copied suckle request cannot replace its original dependency")
        if (not isinstance(result.working_id, str) or not 1 <= len(result.working_id) <= 100
                or not isinstance(result.relation_relevance, tuple)
                or any(not isinstance(row, tuple) or len(row) != 2 or row[1] not in
                       {"unknown", "still_relevant", "currently_supported"} for row in result.relation_relevance)
                or tuple(name for name, _ in result.relation_relevance) != dependency.relations):
            raise ValueError("suckle interpretation changed its requested relation set")
        values = {value for _, value in result.relation_relevance}
        expected = "unresolved_current_relevance" if "unknown" in values else "still_relevant" if "still_relevant" in values else "historical_resolved"
        if not values or result.status != expected:
            raise ValueError("suckle interpretation status contradicts its reported relevance")

    def reconcile(
        self, *, cycle_id: int, cutoff_tick: int, registration: SuckleClaimV1 | None = None,
        task: SuckleTaskV1 | None = None, outcomes: tuple[SuckleOutcomeV1, ...] = (),
        requests: tuple[SuckleMismatchRequestV1, ...] = (), interpretation: SuckleInterpretationV1 | None = None,
        comparison_enabled: bool = True, attention_enabled: bool = True,
    ) -> SuckleLearningPhaseFReportV1:
        """Reconcile one F opportunity with independent expiry and zero durable change.

        Validate everything, copy temporary pending state, expire old eligibility,
        offer canonical earlier results once, consume eligible known relations and
        finally register the current selected contribution without its future
        outcome. Significant requests await the actual D result. Unknown relevance
        stays pending until original eligibility expires. Attention-off discrepancies
        receive no substitute interpretation. No source/target/PNM is modified.
        """
        cycle, tick = _index(cycle_id, "cycle_id", minimum=1), _index(cutoff_tick, "cutoff_tick")
        if self._closed or cycle <= self._last_cycle or tick <= self._last_tick:
            raise RuntimeError("suckle participation is closed or F was already reconciled")
        if not isinstance(comparison_enabled, bool) or not isinstance(attention_enabled, bool):
            raise TypeError("suckle teaching settings must be Boolean")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8 or not isinstance(requests, tuple) or len(requests) > 8:
            raise ValueError("suckle F accepts at most eight outcomes and eight requests")
        for outcome in outcomes:
            self._outcome(outcome, cycle, tick)
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("suckle teaching must preserve distinct increasing publisher order")
        if len({item.claim.preview.pnm.pnm_id for item in outcomes}) != len(outcomes):
            raise ValueError("one suckle claim cannot receive two results in a batch")
        for request in requests:
            if not isinstance(request, SuckleMismatchRequestV1) or not any(request.outcome is item for item in outcomes):
                raise ValueError("suckle dependency requires this batch's actual canonical result")
            self._request(request)
            if request.admitted_tick != tick or request.outcome.number <= self._last_outcome:
                raise ValueError("suckle dependency changed its original C2 publication")
        if len({item.outcome.number for item in requests}) != len(requests):
            raise ValueError("one suckle outcome cannot acquire two interpretation dependencies")
        if not attention_enabled and (requests or interpretation is not None):
            raise ValueError("disabled suckle Attention cannot supply focal interpretation")
        if registration is not None:
            self._claim(registration)
            preview = registration.preview
            if preview.pnm.pnm_id in self._pending:
                raise ValueError("new participation cannot reuse a live suckle claim")
            if (not isinstance(task, SuckleTaskV1) or task.task_id != preview.task_id or task.region_id != preview.region_id
                    or task.status != "active" or task.started_cycle > cycle or task.started_tick > tick):
                raise ValueError("suckle participation requires its original active task context")
            if preview.pnm.created_cycle != cycle or preview.basis.cutoff_tick != tick:
                raise ValueError("suckle participation belongs to its actual application opportunity")
        elif task is not None:
            raise ValueError("a task without a selected application is not new participation")
        if interpretation is not None:
            self._interpretation(interpretation, requests, cycle, tick)
        pending = dict(self._pending)
        dispositions: list[SuckleTeachingDispositionV1] = []
        inspected = len(pending)

        def report(pnm_id: str, status: str, outcome: SuckleOutcomeV1 | None = None, *,
                   accepted: tuple[tuple[str, str], ...] = (), result: SuckleInterpretationV1 | None = None) -> None:
            """Accumulate detached no-update decisions before committing local state."""
            dispositions.append(SuckleTeachingDispositionV1(pnm_id, status, cycle, tick, outcome, accepted, result))

        for pnm_id, expiring in tuple(pending.items()):
            if cycle >= expiring.expires_before_cycle:
                report(pnm_id, "eligibility_expired", expiring.outcome)
                del pending[pnm_id]
        last_outcome = self._last_outcome
        for outcome in outcomes:
            pnm_id = outcome.claim.preview.pnm.pnm_id
            if outcome.number <= last_outcome:
                report(pnm_id, "duplicate_ignored", outcome)
                continue
            last_outcome = outcome.number
            participant = pending.get(pnm_id)
            if participant is None:
                status = "rejected_expired_eligibility" if cycle >= outcome.claim.preview.pnm.created_cycle + 4 else "rejected_unregistered_operation"
                report(pnm_id, status, outcome)
                continue
            dependency = next((item for item in requests if item.outcome is outcome), None)
            needs_interpretation = dependency is not None or (not attention_enabled and outcome.status in {"mismatch", "identity_contradicted"})
            pending[pnm_id] = replace(participant, outcome=outcome, request=dependency, awaiting_interpretation=needs_interpretation)
            if needs_interpretation:
                report(pnm_id, "pending_interpretation", outcome)
        interpretation_handled = False
        for pnm_id, participant in tuple(pending.items()):
            participant_outcome = participant.outcome
            if participant_outcome is None:
                continue
            focal_result: SuckleInterpretationV1 | None = None
            if participant.awaiting_interpretation:
                if interpretation is None or interpretation.request is not participant.request:
                    continue
                if interpretation.request.outcome is not participant_outcome:
                    raise ValueError("suckle interpretation did not answer original participant evidence")
                interpretation_handled = True
                if interpretation.status == "unresolved_current_relevance":
                    report(pnm_id, "pending_unresolved_interpretation", participant_outcome, result=interpretation)
                    continue
                focal_result = interpretation
            known = tuple((name, value) for name, value in participant_outcome.relations if value in {"matched", "mismatch"})
            if not comparison_enabled:
                report(pnm_id, "comparison_disabled_no_teaching", participant_outcome, result=focal_result)
            elif participant_outcome.status in {"matched", "partly_matched", "mismatch"} and known:
                report(pnm_id, "accepted_no_update", participant_outcome, accepted=known, result=focal_result)
            else:
                report(pnm_id, f"rejected_{participant_outcome.status}", participant_outcome, result=focal_result)
            del pending[pnm_id]
        if interpretation is not None and not interpretation_handled:
            old_outcome = interpretation.request.outcome
            expired = cycle >= old_outcome.claim.preview.pnm.created_cycle + 4
            report(old_outcome.claim.preview.pnm.pnm_id,
                   "rejected_expired_interpretation" if expired else "rejected_unregistered_interpretation",
                   old_outcome, result=interpretation)
        new_participation: SuckleParticipationV1 | None = None
        if registration is not None:
            pnm_id = registration.preview.pnm.pnm_id
            if not registration.targets:
                report(pnm_id, "not_applied")
            elif not comparison_enabled:
                report(pnm_id, "comparison_disabled_no_teaching")
            else:
                if task is None:
                    raise ValueError("missing original suckle task context")
                new_participation = SuckleParticipationV1(self.recipient_id, registration, task, cycle)
                pending[pnm_id] = new_participation
        if len(pending) > 8:
            raise OverflowError("eight suckle participants; no silent eviction or extended eligibility")
        result_report = SuckleLearningPhaseFReportV1(
            self.recipient_id, cycle, tick, new_participation, tuple(dispositions), tuple(pending.values()), len(outcomes), inspected,
        )
        self._pending = pending
        self._last_cycle, self._last_tick, self._last_outcome = cycle, tick, last_outcome
        self._history.extend(dispositions)
        return result_report
