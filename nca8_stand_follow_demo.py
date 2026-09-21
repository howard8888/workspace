#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Continuous P16-2B-C stand-to-follow review on the existing isolated hierarchy.

One body, clock, Attention/Navigation pair, source ensemble and target executor
run throughout. This external driver supplies only fixed initial conditions,
capabilities and sensory/physical interventions. It never selects a task from a
stage, a completion flag or a private-world milestone. Righting and Follow-Mom
use their own source evidence, finite task lifetimes and outcome consumers.

The named stand_follow_v1 profile aims two degrees inside the unchanged
12-degree mobility boundary, allowing for the retained one-degree local target
tolerance. The zero-inset control retains the old boundary aim. This is fixed
calibration, not learned competence or a relaxed success criterion. A 160-tick
observer horizon accommodates two independent at-most-80-tick tasks; neither
task budget is enlarged. With four lower updates per focal opportunity the run
has 41 focal reads, below the carried-forward 60-cycle newborn target. This is
not the full hard-newborn benchmark, feeding, maternal outcome routing or B99.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1,
    PlanarObjectV1, PlanarWorldProfileV1, PlanarWorldStateV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import follow_mom_owner_limits_v1, maternal_durable_signature_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_sensorimotor import SensorimotorStepV1

__version__ = "0.1.2"
__all__ = [
    "STAND_FOLLOW_CASES_V1", "StandFollowProfileV1", "StandFollowPhysicalSampleV1", "StandFollowExperimentV1",
    "stand_follow_profile_v1", "create_stand_follow_trial_v1", "run_stand_follow_v1", "render_stand_follow_v1",
    "run_stand_follow_menu_v1", "__version__",
]

STAND_FOLLOW_CASES_V1 = (
    "nominal", "brief_gap", "prolonged_gap", "support_loss", "boundary_aim", "righting_off", "following_off",
    "association_off", "translation_unavailable", "heading_90", "different_target", "already_supported",
    "motor_blocked", "maternal_comparison_off",
)
_OWNER_LIMITS = {
    **follow_mom_owner_limits_v1(),
    "outcome_pending_claims": 8, "outcome_terminal_history": 32, "outcome_installed_targets": 2,
    "outcome_dwell_samples": 3, "outcome_recent_feedback": 16, "outcome_staged_intervals": 16, "outcome_command_ticks": 16,
}


@dataclass(frozen=True, slots=True)
class StandFollowProfileV1:
    """Fixed external experiment settings; no desired task order is stored here.

    Cases alter one named condition, retaining the reference plant equations,
    local timing/tolerances and separate task budgets. Gap cutoffs are focal
    admission interventions, not raw-pixel occlusion physics. The original
    physical acquisitions and their event times are never rewritten.
    """

    case: str
    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    maternal: FollowMomProfileV1
    translation: BodyTranslationCapabilityV1 | None
    target_inset_degrees: float = 2.0
    righting_enabled: bool = True
    visual_gap_cutoffs: tuple[int, ...] = ()

    def as_dict(self) -> dict[str, object]:
        """Disclose initial conditions; retain the original disabled-route export schema."""
        maternal = asdict(self.maternal)
        if not self.maternal.learning_hook_enabled:
            maternal.pop("learning_hook_enabled")
        if not self.maternal.outcome_attention_enabled:
            maternal.pop("outcome_attention_enabled")
        return {
            "profile": "stand_follow_v1", "case": self.case,
            "physical": asdict(self.physical), "planar": asdict(self.planar), "maternal": maternal,
            "translation_capability": None if self.translation is None else self.translation.as_dict(),
            "righting_target_inset_degrees": self.target_inset_degrees, "righting_enabled": self.righting_enabled,
            "visual_gap_focal_cutoffs": list(self.visual_gap_cutoffs), "focal_interval_ticks": 4,
            "physical_horizon_ticks": 160, "physical_tick_seconds": 0.05,
            "each_task_maximum_ticks": 80, "each_task_maximum_focal_opportunities": 20,
            "mobility_maximum_absolute_tilt_degrees": 12.0, "local_orientation_tolerance_degrees": 1.0,
            "supported_completion_samples": 3, "minimum_completion_span_ticks": 8,
            "maternal_adequate_separation_metres": 0.5, "maternal_approach_aim_metres": 0.48,
            "maternal_identity": "declared_developmental_association_not_learned",
        }


