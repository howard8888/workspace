#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first P16-2C-A review: live approach, observed detail and focal access.

All runs reuse the same integrated hierarchy and a fixed eight-second world
horizon. Only external scene/ablation conditions vary. There is no task-stage
list, feeding motor capability or success-token provider. The new detail is a
separate fixed point, visible only inside its declared sensing range. The source
checks its seeded parent relation before ordinary Attention can select it.

The observer can retain complete finite records; cognition never reads them.
Checks qualify this source/access slice, not SeekNipple, latch, feeding, rest or
B99. Contact and milk remain explicitly unobserved, rather than false or zero.
The separate menu-18 P16-2C-B foundation adds supplied oral-target/touch tests;
it does not change any of these P16-2C-A experiments or integrate a feeding IP.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, PlanarDetailObjectV1
from nca8_feeding import FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailNavMapStateV1
from nca8_followmom_demo import follow_mom_owner_limits_v1, maternal_durable_signature_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_oral_demo import run_oral_contact_menu_v1
from nca8_oral_extraction_demo import run_oral_extraction_menu_v1
from nca8_oral_extraction_control_demo import run_oral_extraction_control_menu_v1
from nca8_seek_nipple_demo import run_seek_nipple_menu_v1
from nca8_seek_outcomes_demo import run_seek_nipple_outcome_menu_v1
from nca8_seek_attention_demo import run_seeking_attention_menu_v1
from nca8_seek_learning_demo import run_seeking_learning_menu_v1
from nca8_oral_seal_demo import run_oral_seal_menu_v1
from nca8_suckle_demo import run_suckle_menu_v1
from nca8_suckle_outcomes_demo import run_suckle_outcome_menu_v1
from nca8_suckle_attention_demo import run_suckle_attention_menu_v1
from nca8_suckle_learning_demo import run_suckle_learning_menu_v1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_stand_follow_demo import StandFollowPhysicalSampleV1, StandFollowProfileV1, stand_follow_profile_v1

__version__ = "0.13.0"
__all__ = [
    "FEEDING_DETAIL_CASES_V1", "FeedingDetailExperimentV1", "feeding_detail_profiles_v1", "create_feeding_detail_trial_v1",
    "run_feeding_detail_v1", "render_feeding_detail_v1", "run_feeding_detail_menu_v1", "__version__",
]

FEEDING_DETAIL_CASES_V1 = (
    "nominal", "attention_off", "source_off", "no_feeding_need", "missing_detail", "wrong_category",
    "wrong_detail_seed", "wrong_parent_seed", "incompatible_part", "brief_gap", "prolonged_gap",
    "support_loss", "heading_90", "recognition_off", "spatial_off", "already_near", "support_competition",
)
_LIMITS = {
    **follow_mom_owner_limits_v1(),
    "outcome_pending_claims": 8, "outcome_terminal_history": 32, "outcome_installed_targets": 2,
    "outcome_dwell_samples": 3, "outcome_recent_feedback": 16, "outcome_staged_intervals": 16, "outcome_command_ticks": 16,
    "feeding_detail_durable_maps": 1, "feeding_detail_current_configurations": 1,
}


def feeding_detail_profiles_v1(case: str = "nominal") -> tuple[StandFollowProfileV1, FeedingDetailProfileV1]:
    """Choose declared physical/sensory conditions before any task is selected.

    Parent region_1 remains at (2,1) metres. Detail region_2 is independently at
    (1.82,1), with a 0.4-metre visual radius and a supplied feeding category.
    The incompatible-part control moves ONLY that detail to (1.1,0.7), where it
    becomes visible but fails the seeded 0.3-metre parent-distance constraint.
    Visual gaps are explicit admission interventions at fixed physical cutoffs,
    not simulated retinal occlusion. Support loss is fixed-time external forcing.
    """
    if not isinstance(case, str) or case not in FEEDING_DETAIL_CASES_V1:
        raise ValueError("unknown feeding-detail review case")
    base = stand_follow_profile_v1("nominal")
    detail = PlanarDetailObjectV1("region_2", (1.82, 1.0))
    profile = FeedingDetailProfileV1()
    if case == "wrong_category":
        detail = replace(detail, descriptor="landmark")
    elif case == "incompatible_part":
        detail = replace(detail, position=(1.1, 0.7))
    objects = base.planar.objects if case == "missing_detail" else (*base.planar.objects, detail)
    base = replace(base, case=case, planar=replace(base.planar, objects=objects))
    if case == "attention_off":
        profile = replace(profile, attention_enabled=False)
    elif case == "source_off":
        profile = replace(profile, source_enabled=False)
    elif case == "no_feeding_need":
        profile = replace(profile, feeding_need=False)
    elif case == "wrong_detail_seed":
        profile = replace(profile, seed=FeedingDetailSeedV1(detail_region_id="region_3"))
    elif case == "wrong_parent_seed":
        profile = replace(profile, seed=FeedingDetailSeedV1(parent_region_id="region_3"))
    elif case == "brief_gap":
        base = replace(base, visual_gap_cutoffs=(120,))
    elif case == "prolonged_gap":
        base = replace(base, visual_gap_cutoffs=(120, 124, 128, 132))
    elif case == "support_loss":
        base = replace(base, physical=replace(base.physical, perturbations=(MotorWorldPerturbationV1(117, 161, remove_support=True),)))
    elif case == "heading_90":
        base = replace(base, planar=replace(base.planar, initial_heading=90.0))
    elif case == "recognition_off":
        base = replace(base, maternal=replace(base.maternal, recognition_enabled=False))
    elif case == "spatial_off":
        base = replace(base, maternal=replace(base.maternal, spatial_enabled=False))
    elif case == "support_competition":
        base = replace(base, planar=replace(base.planar, initial_position=(1.58, 0.79)))
    elif case == "already_near":
        base = replace(base, physical=replace(base.physical, initial_body=MotorBodyStateV1(0.0, 1.0)),
                       planar=replace(base.planar, initial_position=(1.58, 0.79)))
    return base, profile


