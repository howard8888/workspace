#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1G-B: source-owned task discrepancy requests and bounded focal interpretation.

This is a domain-local extension of the POSTURE-SUPPORT owner, not another
Evaluator, task primitive or learning module. C2 admits the actual 1G-A terminal
claim results and performs only fixed significance checks. The source's bid may
carry a separate outcome rank; Attention still chooses. Only after Navigation
establishes that source as the current WNM may allocate() spend the one focal
allocation. A dependent response is reconsidered at a later eligible opportunity,
never in the interpretation call. Neither route grants body/motor permission.

Approved profile righting_outcome_attention_v1 keeps eight pending requests,
eight ticks of nonrenewable request lifetime, one previous endpoint for the
persistence test, one dependent interpretation and 32 diagnostic dispositions.
A request references its original immutable claim, not another world model.
Physics, prediction tolerances, task criteria/budgets and lower protection are
unchanged. These fixed engineering rules are not learned relevance or a claim
that all mammalian interpretation requires a separate cognitive opportunity.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from nca8_executive import AttentionBidV1, WorkingNavMapStateV1
from nca8_maps import DurableNavMapRefV1, NavMapStateV1
from nca8_outcomes import RightingClaimOutcomeV1
from nca8_righting import RightingContextV1, RightingTaskV1, righting_support_adequacy_v1

__version__ = "0.1.0"
__all__ = [
    "RightingMismatchRequestV1", "RightingInterpretationV1", "RightingFocalAllocationV1",
    "RightingOutcomeAttentionV1", "__version__",
]

_RELATIONS = ("tilt", "extension", "loading", "destabilization", "contact")
_RESULT_KINDS = {"matched", "mismatch", "unknown", "unevaluable_authorization"}


def _tick(value: int) -> int:
    """Check a physical index with headroom for the eight-tick request lifetime."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("outcome relevance requires a bounded nonnegative tick")
    return value


@dataclass(frozen=True, slots=True)
class RightingMismatchRequestV1:
    """An expiring source request from one actual executed endpoint discrepancy.

    Admission time does not refresh the original sensed event or extend its
    prediction, task or actuator lease. relations names only compatible observed
    contradictions. context is the unchanged originating activity requirement.
    Instances are issued by the source owner; copied instances have no rights.
    """

    request_id: str
    outcome: RightingClaimOutcomeV1
    context: RightingContextV1
    admitted_tick: int
    significance: str
    relations: tuple[str, ...]

    @property
    def expires_at_tick(self) -> int:
        """Read the exclusive expiry; rereading never renews it."""
        return self.admitted_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Export provenance, not a selected source, task or command."""
        preview = self.outcome.registration.preview
        evidence = self.outcome.evidence
        return {
            "request_id": self.request_id, "pnm_id": preview.pnm.pnm_id, "outcome_number": self.outcome.number,
            "task_id": preview.task_id, "context_id": self.context.context_id,
            "source_map_ref": preview.basis.source_map_ref.as_dict(),
            "physical_event_tick": evidence.event_tick if evidence is not None else None,
            "available_tick": evidence.available_tick if evidence is not None else None,
            "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick,
            "significance": self.significance, "relations": list(self.relations), "outcome_rank": 40,
            "grants_motor_permission": False,
        }


