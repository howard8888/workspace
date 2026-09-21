#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2A-B finite translation experiments using the existing hierarchy driver.

The experiment supplies a one-shot LP-kind interface fixture, not a new innate
visual IP or acquired Follow-Mom behavior. The common A-F core selects it from
current visual geometry; BodyMap authorizes an anchored vector target; the same
local executor and motor world consume its drives. Twelve lower intervals and
four focal opportunities are fixed across cases. Observer truth never enters
cognition. No renderer advances the world or restores motor permission.
"""

#pylint: disable=duplicate-code

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1,
    PlanarObjectV1, PlanarPerturbationV1, PlanarWorldProfileV1, PlanarWorldStateV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_sensorimotor import SensorimotorProfileV1, SensorimotorStepV1
from nca8_translation import TranslationFixtureV1

__version__ = "0.1.0"
__all__ = [
    "TRANSLATION_CASES_V1", "TranslationExperimentV1", "create_translation_trial_v1", "run_translation_v1",
    "render_translation_v1", "run_translation_menu_v1", "__version__",
]
TRANSLATION_CASES_V1 = (
    "heading_0", "heading_90", "rotated_coordinates", "translated_coordinates", "different_target",
    "mapping_reversed", "capability_missing", "motor_blocked", "recognition_off", "spatial_off", "vision_missing",
    "heading_missing", "contact_unknown", "narrowed", "obstacle_contact", "support_loss", "support_priority",
    "disturbed", "feedback_slow", "prediction_off", "yaw_disturbed", "feedback_missing", "feedback_delayed", "cancelled",
)
_LIMITS = {
    "durable_maps": 1, "current_source_states": 1, "wnm": 1, "current_pnm": 1, "righting_applications": 8,
    "past_previews": 8, "focal_records": 8, "focal_trace": 4096, "pending_sensor_deliveries": 16,
    "body_sensor_records": 1, "body_pending_proposals": 1, "body_reserved_records": 2, "planar_body_records": 1,
    "lower_pursuits": 2, "lower_command_history": 4, "lower_events": 4, "lower_trace": 256,
    "lower_predictions_per_axis": 4, "lower_replaced_reports": 2,
    "visual_durable_maps": 1, "visual_acquisitions": 1, "visual_current_configurations": 1,
    "visual_retained_detections": 8, "visual_recognition_contributions": 8, "visual_guidance_contributions": 8,
}


def create_translation_trial_v1(case: str, *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Configure independent fixed controls before running any focal or motor work.

    Coordinates, support, perturbations and hardware availability are external
    conditions, never case labels consumed by an operation or controller. The
    same quarter-metre request and eight-tick lease apply throughout. The narrowed
    case changes only available BodyMap step capability, preserving the original
    source forecast. Heading and whole-coordinate changes are different controls.
    """
    if not isinstance(case, str) or case not in TRANSLATION_CASES_V1:
        raise ValueError("unknown translation experiment")
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    planar = PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2.0, 1.0)),))
    fixture = TranslationFixtureV1()
    capability: BodyTranslationCapabilityV1 | None = BodyTranslationCapabilityV1()
    control = SensorimotorProfileV1()
    if case == "heading_90":
        planar = replace(planar, initial_heading=90.0)
    elif case == "rotated_coordinates":
        planar = replace(planar, frame_id="scene_xy:rotated", initial_heading=90.0,
                         objects=(PlanarObjectV1("region_1", (-1.0, 2.0)),))
    elif case == "translated_coordinates":
        planar = replace(planar, initial_position=(10.0, -3.0), objects=(PlanarObjectV1("region_1", (12.0, -2.0)),))
    elif case == "different_target":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (2.0, -1.0)),))
    elif case == "capability_missing":
        capability = None
    elif case == "motor_blocked":
        planar = replace(planar, motor_enabled=False)
    elif case == "recognition_off":
        fixture = replace(fixture, recognition_enabled=False)
    elif case == "spatial_off":
        fixture = replace(fixture, spatial_enabled=False)
    elif case == "vision_missing":
        planar = replace(planar, vision_available=False)
    elif case == "heading_missing":
        planar = replace(planar, heading_available=False)
    elif case == "contact_unknown":
        planar = replace(planar, contact_available=False)
    elif case == "narrowed":
        capability = BodyTranslationCapabilityV1(maximum_step=0.1)
    elif case == "obstacle_contact":
        planar = replace(planar, objects=(*planar.objects, PlanarObjectV1("obstacle", (0.14, 0.07), radius=0.045)))
    elif case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, 12, remove_support=True),))
    elif case == "support_priority":
        physical = replace(physical, initial_body=MotorBodyStateV1(30.0, 0.4))
    elif case in {"disturbed", "feedback_slow", "prediction_off"}:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 2, velocity=(0.0, 1.2)),))
        if case == "prediction_off":
            control = replace(control, prediction_protection=False)
    elif case == "yaw_disturbed":
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 3, heading_rate=180.0),))
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, 12, drop_feedback=True),))
    elif case == "feedback_delayed":
        physical = replace(physical, sensor_delay_ticks=4)
    return IntegratedRightingTrialV1(
        physical, stream_id="translation_reference_body", planar_profile=planar, translation_fixture=fixture,
        translation_capability=capability, translation_mapping_sign=-1 if case == "mapping_reversed" else 1,
        control_profile=control, trace_capacity=trace_capacity,
        focal_only_feedback_from_tick=0 if case == "feedback_slow" else None,
    )


