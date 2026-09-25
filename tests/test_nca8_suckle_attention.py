"""Stage-C J contracts and causal integration; no extra experiment scheduler.

Physical cases use the unchanged H provider and IntegratedRightingTrialV1.
Explicit endpoint/current-source alternatives below are TEST FIXTURES, not
asserted physical outcomes. I computes their canonical historical result before
J sees it. Simultaneous questions use actual independently generated I/D claims
on a common typed source; they do not claim two simultaneous motor tasks.
"""
from __future__ import annotations

from dataclasses import replace
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1, OutcomeInterpretationCandidateV1
from nca8_feeding import FeedingDetailCandidateV1, FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_followmom import FollowMomProfileV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_seek_attention import SeekingOutcomeAttentionV1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_seek_nipple import SeekNippleIPV1
from nca8_suckle import SuckleIPV1, SuckleProfileV1
from nca8_suckle_attention import SuckleOutcomeAttentionV1
from nca8_suckle_demo import create_suckle_trial_v1, suckle_profile_v1
from nca8_suckle_outcomes import SuckleEndpointV1, validate_suckle_outcome_v1


def trial_fixture(case="nonsealable", *, route=True, comparison=True, seeking=True):
    """Build H's existing trial with only explicit switches changed; select no task."""
    profile = suckle_profile_v1(case)
    run = profile.run
    seeking_profile = run.seeking if seeking else replace(run.seeking, outcome_attention_enabled=False, learning_hook_enabled=False)
    return IntegratedRightingTrialV1(
        run.physical, stream_id="suckle_latch_reference_body", planar_profile=run.planar, oral_profile=run.oral,
        oral_seal_profile=profile.seal,
        suckle_profile=replace(profile.suckle, outcomes_enabled=True, prediction_comparison_enabled=comparison,
                               outcome_attention_enabled=route),
        capabilities=(*nominal_body_capabilities_v1(), oral_body_capability_v1(), *((profile.capability,) if profile.capability else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=run.stand_follow,
                                             outcome_attention_enabled=run.stand_follow, learning_hook_enabled=run.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=run.feeding,
        seek_nipple_profile=seeking_profile, stand_follow_enabled=run.stand_follow,
        task_outcomes_enabled=run.stand_follow, task_outcome_attention_enabled=run.stand_follow,
        task_learning_hook_enabled=run.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=run.pnm_registration,
    )


def advance(trial, ticks=4):
    """Use the existing finite lower driver; this helper selects no action."""
    return tuple(trial.advance_lower() for _ in range(ticks))


def historical_fixture(change=None, *, case="nonsealable"):
    """Make a real selected H/I claim, optionally alter only its labelled event8 test sample."""
    trial = trial_fixture(case, route=False)
    first = trial.focal_step()
    advance(trial, 12)
    if change is not None:
        intervals = []
        for interval in trial._suckle_intervals:
            deliveries, observations = [], []
            for sample in interval.deliveries:
                observation = next((v for v in interval.observations if v.sample_id == sample.sample_id), None)
                endpoint = SuckleEndpointV1(sample, observation)
                if sample.event_tick == 8:
                    endpoint = change(endpoint)
                if endpoint is not None:
                    deliveries.append(endpoint.feedback)
                    if endpoint.observation is not None:
                        observations.append(endpoint.observation)
            intervals.append(replace(interval, deliveries=tuple(deliveries), observations=tuple(observations)))
        trial._suckle_intervals[:] = intervals
    cycle = trial.focal_step()
    outcome = cycle.suckle_correspondence.outcomes[0] if cycle.suckle_correspondence.outcomes else None
    owner = SuckleOutcomeAttentionV1(trial.latest_feedback.stream, cycle.feeding_detail_source.seed)
    return trial, first, cycle, outcome, owner


def admit(owner, cycle, outcomes, source=None, task=None):
    """Supply a current source and original task without selecting either IP."""
    source = cycle.feeding_detail_source if source is None else source
    return owner.admit(outcomes, source, cycle.suckle_task.task if task is None else task, cutoff_tick=source.cutoff_tick)


def navigation_fixture(source):
    """Use actual Attention and Navigation to establish the fixture source as WNM."""
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1(motor_preview_enabled=True)
    bid = attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    selection = attention.select((bid,), current_wnm=None, cycle_id=source.applied_cycle)
    return navigation, navigation.update_wnm(selection), bid


def interpret(owner, source):
    """Navigation reserves the one opportunity before the source owner consumes it."""
    navigation, working, _ = navigation_fixture(source)
    candidate = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    winner = navigation.allocate_outcome_interpretation(working, (candidate,), cycle_id=source.applied_cycle, at_tick=source.cutoff_tick)
    assert winner is candidate
    allocation = owner.allocate(working, cycle_id=source.applied_cycle, grant=navigation.last_decision)
    return navigation, working, allocation


def state(owner):
    """Capture all mutable route state so invalid input/read-only checks cannot hide mutation."""
    return (owner.pending(), owner.dispositions(), owner.retained_counts(), owner._dependency, owner._source, owner._task,
            owner._last_number, owner._last_admission, owner._last_allocation_cycle, owner._closed)


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "true", [], {}])
def test_J_flag_is_strict_and_requires_original_correspondence(bad):
    with pytest.raises(TypeError):
        SuckleProfileV1(outcomes_enabled=True, outcome_attention_enabled=bad)


