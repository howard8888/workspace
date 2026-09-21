"""Source-local relevance contracts; live claims precede alternative endpoint fixtures.

Alternative endpoints in these tests are explicitly supplied, paired visual/body
acquisitions, not claimed outputs of the physical surrogate. The existing
maternal comparator computes each verdict before the new route sees it. Full
unmodified body execution and source competition are tested in the companion.
"""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_executive import AttentionRuntimeV1
from nca8_followmom import FollowMomProfileV1
from nca8_followmom_demo import create_follow_mom_trial_v1
from nca8_maternal import MaternalSeedV1, MaternalSourceV1, MaternalCandidateV1
from nca8_maternal_attention import MaternalOutcomeAttentionV1
from nca8_maternal_attention_demo import run_maternal_attention_v1


def endpoint_fixture(change=None, *, case="nominal"):
    """Run a real selected application, then substitute only its due endpoint fixture."""
    trial = create_follow_mom_trial_v1(case, outcomes_enabled=True)
    trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    if change is not None:
        paired = []
        for item in trial._maternal_intervals:
            observations = tuple(change(obs) if obs.event_tick == 8 else obs for obs in item.observations)
            deliveries = []
            for sample in item.deliveries:
                obs = next((obs for obs in observations if obs.sample_id == sample.sample_id), None)
                if obs is not None:
                    xy = None if obs.self_position is None else (obs.self_position.x, obs.self_position.y)
                    sample = replace(sample, planar=replace(sample.planar, position=xy, frame_id=obs.frame_id))
                deliveries.append(sample)
            paired.append(replace(item, deliveries=tuple(deliveries), observations=observations))
        trial._maternal_intervals[:] = paired
    focal = trial.focal_step()
    outcome = focal.maternal_correspondence.outcomes[0]
    route = MaternalOutcomeAttentionV1(trial.latest_feedback.stream, focal.maternal_source.seed)
    return trial, focal, outcome, route


def moved_anchor(obs, dy=0.2):
    return replace(obs, detections=tuple(replace(item, position=NavPointV1(item.position.x, item.position.y + dy))
                                         for item in obs.detections))


def owner_snapshot(route):
    return json.dumps({"pending": [item.as_dict() for item in route.pending()], "history": route.dispositions(),
                       "counts": route.retained_counts(), "number": route._last_number,
                       "admitted": route._last_admission, "allocated": route._last_allocation_cycle}, sort_keys=True)


def admit(route, focal, outcomes):
    return route.admit(outcomes, focal.maternal_source, focal.maternal_task.task, cutoff_tick=focal.calculation.cutoff_tick)


@pytest.mark.parametrize("bad", [None, 0, 1, "yes", (), []])
def test_route_flag_is_boolean(bad):
    with pytest.raises(TypeError):
        FollowMomProfileV1(outcomes_enabled=True, outcome_attention_enabled=bad)


def test_route_is_off_by_default_and_requires_original_comparator():
    assert FollowMomProfileV1().outcome_attention_enabled is False
    with pytest.raises(ValueError):
        FollowMomProfileV1(outcome_attention_enabled=True)


def test_source_owns_optional_route_without_new_durable_map():
    stream = MotorStreamRefV1("ownership", 1)
    source = MaternalSourceV1(stream, MaternalSeedV1())
    before = source.durable_map.as_dict()
    assert source.outcome_attention is None
    source.configure_outcome_attention()
    route = source.outcome_attention
    assert isinstance(route, MaternalOutcomeAttentionV1) and route.stream == stream
    assert source.durable_map.as_dict() == before
    with pytest.raises(RuntimeError):
        source.configure_outcome_attention()


