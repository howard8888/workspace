"""L-A v5 wire evidence is interval-specific, bounded and free of task authority."""
from __future__ import annotations

import copy
from dataclasses import FrozenInstanceError, replace
import json
import math

import pytest

from cca8_motor_contracts import (
    MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, OralExtractionFeedbackV1,
    OralFeedbackV1, OralSealFeedbackV1, PlanarDriveV1, PlanarFeedbackV1, admit_motor_feedback_batch_v1,
)

STREAM = MotorStreamRefV1("extraction_contract", 1)
BAD_NUMBERS = [True, "0.5", [], {}, math.nan, math.inf, -math.inf, 10**400, -0.001, 1.001]


def feedback(event=1, **changes):
    """Construct an actual single-interval schema fixture, not a feeding verdict."""
    value = MotorFeedbackV1(
        STREAM, event + 1, event, event + 1, 0.0, 1.0, True, 1.0, 0.0,
        planar=PlanarFeedbackV1("scene_xy:fixture", (0.0, 0.0), 0.0, False),
        oral=OralFeedbackV1(0.1, True), oral_seal=OralSealFeedbackV1(0.6, True),
        oral_extraction=OralExtractionFeedbackV1(0.2, 0.1 if event else None, event - 1 if event else None),
    )
    return replace(value, **changes)


@pytest.mark.parametrize("drive", [-1.0, 0.0, 0.4, 1.0])
@pytest.mark.parametrize("closure", [None, -0.3, 0.0, 0.6])
@pytest.mark.parametrize("reach", [None, 0.2])
@pytest.mark.parametrize("translation", [None, PlanarDriveV1(0.0, 0.0), PlanarDriveV1(0.1, 0.0)])
def test_v5_command_round_trip_and_neutral_include_every_channel(drive, closure, reach, translation):
    command = MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=drive, oral_closure_drive=closure,
                             oral_drive=reach, translation=translation)
    wire = command.as_dict()
    assert wire["schema"] == "body_motor_command_v5"
    assert set(wire) == {"schema", "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive",
                         "translation", "oral_drive", "oral_closure_drive", "oral_extraction_drive"}
    assert MotorCommandV1.from_dict(json.loads(json.dumps(wire, allow_nan=False))) == command
    assert command.is_neutral == (drive == 0 and closure in (None, 0) and reach is None
                                  and (translation is None or translation.forward == 0))
    assert not replace(command, orientation_drive=0.1).is_neutral
    assert not replace(command, extension_drive=0.1).is_neutral


@pytest.mark.parametrize("bad", [True, "1", [], {}, math.nan, math.inf, 10**400, -1.001, 1.001])
def test_extraction_drive_rejects_invalid_numeric_values(bad):
    with pytest.raises((TypeError, ValueError)):
        MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=bad)


@pytest.mark.parametrize("field", ["stroke", "milk_transferred_units"])
@pytest.mark.parametrize("bad", BAD_NUMBERS)
def test_facet_rejects_out_of_range_nonfinite_or_coerced_values(field, bad):
    with pytest.raises((TypeError, ValueError)):
        replace(OralExtractionFeedbackV1(0.2, 0.1, 0), **{field: bad})


@pytest.mark.parametrize("stroke", [None, 0.0, 0.5, 1.0])
@pytest.mark.parametrize("milk", [None, 0.0, 0.1, 1.0])
def test_missing_channels_are_independent_and_round_trip(stroke, milk):
    facet = OralExtractionFeedbackV1(stroke, milk, 4)
    sample = feedback(5, oral_extraction=facet)
    wire = sample.as_dict()
    assert wire["schema"] == "body_motor_feedback_v5"
    assert wire["oral_extraction"] == {
        "frame_id": "aggregate_oral_extraction_v1", "stroke_units": "normalized", "milk_units": "model_volume_units",
        "stroke": stroke, "milk_transferred_units": milk, "interval_start_tick": 4,
    }
    assert MotorFeedbackV1.from_dict(json.loads(json.dumps(wire, allow_nan=False))) == sample
    # Endpoint channels can be uncertain; transport does not turn a history into a repaired current seal.
    assert replace(sample, oral_seal=OralSealFeedbackV1(None, None)).oral_extraction == facet


@pytest.mark.parametrize("bad", [True, 0.5, "0", -1, 2**63 - 1, 2**63])
def test_interval_start_is_a_bounded_tick_with_room_for_endpoint(bad):
    with pytest.raises((TypeError, ValueError)):
        OralExtractionFeedbackV1(0.0, 0.0, bad)


def test_reset_is_no_prior_interval_not_observed_zero_transfer():
    reset = feedback(0)
    assert reset.oral_extraction.interval_start_tick is None
    assert reset.oral_extraction.milk_transferred_units is None
    assert MotorFeedbackV1.from_dict(reset.as_dict()) == reset
    with pytest.raises(ValueError, match="no prior interval"):
        OralExtractionFeedbackV1(0.0, 0.0, None)


@pytest.mark.parametrize("event,start", [(0, 0), (1, None), (3, 0), (3, 3), (3, 4)])
def test_interval_must_end_at_its_enclosing_event(event, start):
    with pytest.raises(ValueError, match="preceding interval"):
        feedback(event, oral_extraction=OralExtractionFeedbackV1(0.0, None, start))


@pytest.mark.parametrize("change", [{"oral_seal": None}, {"oral": None}, {"planar": None},
                                    {"oral_extraction": {"stroke": 0.2}}, {"oral_extraction": "milk"}])
def test_v5_requires_typed_enclosing_context_not_inferred_fields(change):
    with pytest.raises(TypeError):
        feedback(**change)


