#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-B: supplied oral-target/contact experiments in the existing lower path.

This external fixture builds actual visual/maternal/feeding source products from
admitted sensing, supplies one relation requirement, and lets BodyMap calculate
a finite oral target. It reuses the H4 trial's advance/admission/fault/reset
boundary and the existing scalar executor. No second motor loop is implemented.

There are no Navigation calls, SeekNipple IP, task PNM, latch, milk, rest or
learning. A source update labelled cycle 1 is a fixture opportunity, not an A-F
cognitive cycle. The earlier P16-2C-A experiment separately qualifies focal
access. This slice proves lower capability before task-level integration.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1,
    OralWorldStateV1, OralWorldProfileV1, OralWorldPerturbationV1,
    PlanarDetailObjectV1, PlanarObjectV1, PlanarPerturbationV1, PlanarWorldProfileV1,
)
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import BodyTargetProposalV1, BodyTargetReservationV1, OralReachRequestV1, oral_body_capability_v1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailProfileV1, FeedingDetailSourceV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_sensorimotor import LocalControlEventV1, SensorimotorExecutorV1, SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, LocalTargetReportV1, SensorimotorTargetKindV1, TargetOriginV1
from nca8_sensorimotor_demo import SensorimotorTrialV1
from nca8_visual import VisualSourceV1

__version__ = "0.1.0"
__all__ = [
    "ORAL_CONTACT_CASES_V1", "OralContactTrialV1", "OralContactExperimentV1",
    "run_oral_contact_v1", "render_oral_contact_v1", "run_oral_contact_menu_v1", "__version__",
]

ORAL_CONTACT_CASES_V1 = (
    "nominal", "geometry_only", "source_off", "missing_detail", "wrong_category", "no_capability", "blocked_motor",
    "no_surface", "missing_contact", "heading_90", "rotated_scene", "out_of_reach", "intermediate_target", "early_contact",
    "disturbed", "prediction_off", "open_loop", "dropout", "delayed", "support_loss", "body_shift", "body_turn", "cancelled", "short_lease",
)
_ORAL = SensorimotorTargetKindV1.ORAL_REACH
_TICKS = 12


@dataclass(frozen=True, slots=True)
class _Case:
    """Private external controls; never handed to the mapper or local executor."""

    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    oral: OralWorldProfileV1
    source_enabled: bool = True
    capability_enabled: bool = True
    install: bool = True
    prediction_protection: bool = True
    lease_ticks: int = 8
    cancel_tick: int | None = None


def _case_settings(case: str) -> _Case:
    """Choose fixed geometry/forcing before execution, never from a task outcome."""
    if not isinstance(case, str) or case not in ORAL_CONTACT_CASES_V1:
        raise ValueError("unknown oral contact foundation case")
    detail = (0.36, 0.0) if case == "out_of_reach" else (0.30, 0.0) if case == "intermediate_target" else (0.10, 0.0)
    parent = (0.20, 0.0)
    heading = 90.0 if case in {"heading_90", "rotated_scene"} else 0.0
    if case == "rotated_scene":
        parent, detail = (0.0, 0.20), (0.0, 0.10)
    objects: tuple[PlanarObjectV1, ...] = (PlanarObjectV1("region_1", parent),)
    if case != "missing_detail":
        objects += (PlanarDetailObjectV1("region_2", detail, descriptor="landmark" if case == "wrong_category" else "feeding"),)
    planar = PlanarWorldProfileV1(frame_id="scene_xy:oral_fixture", objects=objects, initial_heading=heading)
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    surface_position = (0.05, 0.0) if case == "early_contact" else detail
    oral = OralWorldProfileV1(surfaces=() if case == "no_surface" else (PlanarObjectV1("touch_surface", surface_position, 0.004),),
                             motor_enabled=case != "blocked_motor", contact_available=case != "missing_contact")
    if case in {"disturbed", "prediction_off", "open_loop"}:
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(1, 2, -0.4),))
    if case == "dropout":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, _TICKS, drop_feedback=True),))
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, _TICKS, remove_support=True),))
    if case in {"body_shift", "body_turn"}:
        planar = replace(planar, perturbations=(PlanarPerturbationV1(
            1, 2, velocity=(0.2, 0.0) if case == "body_shift" else (0.0, 0.0), heading_rate=90.0 if case == "body_turn" else 0.0,
        ),))
    return _Case(physical, planar, oral, case != "source_off", case != "no_capability", case != "geometry_only",
                 case not in {"prediction_off", "open_loop"}, 2 if case == "short_lease" else 8, 1 if case == "cancelled" else None)


