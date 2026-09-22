"""Contact-grounded closure mapping, source correspondence and finite permission."""
from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralFeedbackV1, OralSealFeedbackV1, PlanarFeedbackV1
from nca8_body_targets import (
    BodyTargetMapperV1, BodyMovementRequestV1, OralClosureRequestV1, OralReachRequestV1,
    nominal_body_capabilities_v1, oral_body_capability_v1, oral_closure_capability_v1,
)
from nca8_oral_seal_demo import OralSealTrialV1
from nca8_sensorimotor import SensorimotorExecutorV1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1, LocalTargetDispositionV1

KIND = SensorimotorTargetKindV1.ORAL_CLOSURE


def fresh():
    trial = OralSealTrialV1("preview_only")
    mapper = trial.body.motor_targets
    assert mapper is not None
    return trial, mapper, trial.proposal.request


@pytest.mark.parametrize("desired", [0.1, 0.3, 0.6, 0.9])
def test_target_uses_supplied_coordinate_and_narrows_without_faking_achievement(desired):
    trial, mapper, request = fresh()
    proposal = mapper.propose_oral_closure(replace(request, desired_closure=desired), trial.source, at_tick=0)
    assert proposal.request.desired_closure == desired
    assert proposal.bindings[0].target.endpoint == pytest.approx(min(0.6, desired))
    assert proposal.closure_preview.body == trial.latest_feedback
    assert mapper.reservations(at_tick=0) == ()
    assert trial.world.oral_seal_body.closure == 0.0
    assert not trial.world.oral_seal_body.sealed


@pytest.mark.parametrize("case,reason", [
    ("no_touch", "feeding_contact_not_supported"), ("touch_elsewhere", "feeding_contact_not_supported"),
    ("missing_detail", "current_feeding_detail_unavailable"), ("wrong_category", "current_feeding_detail_unavailable"),
    ("source_off", "current_feeding_detail_unavailable"), ("no_capability", "capability_unavailable"),
    ("missing_contact", "required_contact_evidence_missing"), ("missing_closure", "required_coordinate_missing"),
])
def test_unusable_contact_or_capability_blocks_mapping(case, reason):
    trial = OralSealTrialV1(case)
    assert trial.proposal.bindings == () and trial.proposal.withheld == ((KIND, reason),)
    assert trial.controller.installation_count == 0
    assert trial.advance().command is None


def test_unknown_seal_does_not_block_closure_or_fabricate_confirmation():
    trial = OralSealTrialV1("missing_seal")
    assert trial.proposal.bindings and trial.source.oral_sealed is None
    assert trial.source.seal_correspondence_status == "seal_unknown"


@pytest.mark.parametrize("case", ["release_without_vision", "release_without_touch"])
def test_opening_can_use_body_without_feeding_contact(case):
    trial = OralSealTrialV1(case)
    assert trial.proposal.bindings[0].target.offset < 0
    assert trial.advance().command.oral_closure_drive < 0


@pytest.mark.parametrize("channel", ["body_tilt_degrees", "useful_loading", "support_contact", "destabilization"])
def test_closure_does_not_bypass_missing_support(channel):
    trial, mapper, request = fresh()
    sample = replace(trial.latest_feedback, sample_id=2, event_tick=1, available_tick=1, **{channel: None})
    mapper.update_feedback(sample, at_tick=1)
    # Opening needs no source but still obeys protected current support.
    proposal = mapper.propose_oral_closure(replace(request, desired_closure=0), None, at_tick=1)
    assert proposal.withheld == ((KIND, "required_support_evidence_missing"),)


@pytest.mark.parametrize("change", [{"support_contact": False}, {"useful_loading": 0.7}, {"body_tilt_degrees": 13.0},
                                    {"destabilization": 0.3}])
def test_closure_does_not_bypass_unsafe_support(change):
    trial, mapper, request = fresh()
    sample = replace(trial.latest_feedback, sample_id=2, event_tick=1, available_tick=1, **change)
    mapper.update_feedback(sample, at_tick=1)
    proposal = mapper.propose_oral_closure(replace(request, desired_closure=0), None, at_tick=1)
    assert proposal.withheld == ((KIND, "oral_support_unavailable"),)


def test_unpaired_source_cannot_authorize_closing():
    trial, mapper, request = fresh()
    source = replace(trial.source, oral_feedback=None)
    proposal = mapper.propose_oral_closure(request, source, at_tick=0)
    assert proposal.withheld == ((KIND, "oral_source_body_acquisition_mismatch"),)


def test_contact_location_and_inconsistent_seal_are_distinct():
    trial, _, _ = fresh()
    body = trial.latest_feedback
    no_touch = replace(trial.source, oral_feedback=replace(body, oral=OralFeedbackV1(0.1, False),
                                                          oral_seal=OralSealFeedbackV1(0.6, True)))
    assert no_touch.contact_correspondence_status == "no_touch"
    assert no_touch.seal_correspondence_status == "inconsistent_touch_and_seal"
    unknown = replace(trial.source, oral_feedback=replace(body, oral=OralFeedbackV1(0.1, None),
                                                         oral_seal=OralSealFeedbackV1(0.6, True)))
    assert unknown.seal_correspondence_status == "seal_unlocalized"
    assert OralSealTrialV1("touch_elsewhere").source.contact_correspondence_status == "touch_elsewhere"
    assert replace(trial.source, oral_feedback=None).seal_correspondence_status == "not_supplied"


