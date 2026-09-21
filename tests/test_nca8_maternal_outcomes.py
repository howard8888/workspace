"""Original maternal-claim correspondence and hostile timing/identity boundaries.

Some tests deliberately alter admitted, immutable input records. These are
labelled correspondence fixtures, not claims that the physical provider produced
those alternative trajectories. Live behavior is qualified in the companion.
"""

from __future__ import annotations

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import create_follow_mom_trial_v1
from nca8_maternal_outcomes import MaternalIntervalEvidenceV1, MaternalOutcomeRuntimeV1


def prepared(case="nominal"):
    trial = create_follow_mom_trial_v1(case, outcomes_enabled=True)
    first = trial.focal_step()
    owner = trial.core.maternal_outcomes
    assert owner is not None and first.maternal_correspondence is not None
    return trial, first, owner


def buffered(ticks=12, case="nominal"):
    trial, first, owner = prepared(case)
    for _ in range(ticks):
        trial.advance_lower()
    return trial, first, owner, tuple(trial._maternal_intervals)


def snapshot(owner):
    return ([x.as_dict() for x in owner.pending()], [x.as_dict() for x in owner.history()], owner.retained_counts())


def edit_endpoint(intervals, transform):
    """Replace only the canonical endpoint evidence in a supplied correspondence fixture."""
    updated = []
    for item in intervals:
        observations = tuple(transform(obs) if obs.event_tick == 8 else obs for obs in item.observations)
        deliveries = []
        for sample in item.deliveries:
            observation = next((obs for obs in observations if obs.sample_id == sample.sample_id), None)
            if observation is not None:
                xy = None if observation.self_position is None else (observation.self_position.x, observation.self_position.y)
                sample = replace(sample, planar=replace(sample.planar, position=xy, frame_id=observation.frame_id))
            deliveries.append(sample)
        updated.append(replace(item, deliveries=tuple(deliveries), observations=observations))
    return tuple(updated)


def test_original_registration_precedes_physics_and_is_not_an_outcome():
    trial, first, owner = prepared()
    frame = first.maternal_correspondence
    claim = frame.registration
    assert trial.tick == 0 and trial.handoff_consumptions == trial.controller.installation_count == 1
    assert frame.outcomes == () and frame.pending == (claim,)
    assert claim.preview is first.calculation.navigation.application.projection
    assert claim.request is first.calculation.navigation.application.contribution
    assert claim.targets[0] is first.reservations[0].current
    assert claim.due_tick == 8 and claim.expires_at_tick == 16
    assert owner.history() == () and claim.as_dict()["grants_motor_authority"] is False


def test_historical_endpoint_is_not_the_newest_current_source_or_a_second_acquisition():
    trial, first, owner, intervals = buffered()
    basis = trial.core.maternal.current
    results = owner.consume_intervals(intervals, cutoff_tick=12)
    assert len(results) == 1
    outcome = results[0]
    assert outcome.status == "matched" and outcome.command_intervals == 5
    assert (outcome.evidence.sample_id, outcome.evidence.event_tick, outcome.evidence.available_tick) == (9, 8, 9)
    assert outcome.claim is first.maternal_correspondence.registration
    assert trial.latest_feedback.event_tick == 11
    assert trial.core.maternal.current is basis and basis.event_tick == 0
    assert outcome.as_dict()["establishes_task_completion"] is False
    assert outcome.as_dict()["causal_credit"] == "not_established"


@pytest.mark.parametrize("bad", [None, True, -1, 1.5, "12", 2**63])
def test_invalid_cutoff_changes_no_correspondence(bad):
    _, _, owner, intervals = buffered()
    before = snapshot(owner)
    with pytest.raises((TypeError, ValueError)):
        owner.consume_intervals(intervals, cutoff_tick=bad)
    assert snapshot(owner) == before


@pytest.mark.parametrize("bad", [None, 0, 1, "yes", (), []])
@pytest.mark.parametrize("field", ["outcomes_enabled", "prediction_comparison_enabled"])
def test_profile_flags_are_boolean_not_truthy(bad, field):
    with pytest.raises(TypeError):
        FollowMomProfileV1(**{field: bad})


def test_comparison_off_cannot_silently_mean_no_consumer():
    with pytest.raises(ValueError):
        FollowMomProfileV1(prediction_comparison_enabled=False)


