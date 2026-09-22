#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-G supplied closure, actual seal and independently admitted evidence.

This external fixture reuses the H4 advance/admission/reset boundary and scalar
executor. A supported start already places the mouth at a visual detail; that
initial condition is not a result of Navigation-selected seeking in this trial.
The fixture supplies one closure/opening requirement. No Suckle IP, task PNM,
feeding milestone, milk, nourishment, rest or durable learning is implemented.

Every source refresh consumes delivered sensing. The external observer alone
reads physical state. A current compatible seal relation is not independently
sensed nipple identity and is not an earned task-completion or causal verdict.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1,
    OralWorldProfileV1, OralWorldStateV1, OralWorldPerturbationV1,
    OralSealWorldProfileV1, OralSealWorldStateV1, OralClosurePerturbationV1,
    PlanarObjectV1, PlanarDetailObjectV1, PlanarWorldProfileV1, PlanarPerturbationV1,
)
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import BodyTargetProposalV1, OralClosureRequestV1, oral_closure_capability_v1
from nca8_feeding import FeedingDetailNavMapStateV1, FeedingDetailProfileV1, FeedingDetailSourceV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetReportV1, LocalTargetDispositionV1, TargetOriginV1
from nca8_sensorimotor_demo import SensorimotorTrialV1
from nca8_visual import VisualSourceV1

__version__ = "0.1.0"
__all__ = [
    "ORAL_SEAL_CASES_V1", "OralSealTrialV1", "OralSealExperimentV1", "OralSealPhysicalSampleV1",
    "run_oral_seal_v1", "render_oral_seal_v1", "run_oral_seal_menu_v1", "__version__",
]

ORAL_SEAL_CASES_V1 = (
    "nominal", "preview_only", "nonsealable", "no_touch", "touch_elsewhere", "missing_detail", "wrong_category",
    "source_off", "no_capability", "blocked_motor", "missing_contact", "missing_closure", "missing_seal",
    "partial_closure", "release", "release_without_vision", "release_without_touch", "rotated_scene",
    "disturbed", "prediction_off", "open_loop", "dropout", "delayed", "support_loss", "body_shift", "reach_shift",
    "contact_loss_after", "cancelled", "short_lease",
)
_TICKS = 12


@dataclass(frozen=True, slots=True)
class _Case:
    """Fixed external controls, never passed to the mapper or executor as policy."""

    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    oral: OralWorldProfileV1
    seal: OralSealWorldProfileV1
    desired_closure: float = 0.6
    source_enabled: bool = True
    capability_enabled: bool = True
    install: bool = True
    prediction_protection: bool = True
    lease_ticks: int = 8
    cancel_tick: int | None = None


def _settings(case: str) -> _Case:
    """Select an immutable input/forcing profile before observing any result."""
    if not isinstance(case, str) or case not in ORAL_SEAL_CASES_V1:
        raise ValueError("unknown oral seal fixture case")
    rotated = case == "rotated_scene"
    detail, parent = ((0.0, 0.10), (0.0, 0.20)) if rotated else ((0.10, 0.0), (0.20, 0.0))
    if case == "touch_elsewhere":
        detail = (0.15, 0.0)
    objects: tuple[PlanarObjectV1, ...] = (PlanarObjectV1("region_1", parent),)
    if case != "missing_detail":
        objects += (PlanarDetailObjectV1("region_2", detail, descriptor="landmark" if case == "wrong_category" else "feeding"),)
    planar = PlanarWorldProfileV1(frame_id="scene_xy:oral_seal_fixture", objects=objects,
                                  initial_heading=90.0 if rotated else 0.0, vision_available=case != "release_without_vision")
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    surface = PlanarObjectV1("physical_surface", (0.0, 0.10) if rotated else (0.10, 0.0), 0.004)
    oral = OralWorldProfileV1(initial_extension_metres=0.10,
                             surfaces=() if case in {"no_touch", "release_without_touch"} else (surface,),
                             contact_available=case != "missing_contact")
    releasing = case in {"release", "release_without_vision", "release_without_touch"}
    seal = OralSealWorldProfileV1(initial_closure=0.6 if releasing else 0.0,
                                  sealable_surfaces=() if case == "nonsealable" else (surface,),
                                  motor_enabled=case != "blocked_motor", closure_available=case != "missing_closure",
                                  seal_available=case != "missing_seal")
    if case in {"disturbed", "prediction_off", "open_loop"}:
        seal = replace(seal, perturbations=(OralClosurePerturbationV1(1, 2, -2.0),))
    if case in {"dropout", "support_loss"}:
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(
            1, _TICKS, drop_feedback=case == "dropout", remove_support=case == "support_loss"),))
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case in {"body_shift", "contact_loss_after"}:
        start = 8 if case == "contact_loss_after" else 1
        planar = replace(planar, perturbations=(PlanarPerturbationV1(start, start + 1, velocity=(0.2, 0.0)),))
    if case == "reach_shift":
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(1, 2, 0.2),))
    return _Case(physical, planar, oral, seal, 0.0 if releasing else 0.3 if case == "partial_closure" else 0.6,
                 case != "source_off", case != "no_capability", case != "preview_only",
                 case not in {"prediction_off", "open_loop"}, 2 if case == "short_lease" else 8, 2 if case == "cancelled" else None)


