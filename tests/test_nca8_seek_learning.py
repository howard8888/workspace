"""Original-recipient, expiry and atomic no-learning boundary tests for P16-2C-F."""
from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_feeding import FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_seek_attention import SeekingInterpretationV1
from nca8_seek_learning import SeekingLearningHookV1
from nca8_seek_learning_demo import create_seeking_learning_trial_v1
from nca8_seek_nipple import SeekNippleProfileV1
from nca8_seek_outcomes_demo import create_seek_nipple_outcome_trial_v1
from nca8_maternal_learning_demo import create_maternal_learning_trial_v1


def snapshot(hook):
    return json.dumps({'pending': [p.as_dict() for p in hook.pending()], 'history': [p.as_dict() for p in hook.history()],
                       'counts': hook.retained_counts(), 'cycle': hook._last_cycle, 'tick': hook._last_tick,
                       'outcome': hook._last_outcome, 'closed': hook._closed}, sort_keys=True, allow_nan=False)


@pytest.fixture(scope='module')
def originals():
    result = {}
    for case in ('nominal_on', 'competing_on', 'narrowed', 'no_capability', 'comparison_off'):
        trial = create_seeking_learning_trial_v1(case)
        first = trial.focal_step()
        cycles = [first]
        for _ in range(4):
            for _ in range(4):
                trial.advance_lower()
            cycles.append(trial.focal_step())
        result[case] = trial, tuple(cycles)
    return result


def fresh_hook(originals, case='nominal_on', *, diagnostic_capacity=32):
    trial, cycles = originals[case]
    first = cycles[0]
    hook = SeekingLearningHookV1(trial.latest_feedback.stream, first.feeding_detail_source.seed,
                                 diagnostic_capacity=diagnostic_capacity)
    claim = first.seeking_correspondence.registration
    task = first.calculation.navigation.application.task
    hook.reconcile(cycle_id=1, cutoff_tick=0, registration=claim, task=task,
                   comparison_enabled=case != 'comparison_off')
    return hook, cycles


def published(cycle):
    return cycle.seeking_correspondence.outcomes


def interpreted(cycle):
    frame = cycle.seeking_attention
    return frame.allocation.interpretation if frame is not None and frame.allocation.kind == 'interpretation' else None


@pytest.mark.parametrize('bad', [None, 0, 1, 0.0, 'true', [], {}])
def test_hook_enablement_requires_a_real_boolean(bad):
    with pytest.raises(TypeError):
        SeekNippleProfileV1(outcomes_enabled=True, learning_hook_enabled=bad)


def test_hook_requires_correspondence_and_defaults_remain_inactive():
    assert SeekNippleProfileV1().learning_hook_enabled is False
    with pytest.raises(ValueError):
        SeekNippleProfileV1(learning_hook_enabled=True)
    old = create_seek_nipple_outcome_trial_v1()
    assert old.core.feeding_detail.learning_hook is None
    assert old.focal_step().seeking_learning_report is None


@pytest.mark.parametrize('bad', [None, True, 0, -1, 33, 1.5, '4'])
def test_hook_history_bound_rejects_coercion(bad):
    with pytest.raises(ValueError):
        SeekingLearningHookV1(MotorStreamRefV1('fixture', 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize('which', ['stream', 'seed'])
def test_constructor_requires_actual_domain_objects(which):
    with pytest.raises(TypeError):
        SeekingLearningHookV1(None if which == 'stream' else MotorStreamRefV1('fixture', 1),
                              None if which == 'seed' else FeedingDetailSeedV1())


def test_source_owns_single_optional_hook_and_failed_configuration_is_atomic():
    source = FeedingDetailSourceV1(MotorStreamRefV1('fixture', 1), FeedingDetailProfileV1())
    durable = source.durable_map.as_dict()
    with pytest.raises(ValueError):
        source.configure_learning_hook(diagnostic_capacity=0)
    assert source.learning_hook is None
    source.configure_learning_hook()
    assert source.learning_hook.seed == source.profile.seed
    assert source.durable_map.as_dict() == durable
    with pytest.raises(RuntimeError):
        source.configure_learning_hook()


def test_source_refuses_late_hook_configuration():
    trial = create_seek_nipple_outcome_trial_v1()
    trial.focal_step()
    with pytest.raises(RuntimeError):
        trial.core.feeding_detail.configure_learning_hook()


def test_new_participation_has_no_future_outcome_or_installation_claim(originals):
    hook, cycles = fresh_hook(originals)
    participant = hook.pending()[0]
    assert participant.claim is cycles[0].seeking_correspondence.registration
    assert participant.task is cycles[0].calculation.navigation.application.task
    assert participant.created_cycle == 1 and participant.expires_before_cycle == 5
    assert participant.outcome is None and participant.request is None
    assert participant.as_dict()['grants_motor_authority'] is False


def test_matches_are_accepted_once_from_original_evidence_without_learning(originals):
    hook, cycles = fresh_hook(originals)
    rng = random.getstate()
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]))
    item, = report.dispositions
    assert item.status == 'accepted_no_update'
    assert item.outcome is published(cycles[3])[0]
    assert len(item.accepted_relations) == 3 and item.interpretation is None
    assert not hook.pending()
    duplicate = hook.reconcile(cycle_id=5, cutoff_tick=16, outcomes=published(cycles[3]))
    assert [d.status for d in duplicate.dispositions] == ['duplicate_ignored']
    assert report.as_dict()['durable_learning_updates'] == 0 and random.getstate() == rng