def test_J_is_disabled_by_default_and_cannot_bypass_I():
    assert SuckleProfileV1().outcome_attention_enabled is False
    with pytest.raises(ValueError):
        SuckleProfileV1(outcome_attention_enabled=True)
    trial = create_suckle_trial_v1(outcomes_enabled=True)
    cycle = trial.focal_step()
    assert trial.core.feeding_detail.suckle_outcome_attention is None and cycle.suckle_attention is None
    assert "suckle_attention" not in cycle.as_dict()
    assert cycle.suckle_correspondence.as_dict()["attention_route"] == "deferred_suckle_attention"


@pytest.mark.parametrize("bad", [None, True, 0, -1, 33, 1.5, "3"])
def test_diagnostics_have_a_separate_strict_bound(bad):
    with pytest.raises(ValueError):
        SuckleOutcomeAttentionV1(MotorStreamRefV1("fixture", 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


def test_source_owns_one_optional_question_route_without_new_map_or_IP():
    source = FeedingDetailSourceV1(MotorStreamRefV1("fixture", 1), FeedingDetailProfileV1())
    original = source.durable_map.as_dict()
    source.configure_suckle_outcome_attention()
    assert isinstance(source.suckle_outcome_attention, SuckleOutcomeAttentionV1)
    assert source.durable_map.as_dict() == original and source.current is None
    assert not hasattr(source.suckle_outcome_attention, "apply")
    with pytest.raises(RuntimeError):
        source.configure_suckle_outcome_attention()


def test_physical_executed_missing_seal_requests_ordinary_feeding_attention():
    trial = trial_fixture()
    first = trial.focal_step()
    claim = first.suckle_correspondence.registration
    advance(trial, 12)
    cycle = trial.focal_step()
    request, = cycle.suckle_attention.created
    outcome, = cycle.suckle_correspondence.outcomes
    assert outcome.status == "mismatch" and outcome.command_intervals > 0
    assert outcome.claim is claim and request.outcome is outcome
    assert dict(outcome.relations) == {"mouth_position": "matched", "detail_anchor": "matched", "closure": "matched", "seal": "mismatch"}
    assert request.significance == "expected_seal_not_supported" and request.expires_at_tick == 20
    assert cycle.suckle_attention.source_bid.source_map_state is cycle.feeding_detail_source
    assert cycle.calculation.navigation.wnm.primary_source_state is cycle.feeding_detail_source
    assert cycle.suckle_attention.allocation.kind == "interpretation"
    assert cycle.suckle_attention.allocation.interpretation.status == "still_relevant"
    assert cycle.status == "suckle_interpretation"
    assert cycle.suckle_correspondence.as_dict()["attention_route"] == "suckle_outcome_attention_v1"


@pytest.mark.parametrize("prior_competitor", [False, True])
def test_route_ablation_changes_real_attention_with_identical_other_inputs(prior_competitor, monkeypatch):
    on, off = trial_fixture(route=True), trial_fixture(route=False)
    seen = {}
    def capture(name, attention):
        original = attention.select
        def selected(bids, **kwargs):
            seen[name] = tuple(bids)
            return original(bids, **kwargs)
        monkeypatch.setattr(attention, "select", selected)
    capture("on", on.core.cognition.attention)
    capture("off", off.core.cognition.attention)
    first_on, first_off = on.focal_step(), off.focal_step()
    assert first_on.feeding_detail_source == first_off.feeding_detail_source
    steps_on, steps_off = advance(on, 8), advance(off, 8)
    assert steps_on == steps_off
    on.focal_step(visual_bid_priority=(10, 70) if prior_competitor else None)
    off.focal_step(visual_bid_priority=(10, 70) if prior_competitor else None)
    assert advance(on) == advance(off)
    a = on.focal_step(visual_bid_priority=(10, 70))
    b = off.focal_step(visual_bid_priority=(10, 70))
    assert a.feeding_detail_source == b.feeding_detail_source and a.suckle_task == b.suckle_task
    assert a.local_reports == b.local_reports and a.local_events == b.local_events
    assert a.suckle_correspondence.outcomes == b.suckle_correspondence.outcomes
    assert a.calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
    assert b.calculation.attention.selected_source_state.source_map_ref.map_id == "visual_scene"
    assert a.calculation.attention.disposition.value == ("switch" if prior_competitor else "maintain")
    bids_on, bids_off = seen["on"], seen["off"]
    assert len(bids_on) == len(bids_off)
    for left, right in zip(sorted(bids_on, key=lambda x: x.candidate_id), sorted(bids_off, key=lambda x: x.candidate_id)):
        if left.source_map_state.source_map_ref.map_id == "feeding_detail":
            assert replace(left, prediction_or_envelope_failure_rank=right.prediction_or_envelope_failure_rank, reasons=right.reasons) == right
        else:
            assert left == right


def test_interpretation_never_calls_either_IP_or_creates_new_permission(monkeypatch):
    trial = trial_fixture()
    trial.focal_step()
    advance(trial, 12)
    def forbidden(*args, **kwargs):
        pytest.fail("interpretation reapplied a task IP")
    monkeypatch.setattr(SeekNippleIPV1, "apply", forbidden)
    monkeypatch.setattr(SuckleIPV1, "apply", forbidden)
    cycle = trial.focal_step()
    assert cycle.suckle_attention.allocation.kind == "interpretation"
    assert cycle.calculation.navigation.application is None and cycle.calculation.proposal is None
    assert cycle.reservations == () and cycle.suckle_correspondence.registration is None
    assert cycle.calculation.navigation.reason.startswith("outcome_interpretation:suckle_mismatch:")
    navigation = trial.core.cognition.navigation
    with pytest.raises(ValueError, match="focal hold"):
        navigation.commit(navigation.current_wnm, (trial.core.seek_nipple, trial.core.suckle), cycle_id=cycle.commitment.cycle_id)


@pytest.mark.parametrize("current,status", [(False, "still_relevant"), (True, "historical_resolved"), (None, "unresolved_current_relevance")])
def test_present_relevance_never_rewrites_historical_claim_or_outcome(current, status):
    _, _, cycle, outcome, owner = historical_fixture()
    original = json.dumps(outcome.as_dict(), sort_keys=True, allow_nan=False)
    source = cycle.feeding_detail_source
    source = replace(source, oral_feedback=replace(source.oral_feedback, oral_seal=replace(source.oral_feedback.oral_seal, sealed=current)))
    admit(owner, cycle, (outcome,), source)
    _, _, allocation = interpret(owner, source)
    assert allocation.interpretation.status == status
    assert allocation.interpretation.request.outcome is outcome
    assert json.dumps(outcome.as_dict(), sort_keys=True, allow_nan=False) == original
    assert allocation.interpretation.as_dict()["causal_credit"] == "not_established"
    assert not allocation.interpretation.as_dict()["grants_motor_permission"]
    assert not allocation.interpretation.as_dict()["selects_remedy"]


def test_consumer_rejects_missing_Navigation_grant_atomically():
    _, _, cycle, outcome, owner = historical_fixture()
    admit(owner, cycle, (outcome,))
    _, working, _ = navigation_fixture(cycle.feeding_detail_source)
    before = state(owner)
    with pytest.raises(ValueError, match="prior grant"):
        owner.allocate(working, cycle_id=working.refreshed_cycle)
    assert state(owner) == before


def test_candidate_reads_do_not_consume_or_refresh_question():
    _, _, cycle, outcome, owner = historical_fixture()
    request, = admit(owner, cycle, (outcome,))
    _, working, _ = navigation_fixture(cycle.feeding_detail_source)
    before = state(owner)
    first = owner.interpretation_candidate(working, cycle_id=working.refreshed_cycle)
    assert owner.interpretation_candidate(working, cycle_id=working.refreshed_cycle) == first
    assert first.expires_at_tick == request.expires_at_tick == 20 and state(owner) == before


def test_replayed_outcome_cannot_refresh_original_request_then_expiry_removes_it():
    trial, _, cycle, outcome, owner = historical_fixture()
    request, = admit(owner, cycle, (outcome,))
    advance(trial)
    later = trial.focal_step()
    assert admit(owner, later, (outcome,)) == ()
    assert owner.pending() == (request,) and owner.pending()[0] is request
    assert request.admitted_tick == 12 and request.expires_at_tick == 20
    advance(trial)
    expired = trial.focal_step()
    assert admit(owner, expired, (outcome,)) == () and owner.pending() == ()
    assert (request.request_id, "expired_uninterpreted", 20) in owner.dispositions()


@pytest.mark.parametrize("change,status", [
    (lambda ep: replace(ep, observation=None), "unknown"),
    (lambda ep: replace(ep, feedback=replace(ep.feedback, oral_seal=None)), "unknown"),
    (lambda ep: replace(ep, feedback=replace(ep.feedback, oral_seal=replace(ep.feedback.oral_seal, sealed=None))), "unknown"),
])
def test_missing_endpoint_evidence_never_invents_executed_mismatch(change, status):
    _, _, cycle, outcome, owner = historical_fixture(change)
    assert outcome.status == status
    assert admit(owner, cycle, (outcome,)) == ()


@pytest.mark.parametrize("change", [
    lambda o: replace(o, number=True), lambda o: replace(o, number=0), lambda o: replace(o, number=2**63),
    lambda o: replace(o, evidence=None), lambda o: replace(o, installed=False), lambda o: replace(o, installed=1),
    lambda o: replace(o, command_intervals=True), lambda o: replace(o, command_intervals=0),
    lambda o: replace(o, command_intervals=9), lambda o: replace(o, evaluated_tick=13),
    lambda o: replace(o, relations=(("seal", "matched"),)), lambda o: replace(o, status="matched"),
    lambda o: replace(o, residuals=(("closure", float("nan")),)),
])
def test_invalid_or_relabelled_outcome_is_rejected_before_owner_mutation(change):
    _, _, cycle, outcome, owner = historical_fixture()
    before = state(owner)
    with pytest.raises((TypeError, ValueError)):
        admit(owner, cycle, (change(outcome),))
    assert state(owner) == before


@pytest.mark.parametrize("which", ["stream", "seed", "source", "task_region"])
def test_wrong_identity_is_not_a_valid_cognitive_mismatch(which):
    _, _, cycle, outcome, owner = historical_fixture()
    source, task = cycle.feeding_detail_source, cycle.suckle_task.task
    if which == "stream":
        owner = SuckleOutcomeAttentionV1(MotorStreamRefV1("foreign", 2), source.seed)
    elif which == "seed":
        owner = SuckleOutcomeAttentionV1(source.stream, replace(source.seed, detail_region_id="another_part"))
    elif which == "source":
        maternal = replace(source.maternal, seed=replace(source.maternal.seed, region_id="foreign_parent"),
                           identity_status="unestablished", target_position=None, last_supported_tick=None,
                           separation_rate=None, self_closing_rate=None, target_closing_rate=None)
        source = replace(source, maternal=maternal)
    else:
        task = replace(task, region_id="another_part")
    before = state(owner)
    with pytest.raises((TypeError, ValueError)):
        admit(owner, cycle, (outcome,), source, task)
    assert state(owner) == before


@pytest.mark.parametrize("case", ["nominal", "narrowed", "missing_seal", "no_capability", "blocked_motor", "cancelled"])
def test_nonmismatch_or_nonexecuted_physical_controls_do_not_request_execution_failure(case):
    trial = trial_fixture(case)
    trial.focal_step()
    for _ in range(4):
        advance(trial)
        cycle = trial.focal_step()
        assert cycle.suckle_attention.created == ()
        assert cycle.suckle_attention.allocation.kind != "interpretation"


def test_comparison_off_retains_exposure_but_cannot_invent_a_mismatch_request():
    trial = trial_fixture(comparison=False)
    trial.focal_step()
    advance(trial, 12)
    cycle = trial.focal_step()
    outcome, = cycle.suckle_correspondence.outcomes
    assert outcome.status == "comparison_disabled" and outcome.command_intervals > 0
    assert cycle.suckle_attention.created == ()


def test_reset_discards_J_questions_without_resurrecting_old_generation():
    trial = trial_fixture()
    trial.focal_step()
    advance(trial, 12)
    trial.focal_step(visual_bid_priority=(100, 100))
    owner = trial.core.feeding_detail.suckle_outcome_attention
    assert owner.pending()
    stream = owner.stream
    trial.reset()
    fresh = trial.core.feeding_detail.suckle_outcome_attention
    assert fresh is not owner and fresh.stream.generation == stream.generation + 1
    assert fresh.pending() == () and fresh.retained_counts()["suckle_attention_dependency"] == 0


def seeking_fixture():
    """Generate a D claim with this same declared stream; substitute only event8 evidence."""
    trial = trial_fixture("seek_then_latch", route=False, seeking=False)
    first = trial.focal_step()
    assert first.calculation.navigation.selected_primitive_id == "ip:seek_nipple"
    advance(trial, 12)
    intervals = []
    for interval in trial._seeking_intervals:
        deliveries = tuple(replace(sample, oral=replace(sample.oral, extension_metres=sample.oral.extension_metres + 0.01))
                           if sample.event_tick == 8 else sample for sample in interval.deliveries)
        intervals.append(replace(interval, deliveries=deliveries))
    trial._seeking_intervals[:] = intervals
    cycle = trial.focal_step()
    outcome, = cycle.seeking_correspondence.outcomes
    assert outcome.status == "mismatch"
    return trial, cycle, outcome


def simultaneous_fixture(older_suckle=False, *, unknown=False):
    """Supply two actual original outcomes to one selected-source allocation fixture.

    The donor trials are independent, with explicitly identical stream/seed names
    for this contract test. This is not a claim of simultaneous physical tasks.
    Only the shared session's actual Attention/Navigation path selects focal work.
    """
    donor = trial_fixture(route=False)
    first = donor.focal_step()
    session = Nca8RightingPreviewSessionV1(donor.latest_feedback.stream, visual_preview_enabled=True,
                                          additional_primitives=(donor.core.seek_nipple, donor.core.suckle))
    session.preview(donor.latest_feedback, cutoff_tick=0)
    suckle = SuckleOutcomeAttentionV1(donor.latest_feedback.stream, donor.core.feeding_detail.current.seed)
    if older_suckle:
        advance(donor, 10)
        earlier = donor.focal_step()
        admit(suckle, earlier, earlier.suckle_correspondence.outcomes)
        session.preview(donor.latest_feedback, cutoff_tick=10)
        advance(donor, 2)
    else:
        advance(donor, 12)
    cycle = donor.focal_step()
    if unknown:
        cycle = replace(cycle, feeding_detail_source=replace(cycle.feeding_detail_source, oral_feedback=None))
    admit(suckle, cycle, cycle.suckle_correspondence.outcomes)
    _, seek_cycle, outcome = seeking_fixture()
    seeking = SeekingOutcomeAttentionV1(donor.latest_feedback.stream, cycle.feeding_detail_source.seed)
    seeking.admit((outcome,), cycle.feeding_detail_source, seek_cycle.seeking_task.task, cutoff_tick=12)
    ordinary = session.attention.build_bid(FeedingDetailCandidateV1(cycle.feeding_detail_source, 0), cycle_id=cycle.commitment.cycle_id)
    bid = suckle.contribute_bid(seeking.contribute_bid(ordinary))
    assert bid.prediction_or_envelope_failure_rank == 40  # max, not doubled importance
    prepared = session.prepare_source(donor.latest_feedback, cutoff_tick=12, competing_bids=(bid,))
    return donor, first, cycle, session, prepared, seeking, suckle, seek_cycle.seeking_task.task


@pytest.mark.parametrize("older_suckle", [False, True])
def test_same_source_arbitration_grants_first_consumes_only_winner_and_preserves_loser(older_suckle, monkeypatch):
    donor, _, cycle, session, prepared, seeking, suckle, seek_task = simultaneous_fixture(older_suckle)
    seek_question, = seeking.pending()
    suckle_question, = suckle.pending()
    seen = []
    def witness(name, owner):
        original = owner.allocate
        def consume(*args, **kwargs):
            grant = session.navigation.last_decision
            assert grant is not None and grant.cycle_id == prepared.cycle_id
            assert grant.application is None and grant.reason == f"outcome_interpretation:{owner.pending()[0].request_id}"
            assert seeking.pending() == (seek_question,) and suckle.pending() == (suckle_question,)
            seen.append(name)
            return original(*args, **kwargs)
        monkeypatch.setattr(owner, "allocate", consume)
    witness("seeking", seeking)
    witness("suckle", suckle)
    def forbidden(*args, **kwargs):
        pytest.fail("an interpretation called an IP apply method")
    monkeypatch.setattr(SeekNippleIPV1, "apply", forbidden)
    monkeypatch.setattr(SuckleIPV1, "apply", forbidden)
    result = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=suckle)
    assert seen == (["suckle"] if older_suckle else ["seeking"])
    assert sum(a.kind == "interpretation" for a in (result.seeking_outcome_allocation, result.suckle_outcome_allocation)) == 1
    assert result.navigation.application is None and result.proposal is None
    loser, original = (seeking, seek_question) if older_suckle else (suckle, suckle_question)
    assert loser.pending() == (original,) and loser.pending()[0] is original
    assert original.expires_at_tick == 20
    assert loser._last_allocation_cycle == 0  # Not even its allocator was invoked.
    session.project_selected(result)
    advance(donor)
    later = donor.focal_step()
    seeking.admit((), later.feeding_detail_source, seek_task, cutoff_tick=16)
    admit(suckle, later, ())
    assert loser.pending() == (original,) and original.expires_at_tick == 20
    advance(donor)
    expired = donor.focal_step()
    seeking.admit((), expired.feeding_detail_source, seek_task, cutoff_tick=20)
    admit(suckle, expired, ())
    assert loser.pending() == () and (original.request_id, "expired_uninterpreted", 20) in loser.dispositions()


def test_loser_can_win_a_later_ordinary_focal_opportunity_without_new_lifetime():
    donor, _, _, session, prepared, seeking, suckle, seek_task = simultaneous_fixture()
    losing_question, = suckle.pending()
    first = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=suckle)
    assert first.seeking_outcome_allocation.kind == "interpretation"
    session.project_selected(first)
    advance(donor)
    later = donor.focal_step()
    seeking.admit((), later.feeding_detail_source, seek_task, cutoff_tick=16)
    admit(suckle, later, ())
    bid = session.attention.build_bid(FeedingDetailCandidateV1(later.feeding_detail_source, 0), cycle_id=later.commitment.cycle_id)
    bid = suckle.contribute_bid(seeking.contribute_bid(bid))
    ready = session.prepare_source(donor.latest_feedback, cutoff_tick=16, competing_bids=(bid,))
    second = session.select_prepared(ready, seeking_attention=seeking, suckle_attention=suckle)
    assert second.suckle_outcome_allocation.kind == "interpretation"
    assert second.suckle_outcome_allocation.interpretation.request is losing_question
    assert losing_question.expires_at_tick == 20 and second.navigation.application is None
    assert second.seeking_outcome_allocation.kind == "deferred_other_interpretation"


