#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-1G-C read-only live comparisons and explicitly labelled routing fixtures.

The live cases use the existing 80-tick body, task criteria and controller. Hook
on/off changes temporary evidence processing, not physical or cognitive policy.
The separate routing fixture supplies canonical execution/sensor records to the
real core; it does not claim an actual physical run or a general Ready subsystem.
Both paths use the same source-owned hook and Phase-F consumer as normal trials.
"""

#pylint: disable=duplicate-code

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_hierarchy import IntegratedRightingCoreV1, IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_hierarchy_demo import focal_hierarchy_lines_v1, lower_hierarchy_lines_v1
from nca8_learning_registry import render_learning_ledger_v1
from nca8_outcomes import RightingIntervalEvidenceV1
from nca8_outcome_attention_demo import outcome_attention_owner_limits_v1, outcome_attention_review_bids_v1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, LocalTargetReportV1

__version__ = "0.1.0"
__all__ = [
    "LEARNING_HOOK_CASES_V1", "RightingLearningExperimentV1", "run_learning_hook_v1", "run_learning_routing_fixture_v1",
    "render_learning_hook_v1", "render_learning_hook_summary_v1", "render_learning_routing_fixture_v1",
    "run_learning_review_menu_v1", "__version__",
]
LEARNING_HOOK_CASES_V1 = (
    "nominal_on", "nominal_off", "competing_on", "competing_off", "protected_competitor", "unresolved_current",
    "feedback_missing", "narrowed", "veto", "assisted", "fast_cadence", "delayed_feedback", "attention_off", "comparison_off",
)
_LIMITS = {**outcome_attention_owner_limits_v1(), "learning_participants": 8, "learning_dispositions": 32}


@dataclass(frozen=True, slots=True)
class RightingLearningExperimentV1:
    """Finite external observer records, not another owner or a saved organism."""

    case: str
    hook_enabled: bool
    intervals: tuple[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]], ...]
    final_cycle: IntegratedRightingCycleV1
    physical_samples: tuple[MotorBodyStateV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_signature_before: str
    durable_signature_after: str
    fixed_configuration_unchanged: bool

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check measured owner bounds, not a prewritten success label."""
        return tuple(name for name, value in self.peak_counts if name not in _LIMITS or value > _LIMITS[name])

    def metrics(self) -> dict[str, object]:
        """Summarize actual admission, expiry and no-update work independently of motion."""
        cycles = (*[focal for focal, _ in self.intervals], self.final_cycle)
        reports = [focal.learning_report for focal in cycles if focal.learning_report is not None]
        statuses = Counter(event.status for report in reports for event in report.dispositions)
        task = self.final_cycle.calculation.task
        return {
            "case": self.case, "hook_enabled": self.hook_enabled, "physical_ticks": len(self.physical_samples) - 1,
            "focal_reads": len(cycles), "nonnull_commands": sum(step.command is not None for _, steps in self.intervals for step in steps),
            "task_status": task.status if task is not None else "no_task", "F_hook_calls": len(reports),
            "new_participations": sum(report.new_participation is not None for report in reports),
            "teaching_dispositions": dict(statuses), "final_pending_participants": len(reports[-1].pending) if reports else 0,
            "durable_source_unchanged": self.durable_signature_before == self.durable_signature_after,
            "fixed_configuration_unchanged": self.fixed_configuration_unchanged,
            "durable_learning_updates": 0, "causal_action_credit": "uncertain",
            "final_sensed_tilt": self.final_feedback.body_tilt_degrees,
        }

    def as_dict(self) -> dict[str, object]:
        """Export the finite measured trial; no report can restore eligibility or motor permission."""
        return {
            "profile": "righting_no_learning_v1", "evidence_kind": "live_existing_body", "metrics": self.metrics(),
            "intervals": [{"focal": focal.as_dict(), "lower": [step.as_dict() for step in steps]} for focal, steps in self.intervals],
            "final_focal": self.final_cycle.as_dict(), "final_feedback": self.final_feedback.as_dict(),
            "physical_samples": [{"tick": tick, "tilt": body.body_tilt_degrees, "extension": body.support_extension}
                                 for tick, body in enumerate(self.physical_samples)],
            "peak_owner_counts": dict(self.peak_counts), "owner_limits": dict(_LIMITS), "bound_violations": list(self.bound_violations),
            "durable_signature_before": self.durable_signature_before, "durable_signature_after": self.durable_signature_after,
            "restores_motor_permission": False,
        }


