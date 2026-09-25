"""L-F causal participation, independent time and no-learning boundary tests.

Canonical examples are produced by the accepted extraction/Attention factories.
Constructed timestamp/current-source variants below are labelled contract fixtures,
not additional physical experiments. The hook has no interpretation or motor role.
"""
from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_contracts import CyclePhase
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
from nca8_feeding import FeedingDetailCandidateV1, FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle import SuckleProfileV1
from nca8_suckle_extraction_attention import SuckleExtractionAttentionV1
from nca8_suckle_extraction_attention_demo import EXTRACTION_ATTENTION_CASES_V1, extraction_attention_profile_v1
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1
from nca8_suckle_extraction_learning import SuckleExtractionLearningHookV1


def profile_for(case="matched", *, hook=True):
    """Change only the new participation switch on an accepted fixed profile."""
    profile = extraction_attention_profile_v1(case)
    return replace(profile, latch=replace(profile.latch, suckle=replace(
        profile.latch.suckle, extraction_learning_hook_enabled=hook)))


def collect(case="matched", *, hook=True, capacity=256):
    profile = profile_for(case, hook=hook)
    trial = create_suckle_extraction_trial_v1(profile, trace_capacity=capacity)
    return trial, collect_seek_nipple_evidence_v1(trial, profile.latch.run)


def state(hook):
    """Capture functional/replay state as well as disposable history for atomicity."""
    return (hook.pending(), hook.history(), hook.retained_counts(), hook._registration, hook._seen, hook._dependency,
            hook._interpretation_seen, hook._last_cycle, hook._last_tick, hook._closed)


@pytest.fixture(scope="module")
def originals():
    data = {}
    for case in ("matched", "mismatch", "latch_then_extract", "comparison_off", "no_capability"):
        trial, run = collect(case, hook=False)
        first = next(c for c in run.cycles if c.extraction_correspondence.registration is not None)
        last = next(c for c in run.cycles if c.extraction_correspondence.outcomes)
        data[case] = trial, first, last
    return data


def fresh(originals, case="matched", *, capacity=8, register=True):
    trial, first, last = originals[case]
    claim = first.extraction_correspondence.registration
    hook = SuckleExtractionLearningHookV1(trial.latest_feedback.stream, claim.application.projection.basis.seed,
                                         diagnostic_capacity=capacity)
    if register:
        hook.reconcile(cycle_id=first.commitment.cycle_id, cutoff_tick=first.calculation.cutoff_tick, registration=claim,
                       comparison_enabled=case != "comparison_off")
    return hook, first, last


def performed(cycle):
    frame = cycle.extraction_attention
    return frame.allocation.interpretation if frame is not None and frame.allocation.kind == "interpretation" else None


def offer(hook, cycle, **changes):
    frame = cycle.extraction_attention
    args = dict(cycle_id=cycle.commitment.cycle_id, cutoff_tick=cycle.calculation.cutoff_tick,
                outcomes=cycle.extraction_correspondence.outcomes,
                requests=frame.created if frame is not None else (), interpretation=performed(cycle))
    args.update(changes)
    return hook.reconcile(**args)


@pytest.mark.parametrize("bad", [None, True, 0, -1, 9, 1.5, "4"])
def test_diagnostic_capacity_is_independent_bounded_integer(bad):
    with pytest.raises(ValueError):
        SuckleExtractionLearningHookV1(MotorStreamRefV1("fixture", 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "true", [], {}])
def test_default_disabled_strict_boolean_switch(bad):
    assert SuckleProfileV1().extraction_learning_hook_enabled is False
    with pytest.raises(TypeError):
        SuckleProfileV1(extraction_learning_hook_enabled=bad)


@pytest.mark.parametrize("field", ["stream", "seed"])
def test_constructor_rejects_wrong_domain_objects(field):
    with pytest.raises(TypeError):
        SuckleExtractionLearningHookV1(None if field == "stream" else MotorStreamRefV1("fixture", 1),
                                       None if field == "seed" else FeedingDetailSeedV1())


