"""P16-1G-C owner-local eligibility, provenance, timing and no-update tests.

Fixtures take original immutable claims/outcomes from the real hierarchy. Deliberate
malformations test rejection, not an alternative cognitive/physical implementation.
"""

from dataclasses import FrozenInstanceError, replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_learning import RightingLearningHookV1
from nca8_maps import DurableNavMapRefV1
from nca8_outcome_attention import RightingInterpretationV1, RightingMismatchRequestV1
from nca8_righting import RightingContextV1


@pytest.fixture
def actual():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True)
    first, _ = trial.step()
    second, _ = trial.step()
    third = trial.focal_step()
    return trial, first, second, third.claim_outcomes[0]


def owner(first, *, capacity=32):
    registration = first.claim_registration
    return RightingLearningHookV1(registration.request.origin.stream, registration.preview.basis.source_map_ref,
                                  diagnostic_capacity=capacity)


def register(hook, focal):
    return hook.reconcile(cycle_id=focal.commitment.cycle_id, cutoff_tick=focal.calculation.cutoff_tick,
                          registration=focal.claim_registration, context=focal.calculation.task.context)


def offer(hook, outcome, **changes):
    arguments = dict(cycle_id=3, cutoff_tick=8, outcomes=(outcome,))
    arguments.update(changes)
    return hook.reconcile(**arguments)


def status(report):
    return tuple(item.status for item in report.dispositions)


def test_actual_owner_is_the_source_extension_and_not_current_wnm():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_learning_hook_enabled=True)
    source_owner = trial.core.cognition.sensory
    hook = source_owner.learning_hook
    assert hook is not None
    assert hook.source_ref == trial.core.cognition.maps.posture_support_ref
    assert hook.recipient_id == 'body_sensory:posture_support:consequence'
    assert trial.core.cognition.navigation.current_wnm is None
    with pytest.raises(RuntimeError):
        source_owner.configure_learning_hook(trial.core.cognition.stream)


@pytest.mark.parametrize('options', [{}, {'task_outcomes_enabled': True},
                                   {'task_outcomes_enabled': True, 'task_outcome_attention_enabled': True}])
def test_default_and_retained_profiles_do_not_construct_hook(options):
    trial = IntegratedRightingTrialV1(**options)
    focal, _ = trial.step()
    assert trial.core.cognition.sensory.learning_hook is None
    assert focal.learning_report is None
    assert 'learning_reconciliation' not in focal.as_dict()
    assert not any(key.startswith('learning_') for key in trial.retained_counts())


@pytest.mark.parametrize('bad', [None, 0, 1, 'true', [], {}])
def test_enablement_is_explicit_boolean(bad):
    with pytest.raises(TypeError):
        IntegratedRightingTrialV1(task_outcomes_enabled=True, task_learning_hook_enabled=bad)


def test_hook_cannot_bypass_correspondence_dependency():
    with pytest.raises(ValueError):
        IntegratedRightingTrialV1(task_learning_hook_enabled=True)


def test_participation_has_original_body_permission_and_independent_expiry(actual):
    _, first, _, _ = actual
    hook = owner(first)
    report = register(hook, first)
    part = report.new_participation
    assert part.registration is first.claim_registration
    assert part.context is first.calculation.task.context
    assert part.created_cycle == 1 and part.expires_before_cycle == 5
    assert part.registration.due_tick == 4 and part.registration.expires_at_tick == 12
    assert part.as_dict()['grants_motor_authority'] is False
    assert part.as_dict()['source_sample_id'] == 1
    assert report.offered_outcomes == 0
    assert report.as_dict()['new_action_outcome_available'] is False
    assert not report.dispositions


