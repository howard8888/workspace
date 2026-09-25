"""Sequential M origins are real live claims unless a test explicitly says fixture.

The separate reader/hook instances below exercise transactions against those
originals. Re-offering an acquisition is an explicit transport replay control,
not a new physical event or a new episode. No observer result chooses live actions.
"""
from copy import deepcopy
from dataclasses import replace
from functools import lru_cache

import pytest

from cca8_motor_contracts import FeedingDeficitFeedbackV1, MotorStreamRefV1
from cca8_support_world import PlanarPerturbationV1
from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1, OutcomeInterpretationCandidateV1
from nca8_feeding import FeedingDetailCandidateV1
from nca8_suckle_extraction_attention import SuckleExtractionAttentionV1
from nca8_suckle_extraction_learning import SuckleExtractionLearningHookV1
from nca8_suckle_extraction_outcomes import SuckleExtractionOutcomeRuntimeV1
from nca8_sustained_feeding_demo import create_sustained_feeding_trial_v1, run_sustained_feeding_v1, sustained_feeding_profile_v1


def advance(trial, count):
    for _ in range(count):
        trial.advance_lower()


@lru_cache(None)
def original_run(case="already_sealed"):
    return run_sustained_feeding_v1(case)


def frames(result):
    return tuple(c for c in result.run.cycles if c.extraction_correspondence.registration is not None)


def fresh_hook(result, *, capacity=8):
    first = frames(result)[0]
    claim = first.extraction_correspondence.registration
    hook = SuckleExtractionLearningHookV1(claim.application.contribution.origin.stream,
                                         claim.application.projection.basis.seed, sequential=True, diagnostic_capacity=capacity)
    hook.reconcile(cycle_id=first.commitment.cycle_id, cutoff_tick=claim.start_tick, registration=claim)
    return hook


def offer(hook, cycle, **changes):
    frame = cycle.extraction_attention
    args = dict(cycle_id=cycle.commitment.cycle_id, cutoff_tick=cycle.calculation.cutoff_tick,
                registration=cycle.extraction_correspondence.registration,
                outcomes=cycle.extraction_correspondence.outcomes, requests=frame.created if frame else (),
                interpretation=frame.allocation.interpretation if frame and frame.allocation.kind == "interpretation" else None)
    args.update(changes)
    return hook.reconcile(**args)


def reader_at_second_application():
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    first = trial.focal_step()
    advance(trial, 12)
    second = trial.focal_step()
    return trial, first, second


@pytest.mark.parametrize("cls", [SuckleExtractionOutcomeRuntimeV1, SuckleExtractionAttentionV1, SuckleExtractionLearningHookV1])
@pytest.mark.parametrize("bad", [None, 0, 1, "True", []])
def test_sequential_option_is_strict_boolean(cls, bad):
    claim = frames(original_run())[0].extraction_correspondence.registration
    args = (claim.application.contribution.origin.stream,)
    if cls is not SuckleExtractionOutcomeRuntimeV1:
        args += (claim.application.projection.basis.seed,)
    with pytest.raises(TypeError):
        cls(*args, sequential=bad)


def test_same_F_reconciles_old_A_and_registers_new_B_before_B_installation(monkeypatch):
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    hook, reader = trial.core.feeding_detail.extraction_learning_hook, trial.core.extraction_outcomes
    original = hook.reconcile
    snapshots = []
    def reconcile(**kwargs):
        result = original(**kwargs)
        registration = kwargs.get("registration")
        if registration is not None:
            assert reader.pending() is registration and not reader._evidence.installed
            assert result.new_participation.claim is registration
            assert all(outcome.claim is not registration for outcome in kwargs["outcomes"])
            snapshots.append((registration, kwargs["outcomes"], result))
        return result
    monkeypatch.setattr(hook, "reconcile", reconcile)
    trial.focal_step()
    for _ in range(6):
        advance(trial, 4)
        trial.focal_step()
    assert len(snapshots) == 3
    for previous, current in zip(snapshots, snapshots[1:]):
        claim, outcomes, report = current
        assert len(outcomes) == 1 and outcomes[0].claim is previous[0]
        assert report.dispositions[-1].outcome is outcomes[0]
        assert report.new_participation.expires_before_tick == claim.start_tick + 24
        assert report.dispositions[-1].status == "accepted_no_update"


