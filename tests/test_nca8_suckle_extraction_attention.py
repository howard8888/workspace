"""L-E causal allocation tests; constructed historical/current variants are fixtures.

Live trials use the accepted physical provider and actual cognitive handoff. Three
simultaneous questions use independently produced original claims on a common
stream/seed for the allocation experiment, not simultaneous physical motor tasks.
"""
from dataclasses import replace
import itertools
import json

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from cca8_navmap_kernel import NavPointV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1, OutcomeInterpretationCandidateV1
from nca8_feeding import FeedingDetailCandidateV1, FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_runtime import Nca8RightingPreviewSessionV1
from nca8_seek_attention import SeekingOutcomeAttentionV1
from nca8_seek_nipple import SeekNippleIPV1
from nca8_suckle import SuckleIPV1, SuckleProfileV1
from nca8_suckle_attention import SuckleOutcomeAttentionV1
from nca8_suckle_extraction_attention import SuckleExtractionAttentionV1
from nca8_suckle_extraction_demo import create_suckle_extraction_trial_v1
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeRuntimeV1, validate_suckle_extraction_outcome_v1
from nca8_suckle_extraction_outcomes_demo import suckle_extraction_outcome_profile_v1, SUCKLE_EXTRACTION_OUTCOME_CASES_V1


def make_trial(case="body_shift", *, route=False, **flags):
    p = suckle_extraction_outcome_profile_v1(case)
    p = replace(p, latch=replace(p.latch, suckle=replace(p.latch.suckle, extraction_outcome_attention_enabled=route, **flags)))
    return create_suckle_extraction_trial_v1(p)


def advance(trial, ticks=4):
    return tuple(trial.advance_lower() for _ in range(ticks))


def material(case="body_shift"):
    trial = make_trial(case)
    first = trial.focal_step()
    initial = trial.latest_feedback
    advance(trial, 12)
    intervals = tuple(trial._suckle_intervals)
    cycle = trial.focal_step()
    return trial, first, cycle, cycle.extraction_correspondence.outcomes[0], initial, intervals


def owner_for(outcome, source, *, capacity=8):
    owner = SuckleExtractionAttentionV1(source.stream, source.seed, diagnostic_capacity=capacity)
    owner.admit((outcome,), source, outcome.claim.application, cutoff_tick=source.cutoff_tick)
    return owner


def nav_for(source):
    attention = AttentionRuntimeV1()
    navigation = NavigationRuntimeV1(motor_preview_enabled=True)
    bid = attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    choice = attention.select((bid,), current_wnm=None, cycle_id=source.applied_cycle)
    return navigation, navigation.update_wnm(choice), bid


def interpret(owner, source):
    navigation, working, _ = nav_for(source)
    head = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    navigation.allocate_outcome_interpretation(working, (head,), cycle_id=source.applied_cycle, at_tick=source.cutoff_tick)
    return owner.allocate(working, cycle_id=source.applied_cycle, grant=navigation.last_decision)


def state(owner):
    return (owner.pending(), owner.dispositions(), owner.retained_counts(), owner._dependency, owner._seen,
            owner._source, owner._application, owner._last_admission, owner._last_allocation_cycle, owner._closed)


@pytest.mark.parametrize("bad", [None, 0, 1, 0.0, "yes", [], {}])
def test_strict_default_off_flag(bad):
    assert SuckleProfileV1().extraction_outcome_attention_enabled is False
    with pytest.raises(TypeError):
        SuckleProfileV1(extraction_outcome_attention_enabled=bad)


def test_route_requires_LD_but_not_J_K_or_a_latch_task():
    with pytest.raises(ValueError):
        SuckleProfileV1(extraction_enabled=True, extraction_outcome_attention_enabled=True)
    trial = make_trial(route=True, outcomes_enabled=False, outcome_attention_enabled=False, learning_hook_enabled=False)
    trial.focal_step(); advance(trial, 12); cycle = trial.focal_step()
    assert trial.core.suckle.task is None
    assert trial.core.suckle_outcomes is None and trial.core.feeding_detail.suckle_outcome_attention is None
    assert trial.core.feeding_detail.suckle_learning_hook is None
    assert cycle.extraction_attention.allocation.kind == "interpretation"
    assert cycle.extraction_attention.created[0].outcome.claim.application is trial.core.suckle.extraction_assessment().application


