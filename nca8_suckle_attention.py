#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-J: Suckle discrepancy to feeding relevance and focal interpretation.

This source-owned extension describes questions, not IPs. Original I outcomes
remain immutable. Ordinary Attention selects the feeding source; Navigation
chooses one question BEFORE its consumption and reserves its existing focal
allocation. Interpretation evaluates present relevance only, not cause, remedy,
IP applicability, latch completion or bodily permission. A later ordinary
Attention/Navigation decision is required for any new IP application.

The fixed first profile requests rank 40 for an executed missing expected seal,
a contradicted feeding-part identity, a closure error of at least 0.05, or an
anchor/mouth displacement of at least 0.02 metres. Smaller deviations stay local.
These significance thresholds do NOT change I's correspondence tolerances.
Eight pending requests expire eight physical ticks after original admission.
One dependent interpretation and 32 diagnostic dispositions have separate bounds.
The originating Suckle task's 12-opportunity/48-tick budget is never renewed.
No milk, learning, physical model, generic scheduler or CompareOutcome IP is added.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_executive import AttentionBidV1, NavigationDecisionV1, OutcomeInterpretationCandidateV1, WorkingNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSeedV1
from nca8_suckle import SuckleTaskV1
from nca8_suckle_outcomes import SuckleOutcomeV1, validate_suckle_outcome_v1

__version__ = "0.1.1"
__all__ = ["SuckleMismatchRequestV1", "SuckleInterpretationV1", "SuckleFocalAllocationV1", "SuckleAttentionFrameV1",
           "SuckleOutcomeAttentionV1", "__version__"]


def _tick(value: int) -> int:
    """Reject coerced and overflowing physical identity before any state changes."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("Suckle relevance tick must be a bounded nonnegative integer")
    return value


@dataclass(frozen=True, slots=True)
class SuckleMismatchRequestV1:
    """An original question with immutable expiry, not another Suckle application."""

    request_id: str
    outcome: SuckleOutcomeV1
    admitted_tick: int
    significance: str
    relations: tuple[str, ...]

    @property
    def expires_at_tick(self) -> int:
        """Retain eight original ticks even when this question loses focal allocation."""
        return self.admitted_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Expose historical linkage without exporting any restorable motor right."""
        evidence = self.outcome.evidence
        return {"request_id": self.request_id, "pnm_id": self.outcome.claim.preview.pnm.pnm_id,
                "outcome_number": self.outcome.number, "source_ref": self.outcome.claim.preview.basis.source_map_ref.as_dict(),
                "event_tick": evidence.feedback.event_tick if evidence is not None else None,
                "available_tick": evidence.feedback.available_tick if evidence is not None else None,
                "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick,
                "significance": self.significance, "relations": list(self.relations), "outcome_rank": 40,
                "grants_motor_permission": False, "selects_originating_ip": False}


@dataclass(frozen=True, slots=True)
class SuckleInterpretationV1:
    """Present relevance on the selected source; historical outcomes are not repaired."""

    request: SuckleMismatchRequestV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    current_source: FeedingDetailNavMapStateV1
    status: str
    relation_relevance: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Report one demanding interpretation, without a causal or motor conclusion."""
        return {"request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "working_id": self.working_id, "current_source": self.current_source.as_dict(), "status": self.status,
                "relation_relevance": dict(self.relation_relevance), "demanding_allocations": 1,
                "causal_credit": "not_established", "selects_remedy": False, "grants_motor_permission": False, "durable_updates": 0}


@dataclass(frozen=True, slots=True)
class SuckleFocalAllocationV1:
    """One domain's disposition inside Navigation's existing allocation, not another slot."""

    kind: str
    interpretation: SuckleInterpretationV1 | None = None

    @property
    def permits_primitive_selection(self) -> bool:
        """Report this route's constraint, not independent permission to apply an IP."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Keep deferred questions distinct from performed interpretations and holds."""
        return {"kind": self.kind, "permits_primitive_selection": self.permits_primitive_selection,
                "interpretation_count": int(self.kind == "interpretation"),
                "interpretation": self.interpretation.as_dict() if self.interpretation is not None else None}


