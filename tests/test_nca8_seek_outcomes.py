"""Original seeking correspondence, hostile input and finite lifetime contracts.

Altered immutable packets in these tests are explicit correspondence fixtures,
not claims that the physical provider generated the altered observation. Live
provider/control contrasts are in test_nca8_seek_outcomes_demo.py.
"""

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1, OralFeedbackV1
from cca8_navmap_kernel import NavPointV1
from nca8_seek_nipple import SeekNippleProfileV1
from nca8_seek_nipple_demo import create_seek_nipple_trial_v1
from nca8_seek_outcomes import SeekNippleEndpointV1, SeekNippleIntervalEvidenceV1, SeekNippleOutcomeRuntimeV1
from nca8_seek_outcomes_demo import create_seek_nipple_outcome_trial_v1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1


def prepared(case="nominal"):
    trial = create_seek_nipple_outcome_trial_v1(case)
    first = trial.focal_step()
    return trial, first, trial.core.seeking_outcomes


def buffered(ticks=12, case="nominal"):
    trial, first, owner = prepared(case)
    for _ in range(ticks):
        trial.advance_lower()
    return trial, first, owner, tuple(trial._seeking_intervals)


def snapshot(owner):
    return ([x.as_dict() for x in owner.pending()], [x.as_dict() for x in owner.history()], owner.retained_counts())


def endpoint_fixture(intervals, transform):
    """Change only event8's paired records, preserving explicit fixture provenance."""
    result = []
    for item in intervals:
        deliveries, observations = [], []
        for sample in item.deliveries:
            visual = next((obs for obs in item.observations if obs.sample_id == sample.sample_id), None)
            if sample.event_tick == 8:
                sample, visual = transform(sample, visual)
            if sample is not None:
                deliveries.append(sample)
            if visual is not None:
                observations.append(visual)
        result.append(replace(item, deliveries=tuple(deliveries), observations=tuple(observations)))
    return tuple(result)


def test_old_c_defaults_do_not_create_an_outcome_owner_or_queue():
    trial = create_seek_nipple_trial_v1()
    cycle = trial.focal_step()
    assert trial.core.seeking_outcomes is None and cycle.seeking_correspondence is None
    assert "seeking_correspondence" not in cycle.as_dict()
    assert not any(key.startswith("seeking_") for key in trial.retained_counts())
    trial.advance_lower()
    assert trial._seeking_intervals == []


def test_original_claim_and_permission_exist_before_any_physical_movement():
    trial, first, owner = prepared()
    frame, application = first.seeking_correspondence, first.calculation.navigation.application
    claim = frame.registration
    assert trial.tick == 0 and trial.controller.installation_count == trial.handoff_consumptions == 1
    assert frame.outcomes == () and frame.pending == (claim,) and owner.history() == ()
    assert claim.preview is application.projection and claim.request is application.contribution
    assert claim.targets[0] is first.reservations[0].current
    assert (claim.due_tick, claim.expires_at_tick) == (8, 16)
    assert claim.as_dict()["grants_motor_authority"] is False


def test_local_achievement_and_later_claim_are_distinct_questions():
    trial, first, owner, intervals = buffered()
    source_before = trial.core.feeding_detail.current
    assert trial.controller.reports[0].disposition.value == "achieved"
    result = owner.consume_intervals(intervals, cutoff_tick=12)[0]
    assert result.status == "matched" and result.command_intervals == 4
    assert result.claim is first.seeking_correspondence.registration
    assert (result.evidence.feedback.event_tick, result.evidence.feedback.available_tick) == (8, 9)
    assert trial.latest_feedback.event_tick == 11
    assert trial.core.feeding_detail.current is source_before
    assert result.as_dict()["establishes_task_completion"] is False
    assert result.as_dict()["establishes_contact_latch_or_milk"] is False
    assert result.as_dict()["causal_credit"] == "not_established"


@pytest.mark.parametrize("bad", [None, 0, 1, "false", (), [], 0.0])
@pytest.mark.parametrize("name", ["outcomes_enabled", "prediction_comparison_enabled"])
def test_enablement_cannot_be_coerced(bad, name):
    with pytest.raises(TypeError):
        SeekNippleProfileV1(**{name: bad})


