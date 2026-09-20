"""Approved 1G-B policy: local detection, source relevance and one focal allocation.

The endpoint harness explicitly supplies synthetic normally-returned intervals
and sensor acquisitions to the real 1G-A correspondence owner. It creates every
forecast before supplying its endpoint. It is not attributed to a physical run;
the separate demo/integration tests use the actual H2/H4 hierarchy.
"""

from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorCommandV1, MotorFeedbackV1, MotorStreamRefV1
from nca8_executive import AttentionBidV1, AttentionRuntimeV1, NavigationRuntimeV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_maps import DurableNavMapRefV1, MotorSupportConfigurationV1, create_posture_support_map_library_v1
from nca8_outcome_attention import RightingOutcomeAttentionV1
from nca8_outcomes import RightingIntervalEvidenceV1, RightingOutcomeRuntimeV1
from nca8_righting import RightingContextV1
from nca8_righting_demo import competing_preview_bid_v1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_sensorimotor_contracts import FocalMotorEvidenceV1, LocalTargetDispositionV1, LocalTargetReportV1
from nca8_sensory import Nca8BodySensoryModuleV1

STREAM = MotorStreamRefV1("outcome_attention_fixture", 1)


def sensor(tick, **changes):
    return replace(MotorFeedbackV1(STREAM, tick + 1, tick, tick, 30.0, 0.5, True, 0.4, 0.3), **changes)


class EndpointHarness:
    """Supply explicit execution bookkeeping; do not inject a computed mismatch flag."""

    def __init__(self, *, baseline=None):
        self.session = Nca8RightingPreviewSessionV1(STREAM)
        self.publisher = RightingOutcomeRuntimeV1(STREAM)
        self.tick = 0
        self.baseline = {} if baseline is None else baseline

    def endpoint(self, **changes):
        start = self.tick
        for reservation in self.session.mapper.reservations(at_tick=start):
            self.session.mapper.cancel(reservation, at_tick=start)
        result = self.session.preview(sensor(start, **self.baseline), cutoff_tick=start)
        application, proposal = result.navigation.application, result.proposal
        assert application is not None and proposal is not None and proposal.bindings
        reservations = self.session.mapper.reserve(proposal, execution_id=f"fixture_execution:{start}", at_tick=start)
        targets = tuple(item.current for item in reservations)
        registration = self.publisher.register(application, proposal, targets)
        self.publisher.installed(registration, at_tick=start)
        preview = registration.preview
        endpoint = sensor(registration.due_tick, available_tick=registration.due_tick + 1,
                          body_tilt_degrees=preview.predicted_tilt, support_extension=preview.predicted_extension,
                          useful_loading=preview.predicted_loading, destabilization=preview.predicted_destabilization,
                          support_contact=preview.expected_contact)
        endpoint = replace(endpoint, **changes)
        rows = []
        for tick in range(start, registration.due_tick + 1):
            reports = tuple(LocalTargetReportV1(target, LocalTargetDispositionV1.ACTIVE, tick, "supplied_fixture_interval") for target in targets)
            kinds = {target.target.kind.value for target in targets}
            command = MotorCommandV1(STREAM, tick + 1, tick, 0.2 if "orientation_adjust" in kinds else 0.0,
                                     0.2 if "support_extension" in kinds else 0.0) if tick < registration.due_tick else None
            rows.append(RightingIntervalEvidenceV1(tick, command, reports, (endpoint,) if tick == registration.due_tick else ()))
        self.tick = registration.due_tick + 1
        outcomes = self.publisher.consume_intervals(tuple(rows), cutoff_tick=self.tick)
        assert len(outcomes) == 1
        return outcomes[0]

    @property
    def task(self):
        return self.session.righting.task