def test_LD_is_required_but_no_latch_or_attention_dependency():
    with pytest.raises(ValueError):
        SuckleProfileV1(extraction_enabled=True, extraction_learning_hook_enabled=True)
    p = SuckleProfileV1(extraction_enabled=True, extraction_outcomes_enabled=True, extraction_learning_hook_enabled=True)
    assert not p.outcomes_enabled and not p.learning_hook_enabled and not p.extraction_outcome_attention_enabled
    assert p.as_dict()["extraction_eligibility_lifetime_ticks"] == 24
    assert p.as_dict()["maximum_extraction_learning_participants"] == 1
    trial, run = collect("without_latch_route")
    assert trial.core.suckle.task is None and trial.core.suckle_outcomes is None
    assert trial.core.feeding_detail.suckle_learning_hook is None
    assert any(d.status == "accepted_no_update" for c in run.cycles for d in c.extraction_learning_report.dispositions)


def test_source_attachment_is_once_before_updates_and_failed_config_is_atomic():
    source = FeedingDetailSourceV1(MotorStreamRefV1("fixture", 1), FeedingDetailProfileV1())
    before = source.durable_map.as_dict()
    with pytest.raises(ValueError):
        source.configure_extraction_learning_hook(diagnostic_capacity=9)
    assert source.extraction_learning_hook is None
    source.configure_extraction_learning_hook()
    assert source.current is None and source.durable_map.as_dict() == before
    assert source.extraction_learning_hook.seed == source.profile.seed
    with pytest.raises(RuntimeError):
        source.configure_extraction_learning_hook()
    trial = create_suckle_extraction_trial_v1(profile_for(hook=False))
    trial.focal_step()
    with pytest.raises(RuntimeError):
        trial.core.feeding_detail.configure_extraction_learning_hook()


def test_original_registration_has_no_future_outcome_and_exact_body_PNM_identity(originals):
    hook, first, _ = fresh(originals)
    participant, = hook.pending()
    assert participant.claim is first.extraction_correspondence.registration
    assert participant.claim.application is first.calculation.navigation.application
    assert participant.claim.targets[0] is first.reservations[0].current
    assert participant.claim.targets[0].target.basis is participant.claim.application.projection.basis.oral_feedback
    assert participant.expires_before_tick == first.calculation.cutoff_tick + 24
    assert participant.outcome is None and participant.request is None
    assert participant.as_dict()["grants_motor_authority"] is False


def test_F_callback_runs_before_installation_and_receives_exact_C2_tuple(monkeypatch):
    trial = create_suckle_extraction_trial_v1(profile_for())
    hook, owner = trial.core.feeding_detail.extraction_learning_hook, trial.core.extraction_outcomes
    original_reconcile, consume = hook.reconcile, owner.consume_intervals
    offered = []
    def capture(*args, **kwargs):
        batch = consume(*args, **kwargs)
        offered.append(batch)
        return batch
    def reconcile(**kwargs):
        assert trial.core.scheduler._last_phase_value == CyclePhase.LEARNING_SCHEDULE.value
        assert kwargs["outcomes"] is offered[-1]
        if kwargs["registration"] is not None:
            assert not owner._evidence.installed
            assert kwargs["outcomes"] == ()
        return original_reconcile(**kwargs)
    monkeypatch.setattr(owner, "consume_intervals", capture)
    monkeypatch.setattr(hook, "reconcile", reconcile)
    first = trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    later = trial.focal_step()
    assert first.extraction_learning_report.new_participation is not None
    assert later.extraction_learning_report.dispositions[-1].outcome is offered[-1][0]


def test_known_comparisons_consumed_once_and_no_durable_or_RNG_change(originals, monkeypatch):
    hook, _, last = fresh(originals)
    rng = random.getstate()
    def forbidden(*_args, **_kwargs):
        raise AssertionError("F cannot interpret relevance or classify significance")
    monkeypatch.setattr(SuckleExtractionAttentionV1, "_relevance", forbidden)
    monkeypatch.setattr(SuckleExtractionAttentionV1, "_significance", forbidden)
    report = offer(hook, last)
    disposition, = report.dispositions
    assert disposition.status == "accepted_no_update" and len(disposition.accepted_relations) == 4
    assert disposition.outcome is last.extraction_correspondence.outcomes[0]
    assert not hook.pending() and random.getstate() == rng
    duplicate = offer(hook, last, cycle_id=last.commitment.cycle_id + 1, cutoff_tick=last.calculation.cutoff_tick + 1)
    assert [d.status for d in duplicate.dispositions] == ["duplicate_ignored"]
    assert report.as_dict()["durable_learning_updates"] == 0
    assert disposition.as_dict()["milk_evidence"]["nourishment"] == "not_established"


