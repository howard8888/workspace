#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""P18-H1 contract tests: no provider, actor, Righting or learned behavior claimed."""

from __future__ import annotations

import ast
import json
import random
import subprocess
import sys
from dataclasses import FrozenInstanceError, fields, replace
from pathlib import Path

import pytest

from cca8_motor_contracts import (
    MOTOR_COMMAND_SCHEMA_V1,
    MOTOR_FEEDBACK_SCHEMA_V1,
    MOTOR_FRAME_V1,
    MotorCommandV1,
    MotorFeedbackV1,
    MotorStreamRefV1,
)
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

ROOT = Path(__file__).resolve().parents[1]
STREAM = MotorStreamRefV1("fixture:body", 1)


def _feedback(**changes: object) -> MotorFeedbackV1:
    base = MotorFeedbackV1(STREAM, 1, 0, 1, 30.0, 0.4, True, 0.1285, 0.6)
    return replace(base, **changes)


def _target(kind: SensorimotorTargetKindV1 = SensorimotorTargetKindV1.ORIENTATION_ADJUST) -> BodyRelativeTargetV1:
    extension = kind is SensorimotorTargetKindV1.SUPPORT_EXTENSION
    return BodyRelativeTargetV1(
        target_id="target:extension" if extension else "target:orientation",
        revision=1,
        origin=TargetOriginV1(STREAM, "task:1", "application:1", "envelope:1"),
        kind=kind,
        basis=_feedback(),
        offset=0.2 if extension else -12.0,
        tolerance=0.01 if extension else 1.0,
        max_displacement=0.25 if extension else 18.0,
        max_rate=1.0 if extension else 60.0,
    )


def _committed(kind: SensorimotorTargetKindV1 = SensorimotorTargetKindV1.ORIENTATION_ADJUST) -> CommittedBodyTargetV1:
    return CommittedBodyTargetV1(_target(kind), "execution:1", 1)


def _current_args() -> dict[str, object]:
    return {
        "stream": STREAM, "execution_id": "execution:1", "envelope_id": "envelope:1",
        "target_id": "target:orientation", "target_revision": 1, "now_tick": 1,
    }


def test_wire_roundtrips_and_detachment() -> None:
    records = (STREAM, MotorCommandV1(STREAM, 1, 1, -0.5, 0.5), _feedback(), _feedback(support_contact=False))
    for record in records:
        packet = record.as_dict()
        roundtrip = type(record).from_dict(json.loads(json.dumps(packet, allow_nan=False)))
        assert roundtrip == record
        assert roundtrip is not record
    packet = _feedback().as_dict()
    decoded = MotorFeedbackV1.from_dict(packet)
    packet["stream"]["generation"] = 99
    packet["body_tilt_degrees"] = -60.0
    assert decoded.stream.generation == 1
    assert decoded.body_tilt_degrees == 30.0
    exported = decoded.as_dict()
    exported["stream"]["stream_id"] = "changed"
    assert decoded.stream.stream_id == "fixture:body"


def test_partial_and_missing_channels_preserve_unknown_and_valid_no_contact() -> None:
    absent = _feedback(body_tilt_degrees=None, support_extension=None, support_contact=None, useful_loading=None, destabilization=None)
    assert MotorFeedbackV1.from_dict(absent.as_dict()) == absent
    no_contact = _feedback(support_contact=False, useful_loading=0.0)
    assert no_contact.support_contact is False
    assert absent.support_contact is None
    assert no_contact.useful_loading == 0.0
    # Admission is not a hidden physical-consistency repair or success classifier.
    conflicting = _feedback(support_contact=False, useful_loading=0.7)
    assert conflicting.useful_loading == 0.7