def test_new_originals_preserve_every_old_PNM_body_basis_and_independent_clock():
    result = original_run()
    applications, outcomes = result.applications(), result.outcomes()
    registrations = tuple(c.extraction_correspondence.registration for c in frames(result))
    for application, claim, outcome in zip(applications, registrations, outcomes):
        assert outcome.claim is claim and claim.application is application
        assert claim.targets[0].target.basis is application.projection.basis.oral_feedback
        assert claim.due_tick == claim.start_tick + 8
        assert claim.last_acceptable_availability_tick == claim.due_tick + 8
        assert application.projection.pnm.pnm_id == f"pnm:{application.application_id}"
        assert all(claim.start_tick < sample.feedback.event_tick <= outcome.end_tick for sample in outcome.samples)
    assert len({id(a.projection.pnm) for a in applications}) == 3
    assert [o.claim.start_tick for o in outcomes] == [0, 12, 24]
    assert all(o.milk_evidence()["exact_observed_total"] == pytest.approx(.2) for o in outcomes)


def test_historical_A_acquisition_arriving_while_B_pending_does_not_become_B():
    trial, _, second = reader_at_second_application()
    reader = trial.core.extraction_outcomes
    old = reader.history()[0]
    endpoint = old.samples[1]
    archived = deepcopy(reader._past_evidence[old.claim.application.application_id])
    advance(trial, 4)
    intervals = list(trial._suckle_intervals)
    first = intervals[0]
    intervals[0] = replace(first, deliveries=(*first.deliveries, endpoint.feedback),
                           observations=(*first.observations, endpoint.observation))
    assert reader.consume_intervals(tuple(intervals), cutoff_tick=16) == ()
    assert reader.history() == (old,) and reader.history()[0] is old
    assert reader.pending() is second.extraction_correspondence.registration
    assert all(item.feedback.event_tick > 12 for item in reader._evidence.samples)
    assert reader._past_evidence[old.claim.application.application_id] == archived
    assert old.milk_evidence()["exact_observed_total"] == pytest.approx(.2)


@pytest.mark.parametrize("corruption", ["changed_A", "foreign_stream", "noncontiguous", "copied_target"])
def test_sequential_reader_rejects_entire_batch_before_mutating_B_or_A(corruption):
    trial, _, _ = reader_at_second_application()
    reader = trial.core.extraction_outcomes
    old = reader.history()[0]
    advance(trial, 4)
    intervals = list(trial._suckle_intervals)
    before = deepcopy(vars(reader))
    if corruption == "noncontiguous":
        intervals = intervals[1:]
    elif corruption == "copied_target":
        first = intervals[0]
        report = next(r for r in first.reports if r.committed_target.target.origin.application_id == reader.pending().application.application_id)
        intervals[0] = replace(first, reports=(replace(report, committed_target=replace(report.committed_target)),))
    else:
        endpoint = old.samples[1]
        sample = replace(endpoint.feedback, feeding_deficit=FeedingDeficitFeedbackV1(.8)) if corruption == "changed_A" else replace(
            endpoint.feedback, stream=MotorStreamRefV1("foreign", 1))
        # No paired visual product is supplied for this explicitly malformed replay.
        intervals[0] = replace(intervals[0], deliveries=(*intervals[0].deliveries, sample))
    with pytest.raises((ValueError, TypeError)):
        reader.consume_intervals(tuple(intervals), cutoff_tick=16)
    assert vars(reader) == before


@pytest.mark.parametrize("corruption", ["future_B_cycle", "copied_A_claim", "wrong_A_relations", "old_A_publication", "duplicate_B"])
def test_A_outcome_and_B_registration_are_one_atomic_F_transaction(corruption):
    result = original_run()
    hook = fresh_hook(result)
    a, b = frames(result)[:2]
    registration = b.extraction_correspondence.registration
    outcome = b.extraction_correspondence.outcomes[0]
    options = {}
    if corruption == "future_B_cycle":
        options["cycle_id"] = b.commitment.cycle_id + 1
    elif corruption == "copied_A_claim":
        options["outcomes"] = (replace(outcome, claim=replace(outcome.claim)),)
    elif corruption == "wrong_A_relations":
        options["outcomes"] = (replace(outcome, relations=(("mouth_position", "mismatch"), *outcome.relations[1:])),)
    elif corruption == "old_A_publication":
        options.update(cycle_id=b.commitment.cycle_id+1, cutoff_tick=b.calculation.cutoff_tick+1, registration=None)
    else:
        options["registration"] = a.extraction_correspondence.registration
    before = deepcopy(vars(hook))
    with pytest.raises((ValueError, RuntimeError)):
        offer(hook, b, **options)
    assert vars(hook) == before
    valid = offer(hook, b)
    assert valid.new_participation.claim is registration
    assert valid.dispositions[-1].outcome is outcome
    assert valid.dispositions[-1].status == "accepted_no_update"


