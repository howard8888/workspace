"""Seeking relevance contracts using actual D claims and explicit endpoint fixtures.

The paired alternative acquisitions below are unit fixtures, not asserted plant
outputs. D computes their actual canonical result before the new relevance owner
reads it. Physical forcing and full source competition are tested in the demo
companion. No fixture is installed in ordinary runtime or used as motor truth.
"""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_executive import AttentionRuntimeV1, WorkingNavMapStateV1
from nca8_feeding import FeedingDetailCandidateV1, FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_seek_attention import SeekingOutcomeAttentionV1
from nca8_seek_nipple import SeekNippleProfileV1
from nca8_seek_outcomes import SeekNippleEndpointV1, validate_seeking_outcome_v1
from nca8_seek_outcomes_demo import create_seek_nipple_outcome_trial_v1
from nca8_seek_attention_demo import run_seeking_attention_v1


def endpoint_fixture(change=None, case="nominal"):
    """Execute a real selected task; substitute only an explicitly labelled due sample."""
    trial = create_seek_nipple_outcome_trial_v1(case)
    trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    if change is not None:
        intervals = []
        for interval in trial._seeking_intervals:
            deliveries, observations = [], []
            for sample in interval.deliveries:
                observation = next((v for v in interval.observations if v.sample_id == sample.sample_id), None)
                endpoint = SeekNippleEndpointV1(sample, observation)
                if sample.event_tick == 8:
                    endpoint = change(endpoint)
                deliveries.append(endpoint.feedback)
                if endpoint.observation is not None:
                    observations.append(endpoint.observation)
            intervals.append(replace(interval, deliveries=tuple(deliveries), observations=tuple(observations)))
        trial._seeking_intervals[:] = intervals
    cycle = trial.focal_step()
    outcome = cycle.seeking_correspondence.outcomes[0]
    route = SeekingOutcomeAttentionV1(trial.latest_feedback.stream, cycle.feeding_detail_source.seed)
    return trial, cycle, outcome, route


def displaced(endpoint, delta=.01):
    return replace(endpoint, feedback=replace(endpoint.feedback,
                   oral=replace(endpoint.feedback.oral, extension_metres=endpoint.feedback.oral.extension_metres + delta)))


def detail_changed(endpoint, *, distance=0.03, descriptor="feeding"):
    observation = endpoint.observation
    return replace(endpoint, observation=replace(observation, detections=tuple(
        replace(item, position=NavPointV1(item.position.x + distance, item.position.y), descriptor=descriptor)
        if item.region_id == "region_2" else item for item in observation.detections)))


def admit(route, cycle, outcomes, source=None):
    return route.admit(outcomes, cycle.feeding_detail_source if source is None else source,
                       cycle.seeking_task.task, cutoff_tick=cycle.calculation.cutoff_tick)


def working(source):
    return WorkingNavMapStateV1("fixture:working", source, "source:feeding_detail", source.active_relation_labels, (),
                                source.applied_cycle, source.applied_cycle, 1)


def snapshot(route):
    return json.dumps({"pending": [x.as_dict() for x in route.pending()], "history": route.dispositions(),
                       "counts": route.retained_counts(), "number": route._last_number, "admission": route._last_admission,
                       "allocation": route._last_allocation_cycle,
                       "source": None if route._source is None else route._source.as_dict()}, sort_keys=True, allow_nan=False)


def next_cycle(trial, count=4):
    for _ in range(count):
        trial.advance_lower()
    return trial.focal_step()


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "true", [], {}])
def test_route_flag_requires_actual_boolean(bad):
    with pytest.raises(TypeError):
        SeekNippleProfileV1(outcomes_enabled=True, outcome_attention_enabled=bad)


def test_default_has_no_new_authority_and_route_requires_correspondence():
    assert SeekNippleProfileV1().outcome_attention_enabled is False
    with pytest.raises(ValueError):
        SeekNippleProfileV1(outcome_attention_enabled=True)
    trial = create_seek_nipple_outcome_trial_v1()
    assert trial.core.feeding_detail.outcome_attention is None
    assert trial.focal_step().seeking_attention is None


