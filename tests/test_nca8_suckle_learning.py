"""K's original-recipient, independent-expiry and actual Phase-F boundaries.

Canonical evidence comes from the unchanged H/I/J paths. Hostile packets and
simultaneous-outcome fixtures are explicitly labelled contract tests, not new
physical scenarios. No durable learner or behavioral improvement is assumed.
"""
from __future__ import annotations

from dataclasses import replace
import json
import random

import pytest

from cca8_motor_contracts import MotorStreamRefV1
from nca8_feeding import FeedingDetailProfileV1, FeedingDetailSeedV1, FeedingDetailSourceV1
from nca8_suckle_attention import SuckleInterpretationV1
from nca8_suckle_learning import SuckleLearningHookV1
from nca8_suckle import SuckleProfileV1, SuckleIPV1
from nca8_suckle_demo import create_suckle_trial_v1, suckle_profile_v1, SUCKLE_LATCH_CASES_V1
from nca8_suckle_attention_demo import suckle_attention_profile_v1, SUCKLE_ATTENTION_CASES_V1
from nca8_maternal_learning_demo import create_maternal_learning_trial_v1
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_body_targets import BodyTranslationCapabilityV1, nominal_body_capabilities_v1, oral_body_capability_v1
from nca8_followmom import FollowMomProfileV1
from nca8_seek_nipple import SeekNippleIPV1
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_suckle_outcomes import SuckleOutcomeRuntimeV1, SuckleEndpointV1, validate_suckle_claim_v1


def make_trial(case="nominal_on", *, hook=True, diagnostic_capacity=32, trace_capacity=256):
    """Test-only opt-in: existing physical profiles, task owners and outer driver.

    No candidate production factory/menu is added in Stage C. The collector uses
    the actual H/J schedule, including cancellation and competing-source controls.
    K changes only the profile switch at construction, never the source or physics.
    """
    profile = suckle_attention_profile_v1(case) if case in SUCKLE_ATTENTION_CASES_V1 else suckle_profile_v1(case)
    run = profile.run
    trial = IntegratedRightingTrialV1(
        run.physical, stream_id="suckle_latch_reference_body", planar_profile=run.planar, oral_profile=run.oral,
        oral_seal_profile=profile.seal,
        suckle_profile=replace(profile.suckle, outcomes_enabled=True, learning_hook_enabled=hook),
        capabilities=(*nominal_body_capabilities_v1(), oral_body_capability_v1(), *((profile.capability,) if profile.capability else ())),
        follow_mom_profile=FollowMomProfileV1(outcomes_enabled=run.stand_follow,
                                             outcome_attention_enabled=run.stand_follow, learning_hook_enabled=run.stand_follow),
        translation_capability=BodyTranslationCapabilityV1(), feeding_detail_profile=run.feeding,
        seek_nipple_profile=run.seeking, stand_follow_enabled=run.stand_follow,
        task_outcomes_enabled=run.stand_follow, task_outcome_attention_enabled=run.stand_follow,
        task_learning_hook_enabled=run.stand_follow, righting_target_inset_degrees=2.0,
        task_pnm_consumer_enabled=run.pnm_registration, learning_diagnostic_capacity=diagnostic_capacity, trace_capacity=trace_capacity,
    )
    return trial, profile


def collect(case="nominal_on", **kwargs):
    """Read complete raw evidence; no old experiment's verdict is borrowed for K."""
    trial, profile = make_trial(case, **kwargs)
    return trial, collect_seek_nipple_evidence_v1(trial, profile.run)


def create_suckle_learning_trial_v1(case="nominal_on"):
    """Test helper, not a shipped review function."""
    return make_trial(case)[0]


def create_suckle_outcome_trial_v1():
    """Use accepted I factory with K absent."""
    return create_suckle_trial_v1(outcomes_enabled=True)


def snapshot(hook):
    return json.dumps({'pending': [p.as_dict() for p in hook.pending()], 'history': [p.as_dict() for p in hook.history()],
                       'counts': hook.retained_counts(), 'cycle': hook._last_cycle, 'tick': hook._last_tick,
                       'outcome': hook._last_outcome, 'closed': hook._closed}, sort_keys=True, allow_nan=False)


@pytest.fixture(scope='module')
def originals():
    result = {}
    for case in ('nominal_on', 'competing_on', 'narrowed', 'no_capability', 'comparison_off'):
        trial = create_suckle_learning_trial_v1(case)
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
    hook = SuckleLearningHookV1(trial.latest_feedback.stream, first.feeding_detail_source.seed,
                                 diagnostic_capacity=diagnostic_capacity)
    claim = first.suckle_correspondence.registration
    task = first.calculation.navigation.application.task
    hook.reconcile(cycle_id=1, cutoff_tick=0, registration=claim, task=task,
                   comparison_enabled=case != 'comparison_off')
    return hook, cycles