@dataclass(frozen=True, slots=True)
class SuckleAttentionFrameV1:
    """Read-only cycle evidence, never a queue consumed by cognition or Phase F."""

    created: tuple[SuckleMismatchRequestV1, ...]
    pending: tuple[SuckleMismatchRequestV1, ...]
    source_bid: AttentionBidV1 | None
    allocation: SuckleFocalAllocationV1
    learning_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Separate request/bid/allocation from optional eligibility and absent durable learning."""
        return {"profile": "suckle_outcome_attention_v1", "created": [item.as_dict() for item in self.created],
                "pending": [item.as_dict() for item in self.pending],
                "source_bid": self.source_bid.as_dict() if self.source_bid is not None else None,
                "allocation": self.allocation.as_dict(), "learning_route": "suckle_no_learning_v1" if self.learning_enabled else "unimplemented_no_participation", "durable_updates": 0}


class SuckleOutcomeAttentionV1:
    """Own finite relevance/dependency state for one feeding-source generation.

    Admission performs only integrity/significance checks on newly published I
    evidence. Candidacy is read-only. Consumption requires a prior nonprimitive
    Navigation decision on the same WNM and question. No method applies an IP,
    writes a sensory source or owns a motor target. Closing is sticky; resetting
    constructs a new owner rather than reviving historical permissions.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: FeedingDetailSeedV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, FeedingDetailSeedV1):
            raise TypeError("Suckle relevance requires a typed stream and feeding seed")
        if isinstance(diagnostic_capacity, bool) or not isinstance(diagnostic_capacity, int) or not 1 <= diagnostic_capacity <= 32:
            raise ValueError("Suckle diagnostic capacity must be an integer in [1,32]")
        self.stream, self.seed = stream, seed
        self._pending: tuple[SuckleMismatchRequestV1, ...] = ()
        self._dependency: SuckleInterpretationV1 | None = None
        self._source: FeedingDetailNavMapStateV1 | None = None
        self._task: SuckleTaskV1 | None = None
        self._last_number = 0
        self._last_admission = -1
        self._last_allocation_cycle = 0
        self._closed = False
        self._history: deque[tuple[str, str, int]] = deque(maxlen=diagnostic_capacity)

    def pending(self) -> tuple[SuckleMismatchRequestV1, ...]:
        """Read live questions without interpreting them or refreshing their expiry."""
        return self._pending

    def dispositions(self) -> tuple[tuple[str, str, int], ...]:
        """Read bounded diagnostics; eviction never changes live cognition."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual bounded storage, separately from exported observer records."""
        return {"suckle_attention_pending_requests": len(self._pending), "suckle_attention_dependency": int(self._dependency is not None),
                "suckle_attention_dispositions": len(self._history)}

    def close(self) -> None:
        """Revoke pending/dependent use after stop/reset without rewriting outcomes."""
        self._pending, self._dependency = (), None
        self._closed = True

    @staticmethod
    def _significance(outcome: SuckleOutcomeV1) -> tuple[str, tuple[str, ...]] | None:
        """Recognize a bounded problem, not its cause or a response operation."""
        if outcome.status == "identity_contradicted":
            return "feeding_part_identity_contradiction", ("identity",)
        if outcome.status != "mismatch":
            return None
        mismatches = tuple(name for name, status in outcome.relations if status == "mismatch")
        if "seal" in mismatches:
            return "expected_seal_not_supported", ("seal",)
        residuals = dict(outcome.residuals)
        significant = tuple(name for name in mismatches if residuals.get(name, 0.0) >=
                            (0.05 if name == "closure" else 0.02) - 1e-12)
        return ("consequential_suckle_relation_discrepancy", significant) if significant else None

    def admit(
        self, outcomes: tuple[SuckleOutcomeV1, ...], source: FeedingDetailNavMapStateV1,
        task: SuckleTaskV1 | None, *, cutoff_tick: int,
    ) -> tuple[SuckleMismatchRequestV1, ...]:
        """Validate an entire publication batch, then admit/expire once at C2.

        Missing, nonexecuted and unscored outcomes remain distinct and create no
        executed-mismatch request. A terminal originating task may retain a bounded
        historical question; it is never restarted. Foreign task results cannot
        nominate the present task. Replay of an already read publisher number does
        not create another question or change the original lifetime.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_admission:
            raise ValueError("Suckle relevance requires an open owner and one increasing cutoff")
        if (not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.cutoff_tick != cutoff or self._source is not None and source.applied_cycle <= self._source.applied_cycle):
            raise ValueError("Suckle relevance requires the current frozen feeding source")
        if task is not None and (not isinstance(task, SuckleTaskV1) or task.region_id != self.seed.detail_region_id
                                 or task.started_tick > cutoff or task.started_cycle > source.applied_cycle):
            raise ValueError("Suckle task and current source disagree")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8:
            raise ValueError("Suckle relevance accepts at most eight original results per opportunity")
        for result in outcomes:
            validate_suckle_outcome_v1(result, stream=self.stream, cutoff_tick=cutoff)
            if result.claim.preview.basis.seed != self.seed or result.claim.preview.basis.maternal.seed != source.maternal.seed:
                raise ValueError("Suckle result has foreign part/parent organization")
            if result.number > self._last_number and result.evaluated_tick != cutoff:
                raise ValueError("a new Suckle result must enter at its original publication")
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("Suckle results must preserve distinct increasing publisher order")
        if len({item.claim.preview.pnm.pnm_id for item in outcomes}) != len(outcomes):
            raise ValueError("one original Suckle claim cannot supply two new outcomes")
        task_id = None if task is None else task.task_id
        pending: list[SuckleMismatchRequestV1] = []
        dispositions: list[tuple[str, str, int]] = []
        for request in self._pending:
            if request.outcome.claim.preview.task_id != task_id:
                dispositions.append((request.request_id, "task_invalidated", cutoff))
            elif cutoff >= request.expires_at_tick:
                dispositions.append((request.request_id, "expired_uninterpreted", cutoff))
            else:
                pending.append(request)
        dependency = self._dependency
        if dependency is not None and (dependency.request.outcome.claim.preview.task_id != task_id
                                      or cutoff >= dependency.request.expires_at_tick):
            dispositions.append((dependency.request.request_id, "dependent_response_expired_or_invalidated", cutoff))
            dependency = None
        number = self._last_number
        created: list[SuckleMismatchRequestV1] = []
        for result in outcomes:
            if result.number <= number:
                continue
            significance = self._significance(result) if result.claim.preview.task_id == task_id else None
            if significance is not None:
                request = SuckleMismatchRequestV1(
                    f"suckle_mismatch:g{self.stream.generation}:o{result.number}", result, cutoff, *significance,
                )
                pending.append(request)
                created.append(request)
            number = result.number
        if len(pending) > 8:
            raise OverflowError("eight pending Suckle questions; no silent eviction or extra focal work")
        self._source, self._task = source, task
        self._pending, self._dependency = tuple(pending), dependency
        self._last_number, self._last_admission = number, cutoff
        self._history.extend(dispositions)
        return tuple(created)

    def _budget_exhausted(self) -> bool:
        """Charge interpretation to the existing task's budget, never a renewed IP."""
        return self._task is not None and self._source is not None and (
            self._source.applied_cycle - self._task.started_cycle >= 12 or self._last_admission - self._task.started_tick >= 48
        )

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Change only outcome relevance on an already accessible ordinary source bid.

        Two feeding outcome routes use max rank, not summed importance. Neither
        acquires missing detail or changes protected safety/current-task inputs.
        This initial profile does not provide general uncertain-source recruitment.
        """
        source = self._source
        if self._closed or source is None:
            raise RuntimeError("admit the current Suckle source before contributing relevance")
        if ordinary is not None and (ordinary.source_map_state is not source or ordinary.cycle_id != source.applied_cycle):
            raise ValueError("Suckle relevance must attach to the exact current feeding bid")
        if ordinary is None or not self._pending or not source.focal_accessible or self._budget_exhausted():
            return ordinary
        return replace(ordinary, prediction_or_envelope_failure_rank=max(40, ordinary.prediction_or_envelope_failure_rank),
                       reasons=(*ordinary.reasons, "suckle_pnm_outcome_request"))

    def _validate_working(self, working: WorkingNavMapStateV1 | None, cycle_id: int) -> bool:
        """Validate the admitted basis without mutating or consuming a question."""
        source = self._source
        if (self._closed or source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or source.applied_cycle != cycle_id or cycle_id <= self._last_allocation_cycle):
            raise ValueError("Suckle focal work requires one new admitted opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("Suckle focal work requires this cycle's actual WNM")
        same_source = working is not None and working.primary_source_state.source_map_ref == source.source_map_ref
        if same_source and (working is None or working.primary_source_state is not source or not source.focal_accessible):
            raise ValueError("Suckle interpretation requires the exact accessible source selected as WNM")
        return same_source

    def interpretation_candidate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int,
    ) -> OutcomeInterpretationCandidateV1 | None:
        """Offer one oldest head without interpretation, queue mutation or authority."""
        same_source = self._validate_working(working, cycle_id)
        if not same_source or self._source is None or self._budget_exhausted() or not self._pending:
            return None
        request = self._pending[0]
        return OutcomeInterpretationCandidateV1(request.request_id, self._source, request.admitted_tick, request.expires_at_tick)

    @staticmethod
    def _relevance(request: SuckleMismatchRequestV1, source: FeedingDetailNavMapStateV1) -> tuple[tuple[str, str], ...]:
        """Interpret only present supported relations; do not infer cause or a remedy."""
        preview, evidence = request.outcome.claim.preview, request.outcome.evidence
        event = source.maternal.visual.event_tick
        current = (source.maternal.visual.evidence_current and evidence is not None
                   and event is not None and event >= evidence.feedback.event_tick)
        body = source.oral_feedback
        oral_current = current and source.oral_evidence_current and body is not None and source.frame_id == preview.basis.frame_id
        results: list[tuple[str, str]] = []
        for relation in request.relations:
            relevance = "unknown"
            if current and relation == "identity" and source.association_status == "compatible":
                relevance = "currently_supported"
            elif (current and relation == "detail_anchor" and source.frame_id == preview.basis.frame_id
                  and source.detail_position is not None):
                distance = math.hypot(source.detail_position.x - preview.scene_target.x, source.detail_position.y - preview.scene_target.y)
                relevance = "currently_supported" if distance <= 0.005 + 1e-12 else "still_relevant"
            elif oral_current:
                if relation == "seal":
                    if source.seal_correspondence_status == "compatible":
                        relevance = "currently_supported"
                    elif source.seal_correspondence_status == "no_seal":
                        relevance = "still_relevant"
                elif relation == "closure" and body is not None and body.oral_seal is not None and body.oral_seal.closure is not None:
                    relevance = ("currently_supported" if abs(body.oral_seal.closure - preview.predicted_closure) <= 0.025 + 1e-12
                                 else "still_relevant")
                elif relation == "mouth_position" and source.mouth_position is not None and preview.basis.mouth_position is not None:
                    mouth, original = source.mouth_position, preview.basis.mouth_position
                    distance = math.hypot(mouth.x - original.x, mouth.y - original.y)
                    relevance = "currently_supported" if distance <= 0.005 + 1e-12 else "still_relevant"
            results.append((relation, relevance))
        return tuple(results)

    def allocate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int, grant: NavigationDecisionV1 | None = None,
    ) -> SuckleFocalAllocationV1:
        """Consume a question only after Navigation has reserved this focal opportunity.

        Pending-question consumption requires an explicit matching nonprimitive
        decision. A dependency can only withhold or permit LATER ordinary selection;
        it never chooses/restarts an IP. Calls concerning another source do not
        consume feeding work. No question is interpreted merely because it exists.
        """
        same_source = self._validate_working(working, cycle_id)
        if not same_source or working is None:
            self._last_allocation_cycle = cycle_id
            return SuckleFocalAllocationV1("other_source")
        if self._budget_exhausted():
            self._last_allocation_cycle = cycle_id
            return SuckleFocalAllocationV1("task_budget_exhausted")
        if self._pending:
            request = self._pending[0]
            if (not isinstance(grant, NavigationDecisionV1) or grant.wnm is not working or grant.cycle_id != cycle_id
                    or grant.application is not None or grant.reason != f"outcome_interpretation:{request.request_id}"):
                raise ValueError("Suckle consumption requires Navigation's prior grant for this exact question")
            source = self._source
            if source is None:  # guarded by _validate_working; retained for explicit type narrowing
                raise RuntimeError("selected Suckle source was lost")
            relevance = self._relevance(request, source)
            statuses = {status for _, status in relevance}
            status = ("unresolved_current_relevance" if "unknown" in statuses else
                      "still_relevant" if "still_relevant" in statuses else "historical_resolved")
            interpretation = SuckleInterpretationV1(request, cycle_id, source.cutoff_tick, working.working_id, source, status, relevance)
            self._pending = self._pending[1:]
            if self._dependency is not None:
                self._history.append((self._dependency.request.request_id, "superseded_dependent_response", source.cutoff_tick))
            self._dependency = interpretation
            self._history.append((request.request_id, "interpreted", source.cutoff_tick))
            self._last_allocation_cycle = cycle_id
            return SuckleFocalAllocationV1("interpretation", interpretation)
        self._last_allocation_cycle = cycle_id
        dependency = self._dependency
        if dependency is None:
            return SuckleFocalAllocationV1("ordinary")
        if dependency.status == "unresolved_current_relevance":
            return SuckleFocalAllocationV1("dependent_unresolved", dependency)
        self._dependency = None
        self._history.append((dependency.request.request_id, "response_reconsidered", self._last_admission))
        return SuckleFocalAllocationV1("response_reconsideration", dependency)