def test_comparison_off_requires_an_actual_correspondence_owner():
    with pytest.raises(ValueError):
        SeekNippleProfileV1(prediction_comparison_enabled=False)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes", []])
def test_runtime_comparison_switch_is_boolean(bad):
    with pytest.raises(TypeError):
        SeekNippleOutcomeRuntimeV1(MotorStreamRefV1("test", 1), compare_predictions=bad)


@pytest.mark.parametrize("bad", [None, True, -1, 1.5, "12", 2**63])
def test_invalid_cutoff_is_atomic(bad):
    _, _, owner, intervals = buffered()
    before = snapshot(owner)
    with pytest.raises((TypeError, ValueError)):
        owner.consume_intervals(intervals, cutoff_tick=bad)
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["order", "duplicate", "gap", "future", "foreign", "conflict", "copied_target", "foreign_command"])
def test_bad_batch_cannot_partially_consume_claim_or_exposure(kind):
    _, _, owner, intervals = buffered()
    batch = list(intervals)
    cutoff = 12
    if kind == "order":
        batch[0], batch[1] = batch[1], batch[0]
    elif kind == "duplicate":
        batch.insert(1, batch[0])
    elif kind == "gap":
        batch.pop(0)
    elif kind == "future":
        cutoff = 11
    elif kind == "foreign":
        batch[1] = replace(batch[1], deliveries=(replace(batch[1].deliveries[0], stream=MotorStreamRefV1("foreign", 1)),), observations=())
    elif kind == "conflict":
        sample = replace(batch[2].deliveries[0], sample_id=batch[1].deliveries[0].sample_id)
        visual = replace(batch[2].observations[0], sample_id=sample.sample_id)
        batch[2] = replace(batch[2], deliveries=(sample,), observations=(visual,))
    elif kind == "copied_target":
        report = batch[0].reports[0]
        batch[0] = replace(batch[0], reports=(replace(report, committed_target=replace(report.committed_target)),))
    else:
        batch[0] = replace(batch[0], command=replace(batch[0].command, stream=MotorStreamRefV1("foreign", 1)))
    before = snapshot(owner)
    with pytest.raises((TypeError, ValueError)):
        owner.consume_intervals(tuple(batch), cutoff_tick=cutoff)
    assert snapshot(owner) == before


@pytest.mark.parametrize("kind", ["no_report", "stale_report", "terminal_report", "duplicate_report", "past_lease", "reused_command"])
def test_nonzero_oral_drive_requires_current_original_permission(kind):
    _, _, owner, intervals = buffered()
    batch = list(intervals)
    if kind == "no_report":
        batch[0] = replace(batch[0], reports=())
    elif kind == "stale_report":
        batch[1] = replace(batch[1], reports=batch[0].reports)
    elif kind == "terminal_report":
        report = batch[0].reports[0]
        batch[0] = replace(batch[0], reports=(replace(report, disposition=LocalTargetDispositionV1.CANCELLED),))
    elif kind == "duplicate_report":
        batch[0] = replace(batch[0], reports=batch[0].reports * 2)
    elif kind == "past_lease":
        batch[8] = replace(batch[8], command=replace(batch[0].command, issued_tick=8, command_id=100))
    else:
        batch[1] = replace(batch[1], command=replace(batch[1].command, command_id=batch[0].command.command_id))
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(batch), cutoff_tick=12)
    assert snapshot(owner) == before


def test_protective_report_earlier_in_same_batch_blocks_later_forged_drive():
    _, _, owner, intervals = buffered()
    batch = list(intervals)
    report = batch[0].reports[0]
    batch[0] = replace(batch[0], command=None, reports=(replace(report, disposition=LocalTargetDispositionV1.CANCELLED),))
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(batch), cutoff_tick=12)
    assert snapshot(owner) == before


@pytest.mark.parametrize("contact", [None, False, True])
def test_contact_is_neither_predicted_nor_required_for_geometric_match(contact):
    _, _, owner, intervals = buffered()
    batch = endpoint_fixture(intervals, lambda f, v: (replace(f, oral=replace(f.oral, contact=contact)), v))
    result = owner.consume_intervals(batch, cutoff_tick=12)[0]
    assert result.status == "matched" and "contact" not in dict(result.relations)
    assert result.evidence.feedback.oral.contact is contact


