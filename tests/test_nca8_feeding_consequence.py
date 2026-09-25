"""M body/measurement tests: supplied drives are fixtures, not selected Suckle.

Numerical examples distinguish receipt, later uptake, measurement and task
meaning. The body provider is tested without any cognitive owner or evaluator.
"""
from dataclasses import FrozenInstanceError, replace
import json
import math

import pytest

from cca8_motor_contracts import FeedingDeficitFeedbackV1, MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from cca8_support_world import (
    FeedingConsequenceProfileV1, FeedingConsequenceStateV1, MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1,
    OralExtractionWorldProfileV1, OralSealWorldProfileV1, OralWorldProfileV1, PlanarObjectV1, PlanarWorldProfileV1,
)
from nca8_feeding_state import FeedingNeedStateV1
from nca8_maps import create_posture_support_map_library_v1
from nca8_sensory import Nca8BodySensoryModuleV1

SURFACE = PlanarObjectV1("body_supply", (0.1, 0.0), 0.03)


def world(*, body=None, milk=True, enabled=True, motor=True):
    return MotorWorldV1(
        MotorStreamRefV1("M_physical_fixture", 1),
        MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0), sensor_delay_ticks=0),
        planar_profile=PlanarWorldProfileV1(),
        oral_profile=OralWorldProfileV1(initial_extension_metres=0.1, surfaces=(SURFACE,)),
        oral_seal_profile=OralSealWorldProfileV1(initial_closure=0.6, sealable_surfaces=(SURFACE,)),
        oral_extraction_profile=OralExtractionWorldProfileV1(initial_supply_units=2, supplying_surface=SURFACE,
                                                            motor_enabled=motor, milk_available=milk),
        feeding_consequence_profile=(body or FeedingConsequenceProfileV1()) if enabled else None,
    )


def step(w, drive=0.0):
    return w.step(MotorCommandV1(w.stream, w.tick + 1, w.tick, oral_extraction_drive=drive))[0]


def sensory():
    return Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())


def read(owner, sample, *, cycle, cutoff):
    return owner.apply_feeding_evidence(sample, stream=MotorStreamRefV1("M_physical_fixture", 1),
                                        cycle_id=cycle, cutoff_tick=cutoff)


def test_receipt_cannot_be_processed_in_same_interval_and_neutral_time_can_process_it():
    w = world()
    assert w.feeding_consequence_body == FeedingConsequenceStateV1(0.0, 0.5)
    first = step(w, 1.0)
    assert first.oral_extraction.milk_transferred_units == pytest.approx(0.10)
    assert first.feeding_deficit.deficit_units == 0.5
    assert w.feeding_consequence_body.pending_units == pytest.approx(0.10)
    second = step(w)
    assert second.oral_extraction.milk_transferred_units == 0
    assert second.feeding_deficit.deficit_units == pytest.approx(0.475)
    assert w.feeding_consequence_body.pending_units == pytest.approx(0.075)
    for _ in range(8):
        step(w)
    assert w.oral_extraction_body.transferred_milk_units == pytest.approx(0.10)
    assert w.feeding_consequence_body.deficit_units == pytest.approx(0.40)
    assert w.feeding_consequence_body.pending_units == 0


@pytest.mark.parametrize("rate", [0.0, 0.1, 0.5, 8.0])
def test_intake_conservation_saturation_and_positive_time_not_call_count(rate):
    w = world(body=FeedingConsequenceProfileV1(initial_deficit_units=2.0, uptake_units_per_second=rate))
    for i in range(40):
        step(w, 1.0 if i % 2 == 0 else -1.0)
    state = w.feeding_consequence_body
    processed = 2.0 - state.deficit_units
    assert processed + state.pending_units == pytest.approx(w.oral_extraction_body.transferred_milk_units)
    assert state.deficit_units >= 0
    assert w.tick == 40
    before = vars(w).copy()
    for _ in range(10):
        w.observe(); w.feeding_consequence_body; w.oral_extraction_body
    assert vars(w) == before
    if rate == 0:
        assert processed == 0 and state.deficit_units == 2.0


