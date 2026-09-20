"""Live no-learning neutrality, causal timing, routing fixtures, menus and exports."""

from dataclasses import replace
import ast
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_learning_demo as demo
from nca8_contracts import CyclePhase
from nca8_hierarchy import IntegratedRightingTrialV1
from nca8_hierarchy_demo import run_hierarchy_review_menu_v1
from nca8_outcome_attention_demo import run_outcome_attention_v1
from nca8_runtime import Nca8SessionV1
from nca8_scheduler import Nca8DeterministicSchedulerV1
from nca8_trace import Nca8TraceBufferV1

ROOT = Path(__file__).resolve().parents[1]


def focal_records(result):
    return tuple(focal for focal, _ in result.intervals) + (result.final_cycle,)


def events(result):
    return tuple(event for focal in focal_records(result) if focal.learning_report is not None
                 for event in focal.learning_report.dispositions)


@pytest.mark.parametrize('case', demo.LEARNING_HOOK_CASES_V1)
def test_live_profiles_have_fixed_physical_horizon_and_real_owner_bounds(case):
    before = random.getstate()
    result = demo.run_learning_hook_v1(case)
    assert result.metrics()['physical_ticks'] == 80
    assert len(result.physical_samples) == 81
    assert result.metrics()['durable_source_unchanged'] and result.fixed_configuration_unchanged
    assert result.metrics()['durable_learning_updates'] == 0
    assert not result.bound_violations
    assert random.getstate() == before
    assert all(focal.learning_report is not None for focal in focal_records(result)) == result.hook_enabled


@pytest.mark.parametrize('prefix', ['nominal', 'competing'])
def test_hook_on_off_preserves_all_cognitive_motor_and_physical_records(prefix):
    on, off = (demo.run_learning_hook_v1(f'{prefix}_{suffix}') for suffix in ('on', 'off'))
    assert on.physical_samples == off.physical_samples
    assert on.final_feedback == off.final_feedback
    for left, right in zip(focal_records(on), focal_records(off)):
        left_dict = left.as_dict()
        left_dict.pop('learning_reconciliation')
        assert left_dict == right.as_dict()
    assert tuple(lower for _, lower in on.intervals) == tuple(lower for _, lower in off.intervals)
    assert events(on) and not events(off)
    # The disabled hook comparison is still the accepted 1G-B Attention-on profile.
    retained = run_outcome_attention_v1(f'{prefix}_on')
    assert tuple(focal.as_dict() for focal in focal_records(off)) == (
        tuple(focal.as_dict() for focal, _ in retained.intervals) + (retained.final_cycle.as_dict(),))
    assert off.physical_samples == retained.physical_samples


def test_f_callback_runs_in_actual_f_after_handoff_and_before_close_or_install(monkeypatch):
    trial = IntegratedRightingTrialV1(task_outcomes_enabled=True, task_learning_hook_enabled=True)
    original = trial.core.cognition.sensory.learning_hook.reconcile
    seen = []
    def spy(**kwargs):
        seen.append((trial.core.scheduler._last_phase_value, trial.core.scheduler.last_completed_cycle,
                     trial.core.handoff.receipt.disposition, trial.controller.installation_count, trial.tick))
        return original(**kwargs)
    monkeypatch.setattr(trial.core.cognition.sensory.learning_hook, 'reconcile', spy)
    focal = trial.focal_step()
    assert seen == [(int(CyclePhase.LEARNING_SCHEDULE), 0, 'accepted', 0, 0)]
    assert trial.core.scheduler.last_completed_cycle == 1
    assert trial.controller.installation_count == 1
    channels = [event.channel for event in trial.core.trace.snapshot()]
    assert channels.index('hierarchy_handoff') < channels.index('hierarchy_learning_hook') < channels.index('hierarchy_close')
    assert channels.index('hierarchy_close') < channels.index('hierarchy_installed')
    assert focal.learning_report.offered_outcomes == 0 and trial.tick == 0


def test_routing_fixture_reaches_a_while_b_is_focal_and_a_is_unavailable(monkeypatch):
    def no_world(*_args, **_kwargs):
        raise AssertionError('routing fixture must not construct physical world')
    monkeypatch.setattr('nca8_hierarchy.MotorWorldV1', no_world)
    records = demo.run_learning_routing_fixture_v1()
    first, final = records[0], records[-1]
    assert all(f.calculation.attention.selected_bid.candidate_id == 'fixture:competing_source' for f in records[1:])
    assert all(f.calculation.source.activation == 0 and not f.calculation.source.motor_support.current for f in records[1:])
    event = final.learning_report.dispositions[0]
    assert event.status == 'accepted_no_update'
    assert event.outcome.registration is first.claim_registration
    assert final.learning_report.recipient_id == first.learning_report.recipient_id
    assert 'posture_support' in final.learning_report.recipient_id
    assert final.learning_report.new_participation is None
    assert event.outcome.evidence.event_tick == 4 and event.outcome.evidence.available_tick == 5
    assert 'NO PHYSICAL WORLD STEPS' in demo.render_learning_routing_fixture_v1(records)


