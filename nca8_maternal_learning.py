#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2B-E: source-owned maternal participation and no-learning reconciliation.

The maternal association owner constructs this optional extension before sensing.
It names the original Follow-Mom source, task, application, forecast and authorized
translation, not whichever source is currently WNM. Eight temporary participants
may await corresponding evidence. Eligibility expires before creation cycle + 4,
independently of the physical prediction window, source accessibility, Attention
requests, motor leases and diagnostic retention. These are the inherited 1G-C
engineering bounds, not a general biological learning rule.

The real Phase-F callback offers canonical earlier C2 outcomes and any interpretation
actually performed in the existing focal opportunity. F performs no interpretation,
new action, source selection or durable update. A requested interpretation must
precede acceptance; with the Attention route disabled, discrepant outcomes are
conservatively held until eligibility expires rather than interpreted for free.
Compatible known forecast evidence can be accepted without assigning causal credit.
Identity learning, calibration, preferences, SEC and LP acquisition remain deferred.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_body_targets import VisualApproachRequestV1
from nca8_followmom import FollowMomTaskV1
from nca8_maternal import MOM_REF, MaternalNavMapStateV1, MaternalSeedV1
from nca8_maternal_attention import MaternalInterpretationV1, MaternalMismatchRequestV1
from nca8_maternal_outcomes import MaternalClaimV1, MaternalOutcomeV1
from nca8_prediction import MaternalApproachPreviewV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, CommittedBodyTargetV1
from nca8_visual import VisualObservationV1

__version__ = "0.1.0"
__all__ = [
    "MaternalParticipationV1", "MaternalTeachingDispositionV1", "MaternalLearningPhaseFReportV1",
    "MaternalLearningHookV1", "__version__",
]
_RELATIONS = ("self_position", "maternal_anchor", "separation")
_RESULTS = {"matched", "mismatch", "unknown", "unevaluable_authorization"}
_OUTCOMES = {
    "matched", "partly_matched", "mismatch", "identity_contradicted", "unknown", "observed_without_command",
    "not_applied", "cancelled", "interrupted", "expired_unresolved", "unresolved_stopped", "comparison_disabled",
}