@pytest.mark.parametrize("bad", [None, 0, 1, "true"])
def test_runtime_comparison_option_is_boolean(bad):
    with pytest.raises(TypeError):
        MaternalOutcomeRuntimeV1(MotorStreamRefV1("test", 1), compare_predictions=bad)


@pytest.mark.parametrize("kind", ["wrong_order", "duplicate", "gap", "future", "foreign", "changed_identity", "copied_target"])
def test_bad_frozen_batch_is_atomic(kind):
    _, _, owner, intervals = buffered()
    bad = list(intervals)
    cutoff = 12
    if kind == "wrong_order":
        bad[0], bad[1] = bad[1], bad[0]
    elif kind == "duplicate":
        bad.insert(1, bad[0])
    elif kind == "gap":
        bad.pop(0)
    elif kind == "future":
        cutoff = 11
    elif kind == "foreign":
        foreign = replace(bad[1].deliveries[0], stream=MotorStreamRefV1("foreign", 1))
        bad[1] = replace(bad[1], deliveries=(foreign,), observations=())
    elif kind == "changed_identity":
        sample = bad[2].deliveries[0]
        observation = replace(bad[2].observations[0], sample_id=bad[1].observations[0].sample_id)
        bad[2] = replace(bad[2], deliveries=(replace(sample, sample_id=observation.sample_id),), observations=(observation,))
    else:
        report = bad[0].reports[0]
        bad[0] = replace(bad[0], reports=(replace(report, committed_target=replace(report.committed_target)),))
    before = snapshot(owner)
    with pytest.raises((ValueError, TypeError)):
        owner.consume_intervals(tuple(bad), cutoff_tick=cutoff)
    assert snapshot(owner) == before


def test_consumed_intervals_cannot_be_replayed_with_a_new_cutoff():
    _, _, owner, intervals = buffered()
    owner.consume_intervals(intervals, cutoff_tick=12)
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals(intervals, cutoff_tick=13)
    assert snapshot(owner) == before


def test_repeating_cutoff_cannot_expire_or_recompare():
    _, _, owner, intervals = buffered()
    owner.consume_intervals(intervals, cutoff_tick=12)
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals((), cutoff_tick=12)
    assert snapshot(owner) == before


@pytest.mark.parametrize("change,expected", [
    (lambda obs: replace(obs, self_position=None), "unknown"),
    (lambda obs: replace(obs, detections=()), "unknown"),
    (lambda obs: replace(obs, detections=tuple(replace(x, descriptor=None) for x in obs.detections)), "unknown"),
    (lambda obs: replace(obs, detections=tuple(replace(x, position=None) for x in obs.detections)), "unknown"),
    (lambda obs: replace(obs, detections=tuple(replace(x, descriptor="hazard") for x in obs.detections)), "identity_contradicted"),
    (lambda obs: replace(obs, frame_id="scene_xy:other"), "unknown"),
    (lambda obs: replace(obs, detections=tuple(replace(x, region_id="different") for x in obs.detections)), "unknown"),
])
def test_missing_frame_and_identity_are_not_known_geometry(change, expected):
    _, _, owner, intervals = buffered()
    results = owner.consume_intervals(edit_endpoint(intervals, change), cutoff_tick=12)
    assert results[0].status == expected
    assert dict(results[0].relations)["separation"] == "unknown"


@pytest.mark.parametrize("offset,expected", [(0.019, "matched"), (0.020, "matched"), (0.02001, "mismatch"), (0.06, "mismatch")])
def test_fixed_position_tolerance_is_distinct_from_proximity_and_local_tolerance(offset, expected):
    _, _, owner, intervals = buffered()
    def change(obs):
        return replace(obs, self_position=NavPointV1(obs.self_position.x + offset, obs.self_position.y))
    outcome = owner.consume_intervals(edit_endpoint(intervals, change), cutoff_tick=12)[0]
    assert dict(outcome.relations)["self_position"] == expected
    assert dict(outcome.residuals)["self_position"] == pytest.approx(offset)
    assert outcome.claim.as_dict()["residual_tolerance_metres"] == 0.02