def published(cycle):
    return cycle.suckle_correspondence.outcomes


def interpreted(cycle):
    frame = cycle.suckle_attention
    return frame.allocation.interpretation if frame is not None and frame.allocation.kind == 'interpretation' else None


@pytest.mark.parametrize('bad', [None, 0, 1, 0.0, 'true', [], {}])
def test_hook_enablement_requires_a_real_boolean(bad):
    with pytest.raises(TypeError):
        SuckleProfileV1(outcomes_enabled=True, learning_hook_enabled=bad)


def test_hook_requires_correspondence_and_defaults_remain_inactive():
    assert SuckleProfileV1().learning_hook_enabled is False
    with pytest.raises(ValueError):
        SuckleProfileV1(learning_hook_enabled=True)
    old = create_suckle_outcome_trial_v1()
    assert old.core.feeding_detail.suckle_learning_hook is None
    assert old.focal_step().suckle_learning_report is None


@pytest.mark.parametrize('bad', [None, True, 0, -1, 33, 1.5, '4'])
def test_hook_history_bound_rejects_coercion(bad):
    with pytest.raises(ValueError):
        SuckleLearningHookV1(MotorStreamRefV1('fixture', 1), FeedingDetailSeedV1(), diagnostic_capacity=bad)


@pytest.mark.parametrize('which', ['stream', 'seed'])
def test_constructor_requires_actual_domain_objects(which):
    with pytest.raises(TypeError):
        SuckleLearningHookV1(None if which == 'stream' else MotorStreamRefV1('fixture', 1),
                              None if which == 'seed' else FeedingDetailSeedV1())


def test_source_owns_single_optional_hook_and_failed_configuration_is_atomic():
    source = FeedingDetailSourceV1(MotorStreamRefV1('fixture', 1), FeedingDetailProfileV1())
    durable = source.durable_map.as_dict()
    with pytest.raises(ValueError):
        source.configure_suckle_learning_hook(diagnostic_capacity=0)
    assert source.suckle_learning_hook is None
    source.configure_suckle_learning_hook()
    assert source.suckle_learning_hook.seed == source.profile.seed
    assert source.durable_map.as_dict() == durable
    with pytest.raises(RuntimeError):
        source.configure_suckle_learning_hook()


def test_source_refuses_late_hook_configuration():
    trial = create_suckle_outcome_trial_v1()
    trial.focal_step()
    with pytest.raises(RuntimeError):
        trial.core.feeding_detail.configure_suckle_learning_hook()


def test_new_participation_has_no_future_outcome_or_installation_claim(originals):
    hook, cycles = fresh_hook(originals)
    participant = hook.pending()[0]
    assert participant.claim is cycles[0].suckle_correspondence.registration
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
    assert len(item.accepted_relations) == 4 and item.interpretation is None
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
                                      unevaluable_relations=('mouth_position', 'closure', 'seal'))),
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
    hook = SuckleLearningHookV1(stream, replace(basis.seed, detail_region_id='different') if kind == 'seed' else basis.seed)
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=cycles[0].suckle_correspondence.registration,
                       task=cycles[0].calculation.navigation.application.task)
    assert snapshot(hook) == before


@pytest.mark.parametrize('kind', ['missing', 'wrong_task', 'wrong_region', 'terminal', 'future', 'wrong_cycle', 'task_only'])
def test_registration_requires_this_actual_selected_application(originals, kind):
    _, cycles = originals['nominal_on']
    first = cycles[0]
    hook = SuckleLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    task = first.calculation.navigation.application.task
    task = {'missing': None, 'wrong_task': replace(task, task_id='wrong'), 'wrong_region': replace(task, region_id='wrong'),
            'terminal': replace(task, status='latch_established'), 'future': replace(task, started_tick=1)}.get(kind, task)
    with pytest.raises((TypeError, ValueError)):
        hook.reconcile(cycle_id=2 if kind == 'wrong_cycle' else 1, cutoff_tick=0,
                       registration=None if kind == 'task_only' else first.suckle_correspondence.registration, task=task)
    assert hook.retained_counts()['suckle_learning_participants'] == 0


def test_same_claim_cannot_register_twice_and_same_F_cannot_repeat(originals):
    hook, cycles = fresh_hook(originals)
    first = cycles[0]
    before = snapshot(hook)
    with pytest.raises(RuntimeError):
        hook.reconcile(cycle_id=1, cutoff_tick=0)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=2, cutoff_tick=4, registration=first.suckle_correspondence.registration,
                       task=first.calculation.navigation.application.task)
    assert snapshot(hook) == before


def test_interpretation_dependency_uses_actual_result_then_only_once(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12),
                            requests=at12.suckle_attention.created, interpretation=interpreted(at12))
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
    request = at12.suckle_attention.created[0]
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
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.suckle_attention.created, interpretation=changed)
    assert snapshot(hook) == before