def create_feeding_detail_trial_v1(case: str = "nominal", *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Construct one isolated opt-in source/access run, with no initial world step."""
    base, profile = feeding_detail_profiles_v1(case)
    return IntegratedRightingTrialV1(
        base.physical, stream_id="feeding_detail_reference_body", planar_profile=base.planar,
        follow_mom_profile=base.maternal, translation_capability=base.translation,
        righting_target_inset_degrees=base.target_inset_degrees, task_outcomes_enabled=True,
        stand_follow_enabled=True, trace_capacity=trace_capacity, feeding_detail_profile=profile,
    )


def _durable_signature(trial: IntegratedRightingTrialV1) -> str:
    """Measure actual enduring source content, including the new part seed."""
    owner = trial.core.feeding_detail
    if owner is None:
        raise RuntimeError("feeding-detail review requires its configured source")
    return json.dumps({"existing_sources": maternal_durable_signature_v1(trial), "feeding": owner.durable_map.as_dict()},
                      sort_keys=True, allow_nan=False)


def _selected_source(cycle: IntegratedRightingCycleV1) -> str | None:
    """Read actual Attention selection, not the external experiment's expected case."""
    source = cycle.calculation.attention.selected_source_state
    return None if source is None else source.source_map_ref.map_id


@dataclass(frozen=True, slots=True)
class FeedingDetailExperimentV1:
    """Completed finite observer records; no live source or actuator permission."""

    base_profile: StandFollowProfileV1
    feeding_profile: FeedingDetailProfileV1
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
        """Reject unknown owner counts and measured overflows, not just known ones."""
        required = {"durable_maps", "current_source_states", "wnm", "current_pnm",
                    "feeding_detail_durable_maps", "feeding_detail_current_configurations"}
        missing = tuple(f"missing:{name}" for name in sorted(required - dict(self.peak_counts).keys()))
        invalid = tuple(name for name, value in self.peak_counts if name not in _LIMITS or not 0 <= value <= _LIMITS[name])
        return missing + invalid

    @property
    def durable_unchanged(self) -> bool:
        """Compare actual enduring maps before and after source/access processing."""
        return bool(self.durable_before) and self.durable_before == self.durable_after

    def metrics(self) -> dict[str, object]:
        """Measure focal access separately from movement and missing oral evidence."""
        visible = [c.calculation.cutoff_tick for c in self.cycles
                   if c.feeding_detail_source is not None and c.feeding_detail_source.detail_position is not None]
        focal = [c.calculation.cutoff_tick for c in self.cycles if _selected_source(c) == "feeding_detail"]
        proximity = [c.calculation.cutoff_tick for c in self.cycles
                     if c.maternal_task is not None and c.maternal_task.task is not None and c.maternal_task.task.status == "completed"]
        return {"case": self.base_profile.case, "physical_ticks": len(self.local_steps), "focal_opportunities": len(self.cycles),
                "elapsed_seconds": len(self.local_steps) * 0.05, "first_localized_detail_tick": visible[0] if visible else None,
                "first_feeding_detail_focus_tick": focal[0] if focal else None, "feeding_detail_focal_opportunities": len(focal),
                "maternal_proximity_completed_tick": proximity[0] if proximity else None,
                "target_installations": self.target_installations, "handoff_consumptions": self.handoff_consumptions,
                "feeding_task_applications": sum(c.commitment.selected_primitive_id in {"ip:seek_nipple", "ip:suckle", "ip:rest"}
                                                 for c in self.cycles), "feeding_motor_authority": False,
                "contact_evidence": "not_supplied", "latch_evidence": "not_supplied", "milk_evidence": "not_supplied",
                "rest": "not_implemented", "durable_learning_updates": 0}

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Apply explicit source-slice checks; no broad feeding/B99 qualification.

        Empty or truncated records fail the clock/evidence checks. An adverse
        case can pass by withholding unsupported access, not by claiming feeding.
        Expected-access cases are predeclared, not derived from the observed result.
        """
        selected = tuple(c for c in self.cycles if _selected_source(c) == "feeding_detail")
        expect_access = self.base_profile.case in {"nominal", "brief_gap", "prolonged_gap", "support_loss", "heading_90", "already_near", "support_competition"}
        return (
            ("complete_fixed_horizon", tuple(s.tick for s in self.local_steps) == tuple(range(160)) and
             tuple(c.calculation.cutoff_tick for c in self.cycles) == tuple(range(0, 161, 4)) and len(self.physical_samples) == 161),
            ("expected_access_or_withholding", bool(selected) == expect_access),
            ("one_source_linked_wnm", all(c.calculation.navigation.wnm is not None and
             c.calculation.navigation.wnm.primary_source_state is c.feeding_detail_source for c in selected)),
            ("no_feeding_dispatch_or_pnm", all(c.commitment.selected_primitive_id is None and not c.reservations and
             c.calculation.proposal is None and c.receipt.dispatch.motor is not None and
             c.receipt.dispatch.motor.projection is None for c in selected)),
            ("source_is_actual_common_evidence", all(c.feeding_detail_source is not None and
             c.feeding_detail_source.maternal is c.maternal_source for c in self.cycles)),
            ("bounded_owners", not self.bound_violations),
            ("no_durable_learning", self.durable_unchanged),
            ("ordinary_handoff_count", self.handoff_consumptions == 41),
        )

    @property
    def review_status(self) -> str:
        """Return PASS only for all declared checks of this individual source slice."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export complete detached evidence, including limitations and failed checks."""
        return {"scope": "P16_2C_A_source_and_focal_access_only", "base_profile": self.base_profile.as_dict(),
                "feeding_profile": self.feeding_profile.as_dict(), "metrics": self.metrics(),
                "cycles": [c.as_dict() for c in self.cycles], "local_steps": [s.as_dict() for s in self.local_steps],
                "observer_physical_samples": [s.as_dict() for s in self.physical_samples],
                "final_delivered_feedback": self.final_feedback.as_dict(), "peak_owner_counts": dict(self.peak_counts),
                "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
                "durable_unchanged": self.durable_unchanged, "review_checks": dict(self.checks()), "review_status": self.review_status,
                "feeding_learning": "unimplemented_no_participation", "restores_motor_permission": False,
                "full_P16_2C": "open_task_contact_latch_suckle_nourishment_rest", "B99": "open"}


def run_feeding_detail_v1(case: str = "nominal", *, trace_capacity: int = 256) -> FeedingDetailExperimentV1:
    """Run one fixed horizon through the existing core, handoff, executor and world.

    The only intervention is a predeclared input-gap schedule. No branch consults
    task status, observed access or a milestone to choose the next physical step.
    All observers are detached from cognition; rendering cannot affect execution.
    """
    base, profile = feeding_detail_profiles_v1(case)
    trial = create_feeding_detail_trial_v1(case, trace_capacity=trace_capacity)
    before = _durable_signature(trial)
    cycles: list[IntegratedRightingCycleV1] = []
    steps: list[SensorimotorStepV1] = []
    physical: list[StandFollowPhysicalSampleV1] = []
    peaks: dict[str, int] = {}

    def inspect() -> None:
        """Read actual bounded owner counts without feeding them back to the core."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    for tick in range(161):
        body = trial.observer_planar_body
        if body is None:
            raise RuntimeError("feeding review requires its external planar body")
        physical.append(StandFollowPhysicalSampleV1(tick, trial.observer_body, body))
        if tick % 4 == 0:
            cycles.append(trial.focal_step(visual_input_enabled=tick not in base.visual_gap_cutoffs))
            inspect()
        if tick < 160:
            steps.append(trial.advance_lower())
            inspect()
    return FeedingDetailExperimentV1(base, profile, tuple(cycles), tuple(steps), tuple(physical), trial.latest_feedback,
                                    tuple(sorted(peaks.items())), before, _durable_signature(trial),
                                    trial.handoff_consumptions, trial.controller.installation_count)


def render_feeding_detail_v1(result: FeedingDetailExperimentV1, *, detail: bool = False) -> str:
    """Render retained source/access evidence without stepping or changing any owner."""
    if not isinstance(result, FeedingDetailExperimentV1) or not isinstance(detail, bool):
        raise TypeError("render requires a feeding-detail experiment and Boolean detail option")
    metrics = result.metrics()
    lines = [f"P16-2C-A / {result.base_profile.case} / SOURCE-ACCESS REVIEW: {result.review_status}",
             "One existing body/world run; separate maternal and feeding sources; one selected WNM.",
             f"  Physical ticks={len(result.local_steps)}; focal opportunities={len(result.cycles)}; dt=0.05 seconds.",
             f"  First observed detail: {metrics['first_localized_detail_tick']}; first feeding focus: {metrics['first_feeding_detail_focus_tick']}.",
             f"  Maternal proximity completion: {metrics['maternal_proximity_completed_tick']}; no feeding application or motor target.",
             "  Contact/latch/milk: NOT SUPPLIED. SeekNipple/Suckle/Rest and B99 remain open.",
             "  Need/category/part relation are declared scaffolds, not acquired identity or an interoceptive learner.",
             f"  Durable maps unchanged={result.durable_unchanged}; owner-bound violations={result.bound_violations or 'none'}."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        lines.append("  tick | visual event | feeding association | actual WNM source | actual primitive")
        for cycle in result.cycles:
            source = cycle.feeding_detail_source
            if not isinstance(source, FeedingDetailNavMapStateV1):
                lines.append(f"  {cycle.calculation.cutoff_tick}: feeding evidence absent")
                continue
            lines.append(f"  {cycle.calculation.cutoff_tick:4} | {source.maternal.visual.event_tick!s:12} | "
                         f"{source.association_status:27} | {_selected_source(cycle)!s:16} | "
                         f"{cycle.commitment.selected_primitive_id or '(none)'}")
    return "\n".join(lines)


def run_feeding_detail_menu_v1() -> None:
    """Inspect fresh isolated runs via the common functions; touch no caller session."""
    while True:
        print("\nFeeding detail / P16-2C-A: source and focal access only")
        print("  0) All cases (compact)")
        for index, case in enumerate(FEEDING_DETAIL_CASES_V1, 1):
            print(f"  {index}) {case}")
        print("  18) Oral target/contact foundation (P16-2C-B; supplied requirement)")
        print("  19) Navigation-selected SeekNipple (P16-2C-C; no latch, milk or rest)")
        print("  20) Original seeking prediction and actual execution (P16-2C-D)")
        print("  21) Seeking mismatch and one focal interpretation (P16-2C-E)")
        print("  22) Seeking participation and actual Phase F (P16-2C-F; no durable learning)")
        print("  23) Supplied oral closure and observed seal (P16-2C-G; no Suckle or milk)")
        print("  24) Navigation-selected Suckle: initial latch (P16-2C-H; no milk)")
        print("  25) Original Suckle prediction and actual execution (P16-2C-I)")
        print("  26) Suckle discrepancy to Attention and one Navigation interpretation (P16-2C-J)")
        print("  27) Original Suckle participation and Phase F (P16-2C-K; no durable learning)")
        print("  28) Direct-drive physical extraction and milk sensing (P16-2C-L-A; not autonomous Suckle)")
        print("  29) BodyMap extraction/return target control (P16-2C-L-B; supplied requirement)")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "29":
            run_oral_extraction_control_menu_v1()
        elif choice == "28":
            run_oral_extraction_menu_v1()
            continue
        if choice == "27":
            run_suckle_learning_menu_v1()
            continue
        if choice == "26":
            run_suckle_attention_menu_v1()
            continue
        if choice == "25":
            run_suckle_outcome_menu_v1()
            continue
        if choice == "24":
            run_suckle_menu_v1()
            continue
        if choice == "23":
            run_oral_seal_menu_v1()
            continue
        if choice == "22":
            run_seeking_learning_menu_v1()
            continue
        if choice == "21":
            run_seeking_attention_menu_v1()
            continue
        if choice == "20":
            run_seek_nipple_outcome_menu_v1()
            continue
        if choice == "19":
            run_seek_nipple_menu_v1()
            continue
        if choice == "18":
            run_oral_contact_menu_v1()
        elif choice == "0":
            for case in FEEDING_DETAIL_CASES_V1:
                print(render_feeding_detail_v1(run_feeding_detail_v1(case)))
        elif choice.isascii() and choice.isdigit() and 1 <= int(choice) <= len(FEEDING_DETAIL_CASES_V1):
            print(render_feeding_detail_v1(run_feeding_detail_v1(FEEDING_DETAIL_CASES_V1[int(choice) - 1]), detail=True))
        else:
            print("Choose a displayed number, or press Enter to return.")