def test_interrupted_execution_does_not_erase_known_relations(originals):
    hook, _, last = fresh(originals, "mismatch")
    report = offer(hook, last)
    accepted = report.dispositions[-1]
    assert accepted.status == "accepted_no_update"
    assert accepted.outcome.status == "interrupted"
    assert ("sealed_contact", "mismatch") in accepted.accepted_relations
    assert ("finite_reciprocation", "interrupted") in accepted.outcome.relations
    assert "finite_reciprocation" not in dict(accepted.accepted_relations)
    assert accepted.interpretation is performed(last)
    assert not hook.pending()


@pytest.mark.parametrize("case", ["route_off", "source_unavailable"])
def test_missing_real_interpretation_waits_then_expires_without_motor_permission(case):
    trial, run = collect(case)
    history = trial.core.feeding_detail.extraction_learning_hook.history()
    assert [d.status for d in history] == ["pending_interpretation", "eligibility_expired"]
    assert history[-1].cutoff_tick == 24
    assert not trial.core.feeding_detail.extraction_learning_hook.pending()
    assert not any(d.accepted_relations for d in history)
    assert all(c.extraction_learning_report.as_dict()["restores_motor_permission"] is False for c in run.cycles)


def test_latch_K_and_extraction_have_distinct_recipients_and_clocks():
    trial, run = collect("latch_then_extract")
    latch = [c.suckle_learning_report.new_participation for c in run.cycles
             if c.suckle_learning_report is not None and c.suckle_learning_report.new_participation is not None]
    extraction = [c.extraction_learning_report.new_participation for c in run.cycles
                  if c.extraction_learning_report.new_participation is not None]
    assert len(latch) == len(extraction) == 1
    assert latch[0].expires_before_cycle == latch[0].created_cycle + 4
    assert extraction[0].claim.start_tick == 12 and extraction[0].expires_before_tick == 36
    assert latch[0].recipient_id != extraction[0].recipient_id
    assert trial.core.feeding_detail.suckle_learning_hook is not trial.core.feeding_detail.extraction_learning_hook


@pytest.mark.parametrize("cadence,cycle,tick", [(1, 10, 9), (4, 4, 12), (8, 3, 16)])
def test_ordinary_extraction_eligibility_is_physical_not_four_focal_cycles(cadence, cycle, tick):
    p = profile_for()
    p = replace(p, latch=replace(p.latch, run=replace(p.latch.run, cadence=cadence)))
    trial = create_suckle_extraction_trial_v1(p)
    run = collect_seek_nipple_evidence_v1(trial, p.latch.run)
    accepted = [d for c in run.cycles for d in c.extraction_learning_report.dispositions if d.status == "accepted_no_update"]
    assert len(accepted) == 1 and (accepted[0].cycle_id, accepted[0].cutoff_tick) == (cycle, tick)
    assert run.cycles[0].extraction_learning_report.new_participation.expires_before_tick == 24


def test_real_late_publication_can_resolve_LD_after_LF_expiry():
    """A deliberate bounded delayed focal schedule, not a different sensor result."""
    trial = create_suckle_extraction_trial_v1(profile_for())
    first = trial.focal_step()
    for _ in range(8):
        trial.advance_lower()
    middle = trial.focal_step()
    assert not middle.extraction_correspondence.outcomes
    assert middle.extraction_learning_report.pending[0].expires_before_tick == 24
    for _ in range(16):
        trial.advance_lower()
    last = trial.focal_step()
    outcome, = last.extraction_correspondence.outcomes
    assert outcome.claim is first.extraction_correspondence.registration
    assert outcome.status == "local_sequence_observed" and outcome.evaluated_tick == 24
    assert [d.status for d in last.extraction_learning_report.dispositions] == ["eligibility_expired", "rejected_expired_eligibility"]