def test_relocated_target_answers_original_anchor_without_repairing_it():
    _, first, owner, intervals = buffered()
    original = first.maternal_correspondence.registration.preview.as_dict()
    def change(obs):
        return replace(obs, detections=tuple(replace(x, position=NavPointV1(2.0, 2.0)) for x in obs.detections))
    outcome = owner.consume_intervals(edit_endpoint(intervals, change), cutoff_tick=12)[0]
    assert outcome.status == "mismatch"
    assert dict(outcome.relations) == {"self_position": "matched", "maternal_anchor": "mismatch", "separation": "mismatch"}
    assert outcome.claim.preview.as_dict() == original
    assert outcome.claim.preview.scene_target == NavPointV1(2.0, 1.0)


@pytest.mark.parametrize("availability,status", [(9, "matched"), (16, "matched"), (17, "expired_unresolved")])
def test_original_availability_window_not_latest_sample_controls_delayed_endpoint(availability, status):
    _, _, owner, intervals = buffered(16)
    original_interval = intervals[8]
    sample = replace(original_interval.deliveries[0], available_tick=availability)
    observation = replace(original_interval.observations[0], available_tick=availability)
    batch = [replace(item, deliveries=(), observations=()) if item.tick == 8 else item for item in intervals]
    if availability <= 16:
        destination = availability - 1
        batch[destination] = replace(batch[destination], deliveries=(*batch[destination].deliveries, sample),
                                      observations=(*batch[destination].observations, observation))
        results = owner.consume_intervals(tuple(batch), cutoff_tick=16)
    else:
        assert owner.consume_intervals(tuple(batch), cutoff_tick=16) == ()
        results = owner.consume_intervals((MaternalIntervalEvidenceV1(16, None, (), (sample,), (observation,)),), cutoff_tick=17)
    assert results[0].status == status
    assert results[0].claim.due_tick == 8


def test_missing_original_endpoint_is_not_replaced_by_a_later_nearby_acquisition():
    _, _, owner, intervals = buffered(16)
    batch = tuple(replace(item, observations=()) if item.tick == 8 else item for item in intervals)
    assert owner.consume_intervals(batch, cutoff_tick=16) == ()
    assert len(owner.pending()) == 1
    outcome = owner.consume_intervals((MaternalIntervalEvidenceV1(16, None, (), (), ()),), cutoff_tick=17)[0]
    assert outcome.status == "expired_unresolved" and outcome.evidence is None


def test_uninstalled_or_copied_registration_cannot_borrow_execution():
    trial, first, _ = prepared()
    owner = MaternalOutcomeRuntimeV1(trial.latest_feedback.stream)
    owner.consume_intervals((), cutoff_tick=0)
    claim = owner.register(first.calculation.navigation.application, first.calculation.proposal,
                           tuple(x.current for x in first.reservations))
    with pytest.raises(ValueError):
        owner.installed(replace(claim), at_tick=0)
    trial.advance_lower()
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(trial._maternal_intervals), cutoff_tick=1)
    owner.installed(claim, at_tick=0)
    with pytest.raises(ValueError):
        owner.installed(claim, at_tick=0)


@pytest.mark.parametrize("kind", ["copied_binding", "changed_request", "foreign_stream", "wrong_tick", "duplicate"])
def test_registration_preserves_original_proposal_links(kind):
    trial, first, _ = prepared()
    owner = MaternalOutcomeRuntimeV1(trial.latest_feedback.stream)
    owner.consume_intervals((), cutoff_tick=0)
    application, proposal = first.calculation.navigation.application, first.calculation.proposal
    targets = tuple(x.current for x in first.reservations)
    before = snapshot(owner)
    with pytest.raises((ValueError, RuntimeError)):
        if kind == "copied_binding":
            targets = (replace(targets[0], target=replace(targets[0].target)),)
        elif kind == "changed_request":
            proposal = replace(proposal, request=replace(proposal.request))
        elif kind == "foreign_stream":
            owner = MaternalOutcomeRuntimeV1(MotorStreamRefV1("foreign", 1))
            owner.consume_intervals((), cutoff_tick=0)
        elif kind == "wrong_tick":
            targets = (replace(targets[0], committed_tick=1),)
        else:
            registered = owner.register(application, proposal, targets)
            owner.installed(registered, at_tick=0)
            before = snapshot(owner)
        owner.register(application, proposal, targets)
    assert snapshot(owner) == before


