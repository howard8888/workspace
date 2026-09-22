"""Selected seeking source, task, immutable prediction and authority contracts."""

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralFeedbackV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import OralReachRequestV1
from nca8_feeding import FeedingDetailCandidateV1, FeedingDetailNavMapStateV1
from nca8_prediction import SeekNipplePreviewV1
from nca8_seek_nipple import SeekNippleIPV1, SeekNippleProfileV1, SeekNippleTaskV1
from nca8_seek_nipple_demo import create_seek_nipple_trial_v1, run_seek_nipple_v1
from nca8_sensorimotor_contracts import SensorimotorTargetKindV1


def prepared():
    """Use real admitted source products, then isolate a fresh task owner."""
    trial = create_seek_nipple_trial_v1()
    cycle = trial.focal_step()
    owner = SeekNippleIPV1(trial.core.feeding_detail, SeekNippleProfileV1())
    trial.core.feeding_detail.clear_influence()
    owner.prepare(cycle.feeding_detail_source)
    return trial, cycle, owner


@pytest.fixture(scope="module")
def first():
    return create_seek_nipple_trial_v1().focal_step()


@pytest.mark.parametrize("field", ["enabled", "influence_enabled"])
@pytest.mark.parametrize("value", [None, 0, 1, 0.0, "false", []])
def test_task_switches_are_explicit_booleans(field, value):
    with pytest.raises(TypeError):
        SeekNippleProfileV1(**{field: value})


@pytest.mark.parametrize("value", ["", " padded", "padded ", "a\nb", "a\x00b", "é", "x" * 101, 1, None])
@pytest.mark.parametrize("field", ["task_id", "region_id"])
def test_task_identity_is_bounded_unchanged_printable_ascii(field, value):
    options = {"task_id": "task", "region_id": "region_2", "started_cycle": 1, "started_tick": 0}
    options[field] = value
    with pytest.raises((TypeError, ValueError)):
        SeekNippleTaskV1(**options)


@pytest.mark.parametrize("field,value", [("started_tick", -1), ("started_tick", True), ("started_tick", 2**63),
                                        ("started_cycle", 0), ("started_cycle", 1.0), ("started_cycle", "1"),
                                        ("applications", -1), ("applications", 13), ("applications", False), ("status", "latched")])
