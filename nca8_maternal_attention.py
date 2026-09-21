#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2B-D: maternal claim discrepancy, source relevance and one focal allocation.

This optional extension belongs to the maternal association source. It consumes
canonical P16-2B-B outcomes, never Righting outcomes, private-world state or local
controller warning labels. C2 performs fixed significance checks. Its rank-40
request changes only the outcome component of the ordinary maternal bid;
Attention still chooses. Current localization, task need and bodily permission
are not manufactured by a request.

The named maternal_outcome_attention_v1 profile interprets one original claim
only after its source becomes WNM. That interpretation occupies the existing
focal opportunity; a dependent response must wait for a later opportunity and
ordinary Navigation/BodyMap checks. This is the existing conservative 1G-B
allocation policy applied to a distinct domain, not a CompareOutcome IP or a
universal biological timing rule. Local protection continues independently.

Fixed significance: contradicted seeded identity; maternal-anchor displacement
of at least 0.10 m; expected proximity <=0.50 m contradicted by observed distance;
or two consecutive executed endpoint discrepancies in a shared relation while
observed proximity remains inadequate. A single small residual is not enough.
The comparator's 0.02-m tolerance, physics, task criteria and budgets are unchanged.
Eight pending requests, one preceding outcome and one interpreted dependency
are retained. Requests expire eight ticks after admission without renewal;
diagnostic history is capped at 32 and never consulted for decisions. No learning,
new action, task restart, extra clock or second WNM is implemented here.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorStreamRefV1
from nca8_executive import AttentionBidV1, WorkingNavMapStateV1
from nca8_followmom import FollowMomTaskV1
from nca8_maternal import MOM_REF, MaternalNavMapStateV1, MaternalSeedV1
from nca8_maternal_outcomes import MaternalClaimV1, MaternalOutcomeV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, CommittedBodyTargetV1
from nca8_visual import VisualObservationV1

__version__ = "0.1.1"
__all__ = [
    "MaternalMismatchRequestV1", "MaternalInterpretationV1", "MaternalFocalAllocationV1",
    "MaternalAttentionFrameV1", "MaternalOutcomeAttentionV1", "__version__",
]
_RELATIONS = ("self_position", "maternal_anchor", "separation")
_RELATION_RESULTS = {"matched", "mismatch", "unknown", "unevaluable_authorization"}
_OUTCOME_STATUSES = {
    "matched", "partly_matched", "mismatch", "identity_contradicted", "unknown", "observed_without_command",
    "not_applied", "cancelled", "interrupted", "expired_unresolved", "unresolved_stopped", "comparison_disabled",
}


def _tick(value: int) -> int:
    """Reject noninteger/Boolean indices and retain headroom for finite expiry."""
    if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value < 2**63 - 17:
        raise ValueError("maternal relevance requires a bounded nonnegative tick")
    return value


def _observed_separation(outcome: MaternalOutcomeV1) -> float | None:
    """Read supported original endpoint distance; absence is not a negative observation."""
    observation, preview = outcome.evidence, outcome.claim.preview
    if observation is None or observation.frame_id != preview.basis.frame_id or observation.self_position is None:
        return None
    found = next((item for item in observation.detections if item.region_id == preview.region_id), None)
    if found is None or found.descriptor != preview.basis.seed.descriptor or found.position is None:
        return None
    return math.hypot(found.position.x - observation.self_position.x, found.position.y - observation.self_position.y)


@dataclass(frozen=True, slots=True)
class MaternalMismatchRequestV1:
    """Original executed claim and fixed significance, not a new world configuration."""

    request_id: str
    outcome: MaternalOutcomeV1
    admitted_tick: int
    significance: str
    relations: tuple[str, ...]

    @property
    def expires_at_tick(self) -> int:
        """Return exclusive request expiry, independent of task/claim/target lifetimes."""
        return self.admitted_tick + 8

    def as_dict(self) -> dict[str, object]:
        """Export evidence provenance without granting source selection or motor rights."""
        preview, evidence = self.outcome.claim.preview, self.outcome.evidence
        return {
            "request_id": self.request_id, "outcome_number": self.outcome.number, "pnm_id": preview.pnm.pnm_id,
            "task_id": preview.task_id, "region_id": preview.region_id, "source_map_ref": preview.basis.source_map_ref.as_dict(),
            "physical_event_tick": evidence.event_tick if evidence is not None else None,
            "available_tick": evidence.available_tick if evidence is not None else None,
            "admitted_tick": self.admitted_tick, "expires_at_tick": self.expires_at_tick,
            "significance": self.significance, "relations": list(self.relations), "outcome_rank": 40,
            "grants_motor_permission": False,
        }