def stand_follow_profile_v1(case: str = "nominal") -> StandFollowProfileV1:
    """Choose a fixed profile before execution; no outcome-dependent world changes.

    Nominal starts at the retained 30-degree tilt/0.4 extension. The brief gap
    withholds visual admission at tick60; the prolonged gap also withholds
    cutoffs64..76. Support loss is physical absence over intervals[57,161).
    These times are independent of which tasks actually execute. The initially
    supported control can follow without any Righting task, disproving a forced
    Righting-first runner list. Adverse results are reported, never rescued.
    """
    if not isinstance(case, str) or case not in STAND_FOLLOW_CASES_V1:
        raise ValueError("unknown stand-follow experiment")
    physical = MotorWorldProfileV1()
    planar = PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2.0, 1.0)),))
    maternal = FollowMomProfileV1(outcomes_enabled=True)
    translation = None if case == "translation_unavailable" else BodyTranslationCapabilityV1()
    gaps: tuple[int, ...] = ()
    if case == "brief_gap":
        gaps = (60,)
    elif case == "prolonged_gap":
        gaps = (60, 64, 68, 72, 76)
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(57, 161, remove_support=True),))
    elif case == "following_off":
        maternal = replace(maternal, following_enabled=False)
    elif case == "association_off":
        maternal = replace(maternal, association_enabled=False)
    elif case == "heading_90":
        planar = replace(planar, initial_heading=90.0)
    elif case == "different_target":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (2.0, -1.0)),))
    elif case == "already_supported":
        physical = replace(physical, initial_body=MotorBodyStateV1(0.0, 1.0))
    elif case == "motor_blocked":
        planar = replace(planar, motor_enabled=False)
    elif case == "maternal_comparison_off":
        maternal = replace(maternal, prediction_comparison_enabled=False)
    return StandFollowProfileV1(case, physical, planar, maternal, translation,
                                 0.0 if case == "boundary_aim" else 2.0, case != "righting_off", gaps)