@pytest.mark.parametrize("value", [True, False, 1.0, "1", None])
@pytest.mark.parametrize("field", ["generation", "sample_id", "event_tick", "available_tick", "command_id", "issued_tick"])
def test_identity_and_time_reject_boolean_or_noninteger_values(field: str, value: object) -> None:
    with pytest.raises(TypeError):
        if field == "generation":
            replace(STREAM, generation=value)
        elif field in {"command_id", "issued_tick"}:
            replace(MotorCommandV1(STREAM, 1, 1), **{field: value})
        else:
            _feedback(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("sample_id", 0), ("sample_id", -1), ("event_tick", -1), ("available_tick", -1),
    ("sample_id", 2**63), ("event_tick", 2**63), ("available_tick", 2**63),
])
def test_feedback_counters_have_explicit_finite_bounds(field: str, value: int) -> None:
    with pytest.raises(ValueError):
        _feedback(**{field: value})


@pytest.mark.parametrize("field", ["body_tilt_degrees", "support_extension", "useful_loading", "destabilization"])
@pytest.mark.parametrize("value", [True, "0", float("nan"), float("inf"), -float("inf"), 10**400])
def test_measurements_reject_invalid_numerics(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        _feedback(**{field: value})


@pytest.mark.parametrize("field,value", [
    ("body_tilt_degrees", -90.01), ("body_tilt_degrees", 90.01),
    ("support_extension", -0.01), ("support_extension", 1.01),
    ("useful_loading", -0.01), ("useful_loading", 1.01),
    ("destabilization", -0.01), ("destabilization", 1.01),
])
def test_measurement_ranges_are_not_silently_clipped(field: str, value: float) -> None:
    with pytest.raises(ValueError):
        _feedback(**{field: value})


@pytest.mark.parametrize("value", [0, 1, 0.0, "false", [], {}])
def test_contact_requires_real_boolean_or_none(value: object) -> None:
    with pytest.raises(TypeError):
        _feedback(support_contact=value)
    packet = _feedback().as_dict()
    packet["support_contact"] = value
    with pytest.raises(TypeError):
        MotorFeedbackV1.from_dict(packet)


def test_valid_boundary_values_are_kept_and_integer_measurements_normalize() -> None:
    low = _feedback(body_tilt_degrees=-90, support_extension=0, useful_loading=0, destabilization=1)
    high = _feedback(body_tilt_degrees=90, support_extension=1, useful_loading=1, destabilization=0)
    assert low.body_tilt_degrees == -90.0 and high.body_tilt_degrees == 90.0
    assert type(low.support_extension) is float
    assert type(high.destabilization) is float


@pytest.mark.parametrize("name,value", [
    ("schema", "posture_support_v1"), ("frame_id", "body_ground_v1"),
    ("angle_units", "radians"), ("extension_units", "meters"), ("frame_id", None),
])
def test_feedback_decoder_rejects_other_schemas_frames_and_units(name: str, value: object) -> None:
    packet = _feedback().as_dict()
    packet[name] = value
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)


@pytest.mark.parametrize("key", ["scenario", "success", "policy", "pnm", "milestones", "private_state", "event_cycle"])
def test_feedback_decoder_rejects_unknown_and_privileged_fields(key: str) -> None:
    packet = _feedback().as_dict()
    packet[key] = "not admitted"
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)


def test_feedback_decoder_rejects_missing_fields_nested_fields_and_nonmapping() -> None:
    packet = _feedback().as_dict()
    packet.pop("useful_loading")
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)
    packet = _feedback().as_dict()
    packet["stream"]["extra"] = 1
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)
    with pytest.raises(TypeError):
        MotorFeedbackV1.from_dict([])
    packet = _feedback().as_dict()
    packet[123] = packet.pop("sample_id")
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)


def test_feedback_time_ordering_and_availability_are_separate_from_event_time() -> None:
    with pytest.raises(ValueError):
        _feedback(event_tick=5, available_tick=4)
    delayed = _feedback(event_tick=5, available_tick=7)
    with pytest.raises(ValueError):
        delayed.validate_available(stream=STREAM, at_tick=6)
    delayed.validate_available(stream=STREAM, at_tick=7)
    delayed.validate_available(stream=STREAM, at_tick=8)
    assert delayed.event_tick == 5  # Re-reading is not retimestamping or a new sample.
    immediate_reset = _feedback(event_tick=0, available_tick=0)
    immediate_reset.validate_available(stream=STREAM, at_tick=0)


