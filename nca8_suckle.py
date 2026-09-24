#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-H: the initial latch contribution of Navigation-selected Suckle.

This task organizes closure at a currently represented feeding contact. It uses
one source-linked WNM, an original sparse PNM and protected BodyMap mapping;
it cannot drive a motor or inspect a provider. The functional seal substrate is
supplied competence, not tissue mechanics or learned surface recognition.

The first profile ends at an evidence-supported latch subtask. Two distinct
paired seal/contact acquisitions spanning four physical ticks establish that
narrow result. Closure achievement, touch, predicted seal, milk transfer and
completion of the full Suckle feeding task are different claims. No milk,
rhythmic extraction, Suckle outcome-learning route or durable change is added.
"""

from __future__ import annotations

from collections import deque
from dataclasses import dataclass, replace

from nca8_body_targets import OralClosureRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSourceV1
from nca8_prediction import ProjectedNavMapV1, SucklePreviewV1
from nca8_primitives import PrimitiveApplicationV1, PrimitiveApplicabilityV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1
from nca8_sensorimotor_contracts import CommittedBodyTargetV1, LocalTargetReportV1, SensorimotorTargetKindV1, TargetOriginV1

__version__ = "0.4.0"
__all__ = ["SuckleProfileV1", "SuckleTaskV1", "SuckleApplicationV1", "SuckleAssessmentV1", "SuckleIPV1", "__version__"]

_MAX_TICKS = 48
_MAX_OPPORTUNITIES = 12
_DESIRED_CLOSURE = 0.6
_CLOSURE_TOLERANCE = 0.025


def _index(value: int, minimum: int, maximum: int) -> None:
    """Reject Boolean/coerced counters before owner state changes."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("Suckle counter is outside the declared integer bounds")


def _identifier(value: str) -> None:
    """Require an unchanged, finite ASCII identity rather than normalize aliases."""
    if (not isinstance(value, str) or not 1 <= len(value) <= 100 or not value.isascii()
            or not value.isprintable() or value.strip() != value):
        raise ValueError("Suckle identifiers must be bounded printable ASCII text")


@dataclass(frozen=True, slots=True)
class SuckleProfileV1:
    """Opt in to selected latch formation and its separate source influence.

    The constants describe this first engineering profile, not newborn
    physiology. Enabling it does not supply feeding need or a motor capability.
    The complete feeding task remains unfinished. Optional correspondence observes
    the original closure/seal prediction without changing task or motor decisions.
    J's separate, default-disabled outcome_attention_enabled switch allows those
    outcomes to request source consideration and a Navigation-allocated
    interpretation, never automatic IP reapplication or new motor permission.
    K's separate default-disabled hook records bounded participation at F. It
    requires correspondence, not J, and never implements a durable learning rule.
    """

    enabled: bool = True
    influence_enabled: bool = True
    outcomes_enabled: bool = False
    prediction_comparison_enabled: bool = True
    outcome_attention_enabled: bool = False
    learning_hook_enabled: bool = False

    def __post_init__(self) -> None:
        if not all(isinstance(value, bool) for value in (
                self.enabled, self.influence_enabled, self.outcomes_enabled, self.prediction_comparison_enabled,
                self.outcome_attention_enabled, self.learning_hook_enabled)):
            raise TypeError("Suckle switches must be Boolean")
        if not self.outcomes_enabled and not self.prediction_comparison_enabled:
            raise ValueError("Suckle comparison-off requires its correspondence owner")
        if self.outcome_attention_enabled and not self.outcomes_enabled:
            raise ValueError("Suckle relevance requires original-outcome correspondence")
        if self.learning_hook_enabled and not self.outcomes_enabled:
            raise ValueError("Suckle participation requires original-outcome correspondence")

    def as_dict(self) -> dict[str, object]:
        """Disclose fixed scope, timing and unimplemented consumers."""
        return {"profile": "suckle_initial_latch_v1", "enabled": self.enabled, "influence_enabled": self.influence_enabled,
                "desired_closure": _DESIRED_CLOSURE, "closure_tolerance": _CLOSURE_TOLERANCE,
                "maximum_focal_opportunities": _MAX_OPPORTUNITIES, "maximum_physical_ticks": _MAX_TICKS,
                "maximum_target_lease_ticks": 8, "maximum_evidence_gap_ticks": 8,
                "latch_samples": 2, "minimum_latch_span_ticks": 4, "milk": "not_supplied",
                "task_pnm_correspondence": "suckle_correspondence_v1" if self.outcomes_enabled else "deferred",
                **({"prediction_comparison_enabled": self.prediction_comparison_enabled} if self.outcomes_enabled else {}),
                **({"outcome_attention": "suckle_outcome_attention_v1", "interpretation_policy": "one_opportunity_then_later_response",
                    "maximum_pending_requests": 8, "request_lifetime_ticks": 8} if self.outcome_attention_enabled else {}),
                "learning": "suckle_no_learning_v1" if self.learning_hook_enabled else "unimplemented_no_participation",
                **({"maximum_learning_participants": 8, "eligibility_lifetime_cycles": 4,
                    "learning_maturity": "eligibility_only"} if self.learning_hook_enabled else {}),
                "full_suckle_task": "not_implemented"}


