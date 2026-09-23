"""Selected initial latch: current evidence, finite identity, projection and permission."""

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralSealFeedbackV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import OralClosureRequestV1
from nca8_prediction import Nca8PredictionRuntimeV1
from nca8_suckle import SuckleIPV1, SuckleProfileV1, SuckleTaskV1
from nca8_suckle_demo import create_suckle_trial_v1, run_suckle_v1


def prepared():
    """Use a real admitted source then isolate a fresh, unselected task owner."""
    trial = create_suckle_trial_v1()
    cycle = trial.focal_step()
    owner = SuckleIPV1(trial.core.feeding_detail, SuckleProfileV1())
    trial.core.feeding_detail.clear_influence()
    owner.prepare(cycle.feeding_detail_source)
    return trial, cycle, owner


def selected():
    trial, cycle, owner = prepared()
    wnm = cycle.calculation.navigation.wnm
    app = owner.apply(wnm, owner.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    return trial, cycle, owner, app


def sample(trial, initial, owner, *, cycle, tick, event=None, sample_id=None, closure=0.6, sealed=True, contact=True,
           feedback_changes=None, movement_blocked=False):
    """Inject a declared typed source fixture, not a physical or Navigation result.

    Both sensory products refer to the same occurrence. Independent tests below
    change identity, event, currentness or missing measurements explicitly.
    """
    old = initial.feeding_detail_source
    event = tick - 1 if event is None else event
    sample_id = event + 1 if sample_id is None else sample_id
    visual = replace(old.maternal.visual, applied_cycle=cycle, cutoff_tick=tick, event_tick=event,
                     sample_id=sample_id, available_tick=event, update_count=cycle)
    maternal = replace(old.maternal, visual=visual, last_supported_tick=event)
    feedback = replace(old.oral_feedback, sample_id=sample_id, event_tick=event, available_tick=event,
                       oral=replace(old.oral_feedback.oral, contact=contact), oral_seal=OralSealFeedbackV1(closure, sealed),
                       **(feedback_changes or {}))
    source = trial.core.feeding_detail.update(maternal, oral_feedback=feedback)
    owner.prepare(source, movement_blocked=movement_blocked)
    return source


@pytest.fixture(scope="module")
def first():
    return create_suckle_trial_v1().focal_step()


@pytest.mark.parametrize("field", ["enabled", "influence_enabled"])
@pytest.mark.parametrize("value", [None, 0, 1, 0.0, "false", []])
def test_profile_requires_real_booleans(field, value):
    with pytest.raises(TypeError):
        SuckleProfileV1(**{field: value})


@pytest.mark.parametrize("field", ["task_id", "region_id"])
@pytest.mark.parametrize("value", ["", " padded", "padded ", "a\nb", "a\x00b", "é", "x" * 101, 1, None])
def test_task_identity_is_bounded_without_alias_normalization(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(SuckleTaskV1("task", "region", 1, 0), **{field: value})


@pytest.mark.parametrize("field,value", [("started_tick", -1), ("started_tick", True), ("started_tick", 2**63),
                                        ("started_cycle", 0), ("started_cycle", 1.0), ("started_cycle", "1"),
                                        ("applications", -1), ("applications", 13), ("applications", False),
                                        ("status", "milk_drinking"), ("status", "full_suckle_complete")])
def test_task_cannot_coerce_counters_or_claim_full_feeding(field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(SuckleTaskV1("task", "region", 1, 0), **{field: value})


@pytest.mark.parametrize("source,profile", [(None, SuckleProfileV1()), (object(), SuckleProfileV1()), (None, None)])
def test_owner_requires_explicit_owning_source(source, profile):
    with pytest.raises(TypeError):
        SuckleIPV1(source, profile)


def test_current_sensory_product_is_distinct_from_target_and_forecast(first):
    app, source = first.calculation.navigation.application, first.feeding_detail_source
    assert app.primitive_id == "ip:suckle" and app.contribution.origin_status == "selected_suckle"
    assert source.oral_feedback.oral_seal.closure == 0 and source.oral_sealed is False
    assert source.contact_correspondence_status == "compatible" and source.mouth_position == NavPointV1(0.1, 0)
    assert app.projection.basis is source and app.projection.scene_target == source.detail_position
    assert app.projection.predicted_closure == 0.6 and app.projection.as_dict()["predicted_seal"]
    assert app.projection.as_dict()["status"] == "conditional_not_observed"
    assert app.projection.as_dict()["task_outcome_consumer"] == "deferred_suckle_correspondence"
    assert first.receipt.dispatch.motor.projection is app.projection
    assert first.commitment.task_action == "SUCKLE_INITIAL_LATCH"


def test_prepare_and_query_are_read_only_and_apply_is_once():
    trial, cycle, owner = prepared()
    wnm = cycle.calculation.navigation.wnm
    original = owner.assessment(), trial.observer_oral_seal_body, trial.core.feeding_detail.current.as_dict()
    check = owner.evaluate_applicability(wnm, cycle_id=1)
    assert check.eligible and owner.task is None and not owner.history()
    assert owner.evaluate_applicability(wnm, cycle_id=1) == check
    assert original == (owner.assessment(), trial.observer_oral_seal_body, trial.core.feeding_detail.current.as_dict())
    app = owner.apply(wnm, check, cycle_id=1)
    assert owner.task.applications == 1 and len(owner.history()) == 1
    assert trial.observer_oral_seal_body == original[1]
    assert app.task.as_dict()["full_suckle_complete"] is False
    with pytest.raises(ValueError):
        owner.apply(wnm, check, cycle_id=1)


@pytest.mark.parametrize("clock", [0, True, 1.0, "1", 2**63])
def test_applicability_rejects_invalid_clock(clock):
    _, cycle, owner = prepared()
    with pytest.raises(ValueError):
        owner.evaluate_applicability(cycle.calculation.navigation.wnm, cycle_id=clock)


def test_old_working_sample_cannot_override_new_current_source():
    trial, cycle, owner = prepared()
    for _ in range(4):
        trial.advance_lower()
    trial.focal_step()
    assert not owner.evaluate_applicability(cycle.calculation.navigation.wnm, cycle_id=1).eligible


@pytest.mark.parametrize("change", ["copy", "repeated", "wrong_flag", "mutable_reports", "future_report", "foreign_report"])
def test_bad_preparation_leaves_owner_unchanged(change):
    trial, cycle, owner = prepared()
    candidate = owner if change == "repeated" else SuckleIPV1(trial.core.feeding_detail, SuckleProfileV1())
    basis, kwargs = cycle.feeding_detail_source, {}
    if change == "copy":
        basis = replace(basis)
    elif change == "wrong_flag":
        kwargs["movement_blocked"] = 1
    elif change == "mutable_reports":
        kwargs["reports"] = []
    elif change in {"future_report", "foreign_report"}:
        report = trial.advance_lower().reports[0]
        if change == "future_report":
            report = replace(report, reported_tick=1)
        else:
            target = report.committed_target
            origin = replace(target.target.origin, stream=MotorStreamRefV1("foreign", 1))
            report = replace(report, committed_target=replace(target, target=replace(
                target.target, origin=origin, basis=replace(target.target.basis, stream=origin.stream))),
                             feedback=replace(report.feedback, stream=origin.stream) if report.feedback else None)
        kwargs["reports"] = (report,)
    before = candidate.assessment(), candidate.retained_counts()
    with pytest.raises((TypeError, ValueError)):
        candidate.prepare(basis, **kwargs)
    assert before == (candidate.assessment(), candidate.retained_counts())


@pytest.mark.parametrize("change", ["task", "primitive", "source", "origin_status", "horizon", "coordinate", "region"])
def test_application_links_cannot_be_substituted(first, change):
    app = first.calculation.navigation.application
    options = {}
    if change == "task":
        options["task"] = replace(app.task, task_id="other")
    elif change == "primitive":
        options["primitive_id"] = "ip:other"
    elif change == "source":
        options["source_wnm_id"] = "other"
    else:
        field, value = {"origin_status": ("origin_status", "supplied_requirement"), "horizon": ("lease_ticks", 4),
                        "coordinate": ("desired_closure", 0.5), "region": ("region_id", "other")}[change]
        options["contribution"] = replace(app.contribution, **{field: value})
    with pytest.raises((TypeError, ValueError)):
        replace(app, **options)


@pytest.mark.parametrize("field,value", [("predicted_closure", float("nan")), ("predicted_closure", float("inf")),
                                        ("predicted_closure", True), ("predicted_closure", -0.1), ("predicted_closure", 0.5),
                                        ("predicted_closure", "0.6"), ("horizon_ticks", 0), ("horizon_ticks", 9),
                                        ("horizon_ticks", True), ("task_id", " padded"), ("region_id", "other"),
                                        ("scene_target", NavPointV1(0.2, 0))])
def test_preview_requires_original_relation_and_fixed_calculation(first, field, value):
    with pytest.raises((TypeError, ValueError)):
        replace(first.calculation.navigation.application.projection, **{field: value})


@pytest.mark.parametrize("value", ["", "learned", "selected_seek_nipple", None, True])
def test_closure_origin_is_not_an_arbitrary_task_label(first, value):
    with pytest.raises((TypeError, ValueError)):
        replace(first.calculation.navigation.application.contribution, origin_status=value)


def test_old_supplied_request_export_is_preserved(first):
    request = first.calculation.navigation.application.contribution
    supplied = OralClosureRequestV1(request.origin, request.source_map_ref, request.region_id, 0.6)
    assert supplied.origin_status == "supplied_requirement"
    assert supplied.as_dict()["origin_status"] == "supplied_requirement"


def test_actual_target_can_be_bound_once_only():
    _, cycle, owner, app = selected()
    target = cycle.reservations[0].current
    with pytest.raises(ValueError):
        owner.authorized(replace(app), (target,))
    with pytest.raises(ValueError):
        owner.authorized(app, [target])
    owner.authorized(app, (target,))
    assert owner.authorized_target is target
    with pytest.raises(ValueError):
        owner.authorized(app, (target,))


def test_authorization_refuses_foreign_origin_and_duplicate_targets():
    _, cycle, owner, app = selected()
    target = cycle.reservations[0].current
    foreign = replace(target, target=replace(target.target, origin=replace(target.target.origin, task_id="other")))
    for targets in ((foreign,), (target, target), (None,)):
        with pytest.raises(ValueError):
            owner.authorized(app, targets)
    assert owner.authorized_target is None
    owner.authorized(app, ())
    assert owner.authorized_target is None and owner.task.status == "active"


def test_source_influence_is_relevance_not_observation_or_permission():
    trial, cycle, owner = prepared()
    source, wnm = trial.core.feeding_detail, cycle.calculation.navigation.wnm
    before = source.current.as_dict(), trial.observer_oral_seal_body
    assert source.candidate().current_task_persistence_rank == 0
    owner.apply(wnm, owner.evaluate_applicability(wnm, cycle_id=1), cycle_id=1)
    assert source.candidate().current_task_persistence_rank == 20
    assert before == (source.current.as_dict(), trial.observer_oral_seal_body)
    source.clear_influence(task_id="an_earlier_seeking_task")
    assert source.candidate().current_task_persistence_rank == 20
    source.clear_influence(task_id=owner.task.task_id)
    assert source.candidate().current_task_persistence_rank == 0


@pytest.mark.parametrize("value", [False, 1, "", []])
def test_invalid_scoped_release_does_not_delete_other_task(value):
    trial, _, owner, _ = selected()
    source = trial.core.feeding_detail
    with pytest.raises(ValueError):
        source.clear_influence(task_id=value)
    assert source.candidate().current_task_persistence_rank == 20 and owner.task.status == "active"


def test_completed_seeking_does_not_erase_later_suckle_influence():
    trial = create_suckle_trial_v1()
    first_cycle = trial.focal_step()
    task_id = first_cycle.suckle_task.task.task_id
    for _ in range(4):
        trial.advance_lower()
    second = trial.focal_step()
    assert second.seeking_task.task is None  # Already at the detail; no seeking task was needed.
    assert trial.core.feeding_detail.candidate().current_task_persistence_rank == 20
    trial.core.feeding_detail.clear_influence(task_id=task_id)
    assert trial.core.feeding_detail.candidate().current_task_persistence_rank == 0


def test_two_distinct_post_start_acquisitions_not_repeated_cached_read():
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=1, event=0, sample_id=1)
    assert owner.assessment().latch_samples == ()
    sample(trial, initial, owner, cycle=3, tick=2, event=1, sample_id=2)
    assert len(owner.assessment().latch_samples) == 1
    sample(trial, initial, owner, cycle=4, tick=3, event=1, sample_id=2)
    assert len(owner.assessment().latch_samples) == 1 and owner.task.status == "active"
    sample(trial, initial, owner, cycle=5, tick=6, event=5, sample_id=6)
    assert owner.task.status == "latch_established"
    assert [x.maternal.visual.event_tick for x in owner.assessment().latch_samples] == [1, 5]


@pytest.mark.parametrize("sealed", [False, None])
def test_contradiction_or_unknown_seal_breaks_proof(sealed):
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=2)
    sample(trial, initial, owner, cycle=3, tick=4, sealed=sealed)
    assert owner.assessment().latch_samples == () and owner.task.status == "active"
    sample(trial, initial, owner, cycle=4, tick=6)
    assert len(owner.assessment().latch_samples) == 1 and owner.task.status == "active"


def test_disqualifying_inter_sample_gap_requires_new_proof():
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=2)
    sample(trial, initial, owner, cycle=3, tick=11)
    assert len(owner.assessment().latch_samples) == 1 and owner.task.status == "active"