@pytest.mark.parametrize("stream", [MotorStreamRefV1("other:body", 1), MotorStreamRefV1("fixture:body", 2)])
def test_stream_and_generation_are_not_interchangeable(stream: MotorStreamRefV1) -> None:
    with pytest.raises(ValueError):
        _feedback().validate_available(stream=stream, at_tick=1)
    with pytest.raises(ValueError):
        MotorCommandV1(STREAM, 1, 1).validate_for_update(stream=stream, now_tick=1, previous_command_id=0)
    with pytest.raises(ValueError):
        replace(_target(), basis=_feedback(stream=stream))


@pytest.mark.parametrize("drive", [True, "0", float("nan"), float("inf"), 1.01, -1.01, 10**400])
@pytest.mark.parametrize("channel", ["orientation_drive", "extension_drive"])
def test_motor_commands_are_bounded_signed_drives(channel: str, drive: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(MotorCommandV1(STREAM, 1, 1), **{channel: drive})


def test_motor_command_validation_rejects_wrong_time_duplicate_and_bad_schema() -> None:
    command = MotorCommandV1(STREAM, 3, 5, -1.0, 1.0)
    command.validate_for_update(stream=STREAM, now_tick=5, previous_command_id=2)
    for tick, previous in ((4, 2), (6, 2), (5, 3), (5, 4)):
        with pytest.raises(ValueError):
            command.validate_for_update(stream=STREAM, now_tick=tick, previous_command_id=previous)
    with pytest.raises(TypeError):
        command.validate_for_update(stream=STREAM, now_tick=True, previous_command_id=2)
    packet = command.as_dict()
    packet["target"] = "standing"
    with pytest.raises(ValueError):
        MotorCommandV1.from_dict(packet)
    packet = command.as_dict()
    packet["schema"] = MOTOR_FEEDBACK_SCHEMA_V1
    with pytest.raises(ValueError):
        MotorCommandV1.from_dict(packet)
    with pytest.raises(ValueError):
        MotorCommandV1(STREAM, 1, 2**63 - 1)
    with pytest.raises(ValueError):
        MotorCommandV1(STREAM, 0, 1)


def test_neutral_command_contains_no_task_target_or_physical_success() -> None:
    command = MotorCommandV1(STREAM, 1, 0)
    assert command.is_neutral
    assert not replace(command, extension_drive=0.1).is_neutral
    assert set(command.as_dict()) == {
        "schema", "stream", "command_id", "issued_tick", "orientation_drive", "extension_drive",
    }
    assert command.as_dict()["schema"] == MOTOR_COMMAND_SCHEMA_V1


def test_target_endpoint_is_fixed_to_immutable_body_basis() -> None:
    target = _target()
    assert target.endpoint == 18.0
    newer = _feedback(sample_id=2, event_tick=2, available_tick=3, body_tilt_degrees=25.0)
    assert target.endpoint != newer.body_tilt_degrees + target.offset
    assert target.endpoint == 18.0 and target.basis.body_tilt_degrees == 30.0
    mirrored = replace(target, basis=_feedback(body_tilt_degrees=-30.0), offset=12.0)
    assert mirrored.endpoint == -18.0
    extension = _target(SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    assert extension.endpoint == pytest.approx(0.6)
    assert target.as_dict()["status"] == "proposed"


@pytest.mark.parametrize("field,value", [
    ("revision", True), ("revision", 0), ("lease_ticks", True), ("lease_ticks", 0), ("lease_ticks", 9),
    ("max_corrections", True), ("max_corrections", -1), ("max_corrections", 3),
    ("offset", True), ("offset", 20.0), ("offset", float("nan")),
    ("tolerance", 0.0), ("tolerance", 19.0), ("max_displacement", 0.0), ("max_displacement", 181.0),
    ("max_rate", 0.0), ("max_rate", 91.0), ("kind", "orientation_adjust"),
])
def test_target_parameters_require_finite_valid_contracts(field: str, value: object) -> None:
    with pytest.raises((TypeError, ValueError)):
        replace(_target(), **{field: value})


def test_target_cannot_invent_missing_starting_geometry_or_out_of_range_endpoint() -> None:
    with pytest.raises(ValueError):
        replace(_target(), basis=_feedback(body_tilt_degrees=None))
    extension = _target(SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    with pytest.raises(ValueError):
        replace(extension, basis=_feedback(support_extension=None))
    with pytest.raises(ValueError):
        replace(extension, basis=_feedback(support_extension=0.9))
    with pytest.raises(ValueError):
        replace(_target(), basis=_feedback(body_tilt_degrees=-85.0))
    with pytest.raises(ValueError):
        replace(extension, max_rate=1.1)
    # Missing support contact is not invented by range validation; H3 decides applicability.
    no_contact_basis = replace(extension, basis=_feedback(support_contact=None))
    assert no_contact_basis.basis.support_contact is None


def test_proposal_and_commitment_are_distinct_and_exports_grant_no_live_authority() -> None:
    target = _target()
    committed = CommittedBodyTargetV1(target, "execution:1", 1)
    assert committed.target is target
    assert committed.expires_at_tick == 9
    assert committed.as_dict()["status"] == "committed_description"
    assert committed.as_dict()["restores_live_authority"] is False
    assert target.as_dict()["status"] == "proposed"
    assert not hasattr(committed, "from_dict")
    with pytest.raises(ValueError):
        CommittedBodyTargetV1(target, "execution:1", 0)
    with pytest.raises(ValueError):
        CommittedBodyTargetV1(target, "execution:1", 2**63 - 5)


@pytest.mark.parametrize("name,value", [
    ("stream", MotorStreamRefV1("fixture:body", 2)),
    ("execution_id", "execution:2"), ("envelope_id", "envelope:2"), ("target_id", "target:other"),
    ("target_revision", 2), ("target_revision", True), ("now_tick", 0), ("now_tick", 9), ("now_tick", 10),
])
def test_committed_context_rejects_wrong_owner_revision_and_expiry(name: str, value: object) -> None:
    args = _current_args()
    args[name] = value
    with pytest.raises((TypeError, ValueError)):
        _committed().validate_current(**args)


def test_lease_is_half_open_and_no_output_does_not_renew_or_cancel() -> None:
    committed = _committed()
    args = _current_args()
    for tick in (1, 8):
        args["now_tick"] = tick
        committed.validate_current(**args)
    old = committed.as_dict()
    assert TargetDirectiveV1.NO_NEW_TASK_OUTPUT != TargetDirectiveV1.CANCEL_TARGET
    assert TargetDirectiveV1.INSTALL_TARGET != TargetDirectiveV1.REPLACE_TARGET
    assert committed.as_dict() == old
    assert committed.expires_at_tick == 9


def test_focal_projection_preserves_event_identity_without_future_evidence_or_copy_mutation() -> None:
    feedback = _feedback(sample_id=3, event_tick=4, available_tick=5)
    with pytest.raises(ValueError):
        FocalMotorEvidenceV1(feedback, focal_cycle=2, cutoff_tick=4)
    projection = FocalMotorEvidenceV1(feedback, focal_cycle=2, cutoff_tick=5)
    assert projection.feedback is feedback
    exported = projection.as_dict()
    assert exported["feedback"]["sample_id"] == 3
    assert exported["feedback"]["event_tick"] == 4
    assert exported["independent_sensor_event"] is False and exported["is_wnm"] is False
    exported["feedback"]["body_tilt_degrees"] = -70.0
    assert projection.feedback.body_tilt_degrees == 30.0
    assert feedback.event_tick == 4


def test_local_target_achievement_does_not_establish_useful_support_or_task_success() -> None:
    committed = _committed(SensorimotorTargetKindV1.SUPPORT_EXTENSION)
    observed = _feedback(sample_id=2, event_tick=3, available_tick=4, support_extension=0.6, support_contact=False, useful_loading=0.0)
    report = LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 4, "target_coordinate_observed", observed)
    assert report.feedback.support_extension == pytest.approx(committed.target.endpoint)
    assert report.feedback.support_contact is False
    assert report.as_dict()["establishes_task_success"] is False
    assert report.as_dict()["establishes_action_causation"] is False
    assert report.as_dict()["feedback"]["useful_loading"] == 0.0


def test_local_achievement_needs_matching_available_measurement() -> None:
    committed = _committed()
    good = _feedback(sample_id=2, event_tick=2, available_tick=3, body_tilt_degrees=18.0)
    report = LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 3, "observed", good)
    assert report.disposition is LocalTargetDispositionV1.ACHIEVED
    for observed in (None, replace(good, body_tilt_degrees=None), replace(good, body_tilt_degrees=25.0),
                     replace(good, available_tick=4), replace(good, stream=MotorStreamRefV1("fixture:body", 2))):
        with pytest.raises(ValueError):
            LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 3, "not established", observed)
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.PARTIAL, 3, "missing", None)