@pytest.mark.parametrize("field", ["frame_id", "stroke_units", "milk_units", "stroke", "milk_transferred_units", "interval_start_tick"])
def test_new_facet_requires_every_wire_field(field):
    packet = feedback().as_dict()
    del packet["oral_extraction"][field]
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)


@pytest.mark.parametrize("field,value", [("frame_id", "body_forward_oral_v1"), ("stroke_units", "metres"),
                                         ("milk_units", "millilitres"), ("reservoir", 9), ("donor_id", "mom"),
                                         ("milk_drinking", True), ("nourished", True), ("reward", 1)])
def test_facet_rejects_invented_units_and_privileged_or_task_answers(field, value):
    packet = feedback().as_dict()
    packet["oral_extraction"][field] = value
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)


@pytest.mark.parametrize("schema", [1, 2, 3, 4, 6, "5"])
def test_wrong_top_level_schema_cannot_smuggle_extraction(schema):
    command = MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=0).as_dict()
    command["schema"] = f"body_motor_command_v{schema}" if schema != "5" else 5
    sample = feedback().as_dict()
    sample["schema"] = f"body_motor_feedback_v{schema}" if schema != "5" else 5
    with pytest.raises((TypeError, ValueError)):
        MotorCommandV1.from_dict(command)
    with pytest.raises((TypeError, ValueError)):
        MotorFeedbackV1.from_dict(sample)


@pytest.mark.parametrize("field", ["translation", "oral_drive", "oral_closure_drive", "oral_extraction_drive"])
def test_v5_command_fields_are_required_even_when_earlier_drives_are_null(field):
    packet = MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=0).as_dict()
    del packet[field]
    with pytest.raises(ValueError):
        MotorCommandV1.from_dict(packet)


def test_v5_extraction_drive_cannot_be_null_on_wire():
    packet = MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=0).as_dict()
    packet["oral_extraction_drive"] = None
    with pytest.raises(TypeError):
        MotorCommandV1.from_dict(packet)


@pytest.mark.parametrize("version", [1, 2, 3, 4])
def test_legacy_wire_shapes_and_values_remain_exact(version):
    command = MotorCommandV1(STREAM, 1, 0, translation=PlanarDriveV1(0.1, 0.0) if version >= 2 else None,
                             oral_drive=0.2 if version >= 3 else None, oral_closure_drive=0.3 if version >= 4 else None)
    expected = {"schema": f"body_motor_command_v{version}", "stream": STREAM.as_dict(), "command_id": 1,
                "issued_tick": 0, "orientation_drive": 0.0, "extension_drive": 0.0}
    if version >= 2:
        expected["translation"] = {"forward": 0.1, "left": 0.0}
    if version >= 3:
        expected["oral_drive"] = 0.2
    if version >= 4:
        expected["oral_closure_drive"] = 0.3
    assert command.as_dict() == expected
    assert MotorCommandV1.from_dict(expected) == command
    sample = MotorFeedbackV1(STREAM, 1, 0, 0, 0.0, 1.0, True, 1.0, 0.0,
                             planar=PlanarFeedbackV1("scene_xy:fixture", (0.0, 0.0), 0.0, False) if version >= 2 else None,
                             oral=OralFeedbackV1(0.1, True) if version >= 3 else None,
                             oral_seal=OralSealFeedbackV1(0.6, True) if version >= 4 else None)
    assert sample.as_dict()["schema"] == f"body_motor_feedback_v{version}"
    assert "oral_extraction" not in sample.as_dict()
    assert MotorFeedbackV1.from_dict(sample.as_dict()) == sample
    if version == 4:
        expected["oral_closure_drive"] = None
        with pytest.raises(TypeError):
            MotorCommandV1.from_dict(expected)


def test_export_detaches_all_new_channels_and_the_records_are_frozen():
    sample = feedback()
    packet = copy.deepcopy(sample.as_dict())
    packet["oral_extraction"]["milk_transferred_units"] = 0.9
    assert sample.oral_extraction.milk_transferred_units == 0.1
    with pytest.raises(FrozenInstanceError):
        sample.oral_extraction.stroke = 0.8
    with pytest.raises(FrozenInstanceError):
        MotorCommandV1(STREAM, 1, 0, oral_extraction_drive=0).oral_extraction_drive = 1


def test_delivery_admission_keeps_original_interval_and_does_not_duplicate_transfer():
    previous = replace(feedback(0), available_tick=0)
    first = feedback(1)
    value = admit_motor_feedback_batch_v1((first,), previous, stream=STREAM, at_tick=2)
    assert value == first and value is not first
    for _ in range(5):
        value = admit_motor_feedback_batch_v1((first,), value, stream=STREAM, at_tick=9)
        assert value == first and value.oral_extraction.interval_start_tick == 0
    forged = replace(first, oral_extraction=OralExtractionFeedbackV1(0.2, 0.2, 0))
    with pytest.raises(ValueError, match="reused"):
        admit_motor_feedback_batch_v1((forged,), value, stream=STREAM, at_tick=9)
    with pytest.raises(ValueError, match="not yet"):
        admit_motor_feedback_batch_v1((first,), previous, stream=STREAM, at_tick=1)
    with pytest.raises(ValueError, match="generation"):
        first.validate_available(stream=replace(STREAM, generation=2), at_tick=2)


def test_old_sample_cannot_replace_newer_interval_or_turn_zero_into_unknown():
    newest = feedback(2, oral_extraction=OralExtractionFeedbackV1(None, 0.0, 1))
    result = admit_motor_feedback_batch_v1((feedback(1),), newest, stream=STREAM, at_tick=9)
    assert result == newest and result.oral_extraction.milk_transferred_units == 0.0
