"""Current feeding evidence maps to one bounded body-dependent oral target."""

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralFeedbackV1
from cca8_support_world import (
    MotorBodyStateV1, MotorWorldProfileV1, MotorWorldV1, OralWorldProfileV1,
    PlanarWorldProfileV1, PlanarObjectV1, PlanarDetailObjectV1,
)
from nca8_adapters import admit_motor_visual_surface_v1
from nca8_body_targets import (
    BodyMovementRequestV1, BodyTargetMapperV1, OralReachRequestV1, oral_body_capability_v1, nominal_body_capabilities_v1,
    BodyTranslationCapabilityV1, VisualApproachRequestV1,
)
from nca8_feeding import FeedingDetailSourceV1, FeedingDetailProfileV1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1
from nca8_sensorimotor import SensorimotorExecutorV1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1, TargetOriginV1
from nca8_visual import VisualSourceV1
from nca8_oral_demo import OralContactTrialV1

ORAL = SensorimotorTargetKindV1.ORAL_REACH


def fixture(*, heading=0.0, position=(0.0, 0.0), detail=(0.1, 0.0), parent=(0.2, 0.0), reach=0.0):
    physical = MotorWorldV1(MotorStreamRefV1("oral_mapping_fixture", 1), MotorWorldProfileV1(initial_body=MotorBodyStateV1(0.0, 1.0)),
                           planar_profile=PlanarWorldProfileV1(frame_id="scene_xy:oral_map", initial_heading=heading,
                               initial_position=position, objects=(PlanarObjectV1("region_1", parent), PlanarDetailObjectV1("region_2", detail))),
                           oral_profile=OralWorldProfileV1(initial_extension_metres=reach))
    feedback = physical.observe()
    visual = VisualSourceV1(feedback.stream).update(admit_motor_visual_surface_v1(physical.visual_surface(), feedback), cycle_id=1, cutoff_tick=0)
    maternal = MaternalSourceV1(feedback.stream, MaternalSeedV1()).update(visual)
    source = FeedingDetailSourceV1(feedback.stream, FeedingDetailProfileV1()).update(maternal)
    request = OralReachRequestV1(TargetOriginV1(feedback.stream, "task", "application", "envelope"), source.source_map_ref, "region_2")
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(),))
    mapper.update_feedback(feedback, at_tick=0)
    return physical, feedback, source, request, mapper


@pytest.mark.parametrize("heading,position,detail,parent,offset", [
    (0.0, (0.0, 0.0), (0.1, 0.0), (0.2, 0.0), 0.1),
    (90.0, (0.0, 0.0), (0.0, 0.1), (0.0, 0.2), 0.1),
    (-90.0, (0.0, 0.0), (0.0, -0.1), (0.0, -0.2), 0.1),
    (180.0, (0.0, 0.0), (-0.1, 0.0), (-0.2, 0.0), 0.1),
    (0.0, (1.0, 2.0), (1.1, 2.0), (1.2, 2.0), 0.1),
])
def test_corresponding_scene_body_reexpression_preserves_relation_and_target(heading, position, detail, parent, offset):
    physical, feedback, source, request, mapper = fixture(heading=heading, position=position, detail=detail, parent=parent)
    before = physical.tick, physical.oral_body, json.dumps(source.as_dict(), sort_keys=True)
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert len(proposal.bindings) == 1 and not proposal.withheld
    target = proposal.bindings[0].target
    assert target.kind is ORAL and target.offset == pytest.approx(offset)
    assert target.basis is feedback
    assert proposal.oral_preview.left_metres == pytest.approx(0.0, abs=1e-12)
    assert before == (physical.tick, physical.oral_body, json.dumps(source.as_dict(), sort_keys=True))
    assert mapper.reservations(at_tick=0) == ()
    assert proposal.as_dict()["oral_mapping"]["is_task_pnm"] is False


@pytest.mark.parametrize("heading,detail,reason", [(90.0, (0.1, 0.0), "oral_target_off_axis"),
                                                 (0.0, (0.1, 0.006), "oral_target_off_axis"),
                                                 (0.0, (0.351, 0.0), "oral_target_out_of_reach"),
                                                 (180.0, (0.1, 0.0), "oral_target_out_of_reach")])
def test_actual_heading_or_unreachable_geometry_is_not_silently_repaired(heading, detail, reason):
    _, _, source, request, mapper = fixture(heading=heading, detail=detail)
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert proposal.withheld == ((ORAL, reason),) and not proposal.bindings
    assert mapper.reservations(at_tick=0) == ()


def test_lateral_tolerance_is_explicit_and_not_perfect_contact_claim():
    _, _, source, request, mapper = fixture(detail=(0.1, 0.005))
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert proposal.bindings[0].target.endpoint == 0.1
    assert proposal.oral_preview.left_metres == 0.005
    assert proposal.oral_preview.as_dict()["establishes_contact"] is False


