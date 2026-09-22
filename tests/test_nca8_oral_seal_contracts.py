"""Canonical closure transport and anchored targets; no inferred feeding success."""
from dataclasses import FrozenInstanceError, replace
import copy
import math

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, OralFeedbackV1, OralSealFeedbackV1, PlanarFeedbackV1
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1, CommittedBodyTargetV1, LocalTargetDispositionV1, LocalTargetReportV1,
    SensorimotorTargetKindV1, TargetOriginV1, oral_closure_basis_compatible_v1, scalar_motor_coordinate_v1,
)

STREAM = MotorStreamRefV1("closure_contract", 1)
KIND = SensorimotorTargetKindV1.ORAL_CLOSURE


def feedback(**changes):
    result = MotorFeedbackV1(STREAM, 1, 0, 0, 0.0, 1.0, True, 1.0, 0.0,
                             planar=PlanarFeedbackV1("scene_xy:test", (0.0, 0.0), 0.0, False),
                             oral=OralFeedbackV1(0.1, True), oral_seal=OralSealFeedbackV1(0.0, False))
    return replace(result, **changes)


def target(**changes):
    origin = TargetOriginV1(STREAM, "task:fixture", "application:fixture", "envelope:fixture")
    result = BodyRelativeTargetV1("closure:fixture", 1, origin, KIND, feedback(), 0.6, 0.025, 0.8, 2.0)
    return replace(result, **changes)


@pytest.mark.parametrize("closure", [None, 0, 0.5, 1.0])
@pytest.mark.parametrize("sealed", [None, False, True])
def test_seal_facet_round_trip_preserves_independent_channels(closure, sealed):
    facet = OralSealFeedbackV1(closure, sealed)
    assert OralSealFeedbackV1.from_dict(facet.as_dict()) == facet
    sample = feedback(oral_seal=facet)
    assert sample.as_dict()["schema"] == "body_motor_feedback_v4"
    assert MotorFeedbackV1.from_dict(sample.as_dict()) == sample
    assert sample.sample_id == 1 and sample.event_tick == 0


@pytest.mark.parametrize("bad", [True, "0.6", -0.1, 1.01, math.inf, math.nan, [], 10**400])
def test_invalid_closure_rejected(bad):
    with pytest.raises((TypeError, ValueError)):
        OralSealFeedbackV1(bad, False)


@pytest.mark.parametrize("bad", [0, 1, "true", [], {}])
def test_invalid_seal_boolean_rejected(bad):
    with pytest.raises(TypeError):
        OralSealFeedbackV1(0.6, bad)


@pytest.mark.parametrize("key,value", [("frame_id", "body_forward_oral_v1"), ("units", "metres"), ("latched_nipple", True),
                                      ("milk", True), ("target", 0.6)])
def test_seal_facet_rejects_wrong_units_and_hidden_answers(key, value):
    packet = OralSealFeedbackV1(0.6, True).as_dict()
    packet[key] = value
    with pytest.raises((TypeError, ValueError)):
        OralSealFeedbackV1.from_dict(packet)


@pytest.mark.parametrize("drive", [-1, 0, 0.6, 1])
@pytest.mark.parametrize("reach", [None, 0.25])
def test_closure_command_round_trip_and_neutral(drive, reach):
    command = MotorCommandV1(STREAM, 1, 0, oral_closure_drive=drive, oral_drive=reach)
    packet = command.as_dict()
    assert packet["schema"] == "body_motor_command_v4"
    assert MotorCommandV1.from_dict(packet) == command
    assert command.is_neutral == (drive == 0 and reach is None)
    assert not {"target", "task", "seal", "nipple", "milk"}.intersection(packet)


@pytest.mark.parametrize("drive", [True, "1", -1.001, 1.001, math.inf, math.nan])
def test_invalid_closure_drive_rejected(drive):
    with pytest.raises((TypeError, ValueError)):
        MotorCommandV1(STREAM, 1, 0, oral_closure_drive=drive)


def test_new_feedback_facet_requires_its_typed_oral_context():
    with pytest.raises(TypeError):
        feedback(oral=None)
    with pytest.raises(TypeError):
        feedback(oral_seal={"closure": 0.6, "sealed": True})
    with pytest.raises(TypeError):
        feedback(planar=None)


