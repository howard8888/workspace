#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H6-A: selected Righting, finite target installation and returning sensing.

IntegratedRightingCoreV1 owns only focal cognition and an internal handoff. It
uses the existing A-F scheduler and H5 source/selection/projection stages; it
never calls a physical provider. IntegratedRightingTrialV1 is the separate
synchronous outer driver. It consumes the closed handoff once, installs H3
targets in H4, and calls H2 once per lower tick. Four 0.05-second updates form
the nominal interval between focal opportunities. These are engineering units,
not neural timing claims. There are no threads, RNG calls or durable learners.

A task outlives a target. Every new target envelope has its own authorization;
no-new-output preserves only existing finite rights. PNM, target, local report
and physical evidence retain distinct roles. H6-A reports current adequacy and
local results, not supported task dwell, task-PNM verdicts or causal credit.
The separately enabled P16-1G-A profile adds task dwell and original endpoint
correspondence in the same core/driver; the retained H6 profiles are unchanged.
The opt-in 1G-B source route adds one demanding interpretation before a later
response reconsideration. Protected lower execution still respects its original
lease. The opt-in 1G-C source-owned hook maintains bounded eligibility and
reconciles available evidence at F, with zero durable updates. No profile calls
the legacy/A0 provider, and the learning inventory is never executed as a loop.