def test_same_endpoint_cannot_restore_expired_participation():
    ordinary = demo.run_learning_routing_fixture_v1()
    expired = demo.run_learning_routing_fixture_v1(expired=True)
    before_expiry, after_expiry = expired[-2], expired[-1]
    assert before_expiry.calculation.cutoff_tick == 4
    assert before_expiry.learning_report.dispositions[0].status == 'eligibility_expired'
    assert before_expiry.claim_outcomes == ()
    assert after_expiry.learning_report.dispositions[0].status == 'rejected_expired_eligibility'
    assert ordinary[-1].claim_outcomes[0].as_dict() == after_expiry.claim_outcomes[0].as_dict()
    assert not after_expiry.learning_report.pending


def test_interpreted_teaching_uses_existing_d_allocation_and_no_new_task():
    result = demo.run_learning_hook_v1('competing_on')
    interpreted = []
    for focal in focal_records(result):
        for event in focal.learning_report.dispositions:
            if event.status == 'accepted_no_update' and event.interpretation is not None:
                interpreted.append((focal, event))
                allocation = focal.calculation.outcome_allocation
                assert allocation.kind == 'interpretation'
                assert event.interpretation is allocation.interpretation
                assert event.interpretation.cycle_id == focal.commitment.cycle_id
                assert focal.claim_registration is None and not focal.reservations
                assert focal.commitment.selected_primitive_id is None and focal.commitment.pnm_id is None
    assert interpreted
    assert any(event.interpretation.status == 'corrected_historical_discrepancy' for _, event in interpreted)


def test_unresolved_or_protected_interpretation_never_earns_positive_teaching():
    for case in ('unresolved_current', 'protected_competitor'):
        result = demo.run_learning_hook_v1(case)
        pending = {event.pnm_id for event in events(result) if event.status in {'pending_interpretation', 'pending_unresolved_interpretation'}}
        expired = {event.pnm_id for event in events(result) if event.status == 'eligibility_expired'}
        assert pending & expired
        assert not any(event.status == 'accepted_no_update' and event.pnm_id in expired for event in events(result))


def test_narrowing_accepts_only_unchanged_compatible_forecast_relations():
    result = demo.run_learning_hook_v1('narrowed')
    narrowed = [event for event in events(result) if event.outcome and event.outcome.registration.unevaluable_relations]
    assert narrowed
    for event in narrowed:
        compatible = event.outcome.registration.compatible_relations
        assert all(name in compatible for name, _ in event.accepted_relations)
        assert all(name not in event.outcome.registration.unevaluable_relations for name, _ in event.accepted_relations)


def test_veto_is_not_applied_not_executed_learning_failure():
    result = demo.run_learning_hook_v1('veto')
    assert result.metrics()['nonnull_commands'] == 0 and result.metrics()['new_participations'] == 0
    assert {event.status for event in events(result)} == {'not_applied'}
    assert all(event.outcome is None for event in events(result))


def test_final_pending_claim_is_not_cleared_by_fake_extra_physical_time():
    result = demo.run_learning_hook_v1('nominal_on')
    final = result.final_cycle.learning_report
    assert len(final.pending) == 1
    part = final.pending[0]
    assert part.registration.due_tick == 80 and part.outcome is None
    assert part.created_cycle < final.cycle_id < part.expires_before_cycle
    assert result.metrics()['task_status'] == 'budget_exhausted'


def test_faster_polling_changes_eligibility_time_not_its_four_cycle_definition():
    result = demo.run_learning_hook_v1('fast_cadence')
    assert result.metrics()['focal_reads'] == 81
    assert result.metrics()['teaching_dispositions']['eligibility_expired'] > 0
    assert result.final_cycle.calculation.task.status == 'budget_exhausted'
    assert result.final_cycle.calculation.task.applications <= 20
    for focal in focal_records(result):
        part = focal.learning_report.new_participation
        if part is not None:
            assert part.expires_before_cycle - part.created_cycle == 4


def test_delayed_evidence_still_reaches_source_without_currentness():
    result = demo.run_learning_hook_v1('delayed_feedback')
    admitted = [(f, e) for f in focal_records(result) for e in f.learning_report.dispositions if e.status == 'accepted_no_update']
    assert admitted
    assert any(not focal.calculation.source.motor_support.current for focal, _ in admitted)
    assert all(event.outcome.evidence.available_tick - event.outcome.evidence.event_tick == 4 for _, event in admitted)


