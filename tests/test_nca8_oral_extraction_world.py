"""L-A physical tests use disclosed low-level drives, not a hidden Suckle policy."""
from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import json
import math
import random

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, OralExtractionFeedbackV1, PlanarDriveV1
from cca8_support_world import (
    MotorWorldV1, MotorWorldProfileV1, MotorBodyStateV1, MotorWorldPerturbationV1,
    PlanarWorldProfileV1, PlanarObjectV1, PlanarDetailObjectV1, PlanarPerturbationV1,
    OralWorldProfileV1, OralWorldPerturbationV1, OralSealWorldProfileV1, OralClosurePerturbationV1,
    OralExtractionWorldProfileV1, OralExtractionWorldStateV1,
)

SURFACE = PlanarObjectV1("physical_surface", (0.1, 0.0), 0.03)


def world(*, extraction=None, physical=None, planar=None, oral=None, seal=None, enabled=True):
    """Start in a declared physically supported seal; this is not a selected latch."""
    return MotorWorldV1(
        MotorStreamRefV1("extraction_world", 1),
        physical or MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0), sensor_delay_ticks=0),
        planar_profile=planar or PlanarWorldProfileV1(),
        oral_profile=oral or OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,)),
        oral_seal_profile=seal or OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,)),
        oral_extraction_profile=(extraction or OralExtractionWorldProfileV1(initial_supply_units=2.0, supplying_surface=SURFACE))
        if enabled else None,
    )


def advance(w, drive=1.0, **changes):
    """One explicitly supplied drive interval; no target lease or IP is asserted."""
    return w.step(MotorCommandV1(w.stream, w.tick + 1, w.tick, oral_extraction_drive=drive, **changes))


def state(w):
    """Snapshot immutable owned values, including ordering and delayed feedback."""
    return vars(w).copy()


def test_seal_alone_is_not_extraction_or_milk_and_reset_has_no_interval():
    w = world()
    assert w.oral_seal_body.sealed and w.oral_body.contact
    assert w.oral_extraction_body == OralExtractionWorldStateV1(0, 2, 0, 0)
    assert w.observe().oral_extraction == OralExtractionFeedbackV1(0, None, None)
    assert w.observe().sample_id == 1 and w.tick == 0
    for tick in range(10):
        result = w.step()
        assert result[0].oral_extraction == OralExtractionFeedbackV1(0, 0, tick)
        assert w.oral_extraction_body.transferred_milk_units == 0
        assert w.oral_seal_body.sealed


@pytest.mark.parametrize("drive", [-1.0, -0.5, 0.0, 0.5, 1.0])
def test_signed_drive_changes_only_actual_stroke_with_transfer_only_on_positive_displacement(drive):
    w = world(extraction=OralExtractionWorldProfileV1(0.5, 2, SURFACE))
    old_body, old_planar, old_oral, old_seal = w.body, w.planar_body, w.oral_body, w.oral_seal_body
    sample = advance(w, drive)[0]
    expected_stroke = 0.5 + drive * 2 * 0.05
    expected_milk = max(0.0, expected_stroke - 0.5)
    assert w.oral_extraction_body.stroke == pytest.approx(expected_stroke)
    assert w.oral_extraction_body.interval_milk_units == pytest.approx(expected_milk)
    assert sample.oral_extraction.milk_transferred_units == pytest.approx(expected_milk)
    assert w.oral_extraction_body.remaining_supply_units == pytest.approx(2 - expected_milk)
    assert (w.body, w.planar_body, w.oral_body, w.oral_seal_body) == (old_body, old_planar, old_oral, old_seal)
    assert w.tick == 1 and sample.event_tick == 1 and sample.oral_extraction.interval_start_tick == 0


def test_saturation_then_return_and_extract_is_motion_not_a_call_or_success_counter():
    held, repeated = world(), world()
    for _ in range(20):
        advance(held)
    assert held.oral_extraction_body.stroke == 1
    assert held.oral_extraction_body.transferred_milk_units == pytest.approx(1)
    assert held.oral_extraction_body.interval_milk_units == 0
    for drive in (1.0,) * 10 + (-1.0,) * 10 + (1.0,) * 10:
        before = repeated.oral_extraction_body.transferred_milk_units
        advance(repeated, drive)
        if drive < 0:
            assert repeated.oral_extraction_body.transferred_milk_units == before
    assert repeated.oral_extraction_body.transferred_milk_units == pytest.approx(2)
    assert repeated.oral_extraction_body.remaining_supply_units == pytest.approx(0)
    # Neutral never repeats the previous drive, even after an incomplete stroke.
    partial = world(); advance(partial, 0.5)
    before = partial.oral_extraction_body
    partial.step()
    assert partial.oral_extraction_body.stroke == before.stroke
    assert partial.oral_extraction_body.transferred_milk_units == before.transferred_milk_units
    assert partial.oral_extraction_body.interval_milk_units == 0