def test_unresolved_interpretation_remains_pending_without_renewal(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    item = interpreted(at12)
    # Explicit interpretation-result contract fixture, not new physical evidence.
    unresolved = replace(item, current_source=replace(item.current_source, oral_feedback=None),
                         status='unresolved_current_relevance', relation_relevance=(('seal', 'unknown'),))
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.suckle_attention.created, interpretation=unresolved)
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
    hook = SuckleLearningHookV1(cycles[0].feeding_detail_source.stream, cycles[0].feeding_detail_source.seed)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]))
    assert report.dispositions[0].status == 'rejected_unregistered_operation' and not report.pending


def test_disabling_comparison_cannot_train_existing_participation(originals):
    hook, cycles = fresh_hook(originals)
    report = hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]), comparison_enabled=False)
    assert report.dispositions[0].status == 'comparison_disabled_no_teaching' and not report.pending


def test_diagnostic_eviction_cannot_change_eligibility_or_F_results(originals):
    one, cycles = fresh_hook(originals, 'competing_on', diagnostic_capacity=1)
    full, _ = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    options = dict(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=at12.suckle_attention.created,
                   interpretation=interpreted(at12))
    assert one.reconcile(**options) == full.reconcile(**options)
    assert one.pending() == full.pending() and len(one.history()) == 1 and len(full.history()) == 2


def test_explicit_capacity_fixture_refuses_atomically_without_eviction(originals):
    fresh, cycles = fresh_hook(originals)
    p = fresh.pending()[0]
    hook = SuckleLearningHookV1(fresh.stream, fresh.seed)
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
    from nca8_suckle_outcomes import validate_suckle_claim_v1
    hook, cycles = fresh_hook(originals)
    claim = cycles[0].suckle_correspondence.registration
    before = snapshot(hook)
    assert validate_suckle_claim_v1(claim, stream=hook.stream) is None
    assert snapshot(hook) == before and hook.pending()[0].outcome is None


@pytest.mark.parametrize('kind', ['request_id', 'significance'])
def test_request_identity_and_significance_are_not_arbitrary_strings(originals, kind):
    hook, cycles = fresh_hook(originals, 'competing_on')
    at12 = cycles[3]
    request = replace(at12.suckle_attention.created[0], **{kind: 'invented'})
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(at12), requests=(request,))
    assert snapshot(hook) == before


@pytest.mark.parametrize('status', ['cancelled', 'interrupted', 'unresolved_stopped', 'comparison_disabled'])
def test_unscored_dispositions_cannot_be_promoted_to_teaching(originals, status):
    hook, cycles = fresh_hook(originals)
    original = published(cycles[3])[0]
    # Explicit original-result contract fixture, not a new physical occurrence.
    outcome = replace(original, status=status, evidence=original.evidence if status == 'comparison_disabled' else None,
                      command_intervals=0 if status == 'cancelled' else original.command_intervals, relations=(), residuals=())
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


def without_K_cycle_fields(cycle):
    """Remove only named K disclosures for full accepted-behavior comparison.

    Outcomes, J requests, allocations, permissions, scheduler records and measured
    state are never removed. This projection is a test observer, not a code input.
    """
    data = cycle.as_dict()
    data.pop('suckle_learning_reconciliation', None)
    if 'suckle_learning_status' in data:
        data['suckle_learning_status'] = 'unimplemented_no_participation'
    for name in ('suckle_correspondence', 'suckle_attention'):
        if name in data:
            data[name]['learning_route'] = 'unimplemented_no_participation'
    return data


@pytest.mark.parametrize('case', sorted(set(SUCKLE_LATCH_CASES_V1) | set(SUCKLE_ATTENTION_CASES_V1)))
def test_K_on_off_changes_only_eligibility_not_J_H_I_behavior_or_physics(case):
    rng = random.getstate()
    _, on = collect(case, hook=True)
    _, off = collect(case, hook=False)
    assert on.local_steps == off.local_steps
    assert on.physical_samples == off.physical_samples
    assert on.final_feedback == off.final_feedback
    assert on.registered_suckle_pnm_cycles == off.registered_suckle_pnm_cycles
    assert on.registered_pnm_cycles == off.registered_pnm_cycles
    assert on.installations == off.installations
    assert on.handoff_consumptions == off.handoff_consumptions
    assert on.durable_before == on.durable_after == off.durable_before == off.durable_after
    assert tuple(without_K_cycle_fields(c) for c in on.cycles) == tuple(c.as_dict() for c in off.cycles)
    assert all(c.suckle_learning_report is not None for c in on.cycles)
    assert all(c.suckle_learning_report is None for c in off.cycles)
    on_counts = dict(on.peak_counts)
    assert {k: v for k, v in on_counts.items() if not k.startswith('suckle_learning_')} == dict(off.peak_counts)
    assert on_counts['suckle_learning_participants'] <= 8 and on_counts['suckle_learning_dispositions'] <= 32
    assert random.getstate() == rng