@pytest.mark.parametrize("tick,accepted", [(23, True), (24, False), (25, False)])
def test_exact_eligibility_cutoff_contract(originals, tick, accepted):
    """Constructed delayed publication of the same bounded physical evidence."""
    hook, _, last = fresh(originals)
    outcome = replace(last.extraction_correspondence.outcomes[0], evaluated_tick=tick)
    report = hook.reconcile(cycle_id=20, cutoff_tick=tick, outcomes=(outcome,))
    assert any(d.status == "accepted_no_update" for d in report.dispositions) == accepted
    assert not hook.pending()


def test_unregistered_result_does_not_invent_participation(originals):
    hook, _, last = fresh(originals, register=False)
    report = offer(hook, last)
    assert [d.status for d in report.dispositions] == ["rejected_unregistered_operation"]
    assert report.new_participation is None and not hook.pending()


@pytest.mark.parametrize("case,status", [("no_capability", "not_applied"), ("comparison_off", "comparison_disabled_no_teaching")])
def test_veto_and_comparison_off_do_not_create_eligible_execution(originals, case, status):
    hook, first, _ = fresh(originals, case)
    assert not hook.pending() and [d.status for d in hook.history()] == [status]
    assert first.calculation.navigation.application is not None


@pytest.mark.parametrize("bad", [True, None, -1, 1.5, "1", 2**63])
@pytest.mark.parametrize("field", ["cycle_id", "cutoff_tick"])
def test_invalid_time_rejected_before_mutation(originals, field, bad):
    hook, _, _ = fresh(originals)
    before = state(hook)
    with pytest.raises(ValueError):
        hook.reconcile(**{**dict(cycle_id=2, cutoff_tick=4), field: bad})
    assert state(hook) == before


@pytest.mark.parametrize("field", ["comparison_enabled", "attention_enabled"])
def test_nonboolean_settings_reject_atomically(originals, field):
    hook, _, last = fresh(originals)
    before = state(hook)
    with pytest.raises(TypeError):
        offer(hook, last, **{field: 1})
    assert state(hook) == before


@pytest.mark.parametrize("field", ["outcomes", "requests"])
@pytest.mark.parametrize("bad", [None, [], (None, None)])
def test_bounded_immutable_F_batches(originals, field, bad):
    hook, _, last = fresh(originals)
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, **{field: bad})
    assert state(hook) == before


@pytest.mark.parametrize("variant", ["copied_claim", "forged_relations", "future_publication", "future_sample", "copied_target"])
def test_altered_canonical_evidence_rejected_atomically(originals, variant):
    hook, _, last = fresh(originals)
    outcome = last.extraction_correspondence.outcomes[0]
    if variant == "copied_claim":
        bad = replace(outcome, claim=replace(outcome.claim))
    elif variant == "forged_relations":
        bad = replace(outcome, relations=(("mouth_position", "mismatch"), *outcome.relations[1:]))
    elif variant == "future_publication":
        bad = replace(outcome, evaluated_tick=last.calculation.cutoff_tick + 1)
    elif variant == "future_sample":
        sample = outcome.samples[-1]
        future = last.calculation.cutoff_tick + 1
        bad = replace(outcome, samples=(*outcome.samples[:-1], replace(sample,
            feedback=replace(sample.feedback, available_tick=future),
            observation=replace(sample.observation, available_tick=future))))
    else:
        bad = replace(outcome, claim=replace(outcome.claim, targets=(replace(outcome.claim.targets[0]),)))
    before = state(hook)
    with pytest.raises((ValueError, TypeError)):
        offer(hook, last, outcomes=(bad,))
    assert state(hook) == before