@pytest.mark.parametrize("reason", ["disabled", "no_support", "low_load", "tilted", "saturated"])
def test_same_drive_without_actual_motion_cannot_transfer(reason):
    extraction = OralExtractionWorldProfileV1(initial_stroke=1.0 if reason == "saturated" else 0.0,
                                              initial_supply_units=2, supplying_surface=SURFACE, motor_enabled=reason != "disabled")
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(20 if reason == "tilted" else 0,
                                                                0.3 if reason == "low_load" else 1),
                                    surface_present=reason != "no_support", sensor_delay_ticks=0)
    w = world(extraction=extraction, physical=physical)
    for _ in range(4):
        advance(w)
    assert w.oral_extraction_body.stroke == extraction.initial_stroke
    assert w.oral_extraction_body.transferred_milk_units == 0
    assert w.oral_extraction_body.remaining_supply_units == 2


@pytest.mark.parametrize("supply", [0.0, 0.03, 0.15, 2.0, 1_000_000.0])
def test_supply_conservation_exhaustion_and_no_refill(supply):
    w = world(extraction=OralExtractionWorldProfileV1(initial_supply_units=supply, supplying_surface=SURFACE))
    measured = []
    for i in range(80):
        before = w.oral_extraction_body
        sample = advance(w, 1 if (i // 10) % 2 == 0 else -1)[0]
        after = w.oral_extraction_body
        assert after.remaining_supply_units >= 0 and 0 <= after.stroke <= 1
        assert after.transferred_milk_units + after.remaining_supply_units == pytest.approx(supply)
        assert after.interval_milk_units <= max(0, after.stroke - before.stroke) + 1e-12
        assert after.transferred_milk_units - before.transferred_milk_units == pytest.approx(after.interval_milk_units)
        measured.append(sample.oral_extraction.milk_transferred_units)
    assert sum(measured) == pytest.approx(min(supply, 4.0))
    assert w.oral_extraction_body.transferred_milk_units == pytest.approx(min(supply, 4.0))


@pytest.mark.parametrize("condition", ["dry", "displaced_supplier", "tactile_missing", "seal_missing", "open", "label_only"])
def test_actual_contact_seal_and_supply_are_distinct_not_descriptors(condition):
    supplier = PlanarObjectV1("other_supply", (0.3, 0), 0.03) if condition == "displaced_supplier" else SURFACE
    extraction = OralExtractionWorldProfileV1(initial_supply_units=0 if condition in {"dry", "label_only"} else 2,
                                              supplying_surface=None if condition == "label_only" else supplier)
    oral = OralWorldProfileV1(initial_extension_metres=0.1, surfaces=() if condition == "tactile_missing" else (SURFACE,))
    seal = OralSealWorldProfileV1(initial_closure=0.4 if condition == "open" else 0.6,
                                  sealable_surfaces=() if condition == "seal_missing" else (SURFACE,))
    planar = PlanarWorldProfileV1(objects=(PlanarDetailObjectV1("looks_like_food", (0.1, 0.0), descriptor="feeding"),))
    w = world(extraction=extraction, oral=oral, seal=seal, planar=planar)
    for _ in range(3):
        advance(w)
    assert w.oral_extraction_body.stroke == pytest.approx(0.3)
    assert w.oral_extraction_body.transferred_milk_units == 0


def test_wet_and_dry_fixed_inputs_change_transfer_not_touch_seal_or_motion():
    wet = world(); dry = world(extraction=OralExtractionWorldProfileV1(supplying_surface=SURFACE))
    for _ in range(8):
        advance(wet); advance(dry)
        assert wet.oral_seal_body == dry.oral_seal_body and wet.oral_body == dry.oral_body
        assert wet.oral_extraction_body.stroke == dry.oral_extraction_body.stroke
    assert wet.oral_extraction_body.transferred_milk_units == pytest.approx(0.8)
    assert dry.oral_extraction_body.transferred_milk_units == 0


@pytest.mark.parametrize("movement", ["body", "reach", "yaw", "closure", "support", "tilt"])
def test_contact_or_support_loss_stops_transfer_without_erasing_previous_effect(movement):
    planar = PlanarWorldProfileV1(perturbations=(PlanarPerturbationV1(1, 2, velocity=(1, 0)),)) if movement == "body" else None
    if movement == "yaw":
        planar = PlanarWorldProfileV1(perturbations=(PlanarPerturbationV1(1, 2, heading_rate=180),))
    oral = OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,),
                              perturbations=(OralWorldPerturbationV1(1, 2, 1),)) if movement == "reach" else None
    seal = OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,),
                                  perturbations=(OralClosurePerturbationV1(1, 2, -4),)) if movement == "closure" else None
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=0,
                                    perturbations=(MotorWorldPerturbationV1(1, 2, remove_support=True),)) if movement == "support" else None
    if movement == "tilt":
        physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(10, 1), sensor_delay_ticks=0)
    # Smaller disks ensure yaw loss; use the same surfaces in all geometry layers.
    disk = PlanarObjectV1("small_contact", (0.1, 0), 0.005)
    oral = replace(oral or OralWorldProfileV1(initial_extension_metres=0.1), surfaces=(disk,))
    seal = replace(seal or OralSealWorldProfileV1(initial_closure=0.6), sealable_surfaces=(disk,))
    w = world(planar=planar, oral=oral, seal=seal, physical=physical,
              extraction=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=disk))
    advance(w)
    prior = w.oral_extraction_body.transferred_milk_units
    assert prior > 0
    advance(w, orientation_drive=1 if movement == "tilt" else 0)
    assert w.oral_extraction_body.interval_milk_units == 0
    assert w.oral_extraction_body.transferred_milk_units == prior