@dataclass(frozen=True, slots=True)
class SuckleTaskV1:
    """One bounded initial latch need, not the entire feeding task or a motor tick."""

    task_id: str
    region_id: str
    started_cycle: int
    started_tick: int
    applications: int = 0
    status: str = "active"

    def __post_init__(self) -> None:
        _identifier(self.task_id)
        _identifier(self.region_id)
        _index(self.started_cycle, 1, 2**63 - _MAX_TICKS - 1)
        _index(self.started_tick, 0, 2**63 - _MAX_TICKS - 1)
        _index(self.applications, 0, _MAX_OPPORTUNITIES)
        if self.status not in {"active", "latch_established", "cancelled", "budget_exhausted", "evidence_unavailable",
                               "detail_contradicted", "support_interrupted", "contact_lost", "execution_exhausted"}:
            raise ValueError("unknown Suckle latch disposition")

    def as_dict(self) -> dict[str, object]:
        """Keep the original deadline and explicitly incomplete feeding scope."""
        return {"task_id": self.task_id, "region_id": self.region_id, "started_cycle": self.started_cycle,
                "started_tick": self.started_tick, "applications": self.applications, "status": self.status,
                "expires_at_tick": self.started_tick + _MAX_TICKS, "scope": "initial_latch_only",
                "causal_credit": "not_established", "milk": "not_supplied", "full_suckle_complete": False}


@dataclass(frozen=True, slots=True)
class SuckleApplicationV1(PrimitiveApplicationV1):
    """One selected closure contribution, with separate prospective evidence."""

    task: SuckleTaskV1
    contribution: OralClosureRequestV1
    projection: SucklePreviewV1

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if not isinstance(self.task, SuckleTaskV1) or not isinstance(self.contribution, OralClosureRequestV1):
            raise TypeError("Suckle application requires its typed task and closure request")
        if not isinstance(self.projection, SucklePreviewV1):
            raise TypeError("Suckle application requires its original sparse preview")
        origin, preview = self.contribution.origin, self.projection
        if (self.primitive_id != "ip:suckle" or self.primitive_kind is not PrimitiveKindV1.INSTINCTIVE
                or origin.task_id != self.task.task_id or origin.application_id != self.application_id
                or origin.stream != preview.basis.stream or preview.task_id != self.task.task_id
                or preview.pnm.application_id != self.application_id or preview.pnm.source_wnm_id != self.source_wnm_id
                or preview.pnm.created_cycle != self.cycle_id or self.contribution.source_map_ref != preview.basis.source_map_ref
                or self.contribution.region_id != self.task.region_id or preview.region_id != self.task.region_id
                or self.contribution.desired_closure != _DESIRED_CLOSURE or self.contribution.lease_ticks != preview.horizon_ticks
                or self.contribution.origin_status != "selected_suckle" or self.task.status != "active" or self.task.applications < 1
                or not self.task.started_cycle <= self.cycle_id < self.task.started_cycle + _MAX_OPPORTUNITIES
                or not self.task.started_tick <= preview.basis.cutoff_tick < self.task.started_tick + _MAX_TICKS
                or self.contribution.lease_ticks != min(8, self.task.started_tick + _MAX_TICKS - preview.basis.cutoff_tick)):
            raise ValueError("Suckle task, source, request and original PNM links disagree")

    def as_dict(self) -> dict[str, object]:
        """Export task selection without claiming a physical seal or nourishment."""
        return {**PrimitiveApplicationV1.as_dict(self), "task": self.task.as_dict(),
                "contribution": self.contribution.as_dict(), "projection": self.projection.as_dict(),
                "origin_status": "navigation_selected_suckle_initial_latch"}