@pytest.mark.parametrize("offset,expected", [(0, "matched"), (0.0049, "matched"), (0.005, "matched"), (0.00501, "mismatch"), (0.02, "mismatch")])
def test_fixed_prediction_tolerance_not_local_tolerance_or_touch(offset, expected):
    _, _, owner, intervals = buffered()
    batch = endpoint_fixture(intervals, lambda f, v: (replace(f, oral=replace(f.oral, extension_metres=0.1 + offset)), v))
    result = owner.consume_intervals(batch, cutoff_tick=12)[0]
    assert dict(result.relations)["mouth_position"] == expected
    assert dict(result.residuals)["mouth_position"] == pytest.approx(offset)
    assert result.claim.as_dict()["residual_tolerance_metres"] == 0.005


@pytest.mark.parametrize("missing", ["position", "heading", "oral", "reach", "planar"])
def test_missing_body_coordinate_cannot_be_filled_from_prediction(missing):
    _, _, owner, intervals = buffered()
    def alter(feedback, visual):
        if missing == "position":
            return replace(feedback, planar=replace(feedback.planar, position=None)), replace(visual, self_position=None)
        if missing == "heading":
            return replace(feedback, planar=replace(feedback.planar, heading_degrees=None)), visual
        if missing == "oral":
            return replace(feedback, oral=None), visual
        if missing == "reach":
            return replace(feedback, oral=OralFeedbackV1(None, False)), visual
        return replace(feedback, planar=None, oral=None), None
    result = owner.consume_intervals(endpoint_fixture(intervals, alter), cutoff_tick=12)[0]
    assert result.status == "unknown" and result.evidence.mouth_position is None
    assert dict(result.relations)["mouth_position"] == "unknown"


@pytest.mark.parametrize("kind,expected", [("no_visual", "unknown"), ("no_detections", "unknown"), ("wrong_region", "unknown"),
    ("no_descriptor", "unknown"), ("no_parent", "unknown"), ("no_position", "unknown"), ("wrong_descriptor", "identity_contradicted"),
    ("wrong_parent", "identity_contradicted"), ("part_incompatible", "identity_contradicted"), ("wrong_frame", "unknown")])
def test_missing_and_contradictory_detail_correspondence_remain_distinct(kind, expected):
    _, _, owner, intervals = buffered()
    def alter(feedback, visual):
        if kind == "no_visual":
            return feedback, None
        if kind == "wrong_frame":
            return replace(feedback, planar=replace(feedback.planar, frame_id="scene_xy:other")), replace(visual, frame_id="scene_xy:other")
        details = list(visual.detections)
        if kind == "no_detections":
            details = []
        elif kind == "no_parent":
            details = [item for item in details if item.region_id == "region_2"]
        else:
            for index, item in enumerate(details):
                if kind == "wrong_parent" and item.region_id == "region_1":
                    details[index] = replace(item, descriptor="hazard")
                elif item.region_id == "region_2":
                    changes = {"wrong_region": {"region_id": "other"}, "no_descriptor": {"descriptor": None},
                               "no_position": {"position": None}, "wrong_descriptor": {"descriptor": "hazard"},
                               "part_incompatible": {"position": NavPointV1(1, 0)}}
                    details[index] = replace(item, **changes.get(kind, {}))
        return feedback, replace(visual, detections=tuple(details))
    result = owner.consume_intervals(endpoint_fixture(intervals, alter), cutoff_tick=12)[0]
    assert result.status == expected
    assert dict(result.relations)["detail_anchor"] == "unknown"


def test_relocated_detail_does_not_repair_original_stationary_anchor():
    _, first, owner, intervals = buffered()
    original = first.seeking_correspondence.registration.preview.as_dict()
    batch = endpoint_fixture(intervals, lambda f, v: (f, replace(v, detections=tuple(
        replace(item, position=NavPointV1(0.12, 0)) if item.region_id == "region_2" else item for item in v.detections))))
    result = owner.consume_intervals(batch, cutoff_tick=12)[0]
    assert result.status == "mismatch"
    assert dict(result.relations) == {"mouth_position": "matched", "detail_anchor": "mismatch", "separation": "mismatch"}
    assert result.claim.preview.as_dict() == original