@pytest.mark.parametrize("reach,detail,expected", [(0.0, (0.3, 0.0), 0.15), (0.2, (0.1, 0.0), 0.1), (0.1, (0.1, 0.0), 0.1)])
def test_target_can_be_partial_retraction_or_already_at_coordinate(reach, detail, expected):
    _, _, source, request, mapper = fixture(reach=reach, detail=detail)
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert proposal.bindings[0].target.endpoint == pytest.approx(expected)
    assert abs(proposal.bindings[0].target.offset) <= 0.15


@pytest.mark.parametrize("changes,reason", [
    ({"oral": None}, "required_coordinate_missing"),
    ({"oral": OralFeedbackV1(None, False)}, "required_coordinate_missing"),
    ({"oral": OralFeedbackV1(0.0, None)}, "required_contact_evidence_missing"),
    ({"support_contact": None}, "required_support_evidence_missing"),
    ({"useful_loading": None}, "required_support_evidence_missing"),
    ({"body_tilt_degrees": None}, "required_support_evidence_missing"),
    ({"destabilization": None}, "required_support_evidence_missing"),
    ({"support_contact": False}, "oral_support_unavailable"),
    ({"useful_loading": 0.74}, "oral_support_unavailable"),
    ({"body_tilt_degrees": 12.1}, "oral_support_unavailable"),
    ({"destabilization": 0.26}, "oral_support_unavailable"),
    ({"oral": OralFeedbackV1(0.0, True)}, "oral_contact_before_target"),
])
def test_body_evidence_is_independent_of_recognition_and_cannot_be_backfilled(changes, reason):
    _, feedback, source, request, _ = fixture()
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(),))
    mapper.update_feedback(replace(feedback, **changes), at_tick=0)
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert source.focal_accessible
    assert proposal.withheld == ((ORAL, reason),) and not proposal.bindings


@pytest.mark.parametrize("field", ["position", "heading_degrees"])
def test_missing_independent_body_pose_cannot_be_inferred_from_visual_scene(field):
    _, feedback, source, request, _ = fixture()
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(),))
    mapper.update_feedback(replace(feedback, planar=replace(feedback.planar, **{field: None})), at_tick=0)
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    assert proposal.withheld == ((ORAL, "required_coordinate_missing"),)


@pytest.mark.parametrize("change,reason", [({"sample_id": 2}, "oral_source_body_acquisition_mismatch"),
                                         ({"frame_id": "scene_xy:different"}, "oral_source_frame_mismatch")])
def test_original_visual_acquisition_and_scene_must_correspond_to_body(change, reason):
    _, feedback, source, request, _ = fixture()
    if "frame_id" in change:
        feedback = replace(feedback, planar=replace(feedback.planar, **change))
    else:
        feedback = replace(feedback, **change)
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(),))
    mapper.update_feedback(feedback, at_tick=0)
    assert mapper.propose_oral_reach(request, source, at_tick=0).withheld == ((ORAL, reason),)


@pytest.mark.parametrize("kind", ["absent", "disabled", "wrong_category"])
def test_unavailable_source_never_generates_motor_geometry(kind):
    if kind == "wrong_category":
        trial = OralContactTrialV1(kind)
        assert trial.proposal.withheld == ((ORAL, "current_feeding_detail_unavailable"),)
        return
    _, _, source, request, mapper = fixture()
    value = None if kind == "absent" else replace(source, enabled=False)
    result = mapper.propose_oral_reach(request, value, at_tick=0)
    assert result.withheld == ((ORAL, "current_feeding_detail_unavailable"),)
    assert result.oral_preview.forward_metres is None


@pytest.mark.parametrize("which", ["region", "source", "generation", "cutoff", "untyped"])
def test_foreign_or_wrong_current_request_cannot_replace_pending_proposal(which):
    _, _, source, request, mapper = fixture()
    valid = mapper.propose_oral_reach(request, source, at_tick=0)
    altered = request
    tick = 0
    if which == "region":
        altered = replace(request, region_id="other")
    elif which == "source":
        altered = replace(request, source_map_ref=source.maternal.source_map_ref)
    elif which == "generation":
        altered = replace(request, origin=replace(request.origin, stream=MotorStreamRefV1(request.origin.stream.stream_id, 2)))
    elif which == "cutoff":
        tick = 1
    else:
        altered = {}
    with pytest.raises((ValueError, TypeError)):
        mapper.propose_oral_reach(altered, source, at_tick=tick)
    assert mapper.reserve(valid, execution_id="execution", at_tick=0)


@pytest.mark.parametrize("bad", [0, 9, True, 1.5])
def test_request_cannot_extend_or_coerce_lease(bad):
    _, _, _, request, _ = fixture()
    with pytest.raises((TypeError, ValueError)):
        replace(request, lease_ticks=bad)


