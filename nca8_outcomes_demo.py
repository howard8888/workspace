#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu/script review of the opt-in P16-1G-A task-evidence path.

Every experiment uses the existing integrated core, BodyMap, H4 executor and H2
world. Case labels and perturbations stay outside cognition. All runs keep the
same eighty .05-second physical intervals, including after a task completes.
The original nominal case is not retuned to cross its strict activity boundary.
An externally assisted case demonstrates supported completion without claiming
that the agent's earlier commands caused the result. No file or RNG is touched.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

import cca8_cli
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_hierarchy_demo import focal_hierarchy_lines_v1, lower_hierarchy_lines_v1
from nca8_outcomes import RightingClaimOutcomeV1, RightingClaimRegistrationV1
from nca8_righting import RightingActivityV1, RightingContextV1
from nca8_sensorimotor import SensorimotorStepV1

__version__ = "0.1.0"
__all__ = [
    "RIGHTING_OUTCOME_CASES_V1", "RightingOutcomeExperimentV1", "run_righting_outcome_v1",
    "render_righting_outcome_v1", "render_righting_outcome_summary_v1", "run_righting_outcome_menu_v1", "__version__",
]
RIGHTING_OUTCOME_CASES_V1 = (
    "nominal", "disturbed", "support_loss", "feedback_missing", "blocked_orientation", "narrowed", "veto",
    "assisted", "assisted_no_task", "assisted_comparison_off", "context_change",
)
_OUTCOME_LIMITS = {
    "outcome_pending_claims": 8, "outcome_terminal_history": 32, "outcome_installed_targets": 2,
    "outcome_dwell_samples": 3, "outcome_recent_feedback": 16, "outcome_staged_intervals": 16, "outcome_command_ticks": 16,
    "durable_maps": 1, "current_source_states": 1, "wnm": 1, "current_pnm": 1,
}