@pytest.mark.parametrize("variant", ["stream", "generation", "seed"])
def test_foreign_source_or_generation_cannot_teach(originals, variant):
    _, first, last = originals["matched"]
    basis = first.extraction_correspondence.registration.application.projection.basis
    stream = basis.stream
    if variant == "stream":
        stream = MotorStreamRefV1("foreign", stream.generation)
    elif variant == "generation":
        stream = replace(stream, generation=stream.generation + 1)
    seed = replace(basis.seed, detail_region_id="foreign_detail") if variant == "seed" else basis.seed
    hook = SuckleExtractionLearningHookV1(stream, seed)
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last)
    assert state(hook) == before


def test_conflicting_replay_rejects_even_after_acceptance_and_history_eviction(originals):
    hook, _, last = fresh(originals, capacity=1)
    offer(hook, last)
    for i in range(1, 5):
        offer(hook, last, cycle_id=last.commitment.cycle_id + i, cutoff_tick=last.calculation.cutoff_tick + i)
    assert len(hook.history()) == 1 and hook.history()[0].status == "duplicate_ignored"
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, outcomes=(replace(last.extraction_correspondence.outcomes[0]),),
              cycle_id=last.commitment.cycle_id + 5, cutoff_tick=last.calculation.cutoff_tick + 5)
    assert state(hook) == before


def test_no_second_or_retroactive_registration_and_no_repeated_F(originals):
    hook, first, last = fresh(originals)
    with pytest.raises(RuntimeError):
        hook.reconcile(cycle_id=1, cutoff_tick=0)
    offer(hook, last)
    before = state(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=10, cutoff_tick=20, registration=first.extraction_correspondence.registration)
    assert state(hook) == before
    fresh_hook, _, _ = fresh(originals, register=False)
    with pytest.raises(ValueError):
        fresh_hook.reconcile(cycle_id=10, cutoff_tick=20, registration=first.extraction_correspondence.registration)
    assert not fresh_hook.pending()


def test_known_result_cannot_arrive_by_history_or_in_same_action_F(originals):
    hook, _, last = fresh(originals)
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, cycle_id=10, cutoff_tick=20)
    assert state(hook) == before
    empty, _, _ = fresh(originals, register=False)
    with pytest.raises(ValueError):
        offer(empty, last, cycle_id=1)
    assert not empty.pending()


@pytest.mark.parametrize("variant", ["copied_request", "copied_outcome", "admission", "request_id", "witness", "relations", "bad_distance"])
def test_altered_interpretation_dependencies_reject_before_commit(originals, variant):
    hook, _, last = fresh(originals, "mismatch")
    request = last.extraction_attention.created[0]
    interpretation = performed(last)
    if variant == "copied_request":
        interpretation = replace(interpretation, request=replace(request))
    elif variant == "copied_outcome":
        request = replace(request, outcome=replace(request.outcome))
    elif variant == "admission":
        request = replace(request, admitted_tick=request.admitted_tick + 1)
    elif variant == "request_id":
        request = replace(request, request_id="foreign")
    elif variant == "witness":
        witness = request.evidence[0]
        request = replace(request, evidence=(replace(witness, endpoint=replace(witness.endpoint)), *request.evidence[1:]))
    elif variant == "relations":
        request = replace(request, evidence=(request.evidence[0], request.evidence[0]))
    else:
        request = replace(request, evidence=(replace(request.evidence[0], displacement_metres=float("nan")), *request.evidence[1:]))
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, requests=(request,), interpretation=interpretation)
    assert state(hook) == before


@pytest.mark.parametrize("variant", ["old_cycle", "future_tick", "wrong_status", "wrong_relations", "no_WNM_id", "inaccessible_source"])
def test_only_actual_current_interpretation_is_usable(originals, variant):
    hook, _, last = fresh(originals, "mismatch")
    result = performed(last)
    if variant == "old_cycle":
        result = replace(result, cycle_id=result.cycle_id - 1)
    elif variant == "future_tick":
        result = replace(result, cutoff_tick=result.cutoff_tick + 1)
    elif variant == "wrong_status":
        result = replace(result, status="historical_resolved")
    elif variant == "wrong_relations":
        result = replace(result, relation_relevance=(("milk", "currently_supported"),))
    elif variant == "no_WNM_id":
        result = replace(result, working_id="")
    else:
        result = replace(result, current_source=replace(result.current_source, enabled=False))
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, interpretation=result)
    assert state(hook) == before