@pytest.mark.parametrize("bad", [None, True, 0, -1, 33, 1.5, "3"])
def test_diagnostic_bound_is_strict(bad):
    with pytest.raises(ValueError):
        SeekingOutcomeAttentionV1(MotorStreamRefV1("fixture", 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize("stream,seed", [(None, FeedingDetailSeedV1()), (MotorStreamRefV1("fixture", 1), None)])
def test_owner_requires_actual_typed_stream_and_seed(stream, seed):
    with pytest.raises(TypeError):
        SeekingOutcomeAttentionV1(stream, seed)


def test_source_owns_one_optional_extension_not_another_durable_map():
    source = FeedingDetailSourceV1(MotorStreamRefV1("fixture", 1), FeedingDetailProfileV1())
    before = source.durable_map.as_dict()
    source.configure_outcome_attention()
    assert isinstance(source.outcome_attention, SeekingOutcomeAttentionV1)
    assert source.durable_map.as_dict() == before and source.current is None
    with pytest.raises(RuntimeError):
        source.configure_outcome_attention()
    trial = create_seek_nipple_outcome_trial_v1()
    trial.focal_step()
    with pytest.raises(RuntimeError):
        trial.core.feeding_detail.configure_outcome_attention()


@pytest.mark.parametrize("change,status", [
    (None, "matched"), (lambda ep: replace(ep, observation=None), "unknown"),
    (lambda ep: replace(ep, observation=replace(ep.observation, detections=())), "unknown"),
    (lambda ep: replace(ep, feedback=replace(ep.feedback, oral=replace(ep.feedback.oral, extension_metres=None))), "unknown"),
])
def test_matches_and_missing_evidence_do_not_invent_mismatch(change, status):
    _, cycle, outcome, route = endpoint_fixture(change)
    assert outcome.status == status
    assert admit(route, cycle, (outcome,)) == ()


@pytest.mark.parametrize("offset,expected", [(0.0049, False), (0.005, False), (0.00501, True), (0.01, True)])
def test_original_predicted_reach_boundary_drives_significance(offset, expected):
    _, cycle, outcome, route = endpoint_fixture(lambda ep: displaced(ep, offset))
    requests = admit(route, cycle, (outcome,))
    assert bool(requests) is expected
    if requests:
        assert requests[0].significance == "expected_reach_not_supported"
        assert requests[0].outcome is outcome and requests[0].expires_at_tick == 20


@pytest.mark.parametrize("contact", [None, False, True])
def test_touch_is_not_a_predicted_relation_or_significance_trigger(contact):
    _, cycle, outcome, route = endpoint_fixture(lambda ep: replace(ep, feedback=replace(ep.feedback,
                                                oral=replace(ep.feedback.oral, contact=contact))))
    assert outcome.status == "matched" and admit(route, cycle, (outcome,)) == ()


@pytest.mark.parametrize("distance,expected", [(0.0199, False), (0.02, True), (0.03, True)])
def test_anchor_significance_is_distinct_from_small_geometric_mismatch(distance, expected):
    _, cycle, outcome, route = endpoint_fixture(lambda ep: detail_changed(ep, distance=distance), case="intermediate_target")
    assert outcome.status == "mismatch"
    requests = admit(route, cycle, (outcome,))
    assert bool(requests) is expected
    if requests:
        assert requests[0].significance == "consequential_detail_anchor_shift"


def test_identity_contradiction_differs_from_missing_category():
    _, cycle, outcome, route = endpoint_fixture(lambda ep: detail_changed(ep, distance=0, descriptor="landmark"))
    assert outcome.status == "identity_contradicted"
    request, = admit(route, cycle, (outcome,))
    assert request.significance == "feeding_part_identity_contradiction"
    interpretation = route.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id).interpretation
    assert interpretation.status == "historical_resolved"  # Current category is the real unchanged provider acquisition.


def test_old_mismatch_is_not_repaired_by_current_recovered_geometry():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    original = outcome.as_dict()
    admit(route, cycle, (outcome,))
    allocation = route.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id)
    assert allocation.kind == "interpretation" and not allocation.permits_primitive_selection
    assert allocation.interpretation.status == "historical_resolved"
    assert outcome.as_dict() == original