def test_replayed_A_after_new_B_never_extends_or_duplicates_either_participant():
    result = original_run()
    hook = fresh_hook(result)
    second = frames(result)[1]
    report = offer(hook, second)
    b = report.new_participation
    a = second.extraction_correspondence.outcomes[0]
    replay = hook.reconcile(cycle_id=second.commitment.cycle_id+1, cutoff_tick=13, outcomes=(a,))
    assert replay.pending == (b,) and replay.new_participation is None
    assert replay.dispositions[-1].status == "duplicate_ignored"
    assert b.expires_before_tick == 36
    for state in hook._origins.values():
        if state.registration is a.claim:
            assert state.participant is None and state.seen is a


def test_no_registration_is_invented_when_B_result_arrives_after_registered_A():
    result = original_run()
    hook = fresh_hook(result)
    a, b = result.outcomes()[:2]
    hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(a,))
    report = hook.reconcile(cycle_id=7, cutoff_tick=24, outcomes=(b,))
    assert report.new_participation is None and report.pending == ()
    assert report.dispositions[-1].status == "rejected_unregistered_operation"
    assert hook.retained_counts()["extraction_learning_registrations"] == 1
    assert hook.retained_counts()["extraction_learning_originals"] == 2  # replay guard, not participation


def test_valid_delayed_A_can_outlive_eligibility_while_B_registers_at_same_F():
    trial = create_sustained_feeding_trial_v1(sustained_feeding_profile_v1("already_sealed"))
    trial.focal_step()
    advance(trial, 8)
    first = trial.focal_step()
    assert first.extraction_correspondence.outcomes == ()
    advance(trial, 16)
    later = trial.focal_step()
    assert later.calculation.cutoff_tick == 24
    result, = later.extraction_correspondence.outcomes
    new = later.extraction_correspondence.registration
    assert result.claim.start_tick == 0 and new.start_tick == 24
    report = later.extraction_learning_report
    assert [d.status for d in report.dispositions] == ["eligibility_expired", "rejected_expired_eligibility"]
    assert report.new_participation.claim is new and report.new_participation.expires_before_tick == 48
    assert result.status == "local_sequence_observed"


def test_first_and_second_LF_eligibility_expire_at_their_own_times():
    result = original_run()
    hook = fresh_hook(result)
    second = frames(result)[1]
    # This source-local harness deliberately withholds A's result from F.
    offer(hook, second, outcomes=())
    a, b = hook.pending()
    assert (a.expires_before_tick, b.expires_before_tick) == (24, 36)
    at24 = hook.reconcile(cycle_id=7, cutoff_tick=24)
    assert [d.pnm_id for d in at24.dispositions] == [a.claim.application.projection.pnm.pnm_id]
    assert at24.pending == (b,)
    at36 = hook.reconcile(cycle_id=10, cutoff_tick=36)
    assert [d.pnm_id for d in at36.dispositions] == [b.claim.application.projection.pnm.pnm_id]
    assert at36.pending == ()


def test_second_contribution_mismatch_belongs_to_B_not_previously_matched_A():
    p = sustained_feeding_profile_v1("already_sealed")
    run = p.extraction.latch.run
    run = replace(run, planar=replace(run.planar, perturbations=(PlanarPerturbationV1(13, 15, velocity=(.1, 0)),)))
    p = replace(p, extraction=replace(p.extraction, latch=replace(p.extraction.latch, run=run)))
    trial = create_sustained_feeding_trial_v1(p)
    cycles = [trial.focal_step()]
    for _ in range(8):
        advance(trial, 4)
        cycles.append(trial.focal_step())
    reader = trial.core.extraction_outcomes
    a, b = reader.history()
    assert all(value == "matched" for _, value in a.relations)
    assert b.claim.application.task.applications == 2 and b.status == "interrupted"
    questions = [q for c in cycles for q in c.extraction_attention.created]
    assert len(questions) == 1 and questions[0].outcome is b
    actual = [c.extraction_attention.allocation.interpretation for c in cycles if c.extraction_attention.allocation.kind == "interpretation"]
    assert len(actual) == 1 and actual[0].request is questions[0]
    accepted = [d for c in cycles for d in c.extraction_learning_report.dispositions if d.status == "accepted_no_update"]
    assert len(accepted) == 2 and accepted[0].outcome is a and accepted[1].outcome is b
    assert dict(accepted[1].accepted_relations)["sealed_contact"] == "mismatch"