@pytest.mark.parametrize("reverse", [False, True])
def test_Navigation_tie_policy_is_independent_of_request_registration_order(reverse):
    _, _, cycle, _, _ = historical_fixture()
    source = cycle.feeding_detail_source
    navigation, working, _ = navigation_fixture(source)
    first = OutcomeInterpretationCandidateV1("a:question", source, 10, 18)
    second = OutcomeInterpretationCandidateV1("z:question", source, 10, 18)
    offered = (second, first) if reverse else (first, second)
    winner = navigation.allocate_outcome_interpretation(working, offered, cycle_id=source.applied_cycle, at_tick=12)
    assert winner is first and navigation.last_decision.application is None
    with pytest.raises(ValueError, match="already been used"):
        navigation.allocate_outcome_interpretation(working, offered, cycle_id=source.applied_cycle, at_tick=12)


@pytest.mark.parametrize("defect", ["expired", "premature", "foreign_source", "duplicate", "too_many", "IP", "list"])
def test_Navigation_rejects_bad_candidates_before_any_reservation(defect):
    _, _, cycle, _, _ = historical_fixture()
    source = cycle.feeding_detail_source
    navigation, working, _ = navigation_fixture(source)
    candidate = OutcomeInterpretationCandidateV1("question", source, 12, 20)
    offered = (candidate,)
    if defect == "expired":
        offered = (replace(candidate, admitted_tick=4, expires_at_tick=12),)
    elif defect == "premature":
        offered = (replace(candidate, admitted_tick=13),)
    elif defect == "foreign_source":
        offered = (replace(candidate, source=replace(source)),)
    elif defect == "duplicate":
        offered = (candidate, candidate)
    elif defect == "too_many":
        offered = tuple(replace(candidate, request_id=f"question:{i}") for i in range(4))
    elif defect == "IP":
        offered = (SuckleIPV1,)
    else:
        offered = [candidate]
    with pytest.raises((TypeError, ValueError)):
        navigation.allocate_outcome_interpretation(working, offered, cycle_id=source.applied_cycle, at_tick=12)
    assert navigation.last_decision is None and navigation.current_wnm is working


