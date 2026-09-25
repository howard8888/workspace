#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""L-E: original extraction discrepancy to source relevance and one interpretation.

A question is not an IP, and this owner cannot select its own focal work. It
augments an existing feeding bid; after ordinary Attention establishes WNM,
Navigation grants one of all eligible same-source questions before consumption.
Interpretation concerns present relevance only, never cause, a remedy, another
extraction batch, motor permission, or learning. Original L-D evidence is retained
unchanged, including interruption, uncertain milk coverage and unpredicted yield.

The fixed initial profile admits measured loss of touch/seal, incompatible part
organization, or at least 0.02 metres of corresponding anchor/mouth displacement.
It does not promote uncertainty, dry supply or generic interruption into mismatch.
Each original question lives eight ticks. The default admits one original;
sustained mode permits at most eight with one offered extraction question head.
Dependencies and the independent eight-entry diagnostic ring do not extend any
task, motor or learning lifetime.
"""
from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace
import math

from cca8_motor_contracts import MotorStreamRefV1
from nca8_executive import AttentionBidV1, NavigationDecisionV1, OutcomeInterpretationCandidateV1, WorkingNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSeedV1
from nca8_suckle import SuckleExtractionApplicationV1
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeV1, validate_suckle_extraction_outcome_v1
from nca8_suckle_outcomes import SuckleEndpointV1

__version__ = "0.2.0"
__all__ = ["ExtractionQuestionEvidenceV1", "ExtractionMismatchRequestV1", "ExtractionInterpretationV1",
           "ExtractionFocalAllocationV1", "ExtractionAttentionFrameV1", "SuckleExtractionAttentionV1", "__version__"]


def _tick(value: int) -> int:
    """Reject Boolean/coerced time and leave room for the fixed question lifetime."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("extraction relevance needs bounded nonnegative physical time")
    return value


@dataclass(frozen=True, slots=True)
class ExtractionQuestionEvidenceV1:
    """One original acquisition supporting a reason; no independent new observation."""

    relation: str
    reason: str
    endpoint: SuckleEndpointV1
    displacement_metres: float | None = None

    def as_dict(self) -> dict[str, object]:
        """Expose the actual witness instead of inventing a residual from a status."""
        sample = self.endpoint.feedback
        return {"relation": self.relation, "reason": self.reason, "sample_id": sample.sample_id,
                "event_tick": sample.event_tick, "available_tick": sample.available_tick,
                "displacement_metres": self.displacement_metres}


@dataclass(frozen=True, slots=True)
class ExtractionMismatchRequestV1:
    """One original question, not another application or a restorable motor grant."""

    request_id: str
    outcome: SuckleExtractionOutcomeV1
    admitted_tick: int
    evidence: tuple[ExtractionQuestionEvidenceV1, ...]

    @property
    def expires_at_tick(self) -> int:
        """Losing, rereading and deferred interpretation never renew the eight ticks."""
        return self.admitted_tick + 8

    @property
    def relations(self) -> tuple[str, ...]:
        """Return only relations with an actual qualifying historical witness."""
        return tuple(item.relation for item in self.evidence)

    def as_dict(self) -> dict[str, object]:
        """Describe historical links and finite relevance without response authority."""
        application = self.outcome.claim.application
        return {"request_id": self.request_id, "application_id": application.application_id,
                "pnm_id": application.projection.pnm.pnm_id, "task_id": application.task.task_id,
                "source_ref": application.projection.basis.source_map_ref.as_dict(),
                "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick,
                "evidence": [item.as_dict() for item in self.evidence], "outcome_rank": 40,
                "grants_motor_permission": False, "selects_originating_ip": False}


@dataclass(frozen=True, slots=True)
class ExtractionInterpretationV1:
    """Navigation-granted present relevance; it cannot repair the original outcome."""

    request: ExtractionMismatchRequestV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    current_source: FeedingDetailNavMapStateV1
    status: str
    relation_relevance: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Keep current interpretation separate from original discrepancy and milk."""
        return {"request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
                "working_id": self.working_id, "current_source": self.current_source.as_dict(), "status": self.status,
                "relation_relevance": dict(self.relation_relevance), "demanding_allocations": 1,
                "causal_credit": "not_established", "selects_remedy": False, "grants_motor_permission": False,
                "durable_updates": 0}


@dataclass(frozen=True, slots=True)
class ExtractionFocalAllocationV1:
    """This domain's result inside Navigation's allocation, not a second scheduler."""

    kind: str
    interpretation: ExtractionInterpretationV1 | None = None

    @property
    def permits_primitive_selection(self) -> bool:
        """Return a constraint on ordinary selection, not permission to execute an IP."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Distinguish a performed interpretation from a deferred request or hold."""
        return {"kind": self.kind, "permits_primitive_selection": self.permits_primitive_selection,
                "interpretation_count": int(self.kind == "interpretation"),
                "interpretation": self.interpretation.as_dict() if self.interpretation is not None else None}