@pytest.mark.parametrize("milk,internal", [(True, True), (True, False), (False, True), (False, False)])
def test_sensors_change_only_measurement_under_identical_supplied_commands(milk, internal):
    control = world()
    modified = world(milk=milk, body=FeedingConsequenceProfileV1(sensor_available=internal))
    for drive in (1.0, -1.0, 1.0, -1.0, 0.0, 0.0):
        a, b = step(control, drive), step(modified, drive)
        assert control.feeding_consequence_body == modified.feeding_consequence_body
        assert control.oral_extraction_body == modified.oral_extraction_body
        assert (b.feeding_deficit.deficit_units is None) is not internal
        assert (b.oral_extraction.milk_transferred_units is None) is not milk
        assert a.sample_id == b.sample_id and a.event_tick == b.event_tick


def test_command_without_executed_intake_cannot_nourish():
    w = world(motor=False)
    for _ in range(40):
        step(w, 1.0)
    assert w.feeding_consequence_body == FeedingConsequenceStateV1(0.0, 0.5)


def test_old_profile_disabled_preserves_v5_packet_and_same_extraction_physics():
    off, on = world(enabled=False), world()
    for drive in (1.0, -1.0, 0.0, 1.0):
        old, new = step(off, drive), step(on, drive)
        assert off.oral_extraction_body == on.oral_extraction_body
        assert old.as_dict()["schema"] == "body_motor_feedback_v5"
        assert "feeding_deficit" not in old.as_dict()
        assert replace(new, feeding_deficit=None) == old


def test_optional_sensor_schema_roundtrip_is_strict_and_contains_no_hidden_pool_or_completion():
    w = world()
    packet = step(w, 1.0).as_dict()
    assert packet["schema"] == "body_motor_feedback_v6"
    assert set(packet["feeding_deficit"]) == {"deficit_units", "units"}
    assert MotorFeedbackV1.from_dict(json.loads(json.dumps(packet))).as_dict() == packet
    for forbidden in ("pending_units", "supply", "fed", "nourished", "reward", "task_complete", "rest"):
        bad = json.loads(json.dumps(packet)); bad["feeding_deficit"][forbidden] = True
        with pytest.raises((ValueError, TypeError)):
            MotorFeedbackV1.from_dict(bad)
    bad = json.loads(json.dumps(packet)); bad["feeding_deficit"]["units"] = "calories"
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(bad)


@pytest.mark.parametrize("value", [True, -0.1, 8.01, math.nan, math.inf, "0.5", [], {}])
def test_deficit_measurement_rejects_invalid_values(value):
    with pytest.raises((ValueError, TypeError)):
        FeedingDeficitFeedbackV1(value)


@pytest.mark.parametrize("field", ["initial_deficit_units", "uptake_units_per_second", "initial_pending_units"])
@pytest.mark.parametrize("value", [True, -0.1, 8.01, math.nan, math.inf])
def test_physical_profile_has_explicit_finite_numerical_bounds(field, value):
    with pytest.raises((ValueError, TypeError)):
        FeedingConsequenceProfileV1(**{field: value})


@pytest.mark.parametrize("ticks", [[1], (True,), (-1,), (161,), (2, 1), (1, 1)])
def test_dropout_schedule_is_fixed_typed_and_bounded(ticks):
    with pytest.raises((ValueError, TypeError)):
        FeedingConsequenceProfileV1(unavailable_ticks=ticks)


def test_reset_reinitializes_body_consequence_and_generation_but_not_profile():
    w = world(body=FeedingConsequenceProfileV1(initial_pending_units=0.2))
    step(w, 1.0); step(w)
    original = w.stream
    w.reset()
    assert w.stream.generation == original.generation + 1 and w.tick == 0
    assert w.feeding_consequence_body == FeedingConsequenceStateV1(0.2, 0.5)
    assert w.observe().feeding_deficit.deficit_units == 0.5