@dataclass(frozen=True, slots=True)
class RightingOutcomeExperimentV1:
    """A finite observer export; no objects in it can restore motor permission."""

    case: str
    intervals: tuple[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]], ...]
    final_cycle: IntegratedRightingCycleV1
    outcomes: tuple[RightingClaimOutcomeV1, ...]
    pending: tuple[RightingClaimRegistrationV1, ...]
    final_body: MotorBodyStateV1
    peak_counts: tuple[tuple[str, int], ...]

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check measured live-owner peaks, not the size of an exported timeline."""
        counts = dict(self.peak_counts)
        return tuple(name for name, maximum in _OUTCOME_LIMITS.items() if not 0 <= counts.get(name, -1) <= maximum)

    def metrics(self) -> dict[str, object]:
        """Keep lifecycle, evidential progress, prediction fit and causal credit apart."""
        cycles = tuple(item[0] for item in self.intervals) + (self.final_cycle,)
        task = self.final_cycle.calculation.task
        completions = [item.calculation.cutoff_tick for item in cycles if item.task_outcome is not None and item.task_outcome.completion_supported]
        return {
            "case": self.case, "physical_ticks": 80, "simulation_seconds": 4.0, "focal_reads": len(cycles),
            "task_lifecycle": task.status if task is not None else "no_task",
            "task_completed": task is not None and task.status == "completed",
            "first_supported_completion_cutoff": completions[0] if completions else None,
            "task_evidence_counts": dict(Counter(item.task_outcome.status for item in cycles if item.task_outcome is not None)),
            "prediction_outcome_counts": dict(Counter(item.status for item in self.outcomes)),
            "pending_endpoint_claims": len(self.pending),
            "nonnull_commands": sum(step.command is not None for _, lower in self.intervals for step in lower),
            "observer_final_tilt": self.final_body.body_tilt_degrees, "observer_final_extension": self.final_body.support_extension,
            "causal_action_credit": "uncertain", "durable_learning_updates": 0,
        }

    def as_dict(self) -> dict[str, object]:
        """Export actual retained results without running a replacement evaluation."""
        return {
            "profile": "righting_outcomes_v1", "metrics": self.metrics(),
            "intervals": [{"focal": focal.as_dict(), "lower": [step.as_dict() for step in lower]} for focal, lower in self.intervals],
            "final_focal_read": self.final_cycle.as_dict(), "prediction_outcomes": [item.as_dict() for item in self.outcomes],
            "pending_endpoint_claims": [item.as_dict() for item in self.pending], "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_OUTCOME_LIMITS), "bound_violations": list(self.bound_violations),
            "remaining_gates": "P16-1G-B / GO-OUTCOME-POLICY; P16-1G-C; A99", "restores_motor_permission": False,
        }


def run_righting_outcome_v1(case: str = "nominal", *, trace_capacity: int = 256) -> RightingOutcomeExperimentV1:
    """Run one fixed outcome control through the same live hierarchy, not replay.

    Nominal, disturbance [8,9), support loss [9,12), and dropout from interval8
    retain the earlier physical profiles. New controls use a blocked orientation
    motor, a two-degree BodyMap step limit, or no available capabilities. Assisted
    runs start at tilt30/extension.9 with -40 degrees/s over [8,20), as disclosed
    external help; the no-task member disables Righting. The comparison-off member
    removes only endpoint prediction comparison, preserving task dwell and motion.
    Context change explicitly requests rest at tick16; it cannot complete the old
    mobility task retroactively. Nothing is tuned from an observed outcome.
    """
    if not isinstance(case, str) or case not in RIGHTING_OUTCOME_CASES_V1:
        raise ValueError("unknown Righting outcome experiment")
    physical = MotorWorldProfileV1()
    capabilities = nominal_body_capabilities_v1()
    if case == "disturbed":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(8, 9, 160.0),))
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),))
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(8, 80, drop_feedback=True),))
    elif case == "blocked_orientation":
        physical = replace(physical, orientation_motor_enabled=False)
    elif case == "narrowed":
        capabilities = (replace(capabilities[0], maximum_step=2.0), capabilities[1])
    elif case == "veto":
        capabilities = ()
    elif case.startswith("assisted"):
        physical = replace(physical, initial_body=MotorBodyStateV1(30.0, 0.9),
                           perturbations=(MotorWorldPerturbationV1(8, 20, -40.0),))
    trial = IntegratedRightingTrialV1(
        physical, capabilities=capabilities, righting_enabled=case != "assisted_no_task", trace_capacity=trace_capacity,
        task_outcomes_enabled=True, task_prediction_comparison_enabled=case != "assisted_comparison_off",
    )
    peaks = trial.retained_counts()
    intervals: list[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]]] = []

    def record_peaks() -> None:
        """Measure storage immediately after each focal/lower boundary."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    for _ in range(20):
        context = RightingContextV1("activity:requested_rest", RightingActivityV1.REST) if case == "context_change" and trial.tick >= 16 else None
        focal = trial.focal_step(context=context)
        record_peaks()
        lower: list[SensorimotorStepV1] = []
        for _ in range(4):
            lower.append(trial.advance_lower())
            record_peaks()
        intervals.append((focal, tuple(lower)))
    final = trial.focal_step()
    record_peaks()
    owner = trial.core.outcomes
    if owner is None:
        raise RuntimeError("outcome experiment did not construct its enabled consumer")
    return RightingOutcomeExperimentV1(case, tuple(intervals), final, owner.history(), owner.pending(), trial.observer_body,
                                      tuple(sorted(peaks.items())))


