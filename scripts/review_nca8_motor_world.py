#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect P18-H2 with fixed motor commands, not a cognitive or feedback policy.

Run from the repository root: python scripts/review_nca8_motor_world.py
Every run owns a fresh HybridEnvironment. The preset drives and physical-time
perturbations are disclosed test inputs. Sensor reports retain their original
acquisition/availability times; reading a body for this display is evaluator-only.
No file, live robot, global RNG, task primitive or learned parameter is modified.
"""

from __future__ import annotations

from collections.abc import Callable
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cca8_env import HybridEnvironment
from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1
from cca8_support_world import MotorBodyStateV1, MotorWorldPerturbationV1, MotorWorldProfileV1


def _heading(number: int, text: str) -> None:
    """Print one bounded inspection section."""
    print(f"\n{number}) {text}\n" + "-" * 76)


def _reject(label: str, operation: Callable[[], object]) -> None:
    """Verify that a deliberate invalid operation fails instead of merely claiming it did."""
    try:
        operation()
    except (TypeError, ValueError, RuntimeError) as exc:
        print(f"  {label}: REJECTED ({exc})")
    else:
        raise AssertionError(f"expected rejection: {label}")


def run_motor_case_v1(
    name: str, orientation_drive: float, extension_drive: float, *,
    profile: MotorWorldProfileV1 | None = None, steps: int = 8,
) -> tuple[HybridEnvironment, tuple[MotorFeedbackV1, ...]]:
    """Run a finite fixed-drive fixture through the actual shared environment.

    The constant commands are chosen by this external test, not Righting or an
    SMP. Returned measurements include reset plus only reports delivered within
    the requested physical horizon; pending readings are not flushed by silently
    extending the run. The returned world is for external inspection only.
    """
    if isinstance(steps, bool) or not isinstance(steps, int) or not 1 <= steps <= 80:
        raise ValueError("review steps must be an integer in [1, 80]")
    world = HybridEnvironment()
    initial = world.reset_motor(stream_id=name, profile=profile)
    reports = [initial]
    for tick in range(steps):
        command = MotorCommandV1(initial.stream, tick + 1, tick, orientation_drive, extension_drive)
        reports.extend(world.step_motor(command))
    return world, tuple(reports)


def main() -> int:
    """Execute the nine small physical checks and print their measured results."""
    original_rng = random.getstate()
    print("P18-H2 BODY SIMULATOR -- FIXED COMMANDS, NOT RIGHTING")

    _heading(1, "RESET / ACTUAL BODY AND SENSOR BASIS")
    world = HybridEnvironment()
    first = world.reset_motor(stream_id="h2-review")
    print(f"  physical tilt={world.motor_body.body_tilt_degrees:+.3f} deg; extension={world.motor_body.support_extension:.3f}")
    print(f"  measured contact={first.support_contact}; loading={first.useful_loading:.6f}")
    print(f"  sample={first.sample_id}; event={first.event_tick}; available={first.available_tick}")
    print("  interval=0.05 simulation seconds; post-step sensor delay=1 tick")
    assert first.event_tick == first.available_tick == 0 and first.support_contact is True

    _heading(2, "INDEPENDENT DRIVES / SAME INITIAL BODY, FOUR INTERVALS")
    print("  case                 orientation  extension   final tilt  final extension")
    cases = (("neutral", 0.0, 0.0), ("orientation only", -0.5, 0.0),
             ("extension only", 0.0, 0.5), ("both", -0.5, 0.5), ("opposite rotation", 0.5, 0.0))
    endpoints: dict[str, MotorBodyStateV1] = {}
    for name, orientation, extension in cases:
        case, _ = run_motor_case_v1(name, orientation, extension, steps=4)
        endpoints[name] = case.motor_body
        print(f"  {name:20s} {orientation:+.2f}       {extension:+.2f}      "
              f"{case.motor_body.body_tilt_degrees:+8.3f}      {case.motor_body.support_extension:.3f}")
    assert endpoints["orientation only"].body_tilt_degrees < endpoints["neutral"].body_tilt_degrees
    assert endpoints["opposite rotation"].body_tilt_degrees > endpoints["neutral"].body_tilt_degrees
    assert endpoints["extension only"].support_extension > endpoints["neutral"].support_extension
    print("  Neutral still advances gravity; extension alone does not command upright.")

    _heading(3, "ONE COMMAND INTERVAL / BODY EFFECT BEFORE SENSOR DELIVERY")
    assert world.step_motor(MotorCommandV1(first.stream, 1, 0, -0.5, 0.5)) == ()
    print(f"  boundary 1: actual tilt={world.motor_body.body_tilt_degrees:+.6f}; extension={world.motor_body.support_extension:.3f}")
    print(f"  newest delivered event is still {world.observe_motor().event_tick}; no new report yet")
    delayed = world.step_motor(None)
    assert len(delayed) == 1 and delayed[0].event_tick == 1 and delayed[0].available_tick == 2
    print(f"  boundary 2: delivered sample={delayed[0].sample_id}, event=1, available=2")
    print(f"  that report measures loading={delayed[0].useful_loading:.6f}, destabilization={delayed[0].destabilization:.6f}")
    print("  The second interval used neutral drives, not a repeated first command.")

    _heading(4, "MIRRORED BODY / MIRRORED SUPPLIED COMMANDS")
    positive, _ = run_motor_case_v1("positive", -0.5, 0.5)
    negative, _ = run_motor_case_v1("negative", 0.5, 0.5,
                                   profile=MotorWorldProfileV1(initial_body=MotorBodyStateV1(-30.0, 0.4)))
    print(f"  +30 start with negative drive -> {positive.motor_body.body_tilt_degrees:+.6f} deg")
    print(f"  -30 start with positive drive -> {negative.motor_body.body_tilt_degrees:+.6f} deg")
    assert abs(positive.motor_body.body_tilt_degrees + negative.motor_body.body_tilt_degrees) < 1e-12
    print("  The test supplied the signs; BodyMap has not chosen them yet.")

    _heading(5, "EXTENSION OCCURS / SUPPORT SURFACE ABSENT")
    unsupported, reports = run_motor_case_v1("absent-surface", 0.0, 1.0, steps=4,
                                            profile=MotorWorldProfileV1(surface_present=False, sensor_delay_ticks=0))
    latest = reports[-1]
    print(f"  actual extension={unsupported.motor_body.support_extension:.3f}; measured contact={latest.support_contact}")
    print(f"  measured loading={latest.useful_loading:.3f}; body tilt={latest.body_tilt_degrees:+.3f} deg")
    assert abs(unsupported.motor_body.support_extension - 0.6) < 1e-12
    assert latest.support_contact is False and latest.useful_loading == 0.0
    print("  Movement occurred. No local target or Righting-success verdict was computed.")

    _heading(6, "FIXED-TIME DISTURBANCE / COMMANDS DO NOT CHANGE")
    perturbation = MotorWorldPerturbationV1(2, 3, angular_rate_degrees_s=120.0)
    normal, _ = run_motor_case_v1("normal", -0.5, 0.5, steps=3)
    disturbed, _ = run_motor_case_v1("disturbed", -0.5, 0.5, steps=3,
                                   profile=MotorWorldProfileV1(perturbations=(perturbation,)))
    difference = disturbed.motor_body.body_tilt_degrees - normal.motor_body.body_tilt_degrees
    print("  External rate +120 deg/s during [tick 2, tick 3) = [0.10 s, 0.15 s)")
    print(f"  normal tilt={normal.motor_body.body_tilt_degrees:+.6f}; disturbed tilt={disturbed.motor_body.body_tilt_degrees:+.6f}")
    print(f"  additional rotation={difference:+.6f} deg; same supplied drives in both runs")
    assert abs(difference - 6.0) < 1e-12
    print("  H2 senses the difference; automatic corrective control belongs to H4.")

    _heading(7, "DROPOUT / DELAY / MISSING CHANNEL ARE NOT NO CONTACT")
    dropout = HybridEnvironment()
    dropout.reset_motor(stream_id="dropout", profile=MotorWorldProfileV1(
        perturbations=(MotorWorldPerturbationV1(1, 3, drop_feedback=True),),
    ))
    for _ in range(5):
        due = dropout.step_motor(None)
        identities = [(item.sample_id, item.event_tick, item.available_tick) for item in due]
        print(f"  boundary={dropout.episode_steps}: new (sample,event,available)={identities}; "
              f"cached event={dropout.observe_motor().event_tick}")
    assert dropout.observe_motor().event_tick == 4
    partial = HybridEnvironment()
    partial_reading = partial.reset_motor(stream_id="partial", profile=MotorWorldProfileV1(unavailable_channels=("support_contact",)))
    print(f"  missing contact channel={partial_reading.support_contact}; retained measured loading={partial_reading.useful_loading:.6f}")
    assert partial_reading.support_contact is None
    print("  Earlier reports in transit can still arrive during a later acquisition dropout.")

    _heading(8, "BLOCKED MOTORS / SATURATION / WRONG INPUT")
    blocked, _ = run_motor_case_v1("blocked", -0.5, 0.5, steps=4,
                                 profile=MotorWorldProfileV1(orientation_motor_enabled=False, extension_motor_enabled=False))
    assert blocked.motor_body == endpoints["neutral"]
    print(f"  both motors unavailable -> neutral physical trajectory: tilt={blocked.motor_body.body_tilt_degrees:+.3f}")
    saturated, _ = run_motor_case_v1("saturation", 1.0, 1.0, steps=2,
                                   profile=MotorWorldProfileV1(initial_body=MotorBodyStateV1(89.9, 0.99)))
    print(f"  physical range limits -> tilt={saturated.motor_body.body_tilt_degrees:+.1f}, "
          f"extension={saturated.motor_body.support_extension:.1f}")
    assert saturated.motor_body == MotorBodyStateV1(90.0, 1.0)
    before = world.motor_body, world.episode_steps, world.observe_motor()
    _reject("old command tick", lambda: world.step_motor(MotorCommandV1(first.stream, 2, 0)))
    _reject("legacy stand-up token in motor mode", lambda: world.step("policy:stand_up", None))
    bad_packet = MotorCommandV1(first.stream, 2, world.episode_steps).as_dict()
    bad_packet["success"] = True
    _reject("hidden success field", lambda: MotorCommandV1.from_dict(bad_packet))
    assert (world.motor_body, world.episode_steps, world.observe_motor()) == before
    print("  rejected inputs left body, time and delivered evidence unchanged")

    _heading(9, "RESET / REPLAY / NO COGNITIVE OR LEARNING EFFECT")
    reset_reading = world.reset_motor(stream_id="h2-review")
    assert reset_reading.stream.generation == 2 and world.episode_steps == 0
    old_generation_command = MotorCommandV1(first.stream, 1, 0)
    _reject("old generation after reset", lambda: world.step_motor(old_generation_command))
    again, again_reports = run_motor_case_v1("positive", -0.5, 0.5)
    assert again.motor_body == positive.motor_body
    json.dumps([item.as_dict() for item in again_reports], allow_nan=False)
    assert random.getstate() == original_rng
    print("  reset generation=2; exact fixed-input replay=True; global RNG unchanged=True")
    print("  Righting selection / BodyMap mapping / SMP feedback control: not run")
    print("\nPHYSICAL PROVIDER CHECKS PASSED -- H3 mapping and H4 control remain next stages.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
