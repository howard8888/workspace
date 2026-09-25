#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Inspect P18-H3 BodyMap calculations without selecting Righting or moving a body.

Run: python scripts/review_nca8_body_targets.py
Initial readings come from fresh H2 provider resets. Later changed/missing samples
are explicitly supplied fixtures. The real BodyMap helper forms and reserves the
targets; no motor drive, local controller, task primitive or learner is invoked.
All output is read-only inspection of these disposable private test instances.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import replace
import json
from pathlib import Path
import random
import sys

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from cca8_env import HybridEnvironment
from cca8_motor_contracts import MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import MotorBodyStateV1, MotorWorldProfileV1
from nca8_body import Nca8BodyRuntimeV1
from nca8_body_targets import (
    BodyAxisCapabilityV1,
    BodyMovementRequestV1,
    BodyTargetMapperV1,
    BodyTargetProposalV1,
    nominal_body_capabilities_v1,
)
from nca8_sensorimotor_contracts import BodyRelativeTargetV1, FocalMotorEvidenceV1, TargetOriginV1


def _section(number: int, title: str) -> None:
    """Display a numbered mapping experiment, never a cognitive-cycle number."""
    print(f"\n{number}) {title}")
    print("-" * 76)


def _expect_rejection(label: str, call: Callable[[], object]) -> None:
    """Run the adverse check and fail this inspection if it unexpectedly passes."""
    try:
        call()
    except (ValueError, TypeError) as error:
        print(f"  {label}: REJECTED ({error})")
        return
    raise AssertionError(f"{label} unexpectedly passed")


def _initial(tilt: float = 30.0, *, surface: bool = True) -> MotorFeedbackV1:
    """Acquire actual initial H2 sensor values without issuing a motor command."""
    world = HybridEnvironment()
    profile = MotorWorldProfileV1(initial_body=MotorBodyStateV1(tilt, 0.4), surface_present=surface)
    return world.reset_motor(stream_id="h3-review", profile=profile)


def _configured(
    feedback: MotorFeedbackV1, capabilities: tuple[BodyAxisCapabilityV1, ...] | None = None,
) -> BodyTargetMapperV1:
    """Configure the actual BodyMap owner with explicitly supplied capabilities."""
    body = Nca8BodyRuntimeV1()
    mapper = body.configure_motor_targets(
        feedback.stream, nominal_body_capabilities_v1() if capabilities is None else capabilities,
    )
    mapper.update_feedback(feedback, at_tick=0)
    return mapper


def _request(stream: MotorStreamRefV1) -> BodyMovementRequestV1:
    """Supply a task fixture; the review does not invoke Navigation or Righting."""
    return BodyMovementRequestV1(TargetOriginV1(stream, "task:fixture", "application:1", "envelope:1"), 0.0, 0.6)


def _show(proposal: BodyTargetProposalV1) -> None:
    """Describe each mapped axis or its own refusal without printing a world dump."""
    for binding in proposal.bindings:
        target = binding.target
        if not isinstance(target, BodyRelativeTargetV1):
            raise TypeError("this retained review expects a scalar support target")
        print(
            f"  {target.kind.value}: basis={target.basis_coordinate:+.3f} offset={target.offset:+.3f}"
            f" endpoint={target.endpoint:+.3f}; capability={binding.capability.capability_id}"
        )
    for kind, reason in proposal.withheld:
        print(f"  {kind.value}: WITHHELD ({reason})")