@dataclass(frozen=True, slots=True)
class RightingInterpretationV1:
    """The actual result of one source-linked, demanding focal interpretation.

    The historic mismatch remains unchanged. Current relevance is computed from
    the selected source's eligible measurements and the original requirement;
    it is not a diagnosis of a hidden disturbance, helper or broken actuator.
    An unresolved result blocks only its dependent reconsideration, within the
    original request lifetime. It cannot turn into a delayed automatic action.
    """

    request: RightingMismatchRequestV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    current_evidence: MotorFeedbackV1 | None
    status: str
    relation_relevance: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Keep historical evidence, current relevance and unknown causation separate."""
        return {
            "request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
            "working_id": self.working_id, "current_evidence": self.current_evidence.as_dict() if self.current_evidence else None,
            "status": self.status, "relation_relevance": dict(self.relation_relevance),
            "demanding_allocations": 1, "action_causation": "uncertain", "durable_learning_updates": 0,
        }


@dataclass(frozen=True, slots=True)
class RightingFocalAllocationV1:
    """One scheduling disposition; a result is not a new task application.

    interpretation and dependent_unresolved suppress ordinary primitive
    arbitration for this opportunity. response_reconsideration permits the
    normal selector to recheck current evidence later; it names no primitive.
    ordinary and other_source leave independent processing unchanged.
    """

    kind: str
    interpretation: RightingInterpretationV1 | None = None

    @property
    def permits_primitive_selection(self) -> bool:
        """A demanding interpretation and a new task must never share the slot."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Read the actual allocation and its optional historical dependency."""
        return {
            "kind": self.kind, "permits_primitive_selection": self.permits_primitive_selection,
            "interpretations_this_opportunity": int(self.kind == "interpretation"),
            "interpretation": self.interpretation.as_dict() if self.interpretation is not None else None,
        }