@pytest.mark.parametrize("schema", [1, 2, 3])
def test_absent_new_facets_keep_legacy_wire_shapes(schema):
    base = feedback(oral_seal=None)
    if schema < 3:
        base = replace(base, oral=None)
    if schema < 2:
        base = replace(base, planar=None)
    packet = base.as_dict()
    assert packet["schema"] == f"body_motor_feedback_v{schema}"
    assert "oral_seal" not in packet
    assert MotorFeedbackV1.from_dict(packet) == base
    command = MotorCommandV1(STREAM, 1, 0, oral_drive=0.25 if schema == 3 else None)
    if schema == 2:
        from cca8_motor_contracts import PlanarDriveV1
        command = replace(command, translation=PlanarDriveV1(0.2, 0.0))
    assert command.as_dict()["schema"] == f"body_motor_command_v{schema}"
    assert "oral_closure_drive" not in command.as_dict()
    assert MotorCommandV1.from_dict(command.as_dict()) == command


@pytest.mark.parametrize("key", ["oral_seal", "sample_id", "event_tick", "oral", "planar"])
def test_v4_missing_fields_rejected(key):
    packet = feedback().as_dict()
    del packet[key]
    with pytest.raises((TypeError, ValueError)):
        MotorFeedbackV1.from_dict(packet)


def test_exports_detach_and_records_remain_immutable():
    sample = feedback()
    packet = sample.as_dict()
    before = copy.deepcopy(packet)
    packet["oral_seal"]["sealed"] = True
    assert sample.as_dict() == before
    with pytest.raises(FrozenInstanceError):
        sample.oral_seal.closure = 1.0


def test_closure_coordinate_is_not_reach_or_support():
    sample = feedback(oral_seal=OralSealFeedbackV1(0.3, False))
    assert scalar_motor_coordinate_v1(sample, KIND) == 0.3
    assert scalar_motor_coordinate_v1(sample, SensorimotorTargetKindV1.ORAL_REACH) == 0.1
    assert scalar_motor_coordinate_v1(sample, SensorimotorTargetKindV1.SUPPORT_EXTENSION) == 1.0
    assert scalar_motor_coordinate_v1(replace(sample, oral_seal=None), KIND) is None


@pytest.mark.parametrize("changes", [
    {"oral": OralFeedbackV1(None, True)},
    {"oral": OralFeedbackV1(0.102, True)},
    {"planar": PlanarFeedbackV1("scene_xy:test", (0.01, 0.0), 0.0, False)},
    {"planar": PlanarFeedbackV1("scene_xy:test", (0.0, 0.0), 1.0, False)},
    {"planar": PlanarFeedbackV1("scene_xy:other", (0.0, 0.0), 0.0, False)},
    {"stream": MotorStreamRefV1("closure_contract", 2)},
])
def test_closure_anchor_rejects_changed_or_unknown_body_basis(changes):
    assert not oral_closure_basis_compatible_v1(feedback(), feedback(**changes))


@pytest.mark.parametrize("changes", [{"max_rate": 2.01}, {"lease_ticks": 9}, {"max_corrections": 3},
                                      {"offset": 0.81}, {"offset": -0.1}, {"basis": feedback(oral_seal=OralSealFeedbackV1(None, False))}])
def test_closure_target_has_original_finite_bounds(changes):
    with pytest.raises((TypeError, ValueError)):
        target(**changes)


def test_local_coordinate_achievement_does_not_require_or_claim_seal():
    committed = CommittedBodyTargetV1(target(), "execution:fixture", 0)
    later = feedback(sample_id=7, event_tick=6, available_tick=7, oral_seal=OralSealFeedbackV1(0.6, False))
    report = LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 7, "coordinate_only", later)
    assert not report.as_dict()["establishes_task_success"]
    assert report.feedback.oral_seal.sealed is False
    broken = replace(later, oral=OralFeedbackV1(0.12, True))
    with pytest.raises(ValueError):
        replace(report, feedback=broken)
    with pytest.raises(ValueError):
        replace(report, feedback=replace(later, event_tick=9, available_tick=10), reported_tick=10)
