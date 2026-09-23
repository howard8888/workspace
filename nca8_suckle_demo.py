#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-H: selected initial latch on the common feeding and motor hierarchy.

The retained C collector advances the fixed external schedule. This observer
adds no task-order list, second world or motor loop. A near at-contact start
isolates Suckle; separate seek-then-latch and continuous stand/follow cases use
real earlier operations in the same run. Surface sealability is private physics,
never a task input. The first Suckle scope ends at latch, not milk or full feeding.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_support_world import (
    MotorWorldPerturbationV1, OralSealWorldProfileV1, PlanarDetailObjectV1, PlanarObjectV1, PlanarPerturbationV1,
)
from nca8_body_targets import BodyAxisCapabilityV1, BodyTranslationCapabilityV1, nominal_body_capabilities_v1
from nca8_body_targets import oral_body_capability_v1, oral_closure_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_seek_attention_demo import seeking_attention_owner_limits_v1
from nca8_seek_nipple import SeekNippleApplicationV1
from nca8_seek_nipple_demo import SeekNippleExperimentProfileV1, SeekNippleExperimentV1, collect_seek_nipple_evidence_v1
from nca8_seek_nipple_demo import seek_nipple_profile_v1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1
from nca8_suckle import SuckleApplicationV1, SuckleProfileV1

__version__ = "0.3.0"
__all__ = ["SUCKLE_LATCH_CASES_V1", "SuckleExperimentProfileV1", "SuckleExperimentV1", "suckle_profile_v1",
           "create_suckle_trial_v1", "suckle_owner_limits_v1", "run_suckle_v1", "render_suckle_v1", "run_suckle_menu_v1", "__version__"]

SUCKLE_LATCH_CASES_V1 = (
    "nominal", "suckle_off", "attention_off", "source_off", "no_need", "wrong_category", "missing_detail",
    "no_touch", "touch_elsewhere", "missing_touch", "missing_closure", "missing_seal", "nonsealable",
    "already_sealed", "closed_without_seal", "no_capability", "blocked_motor", "narrowed", "dropout", "delayed",
    "support_loss", "body_shift", "brief_gap", "prolonged_gap", "seal_loss_after", "cancelled",
    "pnm_registration_off", "competing_on", "influence_off", "cadence_1", "cadence_8",
    "seek_then_latch", "seek_then_suckle_off", "stand_follow", "stand_follow_suckle_off",
)
_LATCH_CASES = frozenset({"nominal", "narrowed", "brief_gap", "seal_loss_after", "pnm_registration_off", "competing_on",
                         "influence_off", "cadence_1", "cadence_8", "seek_then_latch", "stand_follow"})
_NO_APPLICATION_CASES = frozenset({"suckle_off", "attention_off", "source_off", "no_need", "wrong_category", "missing_detail",
                                  "no_touch", "touch_elsewhere", "missing_touch", "missing_closure", "already_sealed",
                                  "closed_without_seal", "seek_then_suckle_off", "stand_follow_suckle_off"})
_LIMITS = {**seeking_attention_owner_limits_v1(), "seeking_learning_participants": 8, "seeking_learning_dispositions": 32,
           "suckle_tasks": 1, "suckle_source_bases": 1, "suckle_targets": 1, "suckle_applications": 8, "suckle_latch_samples": 2}


@dataclass(frozen=True, slots=True)
class SuckleExperimentProfileV1:
    """Fixed run conditions and optional task/capability, never an action sequence."""

    run: SeekNippleExperimentProfileV1
    suckle: SuckleProfileV1
    seal: OralSealWorldProfileV1
    capability: BodyAxisCapabilityV1 | None

    def as_dict(self) -> dict[str, object]:
        """Disclose the full provider/schedule and narrow task scope before results."""
        return {"schedule_and_sources": self.run.as_dict(), "suckle": self.suckle.as_dict(), "seal": asdict(self.seal),
                "closure_capability": None if self.capability is None else self.capability.as_dict(),
                "scope": "selected_initial_latch_not_full_feeding"}