def _durable_signature(trial: IntegratedRightingTrialV1) -> str:
    """Read actual source-owned durable records, not a canned unchanged flag."""
    visual = trial.core.visual
    if visual is None:
        raise ValueError("translation inspection requires the actual visual owner")
    return json.dumps({"visual": visual.durable_map.as_dict(),
                       "posture": trial.core.cognition.maps.durable_map().as_dict()}, sort_keys=True)


@dataclass(frozen=True, slots=True)
class TranslationExperimentV1:
    """Completed bounded observer export; never a live task/source or a saved agent."""

    case: str
    cycles: tuple[IntegratedRightingCycleV1, ...]
    local_steps: tuple[SensorimotorStepV1, ...]
    physical_samples: tuple[PlanarWorldStateV1, ...]
    final_feedback: MotorFeedbackV1
    peak_counts: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str

    @property
    def bound_violations(self) -> tuple[str, ...]:
        """Compare every measured owner count against its declared independent bound."""
        return tuple(name for name, value in self.peak_counts if name not in _LIMITS or value > _LIMITS[name])

    @property
    def durable_unchanged(self) -> bool:
        """Compare actual source organization; current movement is not plasticity."""
        return self.durable_before == self.durable_after

    def as_dict(self) -> dict[str, object]:
        """Export real commitments, commands and observations with honest fixture scope."""
        return {"case": self.case, "profile": "visual_translation_v1", "scope": "supplied_operation_not_acquired",
                "physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
                "cycles": [item.as_dict() for item in self.cycles], "local_steps": [item.as_dict() for item in self.local_steps],
                "observer_physical_samples": [item.as_dict() for item in self.physical_samples],
                "final_feedback": self.final_feedback.as_dict(), "peak_counts": dict(self.peak_counts),
                "bound_violations": list(self.bound_violations), "durable_unchanged": self.durable_unchanged,
                "durable_updates": 0, "maternal_identity_or_following": False, "task_outcome_consumer": "not_implemented_for_visual"}