def source_at(cutoff, cycle=2, *, feedback="current"):
    """Provide an explicitly constructed source fixture with a canonical motor facet."""
    maps = create_posture_support_map_library_v1()
    reading = sensor(cutoff) if feedback == "current" else feedback
    evidence = None if reading is None else FocalMotorEvidenceV1(reading, cycle, cutoff)
    return maps.update_motor_current_state(MotorSupportConfigurationV1(maps.posture_support_ref, STREAM, evidence, None, cycle, cutoff))


def owner_for(harness):
    return RightingOutcomeAttentionV1(STREAM, harness.task.source_map_ref)


def ordinary_bid(source):
    cycle = source.applied_cycle
    return AttentionBidV1(f"support_bid:{cycle}", "source:posture_support", source, "body_sensory", cycle,
                          0, 20, 0, 0, 20, 20, ("activity_relative_support_need",), False, "source:posture_support")


def select(owner, source, *, compete=False, navigation=None):
    nav = NavigationRuntimeV1(motor_preview_enabled=True) if navigation is None else navigation
    bid = owner.contribute_bid(ordinary_bid(source))
    bids = [bid]
    if compete:
        bids.append(replace(competing_preview_bid_v1(source.applied_cycle), novelty_or_ambiguity_rank=10))
    choice = AttentionRuntimeV1().select(bids, current_wnm=nav.current_wnm, cycle_id=source.applied_cycle)
    return nav, choice, nav.update_wnm(choice)


def test_default_profiles_do_not_construct_the_new_source_extension():
    for options in ({}, {"task_outcomes_enabled": True}):
        trial = IntegratedRightingTrialV1(**options)
        focal, _ = trial.step()
        assert trial.core.cognition.sensory.outcome_attention is None
        assert focal.calculation.outcome_allocation is None
        assert "outcome_attention" not in focal.calculation.as_dict()
        assert not any(name.startswith("attention_") for name in trial.retained_counts())


@pytest.mark.parametrize("bad", [None, 0, 1, "true", [], {}])
def test_enablement_is_boolean_not_a_truthy_configuration(bad):
    with pytest.raises(TypeError):
        IntegratedRightingTrialV1(task_outcomes_enabled=True, task_outcome_attention_enabled=bad)


def test_new_route_requires_the_real_correspondence_consumer():
    with pytest.raises(ValueError):
        IntegratedRightingTrialV1(task_outcome_attention_enabled=True)


def test_source_extension_is_owned_once_and_does_not_modify_maps():
    maps = create_posture_support_map_library_v1()
    sensory = Nca8BodySensoryModuleV1(maps)
    sensory.configure_outcome_attention(STREAM)
    assert maps.current_state() is None and maps.durable_map_count == 1
    assert sensory.outcome_attention is not None
    with pytest.raises(RuntimeError):
        sensory.configure_outcome_attention(STREAM)
    sensory2 = Nca8BodySensoryModuleV1(create_posture_support_map_library_v1())
    sensory2.apply_motor_evidence(FocalMotorEvidenceV1(sensor(0), 1, 0), stream=STREAM, cycle_id=1, cutoff_tick=0)
    with pytest.raises(RuntimeError):
        sensory2.configure_outcome_attention(STREAM)


def test_real_correspondence_creates_only_a_source_request_before_focal_selection():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    assert outcome.status == "mismatch"
    owner = owner_for(harness)
    source = source_at(5)
    before = source.as_dict(), outcome.as_dict(), random.getstate()
    requests = owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    assert len(requests) == 1 and requests[0].relations == ("contact",)
    assert requests[0].expires_at_tick == 13
    assert owner.retained_counts()["attention_dependency"] == 0
    assert before == (source.as_dict(), outcome.as_dict(), random.getstate())
    assert "primitive_id" not in requests[0].as_dict()


def test_source_bid_changes_only_outcome_component_and_reason():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    before = ordinary_bid(source)
    after = owner.contribute_bid(before)
    assert after.source_map_state is before.source_map_state
    assert after.priority_components == (0, 20, 40, 0, 20, 20)
    assert replace(after, prediction_or_envelope_failure_rank=0, reasons=before.reasons) == before
    history_only = owner.contribute_bid(None)
    assert history_only.new_task_need_rank == history_only.protected_safety_rank == 0


