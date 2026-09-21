#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Menu-first maternal approach qualification on the existing physical hierarchy.

Live cases start in supported standing, use one declared initial MOM association,
and run eighty 0.05-second physical intervals. The ordinary A-F core selects the
actual Follow-Mom IP, and the existing BodyMap/executor/provider perform movement.
External truth is retained only for inspection. Separate explicitly nonphysical
replays examine contradictory recognition and independently approaching targets.
Neither set closes the combined stand-to-follow or maternal PNM-outcome gates.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1,
    PlanarObjectV1, PlanarPerturbationV1, PlanarWorldProfileV1, PlanarWorldStateV1,
)
from nca8_body_targets import BodyTranslationCapabilityV1
from nca8_followmom import FollowMomIPV1, FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingCycleV1, IntegratedRightingTrialV1
from nca8_maternal import MaternalNavMapStateV1, MaternalSeedV1, MaternalSourceV1
from nca8_sensorimotor import SensorimotorStepV1
from nca8_visual import VisualDetectionV1, VisualObservationV1, VisualSourceV1

__version__ = "0.1.0"
__all__ = ["FOLLOW_MOM_CASES_V1", "MATERNAL_REPLAY_CASES_V1", "FollowMomExperimentV1", "MaternalSourceReplayV1",
           "create_follow_mom_trial_v1", "run_follow_mom_v1", "run_maternal_source_replay_v1",
           "render_follow_mom_v1", "render_maternal_replay_v1", "run_follow_mom_menu_v1", "__version__"]

FOLLOW_MOM_CASES_V1 = (
    "nominal", "heading_90", "different_target", "already_near", "association_off", "wrong_seed",
    "recognition_off", "spatial_off", "following_off", "brief_gap", "prolonged_gap", "support_interruption",
    "mapping_reversed", "narrowed", "obstacle_contact", "motor_blocked", "feedback_missing", "cancelled",
    "competing_on", "competing_off", "fast_cadence", "far_target", "assisted", "assisted_no_task",
)
MATERNAL_REPLAY_CASES_V1 = ("independent_approach", "own_closing", "contradiction", "relocated_target")
# These shared-owner limits deliberately match the independent translation control.
# pylint: disable=duplicate-code
_LIMITS = {
    "durable_maps": 1, "current_source_states": 1, "wnm": 1, "current_pnm": 1, "righting_applications": 8,
    "past_previews": 8, "focal_records": 8, "focal_trace": 4096, "pending_sensor_deliveries": 16,
    "body_sensor_records": 1, "body_pending_proposals": 1, "body_reserved_records": 2, "planar_body_records": 1,
    "lower_pursuits": 2, "lower_command_history": 4, "lower_events": 4, "lower_trace": 256,
    "lower_predictions_per_axis": 4, "lower_replaced_reports": 2,
    "visual_durable_maps": 1, "visual_acquisitions": 1, "visual_current_configurations": 1,
    "visual_retained_detections": 8, "visual_recognition_contributions": 8, "visual_guidance_contributions": 8,
    "maternal_durable_maps": 1, "maternal_current_configurations": 1, "maternal_supported_bases": 1,
    "maternal_influence_requests": 1, "follow_mom_tasks": 1, "follow_mom_source_bases": 1,
    "follow_mom_local_targets": 1, "follow_mom_supported_samples": 3, "follow_mom_applications": 8,
}
# pylint: enable=duplicate-code