def test_real_F_registration_occurs_before_outer_installation_or_any_new_outcome(monkeypatch):
    trial, _ = make_trial()
    hook = trial.core.feeding_detail.suckle_learning_hook
    calls = []
    original = hook.reconcile

    def reconcile(**kwargs):
        assert trial.core.handoff.receipt.disposition == 'accepted'
        assert trial.controller.installation_count == 0
        assert trial.tick == 0 and kwargs['outcomes'] == ()
        assert kwargs['registration'] is not None
        calls.append(kwargs)
        return original(**kwargs)

    monkeypatch.setattr(hook, 'reconcile', reconcile)
    first = trial.focal_step()
    assert len(calls) == 1 and trial.controller.installation_count == 1
    participant = first.suckle_learning_report.new_participation
    assert participant.claim is first.suckle_correspondence.registration
    assert participant.claim.preview is first.calculation.navigation.application.projection
    assert participant.task is first.calculation.navigation.application.task
    assert participant.as_dict()['registration_scope'] == 'selected_authorized_not_execution'
    assert first.suckle_learning_report.as_dict()['new_action_outcome_available'] is False


def test_real_J_interpretation_is_consumed_once_at_F_without_IP_application_or_second_interpretation(monkeypatch):
    trial, _ = make_trial('competing_on')
    trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    hook = trial.core.feeding_detail.suckle_learning_hook
    question_owner = trial.core.feeding_detail.suckle_outcome_attention
    original_allocate = question_owner.allocate
    allocated = []

    def allocate(*args, **kwargs):
        result = original_allocate(*args, **kwargs)
        allocated.append(result)
        return result

    def forbidden(*_args, **_kwargs):
        pytest.fail('F or interpretation reapplied an IP or recomputed present relevance')

    monkeypatch.setattr(SeekNippleIPV1, 'apply', forbidden)
    monkeypatch.setattr(SuckleIPV1, 'apply', forbidden)
    monkeypatch.setattr(question_owner, 'allocate', allocate)
    original_reconcile = hook.reconcile

    def reconcile(**kwargs):
        assert len(allocated) == 1 and allocated[0].kind == 'interpretation'
        assert kwargs['interpretation'] is allocated[0].interpretation
        monkeypatch.setattr(question_owner, '_relevance', forbidden)
        return original_reconcile(**kwargs)

    monkeypatch.setattr(hook, 'reconcile', reconcile)
    result = trial.focal_step(visual_bid_priority=(10, 70))
    assert result.calculation.navigation.application is None and result.reservations == ()
    assert result.suckle_learning_report.dispositions[-1].status == 'accepted_no_update'
    assert result.suckle_learning_report.dispositions[-1].interpretation is allocated[0].interpretation
    assert result.suckle_learning_report.dispositions[-1].outcome is result.suckle_correspondence.outcomes[0]


def test_original_source_recipient_receives_match_with_visual_WNM():
    trial, _ = make_trial('nominal_on')
    first = trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    result = trial.focal_step(visual_bid_priority=(10, 70))
    assert result.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == 'visual_scene'
    disposition = result.suckle_learning_report.dispositions[-1]
    assert disposition.status == 'accepted_no_update'
    assert disposition.outcome.claim is first.suckle_learning_report.new_participation.claim
    assert disposition.interpretation is None
    assert disposition.outcome.claim.preview.basis.source_map_ref.map_id == 'feeding_detail'


def test_missing_current_feeding_access_does_not_erase_original_participation():
    trial, _ = make_trial('nominal_on')
    first = trial.focal_step()
    for _ in range(4):
        trial.advance_lower()
    gap = trial.focal_step(visual_input_enabled=False)
    assert not gap.feeding_detail_source.focal_accessible
    participant = gap.suckle_learning_report.pending[0]
    assert participant.claim is first.suckle_correspondence.registration
    assert participant.expires_before_cycle == 5
    for _ in range(8):
        trial.advance_lower()
    later = trial.focal_step()
    disposition, = later.suckle_learning_report.dispositions
    # H correctly cancelled unavailable-detail execution; retaining eligibility
    # does not turn that interrupted outcome into an observed successful closure.
    assert disposition.status == 'rejected_interrupted'
    assert disposition.outcome.claim is participant.claim
    assert not disposition.accepted_relations


