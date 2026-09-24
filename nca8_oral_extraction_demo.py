#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P16-2C-L-A: finite direct-drive extraction and milk-sensing reviews.

This external observer supplies a completely declared motor sequence to the
existing MotorWorldV1. It neither instantiates cognition nor supplies a BodyMap
target or autonomous Suckle routine. Actual stroke, physical transfer, delivered
interval evidence and the experiment's expected result remain separate records.
Reservoir/total values are observer-only; the sensory facet carries neither.

Every case is finite (at most 80 lower ticks). Stable-contact resolution controls
hold physical duration and drive changes fixed. Geometry cases test the declared
conservative whole-interval certificate, not calibrated oral/fluid physiology.
The menu and CLI use the same runner/renderer; retained detail never steps a world.
"""
from __future__ import annotations

from collections import deque
from dataclasses import asdict, dataclass, replace
import math
import json

import cca8_cli
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, MotorWorldPerturbationV1,
    PlanarObjectV1, PlanarWorldProfileV1, PlanarWorldStateV1, PlanarPerturbationV1,
    OralWorldProfileV1, OralWorldStateV1, OralSealWorldProfileV1, OralSealWorldStateV1, OralClosurePerturbationV1,
    OralExtractionWorldProfileV1, OralExtractionWorldStateV1,
)

__version__ = "0.1.0"
__all__ = [
    "ORAL_EXTRACTION_CASES_V1", "OralExtractionReviewProfileV1", "OralExtractionPhysicalSampleV1",
    "OralExtractionExperimentV1", "oral_extraction_review_profile_v1", "create_oral_extraction_world_v1",
    "run_oral_extraction_v1", "render_oral_extraction_v1", "run_oral_extraction_menu_v1", "__version__",
]

ORAL_EXTRACTION_CASES_V1 = (
    "wet_stroke", "neutral_seal", "motor_blocked", "unsupported", "saturated", "dry_surface", "displaced_supplier",
    "no_touch", "no_seal", "return_only", "held_drive", "repeated_strokes", "supply_exhausted", "missing_milk",
    "missing_stroke", "dropout", "delayed", "support_loss", "contact_loss", "seal_loss", "closure_at_endpoint",
    "curved_path", "resolution_base", "resolution_half", "resolution_fine", "feature_off",
)
_STREAM = MotorStreamRefV1("oral_extraction_physical_review", 1)
_MAX_TICKS = 80
_TOLERANCE = 1e-10


@dataclass(frozen=True, slots=True)
class OralExtractionReviewProfileV1:
    """Disclosed physical inputs and an external expected result, fixed before execution.

    The expected quantity is an experiment assertion only. It is never passed to
    the physical provider, a sensor record, or a cognitive owner. Commands are
    low-level drive records, not authorized cognitive task contributions.
    """

    case: str
    physical: MotorWorldProfileV1
    planar: PlanarWorldProfileV1
    oral: OralWorldProfileV1
    seal: OralSealWorldProfileV1
    extraction: OralExtractionWorldProfileV1 | None
    commands: tuple[MotorCommandV1 | None, ...]
    expected_transfer_units: float

    def as_dict(self) -> dict[str, object]:
        """Detach all fixture settings without installing or running anything."""
        return {**json.loads(json.dumps(asdict(self), allow_nan=False)), "commands": [item.as_dict() if item is not None else None for item in self.commands],
                "command_authority": "external_direct_drive_fixture", "milk_units": "uncalibrated_model_volume",
                "scope": "physical_provider_only", "maximum_ticks": _MAX_TICKS}


def oral_extraction_review_profile_v1(case: str = "wet_stroke") -> OralExtractionReviewProfileV1:
    """Build one named deterministic physical experiment without observing its result.

    Wet/dry and sensing controls preserve all non-varied physical settings.
    Held/repeated cases have the same 1.5-second horizon. Resolution cases have
    the same 0.6-second horizon and changes at 0.2 and 0.4 seconds (12/24/60 ticks).
    The curved-path disk contains both endpoints but excludes the arc midpoint.
    """
    if not isinstance(case, str) or case not in ORAL_EXTRACTION_CASES_V1:
        raise ValueError("unknown oral extraction physical review case")
    surface = PlanarObjectV1("physical_supply", (0.1, 0.0), 0.03)
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0), sensor_delay_ticks=0)
    planar = PlanarWorldProfileV1()
    oral = OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(surface,))
    seal = OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(surface,))
    extraction = OralExtractionWorldProfileV1(
        initial_supply_units=2.0, supplying_surface=surface,
    )
    drives: tuple[float, ...] = (1.0,) * 8
    expected = 0.8
    if case in {"neutral_seal", "feature_off"}:
        drives, expected = (0.0,) * 8, 0.0
    if case == "motor_blocked":
        extraction = replace(extraction, motor_enabled=False)
        expected = 0.0
    if case == "unsupported":
        physical, expected = replace(physical, surface_present=False), 0.0
    if case in {"saturated", "return_only"}:
        extraction = replace(extraction, initial_stroke=1.0)
        expected = 0.0
        if case == "return_only":
            drives = (-1.0,) * 8
    if case == "dry_surface":
        extraction, expected = replace(extraction, initial_supply_units=0.0), 0.0
    if case == "displaced_supplier":
        extraction = replace(extraction, supplying_surface=replace(surface, position=(0.3, 0.0)))
        expected = 0.0
    if case == "no_touch":
        oral, expected = replace(oral, surfaces=()), 0.0
    if case == "no_seal":
        seal, expected = replace(seal, sealable_surfaces=()), 0.0
    if case == "held_drive":
        drives, expected = (1.0,) * 30, 1.0
    if case == "repeated_strokes":
        drives, expected = (1.0,) * 10 + (-1.0,) * 10 + (1.0,) * 10, 2.0
    if case == "supply_exhausted":
        extraction, expected = replace(extraction, initial_supply_units=0.25), 0.25
    if case == "missing_milk":
        extraction = replace(extraction, milk_available=False)
    if case == "missing_stroke":
        extraction = replace(extraction, stroke_available=False)
    if case == "dropout":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(1, 3, drop_feedback=True),))
    if case == "delayed":
        physical = replace(physical, sensor_delay_ticks=3)
    if case == "support_loss":
        physical = replace(physical, perturbations=(MotorWorldPerturbationV1(2, 8, remove_support=True),))
        expected = 0.2
    if case == "contact_loss":
        planar = replace(planar, perturbations=(PlanarPerturbationV1(2, 3, velocity=(2.0, 0.0)),))
        expected = 0.2
    if case == "seal_loss":
        seal = replace(seal, perturbations=(OralClosurePerturbationV1(2, 3, -4.0),))
        expected = 0.2
    if case == "closure_at_endpoint":
        seal, expected = replace(seal, initial_closure=0.45), 0.7
    if case == "curved_path":
        reach, radius = 0.01, 0.02
        x, y = reach * math.cos(math.radians(4.5)), reach * math.sin(math.radians(4.5))
        surface = PlanarObjectV1("curved_contact", (x - math.sqrt(radius**2 - y**2), 0.0), radius)
        planar = replace(planar, initial_heading=-4.5, perturbations=(PlanarPerturbationV1(0, 1, heading_rate=180.0),))
        oral = replace(oral, initial_extension_metres=reach, surfaces=(surface,))
        seal = replace(seal, sealable_surfaces=(surface,))
        extraction = replace(extraction, supplying_surface=surface)
        drives, expected = (1.0,), 0.0
    if case.startswith("resolution_"):
        dt = {"resolution_base": 0.05, "resolution_half": 0.025, "resolution_fine": 0.01}[case]
        physical = replace(physical, dt_seconds=dt)
        span = round(0.2 / dt)
        drives = (1.0,) * span + (-1.0,) * span + (1.0,) * span
        expected = 0.8
    selected_extraction = None if case == "feature_off" else extraction
    commands = tuple(MotorCommandV1(
        _STREAM, tick + 1, tick,
        oral_closure_drive=1.0 if case == "closure_at_endpoint" and tick == 0 else None,
        oral_extraction_drive=drive,
    ) if selected_extraction is not None else None for tick, drive in enumerate(drives))
    return OralExtractionReviewProfileV1(case, physical, planar, oral, seal, selected_extraction, commands, expected)


def _world_from_profile(profile: OralExtractionReviewProfileV1) -> MotorWorldV1:
    """Pass only physical settings, never the expected quantity or command plan."""
    return MotorWorldV1(_STREAM, profile.physical, planar_profile=profile.planar, oral_profile=profile.oral,
                        oral_seal_profile=profile.seal, oral_extraction_profile=profile.extraction)


def create_oral_extraction_world_v1(case: str = "wet_stroke") -> MotorWorldV1:
    """Create a fresh independent provider at tick zero; construction transfers no milk."""
    return _world_from_profile(oral_extraction_review_profile_v1(case))


@dataclass(frozen=True, slots=True)
class OralExtractionPhysicalSampleV1:
    """Observer-only physical state; supply and cumulative transfer are never sensing."""

    tick: int
    body: MotorBodyStateV1
    planar: PlanarWorldStateV1
    oral: OralWorldStateV1
    seal: OralSealWorldStateV1
    extraction: OralExtractionWorldStateV1 | None

    def as_dict(self) -> dict[str, object]:
        """Detach an external snapshot without introducing a sensor acquisition."""
        return json.loads(json.dumps(asdict(self), allow_nan=False))


def _snapshot(world: MotorWorldV1) -> OralExtractionPhysicalSampleV1:
    """Inspect immutable public physical state; never return it to the provider."""
    planar, oral, seal = world.planar_body, world.oral_body, world.oral_seal_body
    if planar is None or oral is None or seal is None:
        raise RuntimeError("extraction review requires its complete oral physical context")
    return OralExtractionPhysicalSampleV1(world.tick, world.body, planar, oral, seal, world.oral_extraction_body)


@dataclass(frozen=True, slots=True)
class OralExtractionExperimentV1:
    """Completed bounded evidence, not a live provider, controller, WNM or task result.

    Full finite evidence is retained separately from the configurable diagnostic
    tail. All review checks are pure observers; no method steps or resets a world.
    Sensor totals count each delivered interval once and never substitute private
    supply/total values when the milk channel or an acquisition is absent.
    """

    profile: OralExtractionReviewProfileV1
    commands: tuple[MotorCommandV1 | None, ...]
    physical: tuple[OralExtractionPhysicalSampleV1, ...]
    initial_feedback: MotorFeedbackV1
    deliveries: tuple[tuple[MotorFeedbackV1, ...], ...]
    pending_counts: tuple[int, ...]
    diagnostics: tuple[str, ...]
    diagnostic_capacity: int

    def feedback(self) -> tuple[MotorFeedbackV1, ...]:
        """Return reset plus original delivered acquisitions, never observe() rereads."""
        return (self.initial_feedback,) + tuple(item for batch in self.deliveries for item in batch)

    def metrics(self) -> dict[str, object]:
        """Keep actually transferred and actually measured totals explicitly distinct."""
        final = self.physical[-1].extraction if self.physical else None
        measured = [item.oral_extraction.milk_transferred_units for item in self.feedback()
                    if item.oral_extraction is not None and item.oral_extraction.interval_start_tick is not None
                    and item.oral_extraction.milk_transferred_units is not None]
        return {"lower_ticks": len(self.commands), "duration_seconds": len(self.commands) * self.profile.physical.dt_seconds,
                "physical_transfer_units": final.transferred_milk_units if final is not None else None,
                "measured_delivered_units": math.fsum(measured),
                "known_interval_measurements": len(measured), "delivered_acquisitions": len(self.feedback()),
                "peak_pending_feedback": max(self.pending_counts, default=0),
                "retained_diagnostics": len(self.diagnostics)}

    def _delivery_checks(self) -> tuple[bool, bool, bool]:
        """Validate actual event/availability and sensed interval against original physics."""
        delay = self.profile.physical.sensor_delay_ticks
        available = self.profile.extraction
        acquisition_ticks = [event for event in range(1, len(self.commands) + 1)
                             if not any(p.start_tick <= event - 1 < p.stop_tick and p.drop_feedback
                                        for p in self.profile.physical.perturbations)]
        timing = len(self.deliveries) == len(self.commands) == len(self.pending_counts)
        measurements = True
        wire = True
        for tick, batch in enumerate(self.deliveries, 1):
            timing = timing and tuple(item.event_tick for item in batch) == tuple(e for e in acquisition_ticks if e + delay == tick)
            if tick <= len(self.pending_counts):
                timing = timing and self.pending_counts[tick - 1] == sum(e <= tick < e + delay for e in acquisition_ticks)
        for item in self.feedback():
            event, facet = item.event_tick, item.oral_extraction
            timing = timing and item.stream == _STREAM and item.sample_id == event + 1
            timing = timing and item.available_tick == (event + delay if event else 0)
            wire = wire and MotorFeedbackV1.from_dict(item.as_dict()) == item
            if available is None:
                measurements = measurements and facet is None
                continue
            if facet is None or event >= len(self.physical):
                measurements = False
                continue
            physical = self.physical[event].extraction
            if physical is None:
                measurements = False
                continue
            measurements = measurements and facet.interval_start_tick == (event - 1 if event else None)
            measurements = measurements and facet.stroke == (physical.stroke if available.stroke_available else None)
            expected = physical.interval_milk_units if available.milk_available and event else None
            measurements = measurements and facet.milk_transferred_units == expected
            wire = wire and set(facet.as_dict()) == {
                "frame_id", "stroke_units", "milk_units", "stroke", "milk_transferred_units", "interval_start_tick",
            }
        return timing, measurements, wire

    def checks(self) -> tuple[tuple[str, bool], ...]:
        """Test declared consequences and provenance without duplicating the transfer law.

        Expected endpoint quantities belong to these prescribed fixtures only.
        Conservation/motion/timing tests are independent of the production path
        certificate. Adverse cases pass by reporting zero or unknown truthfully.
        """
        expected = oral_extraction_review_profile_v1(self.profile.case)
        n = len(self.commands)
        shape = 0 < n <= _MAX_TICKS and len(self.physical) == n + 1
        shape = shape and tuple(s.tick for s in self.physical) == tuple(range(n + 1))
        initial = self.physical[0].extraction if self.physical else None
        final = self.physical[-1].extraction if self.physical else None
        profile = self.profile.extraction
        conservation, motion = True, True
        if profile is not None:
            for previous, current in zip(self.physical, self.physical[1:]):
                a, b = previous.extraction, current.extraction
                if a is None or b is None:
                    conservation, motion = False, False
                    continue
                conservation = conservation and math.isclose(
                    b.remaining_supply_units + b.transferred_milk_units, profile.initial_supply_units, abs_tol=_TOLERANCE,
                )
                conservation = conservation and math.isclose(
                    b.transferred_milk_units - a.transferred_milk_units, b.interval_milk_units, abs_tol=_TOLERANCE,
                )
                motion = motion and b.interval_milk_units <= max(0.0, b.stroke - a.stroke) + _TOLERANCE
            initial_ok = initial == OralExtractionWorldStateV1(profile.initial_stroke, profile.initial_supply_units)
            quantity = final is not None and math.isclose(final.transferred_milk_units, expected.expected_transfer_units,
                                                          abs_tol=_TOLERANCE)
        else:
            initial_ok = all(s.extraction is None for s in self.physical)
            quantity = final is None
        timing, measurements, wire = self._delivery_checks()
        known = [item.sample_id for item in self.feedback()]
        return (
            ("declared_profile_and_direct_drive_sequence", self.profile == expected and self.commands == expected.commands),
            ("finite_one_interval_per_command", shape),
            ("initial_state_is_not_a_feeding_event", initial_ok and self.initial_feedback.event_tick == 0),
            ("physical_expected_transfer", quantity),
            ("finite_supply_conserved", conservation),
            ("transfer_requires_actual_positive_displacement", motion),
            ("original_delivery_and_pending_timing", timing),
            ("measurement_matches_its_original_interval_or_unknown", measurements),
            ("no_duplicate_sensor_experience", len(known) == len(set(known))),
            ("strict_wire_and_no_reservoir_in_sensor_facet", wire),
            ("bounded_feedback_and_diagnostics", all(0 <= c <= 16 for c in self.pending_counts)
             and 1 <= self.diagnostic_capacity <= 256 and len(self.diagnostics) <= self.diagnostic_capacity),
        )

    @property
    def review_status(self) -> str:
        """Certify only the declared physical experiment, not feeding-task competence."""
        return "PASS" if all(passed for _, passed in self.checks()) else "FAIL"

    def as_dict(self) -> dict[str, object]:
        """Export detached physical and sensory lanes with their explicit evidence limits."""
        return {"scope": "P16_2C_L_A_physical_extraction_only", "review_status": self.review_status,
                "profile": self.profile.as_dict(), "metrics": self.metrics(), "checks": dict(self.checks()),
                "commands": [item.as_dict() if item is not None else None for item in self.commands],
                "observer_physical": [item.as_dict() for item in self.physical],
                "initial_feedback": self.initial_feedback.as_dict(),
                "delivered_feedback": [[item.as_dict() for item in batch] for batch in self.deliveries],
                "pending_counts": list(self.pending_counts), "diagnostics": list(self.diagnostics),
                "diagnostic_capacity": self.diagnostic_capacity, "command_authority": "external_direct_drive_fixture",
                "autonomous_suckle": False, "BodyMap_extraction_target": "not_implemented",
                "nourishment": "not_modeled", "durable_learning_updates": 0, "B99": "open"}


def run_oral_extraction_v1(case: str = "wet_stroke", *, diagnostic_capacity: int = 32) -> OralExtractionExperimentV1:
    """Run the finite declared commands once; retain newly delivered records separately.

    Diagnostic reads never select a drive. Missing feedback is retained as a
    missing acquisition rather than polled into fresh evidence or flushed by
    undeclared extra steps. Pending readings at the finite horizon remain pending.
    """
    if isinstance(diagnostic_capacity, bool) or not isinstance(diagnostic_capacity, int) or not 1 <= diagnostic_capacity <= 256:
        raise ValueError("diagnostic capacity must be an integer in [1,256]")
    profile = oral_extraction_review_profile_v1(case)
    world = _world_from_profile(profile)
    initial = world.observe()
    physical = [_snapshot(world)]
    deliveries: list[tuple[MotorFeedbackV1, ...]] = []
    pending: list[int] = []
    diagnostics: deque[str] = deque(maxlen=diagnostic_capacity)
    for command in profile.commands:
        batch = world.step(command)
        physical.append(_snapshot(world))
        deliveries.append(batch)
        pending.append(world.pending_feedback_count)
        diagnostics.append(f"tick={world.tick}; delivered_events={tuple(item.event_tick for item in batch)}")
    return OralExtractionExperimentV1(profile, profile.commands, tuple(physical), initial, tuple(deliveries), tuple(pending),
                                      tuple(diagnostics), diagnostic_capacity)


def render_oral_extraction_v1(result: OralExtractionExperimentV1, *, detail: bool = False) -> str:
    """Render completed evidence only; physical supply never masquerades as sensing."""
    if not isinstance(result, OralExtractionExperimentV1) or not isinstance(detail, bool):
        raise TypeError("extraction rendering requires a completed experiment and Boolean detail")
    lines = [f"P16-2C-L-A / {result.profile.case} / ORAL EXTRACTION PHYSICAL REVIEW: {result.review_status}",
             f"  Metrics: {result.metrics()}",
             "  INPUT: declared direct motor drives, not Navigation/Suckle or BodyMap/SMP authorization.",
             "  Stroke rate=2 normalized units/s; yield=1 uncalibrated model-volume unit/full stroke.",
             "  Seal is not extraction; actual milk in the mouth is not nourishment or task completion.",
             "  PHYSICAL includes private supply/total; SENSED includes only delivered interval measurements.",
             "  Unknown milk is not measured zero; reset has no prior interval. No extra steps flush delayed sensing.",
             "  Conservative whole-path contact may undercount boundary intervals; this is not a fluid/physiology model.",
             "  No new WNM, IP, learning, hunger, swallowing, Rest, autonomous suckling or B99 completion."]
    lines.extend(f"  {'PASS' if passed else 'FAIL'}: {name}" for name, passed in result.checks())
    if detail:
        for item in result.physical:
            state = item.extraction
            lines.append(f"  PHYSICAL tick={item.tick}: touch={item.oral.contact}; seal={item.seal.sealed}; "
                         f"extraction={state.as_dict() if state is not None else 'disabled'}")
        for command in result.commands:
            lines.append(f"  FIXTURE DRIVE: {command.as_dict() if command is not None else 'neutral None'}")
        for sample in result.feedback():
            facet = sample.oral_extraction
            lines.append(f"  SENSED sample={sample.sample_id}; event={sample.event_tick}; available={sample.available_tick}; "
                         f"extraction={facet.as_dict() if facet is not None else 'disabled'}")
    return "\n".join(lines)


def run_oral_extraction_menu_v1() -> None:
    """Inspect shared physical fixtures under option28; retained detail never reruns them."""
    groups = {
        "1": ("wet_stroke", "neutral_seal", "motor_blocked", "saturated", "dry_surface", "displaced_supplier"),
        "2": ("held_drive", "repeated_strokes", "return_only", "supply_exhausted", "resolution_base", "resolution_half", "resolution_fine"),
        "3": ("unsupported", "no_touch", "no_seal", "support_loss", "contact_loss", "seal_loss", "closure_at_endpoint", "curved_path"),
        "4": ("missing_milk", "missing_stroke", "dropout", "delayed", "feature_off"),
        "5": ORAL_EXTRACTION_CASES_V1,
    }
    retained: tuple[OralExtractionExperimentV1, ...] = ()
    while True:
        print("\nP16-2C-L-A -- DIRECT-DRIVE PHYSICAL EXTRACTION / MILK SENSING")
        print("  1) Stroke/seal/supply controls / 2) Repetition, exhaustion and physical-time resolution")
        print("  3) Support/contact/interval geometry / 4) Missing/delayed sensing and feature off")
        print("  5) All cases / 6) Retained read-only detail / [Enter] Return")
        choice = cca8_cli.read_menu_input_v1()
        if not choice:
            return
        if choice == "6":
            print("\n\n".join(render_oral_extraction_v1(item, detail=True) for item in retained) if retained else "No retained results.")
        elif choice in groups:
            retained = tuple(run_oral_extraction_v1(case) for case in groups[choice])
            print("\n\n".join(render_oral_extraction_v1(item) for item in retained))
        else:
            print("Unknown choice; use 1-6 or press Enter to return.")
