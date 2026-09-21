#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""A small persistent Follow-Mom IP using the accepted target/hand-off hierarchy.

The operation is developmentally supplied, not learned or a wrapper around the
legacy FollowMom policy. Its situation comes from one selected MOM source. Each
application supplies a limited source-relative approach and a separate sparse
PNM. BodyMap independently grants or withholds translation; local execution
follows only that target. No method reads a provider, drives a motor or chooses
another source. Missing localization does not become exact pursuit from memory.

This first maternal slice uses a twenty-opportunity/eighty-tick task and existing
eight-tick local targets. Adequate proximity is 0.50 m; a 0.48-m approach aim gives
a declared margin against the unchanged 0.01-m local motor tolerance. Completion
requires three distinct current focal acquisitions spanning eight physical ticks.
These are fixed engineering choices, not biological constants. Task PNM outcome
interpretation and the combined stand-to-follow qualification remain separate.
"""

from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorFeedbackV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import VisualApproachRequestV1
from nca8_executive import WorkingNavMapStateV1
from nca8_maternal import MaternalNavMapStateV1, MaternalSeedV1, MaternalSourceV1
from nca8_prediction import MaternalApproachPreviewV1, ProjectedNavMapV1
from nca8_primitives import PrimitiveApplicationV1, PrimitiveApplicabilityV1, PrimitiveKindV1, TaskActionKindV1, TaskActionV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, CommittedBodyTargetV1, LocalTargetReportV1, TargetOriginV1

__version__ = "0.4.0"
__all__ = ["FollowMomProfileV1", "FollowMomTaskV1", "FollowMomApplicationV1", "FollowMomAssessmentV1", "FollowMomIPV1", "__version__"]


@dataclass(frozen=True, slots=True)
class FollowMomProfileV1:
    """Explicit first maternal profile; existing experiments opt in to nothing.

    The seed is an assumed initial association. Association, recognition, spatial
    contribution, operation enablement and selected-operation influence are
    independently controllable. None of these switches changes physical motion,
    support criteria, local feedback or the inherited task/execution time limits.
    """

    seed: MaternalSeedV1 = MaternalSeedV1()
    association_enabled: bool = True
    recognition_enabled: bool = True
    spatial_enabled: bool = True
    following_enabled: bool = True
    influence_enabled: bool = True
    outcomes_enabled: bool = False
    prediction_comparison_enabled: bool = True
    outcome_attention_enabled: bool = False

    def __post_init__(self) -> None:
        if not isinstance(self.seed, MaternalSeedV1):
            raise TypeError("Follow-Mom requires a declared initial association")
        if not all(isinstance(flag, bool) for flag in (self.association_enabled, self.recognition_enabled, self.spatial_enabled,
                                                       self.following_enabled, self.influence_enabled, self.outcomes_enabled,
                                                       self.prediction_comparison_enabled, self.outcome_attention_enabled)):
            raise TypeError("maternal profile switches must be Boolean")
        if self.outcome_attention_enabled and not self.outcomes_enabled:
            raise ValueError("maternal outcome Attention requires the canonical maternal correspondence consumer")
        if not self.outcomes_enabled and not self.prediction_comparison_enabled:
            raise ValueError("disable maternal prediction comparison only inside the opt-in correspondence profile")


@dataclass(frozen=True, slots=True)
class FollowMomTaskV1:
    """One task episode, not one sample, motor target or successful local report."""

    task_id: str
    region_id: str
    started_cycle: int
    started_tick: int
    applications: int = 0
    status: str = "active"

    def __post_init__(self) -> None:
        if not isinstance(self.task_id, str) or not 1 <= len(self.task_id) <= 100 or not self.task_id.isascii():
            raise ValueError("Follow-Mom task identity must be bounded text")
        MaternalSeedV1(self.region_id)
        # Exact built-in integers exclude booleans and integer subclasses from task counters.
        for value, minimum in ((self.started_cycle, 1), (self.started_tick, 0)):
            # pylint: disable-next=unidiomatic-typecheck
            if type(value) is not int or not minimum <= value < 2**63 - 80:
                raise ValueError("Follow-Mom start must be a bounded cycle/tick")
        # pylint: disable-next=unidiomatic-typecheck
        if type(self.applications) is not int or not 0 <= self.applications <= 20:
            raise ValueError("Follow-Mom cannot exceed twenty selected applications")
        if self.status not in {"active", "completed", "cancelled", "budget_exhausted", "identity_contradicted",
                                "target_unavailable", "execution_exhausted"}:
            raise ValueError("unknown Follow-Mom task disposition")

    def as_dict(self) -> dict[str, object]:
        """Describe unchanged original bounds without retaining a stale destination."""
        return {"task_id": self.task_id, "region_id": self.region_id, "started_cycle": self.started_cycle,
                "started_tick": self.started_tick, "applications": self.applications, "status": self.status,
                "maximum_focal_opportunities": 20, "maximum_physical_ticks": 80,
                "adequate_separation_metres": 0.5, "approach_aim_metres": 0.48,
                "causal_credit": "not_established", "learned_operation": False}


@dataclass(frozen=True, slots=True)
class FollowMomApplicationV1(PrimitiveApplicationV1):
    """One selected, bounded contribution with original associated-source anchors."""

    task: FollowMomTaskV1
    contribution: VisualApproachRequestV1
    projection: MaternalApproachPreviewV1

    def __post_init__(self) -> None:
        PrimitiveApplicationV1.__post_init__(self)
        if not isinstance(self.task, FollowMomTaskV1) or not isinstance(self.contribution, VisualApproachRequestV1):
            raise TypeError("Follow-Mom application requires its task and typed contribution")
        if not isinstance(self.projection, MaternalApproachPreviewV1):
            raise TypeError("Follow-Mom application requires a maternal PNM")
        origin = self.contribution.origin
        # Keep this ordered identity rejection guard intact; all original links must agree.
        # pylint: disable-next=too-many-boolean-expressions
        if (origin.application_id != self.application_id or origin.task_id != self.task.task_id
                or self.projection.pnm.application_id != self.application_id or self.projection.task_id != self.task.task_id
                or self.projection.region_id != self.task.region_id or self.contribution.region_id != self.task.region_id
                or self.contribution.source_map_ref != self.projection.basis.source_map_ref
                or self.contribution.origin_status != "selected_follow_mom"):
            raise ValueError("Follow-Mom contribution and PNM must preserve the same original task")

    def as_dict(self) -> dict[str, object]:
        """Export without promoting selected movement to observed proximity or learning."""
        return {**PrimitiveApplicationV1.as_dict(self), "task": self.task.as_dict(),
                "contribution": self.contribution.as_dict(), "projection": self.projection.as_dict(),
                "origin_status": "developmental_follow_mom_with_seeded_association"}


@dataclass(frozen=True, slots=True)
class FollowMomAssessmentV1:
    """One immutable current task disposition, not a prediction-outcome verdict."""

    task: FollowMomTaskV1 | None
    reason: str
    supported_samples: tuple[MaternalNavMapStateV1, ...]
    local_target_busy: bool
    cancel_previous: bool
    outcome_consumer_enabled: bool = False
    support_recovery_pending: bool = False

    def as_dict(self) -> dict[str, object]:
        """Export distinct observed proximity, local continuation and uncertain credit."""
        return {"task": None if self.task is None else self.task.as_dict(), "reason": self.reason,
                "supported_samples": [{"sample_id": item.sample_id, "event_tick": item.event_tick, "separation": item.separation}
                                      for item in self.supported_samples],
                "local_target_busy": self.local_target_busy, "cancel_previous": self.cancel_previous,
                **({"support_recovery_pending": True} if self.support_recovery_pending else {}),
                "task_pnm_correspondence": "separate_maternal_consumer" if self.outcome_consumer_enabled else "deferred_maternal_qualification",
                "durable_updates": 0}


class FollowMomIPV1:
    """Choose repeated limited approaches only through ordinary Navigation selection.

    Preparing an opportunity updates finite task lifetime, local-report readiness
    and simple current-proximity evidence, not a second demanding operation.
    Applicability is read-only. Applying the chosen operation computes a source-
    dependent future relation, consumes one application, and can request source
    relevance. It grants no actuator rights. Completed/failed tasks are sticky;
    resetting requires a fresh owner, not another observation of the same target.
    """

    primitive_id = "ip:follow_mom"
    primitive_kind = PrimitiveKindV1.INSTINCTIVE

    def __init__(self, source: MaternalSourceV1, profile: FollowMomProfileV1) -> None:
        if not isinstance(source, MaternalSourceV1) or not isinstance(profile, FollowMomProfileV1):
            raise TypeError("Follow-Mom requires the owning association and declared profile")
        self.source, self.profile = source, profile
        self._task: FollowMomTaskV1 | None = None
        self._basis: MaternalNavMapStateV1 | None = None
        self._target: CommittedBodyTargetV1 | None = None
        self._support_available = False
        self._support_recovery_pending = False
        self._target_busy = False
        self._applied_cycle = 0
        self._authorized_cycle = 0
        self._cancelled = False
        self._reason = "not_prepared"
        self._cancel_previous = False
        self._supported: list[MaternalNavMapStateV1] = []
        self._history: deque[FollowMomApplicationV1] = deque(maxlen=8)

    @property
    def task(self) -> FollowMomTaskV1 | None:
        """Read the actual persistent task without restarting its original budgets."""
        return self._task

    @property
    def reason(self) -> str:
        """Report the actual current disposition independently of task success."""
        return self._reason

    @property
    def cancel_previous(self) -> bool:
        """Request revocation only of this task's prior translation, not another task."""
        return self._cancel_previous

    def snapshot(self) -> dict[str, object]:
        """Read current task and bounded evidence; diagnostics cannot run cognition."""
        return {**self.assessment().as_dict(), "retained_applications": len(self._history)}

    def assessment(self) -> FollowMomAssessmentV1:
        """Freeze the currently computed disposition without rerunning any cognitive work."""
        return FollowMomAssessmentV1(self._task, self._reason, tuple(self._supported), self._target_busy, self._cancel_previous,
                                     self.profile.outcomes_enabled, self._support_recovery_pending)

    def retained_counts(self) -> dict[str, int]:
        """Measure finite task, evidence and history storage independent of the trace."""
        return {"tasks": int(self._task is not None), "source_bases": int(self._basis is not None),
                "local_targets": int(self._target is not None), "supported_samples": len(self._supported),
                "applications": len(self._history)}

    def history(self) -> tuple[FollowMomApplicationV1, ...]:
        """Return at most eight original application records, never executable replay."""
        return tuple(self._history)

    def cancel(self) -> None:
        """End this task without deleting the maternal association or observed effects."""
        if self._task is not None and self._task.status == "active":
            self._task = replace(self._task, status="cancelled")
        self._reason = "cancelled"
        self._cancelled = True
        self.source.clear_influence()

    def _assess_proximity(self, basis: MaternalNavMapStateV1) -> None:
        """Accumulate distinct focal evidence, never cached values or motor achievement."""
        distance = basis.separation
        if not self._support_available or distance is None or distance > 0.5 + 1e-12:
            self._supported.clear()
            return
        if self._supported and basis.sample_id == self._supported[-1].sample_id:
            return
        if self._supported and (basis.frame_id != self._supported[-1].frame_id or basis.event_tick is None
                                or basis.event_tick - (self._supported[-1].event_tick or 0) > 8):
            self._supported.clear()
        self._supported.append(basis)
        if len(self._supported) > 3:
            self._supported = [self._supported[0], *self._supported[-2:]]
        first = self._supported[0].event_tick
        if len(self._supported) == 3 and first is not None and basis.event_tick is not None and basis.event_tick - first >= 8:
            if self._task is not None:
                self._task = replace(self._task, status="completed")
                self.source.clear_influence()

    def prepare(
        self, basis: MaternalNavMapStateV1, feedback: MotorFeedbackV1 | None, *, reports: tuple[LocalTargetReportV1, ...] = (),
        support_recovery_pending: bool = False,
    ) -> None:
        """Update the current eligible opportunity before Attention and Navigation.

        The body check is a task precondition only; BodyMap repeats its protected
        permission check during E. Reports must belong to the same body stream
        and cannot come from future work. Missing visual input breaks proximity
        proof and requests cancellation of this task's old exact pursuit. Identity
        and a widening possible region stay in the sensory association owner.

        support_recovery_pending is an explicit unfinished support-task constraint
        supplied by the integrated core, not an evaluator's stood-up milestone.
        It withholds applicability without selecting another IP or deleting Mom.
        The core releases this constraint only after the support-completion
        handoff has had an opportunity to revoke the old lower permissions.
        Existing supported-start profiles leave it false.
        """
        if not isinstance(support_recovery_pending, bool):
            raise TypeError("support_recovery_pending must be Boolean")
        if not isinstance(basis, MaternalNavMapStateV1) or basis is not self.source.current:
            raise ValueError("Follow-Mom preparation requires its owner's actual current basis")
        if self._basis is not None and basis.applied_cycle <= self._basis.applied_cycle:
            raise ValueError("Follow-Mom opportunity cannot be prepared twice")
        if feedback is not None:
            if not isinstance(feedback, MotorFeedbackV1):
                raise TypeError("body evidence must be canonical feedback or None")
            feedback.validate_available(stream=basis.stream, at_tick=basis.cutoff_tick)
        if not isinstance(reports, tuple) or len(reports) > 2 or any(not isinstance(item, LocalTargetReportV1) for item in reports):
            raise TypeError("supply at most two immutable local reports")
        if any(item.committed_target.target.origin.stream != basis.stream or item.reported_tick > basis.cutoff_tick for item in reports):
            raise ValueError("local report is foreign or not yet available")
        if any(item.committed_target is not self._target and self._target is not None
               and item.committed_target.target.target_id == self._target.target.target_id for item in reports):
            raise ValueError("a copied local target cannot replace the original authorized record")
        self._basis = basis
        self._support_recovery_pending = support_recovery_pending
        self._support_available = bool(
            not support_recovery_pending and
            feedback is not None and basis.cutoff_tick - feedback.event_tick <= 2 and feedback.support_contact is True
            and feedback.body_tilt_degrees is not None and abs(feedback.body_tilt_degrees) <= 12.0
            and feedback.useful_loading is not None and feedback.useful_loading >= 0.75
            and feedback.destabilization is not None and feedback.destabilization <= 0.15
        )
        report = next((item for item in reports if item.committed_target is self._target), None)
        self._target_busy = bool(
            self._target is not None and basis.cutoff_tick < self._target.expires_at_tick
            and (report is not None and report.disposition.value in {"pending", "active", "partial"}
                 or report is None and not reports)
        )
        owned_live = self._target is not None and self._target_busy
        task = self._task
        if task is not None and task.status == "active":
            if basis.identity_status == "contradicted":
                self._task = replace(task, status="identity_contradicted")
            elif basis.identity_status == "expired":
                self._task = replace(task, status="target_unavailable")
            elif basis.applied_cycle - task.started_cycle >= 20 or basis.cutoff_tick - task.started_tick >= 80:
                self._task = replace(task, status="budget_exhausted")
            elif report is not None and (report.disposition.value in {"blocked", "expired"}
                                         or report.reason == "anomalous_correction_budget_exhausted"):
                self._task = replace(task, status="execution_exhausted")
            else:
                self._assess_proximity(basis)
        if self._task is not None and self._task.status != "active":
            self._reason = self._task.status
            self.source.clear_influence()
        elif self._cancelled:
            self._reason = "cancelled"
        elif not self.profile.following_enabled:
            self._reason = "following_disabled"
        elif not basis.action_localized:
            self._reason = "maternal_location_unavailable"
        elif support_recovery_pending:
            self._reason = "support_recovery_pending"
        elif not self._support_available:
            self._reason = "body_support_unavailable"
        elif basis.separation is not None and basis.separation <= 0.5 + 1e-12:
            self._reason = "adequate_proximity_pending_dwell" if self._task is not None else "already_near_no_task"
        # Each rate needs its own missingness guard before the joint motion test.
        # pylint: disable-next=too-many-boolean-expressions
        elif (basis.separation_rate is not None and basis.separation_rate < -0.05
              and basis.target_closing_rate is not None and basis.target_closing_rate > 0.05
              and basis.self_closing_rate is not None and abs(basis.self_closing_rate) <= 0.02):
            self._reason = "independently_approaching_target_wait"
        elif self._target_busy:
            self._reason = "authorized_local_contribution_continues"
        else:
            self._reason = "initiate_following" if self._task is None else "continue_following"
        self._cancel_previous = owned_live and self._reason not in {"authorized_local_contribution_continues", "initiate_following", "continue_following"}

    def evaluate_applicability(self, wnm: WorkingNavMapStateV1, *, cycle_id: int) -> PrimitiveApplicabilityV1:
        """Query only the actual current WNM; this does not start or spend a task."""
        # A Boolean or integer subclass must not masquerade as the canonical cycle identity.
        # pylint: disable-next=unidiomatic-typecheck
        if not isinstance(wnm, WorkingNavMapStateV1) or type(cycle_id) is not int or wnm.refreshed_cycle != cycle_id:
            raise ValueError("Follow-Mom requires a current focal opportunity")
        basis = wnm.primary_source_state
        eligible = (isinstance(basis, MaternalNavMapStateV1) and basis is self._basis
                    and cycle_id != self._applied_cycle and self._reason in {"initiate_following", "continue_following"})
        reason = self._reason if basis is self._basis else "not_the_prepared_maternal_source"
        return PrimitiveApplicabilityV1(self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id, eligible,
                                        0, 50 if eligible else 0, 0, 0, 0, () if eligible else (reason,), (reason,), self.primitive_id)

    def apply(
        self, wnm: WorkingNavMapStateV1, applicability: PrimitiveApplicabilityV1, *, cycle_id: int,
    ) -> FollowMomApplicationV1:
        """Compute a bounded toward-Mom contribution and PNM before motor permission."""
        current = self.evaluate_applicability(wnm, cycle_id=cycle_id)
        if current != applicability or not current.eligible:
            raise ValueError("Follow-Mom requires this opportunity's eligible Navigation selection")
        basis = wnm.primary_source_state
        if not isinstance(basis, MaternalNavMapStateV1) or basis.self_position is None or basis.target_position is None:
            raise ValueError("selected maternal source lacks current geometry")
        task = self._task or FollowMomTaskV1(f"follow_mom:{basis.stream.generation}:{cycle_id}", basis.seed.region_id, cycle_id, basis.cutoff_tick)
        remaining = task.started_tick + 80 - basis.cutoff_tick
        if remaining < 1:
            raise ValueError("no remaining physical task authority")
        horizon = min(8, remaining)
        dx, dy = basis.target_position.x - basis.self_position.x, basis.target_position.y - basis.self_position.y
        distance = math.hypot(dx, dy)
        extent = min(0.25, distance - 0.48)
        predicted = NavPointV1(basis.self_position.x + dx * extent / distance, basis.self_position.y + dy * extent / distance)
        app_id = f"follow_mom_application:{basis.stream.generation}:{cycle_id}"
        expected = ("SELF:bounded_toward_maternal_target", "MOM:original_target_anchor", "separation:expected_decrease")
        pnm = ProjectedNavMapV1(f"pnm:{app_id}", app_id, self.primitive_id, wnm.working_id, cycle_id,
                               expected, "later corresponding maternal acquisition; conditional proximity change", cycle_id + 1, cycle_id + 2)
        contribution = VisualApproachRequestV1(
            TargetOriginV1(basis.stream, task.task_id, app_id, f"follow_mom_envelope:{basis.stream.generation}:{cycle_id}"),
            basis.source_map_ref, task.region_id, 0.48, 0.25, "selected_follow_mom",
        )
        projection = MaternalApproachPreviewV1(pnm, basis, task.task_id, task.region_id, basis.target_position, predicted, horizon,
                                               self.profile.outcomes_enabled)
        next_task = replace(task, applications=task.applications + 1)
        result = FollowMomApplicationV1(app_id, self.primitive_id, self.primitive_kind, cycle_id, wnm.working_id,
                                       ("maternal:limited_proximity_contribution",), expected, pnm.observation_condition,
                                       TaskActionV1(f"transport:{app_id}", cycle_id, TaskActionKindV1.NO_ACTION, app_id, ()), None,
                                       next_task, contribution, projection)
        if self.profile.influence_enabled:
            self.source.retain_influence(task.task_id, cycle_id=cycle_id, expires_at_tick=basis.cutoff_tick + horizon)
        self._task, self._applied_cycle = next_task, cycle_id
        self._history.append(result)
        return result

    def authorized(self, application: FollowMomApplicationV1, targets: tuple[CommittedBodyTargetV1, ...]) -> None:
        """Remember actual E permission, not an assumed effect of primitive application."""
        if (not self._history or application is not self._history[-1] or application.cycle_id != self._applied_cycle
                or self._authorized_cycle == self._applied_cycle):
            raise ValueError("authorization must answer the original selected maternal application")
        if not isinstance(targets, tuple) or len(targets) > 1:
            raise ValueError("Follow-Mom binds at most one translation resource")
        if any(not isinstance(target, CommittedBodyTargetV1) or not isinstance(target.target, BodyTranslationTargetV1)
               or target.target.origin != application.contribution.origin for target in targets):
            raise ValueError("authorized target does not belong to this maternal application")
        self._target = targets[0] if targets else None
        self._authorized_cycle = self._applied_cycle