def test_source_recipients_separate_same_map_for_seeking_and_Suckle():
    from nca8_seek_learning import SeekingLearningHookV1
    from nca8_seek_learning_demo import create_seeking_learning_trial_v1
    trial, _ = make_trial()
    first = trial.focal_step()
    seeking = create_seeking_learning_trial_v1()
    seek_first = seeking.focal_step()
    assert first.feeding_detail_source.source_map_ref == seek_first.feeding_detail_source.source_map_ref
    k = SuckleLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    f = SeekingLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    assert k.recipient_id != f.recipient_id
    before = snapshot(k)
    with pytest.raises(TypeError):
        k.reconcile(cycle_id=1, cutoff_tick=0, registration=seek_first.seeking_correspondence.registration,
                    task=seek_first.calculation.navigation.application.task)
    assert snapshot(k) == before
    with pytest.raises(TypeError):
        f.reconcile(cycle_id=1, cutoff_tick=0, registration=first.suckle_correspondence.registration,
                    task=first.calculation.navigation.application.task)


def test_full_F_visits_only_configured_recipients_without_learning_ledger_scan(monkeypatch):
    import nca8_learning_registry
    monkeypatch.setattr(nca8_learning_registry, 'learning_capabilities_v1', lambda: pytest.fail('F scanned the learning inventory'))
    trial, evidence = collect('stand_follow')
    assert any(c.learning_report is not None for c in evidence.cycles)
    assert any(c.maternal_learning_report and c.maternal_learning_report.new_participation for c in evidence.cycles)
    assert any(c.seeking_learning_report and c.seeking_learning_report.new_participation for c in evidence.cycles)
    assert any(c.suckle_learning_report and c.suckle_learning_report.new_participation for c in evidence.cycles)
    assert all(c.suckle_learning_report.as_dict()['ledger_rows_executed'] == 0 for c in evidence.cycles)
    assert trial.core.feeding_detail.learning_hook.recipient_id != trial.core.feeding_detail.suckle_learning_hook.recipient_id


@pytest.mark.parametrize('name', ['pending', 'history'])
def test_disposable_diagnostics_and_reads_do_not_extend_timers(originals, name):
    hook, _ = fresh_hook(originals)
    before = snapshot(hook)
    for _ in range(50):
        getattr(hook, name)()
    assert snapshot(hook) == before


def test_reset_closes_old_generation_and_does_not_reuse_participation():
    trial, _ = make_trial()
    first = trial.focal_step()
    old_hook = trial.core.feeding_detail.suckle_learning_hook
    claim = first.suckle_correspondence.registration
    trial.reset()
    new_hook = trial.core.feeding_detail.suckle_learning_hook
    assert old_hook is not new_hook and old_hook._closed and not old_hook.pending()
    assert new_hook.stream.generation == old_hook.stream.generation + 1
    with pytest.raises(ValueError):
        new_hook.reconcile(cycle_id=1, cutoff_tick=0, registration=claim, task=first.calculation.navigation.application.task)
    assert not new_hook.pending()
    new_first = trial.focal_step()
    assert new_first.suckle_learning_report.new_participation.claim.preview.basis.stream == new_hook.stream


def test_F_fault_closes_hook_and_cancels_accepted_handoff_without_outer_install(monkeypatch):
    trial, _ = make_trial()
    hook = trial.core.feeding_detail.suckle_learning_hook

    def fail(**_kwargs):
        raise ValueError('deliberate K boundary fault')

    monkeypatch.setattr(hook, 'reconcile', fail)
    with pytest.raises(ValueError, match='deliberate K'):
        trial.focal_step()
    assert trial.stopped and hook._closed and not hook.pending()
    assert trial.controller.installation_count == 0
    assert trial.core.handoff.receipt.disposition == 'cancelled'


def test_new_inventory_pointers_describe_real_hooks_without_promoting_learning():
    from nca8_learning_registry import learning_capabilities_v1
    rows = learning_capabilities_v1()
    row = next(x for x in rows if x.capability_id == 'L12')
    assert 'SeekingLearningHookV1.reconcile' in row.live_consumer
    assert 'SuckleLearningHookV1.reconcile' in row.live_consumer
    assert 'tests/test_nca8_suckle_learning.py' in row.test_destination
    assert row.maturity == 'eligibility_only_no_durable_rule'
    assert all(not x.as_dict()['durable_rule_implemented'] for x in rows)