@dataclass(frozen=True, slots=True)
class SuckleAssessmentV1:
    """Current readiness plus retained original latch evidence, not a PNM verdict."""

    task: SuckleTaskV1 | None
    reason: str
    latch_samples: tuple[FeedingDetailNavMapStateV1, ...]
    local_target_busy: bool
    movement_blocked: bool
    cancel_previous: bool
    current_seal_status: str

    def as_dict(self) -> dict[str, object]:
        """Keep current seal and a historical established latch separately visible."""
        return {"task": None if self.task is None else self.task.as_dict(), "reason": self.reason,
                "latch_samples": [{"sample_id": item.maternal.visual.sample_id, "event_tick": item.maternal.visual.event_tick,
                                   "distance_metres": item.mouth_detail_distance, "touch": item.oral_contact,
                                   "sealed": item.oral_sealed, "correspondence": item.seal_correspondence_status}
                                  for item in self.latch_samples],
                "local_target_busy": self.local_target_busy, "movement_blocked": self.movement_blocked,
                "cancel_previous": self.cancel_previous, "current_seal_status": self.current_seal_status,
                "pnm_fulfilment": "not_evaluated", "durable_updates": 0, "full_suckle_complete": False}


class SuckleIPV1:
    """Organize initial latch through the ordinary task-selection interface.

    prepare() evaluates current evidence and a finite task; it neither selects
    Suckle nor constructs a target. apply() performs the selected relation
    transformation. authorized() remembers the actual protected contribution.
    Source relevance has one named owner, so an earlier task cannot clear this
    task's influence. Reset is construction of a fresh owner, not permission
    restored from history. Terminal latch is historical, not a promise that the
    physical seal will persist afterward.
    """

    primitive_id = "ip:suckle"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, source: FeedingDetailSourceV1, profile: SuckleProfileV1) -> None:
        if not isinstance(source, FeedingDetailSourceV1) or not isinstance(profile, SuckleProfileV1):
            raise TypeError("Suckle requires its source owner and explicit latch profile")
        self.source, self.profile = source, profile
        self._task: SuckleTaskV1 | None = None
        self._basis: FeedingDetailNavMapStateV1 | None = None
        self._target: CommittedBodyTargetV1 | None = None
        self._history: deque[SuckleApplicationV1] = deque(maxlen=8)
        self._proof: list[FeedingDetailNavMapStateV1] = []
        self._gap_start: int | None = None
        self._applied_cycle, self._authorized_cycle = 0, 0
        self._reason = "not_prepared"
        self._busy, self._blocked, self._cancel_previous, self._cancelled = False, False, False, False

    @property
    def task(self) -> SuckleTaskV1 | None:
        """Read this finite latch subtask; inspection never creates or restarts one."""
        return self._task

    @property
    def authorized_target(self) -> CommittedBodyTargetV1 | None:
        """Retain original target identity for scoped revocation, not renewed rights."""
        return self._target

    @property
    def cancel_previous(self) -> bool:
        """Request cancellation only of this owner's still-live target."""
        return self._cancel_previous

    def assessment(self) -> SuckleAssessmentV1:
        """Freeze readiness without processing another acquisition or advancing time."""
        return SuckleAssessmentV1(self._task, self._reason, tuple(self._proof), self._busy, self._blocked,
                                  self._cancel_previous, self._basis.seal_correspondence_status if self._basis else "unavailable")

    def history(self) -> tuple[SuckleApplicationV1, ...]:
        """Read up to eight original applications without replaying their permissions."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Expose actual bounded owner storage independently from observer exports."""
        return {"tasks": int(self._task is not None), "source_bases": int(self._basis is not None),
                "targets": int(self._target is not None), "applications": len(self._history), "latch_samples": len(self._proof)}

    def cancel(self) -> None:
        """Make cancellation sticky; the caller separately retires motor authority."""
        if self._task is not None:
            if self._task.status == "active":
                self._task = replace(self._task, status="cancelled")
            self.source.clear_influence(task_id=self._task.task_id)
        self._cancelled, self._cancel_previous, self._reason = True, self._target is not None, "cancelled"

    @staticmethod
    def _supported(basis: FeedingDetailNavMapStateV1) -> bool:
        """Check current oral-support evidence; BodyMap independently authorizes it."""
        feedback = basis.oral_feedback
        return bool(basis.oral_evidence_current and feedback is not None and feedback.support_contact is True
                    and feedback.body_tilt_degrees is not None and abs(feedback.body_tilt_degrees) <= 12.0
                    and feedback.useful_loading is not None and feedback.useful_loading >= 0.75
                    and feedback.destabilization is not None and feedback.destabilization <= 0.25)

    @staticmethod
    def _support_contradicted(basis: FeedingDetailNavMapStateV1) -> bool:
        """Distinguish known unsafe support from an incomplete current report."""
        feedback = basis.oral_feedback
        return bool(basis.oral_evidence_current and feedback is not None and (
            feedback.support_contact is False
            or feedback.body_tilt_degrees is not None and abs(feedback.body_tilt_degrees) > 12.0
            or feedback.useful_loading is not None and feedback.useful_loading < 0.75
            or feedback.destabilization is not None and feedback.destabilization > 0.25))

    def _observe_latch(self, basis: FeedingDetailNavMapStateV1) -> None:
        """Accumulate distinct post-start seal evidence, never cached confirmation.

        These are repeated supported observations, not a guarantee about every
        unsampled physical instant. Contradiction or a disqualifying gap breaks
        the proof. Once established, terminal evidence remains historical.
        """
        task, event = self._task, basis.maternal.visual.event_tick
        if task is None or event is None or event <= task.started_tick or basis.seal_correspondence_status != "compatible":
            self._proof.clear()
            return
        if self._proof:
            previous = self._proof[-1]
            previous_event = previous.maternal.visual.event_tick
            if basis.maternal.visual.sample_id == previous.maternal.visual.sample_id:
                return
            if previous_event is None or event <= previous_event:
                self._proof.clear()
                return
            if event - previous_event > 8 or basis.frame_id != previous.frame_id:
                self._proof.clear()
        self._proof.append(basis)
        if len(self._proof) > 2:
            self._proof = [self._proof[0], self._proof[-1]]
        first_event = self._proof[0].maternal.visual.event_tick
        if len(self._proof) == 2 and first_event is not None and event - first_event >= 4:
            self._task = replace(task, status="latch_established")

    def prepare(
        self, basis: FeedingDetailNavMapStateV1, *, reports: tuple[LocalTargetReportV1, ...] = (), movement_blocked: bool = False,
    ) -> None:
        """Prepare one eligible source opportunity without selecting an operation.

        Blocking describes actual incompatible reservations or ongoing support
        authority, not a reached-Mom/seeking-completion milestone. Missing input
        clears latch proof and exact pursuit but permits a bounded current-input
        return. An expired task is never restarted by recovered input.
        """
        if not isinstance(basis, FeedingDetailNavMapStateV1) or basis is not self.source.current:
            raise ValueError("Suckle needs its owner's actual current feeding basis")
        if self._basis is not None and basis.applied_cycle <= self._basis.applied_cycle:
            raise ValueError("Suckle preparation cannot repeat an opportunity")
        if not isinstance(movement_blocked, bool):
            raise TypeError("Suckle movement blocking must be Boolean")
        if not isinstance(reports, tuple) or len(reports) > 2 or any(not isinstance(item, LocalTargetReportV1) for item in reports):
            raise TypeError("Suckle accepts at most two typed local reports")
        for item in reports:
            if item.reported_tick > basis.cutoff_tick or item.committed_target.target.origin.stream != basis.stream:
                raise ValueError("Suckle report is future or foreign")
            if (self._target is not None and item.committed_target.target.target_id == self._target.target.target_id
                    and item.committed_target is not self._target):
                raise ValueError("Suckle report must retain its original authorized target")
        self._basis, self._blocked = basis, movement_blocked
        report = next((item for item in reports if item.committed_target is self._target), None)
        self._busy = bool(self._target is not None and basis.cutoff_tick < self._target.expires_at_tick
                          and (report is None or report.disposition.value in {"pending", "active", "partial"}))
        supported = self._supported(basis)
        body = basis.oral_feedback
        closure = body.oral_seal.closure if basis.oral_evidence_current and body is not None and body.oral_seal is not None else None
        usable = supported and closure is not None and basis.contact_correspondence_status == "compatible"
        task = self._task
        if task is not None and task.status == "active":
            if basis.applied_cycle - task.started_cycle >= _MAX_OPPORTUNITIES or basis.cutoff_tick - task.started_tick >= _MAX_TICKS:
                self._task = replace(task, status="budget_exhausted")
            elif basis.association_status in {"detail_category_contradicted", "part_geometry_contradicted", "parent_seed_mismatch"}:
                self._task = replace(task, status="detail_contradicted")
            elif self._support_contradicted(basis):
                self._task = replace(task, status="support_interrupted")
            elif basis.contact_correspondence_status in {"no_touch", "touch_elsewhere"}:
                self._task = replace(task, status="contact_lost")
            elif report is not None and (report.disposition.value in {"blocked", "expired"}
                                         or report.reason == "anomalous_correction_budget_exhausted"):
                self._task = replace(task, status="execution_exhausted")
            elif self._gap_start is not None and basis.cutoff_tick - self._gap_start >= 8:
                self._task = replace(task, status="evidence_unavailable")
            elif not usable:
                self._gap_start = basis.cutoff_tick if self._gap_start is None else self._gap_start
                self._proof.clear()
            else:
                self._gap_start = None
                self._observe_latch(basis)
        if self._task is not None and self._task.status != "active":
            self._reason = self._task.status
        elif self._cancelled:
            self._reason = "cancelled"
        elif not self.profile.enabled:
            self._reason = "suckle_disabled"
        elif not self.source.profile.feeding_need:
            self._reason = "no_declared_feeding_need"
        elif not basis.oral_evidence_current:
            self._reason = "current_mouth_detail_unavailable"
        elif not supported:
            self._reason = "oral_support_unavailable"
        elif closure is None:
            self._reason = "closure_evidence_unavailable"
        elif basis.contact_correspondence_status != "compatible":
            self._reason = "feeding_contact_not_supported"
        elif movement_blocked:
            self._reason = "awaiting_incompatible_movement_release"
        elif basis.oral_sealed is True:
            self._reason = "latch_confirmation_pending" if self._task is not None else "already_sealed_no_task"
        elif self._busy:
            self._reason = "authorized_closure_continues"
        elif closure >= _DESIRED_CLOSURE - _CLOSURE_TOLERANCE:
            self._reason = "closure_achieved_without_latch_evidence"
        else:
            self._reason = "initiate_latch" if self._task is None else "continue_latch"
        self._cancel_previous = self._target is not None and self._reason not in {
            "initiate_latch", "continue_latch", "authorized_closure_continues", "latch_confirmation_pending",
        }
        if self._task is not None and self._task.status != "active":
            self.source.clear_influence(task_id=self._task.task_id)

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Query this prepared current WNM; no milestone can grant eligibility."""
        _index(cycle_id, 1, 2**63 - 1)
        if not isinstance(wnm, WorkingNavMapStateV1) or wnm.refreshed_cycle != cycle_id:
            raise ValueError("Suckle applicability requires a current WNM")
        eligible = (wnm.primary_source_state is self._basis and self._basis is not None and self.source.current is self._basis
                    and self._basis.applied_cycle == cycle_id and cycle_id != self._applied_cycle
                    and self._reason in {"initiate_latch", "continue_latch"})
        reason = self._reason if wnm.primary_source_state is self._basis else "not_the_prepared_feeding_source"
        return PrimitiveApplicabilityV1(self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
                                        0, 50 if eligible else 0, 0, 0, 0, () if eligible else (reason,), (reason,), self.primitive_id)

    def apply(
        self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int,
    ) -> SuckleApplicationV1:
        """Transform selected current contact into conditional closure/seal relations."""
        current = self.evaluate_applicability(wnm, cycle_id=cycle_id)
        if current != applicability or not current.eligible:
            raise ValueError("Suckle application requires the current eligible selection")
        basis = self._basis
        if basis is None or basis.detail_position is None or basis.oral_feedback is None or basis.oral_feedback.oral_seal is None:
            raise RuntimeError("selected Suckle source lost its paired closure/contact evidence")
        closure = basis.oral_feedback.oral_seal.closure
        if closure is None:
            raise RuntimeError("selected Suckle source lost measured closure")
        task = self._task or SuckleTaskV1(f"suckle_latch:{basis.stream.generation}:{cycle_id}", basis.seed.detail_region_id,
                                         cycle_id, basis.cutoff_tick)
        horizon = min(8, task.started_tick + _MAX_TICKS - basis.cutoff_tick)
        predicted = min(_DESIRED_CLOSURE, closure + min(0.6, 0.1 * horizon))
        app_id = f"suckle_application:{basis.stream.generation}:{cycle_id}"
        relations = ("MOUTH:closure_increase_at_current_detail", "DETAIL:original_scene_anchor", "SEAL:conditional_expected")
        pnm = ProjectedNavMapV1(f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id, relations,
                               "later paired closure/contact/seal acquisition; sealable-surface assumption, not milk", cycle_id + 1, cycle_id + 2)
        request = OralClosureRequestV1(
            TargetOriginV1(basis.stream, task.task_id, app_id, f"suckle_envelope:{basis.stream.generation}:{cycle_id}"),
            basis.source_map_ref, task.region_id, _DESIRED_CLOSURE, horizon, origin_status="selected_suckle",
        )
        projection = SucklePreviewV1(pnm, basis, task.task_id, task.region_id, basis.detail_position, predicted, horizon)
        next_task = replace(task, applications=task.applications + 1)
        result = SuckleApplicationV1(app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
                                    ("feeding:initial_latch_contribution",), relations, pnm.observation_condition,
                                    TaskActionV1(f"transport:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None,
                                    next_task, request, projection)
        if self.profile.influence_enabled:
            self.source.retain_influence(task.task_id, cycle_id=cycle_id, expires_at_tick=basis.cutoff_tick + horizon)
        self._task, self._applied_cycle = next_task, cycle_id
        self._history.append(result)
        return result

    def authorized(self, application: SuckleApplicationV1, targets: tuple[CommittedBodyTargetV1, ...]) -> None:
        """Retain actual closure permission once; a proposal is not motor authority."""
        if (not self._history or application is not self._history[-1] or self._authorized_cycle == self._applied_cycle
                or application.cycle_id != self._applied_cycle):
            raise ValueError("Suckle authorization must answer its original current application once")
        if not isinstance(targets, tuple) or len(targets) > 1:
            raise ValueError("Suckle can bind at most one closure target")
        if any(not isinstance(target, CommittedBodyTargetV1) or target.target.kind is not SensorimotorTargetKindV1.ORAL_CLOSURE
               or target.target.origin != application.contribution.origin for target in targets):
            raise ValueError("target does not belong to the selected Suckle application")
        self._target = targets[0] if targets else None
        self._authorized_cycle = self._applied_cycle