def test_empty_question_set_leaves_normal_IP_selection_available():
    _, _, cycle, _, _ = historical_fixture()
    source = cycle.feeding_detail_source
    navigation, working, _ = navigation_fixture(source)
    assert navigation.allocate_outcome_interpretation(working, (), cycle_id=source.applied_cycle, at_tick=12) is None
    assert navigation.last_decision is None
    assert navigation.commit(working, (), cycle_id=source.applied_cycle).reason == "no_eligible_primitive"


def test_later_reconsideration_uses_ordinary_Navigation_without_restarting_Suckle(monkeypatch):
    trial = trial_fixture()
    first = trial.focal_step()
    task_id = first.suckle_task.task.task_id
    advance(trial, 12)
    interpreted = trial.focal_step()
    assert interpreted.suckle_attention.allocation.kind == "interpretation"
    calls = []
    original = trial.core.cognition.navigation.commit
    def commit(working, primitives, **kwargs):
        calls.append((working, kwargs["cycle_id"]))
        return original(working, primitives, **kwargs)
    monkeypatch.setattr(trial.core.cognition.navigation, "commit", commit)
    advance(trial)
    later = trial.focal_step()
    assert len(calls) == 1 and calls[0][1] == later.commitment.cycle_id
    assert later.suckle_attention.allocation.kind == "response_reconsideration"
    assert later.suckle_task.task.task_id == task_id and later.suckle_task.task.started_tick == 0
    assert later.calculation.navigation.application is None  # Closed/no-seal state does not invent a remedy.
    assert later.reservations == ()