@pytest.mark.parametrize("availability,status", [(9, "matched"), (16, "matched"), (17, "expired_unresolved")])
def test_late_original_endpoint_uses_availability_not_newest_source(availability, status):
    _, _, owner, intervals = buffered(16)
    source = intervals[8]
    sample = replace(source.deliveries[0], available_tick=availability)
    visual = replace(source.observations[0], available_tick=availability)
    batch = list(endpoint_fixture(intervals, lambda _f, _v: (None, None)))
    if availability <= 16:
        index = availability - 1
        batch[index] = replace(batch[index], deliveries=(*batch[index].deliveries, sample), observations=(*batch[index].observations, visual))
        result = owner.consume_intervals(tuple(batch), cutoff_tick=16)[0]
    else:
        assert owner.consume_intervals(tuple(batch), cutoff_tick=16) == ()
        result = owner.consume_intervals((SeekNippleIntervalEvidenceV1(16, None, (), (sample,), (visual,)),), cutoff_tick=17)[0]
    assert result.status == status and result.claim.due_tick == 8


def test_missing_exact_endpoint_expires_without_later_sample_substitution():
    _, _, owner, intervals = buffered(16)
    batch = endpoint_fixture(intervals, lambda _f, _v: (None, None))
    assert owner.consume_intervals(batch, cutoff_tick=16) == ()
    result = owner.consume_intervals((SeekNippleIntervalEvidenceV1(16, None, (), (), ()),), cutoff_tick=17)[0]
    assert result.status == "expired_unresolved" and result.evidence is None


def test_missing_visual_at_known_endpoint_is_unknown_not_missing_entire_event():
    _, _, owner, intervals = buffered()
    result = owner.consume_intervals(endpoint_fixture(intervals, lambda f, _v: (f, None)), cutoff_tick=12)[0]
    assert result.status == "unknown" and result.evidence.feedback.event_tick == 8
    assert dict(result.relations)["mouth_position"] == "matched"
    assert dict(result.relations)["detail_anchor"] == "unknown"


@pytest.mark.parametrize("cancel_tick,expected", [(0, "cancelled"), (2, "interrupted"), (4, "interrupted"), (8, "matched"), (9, "matched")])
def test_cancellation_preserves_realized_endpoint_and_prior_exposure(cancel_tick, expected):
    trial, _, owner = prepared()
    for _ in range(cancel_tick):
        trial.advance_lower()
    trial.cancel()
    while trial.tick < 12:
        trial.advance_lower()
    result = owner.consume_intervals(tuple(trial._seeking_intervals), cutoff_tick=12)[0]
    assert result.status == expected and result.command_intervals == min(cancel_tick, 4)


def test_no_command_is_not_execution_credit_despite_matching_geometry():
    _, _, owner, intervals = buffered()
    result = owner.consume_intervals(tuple(replace(item, command=None) for item in intervals), cutoff_tick=12)[0]
    assert result.status == "observed_without_command" and result.command_intervals == 0
    assert dict(result.relations)["mouth_position"] == "matched"
    assert result.as_dict()["causal_credit"] == "not_established"


def test_narrowing_scores_only_the_unchanged_original_relation():
    _, first, owner, intervals = buffered(case="narrowed")
    claim = first.seeking_correspondence.registration
    original = claim.preview.as_dict()
    assert claim.compatible_relations == ("detail_anchor",)
    assert claim.targets[0].target.endpoint == 0.04 and claim.preview.predicted_mouth.x == pytest.approx(0.1)
    result = owner.consume_intervals(intervals, cutoff_tick=12)[0]
    assert result.status == "partly_matched" and result.claim.preview.as_dict() == original
    assert dict(result.relations) == {"mouth_position": "unevaluable_authorization", "detail_anchor": "matched", "separation": "unevaluable_authorization"}
    assert dict(result.residuals)["mouth_position"] == pytest.approx(0.06)


