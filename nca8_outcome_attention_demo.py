#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1G-B finite observer experiments, shared by the menu and review script.

Each run owns an isolated existing hierarchy/plant and lasts 80 physical ticks.
A controlled second source is an explicit fixture, not implemented visual or
maternal cognition. The main on/off pair has identical input, ordinary priorities,
local feedback, earlier task predictions and commands at cutoff16. Only the
outcome route changes its focal source and single demanding allocation there.
No outcome, task winner or causal diagnosis is supplied by the observer.
"""

#pylint: disable=too-many-boolean-expressions
#pylint: disable=duplicate-code

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_executive import AttentionBidV1
from nca8_hierarchy_demo import focal_hierarchy_lines_v1, lower_hierarchy_lines_v1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_sensorimotor import SensorimotorStepV1

__version__ = "0.1.1"
__all__ = [
    "OUTCOME_ATTENTION_CASES_V1", "RightingOutcomeAttentionExperimentV1", "run_outcome_attention_v1",
    "outcome_attention_owner_limits_v1", "outcome_attention_review_bids_v1", "render_outcome_attention_summary_v1", "render_outcome_attention_v1", "run_outcome_attention_menu_v1", "__version__",
]
OUTCOME_ATTENTION_CASES_V1 = (
    "competing_on", "competing_off", "maintain_on", "maintain_off", "protected_competitor",
    "nominal_on", "nominal_off", "blocked_orientation", "feedback_missing", "unresolved_current",
    "assisted_on", "assisted_off",
)
_LIMITS = {
    "durable_maps": 1, "current_source_states": 1, "wnm": 1, "current_pnm": 1,
    "righting_applications": 8, "past_previews": 8, "focal_records": 8, "focal_trace": 4096,
    "pending_sensor_deliveries": 16, "body_sensor_records": 1, "body_pending_proposals": 1, "body_reserved_records": 2,
    "lower_pursuits": 2, "lower_command_history": 4, "lower_events": 4, "lower_trace": 256,
    "lower_predictions_per_axis": 4, "lower_replaced_reports": 2,
    "outcome_pending_claims": 8, "outcome_terminal_history": 32, "outcome_installed_targets": 2,
    "outcome_dwell_samples": 3, "outcome_recent_feedback": 16, "outcome_staged_intervals": 16, "outcome_command_ticks": 16,
    "attention_pending_requests": 8, "attention_previous_endpoint": 1, "attention_dependency": 1, "attention_dispositions": 32,
}


def outcome_attention_owner_limits_v1() -> dict[str, int]:
    """Return detached observer bounds for extensions, never mutable owner limits.

    The no-learning review adds its own temporary-record limits while preserving
    these qualified H4/H6/1G-A/B counts. Reading this contract runs no experiment.
    """
    return dict(_LIMITS)


def outcome_attention_review_bids_v1(case: str, *, cycle: int, tick: int) -> tuple[AttentionBidV1, ...]:
    """Supply the shared competing-source fixture, not a cognitive relevance policy.

    Competing cases admit B at ticks12/16, maintain cases at16, and the protected
    case over12..24. Other named experiment families have no supplied competitor.
    The caller validates its experiment name; this helper validates the clock and
    returns fresh immutable bids without running a trial or reading physical state.
    """
    if not isinstance(case, str) or not case:
        raise ValueError("review case must be nonempty text")
    if (isinstance(cycle, bool) or not isinstance(cycle, int) or not 1 <= cycle <= 81
            or isinstance(tick, bool) or not isinstance(tick, int) or not 0 <= tick <= 80):
        raise ValueError("review bid requires a finite focal/physical clock")
    compete = (case.startswith("competing") and tick in (12, 16)
               or case.startswith("maintain") and tick == 16
               or case == "protected_competitor" and 12 <= tick <= 24)
    if not compete:
        return ()
    return (replace(competing_preview_bid_v1(cycle), novelty_or_ambiguity_rank=10,
                    protected_safety_rank=int(case == "protected_competitor")),)


@dataclass(frozen=True, slots=True)
class RightingOutcomeAttentionExperimentV1:
    """Finite read-only observer records, never restored cognition or permissions."""

    case: str
    route_enabled: bool
    intervals: tuple[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]], ...]
    final_cycle: IntegratedRightingCycleV1
    physical_samples: tuple[MotorBodyStateV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    dispositions: tuple[tuple[str, str, int], ...]

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Compare actual owner counts to declared bounds, including unknown owners."""
        return tuple(name for name, value in self.peak_counts if name not in _LIMITS or value > _LIMITS[name])

    def metrics(self) -> dict[str, object]:
        """Summarize actual evidence and cost, without re-evaluating task success."""
        cycles = (*[focal for focal, _ in self.intervals], self.final_cycle)
        kinds = Counter(focal.calculation.outcome_allocation.kind for focal in cycles if focal.calculation.outcome_allocation is not None)
        task = self.final_cycle.calculation.task
        interpretations = [focal for focal in cycles if focal.calculation.outcome_allocation is not None
                           and focal.calculation.outcome_allocation.kind == "interpretation"]
        at16 = next(focal for focal in cycles if focal.calculation.cutoff_tick == 16)
        selected = at16.calculation.attention.selected_bid
        return {
            "case": self.case, "route_enabled": self.route_enabled,
            "physical_ticks": sum(len(lower) for _, lower in self.intervals), "focal_reads": len(cycles),
            "nonnull_commands": sum(step.command is not None for _, lower in self.intervals for step in lower),
            "installations": sum(bool(focal.reservations) for focal in cycles),
            "task_status": task.status if task is not None else "no_task",
            "task_completed": task is not None and task.status == "completed",
            "first_completed_cutoff": next((focal.calculation.cutoff_tick for focal in cycles
                                             if focal.task_outcome is not None and focal.task_outcome.completion_supported), None),
            "focal_allocation_counts": dict(kinds),
            "interpretation_ticks": [focal.calculation.cutoff_tick for focal in interpretations],
            "interpretation_results": [focal.calculation.outcome_allocation.interpretation.status for focal in interpretations
                                       if focal.calculation.outcome_allocation is not None
                                       and focal.calculation.outcome_allocation.interpretation is not None],
            "cutoff16_source": selected.candidate_id if selected is not None else None,
            "cutoff16_disposition": at16.calculation.attention.disposition.value,
            "final_sensed_tilt": self.final_feedback.body_tilt_degrees,
            "final_actual_tilt": self.physical_samples[-1].body_tilt_degrees,
            "causal_action_credit": "uncertain", "durable_learning_updates": 0,
        }

    def as_dict(self) -> dict[str, object]:
        """Export original computed records; reading cannot rerun an interpretation."""
        return {
            "profile": "righting_outcome_attention_v1", "metrics": self.metrics(),
            "intervals": [{"focal": focal.as_dict(), "lower": [step.as_dict() for step in lower]} for focal, lower in self.intervals],
            "final_focal": self.final_cycle.as_dict(),
            "physical_samples": [{"tick": tick, "tilt": body.body_tilt_degrees, "extension": body.support_extension}
                                 for tick, body in enumerate(self.physical_samples)],
            "peak_owner_counts": dict(self.peak_counts), "owner_limits": dict(_LIMITS),
            "bound_violations": list(self.bound_violations), "request_dispositions": list(self.dispositions),
            "remaining_gates": "P16-1G-C; A99; no default promotion", "restores_motor_permission": False,
        }