def create_follow_mom_trial_v1(case: str, *, trace_capacity: int = 256) -> IntegratedRightingTrialV1:
    """Configure task-independent physical conditions and declared sensory scaffolds.

    All live cases start supported. The existing body equations and motor limits
    are unchanged. Missing visual access is controlled at scheduled focal input
    admissions by the outer runner; it is not a hidden instruction to the IP.
    Contact/support failures remain sensed by the existing lower controller.
    """
    if not isinstance(case, str) or case not in FOLLOW_MOM_CASES_V1:
        raise ValueError("unknown Follow-Mom experiment")
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    planar = PlanarWorldProfileV1(objects=(PlanarObjectV1("region_1", (2.0, 1.0)),))
    profile = FollowMomProfileV1()
    capability = BodyTranslationCapabilityV1()
    if case == "heading_90":
        planar = replace(planar, initial_heading=90.0)
    elif case == "different_target":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (2.0, -1.0)),))
    elif case == "already_near":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (0.4, 0.0)),))
    elif case == "association_off":
        profile = replace(profile, association_enabled=False)
    elif case == "wrong_seed":
        profile = replace(profile, seed=MaternalSeedV1("unobserved_region"))
    elif case == "recognition_off":
        profile = replace(profile, recognition_enabled=False)
    elif case == "spatial_off":
        profile = replace(profile, spatial_enabled=False)
    elif case in {"following_off", "assisted_no_task"}:
        profile = replace(profile, following_enabled=False)
    elif case == "competing_off":
        profile = replace(profile, influence_enabled=False)
    elif case == "support_interruption":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 17, remove_support=True),))
    elif case == "narrowed":
        capability = BodyTranslationCapabilityV1(maximum_step=0.1)
    elif case == "obstacle_contact":
        planar = replace(planar, objects=(*planar.objects, PlanarObjectV1("obstacle", (0.14, 0.07), radius=0.045)))
    elif case == "motor_blocked":
        planar = replace(planar, motor_enabled=False)
    elif case == "feedback_missing":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(9, 80, drop_feedback=True),))
    elif case == "far_target":
        planar = replace(planar, objects=(PlanarObjectV1("region_1", (20.0, 1.0)),))
    if case in {"assisted", "assisted_no_task"}:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 21, velocity=(1.6, 0.8)),))
    return IntegratedRightingTrialV1(
        physical, stream_id="maternal_reference_body", planar_profile=planar, follow_mom_profile=profile,
        translation_capability=capability, translation_mapping_sign=-1 if case == "mapping_reversed" else 1,
        trace_capacity=trace_capacity,
    )


def _durable(trial: IntegratedRightingTrialV1) -> str:
    """Measure all three actual enduring source organizations, not a canned flag."""
    visual, maternal = trial.core.visual, trial.core.maternal
    if visual is None or maternal is None:
        raise ValueError("maternal trial is missing its source owners")
    return json.dumps({"posture": trial.core.cognition.maps.durable_map().as_dict(),
                       "visual": visual.durable_map.as_dict(), "maternal": maternal.durable_map.as_dict()}, sort_keys=True)


# Parallel observer schemas keep task-specific reports independently inspectable.
# pylint: disable=duplicate-code
@dataclass(frozen=True, slots=True)
class FollowMomExperimentV1:
    """Finite external observer record; neither a current source nor a saved agent."""

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
        """Check every measured owner count against its declared finite bound."""
        return tuple(name for name, value in self.peak_counts if name not in _LIMITS or value > _LIMITS[name])

    @property
    def durable_unchanged(self) -> bool:
        """Source configuration changes are not learning of a map or association."""
        return self.durable_before == self.durable_after

    def as_dict(self) -> dict[str, object]:
        """Export distinct selected tasks, motor work and current-proximity evidence."""
        return {"case": self.case, "profile": "maternal_approach_v1", "initial_condition": "supported_standing",
                "physical_ticks": len(self.local_steps), "elapsed_seconds": len(self.local_steps) * 0.05,
                "cycles": [item.as_dict() for item in self.cycles], "local_steps": [item.as_dict() for item in self.local_steps],
                "observer_physical_samples": [item.as_dict() for item in self.physical_samples],
                "final_feedback": self.final_feedback.as_dict(), "peak_counts": dict(self.peak_counts),
                "bound_violations": list(self.bound_violations), "durable_unchanged": self.durable_unchanged,
                "durable_updates": 0, "task_pnm_correspondence": "deferred_maternal_qualification",
                "full_P16_2B": "open_combined_stand_to_follow_and_outcome_qualification"}


# pylint: enable=duplicate-code


def run_follow_mom_v1(case: str = "nominal", *, trace_capacity: int = 256) -> FollowMomExperimentV1:
    """Run one finite eighty-tick trial with no provider truth in cognitive decisions.

    The competing-source pair raises the real visual owner's candidate at
    tick4, with the same score in both runs. Only prior selected-operation source
    influence differs. The fast-cadence case retains physical time and the original
    twenty-opportunity task cap; its earlier budget exhaustion is not concealed.
    No case stops or extends physical time merely to obtain a positive endpoint.
    """
    trial = create_follow_mom_trial_v1(case, trace_capacity=trace_capacity)
    before = _durable(trial)
    # The same passive collection pattern is retained for cross-profile comparisons.
    # pylint: disable=duplicate-code
    cycles: list[IntegratedRightingCycleV1] = []
    local: list[SensorimotorStepV1] = []
    physical: list[PlanarWorldStateV1] = []
    peaks: dict[str, int] = {}

    def observe() -> None:
        """Read live owner bounds after actual work, independent of renderer retention."""
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    # pylint: enable=duplicate-code

    def focal() -> None:
        """Schedule admissible inputs, never choose the resulting source or primitive."""
        tick = trial.tick
        enabled = not (case == "brief_gap" and tick == 12 or case == "prolonged_gap" and 12 <= tick <= 28)
        priority = (10, 60) if case in {"competing_on", "competing_off"} and tick == 4 else None
        cycles.append(trial.focal_step(visual_input_enabled=enabled, visual_bid_priority=priority))
        observe()

    stride = 1 if case == "fast_cadence" else 4
    for tick in range(80):
        if tick % stride == 0:
            focal()
        if case == "cancelled" and tick == 10:
            trial.cancel()
        local.append(trial.advance_lower())
        body = trial.observer_planar_body
        if body is None:
            raise RuntimeError("maternal trial lost its physical planar body")
        physical.append(body)
        observe()
    focal()
    return FollowMomExperimentV1(case, tuple(cycles), tuple(local), tuple(physical), trial.latest_feedback,
                                 tuple(sorted(peaks.items())), before, _durable(trial))