@pytest.mark.parametrize("kind", ["copied_binding", "changed_request", "foreign", "wrong_tick", "duplicate", "wrong_family"])
def test_registration_requires_actual_original_selected_records(kind):
    trial, first, _ = prepared()
    owner = SeekNippleOutcomeRuntimeV1(MotorStreamRefV1("foreign", 1) if kind == "foreign" else trial.latest_feedback.stream)
    owner.consume_intervals((), cutoff_tick=0)
    application, proposal, targets = first.calculation.navigation.application, first.calculation.proposal, tuple(r.current for r in first.reservations)
    before = snapshot(owner)
    with pytest.raises((TypeError, ValueError, RuntimeError)):
        if kind == "copied_binding":
            targets = (replace(targets[0], target=replace(targets[0].target)),)
        elif kind == "changed_request":
            proposal = replace(proposal, request=replace(proposal.request))
        elif kind == "wrong_tick":
            targets = (replace(targets[0], committed_tick=1),)
        elif kind == "duplicate":
            claim = owner.register(application, proposal, targets)
            owner.installed(claim, at_tick=0)
            before = snapshot(owner)
        elif kind == "wrong_family":
            application = None
        owner.register(application, proposal, targets)
    assert snapshot(owner) == before


def test_installation_and_target_description_copies_do_not_authorize_exposure():
    trial, first, _ = prepared()
    owner = SeekNippleOutcomeRuntimeV1(trial.latest_feedback.stream)
    owner.consume_intervals((), cutoff_tick=0)
    claim = owner.register(first.calculation.navigation.application, first.calculation.proposal, tuple(r.current for r in first.reservations))
    with pytest.raises(ValueError):
        owner.installed(replace(claim), at_tick=0)
    trial.advance_lower()
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(trial._seeking_intervals), cutoff_tick=1)
    owner.installed(claim, at_tick=0)
    with pytest.raises(ValueError):
        owner.installed(claim, at_tick=0)


@pytest.mark.parametrize("kind", ["visual_duplicate", "motor_duplicate", "unpaired", "position", "time", "frame", "sample", "mutable"])
def test_invalid_paired_products_do_not_manufacture_an_occurrence(kind):
    _, _, _, intervals = buffered(3)
    item = intervals[1]
    sample, visual = item.deliveries[0], item.observations[0]
    with pytest.raises((ValueError, TypeError)):
        if kind == "visual_duplicate":
            replace(item, observations=(visual, visual))
        elif kind == "motor_duplicate":
            replace(item, deliveries=(sample, sample))
        elif kind == "unpaired":
            replace(item, deliveries=())
        elif kind == "position":
            replace(item, observations=(replace(visual, self_position=NavPointV1(9, 9)),))
        elif kind == "time":
            replace(item, observations=(replace(visual, available_tick=visual.available_tick + 1),))
        elif kind == "frame":
            SeekNippleEndpointV1(sample, replace(visual, frame_id="scene_xy:other"))
        elif kind == "sample":
            SeekNippleEndpointV1(sample, replace(visual, sample_id=99))
        else:
            replace(item, deliveries=list(item.deliveries))


def test_identical_duplicate_endpoint_cannot_consume_twice():
    _, _, owner, intervals = buffered()
    batch = list(intervals)
    original = batch[8]
    batch[9] = replace(batch[9], deliveries=(*batch[9].deliveries, original.deliveries[0]), observations=(*batch[9].observations, original.observations[0]))
    assert len(owner.consume_intervals(tuple(batch), cutoff_tick=12)) == 1
    assert len(owner.history()) == 1
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals(intervals, cutoff_tick=13)
    assert snapshot(owner) == before


def test_conflicting_motor_contact_with_same_id_is_rejected_before_scoring():
    _, _, owner, intervals = buffered()
    batch = list(intervals)
    original = batch[8]
    altered = replace(original.deliveries[0], oral=replace(original.deliveries[0].oral, contact=False))
    batch[9] = replace(batch[9], deliveries=(*batch[9].deliveries, altered), observations=(*batch[9].observations, original.observations[0]))
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.consume_intervals(tuple(batch), cutoff_tick=12)
    assert snapshot(owner) == before


