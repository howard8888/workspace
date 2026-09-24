#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-L-B: supplied BodyMap extraction patterns, not autonomous Suckle.

One external requirement is mapped/reserved and installed once. The existing
SensorimotorTrialV1 owns every control/world/admission interval, including fault
and reset behavior. The new observer never supplies a motor sequence or edits a
body coordinate. Actual movement and milk sensing remain separate outputs.
No task IP, WNM, PNM, nourishment, remedy selection or learning is introduced.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
import json
import math

import cca8_cli
from cca8_motor_contracts import MotorFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1,
    PlanarObjectV1, PlanarDetailObjectV1, PlanarWorldProfileV1, PlanarPerturbationV1,
    OralWorldProfileV1, OralWorldPerturbationV1, OralSealWorldProfileV1, OralClosurePerturbationV1,
    OralExtractionWorldProfileV1, OralExtractionWorldStateV1,
)
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import BodyAxisCapabilityV1, OralExtractionRequestV1, oral_extraction_capability_v1
from nca8_feeding import FeedingDetailProfileV1, FeedingDetailSourceV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_sensorimotor import SensorimotorExecutorV1, SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1, TargetOriginV1, OralExtractionTargetV1
from nca8_sensorimotor_demo import SensorimotorTrialV1
from nca8_visual import VisualSourceV1

__version__ = "0.1.0"
__all__ = [
    "ORAL_EXTRACTION_CONTROL_CASES_V1", "OralExtractionControlProfileV1", "OralExtractionControlTrialV1",
    "OralExtractionControlExperimentV1", "oral_extraction_control_profile_v1", "run_oral_extraction_control_v1",
    "render_oral_extraction_control_v1", "run_oral_extraction_control_menu_v1", "__version__",
]

ORAL_EXTRACTION_CONTROL_CASES_V1 = (
    "nominal", "twice", "shifted_stroke", "preview_only", "no_capability", "source_off", "no_touch", "no_seal",
    "dry_surface", "exhausted_supply", "missing_milk", "missing_stroke", "missing_seal", "blocked_motor",
    "blocked_prediction_off", "short_lease", "slow_capability", "delayed", "dropout", "support_loss", "seal_loss",
    "body_shift", "reach_shift", "cancelled",
)
_TICKS = 12


@dataclass(frozen=True, slots=True)
class OralExtractionControlProfileV1:
    """Inputs fixed before the run; private physical settings never enter control."""

    case: str
    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    oral: OralWorldProfileV1
    seal: OralSealWorldProfileV1
    extraction: OralExtractionWorldProfileV1
    capability: BodyAxisCapabilityV1 | None
    outward_extent: float = 0.10
    repetitions: int = 1
    lease_ticks: int = 8
    source_enabled: bool = True
    install: bool = True
    prediction_protection: bool = True
    cancel_tick: int | None = None

    def as_dict(self) -> dict[str, object]:
        """Detach settings; no expected quantity is passed to the controller."""
        return {**json.loads(json.dumps(asdict(self), allow_nan=False)), "origin": "supplied_requirement_fixture",
                "focal_calls": 0, "maximum_review_ticks": _TICKS, "milk_units": "uncalibrated_model_volume"}