@pytest.mark.parametrize("field", ["support_contact", "body_tilt_degrees", "useful_loading", "destabilization"])
def test_unknown_support_withholds_without_claiming_known_support_loss(field):
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=4, feedback_changes={field: None})
    assert owner.task.status == "active" and owner.assessment().reason == "oral_support_unavailable"
    assert owner.assessment().cancel_previous is False  # No target was authorized by this isolated fixture.
    sample(trial, initial, owner, cycle=3, tick=12, feedback_changes={field: None})
    assert owner.task.status == "evidence_unavailable"


@pytest.mark.parametrize("field,value", [("support_contact", False), ("body_tilt_degrees", 13),
                                        ("useful_loading", 0.74), ("destabilization", 0.26)])
def test_known_unsafe_support_is_an_explicit_interruption(field, value):
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=4, feedback_changes={field: value})
    assert owner.task.status == "support_interrupted" and not owner.assessment().latch_samples


def test_evidence_expiry_cannot_be_rescued_at_exclusive_deadline():
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=4, contact=None)
    sample(trial, initial, owner, cycle=3, tick=12)
    assert owner.task.status == "evidence_unavailable"
    sample(trial, initial, owner, cycle=4, tick=16)
    assert owner.task.status == "evidence_unavailable" and owner.task.applications == 1