def run_translation_v1(case: str = "heading_0", *, trace_capacity: int = 256) -> TranslationExperimentV1:
    """Run one isolated twelve-tick physical trial; all controls have equal duration.

    The external harness specifies when an opportunity occurs, not which source
    or operation wins. It records actual physical coordinates only after the
    lower call. The core receives admitted observations, never these snapshots.
    Final focal admission at tick12 performs no extra physical step and cannot
    revive the already spent one-shot operation or an expired motor lease.
    """
    trial = create_translation_trial_v1(case, trace_capacity=trace_capacity)
    before = _durable_signature(trial)
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[PlanarWorldStateV1] = []
    peaks: dict[str, int] = {}

    def observe() -> None:
        """Read boundedness independently of text retention and future work."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    for tick in range(12):
        if tick % 4 == 0:
            cycles.append(trial.focal_step())
            observe()
        if case == "cancelled" and tick == 2:
            trial.cancel()
        local.append(trial.advance_lower())
        body = trial.observer_planar_body
        if body is None:
            raise RuntimeError("planar provider unexpectedly disappeared")
        physical.append(body)
        observe()
    cycles.append(trial.focal_step())
    observe()
    return TranslationExperimentV1(case, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback,
                                   tuple(sorted(peaks.items())), before, _durable_signature(trial))


def render_translation_v1(result: TranslationExperimentV1, *, detail: bool = False) -> str:
    """Inspect completed evidence only; showing a trace can never move the body."""
    if not isinstance(result, TranslationExperimentV1) or not isinstance(detail, bool):
        raise TypeError("expected a completed translation result and Boolean detail")
    first, last = result.cycles[0], result.cycles[-1]
    lines = [f"P16-2A-B TRANSLATION | {result.case}",
             "  Supplied LP-kind operation fixture; NOT an innate visual IP, acquired LP or Follow-Mom.",
             f"  physical ticks={len(result.local_steps)}; elapsed={len(result.local_steps) * 0.05:.2f}s; focal opportunities={len(result.cycles)}",
             f"  first selected={first.commitment.selected_primitive_id}; action={first.commitment.task_action}"]
    motor = first.receipt.dispatch.motor
    if detail and motor is not None and motor.projection is not None:
        lines.append(f"  original sparse PNM={motor.projection.as_dict()}")
    for reservation in first.reservations:
        target = reservation.current.target
        lines.append(f"  BodyMap {target.kind.value}: offset={target.offset}; anchored endpoint={target.endpoint}; "
                     f"lease=[{reservation.current.committed_tick},{reservation.current.expires_at_tick})")
    if first.calculation.proposal is not None and first.calculation.proposal.withheld:
        lines.append(f"  BodyMap withheld={first.calculation.proposal.withheld}")
    lines.append(f"  final actual planar body={result.physical_samples[-1].as_dict()}")
    lines.append(f"  last delivered event={result.final_feedback.event_tick}/available={result.final_feedback.available_tick}; "
                 f"planar={None if result.final_feedback.planar is None else result.final_feedback.planar.as_dict()}")
    for report in result.local_steps[-1].reports:
        lines.append(f"  local {report.committed_target.target.kind.value}: {report.disposition.value}; {report.reason}")
    source = last.visual_source
    if source is not None:
        lines.append(f"  returning source={source.source_map_ref.map_id}; sample={source.sample_id}; status={source.input_status}; "
                     f"SELF={None if source.self_position is None else source.self_position.as_dict()}")
    if detail:
        for cycle in result.cycles:
            lines.append(f"  focal cutoff={cycle.calculation.cutoff_tick}: source="
                         f"{cycle.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id if cycle.calculation.navigation.wnm else None}; "
                         f"operation={cycle.commitment.selected_primitive_id}; receipt={cycle.receipt.disposition}")
        for step, body in zip(result.local_steps, result.physical_samples):
            drive = None if step.command is None or step.command.translation is None else step.command.translation.as_dict()
            lines.append(f"  lower tick={step.tick}: drive={drive}; actual={body.position}; "
                         f"reports={[(item.disposition.value, item.reason) for item in step.reports]}")
    lines.append(f"  bounds={list(result.bound_violations)}; durable unchanged={result.durable_unchanged}; learned updates=0")
    lines.append("  Local target achievement is not task-level visual PNM correspondence, maternal approach or B99.")
    return "\n".join(lines)


def run_translation_menu_v1() -> None:
    """Use the same finite experiment functions from the visual menu, without resets."""
    groups = {"1": TRANSLATION_CASES_V1, "2": TRANSLATION_CASES_V1[:5],
              "3": ("heading_0", "mapping_reversed", "narrowed", "capability_missing", "motor_blocked"),
              "4": ("heading_0", "recognition_off", "spatial_off", "vision_missing", "heading_missing", "contact_unknown"),
              "5": ("disturbed", "feedback_slow", "prediction_off", "yaw_disturbed"),
              "6": ("obstacle_contact", "support_loss", "support_priority", "feedback_missing", "feedback_delayed", "cancelled"),
              "7": ("heading_0",)}
    while True:
        print("\nP16-2A-B -- REAL TRANSLATION / CONTACT REVIEW\n"
              "  1) All fixed profiles\n  2) Heading, coordinate re-expression and target direction\n"
              "  3) Mapping, narrowing, missing capability and blocked motor\n"
              "  4) Independent sensory products and missing evidence\n  5) Fast feedback, local prediction and yaw disturbance\n"
              "  6) Contact, support, missing/delayed feedback and cancellation\n  7) Detailed nominal timeline\n"
              "  [Enter] Return to visual review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice not in groups:
            print("Choose 1-7 or press Enter to return.")
            continue
        for case in groups[choice]:
            print(render_translation_v1(run_translation_v1(case), detail=choice == "7"))