class OralSealTrialV1(SensorimotorTrialV1):
    """Supply one requirement while reusing the existing H4 lower execution loop.

    Fixture source updates have a monotonically numbered review opportunity,
    not a hidden A-F cycle or a second focal task. Reset creates fresh owners in
    the provider's new generation; no old permission or seal report is reused.
    """

    def __init__(self, case: str = "nominal", *, trace_capacity: int = 256) -> None:
        self.case = case
        self.settings = _settings(case)
        self.visual: VisualSourceV1
        self.maternal: MaternalSourceV1
        self.feeding: FeedingDetailSourceV1
        self.source: FeedingDetailNavMapStateV1
        super().__init__(self.settings.physical,
                         capabilities=(oral_closure_capability_v1(),) if self.settings.capability_enabled else (),
                         control_profile=SensorimotorProfileV1(self.settings.prediction_protection, trace_capacity),
                         planar_profile=self.settings.planar, oral_profile=self.settings.oral, oral_seal_profile=self.settings.seal,
                         stream_id="oral_seal_fixture_body")

    def _initialize(self, feedback: MotorFeedbackV1) -> None:
        """Build current sources and propose/reserve a supplied target at reset time."""
        self.body = Nca8BodyRuntimeV1()
        mapper = self.body.configure_motor_targets(feedback.stream, self._capabilities, tick_seconds=self.world.profile.dt_seconds)
        mapper.update_feedback(feedback, at_tick=0)
        self.visual = VisualSourceV1(feedback.stream)
        self.maternal = MaternalSourceV1(feedback.stream, MaternalSeedV1())
        self.feeding = FeedingDetailSourceV1(feedback.stream, FeedingDetailProfileV1(source_enabled=self.settings.source_enabled))
        self._latest_feedback = feedback
        self.refresh_source()
        origin = TargetOriginV1(feedback.stream, "task:closure_fixture", "application:closure_fixture", "envelope:closure_fixture")
        request = OralClosureRequestV1(origin, self.source.source_map_ref, self.source.seed.detail_region_id,
                                      self.settings.desired_closure, self.settings.lease_ticks)
        self.proposal = mapper.propose_oral_closure(request, self.source, at_tick=0)
        self.targets = (mapper.reserve(self.proposal, execution_id="execution:closure_fixture", at_tick=0)
                        if self.proposal.bindings and self.settings.install else ())
        self.controller = SensorimotorExecutorV1(mapper, profile=self._control_profile)
        if self.targets:
            self.controller.install(self.targets, at_tick=0)
        self._stopped = False

    def refresh_source(self) -> FeedingDetailNavMapStateV1:
        """Apply only delivered sensing; reads never substitute private physical state."""
        tick, feedback = self.world.tick, self.latest_feedback
        observation = admit_motor_visual_surface_v1(self.world.visual_surface(feedback=feedback), feedback)
        visual = self.visual.update(observation, cycle_id=tick + 1, cutoff_tick=tick)
        self.source = self.feeding.update(self.maternal.update(visual), oral_feedback=feedback)
        return self.source

    def durable_signature(self) -> str:
        """Measure all three owner-held durable maps rather than assert no learning."""
        return json.dumps([owner.durable_map.as_dict() for owner in (self.visual, self.maternal, self.feeding)],
                          sort_keys=True, allow_nan=False)

    def retained_counts(self) -> dict[str, int]:
        """Inspect live bounded owners independently of exported experiment history."""
        mapper = self.body.motor_targets
        if mapper is None:
            raise RuntimeError("closure trial lacks BodyMap")
        counts = {**mapper.retained_counts(), **self.controller.retained_counts(), "provider_pending": self.world.pending_feedback_count}
        for label, owner in (("visual", self.visual), ("maternal", self.maternal), ("feeding", self.feeding)):
            counts.update((f"{label}_{key}", value) for key, value in owner.retained_counts().items())
        return counts


