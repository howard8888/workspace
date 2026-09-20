#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1G-C: a called, source-owned no-learning consequence hook.

Only the POSTURE-SUPPORT sensory owner constructs this optional extension.
Participation names the original source, selected Righting application, forecast
and authorized targets. It is not a second WNM, a replayable motor grant or proof
of causation. The hook maintains real temporary eligibility, but contains no
parameter update, memory writer, task selector, physical call or RNG operation.

Profile righting_no_learning_v1 permits eight participant records and four focal
cycles of eligibility: a record created at c expires before reconciliation c+4.
This clock is independent of the physical prediction window, source access,
Attention-request expiry, target leases and diagnostic retention. The first
consumer is intentionally called at F; that does not mandate all-F timing for
future learners. Known compatible forecast evidence can be accepted without
claiming causal action credit. Required demanding interpretation must already
have run through 1G-B; F never performs it or invents a successful substitute.
"""

#pylint: disable=too-many-boolean-expressions

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_maps import DurableNavMapRefV1
from nca8_outcome_attention import RightingInterpretationV1, RightingMismatchRequestV1
from nca8_outcomes import RightingClaimOutcomeV1, RightingClaimRegistrationV1
from nca8_righting import RightingContextV1
from nca8_sensorimotor_contracts import CommittedBodyTargetV1

__version__ = "0.1.0"
__all__ = [
    "RightingParticipationV1", "RightingTeachingDispositionV1", "LearningPhaseFReportV1", "RightingLearningHookV1", "__version__",
]

_MAX_PARTICIPANTS = 8
_RELATIONS = ("tilt", "extension", "loading", "destabilization", "contact")
_RESULT_KINDS = ("matched", "mismatch", "unknown", "unevaluable_authorization")
_TERMINAL_KINDS = (
    "matched", "partly_matched", "mismatch", "unknown", "observed_without_command", "not_applied",
    "interrupted", "cancelled", "expired_unresolved", "execution_unknown", "unevaluable_authorization", "comparison_disabled",
)


def _index(value: int, name: str, *, minimum: int = 0) -> int:
    """Validate bounded non-Boolean indices before changing any hook state."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value < 2**63 - 17:
        raise ValueError(f"{name} must be a bounded integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class RightingParticipationV1:
    """An original source/operation participant, with independent short eligibility.

    registration retains immutable pre-handoff meaning. outcome, when present,
    is the original publisher result rather than a reconstruction from a trace.
    The optional request is the actual 1G-B interpretation dependency. No current
    WNM, Ready set, mutable map, executor or physical provider is retained here.
    """

    recipient_id: str
    registration: RightingClaimRegistrationV1
    context: RightingContextV1
    created_cycle: int
    outcome: RightingClaimOutcomeV1 | None = None
    request: RightingMismatchRequestV1 | None = None
    awaiting_interpretation: bool = False

    @property
    def expires_before_cycle(self) -> int:
        """Keep exactly four F opportunities, without renewal on reading or feedback."""
        return self.created_cycle + 4

    @property
    def pnm_id(self) -> str:
        """Return the originating claim identity, not the current prospective map."""
        return self.registration.preview.pnm.pnm_id

    def as_dict(self) -> dict[str, object]:
        """Export bounded provenance without granting eligibility or action rights."""
        preview = self.registration.preview
        basis = preview.basis.feedback
        return {
            "recipient_id": self.recipient_id, "source_map_ref": preview.basis.source_map_ref.as_dict(),
            "origin": self.registration.request.origin.as_dict(), "pnm_id": self.pnm_id,
            "source_sample_id": basis.sample_id if basis is not None else None,
            "source_event_tick": basis.event_tick if basis is not None else None,
            "context": self.context.as_dict(), "created_cycle": self.created_cycle,
            "expires_before_cycle": self.expires_before_cycle,
            "compatible_relations": list(self.registration.compatible_relations),
            "unevaluable_relations": list(self.registration.unevaluable_relations),
            "authorized_target_ids": [item.target.target_id for item in self.registration.targets],
            "outcome_number": self.outcome.number if self.outcome is not None else None,
            "interpretation_request_id": self.request.request_id if self.request is not None else None,
            "awaiting_interpretation": self.awaiting_interpretation,
            "maturity": "eligibility_only", "grants_motor_authority": False,
        }


@dataclass(frozen=True, slots=True)
class RightingTeachingDispositionV1:
    """One actual admission, waiting, rejection, expiry or no-update disposition.

    accepted_no_update accepts corresponding forecast evidence only. It neither
    assigns action credit nor implements L12's future learned change. Empty or
    unavailable relations remain explicit; the original publisher is unchanged.
    """

    pnm_id: str
    status: str
    cycle_id: int
    cutoff_tick: int
    outcome: RightingClaimOutcomeV1 | None = None
    accepted_relations: tuple[tuple[str, str], ...] = ()
    interpretation: RightingInterpretationV1 | None = None

    def as_dict(self) -> dict[str, object]:
        """Preserve event time, declared scope and uncertainty in detached output."""
        evidence = self.outcome.evidence if self.outcome is not None else None
        return {
            "pnm_id": self.pnm_id, "status": self.status, "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
            "outcome_number": self.outcome.number if self.outcome is not None else None,
            "original_outcome_status": self.outcome.status if self.outcome is not None else None,
            "evidence_sample_id": evidence.sample_id if evidence is not None else None,
            "evidence_event_tick": evidence.event_tick if evidence is not None else None,
            "evidence_available_tick": evidence.available_tick if evidence is not None else None,
            "accepted_relations": dict(self.accepted_relations),
            "interpretation_status": self.interpretation.status if self.interpretation is not None else None,
            "interpretation_cycle": self.interpretation.cycle_id if self.interpretation is not None else None,
            "action_causation": "uncertain", "durable_learning_updates": 0,
        }


@dataclass(frozen=True, slots=True)
class LearningPhaseFReportV1:
    """A real F call for one participating owner, not a scan of a learner registry.

    New participation concerns the just-issued request and has no future outcome.
    Dispositions concern earlier available evidence or explicit nonapplication.
    Pending records retain their own expiry. No effective/deferred durable change
    exists in this implementation, so every reported durable-update count is zero.
    """

    recipient_id: str
    cycle_id: int
    cutoff_tick: int
    new_participation: RightingParticipationV1 | None
    dispositions: tuple[RightingTeachingDispositionV1, ...]
    pending: tuple[RightingParticipationV1, ...]
    offered_outcomes: int
    inspected_participants: int

    def as_dict(self) -> dict[str, object]:
        """Export the reconciled no-learning state, not a checkpoint to restore."""
        return {
            "profile": "righting_no_learning_v1", "recipient_id": self.recipient_id,
            "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick, "maturity": "eligibility_only",
            "new_participation": self.new_participation.as_dict() if self.new_participation is not None else None,
            "dispositions": [item.as_dict() for item in self.dispositions], "pending": [item.as_dict() for item in self.pending],
            "offered_outcomes": self.offered_outcomes, "inspected_participants": self.inspected_participants,
            "due_owners_visited": int(bool(self.new_participation or self.dispositions or self.inspected_participants)),
            "current_source_refresh_is_learning": False, "new_action_outcome_available": False,
            "already_effective_durable_changes": 0, "due_durable_changes": 0, "durable_learning_updates": 0,
            "ledger_rows_executed": 0, "restores_motor_permission": False,
        }


class RightingLearningHookV1:
    """Maintain one source owner's bounded, non-learning consequence eligibility.

    The sensory owner constructs this once before admitting motor evidence.
    reconcile() is called exactly once per completed focal opportunity at F.
    It receives canonical outcomes frozen earlier in C2, actual source requests,
    and at most the interpretation really computed at D. It never reads current
    focus to select a recipient, visits other maps, or calls the L01-L25 registry.

    Validate the complete batch before mutation. Malformed/foreign/copy-derived
    provenance fails explicitly; a valid unknown, expired, unregistered or
    nonapplied contribution instead receives an honest no-update disposition.
    Diagnostic history is never read by the functional path. close() invalidates
    this generation's temporary rights without erasing another owner's history.
    """

    def __init__(self, stream: MotorStreamRefV1, source_ref: DurableNavMapRefV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(source_ref, DurableNavMapRefV1):
            raise TypeError("learning hook requires typed original stream and source")
        _index(diagnostic_capacity, "diagnostic_capacity", minimum=1)
        if diagnostic_capacity > 32:
            raise ValueError("learning diagnostic capacity cannot exceed 32")
        self.stream, self.source_ref = stream, source_ref
        self.recipient_id = f"body_sensory:{source_ref.map_id}:consequence"
        self._pending: dict[str, RightingParticipationV1] = {}
        self._history: deque[RightingTeachingDispositionV1] = deque(maxlen=diagnostic_capacity)
        self._last_cycle, self._last_tick, self._last_outcome = 0, -1, 0
        self._closed = False

    def retained_counts(self) -> dict[str, int]:
        """Measure actual temporary records; no read renews eligibility."""
        return {"learning_participants": len(self._pending), "learning_dispositions": len(self._history)}

    def pending(self) -> tuple[RightingParticipationV1, ...]:
        """Expose original immutable participants, independent of Ready/focal access."""
        return tuple(self._pending.values())

    def history(self) -> tuple[RightingTeachingDispositionV1, ...]:
        """Expose diagnostic dispositions only; functional routing never consults this."""
        return tuple(self._history)

    def close(self) -> None:
        """Permanently revoke this generation's eligibility on reset or core failure."""
        self._pending.clear()
        self._closed = True

    def _registration(self, registration: RightingClaimRegistrationV1) -> None:
        """Check original source/operation and mapped meaning, not current WNM."""
        if not isinstance(registration, RightingClaimRegistrationV1):
            raise TypeError("participation requires an original typed claim registration")
        preview, origin = registration.preview, registration.request.origin
        if preview.basis.stream != self.stream or origin.stream != self.stream or preview.basis.source_map_ref != self.source_ref:
            raise ValueError("learning contribution has foreign source or generation")
        if (origin.task_id != preview.task_id or origin.application_id != preview.pnm.application_id
                or preview.pnm.primitive_id != "ip:righting"):
            raise ValueError("learning contribution has inconsistent operation identity")
        for group in (registration.compatible_relations, registration.unevaluable_relations):
            if not isinstance(group, tuple) or any(name not in _RELATIONS for name in group):
                raise ValueError("invalid learning relation set")
        names = (*registration.compatible_relations, *registration.unevaluable_relations)
        if len(names) != len(set(names)) or len(names) > 5:
            raise ValueError("learning relations must be unique and disjoint")
        if not isinstance(registration.targets, tuple) or len(registration.targets) > 2 or any(
            not isinstance(target, CommittedBodyTargetV1) for target in registration.targets
        ):
            raise ValueError("participation requires at most two typed authorized targets")
        if len({target.target.target_id for target in registration.targets}) != len(registration.targets):
            raise ValueError("participation cannot duplicate a target")
        if any(target.target.origin != origin for target in registration.targets):
            raise ValueError("authorized target belongs to a different learning origin")
        if any(target.committed_tick != preview.basis.cutoff_tick for target in registration.targets):
            raise ValueError("target commit time differs from its original source opportunity")

    def _outcome(self, outcome: RightingClaimOutcomeV1, cycle: int, tick: int) -> None:
        """Reject malformed outcomes before duplicate handling or state changes."""
        if not isinstance(outcome, RightingClaimOutcomeV1):
            raise TypeError("learning input must be a canonical 1G-A outcome")
        self._registration(outcome.registration)
        _index(outcome.number, "outcome_number", minimum=1)
        _index(outcome.evaluated_tick, "evaluated_tick")
        _index(outcome.command_intervals, "command_intervals")
        if outcome.status not in _TERMINAL_KINDS or outcome.command_intervals > 8:
            raise ValueError("unrecognized or unbounded outcome")
        if outcome.registration.preview.pnm.created_cycle >= cycle or outcome.evaluated_tick > tick:
            raise ValueError("a newly issued action has no outcome at this F boundary")
        if outcome.number > self._last_outcome and outcome.evaluated_tick != tick:
            raise ValueError("new teaching must arrive at its original focal evaluation, not diagnostic replay")
        if not isinstance(outcome.relations, tuple) or len(outcome.relations) > 5 or any(
            not isinstance(row, tuple) or len(row) != 2 or row[0] not in _RELATIONS or row[1] not in _RESULT_KINDS
            for row in outcome.relations
        ):
            raise ValueError("malformed teaching relation results")
        if len({name for name, _ in outcome.relations}) != len(outcome.relations):
            raise ValueError("one relation cannot supply duplicate teaching evidence")
        for name, result in outcome.relations:
            group = (outcome.registration.unevaluable_relations if result == "unevaluable_authorization"
                     else outcome.registration.compatible_relations)
            if name not in group:
                raise ValueError("teaching changed the pre-handoff authorization meaning")
        values = {value for _, value in outcome.relations}
        if (outcome.status == "matched" and values != {"matched"}
                or outcome.status == "partly_matched" and values != {"matched", "unevaluable_authorization"}
                or outcome.status == "mismatch" and "mismatch" not in values
                or outcome.status == "unknown" and ("unknown" not in values or "mismatch" in values)):
            raise ValueError("teaching status contradicts its relation evidence")
        evidence = outcome.evidence
        if evidence is not None:
            evidence.validate_available(stream=self.stream, at_tick=outcome.evaluated_tick)
            basis = outcome.registration.preview.basis.feedback
            if basis is None or evidence.sample_id <= basis.sample_id:
                raise ValueError("teaching endpoint is not a distinct acquisition")
            if evidence.event_tick != outcome.registration.due_tick or evidence.available_tick > outcome.registration.expires_at_tick:
                raise ValueError("teaching does not answer the original physical endpoint")
        if outcome.status in {"matched", "partly_matched", "mismatch"} and (
            evidence is None or outcome.command_intervals == 0 or not outcome.registration.targets
        ):
            raise ValueError("executed teaching requires observed evidence and actual command opportunity")
        participant = self._pending.get(outcome.registration.preview.pnm.pnm_id)
        if participant is not None and participant.registration is not outcome.registration:
            raise ValueError("copied or changed registration cannot replace original participation")

    def reconcile(
        self, *, cycle_id: int, cutoff_tick: int, registration: RightingClaimRegistrationV1 | None = None,
        context: RightingContextV1 | None = None, outcomes: tuple[RightingClaimOutcomeV1, ...] = (),
        requests: tuple[RightingMismatchRequestV1, ...] = (), interpretation: RightingInterpretationV1 | None = None,
        comparison_enabled: bool = True, attention_enabled: bool = True,
    ) -> LearningPhaseFReportV1:
        """Reconcile one F opportunity without learning or another demanding operation.

        Source-A evidence remains eligible while B is focal or A is unavailable;
        its original context/source, not the current WNM, identifies the recipient.
        Required interpretation can arrive now or later, but never renews the
        four-cycle lifetime. With the Attention route disabled, mismatches are
        conservatively held un-interpreted; this hook cannot bypass that ablation.
        Matching known forecast evidence needs no demanding interpretation.

        Returns immutable admission/expiry/no-update records. New E participation
        is registered only after earlier teaching is handled, so it cannot consume
        its own future effect. Fault/overflow validation leaves prior state intact.
        """
        cycle, tick = _index(cycle_id, "cycle_id", minimum=1), _index(cutoff_tick, "cutoff_tick")
        if self._closed or cycle <= self._last_cycle or tick <= self._last_tick:
            raise RuntimeError("learning owner is closed or this F opportunity was already reconciled")
        if not isinstance(comparison_enabled, bool) or not isinstance(attention_enabled, bool):
            raise TypeError("learning route settings must be Boolean")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8 or not isinstance(requests, tuple) or len(requests) > 8:
            raise ValueError("F accepts at most eight outcomes and eight source requests")
        for outcome in outcomes:
            self._outcome(outcome, cycle, tick)
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("teaching batch must preserve unique publisher order")
        for request in requests:
            if not isinstance(request, RightingMismatchRequestV1) or not any(request.outcome is row for row in outcomes):
                raise ValueError("interpretation dependency must be an actual request for this outcome batch")
            if (request.outcome.status != "mismatch" or not request.relations
                    or any((name, "mismatch") not in request.outcome.relations for name in request.relations)):
                raise ValueError("interpretation dependency needs an actual corresponding discrepancy")
            if request.admitted_tick != tick or request.context.context_id != request.outcome.registration.preview.context_id:
                raise ValueError("interpretation request changed its time or context")
        if len({request.outcome.number for request in requests}) != len(requests):
            raise ValueError("a teaching outcome cannot acquire two interpretation dependencies")
        if registration is not None:
            self._registration(registration)
            if registration.preview.pnm.pnm_id in self._pending:
                raise ValueError("new participation cannot reuse a still eligible claim identifier")
            if not isinstance(context, RightingContextV1) or context.context_id != registration.preview.context_id:
                raise ValueError("participation requires its original task context")
            if registration.preview.pnm.created_cycle != cycle or registration.preview.basis.cutoff_tick != tick:
                raise ValueError("participation must be recorded in its actual application opportunity")
        elif context is not None:
            raise ValueError("a context without a performed application is not participation")
        if interpretation is not None:
            if not isinstance(interpretation, RightingInterpretationV1) or interpretation.cycle_id != cycle or interpretation.cutoff_tick != tick:
                raise ValueError("F can only receive the interpretation actually performed this opportunity")
            request = interpretation.request
            if not isinstance(request, RightingMismatchRequestV1) or not request.admitted_tick <= tick < request.expires_at_tick:
                raise ValueError("focal interpretation used an invalid or expired request")
            if interpretation.current_evidence is not None:
                interpretation.current_evidence.validate_available(stream=self.stream, at_tick=tick)
            original = next((item for item in requests if item is request), None)
            if original is None:
                original = next((item.request for item in self._pending.values() if item.request is request), None)
            if original is None:
                # An interpretation can legitimately outlive this hook's short
                # eligibility. Validate its evidence without granting new rights.
                self._registration(request.outcome.registration)
                existing = self._pending.get(request.outcome.registration.preview.pnm.pnm_id)
                if existing is not None:
                    raise ValueError("copied request cannot substitute for this participant's actual dependency")
            elif request.outcome.registration.preview.basis.source_map_ref != self.source_ref:
                raise ValueError("interpretation belongs to another source")
            if interpretation.status not in {"corrected_historical_discrepancy", "still_relevant_support_discrepancy",
                                              "unresolved_current_relevance"}:
                raise ValueError("unrecognized focal interpretation")
        pending = dict(self._pending)
        events: list[RightingTeachingDispositionV1] = []
        inspected = len(pending)

        def report(pnm_id: str, status: str, outcome: RightingClaimOutcomeV1 | None = None, *,
                   accepted: tuple[tuple[str, str], ...] = (), result: RightingInterpretationV1 | None = None) -> None:
            """Collect a bounded disposition; this is not an effective learned change."""
            events.append(RightingTeachingDispositionV1(pnm_id, status, cycle, tick, outcome, accepted, result))

        for pnm_id, expiring in tuple(pending.items()):
            if cycle >= expiring.expires_before_cycle:
                report(pnm_id, "eligibility_expired", expiring.outcome)
                del pending[pnm_id]
        last_outcome = self._last_outcome
        for outcome in outcomes:
            pnm_id = outcome.registration.preview.pnm.pnm_id
            if outcome.number <= last_outcome:
                report(pnm_id, "duplicate_ignored", outcome)
                continue
            last_outcome = outcome.number
            participant = pending.get(pnm_id)
            if participant is None:
                status = "rejected_expired_eligibility" if cycle >= outcome.registration.preview.pnm.created_cycle + 4 else (
                    "rejected_unregistered_operation")
                report(pnm_id, status, outcome)
                continue
            dependency = next((item for item in requests if item.outcome is outcome), None)
            needs_interpretation = dependency is not None or (not attention_enabled and outcome.status == "mismatch")
            participant = replace(participant, outcome=outcome, request=dependency, awaiting_interpretation=needs_interpretation)
            pending[pnm_id] = participant
            if needs_interpretation:
                report(pnm_id, "pending_interpretation", outcome)

        for pnm_id, participant in tuple(pending.items()):
            participant_outcome = participant.outcome
            if participant_outcome is None:
                continue
            result: RightingInterpretationV1 | None = None
            if participant.awaiting_interpretation:
                if interpretation is None or interpretation.request is not participant.request:
                    continue
                if interpretation.request.outcome is not participant_outcome:
                    raise ValueError("interpretation did not answer the participant's original outcome")
                if interpretation.status == "unresolved_current_relevance":
                    report(pnm_id, "pending_unresolved_interpretation", participant_outcome, result=interpretation)
                    continue
                result = interpretation
            known = tuple(
                (name, value)
                for name, value in participant_outcome.relations
                if value in {"matched", "mismatch"}
            )
            if participant_outcome.status in {"matched", "partly_matched", "mismatch"} and known:
                report(pnm_id, "accepted_no_update", participant_outcome, accepted=known, result=result)
            else:
                report(pnm_id, f"rejected_{participant_outcome.status}", participant_outcome, result=result)
            del pending[pnm_id]

        new_participation: RightingParticipationV1 | None = None
        if registration is not None:
            pnm_id = registration.preview.pnm.pnm_id
            if not registration.targets:
                report(pnm_id, "not_applied")
            elif not registration.compatible_relations:
                report(pnm_id, "unevaluable_authorization")
            elif not comparison_enabled:
                report(pnm_id, "comparison_disabled_no_teaching")
            else:
                if context is None:  # validated above; retain explicit narrowing
                    raise ValueError("missing original participation context")
                new_participation = RightingParticipationV1(self.recipient_id, registration, context, cycle)
                pending[pnm_id] = new_participation
        if len(pending) > _MAX_PARTICIPANTS:
            raise OverflowError("eight eligible participants; no silent eviction or lifetime extension")
        f_report = LearningPhaseFReportV1(self.recipient_id, cycle, tick, new_participation, tuple(events), tuple(pending.values()),
                                        len(outcomes), inspected)
        self._pending = pending
        self._last_cycle, self._last_tick, self._last_outcome = cycle, tick, last_outcome
        self._history.extend(events)
        return f_report