def test_assisted_completion_does_not_prove_action_credit_or_learned_competence():
    result = demo.run_learning_hook_v1('assisted')
    assert result.metrics()['task_status'] == 'completed'
    complete = next(f for f in focal_records(result) if f.task_outcome.completion_supported)
    assert complete.calculation.cutoff_tick == 32
    assert result.metrics()['causal_action_credit'] == 'uncertain'
    assert all(event.as_dict()['durable_learning_updates'] == 0 for event in events(result))


@pytest.mark.parametrize('case', ['nominal_on', 'unresolved_current', 'protected_competitor'])
def test_trace_and_history_truncation_do_not_change_live_hook_or_body(case):
    tiny = demo.run_learning_hook_v1(case, trace_capacity=1, diagnostic_capacity=1)
    full = demo.run_learning_hook_v1(case, trace_capacity=4096, diagnostic_capacity=32)
    assert tiny.intervals == full.intervals and tiny.final_cycle == full.final_cycle
    assert tiny.physical_samples == full.physical_samples
    assert tiny.metrics() == full.metrics()
    assert dict(tiny.peak_counts)['learning_dispositions'] <= 1


@pytest.mark.parametrize('case', ['nominal_on', 'competing_on'])
def test_renders_and_exports_never_rerun_cognition_or_change_rng(case, monkeypatch):
    result = demo.run_learning_hook_v1(case)
    before = json.dumps(result.as_dict(), sort_keys=True)
    rng = random.getstate()
    def fail(*_args, **_kwargs):
        raise AssertionError('render attempted to run cognition')
    monkeypatch.setattr(demo, 'run_learning_hook_v1', fail)
    demo.render_learning_hook_v1(result)
    demo.render_learning_hook_v1(result, detail=True)
    demo.render_learning_hook_summary_v1((result,))
    assert json.dumps(result.as_dict(), sort_keys=True) == before and random.getstate() == rng


def test_opening_menu_and_reading_ledger_run_no_trial(monkeypatch, capsys):
    inputs = iter(['7', ''])
    monkeypatch.setattr(demo.cca8_cli, 'read_menu_input_v1', lambda: next(inputs))
    monkeypatch.setattr(demo, 'run_learning_hook_v1', lambda *_args, **_kwargs: pytest.fail('unexpected physical trial'))
    demo.run_learning_review_menu_v1()
    output = capsys.readouterr().out
    assert 'L01' in output and 'L25' in output and 'eligibility_only' in output


@pytest.mark.parametrize('choice,expected', [('2', 4), ('4', 3), ('5', 3), ('6', 2), ('8', 1)])
def test_menu_routes_share_the_common_live_experiments(monkeypatch, choice, expected):
    inputs = iter(['bad', choice, ''])
    monkeypatch.setattr(demo.cca8_cli, 'read_menu_input_v1', lambda: next(inputs))
    called = []
    monkeypatch.setattr(demo, 'run_learning_hook_v1', lambda case: called.append(case) or object())
    monkeypatch.setattr(demo, 'render_learning_hook_summary_v1', lambda _results: 'summary')
    monkeypatch.setattr(demo, 'render_learning_hook_v1', lambda _result, **_kwargs: 'detail')
    demo.run_learning_review_menu_v1()
    assert len(called) == expected


def test_nested_menu_callback_retains_the_existing_a0_session(monkeypatch):
    import nca8_menu
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    inputs = iter(['8', '8', '', '', ''])
    monkeypatch.setattr(demo.cca8_cli, 'read_menu_input_v1', lambda: next(inputs))
    result = nca8_menu.run_nca8_experimental_menu_v1(session)
    assert result is session
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


@pytest.mark.parametrize('bad', [False, 'menu', 2])
def test_bad_parent_menu_callback_rejected_before_reading(bad):
    with pytest.raises(TypeError):
        run_hierarchy_review_menu_v1(learning_menu=bad)