def test_unknown_interpretation_imposes_bounded_hold_not_a_second_interpretation():
    trial, _, cycle, outcome, owner = historical_fixture()
    source = cycle.feeding_detail_source
    unknown = replace(source, oral_feedback=None)
    admit(owner, cycle, (outcome,), unknown)
    _, _, result = interpret(owner, unknown)
    assert result.interpretation.status == "unresolved_current_relevance"
    advance(trial)
    later = trial.focal_step()
    admit(owner, later, ())
    _, working, _ = navigation_fixture(later.feeding_detail_source)
    assert owner.interpretation_candidate(working, cycle_id=later.commitment.cycle_id) is None
    hold = owner.allocate(working, cycle_id=later.commitment.cycle_id)
    assert hold.kind == "dependent_unresolved" and hold.as_dict()["interpretation_count"] == 0
    advance(trial)
    expired = trial.focal_step()
    admit(owner, expired, ())
    assert owner.retained_counts()["suckle_attention_dependency"] == 0


@pytest.mark.parametrize("closure,qualifies", [(0.57, False), (0.55, True), (0.54, True)])
def test_significance_threshold_does_not_change_I_correspondence_tolerance(closure, qualifies):
    _, _, cycle, outcome, owner = historical_fixture(
        lambda ep: replace(ep, feedback=replace(ep.feedback, oral_seal=replace(ep.feedback.oral_seal, closure=closure))), case="nominal")
    assert outcome.status == "mismatch" and dict(outcome.relations)["seal"] == "matched"
    requests = admit(owner, cycle, (outcome,))
    assert bool(requests) is qualifies
    if requests:
        assert requests[0].relations == ("closure",)