@pytest.mark.parametrize("bad", [True, 0, -1, 33, 1.5, "3", None])
def test_diagnostic_capacity_is_finite_and_typed(bad):
    with pytest.raises(ValueError):
        MaternalOutcomeAttentionV1(MotorStreamRefV1("a", 1), MaternalSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize("stream,seed", [(None, MaternalSeedV1()), (MotorStreamRefV1("a", 1), None)])
def test_owner_identity_requires_typed_values(stream, seed):
    with pytest.raises(TypeError):
        MaternalOutcomeAttentionV1(stream, seed)


@pytest.mark.parametrize("change,status", [
    (None, "matched"),
    (lambda obs: replace(obs, self_position=None), "unknown"),
    (lambda obs: replace(obs, detections=()), "unknown"),
    (lambda obs: replace(obs, frame_id="scene_xy:other"), "unknown"),
    (lambda obs: replace(obs, self_position=NavPointV1(obs.self_position.x + .06, obs.self_position.y)), "mismatch"),
    (lambda obs: moved_anchor(obs, .06), "mismatch"),
])
def test_match_missingness_and_single_small_discrepancy_do_not_escalate(change, status):
    _, focal, outcome, route = endpoint_fixture(change)
    assert outcome.status == status
    assert admit(route, focal, (outcome,)) == ()
    assert route.pending() == ()


@pytest.mark.parametrize("offset,expected", [(0.099, False), (0.1, True), (0.2, True)])
def test_fixed_significance_threshold_does_not_change_correspondence_tolerance(offset, expected):
    _, focal, outcome, route = endpoint_fixture(lambda obs: moved_anchor(obs, offset))
    assert dict(outcome.relations)["maternal_anchor"] == "mismatch"
    requests = admit(route, focal, (outcome,))
    assert bool(requests) is expected
    if requests:
        assert requests[0].significance == "consequential_maternal_anchor_shift"
        assert requests[0].outcome is outcome
        assert requests[0].expires_at_tick == 20


def test_observed_identity_contradiction_is_not_missing_recognition():
    change = lambda obs: replace(obs, detections=tuple(replace(item, descriptor="hazard") for item in obs.detections))
    _, focal, outcome, route = endpoint_fixture(change)
    assert outcome.status == "identity_contradicted"
    request, = admit(route, focal, (outcome,))
    assert request.relations == ("identity",)
    allocation = route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id)
    assert allocation.interpretation.status == "historical_resolved"
    assert allocation.interpretation.current_source.identity_status == "supported"
    assert request.outcome.evidence.detections[0].descriptor == "hazard"
    assert allocation.permits_primitive_selection is False


def test_original_shift_preserved_even_when_current_anchor_has_returned():
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    original = outcome.as_dict()
    admit(route, focal, (outcome,))
    allocation = route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id)
    assert allocation.kind == "interpretation"
    assert allocation.interpretation.status == "historical_resolved"
    assert dict(allocation.interpretation.relation_relevance) == {"maternal_anchor": "currently_supported"}
    assert outcome.as_dict() == original


@pytest.fixture(scope="module")
def persistent():
    return run_maternal_attention_v1("competing_off")


def test_two_consecutive_executed_endpoints_request_only_the_shared_relations(persistent):
    first, second = persistent.cycles[3], persistent.cycles[5]
    route = MaternalOutcomeAttentionV1(first.maternal_source.stream, first.maternal_source.seed)
    assert admit(route, first, first.maternal_correspondence.outcomes) == ()
    request, = admit(route, second, second.maternal_correspondence.outcomes)
    assert request.significance == "persistent_executed_maternal_discrepancy"
    assert request.relations == ("self_position", "separation")
    assert request.outcome.evidence.event_tick == 16 < second.maternal_source.event_tick
    assert request.outcome.command_intervals == 5
    assert route.retained_counts()["maternal_attention_previous_endpoint"] == 1


def test_publisher_gap_does_not_prove_persistent_mismatch(persistent):
    first, second = persistent.cycles[3], persistent.cycles[5]
    route = MaternalOutcomeAttentionV1(first.maternal_source.stream, first.maternal_source.seed)
    admit(route, first, first.maternal_correspondence.outcomes)
    outcome = replace(second.maternal_correspondence.outcomes[0], number=3)
    assert admit(route, second, (outcome,)) == ()