@pytest.mark.parametrize("bad", [None, True, -1, 12.5, "12", 2**63])
def test_invalid_cutoff_is_atomic(bad):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    before = snapshot(route)
    with pytest.raises((TypeError, ValueError)):
        route.admit((outcome,), cycle.feeding_detail_source, cycle.seeking_task.task, cutoff_tick=bad)
    assert snapshot(route) == before


@pytest.mark.parametrize("change", [
    lambda o: replace(o, number=True), lambda o: replace(o, number=0), lambda o: replace(o, number=2**63),
    lambda o: replace(o, evaluated_tick=13), lambda o: replace(o, evaluated_tick=11),
    lambda o: replace(o, status="latched"), lambda o: replace(o, command_intervals=0),
    lambda o: replace(o, command_intervals=True), lambda o: replace(o, command_intervals=9),
    lambda o: replace(o, evidence=None), lambda o: replace(o, claim=replace(o.claim, targets=())),
    lambda o: replace(o, claim=replace(o.claim, targets=list(o.claim.targets))),
    lambda o: replace(o, relations=(("separation", "matched"),)),
    lambda o: replace(o, relations=(("milk", "mismatch"),)),
    lambda o: replace(o, relations=o.relations + o.relations[:1]),
    lambda o: replace(o, relations=list(o.relations)),
    lambda o: replace(o, residuals=(("separation", float("nan")),)),
    lambda o: replace(o, residuals=(("separation", -1.0),)),
    lambda o: replace(o, residuals=(("separation", True),)),
    lambda o: replace(o, residuals=(("separation", 0.2),)),
    lambda o: replace(o, residuals=o.residuals + o.residuals[:1]),
    lambda o: replace(o, claim=replace(o.claim, compatible_relations=("detail_anchor",), unevaluable_relations=())),
    lambda o: replace(o, claim=replace(o.claim, compatible_relations=o.claim.compatible_relations + ("mouth_position",))),
    lambda o: replace(o, evidence=replace(o.evidence, observation=None)),
])
def test_corrupted_result_rejected_before_any_owner_change(change):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    before = snapshot(route)
    with pytest.raises((TypeError, ValueError)):
        admit(route, cycle, (change(outcome),))
    assert snapshot(route) == before


@pytest.mark.parametrize("bad", [None, (), "outcome", True])
def test_wrong_outcome_type_is_not_reinterpreted(bad):
    _, cycle, _, route = endpoint_fixture(displaced)
    before = snapshot(route)
    with pytest.raises((TypeError, ValueError)):
        admit(route, cycle, (bad,))
    assert snapshot(route) == before


def test_maternal_outcome_cannot_enter_seeking_route():
    from nca8_maternal_attention_demo import run_maternal_attention_v1
    maternal = run_maternal_attention_v1("competing_on")
    other = next(o for c in maternal.cycles if c.maternal_correspondence for o in c.maternal_correspondence.outcomes)
    _, cycle, _, route = endpoint_fixture(displaced)
    before = snapshot(route)
    with pytest.raises(TypeError):
        admit(route, cycle, (other,))
    assert snapshot(route) == before


@pytest.mark.parametrize("kind", ["stream", "generation", "seed", "parent"])
def test_wrong_recipient_rejected(kind):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    if kind == "stream":
        route = SeekingOutcomeAttentionV1(MotorStreamRefV1("foreign", 1), route.seed)
    elif kind == "generation":
        route = SeekingOutcomeAttentionV1(MotorStreamRefV1(route.stream.stream_id, 2), route.seed)
    elif kind == "seed":
        route = SeekingOutcomeAttentionV1(route.stream, replace(route.seed, detail_region_id="other"))
    else:
        route = SeekingOutcomeAttentionV1(route.stream, replace(route.seed, parent_region_id="other_parent"))
    before = snapshot(route)
    with pytest.raises(ValueError):
        admit(route, cycle, (outcome,))
    assert snapshot(route) == before