@dataclass(frozen=True, slots=True)
class MaternalInterpretationV1:
    """One actual focal interpretation of history against eligible current relations.

    Current proximity need is not evaluated by comparing a moving kid's newest
    position to an old endpoint. SELF/separation discrepancies are interpreted
    against current target-specific proximity. The maternal anchor and identity
    retain their original meanings. No hidden cause, new maternal identity or
    durable parameter is inferred. Unknown current relevance remains unresolved.
    """

    request: MaternalMismatchRequestV1
    cycle_id: int
    cutoff_tick: int
    working_id: str
    current_source: MaternalNavMapStateV1
    status: str
    relation_relevance: tuple[tuple[str, str], ...]

    def as_dict(self) -> dict[str, object]:
        """Keep historical discrepancy and present relevance independently inspectable."""
        return {
            "request": self.request.as_dict(), "cycle_id": self.cycle_id, "cutoff_tick": self.cutoff_tick,
            "working_id": self.working_id, "current_source": self.current_source.as_dict(), "status": self.status,
            "relation_relevance": dict(self.relation_relevance), "demanding_allocations": 1,
            "causal_credit": "not_established", "durable_learning_updates": 0,
        }


@dataclass(frozen=True, slots=True)
class MaternalFocalAllocationV1:
    """A scheduling disposition, never a chosen primitive or new body request."""

    kind: str
    interpretation: MaternalInterpretationV1 | None = None

    @property
    def permits_primitive_selection(self) -> bool:
        """Exclude a new task application from the demanding interpretation opportunity."""
        return self.kind not in {"interpretation", "dependent_unresolved"}

    def as_dict(self) -> dict[str, object]:
        """Export the existing opportunity's allocation without charging a second cycle."""
        return {
            "kind": self.kind, "permits_primitive_selection": self.permits_primitive_selection,
            "interpretations_this_opportunity": int(self.kind == "interpretation"),
            "interpretation": self.interpretation.as_dict() if self.interpretation is not None else None,
        }


@dataclass(frozen=True, slots=True)
class MaternalAttentionFrameV1:
    """Immutable diagnostics of a completed owner admission and focal allocation."""

    created: tuple[MaternalMismatchRequestV1, ...]
    pending: tuple[MaternalMismatchRequestV1, ...]
    source_bid: AttentionBidV1 | None
    allocation: MaternalFocalAllocationV1
    learning_enabled: bool = False

    def as_dict(self) -> dict[str, object]:
        """Describe the actual source route; learning remains a separately deferred lane."""
        return {
            "profile": "maternal_outcome_attention_v1", "created": [item.as_dict() for item in self.created],
            "pending": [item.as_dict() for item in self.pending],
            "source_bid": self.source_bid.as_dict() if self.source_bid is not None else None,
            "allocation": self.allocation.as_dict(),
            "learning_route": "maternal_no_learning_v1" if self.learning_enabled else "deferred_maternal_reconciliation", "durable_updates": 0,
        }