def test_capacity_and_diagnostics_do_not_evict_originals_or_resurrect_eligibility():
    result = original_run("uptake_off")
    one = fresh_hook(result, capacity=1)
    eight = fresh_hook(result, capacity=8)
    for cycle in result.run.cycles[1:]:
        left = offer(one, cycle)
        right = offer(eight, cycle)
        assert left == right
    assert one._origins == eight._origins and len(one._origins) == 8
    assert len(one.history()) == 1 and len(eight.history()) == 8
    first = frames(result)[0].extraction_correspondence.registration
    before = deepcopy(vars(one))
    with pytest.raises((ValueError, RuntimeError)):
        one.reconcile(cycle_id=100, cutoff_tick=140, registration=first)
    assert vars(one) == before


def test_reader_refuses_ninth_registration_without_eviction_even_with_ended_claim():
    p = sustained_feeding_profile_v1("uptake_off")
    trial = create_sustained_feeding_trial_v1(p)
    saved = []
    for tick in range(101):
        if tick % 4 == 0:
            cycle = trial.focal_step()
            if cycle.extraction_correspondence.registration:
                saved.append(cycle)
        if tick < 100:
            trial.advance_lower()
    reader = trial.core.extraction_outcomes
    assert reader.pending() is None and len(reader.history()) == len(reader._claims) == 8
    first = saved[0]
    before = deepcopy(vars(reader))
    with pytest.raises(OverflowError):
        reader.register(first.calculation.navigation.application, first.calculation.proposal, first.extraction_correspondence.registration.targets)
    assert vars(reader) == before


def test_LE_replay_of_A_with_latest_B_preserves_both_originals_and_watermark():
    result = original_run()
    a_cycle, b_cycle = frames(result)[:2]
    a = a_cycle.extraction_correspondence.registration.application
    b = b_cycle.extraction_correspondence.registration.application
    owner = SuckleExtractionAttentionV1(a.contribution.origin.stream, a.projection.basis.seed, sequential=True)
    owner.admit((), a_cycle.feeding_detail_source, a, cutoff_tick=0)
    old_outcome = b_cycle.extraction_correspondence.outcomes[0]
    owner.admit((old_outcome,), b_cycle.feeding_detail_source, b, cutoff_tick=12)
    c = next(c for c in result.run.cycles if c.calculation.cutoff_tick == 16)
    assert owner.admit((old_outcome,), c.feeding_detail_source, b, cutoff_tick=16) == ()
    assert owner._application is b and owner._outcomes[a.application_id] is old_outcome
    assert len(owner._applications) == 2 and owner.pending() == ()


def test_LE_rejects_backwards_application_watermark_before_partial_admission():
    result = original_run()
    first, second = frames(result)[:2]
    a = first.extraction_correspondence.registration.application
    b = second.extraction_correspondence.registration.application
    owner = SuckleExtractionAttentionV1(a.contribution.origin.stream, a.projection.basis.seed, sequential=True)
    owner.admit((), first.feeding_detail_source, a, cutoff_tick=0)
    owner.admit(second.extraction_correspondence.outcomes, second.feeding_detail_source, b, cutoff_tick=12)
    later = next(c for c in result.run.cycles if c.calculation.cutoff_tick == 16)
    before = deepcopy(vars(owner))
    with pytest.raises(ValueError):
        owner.admit((), later.feeding_detail_source, a, cutoff_tick=16)
    assert vars(owner) == before


@pytest.mark.parametrize("route", ["LE_registration", "LF_registration", "LF_unregistered_outcome"])
def test_original_episode_start_cannot_drift_across_sequential_owners(route):
    """A later original may not silently rewrite the first episode's cycle basis."""
    result = original_run()
    first, second = frames(result)[:2]
    a = first.extraction_correspondence.registration
    b = second.extraction_correspondence.registration
    altered_application = replace(b.application, task=replace(b.application.task, started_cycle=2))
    altered_claim = replace(b, application=altered_application)
    if route == "LE_registration":
        owner = SuckleExtractionAttentionV1(a.application.contribution.origin.stream, a.application.projection.basis.seed,
                                           sequential=True)
        owner.admit((), first.feeding_detail_source, a.application, cutoff_tick=0)
        before = deepcopy(vars(owner))
        with pytest.raises(ValueError):
            owner.admit(second.extraction_correspondence.outcomes, second.feeding_detail_source,
                        altered_application, cutoff_tick=12)
    elif route == "LF_registration":
        owner = fresh_hook(result)
        before = deepcopy(vars(owner))
        with pytest.raises(ValueError):
            offer(owner, second, registration=altered_claim)
    else:
        owner = fresh_hook(result)
        owner.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(result.outcomes()[0],))
        altered_outcome = replace(result.outcomes()[1], claim=altered_claim)
        before = deepcopy(vars(owner))
        with pytest.raises(ValueError):
            owner.reconcile(cycle_id=7, cutoff_tick=24, outcomes=(altered_outcome,))
    assert vars(owner) == before
