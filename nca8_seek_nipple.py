#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-C: bounded Navigation-selected approach to represented feeding detail.

SeekNipple uses one current source-linked WNM and the existing task/PNM/BodyMap
boundary. It organizes a limited mouth/detail relation, never drives an actuator
or reads a world. The first profile permits only the already implemented oral
reach axis: no private head turn, body approach, blind search, latch or suckling.
The supplied developmental need and part/recognition seeds are not learned.

Two distinct paired current acquisitions spanning four physical ticks establish
that the mouth reached the represented detail within five millimetres. This
engineering reach criterion is independent of touch; even a true touch cannot
identify a nipple surface, seal a latch or establish milk. P16-2C-D may opt in to
separate original-PNM correspondence. P16-2C-E may allocate its source-owned
interpretation instead of a new primitive in the existing focal slot. Neither
extension changes these task rules or renews their budgets. Feeding participation/learning and full newborn qualification remain deferred.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import OralReachRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailSourceV1
from nca8_prediction import ProjectedNavMapV1, SeekNipplePreviewV1
from nca8_primitives import PrimitiveApplicationV1, PrimitiveApplicabilityV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1
from nca8_sensorimotor_contracts import CommittedBodyTargetV1, LocalTargetReportV1, SensorimotorTargetKindV1, TargetOriginV1

__version__ = "0.3.0"
__all__ = ["SeekNippleProfileV1", "SeekNippleTaskV1", "SeekNippleApplicationV1", "SeekNippleAssessmentV1", "SeekNippleIPV1", "__version__"]

_MAX_TICKS = 48
_MAX_OPPORTUNITIES = 12
_REACH_TOLERANCE = 0.005