class RightingOutcomeAttentionV1:
    """Own bounded transient relevance for one source and one body generation.

    Nca8BodySensoryModuleV1 constructs this opt-in extension. admit() receives
    only canonical 1G-A results under the frozen source cutoff, not local warning
    labels. contribute_bid() changes only the existing outcome ranking component.
    allocate() requires this cycle's selected WNM. It performs no environment,
    motor, primitive or durable-learning call. Overflow rejects the entire batch
    before changing relevance; a core caller then stops rather than hiding work.

    Outcome numbers are monotonic publisher identities. A duplicate cannot
    restart a request or increment persistence. Gaps break persistence, including
    an intervening E-stage nonapplication that has no C2 comparison result.
    Old/out-of-order endpoint arrivals cannot form a fictitious forward streak.
    Diagnostic history is never consulted to authorize focus or a response.
    """

    def __init__(self, stream: MotorStreamRefV1, source_ref: DurableNavMapRefV1) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(source_ref, DurableNavMapRefV1):
            raise TypeError("source relevance requires typed stream and source identity")
        self.stream = stream
        self.source_ref = source_ref
        self._pending: tuple[RightingMismatchRequestV1, ...] = ()
        self._previous: RightingClaimOutcomeV1 | None = None
        self._last_number = 0
        self._last_admission = -1
        self._last_allocation_cycle = 0
        self._dependency: RightingInterpretationV1 | None = None
        self._history: deque[tuple[str, str, int]] = deque(maxlen=32)
        self._source: NavMapStateV1 | None = None
        self._task: RightingTaskV1 | None = None
        self._context: RightingContextV1 | None = None

    def retained_counts(self) -> dict[str, int]:
        """Measure live storage independently of the external trace's capacity."""
        return {
            "attention_pending_requests": len(self._pending), "attention_previous_endpoint": int(self._previous is not None),
            "attention_dependency": int(self._dependency is not None), "attention_dispositions": len(self._history),
        }

    def pending(self) -> tuple[RightingMismatchRequestV1, ...]:
        """Read original immutable requests; this cannot revive expired authority."""
        return self._pending

    def dispositions(self) -> tuple[tuple[str, str, int], ...]:
        """Read bounded diagnostic outcomes; truncation does not change pending work."""
        return tuple(self._history)

    def _validate_outcome(self, outcome: RightingClaimOutcomeV1, cutoff: int) -> None:
        """Reject invalid provenance before any duplicate or significance decision."""
        if not isinstance(outcome, RightingClaimOutcomeV1):
            raise TypeError("only original 1G-A terminal claim outcomes are accepted")
        if isinstance(outcome.number, bool) or not isinstance(outcome.number, int) or not 0 < outcome.number < 2**63 - 1:
            raise ValueError("outcome publisher number must be a bounded positive integer")
        registration = outcome.registration
        preview, origin = registration.preview, registration.request.origin
        if origin.stream != self.stream or preview.basis.stream != self.stream or preview.basis.source_map_ref != self.source_ref:
            raise ValueError("outcome request has foreign source or generation")
        if preview.task_id != origin.task_id or outcome.evaluated_tick > cutoff:
            raise ValueError("outcome has wrong task or is not yet evaluated")
        _tick(outcome.evaluated_tick)
        if isinstance(outcome.command_intervals, bool) or not isinstance(outcome.command_intervals, int) or not 0 <= outcome.command_intervals <= 8:
            raise ValueError("command exposure must be a bounded actual interval count")
        if not isinstance(outcome.relations, tuple) or len(outcome.relations) > 5:
            raise ValueError("outcome relations must be a bounded immutable tuple")
        if any(not isinstance(row, tuple) or len(row) != 2 or row[0] not in _RELATIONS or row[1] not in _RESULT_KINDS
               for row in outcome.relations):
            raise ValueError("unknown or malformed relation result")
        if len({name for name, _ in outcome.relations}) != len(outcome.relations):
            raise ValueError("a relation can be compared only once per outcome")
        evidence = outcome.evidence
        if evidence is not None:
            evidence.validate_available(stream=self.stream, at_tick=outcome.evaluated_tick)
            if evidence.event_tick != registration.due_tick or evidence.available_tick > registration.expires_at_tick:
                raise ValueError("outcome evidence does not answer the original endpoint")
        for name, status in outcome.relations:
            expected_set = registration.unevaluable_relations if status == "unevaluable_authorization" else registration.compatible_relations
            if name not in expected_set:
                raise ValueError("outcome comparison contradicts its pre-handoff authorization meaning")
        if outcome.status == "mismatch" and (evidence is None or not registration.targets or outcome.command_intervals == 0
                                              or not any(status == "mismatch" for _, status in outcome.relations)):
            raise ValueError("executed mismatch requires actual compatible endpoint evidence and command exposure")

    @staticmethod
    def _relevance(
        feedback: MotorFeedbackV1 | None, context: RightingContextV1, relation: str, *, expected_extension: float | None,
    ) -> str:
        """Check one current activity relation without diagnosing the event's cause."""
        if feedback is None:
            return "unknown"
        tilt, loading, instability = context.criterion
        value: float | bool | None
        if relation == "contact":
            value = feedback.support_contact
            okay = value is True
        elif relation == "tilt":
            value = feedback.body_tilt_degrees
            okay = value is not None and abs(value) <= tilt
        elif relation == "loading":
            value = feedback.useful_loading
            okay = value is not None and value >= loading
        elif relation == "destabilization":
            value = feedback.destabilization
            okay = value is not None and value <= instability
        else:
            value = feedback.support_extension
            okay = value is not None and expected_extension is not None and abs(value - expected_extension) <= 0.02 + 1e-12
        return "unknown" if value is None else "currently_supported" if okay else "still_relevant"

    def _significance(
        self, outcome: RightingClaimOutcomeV1, previous: RightingClaimOutcomeV1 | None,
        *, context: RightingContextV1, current: MotorFeedbackV1 | None,
    ) -> tuple[str, tuple[str, ...]] | None:
        """Small fixed C2 checks only; no focal current-versus-historical interpretation."""
        if outcome.status != "mismatch":
            return None
        preview = outcome.registration.preview
        mismatches = tuple(name for name, status in outcome.relations if status == "mismatch")
        critical: list[str] = []
        # Only an expected-supported condition contradicted by corresponding
        # evidence is immediately consequential. Unexpected improvement is not
        # automatically danger; the later focal result retains that distinction.
        expected = {
            "tilt": preview.predicted_tilt, "loading": preview.predicted_loading,
            "destabilization": preview.predicted_destabilization, "contact": preview.expected_contact,
        }
        limits = dict(zip(("tilt", "loading", "destabilization"), context.criterion))
        for name in mismatches:
            value = expected.get(name)
            if value is None:
                continue
            supported = (value is True) if name == "contact" else (
                value >= limits[name] if name == "loading" else abs(value) <= limits[name]
            )
            observed = self._relevance(outcome.evidence, context, name, expected_extension=preview.predicted_extension)
            if supported and observed == "still_relevant":
                critical.append(name)
        if critical:
            return "consequential_support_contradiction", tuple(critical)
        if previous is None or previous.number + 1 != outcome.number or previous.status != "mismatch":
            return None
        before = previous.registration.preview
        if (before.task_id, before.context_id, before.basis.source_map_ref) != (preview.task_id, preview.context_id, preview.basis.source_map_ref):
            return None
        if previous.registration.due_tick >= outcome.registration.due_tick or before.pnm.created_cycle >= preview.pnm.created_cycle:
            return None
        common = tuple(name for name in mismatches if (name, "mismatch") in previous.relations)
        if common and righting_support_adequacy_v1(current, context) is False:
            return "persistent_executed_discrepancy", common
        return None

    def admit(
        self, outcomes: tuple[RightingClaimOutcomeV1, ...], source: NavMapStateV1,
        task: RightingTaskV1 | None, context: RightingContextV1, *, cutoff_tick: int,
    ) -> tuple[RightingMismatchRequestV1, ...]:
        """Admit a frozen C2 batch and return newly created source requests.

        Eight requests is a hard bound. Validate and calculate into local values
        first; rejection cannot partially consume a batch or erase an old request.
        A context change invalidates its old requests/dependency, never relabels
        them successful. Completion does not erase historical mismatch evidence,
        but a later response can never restart a terminal task.
        """
        cutoff = _tick(cutoff_tick)
        if cutoff <= self._last_admission:
            raise ValueError("one relevance admission is allowed per increasing focal cutoff")
        facet = source.motor_support if isinstance(source, NavMapStateV1) else None
        if facet is None or source.source_map_ref != self.source_ref or facet.stream != self.stream or facet.cutoff_tick != cutoff:
            raise ValueError("relevance requires the owning source at this frozen cutoff")
        if not isinstance(context, RightingContextV1):
            raise TypeError("relevance requires the original typed activity context")
        if task is not None and (not isinstance(task, RightingTaskV1) or task.stream != self.stream
                                 or task.source_map_ref != self.source_ref or task.context != context):
            raise ValueError("current task, source and context disagree")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8:
            raise ValueError("at most eight terminal outcomes may enter one focal admission")
        for outcome in outcomes:
            self._validate_outcome(outcome, cutoff)
            if outcome.number > self._last_number and outcome.evaluated_tick != cutoff:
                raise ValueError("new relevance must enter at its first eligible C2 evaluation, not a later replay")
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("outcome batches must preserve unique publisher order")
        active_task_id = task.task_id if task is not None else None
        pending: list[RightingMismatchRequestV1] = []
        dispositions: list[tuple[str, str, int]] = []
        for request in self._pending:
            if request.context != context or request.outcome.registration.preview.task_id != active_task_id:
                dispositions.append((request.request_id, "context_invalidated", cutoff))
            elif cutoff >= request.expires_at_tick:
                dispositions.append((request.request_id, "expired_uninterpreted", cutoff))
            else:
                pending.append(request)
        dependency = self._dependency
        if dependency is not None and (dependency.request.context != context
                                      or dependency.request.outcome.registration.preview.task_id != active_task_id
                                      or cutoff >= dependency.request.expires_at_tick):
            dispositions.append((dependency.request.request_id, "dependent_response_expired_or_invalidated", cutoff))
            dependency = None
        previous = self._previous if self._context == context else None
        last_number = self._last_number
        created: list[RightingMismatchRequestV1] = []
        current = facet.feedback if facet.current else None
        for outcome in outcomes:
            if outcome.number <= last_number:
                continue
            preview = outcome.registration.preview
            belongs = preview.task_id == active_task_id and preview.context_id == context.context_id
            significance = self._significance(outcome, previous, context=context, current=current) if belongs else None
            if significance is not None:
                request = RightingMismatchRequestV1(
                    f"task_mismatch:g{self.stream.generation}:o{outcome.number}", outcome, context, cutoff, *significance,
                )
                pending.append(request)
                created.append(request)
            previous = outcome if belongs else None
            last_number = outcome.number
        if len(pending) > 8:
            raise OverflowError("eight pending interpretation requests; no silent eviction or additional focal work")
        self._source, self._task, self._context = source, task, context
        self._pending, self._dependency = tuple(pending), dependency
        self._previous, self._last_number, self._last_admission = previous, last_number, cutoff
        self._history.extend(dispositions)
        return tuple(created)

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Add outcome rank 40, never safety/task-need rank or synthetic evidence.

        A supported source may need historical interpretation even without an
        ordinary support-need bid. Such a bid has zero body need. With a body
        bid, every non-outcome priority component and source object stays intact.
        A request does not compel selection against a stronger protected source.
        """
        source = self._source
        if source is None:
            raise RuntimeError("admit the current source before asking for a relevance bid")
        if ordinary is not None and (ordinary.source_map_state is not source or ordinary.cycle_id != source.applied_cycle):
            raise ValueError("outcome rank must attach to the exact owning source bid")
        task = self._task
        if task is not None and (source.applied_cycle - task.started_cycle >= 20 or self._last_admission - task.started_tick >= 80):
            return ordinary
        if not self._pending:
            return ordinary
        cycle = source.applied_cycle
        if ordinary is None:
            ordinary = AttentionBidV1(
                f"support_bid:{cycle}", "source:posture_support", source, "body_sensory", cycle,
                0, 0, 0, 0, 0, 20, (), False, "source:posture_support",
            )
        return replace(ordinary, prediction_or_envelope_failure_rank=max(ordinary.prediction_or_envelope_failure_rank, 40),
                       reasons=(*ordinary.reasons, "task_pnm_outcome_request"))

    def allocate(self, working: WorkingNavMapStateV1 | None, *, cycle_id: int) -> RightingFocalAllocationV1:
        """Spend at most one interpretation slot, or release a later reconsideration.

        This method is called only after Attention and WNM establishment. It
        neither calls nor names a primitive. A request is consumed exactly once.
        Unresolved current relevance retains only its bounded dependency; it
        cannot stop another source, source updating or protected lower execution.
        A later ordinary selector, current task and BodyMap still decide whether
        any permitted response actually exists.
        """
        source = self._source
        if (source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or cycle_id != source.applied_cycle or cycle_id <= self._last_allocation_cycle):
            raise ValueError("allocation needs this source admission and one increasing focal opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("allocation must use the actual current WNM")
        if working is not None and working.primary_source_state.source_map_ref == self.source_ref and working.primary_source_state is not source:
            raise ValueError("interpretation must use this owner's exact eligible source sample")
        self._last_allocation_cycle = cycle_id
        if working is None or working.primary_source_state.source_map_ref != self.source_ref:
            return RightingFocalAllocationV1("other_source")
        task = self._task
        if task is not None and (cycle_id - task.started_cycle >= 20 or self._last_admission - task.started_tick >= 80):
            return RightingFocalAllocationV1("task_budget_exhausted")
        facet = source.motor_support
        if facet is None:  # guarded during admission
            raise RuntimeError("selected source lost its admitted motor facet")
        if self._pending:
            request = self._pending[0]
            feedback = facet.feedback if facet.current else None
            relevance = tuple((name, self._relevance(feedback, request.context, name,
                                                   expected_extension=request.outcome.registration.preview.predicted_extension))
                              for name in request.relations)
            kinds = {value for _, value in relevance}
            status = "unresolved_current_relevance" if "unknown" in kinds else (
                "still_relevant_support_discrepancy" if "still_relevant" in kinds else "corrected_historical_discrepancy"
            )
            interpretation = RightingInterpretationV1(request, cycle_id, facet.cutoff_tick, working.working_id, feedback, status, relevance)
            self._pending = self._pending[1:]
            if self._dependency is not None:
                self._history.append((self._dependency.request.request_id, "superseded_dependent_response", facet.cutoff_tick))
            self._dependency = interpretation
            self._history.append((request.request_id, "interpreted", facet.cutoff_tick))
            return RightingFocalAllocationV1("interpretation", interpretation)
        dependency = self._dependency
        if dependency is None:
            return RightingFocalAllocationV1("ordinary")
        if dependency.cycle_id >= cycle_id:
            raise RuntimeError("a dependent response cannot share its interpretation opportunity")
        if dependency.status == "unresolved_current_relevance":
            return RightingFocalAllocationV1("dependent_unresolved", dependency)
        self._dependency = None
        self._history.append((dependency.request.request_id, "response_reconsidered", facet.cutoff_tick))
        return RightingFocalAllocationV1("response_reconsideration", dependency)