@pytest.mark.parametrize("late", [1, 2])
def test_scene_target_cannot_commit_later_under_old_source_review(late):
    _, _, source, request, mapper = fixture()
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    with pytest.raises(ValueError, match="cutoff"):
        mapper.reserve(proposal, execution_id="execution", at_tick=late)
    assert mapper.reserve(proposal, execution_id="execution", at_tick=0)


def test_copied_proposal_and_reservation_do_not_convey_live_permission():
    _, feedback, source, request, mapper = fixture()
    proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    with pytest.raises(ValueError):
        mapper.reserve(replace(proposal), execution_id="execution", at_tick=0)
    reservations = mapper.reserve(proposal, execution_id="execution", at_tick=0)
    executor = SensorimotorExecutorV1(mapper)
    with pytest.raises(ValueError):
        executor.install((replace(reservations[0]),), at_tick=0)
    with pytest.raises(ValueError, match="consumed"):
        executor.install(reservations, at_tick=0)
    assert executor.step(feedback, at_tick=0).command is None


def test_original_fixture_install_is_consumed_once_and_refinement_cannot_rebase():
    trial = OralContactTrialV1()
    with pytest.raises(ValueError, match="consumed"):
        trial.controller.install(trial.targets, at_tick=0)
    with pytest.raises(ValueError, match="new source"):
        trial.body.motor_targets.refine(trial.targets[0], endpoint=0.101, at_tick=1)
    assert trial.targets[0].current.target.endpoint == 0.1
    assert trial.advance().command.oral_drive > 0.0


@pytest.mark.parametrize("oral_first", [True, False])
def test_oral_and_support_resources_are_exclusive_in_both_directions(oral_first):
    _, feedback, source, request, _ = fixture()
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(), nominal_body_capabilities_v1()[1]))
    mapper.update_feedback(feedback, at_tick=0)
    support = BodyMovementRequestV1(request.origin, None, 0.9)
    if oral_first:
        proposal = mapper.propose_oral_reach(request, source, at_tick=0)
    else:
        proposal = mapper.propose(support, at_tick=0)
    original = mapper.reserve(proposal, execution_id="execution", at_tick=0)
    other = mapper.propose(support, at_tick=0) if oral_first else mapper.propose_oral_reach(request, source, at_tick=0)
    assert not other.bindings and other.withheld
    assert mapper.reservations(at_tick=0) == original


def test_capability_is_opt_in_and_small_mapping_is_visible():
    assert ORAL not in {item.kind for item in nominal_body_capabilities_v1()}
    _, feedback, source, request, _ = fixture()
    reduced = replace(oral_body_capability_v1(), maximum_step=0.05, maximum_rate=0.25)
    mapper = BodyTargetMapperV1(feedback.stream, (reduced,))
    mapper.update_feedback(feedback, at_tick=0)
    target = mapper.propose_oral_reach(request, source, at_tick=0).bindings[0].target
    assert target.endpoint == 0.05 and target.max_rate == 0.25


def test_short_lease_narrows_actual_target_not_original_source_destination():
    _, _, source, request, mapper = fixture()
    proposal = mapper.propose_oral_reach(replace(request, lease_ticks=2), source, at_tick=0)
    assert source.detail_position.x == 0.1
    assert proposal.bindings[0].target.endpoint == 0.05
    assert proposal.bindings[0].target.lease_ticks == 2


def test_delayed_sample_cannot_refresh_source_or_old_target_basis():
    trial = OralContactTrialV1()
    source_before = trial.source_signature()
    target = trial.targets[0].initial.target
    for _ in range(6):
        trial.advance()
    assert trial.latest_feedback.event_tick == 5
    assert trial.latest_feedback.oral.extension_metres == 0.1
    assert target.basis.event_tick == 0 and target.basis.oral.extension_metres == 0.0
    assert target.endpoint == 0.1 and trial.source_signature() == source_before


@pytest.mark.parametrize("oral_first", [True, False])
def test_oral_and_planar_motion_cannot_share_live_resources(oral_first):
    _, feedback, source, request, _ = fixture()
    mapper = BodyTargetMapperV1(feedback.stream, (oral_body_capability_v1(),), visual_preview_enabled=True,
                               translation_capability=BodyTranslationCapabilityV1())
    mapper.update_feedback(feedback, at_tick=0)
    visual_request = VisualApproachRequestV1(request.origin, source.maternal.source_map_ref, "region_1", stand_off_metres=0.0)
    if oral_first:
        first = mapper.propose_oral_reach(request, source, at_tick=0)
    else:
        first = mapper.propose_translation(visual_request, source.maternal, at_tick=0)
    original = mapper.reserve(first, execution_id="execution", at_tick=0)
    second = (mapper.propose_translation(visual_request, source.maternal, at_tick=0) if oral_first else
              mapper.propose_oral_reach(request, source, at_tick=0))
    assert not second.bindings and second.withheld
    assert mapper.reservations(at_tick=0) == original