def suckle_profile_v1(case: str = "nominal") -> SuckleExperimentProfileV1:
    """Choose fixed conditions without consulting any task or physical result.

    Nominal starts at the accepted G mouth/detail point (0.1,0). Seeking cases
    instead start at zero oral extension. Continuous cases retain the C scene:
    Mom (2,0), detail (1.8,0). Latch is never an instruction derived from another
    task's completion. The same seed/geometry need not identify actual sealability.
    """
    if not isinstance(case, str) or case not in SUCKLE_LATCH_CASES_V1:
        raise ValueError("unknown selected Suckle latch case")
    continuous = case.startswith("stand_follow")
    seeking_start = continuous or case.startswith("seek_then")
    base = seek_nipple_profile_v1("stand_follow" if continuous else "nominal")
    detail = (1.8, 0.0) if continuous else (0.1, 0.0)
    surface = PlanarObjectV1("latch_surface", detail, 0.004)
    oral = replace(base.oral, initial_extension_metres=0.0 if seeking_start else 0.1,
                   surfaces=() if case == "no_touch" else (surface,), contact_available=case != "missing_touch")
    seal = OralSealWorldProfileV1(
        initial_closure=0.6 if case in {"already_sealed", "closed_without_seal"} else 0.0,
        sealable_surfaces=() if case in {"nonsealable", "closed_without_seal"} else (surface,),
        closure_available=case != "missing_closure", seal_available=case != "missing_seal", motor_enabled=case != "blocked_motor",
    )
    physical, planar = base.physical, base.planar
    if case in {"dropout", "support_loss"}:
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(
            1, 65, drop_feedback=case == "dropout", remove_support=case == "support_loss"),))
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case in {"body_shift", "seal_loss_after"}:
        start = 12 if case == "seal_loss_after" else 1
        planar = replace(planar, perturbations=(PlanarPerturbationV1(start, start + 1, velocity=(0.2, 0.0)),))
    if case == "missing_detail":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (0.2, 0.0)),))
    if case in {"wrong_category", "touch_elsewhere"}:
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (0.2, 0.0)), PlanarDetailObjectV1(
            "region_2", (0.15, 0.0) if case == "touch_elsewhere" else detail,
            descriptor="landmark" if case == "wrong_category" else "feeding")))
    run = replace(base, case=case, physical=physical, planar=planar, oral=oral,
                  feeding=replace(base.feeding, source_enabled=case != "source_off", attention_enabled=case != "attention_off",
                                  feeding_need=case != "no_need"),
                  seeking=replace(base.seeking, outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True),
                  pnm_registration=case != "pnm_registration_off", cadence=1 if case == "cadence_1" else 8 if case == "cadence_8" else 4,
                  visual_gap_cutoffs=(4,) if case == "brief_gap" else (4, 8, 12, 16) if case == "prolonged_gap" else (),
                  competitor_cutoffs=(4,) if case in {"competing_on", "influence_off"} else (),
                  cancel_tick=2 if case == "cancelled" else None)
    capability = None if case == "no_capability" else oral_closure_capability_v1()
    if case == "narrowed" and capability is not None:
        capability = replace(capability, maximum_step=0.3)
    task = SuckleProfileV1(enabled=case not in {"suckle_off", "seek_then_suckle_off", "stand_follow_suckle_off"},
                          influence_enabled=case != "influence_off")
    return SuckleExperimentProfileV1(run, task, seal, capability)