def create_stand_follow_trial_v1(case: str = "nominal", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct one fresh stream with both ordinary task candidates available.

    No focal work or physical increment occurs here. The source readiness check
    and supported-dwell monitoring are enabled together with the separate
    Righting/maternal correspondence consumers. The trial has no stage field.
    """
    profile = stand_follow_profile_v1(case)
    return IntegratedRightingTrialV1(
        profile.physical, stream_id="stand_follow_reference_body", planar_profile=profile.planar,
        follow_mom_profile=profile.maternal, translation_capability=profile.translation,
        righting_enabled=profile.righting_enabled, righting_target_inset_degrees=profile.target_inset_degrees,
        task_outcomes_enabled=True, stand_follow_enabled=True, trace_capacity=trace_capacity,
    )


@dataclass(frozen=True, slots=True)
class StandFollowPhysicalSampleV1:
    """One external observation of private physics, never a cognitive input packet."""

    tick: int
    support: MotorBodyStateV1
    planar: PlanarWorldStateV1

    def as_dict(self) -> dict[str, object]:
        """Export observer truth separately from possibly older admitted sensing."""
        return {"tick": self.tick, "support_body": asdict(self.support), "planar_body": self.planar.as_dict()}


@dataclass(frozen=True, slots=True)
class StandFollowExperimentV1:
    """A finite completed observer export, not a task sequencer or saved organism.

    All metrics are computed after the shared driver has finished. The live
    agent never reads them. Completion is taken from its actual evidence-backed
    task records; prediction outcomes and physical coordinates remain separate.
    """

    profile: StandFollowProfileV1
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[StandFollowPhysicalSampleV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str
    handoff_consumptions: int
    target_installations: int

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check every actually measured owner count, including unknown new owners."""
        return tuple(name for name, value in self.peak_counts if name not in _OWNER_LIMITS or not 0 <= value <= _OWNER_LIMITS[name])

    @property
    def durable_unchanged(self) -> bool:
        """Compare all three actual enduring source organizations before and after."""
        return self.durable_before == self.durable_after

    def metrics(self) -> dict[str, object]:
        """Read the task sequence that occurred, without imposing one on execution."""
        supported = [c.calculation.cutoff_tick for c in self.cycles
                     if c.calculation.task is not None and c.calculation.task.status == "completed"]
        retired = [c.calculation.cutoff_tick for c in self.cycles
                   if c.calculation.task is not None and c.calculation.task.status == "completed"
                   and c.receipt.dispatch.motor is not None and c.receipt.dispatch.motor.directive == "cancel"]
        following = [c.calculation.cutoff_tick for c in self.cycles if c.commitment.selected_primitive_id == "ip:follow_mom"]
        translated = [c.calculation.cutoff_tick for c in self.cycles
                      if c.commitment.selected_primitive_id == "ip:follow_mom" and c.reservations]
        proximity = [c.calculation.cutoff_tick for c in self.cycles
                     if c.maternal_task is not None and c.maternal_task.task is not None and c.maternal_task.task.status == "completed"]
        last = self.cycles[-1]
        task = None if last.maternal_task is None else last.maternal_task.task
        return {
            "case": self.profile.case, "physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
            "focal_opportunities": len(self.cycles), "righting_supported_at_tick": supported[0] if supported else None,
            "righting_terminal_cancel_at_tick": retired[0] if retired else None,
            "first_follow_application_at_tick": following[0] if following else None,
            "first_translation_install_at_tick": translated[0] if translated else None,
            "maternal_proximity_completed_at_tick": proximity[0] if proximity else None,
            "support_to_follow_authority_transition": bool(retired and translated and retired[0] < translated[0]),
            "stood_and_reached": bool(supported and proximity and supported[0] < proximity[0]),
            "righting_final_status": last.calculation.task.status if last.calculation.task is not None else "no_task",
            "maternal_final_status": task.status if task is not None else "no_task",
            "maternal_applications": task.applications if task is not None else 0,
            "handoff_consumptions": self.handoff_consumptions, "target_installations": self.target_installations,
            "final_sensed_separation": last.maternal_source.separation if last.maternal_source is not None else None,
            "observer_final_position": self.physical_samples[-1].planar.position,
            "causal_credit": "not_established_by_completion", "durable_learning_updates": 0,
        }

    def as_dict(self) -> dict[str, object]:
        """Export distinct source/task, command and physical lanes; restore no rights."""
        return {
            "profile": self.profile.as_dict(), "metrics": self.metrics(),
            "cycles": [item.as_dict() for item in self.cycles], "local_steps": [item.as_dict() for item in self.local_steps],
            "observer_physical_samples": [item.as_dict() for item in self.physical_samples],
            "final_delivered_feedback": self.final_feedback.as_dict(), "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_OWNER_LIMITS), "bound_violations": list(self.bound_violations),
            "durable_unchanged": self.durable_unchanged, "restores_motor_permission": False,
            "full_P16_2B": "open_maternal_mismatch_to_attention_and_no_learning_reconciliation",
            "B99": "open_feeding_rest_and_full_hard_newborn_qualification",
        }


def run_stand_follow_v1(case: str = "nominal", *, trace_capacity: int = 256) -> StandFollowExperimentV1:
    """Run exactly 160 physical increments, with no reset or task-dependent branch.

    The only focal-input intervention is the predeclared visual-admission gap.
    Completion neither stops nor extends the horizon. Local protection and each
    selected task's own finite budget determine continuation or failure. Observer
    collection and renderer retention cannot change any cognitive decision.
    """
    profile = stand_follow_profile_v1(case)
    trial = create_stand_follow_trial_v1(case, trace_capacity=trace_capacity)
    before = maternal_durable_signature_v1(trial)
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[StandFollowPhysicalSampleV1] = []
    peaks: dict[str, int] = {}

    def inspect(*, include_physics: bool = False) -> None:
        """Read actual owner bounds and, when requested, the external physical lane."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)
        if include_physics:
            planar = trial.observer_planar_body
            if planar is None:
                raise RuntimeError("stand-follow observer lost its physical planar body")
            physical.append(StandFollowPhysicalSampleV1(trial.tick, trial.observer_body, planar))

    inspect(include_physics=True)
    for tick in range(160):
        if tick % 4 == 0:
            cycles.append(trial.focal_step(visual_input_enabled=tick not in profile.visual_gap_cutoffs))
            inspect()
        local.append(trial.advance_lower())
        inspect(include_physics=True)
    cycles.append(trial.focal_step())
    inspect()
    return StandFollowExperimentV1(profile, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback,
                                   tuple(sorted(peaks.items())), before, maternal_durable_signature_v1(trial),
                                   trial.handoff_consumptions, trial.controller.installation_count)


def render_stand_follow_v1(result: StandFollowExperimentV1, *, detail: bool = False) -> str:
    """Render completed evidence only; no read causes source selection or world work."""
    if not isinstance(result, StandFollowExperimentV1) or not isinstance(detail, bool):
        raise TypeError("stand-follow rendering requires a completed result and Boolean detail")
    lines = [f"P16-2B-C CONTINUOUS STAND -> FOLLOW-MOM | {result.profile.case}",
             "  One body / one clock / one WNM; no runner stage list or evaluator input.",
             f"  Target inset={result.profile.target_inset_degrees:.1f} degrees; task criterion remains 12 degrees; local tolerance remains 1 degree.",
             "  Fixed 160 lower ticks / 8.0 seconds / 41 focal reads; each task retains its own 80-tick / 20-opportunity cap.",
             f"  Evidence-backed results: {result.metrics()}"]
    for cycle in result.cycles:
        calculation = cycle.calculation
        working = calculation.navigation.wnm
        source = None if working is None else working.primary_source_state.source_map_ref.map_id
        maternal = cycle.maternal_source
        assessment = cycle.maternal_task
        motor = cycle.receipt.dispatch.motor
        lines.append(f"  focal {calculation.cutoff_tick}: WNM={source}; IP={cycle.commitment.selected_primitive_id}; "
                     f"Righting={None if calculation.task is None else calculation.task.status}; "
                     f"maternal={None if assessment is None else assessment.reason}; directive={None if motor is None else motor.directive}")
        if detail:
            lines.append(f"    maternal identity={None if maternal is None else maternal.identity_status}; "
                         f"last sensory support={None if maternal is None else maternal.last_supported_tick}; "
                         f"uncertainty={None if maternal is None else maternal.uncertainty_radius}; "
                         f"separation={None if maternal is None else maternal.separation}")
            lines.append(f"    Righting evidence={None if cycle.task_outcome is None else cycle.task_outcome.as_dict()}")
            lines.append(f"    maternal task evidence={None if assessment is None else assessment.as_dict()}")
            if motor is not None and motor.projection is not None:
                lines.append(f"    original PNM={motor.projection.as_dict()}")
            for reservation in cycle.reservations:
                lines.append(f"    authorized BodyMap target={reservation.current.as_dict()}")
            for righting_outcome in cycle.claim_outcomes:
                lines.append(f"    Righting PNM={righting_outcome.status}; commands={righting_outcome.command_intervals}")
            if cycle.maternal_correspondence is not None:
                for maternal_outcome in cycle.maternal_correspondence.outcomes:
                    lines.append(f"    maternal PNM={maternal_outcome.status}; commands={maternal_outcome.command_intervals}; "
                                 f"event={None if maternal_outcome.evidence is None else maternal_outcome.evidence.event_tick}; "
                                 f"relations={dict(maternal_outcome.relations)}")
    if detail:
        for step, physical in zip(result.local_steps, result.physical_samples[1:]):
            lines.append(f"  lower {step.tick}: command={None if step.command is None else step.command.as_dict()}; "
                         f"observer-after={physical.as_dict()}")
    lines.extend((f"  bounds={list(result.bound_violations)}; durable unchanged={result.durable_unchanged}; durable updates=0",
                  "  Seeded maternal identity; completion is not causal credit, learned identity or a prediction verdict.",
                  "  Full P16-2B remains open for maternal mismatch-to-Attention and no-learning reconciliation.",
                  "  No feeding/rest, full hard-newborn qualification, B99 or default-runtime promotion is claimed."))
    return "\n".join(lines)


def run_stand_follow_menu_v1() -> None:
    """Expose identical isolated experiments from NCA8 menu 11; preserve the displayed A0 session."""
    groups = {"1": ("nominal",), "2": ("brief_gap", "prolonged_gap", "support_loss"),
              "3": ("nominal", "boundary_aim", "righting_off", "following_off", "association_off", "translation_unavailable"),
              "4": ("heading_90", "different_target", "already_supported", "motor_blocked", "maternal_comparison_off"),
              "5": STAND_FOLLOW_CASES_V1, "6": ("nominal",), "7": ("brief_gap",)}
    while True:
        print("\nP16-2B-C -- CONTINUOUS STAND -> FOLLOW-MOM\n"
              "  1) Nominal continuous run\n  2) Brief/prolonged visual gaps and physical support loss\n"
              "  3) Target margin and selective mechanism controls\n  4) Heading, destination, supported start and outcome control\n"
              "  5) All profiles\n  6) Detailed nominal timeline\n  7) Detailed brief-gap timeline\n"
              "  [Enter] Return to NCA8 menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice not in groups:
            print("Choose 1-7 or press Enter to return.")
            continue
        for case in groups[choice]:
            print(render_stand_follow_v1(run_stand_follow_v1(case), detail=choice in {"6", "7"}))