@pytest.mark.parametrize("bad", [0, 9, True, None, 1.5, "1"])
def test_separate_diagnostic_bound(bad):
    with pytest.raises(ValueError):
        SuckleExtractionAttentionV1(MotorStreamRefV1("test", 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


def test_source_owns_once_configured_route_no_map_or_IP():
    source = FeedingDetailSourceV1(MotorStreamRefV1("test", 1), FeedingDetailProfileV1())
    before = source.durable_map.as_dict()
    source.configure_extraction_outcome_attention()
    assert isinstance(source.extraction_outcome_attention, SuckleExtractionAttentionV1)
    assert source.current is None and source.durable_map.as_dict() == before
    assert not hasattr(source.extraction_outcome_attention, "apply")
    with pytest.raises(RuntimeError): source.configure_extraction_outcome_attention()


def test_actual_publication_precedes_admission_not_history(monkeypatch):
    trial = make_trial(route=True)
    owner = trial.core.extraction_outcomes
    attention = trial.core.feeding_detail.extraction_outcome_attention
    original = owner.consume_intervals
    published = []
    def consume(*args, **kwargs):
        batch = original(*args, **kwargs); published.append(batch); return batch
    monkeypatch.setattr(owner, "consume_intervals", consume)
    actual = attention.admit
    def admitted(outcomes, *args, **kwargs):
        assert outcomes is published[-1]
        return actual(outcomes, *args, **kwargs)
    monkeypatch.setattr(attention, "admit", admitted)
    first = trial.focal_step(); advance(trial, 12); cycle = trial.focal_step()
    request, = cycle.extraction_attention.created
    result, = published[-1]
    assert request.outcome is result and result.claim is first.extraction_correspondence.registration
    assert dict(result.relations)["sealed_contact"] == "mismatch" and result.status == "interrupted"
    assert request.evidence[0].endpoint in result.samples
    assert request.expires_at_tick == result.evaluated_tick + 8
    assert cycle.extraction_attention.source_bid.source_map_state is cycle.feeding_detail_source
    assert cycle.extraction_attention.allocation.kind == "interpretation"
    assert cycle.status == "extraction_interpretation"
    assert cycle.extraction_correspondence.as_dict()["attention_route"] == "suckle_extraction_attention_v1"


@pytest.mark.parametrize("prior_competitor", [False, True])
def test_real_Attention_consequence_with_all_other_inputs_fixed(prior_competitor, monkeypatch):
    on, off = make_trial(route=True), make_trial(route=False)
    on.focal_step(); off.focal_step()
    assert advance(on) == advance(off)
    priority = (10, 70) if prior_competitor else None
    on.focal_step(visual_bid_priority=priority); off.focal_step(visual_bid_priority=priority)
    assert advance(on) == advance(off)
    bids = {}
    def capture(name, attention):
        original = attention.select
        def select(values, **kwargs): bids[name] = tuple(values); return original(values, **kwargs)
        monkeypatch.setattr(attention, "select", select)
    capture("on", on.core.cognition.attention); capture("off", off.core.cognition.attention)
    left = on.focal_step(visual_bid_priority=(10, 70)); right = off.focal_step(visual_bid_priority=(10, 70))
    assert left.feeding_detail_source == right.feeding_detail_source
    original_left, = left.extraction_correspondence.outcomes
    original_right, = right.extraction_correspondence.outcomes
    assert original_left == original_right
    a = next(b for b in bids["on"] if b.source_map_state.source_map_ref.map_id == "feeding_detail")
    b = next(b for b in bids["off"] if b.source_map_state.source_map_ref.map_id == "feeding_detail")
    assert replace(a, prediction_or_envelope_failure_rank=b.prediction_or_envelope_failure_rank, reasons=b.reasons) == b
    assert a.prediction_or_envelope_failure_rank == 40 and b.prediction_or_envelope_failure_rank == 0
    assert left.calculation.attention.selected_source_state.source_map_ref.map_id == "feeding_detail"
    assert right.calculation.attention.selected_source_state.source_map_ref.map_id != "feeding_detail"
    assert left.calculation.navigation.application is None and not left.reservations


@pytest.mark.parametrize("case", [c for c in SUCKLE_EXTRACTION_OUTCOME_CASES_V1 if c != "consumer_off"])
def test_all_existing_real_result_forms_validate_without_rescoring_history(case):
    p = suckle_extraction_outcome_profile_v1(case)
    from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
    trial = create_suckle_extraction_trial_v1(p)
    collect_seek_nipple_evidence_v1(trial, p.latch.run)
    for result in trial.core.extraction_outcomes.history():
        before = result.as_dict()
        validate_suckle_extraction_outcome_v1(result, stream=trial.latest_feedback.stream, cutoff_tick=trial.tick)
        assert result.as_dict() == before
        if case != "body_shift": assert not SuckleExtractionAttentionV1._significance(result)


@pytest.mark.parametrize("bad", ["status", "scores", "bool_install", "bool_comparison", "commands", "command_order", "samples",
                                  "confirmations", "end", "early_publication", "late_acquisition", "missing_claim", "wrong_stream"])
def test_malformed_original_result_rejects_atomically(bad):
    _, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source
    owner = SuckleExtractionAttentionV1(source.stream, source.seed)
    modified = result
    if bad == "status": modified = replace(result, status="matched")
    elif bad == "scores": modified = replace(result, relations=tuple((key, "matched") for key, _ in result.relations))
    elif bad == "bool_install": modified = replace(result, installed=1)
    elif bad == "bool_comparison": modified = replace(result, comparison_enabled=1)
    elif bad == "commands": modified = replace(result, command_ticks=(result.claim.due_tick,))
    elif bad == "command_order": modified = replace(result, command_ticks=(0, 0))
    elif bad == "samples": modified = replace(result, samples=(result.samples[0], result.samples[0]))
    elif bad == "confirmations": modified = replace(result, confirmations=(result.samples[-1].feedback,))
    elif bad == "end": modified = replace(result, end_tick=result.claim.due_tick + 1)
    elif bad == "early_publication": modified = replace(result, evaluated_tick=1)
    elif bad == "late_acquisition":
        item = result.samples[-1]
        sample = replace(item.feedback, available_tick=result.claim.last_acceptable_availability_tick + 1)
        modified = replace(result, samples=(*result.samples[:-1], replace(item, feedback=sample, observation=None)))
    elif bad == "missing_claim": modified = replace(result, claim=None)
    else: owner = SuckleExtractionAttentionV1(MotorStreamRefV1("wrong", 1), source.seed)
    before = state(owner)
    with pytest.raises((TypeError, ValueError)):
        owner.admit((modified,), source, result.claim.application, cutoff_tick=source.cutoff_tick)
    assert state(owner) == before


def test_original_application_not_latch_or_copy():
    _, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source
    for application in (None, replace(result.claim.application), object()):
        owner = SuckleExtractionAttentionV1(source.stream, source.seed)
        before = state(owner)
        with pytest.raises((TypeError, ValueError)):
            owner.admit((result,), source, application, cutoff_tick=source.cutoff_tick)
        assert state(owner) == before


def test_exact_replay_cannot_renew_but_conflicting_replay_rejects():
    trial, _, cycle, result, _, _ = material()
    owner = owner_for(result, cycle.feeding_detail_source)
    question, = owner.pending(); old_expiry = question.expires_at_tick
    advance(trial); later = trial.focal_step(); source = later.feeding_detail_source
    assert owner.admit((replace(result),), source, result.claim.application, cutoff_tick=16) == ()
    assert owner.pending()[0] is question and question.expires_at_tick == old_expiry
    advance(trial); last = trial.focal_step(); before = state(owner)
    # Changing comparison AND its canonical scores still produces a conflicting replay.
    changed = replace(result, comparison_enabled=False, relations=tuple((k, "comparison_disabled") for k, _ in result.relations))
    with pytest.raises(ValueError, match="conflicting"):
        owner.admit((changed,), last.feeding_detail_source, result.claim.application, cutoff_tick=20)
    assert state(owner) == before
    owner.admit((result,), last.feeding_detail_source, result.claim.application, cutoff_tick=20)
    assert not owner.pending() and (question.request_id, "expired_uninterpreted", 20) in owner.dispositions()


def test_first_admission_cannot_read_later_history():
    trial, _, _, result, _, _ = material()
    advance(trial); cycle = trial.focal_step()
    owner = SuckleExtractionAttentionV1(cycle.feeding_detail_source.stream, cycle.feeding_detail_source.seed)
    with pytest.raises(ValueError, match="publication"):
        owner.admit((result,), cycle.feeding_detail_source, result.claim.application, cutoff_tick=16)
    assert owner.pending() == () and owner._seen is None


@pytest.mark.parametrize("disposition", ["still_relevant", "historical_resolved", "unresolved_current_relevance"])
def test_same_historical_result_current_relevance_does_not_repair_history(disposition):
    _, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source
    if disposition == "historical_resolved":
        _, _, nominal, _, _, _ = material("nominal")
        source = nominal.feeding_detail_source
    elif disposition == "unresolved_current_relevance": source = replace(source, oral_feedback=None)
    owner = owner_for(result, source)
    before = json.dumps(result.as_dict(), sort_keys=True)
    allocation = interpret(owner, source)
    assert allocation.kind == "interpretation" and allocation.interpretation.status == disposition
    assert json.dumps(result.as_dict(), sort_keys=True) == before
    assert allocation.interpretation.request.outcome is result
    assert allocation.as_dict()["interpretation"]["grants_motor_permission"] is False


@pytest.mark.parametrize("distance,qualifies", [(.005, False), (.006, False), (.019, False), (.02, True), (.03, True)])
def test_geometry_mismatch_does_not_bypass_significance_through_seal(distance, qualifies):
    _, first, cycle, _, _, intervals = material("nominal")
    app = first.calculation.navigation.application
    altered = []
    for interval in intervals:
        observations = []
        for observation in interval.observations:
            detections = tuple(replace(d, position=NavPointV1(d.position.x + distance, d.position.y))
                               if d.region_id == app.projection.region_id else d for d in observation.detections)
            observations.append(replace(observation, detections=detections))
        altered.append(replace(interval, observations=tuple(observations)))
    reader = SuckleExtractionOutcomeRuntimeV1(app.projection.basis.stream)
    reader.consume_intervals((), cutoff_tick=0)
    claim = reader.register(app, first.calculation.proposal, tuple(r.current for r in first.reservations))
    reader.installed(claim, at_tick=0)
    result, = reader.consume_intervals(tuple(altered), cutoff_tick=12)
    owner = owner_for(result, cycle.feeding_detail_source)
    assert bool(owner.pending()) is qualifies
    assert all(sample.feedback.oral.contact and sample.feedback.oral_seal.sealed for sample in result.samples)
    if qualifies:
        witness, = owner.pending()[0].evidence
        assert witness.relation == "detail_anchor" and witness.displacement_metres == pytest.approx(distance)


def old_outcome(case):
    """Independent original seeking/latch claims with the common stream, not extra simultaneous tasks."""
    p = suckle_extraction_outcome_profile_v1("seek_then_latch" if case == "seeking" else "latch_then_extract")
    task = replace(p.latch.suckle, extraction_enabled=False, extraction_outcomes_enabled=False,
                   outcome_attention_enabled=False, learning_hook_enabled=False)
    seal = p.latch.seal if case == "seeking" else replace(p.latch.seal, sealable_surfaces=())
    seeking = replace(p.latch.run.seeking, outcome_attention_enabled=False, learning_hook_enabled=False)
    p = replace(p, latch=replace(p.latch, suckle=task, seal=seal, run=replace(p.latch.run, seeking=seeking)))
    trial = create_suckle_extraction_trial_v1(p)
    trial.focal_step(); advance(trial, 12)
    if case == "seeking":
        trial._seeking_intervals[:] = [replace(item, deliveries=tuple(
            replace(s, oral=replace(s.oral, extension_metres=s.oral.extension_metres + .01)) if s.event_tick == 8 else s
            for s in item.deliveries)) for item in trial._seeking_intervals]
    cycle = trial.focal_step()
    if case == "seeking": return cycle.seeking_correspondence.outcomes[0], cycle.seeking_task.task
    return cycle.suckle_correspondence.outcomes[0], cycle.suckle_task.task


def three_way(*, unknown=False):
    trial, first, cycle, result, initial, _ = material()
    source = replace(cycle.feeding_detail_source, oral_feedback=None) if unknown else cycle.feeding_detail_source
    cycle = replace(cycle, feeding_detail_source=source)
    extraction = owner_for(result, source)
    seek_result, seek_task = old_outcome("seeking")
    latch_result, latch_task = old_outcome("latch")
    seeking = SeekingOutcomeAttentionV1(source.stream, source.seed)
    latch = SuckleOutcomeAttentionV1(source.stream, source.seed)
    seeking.admit((seek_result,), source, seek_task, cutoff_tick=12)
    latch.admit((latch_result,), source, latch_task, cutoff_tick=12)
    assert all(owner.pending() for owner in (seeking, latch, extraction))
    session = Nca8RightingPreviewSessionV1(source.stream, visual_preview_enabled=True,
                                          additional_primitives=(trial.core.seek_nipple, trial.core.suckle))
    session.preview(initial, cutoff_tick=0)
    return trial, first, cycle, session, seeking, latch, extraction, seek_task, latch_task


def prepare_shared(session, trial, source, owners):
    bid = session.attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    for owner in owners: bid = owner.contribute_bid(bid)
    assert bid.prediction_or_envelope_failure_rank == 40
    return session.prepare_source(trial.latest_feedback, cutoff_tick=source.cutoff_tick, competing_bids=(bid,))


def test_three_real_questions_one_prior_grant_two_original_losers_then_later_winners(monkeypatch):
    trial, _, cycle, session, seeking, latch, extraction, seek_task, latch_task = three_way()
    owners = (seeking, latch, extraction)
    questions = tuple(o.pending()[0] for o in owners)
    original_app = extraction._application
    seen = []
    for name, owner in zip(("seeking", "latch", "extraction"), owners):
        original = owner.allocate
        def capture(*args, _owner=owner, _name=name, _original=original, **kwargs):
            if _owner.pending():
                grant = session.navigation.last_decision
                assert grant is not None and grant.application is None
                assert grant.reason == f"outcome_interpretation:{_owner.pending()[0].request_id}"
                seen.append(_name)
            return _original(*args, **kwargs)
        monkeypatch.setattr(owner, "allocate", capture)
    def forbidden(*args, **kwargs): pytest.fail("interpretation invoked an IP")
    source = cycle.feeding_detail_source
    for tick, winner in ((12, "extraction"), (16, "seeking"), (17, "latch")):
        if tick != 12:
            advance(trial, tick - trial.tick)
            # The donor's core has no L-E; current source is admitted without running a second interpretation in this session.
            cycle = trial.focal_step(); source = cycle.feeding_detail_source
            seeking.admit((), source, seek_task, cutoff_tick=tick)
            latch.admit((), source, latch_task, cutoff_tick=tick)
            extraction.admit((), source, original_app, cutoff_tick=tick)
        prepared = prepare_shared(session, trial, source, owners)
        before = tuple(o.pending() for o in owners)
        with monkeypatch.context() as guard:
            guard.setattr(SeekNippleIPV1, "apply", forbidden); guard.setattr(SuckleIPV1, "apply", forbidden)
            selection = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=latch, extraction_attention=extraction)
        allocations = (selection.seeking_outcome_allocation, selection.suckle_outcome_allocation, selection.extraction_outcome_allocation)
        assert sum(a.kind == "interpretation" for a in allocations) == 1
        index = ("seeking", "latch", "extraction").index(winner)
        assert allocations[index].kind == "interpretation"
        assert selection.navigation.application is None and selection.proposal is None
        for i, owner in enumerate(owners):
            if i != index:
                assert owner.pending() == before[i]
                if owner.pending(): assert owner.pending()[0] is questions[i] and questions[i].expires_at_tick == 20
        session.project_selected(selection)
    assert seen == ["extraction", "seeking", "latch"]  # Only each winner ran, after its prior exact grant.
    assert all(not o.pending() for o in owners)


@pytest.mark.parametrize("order", list(itertools.permutations(range(3))))
def test_all_six_candidate_orders_use_same_existing_Navigation_policy(order):
    _, _, cycle, _, seeking, latch, extraction, _, _ = three_way()
    nav, working, _ = nav_for(cycle.feeding_detail_source)
    owners = (seeking, latch, extraction)
    heads = tuple(o.interpretation_candidate(working, cycle_id=cycle.commitment.cycle_id) for o in owners)
    before = tuple(state(o) if isinstance(o, SuckleExtractionAttentionV1) else o.pending() for o in owners)
    winner = nav.allocate_outcome_interpretation(working, tuple(heads[i] for i in order), cycle_id=cycle.commitment.cycle_id, at_tick=12)
    assert winner is heads[2]  # Stable lexical tie, not registration order.
    assert before == tuple(state(o) if isinstance(o, SuckleExtractionAttentionV1) else o.pending() for o in owners)


@pytest.mark.parametrize("oldest", [0, 1, 2])
def test_original_admission_precedes_identity_tie_and_four_heads_reject(oldest):
    _, _, cycle, _, _, _ = material()
    source = cycle.feeding_detail_source
    nav, working, _ = nav_for(source)
    heads = tuple(OutcomeInterpretationCandidateV1(f"question:{i}", source, 10 if i == oldest else 12, 18 if i == oldest else 20) for i in range(3))
    with pytest.raises(ValueError):
        nav.allocate_outcome_interpretation(working, (*heads, replace(heads[0], request_id="fourth")), cycle_id=source.applied_cycle, at_tick=12)
    assert nav.last_decision is None
    assert nav.allocate_outcome_interpretation(working, heads, cycle_id=source.applied_cycle, at_tick=12) is heads[oldest]


@pytest.mark.parametrize("defect", ["no_grant", "wrong_reason", "copied_WNM", "primitive"])
def test_bad_grant_cannot_consume(defect):
    _, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source; owner = owner_for(result, source)
    nav, working, _ = nav_for(source)
    head = owner.interpretation_candidate(working, cycle_id=source.applied_cycle)
    nav.allocate_outcome_interpretation(working, (head,), cycle_id=source.applied_cycle, at_tick=12)
    grant = nav.last_decision
    if defect == "no_grant": grant = None
    elif defect == "wrong_reason": grant = replace(grant, reason="other_question")
    elif defect == "copied_WNM": grant = replace(grant, wnm=replace(working))
    before = state(owner)
    with pytest.raises((ValueError, TypeError)):
        if defect == "primitive": grant = replace(grant, application=result.claim.application)  # Existing grant guard rejects first.
        owner.allocate(working, cycle_id=source.applied_cycle, grant=grant)
    assert state(owner) == before


def test_historical_question_independent_of_motor_and_episode_but_never_renews():
    trial, _, cycle, result, _, _ = material()
    owner = owner_for(result, cycle.feeding_detail_source)
    request, = owner.pending()
    assert result.claim.due_tick <= request.admitted_tick < request.expires_at_tick
    target_before = result.claim.targets[0].as_dict()
    interpret(owner, cycle.feeding_detail_source)
    advance(trial); cycle = trial.focal_step()
    owner.admit((), cycle.feeding_detail_source, result.claim.application, cutoff_tick=16)
    nav, working, _ = nav_for(cycle.feeding_detail_source)
    assert owner.allocate(working, cycle_id=cycle.commitment.cycle_id).kind == "response_reconsideration"
    assert result.claim.targets[0].as_dict() == target_before and trial.core.suckle.extraction_assessment().application is result.claim.application
    assert cycle.calculation.navigation.application is None  # One-contribution scope remains closed.


def test_unknown_dependency_is_one_bounded_hold_without_reinterpretation(monkeypatch):
    trial, _, cycle, result, _, _ = material()
    source = replace(cycle.feeding_detail_source, oral_feedback=None)
    owner = owner_for(result, source)
    assert interpret(owner, source).interpretation.status == "unresolved_current_relevance"
    for tick in (16, 20):
        advance(trial, tick - trial.tick); cycle = trial.focal_step()
        current = replace(cycle.feeding_detail_source, oral_feedback=None)
        owner.admit((), current, result.claim.application, cutoff_tick=tick)
        nav, working, _ = nav_for(current)
        monkeypatch.setattr(owner, "_relevance", lambda *args: pytest.fail("dependency cannot reinterpret"))
        a = owner.allocate(working, cycle_id=current.applied_cycle)
        assert a.kind == ("dependent_unresolved" if tick == 16 else "ordinary")


def test_closed_reset_and_read_only_diagnostics():
    trial, _, cycle, result, _, _ = material()
    owner = owner_for(result, cycle.feeding_detail_source, capacity=1)
    before = state(owner)
    for _ in range(20):
        owner.pending()[0].as_dict(); owner.dispositions(); owner.retained_counts()
    assert state(owner) == before
    owner.close()
    assert not owner.pending()
    with pytest.raises(ValueError): owner.admit((), cycle.feeding_detail_source, result.claim.application, cutoff_tick=16)
    with pytest.raises(RuntimeError): owner.contribute_bid(None)
    trial.reset()
    assert trial.core.suckle.task is None
    assert trial.core.extraction_outcomes.history() == ()


def test_three_unresolved_dependencies_impose_one_hold_no_reinterpretation(monkeypatch):
    trial, _, cycle, session, seeking, latch, extraction, seek_task, latch_task = three_way(unknown=True)
    owners = (seeking, latch, extraction)
    source = cycle.feeding_detail_source
    original_app = extraction._application
    for tick in (12, 16, 17, 18):
        if tick != 12:
            advance(trial, tick - trial.tick)
            cycle = trial.focal_step(); source = replace(cycle.feeding_detail_source, oral_feedback=None)
            seeking.admit((), source, seek_task, cutoff_tick=tick)
            latch.admit((), source, latch_task, cutoff_tick=tick)
            extraction.admit((), source, original_app, cutoff_tick=tick)
        prepared = prepare_shared(session, trial, source, owners) if tick != 18 else session.prepare_source(
            trial.latest_feedback, cutoff_tick=tick, competing_bids=(session.attention.build_bid(
                FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle),))
        with monkeypatch.context() as guard:
            def forbidden(*args, **kwargs): pytest.fail("dependency hold performed new demanding work")
            guard.setattr(SeekNippleIPV1, "apply", forbidden); guard.setattr(SuckleIPV1, "apply", forbidden)
            if tick == 18:
                for owner in owners: guard.setattr(owner, "_relevance", forbidden)
            selected = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=latch, extraction_attention=extraction)
        allocations = (selected.seeking_outcome_allocation, selected.suckle_outcome_allocation, selected.extraction_outcome_allocation)
        if tick == 18:
            assert selected.navigation.reason == "feeding_dependent_unresolved"
            assert all(a.kind == "dependent_unresolved" for a in allocations)
            assert selected.navigation.application is None
        else:
            performed = [a for a in allocations if a.kind == "interpretation"]
            assert len(performed) == 1 and performed[0].interpretation.status == "unresolved_current_relevance"
        session.project_selected(selected)