def test_matched_evidence_is_accepted_once_without_causal_credit(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    report = offer(hook, outcome)
    assert status(report) == ('accepted_no_update',)
    event = report.dispositions[0]
    assert event.outcome is outcome and event.accepted_relations
    assert event.as_dict()['action_causation'] == 'uncertain'
    assert event.as_dict()['durable_learning_updates'] == 0
    assert not hook.pending()
    assert status(offer(hook, outcome, cycle_id=4, cutoff_tick=12)) == ('duplicate_ignored',)
    assert not hook.pending()


@pytest.mark.parametrize('cycle,tick', [(1, 0), (2, 4), (4, 12)])
def test_a_just_issued_or_future_outcome_cannot_be_consumed(actual, cycle, tick):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    with pytest.raises((ValueError, RuntimeError)):
        offer(hook, outcome, cycle_id=cycle, cutoff_tick=tick)
    assert len(hook.pending()) == 1


@pytest.mark.parametrize('cycle,tick', [(True, 8), (0, 8), (2.0, 8), ('3', 8), (3, True), (3, -1), (3, 8.0), (3, 2**63)])
def test_bad_reconciliation_indices_do_not_mutate_state(actual, cycle, tick):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    before = hook.pending(), hook.history()
    with pytest.raises(ValueError):
        offer(hook, outcome, cycle_id=cycle, cutoff_tick=tick)
    assert (hook.pending(), hook.history()) == before


def test_repeated_f_call_cannot_repeat_consumption(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    report = offer(hook, outcome)
    with pytest.raises(RuntimeError):
        offer(hook, outcome)
    assert tuple(event.as_dict() for event in hook.history()) == tuple(event.as_dict() for event in report.dispositions)


@pytest.mark.parametrize('change', [
    {'number': 0}, {'number': True}, {'number': 1.5}, {'command_intervals': -1}, {'command_intervals': True},
    {'command_intervals': 9}, {'status': 'success'}, {'status': 'mismatch'}, {'status': 'unknown'},
    {'relations': (('imaginary_relation', 'matched'),)}, {'relations': (('contact', 'success'),)},
    {'relations': (('contact', 'matched'), ('contact', 'matched'))}, {'relations': []},
    {'evidence': None}, {'command_intervals': 0}, {'evaluated_tick': True},
])
def test_malformed_publisher_results_rejected_before_state_change(actual, change):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    before = hook.pending(), hook.history()
    with pytest.raises((ValueError, TypeError)):
        offer(hook, replace(outcome, **change))
    assert (hook.pending(), hook.history()) == before


@pytest.mark.parametrize('which', ['generation', 'source', 'operation', 'target', 'relations', 'duplicate_target'])
def test_wrong_origin_cannot_reach_a_recipient(actual, which):
    _, first, _, outcome = actual
    reg = outcome.registration
    if which == 'generation':
        origin = replace(reg.request.origin, stream=MotorStreamRefV1(reg.request.origin.stream.stream_id, 2))
        reg = replace(reg, request=replace(reg.request, origin=origin))
    elif which == 'source':
        basis = replace(reg.preview.basis, source_map_ref=DurableNavMapRefV1('other_source', 1))
        reg = replace(reg, preview=replace(reg.preview, basis=basis))
    elif which == 'operation':
        reg = replace(reg, request=replace(reg.request, origin=replace(reg.request.origin, application_id='other_application')))
    elif which == 'target':
        reg = replace(reg, targets=(object(),))
    elif which == 'relations':
        reg = replace(reg, compatible_relations=('contact',), unevaluable_relations=('contact',))
    else:
        reg = replace(reg, targets=(reg.targets[0], reg.targets[0]))
    hook = owner(first)
    register(hook, first)
    with pytest.raises((ValueError, TypeError)):
        offer(hook, replace(outcome, registration=reg))
    assert len(hook.pending()) == 1 and not hook.history()


def test_copy_of_equal_registration_cannot_replace_original(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    with pytest.raises(ValueError, match='copied'):
        offer(hook, replace(outcome, registration=replace(outcome.registration)))
    assert len(hook.pending()) == 1


@pytest.mark.parametrize('change', [{'event_tick': 5, 'sample_id': 6}, {'sample_id': 1}, {'available_tick': 9}])
def test_wrong_endpoint_or_future_delivery_cannot_supply_teaching(actual, change):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    with pytest.raises(ValueError):
        offer(hook, replace(outcome, evidence=replace(outcome.evidence, **change)))
    assert len(hook.pending()) == 1


@pytest.mark.parametrize('terminal', ['not_applied', 'interrupted', 'cancelled', 'expired_unresolved', 'execution_unknown',
                                    'unevaluable_authorization', 'comparison_disabled', 'observed_without_command'])
def test_valid_adverse_or_unexecuted_outcome_is_not_positive_teaching(actual, terminal):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = replace(original, status=terminal, evidence=None, relations=(), command_intervals=0)
    report = offer(hook, outcome)
    assert status(report) == (f'rejected_{terminal}',)
    assert not hook.pending()


def test_partial_unknown_is_preserved_without_inventing_failure(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    relations = tuple((name, 'unknown') for name, _ in original.relations)
    outcome = replace(original, status='unknown', relations=relations)
    report = offer(hook, outcome)
    assert status(report) == ('rejected_unknown',)
    assert report.dispositions[0].outcome.relations == relations
    assert not report.dispositions[0].accepted_relations


def mismatch(original):
    relations = tuple((name, 'mismatch' if name == 'contact' else result) for name, result in original.relations)
    return replace(original, status='mismatch', evidence=replace(original.evidence, support_contact=False), relations=relations)


def request_for(outcome, context):
    return RightingMismatchRequestV1('fixture_request', outcome, context, 8, 'consequential_support_contradiction', ('contact',))


def interpretation_for(request, *, cycle=3, tick=8, status_value='still_relevant_support_discrepancy'):
    return RightingInterpretationV1(request, cycle, tick, 'wnm:current', request.outcome.evidence, status_value,
                                   (('contact', 'still_relevant'),))


def test_teaching_waits_for_actual_interpretation_without_renewal(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = mismatch(original)
    request = request_for(outcome, first.calculation.task.context)
    report = offer(hook, outcome, requests=(request,))
    assert status(report) == ('pending_interpretation',)
    assert hook.pending()[0].expires_before_cycle == 5
    result = interpretation_for(request, cycle=4, tick=12)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, interpretation=result)
    assert status(report) == ('accepted_no_update',)
    assert report.dispositions[0].interpretation is result
    assert report.dispositions[0].outcome is outcome
    assert not hook.pending()


def test_unresolved_interpretation_remains_pending_until_its_own_expiry(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = mismatch(original)
    request = request_for(outcome, first.calculation.task.context)
    result = interpretation_for(request, status_value='unresolved_current_relevance')
    report = offer(hook, outcome, requests=(request,), interpretation=result)
    assert status(report) == ('pending_interpretation', 'pending_unresolved_interpretation')
    assert len(hook.pending()) == 1
    hook.reconcile(cycle_id=4, cutoff_tick=12)
    assert status(hook.reconcile(cycle_id=5, cutoff_tick=16)) == ('eligibility_expired',)
    assert not hook.pending()


def test_disabled_attention_cannot_turn_required_interpretation_into_free_work(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    report = offer(hook, mismatch(original), attention_enabled=False)
    assert status(report) == ('pending_interpretation',)
    assert hook.pending()[0].awaiting_interpretation
    assert hook.pending()[0].request is None
    assert status(hook.reconcile(cycle_id=5, cutoff_tick=16)) == ('eligibility_expired',)


def test_copied_interpretation_request_cannot_release_dependency(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = mismatch(original)
    request = request_for(outcome, first.calculation.task.context)
    offer(hook, outcome, requests=(request,))
    with pytest.raises(ValueError, match='copied request'):
        hook.reconcile(cycle_id=4, cutoff_tick=12, interpretation=interpretation_for(replace(request), cycle=4, tick=12))
    assert hook.pending()[0].outcome is outcome


@pytest.mark.parametrize('which', ['copied_outcome', 'wrong_time', 'not_a_mismatch', 'duplicate'])
def test_bad_dependency_batch_has_no_partial_effect(actual, which):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = mismatch(original)
    request = request_for(outcome, first.calculation.task.context)
    if which == 'copied_outcome':
        request = replace(request, outcome=replace(outcome))
    elif which == 'wrong_time':
        request = replace(request, admitted_tick=7)
    elif which == 'not_a_mismatch':
        outcome = original
        request = replace(request, outcome=outcome)
    requests = (request, request) if which == 'duplicate' else (request,)
    with pytest.raises(ValueError):
        offer(hook, outcome, requests=requests)
    assert hook.pending()[0].outcome is None


def test_expiry_does_not_need_evidence_and_cannot_be_refreshed(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    for cycle, tick in ((2, 1), (3, 2), (4, 3)):
        hook.reconcile(cycle_id=cycle, cutoff_tick=tick)
        assert hook.pending()[0].expires_before_cycle == 5
    assert status(hook.reconcile(cycle_id=5, cutoff_tick=4)) == ('eligibility_expired',)
    report = offer(hook, outcome, cycle_id=6)
    assert status(report) == ('rejected_expired_eligibility',)
    assert not hook.pending()


def test_prediction_can_expire_while_eligibility_was_still_live(actual):
    _, first, _, original = actual
    hook = owner(first)
    register(hook, first)
    outcome = replace(original, status='expired_unresolved', evidence=None, relations=(), evaluated_tick=16)
    report = offer(hook, outcome, cycle_id=2, cutoff_tick=16)
    assert status(report) == ('rejected_expired_unresolved',)
    assert not any(event.status == 'eligibility_expired' for event in report.dispositions)


def test_overflow_is_atomic_and_does_not_advance_hook_clock(actual, monkeypatch):
    _, first, second, _ = actual
    hook = owner(first)
    register(hook, first)
    old = hook.pending()
    monkeypatch.setattr('nca8_learning._MAX_PARTICIPANTS', 1)
    with pytest.raises(OverflowError):
        register(hook, second)
    assert hook.pending() == old
    monkeypatch.setattr('nca8_learning._MAX_PARTICIPANTS', 8)
    assert len(register(hook, second).pending) == 2


def test_diagnostic_capacity_and_rereads_do_not_control_acceptance(actual):
    _, first, _, outcome = actual
    histories = []
    for capacity in (1, 32):
        hook = owner(first, capacity=capacity)
        register(hook, first)
        before = random.getstate()
        for _ in range(20):
            json.dumps([part.as_dict() for part in hook.pending()], allow_nan=False)
            hook.history(); hook.retained_counts()
        report = offer(hook, outcome)
        histories.append(report.as_dict())
        assert random.getstate() == before
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=(outcome,))
        assert len(hook.history()) <= capacity
    assert histories[0] == histories[1]


def test_invalid_source_generation_checked_even_for_duplicate_outcomes(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    register(hook, first)
    offer(hook, outcome)
    changed = replace(outcome.registration.request.origin, stream=MotorStreamRefV1('wrong', 1))
    registration = replace(outcome.registration, request=replace(outcome.registration.request, origin=changed))
    with pytest.raises(ValueError):
        offer(hook, replace(outcome, registration=registration), cycle_id=4, cutoff_tick=12)


def test_valid_unregistered_operation_is_rejected_not_sent_to_current_owner(actual):
    _, first, _, outcome = actual
    hook = owner(first)
    report = offer(hook, outcome)
    assert status(report) == ('rejected_unregistered_operation',)
    assert not hook.pending()


def test_reset_closes_old_owner_and_new_generation_cannot_borrow_credit():
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_learning_hook_enabled=True)
    first, _ = trial.step()
    old = trial.core.cognition.sensory.learning_hook
    assert old.pending()
    trial.reset()
    new = trial.core.cognition.sensory.learning_hook
    assert new is not old and not old.pending() and not new.pending()
    with pytest.raises(RuntimeError):
        old.reconcile(cycle_id=2, cutoff_tick=4)
    with pytest.raises(ValueError):
        new.reconcile(cycle_id=1, cutoff_tick=0, registration=first.claim_registration, context=first.calculation.task.context)


def test_failure_in_f_stops_before_new_installation_or_physical_call(monkeypatch):
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_learning_hook_enabled=True)
    def fail(**_kwargs):
        raise ValueError('deliberate hook integrity failure')
    monkeypatch.setattr(trial.core.cognition.sensory.learning_hook, 'reconcile', fail)
    with pytest.raises(ValueError):
        trial.focal_step()
    assert trial.tick == 0 and trial.controller.installation_count == 0 and trial.stopped
    assert not trial.core.handoff.has_pending_request


def test_results_are_immutable_and_exported_lists_are_detached(actual):
    _, first, _, _ = actual
    hook = owner(first)
    report = register(hook, first)
    with pytest.raises(FrozenInstanceError):
        report.new_participation.created_cycle = 7
    exported = report.as_dict()
    exported['pending'].clear()
    assert len(hook.pending()) == 1


@pytest.mark.parametrize('capacity', [0, 33, True, 1.5, '1'])
def test_diagnostic_limits_are_not_coerced(actual, capacity):
    _, first, _, _ = actual
    with pytest.raises(ValueError):
        owner(first, capacity=capacity)


def test_new_application_cannot_reuse_a_still_eligible_claim_identifier(actual):
    _, first, second, _ = actual
    hook = owner(first)
    register(hook, first)
    old = hook.pending()
    proposal = second.claim_registration
    reused = replace(proposal, preview=replace(proposal.preview,
                     pnm=replace(proposal.preview.pnm, pnm_id=first.claim_registration.preview.pnm.pnm_id)))
    with pytest.raises(ValueError, match='reuse'):
        hook.reconcile(cycle_id=2, cutoff_tick=4, registration=reused, context=second.calculation.task.context)
    assert hook.pending() == old and not hook.history()


def test_target_commit_time_cannot_be_relabelled_as_current_participation(actual):
    _, first, _, _ = actual
    hook = owner(first)
    proposal = first.claim_registration
    changed = replace(proposal, targets=tuple(replace(target, committed_tick=1) for target in proposal.targets))
    with pytest.raises(ValueError, match='commit'):
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=changed, context=first.calculation.task.context)
    assert not hook.pending() and not hook.history()
