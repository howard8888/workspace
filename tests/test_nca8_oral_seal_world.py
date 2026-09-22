"""Physical closure and independent seal sensing without cognition or target access."""
from dataclasses import replace
import math

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorStreamRefV1
from cca8_support_world import (
    MotorWorldV1, MotorBodyStateV1, MotorWorldProfileV1, MotorWorldPerturbationV1,
    OralWorldProfileV1, OralWorldPerturbationV1, OralSealWorldProfileV1, OralSealWorldStateV1, OralClosurePerturbationV1,
    PlanarWorldProfileV1, PlanarObjectV1, PlanarPerturbationV1,
)

SURFACE = PlanarObjectV1("surface", (0.1, 0.0), 0.004)


def world(*, seal=None, oral=None, planar=None, physical=None):
    return MotorWorldV1(MotorStreamRefV1("seal_world", 1), physical or MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1)),
                        planar_profile=planar or PlanarWorldProfileV1(),
                        oral_profile=oral or OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,)),
                        oral_seal_profile=seal or OralSealWorldProfileV1(sealable_surfaces=(SURFACE,)))


def advance(w, drive=1.0):
    return w.step(MotorCommandV1(w.stream, w.tick + 1, w.tick, oral_closure_drive=drive))


def test_physical_seal_precedes_delivered_seal_but_is_not_initial_touch():
    w = world()
    assert w.observe().oral.contact and not w.observe().oral_seal.sealed
    for tick in range(5):
        advance(w)
        assert w.oral_seal_body.closure == pytest.approx((tick + 1) * 0.1)
    assert w.tick == 5 and w.oral_seal_body.sealed
    assert not w.observe().oral_seal.sealed and w.observe().event_tick == 4
    w.step()
    assert w.observe().oral_seal.sealed and w.observe().event_tick == 5


@pytest.mark.parametrize("tactile,sealable", [(False, True), (True, False), (False, False), (True, True)])
def test_closed_coordinate_does_not_manufacture_surface_seal(tactile, sealable):
    w = world(oral=OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,) if tactile else ()),
              seal=OralSealWorldProfileV1(sealable_surfaces=(SURFACE,) if sealable else ()))
    for _ in range(6):
        advance(w)
    assert w.oral_seal_body.closure == pytest.approx(0.6)
    assert w.oral_seal_body.sealed == (tactile and sealable)


@pytest.mark.parametrize("closure", [0.0, 0.49, 0.5, 0.6, 1.0])
def test_seal_derived_at_reset_not_from_step_count(closure):
    w = world(seal=OralSealWorldProfileV1(initial_closure=closure, sealable_surfaces=(SURFACE,)))
    assert w.oral_seal_body.sealed == (closure >= 0.5)
    assert w.observe().event_tick == w.observe().available_tick == 0


@pytest.mark.parametrize("closure_available,seal_available", [(True, True), (False, True), (True, False), (False, False)])
def test_missing_sensors_do_not_change_physics(closure_available, seal_available):
    w = world(seal=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,),
                                        closure_available=closure_available, seal_available=seal_available))
    assert w.oral_seal_body.sealed
    assert w.observe().oral_seal.closure == (0.6 if closure_available else None)
    assert w.observe().oral_seal.sealed is (True if seal_available else None)


@pytest.mark.parametrize("mode", ["body", "reach"])
def test_neutral_does_not_preserve_seal_against_external_motion(mode):
    planar = PlanarWorldProfileV1(perturbations=(PlanarPerturbationV1(0, 1, velocity=(0.2, 0)),)) if mode == "body" else None
    oral = (OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,),
                              perturbations=(OralWorldPerturbationV1(0, 1, 0.2),)) if mode == "reach" else None)
    w = world(seal=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,)), planar=planar, oral=oral)
    assert w.oral_seal_body.sealed
    w.step()
    assert w.oral_seal_body.closure == 0.6 and not w.oral_seal_body.sealed