@pytest.mark.parametrize("cycle,tick", [(13, 12), (2, 48)])
def test_original_focal_and_physical_deadlines_apply_even_to_good_late_evidence(cycle, tick):
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=cycle, tick=tick)
    assert owner.task.status == "budget_exhausted" and owner.task.started_tick == 0


def test_cancellation_is_sticky_but_does_not_rewrite_established_latch():
    trial, initial, owner, _ = selected()
    sample(trial, initial, owner, cycle=2, tick=2)
    sample(trial, initial, owner, cycle=3, tick=6)
    proof = owner.assessment().latch_samples
    owner.cancel()
    assert owner.task.status == "latch_established"
    sample(trial, initial, owner, cycle=4, tick=10, sealed=False)
    assert owner.task.status == "latch_established" and owner.assessment().latch_samples == proof
    assert owner.assessment().current_seal_status == "no_seal"


def test_active_cancellation_and_recovery_never_restart_task():
    trial, initial, owner, _ = selected()
    owner.cancel()
    sample(trial, initial, owner, cycle=2, tick=4, closure=0, sealed=False)
    assert owner.task.status == "cancelled" and owner.assessment().reason == "cancelled"
    assert owner.task.applications == 1


def test_latch_local_and_task_prediction_results_stay_distinct():
    result = run_suckle_v1()
    done = next(c for c in result.run.cycles if c.suckle_task.task is not None and c.suckle_task.task.status == "latch_established")
    assert done.suckle_task.as_dict()["pnm_fulfilment"] == "not_evaluated"
    assert done.as_dict()["suckle_learning_status"] == "unimplemented_no_participation"
    assert done.suckle_task.task.as_dict()["milk"] == "not_supplied"
    assert done.suckle_task.task.as_dict()["causal_credit"] == "not_established"