@pytest.mark.parametrize("container_kind", ["list", "duplicate", "reversed", "too_many"])
def test_batch_order_and_bounds_are_atomic(container_kind):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    batch = {"list": [outcome], "duplicate": (outcome, outcome), "reversed": (replace(outcome, number=2), outcome),
             "too_many": tuple(replace(outcome, number=i+1) for i in range(9))}[container_kind]
    before = snapshot(route)
    with pytest.raises(ValueError):
        admit(route, cycle, batch)
    assert snapshot(route) == before


def test_replay_cannot_create_another_request_or_refresh_expiry():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    request, = admit(route, cycle, (outcome,))
    later = next_cycle(trial)
    assert admit(route, later, (outcome,)) == ()
    assert route.pending() == (request,) and request.expires_at_tick == 20
    final = next_cycle(trial)
    assert admit(route, final, (outcome,)) == () and route.pending() == ()
    assert route.dispositions()[-1] == (request.request_id, "expired_uninterpreted", 20)


def test_bid_changes_only_its_named_rank_and_reason():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    source = cycle.feeding_detail_source
    admit(route, cycle, (outcome,))
    ordinary = AttentionRuntimeV1().build_bid(FeedingDetailCandidateV1(source), cycle_id=source.applied_cycle)
    before = snapshot(route)
    enhanced = route.contribute_bid(ordinary)
    assert enhanced.prediction_or_envelope_failure_rank == 40
    assert replace(enhanced, prediction_or_envelope_failure_rank=ordinary.prediction_or_envelope_failure_rank,
                   reasons=ordinary.reasons) == ordinary
    assert snapshot(route) == before
    assert route.contribute_bid(None) is None  # No hidden recovery of disabled nomination.


def test_new_need_priority_still_beats_outcome_rank():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    source = cycle.feeding_detail_source
    admit(route, cycle, (outcome,))
    attention = AttentionRuntimeV1()
    ordinary = attention.build_bid(FeedingDetailCandidateV1(source), cycle_id=source.applied_cycle)
    competitor = replace(ordinary, bid_id="competing_bid", candidate_id="competing", source_map_state=cycle.visual_source,
                          new_task_need_rank=11, stable_tie_key="other")
    selection = attention.select((route.contribute_bid(ordinary), competitor), current_wnm=None, cycle_id=source.applied_cycle)
    assert selection.selected_bid is competitor and route.pending()


def test_stale_or_copied_source_bid_does_not_enter_owner():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    source = cycle.feeding_detail_source
    admit(route, cycle, (outcome,))
    wrong = AttentionRuntimeV1().build_bid(FeedingDetailCandidateV1(replace(source)), cycle_id=source.applied_cycle)
    before = snapshot(route)
    with pytest.raises(ValueError):
        route.contribute_bid(wrong)
    assert snapshot(route) == before


def test_one_interpretation_then_a_later_response_without_duplicate_consumption():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    admit(route, cycle, (outcome,))
    first = route.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id)
    assert first.kind == "interpretation" and not first.permits_primitive_selection
    with pytest.raises(ValueError):
        route.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id)
    later = next_cycle(trial)
    admit(route, later, ())
    response = route.allocate(working(later.feeding_detail_source), cycle_id=later.commitment.cycle_id)
    assert response.kind == "response_reconsideration" and response.permits_primitive_selection
    assert response.interpretation is first.interpretation