@pytest.mark.parametrize('arguments', [('--learning-hook', 'competing_on'), ('--learning-routing',), ('--learning-ledger',)])
def test_permanent_script_works_outside_repository_and_json_is_real(tmp_path, arguments):
    command = [sys.executable, str(ROOT / 'scripts/review_nca8_hierarchy.py'), *arguments, '--json']
    result = subprocess.run(command, cwd=tmp_path, capture_output=True, text=True, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    assert payload
    if '--learning-hook' in arguments:
        assert payload == [demo.run_learning_hook_v1('competing_on').as_dict()]
    elif '--learning-routing' in arguments:
        assert payload['evidence_kind'] == 'canonical_replay_no_world_steps'
        assert len(payload['fixtures']) == 2
    else:
        assert len(payload) == 25 and not any(row['durable_rule_implemented'] for row in payload)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize('arguments', [('--learning-hook', 'bad'), ('--learning-hook', '--outcomes'),
                                      ('--learning-ledger', '--learning-routing'), ('--learning-routing', '--case', 'nominal')])
def test_cli_refuses_ambiguous_or_unknown_selectors(arguments):
    result = subprocess.run([sys.executable, str(ROOT / 'scripts/review_nca8_hierarchy.py'), *arguments],
                            capture_output=True, text=True, check=False)
    assert result.returncode == 2


def test_summary_discloses_bad_bounds_or_changed_durable_state():
    result = demo.run_learning_hook_v1()
    bad = replace(result, peak_counts=(('learning_participants', 9),), durable_signature_after='changed')
    text = demo.render_learning_hook_summary_v1((bad,))
    assert "'durable_source_unchanged': False" in text
    assert "bound violations=['learning_participants']" in text


def test_learning_core_never_imports_ledger_or_calls_physical_or_executive_apis():
    tree = ast.parse((ROOT / 'nca8_learning.py').read_text())
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            assert node.module not in {'nca8_learning_registry', 'nca8_learning_demo', 'cca8_env', 'cca8_support_world'}
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr not in {'step', 'apply', 'commit', 'select', 'observe', 'install', 'install_authorized', 'allocate'}


def phase_e_scheduler():
    scheduler = Nca8DeterministicSchedulerV1()
    trace = Nca8TraceBufferV1()
    scheduler.phase_a_poll_and_stage(1, (), trace)
    scheduler.phase_b_freeze_eligible(1, trace)
    scheduler.phase_c_apply_frozen(1, trace)
    scheduler.enter_runtime_phase(1, CyclePhase.FOCAL_COMMITMENT)
    scheduler.enter_runtime_phase(1, CyclePhase.PROJECT_DISPATCH)
    return scheduler, trace


def test_scheduler_optional_callback_executes_once_in_f_before_retirement():
    scheduler, trace = phase_e_scheduler()
    seen = []
    def callback():
        seen.append((scheduler._last_phase_value, scheduler.last_completed_cycle))
    snapshot = scheduler.phase_f_finish(1, trace, reconcile=callback)
    assert seen == [(6, 0)] and scheduler.last_completed_cycle == 1
    assert snapshot.phases == tuple(CyclePhase)


def test_scheduler_callback_failure_cannot_be_retried_or_close_cycle():
    scheduler, trace = phase_e_scheduler()
    seen = []
    def callback():
        seen.append(1)
        raise ValueError('deliberate callback failure')
    with pytest.raises(ValueError):
        scheduler.phase_f_finish(1, trace, reconcile=callback)
    assert scheduler.last_completed_cycle == 0
    with pytest.raises((ValueError, RuntimeError)):
        scheduler.phase_f_finish(1, trace, reconcile=callback)
    assert seen == [1]


@pytest.mark.parametrize('bad', [False, 'f', 1])
def test_invalid_f_callback_does_not_enter_the_phase(bad):
    scheduler, trace = phase_e_scheduler()
    with pytest.raises(TypeError):
        scheduler.phase_f_finish(1, trace, reconcile=bad)
    assert scheduler._last_phase_value == 5
    assert scheduler.phase_f_finish(1, trace).phases == tuple(CyclePhase)


def test_shared_review_bids_are_exact_readonly_fixture_inputs():
    from nca8_outcome_attention_demo import outcome_attention_review_bids_v1
    from nca8_righting_demo import competing_preview_bid_v1
    before = random.getstate()
    expected = replace(competing_preview_bid_v1(5), novelty_or_ambiguity_rank=10, protected_safety_rank=0)
    assert outcome_attention_review_bids_v1('competing_on', cycle=5, tick=16) == (expected,)
    assert outcome_attention_review_bids_v1('maintain_on', cycle=5, tick=16) == (expected,)
    assert outcome_attention_review_bids_v1('nominal_on', cycle=5, tick=16) == ()
    assert outcome_attention_review_bids_v1('protected_competitor', cycle=5, tick=16)[0].protected_safety_rank == 1
    assert random.getstate() == before


@pytest.mark.parametrize('case,cycle,tick', [(None, 1, 0), ('', 1, 0), ('nominal_on', True, 0),
                                          ('nominal_on', 1, 81), ('nominal_on', 82, 0)])
def test_shared_review_bids_reject_invalid_fixture_clock(case, cycle, tick):
    from nca8_outcome_attention_demo import outcome_attention_review_bids_v1
    with pytest.raises(ValueError):
        outcome_attention_review_bids_v1(case, cycle=cycle, tick=tick)
