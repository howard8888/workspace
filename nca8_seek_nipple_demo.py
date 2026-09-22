#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first selected SeekNipple review on the existing integrated hierarchy.

Fixed physical, sensing and ablation profiles are chosen before a run. The
external observer advances one shared clock and never chooses a task from a
milestone or a completed record. Near-start cases isolate oral task integration;
three longer axis-aligned cases exercise the continuous stand/follow/seeking
path without changing the accepted A/B scene or their output formats.

Reach, touch, local achievement, sparse prediction and task status are separate.
These finite reviews do not qualify latch, suckling, nourishment, Rest or B99.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1, OralWorldProfileV1, OralWorldStateV1,
    PlanarObjectV1, PlanarDetailObjectV1, PlanarWorldProfileV1, PlanarWorldStateV1, PlanarPerturbationV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_feeding import FeedingDetailProfileV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import follow_mom_owner_limits_v1, maternal_durable_signature_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_outcome_attention_demo import outcome_attention_owner_limits_v1
from nca8_seek_nipple import SeekNippleApplicationV1, SeekNippleProfileV1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1

__version__ = "0.2.0"
__all__ = ["SEEK_NIPPLE_CASES_V1", "SeekNippleExperimentProfileV1", "SeekNipplePhysicalSampleV1", "SeekNippleExperimentV1",
           "seek_nipple_profile_v1", "create_seek_nipple_trial_v1", "run_seek_nipple_v1", "render_seek_nipple_v1",
           "run_seek_nipple_menu_v1", "seek_nipple_owner_limits_v1", "collect_seek_nipple_evidence_v1", "__version__"]

SEEK_NIPPLE_CASES_V1 = (
    "nominal", "seek_off", "attention_off", "source_off", "no_need", "missing_detail", "wrong_category",
    "missing_touch", "missing_reach", "no_capability", "blocked_motor", "no_surface", "heading_90", "rotated_scene",
    "out_of_reach", "intermediate_target", "early_contact", "brief_gap", "prolonged_gap", "dropout", "delayed",
    "support_loss", "body_shift", "body_turn", "cancelled", "pnm_registration_off", "competing_on", "influence_off",
    "cadence_1", "cadence_8", "stand_follow", "stand_follow_seek_off", "stand_follow_no_surface",
)
_LIMITS = {
    **follow_mom_owner_limits_v1(), **outcome_attention_owner_limits_v1(),
    "feeding_detail_durable_maps": 1, "feeding_detail_current_configurations": 1, "feeding_detail_task_influences": 1,
    "seek_nipple_tasks": 1, "seek_nipple_source_bases": 1, "seek_nipple_targets": 1, "seek_nipple_applications": 8,
    "seek_nipple_reach_samples": 2, "learning_participants": 8, "learning_dispositions": 32,
    "maternal_attention_pending_requests": 8, "maternal_attention_previous_endpoint": 1,
    "maternal_attention_dependency": 1, "maternal_attention_dispositions": 32,
    "maternal_learning_participants": 8, "maternal_learning_dispositions": 32,
}
_EXPECT_REACH = frozenset({"nominal", "no_surface", "rotated_scene", "intermediate_target", "brief_gap", "body_shift",
                           "pnm_registration_off", "competing_on", "influence_off", "cadence_8", "stand_follow", "stand_follow_no_surface"})


@dataclass(frozen=True, slots=True)
class SeekNippleExperimentProfileV1:
    """Fixed external conditions, not a cognitive instruction list or success target."""

    case: str
    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    oral: OralWorldProfileV1
    feeding: FeedingDetailProfileV1 = FeedingDetailProfileV1()
    seeking: SeekNippleProfileV1 = SeekNippleProfileV1()
    oral_capability: bool = True
    pnm_registration: bool = True
    stand_follow: bool = False
    horizon_ticks: int = 64
    cadence: int = 4
    visual_gap_cutoffs: tuple[int, ...] = ()
    competitor_cutoffs: tuple[int, ...] = ()
    cancel_tick: int | None = None

    def as_dict(self) -> dict[str, object]:
        """Export the entire fixed profile; no outcome-dependent field is omitted."""
        return {"case": self.case, "physical": asdict(self.physical), "planar": asdict(self.planar), "oral": asdict(self.oral),
                "feeding": self.feeding.as_dict(), "seeking": self.seeking.as_dict(), "oral_capability": self.oral_capability,
                "pnm_registration": self.pnm_registration, "stand_follow": self.stand_follow, "horizon_ticks": self.horizon_ticks,
                "cadence": self.cadence, "visual_gap_cutoffs": list(self.visual_gap_cutoffs),
                "competitor_cutoffs": list(self.competitor_cutoffs), "cancel_tick": self.cancel_tick,
                "scene_scope": "declared_axis_aligned_stand_follow" if self.stand_follow else "near_supported_start",
                "source_of_need": "fixed_developmental_scaffold_not_milestone"}


