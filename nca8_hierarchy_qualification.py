#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H6-B: matched hierarchy controls and read-only qualification reports.

This is an external experiment/inspection module, not a new cognitive owner.
Every live run uses IntegratedRightingTrialV1's existing focal core, BodyMap,
H4 executor and H2 plant. Cases change one declared connection, capability or
external condition; they never supply an answer to Righting. Each run advances
80 physical intervals of 0.05 seconds, regardless of focal cadence or task exit.

The task-PNM control disables only the implemented Prediction registration
consumer. Sparse projection generation and mandatory handoff integrity remain.
A null motor result cannot establish either predictive usefulness or biological
redundancy; task-PNM correspondence and outcomes remain P16-1G. Likewise, a local
achievement and current activity adequacy are not supported task completion.

Observer exports are finite (at most 81 focal reads and 81 physical snapshots).
They cannot restore motor permission or influence cognition. No file is written,
no random value is drawn and no durable learning is performed by these reviews.
"""

from __future__ import annotations

import math
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1
from nca8_body_targets import nominal_body_capabilities_v1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_hierarchy_demo import focal_hierarchy_lines_v1, lower_hierarchy_lines_v1
from nca8_sensorimotor import SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, SensorimotorTargetKindV1
from nca8_sensorimotor_demo import render_sensorimotor_experiment_v1, run_sensorimotor_experiment_v1
from nca8_trace import Nca8TraceEventV1

__version__ = "0.1.0"
__all__ = [
    "HIERARCHY_QUALIFICATION_CASES_V1", "HIERARCHY_QUALIFICATION_GROUPS_V1", "HierarchyQualificationProfileV1",
    "HierarchyPhysicalSampleV1", "HierarchyQualificationResultV1", "hierarchy_qualification_profile_v1",
    "run_hierarchy_qualification_v1", "run_hierarchy_qualification_group_v1", "hierarchy_contrast_v1",
    "render_hierarchy_qualification_v1", "render_hierarchy_qualification_summary_v1",
    "run_hierarchy_qualification_menu_v1", "__version__",
]

HIERARCHY_QUALIFICATION_CASES_V1 = (
    "nominal", "disturbed", "righting_off", "righting_off_disturbed", "mapping_reversed", "orientation_unavailable",
    "fast_feedback_off", "delayed_feedback", "feedback_missing", "local_prediction_off", "task_pnm_consumer_off",
    "cadence_1", "cadence_8", "support_loss", "support_loss_prediction_off", "assistance_off", "assistance_on",
)
HIERARCHY_QUALIFICATION_GROUPS_V1 = ("all", "righting", "mapping", "feedback", "prediction", "cadence", "assistance")
_GROUP_CASES = {
    "all": HIERARCHY_QUALIFICATION_CASES_V1,
    "righting": ("nominal", "righting_off", "disturbed", "righting_off_disturbed"),
    "mapping": ("nominal", "mapping_reversed", "orientation_unavailable"),
    "feedback": ("nominal", "disturbed", "fast_feedback_off", "delayed_feedback", "feedback_missing"),
    "prediction": ("disturbed", "local_prediction_off", "task_pnm_consumer_off", "support_loss", "support_loss_prediction_off"),
    "cadence": ("disturbed", "cadence_1", "cadence_8"),
    "assistance": ("assistance_off", "assistance_on"),
}
_FUNCTIONAL_LIMITS = {
    "durable_maps": 1, "current_source_states": 1, "wnm": 1, "current_pnm": 1,
    "righting_applications": 8, "past_previews": 8, "focal_records": 8, "pending_sensor_deliveries": 16,
    "body_sensor_records": 1, "body_pending_proposals": 1, "body_reserved_records": 2,
    "lower_pursuits": 2, "lower_command_history": 4, "lower_events": 4, "lower_predictions_per_axis": 4,
    "lower_replaced_reports": 2,
}
_CONTRASTS = (
    ("nominal", "righting_off"), ("disturbed", "righting_off_disturbed"),
    ("nominal", "mapping_reversed"), ("nominal", "orientation_unavailable"), ("nominal", "disturbed"),
    ("disturbed", "fast_feedback_off"), ("disturbed", "delayed_feedback"), ("disturbed", "feedback_missing"),
    ("disturbed", "local_prediction_off"), ("disturbed", "task_pnm_consumer_off"),
    ("disturbed", "cadence_1"), ("disturbed", "cadence_8"),
    ("support_loss", "support_loss_prediction_off"), ("assistance_off", "assistance_on"),
)


@dataclass(frozen=True, slots=True)
class HierarchyQualificationProfileV1:
    """A predeclared external experiment, not an instruction for choosing a task.

    The complete physical profile stays in the outer driver. Only the individual
    capability/mapping/registration settings reach their named owners. None of
    the case labels, forcing schedules or observer metrics is a cognitive input.
    The fixed 80-tick horizon and 20-opportunity task cap are never expanded.
    """

    case: str
    physical: MotorWorldProfileV1
    focal_interval_ticks: int = 4
    righting_enabled: bool = True
    orientation_mapping_sign: int = 1
    orientation_available: bool = True
    local_prediction_enabled: bool = True
    task_pnm_consumer_enabled: bool = True
    focal_only_feedback_from_tick: int | None = None

    def __post_init__(self) -> None:
        if not isinstance(self.case, str) or self.case not in HIERARCHY_QUALIFICATION_CASES_V1:
            raise ValueError("unknown hierarchy qualification case")
        if not isinstance(self.physical, MotorWorldProfileV1) or self.physical.dt_seconds != 0.05:
            raise ValueError("qualification preserves the 0.05-second H2 interval")
        if isinstance(self.focal_interval_ticks, bool) or not isinstance(self.focal_interval_ticks, int):
            raise TypeError("focal_interval_ticks must be a non-Boolean integer")
        if self.focal_interval_ticks not in (1, 4, 8):
            raise ValueError("qualification focal intervals are 1, 4 or 8 ticks")
        if isinstance(self.orientation_mapping_sign, bool) or not isinstance(self.orientation_mapping_sign, int):
            raise TypeError("orientation_mapping_sign must be a non-Boolean integer")
        if self.orientation_mapping_sign not in (-1, 1):
            raise ValueError("orientation_mapping_sign must be +1 or -1")
        for name in ("righting_enabled", "orientation_available", "local_prediction_enabled", "task_pnm_consumer_enabled"):
            if not isinstance(getattr(self, name), bool):
                raise TypeError(f"{name} must be Boolean")
        cutoff = self.focal_only_feedback_from_tick
        if cutoff is not None and (isinstance(cutoff, bool) or not isinstance(cutoff, int) or not 0 <= cutoff <= 80):
            raise ValueError("focal-only feedback cutoff must be None or an integer in [0, 80]")

    def as_dict(self) -> dict[str, object]:
        """Disclose unchanged physical constants and every selected intervention."""
        physical = self.physical
        return {
            "profile": "hierarchy_qualification_v1", "case": self.case,
            "dt_seconds": physical.dt_seconds, "physical_horizon_ticks": 80, "task_focal_budget": 20,
            "focal_interval_ticks": self.focal_interval_ticks, "righting_enabled": self.righting_enabled,
            "orientation_mapping_sign": self.orientation_mapping_sign, "orientation_available": self.orientation_available,
            "local_prediction_enabled": self.local_prediction_enabled, "task_pnm_consumer_enabled": self.task_pnm_consumer_enabled,
            "task_pnm_consumer": "Prediction.adopt_support_preview registration only; task outcomes deferred",
            "focal_only_feedback_from_tick": self.focal_only_feedback_from_tick,
            "physical_profile": physical.profile_id, "initial_tilt": physical.initial_body.body_tilt_degrees,
            "initial_extension": physical.initial_body.support_extension, "surface_reach": physical.surface_reach,
            "surface_present": physical.surface_present, "sensor_delay_ticks": physical.sensor_delay_ticks,
            "orientation_motor_enabled": physical.orientation_motor_enabled, "extension_motor_enabled": physical.extension_motor_enabled,
            "unavailable_channels": list(physical.unavailable_channels),
            "external_interventions": [
                {"start_tick": item.start_tick, "stop_tick": item.stop_tick, "angular_rate_degrees_s": item.angular_rate_degrees_s,
                 "remove_support": item.remove_support, "drop_feedback": item.drop_feedback} for item in physical.perturbations
            ],
            "lower_target_tolerance_degrees": 1.0, "mobility_maximum_absolute_tilt_degrees": 12.0,
            "durable_learning_enabled": False,
        }


def hierarchy_qualification_profile_v1(case: str) -> HierarchyQualificationProfileV1:
    """Select fixed controls before running; never adjust them to obtain success.

    Angular disturbance acts over interval [8,9); support loss over [9,12).
    The fast-route ablation starts at tick 8, after a matched physical/target
    prefix. Full sensor loss drops acquisitions from interval 8 onward while
    allowing existing in-flight reports to arrive. The delay control affects
    both lower and focal readers; it is not falsely labelled a lower-only lesion.
    Assistance uses a matched, initially extended body and no Righting in either
    member. Its external -40 degree/s force lasts over intervals [8,20).
    """
    if not isinstance(case, str) or case not in HIERARCHY_QUALIFICATION_CASES_V1:
        raise ValueError("unknown hierarchy qualification case")
    disturbed = case in {
        "disturbed", "righting_off_disturbed", "fast_feedback_off", "delayed_feedback", "feedback_missing",
        "local_prediction_off", "task_pnm_consumer_off", "cadence_1", "cadence_8",
    }
    physical = MotorWorldProfileV1(perturbations=(MotorWorldPerturbationV1(8, 9, 160.0),) if disturbed else ())
    if case == "delayed_feedback":
        physical = replace(physical, sensor_delay_ticks=4)
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(
            MotorWorldPerturbationV1(8, 9, 160.0, drop_feedback=True), MotorWorldPerturbationV1(9, 80, drop_feedback=True),
        ))
    elif case in {"support_loss", "support_loss_prediction_off"}:
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 12, remove_support=True),))
    elif case in {"assistance_off", "assistance_on"}:
        physical = replace(physical, initial_body=MotorBodyStateV1(30.0, 0.9),
                           perturbations=(MotorWorldPerturbationV1(8, 20, -40.0),) if case == "assistance_on" else ())
    return HierarchyQualificationProfileV1(
        case, physical, focal_interval_ticks=1 if case == "cadence_1" else 8 if case == "cadence_8" else 4,
        righting_enabled=case not in {"righting_off", "righting_off_disturbed", "assistance_off", "assistance_on"},
        orientation_mapping_sign=-1 if case == "mapping_reversed" else 1,
        orientation_available=case != "orientation_unavailable",
        local_prediction_enabled=case not in {"local_prediction_off", "support_loss_prediction_off"},
        task_pnm_consumer_enabled=case != "task_pnm_consumer_off",
        focal_only_feedback_from_tick=8 if case == "fast_feedback_off" else None,
    )


@dataclass(frozen=True, slots=True)
class HierarchyPhysicalSampleV1:
    """An external observation of a boundary, not another cognitive sensor event.

    body is simulator truth for the observer. feedback is the latest delivered
    acquisition and can be older or missing channels. Only that legitimate
    feedback already travels through the trial's existing admission interface.
    """

    tick: int
    body: MotorBodyStateV1
    feedback: MotorFeedbackV1

    def as_dict(self) -> dict[str, object]:
        """Keep actual coordinates and delivered evidence explicitly separate."""
        return {
            "tick": self.tick, "observer_tilt": self.body.body_tilt_degrees,
            "observer_extension": self.body.support_extension, "delivered_feedback": self.feedback.as_dict(),
        }


def _drives(step: SensorimotorStepV1) -> tuple[float, float]:
    """Read issued drive values only; neutral is not physical immobilization."""
    command = step.command
    return (0.0, 0.0) if command is None else (command.orientation_drive, command.extension_drive)


@dataclass(frozen=True, slots=True)
class HierarchyQualificationResultV1:
    """A finite observer dossier, with no route back into live cognitive authority.

    The task may stop before the fixed horizon. Remaining physical intervals
    still occur, with only valid remaining local permissions. Counts expose
    that difference; they do not turn the final observation into task success.
    """

    profile: HierarchyQualificationProfileV1
    intervals: tuple[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]], ...]
    final_cycle: IntegratedRightingCycleV1
    physical_samples: tuple[HierarchyPhysicalSampleV1, ...]
    installation_count: int
    handoff_consumptions: int
    registered_pnm_ticks: tuple[int, ...]
    first_task_budget_exit_tick: int | None
    peak_counts: tuple[tuple[str, int], ...]
    trace: tuple[Nca8TraceEventV1, ...]

    @property
    def steps(self) -> tuple[SensorimotorStepV1, ...]:
        """Flatten at most eighty already-recorded updates without running anything."""
        return tuple(step for _, lower in self.intervals for step in lower)

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Check measured functional maxima, not the number of exported trace rows."""
        peaks = dict(self.peak_counts)
        return tuple(
            name for name, limit in _FUNCTIONAL_LIMITS.items()
            if name not in peaks or not 0 <= peaks[name] <= limit
        )

    def metrics(self) -> dict[str, object]:
        """Measure behavior, cost proxies and timing without assigning causal credit.

        Absolute drive-time is a normalized commanded-effort proxy, not energy,
        torque, work in joules or a biological cost. The tick-16 observation is a
        common early checkpoint before the task's 20-opportunity cap can bind in
        these K=1/4/8 profiles. Later cadence comparisons include that budget effect.
        """
        steps = self.steps
        last = self.physical_samples[-1]
        task = self.final_cycle.calculation.task
        achieved = {
            report.committed_target.target.target_id for step in steps for report in step.reports
            if report.disposition is LocalTargetDispositionV1.ACHIEVED
        }
        corrections = tuple(step.tick for step in steps if any(
            item.reason == "bounded_anomalous_correction" for item in step.reports
        ))
        latencies = [
            step.tick - comparison.feedback.event_tick for step in steps for comparison in step.comparisons
            if comparison.unexpected and any(
                report.reason == "bounded_anomalous_correction" and
                report.committed_target.target.target_id == comparison.prediction.target_id for report in step.reports
            )
        ]
        support = self.final_cycle.calculation.source.motor_support
        return {
            "physical_ticks": last.tick, "simulation_seconds": last.tick * 0.05,
            "focal_reads": len(self.intervals) + 1, "target_installations": self.installation_count,
            "handoff_consumptions": self.handoff_consumptions,
            "nonnull_motor_commands": sum(step.command is not None for step in steps),
            "orientation_absolute_drive_time": 0.05 * math.fsum(abs(_drives(step)[0]) for step in steps),
            "extension_absolute_drive_time": 0.05 * math.fsum(abs(_drives(step)[1]) for step in steps),
            "local_achieved_target_count": len(achieved), "anomalous_correction_ticks": list(corrections),
            "same_update_anomaly_response_latency_ticks": latencies,
            "final_source_evidence_current": support is not None and support.current,
            "last_sensed_age_ticks": last.tick - last.feedback.event_tick,
            "registered_pnm_opportunities": len(self.registered_pnm_ticks),
            "first_task_budget_exit_tick": self.first_task_budget_exit_tick,
            "final_source_status": self.final_cycle.calculation.source_status,
            "final_task_status": task.status if task is not None else "no_task_selected",
            "final_observer_tilt": last.body.body_tilt_degrees, "final_observer_extension": last.body.support_extension,
            "last_sensed_tilt": last.feedback.body_tilt_degrees, "last_sensed_loading": last.feedback.useful_loading,
            "last_sensed_contact": last.feedback.support_contact,
            "last_sensed_event_tick": last.feedback.event_tick, "last_sensed_available_tick": last.feedback.available_tick,
            "tick16_observer_tilt": self.physical_samples[16].body.body_tilt_degrees,
            "task_success_established": False, "durable_learning_updates": 0,
        }

    def as_dict(self) -> dict[str, object]:
        """Export a bounded review, never a resumable organism or live motor receipt."""
        return {
            "profile": self.profile.as_dict(), "metrics": self.metrics(),
            "intervals": [{"focal": focal.as_dict(), "lower": [step.as_dict() for step in lower]} for focal, lower in self.intervals],
            "final_focal_read": self.final_cycle.as_dict(),
            "physical_samples": [item.as_dict() for item in self.physical_samples],
            "registered_pnm_ticks": list(self.registered_pnm_ticks), "peak_owner_counts": dict(self.peak_counts),
            "owner_limits": dict(_FUNCTIONAL_LIMITS), "bound_violations": list(self.bound_violations),
            "restores_live_permissions": False, "task_outcomes": "deferred_to_P16_1G",
        }