def test_preview_registration_uses_existing_single_slot_not_second_world(first):
    registry = Nca8PredictionRuntimeV1()
    preview = first.calculation.navigation.application.projection
    registry.adopt_suckle_preview(preview)
    assert registry.current_suckle_preview is preview and registry.current_pnm is preview.pnm
    assert registry.current_seeking_preview is None and registry.current_support_preview is None
    registry.adopt_support_preview(None)
    assert registry.current_suckle_preview is None and registry.current_pnm is None
    assert json.dumps(preview.as_dict(), sort_keys=True)


@pytest.mark.parametrize("field,value", [("status", "latch_established"), ("applications", 0),
                                        ("started_cycle", 2), ("started_tick", 1)])
def test_application_cannot_forge_terminal_or_not_yet_started_task(first, field, value):
    app = first.calculation.navigation.application
    with pytest.raises(ValueError):
        replace(app, task=replace(app.task, **{field: value}))


def test_no_target_report_does_not_silently_end_existing_lease():
    trial, initial, owner, app = selected()
    owner.authorized(app, (initial.reservations[0].current,))
    sample(trial, initial, owner, cycle=2, tick=4, closure=0.3, sealed=False)
    assert owner.assessment().local_target_busy
    assert owner.assessment().reason == "authorized_closure_continues"


def test_earlier_completed_seek_in_continuous_run_cannot_erase_later_latch_influence():
    result = run_suckle_v1("seek_then_latch")
    cycle = next(c for c in result.run.cycles if c.calculation.cutoff_tick == 12)
    assert cycle.seeking_task.task.status == "reached_detail"
    # An actually selected later Suckle task is still under its own original lease.
    assert cycle.suckle_task.task.status == "active" and cycle.suckle_task.reason == "authorized_closure_continues"
    feeding_bid = cycle.calculation.attention.selected_bid
    assert feeding_bid.source_map_state is cycle.feeding_detail_source
    assert feeding_bid.current_task_persistence_rank == 20