def oral_extraction_control_profile_v1(case: str = "nominal") -> OralExtractionControlProfileV1:
    """Construct a finite paired-control setting without observing its result.

    Wet/dry/sensing cases have the same requirement and non-milk body evidence.
    Blocked-motor controls vary only the private actuator switch. Two cycles
    retain the same eight-tick lease; slow/delayed controls may honestly expire.
    """
    if not isinstance(case, str) or case not in ORAL_EXTRACTION_CONTROL_CASES_V1:
        raise ValueError("unknown oral extraction control case")
    surface = PlanarObjectV1("physical_surface", (0.1, 0.0), 0.004)
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0))
    planar = PlanarWorldProfileV1(frame_id="scene_xy:extraction_control", objects=(
        PlanarObjectV1("region_1", (0.2, 0.0)), PlanarDetailObjectV1("region_2", (0.1, 0.0), descriptor="feeding"),
    ))
    oral = OralWorldProfileV1(initial_extension_metres=0.1, surfaces=() if case == "no_touch" else (surface,))
    seal = OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=() if case == "no_seal" else (surface,),
                                   seal_available=case != "missing_seal")
    extraction = OralExtractionWorldProfileV1(initial_supply_units=1.0, supplying_surface=surface,
                                               initial_stroke=0.6 if case == "shifted_stroke" else 0.0,
                                               motor_enabled=case not in {"blocked_motor", "blocked_prediction_off"},
                                               milk_available=case != "missing_milk", stroke_available=case != "missing_stroke")
    capability = oral_extraction_capability_v1()
    if case in {"dry_surface", "exhausted_supply"}:
        extraction = replace(extraction, initial_supply_units=0.0 if case == "dry_surface" else 0.05)
    if case == "slow_capability":
        capability = replace(capability, maximum_rate=0.5)
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case in {"dropout", "support_loss"}:
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(
            1, _TICKS, drop_feedback=case == "dropout", remove_support=case == "support_loss"),))
    if case == "body_shift":
        planar = replace(planar, perturbations=(PlanarPerturbationV1(1, 2, velocity=(0.2, 0.0)),))
    if case == "reach_shift":
        oral = replace(oral, perturbations=(OralWorldPerturbationV1(1, 2, 0.2),))
    if case == "seal_loss":
        seal = replace(seal, perturbations=(OralClosurePerturbationV1(1, 2, -4.0),))
    return OralExtractionControlProfileV1(
        case, physical, planar, oral, seal, extraction, None if case == "no_capability" else capability,
        repetitions=2 if case == "twice" else 1, lease_ticks=2 if case == "short_lease" else 8,
        source_enabled=case != "source_off", install=case != "preview_only",
        prediction_protection=case != "blocked_prediction_off", cancel_tick=2 if case == "cancelled" else None,
    )


class OralExtractionControlTrialV1(SensorimotorTrialV1):
    """Supply one target while retaining the original lower advance/admission loop.

    Only initialization is specialized. Sources are initialized from actual
    admitted sensory input; the controller subsequently uses BodyMap's local
    evidence, not private supply or an observer's expected success. A reset
    constructs new owners and no old reservation can install in the new stream.
    """

    def __init__(self, case: str = "nominal", *, trace_capacity: int = 256,
                 settings: OralExtractionControlProfileV1 | None = None) -> None:
        self.settings = oral_extraction_control_profile_v1(case) if settings is None else settings
        if not isinstance(self.settings, OralExtractionControlProfileV1):
            raise TypeError("extraction trial needs its typed experimental settings")
        self.case = self.settings.case
        super().__init__(self.settings.physical,
                         capabilities=() if self.settings.capability is None else (self.settings.capability,),
                         control_profile=SensorimotorProfileV1(self.settings.prediction_protection, trace_capacity),
                         planar_profile=self.settings.planar, oral_profile=self.settings.oral, oral_seal_profile=self.settings.seal,
                         oral_extraction_profile=self.settings.extraction, stream_id="oral_extraction_control_fixture")

    def _initialize(self, feedback: MotorFeedbackV1) -> None:
        """Propose with paired source/body evidence; install once, without a task IP."""
        self.body = Nca8BodyRuntimeV1()
        mapper = self.body.configure_motor_targets(feedback.stream, self._capabilities, tick_seconds=self.world.profile.dt_seconds)
        mapper.update_feedback(feedback, at_tick=0)
        self.visual = VisualSourceV1(feedback.stream)
        self.maternal = MaternalSourceV1(feedback.stream, MaternalSeedV1())
        self.feeding = FeedingDetailSourceV1(feedback.stream, FeedingDetailProfileV1(source_enabled=self.settings.source_enabled))
        observation = admit_motor_visual_surface_v1(self.world.visual_surface(feedback=feedback), feedback)
        self.source = self.feeding.update(self.maternal.update(self.visual.update(observation, cycle_id=1, cutoff_tick=0)),
                                          oral_feedback=feedback)
        origin = TargetOriginV1(feedback.stream, "task:extraction_fixture", "application:extraction_fixture", "envelope:extraction_fixture")
        request = OralExtractionRequestV1(origin, self.source.source_map_ref, self.source.seed.detail_region_id,
                                          self.settings.outward_extent, self.settings.repetitions, self.settings.lease_ticks)
        self.proposal = mapper.propose_oral_extraction(request, self.source, at_tick=0)
        self.targets = (mapper.reserve(self.proposal, execution_id="execution:extraction_fixture", at_tick=0)
                        if self.proposal.bindings and self.settings.install else ())
        self.controller = SensorimotorExecutorV1(mapper, profile=self._control_profile)
        if self.targets:
            self.controller.install(self.targets, at_tick=0)
        self._latest_feedback = feedback
        self._stopped = False

    def durable_signature(self) -> str:
        """Inspect actual source-owned content; don't merely assert zero learning."""
        return json.dumps([owner.durable_map.as_dict() for owner in (self.visual, self.maternal, self.feeding)],
                          sort_keys=True, allow_nan=False)