def test_disabled_Navigation_keeps_all_questions_unconsumed(monkeypatch):
    trial, _, cycle, session, seeking, latch, extraction, _, _ = three_way()
    owners = (seeking, latch, extraction)
    prepared = prepare_shared(session, trial, cycle.feeding_detail_source, owners)
    before = tuple(o.pending() for o in owners)
    monkeypatch.setattr(session.navigation, "_enabled", False)
    for owner in owners:
        monkeypatch.setattr(owner, "allocate", lambda *a, **kw: pytest.fail("disabled Navigation invoked a consumer"))
    result = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=latch, extraction_attention=extraction)
    assert result.navigation.application is None
    assert all(a.kind == "navigation_disabled" for a in (result.seeking_outcome_allocation, result.suckle_outcome_allocation, result.extraction_outcome_allocation))
    assert tuple(o.pending() for o in owners) == before


@pytest.mark.parametrize("defect", ["list", "two_results", "wrong_seed", "future_source", "foreign_original", "backward_cutoff", "bool_tick"])
def test_whole_admission_validates_before_mutation(defect):
    trial, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source; owner = owner_for(result, source)
    advance(trial); later = trial.focal_step(); source = later.feeding_detail_source
    inputs, original, cutoff = (), result.claim.application, 16
    if defect == "list": inputs = []
    elif defect == "two_results": inputs = (result, result)
    elif defect == "wrong_seed": owner = SuckleExtractionAttentionV1(source.stream, replace(source.seed, detail_region_id="other"))
    elif defect == "future_source": cutoff = 17
    elif defect == "foreign_original": original = replace(result.claim.application)
    elif defect == "backward_cutoff": cutoff = 11
    elif defect == "bool_tick": cutoff = True
    before = state(owner)
    with pytest.raises((ValueError, TypeError)):
        owner.admit(inputs, source, original, cutoff_tick=cutoff)
    assert state(owner) == before