@dataclass(frozen=True, slots=True)
class MaternalSourceReplayV1:
    """Labelled nonphysical source/applicability evidence, not an executed task."""

    case: str
    sources: tuple[MaternalNavMapStateV1, ...]
    dispositions: tuple[str, ...]

    def as_dict(self) -> dict[str, object]:
        """No replay frame counts as motor, completion, maternal acquisition or learning."""
        return {"case": self.case, "scope": "supplied_source_replay_no_physics_no_selected_application",
                "sources": [source.as_dict() for source in self.sources], "dispositions": list(self.dispositions),
                "physical_steps": 0, "selected_applications": 0, "durable_updates": 0}


def run_maternal_source_replay_v1(case: str) -> MaternalSourceReplayV1:
    """Exercise distinct motion and contradictory evidence without new world features.

    Returning-target motion is supplied here, not implemented physical Mom motion.
    Source labels describe measured kinematics, not proof of who caused movement.
    The ordinary owner and IP preparation functions are called, but Navigation
    never selects an application and no executor or physical provider is created.
    """
    if not isinstance(case, str) or case not in MATERNAL_REPLAY_CASES_V1:
        raise ValueError("unknown maternal source replay")
    stream = MotorStreamRefV1("maternal_source_replay", 1)
    visual = VisualSourceV1(stream)
    profile = FollowMomProfileV1()
    maternal = MaternalSourceV1(stream, profile.seed)
    operation = FollowMomIPV1(maternal, profile)
    sources: list[MaternalNavMapStateV1] = []
    reasons: list[str] = []
    for cycle, tick in ((1, 0), (2, 4)):
        target = NavPointV1(2.0, 1.0)
        position = NavPointV1(0.0, 0.0)
        descriptor = "object"
        if cycle == 2:
            if case == "independent_approach":
                target = NavPointV1(1.8, 0.9)
            elif case == "own_closing":
                position = NavPointV1(0.2, 0.1)
            elif case == "contradiction":
                descriptor = "hazard"
            elif case == "relocated_target":
                target = NavPointV1(2.0, -1.0)
        observation = VisualObservationV1(stream, cycle, tick, tick, "scene_xy:lab", position,
                                          (VisualDetectionV1("region_1", descriptor, target),))
        current = maternal.update(visual.update(observation, cycle_id=cycle, cutoff_tick=tick))
        feedback = MotorFeedbackV1(stream, cycle, tick, tick, 0.0, 1.0, True, 1.0, 0.0)
        operation.prepare(current, feedback)
        sources.append(current)
        reasons.append(operation.reason)
    return MaternalSourceReplayV1(case, tuple(sources), tuple(reasons))


