#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Source-owned seeking discrepancy relevance and one explicit focal interpretation.

P16-2C-E reuses the conservative one-opportunity policy already qualified for
Righting and maternal outcomes. Local original-endpoint comparison remains in
D. Here a fixed significance rule can request consideration of current feeding
content. Only ordinary Attention and Navigation can allocate its interpretation;
no comparator selects an IP, changes the source, or controls a motor.

A request adds outcome rank40 only to an already eligible feeding bid. There is
no new access to missing/contradicted detail. Eight pending requests, one prior
endpoint and one dependent response are bounded separately from diagnostic
history. Requests expire eight physical ticks after admission, and the original
seeking task's 12-focal/48-tick budget includes any interpretation. Historical
resolution is not current success, latch, learned identity or causal credit.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_executive import AttentionBidV1, OutcomeInterpretationCandidateV1, WorkingNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSeedV1
from nca8_seek_nipple import SeekNippleTaskV1
from nca8_seek_outcomes import SeekNippleOutcomeV1, validate_seeking_outcome_v1

__version__ = "0.3.0"
__all__ = ["SeekingMismatchRequestV1", "SeekingInterpretationV1", "SeekingFocalAllocationV1", "SeekingAttentionFrameV1",
           "SeekingOutcomeAttentionV1", "__version__"]


def _tick(value: int) -> int:
    """Validate finite physical identity, rejecting Boolean values and coercion."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("seeking relevance tick must be a bounded nonnegative integer")
    return value


def _separation(outcome: SeekNippleOutcomeV1) -> float | None:
    """Read the original endpoint only; unknown identity cannot supply a location."""
    evidence, preview = outcome.evidence, outcome.claim.preview
    if evidence is None or evidence.observation is None or evidence.mouth_position is None:
        return None
    if dict(outcome.relations).get("separation") not in {"matched", "mismatch"}:
        return None
    detail = next((item for item in evidence.observation.detections if item.region_id == preview.region_id), None)
    if detail is None or detail.position is None:
        return None
    mouth = evidence.mouth_position
    return math.hypot(detail.position.x - mouth.x, detail.position.y - mouth.y)


@dataclass(frozen=True, slots=True)
class SeekingMismatchRequestV1:
    """An original result awaiting consideration, never a remembered motor grant."""

    request_id: str
    outcome: SeekNippleOutcomeV1
    admitted_tick: int
    significance: str
    relations: tuple[str, ...]

    @property
    def expires_at_tick(self) -> int:
        """Keep the original eight-tick relevance lifetime without renewal on reads."""
        return self.admitted_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Detach identity, timing and significance without rewriting the old result."""
        evidence = self.outcome.evidence
        return {"request_id": self.request_id, "pnm_id": self.outcome.claim.preview.pnm.pnm_id,
                "outcome_number": self.outcome.number, "source_ref": self.outcome.claim.preview.basis.source_map_ref.as_dict(),
                "event_tick": evidence.feedback.event_tick if evidence is not None else None,
                "available_tick": evidence.feedback.available_tick if evidence is not None else None,
                "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick,
                "significance": self.significance, "relations": list(self.relations), "outcome_rank": 40,
                "grants_motor_permission": False}


@dataclass(frozen=True, slots=True)
class SeekingInterpretationV1:
    """One focal comparison with current supported relations, not an inferred cause."""

    request: SeekingMismatchRequestV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    current_source: FeedingDetailNavMapStateV1
    status: str
    relation_relevance: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Distinguish original endpoint from current relevance and future response."""
        return {"request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "working_id": self.working_id, "current_source": self.current_source.as_dict(), "status": self.status,
                "relation_relevance": dict(self.relation_relevance), "demanding_allocations": 1,
                "causal_credit": "not_established", "durable_updates": 0}


@dataclass(frozen=True, slots=True)
class SeekingFocalAllocationV1:
    """Use the existing focal slot; an interpretation and new task cannot share it."""

    kind: str
    interpretation: SeekingInterpretationV1 | None = None

    @property
    def permits_primitive_selection(self) -> bool:
        """Unknown dependent work blocks this source only, never another source."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Expose the actual slot use, not a count of all stored historical results."""
        return {"kind": self.kind, "permits_primitive_selection": self.permits_primitive_selection,
                "interpretation_count": int(self.kind == "interpretation"),
                "interpretation": self.interpretation.as_dict() if self.interpretation is not None else None}