@pytest.mark.parametrize('bad', [None, True, -1, 0.5, '12', 2**63])
def test_invalid_tick_is_atomic(originals, bad):
    hook, cycles = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=bad, outcomes=published(cycles[3]))
    assert snapshot(hook) == before


@pytest.mark.parametrize('bad', [None, True, 0, -1, 4.0, '4', 2**63])
def test_invalid_cycle_is_atomic(originals, bad):
    hook, cycles = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=bad, cutoff_tick=12, outcomes=published(cycles[3]))
    assert snapshot(hook) == before


@pytest.mark.parametrize('flag', ['attention_enabled', 'comparison_enabled'])
@pytest.mark.parametrize('bad', [None, 0, 1, 'true'])
def test_reconciliation_flags_are_not_truthiness(originals, flag, bad):
    hook, _ = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises(TypeError):
        hook.reconcile(cycle_id=2, cutoff_tick=4, **{flag: bad})
    assert snapshot(hook) == before


@pytest.mark.parametrize('change', [
    lambda o: replace(o, number=True), lambda o: replace(o, number=0), lambda o: replace(o, evaluated_tick=13),
    lambda o: replace(o, command_intervals=0), lambda o: replace(o, command_intervals=True),
    lambda o: replace(o, status='learned'), lambda o: replace(o, relations=()),
    lambda o: replace(o, relations=o.relations + o.relations[:1]),
    lambda o: replace(o, residuals=(('mouth_position', float('nan')),)),
    lambda o: replace(o, evidence=None), lambda o: replace(o, claim=replace(o.claim)),
    lambda o: replace(o, claim=replace(o.claim, compatible_relations=('detail_anchor',),
                                      unevaluable_relations=('mouth_position', 'separation'))),
])
def test_forged_outcome_never_changes_eligibility(originals, change):
    hook, cycles = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(change(published(cycles[3])[0]),))
    assert snapshot(hook) == before


@pytest.mark.parametrize('bad', [None, 'outcome', True, (), {}])
def test_wrong_outcome_domain_or_type_is_rejected(originals, bad):
    hook, _ = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(bad,))
    assert snapshot(hook) == before


def test_maternal_result_cannot_teach_the_feeding_recipient(originals):
    maternal = create_maternal_learning_trial_v1('nominal_on')
    maternal.focal_step()
    for _ in range(12):
        maternal.advance_lower()
    result = maternal.focal_step().maternal_correspondence.outcomes[0]
    hook, _ = fresh_hook(originals)
    before = snapshot(hook)
    with pytest.raises(TypeError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(result,))
    assert snapshot(hook) == before


@pytest.mark.parametrize('kind', ['list', 'duplicate', 'too_many', 'duplicate_claim'])
def test_batch_is_validated_completely_before_consumption(originals, kind):
    hook, cycles = fresh_hook(originals)
    outcome = published(cycles[3])[0]
    values = {'list': [outcome], 'duplicate': (outcome, outcome), 'too_many': (outcome,) * 9,
              'duplicate_claim': (outcome, replace(outcome, number=outcome.number + 1))}[kind]
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=values)
    assert snapshot(hook) == before


@pytest.mark.parametrize('kind', ['stream', 'generation', 'seed'])
def test_wrong_recipient_preserves_both_owners(originals, kind):
    _, cycles = originals['nominal_on']
    basis = cycles[0].feeding_detail_source
    stream = MotorStreamRefV1('wrong', 1) if kind == 'stream' else replace(basis.stream, generation=2) if kind == 'generation' else basis.stream
    hook = SeekingLearningHookV1(stream, replace(basis.seed, detail_region_id='different') if kind == 'seed' else basis.seed)
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=cycles[0].seeking_correspondence.registration,
                       task=cycles[0].calculation.navigation.application.task)
    assert snapshot(hook) == before