def render_follow_mom_v1(result: FollowMomExperimentV1, *, detail: bool = False) -> str:
    """Read completed evidence only; interpretation here has no cognitive authority."""
    if not isinstance(result, FollowMomExperimentV1) or not isinstance(detail, bool):
        raise TypeError("expected a completed Follow-Mom result and Boolean detail")
    last = result.cycles[-1]
    task = last.maternal_task
    lines = [f"P16-2B-A MATERNAL APPROACH | {result.case}",
             "  Initial supported standing; seeded MOM association, selected developmental Follow-Mom IP; no learned identity.",
             f"  physical ticks={len(result.local_steps)}; elapsed={len(result.local_steps)*0.05:.2f}s; focal opportunities={len(result.cycles)}",
             f"  final task={None if task is None or task.task is None else task.task.as_dict()}",
             f"  final source={None if last.maternal_source is None else last.maternal_source.identity_status}; "
             f"separation={None if last.maternal_source is None else last.maternal_source.separation}",
             f"  final actual body={result.physical_samples[-1].as_dict()}",
             f"  supported proximity proof={None if task is None else task.as_dict()['supported_samples']}"]
    for cycle in result.cycles:
        source, assessment = cycle.maternal_source, cycle.maternal_task
        if source is None or assessment is None:
            raise ValueError("maternal experiment record lacks its actual source/task disposition")
        lines.append(f"  focal {cycle.calculation.cutoff_tick}: {cycle.calculation.attention.disposition.value} "
                     f"{cycle.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id if cycle.calculation.navigation.wnm else None}; "
                     f"IP={cycle.commitment.selected_primitive_id}; {assessment.reason}; "
                     f"identity={source.identity_status}; separation={source.separation}; targets={len(cycle.reservations)}")
        if detail:
            lines.append(f"    source sample/event={source.sample_id}/{source.event_tick}; "
                         f"last support={source.last_supported_tick}; uncertainty radius={source.uncertainty_radius}; "
                         f"separation/self/target closing rates={(source.separation_rate, source.self_closing_rate, source.target_closing_rate)}")
            motor = cycle.receipt.dispatch.motor
            if motor is not None and motor.projection is not None:
                lines.append(f"    original PNM={motor.projection.as_dict()}")
            for reservation in cycle.reservations:
                target = reservation.current.target
                lines.append(f"    BodyMap {target.kind.value}: offset={target.offset}; endpoint={target.endpoint}; "
                             f"lease=[{reservation.current.committed_tick},{reservation.current.expires_at_tick})")
    if detail:
        for step, body in zip(result.local_steps, result.physical_samples):
            drive = None if step.command is None or step.command.translation is None else step.command.translation.as_dict()
            lines.append(f"  lower {step.tick}: drive={drive}; actual={body.position}; "
                         f"reports={[(item.disposition.value, item.reason) for item in step.reports]}")
    lines.extend((f"  bounds={list(result.bound_violations)}; durable unchanged={result.durable_unchanged}; learned updates=0",
                  "  Current-proximity completion is not causal credit or a task-PNM verdict.",
                  "  Full P16-2B remains open: combined stand-to-follow and maternal outcome qualification are not claimed here."))
    return "\n".join(lines)


def render_maternal_replay_v1(result: MaternalSourceReplayV1) -> str:
    """Show supplied source evidence as a replay, never as measured physical Mom motion."""
    if not isinstance(result, MaternalSourceReplayV1):
        raise TypeError("expected a maternal source replay")
    lines = [f"MATERNAL SOURCE REPLAY | {result.case} | NO PHYSICS / NO SELECTED APPLICATION"]
    for source, reason in zip(result.sources, result.dispositions):
        lines.append(f"  tick={source.cutoff_tick}; identity={source.identity_status}; separation={source.separation}; "
                     f"self_closing={source.self_closing_rate}; target_closing={source.target_closing_rate}; disposition={reason}")
    return "\n".join(lines)


def run_follow_mom_menu_v1() -> None:
    """Reuse the same experiments from the normal NCA8 menu without touching A0."""
    groups = {"1": FOLLOW_MOM_CASES_V1, "2": ("nominal", "heading_90", "different_target", "already_near"),
              "3": ("association_off", "wrong_seed", "recognition_off", "spatial_off", "following_off"),
              "4": ("brief_gap", "prolonged_gap", "support_interruption"),
              "5": ("competing_on", "competing_off"),
              "6": ("mapping_reversed", "narrowed", "obstacle_contact", "motor_blocked", "feedback_missing", "cancelled"),
              "7": ("fast_cadence", "far_target", "assisted", "assisted_no_task"), "9": ("nominal",)}
    while True:
        print("\nP16-2B-A -- MOM SOURCE / PERSISTENT FOLLOW-MOM\n"
              "  1) All live profiles\n  2) Nominal, heading, target direction and already near\n"
              "  3) Association, recognition, geometry and IP controls\n  4) Brief/prolonged gaps and support interruption\n"
              "  5) Selected source influence / competing source\n  6) Mapping, capability, contact and faults\n"
              "  7) Cadence, finite task and external assistance\n  8) Source-only motion/contradiction replays\n"
              "  9) Detailed nominal live timeline\n  [Enter] Return to NCA8 menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "8":
            for case in MATERNAL_REPLAY_CASES_V1:
                print(render_maternal_replay_v1(run_maternal_source_replay_v1(case)))
        elif choice in groups:
            for case in groups[choice]:
                print(render_follow_mom_v1(run_follow_mom_v1(case), detail=choice == "9"))
        else:
            print("Choose 1-9 or press Enter to return.")