@dataclass(frozen=True, slots=True)
class OralExtractionControlExperimentV1:
    """Read-only evidence of lower target execution, not a saved live permission."""

    settings: OralExtractionControlProfileV1
    target: OralExtractionTargetV1 | None
    steps: tuple[SensorimotorStepV1, ...]
    physical: tuple[OralExtractionWorldStateV1, ...]
    installation_count: int
    source_before: str
    source_after: str
    trace_retained: int

    @property
    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Check authority, ordered progress and scenario-specific outcomes externally.

        Expected quantities are assertions after the run, never motor decisions.
        Missing milk sensing is deliberately excluded from movement completion.
        """
        target = self.target
        reports = tuple(report for step in self.steps for report in step.reports)
        final = reports[-1] if reports else None
        achieved = final is not None and final.disposition is LocalTargetDispositionV1.ACHIEVED
        normal = self.settings.case in {"nominal", "twice", "shifted_stroke", "dry_surface", "exhausted_supply", "missing_milk"}
        unsupported = self.settings.case in {"preview_only", "no_capability", "source_off", "no_touch", "no_seal", "missing_stroke", "missing_seal"}
        commands = tuple(step.command for step in self.steps if step.command is not None)
        transfer = self.physical[-1].transferred_milk_units
        quantity = min(self.settings.extraction.initial_supply_units, self.settings.outward_extent * self.settings.repetitions)
        return (
            ("finite_shared_lower_intervals", len(self.steps) == _TICKS and len(self.physical) == _TICKS + 1),
            ("one_original_installation", self.installation_count == (0 if target is None else 1)),
            ("no_uninstalled_drive", target is not None or not commands),
            ("only_extraction_drives", all(command.oral_extraction_drive is not None and command.orientation_drive == 0.0
                 and command.extension_drive == 0.0 and command.translation is None and command.oral_drive is None
                 and command.oral_closure_drive is None for command in commands)),
            ("original_lease_preserved", target is None or all(step.command is None for step in self.steps if step.tick >= target.lease_ticks)),
            ("no_task_success_claim", all(not report.as_dict()["establishes_task_success"] for report in reports)),
            ("ordered_bounded_confirmation", target is None or all(len(report.extraction_confirmations) <= 2 * target.repetitions for report in reports)),
            ("normal_pattern_completed", not normal or achieved),
            ("adverse_not_false_achievement", normal or not achieved),
            ("unsupported_no_execution", not unsupported or target is None and not commands and transfer == 0.0),
            ("normal_physical_transfer", not normal or math.isclose(transfer, quantity, abs_tol=1e-10)),
            ("no_source_or_learning_change", self.source_before == self.source_after),
            ("bounded_diagnostics", 0 <= self.trace_retained <= _TICKS),
        )

    @property
    def review_status(self) -> str:
        """Return an observer verdict, never an input to physics or execution."""
        return "PASS" if all(passed for _, passed in self.checks) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Detach complete physical/sensed evidence; no live action state is restored."""
        return {"settings": self.settings.as_dict(), "target": None if self.target is None else self.target.as_dict(),
                "steps": [step.as_dict() for step in self.steps], "physical": [item.as_dict() for item in self.physical],
                "installation_count": self.installation_count, "review_status": self.review_status,
                "checks": [{"name": name, "passed": passed} for name, passed in self.checks],
                "durable_before": self.source_before, "durable_after": self.source_after, "trace_retained": self.trace_retained,
                "focal_calls": 0, "is_navigation_selected_suckle": False, "durable_learning_updates": 0,
                "scope": "supplied_bodymap_target_and_lower_execution"}