def test_expired_missing_endpoint_is_not_a_seal_failure():
    trial, _, cycle, _, owner = historical_fixture(lambda ep: None)
    assert cycle.suckle_correspondence.outcomes == ()
    advance(trial, 5)
    expired = trial.focal_step()
    outcome, = expired.suckle_correspondence.outcomes
    assert outcome.status == "expired_unresolved" and outcome.evidence is None
    assert admit(owner, expired, (outcome,)) == ()


def test_two_unknown_dependencies_use_one_hold_without_two_interpretations(monkeypatch):
    donor, _, _, session, prepared, seeking, suckle, seek_task = simultaneous_fixture(unknown=True)
    first = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=suckle)
    assert first.seeking_outcome_allocation.interpretation.status == "unresolved_current_relevance"
    session.project_selected(first)
    for tick in (16, 17):
        advance(donor, tick - donor.tick)
        cycle = donor.focal_step()
        source = replace(cycle.feeding_detail_source, oral_feedback=None)
        seeking.admit((), source, seek_task, cutoff_tick=tick)
        admit(suckle, cycle, (), source)
        bid = session.attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
        bid = suckle.contribute_bid(seeking.contribute_bid(bid))
        prepared = session.prepare_source(donor.latest_feedback, cutoff_tick=tick, competing_bids=(bid,))
        if tick == 17:
            def forbidden(*args, **kwargs):
                pytest.fail("two dependencies must not perform another interpretation or IP application")
            monkeypatch.setattr(seeking, "_relevance", forbidden)
            monkeypatch.setattr(suckle, "_relevance", forbidden)
            monkeypatch.setattr(SeekNippleIPV1, "apply", forbidden)
            monkeypatch.setattr(SuckleIPV1, "apply", forbidden)
        result = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=suckle)
        if tick == 16:
            assert result.suckle_outcome_allocation.interpretation.status == "unresolved_current_relevance"
        else:
            assert result.navigation.reason == "feeding_dependent_unresolved"
            assert result.seeking_outcome_allocation.kind == result.suckle_outcome_allocation.kind == "dependent_unresolved"
            assert result.navigation.application is None
        session.project_selected(result)