def run_outcome_attention_v1(case: str = "competing_on", *, trace_capacity: int = 256) -> RightingOutcomeAttentionExperimentV1:
    """Run one declared fixed-time profile through the existing core and lower loop.

    Competing on/off: the same support-loss interval [9,12), candidate B at
    cutoffs12/16, and no other input difference. Maintain on/off supplies B only
    at16, preserving A as the previous focal source. B's novelty rank10 beats
    ordinary A but not A's outcome rank40. Protected B has safety rank1 over
    cutoffs12..24 and tests honest expiry. These are fixed ranking fixtures.

    Nominal and blocked-orientation use unchanged physical profiles. Missing
    feedback from interval8 creates no invented discrepancy. Unresolved-current
    combines support loss [9,12) with dropout [13,80): its actual endpoint12
    arrives, but newer focal currentness is lost. Assistance uses the retained
    1G-A initial tilt30/extension.9 and -40 degrees/s over [8,20). No threshold,
    physical equation, task budget or controller tolerance is adjusted.
    """
    if not isinstance(case, str) or case not in OUTCOME_ATTENTION_CASES_V1:
        raise ValueError("unknown task-outcome Attention experiment")
    physical = MotorWorldProfileV1()
    route = not case.endswith("_off")
    if case.startswith(("competing", "maintain")) or case == "protected_competitor":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),))
    elif case == "unresolved_current":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),
                                                   MotorWorldPerturbationV1(13, 80, drop_feedback=True)))
    elif case == "blocked_orientation":
        physical = replace(physical, orientation_motor_enabled=False)
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(8, 80, drop_feedback=True),))
    elif case.startswith("assisted"):
        physical = replace(physical, initial_body=MotorBodyStateV1(30.0, 0.9),
                           perturbations=(MotorWorldPerturbationV1(8, 20, -40.0),))
    trial = IntegratedRightingTrialV1(physical, task_outcomes_enabled=True, task_outcome_attention_enabled=route,
                                    trace_capacity=trace_capacity)
    peaks = trial.retained_counts()
    physical_samples = [trial.observer_body]
    intervals: list[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]]] = []

    def record_peaks() -> None:
        """Measure owner storage at each actual boundary, never from rendered traces."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    for cycle in range(1, 21):
        bids = outcome_attention_review_bids_v1(case, cycle=cycle, tick=trial.tick)
        focal = trial.focal_step(competing_bids=bids)
        record_peaks()
        lower: list[SensorimotorStepV1] = []
        for _ in range(4):
            lower.append(trial.advance_lower())
            physical_samples.append(trial.observer_body)
            record_peaks()
        intervals.append((focal, tuple(lower)))
    final = trial.focal_step()
    record_peaks()
    owner = trial.core.cognition.sensory.outcome_attention
    return RightingOutcomeAttentionExperimentV1(case, route, tuple(intervals), final, tuple(physical_samples), trial.latest_feedback,
                                               tuple(sorted(peaks.items())), () if owner is None else owner.dispositions())


def render_outcome_attention_summary_v1(results: tuple[RightingOutcomeAttentionExperimentV1, ...]) -> str:
    """Present measured outcomes and null contrasts without manufacturing success."""
    if not isinstance(results, tuple) or not results or any(not isinstance(item, RightingOutcomeAttentionExperimentV1) for item in results):
        raise TypeError("summary requires a nonempty tuple of actual Attention experiments")
    if len({item.case for item in results}) != len(results):
        raise ValueError("summary cannot duplicate an experiment identity")
    lines = [
        "P16-1G-B | TASK MISMATCH -> SOURCE REQUEST -> ONE FOCAL INTERPRETATION",
        "Every row: 80 physical updates / 4.00 s / 21 closed focal reads. Fixed original task and target budgets.",
        "Interpretation is not another IP or a new motor command. A dependent response waits for a later opportunity.",
        "Competing source B is an explicit fixture, not a new visual/maternal domain.",
    ]
    for result in results:
        metrics = result.metrics()
        lines.append(f"{result.case}: task={metrics['task_status']}; commands={metrics['nonnull_commands']}; "
                     f"interpretation ticks={metrics['interpretation_ticks']}; bounds={list(result.bound_violations)}")
        lines.append(f"  at16: {metrics['cutoff16_disposition']} {metrics['cutoff16_source']}; "
                     f"results={metrics['interpretation_results']}; allocations={metrics['focal_allocation_counts']}")
    by_case = {item.case: item for item in results}
    for prefix in ("competing", "maintain"):
        if f"{prefix}_on" in by_case and f"{prefix}_off" in by_case:
            on, off = by_case[f"{prefix}_on"], by_case[f"{prefix}_off"]
            left, right = on.intervals[4][0], off.intervals[4][0]
            lines.append(f"{prefix} cutoff16 controlled equality: source={left.calculation.source == right.calculation.source}; "
                         f"task outcomes={left.claim_outcomes == right.claim_outcomes}; "
                         f"local warnings={left.local_events == right.local_events}; "
                         f"physical prefix={on.physical_samples[:17] == off.physical_samples[:17]}")
    lines.extend([
        "Historical contact loss can be significant without being current danger; causes remain uncertain.",
        "Unknown current relevance can defer its dependent response, never source maintenance or lower protection.",
        "Interpretation costs an existing focal opportunity. No success threshold, physical time or budget is increased.",
        "GO-OUTCOME-POLICY approved; this implementation still requires local acceptance. P16-1G-C and A99 remain open.",
    ])
    return "\n".join(lines)


def render_outcome_attention_v1(result: RightingOutcomeAttentionExperimentV1, *, detail: bool = False) -> str:
    """Render retained results only; no source, interpretation or physical work runs."""
    if not isinstance(result, RightingOutcomeAttentionExperimentV1) or not isinstance(detail, bool):
        raise TypeError("render requires an actual Attention experiment and Boolean detail")
    lines = [render_outcome_attention_summary_v1((result,)), ""]
    for focal, lower in (*result.intervals, (result.final_cycle, ())):
        lines.extend(focal_hierarchy_lines_v1(focal))
        lines.append("  FROZEN-CYCLE DETAIL: C2/D work already occurred above; this is not another focal opportunity.")
        for outcome in focal.claim_outcomes:
            lines.append(f"  C2 ENDPOINT: {outcome.registration.preview.pnm.pnm_id}; {outcome.status}; "
                         f"relations={dict(outcome.relations)}; event={outcome.evidence.event_tick if outcome.evidence else None}")
        for request in focal.outcome_requests_created:
            lines.append(f"  SOURCE REQUEST: {request.request_id}; {request.significance}; relations={request.relations}; "
                         f"lifetime=[{request.admitted_tick},{request.expires_at_tick})")
        allocation = focal.calculation.outcome_allocation
        bid = focal.calculation.outcome_source_bid
        if allocation is not None:
            lines.append(f"  D ALLOCATION: {allocation.kind}; source bid components={bid.priority_components if bid else None}")
            interpreted = allocation.interpretation
            if interpreted is not None:
                lines.append(f"    interpretation at cycle={interpreted.cycle_id}, tick={interpreted.cutoff_tick}: "
                             f"{interpreted.status}; relations={dict(interpreted.relation_relevance)}; causal credit uncertain")
        lines.extend(lower_hierarchy_lines_v1(lower, detail=detail))
        lines.append("")
    lines.append(f"Request dispositions (bounded diagnostic history): {result.dispositions}")
    return "\n".join(lines)


def run_outcome_attention_menu_v1() -> None:
    """Expose the same finite experiments without resetting the retained A0 session."""
    groups = {
        "1": OUTCOME_ATTENTION_CASES_V1, "2": ("competing_on", "competing_off"),
        "3": ("maintain_on", "maintain_off"), "4": ("protected_competitor",),
        "5": ("feedback_missing", "unresolved_current"), "6": ("nominal_on", "nominal_off", "blocked_orientation"),
        "7": ("assisted_on", "assisted_off"), "8": ("competing_on",),
    }
    while True:
        print("\nP16-1G-B -- TASK-OUTCOME ATTENTION REVIEW")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("  1) All fixed profiles (summary)")
        print("  2) Same body/claim, competing source: route on/off")
        print("  3) Same-source maintain: route on/off")
        print("  4) Protected competing source and request expiry")
        print("  5) Missing evidence / unresolved current interpretation")
        print("  6) Nominal and persistent blocked-motor discrepancy")
        print("  7) Assisted completion: route on/off, no perfect action credit")
        print("  8) Competing-source timeline with local detail")
        print("  [Enter] Return to integrated hierarchy review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        cases = groups.get(choice)
        if cases is None:
            print("Choose 1-8, or press Enter to return.")
            continue
        results = tuple(run_outcome_attention_v1(case) for case in cases)
        print(render_outcome_attention_summary_v1(results))
        if choice != "1":
            print("\n\n".join(render_outcome_attention_v1(item, detail=choice == "8") for item in results))