def test_failed_command_changes_no_body_clock_or_intake():
    w = world(); before = vars(w).copy()
    wrong = MotorCommandV1(MotorStreamRefV1("foreign", 1), 1, 0, oral_extraction_drive=1.0)
    with pytest.raises(ValueError):
        w.step(wrong)
    assert vars(w) == before


def test_body_sensor_not_F_maintains_need_without_touching_support_map():
    w, owner = world(), sensory()
    support = owner.map_library.current_state()
    evidence = read(owner, w.observe(), cycle=1, cutoff=0)
    assert owner.feeding_need is evidence and evidence.current and evidence.new_acquisition
    assert owner.map_library.current_state() is support
    assert evidence.as_dict()["owner"] == "body_sensory" and evidence.deficit_units == 0.5
    assert not hasattr(owner, "feeding_complete")
    with pytest.raises(FrozenInstanceError):
        evidence.deficit_units = 0


def test_duplicate_read_never_refreshes_event_time_and_stale_low_is_not_current():
    w, owner = world(body=FeedingConsequenceProfileV1(initial_deficit_units=0)), sensory()
    sample = w.observe()
    first = read(owner, sample, cycle=1, cutoff=0)
    duplicate = read(owner, sample, cycle=2, cutoff=4)
    stale = read(owner, sample, cycle=3, cutoff=9)
    assert first.new_acquisition and not duplicate.new_acquisition and not stale.new_acquisition
    assert duplicate.event_tick == stale.event_tick == 0
    assert duplicate.current and not stale.current and stale.deficit_units == 0


def test_missing_and_unavailable_evidence_are_never_zero_or_backfilled():
    w, owner = world(), sensory()
    read(owner, w.observe(), cycle=1, cutoff=0)
    missing = read(owner, None, cycle=2, cutoff=4)
    assert missing.deficit_units is None and missing.sample_id is None and not missing.current
    w = world(body=FeedingConsequenceProfileV1(sensor_available=False))
    owner = sensory(); unavailable = read(owner, w.observe(), cycle=1, cutoff=0)
    assert unavailable.sample_id == 1 and unavailable.deficit_units is None and not unavailable.current


@pytest.mark.parametrize("change", ["foreign", "future", "changed_duplicate", "reversed_event", "repeated_cycle", "backward_cutoff"])
def test_sensory_invalid_input_rejects_before_state_mutation(change):
    w, owner = world(), sensory()
    sample = step(w, 1.0)
    read(owner, sample, cycle=1, cutoff=1)
    cycle, tick, bad = 2, 4, sample
    if change == "foreign":
        bad = replace(sample, stream=MotorStreamRefV1("M_physical_fixture", 2))
    elif change == "future":
        bad = replace(sample, available_tick=5)
    elif change == "changed_duplicate":
        bad = replace(sample, feeding_deficit=FeedingDeficitFeedbackV1(0))
    elif change == "reversed_event":
        bad = replace(sample, sample_id=sample.sample_id+1)
    elif change == "repeated_cycle":
        cycle = 1
    else:
        tick = 0
    before = vars(owner).copy()
    with pytest.raises((ValueError, TypeError)):
        read(owner, bad, cycle=cycle, cutoff=tick)
    assert vars(owner) == before


@pytest.mark.parametrize("change", [dict(cycle_id=True), dict(cutoff_tick=-1), dict(event_tick=None),
                                    dict(available_tick=10), dict(sample_id=None), dict(deficit_units=math.nan)])
def test_shared_record_cannot_carry_fabricated_time_or_number(change):
    context = FeedingNeedStateV1(MotorStreamRefV1("need",1), 1, 4, 1, 0, 0, 0.5, True)
    with pytest.raises((ValueError, TypeError)):
        replace(context, **change)