@pytest.mark.parametrize('kind', ['missing', 'wrong_task', 'wrong_region', 'terminal', 'future', 'wrong_cycle', 'task_only'])
def test_registration_requires_this_actual_selected_application(originals, kind):
    _, cycles = originals['nominal_on']
    first = cycles[0]
    hook = SeekingLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    task = first.calculation.navigation.application.task
    task = {'missing': None, 'wrong_task': replace(task, task_id='wrong'), 'wrong_region': replace(task, region_id='wrong'),
            'terminal': replace(task, status='reached_detail'), 'future': replace(task, started_tick=1)}.get(kind, task)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=2 if kind == 'wrong_cycle' else 1, cutoff_tick=0,
                       registration=None if kind == 'task_only' else first.seeking_correspondence.registration, task=task)
    assert hook.retained_counts()['seeking_learning_participants'] == 0


def test_same_claim_cannot_register_twice_and_same_F_cannot_repeat(originals):
    hook, cycles = fresh_hook(originals)
    first = cycles[0]
    before = snapshot(hook)
    with pytest.raises(RuntimeError):
        hook.reconcile(cycle_id=1, cutoff_tick=0)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=2, cutoff_tick=4, registration=first.seeking_correspondence.registration,
                       task=first.calculation.navigation.application.task)
    assert snapshot(hook) == before


def test_interpretation_dependency_uses_actual_result_then_only_once(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12),
                            requests=at12.seeking_attention.created, interpretation=interpreted(at12))
    assert [d.status for d in report.dispositions] == ['pending_interpretation', 'accepted_no_update']
    assert report.dispositions[-1].interpretation is interpreted(at12)
    assert not hook.pending()
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=5, cutoff_tick=16, interpretation=interpreted(at12))


def test_attention_off_cannot_supply_free_interpretation(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), attention_enabled=False)
    assert [d.status for d in report.dispositions] == ['pending_interpretation']
    assert report.pending[0].awaiting_interpretation and report.pending[0].request is None
    expired = hook.reconcile(cycle_id=5, cutoff_tick=16, attention_enabled=False)
    assert [d.status for d in expired.dispositions] == ['eligibility_expired']
    assert not hook.pending()


@pytest.mark.parametrize('kind', ['copied_outcome', 'future', 'wrong_relation', 'duplicate', 'list', 'too_many', 'attention_off'])
def test_request_batch_must_reference_actual_C2_output(originals, kind):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    request = at12.seeking_attention.created[0]
    changed = {'copied_outcome': replace(request, outcome=replace(request.outcome)),
               'future': replace(request, admitted_tick=13), 'wrong_relation': replace(request, relations=('touch',))}.get(kind, request)
    requests = [changed] if kind == 'list' else (changed,) * (9 if kind == 'too_many' else 2 if kind == 'duplicate' else 1)
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=requests, attention_enabled=kind != 'attention_off')
    assert snapshot(hook) == before


@pytest.mark.parametrize('kind', ['wrong_cycle', 'future', 'wrong_source', 'wrong_status', 'relations', 'working', 'bool_cycle'])
def test_focal_result_is_current_structural_and_not_recomputed(originals, kind):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    item = interpreted(at12)
    changed = {'wrong_cycle': replace(item, cycle_id=5), 'future': replace(item, cutoff_tick=13),
               'wrong_source': replace(item, current_source=cycles[0].feeding_detail_source),
               'wrong_status': replace(item, status='causally_proven'), 'relations': replace(item, relation_relevance=()),
               'working': replace(item, working_id=''), 'bool_cycle': replace(item, cycle_id=True)}[kind]
    before = snapshot(hook)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.seeking_attention.created, interpretation=changed)
    assert snapshot(hook) == before


def test_unresolved_interpretation_remains_pending_without_renewal(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    item = interpreted(at12)
    # Explicit interpretation-result contract fixture, not new physical evidence.
    unresolved = replace(item, current_source=replace(item.current_source, oral_feedback=None),
                         status='unresolved_current_relevance', relation_relevance=(('separation', 'unknown'),))
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.seeking_attention.created, interpretation=unresolved)
    assert [d.status for d in report.dispositions] == ['pending_interpretation', 'pending_unresolved_interpretation']
    assert report.pending[0].expires_before_cycle == 5
    assert hook.reconcile(cycle_id=5, cutoff_tick=16).dispositions[0].status == 'eligibility_expired'