def seek_nipple_profile_v1(case: str = "nominal") -> SeekNippleExperimentProfileV1:
    """Choose finite task-independent conditions before any cognition or movement.

    The near nominal body starts at (0,0), Mom at (0.2,0), detail at (0.1,0).
    Longer-reach/gap/cadence cases use detail (0.3,0); the same existing actuator
    must obtain a second selected contribution. The continuous case uses Mom
    (2,0) and detail (1.8,0), keeping the body-forward oral axis feasible without
    inventing a head-turn capability. No accepted earlier scene is modified.
    """
    if not isinstance(case, str) or case not in SEEK_NIPPLE_CASES_V1:
        raise ValueError("unknown selected SeekNipple review case")
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    parent, detail = (0.2, 0.0), (0.1, 0.0)
    if case in {"intermediate_target", "brief_gap", "prolonged_gap", "cadence_1", "cadence_8", "competing_on", "influence_off"}:
        detail = (0.3, 0.0)
    if case == "out_of_reach":
        detail = (0.36, 0.0)
    stand_follow = case.startswith("stand_follow")
    if stand_follow:
        physical = MotorWorldProfileV1()
        parent, detail = (2.0, 0.0), (1.8, 0.0)
    if case == "rotated_scene":
        parent, detail = (0.0, 0.2), (0.0, 0.1)
    objects: tuple[PlanarObjectV1, ...] = (PlanarObjectV1("region_1", parent),)
    if case != "missing_detail":
        objects += (PlanarDetailObjectV1("region_2", detail, descriptor="landmark" if case == "wrong_category" else "feeding"),)
    planar = PlanarWorldProfileV1(objects=objects, initial_heading=90.0 if case in {"heading_90", "rotated_scene"} else 0.0)
    surface = (0.05, 0.0) if case == "early_contact" else detail
    oral = OralWorldProfileV1(surfaces=() if case in {"no_surface", "stand_follow_no_surface"} else (PlanarObjectV1("touch_surface", surface, 0.004),),
                             motor_enabled=case != "blocked_motor", extension_available=case != "missing_reach",
                             contact_available=case != "missing_touch")
    if case == "dropout":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, 65, drop_feedback=True),))
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, 65, remove_support=True),))
    elif case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case in {"body_shift", "body_turn"}:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 2, velocity=(0.2, 0.0) if case == "body_shift" else (0.0, 0.0),
                                                                     heading_rate=90.0 if case == "body_turn" else 0.0),))
    feeding = FeedingDetailProfileV1(source_enabled=case != "source_off", attention_enabled=case != "attention_off", feeding_need=case != "no_need")
    seeking = SeekNippleProfileV1(enabled=case not in {"seek_off", "stand_follow_seek_off"}, influence_enabled=case != "influence_off")
    return SeekNippleExperimentProfileV1(
        case, physical, planar, oral, feeding, seeking, case != "no_capability", case != "pnm_registration_off", stand_follow,
        160 if stand_follow else 64, 1 if case == "cadence_1" else 8 if case == "cadence_8" else 4,
        (4,) if case == "brief_gap" else (4, 8, 12, 16) if case == "prolonged_gap" else (),
        (4, 12) if case in {"competing_on", "influence_off"} else (), 1 if case == "cancelled" else None,
    )