def test_request_and_interpretation_are_not_allowed_from_disabled_LE(originals):
    hook, _, last = fresh(originals, "mismatch")
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, attention_enabled=False)
    assert state(hook) == before


def test_no_dependency_invented_by_an_interpretation_alone(originals):
    hook, _, last = fresh(originals, "mismatch")
    before = state(hook)
    with pytest.raises(ValueError):
        offer(hook, last, requests=())
    assert state(hook) == before


def test_retained_LE_response_reference_is_not_reconsumed(originals):
    hook, _, last = fresh(originals, "mismatch")
    offer(hook, last)
    before = state(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=last.commitment.cycle_id + 1, cutoff_tick=last.calculation.cutoff_tick + 4,
                       interpretation=performed(last))
    assert state(hook) == before
    _, run = collect("mismatch")
    responses = [c for c in run.cycles if c.extraction_attention.allocation.kind == "response_reconsideration"]
    assert responses and all(not c.extraction_learning_report.dispositions for c in responses)


def test_actual_unknown_relevance_remains_pending_without_F_interpretation(originals):
    """Controlled current-source dropout with real L-E/Navigation interpretation."""
    hook, _, last = fresh(originals, "mismatch")
    source = replace(last.feeding_detail_source, oral_feedback=None)
    outcome = last.extraction_correspondence.outcomes[0]
    owner = SuckleExtractionAttentionV1(source.stream, source.seed)
    requests = owner.admit((outcome,), source, outcome.claim.application, cutoff_tick=source.cutoff_tick)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1(motor_preview_enabled=True)
    bid = attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    choice = attention.select((bid,), current_wnm=None, cycle_id=source.applied_cycle)
    working = navigation.update_wnm(choice)
    head = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    navigation.allocate_outcome_interpretation(working, (head,), cycle_id=source.applied_cycle, at_tick=source.cutoff_tick)
    allocation = owner.allocate(working, cycle_id=source.applied_cycle, grant=navigation.last_decision)
    assert allocation.interpretation.status == "unresolved_current_relevance"
    report = offer(hook, last, requests=requests, interpretation=allocation.interpretation)
    assert [d.status for d in report.dispositions] == ["pending_interpretation", "pending_unresolved_interpretation"]
    assert hook.pending()[0].expires_before_tick == 24
    expired = hook.reconcile(cycle_id=10, cutoff_tick=24)
    assert [d.status for d in expired.dispositions] == ["eligibility_expired"]


@pytest.mark.parametrize("reason", ["fault", "reset"])
def test_fault_and_generation_reset_permanently_close_old_hook(reason):
    trial = create_suckle_extraction_trial_v1(profile_for())
    trial.focal_step()
    old = trial.core.feeding_detail.extraction_learning_hook
    if reason == "reset":
        trial.reset()
        assert trial.core.feeding_detail.extraction_learning_hook is not old
        assert not trial.core.feeding_detail.extraction_learning_hook.pending()
    else:
        trial.core.stop("test_fault")
    assert not old.pending()
    with pytest.raises(RuntimeError):
        old.reconcile(cycle_id=2, cutoff_tick=4)


def test_cancellation_keeps_already_realized_evidence_without_reactivation():
    trial, run = collect("cancelled")
    outcomes = [r for c in run.cycles for r in c.extraction_correspondence.outcomes]
    assert outcomes and outcomes[0].status == "interrupted" and outcomes[0].command_ticks
    assert any(d.status == "accepted_no_update" for c in run.cycles for d in c.extraction_learning_report.dispositions)
    assert not trial.core.feeding_detail.extraction_learning_hook.pending()