def test_exported_seal_relation_does_not_overwrite_old_snapshot_or_claim_task():
    trial = OralSealTrialV1()
    old = trial.source
    before = json.dumps(old.as_dict(), sort_keys=True)
    for _ in range(7):
        trial.advance(); trial.refresh_source()
    assert trial.source.seal_correspondence_status == "compatible"
    assert json.dumps(old.as_dict(), sort_keys=True) == before
    relation = trial.source.as_dict()["seal_relation"]
    assert relation["establishes_surface_identity"] is False and relation["establishes_latch_task"] is False
    assert relation["establishes_nourishment"] is False


def test_foreign_request_region_and_old_source_are_rejected():
    trial, mapper, request = fresh()
    bad_origin = replace(request.origin, stream=MotorStreamRefV1("other", 1))
    with pytest.raises(ValueError):
        mapper.propose_oral_closure(replace(request, origin=bad_origin), trial.source, at_tick=0)
    with pytest.raises(ValueError):
        mapper.propose_oral_closure(replace(request, region_id="other"), trial.source, at_tick=0)
    with pytest.raises(ValueError):
        mapper.propose_oral_closure(request, trial.source, at_tick=1)


def test_stale_copied_and_changed_basis_proposals_cannot_reserve():
    trial, mapper, _ = fresh()
    proposal = trial.proposal
    with pytest.raises(ValueError):
        mapper.reserve(replace(proposal), execution_id="exec", at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(proposal, execution_id="exec", at_tick=1)
    sample = replace(trial.latest_feedback, sample_id=2, oral_seal=OralSealFeedbackV1(0.1, False))
    with pytest.raises(ValueError):
        mapper.update_feedback(sample, at_tick=0)
    assert mapper.current_feedback(at_tick=0) == trial.latest_feedback


@pytest.mark.parametrize("other_kind", ["support", "reach"])
def test_closure_excludes_other_movement_and_other_movement_excludes_closure(other_kind):
    trial, _, request = fresh()
    mapper = BodyTargetMapperV1(trial.latest_feedback.stream,
                               nominal_body_capabilities_v1() + (oral_body_capability_v1(), oral_closure_capability_v1()))
    mapper.update_feedback(trial.latest_feedback, at_tick=0)
    closure = mapper.propose_oral_closure(request, trial.source, at_tick=0)
    mapper.reserve(closure, execution_id="exec", at_tick=0)
    if other_kind == "support":
        other = mapper.propose(BodyMovementRequestV1(request.origin, desired_extension=0.9), at_tick=0)
    else:
        other = mapper.propose_oral_reach(OralReachRequestV1(request.origin, request.source_map_ref, request.region_id), trial.source, at_tick=0)
    assert other.bindings == ()
    assert other.withheld[0][1] == "incompatible_body_resource_reserved"
    current = mapper.reservations(at_tick=0)[0]
    mapper.cancel(current, at_tick=0)
    if other_kind == "support":
        other = mapper.propose(BodyMovementRequestV1(request.origin, desired_extension=0.9), at_tick=0)
    else:
        other = mapper.propose_oral_reach(OralReachRequestV1(request.origin, request.source_map_ref, request.region_id), trial.source, at_tick=0)
    mapper.reserve(other, execution_id="exec", at_tick=0)
    denied = mapper.propose_oral_closure(request, trial.source, at_tick=0)
    assert denied.withheld == ((KIND, "incompatible_body_resource_reserved"),)


def test_no_in_place_closure_refinement_or_duplicate_installation():
    trial = OralSealTrialV1()
    mapper = trial.body.motor_targets
    reservation = trial.targets[0]
    with pytest.raises((ValueError, RuntimeError)):
        trial.controller.install(trial.targets, at_tick=0)
    with pytest.raises(ValueError):
        mapper.refine(reservation, endpoint=0.4, at_tick=0)


@pytest.mark.parametrize("case,reason", [("body_shift", "oral_closure_anchor_changed"), ("reach_shift", "oral_closure_anchor_changed"),
                                       ("support_loss", "unexpected_contact_loss")])
def test_new_local_evidence_stops_old_permission(case, reason):
    trial = OralSealTrialV1(case)
    results = [trial.advance() for _ in range(5)]
    assert any(report.reason == reason for step in results for report in step.reports)
    assert results[-1].command is None


def test_missing_feedback_never_renews_lease_and_recovery_needs_reset():
    trial = OralSealTrialV1("dropout")
    results = [trial.advance() for _ in range(12)]
    assert all(step.command is None for step in results[8:])
    old = trial.targets[0]
    trial.reset()
    assert trial.world.tick == 0 and trial.world.stream.generation == 2
    assert trial.source.stream.generation == 2 and trial.world.oral_seal_body.closure == 0
    with pytest.raises((ValueError, RuntimeError)):
        trial.body.motor_targets.validate_reservation(old, at_tick=0)


@pytest.mark.parametrize("change", [{"desired_closure": True}, {"desired_closure": -0.1}, {"desired_closure": 1.1},
                                    {"lease_ticks": 9}, {"lease_ticks": False}])
def test_request_keeps_finite_explicit_bounds(change):
    _, _, request = fresh()
    with pytest.raises((ValueError, TypeError)):
        replace(request, **change)