@pytest.mark.parametrize("entry", ["body", "reach", "closure"])
def test_new_endpoint_contact_does_not_retroactively_credit_the_interval(entry):
    disk = PlanarObjectV1("small", (0.1, 0), 0.002)
    planar = PlanarWorldProfileV1(initial_position=(-0.01, 0),
                                  perturbations=(PlanarPerturbationV1(0, 1, velocity=(0.2, 0)),)) if entry == "body" else None
    oral = OralWorldProfileV1(initial_extension_metres=0.09 if entry == "reach" else 0.1, surfaces=(disk,),
                              perturbations=(OralWorldPerturbationV1(0, 1, 0.2),) if entry == "reach" else ())
    seal = OralSealWorldProfileV1(initial_closure=0.45 if entry == "closure" else 0.6, sealable_surfaces=(disk,))
    w = world(planar=planar, oral=oral, seal=seal,
              extraction=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=disk))
    assert not w.oral_seal_body.sealed
    advance(w, oral_closure_drive=1 if entry == "closure" else None)
    assert w.oral_seal_body.sealed
    assert w.oral_extraction_body.stroke > 0 and w.oral_extraction_body.interval_milk_units == 0
    advance(w)
    assert w.oral_extraction_body.interval_milk_units == pytest.approx(0.1)


def test_yaw_wrapping_does_not_create_a_false_full_rotation_or_release_supply():
    disk = PlanarObjectV1("rear", (-0.1, 0), 0.03)
    w = world(planar=PlanarWorldProfileV1(initial_heading=179, perturbations=(PlanarPerturbationV1(0, 1, heading_rate=40),)),
              oral=OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(disk,)),
              seal=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(disk,)),
              extraction=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=disk))
    advance(w)
    assert w.planar_body.heading_degrees == -179
    assert w.oral_extraction_body.interval_milk_units == pytest.approx(0.1)