P16-2B-C explicitly permits both domain-specific outcome consumers in one stream.
The outer driver routes support target reports to Righting and shared acquisitions
with their original identity to both consumers; it never converts a translation
into a Righting command. An unfinished recovery constrains Follow-Mom applicability.
A terminal Righting transition retires its rights once; the historical record
cannot cancel a later independently authorized task. No task-order list is added.
"""

from __future__ import annotations

from collections import deque
from collections.abc import Sequence
from dataclasses import dataclass, replace

from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1, admit_motor_feedback_batch_v1
from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, PlanarWorldProfileV1, PlanarWorldStateV1
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_body_targets import BodyAxisCapabilityV1, BodyTargetReservationV1, BodyTranslationCapabilityV1
from nca8_translation import TranslationFixtureV1, TranslationApplicationV1, SuppliedTranslationOperationV1
from nca8_visual import VisualSourceV1, VisualNavMapStateV1, VisualObservationV1
from nca8_maternal import MaternalSourceV1, MaternalNavMapStateV1
from nca8_followmom import FollowMomProfileV1, FollowMomIPV1, FollowMomApplicationV1, FollowMomAssessmentV1
from nca8_maternal_outcomes import MaternalIntervalEvidenceV1, MaternalOutcomeFrameV1, MaternalOutcomeRuntimeV1
from nca8_contracts import CircuitResultV1, CircuitTimingV1, CycleCommitmentV1, CyclePhase
from nca8_executive import AttentionBidV1
from nca8_handoff import Nca8HandoffReceiptV1, Nca8InternalHandoffV1, Nca8MotorEnvelopeV1, Nca8PhaseEDispatchV1
from nca8_outcomes import (
    RightingClaimOutcomeV1, RightingClaimRegistrationV1, RightingIntervalEvidenceV1, RightingOutcomeRuntimeV1,
    RightingTaskAssessmentV1,
)
from nca8_righting import RightingApplicationV1, RightingContextV1
from nca8_outcome_attention import RightingMismatchRequestV1
from nca8_learning import LearningPhaseFReportV1
from nca8_runtime import Nca8RightingPreviewSessionV1, RightingPreviewResultV1
from nca8_scheduler import CircuitPollSourceV1, Nca8DeterministicSchedulerV1, SchedulerCycleSnapshotV1
from nca8_sensorimotor import LocalControlEventV1, SensorimotorExecutorV1, SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import BodyTranslationTargetV1, FocalMotorEvidenceV1, LocalTargetReportV1
from nca8_trace import Nca8TraceBufferV1

__version__ = "0.9.0"
__all__ = [
    "IntegratedRightingCycleV1", "IntegratedRightingCoreV1", "IntegratedRightingTrialV1", "__version__",
]


def _bounded_count(value: int, name: str, minimum: int, maximum: int) -> int:
    """Validate caller-supplied finite budgets without coercing Boolean values."""
    if isinstance(value, bool) or not isinstance(value, int) or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer in [{minimum}, {maximum}]")
    return value


@dataclass(frozen=True, slots=True)
class IntegratedRightingCycleV1:
    """One closed focal decision, before outer installation or later body movement.

    calculation is the shared preauthorization computation, not another cognitive
    cycle or another WNM. receipt is the historical ready snapshot at closure.
    Later consumption/installation is reported separately by the outer owner.
    Every retained object is immutable; as_dict() grants no restorable rights.
    """

    calculation: RightingPreviewResultV1
    commitment: CycleCommitmentV1
    receipt: Nca8HandoffReceiptV1
    reservations: tuple[BodyTargetReservationV1, ...]
    scheduler: SchedulerCycleSnapshotV1
    local_reports: tuple[LocalTargetReportV1, ...]
    local_events: tuple[LocalControlEventV1, ...]
    task_outcome: RightingTaskAssessmentV1 | None = None
    claim_outcomes: tuple[RightingClaimOutcomeV1, ...] = ()
    claim_registration: RightingClaimRegistrationV1 | None = None
    outcome_requests_created: tuple[RightingMismatchRequestV1, ...] = ()
    outcome_requests_pending: tuple[RightingMismatchRequestV1, ...] = ()
    learning_report: LearningPhaseFReportV1 | None = None
    visual_source: VisualNavMapStateV1 | None = None
    maternal_source: MaternalNavMapStateV1 | None = None
    maternal_task: FollowMomAssessmentV1 | None = None
    maternal_correspondence: MaternalOutcomeFrameV1 | None = None

    @property
    def status(self) -> str:
        """Separate safe pending/refusal/local reporting from task completion."""
        if self.reservations:
            proposal = self.calculation.proposal
            return "partial_authorization" if proposal is not None and proposal.withheld else "authorized_pending_execution"
        if self.calculation.proposal is not None:
            return "refused_no_usable_target"
        return self.calculation.source_status

    def as_dict(self) -> dict[str, object]:
        """Export the complete causal linkage, without interpreting a task outcome."""
        return {
            "preauthorization_calculation": self.calculation.as_dict(), "commitment": self.commitment.as_dict(),
            "core_closed_receipt": self.receipt.as_dict(), "dispatch": self.receipt.dispatch.as_dict(),
            "scheduler": self.scheduler.as_dict(), "status": self.status,
            "earlier_local_reports": [item.as_dict() for item in self.local_reports],
            "earlier_local_events": [item.as_dict() for item in self.local_events],
            "task_completion": (self.maternal_task.task.status if self.maternal_task is not None and self.maternal_task.task is not None else
                                self.task_outcome.status if self.task_outcome is not None else
                                "not_established_maternal" if self.maternal_source is not None else
                                "not_established_visual_fixture" if self.visual_source is not None else "not_established_H6A"),
            "durable_learning_updates": 0,
            **({"task_outcome": self.task_outcome.as_dict(),
                "claim_outcomes": [item.as_dict() for item in self.claim_outcomes],
                "claim_registration": self.claim_registration.as_dict() if self.claim_registration is not None else None}
               if self.task_outcome is not None else {}),
            **({"outcome_requests_created": [item.as_dict() for item in self.outcome_requests_created],
                "outcome_requests_pending": [item.as_dict() for item in self.outcome_requests_pending]}
               if self.calculation.outcome_allocation is not None else {}),
            **({"learning_reconciliation": self.learning_report.as_dict()} if self.learning_report is not None else {}),
            **({"visual_source": self.visual_source.as_dict(), "operation_scope": "developmental_follow_mom" if self.maternal_source is not None else "supplied_translation_fixture"}
               if self.visual_source is not None else {}),
            **({"maternal_source": self.maternal_source.as_dict(),
                "maternal_task": self.maternal_task.as_dict() if self.maternal_task is not None else None}
               if self.maternal_source is not None else {}),
            **({"maternal_correspondence": self.maternal_correspondence.as_dict()} if self.maternal_correspondence is not None else {}),
        }


class IntegratedRightingCoreV1:
    """Run one actual A-F focal core with no environment or local-executor call.

    The immutable feedback sidecar is bound to one scheduler ingress result.
    Its result timing describes publication of the focal summary, not the
    physical acquisition: original event/availability ticks remain in the typed
    evidence and payload. Future sensing cannot replace that frozen sidecar.
    Exceptions after processing starts stop this core; reset creates fresh owners.
    """

    def __init__(
        self, stream: MotorStreamRefV1, *, context: RightingContextV1 | None = None,
        capabilities: tuple[BodyAxisCapabilityV1, ...] | None = None,
        righting_enabled: bool = True, influence_enabled: bool = True,
        handoff_enabled: bool = True, trace_capacity: int = 256,
        orientation_mapping_sign: int = 1, task_pnm_consumer_enabled: bool = True,
        task_outcomes_enabled: bool = False, task_prediction_comparison_enabled: bool = True,
        task_outcome_attention_enabled: bool = False, task_learning_hook_enabled: bool = False,
        learning_diagnostic_capacity: int = 32,
        translation_fixture: TranslationFixtureV1 | None = None,
        translation_capability: BodyTranslationCapabilityV1 | None = None, translation_mapping_sign: int = 1,
        follow_mom_profile: FollowMomProfileV1 | None = None,
        stand_follow_enabled: bool = False, righting_target_inset_degrees: float = 0.0,
    ) -> None:
        _bounded_count(trace_capacity, "trace_capacity", 1, 4096)
        if not all(isinstance(flag, bool) for flag in (
            task_outcomes_enabled, task_prediction_comparison_enabled, task_outcome_attention_enabled, task_learning_hook_enabled,
        )):
            raise TypeError("task outcome options must be Boolean")
        if task_outcome_attention_enabled and not task_outcomes_enabled:
            raise ValueError("task-outcome Attention requires the 1G-A correspondence consumer")
        if task_learning_hook_enabled and not task_outcomes_enabled:
            raise ValueError("the no-learning hook requires the 1G-A correspondence consumer")
        _bounded_count(learning_diagnostic_capacity, "learning_diagnostic_capacity", 1, 32)
        if translation_fixture is not None and not isinstance(translation_fixture, TranslationFixtureV1):
            raise TypeError("translation requires its explicit supplied-operation fixture")
        if follow_mom_profile is not None and not isinstance(follow_mom_profile, FollowMomProfileV1):
            raise TypeError("maternal operation requires its explicit profile")
        if follow_mom_profile is not None and translation_fixture is not None:
            raise ValueError("supplied translation and developmental Follow-Mom are separate experiment profiles")
        visual_profile = translation_fixture if translation_fixture is not None else follow_mom_profile
        if not isinstance(stand_follow_enabled, bool):
            raise TypeError("stand_follow_enabled must be Boolean")
        if stand_follow_enabled and (follow_mom_profile is None or not follow_mom_profile.outcomes_enabled or not task_outcomes_enabled):
            raise ValueError("stand-follow requires separate Righting and maternal correspondence consumers")
        if visual_profile is not None and task_outcomes_enabled and not stand_follow_enabled:
            raise ValueError("Righting-only task outcome/learning consumers cannot score visual or maternal translation")
        self.stand_follow_enabled = stand_follow_enabled
        if visual_profile is None and (translation_capability is not None or translation_mapping_sign != 1):
            raise ValueError("translation capability/calibration requires an opt-in visual operation")
        self.translation = None if translation_fixture is None else SuppliedTranslationOperationV1(translation_fixture)
        self.visual = None if visual_profile is None else VisualSourceV1(
            stream, recognition_enabled=visual_profile.recognition_enabled, spatial_enabled=visual_profile.spatial_enabled,
        )
        self.maternal = None if follow_mom_profile is None else MaternalSourceV1(
            stream, follow_mom_profile.seed, enabled=follow_mom_profile.association_enabled,
        )
        self.follow_mom = (FollowMomIPV1(self.maternal, follow_mom_profile)
                           if self.maternal is not None and follow_mom_profile is not None else None)
        self.maternal_outcomes = (MaternalOutcomeRuntimeV1(stream, compare_predictions=follow_mom_profile.prediction_comparison_enabled)
                                  if follow_mom_profile is not None and follow_mom_profile.outcomes_enabled else None)
        self.outcomes = RightingOutcomeRuntimeV1(stream, compare_predictions=task_prediction_comparison_enabled) if task_outcomes_enabled else None
        self.cognition = Nca8RightingPreviewSessionV1(
            stream, context=context, capabilities=capabilities,
            righting_enabled=righting_enabled, influence_enabled=influence_enabled,
            orientation_mapping_sign=orientation_mapping_sign, task_pnm_consumer_enabled=task_pnm_consumer_enabled,
            outcome_attention_enabled=task_outcome_attention_enabled,
            additional_primitives=tuple(item for item in (self.translation, self.follow_mom) if item is not None),
            visual_preview_enabled=self.visual is not None, translation_capability=translation_capability,
            translation_mapping_sign=translation_mapping_sign, monitor_support_completion=stand_follow_enabled,
            righting_target_inset_degrees=righting_target_inset_degrees,
        )
        if task_learning_hook_enabled:
            self.cognition.sensory.configure_learning_hook(stream, diagnostic_capacity=learning_diagnostic_capacity)
        self.handoff = Nca8InternalHandoffV1(generation=stream.generation, enabled=handoff_enabled)
        self.scheduler = Nca8DeterministicSchedulerV1()
        self.trace = Nca8TraceBufferV1(trace_capacity)
        self.last_result: IntegratedRightingCycleV1 | None = None
        self.last_commitment: CycleCommitmentV1 | None = None
        self._running = False
        self._fault: str | None = None

    @property
    def running(self) -> bool:
        """Expose only the boundary guard, never a physical clock."""
        return self._running

    @property
    def fault(self) -> str | None:
        """Return the sticky stop reason; diagnostic reads do not clear it."""
        return self._fault

    def stop(self, reason: str) -> None:
        """Invalidate future focal use without changing a past commitment or body.

        The outer owner must separately stop lower execution. An accepted but
        unreleased receipt is cancelled; a consumed receipt cannot be retried.
        """
        if not isinstance(reason, str) or not reason.strip():
            raise ValueError("core stop requires a nonempty reason")
        self._fault = reason[:100]
        if self.maternal_outcomes is not None:
            self.maternal_outcomes.close(reason=self._fault)
        hook = self.cognition.sensory.learning_hook
        if hook is not None:
            hook.close()
        if self.outcomes is not None:
            self.outcomes.reject_uninstalled()
        receipt = self.handoff.receipt
        if receipt is not None and receipt.disposition in {"accepted", "ready"}:
            self.handoff.cancel(receipt, reason=self._fault)

    def run_cycle(
        self, feedback: MotorFeedbackV1 | None, *, cutoff_tick: int,
        context: RightingContextV1 | None = None, competing_bids: Sequence[AttentionBidV1] = (),
        local_reports: tuple[LocalTargetReportV1, ...] = (), local_events: tuple[LocalControlEventV1, ...] = (),
        outcome_intervals: tuple[RightingIntervalEvidenceV1, ...] = (), visual_observation: VisualObservationV1 | None = None,
        maternal_intervals: tuple[MaternalIntervalEvidenceV1, ...] = (),
        visual_bid_priority: tuple[int, int] | None = None,
    ) -> IntegratedRightingCycleV1:
        """Freeze one eligible summary, choose/project/authorize, finish F and close.

        A returned receipt is ready, not consumed. The caller must explicitly
        consume or cancel it before another focal pass. No lower tick runs here.
        Significant local events are read with original identity; this is not the
        deferred task-PNM mismatch-to-Attention route or a learned outcome hook.
        """
        if self._running or self._fault is not None or self.handoff.has_pending_request:
            raise RuntimeError("core is running, stopped, or has an unconsumed handoff")
        _bounded_count(cutoff_tick, "cutoff_tick", 0, 2**63 - 9)
        if self.last_result is not None and cutoff_tick <= self.last_result.calculation.cutoff_tick:
            raise ValueError("a new focal opportunity requires a later physical cutoff")
        if not isinstance(local_reports, tuple) or len(local_reports) > 2 or any(
            not isinstance(item, LocalTargetReportV1) for item in local_reports
        ):
            raise TypeError("supply at most two immutable local reports")
        if not isinstance(local_events, tuple) or len(local_events) > 4 or any(
            not isinstance(item, LocalControlEventV1) for item in local_events
        ):
            raise TypeError("supply at most four immutable local events")
        if any(item.reported_tick > cutoff_tick or item.committed_target.target.origin.stream != self.cognition.stream
               for item in local_reports):
            raise ValueError("local reports are future or foreign")
        if any(item.noticed_tick > cutoff_tick for item in local_events):
            raise ValueError("local events have not occurred at this cutoff")
        if not isinstance(outcome_intervals, tuple) or len(outcome_intervals) > 16:
            raise ValueError("outcome input must be a bounded immutable interval batch")
        if self.outcomes is None and outcome_intervals:
            raise ValueError("outcome input requires the explicit 1G-A profile")
        if not isinstance(maternal_intervals, tuple) or len(maternal_intervals) > 16:
            raise ValueError("maternal intervals require a bounded immutable batch")
        if self.maternal_outcomes is None and maternal_intervals:
            raise ValueError("maternal interval input requires the explicit correspondence profile")
        if visual_bid_priority is not None:
            if self.visual is None or not isinstance(visual_bid_priority, tuple) or len(visual_bid_priority) != 2:
                raise ValueError("priority control needs a configured visual source and two integer ranks")
            for rank in visual_bid_priority:
                _bounded_count(rank, "visual priority component", 0, 1000)
        if self.visual is None and visual_observation is not None:
            raise ValueError("visual input requires its configured source owner")
        if visual_observation is not None:
            if not isinstance(visual_observation, VisualObservationV1):
                raise TypeError("visual input must be an admitted acquisition")
            visual_observation.validate_available(stream=self.cognition.stream, at_tick=cutoff_tick)
        self._running = True
        try:
            return self._run_cycle(
                feedback, tick=cutoff_tick, context=context, competing_bids=competing_bids, reports=local_reports, events=local_events,
                outcome_intervals=outcome_intervals, visual_observation=visual_observation, visual_bid_priority=visual_bid_priority,
                maternal_intervals=maternal_intervals,
            )
        except BaseException:
            self.stop("internal_hierarchy_cycle_failed_no_world_call")
            raise
        finally:
            self._running = False

    def _run_cycle(
        self, feedback: MotorFeedbackV1 | None, *, tick: int, context: RightingContextV1 | None,
        competing_bids: Sequence[AttentionBidV1], reports: tuple[LocalTargetReportV1, ...],
        events: tuple[LocalControlEventV1, ...], outcome_intervals: tuple[RightingIntervalEvidenceV1, ...],
        visual_observation: VisualObservationV1 | None, visual_bid_priority: tuple[int, int] | None,
        maternal_intervals: tuple[MaternalIntervalEvidenceV1, ...],
    ) -> IntegratedRightingCycleV1:
        """Implement the guarded C/D/E owner stages between real scheduler boundaries."""
        cycle = self.scheduler.last_completed_cycle + 1
        previous_support_task = self.cognition.righting.task
        evidence = None if feedback is None else FocalMotorEvidenceV1(feedback, cycle, tick)
        if feedback is not None:
            feedback.validate_available(stream=self.cognition.stream, at_tick=tick)
        ingress = CircuitResultV1.from_mapping(
            result_id=f"motor_summary:{cycle}", source_circuit="motor_summary_ingress", source_sequence=cycle,
            timing=CircuitTimingV1(cycle, cycle, expires_after_cycle=cycle),
            payload={
                "cutoff_tick": tick, "sample_id": feedback.sample_id if feedback is not None else None,
                "physical_event_tick": feedback.event_tick if feedback is not None else None,
                "physical_available_tick": feedback.available_tick if feedback is not None else None,
                **({"visual_sample": visual_observation.sample_id if visual_observation is not None else None,
                    "visual_event": visual_observation.event_tick if visual_observation is not None else None}
                   if self.visual is not None else {}),
                **({"outcome_interval_count": len(outcome_intervals),
                    "outcome_last_interval_tick": outcome_intervals[-1].tick if outcome_intervals else None}
                   if self.outcomes is not None else {}),
                **({"maternal_interval_count": len(maternal_intervals),
                    "maternal_last_interval_tick": maternal_intervals[-1].tick if maternal_intervals else None}
                   if self.maternal_outcomes is not None else {}),
            },
        )
        self.trace.append("hierarchy_cycle", "focal core opened; physical time is held", cycle_id=cycle,
                          details={"cutoff_tick": tick})
        self.scheduler.phase_a_poll_and_stage(cycle, (CircuitPollSourceV1("motor_summary_ingress", lambda _cycle: (ingress,)),), self.trace)
        frozen = self.scheduler.phase_b_freeze_eligible(cycle, self.trace)
        applied = self.scheduler.phase_c_apply_frozen(cycle, self.trace)
        if tuple(item.result_id for item in applied) != (ingress.result_id,):
            raise RuntimeError("the frozen summary sidecar lost its ingress association")
        maternal_owner = self.maternal_outcomes
        maternal_before = maternal_owner.history()[-1].number if maternal_owner is not None and maternal_owner.history() else 0
        if maternal_owner is not None:
            maternal_results = maternal_owner.consume_intervals(maternal_intervals, cutoff_tick=tick)
            for outcome in maternal_results:
                self.trace.append("hierarchy_maternal_outcome", "original maternal endpoint compared once, not task success or causal credit",
                                  cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                                  details={"pnm_id": outcome.claim.preview.pnm.pnm_id, "status": outcome.status,
                                           "event_tick": outcome.evidence.event_tick if outcome.evidence is not None else None,
                                           "command_intervals": outcome.command_intervals})
        claim_outcomes = () if self.outcomes is None else self.outcomes.consume_intervals(outcome_intervals, cutoff_tick=tick)
        visual_source = None
        if self.visual is not None:
            visual_source = self.visual.update(visual_observation, cycle_id=cycle, cutoff_tick=tick)
            candidate = self.visual.candidate()
            if candidate is not None:
                visual_bid = self.cognition.attention.build_bid(candidate, cycle_id=cycle)
                if visual_bid_priority is not None:
                    visual_bid = replace(visual_bid, new_task_need_rank=visual_bid_priority[0], activation_rank=visual_bid_priority[1],
                                         reasons=("explicit_visual_priority_control",))
                competing_bids = (*competing_bids, visual_bid)
            self.trace.append("hierarchy_visual_source", "eligible measured geometry updated one enduring visual source",
                              cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                              details={"sample": visual_source.sample_id, "event": visual_source.event_tick,
                                       "status": visual_source.input_status, "frame": visual_source.frame_id})
        maternal_source = None
        if self.maternal is not None and self.follow_mom is not None:
            if visual_source is None:
                raise RuntimeError("maternal association requires the applied visual configuration")
            maternal_source = self.maternal.update(visual_source)
            # This is unfinished task authority, not a newborn stage or evaluator milestone.
            # C2 completion later in this pass releases it only for the next opportunity,
            # allowing the closed handoff to retire old support rights first.
            support_pending = (self.stand_follow_enabled and previous_support_task is not None
                               and previous_support_task.status != "completed")
            self.follow_mom.prepare(maternal_source, feedback, reports=reports, support_recovery_pending=support_pending)
            maternal_candidate = self.maternal.candidate(task_id=self.follow_mom.task.task_id if self.follow_mom.task is not None else None)
            if maternal_candidate is not None:
                competing_bids = (*competing_bids, self.cognition.attention.build_bid(maternal_candidate, cycle_id=cycle))
            self.trace.append("hierarchy_maternal_source", "MOM association updated from independent recognition and geometry",
                              cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                              details={"identity": maternal_source.identity_status, "localized": maternal_source.action_localized,
                                       "separation": maternal_source.separation, "task_disposition": self.follow_mom.reason,
                                       "last_supported_tick": maternal_source.last_supported_tick})
        next_context = self.cognition.context if context is None else context
        changed_context = next_context != self.cognition.context
        prepared = self.cognition.prepare_source(
            evidence.feedback if evidence is not None else None,
            cutoff_tick=tick, context=context, competing_bids=competing_bids,
        )
        task_outcome = None if self.outcomes is None else self.outcomes.assess_task(
            self.cognition.righting.task, prepared.source.motor_support, prepared.context, cutoff_tick=tick,
        )
        if task_outcome is not None:
            self.trace.append("hierarchy_task_outcome", "task evidence and original PNM correspondence, not causal interpretation",
                              cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                              details={"task_id": task_outcome.task_id, "status": task_outcome.status,
                                       "supported_samples": len(task_outcome.supported_samples), "resolved_claims": len(claim_outcomes),
                                       "event_tick": task_outcome.feedback.event_tick if task_outcome.feedback is not None else None})
            for claim in claim_outcomes:
                self.trace.append("hierarchy_claim_outcome", "original endpoint claim resolved once; no causal learning credit",
                                  cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                                  details={"pnm_id": claim.registration.preview.pnm.pnm_id, "status": claim.status,
                                           "event_tick": claim.evidence.event_tick if claim.evidence is not None else None,
                                           "command_intervals": claim.command_intervals})
            if task_outcome.completion_supported and task_outcome.task_id is not None:
                prepared = self.cognition.complete_prepared_task(prepared, task_outcome.supported_samples, task_id=task_outcome.task_id)
        outcome_owner = self.cognition.sensory.outcome_attention
        created_requests = () if outcome_owner is None else outcome_owner.admit(
            claim_outcomes, prepared.source, self.cognition.righting.task, prepared.context, cutoff_tick=tick,
        )
        for request in created_requests:
            self.trace.append("hierarchy_outcome_request", "task-PNM discrepancy changed a source request, not a task decision",
                              cycle_id=cycle, phase=CyclePhase.UPDATE_OUTCOMES.name,
                              details={"request_id": request.request_id, "pnm_id": request.outcome.registration.preview.pnm.pnm_id,
                                       "significance": request.significance, "relations": ",".join(request.relations),
                                       "admitted_tick": tick, "expires_at_tick": request.expires_at_tick})
        self.cognition.mapper.expire(at_tick=tick)
        self.trace.append(
            "hierarchy_source", "one POSTURE-SUPPORT source updated from eligible physical evidence", cycle_id=cycle,
            phase=CyclePhase.UPDATE_OUTCOMES.name,
            details={**ingress.payload_dict(), "source_status": prepared.source_status, "owner": "body_sensory",
                     "earlier_local_results": len(reports), "earlier_local_events": len(events)},
        )
        for event in events:
            self.trace.append("hierarchy_local_event", "earlier local warning read; task interpretation deferred", cycle_id=cycle,
                              phase=CyclePhase.UPDATE_OUTCOMES.name,
                              details={"number": event.number, "reason": event.reason, "sample_id": event.sample_id,
                                       "event_tick": event.event_tick, "noticed_tick": event.noticed_tick})
        self.scheduler.enter_runtime_phase(cycle, CyclePhase.FOCAL_COMMITMENT)
        selected = self.cognition.select_prepared(prepared)
        allocation = selected.outcome_allocation
        if allocation is not None:
            interpretation = allocation.interpretation
            self.trace.append("hierarchy_outcome_allocation", "single focal allocation; dependent response cannot share interpretation",
                              cycle_id=cycle, phase=CyclePhase.FOCAL_COMMITMENT.name,
                              details={"kind": allocation.kind,
                                       "request_id": interpretation.request.request_id if interpretation is not None else None,
                                       "interpretation_status": interpretation.status if interpretation is not None else None,
                                       "interpretation_cycle": interpretation.cycle_id if interpretation is not None else None,
                                       "outcome_rank": selected.outcome_source_bid.prediction_or_envelope_failure_rank
                                       if selected.outcome_source_bid is not None else 0})
        application = selected.navigation.application
        if application is not None and not isinstance(application, (RightingApplicationV1, TranslationApplicationV1, FollowMomApplicationV1)):
            raise TypeError("this integrated profile has no consumer for the selected application")
        self.trace.append(
            "hierarchy_selection", ("Attention selected the source; Navigation recorded the single focal allocation" if allocation is not None
                                    else "Attention selected the source; Navigation selected the task"), cycle_id=cycle,
            phase=CyclePhase.FOCAL_COMMITMENT.name,
            details={"attention": selected.attention.disposition.value, "primitive": selected.navigation.selected_primitive_id,
                     "task_id": selected.task.task_id if selected.task is not None else None,
                     "strategy": application.strategy if isinstance(application, RightingApplicationV1) else None},
        )
        self.scheduler.enter_runtime_phase(cycle, CyclePhase.PROJECT_DISPATCH)
        calculation = self.cognition.project_selected(selected, replace_existing=True)
        self.trace.append(
            "hierarchy_pnm_consumer", "Prediction registration is separate from the deferred task-outcome consumer",
            cycle_id=cycle, phase=CyclePhase.PROJECT_DISPATCH.name,
            details={"enabled": self.cognition.task_pnm_consumer_enabled,
                     "registered": self.cognition.prediction.current_pnm is not None,
                     "consumer": ("adopt_maternal_preview" if isinstance(application, FollowMomApplicationV1) else
                                  "adopt_visual_preview" if isinstance(application, TranslationApplicationV1) else "adopt_support_preview"),
                     "task_outcomes": ("separate_righting_and_maternal_consumers" if self.stand_follow_enabled else
                                       "maternal_correspondence_v1" if maternal_owner is not None else
                                       "not_implemented_for_visual" if self.visual is not None else
                                       "P16_1G_A" if self.outcomes is not None else "deferred_to_P16_1G")},
        )
        proposal = calculation.proposal
        reservations: tuple[BodyTargetReservationV1, ...] = ()
        if proposal is not None and proposal.bindings:
            reservations = self.cognition.mapper.reserve(proposal, execution_id=f"motor_execution:{self.cognition.stream.generation}:{cycle}",
                                                        at_tick=tick)
        if isinstance(application, FollowMomApplicationV1) and self.follow_mom is not None:
            self.follow_mom.authorized(application, tuple(item.current for item in reservations))
        maternal_registration = None
        if maternal_owner is not None and isinstance(application, FollowMomApplicationV1) and proposal is not None:
            maternal_registration = maternal_owner.register(application, proposal, tuple(item.current for item in reservations))
            self.trace.append("hierarchy_maternal_claim", "original maternal forecast reconciled before handoff",
                              cycle_id=cycle, phase=CyclePhase.PROJECT_DISPATCH.name,
                              details={"pnm_id": maternal_registration.preview.pnm.pnm_id, "endpoint_event_tick": maternal_registration.due_tick,
                                       "compatible": ",".join(maternal_registration.compatible_relations),
                                       "unevaluable": ",".join(maternal_registration.unevaluable_relations)})
        claim_registration = None
        if self.outcomes is not None and isinstance(application, RightingApplicationV1) and proposal is not None:
            claim_registration = self.outcomes.register(application, proposal, tuple(item.current for item in reservations))
            self.trace.append("hierarchy_claim", "original forecast reconciled with authorized meaning before handoff", cycle_id=cycle,
                              phase=CyclePhase.PROJECT_DISPATCH.name,
                              details={"pnm_id": claim_registration.preview.pnm.pnm_id, "endpoint_event_tick": claim_registration.due_tick,
                                       "compatible": ",".join(claim_registration.compatible_relations),
                                       "unevaluable": ",".join(claim_registration.unevaluable_relations), "target_count": len(reservations)})
        projection = application.projection if isinstance(application, (RightingApplicationV1, TranslationApplicationV1, FollowMomApplicationV1)) else None
        origin = reservations[0].current.target.origin if reservations else None
        terminal_task = calculation.task is not None and calculation.task.status != "active"
        if self.stand_follow_enabled:
            # Retire the terminal transition once. A historical completed Righting
            # task must never cancel a later, independently authorized translation.
            terminal_task = terminal_task and (previous_support_task is None or previous_support_task.status == "active")
        motor = Nca8MotorEnvelopeV1(
            self.cognition.stream, tick, projection, tuple(item.current for item in reservations),
            tuple(item.current for item in proposal.replaces) if proposal is not None and reservations else (), changed_context or terminal_task or (self.follow_mom is not None and self.follow_mom.cancel_previous),
        )
        decision = calculation.navigation
        commitment = CycleCommitmentV1(
            cycle, cycle, tuple(item.result_id for item in frozen), tuple(item.result_id for item in applied),
            calculation.attention.selection_id, decision.wnm.working_id if decision.wnm is not None else None,
            decision.selected_primitive_id, application.application_id if application is not None else None,
            projection.pnm.pnm_id if projection is not None else None,
            ("FOLLOW_MOM" if isinstance(application, FollowMomApplicationV1) else
             "TRANSLATE_TO_VISIBLE_REGION" if isinstance(application, TranslationApplicationV1) else "RESTORE_VIABLE_SUPPORT")
            if reservations else None,
            origin.application_id if origin is not None else None, origin.envelope_id if origin is not None else None,
        )
        self.last_commitment = commitment
        self.trace.append("hierarchy_commit", "sparse task PNM and finite target payload committed before movement", cycle_id=cycle,
                          phase=CyclePhase.PROJECT_DISPATCH.name,
                          details={"pnm": commitment.pnm_id, "envelope": commitment.action_envelope_id,
                                   "directive": motor.directive, "target_count": len(reservations), "cutoff_tick": tick})
        accepted = self.handoff.accept(Nca8PhaseEDispatchV1(commitment, None, projection.pnm if projection else None, None, motor))
        self.trace.append("hierarchy_handoff", "target handoff accepted; not yet released or installed", cycle_id=cycle,
                          phase=CyclePhase.PROJECT_DISPATCH.name, details={"receipt": accepted.receipt_id})
        hook = self.cognition.sensory.learning_hook
        learning_report: LearningPhaseFReportV1 | None = None

        def reconcile_learning() -> None:
            """Visit the one source-side participant while the scheduler is actually in F."""
            nonlocal learning_report
            if hook is not None:
                learning_report = hook.reconcile(
                    cycle_id=cycle, cutoff_tick=tick, registration=claim_registration,
                    context=application.task.context if isinstance(application, RightingApplicationV1) else None,
                    outcomes=claim_outcomes, requests=created_requests,
                    interpretation=allocation.interpretation if allocation is not None and allocation.kind == "interpretation" else None,
                    comparison_enabled=self.outcomes.compare_predictions if self.outcomes is not None else False,
                    attention_enabled=outcome_owner is not None,
                )
                self.trace.append("hierarchy_learning_hook", "F reconciled source participation; eligibility only, no durable update",
                                  cycle_id=cycle, phase=CyclePhase.LEARNING_SCHEDULE.name,
                                  details={"recipient": learning_report.recipient_id, "participants": len(learning_report.pending),
                                           "offered_outcomes": learning_report.offered_outcomes,
                                           "dispositions": ",".join(item.status for item in learning_report.dispositions),
                                           "durable_learning_updates": 0, "ledger_rows_executed": 0})
            self.trace.append("hierarchy_learning", "F reconciliation: no durable learner or new physical outcome", cycle_id=cycle,
                              phase=CyclePhase.LEARNING_SCHEDULE.name, details={"durable_learning_updates": 0})

        if hook is None:
            # Preserve the retained empty-F trace and original scheduler call.
            reconcile_learning()
            schedule = self.scheduler.phase_f_finish(cycle, self.trace)
        else:
            schedule = self.scheduler.phase_f_finish(cycle, self.trace, reconcile=reconcile_learning)
        self.trace.append("hierarchy_close", "focal core closed; physical work may now be attempted", cycle_id=cycle,
                          details={"cutoff_tick": tick})
        ready = self.handoff.release_after_close(accepted)
        result = IntegratedRightingCycleV1(
            calculation, commitment, ready, reservations, schedule, reports, events, task_outcome, claim_outcomes, claim_registration,
            created_requests, () if outcome_owner is None else outcome_owner.pending(), learning_report, visual_source,
            maternal_source, self.follow_mom.assessment() if self.follow_mom is not None else None,
            MaternalOutcomeFrameV1(tick, tuple(item for item in maternal_owner.history() if item.number > maternal_before),
                                   maternal_registration, maternal_owner.pending(), maternal_owner.compare_predictions)
            if maternal_owner is not None else None,
        )
        self.last_result = result
        return result


class IntegratedRightingTrialV1:
    """Own the external timebase, isolated H2 plant and one H4 executor.

    Construction senses the reset body but performs no focal selection or motor
    installation. focal_step() runs/consumes one core result without moving;
    advance_lower() advances exactly one interval without selecting a task;
    step() combines one focal call and four lower intervals. Inspecting pauses
    this synchronous surrogate. Public physical snapshots are observer-only.
    Faults stop both owners; reset revokes them before replacing the generation.

    H6-B may select a fixed tick after which local control receives only the
    last focal acquisition. The cortical source still receives every latest
    eligible focal summary. The lower reader retains the original acquisition
    time and all freshness/lease checks; this is loss of the fast route, not
    permission to pretend an old sample is fresh or to disable protection.
    By default no such route restriction exists. No experiment label enters
    the task, target executor or physical provider as a hidden answer.
    """

    def __init__(
        self, physical_profile: MotorWorldProfileV1 | None = None, *, stream_id: str = "h6_reference_body",
        context: RightingContextV1 | None = None, capabilities: tuple[BodyAxisCapabilityV1, ...] | None = None,
        control_profile: SensorimotorProfileV1 | None = None, righting_enabled: bool = True,
        influence_enabled: bool = True, handoff_enabled: bool = True, trace_capacity: int = 256,
        orientation_mapping_sign: int = 1, task_pnm_consumer_enabled: bool = True,
        focal_only_feedback_from_tick: int | None = None,
        task_outcomes_enabled: bool = False, task_prediction_comparison_enabled: bool = True,
        task_outcome_attention_enabled: bool = False, task_learning_hook_enabled: bool = False,
        learning_diagnostic_capacity: int = 32,
        translation_fixture: TranslationFixtureV1 | None = None, planar_profile: PlanarWorldProfileV1 | None = None,
        translation_capability: BodyTranslationCapabilityV1 | None = None, translation_mapping_sign: int = 1,
        follow_mom_profile: FollowMomProfileV1 | None = None,
        stand_follow_enabled: bool = False, righting_target_inset_degrees: float = 0.0,
    ) -> None:
        profile = MotorWorldProfileV1() if physical_profile is None else physical_profile
        if not isinstance(profile, MotorWorldProfileV1) or profile.dt_seconds != 0.05:
            raise ValueError("H6-A requires the declared 0.05-second physical profile")
        if focal_only_feedback_from_tick is not None:
            _bounded_count(focal_only_feedback_from_tick, "focal_only_feedback_from_tick", 0, 80)
        if not all(isinstance(flag, bool) for flag in (
            task_outcomes_enabled, task_prediction_comparison_enabled, task_outcome_attention_enabled, task_learning_hook_enabled,
        )):
            raise TypeError("task outcome options must be Boolean")
        if task_outcome_attention_enabled and not task_outcomes_enabled:
            raise ValueError("task-outcome Attention requires the 1G-A correspondence consumer")
        if task_learning_hook_enabled and not task_outcomes_enabled:
            raise ValueError("the no-learning hook requires the 1G-A correspondence consumer")
        _bounded_count(learning_diagnostic_capacity, "learning_diagnostic_capacity", 1, 32)
        self._task_learning_hook_enabled = task_learning_hook_enabled
        self._learning_diagnostic_capacity = learning_diagnostic_capacity
        self._task_outcomes_enabled = task_outcomes_enabled
        self._task_outcome_attention_enabled = task_outcome_attention_enabled
        self._task_prediction_comparison_enabled = task_prediction_comparison_enabled
        self._outcome_intervals: list[RightingIntervalEvidenceV1] = []
        self._maternal_intervals: list[MaternalIntervalEvidenceV1] = []
        self._focal_only_feedback_from_tick = focal_only_feedback_from_tick
        self._orientation_mapping_sign = orientation_mapping_sign
        self._task_pnm_consumer_enabled = task_pnm_consumer_enabled
        if (translation_fixture is None and follow_mom_profile is None) != (planar_profile is None):
            raise ValueError("an integrated visual operation requires its physical planar profile")
        self._follow_mom_profile = follow_mom_profile
        self._stand_follow_enabled = stand_follow_enabled
        self._righting_target_inset_degrees = righting_target_inset_degrees
        self._translation_fixture, self._translation_capability = translation_fixture, translation_capability
        self._translation_mapping_sign = translation_mapping_sign
        self._world = MotorWorldV1(MotorStreamRefV1(stream_id, 1), profile, planar_profile=planar_profile)
        self._context, self._capabilities, self._control_profile = context, capabilities, control_profile
        self._righting_enabled, self._influence_enabled, self._handoff_enabled = righting_enabled, influence_enabled, handoff_enabled
        self._trace_capacity = trace_capacity
        self._busy = False
        self.core: IntegratedRightingCoreV1
        self.controller: SensorimotorExecutorV1
        self._latest_feedback: MotorFeedbackV1
        self._focal_feedback: MotorFeedbackV1
        self._fault: str | None = None
        self._consumptions = 0
        self._history: deque[IntegratedRightingCycleV1] = deque(maxlen=8)
        self._initialize(self._world.observe())

    def _initialize(self, feedback: MotorFeedbackV1) -> None:
        """Create fresh cognitive/target owners; never reload old execution rights."""
        self.core = IntegratedRightingCoreV1(
            feedback.stream, context=self._context, capabilities=self._capabilities, righting_enabled=self._righting_enabled,
            influence_enabled=self._influence_enabled, handoff_enabled=self._handoff_enabled, trace_capacity=self._trace_capacity,
            orientation_mapping_sign=self._orientation_mapping_sign, task_pnm_consumer_enabled=self._task_pnm_consumer_enabled,
            task_outcomes_enabled=self._task_outcomes_enabled, task_prediction_comparison_enabled=self._task_prediction_comparison_enabled,
            task_outcome_attention_enabled=self._task_outcome_attention_enabled,
            task_learning_hook_enabled=self._task_learning_hook_enabled, learning_diagnostic_capacity=self._learning_diagnostic_capacity,
            translation_fixture=self._translation_fixture, translation_capability=self._translation_capability,
            translation_mapping_sign=self._translation_mapping_sign, follow_mom_profile=self._follow_mom_profile,
            stand_follow_enabled=self._stand_follow_enabled, righting_target_inset_degrees=self._righting_target_inset_degrees,
        )
        self.controller = SensorimotorExecutorV1(
            self.core.cognition.mapper, profile=self._control_profile, installation_source=self.core.handoff,
        )
        self._latest_feedback = MotorFeedbackV1.from_dict(feedback.as_dict())
        self._focal_feedback = self._latest_feedback
        self._fault, self._consumptions = None, 0
        self._history.clear()
        self._outcome_intervals.clear()
        self._maternal_intervals.clear()

    @property
    def tick(self) -> int:
        """Read the one external physical boundary index without advancing it."""
        return self._world.tick

    @property
    def handoff_consumptions(self) -> int:
        """Read the actual consume count, independently of diagnostics or installations."""
        return self._consumptions

    @property
    def latest_feedback(self) -> MotorFeedbackV1:
        """Return the last delivered acquisition, possibly old; do not refresh it."""
        return self._latest_feedback

    @property
    def observer_body(self) -> MotorBodyStateV1:
        """Expose actual H2 coordinates to external tests only, never the core."""
        return self._world.body

    @property
    def observer_planar_body(self) -> PlanarWorldStateV1 | None:
        """Expose physical coordinates to the external observer, never to cognition."""
        return self._world.planar_body

    @property
    def stopped(self) -> bool:
        """Report a sticky runtime failure; a terminal task alone does not stop time."""
        return self._fault is not None or self.core.fault is not None or self.controller.fault is not None

    def history(self) -> tuple[IntegratedRightingCycleV1, ...]:
        """Read at most eight closed focal records, not an unbounded motor movie."""
        return tuple(self._history)

    def retained_counts(self) -> dict[str, int]:
        """Read owner storage bounds independently of trace rendering or task choice.

        Qualification samples these counts after each focal and lower step. A
        result may keep a larger finite observer export outside the live agent;
        that export is not an additional WNM, current PNM or cognitive memory.
        """
        cognition = self.core.cognition
        return {
            "durable_maps": cognition.maps.durable_map_count, "current_source_states": cognition.maps.current_state_count,
            "wnm": int(cognition.navigation.current_wnm is not None),
            "current_pnm": int(cognition.prediction.current_pnm is not None),
            "righting_applications": len(cognition.righting.history()), "past_previews": len(cognition.prediction.preview_history()),
            "focal_records": len(self._history), "focal_trace": self.core.trace.retained_count,
            "pending_sensor_deliveries": self._world.pending_feedback_count,
            **cognition.mapper.retained_counts(), **self.controller.retained_counts(),
            **({f"visual_{key}": value for key, value in self.core.visual.retained_counts().items()} if self.core.visual is not None else {}),
            **({f"maternal_{key}": value for key, value in self.core.maternal.retained_counts().items()}
               if self.core.maternal is not None else {}),
            **({f"follow_mom_{key}": value for key, value in self.core.follow_mom.retained_counts().items()}
               if self.core.follow_mom is not None else {}),
            **({"outcome_staged_intervals": len(self._outcome_intervals), **self.core.outcomes.retained_counts()}
               if self.core.outcomes is not None else {}),
            **(cognition.sensory.outcome_attention.retained_counts() if cognition.sensory.outcome_attention is not None else {}),
            **(cognition.sensory.learning_hook.retained_counts() if cognition.sensory.learning_hook is not None else {}),
            **({"maternal_staged_intervals": len(self._maternal_intervals), **self.core.maternal_outcomes.retained_counts()}
               if self.core.maternal_outcomes is not None else {}),
        }

    def snapshot(self) -> dict[str, object]:
        """Read bounded task/source/execution status, without stepping or learning."""
        task = self.core.cognition.righting.task
        receipt = self.core.handoff.receipt
        return {
            "profile": "stand_follow_v1" if self._stand_follow_enabled else "integrated_righting_v1",
            "stream": self._world.stream.as_dict(),
            **({"righting_target_inset_degrees": self._righting_target_inset_degrees,
                "support_release_policy": "completed_task_then_closed_handoff_before_follow_applicability"}
               if self._stand_follow_enabled else {}),
            "tick": self.tick, "elapsed_seconds": self.tick * 0.05, "focal_cycles": self.core.scheduler.last_completed_cycle,
            "handoff_consumptions": self._consumptions, "installation_count": self.controller.installation_count,
            "task": task.as_dict() if task is not None else None,
            "handoff": receipt.as_dict() if receipt is not None else None,
            "latest_feedback": self._latest_feedback.as_dict(), "controller": self.controller.snapshot(),
            "fault": self._fault, "stopped": self.stopped, "retained_focal_records": len(self._history),
            "pending_sensor_count": self._world.pending_feedback_count,
            "task_pnm_registration_enabled": self._task_pnm_consumer_enabled,
            "focal_only_feedback_from_tick": self._focal_only_feedback_from_tick,
            "orientation_mapping_sign": self._orientation_mapping_sign,
            "durable_map_count": self.core.cognition.maps.durable_map_count,
            "wnm_count": int(self.core.cognition.navigation.current_wnm is not None),
            "current_task_pnm_count": int(self.core.cognition.prediction.current_pnm is not None),
            "task_success_established": task is not None and task.status == "completed", "durable_learning_updates": 0,
            **({"translation_scope": "developmental_follow_mom" if self.core.follow_mom is not None else "one_supplied_operation_not_acquired", "translation_mapping_sign": self._translation_mapping_sign,
                "visual_source": self.core.visual.current.as_dict() if self.core.visual.current is not None else None}
               if self.core.visual is not None else {}),
            **({"maternal_task": self.core.follow_mom.snapshot()} if self.core.follow_mom is not None else {}),
            **({"maternal_pending_claims": [item.as_dict() for item in self.core.maternal_outcomes.pending()],
                "maternal_outcome_history": [item.as_dict() for item in self.core.maternal_outcomes.history()]}
               if self.core.maternal_outcomes is not None else {}),
            **({"learning_participation": [item.as_dict() for item in self.core.cognition.sensory.learning_hook.pending()]}
               if self.core.cognition.sensory.learning_hook is not None else {}),
            **({"task_outcomes_profile": "righting_outcomes_v1",
                "task_assessment": self.core.outcomes.last_assessment.as_dict() if self.core.outcomes.last_assessment is not None else None,
                "pending_claims": [item.as_dict() for item in self.core.outcomes.pending()],
                "outcome_history": [item.as_dict() for item in self.core.outcomes.history()]}
               if self.core.outcomes is not None else {}),
        }

    def _require_idle(self) -> None:
        """Reject re-entry, unconsumed core output and foreign time before any effect."""
        if self._busy or self.stopped or self.core.running:
            raise RuntimeError("hierarchy trial is busy or stopped; no automatic retry")
        if self.tick != self.controller.next_tick or self._world.stream != self.core.cognition.stream:
            raise RuntimeError("world and lower owner no longer share time/generation")

    def _stop(self, reason: str) -> None:
        """Stop future dispatch after a boundary fault; never undo possible movement."""
        self._fault = reason
        self.core.stop(reason)
        self.controller.abort(reason, at_tick=self.controller.next_tick)

    def focal_step(
        self, *, context: RightingContextV1 | None = None, competing_bids: Sequence[AttentionBidV1] = (),
        visual_input_enabled: bool = True, visual_bid_priority: tuple[int, int] | None = None,
    ) -> IntegratedRightingCycleV1:
        """Run one focal opportunity and consume/install once, with zero world steps."""
        self._require_idle()
        if not isinstance(visual_input_enabled, bool):
            raise TypeError("visual_input_enabled must be Boolean")
        if self.core.last_result is not None and self.tick <= self.core.last_result.calculation.cutoff_tick:
            raise ValueError("advance physical time before the next focal opportunity")
        self._busy = True
        try:
            visual = (admit_motor_visual_surface_v1(self._world.visual_surface(), self._latest_feedback)
                      if self.core.visual is not None and visual_input_enabled else None)
            result = self.core.run_cycle(
                self._latest_feedback, cutoff_tick=self.tick, context=context, competing_bids=competing_bids,
                local_reports=self.controller.reports, local_events=self.controller.events,
                outcome_intervals=tuple(self._outcome_intervals), visual_observation=visual, visual_bid_priority=visual_bid_priority,
                maternal_intervals=tuple(self._maternal_intervals) if visual_input_enabled else
                tuple(replace(item, observations=()) for item in self._maternal_intervals),
            )
            self._outcome_intervals.clear()
            self._maternal_intervals.clear()
            motor = self.core.handoff.consume_motor(result.receipt)
            self._consumptions += 1
            self.core.trace.append("hierarchy_consumed", "outer driver consumed the closed handoff once", cycle_id=result.commitment.cycle_id,
                                   details={"tick": self.tick, "directive": motor.directive, "receipt": result.receipt.receipt_id})
            if result.reservations:
                self.controller.install_authorized(result.reservations, at_tick=self.tick)
                if self._stand_follow_enabled:
                    # Family replacement ends only the previous family's execution.
                    # Old claims retain their original endpoint/evidence lifetimes.
                    if result.claim_registration is None and self.core.outcomes is not None:
                        self.core.outcomes.end_execution(at_tick=self.tick, reason="replacement")
                    if (self.core.maternal_outcomes is not None and
                            (result.maternal_correspondence is None or result.maternal_correspondence.registration is None)):
                        self.core.maternal_outcomes.end_execution(at_tick=self.tick, reason="replacement")
                if self.core.maternal_outcomes is not None and result.maternal_correspondence is not None:
                    maternal_claim = result.maternal_correspondence.registration
                    if maternal_claim is not None:
                        self.core.maternal_outcomes.installed(maternal_claim, at_tick=self.tick)
                if self.core.outcomes is not None and result.claim_registration is not None:
                    self.core.outcomes.installed(result.claim_registration, at_tick=self.tick)
                self.core.trace.append("hierarchy_installed", "authorized targets installed once; no physical step yet",
                                       cycle_id=result.commitment.cycle_id,
                                       details={"tick": self.tick, "execution": result.reservations[0].current.execution_id,
                                                "installation_count": self.controller.installation_count})
            elif motor.cancel_previous:
                self.controller.cancel_execution(at_tick=self.tick)
                if self.core.maternal_outcomes is not None:
                    self.core.maternal_outcomes.end_execution(at_tick=self.tick)
                if self.core.outcomes is not None:
                    self.core.outcomes.end_execution(at_tick=self.tick)
                self.core.trace.append("hierarchy_cancel", "explicit context/terminal-task revocation stopped earlier lower execution",
                                       cycle_id=result.commitment.cycle_id, details={"tick": self.tick})
            if result.local_events:
                self.controller.acknowledge_events(result.local_events[-1].number)
            self._focal_feedback = self._latest_feedback
            self._history.append(result)
            return result
        except BaseException:
            if self.core.outcomes is not None:
                self.core.outcomes.end_execution(at_tick=self.tick, reason="not_applied")
            self._stop("focal_or_installation_fault_no_automatic_retry")
            raise
        finally:
            self._busy = False

    def advance_lower(self) -> SensorimotorStepV1:
        """Compute one bounded local drive, move H2 once, then stage due sensing.

        Sensing returned by the physical call cannot influence the command that
        caused it. It may affect the next lower update and the next eligible
        focal summary. A call/admission exception is execution uncertainty;
        neither the command nor the old cognitive receipt is retried.
        """
        self._require_idle()
        if self.core.handoff.has_pending_request:
            raise RuntimeError("consume or cancel the closed focal output before lower execution")
        if self.core.outcomes is not None and len(self._outcome_intervals) >= 16:
            self._stop("outcome_ingress_overflow_before_physical_step")
            raise OverflowError("sixteen lower intervals await focal outcome admission; physical time was not advanced")
        if self.core.maternal_outcomes is not None and len(self._maternal_intervals) >= 16:
            self._stop("maternal_ingress_overflow_before_physical_step")
            raise OverflowError("sixteen returned maternal intervals await C2; no further physical step")
        self._busy = True
        try:
            tick = self.tick
            cutoff = self._focal_only_feedback_from_tick
            feedback = self._focal_feedback if cutoff is not None and tick >= cutoff else self._latest_feedback
            result = self.controller.step(feedback, at_tick=tick)
            command = result.command
            self.core.trace.append(
                "hierarchy_lower", "local feedback produced a bounded drive; not a new focal decision",
                details={"tick": tick, "orientation_drive": command.orientation_drive if command is not None else 0.0,
                         "extension_drive": command.extension_drive if command is not None else 0.0,
                         "feedback_sample": result.feedback.sample_id if result.feedback is not None else None,
                         "significant_events_added": result.significant_events_added,
                         **({"translation_forward": command.translation.forward if command is not None and command.translation is not None else 0.0,
                             "translation_left": command.translation.left if command is not None and command.translation is not None else 0.0}
                            if self.core.visual is not None else {})},
            )
            delivered = self._world.step(command)
            if self.tick != tick + 1:
                raise RuntimeError("physical provider did not advance exactly one interval")
            self._latest_feedback = admit_motor_feedback_batch_v1(
                delivered, self._latest_feedback, stream=self.core.cognition.stream, at_tick=self.tick,
            )
            if self.core.outcomes is not None:
                # The Righting consumer receives only its support-resource reports.
                # Keep the original command and acquisitions: do not fabricate a
                # neutral action or count maternal movement as Righting exposure.
                support_reports = (tuple(report for report in result.reports
                                         if not isinstance(report.committed_target.target, BodyTranslationTargetV1))
                                   if self._stand_follow_enabled else result.reports)
                self._outcome_intervals.append(RightingIntervalEvidenceV1(tick, command, support_reports, delivered))
            if self.core.maternal_outcomes is not None:
                observations: list[VisualObservationV1] = []
                for sample in delivered:
                    observation = admit_motor_visual_surface_v1(self._world.visual_surface(feedback=sample), sample)
                    if observation is not None:
                        observations.append(observation)
                self._maternal_intervals.append(MaternalIntervalEvidenceV1(tick, command, result.reports, delivered, tuple(observations)))
            self.core.trace.append(
                "hierarchy_input", "physical interval completed; due sensing staged for later consumers",
                details={"tick": self.tick, "sample_id": self._latest_feedback.sample_id,
                         "event_tick": self._latest_feedback.event_tick, "available_tick": self._latest_feedback.available_tick,
                         "tilt": self._latest_feedback.body_tilt_degrees, "extension": self._latest_feedback.support_extension},
            )
            return result
        except BaseException:
            if self.core.outcomes is not None:
                self.core.outcomes.end_execution(at_tick=self.tick, reason="execution_unknown")
            self._stop("lower_or_physical_admission_fault_effects_unresolved")
            raise
        finally:
            self._busy = False

    def step(
        self, *, context: RightingContextV1 | None = None, local_updates: int = 4,
    ) -> tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]]:
        """Run one focal opportunity followed by 1, 4 or 8 physical updates.

        Four remains the unchanged nominal cadence. This explicit H6-B control
        varies only the next focal opportunity, not lower dt, feedback timing,
        target leases or either task budget. The outer experiment must keep a
        fixed total physical horizon. Invalid cadence is rejected before any
        focal work or side effect; faster polling does not grant a larger budget.
        """
        _bounded_count(local_updates, "local_updates", 1, 8)
        if local_updates not in (1, 4, 8):
            raise ValueError("supported focal cadences are 1, 4 or 8 lower updates")
        result = self.focal_step(context=context)
        return result, tuple(self.advance_lower() for _ in range(local_updates))

    def cancel(self) -> None:
        """Explicitly cancel the current task and its execution before another tick.

        Already achieved local results and realized physical consequences remain.
        A new context, not a repeated sample, is required to start another task.
        This stop is not a new demanding task and does not create a fresh PNM.
        """
        self._require_idle()
        if self.core.handoff.has_pending_request:
            raise RuntimeError("resolve the pending focal handoff before cancellation")
        self.controller.cancel_execution(at_tick=self.tick)
        if self.core.maternal_outcomes is not None:
            self.core.maternal_outcomes.end_execution(at_tick=self.tick)
        if self.core.outcomes is not None:
            self.core.outcomes.end_execution(at_tick=self.tick)
        self.core.cognition.righting.cancel_task()
        if self.core.translation is not None:
            self.core.translation.cancel()
        if self.core.follow_mom is not None:
            self.core.follow_mom.cancel()
        self.core.cognition.sensory.clear_motor_context()
        self.core.trace.append("hierarchy_cancel", "explicit task and execution cancellation; no success claim",
                               details={"tick": self.tick})

    def reset(self) -> None:
        """Revoke old owners and replace all current evidence/rights in a new generation."""
        if self._busy or self.core.running:
            raise RuntimeError("cannot reset during focal or physical work")
        self.core.stop("generation_reset")
        self.controller.abort("generation_reset", at_tick=self.controller.next_tick)
        self._initialize(self._world.reset())