def create_suckle_trial_v1(
    case: str = "nominal", *, trace_capacity: int = 256, outcomes_enabled: bool = False, compare_predictions: bool = True,
    outcome_attention_enabled: bool = False,
) -> IntegratedRightingTrialV1:
    """Construct the common H hierarchy with an optional I observation-only consumer.

    The correspondence switches do not alter physical profiles, source timing,
    selection, target mapping or H's latch rule. Default H export stays unchanged.
    J may explicitly enable its source-relevance consumer; default H/I callers
    remain unchanged. No task is selected and no physical interval runs here.
    """
    profile = suckle_profile_v1(case)
    run = profile.run
    return IntegratedRightingTrialV1(
        run.physical, stream_id="suckle_latch_reference_body", planar_profile=run.planar, oral_profile=run.oral,
        oral_seal_profile=profile.seal, suckle_profile=replace(profile.suckle, outcomes_enabled=outcomes_enabled,
                                                           prediction_comparison_enabled=compare_predictions,
                                                           outcome_attention_enabled=outcome_attention_enabled),
        capabilities=(*nominal_body_capabilities_v1(), oral_body_capability_v1(), *((profile.capability,) if profile.capability else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=run.stand_follow,
                                             outcome_attention_enabled=run.stand_follow, learning_hook_enabled=run.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=run.feeding,
        seek_nipple_profile=run.seeking, stand_follow_enabled=run.stand_follow,
        task_outcomes_enabled=run.stand_follow, task_outcome_attention_enabled=run.stand_follow,
        task_learning_hook_enabled=run.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=run.pnm_registration, trace_capacity=trace_capacity,
    )


@dataclass(frozen=True, slots=True)
class SuckleExperimentV1:
    """Complete observer evidence and this experiment's own qualification rules.

    The shared collector does not make C's case-specific claims valid for H.
    This wrapper supplies the H checks, full scope and all retained source,
    task, motor, physical and prediction evidence without using its old labels.
    """

    profile: SuckleExperimentProfileV1
    run: SeekNippleExperimentV1

    def metrics(self) -> dict[str, object]:
        """Measure actual selection, closure, seal and latch separately."""
        selected = [cycle for cycle in self.run.cycles if isinstance(cycle.calculation.navigation.application, SuckleApplicationV1)]
        latched = [cycle.calculation.cutoff_tick for cycle in self.run.cycles if cycle.suckle_task is not None
                   and cycle.suckle_task.task is not None and cycle.suckle_task.task.status == "latch_established"]
        sealed = [item.tick for item in self.run.physical_samples if item.seal is not None and item.seal.sealed]
        sources = [cycle.feeding_detail_source for cycle in self.run.cycles if cycle.feeding_detail_source is not None]
        sensed = [item for item in sources if item.seal_correspondence_status == "compatible"]
        seeking = [cycle.calculation.cutoff_tick for cycle in self.run.cycles
                   if isinstance(cycle.calculation.navigation.application, SeekNippleApplicationV1)]
        final = self.run.cycles[-1].suckle_task if self.run.cycles else None
        state = self.run.physical_samples[-1].seal if self.run.physical_samples else None
        return {"physical_ticks": len(self.run.local_steps), "focal_opportunities": len(self.run.cycles),
                "first_suckle_tick": selected[0].calculation.cutoff_tick if selected else None,
                "first_seeking_tick": seeking[0] if seeking else None,
                "first_geometric_reach_tick": self.run.metrics()["first_reached_detail_tick"],
                "first_physical_seal_tick": sealed[0] if sealed else None,
                "first_source_seal_event": sensed[0].maternal.visual.event_tick if sensed else None,
                "first_source_seal_cutoff": sensed[0].cutoff_tick if sensed else None,
                "latch_established_tick": latched[0] if latched else None,
                "suckle_applications": len(selected),
                "closure_commands": sum(item.command is not None and item.command.oral_closure_drive not in (None, 0.0)
                                        for item in self.run.local_steps),
                "final_closure": state.closure if state else None, "final_physical_seal": state.sealed if state else None,
                "final_task_status": final.task.status if final is not None and final.task is not None else "no_task",
                "final_current_seal": final.current_seal_status if final else "unavailable",
                "target_installations": self.run.installations, "handoff_consumptions": self.run.handoff_consumptions,
                "registered_suckle_pnm_cycles": list(self.run.registered_suckle_pnm_cycles),
                "milk": "not_supplied", "full_suckle_complete": False, "causal_credit": "not_established"}

    @staticmethod
    def _proof_valid(cycle: IntegratedRightingCycleV1) -> bool:
        """Check the original supported latch samples, not the latest world state."""
        assessment = cycle.suckle_task
        if assessment is None or assessment.task is None or assessment.task.status != "latch_established":
            return True
        samples = assessment.latch_samples
        if len(samples) != 2:
            return False
        start, end = samples[0].maternal.visual.event_tick, samples[1].maternal.visual.event_tick
        return (start is not None and end is not None and assessment.task.started_tick < start and 4 <= end - start <= 8
                and samples[0].maternal.visual.sample_id != samples[1].maternal.visual.sample_id
                and all(item.oral_evidence_current and item.seal_correspondence_status == "compatible" for item in samples))

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Apply fixed positive/adverse expectations and actual causal-boundary checks."""
        metrics = self.metrics()
        selected = tuple(c for c in self.run.cycles if isinstance(c.calculation.navigation.application, SuckleApplicationV1))
        targets = tuple(item.current for cycle in self.run.cycles for item in cycle.reservations
                        if item.current.target.kind is SensorimotorTargetKindV1.ORAL_CLOSURE)
        counts = dict(self.run.peak_counts)
        case = self.profile.run.case
        correct_ownership = all(
            step.command is None or step.command.oral_closure_drive in (None, 0.0) or any(
                report.committed_target is target and target.target.origin.stream == step.command.stream
                and target.committed_tick <= step.tick < target.expires_at_tick
                for target in targets for report in step.reports) for step in self.run.local_steps
        )
        return (
            ("fixed_physical_horizon", len(self.run.local_steps) == self.profile.run.horizon_ticks),
            ("one_physical_update_per_lower_tick", tuple(s.tick for s in self.run.local_steps) == tuple(range(self.profile.run.horizon_ticks))),
            ("fixed_focal_schedule", tuple(c.calculation.cutoff_tick for c in self.run.cycles)
             == tuple(range(0, self.profile.run.horizon_ticks + 1, self.profile.run.cadence))),
            ("expected_latch_or_bounded_noncompletion", (metrics["latch_established_tick"] is not None) == (case in _LATCH_CASES)),
            ("expected_application_gate", bool(selected) == (case not in _NO_APPLICATION_CASES)),
            ("one_focal_source_and_pnm", counts.get("wnm") == 1 and counts.get("current_pnm", 0) <= 1),
            ("selected_current_feeding_source", all(c.calculation.navigation.wnm is not None
             and c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in selected)),
            ("actual_closure_requires_authorized_target", correct_ownership),
            ("closure_request_was_navigation_selected", all(isinstance(c.calculation.navigation.application, SuckleApplicationV1)
             for c in self.run.cycles if any(r.current.target.kind is SensorimotorTargetKindV1.ORAL_CLOSURE for r in c.reservations))),
            ("original_target_and_preview_link", all(isinstance(c.calculation.navigation.application, SuckleApplicationV1)
             and c.receipt.dispatch.motor is not None
             and c.receipt.dispatch.motor.projection is c.calculation.navigation.application.projection for c in selected)),
            ("distinct_post_start_latch_evidence", all(self._proof_valid(c) for c in self.run.cycles)),
            ("bounded_live_owners", len(counts) == len(self.run.peak_counts) and all(
                key in _LIMITS and isinstance(count, int) and not isinstance(count, bool) and 0 <= count <= _LIMITS[key]
                for key, count in self.run.peak_counts)),
            ("task_and_physical_deadlines_not_renewed", len({
                (c.suckle_task.task.task_id, c.suckle_task.task.started_cycle, c.suckle_task.task.started_tick)
                for c in self.run.cycles if c.suckle_task is not None and c.suckle_task.task is not None}) <= 1
             and all(target.expires_at_tick - target.committed_tick <= 8 for target in targets)
             and all(isinstance(c.calculation.navigation.application, SuckleApplicationV1)
                     and c.calculation.cutoff_tick + c.calculation.navigation.application.contribution.lease_ticks
                     <= c.calculation.navigation.application.task.started_tick + 48 for c in selected)),
            ("no_durable_learning", self.run.durable_before == self.run.durable_after),
            ("one_handoff_consumption_per_cycle", self.run.handoff_consumptions == len(self.run.cycles)),
            ("registration_only_control", self.run.registered_suckle_pnm_cycles == (
                tuple(c.commitment.cycle_id for c in selected) if self.profile.run.pnm_registration else ())),
            ("no_full_feeding_or_milk_claim", all(c.suckle_task is None or not c.suckle_task.as_dict()["full_suckle_complete"]
                                                for c in self.run.cycles)),
        )

    @property
    def review_status(self) -> str:
        """Report the measured check result; an adverse case can legitimately pass."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export full unfiltered evidence under H's actual scope rather than C's labels."""
        return {"scope": "P16_2C_H_selected_suckle_initial_latch", "profile": self.profile.as_dict(), "metrics": self.metrics(),
                "cycles": [item.as_dict() for item in self.run.cycles], "local_steps": [item.as_dict() for item in self.run.local_steps],
                "observer_physical_samples": [item.as_dict() for item in self.run.physical_samples],
                "final_feedback": self.run.final_feedback.as_dict(), "peak_owner_counts": dict(self.run.peak_counts),
                "owner_limits": dict(_LIMITS), "durable_before": self.run.durable_before, "durable_after": self.run.durable_after,
                "checks": dict(self.checks()), "review_status": self.review_status, "B99": "open",
                "suckle_pnm_correspondence": "deferred", "suckle_learning": "unimplemented_no_participation"}


def suckle_owner_limits_v1() -> dict[str, int]:
    """Return detached H storage limits for additive experimental qualification.

    New observers may extend these limits in their own review. They cannot edit
    the retained H bounds or silently discard new counters to claim boundedness.
    """
    return dict(_LIMITS)


def run_suckle_v1(case: str = "nominal", *, trace_capacity: int = 256) -> SuckleExperimentV1:
    """Run the retained shared clock/collector with one fixed H configuration."""
    profile = suckle_profile_v1(case)
    trial = create_suckle_trial_v1(case, trace_capacity=trace_capacity)
    return SuckleExperimentV1(profile, collect_seek_nipple_evidence_v1(trial, profile.run))


def render_suckle_v1(result: SuckleExperimentV1, *, detail: bool = False) -> str:
    """Render retained evidence without new physics, cognition or hidden replay."""
    if not isinstance(result, SuckleExperimentV1) or not isinstance(detail, bool):
        raise TypeError("Suckle renderer needs a completed experiment and Boolean detail")
    metrics = result.metrics()
    lines = [f"P16-2C-H / {result.profile.run.case} / SELECTED INITIAL LATCH REVIEW: {result.review_status}",
             "  Current feeding contact -> Attention/WNM -> Suckle/PNM -> protected closure -> later seal evidence.",
             f"  Selected={metrics['first_suckle_tick']}; physical seal={metrics['first_physical_seal_tick']}; "
             f"source seal event/cutoff={metrics['first_source_seal_event']}/{metrics['first_source_seal_cutoff']}",
             f"  Latch evidence complete={metrics['latch_established_tick']}; task={metrics['final_task_status']}; "
             f"current seal={metrics['final_current_seal']}",
             f"  Closure commands={metrics['closure_commands']}; applications={metrics['suckle_applications']}; "
             f"final closure={metrics['final_closure']}; physical seal={metrics['final_physical_seal']}",
             "  Initial latch only: no milk/nourishment, full Suckle, Rest, Suckle PNM comparison or learning claim."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        lines.append("  cutoff | focal source | selected operation | latch reason | handoff")
        for cycle in result.run.cycles:
            source, motor = cycle.calculation.attention.selected_source_state, cycle.receipt.dispatch.motor
            lines.append(f"  {cycle.calculation.cutoff_tick:4} | {source.source_map_ref.map_id if source else '(none)'} | "
                         f"{cycle.commitment.selected_primitive_id or '(none)'} | "
                         f"{cycle.suckle_task.reason if cycle.suckle_task else '(none)'} | {motor.directive if motor else '(none)'}")
        lines.append("  Original projections and latch evidence: " + json.dumps(
            [{"cutoff": cycle.calculation.cutoff_tick,
              "preview": cycle.receipt.dispatch.motor.projection.as_dict()
              if cycle.receipt.dispatch.motor is not None and cycle.receipt.dispatch.motor.projection is not None else None,
              "latch": cycle.suckle_task.as_dict() if cycle.suckle_task is not None else None}
             for cycle in result.run.cycles], sort_keys=True, allow_nan=False))
    return "\n".join(lines)


def run_suckle_menu_v1() -> None:
    """Offer fixed experiments and read-only inspection through the feeding menu."""
    groups = {"1": ("nominal", "nonsealable", "missing_seal", "already_sealed", "closed_without_seal"),
              "2": ("suckle_off", "attention_off", "no_need", "no_capability", "blocked_motor", "narrowed"),
              "3": ("dropout", "delayed", "support_loss", "brief_gap", "prolonged_gap", "seal_loss_after", "cancelled"),
              "4": ("seek_then_latch", "seek_then_suckle_off", "stand_follow", "stand_follow_suckle_off"),
              "5": SUCKLE_LATCH_CASES_V1}
    retained: tuple[SuckleExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-H -- SELECTED SUCKLE: INITIAL LATCH ONLY, NOT MILK OR FULL FEEDING")
        print("  1) Seal versus closure/evidence / 2) Selection, permission and narrowed contribution")
        print("  3) Missing evidence, protection and later seal loss / 4) Seeking and continuous stand-follow-latch")
        print("  5) All cases / 6) Inspect retained detail without new movement / [Enter] Return")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            print("\n\n".join(render_suckle_v1(item, detail=True) for item in retained) if retained else "No completed results to inspect.")
        elif choice in groups:
            retained = tuple(run_suckle_v1(case) for case in groups[choice])
            print("\n\n".join(render_suckle_v1(item) for item in retained))
        else:
            print("Unknown choice; no movement was performed.")