@pytest.mark.parametrize("enabled", [(True, False, False), (False, True, False), (False, False, True),
                                     (True, True, False), (True, False, True), (False, True, True)])
def test_optional_owner_combinations_keep_one_existing_focal_allocation(enabled, monkeypatch):
    trial, _, cycle, session, seeking, latch, extraction, _, _ = three_way()
    owners = tuple(owner if active else None for owner, active in zip((seeking, latch, extraction), enabled))
    prepared = prepare_shared(session, trial, cycle.feeding_detail_source, tuple(o for o in owners if o is not None))
    before = tuple(o.pending() for o in owners if o is not None)
    def forbidden(*args, **kwargs): pytest.fail("an interpretation called a task IP")
    monkeypatch.setattr(SeekNippleIPV1, "apply", forbidden); monkeypatch.setattr(SuckleIPV1, "apply", forbidden)
    result = session.select_prepared(prepared, seeking_attention=owners[0], suckle_attention=owners[1], extraction_attention=owners[2])
    allocations = (result.seeking_outcome_allocation, result.suckle_outcome_allocation, result.extraction_outcome_allocation)
    assert sum(a is not None and a.kind == "interpretation" for a in allocations) == 1
    assert result.navigation.application is None
    after = tuple(o.pending() for o in owners if o is not None)
    assert sum(len(b) - len(a) for b, a in zip(before, after)) == 1
    for b, a in zip(before, after):
        if a: assert a[0] is b[0] and a[0].expires_at_tick == 20