class OralContactTrialV1(SensorimotorTrialV1):
    """Reuse the H4 external runner with only a different source/target fixture.

    Inherited advance(), advance_open_loop(), _admit() and reset() retain the
    tested single-step, consumed-command, stop-on-fault and new-generation
    rules. The override builds a feeding relation rather than a support request.
    It is not a second cognitive runtime and never selects the next task.
    """

    def __init__(self, case: str = "nominal", *, trace_capacity: int = 256) -> None:
        self.case = case
        self._settings = _case_settings(case)
        self.source: FeedingDetailNavMapStateV1
        self.visual: VisualSourceV1
        self.maternal: MaternalSourceV1
        self.feeding: FeedingDetailSourceV1
        super().__init__(self._settings.physical,
                         capabilities=(oral_body_capability_v1(),) if self._settings.capability_enabled else (),
                         control_profile=SensorimotorProfileV1(self._settings.prediction_protection, trace_capacity),
                         planar_profile=self._settings.planar, oral_profile=self._settings.oral, stream_id="oral_fixture_body")

    def _initialize(self, feedback: MotorFeedbackV1) -> None:
        """Create fresh owners and one fixture proposal; no old rights survive reset."""
        self.body = Nca8BodyRuntimeV1()
        mapper = self.body.configure_motor_targets(feedback.stream, self._capabilities, tick_seconds=self.world.profile.dt_seconds)
        mapper.update_feedback(feedback, at_tick=0)
        self.visual = VisualSourceV1(feedback.stream)
        self.maternal = MaternalSourceV1(feedback.stream, MaternalSeedV1())
        self.feeding = FeedingDetailSourceV1(feedback.stream, FeedingDetailProfileV1(source_enabled=self._settings.source_enabled))
        observation = admit_motor_visual_surface_v1(self.world.visual_surface(), feedback)
        self.source = self.feeding.update(self.maternal.update(self.visual.update(observation, cycle_id=1, cutoff_tick=0)))
        origin = TargetOriginV1(feedback.stream, "task:oral_fixture", "application:oral_fixture", "envelope:oral_fixture")
        request = OralReachRequestV1(origin, self.source.source_map_ref, self.source.seed.detail_region_id, self._settings.lease_ticks)
        self.proposal = mapper.propose_oral_reach(request, self.source, at_tick=0)
        self.targets = (mapper.reserve(self.proposal, execution_id="execution:oral_fixture", at_tick=0)
                        if self.proposal.bindings and self._settings.install else ())
        self.controller = SensorimotorExecutorV1(mapper, profile=self._control_profile)
        if self.targets:
            self.controller.install(self.targets, at_tick=0)
        self._latest_feedback = feedback
        self._stopped = False

    def source_signature(self) -> str:
        """Read the one retained configuration; later touch is not a visual rewrite."""
        return json.dumps(self.source.as_dict(), sort_keys=True, allow_nan=False)

    def durable_signature(self) -> str:
        """Read actual owner-held maps, not a constant zero-learning assertion."""
        maps = (self.visual.durable_map, self.maternal.durable_map, self.feeding.durable_map)
        return json.dumps([navmap.as_dict() for navmap in maps], sort_keys=True, allow_nan=False)

    def retained_counts(self) -> dict[str, int]:
        """Measure live owner buffers independently of exported experiment storage."""
        mapper = self.body.motor_targets
        if mapper is None:
            raise RuntimeError("oral trial lacks its configured BodyMap")
        counts = {**mapper.retained_counts(), **self.controller.retained_counts(), "provider_pending": self.world.pending_feedback_count}
        for name, owner_counts in (("visual", self.visual.retained_counts()), ("maternal", self.maternal.retained_counts()),
                                   ("feeding", self.feeding.retained_counts())):
            counts.update((f"{name}_{key}", value) for key, value in owner_counts.items())
        return counts

    @property
    def settings(self) -> _Case:
        """Expose immutable original fixture settings to the external observer only."""
        return self._settings

    @property
    def cancel_tick(self) -> int | None:
        """Expose a fixed-time external cancellation control, not task policy."""
        return self._settings.cancel_tick