def main() -> int:
    """Execute ten positive/adverse H3 checks; return zero only after all assertions."""
    original_rng = random.getstate()
    first = _initial()
    request = _request(first.stream)
    print("P18-H3 BODYMAP TARGETS -- SUPPLIED TASK, NO MOTOR EXECUTION")

    _section(1, "SAME TASK REQUIREMENT / TWO MIRRORED BODIES")
    print("  Supplied requirement: tilt toward 0 degrees; extension toward 0.60")
    for tilt in (30.0, -30.0):
        mapper = _configured(_initial(tilt))
        proposal = mapper.propose(request, at_tick=0)
        print(f"  Starting body tilt={tilt:+.1f} degrees")
        _show(proposal)
        target = proposal.bindings[0].target
        assert isinstance(target, BodyRelativeTargetV1)
        assert target.endpoint == (18.0 if tilt > 0 else -18.0)
        assert not mapper.reservations(at_tick=0)
    print("  BodyMap computed the signs. No target was supplied directly by the fixture.")

    _section(2, "SAME BODY / SMALLER CAPABILITY AND ABSENT CAPABILITY")
    capabilities = nominal_body_capabilities_v1()
    smaller = replace(capabilities[0], maximum_step=4.0, maximum_excursion=6.0, maximum_rate=20.0)
    limited = _configured(first, (smaller, capabilities[1])).propose(request, at_tick=0)
    _show(limited)
    limited_target = limited.bindings[0].target
    assert isinstance(limited_target, BodyRelativeTargetV1)
    assert limited_target.endpoint == 26.0
    print("  Now offer only the extension capability:")
    _show(_configured(first, (capabilities[1],)).propose(request, at_tick=0))

    _section(3, "NO SUPPORT / MISSING TILT / MISSING CONTACT ARE DISTINCT")
    print("  Actual H2 reset with no supporting surface:")
    unsupported = _configured(_initial(surface=False)).propose(request, at_tick=0)
    _show(unsupported)
    assert len(unsupported.bindings) == 1 and unsupported.bindings[0].target.basis.support_contact is False
    print("  Supplied fixture with unavailable tilt measurement:")
    _show(_configured(replace(first, body_tilt_degrees=None)).propose(request, at_tick=0))
    print("  Supplied fixture with unavailable contact measurement:")
    _show(_configured(replace(first, support_contact=None)).propose(request, at_tick=0))
    print("  Extension remains a possible attempt, not proof of contact or useful load.")

    _section(4, "NEW BODY EVIDENCE / OLD TARGET AND FOCAL BASIS STAY FIXED")
    mapper = _configured(first)
    original = mapper.propose(request, at_tick=0)
    old_target = original.bindings[0].target
    assert isinstance(old_target, BodyRelativeTargetV1)
    focal = FocalMotorEvidenceV1(first, 1, 0)
    old_focal = json.dumps(focal.as_dict(), sort_keys=True)
    later = replace(first, sample_id=2, event_tick=1, available_tick=1, body_tilt_degrees=25.0)
    mapper.update_feedback(later, at_tick=1)  # Explicit later-sample fixture, not a physical command result.
    newer = mapper.propose(request, at_tick=1)
    assert isinstance(newer.bindings[0].target, BodyRelativeTargetV1)
    print(f"  supplied later tilt=25.0; original target endpoint={old_target.endpoint:+.1f}")
    print(f"  a NEW proposal from that new basis targets {newer.bindings[0].target.endpoint:+.1f}")
    print(f"  original focal evidence unchanged: {json.dumps(focal.as_dict(), sort_keys=True) == old_focal}")
    assert old_target.endpoint == 18.0 and newer.bindings[0].target.endpoint == 13.0
    assert json.dumps(focal.as_dict(), sort_keys=True) == old_focal

    _section(5, "PROPOSAL / BODY-SIDE RESERVATION / RESOURCE CONFLICT")
    mapper = _configured(first)
    proposal = mapper.propose(request, at_tick=0)
    print(f"  reservations before explicit reserve: {len(mapper.reservations(at_tick=0))}")
    #tilt_reservation, extension_reservation = mapper.reserve(proposal, execution_id="execution:fixture", at_tick=0)
    reservations = mapper.reserve(
    proposal,
    execution_id="execution:fixture",
    at_tick=0,
    )
    assert len(reservations) == 2
    tilt_reservation = reservations[0]
    extension_reservation = reservations[1]
    print(f"  reservations after explicit reserve: {len(mapper.reservations(at_tick=0))}")
    _show(mapper.propose(request, at_tick=0))
    other = replace(request, origin=replace(request.origin, task_id="task:other", envelope_id="envelope:other"))
    _show(mapper.propose(other, at_tick=0))
    print("  Both targets share one task/envelope. No motor executor was installed.")

    _section(6, "BOUNDED REFINEMENT / NO DRIFT OR LEASE RENEWAL")
    mapper.update_feedback(later, at_tick=1)
    revised = mapper.refine(tilt_reservation, endpoint=17.5, at_tick=1)
    assert isinstance(revised.current.target, BodyRelativeTargetV1)
    print(
        f"  original endpoint=18.0; refined endpoint={revised.current.target.endpoint:.1f};"
        f" revision={revised.current.target.revision}; revision event={revised.updated_tick}"
    )
    print(f"  initial basis remains 30.0; original expiry remains tick {revised.current.expires_at_tick}")
    _expect_rejection("retained old reservation", lambda: mapper.validate_reservation(tilt_reservation, at_tick=1))
    _expect_rejection("endpoint outside ORIGINAL [17,19] band", lambda: mapper.refine(revised, endpoint=16.5, at_tick=2))
    assert revised.current.expires_at_tick == 8

    _section(7, "CANCEL ONE AXIS / OTHER AXIS STILL RESERVED / FINITE EXPIRY")
    cancelled = mapper.cancel(revised, at_tick=2)
    assert cancelled.status == "cancelled"
    assert mapper.reservations(at_tick=2) == (extension_reservation,)
    print("  orientation cancelled; extension reservation retained")
    print(f"  no new task output: tick 7 live={len(mapper.reservations(at_tick=7))}; tick 8 live={len(mapper.reservations(at_tick=8))}")
    expired = mapper.expire(at_tick=8)
    assert len(expired) == 1 and expired[0].status == "expired"
    _expect_rejection("old extension permission", lambda: mapper.validate_reservation(extension_reservation, at_tick=8))

    _section(8, "REREADING IS NOT FRESH SENSING / EXPLICIT MISSING FEEDBACK")
    mapper = _configured(first)
    print(f"  reread at tick 2: {mapper.update_feedback(first, at_tick=2)}; acquisition age={mapper.body_view(at_tick=2)['age_ticks']}")
    print(f"  tick 3 view={mapper.body_view(at_tick=3)['status']}")
    _show(mapper.propose(request, at_tick=3))
    mapper = _configured(first)
    mapper.update_feedback(None, at_tick=1)
    print(f"  explicit missing report: view={mapper.body_view(at_tick=1)['status']}")
    _show(mapper.propose(request, at_tick=1))

    _section(9, "FUTURE / WRONG-GENERATION INPUT AND COPIED PROPOSAL REJECTED")
    mapper = _configured(first)
    proposal = mapper.propose(request, at_tick=0)
    _expect_rejection("future reading", lambda: mapper.update_feedback(replace(first, available_tick=2), at_tick=0))
    _expect_rejection(
        "wrong generation",
        lambda: mapper.update_feedback(replace(first, stream=MotorStreamRefV1(first.stream.stream_id, 2)), at_tick=0),
    )
    _expect_rejection("copied proposal", lambda: mapper.reserve(replace(proposal), execution_id="execution:fixture", at_tick=0))
    assert mapper.body_view(at_tick=0)["feedback"] == first.as_dict()
    assert mapper.reservations(at_tick=0) == ()

    _section(10, "SCOPE / BOUNDED STATE / NO COGNITIVE OR PHYSICAL SIDE EFFECT")
    print("  one current sensor record; one pending proposal; at most two reserved axes")
    print("  supplied task only; Righting selection / SMP control / learning: not run")
    print("  motor commands issued: 0; no WNM or PNM created or modified")
    print(f"  RNG unchanged: {random.getstate() == original_rng}; finite JSON export: True")
    assert random.getstate() == original_rng
    json.dumps(proposal.as_dict(), allow_nan=False)
    print("\nBODYMAP TARGET CHECKS PASSED -- H4 target execution remains next.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