@pytest.mark.parametrize("case", EXTRACTION_ATTENTION_CASES_V1)
def test_hook_ablation_preserves_every_cognitive_and_physical_effect(case):
    _, enabled = collect(case)
    off_trial, disabled = collect(case, hook=False)
    assert off_trial.core.feeding_detail.extraction_learning_hook is None
    assert enabled.local_steps == disabled.local_steps
    assert enabled.physical_samples == disabled.physical_samples
    assert enabled.installations == disabled.installations
    assert enabled.durable_before == enabled.durable_after == disabled.durable_after
    assert len(enabled.cycles) == len(disabled.cycles)
    for left, right in zip(enabled.cycles, disabled.cycles):
        normalized = replace(left, extraction_learning_report=None,
                             extraction_correspondence=replace(left.extraction_correspondence, learning_hook_enabled=False),
                             suckle_extraction=replace(left.suckle_extraction, participation_enabled=False))
        assert normalized == right
        assert left.extraction_learning_report.as_dict()["durable_learning_updates"] == 0


def test_diagnostic_capacity_does_not_change_functional_participation(originals):
    small, _, last = fresh(originals, capacity=1)
    large, _, _ = fresh(originals, capacity=8)
    assert offer(small, last) == offer(large, last)
    for i in range(1, 12):
        args = dict(cycle_id=last.commitment.cycle_id + i, cutoff_tick=last.calculation.cutoff_tick + i)
        assert offer(small, last, **args) == offer(large, last, **args)
    assert len(small.history()) == 1 and len(large.history()) == 8
    assert small.pending() == large.pending() == ()
    assert small._seen is large._seen
    json.dumps([d.as_dict() for d in large.history()], allow_nan=False)


def allocate_question(owner, source):
    """Perform the real existing Navigation grant for a controlled current source."""
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1(motor_preview_enabled=True)
    bid = attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    working = navigation.update_wnm(attention.select((bid,), current_wnm=None, cycle_id=source.applied_cycle))
    head = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    navigation.allocate_outcome_interpretation(working, (head,), cycle_id=source.applied_cycle, at_tick=source.cutoff_tick)
    return owner.allocate(working, cycle_id=source.applied_cycle, grant=navigation.last_decision).interpretation


def test_current_resolution_does_not_repair_historical_error(originals):
    """Counterfactual current-source control, not a claim of physically observed recovery."""
    hook, _, last = fresh(originals, "mismatch")
    _, control = collect("matched", hook=False)
    source = next(c.feeding_detail_source for c in control.cycles if c.calculation.cutoff_tick == last.calculation.cutoff_tick)
    outcome = last.extraction_correspondence.outcomes[0]
    original_relations = outcome.relations
    owner = SuckleExtractionAttentionV1(source.stream, source.seed)
    requests = owner.admit((outcome,), source, outcome.claim.application, cutoff_tick=source.cutoff_tick)
    interpretation = allocate_question(owner, source)
    assert interpretation.status == "historical_resolved"
    report = offer(hook, last, requests=requests, interpretation=interpretation)
    accepted = report.dispositions[-1]
    assert accepted.status == "accepted_no_update"
    assert ("sealed_contact", "mismatch") in accepted.accepted_relations
    assert outcome.relations == original_relations


def test_dependency_waits_for_later_actual_allocation_not_F_work(originals):
    """Controlled deferred allocation on real returned source samples and old evidence."""
    hook, _, last = fresh(originals, "mismatch")
    _, run = collect("mismatch", hook=False)
    outcome = last.extraction_correspondence.outcomes[0]
    source = last.feeding_detail_source
    owner = SuckleExtractionAttentionV1(source.stream, source.seed)
    requests = owner.admit((outcome,), source, outcome.claim.application, cutoff_tick=source.cutoff_tick)
    report = offer(hook, last, requests=requests, interpretation=None)
    assert [d.status for d in report.dispositions] == ["pending_interpretation"]
    dependency = hook.pending()[0].request
    later = next(c for c in run.cycles if c.calculation.cutoff_tick == source.cutoff_tick + 4)
    owner.admit((), later.feeding_detail_source, outcome.claim.application, cutoff_tick=later.calculation.cutoff_tick)
    interpretation = allocate_question(owner, later.feeding_detail_source)
    report = hook.reconcile(cycle_id=later.commitment.cycle_id, cutoff_tick=later.calculation.cutoff_tick, interpretation=interpretation)
    assert report.dispositions[-1].status == "accepted_no_update"
    assert interpretation.request is dependency and dependency is requests[0]
    assert dependency.expires_at_tick == outcome.evaluated_tick + 8