def render_righting_outcome_summary_v1(results: tuple[RightingOutcomeExperimentV1, ...]) -> str:
    """Describe fixed-run results; unexpected/null scientific contrasts remain visible."""
    if not isinstance(results, tuple) or not results or any(not isinstance(item, RightingOutcomeExperimentV1) for item in results):
        raise TypeError("summary requires a nonempty tuple of actual outcome experiments")
    lines = ["P16-1G-A | SUPPORTED TASK EVIDENCE AND ORIGINAL PNM CORRESPONDENCE",
             "Every case: 80 lower ticks / 4.00 s; 21 focal reads. Dwell: 3 distinct focal samples spanning >=8 ticks.",
             "Local target achievement, task completion, forecast fit and causal credit remain different."]
    for result in results:
        metrics = result.metrics()
        lines.append(f"{result.case}: task={metrics['task_lifecycle']}; completion_cutoff={metrics['first_supported_completion_cutoff']}; "
                     f"commands={metrics['nonnull_commands']}; bounds={list(result.bound_violations)}")
        lines.append(f"  evidence={metrics['task_evidence_counts']}; predictions={metrics['prediction_outcome_counts']}; "
                     f"pending={metrics['pending_endpoint_claims']}")
    lines.extend(["Nominal strict 12-degree task boundary and lower 1-degree tolerance are unchanged.",
                  "Assistance is external; completion supplies no perfect action credit. No durable learning.",
                  "Endpoint evidence unavailable at the final physical horizon remains pending, not failed.",
                  "1G-B mismatch-to-Attention / GO-OUTCOME-POLICY, 1G-C and A99 remain open."])
    return "\n".join(lines)


def render_righting_outcome_v1(result: RightingOutcomeExperimentV1, *, detail: bool = False) -> str:
    """Show the already computed causal timeline, with optional unchanged lower detail."""
    if not isinstance(result, RightingOutcomeExperimentV1) or not isinstance(detail, bool):
        raise TypeError("render requires an outcome experiment and a Boolean detail flag")
    lines = [render_righting_outcome_summary_v1((result,)), ""]
    for focal, lower in (*result.intervals, (result.final_cycle, ())):
        lines.extend(focal_hierarchy_lines_v1(focal))
        assessment = focal.task_outcome
        if assessment is not None:
            lines.append(f"  TASK EVIDENCE: {assessment.status}; dwell events={[item.event_tick for item in assessment.supported_samples]}; "
                         f"changes={dict(assessment.relation_changes)}; causal credit uncertain")
        registration = focal.claim_registration
        if registration is not None:
            lines.append(f"  BEFORE HANDOFF: endpoint event {registration.due_tick}; compatible={registration.compatible_relations}; "
                         f"unevaluable={registration.unevaluable_relations}; authorized targets={len(registration.targets)}; "
                         f"disposition={registration.as_dict()['authorization_disposition']}")
        for outcome in focal.claim_outcomes:
            lines.append(f"  EARLIER PNM: {outcome.registration.preview.pnm.pnm_id} -> {outcome.status}; "
                         f"event={outcome.evidence.event_tick if outcome.evidence else None}; results={dict(outcome.relations)}")
        lines.extend(lower_hierarchy_lines_v1(lower, detail=detail))
        lines.append("")
    return "\n".join(lines)


def run_righting_outcome_menu_v1() -> None:
    """Open a read-only review menu; opening it creates no trial or hidden reset."""
    while True:
        print("\nP16-1G-A -- RIGHTING TASK OUTCOME REVIEW")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("  1) All fixed outcome cases (summary)")
        print("  2) Nominal progress / near-boundary stall")
        print("  3) Supported assisted completion / uncertain causal credit")
        print("  4) Support loss / prediction discrepancy")
        print("  5) Missing-input bounded exit")
        print("  6) Material narrowing / pre-execution veto")
        print("  7) Assisted completion with endpoint comparison on/off")
        print("  8) Nominal timeline with local detail")
        print("  [Enter] Return to integrated review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        cases = {
            "1": RIGHTING_OUTCOME_CASES_V1, "2": ("nominal",), "3": ("assisted", "assisted_no_task"),
            "4": ("support_loss",), "5": ("feedback_missing",), "6": ("narrowed", "veto"),
            "7": ("assisted", "assisted_comparison_off"), "8": ("nominal",),
        }.get(choice)
        if cases is None:
            print("Choose 1-8, or press Enter to return.")
            continue
        results = tuple(run_righting_outcome_v1(case) for case in cases)
        print(render_righting_outcome_summary_v1(results))
        if choice != "1":
            print("\n\n".join(render_righting_outcome_v1(item, detail=choice == "8") for item in results))