@dataclass(frozen=True, slots=True)
class OralContactExperimentV1:
    """Completed observer evidence with original source, target and sensor times.

    Physical samples are evaluator-only. Sensor rows may reread the same event
    during delay; metrics identify its original occurrence rather than counting
    duplicate confirmations. Nothing here restores action permissions or learning.
    """

    case: str
    proposal: BodyTargetProposalV1
    targets: tuple[BodyTargetReservationV1, ...]
    steps: tuple[SensorimotorStepV1, ...]
    sensed: tuple[MotorFeedbackV1, ...]
    physical: tuple[OralWorldStateV1, ...]
    reports: tuple[LocalTargetReportV1, ...]
    events: tuple[LocalControlEventV1, ...]
    installations: int
    trace_capacity: int
    peak_counts: tuple[tuple[str, int], ...]
    source_before: str
    source_after: str
    durable_before: str
    durable_after: str
    elapsed_ticks: int
    settings: _Case

    @property
    def open_loop(self) -> bool:
        """Distinguish explicit nominal-command replay from feedback control."""
        return self.case == "open_loop"

    @property
    def commands(self) -> tuple[MotorCommandV1 | None, ...]:
        """Return the recorded issued schedule without re-running an experiment."""
        return tuple(step.command for step in self.steps)

    def metrics(self) -> dict[str, object]:
        """Separate physical touch, admitted touch and coordinate achievement."""
        contacts = tuple(item for item in self.sensed if item.oral is not None and item.oral.contact is True)
        first = contacts[0] if contacts else None
        achieved = tuple(report for report in self.reports if report.disposition is LocalTargetDispositionV1.ACHIEVED)
        return {"physical_ticks": self.elapsed_ticks, "elapsed_seconds": self.elapsed_ticks * 0.05,
                "focal_calls": 0, "source_update_fixture_opportunities": 1, "target_installations": self.installations,
                "first_physical_touch_tick": next((tick for tick, item in enumerate(self.physical) if item.contact), None),
                "first_sensed_touch_event": None if first is None else first.event_tick,
                "first_touch_available_tick": None if first is None else first.available_tick,
                "observed_local_coordinate_achieved": bool(achieved),
                "local_achievement_reported_tick": achieved[0].reported_tick if achieved else None,
                "final_measured_reach": self.sensed[-1].oral.extension_metres if self.sensed and self.sensed[-1].oral is not None else None,
                "final_measured_touch": self.sensed[-1].oral.contact if self.sensed and self.sensed[-1].oral is not None else None,
                "nonneutral_commands": sum(command is not None and not command.is_neutral for command in self.commands)}

    def _case_expectation(self) -> bool:
        """Check the predeclared case effect, including truthful negative outcomes."""
        metrics = self.metrics()
        achieved = metrics["observed_local_coordinate_achieved"]
        contact = metrics["first_sensed_touch_event"] is not None
        final_contact = metrics["final_measured_touch"]
        no_motion = all(command is None for command in self.commands)
        if self.case in {"nominal", "rotated_scene", "disturbed", "prediction_off"}:
            return achieved is True and final_contact is True
        if self.case in {"no_surface", "intermediate_target", "short_lease"}:
            return achieved is True and not contact
        if self.case in {"source_off", "missing_detail", "wrong_category", "no_capability", "missing_contact", "heading_90", "out_of_reach"}:
            return bool(self.proposal.withheld) and self.installations == 0 and no_motion
        if self.case == "geometry_only":
            return bool(self.proposal.bindings) and self.installations == 0 and no_motion and not contact
        if self.case == "blocked_motor":
            return any(command is not None and not command.is_neutral for command in self.commands) and (
                metrics["final_measured_reach"] == 0.0 and not contact and not achieved)
        if self.case == "open_loop":
            final = self.sensed[-1].oral if self.sensed else None
            return (not self.reports and not self.events and not contact and final is not None
                    and final.extension_metres is not None and abs(final.extension_metres - 0.08) < 1e-10)
        if self.case == "early_contact":
            return contact and not achieved and any(item.reason == "oral_contact_before_target" for item in self.reports)
        if self.case in {"dropout", "delayed"}:
            return not achieved and not contact and any(item.reason == "current_feedback_timeout" for item in self.reports)
        if self.case in {"body_shift", "body_turn"}:
            return not achieved and any(item.reason == "oral_body_anchor_changed" for item in self.reports)
        if self.case == "support_loss":
            return not achieved and any(item.reason in {"oral_support_unavailable", "unexpected_contact_loss"} for item in self.reports)
        if self.case == "cancelled":
            return not achieved and any(item.disposition is LocalTargetDispositionV1.CANCELLED for item in self.reports)
        return False

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Qualify complete evidence, never treat absence or an empty run as PASS."""
        limits = {"body_sensor_records": 1, "body_pending_proposals": 1, "body_reserved_records": 1,
                  "lower_pursuits": 1, "lower_command_history": 4, "lower_events": 4, "lower_trace": self.trace_capacity,
                  "lower_predictions_per_axis": 4, "lower_replaced_reports": 2, "provider_pending": 16,
                  "visual_durable_maps": 1, "visual_acquisitions": 1, "visual_current_configurations": 1,
                  "visual_retained_detections": 8, "visual_recognition_contributions": 8, "visual_guidance_contributions": 8,
                  "maternal_durable_maps": 1, "maternal_current_configurations": 1, "maternal_supported_bases": 1,
                  "maternal_influence_requests": 1, "feeding_durable_maps": 1, "feeding_current_configurations": 1}
        counts = dict(self.peak_counts)
        bounds = (len(counts) == len(self.peak_counts) and set(counts) == set(limits)
                  and all(isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= limits[key] for key, value in counts.items()))
        complete = (self.elapsed_ticks == _TICKS and len(self.steps) == _TICKS and len(self.sensed) == len(self.physical) == _TICKS + 1
                    and self.settings == _case_settings(self.case))
        timely = (all(item.available_tick <= tick for tick, item in enumerate(self.sensed))
                  and all(step.feedback is None or step.feedback.available_tick <= step.tick for step in self.steps)
                  and all(prediction.issued_tick == step.tick and prediction.event_tick > step.tick
                          for step in self.steps for prediction in step.predictions))
        bounded_commands = all(command is None or (
            command.issued_tick == tick and command.orientation_drive == command.extension_drive == 0.0 and command.translation is None
            and command.oral_drive is not None and abs(command.oral_drive) <= 1.0 and bool(self.targets)
            and tick < self.targets[0].current.expires_at_tick) for tick, command in enumerate(self.commands))
        original_targets = (self.proposal.oral_preview is not None
                            and all(item.initial.target.kind is _ORAL and item.current == item.initial for item in self.targets))
        return (("complete_fixed_physical_horizon", complete), ("consecutive_local_intervals", tuple(s.tick for s in self.steps) == tuple(range(_TICKS))),
                ("original_source_and_target_meaning", original_targets and bool(self.source_before) and self.source_before == self.source_after),
                ("observed_evidence_never_from_future", timely), ("commands_within_original_oral_lease", bounded_commands),
                ("one_explicit_fixture_installation", self.installations == len(self.targets) and self.installations in (0, 1)),
                ("measured_owner_storage_bounded", bounds), ("durable_maps_unchanged", bool(self.durable_before) and self.durable_before == self.durable_after),
                ("predeclared_positive_or_adverse_effect", complete and self._case_expectation()))

    @property
    def review_status(self) -> str:
        """Require every structural and case-specific check, including full evidence."""
        return "PASS" if all(passed for _name, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export detached evidence only; no task, save/load or actuator restoration."""
        return {"schema": "oral_contact_experiment_v1", "case": self.case, "review_status": self.review_status,
                "supplied_fixture_profile": asdict(self.settings),
                "metrics": self.metrics(), "checks": [{"name": name, "passed": passed} for name, passed in self.checks()],
                "proposal": self.proposal.as_dict(), "targets": [item.as_dict() for item in self.targets],
                "steps": [item.as_dict() for item in self.steps], "sensed": [item.as_dict() for item in self.sensed],
                "external_physical": [item.as_dict() for item in self.physical], "reports": [item.as_dict() for item in self.reports],
                "events": [item.as_dict() for item in self.events], "peak_counts": dict(self.peak_counts),
                "trace_capacity": self.trace_capacity, "source_before": self.source_before, "source_after": self.source_after,
                "durable_before": self.durable_before, "durable_after": self.durable_after,
                "oral_residual_limit_metres": 0.01, "open_loop": self.open_loop,
                "task_selection": "not_implemented_supplied_requirement_fixture", "task_pnm": "not_supplied",
                "feeding_learning": "unimplemented_no_participation", "latch": "not_modeled", "milk": "not_modeled",
                "rest": "not_implemented", "B99": "open", "restores_motor_permission": False}


