#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Print P18-H1 contract fixtures without creating a runtime or physical body.

Run from the repository root with ``python scripts/review_nca8_motor_contracts.py``.
This menu-independent development review is permitted by Planning v18 section
38.2. Every target, command and sensor reading below is an explicit fixture,
not the output of a Righting controller or the future H2 physical provider.
The program writes no files and makes no actuator or environment calls.
"""

from __future__ import annotations

import json
import random
import sys
from dataclasses import replace
from pathlib import Path
from typing import Callable

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1,
    CommittedBodyTargetV1,
    FocalMotorEvidenceV1,
    LocalTargetDispositionV1,
    LocalTargetReportV1,
    SensorimotorTargetKindV1,
    TargetDirectiveV1,
    TargetOriginV1,
)


def _heading(number: int, text: str) -> None:
    """Print one human-readable section without a trace-retention side effect."""
    print(f"\n{number}) {text}\n" + "-" * 72)


def _reject(label: str, operation: Callable[[], object]) -> None:
    """Print the expected contract refusal and fail loudly if it is not refused."""
    try:
        operation()
    except (TypeError, ValueError) as exc:
        print(f"  {label}: REJECTED ({exc})")
        return
    raise AssertionError(f"{label}: invalid fixture unexpectedly accepted")


def main() -> int:
    """Execute finite positive/adverse contract fixtures; return zero when correct."""
    rng_before = random.getstate()
    stream = MotorStreamRefV1("h1_review:body", 1)
    observed = MotorFeedbackV1(stream, 1, 0, 1, 30.0, 0.4, True, 0.1285, 0.6)
    origin = TargetOriginV1(stream, "task:fixture", "application:fixture", "envelope:fixture")
    target = BodyRelativeTargetV1(
        "orientation:fixture", 1, origin, SensorimotorTargetKindV1.ORIENTATION_ADJUST,
        observed, -12.0, 1.0, 18.0, 60.0,
    )
    committed = CommittedBodyTargetV1(target, "execution:fixture", 1)

    print("P18-H1 CONTRACT REVIEW -- FIXTURES ONLY, NO MOVEMENT")
    _heading(1, "PROPOSED BODY TARGET / FIXED STARTING BASIS")
    later = replace(observed, sample_id=2, event_tick=2, available_tick=3, body_tilt_degrees=25.0)
    print(f"  basis tilt={observed.body_tilt_degrees:.1f} deg; offset={target.offset:+.1f} deg; endpoint={target.endpoint:+.1f} deg")
    print(f"  later sensed tilt={later.body_tilt_degrees:.1f} deg; original endpoint still={target.endpoint:+.1f} deg")
    mirrored = replace(target, basis=replace(observed, body_tilt_degrees=-30.0), offset=12.0)
    print(f"  mirrored supplied target endpoint={mirrored.endpoint:+.1f} deg")
    print("  BodyMap mapping executed: False; these targets were supplied as fixtures")
    assert target.endpoint == 18.0 and mirrored.endpoint == -18.0

    _heading(2, "COMMITTED DESCRIPTION / COMMAND / SENSING ARE DIFFERENT")
    command = MotorCommandV1(stream, 1, 1, -0.5, 0.5)
    command.validate_for_update(stream=stream, now_tick=1, previous_command_id=0)
    print(f"  target description lease=[{committed.committed_tick}, {committed.expires_at_tick})")
    print(
        f"  independent command fixture: orientation_drive={command.orientation_drive:+.1f}, "
        f"extension_drive={command.extension_drive:+.1f}"
    )
    print(f"  sensor fixture: sample={observed.sample_id}, event={observed.event_tick}, available={observed.available_tick}")
    print("  installed execution: False; provider called: False; source changed: False")

    _heading(3, "LOCAL EXTENSION ACHIEVED / NO USEFUL SUPPORT")
    extension = BodyRelativeTargetV1(
        "extension:fixture", 1, origin, SensorimotorTargetKindV1.SUPPORT_EXTENSION,
        observed, 0.2, 0.01, 0.25, 1.0,
    )
    extension_context = CommittedBodyTargetV1(extension, "execution:fixture", 1)
    no_contact = replace(observed, sample_id=3, event_tick=3, available_tick=4,
                         support_extension=0.6, support_contact=False, useful_loading=0.0)
    report = LocalTargetReportV1(extension_context, LocalTargetDispositionV1.ACHIEVED, 4, "fixture_coordinate_observed", no_contact)
    print(f"  target extension={extension.endpoint:.2f}; sensed extension={no_contact.support_extension:.2f}")
    print(
        f"  local disposition={report.disposition.value}; support_contact={no_contact.support_contact}; "
        f"useful_loading={no_contact.useful_loading:.1f}"
    )
    print("  establishes Righting success: False; establishes action causation: False")

    _heading(4, "MISSING FEEDBACK IS NOT A FALSE CONTACT REPORT")
    unresolved = LocalTargetReportV1(extension_context, LocalTargetDispositionV1.UNRESOLVED, 4, "no_feedback_fixture")
    print(f"  missing report: feedback={unresolved.feedback}; disposition={unresolved.disposition.value}")
    print(f"  valid no-contact report: support_contact={no_contact.support_contact}; loading={no_contact.useful_loading:.1f}")
    _reject("achievement without feedback", lambda: LocalTargetReportV1(
        extension_context, LocalTargetDispositionV1.ACHIEVED, 4, "unsupported_claim"))

    _heading(5, "FUTURE FEEDBACK BLOCKED / FOCAL VIEW KEEPS THE SAME EVENT")
    _reject("cutoff 3 before availability 4", lambda: FocalMotorEvidenceV1(no_contact, 2, 3))
    focal = FocalMotorEvidenceV1(no_contact, 2, 4)
    print(f"  accepted at cutoff={focal.cutoff_tick}; same sample={focal.feedback.sample_id}; original event={focal.feedback.event_tick}")
    print("  new independent sensor event: False; new WNM: False")
    exported = focal.as_dict()
    exported_feedback = exported["feedback"]
    assert isinstance(exported_feedback, dict)
    exported_feedback["support_extension"] = 0.0
    print(f"  editing diagnostic dictionary changed original evidence: {focal.feedback.support_extension != 0.6}")

    _heading(6, "FINITE LEASE / WRONG GENERATION AND REVISION")
    # Explicit keyword arguments retain type-checker-visible parameter types.
    def check(tick: int, generation: int = 1, revision: int = 1) -> None:
        """Validate the fixture against an independently supplied current context."""
        committed.validate_current(
            stream=MotorStreamRefV1(stream.stream_id, generation), execution_id="execution:fixture",
            envelope_id="envelope:fixture", target_id=target.target_id, target_revision=revision, now_tick=tick,
        )
    check(8)
    print(f"  current at tick=8: True; expiry tick={committed.expires_at_tick}")
    _reject("pursuit at expiry tick 9", lambda: check(9))
    _reject("generation 2", lambda: check(8, generation=2))
    _reject("target revision 2", lambda: check(8, revision=2))
    print(f"  {TargetDirectiveV1.NO_NEW_TASK_OUTPUT.value} does not renew or cancel a target")

    _heading(7, "STRICT PACKETS / MALFORMED AND DUPLICATE COMMANDS")
    bad_packet = observed.as_dict()
    bad_packet["success"] = True
    _reject("hidden success field", lambda: MotorFeedbackV1.from_dict(bad_packet))
    _reject("Boolean tilt", lambda: replace(observed, body_tilt_degrees=True))
    numeric_contact_packet = observed.as_dict()
    numeric_contact_packet["support_contact"] = 0
    _reject("numeric contact", lambda: MotorFeedbackV1.from_dict(numeric_contact_packet))   
    #_reject("numeric contact", lambda: replace(observed, support_contact=0))
    _reject("availability before event", lambda: replace(observed, event_tick=3, available_tick=2))
    _reject("duplicate command", lambda: command.validate_for_update(stream=stream, now_tick=1, previous_command_id=1))

    _heading(8, "BOUNDARY SUMMARY / NO RUNTIME OR LEARNING")
    json.dumps(report.as_dict(), sort_keys=True, allow_nan=False)
    forbidden = {"cca8_env", "nca8_runtime", "nca8_body", "nca8_primitives"}
    assert not forbidden.intersection(sys.modules)
    assert rng_before == random.getstate()
    print("  provider, runtime, BodyMap actor, task primitive imported: False")
    print("  motor execution / NavMap revision / learning performed: False")
    print("  RNG unchanged: True; finite JSON export: True")
    print("\nCONTRACT FIXTURES PASSED -- H2 movement and H4 feedback control are not implemented here.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