@dataclass(frozen=True, slots=True)
class SeekingAttentionFrameV1:
    """Record C2 requests, the ordinary bid and the one D allocation separately."""

    created: tuple[SeekingMismatchRequestV1, ...]
    pending: tuple[SeekingMismatchRequestV1, ...]
    source_bid: AttentionBidV1 | None
    allocation: SeekingFocalAllocationV1
    learning_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Report the relevance route and optional no-learning hook without claiming plasticity."""
        return {"profile": "seeking_outcome_attention_v1", "created": [item.as_dict() for item in self.created],
                "pending": [item.as_dict() for item in self.pending],
                "source_bid": self.source_bid.as_dict() if self.source_bid is not None else None,
                "allocation": self.allocation.as_dict(), "learning_route": "seeking_no_learning_v1" if self.learning_enabled else "unimplemented_no_participation", "durable_updates": 0}


class SeekingOutcomeAttentionV1:
    """Maintain bounded relevance/dependency within one feeding source generation.

    Admit current source/task and newly published outcomes at C2. Contribute to
    its ordinary bid, then allocate only after the one WNM is established. All
    batch validation precedes mutation. Immutable outcomes are never changed;
    diagnostics cannot refresh a request or restore permission. Closing after
    a fault/reset revokes further use, while retaining read-only dispositions.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: FeedingDetailSeedV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, FeedingDetailSeedV1):
            raise TypeError("seeking relevance requires its typed stream and feeding seed")
        if isinstance(diagnostic_capacity, bool) or not isinstance(diagnostic_capacity, int) or not 1 <= diagnostic_capacity <= 32:
            raise ValueError("seeking diagnostic capacity must be an integer in [1,32]")
        self.stream, self.seed = stream, seed
        self._pending: tuple[SeekingMismatchRequestV1, ...] = ()
        self._previous: SeekNippleOutcomeV1 | None = None
        self._dependency: SeekingInterpretationV1 | None = None
        self._source: FeedingDetailNavMapStateV1 | None = None
        self._task: SeekNippleTaskV1 | None = None
        self._last_number = 0
        self._last_admission = -1
        self._last_allocation_cycle = 0
        self._closed = False
        self._history: deque[tuple[str, str, int]] = deque(maxlen=diagnostic_capacity)

    def pending(self) -> tuple[SeekingMismatchRequestV1, ...]:
        """Read pending descriptions without extending their original expiry."""
        return self._pending

    def dispositions(self) -> tuple[tuple[str, str, int], ...]:
        """Read bounded diagnostics; eviction does not affect live dependencies."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure live owner storage independently of trace and terminal histories."""
        return {"seeking_attention_pending_requests": len(self._pending),
                "seeking_attention_previous_endpoint": int(self._previous is not None),
                "seeking_attention_dependency": int(self._dependency is not None),
                "seeking_attention_dispositions": len(self._history)}

    def close(self) -> None:
        """Revoke old-generation processing without undoing any physical effect."""
        self._closed = True
        self._pending, self._previous, self._dependency = (), None, None

    @staticmethod
    def _significance(outcome: SeekNippleOutcomeV1, previous: SeekNippleOutcomeV1 | None) -> tuple[str, tuple[str, ...]] | None:
        """Perform fixed local checks, not rich current-world or causal interpretation."""
        if outcome.status == "identity_contradicted":
            return "feeding_part_identity_contradiction", ("identity",)
        if outcome.status != "mismatch":
            return None
        mismatches = tuple(name for name, status in outcome.relations if status == "mismatch")
        if "detail_anchor" in mismatches and dict(outcome.residuals).get("detail_anchor", 0.0) >= 0.02 - 1e-12:
            return "consequential_detail_anchor_shift", ("detail_anchor",)
        separation = _separation(outcome)
        if ("separation" in mismatches and outcome.claim.preview.predicted_separation <= 0.005 + 1e-12
                and separation is not None and separation > 0.005 + 1e-12):
            return "expected_reach_not_supported", ("separation",)
        if previous is None or previous.number + 1 != outcome.number or previous.status != "mismatch":
            return None
        before, after = previous.claim.preview, outcome.claim.preview
        if ((before.task_id, before.region_id, before.basis.frame_id) != (after.task_id, after.region_id, after.basis.frame_id)
                or previous.claim.due_tick >= outcome.claim.due_tick or before.pnm.created_cycle >= after.pnm.created_cycle):
            return None
        common = tuple(name for name in mismatches if (name, "mismatch") in previous.relations)
        if common and separation is not None and separation > 0.005 + 1e-12:
            return "persistent_executed_seeking_discrepancy", common
        return None

    def admit(
        self, outcomes: tuple[SeekNippleOutcomeV1, ...], source: FeedingDetailNavMapStateV1,
        task: SeekNippleTaskV1 | None, *, cutoff_tick: int,
    ) -> tuple[SeekingMismatchRequestV1, ...]:
        """Validate and admit a whole batch once; expire without replay-based renewal.

        A terminal task can retain a historical question within its original
        budget; no result restarts it. Unscored/unknown outcomes cannot create a
        mismatch request. An unavailable source can retain an old question but
        cannot supply a bid, a current coordinate or interpretation by itself.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_admission:
            raise ValueError("seeking relevance requires an open owner and one increasing cutoff")
        if (not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.cutoff_tick != cutoff or self._source is not None and source.applied_cycle <= self._source.applied_cycle):
            raise ValueError("seeking relevance requires the current frozen feeding source")
        if task is not None and (not isinstance(task, SeekNippleTaskV1) or task.region_id != self.seed.detail_region_id
                                 or task.started_tick > cutoff or task.started_cycle > source.applied_cycle):
            raise ValueError("seeking task and current source disagree")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8:
            raise ValueError("seeking relevance accepts at most eight canonical results per opportunity")
        for result in outcomes:
            validate_seeking_outcome_v1(result, stream=self.stream, cutoff_tick=cutoff)
            if result.claim.preview.basis.seed != self.seed or result.claim.preview.basis.maternal.seed != source.maternal.seed:
                raise ValueError("seeking result has foreign part/parent organization")
            if result.number > self._last_number and result.evaluated_tick != cutoff:
                raise ValueError("a new seeking result must enter at its original C2 publication")
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("seeking results must preserve distinct increasing publisher order")
        task_id = None if task is None else task.task_id
        pending: list[SeekingMismatchRequestV1] = []
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
        previous, number = self._previous, self._last_number
        created: list[SeekingMismatchRequestV1] = []
        for result in outcomes:
            if result.number <= number:
                continue
            belongs = result.claim.preview.task_id == task_id
            significance = self._significance(result, previous) if belongs else None
            if significance is not None:
                request = SeekingMismatchRequestV1(f"seeking_mismatch:g{self.stream.generation}:o{result.number}", result, cutoff, *significance)
                pending.append(request)
                created.append(request)
            previous, number = (result if belongs else None), result.number
        if len(pending) > 8:
            raise OverflowError("eight pending seeking requests; no silent eviction or extra focal work")
        self._source, self._task = source, task
        self._pending, self._dependency = tuple(pending), dependency
        self._previous, self._last_number, self._last_admission = previous, number, cutoff
        self._history.extend(dispositions)
        return tuple(created)

    def _budget_exhausted(self) -> bool:
        """Charge interpretation to the existing task, not a fresh response budget."""
        return self._task is not None and self._source is not None and (
            self._source.applied_cycle - self._task.started_cycle >= 12 or self._last_admission - self._task.started_tick >= 48
        )

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Alter only outcome rank on existing accessible, developmentally eligible content.

        Unlike a general reinspection operation, this bounded initial profile
        cannot recruit missing/contradicted detail. Disabled ordinary feeding
        nomination stays disabled. Current body/support and task-need priorities
        remain independently ranked by the existing Attention owner.
        """
        source = self._source
        if self._closed or source is None:
            raise RuntimeError("admit the live seeking source before requesting relevance")
        if ordinary is not None and (ordinary.source_map_state is not source or ordinary.cycle_id != source.applied_cycle):
            raise ValueError("seeking relevance must attach to the exact current feeding bid")
        if ordinary is None or not self._pending or not source.focal_accessible or self._budget_exhausted():
            return ordinary
        return replace(ordinary, prediction_or_envelope_failure_rank=max(40, ordinary.prediction_or_envelope_failure_rank),
                       reasons=(*ordinary.reasons, "seeking_pnm_outcome_request"))

    @staticmethod
    def _relevance(request: SeekingMismatchRequestV1, source: FeedingDetailNavMapStateV1) -> tuple[tuple[str, str], ...]:
        """Interpret on the chosen source using current evidence, never predicted touch."""
        evidence = request.outcome.evidence
        event = source.maternal.visual.event_tick
        current = source.maternal.visual.evidence_current and evidence is not None and event is not None and event >= evidence.feedback.event_tick
        results: list[tuple[str, str]] = []
        for relation in request.relations:
            result = "unknown"
            if current and relation == "identity":
                if source.association_status == "compatible":
                    result = "currently_supported"
                elif source.association_status in {"detail_category_contradicted", "part_geometry_contradicted"}:
                    result = "still_relevant"
            elif current and source.frame_id == request.outcome.claim.preview.basis.frame_id:
                if relation == "detail_anchor" and source.detail_position is not None:
                    original = request.outcome.claim.preview.scene_target
                    distance = math.hypot(source.detail_position.x - original.x, source.detail_position.y - original.y)
                    result = "currently_supported" if distance <= 0.005 + 1e-12 else "still_relevant"
                elif relation in {"mouth_position", "separation"} and source.mouth_detail_distance is not None:
                    result = "currently_supported" if source.mouth_detail_distance <= 0.005 + 1e-12 else "still_relevant"
            results.append((relation, result))
        return tuple(results)

    def interpretation_candidate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int,
    ) -> OutcomeInterpretationCandidateV1 | None:
        """Offer the oldest eligible question without interpreting or consuming it.

        Used only by J's pre-consumption Navigation arbitration. Existing seeking
        allocation remains unchanged when J is absent. A losing request, dependency,
        diagnostic history and last-allocation marker are all untouched by this read.
        """
        source = self._source
        if (self._closed or source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or source.applied_cycle != cycle_id or cycle_id <= self._last_allocation_cycle):
            raise ValueError("seeking candidacy requires one new admitted opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("seeking candidacy requires this cycle's actual WNM")
        if working is None or working.primary_source_state.source_map_ref != source.source_map_ref:
            return None
        if working.primary_source_state is not source or not source.focal_accessible:
            raise ValueError("seeking candidacy requires the exact selected feeding source")
        if self._budget_exhausted() or not self._pending:
            return None
        request = self._pending[0]
        return OutcomeInterpretationCandidateV1(request.request_id, source, request.admitted_tick, request.expires_at_tick)

    def allocate(self, working: WorkingNavMapStateV1 | None, *, cycle_id: int) -> SeekingFocalAllocationV1:
        """Consume at most one question in the existing selected-source opportunity.

        Interpretation never shares a slot with a new primitive. A resolved
        dependency only permits later reconsideration through ordinary current
        applicability and BodyMap; an unknown one waits or expires. No old motor
        command is replayed. Foreign-source work and lower protection continue.
        """
        source = self._source
        if (self._closed or source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or source.applied_cycle != cycle_id or cycle_id <= self._last_allocation_cycle):
            raise ValueError("seeking allocation requires one new admitted focal opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("seeking allocation requires this cycle's actual WNM")
        same_source = working is not None and working.primary_source_state.source_map_ref == source.source_map_ref
        if same_source and (working is None or working.primary_source_state is not source or not source.focal_accessible):
            raise ValueError("seeking interpretation requires the exact accessible source selected as WNM")
        self._last_allocation_cycle = cycle_id
        if not same_source or working is None:
            return SeekingFocalAllocationV1("other_source")
        if self._budget_exhausted():
            return SeekingFocalAllocationV1("task_budget_exhausted")
        if self._pending:
            request = self._pending[0]
            relevance = self._relevance(request, source)
            statuses = {status for _, status in relevance}
            status = ("unresolved_current_relevance" if "unknown" in statuses else
                      "still_relevant" if "still_relevant" in statuses else "historical_resolved")
            interpretation = SeekingInterpretationV1(request, cycle_id, source.cutoff_tick, working.working_id, source, status, relevance)
            self._pending = self._pending[1:]
            if self._dependency is not None:
                self._history.append((self._dependency.request.request_id, "superseded_dependent_response", source.cutoff_tick))
            self._dependency = interpretation
            self._history.append((request.request_id, "interpreted", source.cutoff_tick))
            return SeekingFocalAllocationV1("interpretation", interpretation)
        dependency = self._dependency
        if dependency is None:
            return SeekingFocalAllocationV1("ordinary")
        if dependency.status == "unresolved_current_relevance":
            return SeekingFocalAllocationV1("dependent_unresolved", dependency)
        self._dependency = None
        self._history.append((dependency.request.request_id, "response_reconsidered", source.cutoff_tick))
        return SeekingFocalAllocationV1("response_reconsideration", dependency)