@pytest.mark.parametrize("change", [
    {"support_contact": None}, {"body_tilt_degrees": None}, {"useful_loading": None}, {"destabilization": None},
    {"support_extension": None}, {},
])
def test_unknown_or_matching_endpoints_do_not_create_mismatch_capture(change):
    harness = EndpointHarness()
    outcome = harness.endpoint(**change)
    owner = owner_for(harness)
    source = source_at(5)
    assert not owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    assert owner.contribute_bid(ordinary_bid(source)).prediction_or_envelope_failure_rank == 0


@pytest.mark.parametrize("baseline,change,relation", [
    ({"body_tilt_degrees": 13.0}, {"body_tilt_degrees": 25.0}, "tilt"),
    ({"useful_loading": 0.7}, {"useful_loading": 0.2}, "loading"),
    ({"destabilization": 0.17}, {"destabilization": 0.7}, "destabilization"),
])
def test_observed_contradiction_of_expected_supported_activity_condition_is_consequential(baseline, change, relation):
    harness = EndpointHarness(baseline=baseline)
    outcome = harness.endpoint(**change)
    owner = owner_for(harness)
    requests = owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    assert requests and relation in requests[0].relations
    assert requests[0].significance == "consequential_support_contradiction"


def test_partial_unknown_relations_do_not_erase_a_known_contact_contradiction():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False, body_tilt_degrees=None)
    owner = owner_for(harness)
    request, = owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    assert request.relations == ("contact",) and ("tilt", "unknown") in request.outcome.relations