def test_same_old_outcome_cannot_be_replayed_as_new_significance(persistent):
    first, second = persistent.cycles[3], persistent.cycles[5]
    route = MaternalOutcomeAttentionV1(first.maternal_source.stream, first.maternal_source.seed)
    admit(route, first, first.maternal_correspondence.outcomes)
    assert admit(route, second, first.maternal_correspondence.outcomes) == ()
    assert route._last_number == 1


@pytest.mark.parametrize("bad", [True, -1, None, "12", 12.5, 2**63])
def test_bad_cutoff_cannot_change_owner(bad):
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    before = owner_snapshot(route)
    with pytest.raises((TypeError, ValueError)):
        route.admit((outcome,), focal.maternal_source, focal.maternal_task.task, cutoff_tick=bad)
    assert owner_snapshot(route) == before


@pytest.mark.parametrize("mutate", [
    lambda o: replace(o, number=True), lambda o: replace(o, number=0),
    lambda o: replace(o, evaluated_tick=13), lambda o: replace(o, evaluated_tick=11),
    lambda o: replace(o, status="success"), lambda o: replace(o, command_intervals=0),
    lambda o: replace(o, command_intervals=True), lambda o: replace(o, command_intervals=9),
    lambda o: replace(o, evidence=None), lambda o: replace(o, evidence=replace(o.evidence, event_tick=9)),
    lambda o: replace(o, evidence=replace(o.evidence, stream=MotorStreamRefV1("foreign", 1))),
    lambda o: replace(o, claim=replace(o.claim, targets=())),
    lambda o: replace(o, relations=(("self_position", "mismatch"),)),
    lambda o: replace(o, relations=(("no_such_relation", "mismatch"),)),
    lambda o: replace(o, relations=o.relations + o.relations[:1]),
    lambda o: replace(o, residuals=(("maternal_anchor", float("nan")),)),
    lambda o: replace(o, residuals=(("maternal_anchor", -1.0),)),
    lambda o: replace(o, residuals=(("maternal_anchor", True),)),
    lambda o: replace(o, claim=replace(o.claim, compatible_relations=("maternal_anchor",), unevaluable_relations=())),
])
def test_malformed_or_wrong_execution_outcome_is_atomically_rejected(mutate):
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    before = owner_snapshot(route)
    with pytest.raises((TypeError, ValueError)):
        admit(route, focal, (mutate(outcome),))
    assert owner_snapshot(route) == before


def test_wrong_maternal_seed_or_generation_cannot_receive_claim():
    _, focal, outcome, _ = endpoint_fixture(moved_anchor)
    for stream, seed in ((MotorStreamRefV1(focal.maternal_source.stream.stream_id, 2), focal.maternal_source.seed),
                         (focal.maternal_source.stream, MaternalSeedV1("another", "object"))):
        route = MaternalOutcomeAttentionV1(stream, seed)
        before = owner_snapshot(route)
        with pytest.raises(ValueError):
            admit(route, focal, (outcome,))
        assert owner_snapshot(route) == before


def test_bid_changes_only_outcome_rank_and_reason(persistent):
    first, second = persistent.cycles[3], persistent.cycles[5]
    route = MaternalOutcomeAttentionV1(first.maternal_source.stream, first.maternal_source.seed)
    admit(route, first, first.maternal_correspondence.outcomes)
    admit(route, second, second.maternal_correspondence.outcomes)
    # Ordinary maternal candidate remains in actual Attention's inspected candidate set.
    ordinary = AttentionRuntimeV1().build_bid(MaternalCandidateV1(second.maternal_source), cycle_id=second.calculation.cycle_id)
    enhanced = route.contribute_bid(ordinary)
    assert enhanced.prediction_or_envelope_failure_rank == 40
    assert replace(enhanced, prediction_or_envelope_failure_rank=ordinary.prediction_or_envelope_failure_rank,
                   reasons=ordinary.reasons) == ordinary
    assert enhanced.source_map_state is second.maternal_source


