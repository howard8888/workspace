#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""External P18-H4 experiments and the shared menu/CLI review functions.

This file owns disposable physical worlds and drives the local controller. It
is a test/demo runner, not a cognitive executive. Its task requirement is an
explicit fixture. The actual controller in nca8_sensorimotor never receives the
world profile, actual hidden body, disturbance schedule or comparison label.
The old NCA8 session and its focal runtime are neither constructed nor advanced.

A matched open-loop control replays nominal commands into a perturbed body.
Its sensors remain visible only to the external observer, not to command choice.
This deliberate ablation does not bypass the normal controller's missing-data
policy or masquerade cached/predicted positions as new measurements.
"""

from __future__ import annotations

from dataclasses import dataclass, replace

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, admit_motor_feedback_batch_v1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1, MotorWorldV1, OralWorldProfileV1, OralSealWorldProfileV1, PlanarWorldProfileV1,
)
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import (
    BodyAxisCapabilityV1, BodyMovementRequestV1, BodyTargetProposalV1, BodyTargetReservationV1,
    nominal_body_capabilities_v1,
)
from nca8_sensorimotor import LocalControlEventV1, SensorimotorExecutorV1, SensorimotorProfileV1, SensorimotorStepV1
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, LocalTargetReportV1, SensorimotorTargetKindV1, TargetOriginV1

__version__ = "0.4.0"
__all__ = [
    "SensorimotorTrialV1", "SensorimotorExperimentV1", "run_sensorimotor_experiment_v1",
    "render_sensorimotor_experiment_v1", "run_sensorimotor_review_v1", "run_sensorimotor_review_menu_v1", "__version__",
]

_EXPERIMENTS = (
    "nominal", "perturbed", "feedback_off", "prediction_off", "dropout", "delayed",
    "no_surface", "no_orientation", "blocked_motor", "support_loss", "support_loss_prediction_off",
)


def _count(value: object, label: str, minimum: int, maximum: int) -> int:
    """Validate finite experiment bounds without accepting Boolean or float counters."""
    if not isinstance(value, int):
        raise TypeError(f"{label} must be an integer")
    if isinstance(value, bool):
        raise TypeError(f"{label} must be an integer")
    if value < minimum:
        raise ValueError(f"{label} must be in [{minimum}, {maximum}]")
    if value > maximum:
        raise ValueError(f"{label} must be in [{minimum}, {maximum}]")
    return value


@dataclass(frozen=True, slots=True)
class SensorimotorExperimentV1:
    """A finite observer result, not a saved brain or restorable motor permission."""

    case: str
    tick_seconds: float
    elapsed_ticks: int
    marker_stride: int
    targets: tuple[BodyTargetReservationV1, ...]
    withheld: tuple[tuple[SensorimotorTargetKindV1, str], ...]
    steps: tuple[SensorimotorStepV1, ...]
    final_body: MotorBodyStateV1
    latest_feedback: MotorFeedbackV1
    reports: tuple[LocalTargetReportV1, ...]
    events: tuple[LocalControlEventV1, ...]
    installation_count: int
    prediction_protection: bool
    open_loop: bool

    @property
    def commands(self) -> tuple[MotorCommandV1 | None, ...]:
        """Return the actual finite command schedule used for observer comparison."""
        return tuple(item.command for item in self.steps)

    def as_dict(self) -> dict[str, object]:
        """Export physical outcomes and controller evidence with their different roles."""
        return {
            "case": self.case, "tick_seconds": self.tick_seconds, "elapsed_ticks": self.elapsed_ticks,
            "control_profile_id": "fixed_target_control_v1", "physical_profile_id": "planar_motor_world_v1",
            "elapsed_seconds": self.elapsed_ticks * self.tick_seconds, "marker_stride": self.marker_stride,
            "supplied_target_descriptions": [item.current.as_dict() for item in self.targets],
            "withheld": [{"kind": kind.value, "reason": reason} for kind, reason in self.withheld],
            "steps": [item.as_dict() for item in self.steps],
            "external_final_body": {
                "body_tilt_degrees": self.final_body.body_tilt_degrees, "support_extension": self.final_body.support_extension,
            },
            "latest_feedback": self.latest_feedback.as_dict(), "reports": [item.as_dict() for item in self.reports],
            "events": [item.as_dict() for item in self.events], "installation_count": self.installation_count,
            "prediction_protection": self.prediction_protection, "open_loop": self.open_loop,
            "task_requirement_source": "external_fixture", "focal_calls": 0, "durable_learning_updates": 0,
            "establishes_righting_success": False,
        }


class SensorimotorTrialV1:
    """Own one isolated physical world and its local target executor.

    advance() consumes one local command and invokes the provider once. It never
    selects a new task from physical state or calls the focal NCA8 runtime. The
    provider's due sensor results are staged for the next boundary. A failed
    physical call or malformed return stops the driver, including when a body may
    already have moved; there is no retry or fictional rollback.

    A fresh/reset trial explicitly supplies the desired coordinates, constructs
    BodyMap targets through H3, and installs that fixture once. Current body
    readings are real H2 measurements. No target endpoint is assigned to physics.
    Optional planar/oral physical profiles let a specialized relation fixture
    override only _initialize(); construction, stepping, fault handling and reset
    stay shared. Default H4 profiles and complete experiment exports are unchanged.
    """

    def __init__(
        self, physical_profile: MotorWorldProfileV1 | None = None, *,
        capabilities: tuple[BodyAxisCapabilityV1, ...] | None = None,
        desired_tilt_degrees: float | None = 0.0, desired_extension: float | None = 0.60,
        control_profile: SensorimotorProfileV1 | None = None,
        planar_profile: PlanarWorldProfileV1 | None = None, oral_profile: OralWorldProfileV1 | None = None,
        stream_id: str = "h4_fixture_body", oral_seal_profile: OralSealWorldProfileV1 | None = None,
    ) -> None:
        self.world = MotorWorldV1(MotorStreamRefV1(stream_id, 1), physical_profile,
                                 planar_profile=planar_profile, oral_profile=oral_profile, oral_seal_profile=oral_seal_profile)
        self._capabilities = nominal_body_capabilities_v1() if capabilities is None else capabilities
        self._desired_tilt = desired_tilt_degrees
        self._desired_extension = desired_extension
        self._control_profile = control_profile if control_profile is not None else SensorimotorProfileV1()
        self._stepping = False
        self._stopped = False
        self.body: Nca8BodyRuntimeV1
        self.controller: SensorimotorExecutorV1
        self.proposal: BodyTargetProposalV1
        self.targets: tuple[BodyTargetReservationV1, ...]
        self._latest_feedback: MotorFeedbackV1
        self._initialize(self.world.observe())

    def _initialize(self, feedback: MotorFeedbackV1) -> None:
        """Create fresh body/controller ownership; old leases and sensor queues are not reused."""
        self.body = Nca8BodyRuntimeV1()
        mapper = self.body.configure_motor_targets(
            feedback.stream, self._capabilities, tick_seconds=self.world.profile.dt_seconds,
        )
        mapper.update_feedback(feedback, at_tick=0)
        origin = TargetOriginV1(feedback.stream, "task:h4_fixture", "application:h4_fixture", "envelope:h4_fixture")
        request = BodyMovementRequestV1(origin, self._desired_tilt, self._desired_extension)
        self.proposal = mapper.propose(request, at_tick=0)
        self.targets = mapper.reserve(self.proposal, execution_id="execution:h4_fixture", at_tick=0) if self.proposal.bindings else ()
        self.controller = SensorimotorExecutorV1(mapper, profile=self._control_profile)
        if self.targets:
            self.controller.install(self.targets, at_tick=0)
        self._latest_feedback = feedback
        self._stopped = False

    @property
    def stopped(self) -> bool:
        """Report whether a failed boundary requires an explicit reset."""
        return self._stopped

    @property
    def latest_feedback(self) -> MotorFeedbackV1:
        """Read the last delivered acquisition without updating its age or the body."""
        return self._latest_feedback

    def reset(self) -> None:
        """Explicitly replace local ownership after the provider advances its generation."""
        if self._stepping:
            raise RuntimeError("cannot reset during a physical advance")
        feedback = self.world.reset()
        self._initialize(feedback)

    def _admit(self, delivered: tuple[MotorFeedbackV1, ...]) -> None:
        """Validate a returned sensor batch before replacing the pending local reading.

        Replays retain their time and strictly older arrivals cannot replace the
        newer acquisition. A changed reused identity or inconsistent ordering is
        a fault, not a fresh confirmation. This external admission runs after
        physical evolution and never re-enters the just-completed control step.
        """
        self._latest_feedback = admit_motor_feedback_batch_v1(
            delivered, self._latest_feedback, stream=self.world.stream, at_tick=self.world.tick,
        )

    def advance_open_loop(self, command: MotorCommandV1 | None) -> SensorimotorStepV1:
        """Replay one explicitly supplied comparator command, without feedback control.

        This method is for the named external ablation, not normal execution.
        Current sensors remain observer-only. The original finite lease and
        command time/stream still apply; no replay can renew the fixture target.
        The same stop-on-exception and post-step admission boundary is retained.
        """
        if self._stepping or self._stopped:
            raise RuntimeError("trial is stopped or already advancing; no automatic retry")
        tick = self.world.tick
        self._stepping = True
        try:
            if self.world.stream != self._latest_feedback.stream:
                raise ValueError("open-loop replay belongs to a different physical generation")
            if command is not None:
                if not self.targets or any(tick >= item.current.expires_at_tick for item in self.targets):
                    raise ValueError("open-loop command exceeds its original fixture lease")
            result = SensorimotorStepV1(tick, self._latest_feedback, "external_observer_only", command, (), (), (), 0, False)
            delivered = self.world.step(command)
            if self.world.tick != tick + 1:
                raise ValueError("physical provider did not advance exactly one interval")
            self._admit(delivered)
            return result
        except BaseException:
            self._stopped = True
            self.controller.abort("external_replay_or_admission_failed", at_tick=tick)
            raise
        finally:
            self._stepping = False

    def advance(self) -> SensorimotorStepV1:
        """Issue at most one command, step physics once, then stage due real sensing."""
        if self._stepping or self._stopped:
            raise RuntimeError("trial is stopped or already advancing; no automatic retry")
        tick = self.world.tick
        self._stepping = True
        try:
            if self.world.stream != self._latest_feedback.stream or tick != self.controller.next_tick:
                raise ValueError("physical world and local execution no longer share their generation/time")
            result = self.controller.step(self._latest_feedback, at_tick=tick)
            delivered = self.world.step(result.command)
            if self.world.tick != tick + 1:
                raise ValueError("physical provider did not advance exactly one interval")
            self._admit(delivered)
            return result
        except BaseException:
            self._stopped = True
            self.controller.abort("external_advance_or_admission_failed", at_tick=tick)
            raise
        finally:
            self._stepping = False


def _physical_profile(case: str) -> MotorWorldProfileV1:
    """Select disclosed observer-controlled forcing; never pass its label to the executor."""
    profile = MotorWorldProfileV1()
    if case in {"perturbed", "feedback_off", "prediction_off"}:
        return replace(profile, perturbations=(MotorWorldPerturbationV1(1, 2, angular_rate_degrees_s=120.0),))
    if case in {"support_loss", "support_loss_prediction_off"}:
        return replace(profile, perturbations=(MotorWorldPerturbationV1(1, 12, remove_support=True),))
    if case == "dropout":
        return replace(profile, perturbations=(MotorWorldPerturbationV1(1, 12, drop_feedback=True),))
    if case == "delayed":
        return replace(profile, sensor_delay_ticks=4)
    if case == "no_surface":
        return replace(profile, surface_present=False)
    if case == "blocked_motor":
        return replace(profile, orientation_motor_enabled=False)
    return profile


def run_sensorimotor_experiment_v1(
    case: str = "nominal", *, ticks: int = 12, marker_stride: int = 4, trace_capacity: int = 256,
) -> SensorimotorExperimentV1:
    """Run a finite supplied-target experiment or its explicit open-loop comparison.

    Markers at K=1/4/8 are observer reference opportunities only. H4 runs zero
    focal decisions; changing these markers cannot change drives or physical
    time. Each run uses the same dt and requested tick horizon. Open-loop control
    replays the nominal issued schedule, not a hidden stand-up policy or future
    perturbed observations. Its output reports no fictitious local achievement.
    """
    if case not in _EXPERIMENTS:
        raise ValueError("unknown H4 experiment")
    _count(ticks, "ticks", 1, 80)
    _count(marker_stride, "marker_stride", 1, 8)
    control = SensorimotorProfileV1(
        prediction_protection=case not in {"prediction_off", "support_loss_prediction_off", "feedback_off"},
        trace_capacity=trace_capacity,
    )
    capabilities = nominal_body_capabilities_v1()
    if case == "no_orientation":
        capabilities = tuple(item for item in capabilities if item.kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    trial = SensorimotorTrialV1(_physical_profile(case), capabilities=capabilities, control_profile=control)
    steps: list[SensorimotorStepV1] = []
    if case == "feedback_off":
        reference = run_sensorimotor_experiment_v1("nominal", ticks=ticks, marker_stride=marker_stride, trace_capacity=trace_capacity)
        for original in reference.commands:
            # This is an external control experiment: sensed data never choose the replay command.
            command = None if original is None else replace(original, stream=trial.world.stream)
            steps.append(trial.advance_open_loop(command))
        reports: tuple[LocalTargetReportV1, ...] = ()
        events: tuple[LocalControlEventV1, ...] = ()
    else:
        steps = [trial.advance() for _ in range(ticks)]
        reports, events = trial.controller.reports, trial.controller.events
    return SensorimotorExperimentV1(
        case, trial.world.profile.dt_seconds, trial.world.tick, marker_stride, trial.targets, trial.proposal.withheld,
        tuple(steps), trial.world.body, trial.latest_feedback, reports, events, trial.controller.installation_count,
        control.prediction_protection, case == "feedback_off",
    )


def render_sensorimotor_experiment_v1(result: SensorimotorExperimentV1, *, detailed: bool = False) -> tuple[str, ...]:
    """Render completed observer results only; printing cannot advance an experiment."""
    lines = [
        f"CASE: {result.case} | supplied targets; no Righting or focal decision",
        "  profiles: fixed_target_control_v1 / planar_motor_world_v1 (fixed engineering assumptions)",
        f"  dt={result.tick_seconds:.3f}s; physical ticks={result.elapsed_ticks}; "
        f"elapsed={result.elapsed_ticks * result.tick_seconds:.3f}s",
        f"  installations={result.installation_count}; replayed open-loop={result.open_loop}; "
        f"local prediction protection={result.prediction_protection}",
    ]
    for reservation in result.targets:
        committed = reservation.current
        target = committed.target
        if not isinstance(target, BodyRelativeTargetV1):
            raise TypeError("this retained review expects a scalar support target")
        lines.append(
            f"  target {target.kind.value}: {target.basis_coordinate:+.3f} -> {target.endpoint:+.3f}; "
            f"lease=[{committed.committed_tick},{committed.expires_at_tick})"
        )
    for kind, reason in result.withheld:
        lines.append(f"  withheld {kind.value}: {reason}")
    lines.append(
        f"  external final body: tilt={result.final_body.body_tilt_degrees:+.6f}; "
        f"extension={result.final_body.support_extension:.6f}"
    )
    feedback = result.latest_feedback
    lines.append(
        f"  last delivered event={feedback.event_tick}, available={feedback.available_tick}; "
        f"contact={feedback.support_contact}; loading={feedback.useful_loading}"
    )
    for report in result.reports:
        target = report.committed_target.target
        observed_event_tick = report.feedback.event_tick if report.feedback is not None else None
        lines.append(
            f"  {target.kind.value}: {report.disposition.value}; reason={report.reason}; "
            f"sensed event={observed_event_tick}; anomalies corrected={report.correction_count}"
        )
    if result.open_loop:
        lines.append("  Local achievement not evaluated: sensing is external observation only in this replay control.")
    for event in result.events:
        lines.append(
            f"  significant {event.number}: {event.kind.value} {event.reason}; physical={event.event_tick}; "
            f"noticed={event.noticed_tick}; residual={event.residual}"
        )
    if detailed:
        lines.append("  tick | sensed(event/available) | orientation drive | extension drive | local reasons")
        for item in result.steps:
            if item.tick % result.marker_stride == 0:
                lines.append(
                    f"  ---- reference focal marker {item.tick} "
                    "(NO focal call; lower execution continues only within its lease) ----"
                )
            sensed = f"{item.feedback.event_tick}/{item.feedback.available_tick}" if item.feedback is not None else "missing"
            orientation = item.command.orientation_drive if item.command is not None else 0.0
            extension = item.command.extension_drive if item.command is not None else 0.0
            reasons = "; ".join(f"{report.committed_target.target.kind.value}:{report.reason}" for report in item.reports)
            lines.append(f"  {item.tick:4d} | {sensed:>22s} | {orientation:+.6f} | {extension:+.6f} | {reasons or 'external replay'}")
            for comparison in item.comparisons:
                lines.append(
                    f"       prediction for event {comparison.prediction.event_tick}: residual={comparison.residual}; "
                    f"contact mismatch={comparison.contact_mismatch}"
                )
    lines.append("  Achievement names a sensed event; pursuit then stops. Passive tilt may drift afterward.")
    lines.append("  Local target results are not task completion or learning.")
    return tuple(lines)


def run_sensorimotor_review_v1(*, detailed: bool = False) -> tuple[SensorimotorExperimentV1, ...]:
    """Run and print the shared finite review cases used by CLI and menu tests."""
    print("P18-H4 SENSORIMOTOR REVIEW -- SUPPLIED TARGETS, REAL MOVEMENT, NO RIGHTING TASK")
    results = tuple(run_sensorimotor_experiment_v1(case) for case in _EXPERIMENTS)
    for number, result in enumerate(results, 1):
        print(f"\n{number}) {'-' * 68}")
        print("\n".join(render_sensorimotor_experiment_v1(result, detailed=detailed)))
    print("\nLOCAL TARGET EXECUTION REVIEW COMPLETE -- H5 Righting preview remains next.")
    return results


def run_sensorimotor_review_menu_v1() -> None:
    """Open a small isolated H4 review menu, preserving any retained A0 session.

    Opening, returning and viewing retained detail perform no simulation. Each
    explicit run constructs fresh private fixtures; no old motor permission is
    restored. The main menu retains ownership of its common return pause.
    """
    latest: tuple[SensorimotorExperimentV1, ...] = ()
    while True:
        print("\nP18-H4 -- SUPPLIED-TARGET MOVEMENT / FAST LOCAL FEEDBACK")
        print(cca8_cli.MENU_RESPONSE_DIVIDER)
        print("Each selected run uses a fresh isolated body. No Righting selection, WNM, PNM or learning runs here.")
        print("  1) Run nominal supplied-target movement")
        print("  2) Compare disturbed feedback, nominal-command replay, and prediction-protection-off")
        print("  3) Run with orientation capability unavailable")
        print("  4) Review missing and delayed sensor feedback")
        print("  5) Run with the supporting surface absent")
        print("  6) Inspect the last run's detailed local history (no new movement)")
        print("  [Enter] Return to NCA8 menu")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        selections = {
            "1": ("nominal",), "2": ("perturbed", "feedback_off", "prediction_off", "support_loss", "support_loss_prediction_off"),
            "3": ("no_orientation",), "4": ("dropout", "delayed"), "5": ("no_surface",),
        }
        if choice == "6":
            if not latest:
                print("No H4 run is retained. Choose an explicit experiment first.")
            for result in latest:
                print("\n".join(render_sensorimotor_experiment_v1(result, detailed=True)))
        elif choice in selections:
            latest = tuple(run_sensorimotor_experiment_v1(case) for case in selections[choice])
            for result in latest:
                print("\n".join(render_sensorimotor_experiment_v1(result)))
        else:
            print("Choose 1-6 or press Enter to return.")