def test_late_report_can_describe_earlier_achievement_but_cannot_reactivate_pursuit() -> None:
    committed = _committed()
    delayed = _feedback(sample_id=2, event_tick=8, available_tick=10, body_tilt_degrees=18.0)
    report = LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 10, "delayed_observed_result", delayed)
    assert report.reported_tick == 10
    with pytest.raises(ValueError):
        committed.validate_current(**{**_current_args(), "now_tick": 10})
    after_lease = replace(delayed, event_tick=10, available_tick=11)
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.ACHIEVED, 11, "outside_lease", after_lease)


def test_local_disposition_time_counter_and_enum_constraints() -> None:
    committed = _committed()
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.EXPIRED, 8, "too_early")
    LocalTargetReportV1(committed, LocalTargetDispositionV1.EXPIRED, 9, "lease_elapsed")
    for status in (LocalTargetDispositionV1.PENDING, LocalTargetDispositionV1.ACTIVE):
        with pytest.raises(ValueError):
            LocalTargetReportV1(committed, status, 9, "too_late")
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.UNRESOLVED, 0, "too_early")
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.UNRESOLVED, 2, "too_many", correction_count=3)
    with pytest.raises(TypeError):
        LocalTargetReportV1(committed, "achieved", 2, "not_an_enum")
    with pytest.raises(TypeError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.UNRESOLVED, 2, "bool_count", correction_count=True)