class MaternalOutcomeAttentionV1:
    """Source-owned transient relevance with atomic admission and bounded history.

    Construct through MaternalSourceV1 before its first update. admit() validates
    the complete frozen batch before changing its high-water mark or pending
    requests. Monotonic canonical outcome numbers prevent replay from extending
    significance or lifetime; gaps break the two-endpoint persistence test.
    contribute_bid() preserves every ordinary priority except the named outcome
    component. allocate() requires this owner's exact current selected source.
    Request overflow raises rather than evicting unresolved work; the enclosing
    core's existing fault path stops. Reset requires a fresh source/generation.
    """

    def __init__(self, stream: MotorStreamRefV1, seed: MaternalSeedV1, *, diagnostic_capacity: int = 32) -> None:
        if not isinstance(stream, MotorStreamRefV1) or not isinstance(seed, MaternalSeedV1):
            raise TypeError("maternal relevance requires its typed stream and declared association")
        if isinstance(diagnostic_capacity, bool) or not isinstance(diagnostic_capacity, int) or not 1 <= diagnostic_capacity <= 32:
            raise ValueError("maternal relevance diagnostic capacity must be 1..32")
        self.stream, self.seed = stream, seed
        self._pending: tuple[MaternalMismatchRequestV1, ...] = ()
        self._previous: MaternalOutcomeV1 | None = None
        self._dependency: MaternalInterpretationV1 | None = None
        self._source: MaternalNavMapStateV1 | None = None
        self._task: FollowMomTaskV1 | None = None
        self._last_number = 0
        self._last_admission = -1
        self._last_allocation_cycle = 0
        self._history: deque[tuple[str, str, int]] = deque(maxlen=diagnostic_capacity)

    def retained_counts(self) -> dict[str, int]:
        """Measure live owner storage; neither trace truncation nor exports drive decisions."""
        return {
            "maternal_attention_pending_requests": len(self._pending),
            "maternal_attention_previous_endpoint": int(self._previous is not None),
            "maternal_attention_dependency": int(self._dependency is not None),
            "maternal_attention_dispositions": len(self._history),
        }

    def pending(self) -> tuple[MaternalMismatchRequestV1, ...]:
        """Read original immutable requests without renewing their expiry."""
        return self._pending

    def dispositions(self) -> tuple[tuple[str, str, int], ...]:
        """Read bounded diagnostic dispositions, not an executable history."""
        return tuple(self._history)

    def _validate_outcome(self, outcome: MaternalOutcomeV1, cutoff: int) -> None:
        """Reject wrong source, operation, permission, time and malformed result payloads."""
        if not isinstance(outcome, MaternalOutcomeV1) or not isinstance(outcome.claim, MaternalClaimV1):
            raise TypeError("maternal relevance accepts only canonical maternal claim outcomes")
        if isinstance(outcome.number, bool) or not isinstance(outcome.number, int) or not 0 < outcome.number < 2**63 - 1:
            raise ValueError("maternal outcome number must be a bounded positive publisher identity")
        _tick(outcome.evaluated_tick)
        if outcome.evaluated_tick > cutoff or (outcome.number > self._last_number and outcome.evaluated_tick != cutoff):
            raise ValueError("new maternal results must enter at their original C2 evaluation, not from future or later replay")
        claim, preview = outcome.claim, outcome.claim.preview
        request, origin = claim.request, claim.request.origin
        if (origin.stream != self.stream or preview.basis.stream != self.stream or preview.basis.source_map_ref != MOM_REF
                or preview.basis.seed != self.seed or preview.task_id != origin.task_id or preview.region_id != self.seed.region_id
                or preview.pnm.application_id != origin.application_id or preview.pnm.primitive_id != "ip:follow_mom"
                or request.source_map_ref != MOM_REF or request.region_id != preview.region_id
                or request.origin_status != "selected_follow_mom"):
            raise ValueError("maternal outcome has foreign source, generation, seed or task/application")
        if not isinstance(claim.targets, tuple) or len(claim.targets) > 1:
            raise ValueError("maternal claim must retain at most one original translation target")
        for target in claim.targets:
            if (not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyTranslationTargetV1)
                    or target.target.origin != origin or target.committed_tick != preview.basis.cutoff_tick):
                raise ValueError("maternal claim does not retain its original translation authorization")
        for names in (claim.compatible_relations, claim.unevaluable_relations):
            if not isinstance(names, tuple) or any(name not in _RELATIONS for name in names) or len(set(names)) != len(names):
                raise ValueError("maternal authorization relation sets are malformed")
        if (set(claim.compatible_relations) & set(claim.unevaluable_relations)
                or set(claim.compatible_relations) | set(claim.unevaluable_relations) != set(_RELATIONS)):
            raise ValueError("maternal authorization must classify each original relation exactly once")
        if outcome.status not in _OUTCOME_STATUSES:
            raise ValueError("unknown maternal endpoint disposition")
        if (isinstance(outcome.command_intervals, bool) or not isinstance(outcome.command_intervals, int)
                or not 0 <= outcome.command_intervals <= preview.horizon_ticks):
            raise ValueError("maternal command exposure must fit the original finite horizon")
        if not isinstance(outcome.relations, tuple) or len(outcome.relations) > 3:
            raise ValueError("maternal results must be a bounded immutable relation tuple")
        for relation_row in outcome.relations:
            if (not isinstance(relation_row, tuple) or len(relation_row) != 2 or relation_row[0] not in _RELATIONS
                    or relation_row[1] not in _RELATION_RESULTS):
                raise ValueError("malformed maternal relation result")
            permitted = (claim.unevaluable_relations
                         if relation_row[1] == "unevaluable_authorization" else claim.compatible_relations)
            if relation_row[0] not in permitted:
                raise ValueError("maternal result contradicts its original authorization meaning")
        if len({name for name, _ in outcome.relations}) != len(outcome.relations):
            raise ValueError("duplicate maternal relation result")
        if not isinstance(outcome.residuals, tuple) or len(outcome.residuals) > 3:
            raise ValueError("maternal residuals must be a bounded immutable tuple")
        for residual_row in outcome.residuals:
            if (not isinstance(residual_row, tuple) or len(residual_row) != 2 or residual_row[0] not in _RELATIONS
                    or isinstance(residual_row[1], bool) or not isinstance(residual_row[1], (int, float))
                    or not math.isfinite(residual_row[1]) or residual_row[1] < 0):
                raise ValueError("maternal residual must be finite, nonnegative and relation-specific")
        if len({name for name, _ in outcome.residuals}) != len(outcome.residuals):
            raise ValueError("duplicate maternal residual")
        evidence = outcome.evidence
        if evidence is not None:
            if not isinstance(evidence, VisualObservationV1):
                raise TypeError("maternal endpoint requires canonical visual evidence")
            evidence.validate_available(stream=self.stream, at_tick=outcome.evaluated_tick)
            if (evidence.event_tick != claim.due_tick or evidence.available_tick > claim.expires_at_tick
                    or preview.basis.sample_id is None or evidence.sample_id <= preview.basis.sample_id):
                raise ValueError("maternal evidence is not the original endpoint's later acquisition")
        executed_discrepancy = outcome.status in {"mismatch", "identity_contradicted"}
        if executed_discrepancy and (not claim.targets or outcome.command_intervals == 0 or evidence is None):
            raise ValueError("maternal discrepancy requires original permission, command exposure and endpoint evidence")
        residuals = dict(outcome.residuals)
        if outcome.status == "mismatch" and not any(status == "mismatch" for _, status in outcome.relations):
            raise ValueError("maternal mismatch lacks a contradicted compatible relation")
        for name, status in outcome.relations:
            if status in {"matched", "mismatch"}:
                residual = residuals.get(name)
                if residual is None or (residual <= 0.02 + 1e-12) != (status == "matched"):
                    raise ValueError("maternal result disagrees with its canonical residual tolerance")
                if evidence is None or evidence.frame_id != preview.basis.frame_id:
                    raise ValueError("scored maternal geometry requires its original scene frame")
        if outcome.status == "identity_contradicted":
            found = None if evidence is None else next((item for item in evidence.detections if item.region_id == preview.region_id), None)
            if found is None or found.descriptor is None or found.descriptor == self.seed.descriptor:
                raise ValueError("identity contradiction requires observed conflicting category, not missing recognition")

    @staticmethod
    def _significance(outcome: MaternalOutcomeV1, previous: MaternalOutcomeV1 | None) -> tuple[str, tuple[str, ...]] | None:
        """Perform fixed local checks only; do not interpret history against current WNM."""
        if outcome.status == "identity_contradicted":
            return "maternal_identity_contradiction", ("identity",)
        if outcome.status != "mismatch":
            return None
        mismatches = tuple(name for name, status in outcome.relations if status == "mismatch")
        residuals = dict(outcome.residuals)
        if "maternal_anchor" in mismatches and residuals.get("maternal_anchor", 0.0) >= 0.10 - 1e-12:
            return "consequential_maternal_anchor_shift", ("maternal_anchor",)
        separation = _observed_separation(outcome)
        if ("separation" in mismatches and outcome.claim.preview.predicted_separation <= 0.50
                and separation is not None and separation > 0.50):
            return "expected_proximity_not_supported", ("separation",)
        if previous is None or previous.number + 1 != outcome.number or previous.status != "mismatch":
            return None
        before, after = previous.claim.preview, outcome.claim.preview
        if ((before.task_id, before.region_id, before.basis.frame_id) != (after.task_id, after.region_id, after.basis.frame_id)
                or previous.claim.due_tick >= outcome.claim.due_tick or before.pnm.created_cycle >= after.pnm.created_cycle):
            return None
        common = tuple(name for name in mismatches if (name, "mismatch") in previous.relations)
        if common and separation is not None and separation > 0.50:
            return "persistent_executed_maternal_discrepancy", common
        return None

    def admit(
        self, outcomes: tuple[MaternalOutcomeV1, ...], source: MaternalNavMapStateV1,
        task: FollowMomTaskV1 | None, *, cutoff_tick: int,
    ) -> tuple[MaternalMismatchRequestV1, ...]:
        """Atomically admit one increasing frozen opportunity; expire without renewal.

        A terminal task may retain a historical question within its original
        budget, but no outcome can reactivate it. Replaced task identity discards
        only the old relevance/dependency, not its immutable claim. Nonapplication,
        unresolved input and comparison-off cannot manufacture mismatch requests.
        """
        cutoff = _tick(cutoff_tick)
        if cutoff <= self._last_admission:
            raise ValueError("maternal relevance admission needs one increasing cutoff")
        if (not isinstance(source, MaternalNavMapStateV1) or source.stream != self.stream
                or source.seed != self.seed or source.source_map_ref != MOM_REF or source.cutoff_tick != cutoff
                or (self._source is not None and source.applied_cycle <= self._source.applied_cycle)):
            raise ValueError("maternal relevance requires this owner's current frozen source")
        if task is not None and (not isinstance(task, FollowMomTaskV1) or task.region_id != self.seed.region_id
                                 or task.started_tick > cutoff or task.started_cycle > source.applied_cycle):
            raise ValueError("maternal task and current source disagree")
        if not isinstance(outcomes, tuple) or len(outcomes) > 8:
            raise ValueError("at most eight canonical maternal outcomes may enter a frozen batch")
        for outcome in outcomes:
            self._validate_outcome(outcome, cutoff)
        if any(left.number >= right.number for left, right in zip(outcomes, outcomes[1:])):
            raise ValueError("maternal outcomes must preserve distinct increasing publisher order")
        task_id = task.task_id if task is not None else None
        pending: list[MaternalMismatchRequestV1] = []
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
        previous, last_number = self._previous, self._last_number
        created: list[MaternalMismatchRequestV1] = []
        for outcome in outcomes:
            if outcome.number <= last_number:
                continue
            belongs = outcome.claim.preview.task_id == task_id
            significance = self._significance(outcome, previous) if belongs else None
            if significance is not None:
                request = MaternalMismatchRequestV1(
                    f"maternal_mismatch:g{self.stream.generation}:o{outcome.number}", outcome, cutoff, *significance,
                )
                pending.append(request)
                created.append(request)
            previous, last_number = (outcome if belongs else None), outcome.number
        if len(pending) > 8:
            raise OverflowError("eight pending maternal requests; no silent eviction or extra focal work")
        self._source, self._task = source, task
        self._pending, self._dependency = tuple(pending), dependency
        self._previous, self._last_number, self._last_admission = previous, last_number, cutoff
        self._history.extend(dispositions)
        return tuple(created)

    def _budget_exhausted(self) -> bool:
        """Respect the original task's physical and focal caps during interpretation too."""
        return self._task is not None and self._source is not None and (
            self._source.applied_cycle - self._task.started_cycle >= 20 or self._last_admission - self._task.started_tick >= 80
        )

    def contribute_bid(self, ordinary: AttentionBidV1 | None) -> AttentionBidV1 | None:
        """Add only outcome rank 40; never revive an inaccessible source or bodily rights."""
        source = self._source
        if source is None:
            raise RuntimeError("admit maternal source/outcomes before requesting relevance")
        if ordinary is not None and (ordinary.source_map_state is not source or ordinary.cycle_id != source.applied_cycle):
            raise ValueError("maternal relevance must attach to the exact current source bid")
        if not self._pending or not source.focal_accessible or self._budget_exhausted():
            return ordinary
        if ordinary is None:
            ordinary = AttentionBidV1(
                f"maternal_outcome_bid:{source.applied_cycle}", "maternal:target_candidate", source, source.owner_circuit,
                source.applied_cycle, 0, 0, 0, 0, 0, 0, (), False, "maternal_target",
            )
        return replace(ordinary, prediction_or_envelope_failure_rank=max(40, ordinary.prediction_or_envelope_failure_rank),
                       reasons=(*ordinary.reasons, "maternal_pnm_outcome_request"))

    @staticmethod
    def _relevance(request: MaternalMismatchRequestV1, source: MaternalNavMapStateV1) -> tuple[tuple[str, str], ...]:
        """Interpret only at the selected source's focal opportunity, with no causal oracle."""
        results: list[tuple[str, str]] = []
        evidence = request.outcome.evidence
        current = (source.visual.evidence_current and source.event_tick is not None and evidence is not None
                   and source.event_tick >= evidence.event_tick)
        for relation in request.relations:
            result = "unknown"
            if current and relation == "identity":
                if source.identity_status == "contradicted":
                    result = "still_relevant"
                elif source.identity_status == "supported":
                    result = "currently_supported"
            elif current and source.action_localized and source.frame_id == request.outcome.claim.preview.basis.frame_id:
                if relation == "maternal_anchor" and source.target_position is not None:
                    anchor = request.outcome.claim.preview.scene_target
                    residual = math.hypot(source.target_position.x - anchor.x, source.target_position.y - anchor.y)
                    result = "currently_supported" if residual <= 0.02 + 1e-12 else "still_relevant"
                elif relation in {"self_position", "separation"} and source.separation is not None:
                    result = "currently_supported" if source.separation <= 0.50 else "still_relevant"
            results.append((relation, result))
        return tuple(results)

    def allocate(self, working: WorkingNavMapStateV1 | None, *, cycle_id: int) -> MaternalFocalAllocationV1:
        """Consume one request only on its selected source; reconsider a response later.

        An unresolved interpretation retains its dependency until the original
        request expires. It blocks only new primitive selection on that source;
        it cannot halt another source, ordinary maintenance or lower protection.
        Expiry releases a dependency, not a remembered motor command. Every later
        response still needs current applicability and BodyMap authorization.
        """
        source = self._source
        if (source is None or isinstance(cycle_id, bool) or not isinstance(cycle_id, int)
                or source.applied_cycle != cycle_id or cycle_id <= self._last_allocation_cycle):
            raise ValueError("maternal allocation requires one new admitted focal opportunity")
        if working is not None and (not isinstance(working, WorkingNavMapStateV1) or working.refreshed_cycle != cycle_id):
            raise ValueError("maternal allocation requires this cycle's actual WNM")
        if working is not None and working.primary_source_state.source_map_ref == MOM_REF and working.primary_source_state is not source:
            raise ValueError("maternal interpretation requires the exact source sample chosen as WNM")
        self._last_allocation_cycle = cycle_id
        if working is None or working.primary_source_state.source_map_ref != MOM_REF:
            return MaternalFocalAllocationV1("other_source")
        if self._budget_exhausted():
            return MaternalFocalAllocationV1("task_budget_exhausted")
        if self._pending:
            request = self._pending[0]
            relevance = self._relevance(request, source)
            statuses = {status for _, status in relevance}
            status = ("unresolved_current_relevance" if "unknown" in statuses else
                      "still_relevant" if "still_relevant" in statuses else "historical_resolved")
            interpretation = MaternalInterpretationV1(request, cycle_id, source.cutoff_tick, working.working_id, source, status, relevance)
            self._pending = self._pending[1:]
            if self._dependency is not None:
                self._history.append((self._dependency.request.request_id, "superseded_dependent_response", source.cutoff_tick))
            self._dependency = interpretation
            self._history.append((request.request_id, "interpreted", source.cutoff_tick))
            return MaternalFocalAllocationV1("interpretation", interpretation)
        dependency = self._dependency
        if dependency is None:
            return MaternalFocalAllocationV1("ordinary")
        if dependency.cycle_id >= cycle_id:
            raise RuntimeError("a response cannot share the maternal interpretation opportunity")
        if dependency.status == "unresolved_current_relevance":
            return MaternalFocalAllocationV1("dependent_unresolved", dependency)
        self._dependency = None
        self._history.append((dependency.request.request_id, "response_reconsidered", source.cutoff_tick))
        return MaternalFocalAllocationV1("response_reconsideration", dependency)
