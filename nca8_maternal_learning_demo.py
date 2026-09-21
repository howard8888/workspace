#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2B-E: live maternal no-learning/F reviews and separate routing fixtures.

The hook-on/off pairs hold the body, source/Attention rules, task, motor profile
and physical horizon fixed. Only source-owned temporary eligibility changes.
The live runs never use evaluator results to select a task or a runner stage.
The two explicitly synthetic routing fixtures instead supply canonical interval
and sensor records to the real core. They test an original recipient after focus
and current-access loss; they are not physics or a general Ready implementation.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, PlanarDriveV1, PlanarFeedbackV1
from cca8_navmap_kernel import NavPointV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1,
    PlanarObjectV1, PlanarPerturbationV1, PlanarWorldProfileV1, PlanarWorldStateV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import follow_mom_owner_limits_v1, maternal_durable_signature_v1
from nca8_hierarchy import IntegratedRightingCoreV1, IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_learning_registry import render_learning_ledger_v1
from nca8_maternal_outcomes import MaternalIntervalEvidenceV1
from nca8_outcome_attention_demo import outcome_attention_owner_limits_v1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, LocalTargetReportV1
from nca8_visual import VisualDetectionV1, VisualObservationV1

__version__ = "0.1.0"
__all__ = [
    "MATERNAL_LEARNING_CASES_V1", "MaternalLearningExperimentV1", "create_maternal_learning_trial_v1",
    "run_maternal_learning_v1", "render_maternal_learning_v1", "run_maternal_learning_routing_fixture_v1",
    "render_maternal_learning_routing_fixture_v1", "run_maternal_learning_menu_v1", "__version__",
]
MATERNAL_LEARNING_CASES_V1 = (
    "nominal_on", "nominal_off", "competing_on", "competing_off", "protected_competitor", "unresolved_current",
    "support_loss", "narrowed", "veto", "delayed_feedback", "fast_cadence", "assisted", "assisted_no_task",
    "attention_off", "comparison_off", "brief_gap", "prolonged_gap", "stand_follow", "stand_drift",
)
_LIMITS = {
    **outcome_attention_owner_limits_v1(), **follow_mom_owner_limits_v1(),
    "maternal_attention_pending_requests": 8, "maternal_attention_previous_endpoint": 1,
    "maternal_attention_dependency": 1, "maternal_attention_dispositions": 32,
    "learning_participants": 8, "learning_dispositions": 32,
    "maternal_learning_participants": 8, "maternal_learning_dispositions": 32,
}


def create_maternal_learning_trial_v1(
    case: str, *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> IntegratedRightingTrialV1:
    """Construct a fixed profile without selecting a task or advancing the body.

    Nominal/competing pairs differ only in the maternal hook switch. Drift uses
    the already qualified 2B-D external intervals [6,8) and [14,16); stand drift
    offsets them by 40. Support loss and missing-current cases keep their 2B-D
    timing. Narrowing limits the supplied translation capability to 0.10 metre,
    without changing the original projection. Faster cadence changes only focal
    sampling, not physical time or the four-cycle eligibility definition.
    """
    if not isinstance(case, str) or case not in MATERNAL_LEARNING_CASES_V1:
        raise ValueError("unknown maternal no-learning experiment")
    stand = case in {"stand_follow", "stand_drift"}
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1() if stand else MotorBodyStateV1(0.0, 1.0))
    planar = PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2.0, 1.0)),))
    if case in {"competing_on", "competing_off", "protected_competitor", "unresolved_current", "support_loss",
                "attention_off", "stand_drift"}:
        offset = 40 if stand else 0
        planar = replace(planar, perturbations=(PlanarPerturbationV1(offset + 6, offset + 8, velocity=(0.6, 0.3)),
                                                PlanarPerturbationV1(offset + 14, offset + 16, velocity=(0.6, 0.3))))
    if case == "unresolved_current":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(17, 81, drop_feedback=True),))
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(20, 81, remove_support=True),))
    elif case == "delayed_feedback":
        physical = replace(physical, sensor_delay_ticks=4)
    elif case == "veto":
        planar = replace(planar, heading_available=False)
    elif case in {"assisted", "assisted_no_task"}:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 21, velocity=(1.6, 0.8)),))
    profile = FollowMomProfileV1(
        outcomes_enabled=True, outcome_attention_enabled=case != "attention_off",
        prediction_comparison_enabled=case != "comparison_off", following_enabled=case != "assisted_no_task",
        learning_hook_enabled=case not in {"nominal_off", "competing_off"},
    )
    capability = BodyTranslationCapabilityV1(maximum_step=0.1) if case == "narrowed" else BodyTranslationCapabilityV1()
    return IntegratedRightingTrialV1(
        physical, stream_id="maternal_learning_reference_body", planar_profile=planar, follow_mom_profile=profile,
        translation_capability=capability, trace_capacity=trace_capacity, learning_diagnostic_capacity=diagnostic_capacity,
        task_outcomes_enabled=stand, task_learning_hook_enabled=stand,
        stand_follow_enabled=stand, righting_target_inset_degrees=2.0 if stand else 0.0,
    )