def test_independent_eligibility_expiry_preserves_the_matching_outcome(originals):
    hook, cycles = fresh_hook(originals)
    outcome = published(cycles[3])[0]
    before = outcome.as_dict()
    report = hook.reconcile(cycle_id=5, cutoff_tick=12, outcomes=(outcome,))
    assert [d.status for d in report.dispositions] == ['eligibility_expired', 'rejected_expired_eligibility']
    assert outcome.as_dict() == before and outcome.status == 'matched'


def test_unregistered_valid_outcome_cannot_create_participation(originals):
    _, cycles = originals['nominal_on']
    hook = SeekingLearningHookV1(cycles[0].feeding_detail_source.stream, cycles[0].feeding_detail_source.seed)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]))
    assert report.dispositions[0].status == 'rejected_unregistered_operation' and not report.pending


def test_disabling_comparison_cannot_train_existing_participation(originals):
    hook, cycles = fresh_hook(originals)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]), comparison_enabled=False)
    assert report.dispositions[0].status == 'rejected_matched' and not report.pending


def test_diagnostic_eviction_cannot_change_eligibility_or_F_results(originals):
    one, cycles = fresh_hook(originals, 'competing_on', diagnostic_capacity=1)
    full, _ = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    options = dict(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.seeking_attention.created,
                   interpretation=interpreted(at12))
    assert one.reconcile(**options) == full.reconcile(**options)
    assert one.pending() == full.pending() and len(one.history()) == 1 and len(full.history()) == 2


def test_explicit_capacity_fixture_refuses_atomically_without_eviction(originals):
    fresh, cycles = fresh_hook(originals)
    p = fresh.pending()[0]
    hook = SeekingLearningHookV1(fresh.stream, fresh.seed)
    # Artificial full-capacity fixture, not evidence that normal one-application
    # per opportunity with four-cycle expiry naturally fills eight participants.
    hook._pending = {f'capacity:{i}': p for i in range(8)}
    before = snapshot(hook)
    with pytest.raises(OverflowError):
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=p.claim, task=p.task)
    assert snapshot(hook) == before


def test_close_revokes_processing_without_erasing_historical_outcome(originals):
    hook, cycles = fresh_hook(originals)
    outcome = published(cycles[3])[0]
    prior = outcome.as_dict()
    hook.close()
    assert not hook.pending()
    with pytest.raises(RuntimeError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    assert outcome.as_dict() == prior


def test_exports_are_detached_and_reading_never_renews_participation(originals):
    hook, _ = fresh_hook(originals)
    before = snapshot(hook)
    value = hook.pending()[0].as_dict()
    value['compatible_relations'].clear()
    value['task']['task_id'] = 'changed'
    for _ in range(20):
        hook.pending(); hook.history(); hook.retained_counts()
    assert snapshot(hook) == before


def test_new_claim_validation_creates_no_synthetic_result(originals):
    from nca8_seek_outcomes import validate_seeking_claim_v1
    hook, cycles = fresh_hook(originals)
    claim = cycles[0].seeking_correspondence.registration
    before = snapshot(hook)
    assert validate_seeking_claim_v1(claim, stream=hook.stream) is None
    assert snapshot(hook) == before and hook.pending()[0].outcome is None


@pytest.mark.parametrize('kind', ['request_id', 'significance'])
def test_request_identity_and_significance_are_not_arbitrary_strings(originals, kind):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    request = replace(at12.seeking_attention.created[0], **{kind: 'invented'})
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=(request,))
    assert snapshot(hook) == before


@pytest.mark.parametrize('status', ['cancelled', 'interrupted', 'expired_unresolved', 'unresolved_stopped', 'comparison_disabled'])
def test_unscored_dispositions_cannot_be_promoted_to_teaching(originals, status):
    hook, cycles = fresh_hook(originals)
    # Explicit downstream contract fixture, not a new physical event.
    outcome = replace(published(cycles[3])[0], status=status, evidence=None, relations=(), residuals=())
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    assert report.dispositions[0].status == 'rejected_' + status
    assert not report.dispositions[0].accepted_relations


def test_observed_match_without_command_never_receives_execution_credit(originals):
    hook, cycles = fresh_hook(originals)
    # Contract fixture removes execution exposure while retaining real sensing.
    outcome = replace(published(cycles[3])[0], command_intervals=0, status='observed_without_command')
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
    assert report.dispositions[0].status == 'rejected_observed_without_command'
    assert report.as_dict()['durable_learning_updates'] == 0