def test_K_hook_waits_for_losing_J_question_and_does_not_consume_it():
    # Accepted J fixture: independent real D/I claims on a common source.
    # This proves allocation/evidence contracts, not a simultaneous physical run.
    from test_nca8_suckle_attention import simultaneous_fixture
    from nca8_feeding import FeedingDetailCandidateV1
    donor, first, cycle, session, prepared, seeking, suckle, seek_task = simultaneous_fixture()
    question = suckle.pending()[0]
    k = SuckleLearningHookV1(donor.latest_feedback.stream, cycle.feeding_detail_source.seed)
    k.reconcile(cycle_id=1, cutoff_tick=0, registration=first.suckle_correspondence.registration,
                task=first.calculation.navigation.application.task)
    selected = session.select_prepared(prepared, seeking_attention=seeking, suckle_attention=suckle)
    assert selected.seeking_outcome_allocation.kind == 'interpretation'
    assert selected.suckle_outcome_allocation.kind == 'deferred_other_interpretation'
    before_questions = suckle.pending()
    report = k.reconcile(cycle_id=cycle.commitment.cycle_id, cutoff_tick=12,
                         outcomes=cycle.suckle_correspondence.outcomes, requests=(question,))
    assert [d.status for d in report.dispositions] == ['pending_interpretation']
    assert k.pending()[0].request is question and suckle.pending() == before_questions
    assert question.expires_at_tick == 20
    session.project_selected(selected)
    for _ in range(4):
        donor.advance_lower()
    later = donor.focal_step()
    seeking.admit((), later.feeding_detail_source, seek_task, cutoff_tick=16)
    suckle.admit((), later.feeding_detail_source, later.suckle_task.task, cutoff_tick=16)
    bid = session.attention.build_bid(FeedingDetailCandidateV1(later.feeding_detail_source, 0), cycle_id=later.commitment.cycle_id)
    bid = suckle.contribute_bid(seeking.contribute_bid(bid))
    ready = session.prepare_source(donor.latest_feedback, cutoff_tick=16, competing_bids=(bid,))
    second = session.select_prepared(ready, seeking_attention=seeking, suckle_attention=suckle)
    interpretation = second.suckle_outcome_allocation.interpretation
    assert second.suckle_outcome_allocation.kind == 'interpretation' and interpretation.request is question
    # Skipped donor opportunities make this an on-time control: cycle3, not5.
    assert later.commitment.cycle_id < 5
    accepted = k.reconcile(cycle_id=later.commitment.cycle_id, cutoff_tick=16, interpretation=interpretation)
    assert [d.status for d in accepted.dispositions] == ['accepted_no_update']
    assert not k.pending() and question.expires_at_tick == 20


def test_live_J_question_can_be_interpreted_after_K_eligibility_expires_without_revival():
    from nca8_executive import AttentionRuntimeV1, NavigationRuntimeV1
    from nca8_feeding import FeedingDetailCandidateV1
    from nca8_suckle_attention import SuckleOutcomeAttentionV1
    trial, _ = make_trial('nonsealable')  # I enabled; J disabled for donor.
    first = trial.focal_step()
    k = trial.core.feeding_detail.suckle_learning_hook
    j = SuckleOutcomeAttentionV1(trial.latest_feedback.stream, first.feeding_detail_source.seed)
    for _ in range(3):
        for _ in range(4):
            trial.advance_lower()
        cycle = trial.focal_step()
    outcomes = cycle.suckle_correspondence.outcomes
    request, = j.admit(outcomes, cycle.feeding_detail_source, cycle.suckle_task.task, cutoff_tick=12)
    assert cycle.commitment.cycle_id == 4 and k.pending()[0].expires_before_cycle == 5
    # Separate recipient using exact original participation; do not mutate a live
    # owner to retroactively install a previously unprovided dependency.
    recipient = SuckleLearningHookV1(trial.latest_feedback.stream, first.feeding_detail_source.seed)
    recipient.reconcile(cycle_id=1, cutoff_tick=0, registration=first.suckle_correspondence.registration,
                        task=first.calculation.navigation.application.task)
    recipient.reconcile(cycle_id=4, cutoff_tick=12, outcomes=outcomes, requests=(request,))
    for _ in range(4):
        trial.advance_lower()
    later = trial.focal_step()
    assert later.commitment.cycle_id == 5
    j.admit((), later.feeding_detail_source, later.suckle_task.task, cutoff_tick=16)
    attention, navigation = AttentionRuntimeV1(), NavigationRuntimeV1(motor_preview_enabled=True)
    bid = attention.build_bid(FeedingDetailCandidateV1(later.feeding_detail_source, 0), cycle_id=5)
    working = navigation.update_wnm(attention.select((bid,), current_wnm=None, cycle_id=5))
    candidate = j.interpretation_candidate(working, cycle_id=5)
    navigation.allocate_outcome_interpretation(working, (candidate,), cycle_id=5, at_tick=16)
    interpretation = j.allocate(working, cycle_id=5, grant=navigation.last_decision).interpretation
    original = outcomes[0].as_dict()
    report = recipient.reconcile(cycle_id=5, cutoff_tick=16, interpretation=interpretation)
    assert [d.status for d in report.dispositions] == ['eligibility_expired', 'rejected_expired_interpretation']
    assert request.expires_at_tick == 20 and outcomes[0].as_dict() == original and not recipient.pending()
    assert report.dispositions[-1].interpretation is interpretation