def _collect_peaks(peaks: dict[str, int], trial: IntegratedRightingTrialV1) -> None:
    """Read actual owner counts after a completed boundary; change diagnostics only."""
    for name, count in trial.retained_counts().items():
        peaks[name] = max(count, peaks.get(name, 0))


def run_hierarchy_qualification_v1(case: str = "nominal", *, trace_capacity: int = 256) -> HierarchyQualificationResultV1:
    """Run one fresh declared profile through the existing hierarchy at fixed time.

    Only the external call schedule is coordinated here. Focal decisions, target
    mapping, handoff consumption, local control and physics are never reimplemented.
    No early favorable/adverse result changes the 80-tick horizon. An exception
    propagates as a failed review, not an invented successful or safe trajectory.
    Each stored sample is observer-only, with acquisition and availability intact.
    """
    profile = hierarchy_qualification_profile_v1(case)
    if isinstance(trace_capacity, bool) or not isinstance(trace_capacity, int) or not 1 <= trace_capacity <= 4096:
        raise ValueError("trace_capacity must be an integer in [1, 4096]")
    capabilities = nominal_body_capabilities_v1()
    if not profile.orientation_available:
        capabilities = tuple(item for item in capabilities if item.kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    trial = IntegratedRightingTrialV1(
        profile.physical, capabilities=capabilities, righting_enabled=profile.righting_enabled,
        orientation_mapping_sign=profile.orientation_mapping_sign, task_pnm_consumer_enabled=profile.task_pnm_consumer_enabled,
        focal_only_feedback_from_tick=profile.focal_only_feedback_from_tick, trace_capacity=trace_capacity,
        control_profile=SensorimotorProfileV1(profile.local_prediction_enabled, min(256, trace_capacity)),
    )
    intervals: list[tuple[IntegratedRightingCycleV1, tuple[SensorimotorStepV1, ...]]] = []
    samples = [HierarchyPhysicalSampleV1(trial.tick, trial.observer_body, trial.latest_feedback)]
    peaks: dict[str, int] = {}
    registered: list[int] = []
    first_exit: int | None = None
    _collect_peaks(peaks, trial)
    for _ in range(80 // profile.focal_interval_ticks):
        focal = trial.focal_step()
        if trial.core.cognition.prediction.current_support_preview is not None:
            registered.append(trial.tick)
        if first_exit is None and focal.calculation.task is not None and focal.calculation.task.status == "budget_exhausted":
            first_exit = trial.tick
        _collect_peaks(peaks, trial)
        lower: list[SensorimotorStepV1] = []
        for _ in range(profile.focal_interval_ticks):
            lower.append(trial.advance_lower())
            samples.append(HierarchyPhysicalSampleV1(trial.tick, trial.observer_body, trial.latest_feedback))
            _collect_peaks(peaks, trial)
        intervals.append((focal, tuple(lower)))
    final = trial.focal_step()
    if trial.core.cognition.prediction.current_support_preview is not None:
        registered.append(trial.tick)
    if first_exit is None and final.calculation.task is not None and final.calculation.task.status == "budget_exhausted":
        first_exit = trial.tick
    _collect_peaks(peaks, trial)
    return HierarchyQualificationResultV1(
        profile, tuple(intervals), final, tuple(samples), trial.controller.installation_count,
        trial.handoff_consumptions, tuple(registered), first_exit, tuple(sorted(peaks.items())), trial.core.trace.snapshot(),
    )


def run_hierarchy_qualification_group_v1(group: str = "all", *, trace_capacity: int = 256) -> tuple[HierarchyQualificationResultV1, ...]:
    """Run only the declared comparison group in isolated fresh trials, in fixed order."""
    if not isinstance(group, str) or group not in _GROUP_CASES:
        raise ValueError("unknown hierarchy qualification group")
    return tuple(run_hierarchy_qualification_v1(case, trace_capacity=trace_capacity) for case in _GROUP_CASES[group])


def _forcing(profile: MotorWorldProfileV1) -> tuple[tuple[int, int, float, bool], ...]:
    """Extract physical forcing, deliberately excluding a sensor-only dropout change."""
    return tuple((item.start_tick, item.stop_tick, item.angular_rate_degrees_s, item.remove_support)
                 for item in profile.perturbations if item.angular_rate_degrees_s != 0.0 or item.remove_support)


def hierarchy_contrast_v1(reference: HierarchyQualificationResultV1, control: HierarchyQualificationResultV1) -> dict[str, object]:
    """Describe an actual pair without pretending every changed outcome is selective.

    The report explicitly checks physical starting conditions, forcing and horizon.
    It reports both first drive divergence and endpoint differences. An absent
    drive difference is a legitimate null result, not a reason to change a profile.
    Sensor delay or the focal-opportunity cap can change later task contributions;
    their output is not relabelled as an identical-target lower-only experiment.
    """
    if not isinstance(reference, HierarchyQualificationResultV1) or not isinstance(control, HierarchyQualificationResultV1):
        raise TypeError("contrast requires two recorded hierarchy qualifications")
    original, changed = reference.profile.physical, control.profile.physical
    first_difference = next((a.tick for a, b in zip(reference.steps, control.steps) if _drives(a) != _drives(b)), None)
    return {
        "reference": reference.profile.case, "control": control.profile.case,
        "same_initial_body": original.initial_body == changed.initial_body,
        "same_physical_forcing": _forcing(original) == _forcing(changed),
        "same_surface_and_motors": (original.surface_reach, original.surface_present,
                                    original.orientation_motor_enabled, original.extension_motor_enabled) ==
                                   (changed.surface_reach, changed.surface_present,
                                    changed.orientation_motor_enabled, changed.extension_motor_enabled),
        "same_dt_and_horizon": original.dt_seconds == changed.dt_seconds and
                               reference.physical_samples[-1].tick == control.physical_samples[-1].tick,
        "same_sensor_delay": original.sensor_delay_ticks == changed.sensor_delay_ticks,
        "first_drive_difference_tick": first_difference,
        "final_observer_tilt_difference": control.physical_samples[-1].body.body_tilt_degrees -
                                          reference.physical_samples[-1].body.body_tilt_degrees,
        "tick16_observer_tilt_difference": control.physical_samples[16].body.body_tilt_degrees -
                                           reference.physical_samples[16].body.body_tilt_degrees,
        "reference_budget_exit_tick": reference.first_task_budget_exit_tick,
        "control_budget_exit_tick": control.first_task_budget_exit_tick,
        "task_success_inferred": False,
    }


def _optional(value: float | None) -> str:
    """Keep unknown measurements distinct from a numeric zero."""
    return "unknown" if value is None else f"{value:.4f}"


def render_hierarchy_qualification_v1(result: HierarchyQualificationResultV1, *, detail: bool = False) -> str:
    """Render one completed run using the same focal/lower formatter as H6-A."""
    if not isinstance(result, HierarchyQualificationResultV1) or not isinstance(detail, bool):
        raise TypeError("render requires a qualification result and a Boolean detail flag")
    profile = result.profile
    lines = [
        f"P18-H6-B HIERARCHY QUALIFICATION | {profile.case}",
        f"Fixed horizon=80 ticks / 4.00 s; K={profile.focal_interval_ticks}; unchanged 20-opportunity task cap.",
        f"Righting={profile.righting_enabled}; mapping sign={profile.orientation_mapping_sign:+d}; "
        f"orientation capability={profile.orientation_available}; local prediction consumer={profile.local_prediction_enabled}.",
        f"Task-PNM registration consumer={profile.task_pnm_consumer_enabled}; generation and handoff integrity remain.",
        f"Sensor delay={profile.physical.sensor_delay_ticks}; focal-only lower feedback from={profile.focal_only_feedback_from_tick}.",
        "The external case label/forcing are not cognitive inputs. No task completion or causal learning is established.", "",
    ]
    for focal, lower in result.intervals:
        lines.extend(focal_hierarchy_lines_v1(focal))
        lines.append(f"  PNM registration: {focal.calculation.cutoff_tick in result.registered_pnm_ticks}; "
                     "task-PNM outcome consumer remains deferred.")
        lines.extend(lower_hierarchy_lines_v1(lower, detail=detail))
        delivered = result.physical_samples[lower[-1].tick + 1].feedback
        lines.append(f"  INPUT next eligible acquisition: sample={delivered.sample_id}; "
                     f"event={delivered.event_tick}; available={delivered.available_tick}.")
        lines.append("")
    lines.extend(focal_hierarchy_lines_v1(result.final_cycle))
    metrics = result.metrics()
    lines.extend([
        "", f"FINAL: {metrics['physical_ticks']} physical updates; {metrics['focal_reads']} focal reads; "
        f"{result.installation_count} installations; first task-budget exit tick={result.first_task_budget_exit_tick}.",
        f"Last SENSED tilt={_optional(result.physical_samples[-1].feedback.body_tilt_degrees)}; "
        f"OBSERVER final tilt={result.physical_samples[-1].body.body_tilt_degrees:.4f}.",
        f"Current source status={metrics['final_source_status']}; task status={metrics['final_task_status']}.",
        f"Commanded absolute drive-time (not energy): orientation={metrics['orientation_absolute_drive_time']:.6f}; "
        f"extension={metrics['extension_absolute_drive_time']:.6f}.",
        f"Owner storage-bound violations={list(result.bound_violations)}; peak counts={dict(result.peak_counts)}.",
        "Local target achievement != task completion. Near-boundary tolerance/criterion mismatch is unchanged.",
        "Task completion NOT established; durable learning updates=0; P16-1G and A99 remain open.",
    ])
    return "\n".join(lines)


def render_hierarchy_qualification_summary_v1(results: tuple[HierarchyQualificationResultV1, ...]) -> str:
    """Print actual matched metrics, null effects and scope limits; never rerun a trial."""
    if not isinstance(results, tuple) or not results or len(results) > len(HIERARCHY_QUALIFICATION_CASES_V1):
        raise ValueError("summary requires a nonempty bounded tuple of qualification results")
    if any(not isinstance(item, HierarchyQualificationResultV1) for item in results):
        raise TypeError("summary contains a non-qualification result")
    by_case = {item.profile.case: item for item in results}
    if len(by_case) != len(results):
        raise ValueError("summary case identities must be distinct")
    lines = [
        "P18-H6-B -- HIERARCHY QUALIFICATION SUMMARY", "All rows: 80 physical updates / 4.00 s; no durable learning or A99 claim.",
        "focal=closed reads (includes final read); install=target envelopes; cmd=nonneutral motor commands; PNM=registration opportunities.",
        "drive-time=absolute normalized drive integrated over time, not energy; response delay=physical event to same-update correction.",
        "case                              K focal install  cmd  sensed tilt  actual tilt  budget@  PNM", "-" * 100,
    ]
    for item in results:
        metrics = item.metrics()
        last = item.physical_samples[-1]
        lines.append(
            f"{item.profile.case:32s} {item.profile.focal_interval_ticks:2d} {len(item.intervals) + 1:5d} "
            f"{item.installation_count:7d} {metrics['nonnull_motor_commands']:4d} "
            f"{_optional(last.feedback.body_tilt_degrees):>12s} {last.body.body_tilt_degrees:12.4f} "
            f"{str(item.first_task_budget_exit_tick):>8s} {len(item.registered_pnm_ticks):4d}"
        )
        lines.append(f"  source={item.final_cycle.calculation.source_status}; current evidence={metrics['final_source_evidence_current']}; "
                     f"corrections={metrics['anomalous_correction_ticks']}; response delay ticks={metrics['same_update_anomaly_response_latency_ticks']}")
        lines.append(f"  drive-time orientation/extension={metrics['orientation_absolute_drive_time']:.6f}/"
                     f"{metrics['extension_absolute_drive_time']:.6f}; "
                     f"bounds={'PASS' if not item.bound_violations else list(item.bound_violations)}")
    lines.extend(["", "PAIRED MEASUREMENTS -- control minus reference; different forcing is explicit"])
    for original, changed in _CONTRASTS:
        if original not in by_case or changed not in by_case:
            continue
        pair = hierarchy_contrast_v1(by_case[original], by_case[changed])
        lines.append(f"  {original} -> {changed}: first drive difference={pair['first_drive_difference_tick']}; "
                     f"final tilt delta={pair['final_observer_tilt_difference']:+.6f}; "
                     f"same start/forcing/time={pair['same_initial_body']}/{pair['same_physical_forcing']}/{pair['same_dt_and_horizon']}")
    lines.extend([
        "", "INTERPRETATION LIMITS",
        "  fast_feedback_off retains valid focal sensing but removes the fast return from tick 8; stale local samples never gain new time.",
        "  delayed_feedback changes both source and lower availability; feedback_missing drops acquisitions, not contact measurements.",
        "  task_pnm_consumer_off disables registration only. Same drives are a NULL motor effect, not proof that task prediction is useful or useless.",
        "  Sparse PNM generation and origin guards remain. A substantive task-PNM outcome consumer is not implemented until P16-1G.",
        "  Cadence K=1 can exhaust the unchanged 20-opportunity budget at tick 20; K=4/8 retain the same 80-tick physical horizon.",
        "  The common tick-16 observer tilts below precede that cap; later differences include budget exhaustion, not only polling latency.",
    ])
    for item in results:
        if item.profile.case in {"disturbed", "cadence_1", "cadence_8"}:
            lines.append(f"    {item.profile.case}: tick16 tilt={item.physical_samples[16].body.body_tilt_degrees:.6f}; "
                         f"first budget exit={item.first_task_budget_exit_tick}")
    lines.extend([
        "  Assistance uses matched tilt30/extension0.9 starts with Righting disabled. Any improvement is not credited to an absent command.",
        "  Local success, current adequacy and supported task completion remain distinct. No criterion, tolerance or physics was tuned to force success.",
        "  Retained H4 fixed-target/open-loop controls are separate lower-only experiments, not Navigation-selected tasks.",
        "Review candidate only: local validation and manual acceptance are still required; P16-1G and A99 remain open.",
    ])
    return "\n".join(lines)


def _review_case_menu(detail: bool) -> None:
    """Select one fresh trial by visible case number; cancelling runs nothing."""
    print("\nSelect an isolated qualification profile:")
    for number, case in enumerate(HIERARCHY_QUALIFICATION_CASES_V1, start=1):
        print(f"  {number}) {case}")
    print("  [Enter] Cancel")
    choice = cca8_cli.read_menu_input_v1()
    if not choice:
        return
    choices = {str(number): case for number, case in enumerate(HIERARCHY_QUALIFICATION_CASES_V1, start=1)}
    if choice not in choices:
        print("Choose one of the displayed profile numbers.")
        return
    result = run_hierarchy_qualification_v1(choices[choice])
    print(render_hierarchy_qualification_v1(result, detail=detail))


def run_hierarchy_qualification_menu_v1() -> None:
    """Inspect shared H6-B controls without touching an existing A0 or live trial.

    Opening, returning and invalid selections construct no trial. Each requested
    experiment is fresh, synchronous and finite. Compact/detail render the same
    recorded computation. Retained H4 comparisons call their original shared
    functions and explicitly retain their supplied-target, no-task scope.
    """
    groups = {"1": "all", "2": "mapping", "3": "feedback", "4": "prediction", "5": "cadence", "6": "assistance", "7": "righting"}
    while True:
        print("\nP18-H6-B -- HIERARCHY QUALIFICATION / INSPECTION")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("  1) All qualification profiles (summary and matched contrasts)")
        print("  2) BodyMap mapping / missing orientation capability")
        print("  3) Disturbed fast-feedback / delayed / missing sensing")
        print("  4) Local prediction and task-PNM registration controls")
        print("  5) Focal cadence K=1/4/8 at fixed physical horizon")
        print("  6) External assistance with no Righting commands")
        print("  7) Righting organization on/off, nominal and disturbed")
        print("  8) Inspect one profile (compact causal timeline)")
        print("  9) Inspect one profile (detailed local timeline)")
        print("  10) Retained H4 fixed-target feedback/open-loop/prediction controls")
        print("  [Enter] Return to integrated hierarchy review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice in groups:
            print(render_hierarchy_qualification_summary_v1(run_hierarchy_qualification_group_v1(groups[choice])))
        elif choice in {"8", "9"}:
            _review_case_menu(choice == "9")
        elif choice == "10":
            print("H4 LOWER-ONLY CONTROLS: supplied targets, not selected Righting; twelve physical ticks per case.")
            for case in ("perturbed", "feedback_off", "prediction_off", "support_loss", "support_loss_prediction_off"):
                print("\n".join(render_sensorimotor_experiment_v1(run_sensorimotor_experiment_v1(case))))
        else:
            print("Choose 1-10, or press Enter to return.")
