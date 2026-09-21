"""The opt-in oral facet extends exact motor records, not task authority."""

from dataclasses import FrozenInstanceError, replace
import json

import pytest

from cca8_motor_contracts import (
    MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1, OralFeedbackV1, PlanarDriveV1, PlanarFeedbackV1,
    admit_motor_feedback_batch_v1,
)
from nca8_sensorimotor_contracts import (
    BodyRelativeTargetV1, CommittedBodyTargetV1, LocalTargetDispositionV1, LocalTargetReportV1,
    SensorimotorTargetKindV1, TargetOriginV1, oral_basis_compatible_v1, scalar_motor_coordinate_v1,
)

STREAM = MotorStreamRefV1("oral_contract_fixture", 1)
ORAL = SensorimotorTargetKindV1.ORAL_REACH
PLANAR = PlanarFeedbackV1("scene_xy:oral_contract", (0.0, 0.0), 0.0, False)


def feedback(**changes):
    base = MotorFeedbackV1(STREAM, 1, 0, 0, 0.0, 1.0, True, 1.0, 0.0, planar=PLANAR, oral=OralFeedbackV1(0.0, False))
    return replace(base, **changes)


def target(**changes):
    base = BodyRelativeTargetV1("oral_target", 1, TargetOriginV1(STREAM, "task", "application", "envelope"),
                                ORAL, feedback(), 0.10, 0.0025, 0.20, 0.5)
    return replace(base, **changes)


@pytest.mark.parametrize("reach", [None, 0, 0.1, 0.35])
@pytest.mark.parametrize("contact", [None, False, True])
def test_oral_roundtrip_distinguishes_unknown_zero_and_boolean(reach, contact):
    value = OralFeedbackV1(reach, contact)
    wire = json.loads(json.dumps(value.as_dict(), allow_nan=False))
    assert OralFeedbackV1.from_dict(wire) == value
    assert value.contact is contact
    assert wire["units"] == "metres" and wire["frame_id"] == "body_forward_oral_v1"


@pytest.mark.parametrize("bad", [True, False, "0.1", [], -0.001, 0.35001, float("nan"), float("inf"), 10**400])
def test_invalid_reach_is_not_coerced(bad):
    with pytest.raises((ValueError, TypeError)):
        OralFeedbackV1(bad, False)


@pytest.mark.parametrize("bad", [0, 1, 0.0, "false", [], {}])
def test_numeric_contact_is_not_a_touch_report(bad):
    with pytest.raises(TypeError):
        OralFeedbackV1(0.0, bad)


@pytest.mark.parametrize("change", [{"milestone": True}, {"latch": True}, {"milk": 1.0}, {"units": "mm"},
                                    {"frame_id": "world_oral"}, {"contact": 1}])
def test_strict_oral_wire_refuses_unknown_answers_and_unit_changes(change):
    wire = OralFeedbackV1(0.1, False).as_dict()
    wire.update(change)
    with pytest.raises((ValueError, TypeError)):
        OralFeedbackV1.from_dict(wire)


@pytest.mark.parametrize("key", ["frame_id", "units", "extension_metres", "contact"])
def test_oral_wire_requires_missing_channels_to_be_explicit(key):
    wire = OralFeedbackV1(None, None).as_dict()
    del wire[key]
    with pytest.raises(ValueError):
        OralFeedbackV1.from_dict(wire)


@pytest.mark.parametrize("drive", [-1.0, -0.1, 0.0, 0.3, 1.0])
@pytest.mark.parametrize("translation", [None, PlanarDriveV1(0.2, 0.0)])
def test_v3_command_roundtrip_has_one_physical_interval(drive, translation):
    value = MotorCommandV1(STREAM, 1, 0, oral_drive=drive, translation=translation)
    wire = value.as_dict()
    assert wire["schema"] == "body_motor_command_v3"
    assert MotorCommandV1.from_dict(json.loads(json.dumps(wire))) == value
    assert value.is_neutral == (drive == 0.0 and translation is None)
    assert set(wire) == {"schema", "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive", "translation", "oral_drive"}


@pytest.mark.parametrize("bad", [True, "1", 1.001, -1.001, float("nan"), float("inf"), 10**400])
def test_invalid_oral_drive_is_refused_before_dispatch(bad):
    with pytest.raises((TypeError, ValueError)):
        MotorCommandV1(STREAM, 1, 0, oral_drive=bad)


@pytest.mark.parametrize("change", [{"oral_drive": None}, {"schema": "body_motor_command_v2"}, {"target": 0.1}, {"translation": {}}])
def test_v3_wire_cannot_be_silently_downgraded_or_accept_task_endpoint(change):
    wire = MotorCommandV1(STREAM, 1, 0, oral_drive=0.0).as_dict()
    wire.update(change)
    with pytest.raises((TypeError, ValueError)):
        MotorCommandV1.from_dict(wire)


def test_original_v1_v2_command_and_feedback_shapes_are_unchanged():
    for translation, schema in [(None, "body_motor_command_v1"), (PlanarDriveV1(1.0, 0.0), "body_motor_command_v2")]:
        wire = MotorCommandV1(STREAM, 1, 0, translation=translation).as_dict()
        assert wire["schema"] == schema and "oral_drive" not in wire
        assert MotorCommandV1.from_dict(wire).as_dict() == wire
    for planar, schema in [(None, "body_motor_feedback_v1"), (PLANAR, "body_motor_feedback_v2")]:
        wire = feedback(oral=None, planar=planar).as_dict()
        assert wire["schema"] == schema and "oral" not in wire
        assert MotorFeedbackV1.from_dict(wire).as_dict() == wire