def run_oral_extraction_control_v1(case: str = "nominal", *, trace_capacity: int = 256) -> OralExtractionControlExperimentV1:
    """Run one finite experiment; every step is the existing driver, never a task loop."""
    trial = OralExtractionControlTrialV1(case, trace_capacity=trace_capacity)
    initial = trial.world.oral_extraction_body
    if initial is None:
        raise RuntimeError("control fixture requires the declared extraction plant")
    physical = [initial]
    steps: list[SensorimotorStepV1] = []
    before = trial.durable_signature()
    for _ in range(_TICKS):
        if trial.settings.cancel_tick == trial.world.tick and trial.targets:
            trial.controller.cancel_execution(at_tick=trial.world.tick)
        steps.append(trial.advance())
        body = trial.world.oral_extraction_body
        if body is None:
            raise RuntimeError("extraction plant unexpectedly disappeared")
        physical.append(body)
    target = trial.targets[0].current.target if trial.targets else None
    if target is not None and not isinstance(target, OralExtractionTargetV1):
        raise TypeError("control fixture installed a different target family")
    return OralExtractionControlExperimentV1(trial.settings, target, tuple(steps), tuple(physical),
                                             trial.controller.installation_count, before, trial.durable_signature(),
                                             len(trial.controller.trace_snapshot()))


def render_oral_extraction_control_v1(result: OralExtractionControlExperimentV1, *, detail: bool = False) -> str:
    """Render retained evidence only; no hidden provider read or new command."""
    if not isinstance(result, OralExtractionControlExperimentV1) or not isinstance(detail, bool):
        raise TypeError("renderer needs a completed experiment and Boolean detail flag")
    rows = [f"P16-2C-L-B {result.settings.case}: {result.review_status}",
            "SUPPLIED requirement -> BodyMap -> one installed lower pattern (NOT Navigation-selected Suckle)",
            f"installations={result.installation_count}; focal calls=0; durable updates=0",
            f"physical transfer={result.physical[-1].transferred_milk_units:.6f} model units; NOT nourishment"]
    for name, passed in result.checks:
        rows.append(f"  {'PASS' if passed else 'FAIL'} {name}")
    if detail:
        for step in result.steps:
            command = None if step.command is None else step.command.oral_extraction_drive
            report = step.reports[0] if step.reports else None
            measured = None if step.feedback is None or step.feedback.oral_extraction is None else step.feedback.oral_extraction.as_dict()
            rows.append(f"tick={step.tick}: drive={command}; sensed={measured}")
            if report is not None:
                rows.append(f"  {report.disposition.value}: {report.reason}; endpoints={len(report.extraction_confirmations)}")
    return "\n".join(rows)


def run_oral_extraction_control_menu_v1() -> None:
    """Expose shared experiments and retained detail; inspection executes no new trial."""
    retained: tuple[OralExtractionControlExperimentV1, ...] = ()
    groups = {"1": ("nominal", "twice", "shifted_stroke", "preview_only"),
              "2": ("dry_surface", "exhausted_supply", "missing_milk"),
              "3": ("blocked_motor", "blocked_prediction_off", "short_lease", "slow_capability", "delayed", "dropout"),
              "4": ("support_loss", "seal_loss", "body_shift", "reach_shift", "cancelled", "no_capability", "no_seal", "missing_stroke"),
              "5": ORAL_EXTRACTION_CONTROL_CASES_V1}
    while True:
        print("\nL-B: supplied extraction/return targets -- not autonomous Suckle")
        print("1 movement/installation; 2 milk independence; 3 incomplete/expiry; 4 protection; 5 all; 6 retained detail; 0 back")
        choice = cca8_cli.read_menu_input_v1("Select: ")
        if not choice or choice == "0":
            return
        if choice == "6":
            print("\n\n".join(render_oral_extraction_control_v1(item, detail=True) for item in retained) or "No retained review.")
        elif choice in groups:
            retained = tuple(run_oral_extraction_control_v1(case) for case in groups[choice])
            print("\n\n".join(render_oral_extraction_control_v1(item) for item in retained))
        else:
            print("Choose 0-6.")