def test_reports_reject_feedback_from_before_the_target_basis() -> None:
    later_basis = _feedback(sample_id=5, event_tick=5, available_tick=6)
    committed = CommittedBodyTargetV1(replace(_target(), basis=later_basis), "execution:1", 6)
    with pytest.raises(ValueError):
        LocalTargetReportV1(committed, LocalTargetDispositionV1.PARTIAL, 6, "old", _feedback())


def test_bounded_text_and_nested_types_are_validated() -> None:
    for text in ("", " ", "x" * 121, "a\nb"):
        with pytest.raises(ValueError):
            MotorStreamRefV1(text, 1)
        with pytest.raises(ValueError):
            replace(_target(), target_id=text)
        with pytest.raises(ValueError):
            replace(_target().origin, envelope_id=text)
    with pytest.raises(TypeError):
        replace(_target(), origin={})
    with pytest.raises(TypeError):
        replace(_target(), basis={})
    with pytest.raises(TypeError):
        replace(_feedback(), stream={})
    assert MotorStreamRefV1(" fixture:body ", 1) == STREAM


def test_all_contracts_are_frozen_and_diagnostic_json_is_finite() -> None:
    committed = _committed()
    records = (
        STREAM, _feedback(), MotorCommandV1(STREAM, 1, 1), _target().origin,
        _target(), committed, FocalMotorEvidenceV1(_feedback(), 1, 1),
        LocalTargetReportV1(committed, LocalTargetDispositionV1.UNRESOLVED, 1, "no_execution_in_h1"),
    )
    rng_before = random.getstate()
    for record in records:
        first = fields(record)[0].name
        with pytest.raises(FrozenInstanceError):
            setattr(record, first, None)
        first_export = json.dumps(record.as_dict(), sort_keys=True, allow_nan=False)
        assert first_export == json.dumps(record.as_dict(), sort_keys=True, allow_nan=False)
        assert len(first_export) < 4096
    assert random.getstate() == rng_before