@pytest.mark.parametrize('current,status', [(False, 'still_relevant'), (True, 'historical_resolved'), (None, 'unresolved_current_relevance')])
def test_actual_J_interpretation_records_present_relevance_without_changing_original_outcome(current, status):
    from test_nca8_suckle_attention import historical_fixture, admit, interpret
    _, first, cycle, outcome, owner = historical_fixture()
    source = cycle.feeding_detail_source
    # Explicit current-source control; only J performs its relevance calculation.
    source = replace(source, oral_feedback=replace(source.oral_feedback, oral_seal=replace(source.oral_feedback.oral_seal, sealed=current)))
    request, = admit(owner, cycle, (outcome,), source)
    _, _, allocation = interpret(owner, source)
    assert allocation.interpretation.status == status
    k = SuckleLearningHookV1(source.stream, source.seed)
    k.reconcile(cycle_id=1, cutoff_tick=0, registration=first.suckle_correspondence.registration,
                task=first.calculation.navigation.application.task)
    saved = outcome.as_dict()
    report = k.reconcile(cycle_id=source.applied_cycle, cutoff_tick=12, outcomes=(outcome,),
                         requests=(request,), interpretation=allocation.interpretation)
    expected = 'pending_unresolved_interpretation' if current is None else 'accepted_no_update'
    assert report.dispositions[-1].status == expected and outcome.as_dict() == saved and outcome.status == 'mismatch'
    assert dict(report.dispositions[-1].accepted_relations).get('seal') == (None if current is None else 'mismatch')


@pytest.mark.parametrize('mode', ['missing_visual', 'missing_seal', 'narrowed', 'no_capability', 'comparison_off'])
def test_independently_measured_or_nonapplied_evidence_has_honest_K_disposition(mode):
    if mode == 'missing_visual':
        from test_nca8_suckle_attention import historical_fixture
        _, first, cycle, outcome, _ = historical_fixture(lambda ep: replace(ep, observation=None))
        hook = SuckleLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
        hook.reconcile(cycle_id=1, cutoff_tick=0, registration=first.suckle_correspondence.registration,
                       task=first.calculation.navigation.application.task)
        report = hook.reconcile(cycle_id=cycle.commitment.cycle_id, cutoff_tick=12, outcomes=(outcome,))
        assert report.dispositions[-1].status == 'rejected_unknown'
        return
    _, evidence = collect(mode)
    reports = [c.suckle_learning_report for c in evidence.cycles]
    statuses = [d.status for r in reports for d in r.dispositions]
    expected = {'missing_seal': 'rejected_unknown', 'narrowed': 'accepted_no_update',
                'no_capability': 'not_applied', 'comparison_off': 'comparison_disabled_no_teaching'}[mode]
    assert expected in statuses
    if mode in {'no_capability', 'comparison_off'}:
        assert all(r.new_participation is None for r in reports)
    if mode == 'narrowed':
        accepted = next(d for r in reports for d in r.dispositions if d.status == 'accepted_no_update')
        assert accepted.outcome.claim.unevaluable_relations
        assert set(dict(accepted.accepted_relations)) <= set(accepted.outcome.claim.compatible_relations)
        assert not (set(dict(accepted.accepted_relations)) & set(accepted.outcome.claim.unevaluable_relations))


def test_missing_endpoint_and_long_I_arrival_window_do_not_extend_K_eligibility():
    from test_nca8_suckle_attention import historical_fixture, advance
    trial, first, cycle, outcome, _ = historical_fixture(lambda _ep: None)
    assert outcome is None
    hook = SuckleLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    claim = first.suckle_correspondence.registration
    hook.reconcile(cycle_id=1, cutoff_tick=0, registration=claim, task=first.calculation.navigation.application.task)
    assert claim.expires_at_tick == 16
    hook.reconcile(cycle_id=5, cutoff_tick=12)
    assert not hook.pending()  # Independent cycle clock; not the claim's physical window.
    advance(trial, 8)
    at20 = trial.focal_step()
    outcome, = at20.suckle_correspondence.outcomes
    assert outcome.status == 'expired_unresolved' and outcome.evidence is None
    report = hook.reconcile(cycle_id=6, cutoff_tick=20, outcomes=(outcome,))
    assert report.dispositions[-1].status == 'rejected_expired_eligibility' and report.dispositions[-1].outcome is outcome


@pytest.mark.parametrize('case', ['nominal_on', 'competing_on', 'comparison_off'])
def test_diagnostic_capacity_and_trace_eviction_do_not_change_eligibility_or_behavior(case):
    _, one = collect(case, diagnostic_capacity=1, trace_capacity=8)
    _, full = collect(case, diagnostic_capacity=32, trace_capacity=256)
    assert one.cycles == full.cycles
    assert one.local_steps == full.local_steps and one.physical_samples == full.physical_samples
    assert one.durable_after == full.durable_after
    assert all(c.suckle_learning_report.as_dict()['durable_learning_updates'] == 0 for c in one.cycles)