def test_allocation_cannot_run_twice_in_the_same_opportunity():
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id)
    before = owner_snapshot(route)
    with pytest.raises(ValueError):
        route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id)
    assert owner_snapshot(route) == before


def test_copied_or_old_working_sample_cannot_substitute_for_current_source():
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    original = focal.calculation.navigation.wnm
    before = owner_snapshot(route)
    copied = replace(original, primary_source_state=replace(original.primary_source_state))
    with pytest.raises(ValueError):
        route.allocate(copied, cycle_id=focal.calculation.cycle_id)
    with pytest.raises(ValueError):
        route.allocate(original, cycle_id=focal.calculation.cycle_id + 1)
    assert owner_snapshot(route) == before



def test_unselected_request_expires_without_replay_renewal():
    trial, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    request = route.pending()[0]
    assert route.allocate(None, cycle_id=focal.calculation.cycle_id).kind == "other_source"
    for tick in (16, 20):
        for _ in range(4): trial.advance_lower()
        later = trial.focal_step()
        assert admit(route, later, (outcome,)) == ()
    assert route.pending() == ()
    assert route.dispositions() == ((request.request_id, "expired_uninterpreted", 20),)


def test_resolved_response_waits_for_later_normal_navigation():
    trial, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id)
    for _ in range(4): trial.advance_lower()
    later = trial.focal_step()
    admit(route, later, later.maternal_correspondence.outcomes)
    response = route.allocate(later.calculation.navigation.wnm, cycle_id=later.calculation.cycle_id)
    assert response.kind == "response_reconsideration" and response.permits_primitive_selection
    assert route.retained_counts()["maternal_attention_dependency"] == 0


def test_narrowed_authorization_is_not_punished_as_failed_original_self_prediction():
    _, focal, outcome, route = endpoint_fixture(case="narrowed_k8")
    assert outcome.claim.unevaluable_relations == ("self_position", "separation")
    assert outcome.status == "partly_matched"
    assert admit(route, focal, (outcome,)) == ()


def test_current_target_does_not_receive_credit_for_unapplied_request():
    trial = create_follow_mom_trial_v1("veto", outcomes_enabled=True)
    focal = trial.focal_step()
    outcome = focal.maternal_correspondence.outcomes[0]
    assert outcome.status == "not_applied" and not outcome.claim.targets
    route = MaternalOutcomeAttentionV1(trial.latest_feedback.stream, focal.maternal_source.seed)
    assert admit(route, focal, (outcome,)) == ()


def test_observed_endpoint_without_agent_commands_does_not_raise_predictive_blame():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    trial.focal_step()
    for _ in range(12): trial.advance_lower()
    # Explicit command-exposure replay control: observations alone are not agent causation.
    trial._maternal_intervals[:] = [replace(item, command=None) for item in trial._maternal_intervals]
    focal = trial.focal_step()
    outcome = focal.maternal_correspondence.outcomes[0]
    assert outcome.status == "observed_without_command" and outcome.command_intervals == 0
    route = MaternalOutcomeAttentionV1(trial.latest_feedback.stream, focal.maternal_source.seed)
    assert admit(route, focal, (outcome,)) == ()