@pytest.mark.parametrize("change", [{"oral": None}, {"planar": None}, {"oral": {}}, {"schema": "body_motor_feedback_v2"},
                                    {"done": True}])
def test_v3_feedback_rejects_invalid_facet_or_schema(change):
    wire = feedback().as_dict()
    wire.update(change)
    with pytest.raises((TypeError, ValueError)):
        MotorFeedbackV1.from_dict(wire)


def test_shared_acquisition_roundtrip_detachment_and_availability():
    value = feedback(sample_id=5, event_tick=4, available_tick=5, oral=OralFeedbackV1(0.1, True))
    wire = value.as_dict()
    restored = MotorFeedbackV1.from_dict(json.loads(json.dumps(wire)))
    assert restored == value and restored is not value
    wire["oral"]["contact"] = False
    wire["planar"]["position"][0] = 9.0
    assert restored.oral.contact is True and restored.planar.position == (0.0, 0.0)
    with pytest.raises(ValueError):
        restored.validate_available(stream=STREAM, at_tick=4)
    restored.validate_available(stream=STREAM, at_tick=5)
    assert admit_motor_feedback_batch_v1((restored,), feedback(), stream=STREAM, at_tick=5) == restored
    with pytest.raises(ValueError):
        admit_motor_feedback_batch_v1((replace(restored, oral=OralFeedbackV1(0.1, False)),), restored, stream=STREAM, at_tick=5)


@pytest.mark.parametrize("change", [{"planar": None}, {"oral": {}}, {"available_tick": -1}, {"event_tick": 1}])
def test_invalid_feedback_cannot_gain_oral_authority(change):
    with pytest.raises((TypeError, ValueError)):
        feedback(**change)


def test_shared_scalar_dispatch_never_substitutes_support_extension_for_oral_reach():
    value = feedback(oral=OralFeedbackV1(0.1, False))
    assert scalar_motor_coordinate_v1(value, ORAL) == 0.1
    assert scalar_motor_coordinate_v1(value, SensorimotorTargetKindV1.SUPPORT_EXTENSION) == 1.0
    assert scalar_motor_coordinate_v1(value, SensorimotorTargetKindV1.ORIENTATION_ADJUST) == 0.0
    assert scalar_motor_coordinate_v1(replace(value, oral=None), ORAL) is None
    with pytest.raises(ValueError):
        scalar_motor_coordinate_v1(value, SensorimotorTargetKindV1.PLANAR_TRANSLATION)


@pytest.mark.parametrize("change", [{"offset": 0.4}, {"offset": -0.1}, {"max_rate": 0.51}, {"max_displacement": 0.36},
                                    {"lease_ticks": 9}, {"lease_ticks": True}, {"max_corrections": 3},
                                    {"basis": feedback(oral=None)}, {"basis": feedback(planar=replace(PLANAR, heading_degrees=None))}])
def test_oral_target_bounds_and_missing_original_geometry(change):
    with pytest.raises((TypeError, ValueError)):
        target(**change)


@pytest.mark.parametrize("position,heading,compatible", [((0.0, 0.0), 0.0, True), ((0.001, 0.0), 0.5, True),
                                                       ((0.0011, 0.0), 0.0, False), ((0.0, 0.0), 0.51, False)])
def test_original_body_anchor_has_independent_position_and_yaw_tolerances(position, heading, compatible):
    later = feedback(planar=replace(PLANAR, position=position, heading_degrees=heading))
    assert oral_basis_compatible_v1(feedback(), later) is compatible


@pytest.mark.parametrize("contact", [False, True, None])
def test_local_coordinate_result_never_proves_contact_or_latch(contact):
    committed = CommittedBodyTargetV1(target(), "execution", 0)
    later = feedback(sample_id=5, event_tick=4, available_tick=5, oral=OralFeedbackV1(0.1, contact))
    report = LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 5, "coordinate_observed", later)
    assert report.feedback.oral.contact is contact
    assert "latch" not in report.as_dict() and "milk" not in report.as_dict()
    assert report.committed_target.target.endpoint == 0.1


@pytest.mark.parametrize("change", [{"oral": OralFeedbackV1(None, True)}, {"oral": OralFeedbackV1(0.08, True)},
                                    {"planar": replace(PLANAR, position=(0.02, 0.0))},
                                    {"planar": replace(PLANAR, heading_degrees=2.0)}, {"event_tick": 9, "available_tick": 9}])
def test_achievement_requires_observed_coordinate_original_anchor_and_lease(change):
    later = feedback(sample_id=5, event_tick=4, available_tick=5, oral=OralFeedbackV1(0.1, True))
    later = replace(later, **change)
    with pytest.raises(ValueError):
        LocalTargetReportV1(CommittedBodyTargetV1(target(), "execution", 0), LocalTargetDispositionV1.ACHIEVED,
                            9, "not_a_supported_result", later)


def test_immutable_original_target_is_not_rebased_after_motion():
    original = target()
    later = feedback(oral=OralFeedbackV1(0.05, False))
    assert original.endpoint == 0.1 and scalar_motor_coordinate_v1(later, ORAL) == 0.05
    with pytest.raises((FrozenInstanceError, AttributeError)):
        original.offset = 0.2
    assert original.as_dict()["basis"]["oral"]["extension_metres"] == 0.0