@pytest.mark.parametrize("drive", [-1.0, 0.0, 1.0])
def test_signed_motor_and_saturation_are_finite(drive):
    w = world(seal=OralSealWorldProfileV1(initial_closure=0.5))
    for _ in range(20):
        advance(w, drive)
    assert w.oral_seal_body.closure == pytest.approx(0.0 if drive < 0 else 1.0 if drive > 0 else 0.5)


@pytest.mark.parametrize("failure", ["motor", "support"])
def test_unavailable_competence_or_support_does_not_execute(failure):
    w = world(seal=OralSealWorldProfileV1(motor_enabled=failure != "motor"),
              physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), surface_present=failure != "support"))
    advance(w)
    assert w.oral_seal_body.closure == 0.0


def test_fixed_forcing_can_open_even_disabled_motor_and_no_command():
    w = world(seal=OralSealWorldProfileV1(initial_closure=0.6, motor_enabled=False,
                                        sealable_surfaces=(SURFACE,), perturbations=(OralClosurePerturbationV1(0, 2, -2.0),)))
    w.step(); w.step()
    assert w.oral_seal_body.closure == pytest.approx(0.4) and not w.oral_seal_body.sealed


def test_dropout_does_not_prevent_unobserved_physical_seal():
    w = world(physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1),
                                          perturbations=(MotorWorldPerturbationV1(0, 12, drop_feedback=True),)))
    for _ in range(6):
        assert advance(w) == ()
    assert w.oral_seal_body.sealed and w.observe().sample_id == 1 and not w.observe().oral_seal.sealed


def test_foreign_replayed_and_missing_profile_commands_fail_before_effect():
    w = world()
    command = MotorCommandV1(w.stream, 1, 0, oral_closure_drive=1)
    advance(w)
    before = (w.tick, w.oral_seal_body)
    with pytest.raises(ValueError):
        w.step(command)
    assert (w.tick, w.oral_seal_body) == before
    w.reset()
    with pytest.raises(ValueError):
        w.step(command)
    assert w.tick == 0 and w.oral_seal_body.closure == 0
    old = MotorWorldV1(MotorStreamRefV1("old", 1))
    with pytest.raises(ValueError):
        old.step(MotorCommandV1(old.stream, 1, 0, oral_closure_drive=0))
    assert old.tick == 0


@pytest.mark.parametrize("kwargs", [{"initial_closure": True}, {"initial_closure": 1.1}, {"initial_closure": math.nan},
                                    {"motor_enabled": 1}, {"closure_available": 0}, {"seal_available": "yes"},
                                    {"sealable_surfaces": [SURFACE]}, {"sealable_surfaces": (SURFACE,) * 9},
                                    {"sealable_surfaces": (PlanarObjectV1("x", (0, 0), 0.1),)},
                                    {"perturbations": (OralClosurePerturbationV1(2, 4, 1), OralClosurePerturbationV1(3, 5, 1))}])
def test_seal_profile_rejects_invalid_controls(kwargs):
    with pytest.raises((TypeError, ValueError)):
        OralSealWorldProfileV1(**kwargs)


@pytest.mark.parametrize("args", [(0, 0, 1), (-1, 2, 1), (False, 1, 1), (0, 1, math.inf), (0, 1, 4.1)])
def test_invalid_closure_forcing_rejected(args):
    with pytest.raises((TypeError, ValueError)):
        OralClosurePerturbationV1(*args)


def test_seal_profile_requires_oral_and_planar_profiles():
    with pytest.raises(TypeError):
        MotorWorldV1(MotorStreamRefV1("bad", 1), oral_seal_profile=OralSealWorldProfileV1())


def test_external_state_has_no_milestone_and_physical_seal_must_be_boolean():
    assert OralSealWorldStateV1(0.6, True).as_dict() == {"closure": 0.6, "sealed": True}
    with pytest.raises(TypeError):
        OralSealWorldStateV1(0.6, 1)