@dataclass(frozen=True, slots=True)
class ExtractionAttentionFrameV1:
    """Read-only cycle report; neither cognition nor learning consumes this export."""

    created: tuple[ExtractionMismatchRequestV1, ...]
    pending: tuple[ExtractionMismatchRequestV1, ...]
    source_bid: AttentionBidV1 | None
    allocation: ExtractionFocalAllocationV1

    def as_dict(self) -> dict[str, object]:
        """Report live source influence without adding a teaching or action route."""
        return {"profile": "suckle_extraction_attention_v1", "created": [item.as_dict() for item in self.created],
                "pending": [item.as_dict() for item in self.pending],
                "source_bid": self.source_bid.as_dict() if self.source_bid is not None else None,
                "allocation": self.allocation.as_dict(), "learning_route": "unimplemented_for_extraction", "durable_updates": 0}


class SuckleExtractionAttentionV1:
    """One generation's bounded historical question attached to the feeding source.

    Admit only the actual publication and original extraction application, never a
    latch-task substitute or diagnostic-history read. All validation precedes an
    atomic admission. Candidacy is read-only; consumption needs Navigation's prior
    matching nonprimitive decision. Close is sticky; reset constructs a new owner.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: FeedingDetailSeedV1, *, diagnostic_capacity: int = 8, sequential: bool = False) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, FeedingDetailSeedV1):
            raise TypeError("extraction relevance requires a typed stream and source seed")
        if isinstance(diagnostic_capacity, bool) or not isinstance(diagnostic_capacity, int) or not 1 <= diagnostic_capacity <= 8:
            raise ValueError("extraction relevance diagnostics require capacity in [1,8]")
        if not isinstance(sequential, bool):
            raise TypeError("sequential extraction relevance must be Boolean")
        self.sequential = sequential
        self._applications: dict[str, SuckleExtractionApplicationV1] = {}
        self._outcomes: dict[str, SuckleExtractionOutcomeV1] = {}
        self._dependencies: tuple[ExtractionInterpretationV1, ...] = ()
        self.stream, self.seed = stream, seed
        self._pending: tuple[ExtractionMismatchRequestV1, ...] = ()
        self._dependency: ExtractionInterpretationV1 | None = None
        self._seen: SuckleExtractionOutcomeV1 | None = None
        self._source: FeedingDetailNavMapStateV1 | None = None
        self._application: SuckleExtractionApplicationV1 | None = None
        self._last_admission, self._last_allocation_cycle = -1, 0
        self._history: deque[tuple[str, str, int]] = deque(maxlen=diagnostic_capacity)
        self._closed = False

    def pending(self) -> tuple[ExtractionMismatchRequestV1, ...]:
        """Read without reinterpreting, refreshing expiry or creating another sample."""
        return self._pending

    def dispositions(self) -> tuple[tuple[str, str, int], ...]:
        """Read diagnostics independently of question and dependency lifetime."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Expose bounded original associations separately from disposable diagnostics."""
        counts = {"extraction_attention_pending_requests": len(self._pending),
                "extraction_attention_dependency": len(self._dependencies),
                "extraction_attention_seen_outcomes": len(self._outcomes),
                "extraction_attention_dispositions": len(self._history)}
        if self.sequential:
            counts["extraction_attention_original_applications"] = len(self._applications)
        return counts

    def close(self) -> None:
        """Revoke question/dependency use without editing outcome history or any IP."""
        self._pending, self._dependencies, self._dependency = (), (), None
        self._closed = True

    @staticmethod
    def _significance(outcome: SuckleExtractionOutcomeV1) -> tuple[ExtractionQuestionEvidenceV1, ...]:
        """Recognize consequential measured relations, not uncertainty, causes or milk.

        Geometric seal disagreement cannot bypass the 0.02-metre significance
        threshold when neither touch nor seal sensing actually reports loss.
        Retain the first qualifying acquisition per relation, at most three refs.
        """
        if (not outcome.comparison_enabled or not outcome.installed or not outcome.command_ticks
                or outcome.status == "execution_unknown_after_fault"):
            return ()
        mismatches = {name for name, status in outcome.relations if status == "mismatch"}
        preview = outcome.claim.application.projection
        found: dict[str, ExtractionQuestionEvidenceV1] = {}
        for endpoint in outcome.samples:
            body, observation = endpoint.feedback, endpoint.observation
            if "sealed_contact" in mismatches and "sealed_contact" not in found:
                reason = ("measured_touch_loss" if body.oral is not None and body.oral.contact is False else
                          "measured_seal_loss" if body.oral_seal is not None and body.oral_seal.sealed is False else None)
                if reason is not None:
                    found["sealed_contact"] = ExtractionQuestionEvidenceV1("sealed_contact", reason, endpoint)
            if body.planar is None or body.planar.frame_id != preview.basis.frame_id:
                continue
            original, mouth = preview.basis.mouth_position, endpoint.mouth_position
            if "mouth_position" in mismatches and "mouth_position" not in found and original is not None and mouth is not None:
                distance = math.hypot(mouth.x - original.x, mouth.y - original.y)
                if distance >= 0.02 - 1e-12:
                    found["mouth_position"] = ExtractionQuestionEvidenceV1("mouth_position", "mouth_displaced", endpoint, distance)
            if "detail_anchor" not in mismatches or "detail_anchor" in found or observation is None:
                continue
            detail = next((item for item in observation.detections if item.region_id == preview.region_id), None)
            parent = next((item for item in observation.detections if item.region_id == preview.basis.seed.parent_region_id), None)
            if detail is None or detail.descriptor is None:
                continue
            incompatible = detail.descriptor != "feeding" or (parent is not None and parent.descriptor is not None
                                                              and parent.descriptor != preview.basis.maternal.seed.descriptor)
            if detail.position is not None and parent is not None and parent.position is not None and parent.descriptor is not None:
                incompatible = incompatible or math.hypot(detail.position.x - parent.position.x, detail.position.y - parent.position.y) > preview.basis.seed.maximum_parent_distance + 1e-12
            if incompatible:
                found["detail_anchor"] = ExtractionQuestionEvidenceV1("detail_anchor", "part_context_contradicted", endpoint)
            elif detail.position is not None:
                distance = math.hypot(detail.position.x - preview.scene_target.x, detail.position.y - preview.scene_target.y)
                if distance >= 0.02 - 1e-12:
                    found["detail_anchor"] = ExtractionQuestionEvidenceV1("detail_anchor", "detail_displaced", endpoint, distance)
        return tuple(found[name] for name in ("mouth_position", "detail_anchor", "sealed_contact") if name in found)

    def admit(
        self, outcomes: tuple[SuckleExtractionOutcomeV1, ...], source: FeedingDetailNavMapStateV1,
        application: SuckleExtractionApplicationV1 | None, *, cutoff_tick: int,
    ) -> tuple[ExtractionMismatchRequestV1, ...]:
        """Validate a live publication and current basis before admitting/expiring once.

        The original selected extraction (which may have no old latch task) binds
        the new result. Exact replay is harmless but never renewed. Conflicting
        replay, foreign originals and later history admission reject atomically.
        A presently inaccessible source may retain a question, not gain a fake bid.
        """
        cutoff = _tick(cutoff_tick)
        if self._closed or cutoff <= self._last_admission:
            raise ValueError("extraction relevance requires one increasing open source opportunity")
        if (not isinstance(source, FeedingDetailNavMapStateV1) or source.stream != self.stream or source.seed != self.seed
                or source.cutoff_tick != cutoff or self._source is not None and source.applied_cycle <= self._source.applied_cycle):
            raise ValueError("extraction relevance needs the exact current source generation and cutoff")
        if application is not None:
            if not isinstance(application, SuckleExtractionApplicationV1):
                raise TypeError("extraction questions bind a selected extraction, not a latch task")
            if (application.projection.basis.stream != self.stream or application.projection.basis.seed != self.seed
                    or application.projection.basis.maternal.seed != source.maternal.seed
                    or application.projection.basis.cutoff_tick > cutoff):
                raise ValueError("extraction application and current source organization disagree")
        applications = dict(self._applications)
        if application is not None:
            original = applications.get(application.application_id)
            if original is not None and application is not original:
                raise ValueError("original extraction application cannot be replaced by a copy")
            if original is not None and self._application is not None and application is not self._application:
                raise ValueError("latest extraction application cannot regress to an earlier retained original")
            if original is None:
                if len(applications) >= (8 if self.sequential else 1):
                    raise ValueError("original extraction application cannot be replaced or restarted beyond its bound")
                if application.task.sustained != self.sequential:
                    raise ValueError("extraction relevance mode does not match its originating task")
                if self._application is not None:
                    previous = self._application
                    if (application.task.task_id != previous.task.task_id or application.task.started_tick != previous.task.started_tick
                            or application.task.region_id != previous.task.region_id or application.task.started_cycle != previous.task.started_cycle
                            or application.cycle_id <= previous.cycle_id
                            or application.task.applications != previous.task.applications + 1):
                        raise ValueError("sequential relevance preserves the original episode and ordered contributions")
                applications[application.application_id] = application
        elif self._application is not None:
            raise ValueError("original extraction application cannot disappear")
        if not isinstance(outcomes, tuple) or len(outcomes) > 1:
            raise ValueError("one original extraction publication per opportunity")
        seen_outcomes = dict(self._outcomes)
        new_result = None
        for result in outcomes:
            validate_suckle_extraction_outcome_v1(result, stream=self.stream, cutoff_tick=cutoff)
            identity = result.claim.application.application_id
            if result.claim.application is not applications.get(identity):
                raise ValueError("extraction result is not a retained original selected application")
            seen = seen_outcomes.get(identity)
            if seen is not None and result != seen:
                raise ValueError("conflicting extraction publication cannot be a replay")
            if seen is None:
                if result.evaluated_tick != cutoff:
                    raise ValueError("admit a new extraction result at its actual publication, not a history read")
                seen_outcomes[identity] = result
                new_result = result
        dispositions: list[tuple[str, str, int]] = []
        pending = tuple(item for item in self._pending if cutoff < item.expires_at_tick)
        for item in self._pending:
            if cutoff >= item.expires_at_tick:
                dispositions.append((item.request_id, "expired_uninterpreted", cutoff))
        dependencies = tuple(item for item in self._dependencies if cutoff < item.request.expires_at_tick)
        for dependency in self._dependencies:
            if cutoff >= dependency.request.expires_at_tick:
                dispositions.append((dependency.request.request_id, "dependent_response_expired", cutoff))
        created: tuple[ExtractionMismatchRequestV1, ...] = ()
        if new_result is not None:
            evidence = self._significance(new_result)
            if evidence:
                created = (ExtractionMismatchRequestV1(f"extraction_mismatch:{new_result.claim.application.application_id}",
                                                      new_result, cutoff, evidence),)
                pending = (*pending, *created)
        self._pending, self._dependencies = pending, dependencies
        self._dependency = dependencies[0] if dependencies else None
        self._seen = new_result if new_result is not None else self._seen
        self._applications, self._outcomes = applications, seen_outcomes
        self._source, self._application = source, application
        self._last_admission = cutoff
        self._history.extend(dispositions)
        return created

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Augment only an available ordinary source; never stack outcome ranks."""
        source = self._source
        if self._closed or source is None:
            raise RuntimeError("admit the current extraction source before contributing relevance")
        if ordinary is not None and (ordinary.source_map_state is not source or ordinary.cycle_id != source.applied_cycle):
            raise ValueError("extraction relevance must attach to the exact ordinary current bid")
        if ordinary is None or not self._pending or not source.focal_accessible:
            return ordinary
        return replace(ordinary, prediction_or_envelope_failure_rank=max(40, ordinary.prediction_or_envelope_failure_rank),
                       reasons=(*ordinary.reasons, "suckle_extraction_outcome_request"))

    def _validate_working(self, working: WorkingNavMapStateV1 | None, cycle_id: int) -> bool:
        """Read-only focal-basis validation before any allocation mutation."""
        source = self._source
        if (self._closed or source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or source.applied_cycle != cycle_id or cycle_id <= self._last_allocation_cycle):
            raise ValueError("extraction interpretation needs one new admitted opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("extraction interpretation needs this cycle's actual WNM")
        same = working is not None and working.primary_source_state.source_map_ref == source.source_map_ref
        if same and (working is None or working.primary_source_state is not source or not source.focal_accessible):
            raise ValueError("extraction interpretation requires the exact selected accessible source")
        return same

    def interpretation_candidate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int,
    ) -> OutcomeInterpretationCandidateV1 | None:
        """Offer the sole question without consuming it or choosing an operation."""
        same = self._validate_working(working, cycle_id)
        if not same or self._source is None or not self._pending:
            return None
        request = self._pending[0]
        return OutcomeInterpretationCandidateV1(request.request_id, self._source, request.admitted_tick, request.expires_at_tick)

    @staticmethod
    def _relevance(request: ExtractionMismatchRequestV1, source: FeedingDetailNavMapStateV1) -> tuple[tuple[str, str], ...]:
        """Interpret only current affected relations; present endpoints cannot repair history."""
        preview, visual = request.outcome.claim.application.projection, source.maternal.visual
        values: list[tuple[str, str]] = []
        for witness in request.evidence:
            relevance = "unknown"
            current = (visual.evidence_current and visual.event_tick is not None
                       and visual.event_tick >= witness.endpoint.feedback.event_tick and source.frame_id == preview.basis.frame_id)
            paired = current and source.oral_evidence_current
            if witness.relation == "detail_anchor" and current and source.association_status == "compatible" and source.detail_position is not None:
                distance = math.hypot(source.detail_position.x - preview.scene_target.x, source.detail_position.y - preview.scene_target.y)
                relevance = "currently_supported" if distance <= 0.005 + 1e-12 else "still_relevant"
            elif witness.relation == "mouth_position" and paired and source.mouth_position is not None and preview.basis.mouth_position is not None:
                mouth, original = source.mouth_position, preview.basis.mouth_position
                relevance = "currently_supported" if math.hypot(mouth.x - original.x, mouth.y - original.y) <= 0.005 + 1e-12 else "still_relevant"
            elif witness.relation == "sealed_contact" and paired:
                if source.oral_contact is False or source.oral_sealed is False or source.contact_correspondence_status == "touch_elsewhere":
                    relevance = "still_relevant"
                elif source.seal_correspondence_status == "compatible":
                    relevance = "currently_supported"
            values.append((witness.relation, relevance))
        return tuple(values)

    def allocate(
        self, working: WorkingNavMapStateV1 | None, *, cycle_id: int, grant: NavigationDecisionV1 | None = None,
    ) -> ExtractionFocalAllocationV1:
        """Consume only Navigation's prior exact grant; later holds never reinterpret."""
        same = self._validate_working(working, cycle_id)
        if not same or working is None:
            self._last_allocation_cycle = cycle_id
            return ExtractionFocalAllocationV1("other_source")
        if self._pending:
            request = self._pending[0]
            if (not isinstance(grant, NavigationDecisionV1) or grant.wnm is not working or grant.cycle_id != cycle_id
                    or grant.application is not None or grant.reason != f"outcome_interpretation:{request.request_id}"):
                raise ValueError("extraction consumption requires Navigation's prior exact question grant")
            source = self._source
            if source is None:
                raise RuntimeError("validated source disappeared")
            relevance = self._relevance(request, source)
            statuses = {value for _, value in relevance}
            status = ("unresolved_current_relevance" if "unknown" in statuses else
                      "still_relevant" if "still_relevant" in statuses else "historical_resolved")
            interpretation = ExtractionInterpretationV1(request, cycle_id, source.cutoff_tick, working.working_id, source, status, relevance)
            self._pending = self._pending[1:]
            self._dependencies = (*self._dependencies, interpretation)
            self._dependency = self._dependencies[0]
            self._last_allocation_cycle = cycle_id
            self._history.append((request.request_id, "interpreted", source.cutoff_tick))
            return ExtractionFocalAllocationV1("interpretation", interpretation)
        self._last_allocation_cycle = cycle_id
        dependency = self._dependency
        if dependency is None:
            return ExtractionFocalAllocationV1("ordinary")
        if dependency.status == "unresolved_current_relevance":
            return ExtractionFocalAllocationV1("dependent_unresolved", dependency)
        self._dependencies = self._dependencies[1:]
        self._dependency = self._dependencies[0] if self._dependencies else None
        self._history.append((dependency.request.request_id, "response_reconsidered", self._last_admission))
        return ExtractionFocalAllocationV1("response_reconsideration", dependency)