def create_seek_nipple_trial_v1(case: str = "nominal", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct all source/task owners at entry; select no task and install nothing."""
    profile = seek_nipple_profile_v1(case)
    return IntegratedRightingTrialV1(
        profile.physical, stream_id="seek_nipple_reference_body", planar_profile=profile.planar, oral_profile=profile.oral,
        capabilities=(*nominal_body_capabilities_v1(), *((oral_body_capability_v1(),) if profile.oral_capability else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=profile.stand_follow,
                                             outcome_attention_enabled=profile.stand_follow, learning_hook_enabled=profile.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=profile.feeding,
        seek_nipple_profile=profile.seeking, stand_follow_enabled=profile.stand_follow,
        task_outcomes_enabled=profile.stand_follow, task_outcome_attention_enabled=profile.stand_follow,
        task_learning_hook_enabled=profile.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=profile.pnm_registration, trace_capacity=trace_capacity,
    )


def _durable_signature(trial: IntegratedRightingTrialV1) -> str:
    """Measure actual enduring source maps before and after the run."""
    owner = trial.core.feeding_detail
    if owner is None:
        raise RuntimeError("seeking trial lacks its feeding source")
    return json.dumps({"existing": maternal_durable_signature_v1(trial), "feeding": owner.durable_map.as_dict()}, sort_keys=True, allow_nan=False)


@dataclass(frozen=True, slots=True)
class SeekNipplePhysicalSampleV1:
    """Private physical state captured by the observer, never passed to cognition."""

    tick: int
    support: MotorBodyStateV1
    planar: PlanarWorldStateV1
    oral: OralWorldStateV1

    def as_dict(self) -> dict[str, object]:
        """Detach evaluator physics and label it independently from admitted sensing."""
        return {"tick": self.tick, "support": asdict(self.support), "planar": self.planar.as_dict(), "oral": self.oral.as_dict()}


@dataclass(frozen=True, slots=True)
class SeekNippleExperimentV1:
    """Complete bounded observer evidence; none of these records controls the run."""

    profile: SeekNippleExperimentProfileV1
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[SeekNipplePhysicalSampleV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str
    handoff_consumptions: int
    installations: int
    registered_pnm_cycles: tuple[int, ...]

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check measured limits, missing required owners and duplicate count keys."""
        required = {"wnm", "current_pnm", "body_reserved_records", "seek_nipple_tasks", "seek_nipple_reach_samples",
                    "feeding_detail_current_configurations"}
        missing = tuple(f"missing:{key}" for key in sorted(required - dict(self.peak_counts).keys()))
        duplicate = ("duplicate_owner_count",) if len(dict(self.peak_counts)) != len(self.peak_counts) else ()
        return missing + duplicate + tuple(key for key, count in self.peak_counts if key not in _LIMITS or isinstance(count, bool) or not isinstance(count, int) or not 0 <= count <= _LIMITS[key])

    def metrics(self) -> dict[str, object]:
        """Measure actual task, motor, sensory and allocation results separately."""
        selected = [c for c in self.cycles if isinstance(c.calculation.navigation.application, SeekNippleApplicationV1)]
        reaches = [c.calculation.cutoff_tick for c in self.cycles if c.seeking_task is not None and c.seeking_task.task is not None
                   and c.seeking_task.task.status == "reached_detail"]
        touches = [p.tick for p in self.physical_samples if p.oral.contact]
        sensed = [s for s in self.local_steps if s.feedback is not None and s.feedback.oral is not None and s.feedback.oral.contact is True]
        task = self.cycles[-1].seeking_task.task if self.cycles and self.cycles[-1].seeking_task is not None else None
        return {"physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
                "focal_opportunities": len(self.cycles), "seeking_applications": len(selected),
                "first_seeking_tick": selected[0].calculation.cutoff_tick if selected else None,
                "first_reached_detail_tick": reaches[0] if reaches else None, "final_task_status": task.status if task is not None else "no_task",
                "first_physical_touch_tick": touches[0] if touches else None,
                "first_delivered_touch_event": sensed[0].feedback.event_tick if sensed and sensed[0].feedback is not None else None,
                "first_touch_consumption_tick": sensed[0].tick if sensed else None,
                "oral_commands": sum(s.command is not None and s.command.oral_drive not in (None, 0.0) for s in self.local_steps),
                "final_physical_reach_metres": self.physical_samples[-1].oral.extension_metres if self.physical_samples else None,
                "target_installations": self.installations, "handoff_consumptions": self.handoff_consumptions,
                "task_prediction_registrations": len(self.registered_pnm_cycles),
                "latch": "not_implemented", "milk": "not_supplied", "rest": "not_implemented", "causal_credit": "not_established"}

    @staticmethod
    def _reach_proof_valid(cycle: IntegratedRightingCycleV1) -> bool:
        """Verify a completed task against its retained original geometry acquisitions."""
        assessment = cycle.seeking_task
        if assessment is None or assessment.task is None or assessment.task.status != "reached_detail":
            return True
        if len(assessment.reach_samples) != 2:
            return False
        first, last = assessment.reach_samples
        start, end = first.maternal.visual.event_tick, last.maternal.visual.event_tick
        return (start is not None and end is not None and 4 <= end - start <= 8
                and first.maternal.visual.sample_id != last.maternal.visual.sample_id
                and all(item.oral_evidence_current and item.mouth_detail_distance is not None
                        and item.mouth_detail_distance <= 0.005 + 1e-12 for item in (first, last)))

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Apply predeclared scope/invariant tests; adverse outcomes may qualify honestly."""
        selected = tuple(c for c in self.cycles if isinstance(c.calculation.navigation.application, SeekNippleApplicationV1))
        oral_targets = tuple(item.current for c in self.cycles for item in c.reservations
                             if item.current.target.kind is SensorimotorTargetKindV1.ORAL_REACH)
        expected_ticks = tuple(range(0, self.profile.horizon_ticks + 1, self.profile.cadence))
        steps_valid = all(s.command is None or s.command.oral_drive in (None, 0.0) or any(
            report.committed_target is target and target.target.origin.stream == s.command.stream
            and target.committed_tick <= s.tick < target.expires_at_tick
            for target in oral_targets for report in s.reports) for s in self.local_steps)
        # The neutral command wire has no task name. Match the actual execution ID
        # via the local reports instead of requiring task context in the motor wire.
        return (
            ("complete_fixed_horizon", tuple(s.tick for s in self.local_steps) == tuple(range(self.profile.horizon_ticks))
             and tuple(c.calculation.cutoff_tick for c in self.cycles) == expected_ticks
             and tuple(p.tick for p in self.physical_samples) == tuple(range(self.profile.horizon_ticks + 1))),
            ("expected_reach_or_bounded_nonreach", (self.metrics()["first_reached_detail_tick"] is not None) == (self.profile.case in _EXPECT_REACH)),
            ("one_source_linked_selection", all(c.calculation.navigation.wnm is not None
             and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in selected)),
            ("original_pnm_before_handoff", all(c.receipt.dispatch.motor is not None and c.receipt.dispatch.motor.projection is not None
             and c.commitment.pnm_id == c.receipt.dispatch.motor.projection.pnm.pnm_id for c in selected)),
            ("original_lease_controls_commands", steps_valid),
            ("oral_resources_exclusive", all(len(c.reservations) == 1 for c in self.cycles
             if any(item.current.target.kind is SensorimotorTargetKindV1.ORAL_REACH for item in c.reservations))),
            ("paired_source_not_new_occurrence", all(c.feeding_detail_source is not None
             and c.feeding_detail_source.maternal is c.maternal_source for c in self.cycles)),
            ("finite_owner_storage", not self.bound_violations),
            ("no_durable_learning", bool(self.durable_before) and self.durable_before == self.durable_after),
            ("one_handoff_per_focal_opportunity", self.handoff_consumptions == len(expected_ticks)),
            ("installations_are_actual_authorizations", self.installations == sum(bool(c.reservations) for c in self.cycles)),
            ("one_task_and_original_physical_budget", len({c.seeking_task.task.task_id for c in self.cycles
             if c.seeking_task is not None and c.seeking_task.task is not None}) <= 1 and all(
             target.expires_at_tick <= c.seeking_task.task.started_tick + 48
             for target in oral_targets for c in self.cycles if c.seeking_task is not None and c.seeking_task.task is not None
             and target.target.origin.task_id == c.seeking_task.task.task_id)),
            ("reach_has_distinct_paired_evidence", all(self._reach_proof_valid(c) for c in self.cycles)),
            ("named_prediction_registration_control", self.registered_pnm_cycles == (
             tuple(c.commitment.cycle_id for c in selected) if self.profile.pnm_registration else ())),
        )

    @property
    def review_status(self) -> str:
        """Report failed evidence rather than emitting an unconditional success banner."""
        return "PASS" if all(value for _, value in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export full original evidence, not a filtered endpoint-only success story."""
        return {"scope": "P16_2C_C_selected_seek_nipple", "profile": self.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in self.cycles], "local_steps": [s.as_dict() for s in self.local_steps],
                "observer_physical_samples": [p.as_dict() for p in self.physical_samples], "final_feedback": self.final_feedback.as_dict(),
                "peak_owner_counts": dict(self.peak_counts), "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
                "durable_before": self.durable_before, "durable_after": self.durable_after,
                "registered_pnm_cycles": list(self.registered_pnm_cycles), "checks": dict(self.checks()), "review_status": self.review_status,
                "feeding_learning": "unimplemented_no_participation", "seeking_pnm_comparison": "deferred", "B99": "open"}