def test_two_distinct_consecutive_noncritical_endpoints_can_escalate_persistence():
    harness = EndpointHarness()
    one = harness.endpoint(body_tilt_degrees=30.0)
    owner = owner_for(harness)
    assert not owner.admit((one,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    two = harness.endpoint(body_tilt_degrees=30.0)
    requests = owner.admit((two,), source_at(10, 3), harness.task, harness.task.context, cutoff_tick=10)
    assert len(requests) == 1 and requests[0].significance == "persistent_executed_discrepancy"
    assert requests[0].relations == ("tilt",)
    assert requests[0].outcome is two and one.registration.due_tick < two.registration.due_tick


@pytest.mark.parametrize("middle", [{}, {"body_tilt_degrees": None}, {"support_extension": 0.95}])
def test_matching_unknown_or_different_relation_breaks_the_same_relation_streak(middle):
    harness = EndpointHarness()
    first = harness.endpoint(body_tilt_degrees=30.0)
    owner = owner_for(harness)
    owner.admit((first,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    second = harness.endpoint(**middle)
    owner.admit((second,), source_at(10, 3), harness.task, harness.task.context, cutoff_tick=10)
    third = harness.endpoint(body_tilt_degrees=30.0)
    assert not owner.admit((third,), source_at(15, 4), harness.task, harness.task.context, cutoff_tick=15)


def test_publisher_gap_breaks_persistence_rather_than_hiding_intervening_nonapplication():
    harness = EndpointHarness()
    one = harness.endpoint(body_tilt_degrees=30.0)
    owner = owner_for(harness)
    owner.admit((one,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    harness.endpoint()  # An intervening result was not delivered to this consumer.
    third = harness.endpoint(body_tilt_degrees=30.0)
    assert not owner.admit((third,), source_at(15, 4), harness.task, harness.task.context, cutoff_tick=15)


def test_persistence_does_not_escalate_after_current_activity_has_recovered():
    harness = EndpointHarness()
    owner = None
    for cycle in (2, 3):
        outcome = harness.endpoint(body_tilt_degrees=30.0)
        if owner is None:
            owner = owner_for(harness)
        reading = sensor(harness.tick, body_tilt_degrees=10.0, useful_loading=0.9, destabilization=0.05)
        assert not owner.admit((outcome,), source_at(harness.tick, cycle, feedback=reading), harness.task, harness.task.context,
                               cutoff_tick=harness.tick)


def test_expected_adversity_and_unexpected_improvement_are_not_automatic_danger():
    harness = EndpointHarness()
    outcome = harness.endpoint(body_tilt_degrees=10.0, useful_loading=0.9, destabilization=0.01)
    owner = owner_for(harness)
    assert outcome.status == "mismatch"
    assert not owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)


@pytest.mark.parametrize("feedback,status", [
    (sensor(5), "corrected_historical_discrepancy"),
    (sensor(5, support_contact=False), "still_relevant_support_discrepancy"),
    (None, "unresolved_current_relevance"),
    (sensor(5, support_contact=None), "unresolved_current_relevance"),
])
def test_one_interpretation_preserves_original_event_and_classifies_current_relevance(feedback, status):
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5, feedback=feedback)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    nav, _, working = select(owner, source)
    allocation = owner.allocate(working, cycle_id=2)
    assert allocation.kind == "interpretation" and not allocation.permits_primitive_selection
    assert allocation.interpretation.status == status
    assert allocation.interpretation.request.outcome.evidence.support_contact is False
    nav.record_focal_hold(working, cycle_id=2, reason=allocation.kind)
    with pytest.raises(ValueError):
        nav.commit(working, (harness.session.righting,), cycle_id=2)
    with pytest.raises(ValueError):
        owner.allocate(working, cycle_id=2)
    assert not owner.pending()


def test_no_selected_source_means_no_demanding_interpretation():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    allocation = owner.allocate(None, cycle_id=2)
    assert allocation.kind == "other_source" and owner.pending()
    assert owner.retained_counts()["attention_dependency"] == 0


def test_stronger_protected_source_still_wins_without_consuming_the_request():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    nav = NavigationRuntimeV1()
    safety = replace(competing_preview_bid_v1(2), protected_safety_rank=1)
    selection = AttentionRuntimeV1().select([owner.contribute_bid(ordinary_bid(source)), safety], current_wnm=None, cycle_id=2)
    assert selection.selected_bid is safety
    assert owner.allocate(nav.update_wnm(selection), cycle_id=2).kind == "other_source"
    assert len(owner.pending()) == 1


def test_later_reconsideration_consumes_the_original_interpretation_once():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    nav, _, working = select(owner, source)
    first = owner.allocate(working, cycle_id=2)
    later = source_at(6, 3, feedback=sensor(6, body_tilt_degrees=28.0))
    owner.admit((), later, harness.task, harness.task.context, cutoff_tick=6)
    _, _, working = select(owner, later, navigation=nav)
    response = owner.allocate(working, cycle_id=3)
    assert response.kind == "response_reconsideration" and response.permits_primitive_selection
    assert response.interpretation is first.interpretation
    assert working.primary_source_state.motor_support.feedback.body_tilt_degrees == 28.0
    assert first.interpretation.current_evidence.body_tilt_degrees == 30.0
    third = source_at(7, 4)
    owner.admit((), third, harness.task, harness.task.context, cutoff_tick=7)
    _, _, working = select(owner, third, navigation=nav)
    assert owner.allocate(working, cycle_id=4).kind == "ordinary"


def test_unresolved_dependency_does_not_block_another_source_or_refresh_itself():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5, feedback=None)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    nav, _, working = select(owner, source)
    first = owner.allocate(working, cycle_id=2)
    assert first.interpretation.status == "unresolved_current_relevance"
    current = source_at(6, 3)
    owner.admit((), current, harness.task, harness.task.context, cutoff_tick=6)
    _, selection, working = select(owner, current, compete=True, navigation=nav)
    assert selection.selected_bid.candidate_id == "fixture:competing_source"
    assert owner.allocate(working, cycle_id=3).kind == "other_source"
    current = source_at(7, 4)
    owner.admit((), current, harness.task, harness.task.context, cutoff_tick=7)
    _, _, working = select(owner, current, navigation=nav)
    assert not owner.allocate(working, cycle_id=4).permits_primitive_selection
    current = source_at(13, 5)
    owner.admit((), current, harness.task, harness.task.context, cutoff_tick=13)
    _, _, working = select(owner, current, navigation=nav)
    assert owner.allocate(working, cycle_id=5).kind == "ordinary"
    assert any(kind == "dependent_response_expired_or_invalidated" for _, kind, _ in owner.dispositions())


def test_duplicate_publisher_result_cannot_accumulate_or_renew_requests():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    request, = owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    assert not owner.admit((outcome,), source_at(6, 3), harness.task, harness.task.context, cutoff_tick=6)
    assert owner.pending() == (request,) and request.expires_at_tick == 13
    assert not owner.admit((outcome,), source_at(13, 4), harness.task, harness.task.context, cutoff_tick=13)
    assert not owner.pending()
    assert owner.contribute_bid(None) is None
    assert (request.request_id, "expired_uninterpreted", 13) in owner.dispositions()


def test_old_unseen_outcome_cannot_start_a_fresh_lifetime_on_late_replay():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    with pytest.raises(ValueError):
        owner.admit((outcome,), source_at(10), harness.task, harness.task.context, cutoff_tick=10)
    assert not owner.pending()


@pytest.mark.parametrize("bad", [True, -1, 0.5, "5", 2**63])
def test_bad_cutoff_is_rejected_before_any_relevance_state_changes(bad):
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    before = owner.retained_counts()
    with pytest.raises(ValueError):
        owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=bad)
    assert owner.retained_counts() == before


@pytest.mark.parametrize("bad", [None, True, "mismatch", {"mismatch": True}])
def test_a_label_or_dictionary_cannot_substitute_for_a_corresponding_outcome(bad):
    harness = EndpointHarness()
    harness.endpoint()
    owner = owner_for(harness)
    with pytest.raises(TypeError):
        owner.admit((bad,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)


@pytest.mark.parametrize("changes", [
    {"number": True}, {"number": 0}, {"evaluated_tick": 6}, {"command_intervals": 0},
    {"command_intervals": True}, {"command_intervals": 9}, {"evidence": None},
    {"relations": (("unsupported", "mismatch"),)}, {"relations": (("contact", "mismatch"), ("contact", "mismatch"))},
])
def test_invalid_correspondence_cannot_gain_source_priority(changes):
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    bad = replace(outcome, **changes)
    with pytest.raises((TypeError, ValueError)):
        owner.admit((bad,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    assert not owner.pending() and owner.retained_counts()["attention_previous_endpoint"] == 0


def test_wrong_generation_and_wrong_source_are_rejected_even_on_duplicate_numbers():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    for stream, reference in ((replace(STREAM, generation=2), harness.task.source_map_ref),
                              (STREAM, DurableNavMapRefV1("other_source", 1))):
        owner = RightingOutcomeAttentionV1(stream, reference)
        with pytest.raises(ValueError):
            owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
        assert not owner.pending()


def test_context_change_invalidates_old_request_and_does_not_relabel_it_successful():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    request, = owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    context = RightingContextV1("activity:new_requirement")
    owner.admit((), source_at(6, 3), None, context, cutoff_tick=6)
    assert not owner.pending()
    assert (request.request_id, "context_invalidated", 6) in owner.dispositions()
    assert request.outcome.status == "mismatch"


def test_no_task_cannot_borrow_an_old_tasks_discrepancy():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    assert not owner.admit((outcome,), source_at(5), None, harness.task.context, cutoff_tick=5)


def test_copy_of_source_cannot_replace_the_frozen_source_used_for_interpretation():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    _, _, working = select(owner, source)
    with pytest.raises(ValueError):
        owner.allocate(replace(working, primary_source_state=replace(source)), cycle_id=2)
    assert owner.allocate(working, cycle_id=2).kind == "interpretation"


def test_owner_cap_refuses_whole_batch_and_preserves_existing_requests():
    """Stress the source queue with explicitly supplied simultaneous publisher records.

    Copies here model distinct publisher identities for capacity stress only;
    they are not the causal experiment, which uses real independent executions.
    """
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    batch = tuple(replace(outcome, number=number) for number in range(1, 9))
    requests = owner.admit(batch, source_at(5), harness.task, harness.task.context, cutoff_tick=5)
    assert len(requests) == 8
    before = owner.pending(), owner.retained_counts(), owner.dispositions()
    ninth = replace(outcome, number=9, evaluated_tick=6)
    with pytest.raises(OverflowError):
        owner.admit((ninth,), source_at(6, 3), harness.task, harness.task.context, cutoff_tick=6)
    assert before == (owner.pending(), owner.retained_counts(), owner.dispositions())


def test_out_of_order_or_duplicate_batch_cannot_partially_capture_focus():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    for batch in ((outcome, outcome), (replace(outcome, number=2), outcome)):
        owner = owner_for(harness)
        with pytest.raises(ValueError):
            owner.admit(batch, source_at(5), harness.task, harness.task.context, cutoff_tick=5)
        assert not owner.pending()


def test_budget_boundary_can_retain_evidence_but_cannot_buy_another_interpretation():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(80, 21)
    task = replace(harness.task, last_cycle=21, status="budget_exhausted")
    owner.admit((replace(outcome, evaluated_tick=80),), source, task, task.context, cutoff_tick=80)
    assert owner.pending()
    assert owner.contribute_bid(None) is None
    _, _, working = select(owner, source)
    assert owner.allocate(working, cycle_id=21).kind == "task_budget_exhausted"
    assert owner.retained_counts()["attention_dependency"] == 0


def test_json_export_and_repeated_reads_grant_no_work_or_rng_effect():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    before = owner.retained_counts(), owner.pending(), random.getstate(), source.as_dict()
    for _ in range(10):
        data = owner.pending()[0].as_dict()
        data["relations"].clear()
        json.dumps(owner.pending()[0].as_dict(), allow_nan=False)
        owner.dispositions()
        owner.contribute_bid(ordinary_bid(source))
    assert before == (owner.retained_counts(), owner.pending(), random.getstate(), source.as_dict())


@pytest.mark.parametrize("cycle", [2.0, "2", None, True])
def test_focal_allocation_rejects_coerced_cycle_before_consuming_request(cycle):
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    _, _, working = select(owner, source)
    before = owner.pending()
    with pytest.raises(ValueError):
        owner.allocate(working, cycle_id=cycle)
    assert owner.pending() == before
    assert owner.allocate(working, cycle_id=2).kind == "interpretation"


def test_historical_dependency_export_does_not_count_another_interpretation():
    harness = EndpointHarness()
    outcome = harness.endpoint(support_contact=False)
    owner = owner_for(harness)
    source = source_at(5)
    owner.admit((outcome,), source, harness.task, harness.task.context, cutoff_tick=5)
    nav, _, working = select(owner, source)
    interpreted = owner.allocate(working, cycle_id=2)
    assert interpreted.as_dict()["interpretations_this_opportunity"] == 1
    source = source_at(9, 3)
    owner.admit((), source, harness.task, harness.task.context, cutoff_tick=9)
    _, _, working = select(owner, source, navigation=nav)
    later = owner.allocate(working, cycle_id=3)
    assert later.kind == "response_reconsideration"
    assert later.interpretation is interpreted.interpretation
    assert later.as_dict()["interpretations_this_opportunity"] == 0


def test_accurately_predicted_inadequate_endpoint_has_no_mismatch_request():
    harness = EndpointHarness()
    outcome = harness.endpoint()
    assert outcome.status == "matched" and outcome.evidence.body_tilt_degrees > 12.0
    owner = owner_for(harness)
    assert owner.admit((outcome,), source_at(5), harness.task, harness.task.context, cutoff_tick=5) == ()