def test_unknown_current_oral_relation_holds_only_same_source_until_original_expiry():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    source = cycle.feeding_detail_source
    missing = replace(source, oral_feedback=replace(source.oral_feedback, oral=replace(source.oral_feedback.oral, extension_metres=None)))
    assert missing.focal_accessible and missing.mouth_detail_distance is None
    admit(route, cycle, (outcome,), missing)
    first = route.allocate(working(missing), cycle_id=cycle.commitment.cycle_id)
    assert first.interpretation.status == "unresolved_current_relevance"
    later = next_cycle(trial)
    admit(route, later, ())
    result = route.allocate(working(later.feeding_detail_source), cycle_id=later.commitment.cycle_id)
    assert result.kind == "dependent_unresolved" and not result.permits_primitive_selection
    assert result.interpretation is first.interpretation
    final = next_cycle(trial)
    admit(route, final, ())
    assert route.allocate(working(final.feeding_detail_source), cycle_id=final.commitment.cycle_id).kind == "ordinary"


def test_other_source_can_work_while_question_is_pending():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    admit(route, cycle, (outcome,))
    foreign = working(cycle.visual_source)
    allocation = route.allocate(foreign, cycle_id=cycle.commitment.cycle_id)
    assert allocation.kind == "other_source" and allocation.permits_primitive_selection and route.pending()


@pytest.mark.parametrize("bad", [0, True, 1.5, "2", None])
def test_wrong_cycle_is_rejected_before_allocating(bad):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    admit(route, cycle, (outcome,))
    before = snapshot(route)
    with pytest.raises(ValueError):
        route.allocate(working(cycle.feeding_detail_source), cycle_id=bad)
    assert snapshot(route) == before


def test_copied_wnm_source_rejected_without_spending_allocation():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    admit(route, cycle, (outcome,))
    before = snapshot(route)
    with pytest.raises(ValueError):
        route.allocate(working(replace(cycle.feeding_detail_source)), cycle_id=cycle.commitment.cycle_id)
    assert snapshot(route) == before


def test_closing_route_revokes_old_processing_but_keeps_readonly_inspection():
    _, cycle, outcome, route = endpoint_fixture(displaced)
    admit(route, cycle, (outcome,))
    route.close()
    assert route.pending() == () and route.retained_counts()["seeking_attention_dependency"] == 0
    for call in (lambda: admit(route, cycle, (outcome,)), lambda: route.contribute_bid(None),
                 lambda: route.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id)):
        with pytest.raises((ValueError, RuntimeError)):
            call()


def test_overflow_refuses_without_erasing_older_pending_requests():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    batch = tuple(replace(outcome, number=i+1) for i in range(8))  # Explicit capacity fixture, not eight real executions.
    assert len(admit(route, cycle, batch)) == 8
    later = next_cycle(trial)
    before = snapshot(route)
    ninth = replace(outcome, number=9, evaluated_tick=16)
    with pytest.raises(OverflowError):
        admit(route, later, (ninth,))
    assert snapshot(route) == before


def test_task_replacement_discards_old_relevance_without_relabeling_outcome():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    original = outcome.as_dict()
    admit(route, cycle, (outcome,))
    later = next_cycle(trial)
    route.admit((), later.feeding_detail_source, None, cutoff_tick=16)
    assert not route.pending() and outcome.as_dict() == original
    assert route.dispositions()[-1][1] == "task_invalidated"


def test_two_consecutive_partial_endpoint_errors_are_required_for_persistence():
    result = run_seeking_attention_v1("persistent")
    requests = result.requests()
    assert len(requests) == 1 and requests[0].admitted_tick == 20
    assert requests[0].significance == "persistent_executed_seeking_discrepancy"
    first = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == 12)
    second = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == 20)
    route = SeekingOutcomeAttentionV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    assert admit(route, first, first.seeking_correspondence.outcomes) == ()
    skipped = replace(second.seeking_correspondence.outcomes[0], number=3)
    assert admit(route, second, (skipped,)) == ()  # Missing result breaks the alleged consecutive pattern.