def run_seek_nipple_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SeekNippleExperimentV1:
    """Advance one fixed schedule with no observer-result-dependent task branching."""
    profile = seek_nipple_profile_v1(case)
    trial = create_seek_nipple_trial_v1(case, trace_capacity=trace_capacity)
    return collect_seek_nipple_evidence_v1(trial, profile)


def seek_nipple_owner_limits_v1() -> dict[str, int]:
    """Expose a detached copy of the retained C observer's measured owner bounds."""
    return dict(_LIMITS)


def collect_seek_nipple_evidence_v1(
    trial: IntegratedRightingTrialV1, profile: SeekNippleExperimentProfileV1,
) -> SeekNippleExperimentV1:
    """Collect complete evidence on one fixed external schedule, without task policy.

    Shared by the retained C experiment and the separate D correspondence review.
    The caller has already selected the provider/configuration at construction;
    this driver never interprets an outcome to choose a task. Collection requires
    a fresh idle trial and a finite 1/4/8 cadence within 160 physical ticks.
    Returning this record does not automatically qualify a different experiment
    under C's case-specific review rules; D supplies its own explicit checks.
    """
    if not isinstance(trial, IntegratedRightingTrialV1) or not isinstance(profile, SeekNippleExperimentProfileV1):
        raise TypeError("seeking collection requires its typed trial and frozen profile")
    if trial.tick != 0 or trial.handoff_consumptions or trial.core.last_result is not None:
        raise ValueError("seeking collection requires a fresh trial without earlier focal work")
    if (isinstance(profile.horizon_ticks, bool) or not isinstance(profile.horizon_ticks, int) or not 1 <= profile.horizon_ticks <= 160
            or isinstance(profile.cadence, bool) or not isinstance(profile.cadence, int) or profile.cadence not in (1, 4, 8)):
        raise ValueError("seeking collection requires a finite physical horizon and declared cadence")
    before = _durable_signature(trial)
    cycles: list[IntegratedRightingCycleV1] = []
    steps: list[SensorimotorStepV1] = []
    physical: list[SeekNipplePhysicalSampleV1] = []
    registrations: list[int] = []
    peaks: dict[str, int] = {}

    def inspect() -> None:
        """Read live owner counts after transitions; never send an observation back."""
        for name, count in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), count)

    for tick in range(profile.horizon_ticks + 1):
        planar, oral = trial.observer_planar_body, trial.observer_oral_body
        if planar is None or oral is None:
            raise RuntimeError("seeking observer requires its declared planar/oral physical profile")
        physical.append(SeekNipplePhysicalSampleV1(tick, trial.observer_body, planar, oral))
        if tick == profile.cancel_tick:
            trial.cancel()
        if tick % profile.cadence == 0:
            cycles.append(trial.focal_step(visual_input_enabled=tick not in profile.visual_gap_cutoffs,
                                          visual_bid_priority=(10, 70) if tick in profile.competitor_cutoffs else None))
            if trial.core.cognition.prediction.current_seeking_preview is not None:
                registrations.append(cycles[-1].commitment.cycle_id)
            inspect()
        if tick < profile.horizon_ticks:
            steps.append(trial.advance_lower())
            inspect()
    return SeekNippleExperimentV1(profile, tuple(cycles), tuple(steps), tuple(physical), trial.latest_feedback,
                                  tuple(sorted(peaks.items())), before, _durable_signature(trial), trial.handoff_consumptions,
                                  trial.controller.installation_count, tuple(registrations))