def test_curved_tip_path_with_contact_at_both_endpoints_is_not_assumed_inside():
    # Arc from -4.5 to+4.5 degrees bows outward from the vertical chord. This disk
    # contains both endpoints but excludes the midpoint. Endpoint-only gating would leak milk.
    reach, radius = 0.01, 0.02
    endpoint_y = reach * math.sin(math.radians(4.5))
    endpoint_x = reach * math.cos(math.radians(4.5))
    center_x = endpoint_x - math.sqrt(radius**2 - endpoint_y**2)
    disk = PlanarObjectV1("arc_chord", (center_x, 0), radius)
    assert abs(reach - center_x) > radius + 1e-12  # Independently establish the intermediate contact loss.
    w = world(planar=PlanarWorldProfileV1(initial_heading=-4.5, perturbations=(PlanarPerturbationV1(0, 1, heading_rate=180),)),
              oral=OralWorldProfileV1(initial_extension_metres=reach, surfaces=(disk,)),
              seal=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(disk,)),
              extraction=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=disk))
    assert w.oral_seal_body.sealed
    advance(w)
    assert w.oral_seal_body.sealed
    assert w.oral_extraction_body.interval_milk_units == 0


@pytest.mark.parametrize("stroke_known,milk_known", [(True, True), (False, True), (True, False), (False, False)])
def test_sensor_channel_availability_changes_knowledge_not_physics(stroke_known, milk_known):
    observed = world()
    missing = world(extraction=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=SURFACE,
                                                           stroke_available=stroke_known, milk_available=milk_known))
    for _ in range(6):
        advance(observed); advance(missing)
        assert observed.oral_extraction_body == missing.oral_extraction_body
        facet = missing.observe().oral_extraction
        assert facet.stroke == (missing.oral_extraction_body.stroke if stroke_known else None)
        assert facet.milk_transferred_units == (missing.oral_extraction_body.interval_milk_units if milk_known else None)


def test_missing_contact_seal_and_body_sensing_do_not_delete_real_transfer():
    w = world(oral=OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,), contact_available=False),
              seal=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,), seal_available=False),
              physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=0,
                                            unavailable_channels=("support_contact", "useful_loading")))
    sample = advance(w)[0]
    assert sample.oral.contact is None and sample.oral_seal.sealed is None and sample.support_contact is None
    assert sample.oral_extraction.milk_transferred_units == pytest.approx(0.1)


@pytest.mark.parametrize("delay", [0, 1, 4, 16])
def test_delay_and_reading_preserve_original_interval_not_latest_reservoir(delay):
    w = world(physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=delay))
    initial = w.observe()
    reports = []
    for _ in range(delay + 3):
        reports.extend(advance(w))
        before = state(w)
        for _ in range(10):
            json.dumps(w.observe().as_dict()); w.oral_extraction_body.as_dict(); w.visual_surface()
        assert state(w) == before and w.pending_feedback_count <= 16
    assert reports[0].event_tick == 1 and reports[0].available_tick == 1 + delay
    assert reports[0].oral_extraction.interval_start_tick == 0
    assert reports[0].oral_extraction.milk_transferred_units == pytest.approx(0.1)
    assert initial.oral_extraction.milk_transferred_units is None


def test_dropped_acquisition_is_not_delayed_accumulated_milk_or_physical_freeze():
    w = world(physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=0,
                                          perturbations=(MotorWorldPerturbationV1(0, 2, drop_feedback=True),)))
    reset = w.observe()
    assert advance(w) == () and advance(w) == ()
    assert w.observe() is reset and w.oral_extraction_body.transferred_milk_units == pytest.approx(0.2)
    sample = advance(w)[0]
    assert sample.sample_id == 4 and sample.event_tick == 3
    assert sample.oral_extraction.interval_start_tick == 2
    assert sample.oral_extraction.milk_transferred_units == pytest.approx(0.1)  # Not the unobserved 0.3 total.
    assert w.oral_extraction_body.transferred_milk_units == pytest.approx(0.3)


@pytest.mark.parametrize("dt", [0.05, 0.025, 0.01])
def test_equal_duration_uses_motion_not_number_of_calls(dt):
    w = world(physical=MotorWorldProfileV1(dt_seconds=dt, initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=0))
    intervals = round(0.5 / dt)
    for drive in [1] * intervals + [-1] * intervals + [1] * intervals:
        advance(w, drive)
    assert w.elapsed_seconds == pytest.approx(1.5)
    assert w.oral_extraction_body.stroke == pytest.approx(1)
    assert w.oral_extraction_body.transferred_milk_units == pytest.approx(2)


@pytest.mark.parametrize("bad", [True, "suckle", 1, {"oral_extraction_drive": 1}])
def test_wrong_command_types_cannot_change_any_owned_state(bad):
    w = world(); before = state(w)
    with pytest.raises(TypeError):
        w.step(bad)
    assert state(w) == before