def test_closed_owner_preserves_unknown_effects_and_cannot_restart():
    _, _, owner, _ = buffered(2)
    owner.close(reason="physical_effect_unknown")
    assert owner.history()[0].status == "unresolved_stopped" and not owner.pending()
    before = snapshot(owner)
    owner.close(reason="physical_effect_unknown")
    assert snapshot(owner) == before
    with pytest.raises(ValueError):
        owner.consume_intervals((), cutoff_tick=12)


def test_repeated_export_and_mutation_of_detached_values_do_not_change_owner():
    _, _, owner, intervals = buffered()
    before = snapshot(owner)
    for _ in range(4):
        value = owner.pending()[0].as_dict()
        value["original_preview"]["predicted_mouth"]["x"] = 500
        json.dumps(value, allow_nan=False)
    assert snapshot(owner) == before
    assert owner.consume_intervals(intervals, cutoff_tick=12)[0].status == "matched"


def test_protective_stop_remains_binding_after_its_pending_claim_is_retired():
    _, _, owner, intervals = buffered()
    first = intervals[0].reports[0]
    stopped = replace(first, disposition=LocalTargetDispositionV1.INTERRUPTED, reported_tick=1,
                      reason="explicit_test_protection")
    initial = (intervals[0], replace(intervals[1], command=None, reports=(stopped,)))
    assert owner.consume_intervals(initial, cutoff_tick=2)[0].status == "interrupted"
    assert owner.pending() == ()
    before = snapshot(owner)
    with pytest.raises(ValueError, match="cancellation"):
        owner.consume_intervals(intervals[2:4], cutoff_tick=4)
    assert snapshot(owner) == before


def test_awaiting_installation_cannot_be_overwritten_by_another_registration():
    _, first, _, _ = buffered()
    application = first.calculation.navigation.application
    proposal = first.calculation.proposal
    owner = SeekNippleOutcomeRuntimeV1(application.contribution.origin.stream)
    owner.consume_intervals((), cutoff_tick=0)
    owner.register(application, proposal, tuple(item.current for item in first.reservations))
    before = snapshot(owner)
    with pytest.raises(RuntimeError, match="awaiting"):
        owner.register(application, proposal, tuple(item.current for item in first.reservations))
    assert snapshot(owner) == before


def test_pending_capacity_refusal_is_atomic_with_an_explicit_full_queue_fixture():
    """Inject a full typed ownership fixture; this is not a biological/run-size claim."""
    _, first, source_owner = prepared()
    owner = SeekNippleOutcomeRuntimeV1(source_owner.stream)
    owner.consume_intervals((), cutoff_tick=0)
    pending = next(iter(source_owner._pending.values()))
    # Capacity is tested independently of the live task's smaller normal workload.
    owner._pending = {f"other_pending:{i}": replace(pending) for i in range(8)}
    before = snapshot(owner)
    with pytest.raises(OverflowError, match="eight"):
        owner.register(first.calculation.navigation.application, first.calculation.proposal,
                       tuple(item.current for item in first.reservations))
    assert snapshot(owner) == before and len(owner.pending()) == 8


def test_terminal_diagnostic_capacity_is_independent_of_pending_ownership():
    """Exercise bounded terminal storage using explicitly supplied already-terminal records."""
    _, _, owner, intervals = buffered()
    owner.consume_intervals(intervals, cutoff_tick=12)
    original = owner.history()[0]
    for number in range(2, 41):
        owner._history.append(replace(original, number=number))
    assert len(owner.history()) == 32
    assert owner.history()[0].number == 9 and owner.history()[-1].number == 40
    assert not owner.pending() and owner.retained_counts()["seeking_outcome_history"] == 32


@pytest.mark.parametrize("bad", [None, True, [], (), "", "x" * 101])
def test_closure_reason_is_bounded_and_cannot_mutate_a_valid_owner(bad):
    _, _, owner = prepared()
    before = snapshot(owner)
    with pytest.raises(ValueError):
        owner.close(reason=bad)
    assert snapshot(owner) == before