def test_task_bounds_cannot_be_coerced_or_claim_latch(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(SeekNippleTaskV1("task", "region_2", 1, 0), **{field: value})


def test_current_mouth_is_derived_from_one_original_acquisition(first):
    source = first.feeding_detail_source
    feedback = source.oral_feedback
    assert source.maternal is first.maternal_source
    assert source.maternal.visual is first.visual_source
    assert source.oral_evidence_current and source.mouth_position == NavPointV1(0, 0)
    assert source.mouth_detail_distance == pytest.approx(0.1) and source.oral_contact is False
    assert feedback.sample_id == source.maternal.visual.sample_id
    assert feedback.event_tick == source.maternal.visual.event_tick == 0
    assert source.as_dict()["oral_relation"]["contact_identifies_surface"] is False


@pytest.mark.parametrize("change", ["sample", "frame", "position", "heading", "oral", "extension", "planar"])
def test_missing_or_mismatched_body_cannot_be_reconstructed_from_detail(first, change):
    source = first.feeding_detail_source
    feedback = source.oral_feedback
    if change == "sample":
        feedback = replace(feedback, sample_id=2)
    elif change == "frame":
        feedback = replace(feedback, planar=replace(feedback.planar, frame_id="scene_xy:other"))
    elif change == "position":
        feedback = replace(feedback, planar=replace(feedback.planar, position=(0.01, 0.0)))
    elif change == "heading":
        feedback = replace(feedback, planar=replace(feedback.planar, heading_degrees=None))
    elif change == "oral":
        feedback = replace(feedback, oral=None)
    elif change == "extension":
        feedback = replace(feedback, oral=OralFeedbackV1(None, False))
    elif change == "planar":
        feedback = replace(feedback, planar=None, oral=None)
    changed = replace(source, oral_feedback=feedback)
    assert changed.mouth_position is None and changed.mouth_detail_distance is None
    assert changed.oral_evidence_current is (change == "extension")
    assert changed.detail_position == source.detail_position
    assert source.oral_evidence_current


@pytest.mark.parametrize("contact", [None, False, True])
def test_tactile_missingness_does_not_change_observed_mouth_geometry(first, contact):
    source = first.feeding_detail_source
    changed = replace(source, oral_feedback=replace(source.oral_feedback, oral=OralFeedbackV1(0, contact)))
    assert changed.oral_evidence_current and changed.mouth_detail_distance == source.mouth_detail_distance
    assert changed.oral_contact is contact


@pytest.mark.parametrize("change", [{"available_tick": 1}, {"event_tick": 1, "available_tick": 1},
                                    {"stream": MotorStreamRefV1("foreign", 1)}, {"stream": MotorStreamRefV1("seek_nipple_reference_body", 2)}])
def test_future_or_foreign_oral_feedback_cannot_enter_current_source(first, change):
    with pytest.raises(ValueError):
        replace(first.feeding_detail_source, oral_feedback=replace(first.feeding_detail_source.oral_feedback, **change))


def test_optional_pair_does_not_rewrite_default_a_b_source_contract(first):
    source = first.feeding_detail_source
    old = FeedingDetailNavMapStateV1(source.maternal, source.seed)
    export = old.as_dict()
    assert "oral_relation" not in export and export["contact_evidence"] == "not_supplied"
    assert old.mouth_position is None and old.oral_contact is None
    assert old.detail_position == source.detail_position and old.focal_accessible == source.focal_accessible


@pytest.mark.parametrize("value", [None, True, -1, 1, 20.0, "20"])
def test_relevance_rank_has_no_unbounded_or_coerced_values(first, value):
    with pytest.raises((TypeError, ValueError)):
        FeedingDetailCandidateV1(first.feeding_detail_source, value)


def test_relevance_is_owner_mediated_and_does_not_change_sensing_or_permission():
    trial, cycle, owner = prepared()
    source, wnm = trial.core.feeding_detail, cycle.calculation.navigation.wnm
    before, body = source.current.as_dict(), trial.observer_oral_body
    bid = source.candidate()
    application = owner.apply(wnm, owner.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    assert bid.current_task_persistence_rank == 0 and source.candidate().current_task_persistence_rank == 20
    assert source.current.as_dict() == before and trial.observer_oral_body == body
    assert application.contribution.origin_status == "selected_seek_nipple"
    source.clear_influence()
    assert source.candidate().current_task_persistence_rank == 0 and source.current.as_dict() == before


@pytest.mark.parametrize("expiry", [0, 9, True, 4.0, "8"])
def test_source_influence_cannot_refresh_time_or_extend_its_lease(expiry):
    trial, cycle, _ = prepared()
    source = trial.core.feeding_detail
    before = source.current.as_dict(), source.retained_counts()
    with pytest.raises((TypeError, ValueError)):
        source.retain_influence("task", cycle_id=1, expires_at_tick=expiry)
    assert (source.current.as_dict(), source.retained_counts()) == before


def test_relevance_expiry_and_unavailable_source_do_not_gain_freshness():
    trial, cycle, _ = prepared()
    source = trial.core.feeding_detail
    source.retain_influence("task", cycle_id=1, expires_at_tick=4)
    for _ in range(4):
        trial.advance_lower()
    next_cycle = trial.focal_step(visual_input_enabled=False)
    assert next_cycle.feeding_detail_source.mouth_position is None
    assert source.candidate() is None and "task_influences" not in source.retained_counts()
    assert cycle.feeding_detail_source.cutoff_tick == 0


def test_applicability_is_read_only_and_apply_consumes_only_one_current_opportunity():
    trial, cycle, owner = prepared()
    wnm = cycle.calculation.navigation.wnm
    before = owner.assessment(), trial.observer_oral_body
    one = owner.evaluate_applicability(wnm, cycle_id=1)
    assert one.eligible and owner.evaluate_applicability(wnm, cycle_id=1) == one
    assert (owner.assessment(), trial.observer_oral_body) == before and owner.task is None
    application = owner.apply(wnm, one, cycle_id=1)
    assert application.task.applications == 1 and len(owner.history()) == 1
    assert application.projection.basis is cycle.feeding_detail_source
    with pytest.raises(ValueError):
        owner.apply(wnm, one, cycle_id=1)
    assert len(owner.history()) == 1


@pytest.mark.parametrize("cycle_id", [0, True, 1.0, "1", 2**63])
def test_applicability_refuses_bad_clock(cycle_id):
    _, cycle, owner = prepared()
    with pytest.raises(ValueError):
        owner.evaluate_applicability(cycle.calculation.navigation.wnm, cycle_id=cycle_id)


def test_old_working_sample_cannot_override_a_new_owner_current_source():
    trial, cycle, owner = prepared()
    for _ in range(4):
        trial.advance_lower()
    trial.focal_step()
    assert not owner.evaluate_applicability(cycle.calculation.navigation.wnm, cycle_id=1).eligible


@pytest.mark.parametrize("bad", ["copy", "wrong_flag", "mutable_reports", "future_report", "foreign_report"])
def test_preparation_validation_is_atomic(bad):
    trial, cycle, owner = prepared()
    other = SeekNippleIPV1(trial.core.feeding_detail, SeekNippleProfileV1())
    basis, kwargs = cycle.feeding_detail_source, {}
    if bad == "copy":
        basis = replace(basis)
    elif bad == "wrong_flag":
        kwargs["movement_blocked"] = 1
    elif bad == "mutable_reports":
        kwargs["reports"] = []
    else:
        report = trial.advance_lower().reports[0]
        if bad == "future_report":
            report = replace(report, reported_tick=1)
        else:
            target = report.committed_target
            origin = replace(target.target.origin, stream=MotorStreamRefV1("foreign", 1))
            # A report/target with another stream is rejected by its own canonical validator.
            with pytest.raises((TypeError, ValueError)):
                replace(target.target, origin=origin)
            return
        kwargs["reports"] = (report,)
    before = other.assessment(), other.retained_counts()
    with pytest.raises((TypeError, ValueError)):
        other.prepare(basis, **kwargs)
    assert (other.assessment(), other.retained_counts()) == before


@pytest.mark.parametrize("field,value", [("horizon_ticks", 0), ("horizon_ticks", 9), ("horizon_ticks", True),
                                        ("horizon_ticks", 2.0), ("region_id", "other"), ("task_id", " padded"),
                                        ("scene_target", NavPointV1(0.2, 0)), ("predicted_mouth", NavPointV1(-0.01, 0)),
                                        ("predicted_mouth", NavPointV1(0.151, 0)), ("predicted_mouth", None)])
def test_sparse_prediction_validates_original_anchors_and_bounds(first, field, value):
    preview = first.calculation.navigation.application.projection
    with pytest.raises((TypeError, ValueError)):
        replace(preview, **{field: value})


def test_prediction_is_conditional_and_does_not_infer_contact(first):
    preview = first.calculation.navigation.application.projection
    assert isinstance(preview, SeekNipplePreviewV1)
    assert preview.predicted_mouth.x == pytest.approx(0.1) and preview.predicted_mouth.y == 0
    assert preview.predicted_separation == pytest.approx(0, abs=1e-12)
    assert preview.basis.oral_contact is False and preview.basis.mouth_position == NavPointV1(0, 0)
    assert "not_inferred" in preview.as_dict()["contact_prediction"]
    assert preview.as_dict()["task_outcome_consumer"] == "deferred_seek_correspondence"


@pytest.mark.parametrize("change", ["task", "primitive", "source", "origin_status", "horizon"])
def test_application_cannot_substitute_other_task_source_or_request(first, change):
    app = first.calculation.navigation.application
    options = {}
    if change == "task":
        options["task"] = replace(app.task, task_id="other")
    elif change == "primitive":
        options["primitive_id"] = "ip:other"
    elif change == "source":
        options["source_wnm_id"] = "other"
    elif change == "origin_status":
        options["contribution"] = replace(app.contribution, origin_status="supplied_requirement_fixture")
    else:
        options["contribution"] = replace(app.contribution, lease_ticks=4)
    with pytest.raises((TypeError, ValueError)):
        replace(app, **options)


@pytest.mark.parametrize("value", ["", "learned", "selected_suckle", None, True])
def test_oral_request_origin_is_explicit_not_arbitrary_task_label(first, value):
    with pytest.raises((TypeError, ValueError)):
        replace(first.calculation.navigation.application.contribution, origin_status=value)


def test_selected_target_authorization_is_once_and_original():
    trial, cycle, owner = prepared()
    wnm = cycle.calculation.navigation.wnm
    app = owner.apply(wnm, owner.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    target = cycle.reservations[0].current
    with pytest.raises(ValueError):
        owner.authorized(replace(app), (target,))
    with pytest.raises(ValueError):
        owner.authorized(app, [target])
    assert owner.authorized_target is None
    owner.authorized(app, (target,))
    assert owner.authorized_target is target and target.target.kind is SensorimotorTargetKindV1.ORAL_REACH
    with pytest.raises(ValueError):
        owner.authorized(app, (target,))


def test_reaching_uses_distinct_current_samples_not_touch_or_pnm():
    result = run_seek_nipple_v1("no_surface")
    cycles = {c.calculation.cutoff_tick: c for c in result.cycles}
    assert cycles[8].seeking_task.task.status == "active" and len(cycles[8].seeking_task.reach_samples) == 1
    proof = cycles[12].seeking_task.reach_samples
    assert [p.maternal.visual.event_tick for p in proof] == [7, 11]
    assert all(p.oral_contact is False for p in proof)
    assert cycles[12].seeking_task.task.status == "reached_detail"
    assert cycles[12].seeking_task.as_dict()["pnm_fulfilment"] == "not_evaluated"
    assert json.dumps(cycles[0].calculation.navigation.application.projection.as_dict(), sort_keys=True)
