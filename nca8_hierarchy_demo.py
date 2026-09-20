#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Finite integrated Righting review, shared by the menu and developer script.

Only nominal and fixed-time disturbed runs belong to this H6-A entry. It does
not claim H6-B ablation qualification or P16-1G task completion. Profile labels
and final actual body coordinates are external observer information, never
cognitive inputs. Rendering retained immutable results does not rerun cognition.
"""

from __future__ import annotations

from dataclasses import dataclass

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_righting import RightingApplicationV1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_trace import Nca8TraceEventV1

__version__ = "0.1.0"
__all__ = [
    "IntegratedRightingExperimentV1", "run_integrated_righting_v1", "render_integrated_righting_v1",
    "run_hierarchy_review_menu_v1", "__version__",
]


@dataclass(frozen=True, slots=True)
class IntegratedRightingExperimentV1:
    """A bounded external record: twenty intervals, eighty ticks, one final read.

    Each lower tuple follows its originating closed focal result. The last
    focal result at tick 80 observes the exhausted task; it does not extend the
    physical horizon. These diagnostic records cannot restore live permissions.
    """

    case: str
    intervals: tuple[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]], ...]
    final_cycle: IntegratedRightingCycleV1
    final_feedback: MotorFeedbackV1
    final_body: MotorBodyStateV1
    installation_count: int
    trace: tuple[Nca8TraceEventV1, ...]

    def as_dict(self) -> dict[str, object]:
        """Export the finite observer timeline, not a saved organism or success flag."""
        return {
            "case": self.case, "profile": "integrated_righting_v1", "dt_seconds": 0.05,
            "local_ticks": 80, "focal_opportunities": 21, "installation_count": self.installation_count,
            "intervals": [{"focal": focal.as_dict(), "lower": [step.as_dict() for step in lower]}
                          for focal, lower in self.intervals],
            "final_focal_read": self.final_cycle.as_dict(), "final_feedback": self.final_feedback.as_dict(),
            "observer_final_body": {"body_tilt_degrees": self.final_body.body_tilt_degrees,
                                    "support_extension": self.final_body.support_extension},
            "task_success_established": False, "durable_learning_updates": 0,
        }


def run_integrated_righting_v1(case: str = "nominal", *, trace_capacity: int = 256) -> IntegratedRightingExperimentV1:
    """Run the same fixed physical horizon under one named external condition.

    Both start from H2's normal body and use the unchanged H5 task and H4 local
    controller. The disturbed run adds +160 degrees/s only during interval [8,9),
    independently of task state or command count. No task target is supplied by
    this harness. Twenty nominal focal intervals use the original 80-tick task
    budget; the final focal read reports that exit without moving again.
    """
    if case not in {"nominal", "disturbed"}:
        raise ValueError("H6-A reviews are nominal or disturbed")
    perturbations = (MotorWorldPerturbationV1(8, 9, 160.0),) if case == "disturbed" else ()
    trial = IntegratedRightingTrialV1(MotorWorldProfileV1(perturbations=perturbations), trace_capacity=trace_capacity)
    intervals = tuple(trial.step() for _ in range(20))
    final = trial.focal_step()
    return IntegratedRightingExperimentV1(
        case, intervals, final, trial.latest_feedback, trial.observer_body,
        trial.controller.installation_count, trial.core.trace.snapshot(),
    )


def _value(value: float | None) -> str:
    """Format an optional measurement without making unknown equal zero."""
    return "unknown" if value is None else f"{value:.4f}"


def _focal_lines(result: IntegratedRightingCycleV1) -> list[str]:
    """Describe one real C/D/E/F result; do not compute a replacement decision."""
    calc = result.calculation
    support = calc.source.motor_support
    feedback = support.feedback if support is not None else None
    app = calc.navigation.application
    task = calc.task
    motor = result.receipt.dispatch.motor
    lines = [f"FOCAL {calc.cycle_id:02d} | cutoff tick {calc.cutoff_tick} | t={calc.cutoff_tick * 0.05:.2f} s"]
    if feedback is not None:
        lines.append(f"  C  POSTURE-SUPPORT sample={feedback.sample_id} event={feedback.event_tick} available={feedback.available_tick}; "
                     f"tilt={_value(feedback.body_tilt_degrees)} load={_value(feedback.useful_loading)}")
    else:
        lines.append("  C  POSTURE-SUPPORT: current physical input unavailable")
    lines.append(f"  D  Attention={calc.attention.disposition.value}; Navigation={calc.navigation.selected_primitive_id or 'none'}; "
                 f"task={task.task_id if task else 'none'}")
    if isinstance(app, RightingApplicationV1):
        request, projection = app.contribution, app.projection
        lines.append(f"     {app.strategy}: contribution tilt={_value(request.desired_tilt_degrees)}, "
                     f"extension={_value(request.desired_extension)}")
        lines.append(f"  E  PNM={projection.pnm.pnm_id}; expected tilt={_value(projection.predicted_tilt)}, "
                     f"load={_value(projection.predicted_loading)}; conditional, not sensory truth")
    if calc.proposal is not None:
        for binding in calc.proposal.bindings:
            target = binding.target
            lines.append(f"     BodyMap {target.kind.value}: endpoint={target.endpoint:.4f}, "
                         f"basis sample={target.basis.sample_id}, finite lease={target.lease_ticks} ticks")
        for kind, reason in calc.proposal.withheld:
            lines.append(f"     BodyMap withheld {kind.value}: {reason}")
    lines.append(f"     status={result.status}; directive={motor.directive if motor else 'none'}; "
                 f"receipt={result.receipt.receipt_id}")
    lines.append("  F  No durable learning; scheduler finished; CORE CLOSED.")
    lines.append("  OUTER handoff consumed ONCE; " +
                 ("new target envelope installed ONCE." if result.reservations else "no new target installation."))
    return lines


def render_integrated_righting_v1(result: IntegratedRightingExperimentV1, *, detail: bool = False) -> str:
    """Render immutable results only; local achievement never becomes task success."""
    if not isinstance(result, IntegratedRightingExperimentV1) or not isinstance(detail, bool):
        raise TypeError("render requires an experiment and a Boolean detail flag")
    lines = [
        f"P18-H6-A INTEGRATED RIGHTING | {result.case}",
        "One continuing task -> finite BodyMap targets -> local feedback/drives -> H2 -> later same-source evidence.",
        "dt=0.05 s; four lower updates per nominal focal interval; no legacy/A0 fallback.",
        "Task PNM is separate from local prediction; local target achieved is NOT Righting completion.",
        "",
    ]
    for focal, lower in result.intervals:
        lines.extend(_focal_lines(focal))
        if detail:
            for step in lower:
                command = step.command
                orientation = command.orientation_drive if command is not None else 0.0
                extension = command.extension_drive if command is not None else 0.0
                sample = step.feedback.sample_id if step.feedback is not None else None
                lines.append(f"    LOWER tick={step.tick:02d} sample={sample} drives=({orientation:+.4f}, {extension:+.4f})")
                for report in step.reports:
                    lines.append(f"      {report.committed_target.target.kind.value}: {report.disposition.value}; {report.reason}")
                for comparison in step.comparisons:
                    if comparison.unexpected:
                        lines.append(f"      LOCAL MISMATCH event={comparison.feedback.event_tick}, "
                                     f"available={comparison.feedback.available_tick}, residual={_value(comparison.residual)}")
        else:
            commands = ", ".join(
                f"({step.command.orientation_drive:+.2f},{step.command.extension_drive:+.2f})" if step.command else "(0,0)"
                for step in lower
            )
            outcomes = ", ".join(f"{item.committed_target.target.kind.value}:{item.disposition.value}" for item in lower[-1].reports)
            lines.append(f"    LOWER ticks {lower[0].tick}-{lower[-1].tick}: drives {commands}; {outcomes or 'no active target'}")
            corrections = [step.tick for step in lower if any(item.reason == "bounded_anomalous_correction" for item in step.reports)]
            if corrections:
                lines.append(f"    LOCAL bounded anomalous correction at tick(s) {corrections}, before the next focal call.")
        lines.append("    H2 physical consequences become eligible source evidence at the following focal boundary.")
        lines.append("")
    lines.extend(_focal_lines(result.final_cycle))
    lines.extend([
        "",
        f"FINAL: 80 physical updates / 4.00 s; 21 closed focal reads; {result.installation_count} target installations.",
        f"Last sensed event={result.final_feedback.event_tick}, available={result.final_feedback.available_tick}: "
        f"tilt={_value(result.final_feedback.body_tilt_degrees)}, load={_value(result.final_feedback.useful_loading)}.",
        f"Task exit={result.final_cycle.status}; task completion NOT established; durable learning updates=0.",
        "The local 1-degree target tolerance is wider than the strict 12-degree task boundary.",
        "Near-boundary local attainment does not waive that task criterion or extend the task budget.",
        "H6-A integration review complete. H6-B qualification and P16-1G outcomes remain pending.",
    ])
    return "\n".join(lines)


def run_hierarchy_review_menu_v1() -> None:
    """Inspect fresh finite H6-A runs without changing the retained A0/menu session.

    Merely opening this submenu creates no trial. Both presentation modes call
    the same experiment; more detail never changes the dynamics or decision.
    Full H6-B ablation/inspector qualification is intentionally not claimed here.
    """
    while True:
        print("\nP18-H6-A -- INTEGRATED RIGHTING REVIEW")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("  1) Nominal integrated run (compact)")
        print("  2) Fixed-time disturbed run (compact)")
        print("  3) Nominal integrated run (local detail)")
        print("  4) Fixed-time disturbed run (local detail)")
        print("  [Enter] Return to NCA8 menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice not in {"1", "2", "3", "4"}:
            print("Choose 1-4, or press Enter to return.")
            continue
        case = "disturbed" if choice in {"2", "4"} else "nominal"
        print(render_integrated_righting_v1(run_integrated_righting_v1(case), detail=choice in {"3", "4"}))