def run_oral_contact_v1(case: str = "nominal", *, trace_capacity: int = 256) -> OralContactExperimentV1:
    """Execute one fixed-horizon trial using the shared H4 boundary, never a task list.

    The open-loop comparator uses the nominal issued schedule in a fresh disturbed
    world. Its current sensors remain observer-only; no fabricated fresh feedback
    bypasses the normal missing-input rule. Fixed-time cancellation is a labelled
    intervention. Neither control changes an unprovided task or extends its lease.
    """
    _case_settings(case)
    reference = run_oral_contact_v1("nominal", trace_capacity=trace_capacity).commands if case == "open_loop" else ()
    trial = OralContactTrialV1(case, trace_capacity=trace_capacity)
    source_before, durable_before = trial.source_signature(), trial.durable_signature()
    peaks: dict[str, int] = {}
    physical: list[OralWorldStateV1] = []
    sensed: list[MotorFeedbackV1] = []
    steps: list[SensorimotorStepV1] = []

    def observe() -> None:
        """Record external evidence after an interval without influencing control."""
        state = trial.world.oral_body
        if state is None:
            raise RuntimeError("oral trial provider omitted its physical facet")
        physical.append(state)
        sensed.append(trial.latest_feedback)
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    observe()
    for tick in range(_TICKS):
        if trial.cancel_tick == tick:
            trial.controller.cancel_execution(at_tick=tick)
        steps.append(trial.advance_open_loop(reference[tick]) if case == "open_loop" else trial.advance())
        observe()
    return OralContactExperimentV1(case, trial.proposal, trial.targets, tuple(steps), tuple(sensed), tuple(physical),
                                   () if case == "open_loop" else trial.controller.reports,
                                   () if case == "open_loop" else trial.controller.events,
                                   trial.controller.installation_count, trace_capacity, tuple(sorted(peaks.items())),
                                   source_before, trial.source_signature(), durable_before, trial.durable_signature(), trial.world.tick, trial.settings)