@pytest.mark.parametrize("fault", ["stream", "generation", "future", "replayed", "past"])
def test_identity_and_order_faults_are_atomic(fault):
    w = world(); advance(w)
    c = MotorCommandV1(w.stream, 2, 1, oral_extraction_drive=1)
    if fault == "stream":
        c = replace(c, stream=MotorStreamRefV1("another", 1))
    elif fault == "generation":
        c = replace(c, stream=replace(w.stream, generation=2))
    elif fault == "future":
        c = replace(c, issued_tick=2)
    elif fault == "replayed":
        c = replace(c, command_id=1)
    else:
        c = replace(c, issued_tick=0)
    before = state(w)
    with pytest.raises(ValueError):
        w.step(c)
    assert state(w) == before


def test_absent_profile_rejects_even_zero_extraction_without_state_change():
    w = world(enabled=False); before = state(w)
    with pytest.raises(ValueError, match="extraction physical profile"):
        advance(w, 0)
    assert state(w) == before and w.oral_extraction_body is None


def test_sensor_queue_overflow_rolls_back_computed_extraction_and_supply():
    w = world()
    base = w.observe()
    # Capacity fixture, not naturally generated with the legal delay bound.
    w._pending = tuple(replace(base, sample_id=i + 2, event_tick=i + 1, available_tick=100,
                               oral_extraction=OralExtractionFeedbackV1(0, 0, i)) for i in range(16))
    w._profile = replace(w.profile, sensor_delay_ticks=16)
    before = state(w)
    with pytest.raises(OverflowError, match="staging"):
        advance(w)
    assert state(w) == before


def test_failed_measurement_leaves_commands_clock_and_physical_transfer_untouched(monkeypatch):
    w = world()
    def fail(*args, **kwargs):
        raise ValueError("controlled acquisition construction failure")
    monkeypatch.setattr(w, "_measure", fail)
    before = state(w)
    with pytest.raises(ValueError, match="controlled acquisition"):
        advance(w)
    assert state(w) == before


def test_counter_and_generation_exhaustion_leave_state_unchanged():
    w = world(); w._tick = 2**63 - 2
    before = state(w)
    with pytest.raises(OverflowError):
        w.step()
    assert state(w) == before
    w = world(); w._stream = MotorStreamRefV1("exhausted", 2**63 - 1)
    before = state(w)
    with pytest.raises(ValueError):
        w.reset()
    assert state(w) == before


def test_reset_is_a_fresh_generation_not_replayed_transfer_or_replenishment_in_place():
    w = world(physical=MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=4))
    command = MotorCommandV1(w.stream, 1, 0, oral_extraction_drive=1)
    w.step(command)
    assert w.oral_extraction_body.transferred_milk_units > 0 and w.pending_feedback_count == 1
    sample = w.reset()
    assert w.stream.generation == 2 and w.tick == 0 and w.pending_feedback_count == 0
    assert w.oral_extraction_body == OralExtractionWorldStateV1(0, 2, 0, 0)
    assert sample.oral_extraction == OralExtractionFeedbackV1(0, None, None)
    before = state(w)
    with pytest.raises(ValueError):
        w.step(command)
    assert state(w) == before


@pytest.mark.parametrize("kwargs", [
    {"initial_stroke": -0.1}, {"initial_stroke": 1.1}, {"initial_stroke": True}, {"initial_stroke": math.nan},
    {"initial_supply_units": -1}, {"initial_supply_units": 1_000_001}, {"initial_supply_units": math.inf},
    {"initial_supply_units": True}, {"initial_supply_units": 10**400}, {"initial_supply_units": 1},
    {"supplying_surface": {}}, {"supplying_surface": PlanarObjectV1("no_disk", (0, 0), 0)},
    {"supplying_surface": PlanarObjectV1("too_large", (0, 0), 0.1)},
    {"motor_enabled": 1}, {"stroke_available": 0}, {"milk_available": "yes"},
])
def test_profile_invalid_values_are_rejected(kwargs):
    with pytest.raises((TypeError, ValueError)):
        OralExtractionWorldProfileV1(**kwargs)


@pytest.mark.parametrize("kwargs", [{"stroke": True}, {"stroke": 1.1}, {"interval_milk_units": 0.1},
                                    {"interval_milk_units": math.nan}, {"remaining_supply_units": -1},
                                    {"transferred_milk_units": True}, {"transferred_milk_units": math.inf},
                                    {"remaining_supply_units": 1_000_000, "transferred_milk_units": 1}])