def test_neutral_module_imports_only_the_standard_library() -> None:
    tree = ast.parse((ROOT / "cca8_motor_contracts.py").read_text(encoding="utf-8"))
    roots = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            roots.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            roots.add(node.module.split(".")[0])
    assert roots <= {"__future__", "math", "collections", "dataclasses"}


def test_contract_import_does_not_start_a_runtime_or_change_rng() -> None:
    script = (
        "import random,sys; before=random.getstate(); "
        "import cca8_motor_contracts,nca8_sensorimotor_contracts; "
        "assert random.getstate()==before; "
        "assert not ({'cca8_env','cca8_run','nca8_runtime','nca8_body','nca8_primitives'} & set(sys.modules))"
    )
    completed = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_h1_registers_production_contract_modules_without_starting_new_actors() -> None:
    script = (
        "import sys,cca8_run; "
        "assert not any(name.startswith('nca8_') for name in sys.modules); "
        "registry=dict(cca8_run._CCA8_COMPONENT_REGISTRY); "
        "assert registry['motor_contracts']=='cca8_motor_contracts'; "
        "assert registry['nca8_sensorimotor_contracts']=='nca8_sensorimotor_contracts'; "
        "assert len(cca8_run._cca8_component_rows())==94; "
        "assert len(cca8_run.PRIMITIVES)==8"
    )
    completed = subprocess.run([sys.executable, "-c", script], cwd=ROOT, capture_output=True, text=True, check=False)
    assert completed.returncode == 0, completed.stderr


def test_existing_support_wire_schema_remains_a_separate_unchanged_provider() -> None:
    from cca8_support_world import SupportWorldStateV1, support_observation_packet_v1
    packet = support_observation_packet_v1(SupportWorldStateV1(10.0, 0.45, 0.4), step_index=0)
    assert packet["schema"] == "posture_support_v1"
    assert set(packet) == {
        "schema", "sample_id", "event_cycle", "frame_id", "body_ground_angle_degrees",
        "useful_loading", "destabilization", "lateral_contact",
    }
    with pytest.raises(ValueError):
        MotorFeedbackV1.from_dict(packet)
    assert _feedback().frame_id == MOTOR_FRAME_V1


def test_a_reused_sensor_id_cannot_claim_changed_achievement() -> None:
    changed = _feedback(body_tilt_degrees=18.0)
    with pytest.raises(ValueError, match="one sensor sample identity"):
        LocalTargetReportV1(_committed(), LocalTargetDispositionV1.ACHIEVED, 1, "changed_same_id", changed)
    unchanged_target = CommittedBodyTargetV1(replace(_target(), offset=0.0), "execution:1", 1)
    report = LocalTargetReportV1(unchanged_target, LocalTargetDispositionV1.ACHIEVED, 1, "already_at_target", _feedback())
    assert report.as_dict()["establishes_action_causation"] is False


def test_manual_contract_review_is_deterministic_and_explicitly_nonexecuting() -> None:
    command = [sys.executable, "scripts/review_nca8_motor_contracts.py"]
    first = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    second = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, check=False)
    assert first.returncode == second.returncode == 0, first.stderr + second.stderr
    assert first.stdout == second.stdout
    assert "CONTRACT FIXTURES PASSED" in first.stdout
    assert "NO MOVEMENT" in first.stdout
    assert "local disposition=achieved; support_contact=False; useful_loading=0.0" in first.stdout
    assert "cutoff 3 before availability 4: REJECTED" in first.stdout
    assert "generation 2: REJECTED" in first.stdout
    assert "target revision 2: REJECTED" in first.stdout
    assert "motor execution / NavMap revision / learning performed: False" in first.stdout