def render_seek_nipple_v1(result: SeekNippleExperimentV1, *, detail: bool = False) -> str:
    """Render retained records; no owner mutation, new simulation or hidden replay."""
    if not isinstance(result, SeekNippleExperimentV1) or not isinstance(detail, bool):
        raise TypeError("seeking render requires the completed experiment and Boolean detail flag")
    metrics = result.metrics()
    lines = [f"P16-2C-C / {result.profile.case} / SELECTED SEEKING REVIEW: {result.review_status}",
             "  Feeding source -> Attention/WNM -> SeekNipple/PNM -> BodyMap -> existing local motor path.",
             f"  physical ticks={metrics['physical_ticks']}; focal opportunities={metrics['focal_opportunities']}; cadence={result.profile.cadence}",
             f"  first selected={metrics['first_seeking_tick']}; reached detail={metrics['first_reached_detail_tick']}; task={metrics['final_task_status']}",
             f"  physical touch={metrics['first_physical_touch_tick']}; delivered touch event={metrics['first_delivered_touch_event']}; consumed={metrics['first_touch_consumption_tick']}",
             f"  oral commands={metrics['oral_commands']}; applications={metrics['seeking_applications']}; final reach={metrics['final_physical_reach_metres']}",
             "  Reach is not touch; touch does not identify a surface, latch, milk or nourishment.",
             "  PNM correspondence and feeding learning remain deferred; Rest and B99 remain open."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        lines.append("  tick | focal source | selected primitive | task reason | body directive")
        for cycle in result.cycles:
            source, motor = cycle.calculation.attention.selected_source_state, cycle.receipt.dispatch.motor
            lines.append(f"  {cycle.calculation.cutoff_tick:4} | {source.source_map_ref.map_id if source is not None else '(none)'} | "
                         f"{cycle.commitment.selected_primitive_id or '(none)'} | {cycle.seeking_task.reason if cycle.seeking_task else '(none)'} | "
                         f"{motor.directive if motor is not None else '(none)'}")
        lines.append("  lower tick | feedback event/available | oral drive | local report")
        for step in result.local_steps:
            feedback, command = step.feedback, step.command
            timing = f"{feedback.event_tick}/{feedback.available_tick}" if feedback is not None else "unknown"
            reports = "; ".join(item.reason for item in step.reports if item.committed_target.target.kind is SensorimotorTargetKindV1.ORAL_REACH)
            lines.append(f"  {step.tick:4} | {timing:12} | {command.oral_drive if command is not None else None!s:8} | {reports}")
    return "\n".join(lines)


def run_seek_nipple_menu_v1() -> None:
    """Offer shared finite cases and a read-only retained-result view without resets."""
    groups = {
        "1": ("nominal", "no_surface", "missing_touch"),
        "2": ("seek_off", "attention_off", "source_off", "no_need", "no_capability", "blocked_motor", "missing_detail", "wrong_category"),
        "3": ("intermediate_target", "heading_90", "rotated_scene", "out_of_reach", "body_shift", "body_turn"),
        "4": ("brief_gap", "prolonged_gap", "dropout", "delayed", "support_loss", "early_contact", "cancelled"),
        "5": ("pnm_registration_off", "competing_on", "influence_off", "cadence_1", "cadence_8"),
        "6": ("stand_follow", "stand_follow_seek_off", "stand_follow_no_surface"), "7": SEEK_NIPPLE_CASES_V1,
    }
    retained: tuple[SeekNippleExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-C -- NAVIGATION-SELECTED SEEKING / NO LATCH, MILK OR REST")
        print("  1) Reach versus touch / 2) Task, source, need and capability controls")
        print("  3) Intermediate reach and body geometry / 4) Gaps, protection and cancellation")
        print("  5) Prediction registration, relevance and cadence / 6) Continuous stand-follow-seeking")
        print("  7) All cases / 8) Inspect last results (detailed; no new movement)")
        print("  [Enter] Return to feeding review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "8":
            print("\n\n".join(render_seek_nipple_v1(item, detail=True) for item in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_seek_nipple_v1(case) for case in groups[choice])
            print("\n\n".join(render_seek_nipple_v1(item) for item in retained))
        else:
            print("Choose 1-8 or press Enter to return.")