def test_physical_state_is_finite_bounded_and_consistent(kwargs):
    with pytest.raises((TypeError, ValueError)):
        OralExtractionWorldStateV1(**kwargs)


def test_profile_requires_existing_physical_context_and_retains_immutable_ownership():
    with pytest.raises(TypeError):
        MotorWorldV1(MotorStreamRefV1("missing", 1), oral_extraction_profile=OralExtractionWorldProfileV1())
    with pytest.raises(TypeError):
        world(extraction={"supply": 1})
    w = world()
    with pytest.raises(FrozenInstanceError):
        w.oral_extraction_body.stroke = 1
    detached = w.oral_extraction_body.as_dict(); detached["remaining_supply_units"] = 0
    assert w.oral_extraction_body.remaining_supply_units == 2


@pytest.mark.parametrize("variant", ["nominal", "delayed", "dropout", "body", "reach", "opening", "missing", "unsupported"])
def test_optional_extraction_never_changes_old_channels_or_rng(variant):
    physical = MotorWorldProfileV1(initial_body=MotorBodyStateV1(0, 1), sensor_delay_ticks=4 if variant == "delayed" else 0,
                                    surface_present=variant != "unsupported",
                                    perturbations=(MotorWorldPerturbationV1(2, 4, drop_feedback=True),) if variant == "dropout" else ())
    planar = PlanarWorldProfileV1(perturbations=(PlanarPerturbationV1(2, 5, velocity=(0.1, 0)),) if variant == "body" else ())
    oral = OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,), contact_available=variant != "missing",
                              perturbations=(OralWorldPerturbationV1(3, 5, -0.1),) if variant == "reach" else ())
    seal = OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,), seal_available=variant != "missing",
                                  perturbations=(OralClosurePerturbationV1(3, 5, -2),) if variant == "opening" else ())
    base, extended = (world(physical=physical, planar=planar, oral=oral, seal=seal, enabled=flag) for flag in (False, True))
    rng = random.getstate()
    for i in range(20):
        old = MotorCommandV1(base.stream, i + 1, i, oral_closure_drive=0.1, oral_drive=0.01,
                             translation=PlanarDriveV1(0, 0))
        a = base.step(old); b = extended.step(replace(old, oral_extraction_drive=1 if i < 10 else -1))
        assert len(a) == len(b)
        for before, after in zip(a, b):
            wire = after.as_dict(); del wire["oral_extraction"]; wire["schema"] = "body_motor_feedback_v4"
            assert wire == before.as_dict()
        assert base.body == extended.body and base.planar_body == extended.planar_body
        assert base.oral_body == extended.oral_body and base.oral_seal_body == extended.oral_seal_body
        assert base.tick == extended.tick and base.pending_feedback_count == extended.pending_feedback_count
        assert base.visual_surface() == extended.visual_surface()
    assert random.getstate() == rng


def test_wire_never_exposes_supply_donor_or_cumulative_consumption():
    w = world(); sample = advance(w)[0]
    wire = json.dumps(sample.as_dict())
    for forbidden in ["physical_surface", "remaining_supply", "transferred_milk_units", "nourishment", "reward", "task", "milestone"]:
        assert forbidden not in wire
    assert MotorFeedbackV1.from_dict(sample.as_dict()) == sample


def test_extraction_physical_context_is_keyword_only_and_computation_does_not_mutate_world():
    """Reject a positional state bundle before mutation; named inputs retain the actual step result."""
    w = world()
    command = MotorCommandV1(w.stream, w.tick + 1, w.tick, oral_extraction_drive=1.0)
    before = state(w)
    with pytest.raises(TypeError):
        w._advance_oral_extraction(command, w.body, w.planar_body, w.oral_body, w.oral_seal_body, True)
    assert state(w) == before
    calculated = w._advance_oral_extraction(
        command, body=w.body, planar=w.planar_body, oral=w.oral_body, seal=w.oral_seal_body, surface_present=True,
    )
    assert state(w) == before
    sample = w.step(command)[0]
    assert w.oral_extraction_body == calculated
    assert calculated.interval_milk_units == pytest.approx(0.1)
    assert sample.oral_extraction.milk_transferred_units == calculated.interval_milk_units