@dataclass(frozen=True, slots=True)
class OralSealPhysicalSampleV1:
    """An external-only snapshot, never an input to source or lower control."""

    tick: int
    oral: OralWorldStateV1
    seal: OralSealWorldStateV1
    position: tuple[float, float]

    def as_dict(self) -> dict[str, object]:
        """Detach observer evidence with its actual physical event time."""
        return {"tick": self.tick, "oral": self.oral.as_dict(), "seal": self.seal.as_dict(), "position": list(self.position)}


@dataclass(frozen=True, slots=True)
class OralSealExperimentV1:
    """Finite lower-capability evidence, not selected Suckle or a latch task result."""

    case: str
    settings: _Case
    proposal: BodyTargetProposalV1
    steps: tuple[SensorimotorStepV1, ...]
    physical: tuple[OralSealPhysicalSampleV1, ...]
    sources: tuple[FeedingDetailNavMapStateV1, ...]
    reports: tuple[LocalTargetReportV1, ...]
    installation_count: int
    peaks: tuple[tuple[str, int], ...]
    durable_before: str
    durable_after: str

    @property
    def commands(self) -> tuple[MotorCommandV1 | None, ...]:
        """Return actual issued commands; a request or seal report is not a drive."""
        return tuple(step.command for step in self.steps)

    def metrics(self) -> dict[str, object]:
        """Separate coordinate, physical seal, delivery and source correspondence."""
        compatible = next((source for source in self.sources if source.seal_correspondence_status == "compatible"), None)
        sealed = next((item.tick for item in self.physical if item.seal.sealed), None)
        return {"command_count": sum(command is not None for command in self.commands),
                "final_closure": self.physical[-1].seal.closure, "physical_seal_first_tick": sealed,
                "physical_seal_final": self.physical[-1].seal.sealed,
                "compatible_seal_first_cutoff": None if compatible is None else compatible.cutoff_tick,
                "final_correspondence": self.sources[-1].seal_correspondence_status,
                "local_coordinate_achieved": any(report.disposition is LocalTargetDispositionV1.ACHIEVED for report in self.reports),
                "requested_coordinate_met": abs(self.physical[-1].seal.closure - self.settings.desired_closure) <= 0.025 + 1e-12,
                "physical_ticks": len(self.steps), "navigation_selections": 0, "durable_learning_updates": 0,
                "latch_task_implemented": False, "milk_evidence": "not_supplied"}

    def _case_expectation(self) -> bool:
        """Check predeclared distinctions; adverse cases need not attain the target."""
        metrics = self.metrics()
        if self.case in {"nominal", "rotated_scene"}:
            return bool(metrics["local_coordinate_achieved"] and metrics["physical_seal_final"]
                        and metrics["final_correspondence"] == "compatible")
        if self.case == "nonsealable":
            return bool(metrics["local_coordinate_achieved"] and not metrics["physical_seal_final"])
        if self.case == "missing_seal":
            return bool(metrics["local_coordinate_achieved"] and metrics["physical_seal_final"]
                        and metrics["final_correspondence"] == "seal_unknown")
        if self.case in {"release", "release_without_vision", "release_without_touch"}:
            return bool(metrics["local_coordinate_achieved"] and not metrics["physical_seal_final"])
        if self.case == "contact_loss_after":
            return bool(metrics["local_coordinate_achieved"] and metrics["physical_seal_first_tick"] is not None
                        and not metrics["physical_seal_final"] and metrics["final_correspondence"] == "no_seal")
        if self.case in {"preview_only", "no_touch", "touch_elsewhere", "missing_detail", "wrong_category", "source_off",
                         "no_capability", "missing_contact", "missing_closure"}:
            return metrics["command_count"] == 0 and metrics["physical_seal_first_tick"] is None
        if self.case in {"partial_closure", "short_lease", "cancelled", "dropout", "delayed", "support_loss", "body_shift", "reach_shift"}:
            return metrics["physical_seal_first_tick"] is None
        if self.case == "blocked_motor":
            return metrics["command_count"] != 0 and metrics["final_closure"] == 0.0 and not metrics["local_coordinate_achieved"]
        if self.case in {"disturbed", "prediction_off"}:
            return bool(metrics["local_coordinate_achieved"] and metrics["requested_coordinate_met"])
        # This replay can form a seal while missing its supplied closure coordinate.
        return self.case == "open_loop" and not metrics["requested_coordinate_met"] and bool(metrics["physical_seal_final"])

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Test scope, time, authority, sensing and each case's expected distinction."""
        commands = tuple(command for command in self.commands if command is not None)
        feedback = tuple(source.oral_feedback for source in self.sources if source.oral_feedback is not None)
        bindings = self.proposal.bindings
        limit = 8 if not bindings else bindings[0].target.lease_ticks
        return (
            ("declared_case", self.case in ORAL_SEAL_CASES_V1),
            ("finite_physical_time", len(self.steps) == _TICKS and self.physical[-1].tick == _TICKS),
            ("one_physical_step_per_update", tuple(item.tick for item in self.physical) == tuple(range(_TICKS + 1))),
            ("one_installation_at_most", self.installation_count <= 1),
            ("closure_commands_only", all(command.oral_closure_drive is not None and command.oral_drive is None
                                          and command.translation is None and command.orientation_drive == command.extension_drive == 0
                                          for command in commands)),
            ("finite_original_lease", all(command.issued_tick < limit for command in commands)),
            ("bounded_drive", all(abs(command.oral_closure_drive or 0.0) <= 1.0 for command in commands)),
            ("event_available_before_use", all(source.oral_feedback is None or source.oral_feedback.available_tick <= source.cutoff_tick
                                               for source in self.sources)),
            ("seal_does_not_precede_contact_or_closure", all(not item.seal.sealed or item.oral.contact and item.seal.closure >= 0.5 - 1e-12
                                                            for item in self.physical)),
            ("compatible_source_needs_real_sensing", all(source.seal_correspondence_status != "compatible"
                                                       or source.oral_sealed is True and source.contact_correspondence_status == "compatible"
                                                       for source in self.sources)),
            ("canonical_v4_feedback", all(item.as_dict()["schema"] == "body_motor_feedback_v4" for item in feedback)),
            ("no_durable_change", self.durable_before == self.durable_after),
            ("bounded_prediction_history", dict(self.peaks)["lower_predictions_per_axis"] <= 4),
            ("bounded_command_history", dict(self.peaks)["lower_command_history"] <= 4),
            ("single_closure_pursuit", dict(self.peaks)["lower_pursuits"] <= 1),
            ("single_current_source", dict(self.peaks)["feeding_current_configurations"] == 1),
            ("bounded_event_queue", dict(self.peaks)["lower_events"] <= 4),
            ("bounded_provider_queue", dict(self.peaks)["provider_pending"] <= 16),
            ("case_distinction", self._case_expectation()),
        )

    @property
    def review_status(self) -> str:
        """PASS means all declared checks, not full feeding or task competence."""
        return "PASS" if all(value for _, value in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export the full detached experiment; these records cannot restore rights."""
        return {"case": self.case, "profile": asdict(self.settings), "scope": "supplied_closure_not_selected_suckle",
                "proposal": self.proposal.as_dict(), "steps": [step.as_dict() for step in self.steps],
                "physical": [sample.as_dict() for sample in self.physical], "sources": [source.as_dict() for source in self.sources],
                "reports": [report.as_dict() for report in self.reports], "installation_count": self.installation_count,
                "peaks": dict(self.peaks), "durable_before": self.durable_before, "durable_after": self.durable_after,
                "metrics": self.metrics(), "checks": dict(self.checks()), "review_status": self.review_status}


def run_oral_seal_v1(case: str = "nominal", *, trace_capacity: int = 256) -> OralSealExperimentV1:
    """Run one isolated fixture through the inherited lower loop; no hidden tasks.

    The explicit open-loop comparator replays a nominal command schedule into
    the same fixed-disturbance body. Observation remains available to the human
    reviewer but cannot influence those replayed commands. It is not normal
    protected feedback control and is never selected as a runtime fallback.
    """
    trial = OralSealTrialV1(case, trace_capacity=trace_capacity)
    before = trial.durable_signature()
    physical: list[OralSealPhysicalSampleV1] = []
    sources: list[FeedingDetailNavMapStateV1] = []
    steps: list[SensorimotorStepV1] = []
    peaks: dict[str, int] = {}
    reference = run_oral_seal_v1("nominal", trace_capacity=trace_capacity).commands if case == "open_loop" else ()

    def inspect() -> None:
        """Record physical and admitted evidence separately without changing control."""
        oral, seal, planar = trial.world.oral_body, trial.world.oral_seal_body, trial.world.planar_body
        if oral is None or seal is None or planar is None:
            raise RuntimeError("seal fixture lost its declared physical facets")
        physical.append(OralSealPhysicalSampleV1(trial.world.tick, oral, seal, planar.position))
        sources.append(trial.source)
        for name, value in trial.retained_counts().items():
            peaks[name] = max(peaks.get(name, 0), value)

    inspect()
    for tick in range(_TICKS):
        if tick == trial.settings.cancel_tick:
            trial.controller.cancel_execution(at_tick=tick)
        steps.append(trial.advance_open_loop(reference[tick]) if case == "open_loop" else trial.advance())
        trial.refresh_source()
        inspect()
    return OralSealExperimentV1(case, trial.settings, trial.proposal, tuple(steps), tuple(physical), tuple(sources),
                                () if case == "open_loop" else trial.controller.reports, trial.controller.installation_count,
                                tuple(sorted(peaks.items())), before, trial.durable_signature())


def render_oral_seal_v1(result: OralSealExperimentV1, *, detail: bool = False) -> str:
    """Render retained evidence only; detail changes neither sensing nor movement."""
    if not isinstance(result, OralSealExperimentV1) or not isinstance(detail, bool):
        raise TypeError("seal rendering requires a typed result and Boolean detail flag")
    lines = [f"P16-2C-G / {result.case} / ORAL CLOSURE AND SEAL REVIEW: {result.review_status}",
             "Supplied target; no Navigation-selected Suckle, milk, nourishment or Rest.",
             "Coordinate achievement != physical seal != current feeding-contact correspondence != latch task completion.",
             json.dumps(result.metrics(), sort_keys=True, allow_nan=False),
             f"CHECKS: {sum(passed for _, passed in result.checks())}/{len(result.checks())}"]
    if detail:
        lines.extend(f"{name}: {'PASS' if passed else 'FAIL'}" for name, passed in result.checks())
        lines.append(json.dumps(result.as_dict(), sort_keys=True, indent=2, allow_nan=False))
    return "\n".join(lines)


def run_oral_seal_menu_v1() -> None:
    """Review fresh isolated trials or inspect retained detail without another run."""
    latest: tuple[OralSealExperimentV1, ...] = ()
    choices = {"1": ("nominal", "nonsealable", "missing_seal", "partial_closure"),
               "2": ("release", "release_without_vision", "release_without_touch", "contact_loss_after"),
               "3": ("disturbed", "prediction_off", "open_loop"), "4": ORAL_SEAL_CASES_V1}
    while True:
        print("\nP16-2C-G -- SUPPLIED ORAL CLOSURE / SEAL FOUNDATION")
        print("  1) Closure, touch, seal and missing seal evidence")
        print("  2) Explicit opening, missing vision/touch, and later seal loss")
        print("  3) Fixed disturbance: prediction/reactive/open-loop controls")
        print("  4) All cases (compact)")
        print("  5) Inspect retained detail (no new movement)")
        print("  [Enter] Return to feeding review")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "5":
            if not latest:
                print("No results retained. Run an experiment first.")
            for result in latest:
                print(render_oral_seal_v1(result, detail=True))
        elif choice in choices:
            latest = tuple(run_oral_seal_v1(case) for case in choices[choice])
            for result in latest:
                print(render_oral_seal_v1(result))
        else:
            print("Choose 1-5, or press Enter to return.")