@pytest.mark.parametrize("dimension,limit,eligible", [("physical", 47, True), ("physical", 48, False),
                                                      ("focal", 12, True), ("focal", 13, False)])
def test_interpretation_cannot_restart_or_extend_original_task_budget(dimension, limit, eligible):
    trial, _, cycle, outcome, owner = historical_fixture()
    if dimension == "physical":
        while trial.tick < limit:
            advance(trial, min(12, limit - trial.tick))
            cycle = trial.focal_step()
    else:
        while cycle.commitment.cycle_id < limit:
            advance(trial, 1)
            cycle = trial.focal_step()
    # Deliberately delayed publication fixture, not changed historical event/claim/permission.
    published = replace(outcome, evaluated_tick=trial.tick)
    admit(owner, cycle, (published,))
    source = cycle.feeding_detail_source
    navigation, working, ordinary = navigation_fixture(source)
    bid = owner.contribute_bid(ordinary)
    candidate = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    assert (candidate is not None) is eligible
    assert (bid.prediction_or_envelope_failure_rank == 40) is eligible
    if candidate is not None:
        navigation.allocate_outcome_interpretation(working, (candidate,), cycle_id=source.applied_cycle, at_tick=source.cutoff_tick)
    allocation = owner.allocate(working, cycle_id=source.applied_cycle, grant=navigation.last_decision)
    assert allocation.kind == ("interpretation" if eligible else "task_budget_exhausted")
    assert cycle.suckle_task.task.started_cycle == 1 and cycle.suckle_task.task.started_tick == 0
    assert outcome.evaluated_tick == 12