def render_oral_contact_v1(result: OralContactExperimentV1, *, detail: bool = False) -> str:
    """Render existing records only, with physical and delivered touch kept distinct."""
    if not isinstance(result, OralContactExperimentV1) or not isinstance(detail, bool):
        raise TypeError("oral rendering needs a typed result and Boolean detail flag")
    metrics = result.metrics()
    lines = [f"P16-2C-B / {result.case} / ORAL FOUNDATION REVIEW: {result.review_status}",
             "Supplied relation fixture -> BodyMap -> existing target executor -> actual reach -> sensed touch.",
             "One body-forward axis, no head turn. No Navigation/SeekNipple/task PNM/latch/milk/rest/learning.",
             f"  Physical ticks={result.elapsed_ticks}; dt=0.05s; focal calls=0; installations={result.installations}; open-loop={result.open_loop}.",
             f"  Physical touch first={metrics['first_physical_touch_tick']}; sensed event={metrics['first_sensed_touch_event']}; "
             f"available={metrics['first_touch_available_tick']}.",
             f"  Coordinate achieved={metrics['observed_local_coordinate_achieved']}; "
             f"final measured reach={metrics['final_measured_reach']} m; final measured touch={metrics['final_measured_touch']}."]
    if result.proposal.oral_preview is not None:
        preview = result.proposal.oral_preview
        lines.append(f"  BodyMap: {preview.status}; forward={preview.forward_metres} m; lateral={preview.left_metres} m.")
    for report in result.reports:
        lines.append(f"  Local result: {report.disposition.value}; {report.reason}; reported at {report.reported_tick}.")
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        lines.append("  tick | sensed event/available | observed reach/touch | issued oral drive | local disposition")
        for step in result.steps:
            sensed = step.feedback
            evidence = "missing" if sensed is None else f"{sensed.event_tick}/{sensed.available_tick}"
            oral = None if sensed is None else sensed.oral
            drive = step.command.oral_drive if step.command is not None else 0.0
            lines.append(f"  {step.tick:4d} | {evidence:>22} | {str(oral):48} | {drive!s:>10} | "
                         + "; ".join(report.reason for report in step.reports))
        for event in result.events:
            lines.append(f"  Local event: {event.reason}; occurred={event.event_tick}; noticed={event.noticed_tick}; residual={event.residual}.")
    lines.append("Coordinate attainment is not contact; contact is not latch or nourishment. B99 remains open.")
    return "\n".join(lines)