def _index(value: int, name: str, *, minimum: int = 0) -> int:
    """Reject Boolean, noninteger and overflowing indices before any owner mutation."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value < 2**63 - 17:
        raise ValueError(f"{name} must be a bounded integer >= {minimum}")
    return value


@dataclass(frozen=True, slots=True)
class MaternalParticipationV1:
    """Original source/task participation with its own four-opportunity lifetime.

    The canonical claim retains proposed versus authorized meaning. The task is
    the immutable original application context, not a live task or a permission
    to resume it. outcome/request reference actual publishers, never trace rows.
    """

    recipient_id: str
    claim: MaternalClaimV1
    task: FollowMomTaskV1
    created_cycle: int
    outcome: MaternalOutcomeV1 | None = None
    request: MaternalMismatchRequestV1 | None = None
    awaiting_interpretation: bool = False

    @property
    def expires_before_cycle(self) -> int:
        """Return exclusive eligibility expiry; no reread or later outcome renews it."""
        return self.created_cycle + 4

    @property
    def pnm_id(self) -> str:
        """Identify this original forecast, not the currently displayed PNM."""
        return self.claim.preview.pnm.pnm_id

    def as_dict(self) -> dict[str, object]:
        """Export detached provenance without granting learning or movement rights."""
        basis = self.claim.preview.basis
        return {
            "recipient_id": self.recipient_id, "source_map_ref": basis.source_map_ref.as_dict(),
            "origin": self.claim.request.origin.as_dict(), "pnm_id": self.pnm_id, "task": self.task.as_dict(),
            "source_sample_id": basis.sample_id, "source_event_tick": basis.event_tick,
            "source_cutoff_tick": basis.cutoff_tick, "seed": basis.seed.as_dict(),
            "created_cycle": self.created_cycle, "expires_before_cycle": self.expires_before_cycle,
            "compatible_relations": list(self.claim.compatible_relations),
            "unevaluable_relations": list(self.claim.unevaluable_relations),
            "authorized_target_ids": [item.target.target_id for item in self.claim.targets],
            "outcome_number": self.outcome.number if self.outcome is not None else None,
            "interpretation_request_id": self.request.request_id if self.request is not None else None,
            "awaiting_interpretation": self.awaiting_interpretation,
            "maturity": "eligibility_only", "grants_motor_authority": False,
        }


@dataclass(frozen=True, slots=True)
class MaternalTeachingDispositionV1:
    """One actual no-update admission, rejection, waiting or expiry decision.

    accepted_no_update concerns only known compatible original forecast relations.
    It is not correct action attribution, learned maternal identity, task success
    or a durable L12 mechanism. Unknown relations are not converted to failures.
    """

    pnm_id: str
    status: str
    cycle_id: int
    cutoff_tick: int
    outcome: MaternalOutcomeV1 | None = None
    accepted_relations: tuple[tuple[str, str], ...] = ()
    interpretation: MaternalInterpretationV1 | None = None

    def as_dict(self) -> dict[str, object]:
        """Keep physical event, availability, interpretation and F time distinguishable."""
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
class MaternalLearningPhaseFReportV1:
    """One executed F reconciliation for this source, not a scan of all learners.

    New participation has no observed future outcome. Other dispositions concern
    previously available evidence or explicit nonapplication. No durable learning
    exists here; effective, deferred and total durable-update counts remain zero.
    """

    recipient_id: str
    cycle_id: int
    cutoff_tick: int
    new_participation: MaternalParticipationV1 | None
    dispositions: tuple[MaternalTeachingDispositionV1, ...]
    pending: tuple[MaternalParticipationV1, ...]
    offered_outcomes: int
    inspected_participants: int

    def as_dict(self) -> dict[str, object]:
        """Describe actual eligibility-only work, never restorable execution state."""
        return {
            "profile": "maternal_no_learning_v1", "recipient_id": self.recipient_id,
            "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick, "maturity": "eligibility_only",
            "new_participation": self.new_participation.as_dict() if self.new_participation is not None else None,
            "dispositions": [item.as_dict() for item in self.dispositions], "pending": [item.as_dict() for item in self.pending],
            "offered_outcomes": self.offered_outcomes, "inspected_participants": self.inspected_participants,
            "due_owners_visited": int(bool(self.new_participation or self.dispositions or self.inspected_participants)),
            "current_source_refresh_is_learning": False, "new_action_outcome_available": False,
            "already_effective_durable_changes": 0, "due_durable_changes": 0, "durable_learning_updates": 0,
            "ledger_rows_executed": 0, "restores_motor_permission": False,
        }


class MaternalLearningHookV1:
    """Own bounded maternal eligibility independently of focal or Ready access.

    The source configures this once. reconcile() is called from the real F callback
    with original C2 results, current E registration and actual D interpretation.
    Complete input validation and a temporary pending dictionary precede mutation.
    A malformed/foreign/copied dependency raises; valid unknown, duplicate,
    unregistered or expired evidence receives an explicit no-update disposition.
    No path consults diagnostic history, changes a map, selects a task, invokes a
    physical provider, performs interpretation or uses RNG. close() permanently
    revokes this generation's eligibility, without changing any historical claim.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: MaternalSeedV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, MaternalSeedV1):
            raise TypeError("maternal hook requires its typed original stream and association seed")
        _index(diagnostic_capacity, "diagnostic_capacity", minimum=1)
        if diagnostic_capacity > 32:
            raise ValueError("maternal learning diagnostic capacity cannot exceed 32")
        self.stream, self.seed = stream, seed
        self.source_ref = MOM_REF
        self.recipient_id = f"maternal_association:{MOM_REF.map_id}:consequence"
        self._pending: dict[str, MaternalParticipationV1] = {}
        self._history: deque[MaternalTeachingDispositionV1] = deque(maxlen=diagnostic_capacity)
        self._last_cycle, self._last_tick, self._last_outcome = 0, -1, 0
        self._closed = False

    def retained_counts(self) -> dict[str, int]:
        """Measure actual temporary storage; diagnostics never extend participation."""
        return {"maternal_learning_participants": len(self._pending), "maternal_learning_dispositions": len(self._history)}

    def pending(self) -> tuple[MaternalParticipationV1, ...]:
        """Read original immutable participants without restoring source accessibility."""
        return tuple(self._pending.values())

    def history(self) -> tuple[MaternalTeachingDispositionV1, ...]:
        """Read bounded diagnostics; the functional path never reads this history."""
        return tuple(self._history)

    def close(self) -> None:
        """Revoke eligibility on reset/stop; the closed owner cannot be reused."""
        self._pending.clear()
        self._closed = True

    def _claim(self, claim: MaternalClaimV1) -> None:
        """Validate original source, selected operation and pre-handoff authorization."""
        if (not isinstance(claim, MaternalClaimV1) or not isinstance(claim.preview, MaternalApproachPreviewV1)
                or not isinstance(claim.request, VisualApproachRequestV1)):
            raise TypeError("maternal participation requires a typed original claim, preview and request")
        preview, request = claim.preview, claim.request
        basis, origin = preview.basis, request.origin
        if (basis.stream != self.stream or origin.stream != self.stream or basis.seed != self.seed
                or basis.source_map_ref != MOM_REF or request.source_map_ref != MOM_REF
                or preview.region_id != self.seed.region_id or request.region_id != preview.region_id
                or origin.task_id != preview.task_id or origin.application_id != preview.pnm.application_id
                or preview.pnm.primitive_id != "ip:follow_mom" or request.origin_status != "selected_follow_mom"
                or preview.pnm.created_cycle != basis.applied_cycle):
            raise ValueError("maternal participation changed its source, seed, generation or original application")
        for names in (claim.compatible_relations, claim.unevaluable_relations):
            if not isinstance(names, tuple) or any(name not in _RELATIONS for name in names) or len(set(names)) != len(names):
                raise ValueError("maternal claim has malformed authorization relations")
        if (set(claim.compatible_relations) & set(claim.unevaluable_relations)
                or set(claim.compatible_relations) | set(claim.unevaluable_relations) != set(_RELATIONS)):
            raise ValueError("each original maternal relation needs one authorization disposition")
        if not isinstance(claim.targets, tuple) or len(claim.targets) > 1:
            raise ValueError("maternal participation permits at most one original translation")
        for target in claim.targets:
            if (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyTranslationTargetV1)
                    or target.target.origin != origin or target.committed_tick != basis.cutoff_tick
                    or target.target.basis.planar is None or target.target.basis.planar.frame_id != basis.frame_id):
                raise ValueError("maternal participation lost original translation authority or frame")

    def _outcome(self, outcome: MaternalOutcomeV1, cycle: int, tick: int) -> None:
        """Check evidence integrity, not a new prediction comparison or interpretation."""
        if not isinstance(outcome, MaternalOutcomeV1):
            raise TypeError("maternal teaching requires a canonical maternal outcome")
        self._claim(outcome.claim)
        _index(outcome.number, "outcome_number", minimum=1)
        _index(outcome.evaluated_tick, "evaluated_tick")
        _index(outcome.command_intervals, "command_intervals")
        claim = outcome.claim
        if outcome.status not in _OUTCOMES or outcome.command_intervals > claim.preview.horizon_ticks:
            raise ValueError("unrecognized or unbounded maternal outcome")
        if claim.preview.pnm.created_cycle >= cycle or outcome.evaluated_tick > tick:
            raise ValueError("a just-issued maternal action has no outcome at this F boundary")
        if outcome.number > self._last_outcome and outcome.evaluated_tick != tick:
            raise ValueError("new maternal teaching must arrive at its original C2 evaluation")
        if not isinstance(outcome.relations, tuple) or len(outcome.relations) > 3:
            raise ValueError("maternal teaching requires at most three immutable relation results")
        for relation_row in outcome.relations:
            if (not isinstance(relation_row, tuple) or len(relation_row) != 2
                    or relation_row[0] not in _RELATIONS or relation_row[1] not in _RESULTS):
                raise ValueError("malformed maternal teaching relation")
            permitted = claim.unevaluable_relations if relation_row[1] == "unevaluable_authorization" else claim.compatible_relations
            if relation_row[0] not in permitted:
                raise ValueError("maternal teaching rewrote the original authorized meaning")
        if len({name for name, _ in outcome.relations}) != len(outcome.relations):
            raise ValueError("maternal relation cannot be taught twice in one outcome")
        if not isinstance(outcome.residuals, tuple) or len(outcome.residuals) > 3:
            raise ValueError("maternal residuals must be a bounded immutable tuple")
        for residual_row in outcome.residuals:
            if (not isinstance(residual_row, tuple) or len(residual_row) != 2 or residual_row[0] not in _RELATIONS
                    or isinstance(residual_row[1], bool) or not isinstance(residual_row[1], (float, int))
                    or not math.isfinite(residual_row[1]) or residual_row[1] < 0):
                raise ValueError("maternal residual must be finite, nonnegative and relation-specific")
        residuals = dict(outcome.residuals)
        if len(residuals) != len(outcome.residuals):
            raise ValueError("duplicate maternal residual")
        if outcome.status in {"matched", "partly_matched", "mismatch", "unknown", "identity_contradicted", "observed_without_command"}:
            if {name for name, _ in outcome.relations} != set(_RELATIONS):
                raise ValueError("a compared maternal endpoint must retain all three original relation dispositions")
        values = {value for _, value in outcome.relations}
        if (outcome.status == "matched" and values != {"matched"}
                or outcome.status == "partly_matched" and values != {"matched", "unevaluable_authorization"}
                or outcome.status == "mismatch" and "mismatch" not in values
                or outcome.status == "unknown" and ("unknown" not in values or "mismatch" in values)):
            raise ValueError("maternal teaching status contradicts relation evidence")
        evidence = outcome.evidence
        if evidence is not None:
            if not isinstance(evidence, VisualObservationV1):
                raise TypeError("maternal teaching requires canonical visual evidence")
            evidence.validate_available(stream=self.stream, at_tick=outcome.evaluated_tick)
            if (evidence.event_tick != claim.due_tick or evidence.available_tick > claim.expires_at_tick
                    or claim.preview.basis.sample_id is None or evidence.sample_id <= claim.preview.basis.sample_id):
                raise ValueError("maternal teaching does not answer the original later endpoint")
        for name, value in outcome.relations:
            if value in {"matched", "mismatch"}:
                residual = residuals.get(name)
                if (residual is None or (residual <= 0.02 + 1e-12) != (value == "matched")
                        or evidence is None or evidence.frame_id != claim.preview.basis.frame_id):
                    raise ValueError("maternal scored relation lacks matching frame/residual evidence")
        if outcome.status in {"matched", "partly_matched", "mismatch", "identity_contradicted"} and (
            evidence is None or not claim.targets or outcome.command_intervals == 0
        ):
            raise ValueError("executed maternal teaching requires permission, command opportunity and endpoint")
        if outcome.status == "identity_contradicted":
            detection = None if evidence is None else next((item for item in evidence.detections if item.region_id == self.seed.region_id), None)
            if detection is None or detection.descriptor is None or detection.descriptor == self.seed.descriptor:
                raise ValueError("maternal identity contradiction requires observed contradictory recognition")
        participant = self._pending.get(claim.preview.pnm.pnm_id)
        if participant is not None and participant.claim is not claim:
            raise ValueError("copied or changed maternal claim cannot replace original participation")
        if participant is not None and participant.outcome is not None and participant.outcome is not outcome:
            raise ValueError("a second outcome cannot replace a maternal participant's original evidence")

    def _interpretation(
        self, result: MaternalInterpretationV1, requests: tuple[MaternalMismatchRequestV1, ...], cycle: int, tick: int,
    ) -> None:
        """Require the original live dependency and an actual current focal result.

        Structural consistency is checked without recomputing relevance. A result
        can arrive after this hook's eligibility expired; it then grants no new
        rights. A copied request cannot replace an existing participant's request.
        """
        if not isinstance(result, MaternalInterpretationV1) or result.cycle_id != cycle or result.cutoff_tick != tick:
            raise ValueError("maternal F only receives interpretation actually performed this opportunity")
        _index(result.cycle_id, "interpretation_cycle", minimum=1)
        _index(result.cutoff_tick, "interpretation_cutoff")
        dependency, source = result.request, result.current_source
        if not isinstance(dependency, MaternalMismatchRequestV1) or not dependency.admitted_tick <= tick < dependency.expires_at_tick:
            raise ValueError("maternal interpretation used an invalid or expired request")
        _index(dependency.admitted_tick, "interpretation_admitted_tick")
        self._claim(dependency.outcome.claim)
        if (not isinstance(source, MaternalNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.applied_cycle != cycle or source.cutoff_tick != tick or not source.focal_accessible):
            raise ValueError("maternal interpretation lacks this opportunity's selected source")
        original = next((item for item in requests if item is dependency), None)
        if original is None:
            original = next((item.request for item in self._pending.values() if item.request is dependency), None)
        if original is None and dependency.outcome.claim.preview.pnm.pnm_id in self._pending:
            raise ValueError("copied request cannot release a maternal participant's original dependency")
        if (not isinstance(result.relation_relevance, tuple) or len(result.relation_relevance) != len(dependency.relations)
                or any(not isinstance(row, tuple) or len(row) != 2 or row[1] not in {"unknown", "currently_supported", "still_relevant"}
                       for row in result.relation_relevance)
                or tuple(name for name, _ in result.relation_relevance) != dependency.relations):
            raise ValueError("maternal interpretation changed its requested relations")
        values = {value for _, value in result.relation_relevance}
        expected = "unresolved_current_relevance" if "unknown" in values else "still_relevant" if "still_relevant" in values else "historical_resolved"
        if not values or result.status != expected:
            raise ValueError("maternal interpretation status contradicts its reported relevance")

    def reconcile(
        self, *, cycle_id: int, cutoff_tick: int, registration: MaternalClaimV1 | None = None,
        task: FollowMomTaskV1 | None = None, outcomes: tuple[MaternalOutcomeV1, ...] = (),
        requests: tuple[MaternalMismatchRequestV1, ...] = (), interpretation: MaternalInterpretationV1 | None = None,
        comparison_enabled: bool = True, attention_enabled: bool = True,
    ) -> MaternalLearningPhaseFReportV1:
        """Reconcile one F opportunity with independent expiry and zero durable change.

        Validate the whole bounded batch before changing owner state. Expire old
        participants, admit earlier canonical outcomes once, consume resolved known
        evidence, then register this opportunity's E contribution without its future
        effect. Requests wait for actual D interpretation; unresolved results remain
        pending only until original eligibility expires. Disabled Attention never
        buys a free interpretation here. Matching/routine evidence needs no extra
        focal work. Unknown, nonapplied, interrupted and externally observed-only
        outcomes cannot become executed training or motor permission.
        """
        cycle, tick = _index(cycle_id, "cycle_id", minimum=1), _index(cutoff_tick, "cutoff_tick")
        if self._closed or cycle <= self._last_cycle or tick <= self._last_tick:
            raise RuntimeError("maternal hook is closed or F has already been reconciled")
        if not isinstance(comparison_enabled, bool) or not isinstance(attention_enabled, bool):
            raise TypeError("maternal learning route settings must be Boolean")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8 or not isinstance(requests, tuple) or len(requests) > 8:
            raise ValueError("maternal F accepts at most eight outcomes and eight actual requests")
        for outcome in outcomes:
            self._outcome(outcome, cycle, tick)
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("maternal teaching batch must preserve unique increasing publisher order")
        if len({outcome.claim.preview.pnm.pnm_id for outcome in outcomes}) != len(outcomes):
            raise ValueError("one maternal claim cannot receive two publisher outcomes in one batch")
        for request in requests:
            if not isinstance(request, MaternalMismatchRequestV1) or not any(request.outcome is item for item in outcomes):
                raise ValueError("maternal dependency requires this batch's actual canonical outcome")
            _index(request.admitted_tick, "request_admitted_tick")
            if (request.admitted_tick != tick or request.outcome.number <= self._last_outcome
                    or not isinstance(request.relations, tuple) or not 1 <= len(request.relations) <= 3
                    or len(set(request.relations)) != len(request.relations)):
                raise ValueError("maternal dependency changed its original time or relation set")
            if request.outcome.status == "identity_contradicted":
                if request.relations != ("identity",):
                    raise ValueError("contradicted identity has a distinct interpretation dependency")
            elif (request.outcome.status != "mismatch"
                  or any((name, "mismatch") not in request.outcome.relations for name in request.relations)):
                raise ValueError("maternal dependency requires a corresponding executed discrepancy")
        if len({request.outcome.number for request in requests}) != len(requests):
            raise ValueError("one maternal outcome cannot acquire two interpretation dependencies")
        if not attention_enabled and (requests or interpretation is not None):
            raise ValueError("disabled maternal Attention cannot supply focal interpretation")
        if registration is not None:
            self._claim(registration)
            preview = registration.preview
            if preview.pnm.pnm_id in self._pending:
                raise ValueError("new maternal participation cannot reuse a live claim identifier")
            if (not isinstance(task, FollowMomTaskV1) or task.task_id != preview.task_id or task.region_id != preview.region_id
                    or task.status != "active" or task.started_cycle > cycle or task.started_tick > tick):
                raise ValueError("maternal participation requires its original active task context")
            if preview.pnm.created_cycle != cycle or preview.basis.cutoff_tick != tick:
                raise ValueError("maternal participation belongs to its actual application opportunity")
        elif task is not None:
            raise ValueError("a task without a performed maternal application is not new participation")
        if interpretation is not None:
            self._interpretation(interpretation, requests, cycle, tick)
        pending = dict(self._pending)
        dispositions: list[MaternalTeachingDispositionV1] = []
        inspected = len(pending)

        def report(pnm_id: str, status: str, outcome: MaternalOutcomeV1 | None = None, *,
                   accepted: tuple[tuple[str, str], ...] = (), result: MaternalInterpretationV1 | None = None) -> None:
            """Collect no-update evidence locally; this call performs no lasting update."""
            dispositions.append(MaternalTeachingDispositionV1(pnm_id, status, cycle, tick, outcome, accepted, result))

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
        for pnm_id, participant in tuple(pending.items()):
            participant_outcome = participant.outcome
            if participant_outcome is None:
                continue
            result: MaternalInterpretationV1 | None = None
            if participant.awaiting_interpretation:
                if interpretation is None or interpretation.request is not participant.request:
                    continue
                if interpretation.request.outcome is not participant_outcome:
                    raise ValueError("maternal interpretation did not answer original participant evidence")
                if interpretation.status == "unresolved_current_relevance":
                    report(pnm_id, "pending_unresolved_interpretation", participant_outcome, result=interpretation)
                    continue
                result = interpretation
            known = tuple((name, value) for name, value in participant_outcome.relations if value in {"matched", "mismatch"})
            if comparison_enabled and participant_outcome.status in {"matched", "partly_matched", "mismatch"} and known:
                report(pnm_id, "accepted_no_update", participant_outcome, accepted=known, result=result)
            else:
                report(pnm_id, f"rejected_{participant_outcome.status}", participant_outcome, result=result)
            del pending[pnm_id]
        new_participation: MaternalParticipationV1 | None = None
        if registration is not None:
            pnm_id = registration.preview.pnm.pnm_id
            if not registration.targets:
                report(pnm_id, "not_applied")
            elif not registration.compatible_relations:
                report(pnm_id, "unevaluable_authorization")
            elif not comparison_enabled:
                report(pnm_id, "comparison_disabled_no_teaching")
            else:
                if task is None:  # Already validated; retain explicit static narrowing.
                    raise ValueError("missing original maternal task context")
                new_participation = MaternalParticipationV1(self.recipient_id, registration, task, cycle)
                pending[pnm_id] = new_participation
        if len(pending) > 8:
            raise OverflowError("eight maternal participants; no silent eviction or eligibility extension")
        result_report = MaternalLearningPhaseFReportV1(
            self.recipient_id, cycle, tick, new_participation, tuple(dispositions), tuple(pending.values()), len(outcomes), inspected,
        )
        self._pending = pending
        self._last_cycle, self._last_tick, self._last_outcome = cycle, tick, last_outcome
        self._history.extend(dispositions)
        return result_report