def test_expected_near_but_observed_far_is_significant_without_two_failures():
    trial = create_follow_mom_trial_v1("nominal", outcomes_enabled=True)
    for tick in range(60):
        if tick % 4 == 0: trial.focal_step()
        trial.advance_lower()
    edited = []
    for item in trial._maternal_intervals:
        observations = tuple(replace(obs, self_position=NavPointV1(obs.self_position.x - 0.10, obs.self_position.y))
                             if obs.event_tick == 56 else obs for obs in item.observations)
        deliveries = tuple(replace(sample, planar=replace(sample.planar,
                            position=(observations[0].self_position.x, observations[0].self_position.y)))
                           if sample.event_tick == 56 else sample for sample in item.deliveries)
        edited.append(replace(item, observations=observations, deliveries=deliveries))
    trial._maternal_intervals[:] = edited
    focal = trial.focal_step()
    outcome = focal.maternal_correspondence.outcomes[0]
    assert outcome.claim.preview.predicted_separation <= .5
    assert dict(outcome.relations)["separation"] == "mismatch"
    route = MaternalOutcomeAttentionV1(trial.latest_feedback.stream, focal.maternal_source.seed)
    request, = admit(route, focal, (outcome,))
    assert request.significance == "expected_proximity_not_supported"
    # Genuine newer evidence can resolve current relevance, never rewrite the old failed claim.
    interpretation = route.allocate(focal.calculation.navigation.wnm, cycle_id=focal.calculation.cycle_id).interpretation
    assert interpretation.status == "historical_resolved"
    assert interpretation.current_source.separation <= .5
    assert request.outcome.status == "mismatch"


@pytest.mark.parametrize("batch_kind", ["mutable", "too_large", "duplicated", "untyped"])
def test_malformed_batches_do_not_partially_create_requests(batch_kind):
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    batch = {"mutable": [outcome], "too_large": (outcome,) * 9, "duplicated": (outcome, outcome),
             "untyped": (outcome, object())}[batch_kind]
    before = owner_snapshot(route)
    with pytest.raises((ValueError, TypeError)):
        admit(route, focal, batch)
    assert owner_snapshot(route) == before


def test_unrelated_task_cannot_inherit_prior_maternal_significance():
    _, focal, outcome, route = endpoint_fixture(moved_anchor)
    assert route.admit((outcome,), focal.maternal_source, replace(focal.maternal_task.task, task_id="follow_mom:other"),
                       cutoff_tick=12) == ()
    assert route.pending() == ()


def test_inaccessible_source_cannot_be_reactivated_by_pending_request():
    trial, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    for _ in range(4): trial.advance_lower()
    later = trial.focal_step()
    source = replace(later.maternal_source, identity_status="expired", target_position=None,
                     separation_rate=None, self_closing_rate=None, target_closing_rate=None)
    route.admit((), source, later.maternal_task.task, cutoff_tick=16)
    assert route.pending() and route.contribute_bid(None) is None
    assert route.allocate(None, cycle_id=later.calculation.cycle_id).kind == "other_source"


def test_original_physical_budget_cannot_be_extended_for_interpretation():
    trial, focal, outcome, route = endpoint_fixture(moved_anchor)
    admit(route, focal, (outcome,))
    for _ in range(4): trial.advance_lower()
    later = trial.focal_step()
    # A long focal scheduling gap is a fixture, not a refreshed sensor or new task.
    source = replace(later.maternal_source, visual=replace(later.maternal_source.visual, applied_cycle=21))
    task = later.maternal_task.task
    route.admit((), source, task, cutoff_tick=16)
    working = replace(later.calculation.navigation.wnm, primary_source_state=source, refreshed_cycle=21, focus_age=21)
    assert route.allocate(working, cycle_id=21).kind == "task_budget_exhausted"
    assert route.pending()  # No silent consumption, reinterpretation or renewed task permission.


def test_full_pending_queue_overflow_is_atomic_not_silent_eviction():
    trial, focal, outcome, route = endpoint_fixture(moved_anchor)
    request, = admit(route, focal, (outcome,))
    # Synthetic capacity boundary: normal demo does not accumulate eight requests.
    route._pending = tuple(replace(request, request_id=f"full_queue_fixture:{index}") for index in range(8))
    for _ in range(4): trial.advance_lower()
    later = trial.focal_step()
    incoming = replace(outcome, number=2, evaluated_tick=16)
    before = owner_snapshot(route)
    with pytest.raises(OverflowError):
        admit(route, later, (incoming,))
    assert owner_snapshot(route) == before