@pytest.mark.parametrize("kind", ["part_category", "parent_category", "parent_geometry", "unknown_part"])
def test_part_relation_significance_retains_actual_witness_not_milk(kind):
    _, first, cycle, _, _, intervals = material("nominal")
    app = first.calculation.navigation.application
    altered = []
    for interval in intervals:
        observations = []
        for observation in interval.observations:
            detections = []
            for detection in observation.detections:
                if detection.region_id == app.projection.region_id and kind in {"part_category", "unknown_part"}:
                    detection = replace(detection, descriptor="object" if kind == "part_category" else None)
                elif detection.region_id == app.projection.basis.seed.parent_region_id:
                    if kind == "parent_category": detection = replace(detection, descriptor="feeding")
                    elif kind == "parent_geometry": detection = replace(detection, position=NavPointV1(1., 0.))
                detections.append(detection)
            observations.append(replace(observation, detections=tuple(detections)))
        altered.append(replace(interval, observations=tuple(observations)))
    reader = SuckleExtractionOutcomeRuntimeV1(app.projection.basis.stream)
    reader.consume_intervals((), cutoff_tick=0)
    claim = reader.register(app, first.calculation.proposal, tuple(r.current for r in first.reservations))
    reader.installed(claim, at_tick=0)
    result, = reader.consume_intervals(tuple(altered), cutoff_tick=12)
    owner = owner_for(result, cycle.feeding_detail_source)
    assert bool(owner.pending()) == (kind != "unknown_part")
    if owner.pending():
        witness, = owner.pending()[0].evidence
        assert witness.reason == "part_context_contradicted" and witness.endpoint in result.samples
        assert witness.displacement_metres is None
    assert result.milk_evidence()["known_interval_sum"] == pytest.approx(.2)


def test_existing_larger_bid_rank_is_not_reduced_or_added():
    _, _, cycle, result, _, _ = material()
    source = cycle.feeding_detail_source; owner = owner_for(result, source)
    nav, _, _ = nav_for(source)
    attention = AttentionRuntimeV1()
    bid = attention.build_bid(FeedingDetailCandidateV1(source, 0), cycle_id=source.applied_cycle)
    high = replace(bid, prediction_or_envelope_failure_rank=70)
    changed = owner.contribute_bid(high)
    assert changed.prediction_or_envelope_failure_rank == 70
    assert replace(changed, reasons=high.reasons) == high
    assert owner.contribute_bid(None) is None