def _visual_priority(case: str, tick: int) -> tuple[int, int] | None:
    """Supply ordinary relevance, never force a winner or supply outcome evidence."""
    if case in {"competing_on", "competing_off", "attention_off"} and tick in (16, 20):
        return (10, 60)
    if case == "protected_competitor" and 16 <= tick <= 32:
        return (11, 60)
    return None


@dataclass(frozen=True, slots=True)
class MaternalLearningExperimentV1:
    """Completed observer-only data, not an eligibility owner or restorable organism."""

    case: str
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[PlanarWorldStateV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str
    fixed_configuration_unchanged: bool

    @property
    def durable_unchanged(self) -> bool:
        """Compare the actual enduring body, visual and maternal map organizations."""
        return self.durable_before == self.durable_after

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check all measured owner counts, rejecting undeclared storage as well."""
        return tuple(name for name, count in self.peak_counts if name not in _LIMITS or not 0 <= count <= _LIMITS[name])

    def metrics(self) -> dict[str, object]:
        """Report actual F work separately from task success, interpretation and physics."""
        reports = tuple(item.maternal_learning_report for item in self.cycles if item.maternal_learning_report is not None)
        dispositions = tuple(item for report in reports for item in report.dispositions)
        task_frame = self.cycles[-1].maternal_task
        task = None if task_frame is None else task_frame.task
        return {
            "case": self.case, "physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
            "focal_opportunities": len(self.cycles), "maternal_F_calls": len(reports),
            "righting_F_calls": sum(item.learning_report is not None for item in self.cycles),
            "new_participants": sum(report.new_participation is not None for report in reports),
            "dispositions": dict(sorted(Counter(item.status for item in dispositions).items())),
            "interpretation_ticks": [item.calculation.cutoff_tick for item in self.cycles if item.maternal_attention is not None
                                     and item.maternal_attention.allocation.kind == "interpretation"],
            "response_ticks": [item.calculation.cutoff_tick for item in self.cycles if item.maternal_attention is not None
                                and item.maternal_attention.allocation.kind == "response_reconsideration"],
            "pending_at_horizon": len(reports[-1].pending) if reports else 0,
            "maternal_final_status": task.status if task is not None else "no_task",
            "proximity_completed_at_tick": next((item.calculation.cutoff_tick for item in self.cycles
                                                  if item.maternal_task is not None and item.maternal_task.task is not None
                                                  and item.maternal_task.task.status == "completed"), None),
            "target_installations": sum(bool(item.reservations) for item in self.cycles),
            "command_intervals": sum(item.command is not None for item in self.local_steps),
            "durable_learning_updates": 0, "causal_credit": "not_established_by_completion",
        }

    def as_dict(self) -> dict[str, object]:
        """Export detached finite results; no renderer replays cognition or owner work."""
        return {
            "profile": "maternal_no_learning_review_v1", "metrics": self.metrics(),
            "cycles": [item.as_dict() for item in self.cycles], "local_steps": [item.as_dict() for item in self.local_steps],
            "observer_planar_samples": [asdict(item) for item in self.physical_samples],
            "final_feedback": self.final_feedback.as_dict(), "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
            "durable_unchanged": self.durable_unchanged, "fixed_configuration_unchanged": self.fixed_configuration_unchanged,
            "restores_motor_permission": False, "L12_maturity": "eligibility_only_no_durable_rule",
            "B99": "open_feeding_rest_and_full_newborn_qualification",
        }


def run_maternal_learning_v1(
    case: str = "nominal_on", *, trace_capacity: int = 256, diagnostic_capacity: int = 32,
) -> MaternalLearningExperimentV1:
    """Run the real hierarchy at a fixed horizon, without success-driven extra cycles.

    Narrowing uses the supported eight-tick cadence so the original eight-tick
    endpoint is not continually interrupted by earlier replacement. Faster focal
    cadence uses one tick. All others retain four ticks. Only stand profiles have
    160 physical ticks; others have 80. Each task keeps its original own budget.
    """
    trial = create_maternal_learning_trial_v1(case, trace_capacity=trace_capacity, diagnostic_capacity=diagnostic_capacity)
    before = maternal_durable_signature_v1(trial)
    if trial.core.follow_mom is None:
        raise RuntimeError("maternal review requires the configured operation")
    fixed_before = (trial.core.cognition.mapper.capabilities, trial.controller.profile,
                    trial.core.cognition.righting.context, trial.core.follow_mom.profile)
    horizon = 160 if case in {"stand_follow", "stand_drift"} else 80
    cadence = 1 if case == "fast_cadence" else 8 if case == "narrowed" else 4
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[PlanarWorldStateV1] = []
    peaks: dict[str, int] = {}

    def observe() -> None:
        """Inspect actual bounded storage without letting diagnostics control the run."""
        for name, count in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), count)

    for tick in range(horizon):
        if tick % cadence == 0:
            visual_enabled = not (case == "brief_gap" and tick == 12 or case == "prolonged_gap" and 12 <= tick <= 28)
            cycles.append(trial.focal_step(visual_input_enabled=visual_enabled, visual_bid_priority=_visual_priority(case, tick)))
            observe()
        local.append(trial.advance_lower())
        body = trial.observer_planar_body
        if body is None:
            raise RuntimeError("maternal review lost its planar provider")
        physical.append(body)
        observe()
    cycles.append(trial.focal_step(visual_bid_priority=_visual_priority(case, horizon)))
    observe()
    fixed_after = (trial.core.cognition.mapper.capabilities, trial.controller.profile,
                   trial.core.cognition.righting.context, trial.core.follow_mom.profile)
    return MaternalLearningExperimentV1(case, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback,
                                       tuple(sorted(peaks.items())), before, maternal_durable_signature_v1(trial), fixed_before == fixed_after)


def run_maternal_learning_routing_fixture_v1(*, expired: bool = False) -> tuple[IntegratedRightingCycleV1, ...]:
    """Run real C2/D/E/F on supplied records, explicitly without physical world steps.

    A real selected Follow-Mom application is authorized and installed. Only the
    subsequent command/exact-endpoint records are synthetic fixtures. Current A
    loses localization/access while B becomes focal; historical evidence still
    addresses the original maternal recipient. The expired variant adds focal
    opportunities, not new physical evidence, so eligibility expires before the
    same original endpoint arrives. No general Ready/offloading claim is made.
    """
    if not isinstance(expired, bool):
        raise TypeError("expired must be Boolean")
    stream = MotorStreamRefV1("maternal_learning_routing_fixture", 1)
    core = IntegratedRightingCoreV1(stream, follow_mom_profile=FollowMomProfileV1(
        outcomes_enabled=True, outcome_attention_enabled=True, learning_hook_enabled=True,
    ), translation_capability=BodyTranslationCapabilityV1())
    initial = MotorFeedbackV1(stream, 1, 0, 0, 0.0, 1.0, True, 1.0, 0.0,
                              planar=PlanarFeedbackV1("scene_xy:lab", (0.0, 0.0), 0.0, False))
    visual = VisualObservationV1(stream, 1, 0, 0, "scene_xy:lab", NavPointV1(0.0, 0.0),
                                 (VisualDetectionV1("region_1", "object", NavPointV1(2.0, 1.0)),))
    first = core.run_cycle(initial, cutoff_tick=0, visual_observation=visual)
    core.handoff.consume_motor(first.receipt)
    controller = SensorimotorExecutorV1(core.cognition.mapper, installation_source=core.handoff)
    controller.install_authorized(first.reservations, at_tick=0)
    registration = first.maternal_correspondence.registration if first.maternal_correspondence is not None else None
    publisher = core.maternal_outcomes
    if registration is None or publisher is None:
        raise RuntimeError("routing fixture did not produce an actual maternal claim")
    publisher.installed(registration, at_tick=0)
    position = registration.preview.predicted_self
    endpoint = replace(visual, sample_id=9, event_tick=8, available_tick=9, self_position=position)
    motor_endpoint = replace(initial, sample_id=9, event_tick=8, available_tick=9,
                             planar=PlanarFeedbackV1("scene_xy:lab", (position.x, position.y), 0.0, False))
    records = [first]
    previous_tick = 0
    cutoffs = (1, 2, 3, 4, 12) if expired else (4, 12)
    for cycle, tick in enumerate(cutoffs, 2):
        intervals: list[MaternalIntervalEvidenceV1] = []
        for event in range(previous_tick, tick):
            disposition = LocalTargetDispositionV1.ACTIVE if event < 8 else LocalTargetDispositionV1.EXPIRED
            reports = tuple(LocalTargetReportV1(target, disposition, event, "supplied_maternal_routing_fixture")
                            for target in registration.targets)
            command = MotorCommandV1(stream, event + 1, event, translation=PlanarDriveV1(0.5, 0.25)) if event < 8 else None
            intervals.append(MaternalIntervalEvidenceV1(event, command, reports, (motor_endpoint,) if event == 8 else (),
                                                        (endpoint,) if event == 8 else ()))
        bid = replace(competing_preview_bid_v1(cycle), protected_safety_rank=1, novelty_or_ambiguity_rank=10)
        focal = core.run_cycle(None, cutoff_tick=tick, competing_bids=(bid,), maternal_intervals=tuple(intervals))
        core.handoff.consume_motor(focal.receipt)
        records.append(focal)
        previous_tick = tick
    return tuple(records)


def _f_lines(focal: IntegratedRightingCycleV1) -> list[str]:
    """Describe the actual recorded F work; never call a recipient while displaying it."""
    report = focal.maternal_learning_report
    selected = focal.calculation.attention.selected_bid
    lines = [f"  cycle={focal.commitment.cycle_id} tick={focal.calculation.cutoff_tick}; "
             f"WNM={selected.candidate_id if selected is not None else 'none'}; IP={focal.commitment.selected_primitive_id}"]
    if report is None:
        lines.append("    maternal hook disabled; no maternal eligibility owner called")
        return lines
    lines.append(f"    F recipient={report.recipient_id}; pending={len(report.pending)}; durable updates=0")
    if report.new_participation is not None:
        part = report.new_participation
        lines.append(f"    new participation={part.pnm_id}; expires before cycle={part.expires_before_cycle}; no future outcome yet")
    for item in report.dispositions:
        lines.append(f"    {item.pnm_id}: {item.status}; known={dict(item.accepted_relations)}; "
                     f"interpretation={item.interpretation.status if item.interpretation is not None else 'not_required_or_pending'}")
    return lines


def render_maternal_learning_routing_fixture_v1(records: tuple[IntegratedRightingCycleV1, ...]) -> str:
    """Keep supplied historical evidence and general Ready limitations visible."""
    if not records or any(item.maternal_learning_report is None for item in records):
        raise ValueError("routing display needs actual hook-enabled core records")
    lines = ["P16-2B-E ORIGINAL-RECIPIENT ROUTING FIXTURE -- NO PHYSICAL WORLD STEPS",
             "  A participated; B later focal; A current localization/access absent.",
             "  Supplied command and endpoint records; not a general Ready/offloading implementation."]
    for focal in records:
        lines.extend(_f_lines(focal))
    return "\n".join(lines)


def render_maternal_learning_v1(result: MaternalLearningExperimentV1, *, detail: bool = False) -> str:
    """Display one completed experiment with explicitly zero durable learning."""
    if not isinstance(result, MaternalLearningExperimentV1) or not isinstance(detail, bool):
        raise TypeError("maternal learning display requires a completed result and Boolean detail")
    lines = [f"P16-2B-E MATERNAL PARTICIPATION / PHASE F | {result.case}",
             "  Eight candidate participants; four focal-cycle eligibility; independent claim/request/target lifetimes.",
             "  Original maternal owner receives old evidence; F performs no free interpretation or new action.",
             f"  Results: {result.metrics()}"]
    for focal in result.cycles:
        lines.extend(_f_lines(focal))
        if detail:
            lines.append(f"    F record={focal.maternal_learning_report.as_dict() if focal.maternal_learning_report else None}")
            lines.append(f"    original correspondence={focal.maternal_correspondence.as_dict() if focal.maternal_correspondence else None}")
    lines.extend([f"  bounds={list(result.bound_violations)}; durable unchanged={result.durable_unchanged}; "
                  f"fixed configuration unchanged={result.fixed_configuration_unchanged}",
                  "  L12 remains eligibility-only; no learned identity, calibration, LP or causal action credit.",
                  "  Feeding/rest and full newborn qualification remain open; no B99 or default promotion."])
    return "\n".join(lines)


def run_maternal_learning_menu_v1() -> None:
    """Offer shared read-only reviews without touching the retained A0 session."""
    groups = {
        "1": ("nominal_on", "nominal_off", "competing_on", "competing_off"),
        "2": ("protected_competitor", "unresolved_current", "attention_off", "comparison_off"),
        "3": ("narrowed", "veto", "support_loss", "delayed_feedback", "fast_cadence"),
        "4": ("assisted", "assisted_no_task", "brief_gap", "prolonged_gap"),
        "5": ("stand_follow", "stand_drift"), "6": MATERNAL_LEARNING_CASES_V1,
        "9": ("competing_on", "unresolved_current"),
    }
    while True:
        print("\nMATERNAL NO-LEARNING / PHASE F REVIEW (P16-2B-E)")
        print("  1) Hook on/off: unchanged cognition and physical control")
        print("  2) Interpretation dependency, protected delay and route controls")
        print("  3) Narrowing, veto, support loss, delayed sensing and faster cadence")
        print("  4) Assistance and visual gaps / 5) Continuous stand-follow, two original recipients")
        print("  6) All live profiles / 7) Original recipient and independent expiry (synthetic fixtures)")
        print("  8) Read L01-L25 inventory (no trial) / 9) Detailed interpretation and unresolved evidence")
        print("  Enter returns without resetting the existing session")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "7":
            for expired in (False, True):
                print(render_maternal_learning_routing_fixture_v1(run_maternal_learning_routing_fixture_v1(expired=expired)))
        elif choice == "8":
            print(render_learning_ledger_v1())
        elif choice in groups:
            for case in groups[choice]:
                print(render_maternal_learning_v1(run_maternal_learning_v1(case), detail=choice == "9"))
        else:
            print("Choose 1-9 or press Enter to return.")