def run_oral_contact_menu_v1() -> None:
    """Review isolated trials; the retained detail option never runs the body again."""
    latest: tuple[OralContactExperimentV1, ...] = ()
    selections = {"1": ("nominal",), "2": ("no_surface", "missing_contact", "early_contact"),
                  "3": ("heading_90", "rotated_scene", "out_of_reach", "intermediate_target", "short_lease"),
                  "4": ("geometry_only", "source_off", "missing_detail", "wrong_category", "no_capability", "blocked_motor"),
                  "5": ("disturbed", "prediction_off", "open_loop"),
                  "6": ("dropout", "delayed", "support_loss", "body_shift", "body_turn", "cancelled"), "7": ORAL_CONTACT_CASES_V1}
    while True:
        print("\nP16-2C-B -- ORAL TARGET / CONTACT FOUNDATION (supplied requirement, no feeding task)")
        print("  1) Nominal actual reach and sensed touch")
        print("  2) Coordinate versus contact; missing versus absent touch")
        print("  3) Heading, reachability, intermediate target and short lease")
        print("  4) Geometry-only, missing source/capability, and blocked motor")
        print("  5) Disturbed feedback / prediction consumer off / open-loop replay")
        print("  6) Feedback gaps/delay, support/body changes, and cancellation")
        print("  7) All cases (compact)")
        print("  8) Inspect last results (detailed; no new movement)")
        print("  [Enter] Return to feeding review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "8":
            if not latest:
                print("No oral results retained. Select an experiment first.")
            for result in latest:
                print(render_oral_contact_v1(result, detail=True))
        elif choice in selections:
            latest = tuple(run_oral_contact_v1(case) for case in selections[choice])
            for result in latest:
                print(render_oral_contact_v1(result))
        else:
            print("Choose 1-8, or press Enter to return.")