@pytest.mark.parametrize("delta,qualifies", [(0.01, False), (0.0199, False), (0.02, True), (0.03, True)])
def test_anchor_significance_is_not_any_small_geometric_mismatch(delta, qualifies):
    def moved(endpoint):
        observations = replace(endpoint.observation, detections=tuple(
            replace(item, position=NavPointV1(item.position.x + delta, item.position.y)) if item.region_id == "region_2" else item
            for item in endpoint.observation.detections))
        return replace(endpoint, observation=observations)
    # Closure 0.3 is not predicted to seal; narrowed claims cannot supply dependent seal errors.
    _, _, cycle, outcome, owner = historical_fixture(moved, case="narrowed")
    assert outcome.status == "mismatch" and "detail_anchor" in dict(outcome.relations)
    assert bool(admit(owner, cycle, (outcome,))) is qualifies


def test_historical_identity_contradiction_is_distinct_from_wrong_transport_identity():
    def contradicted(endpoint):
        return replace(endpoint, observation=replace(endpoint.observation, detections=tuple(
            replace(item, descriptor="landmark") if item.region_id == "region_2" else item for item in endpoint.observation.detections)))
    _, _, cycle, outcome, owner = historical_fixture(contradicted)
    assert outcome.status == "identity_contradicted"
    request, = admit(owner, cycle, (outcome,))
    assert request.significance == "feeding_part_identity_contradiction"
    _, _, result = interpret(owner, cycle.feeding_detail_source)
    assert result.interpretation.status == "historical_resolved" and outcome.status == "identity_contradicted"


def test_nonexecuted_outcome_keeps_its_disposition_and_never_requests_executed_failure():
    trial = trial_fixture(route=False)
    trial.focal_step()
    advance(trial, 12)
    # Explicit exposure-ablation fixture: no returned nonzero closure command.
    # Physics is not claimed to have been driven by these altered interval records.
    trial._suckle_intervals[:] = [replace(item, command=None) for item in trial._suckle_intervals]
    cycle = trial.focal_step()
    outcome, = cycle.suckle_correspondence.outcomes
    assert outcome.status == "observed_without_command" and outcome.command_intervals == 0
    owner = SuckleOutcomeAttentionV1(trial.latest_feedback.stream, cycle.feeding_detail_source.seed)
    assert admit(owner, cycle, (outcome,)) == ()


def test_public_validator_is_read_only_and_retains_original_publisher_history():
    trial, _, _, outcome, _ = historical_fixture()
    before = trial.core.suckle_outcomes.history()
    validate_suckle_outcome_v1(outcome, stream=trial.latest_feedback.stream, cutoff_tick=12)
    validate_suckle_outcome_v1(outcome, stream=trial.latest_feedback.stream, cutoff_tick=16)
    assert trial.core.suckle_outcomes.history() == before
    assert trial.core.suckle_outcomes.history()[0] is outcome


def test_Navigation_ablation_does_not_allow_domain_owner_to_interpret():
    trial = trial_fixture()
    trial.focal_step()
    advance(trial, 12)
    trial.core.cognition.navigation._enabled = False  # Explicit ablation of the actual authority.
    cycle = trial.focal_step()
    assert len(cycle.suckle_attention.pending) == 1
    assert cycle.suckle_attention.allocation.kind == "navigation_disabled"
    assert cycle.calculation.navigation.application is None


def test_another_selected_source_leaves_Suckle_question_unconsumed():
    trial = trial_fixture()
    trial.focal_step()
    advance(trial, 12)
    cycle = trial.focal_step(visual_bid_priority=(100, 100))
    assert cycle.calculation.attention.selected_source_state.source_map_ref.map_id == "visual_scene"
    assert cycle.suckle_attention.allocation.kind == "other_source"
    assert len(cycle.suckle_attention.pending) == 1 and cycle.suckle_attention.pending[0].expires_at_tick == 20


def test_duplicate_claim_batch_and_bad_cutoff_leave_admission_atomic():
    _, _, cycle, outcome, owner = historical_fixture()
    before = state(owner)
    with pytest.raises(ValueError):
        admit(owner, cycle, (outcome, replace(outcome, number=outcome.number + 1)))
    assert state(owner) == before
    with pytest.raises(ValueError):
        owner.admit((outcome,), cycle.feeding_detail_source, cycle.suckle_task.task, cutoff_tick=True)
    assert state(owner) == before