def test_real_interpretation_after_eligibility_can_be_valid_but_cannot_teach(originals):
    """Delayed-publication contract fixture, retaining real current-source samples."""
    hook, _, last = fresh(originals, "mismatch")
    _, run = collect("mismatch", hook=False)
    source = next(c.feeding_detail_source for c in run.cycles if c.calculation.cutoff_tick == 20)
    outcome = replace(last.extraction_correspondence.outcomes[0], evaluated_tick=20)
    owner = SuckleExtractionAttentionV1(source.stream, source.seed)
    requests = owner.admit((outcome,), source, outcome.claim.application, cutoff_tick=20)
    hook.reconcile(cycle_id=source.applied_cycle, cutoff_tick=20, outcomes=(outcome,), requests=requests)
    later = next(c.feeding_detail_source for c in run.cycles if c.calculation.cutoff_tick == 24)
    owner.admit((), later, outcome.claim.application, cutoff_tick=24)
    interpretation = allocate_question(owner, later)
    report = hook.reconcile(cycle_id=later.applied_cycle, cutoff_tick=24, interpretation=interpretation)
    assert interpretation.request.expires_at_tick == 28
    assert [d.status for d in report.dispositions] == ["eligibility_expired", "rejected_expired_interpretation"]
    assert not hook.pending()


@pytest.mark.parametrize("status", ["uninstalled_unresolved", "no_command_evidence", "observed_without_command", "execution_unknown_after_fault"])
def test_uninstalled_or_unknown_execution_never_teaches(originals, status):
    """Canonical no/unknown-execution contract fixtures, not extra live motor trials."""
    hook, _, last = fresh(originals)
    original = last.extraction_correspondence.outcomes[0]
    samples = original.samples if status in {"observed_without_command", "execution_unknown_after_fault"} else ()
    outcome = replace(original, status=status, installed=status != "uninstalled_unresolved", evaluated_tick=20,
                      command_ticks=original.command_ticks if status == "execution_unknown_after_fault" else (),
                      termination=None, samples=samples, confirmations=(),
                      relations=tuple((name, "unresolved_execution") for name, _ in original.relations))
    report = hook.reconcile(cycle_id=10, cutoff_tick=20, outcomes=(outcome,))
    assert [d.status for d in report.dispositions] == [f"rejected_{status}"]
    assert not report.dispositions[0].accepted_relations


def test_unknown_relations_are_not_promoted_but_measured_milk_survives(originals):
    """Paired-visual-product removal fixture preserves the original body acquisitions."""
    hook, _, last = fresh(originals)
    original = last.extraction_correspondence.outcomes[0]
    outcome = replace(original, samples=tuple(replace(s, observation=None) for s in original.samples),
                      relations=(("mouth_position", "matched"), ("detail_anchor", "unknown"),
                                 ("sealed_contact", "unknown"), ("finite_reciprocation", "matched")))
    report = offer(hook, last, outcomes=(outcome,))
    accepted, = report.dispositions
    assert accepted.status == "accepted_no_update"
    assert accepted.accepted_relations == (("mouth_position", "matched"), ("finite_reciprocation", "matched"))
    assert accepted.outcome.milk_evidence()["known_interval_sum"] == original.milk_evidence()["known_interval_sum"]
    assert accepted.outcome.milk_evidence()["original_detail_associated_event_ticks"] == []


def test_F_failure_prevents_outer_installation_and_closes_eligibility(monkeypatch):
    trial = create_suckle_extraction_trial_v1(profile_for())
    hook = trial.core.feeding_detail.extraction_learning_hook
    body = trial.observer_oral_extraction_body
    def fail(**_kwargs):
        raise ValueError("deliberate malformed F input")
    monkeypatch.setattr(hook, "reconcile", fail)
    with pytest.raises(ValueError):
        trial.focal_step()
    assert trial.tick == 0 and trial.observer_oral_extraction_body == body
    assert trial.stopped and hook._closed and not hook.pending()
    assert trial.handoff_consumptions == 0
    with pytest.raises(RuntimeError):
        trial.focal_step()