def _index(value: int, minimum: int, maximum: int) -> None:
    """Reject Boolean, coerced and out-of-profile counters before changing an owner."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError("seeking counter is outside its declared integer bounds")


@dataclass(frozen=True, slots=True)
class SeekNippleProfileV1:
    """Enable the selected task and its relevance contribution independently.

    Creating this profile opts in to task integration; existing A/B experiments
    do not construct it. Fixed control constants are disclosed rather than made
    tunable per scenario. BodyMap competence and protection remain independent.
    """

    enabled: bool = True
    influence_enabled: bool = True
    outcomes_enabled: bool = False
    prediction_comparison_enabled: bool = True
    outcome_attention_enabled: bool = False

    def __post_init__(self) -> None:
        if not all(isinstance(flag, bool) for flag in (self.enabled, self.influence_enabled, self.outcomes_enabled, self.prediction_comparison_enabled, self.outcome_attention_enabled)):
            raise TypeError("seeking switches must be Boolean")
        if not self.outcomes_enabled and not self.prediction_comparison_enabled:
            raise ValueError("comparison-off requires the explicit seeking correspondence consumer")
        if self.outcome_attention_enabled and not self.outcomes_enabled:
            raise ValueError("seeking relevance requires the canonical correspondence consumer")

    def as_dict(self) -> dict[str, object]:
        """Describe fixed scope without promising task success or physiological realism."""
        return {"profile": "seek_nipple_v1", "enabled": self.enabled, "influence_enabled": self.influence_enabled,
                "maximum_focal_opportunities": _MAX_OPPORTUNITIES, "maximum_physical_ticks": _MAX_TICKS,
                "maximum_contribution_metres": 0.15, "maximum_target_lease_ticks": 8,
                "maximum_detail_gap_ticks": 8, "reach_tolerance_metres": _REACH_TOLERANCE,
                "reach_samples": 2, "minimum_reach_span_ticks": 4, "contact_required_for_reach": False,
                "task_pnm_correspondence": "seek_nipple_correspondence_v1" if self.outcomes_enabled else "deferred",
                **({"prediction_comparison_enabled": self.prediction_comparison_enabled} if self.outcomes_enabled else {}),
                **({"outcome_attention": "seeking_outcome_attention_v1"} if self.outcome_attention_enabled else {}),
                "feeding_learning": "unimplemented_no_participation"}


@dataclass(frozen=True, slots=True)
class SeekNippleTaskV1:
    """One finite oral-approach need, not an application, motor tick or latch."""

    task_id: str
    region_id: str
    started_cycle: int
    started_tick: int
    applications: int = 0
    status: str = "active"

    def __post_init__(self) -> None:
        for text in (self.task_id, self.region_id):
            if not isinstance(text, str) or not 1 <= len(text) <= 100 or not text.isascii() or not text.isprintable() or text.strip() != text:
                raise ValueError("seeking task identifiers must be bounded ASCII text")
        _index(self.started_cycle, 1, 2**63 - _MAX_TICKS - 1)
        _index(self.started_tick, 0, 2**63 - _MAX_TICKS - 1)
        _index(self.applications, 0, _MAX_OPPORTUNITIES)
        if self.status not in {"active", "reached_detail", "cancelled", "budget_exhausted", "target_unavailable",
                                "detail_contradicted", "support_interrupted", "execution_exhausted", "unexpected_contact"}:
            raise ValueError("unknown seeking task disposition")

    def as_dict(self) -> dict[str, object]:
        """Retain the original task deadline and uncertain causal credit."""
        return {"task_id": self.task_id, "region_id": self.region_id, "started_cycle": self.started_cycle,
                "started_tick": self.started_tick, "applications": self.applications, "status": self.status,
                "expires_at_tick": self.started_tick + _MAX_TICKS, "causal_credit": "not_established",
                "latch": "not_implemented", "milk": "not_supplied"}


@dataclass(frozen=True, slots=True)
class SeekNippleApplicationV1(PrimitiveApplicationV1):
    """One selected bounded source transform with separate request and prediction."""

    task: SeekNippleTaskV1
    contribution: OralReachRequestV1
    projection: SeekNipplePreviewV1

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if not isinstance(self.task, SeekNippleTaskV1) or not isinstance(self.contribution, OralReachRequestV1):
            raise TypeError("seeking application requires its task and oral relation request")
        if not isinstance(self.projection, SeekNipplePreviewV1):
            raise TypeError("seeking application requires its original sparse PNM")
        origin, preview = self.contribution.origin, self.projection
        if (self.primitive_id != "ip:seek_nipple" or self.primitive_kind is not PrimitiveKindV1.INSTINCTIVE
                or origin.task_id != self.task.task_id or origin.application_id != self.application_id
                or preview.task_id != self.task.task_id or preview.pnm.application_id != self.application_id
                or preview.pnm.source_wnm_id != self.source_wnm_id or preview.pnm.created_cycle != self.cycle_id
                or origin.stream != preview.basis.stream or self.contribution.source_map_ref != preview.basis.source_map_ref
                or preview.region_id != self.task.region_id or self.contribution.region_id != self.task.region_id
                or self.contribution.lease_ticks != preview.horizon_ticks or self.contribution.origin_status != "selected_seek_nipple"):
            raise ValueError("seeking application, request and PNM must preserve their original source/task links")

    def as_dict(self) -> dict[str, object]:
        """Export proposed approach, not observed reach/contact or motor permission."""
        return {**PrimitiveApplicationV1.as_dict(self), "task": self.task.as_dict(),
                "contribution": self.contribution.as_dict(), "projection": self.projection.as_dict(),
                "origin_status": "navigation_selected_seek_nipple_with_declared_seed"}


@dataclass(frozen=True, slots=True)
class SeekNippleAssessmentV1:
    """Current task readiness and measured reach proof, independent of PNM verdicts."""

    task: SeekNippleTaskV1 | None
    reason: str
    reach_samples: tuple[FeedingDetailNavMapStateV1, ...]
    local_target_busy: bool
    movement_blocked: bool
    cancel_previous: bool

    def as_dict(self) -> dict[str, object]:
        """Keep geometry, tactile evidence, permission and task completion distinct."""
        return {"task": None if self.task is None else self.task.as_dict(), "reason": self.reason,
                "reach_samples": [{"sample_id": item.maternal.visual.sample_id, "event_tick": item.maternal.visual.event_tick,
                                   "distance_metres": item.mouth_detail_distance, "touch": item.oral_contact} for item in self.reach_samples],
                "local_target_busy": self.local_target_busy, "movement_blocked": self.movement_blocked,
                "cancel_previous": self.cancel_previous, "pnm_fulfilment": "not_evaluated", "durable_updates": 0}


class SeekNippleIPV1:
    """Organize one finite seeking task through the common Navigation interface.

    prepare() updates only current readiness, finite lifetime and elementary
    reach evidence. It does not choose a task, compute a new prospective approach
    or reserve a target. apply() performs that one selected transformation.
    authorized() remembers what BodyMap actually permitted, not what was desired.
    The task never reads a provider, local driver or diagnostic history to act.
    """

    primitive_id = "ip:seek_nipple"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, source: FeedingDetailSourceV1, profile: SeekNippleProfileV1) -> None:
        if not isinstance(source, FeedingDetailSourceV1) or not isinstance(profile, SeekNippleProfileV1):
            raise TypeError("seeking requires its own source owner and explicit profile")
        self.source, self.profile = source, profile
        self._task: SeekNippleTaskV1 | None = None
        self._basis: FeedingDetailNavMapStateV1 | None = None
        self._target: CommittedBodyTargetV1 | None = None
        self._history: deque[SeekNippleApplicationV1] = deque(maxlen=8)
        self._reach: list[FeedingDetailNavMapStateV1] = []
        self._gap_start: int | None = None
        self._applied_cycle, self._authorized_cycle = 0, 0
        self._reason = "not_prepared"
        self._busy, self._blocked, self._cancel_previous, self._cancelled = False, False, False, False

    @property
    def task(self) -> SeekNippleTaskV1 | None:
        """Read the immutable task, including terminal history; never restart it."""
        return self._task

    @property
    def authorized_target(self) -> CommittedBodyTargetV1 | None:
        """Read the original target identity for scoped revocation, not live permission."""
        return self._target

    @property
    def cancel_previous(self) -> bool:
        """Request retirement of this task's target only; the core checks live ownership."""
        return self._cancel_previous

    def assessment(self) -> SeekNippleAssessmentV1:
        """Freeze current readiness; inspection does not run another calculation."""
        return SeekNippleAssessmentV1(self._task, self._reason, tuple(self._reach), self._busy, self._blocked, self._cancel_previous)

    def history(self) -> tuple[SeekNippleApplicationV1, ...]:
        """Expose at most eight original applications, never replayable permissions."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Measure actual finite owner storage separately from observer exports."""
        return {"tasks": int(self._task is not None), "source_bases": int(self._basis is not None),
                "targets": int(self._target is not None), "applications": len(self._history), "reach_samples": len(self._reach)}

    def cancel(self) -> None:
        """Make cancellation sticky; the caller must separately revoke live lower rights."""
        if self._task is not None and self._task.status == "active":
            self._task = replace(self._task, status="cancelled")
        self._cancelled, self._cancel_previous, self._reason = True, self._target is not None, "cancelled"
        self.source.clear_influence()

    @staticmethod
    def _support_available(basis: FeedingDetailNavMapStateV1) -> bool:
        """Check declared oral support preconditions without granting BodyMap rights."""
        feedback = basis.oral_feedback
        return bool(basis.oral_evidence_current and feedback is not None and feedback.support_contact is True
                    and feedback.body_tilt_degrees is not None and abs(feedback.body_tilt_degrees) <= 12.0
                    and feedback.useful_loading is not None and feedback.useful_loading >= 0.75
                    and feedback.destabilization is not None and feedback.destabilization <= 0.25)

    def _observe_reach(self, basis: FeedingDetailNavMapStateV1, supported: bool) -> None:
        """Require distinct paired acquisitions and a fixed physical span, not rereads."""
        distance = basis.mouth_detail_distance
        if not supported or distance is None or distance > _REACH_TOLERANCE + 1e-12:
            self._reach.clear()
            return
        event = basis.maternal.visual.event_tick
        if event is None:
            raise RuntimeError("paired oral evidence lost its event identity")
        if self._reach:
            previous = self._reach[-1]
            previous_event = previous.maternal.visual.event_tick
            if basis.maternal.visual.sample_id == previous.maternal.visual.sample_id:
                return
            if previous_event is None or basis.frame_id != previous.frame_id or event - previous_event > 8:
                self._reach.clear()
        self._reach.append(basis)
        if len(self._reach) > 2:
            self._reach = [self._reach[0], self._reach[-1]]
        first_event = self._reach[0].maternal.visual.event_tick
        if len(self._reach) == 2 and first_event is not None and event - first_event >= 4 and self._task is not None:
            self._task = replace(self._task, status="reached_detail")

    def prepare(
        self, basis: FeedingDetailNavMapStateV1, *, reports: tuple[LocalTargetReportV1, ...] = (), movement_blocked: bool = False,
    ) -> None:
        """Prepare one current source opportunity before ordinary Attention.

        movement_blocked describes actual incompatible motor ownership or an
        unfinished support task, not reached-Mom or a benchmark stage. It never
        deletes detail or forces another operation. A short missing-detail gap
        cancels exact pursuit but can retain this task until its original deadline;
        eight ticks without usable detail terminates it without a silent restart.
        """
        if not isinstance(basis, FeedingDetailNavMapStateV1) or basis is not self.source.current:
            raise ValueError("seeking requires the owning source's actual current basis")
        if self._basis is not None and basis.applied_cycle <= self._basis.applied_cycle:
            raise ValueError("seeking preparation cannot repeat an opportunity")
        if not isinstance(movement_blocked, bool):
            raise TypeError("movement blocking must be explicit Boolean authority state")
        if not isinstance(reports, tuple) or len(reports) > 2 or any(not isinstance(item, LocalTargetReportV1) for item in reports):
            raise TypeError("seeking accepts at most two immutable lower reports")
        for item in reports:
            if item.reported_tick > basis.cutoff_tick or item.committed_target.target.origin.stream != basis.stream:
                raise ValueError("seeking report is future or foreign")
            if (self._target is not None and item.committed_target.target.target_id == self._target.target.target_id
                    and item.committed_target is not self._target):
                raise ValueError("seeking report must retain the original authorized target")
        self._basis, self._blocked = basis, movement_blocked
        report = next((item for item in reports if item.committed_target is self._target), None)
        self._busy = bool(self._target is not None and basis.cutoff_tick < self._target.expires_at_tick
                          and (report is None and not reports or report is not None and report.disposition.value in {"pending", "active", "partial"}))
        supported = self._support_available(basis)
        distance = basis.mouth_detail_distance
        task = self._task
        if task is not None and task.status == "active":
            if basis.applied_cycle - task.started_cycle >= _MAX_OPPORTUNITIES or basis.cutoff_tick - task.started_tick >= _MAX_TICKS:
                self._task = replace(task, status="budget_exhausted")
            elif basis.association_status in {"detail_category_contradicted", "part_geometry_contradicted", "parent_seed_mismatch"}:
                self._task = replace(task, status="detail_contradicted")
            elif basis.oral_evidence_current and not supported:
                self._task = replace(task, status="support_interrupted")
            elif basis.oral_contact is True and distance is not None and distance > _REACH_TOLERANCE + 1e-12:
                self._task = replace(task, status="unexpected_contact")
            elif report is not None and report.reason == "oral_contact_before_target":
                self._task = replace(task, status="unexpected_contact")
            elif report is not None and report.reason != "oral_body_anchor_changed" and (
                    report.disposition.value in {"blocked", "expired"} or report.reason == "anomalous_correction_budget_exhausted"):
                self._task = replace(task, status="execution_exhausted")
            elif self._gap_start is not None and basis.cutoff_tick - self._gap_start >= 8:
                self._task = replace(task, status="target_unavailable")
            elif not basis.oral_evidence_current or distance is None:
                self._gap_start = basis.cutoff_tick if self._gap_start is None else self._gap_start
                self._reach.clear()
                if basis.cutoff_tick - self._gap_start >= 8:
                    self._task = replace(task, status="target_unavailable")
            else:
                self._gap_start = None
                self._observe_reach(basis, supported)
        if self._task is not None and self._task.status != "active":
            self._reason = self._task.status
        elif self._cancelled:
            self._reason = "cancelled"
        elif not self.profile.enabled:
            self._reason = "seeking_disabled"
        elif not self.source.profile.feeding_need:
            self._reason = "no_declared_feeding_need"
        elif not basis.oral_evidence_current or distance is None:
            self._reason = "current_mouth_detail_unavailable"
        elif not supported:
            self._reason = "oral_support_unavailable"
        elif movement_blocked:
            self._reason = "awaiting_incompatible_movement_release"
        elif basis.oral_contact is None:
            self._reason = "touch_evidence_unavailable"
        elif distance <= _REACH_TOLERANCE + 1e-12:
            self._reason = "reach_confirmation_pending" if self._task is not None else "already_at_detail_no_task"
        elif basis.oral_contact is True:
            self._reason = "unexpected_contact"
        elif self._busy:
            self._reason = "authorized_oral_contribution_continues"
        else:
            self._reason = "initiate_seeking" if self._task is None else "continue_seeking"
        self._cancel_previous = self._target is not None and self._reason not in {
            "initiate_seeking", "continue_seeking", "authorized_oral_contribution_continues",
        }
        if self._task is not None and self._task.status != "active" or self._cancelled:
            self.source.clear_influence()

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Query only this source's current focal sample, without starting a task."""
        _index(cycle_id, 1, 2**63 - 1)
        if not isinstance(wnm, WorkingNavMapStateV1) or wnm.refreshed_cycle != cycle_id:
            raise ValueError("seeking applicability requires a current WNM")
        eligible = (wnm.primary_source_state is self._basis and self._basis is not None and self.source.current is self._basis
                    and self._basis.applied_cycle == cycle_id and cycle_id != self._applied_cycle
                    and self._reason in {"initiate_seeking", "continue_seeking"})
        reason = self._reason if wnm.primary_source_state is self._basis else "not_the_prepared_feeding_source"
        return PrimitiveApplicabilityV1(self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
                                        0, 50 if eligible else 0, 0, 0, 0, () if eligible else (reason,), (reason,), self.primitive_id)

    def apply(
        self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int,
    ) -> SeekNippleApplicationV1:
        """Transform the selected mouth/detail relation before any bodily authorization."""
        current = self.evaluate_applicability(wnm, cycle_id=cycle_id)
        if current != applicability or not current.eligible:
            raise ValueError("seeking application requires the current eligible Navigation selection")
        basis = self._basis
        if basis is None or basis.mouth_position is None or basis.detail_position is None:
            raise RuntimeError("selected seeking source lost its paired geometry")
        mouth, detail = basis.mouth_position, basis.detail_position
        task = self._task or SeekNippleTaskV1(f"seek_nipple:{basis.stream.generation}:{cycle_id}", basis.seed.detail_region_id,
                                             cycle_id, basis.cutoff_tick)
        horizon = min(8, task.started_tick + _MAX_TICKS - basis.cutoff_tick)
        if horizon < 1:
            raise ValueError("seeking has no remaining physical task authority")
        distance = math.hypot(detail.x - mouth.x, detail.y - mouth.y)
        extent = min(0.15, 0.025 * horizon, distance)
        predicted = NavPointV1(mouth.x + (detail.x - mouth.x) * extent / distance, mouth.y + (detail.y - mouth.y) * extent / distance)
        app_id = f"seek_nipple_application:{basis.stream.generation}:{cycle_id}"
        relations = ("MOUTH:bounded_toward_represented_feeding_detail", "DETAIL:original_scene_anchor", "mouth_detail_separation:decrease")
        pnm = ProjectedNavMapV1(f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id, relations,
                               "later corresponding mouth/detail acquisition; conditional approach, not contact", cycle_id + 1, cycle_id + 2)
        request = OralReachRequestV1(TargetOriginV1(basis.stream, task.task_id, app_id, f"seek_nipple_envelope:{basis.stream.generation}:{cycle_id}"),
                                     basis.source_map_ref, task.region_id, horizon, "selected_seek_nipple")
        projection = SeekNipplePreviewV1(pnm, basis, task.task_id, task.region_id, detail, predicted, horizon,
                                        outcome_consumer_enabled=self.profile.outcomes_enabled)
        next_task = replace(task, applications=task.applications + 1)
        result = SeekNippleApplicationV1(app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
                                         ("feeding:limited_mouth_detail_approach",), relations, pnm.observation_condition,
                                         TaskActionV1(f"transport:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None,
                                         next_task, request, projection)
        if self.profile.influence_enabled:
            self.source.retain_influence(task.task_id, cycle_id=cycle_id, expires_at_tick=basis.cutoff_tick + horizon)
        self._task, self._applied_cycle = next_task, cycle_id
        self._history.append(result)
        return result

    def authorized(self, application: SeekNippleApplicationV1, targets: tuple[CommittedBodyTargetV1, ...]) -> None:
        """Retain only this original application's actual bounded oral authorization."""
        if (not self._history or application is not self._history[-1] or self._authorized_cycle == self._applied_cycle
                or application.cycle_id != self._applied_cycle):
            raise ValueError("seeking authorization must answer its original current application once")
        if not isinstance(targets, tuple) or len(targets) > 1:
            raise ValueError("seeking can bind at most one oral target")
        if any(not isinstance(target, CommittedBodyTargetV1) or target.target.kind is not SensorimotorTargetKindV1.ORAL_REACH
               or target.target.origin != application.contribution.origin for target in targets):
            raise ValueError("target does not belong to the selected seeking application")
        self._target = targets[0] if targets else None
        self._authorized_cycle = self._applied_cycle