def test_diagnostic_capacity_does_not_change_requests_or_allocation():
    _, cycle, outcome, full = endpoint_fixture(displaced)
    small = SeekingOutcomeAttentionV1(full.stream, full.seed, diagnostic_capacity=1)
    assert [r.as_dict() for r in admit(full, cycle, (outcome,))] == [r.as_dict() for r in admit(small, cycle, (outcome,))]
    assert full.allocate(working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id).as_dict() == small.allocate(
        working(cycle.feeding_detail_source), cycle_id=cycle.commitment.cycle_id).as_dict()


def test_validator_rechecks_original_scoring_without_consuming_again():
    trial, cycle, outcome, _ = endpoint_fixture(displaced)
    before = tuple(x.as_dict() for x in trial.core.seeking_outcomes.history())
    validate_seeking_outcome_v1(outcome, stream=trial.latest_feedback.stream, cutoff_tick=12)
    validate_seeking_outcome_v1(outcome, stream=trial.latest_feedback.stream, cutoff_tick=16)
    assert tuple(x.as_dict() for x in trial.core.seeking_outcomes.history()) == before


@pytest.mark.parametrize("dimension,limit,allowed", [("focal", 12, True), ("focal", 13, False),
                                                     ("physical", 47, True), ("physical", 48, False)])
def test_original_task_budget_applies_to_newly_admitted_interpretation(dimension, limit, allowed):
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    if dimension == "focal":
        while cycle.commitment.cycle_id < limit:
            cycle = next_cycle(trial, count=1)
    else:
        while limit - trial.tick > 12:
            cycle = next_cycle(trial, count=12)
        cycle = next_cycle(trial, count=limit - trial.tick)
    # Explicit late-publication fixture; the original event/acquisition/permission are unchanged.
    published = replace(outcome, evaluated_tick=trial.tick)
    request, = admit(route, cycle, (published,))
    assert request.expires_at_tick == trial.tick + 8
    source = cycle.feeding_detail_source
    ordinary = AttentionRuntimeV1().build_bid(FeedingDetailCandidateV1(source), cycle_id=source.applied_cycle)
    assert ordinary is not None
    bid = route.contribute_bid(ordinary)
    allocation = route.allocate(working(source), cycle_id=source.applied_cycle)
    assert allocation.kind == ("interpretation" if allowed else "task_budget_exhausted")
    assert (bid.prediction_or_envelope_failure_rank == 40) == allowed
    assert cycle.seeking_task.task.started_cycle == 1 and cycle.seeking_task.task.started_tick == 0
    assert outcome.as_dict()["evaluated_tick"] == 12


def test_unknown_dependency_does_not_consume_another_sources_focal_work():
    trial, cycle, outcome, route = endpoint_fixture(displaced)
    source = cycle.feeding_detail_source
    missing = replace(source, oral_feedback=replace(source.oral_feedback, oral=replace(source.oral_feedback.oral, extension_metres=None)))
    admit(route, cycle, (outcome,), missing)
    first = route.allocate(working(missing), cycle_id=cycle.commitment.cycle_id)
    assert first.interpretation.status == "unresolved_current_relevance"
    later = next_cycle(trial)
    admit(route, later, ())
    result = route.allocate(working(later.visual_source), cycle_id=later.commitment.cycle_id)
    assert result.kind == "other_source" and result.permits_primitive_selection
    assert route.retained_counts()["seeking_attention_dependency"] == 1


@pytest.mark.parametrize("omitted", ["mouth_position", "separation"])
def test_permission_description_cannot_hide_an_unnarrowed_movement_prediction(omitted):
    _, cycle, outcome, route = endpoint_fixture(displaced)
    forged = replace(outcome, claim=replace(outcome.claim,
        compatible_relations=tuple(name for name in outcome.claim.compatible_relations if name != omitted),
        unevaluable_relations=(omitted,)))
    before = snapshot(route)
    with pytest.raises(ValueError, match="narrowing"):
        admit(route, cycle, (forged,))
    assert snapshot(route) == before