def test_full_veto_is_nonapplication_not_an_observed_failure():
    _, first, owner = prepared("veto")
    outcome = first.maternal_correspondence.outcomes[0]
    assert not first.reservations and not owner.pending()
    assert outcome.status == "not_applied" and outcome.command_intervals == 0 and outcome.evidence is None
    assert outcome.claim.preview.predicted_separation < outcome.claim.preview.basis.separation


def test_narrowed_original_relations_are_not_rewritten():
    trial, first, owner, intervals = buffered(case="narrowed")
    claim = first.maternal_correspondence.registration
    assert claim.compatible_relations == ("maternal_anchor",)
    assert claim.unevaluable_relations == ("self_position", "separation")
    outcome = owner.consume_intervals(intervals, cutoff_tick=12)[0]
    assert outcome.status == "partly_matched"
    assert dict(outcome.relations) == {"self_position": "unevaluable_authorization", "maternal_anchor": "matched",
                                      "separation": "unevaluable_authorization"}
    assert dict(outcome.residuals)["self_position"] == pytest.approx(0.15)
    assert outcome.command_intervals == 2
    assert trial.controller.reports[0].disposition.value == "achieved"


@pytest.mark.parametrize("cancel_tick,expected", [(0, "cancelled"), (2, "interrupted"), (8, "matched")])
def test_cancellation_respects_realized_endpoint_and_buffered_exposure(cancel_tick, expected):
    trial, _, owner = prepared()
    for _ in range(cancel_tick):
        trial.advance_lower()
    trial.cancel()
    while trial.tick < 12:
        trial.advance_lower()
    outcome = owner.consume_intervals(tuple(trial._maternal_intervals), cutoff_tick=12)[0]
    assert outcome.status == expected
    assert outcome.command_intervals == min(cancel_tick, 5)


def test_removing_command_exposure_cannot_earn_action_credit():
    _, _, owner, intervals = buffered()
    batch = tuple(replace(item, command=None) for item in intervals)
    outcome = owner.consume_intervals(batch, cutoff_tick=12)[0]
    assert outcome.status == "observed_without_command" and outcome.command_intervals == 0
    assert dict(outcome.relations)["self_position"] == "matched"
    assert outcome.as_dict()["causal_credit"] == "not_established"


def test_owner_stop_is_unresolved_not_a_fabricated_nonapplication():
    _, _, owner, _ = buffered(2)
    owner.close(reason="physical_effects_uncertain")
    assert owner.history()[0].status == "unresolved_stopped"
    assert not owner.pending()
    before = snapshot(owner)
    owner.close(reason="physical_effects_uncertain")
    assert snapshot(owner) == before
    with pytest.raises(ValueError):
        owner.consume_intervals((), cutoff_tick=12)


def test_diagnostic_export_is_detached_and_cannot_renew_claims():
    _, _, owner, intervals = buffered()
    before = snapshot(owner)
    for _ in range(10):
        exported = owner.pending()[0].as_dict()
        exported["original_preview"]["predicted_self"]["x"] = 9000
        json.dumps(exported, allow_nan=False)
    assert snapshot(owner) == before
    owner.consume_intervals(intervals, cutoff_tick=12)
    assert owner.history()[0].status == "matched"


@pytest.mark.parametrize("kind", ["duplicate_visual", "duplicate_motor", "unpaired", "position", "time", "frame"])
def test_paired_products_cannot_manufacture_a_second_occurrence(kind):
    _, _, _, intervals = buffered(3)
    item = intervals[1]
    visual = item.observations[0]
    with pytest.raises(ValueError):
        if kind == "duplicate_visual":
            replace(item, observations=(visual, visual))
        elif kind == "duplicate_motor":
            replace(item, deliveries=(*item.deliveries, item.deliveries[0]))
        elif kind == "unpaired":
            replace(item, deliveries=())
        elif kind == "position":
            replace(item, observations=(replace(visual, self_position=NavPointV1(5, 5)),))
        elif kind == "time":
            replace(item, observations=(replace(visual, available_tick=visual.available_tick + 1),))
        else:
            replace(item, observations=(replace(visual, frame_id="scene_xy:other"),))