def test_request_expiry_is_checked_even_while_K_eligibility_is_live(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    event = cycles[3]
    result = interpreted(event)
    hook.reconcile(cycle_id=2, cutoff_tick=12, outcomes=published(event), requests=event.suckle_attention.created)
    before = snapshot(hook)
    # Explicit late-result contract fixture. A different cadence leaves K live,
    # but the J question expires at20 independently of K's expiry at cycle5.
    late = replace(result, cycle_id=3, cutoff_tick=20)
    with pytest.raises(ValueError, match='expired request'):
        hook.reconcile(cycle_id=3, cutoff_tick=20, interpretation=late)
    assert snapshot(hook) == before and hook.pending()[0].expires_before_cycle == 5


def test_copied_request_cannot_replace_a_still_pending_original_dependency(originals):
    hook, cycles = fresh_hook(originals, 'competing_on')
    cycle = cycles[3]
    hook.reconcile(cycle_id=2, cutoff_tick=12, outcomes=published(cycle), requests=cycle.suckle_attention.created)
    result = interpreted(cycle)
    source = cycles[4].feeding_detail_source
    copied = replace(result, cycle_id=source.applied_cycle, cutoff_tick=source.cutoff_tick,
                     current_source=source, request=replace(result.request))
    before = snapshot(hook)
    with pytest.raises(ValueError, match='copied suckle request'):
        hook.reconcile(cycle_id=source.applied_cycle, cutoff_tick=source.cutoff_tick, interpretation=copied)
    assert snapshot(hook) == before


def test_current_action_cannot_offer_its_own_future_outcome_at_same_F(originals):
    _, cycles = originals['nominal_on']
    first = cycles[0]
    hook = SuckleLearningHookV1(first.feeding_detail_source.stream, first.feeding_detail_source.seed)
    before = snapshot(hook)
    with pytest.raises(ValueError, match='just-issued'):
        hook.reconcile(cycle_id=1, cutoff_tick=12, outcomes=published(cycles[3]))
    assert snapshot(hook) == before


def test_foreign_request_or_interpretation_domain_is_rejected(originals):
    from nca8_seek_learning_demo import create_seeking_learning_trial_v1
    trial = create_seeking_learning_trial_v1('competing_on')
    trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    earlier = trial.focal_step()
    hook, cycles = fresh_hook(originals, 'competing_on')
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, outcomes=published(cycles[3]), requests=earlier.seeking_attention.created)
    assert snapshot(hook) == before
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=4, cutoff_tick=12, interpretation=earlier.seeking_attention.allocation.interpretation)
    assert snapshot(hook) == before


def test_whole_batch_failure_keeps_expiry_registration_and_previous_results_unmodified(originals):
    hook, cycles = fresh_hook(originals)
    original = published(cycles[3])[0]
    invalid = replace(original, number=original.number + 1, evidence=None)
    before = snapshot(hook)
    with pytest.raises(ValueError):
        hook.reconcile(cycle_id=5, cutoff_tick=12, outcomes=(original, invalid))
    assert snapshot(hook) == before  # Even due expiry was not partially applied.


def test_hook_disabled_source_and_old_profile_export_are_unchanged():
    trial = create_suckle_trial_v1(outcomes_enabled=True, outcome_attention_enabled=True)
    frame = trial.focal_step()
    assert trial.core.feeding_detail.suckle_learning_hook is None
    assert frame.suckle_learning_report is None
    assert 'suckle_learning_reconciliation' not in frame.as_dict()
    assert 'eligibility_lifetime_cycles' not in SuckleProfileV1().as_dict()
    assert frame.suckle_attention.as_dict()['learning_route'] == 'unimplemented_no_participation'


def test_K_callback_really_runs_inside_scheduler_F_and_does_not_scan_diagnostics(monkeypatch):
    from nca8_contracts import CyclePhase
    trial, _ = make_trial()
    hook = trial.core.feeding_detail.suckle_learning_hook
    entered = []
    scheduler = trial.core.scheduler
    original_finish = scheduler.phase_f_finish
    original_reconcile = hook.reconcile

    def finish(cycle_id, trace, *, reconcile=None):
        assert reconcile is not None
        entered.append(cycle_id)
        return original_finish(cycle_id, trace, reconcile=reconcile)

    def reconcile(**kwargs):
        assert entered == [kwargs['cycle_id']]
        assert scheduler._last_phase_value == int(CyclePhase.LEARNING_SCHEDULE)
        return original_reconcile(**kwargs)

    monkeypatch.setattr(scheduler, 'phase_f_finish', finish)
    monkeypatch.setattr(hook, 'reconcile', reconcile)
    monkeypatch.setattr(hook, 'history', lambda: pytest.fail('F used diagnostic history as input'))
    first = trial.focal_step()
    assert first.suckle_learning_report.new_participation is not None
    events = trial.core.trace.snapshot()
    channels = [e.channel for e in events]
    assert channels.index('hierarchy_handoff') < channels.index('hierarchy_suckle_learning_hook')
    assert channels.index('hierarchy_suckle_learning_hook') < channels.index('hierarchy_close') < channels.index('hierarchy_consumed')