def run_learning_hook_v1(case: str = "nominal_on", *, trace_capacity: int = 256,
                         diagnostic_capacity: int = 32) -> RightingLearningExperimentV1:
    """Run a fixed existing-body profile with the no-learning route independently controlled.

    Nominal/competing on/off pairs change only the hook; 1G-B Attention remains
    enabled in both. The competitor and [9,12) support loss are the retained
    1G-B fixture. The protected case withholds A until tick24; unresolved-current
    drops feedback from13 after contact loss. Remaining cases retain the earlier
    missing-input, narrowing, veto, assistance and four-tick sensing-delay controls.
    Fast cadence uses K=1 but the original 20-opportunity/80-tick task budgets.
    No profile claims the four-cycle eligibility timer as a biological constant.
    """
    if not isinstance(case, str) or case not in LEARNING_HOOK_CASES_V1:
        raise ValueError("unknown no-learning hook experiment")
    physical = MotorWorldProfileV1()
    capabilities = nominal_body_capabilities_v1()
    if case.startswith("competing") or case == "protected_competitor":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),))
    elif case == "unresolved_current":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),
                                                   MotorWorldPerturbationV1(13, 80, drop_feedback=True)))
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(8, 80, drop_feedback=True),))
    elif case == "narrowed":
        capabilities = (replace(capabilities[0], maximum_step=2.0), capabilities[1])
    elif case == "veto":
        capabilities = ()
    elif case == "assisted":
        physical = replace(physical, initial_body=MotorBodyStateV1(30.0, 0.9),
                           perturbations=(MotorWorldPerturbationV1(8, 20, -40.0),))
    elif case == "delayed_feedback":
        physical = replace(physical, sensor_delay_ticks=4)
    enabled = case not in {"nominal_off", "competing_off"}
    trial = IntegratedRightingTrialV1(
        physical, capabilities=capabilities, task_outcomes_enabled=True, task_learning_hook_enabled=enabled,
        task_outcome_attention_enabled=case != "attention_off", task_prediction_comparison_enabled=case != "comparison_off",
        trace_capacity=trace_capacity, learning_diagnostic_capacity=diagnostic_capacity,
    )
    before = trial.core.cognition.maps.durable_record_signature()
    fixed_before = (trial.core.cognition.mapper.capabilities, trial.controller.profile, trial.core.cognition.righting.context)
    peaks = trial.retained_counts()
    bodies = [trial.observer_body]
    intervals: list[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]]] = []

    def record() -> None:
        """Sample all live owner counts after each boundary, independently of tracing."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(value, peaks.get(name, 0))

    cadence = 1 if case == "fast_cadence" else 4
    while trial.tick < 80:
        cycle = len(intervals) + 1
        bids = outcome_attention_review_bids_v1(case, cycle=cycle, tick=trial.tick)
        focal = trial.focal_step(competing_bids=bids)
        record()
        lower: list[SensorimotorStepV1] = []
        for _ in range(cadence):
            lower.append(trial.advance_lower())
            bodies.append(trial.observer_body)
            record()
        intervals.append((focal, tuple(lower)))
    final = trial.focal_step()
    record()
    fixed_after = (trial.core.cognition.mapper.capabilities, trial.controller.profile, trial.core.cognition.righting.context)
    return RightingLearningExperimentV1(case, enabled, tuple(intervals), final, tuple(bodies), trial.latest_feedback,
                                       tuple(sorted(peaks.items())), before, trial.core.cognition.maps.durable_record_signature(),
                                       fixed_before == fixed_after)


def run_learning_routing_fixture_v1(*, expired: bool = False) -> tuple[IntegratedRightingCycleV1, ...]:
    """Exercise actual C2/D/E/F with supplied records, not an actual physical run.

    The initial core selects Righting and produces a real authorized target and
    PNM; its handoff is consumed and the actual lower executor installs it. The
    fixture supplies declared command-interval and predicted-endpoint sensing
    records instead of invoking physics. Source B subsequently wins. At the
    endpoint's delivery, A's current summary is absent and its activation is zero,
    yet the original source-A recipient is still correctly addressed.

    The expired variant inserts faster focal opportunities before the same old
    endpoint arrives. Eligibility expires at cycle5 while the original physical
    claim is still pending. Neither source accessibility nor pending prediction
    renews that eligibility. This tests the Ready-loss boundary with controlled
    unavailable-source input; it does not implement general P16-3A Ready/offload.
    """
    if not isinstance(expired, bool):
        raise TypeError("expired must be Boolean")
    stream = MotorStreamRefV1("learning_routing_fixture", 1)
    core = IntegratedRightingCoreV1(stream, task_outcomes_enabled=True, task_outcome_attention_enabled=True,
                                   task_learning_hook_enabled=True)
    initial = MotorFeedbackV1(stream, 1, 0, 0, 30.0, 0.5, True, 0.5, 0.3)
    first = core.run_cycle(initial, cutoff_tick=0)
    core.handoff.consume_motor(first.receipt)
    controller = SensorimotorExecutorV1(core.cognition.mapper, installation_source=core.handoff)
    controller.install_authorized(first.reservations, at_tick=0)
    registration = first.claim_registration
    publisher = core.outcomes
    if registration is None or publisher is None:
        raise RuntimeError("routing fixture did not produce an actual claim")
    publisher.installed(registration, at_tick=0)
    preview = registration.preview
    endpoint = MotorFeedbackV1(stream, 5, 4, 5, preview.predicted_tilt, preview.predicted_extension, preview.expected_contact,
                               preview.predicted_loading, preview.predicted_destabilization)
    result = [first]
    previous_tick = 0
    cutoffs = (1, 2, 3, 4, 8) if expired else (4, 8)
    for cycle, tick in enumerate(cutoffs, 2):
        intervals = []
        for event in range(previous_tick, tick):
            reports = tuple(LocalTargetReportV1(target, LocalTargetDispositionV1.ACTIVE, event, "supplied_routing_fixture")
                            for target in registration.targets)
            command = MotorCommandV1(stream, event + 1, event, 0.2, 0.2) if event < 4 else None
            intervals.append(RightingIntervalEvidenceV1(event, command, reports, (endpoint,) if event == 4 else ()))
        # Current-source absence is an explicit fixture, never inferred from a
        # private body. Historical endpoint evidence remains in its own batch.
        current = None
        bid = replace(competing_preview_bid_v1(cycle), protected_safety_rank=1, novelty_or_ambiguity_rank=10)
        focal = core.run_cycle(current, cutoff_tick=tick, competing_bids=(bid,), outcome_intervals=tuple(intervals))
        core.handoff.consume_motor(focal.receipt)
        result.append(focal)
        previous_tick = tick
    return tuple(result)


def render_learning_routing_fixture_v1(records: tuple[IntegratedRightingCycleV1, ...]) -> str:
    """Display original-recipient evidence with explicit replay/Ready limitations."""
    if not records or any(item.learning_report is None for item in records):
        raise ValueError("routing display requires actual hook-enabled core records")
    lines = ["P16-1G-C | CANONICAL ROUTING FIXTURE -- NO PHYSICAL WORLD STEPS",
             "Original A participation; B subsequently focal; A current summary/activation absent.",
             "Controlled unavailable-source boundary, not a completed general Ready/offloading subsystem."]
    for focal in records:
        lines.extend(_learning_lines(focal))
    return "\n".join(lines)


def _learning_lines(focal: IntegratedRightingCycleV1) -> list[str]:
    """Render already computed F records without querying an owner or changing time."""
    report = focal.learning_report
    selected = focal.calculation.attention.selected_bid
    facet = focal.calculation.source.motor_support
    current = facet is not None and facet.current
    lines = [f"cycle={focal.commitment.cycle_id} tick={focal.calculation.cutoff_tick}; "
             f"focal={selected.candidate_id if selected else 'none'}; source_current={current}"]
    if report is None:
        lines.append("  hook disabled; no extra eligibility owner or F work")
        return lines
    lines.append(f"  F recipient={report.recipient_id}; pending={len(report.pending)}; durable updates=0; ledger actors=0")
    if report.new_participation is not None:
        part = report.new_participation
        lines.append(f"  participation {part.pnm_id}; expires before cycle={part.expires_before_cycle}; no new action outcome yet")
    for event in report.dispositions:
        lines.append(f"  {event.pnm_id}: {event.status}; known relations={dict(event.accepted_relations)}; "
                     f"interpretation={event.interpretation.status if event.interpretation else 'not_required_or_pending'}")
    return lines


def render_learning_hook_v1(result: RightingLearningExperimentV1, *, detail: bool = False) -> str:
    """Render actual live control and F evidence, without recomputing outcomes."""
    if not isinstance(result, RightingLearningExperimentV1):
        raise TypeError("learning review requires a completed experiment")
    lines = [f"P16-1G-C | {result.case} | bounded eligibility, no durable learner"]
    for focal, lower in result.intervals:
        lines.extend(_learning_lines(focal))
        if detail:
            lines.extend(focal_hierarchy_lines_v1(focal))
            lines.extend(lower_hierarchy_lines_v1(lower, detail=True))
    lines.extend(_learning_lines(result.final_cycle))
    lines.append(f"Measured: {result.metrics()}; bound violations={list(result.bound_violations)}")
    return "\n".join(lines)


def render_learning_hook_summary_v1(results: tuple[RightingLearningExperimentV1, ...]) -> str:
    """Keep positive evidence admissions, unknowns, rejection and expiry distinct."""
    if not isinstance(results, tuple) or not results or any(not isinstance(item, RightingLearningExperimentV1) for item in results):
        raise TypeError("summary requires actual nonempty experiment records")
    if len({item.case for item in results}) != len(results):
        raise ValueError("summary cannot count the same case twice")
    lines = ["P16-1G-C | CALLED NO-LEARNING HOOK / PHASE F",
             "Every live row: 80 physical ticks / 4.00 s. Four focal cycles of eligibility, independent of prediction/target expiry.",
             "accepted_no_update means forecast evidence reached its original source-side recipient; action causation stays uncertain."]
    for item in results:
        lines.append(str(item.metrics()))
        lines.append(f"  bound violations={list(item.bound_violations)}")
    by_case = {item.case: item for item in results}
    for prefix in ("nominal", "competing"):
        if f"{prefix}_on" in by_case and f"{prefix}_off" in by_case:
            on, off = by_case[f"{prefix}_on"], by_case[f"{prefix}_off"]
            commands_on = tuple(step.command for _, lower in on.intervals for step in lower)
            commands_off = tuple(step.command for _, lower in off.intervals for step in lower)
            choices_on = tuple(focal.commitment for focal, _ in on.intervals)
            choices_off = tuple(focal.commitment for focal, _ in off.intervals)
            lines.append(f"{prefix} hook on/off: body equal={on.physical_samples == off.physical_samples}; "
                         f"commands equal={commands_on == commands_off}; commitments equal={choices_on == choices_off}")
    lines.append("No active durable learner, adaptive SEC, acquired LP or default-runtime promotion is established. Local acceptance is required.")
    return "\n".join(lines)


def run_learning_review_menu_v1() -> None:
    """Open no trial merely by entering; all routes reuse the shared inspector functions."""
    while True:
        print("\nP16-1G-C -- NO-LEARNING HOOK / PHASE F / COVERAGE")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("  1) All live profiles (summary)")
        print("  2) Hook on/off with unchanged cognition and body")
        print("  3) Original recipient after focus/access loss; independent expiry (replay fixtures)")
        print("  4) Focal interpretation, protected delay and unresolved evidence")
        print("  5) Narrowed, vetoed and missing-evidence contributions")
        print("  6) Faster focal cadence / delayed feedback")
        print("  7) Complete L01-L25 owner, depth, maturity and promotion inventory")
        print("  8) Detailed nominal live timeline")
        print("  [Enter] Return to integrated hierarchy review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "3":
            for expired in (False, True):
                print(render_learning_routing_fixture_v1(run_learning_routing_fixture_v1(expired=expired)))
            continue
        if choice == "7":
            print(render_learning_ledger_v1(detail=True))
            continue
        groups = {
            "1": LEARNING_HOOK_CASES_V1, "2": ("nominal_on", "nominal_off", "competing_on", "competing_off"),
            "4": ("competing_on", "protected_competitor", "unresolved_current"),
            "5": ("narrowed", "veto", "feedback_missing"), "6": ("fast_cadence", "delayed_feedback"), "8": ("nominal_on",),
        }
        if choice not in groups:
            print("Choose 1-8, or press Enter to return.")
            continue
        results = tuple(run_learning_hook_v1(case) for case in groups[choice])
        print(render_learning_hook_summary_v1(results))
        if choice not in {"1", "2"}:
            for item in results:
                print(render_learning_hook_v1(item, detail=choice == "8"))
