"""Live F ordering, causal noninterference, lifecycle and menu/CLI review tests."""
from __future__ import annotations

import ast
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import cca8_run
from cca8_support_world import MotorWorldV1
import nca8_feeding_demo
from nca8_seek_learning import SeekingLearningHookV1
import nca8_seek_learning_demo as demo
from nca8_seek_nipple_demo import collect_seek_nipple_evidence_v1
from nca8_seek_outcomes import validate_seeking_outcome_v1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope='module')
def results():
    return {case: demo.run_seeking_learning_v1(case) for case in demo.SEEKING_LEARNING_CASES_V1}


@pytest.mark.parametrize('case', demo.SEEKING_LEARNING_CASES_V1)
def test_every_declared_case_has_complete_measured_evidence(results, case):
    result = results[case]
    assert result.review_status == 'PASS', result.checks()
    assert len(result.checks()) == 19 and not result.bound_violations
    json.dumps(result.as_dict(), allow_nan=False)
    assert result.evidence.durable_before == result.evidence.durable_after


@pytest.mark.parametrize('pair', [('nominal_on', 'nominal_off'), ('competing_on', 'competing_off'), ('stand_follow', 'stand_follow_off')])
def test_hook_changes_only_participation_not_complete_cognitive_or_physical_path(results, pair):
    on, off = (results[name].evidence for name in pair)
    assert on.profile.physical == off.profile.physical and on.profile.oral == off.profile.oral and on.profile.planar == off.profile.planar
    assert on.local_steps == off.local_steps
    assert on.physical_samples == off.physical_samples and on.final_feedback == off.final_feedback
    assert on.durable_before == off.durable_before == on.durable_after == off.durable_after
    assert on.registered_pnm_cycles == off.registered_pnm_cycles
    for a, b in zip(on.cycles, off.cycles, strict=True):
        assert a.commitment == b.commitment
        assert a.calculation == b.calculation
        assert a.feeding_detail_source == b.feeding_detail_source and a.seeking_task == b.seeking_task
        assert a.receipt == b.receipt and a.reservations == b.reservations
        assert a.seeking_correspondence.outcomes == b.seeking_correspondence.outcomes
        assert a.seeking_correspondence.registration == b.seeking_correspondence.registration
        if a.seeking_attention is not None:
            assert a.seeking_attention.created == b.seeking_attention.created
            assert a.seeking_attention.allocation == b.seeking_attention.allocation
        assert a.seeking_learning_report is not None and b.seeking_learning_report is None


def test_new_participation_runs_inside_F_before_outer_consumption_or_movement(monkeypatch):
    trial = demo.create_seeking_learning_trial_v1()
    old = SeekingLearningHookV1.reconcile
    seen = []

    def observe(hook, **kwargs):
        assert trial.tick == 0 and trial.handoff_consumptions == 0
        assert trial.controller.installation_count == 0
        assert trial.core.handoff.receipt.disposition == 'accepted'
        assert trial.core.scheduler.last_completed_cycle == 0
        seen.append(kwargs)
        return old(hook, **kwargs)

    monkeypatch.setattr(SeekingLearningHookV1, 'reconcile', observe)
    result = trial.focal_step()
    assert len(seen) == 1 and seen[0]['outcomes'] == ()
    assert result.seeking_learning_report.new_participation.outcome is None
    assert trial.controller.installation_count == 1 and trial.tick == 0


def test_matching_endpoint_reaches_original_owner_when_visual_source_is_focal(results):
    cycle = next(c for c in results['nonfocal'].evidence.cycles if c.calculation.cutoff_tick == 12)
    assert cycle.calculation.navigation.wnm.primary_source_state.source_map_ref.map_id == 'visual_scene'
    disposition, = cycle.seeking_learning_report.dispositions
    assert disposition.status == 'accepted_no_update'
    assert disposition.outcome.claim.preview.basis.source_map_ref.map_id == 'feeding_detail'


def test_old_endpoint_can_reconcile_with_current_feeding_access_absent():
    trial = demo.create_seeking_learning_trial_v1()
    trial.focal_step()
    for _ in range(12):
        trial.advance_lower()
    before_physics = trial.observer_oral_body
    # Explicit core-input routing fixture: keep real historical acquisitions,
    # while the latest focal visual product is unavailable. This makes no new
    # physical call and does not claim general Ready/offloading implementation.
    cycle = trial.core.run_cycle(trial.latest_feedback, cutoff_tick=12, visual_observation=None,
                                 local_reports=trial.controller.reports, local_events=trial.controller.events,
                                 seeking_intervals=tuple(trial._seeking_intervals))
    assert not cycle.feeding_detail_source.focal_accessible
    assert cycle.seeking_learning_report.dispositions[0].status == 'accepted_no_update'
    assert cycle.seeking_learning_report.dispositions[0].outcome.evidence.feedback.event_tick == 8
    assert trial.observer_oral_body == before_physics and trial.tick == 12


def test_missing_entire_visual_interval_batch_is_not_the_same_as_missing_current_product(results):
    item = results['unavailable_source']
    assert not any(d.status == 'accepted_no_update' for d in item.dispositions())
    assert any(d.status == 'rejected_unknown' for d in item.dispositions())


def test_attention_off_keeps_mismatch_and_physics_but_cannot_teach_for_free(results):
    result = results['attention_off']
    assert result.metrics()['disposition_counts']['pending_interpretation'] == 1
    assert result.metrics()['disposition_counts']['eligibility_expired'] == 1
    assert not result.metrics()['accepted_ticks']
    assert result.evidence.local_steps == results['competing_on'].evidence.local_steps
    assert result.evidence.physical_samples == results['competing_on'].evidence.physical_samples


def test_history_resolved_still_accepts_original_mismatch_not_rewritten_match(results):
    accepted = [d for d in results['historical_resolved'].dispositions() if d.status == 'accepted_no_update']
    assert accepted[0].outcome.status == 'mismatch'
    assert accepted[0].interpretation.status == 'historical_resolved'
    assert ('separation', 'mismatch') in accepted[0].accepted_relations


def test_narrowed_contributions_teach_only_their_original_compatible_subset(results):
    accepted = [d for d in results['narrowed'].dispositions() if d.status == 'accepted_no_update']
    assert accepted[0].accepted_relations == (('detail_anchor', 'matched'),)
    assert accepted[-1].outcome.claim.unevaluable_relations == ()
    assert len(accepted[-1].accepted_relations) == 3
    for item in accepted:
        assert all(n in item.outcome.claim.compatible_relations for n, _ in item.accepted_relations)


def test_no_surface_can_match_geometry_without_touch_or_nourishment(results):
    a, b = results['nominal_on'], results['no_surface']
    assert a.metrics()['accepted_original_statuses'] == b.metrics()['accepted_original_statuses'] == ['matched']
    assert a.metrics()['first_physical_touch_tick'] == 4
    assert b.metrics()['first_physical_touch_tick'] is None
    assert all('contact' not in dict(d.accepted_relations) for d in b.dispositions())


@pytest.mark.parametrize('case', ['dropout', 'cancelled', 'delayed', 'no_capability', 'comparison_off'])
def test_unsupported_teaching_does_not_become_an_update(results, case):
    assert not results[case].metrics()['accepted_ticks']
    assert results[case].metrics()['durable_learning_updates'] == 0


def test_fast_focal_cadence_expires_eligibility_without_erasing_matching_claim(results):
    result = results['cadence_1']
    assert result.metrics()['disposition_counts']['rejected_expired_eligibility'] == 2
    assert any(d.outcome is not None and d.outcome.status == 'matched' for d in result.dispositions())
    assert result.evidence.profile.horizon_ticks == results['cadence_8'].evidence.profile.horizon_ticks == 64


def test_all_three_domain_hooks_share_real_F_without_another_focal_operation(results):
    result = results['stand_follow_drift']
    assert result.metrics()['F_calls'] == result.metrics()['righting_F_calls'] == result.metrics()['maternal_F_calls'] == 41
    assert all(dict(result.checks())[name] for name in ('single_demanding_operation', 'no_durable_or_ledger_execution'))
    d = next(d for d in result.dispositions() if d.cutoff_tick == 112 and d.status == 'accepted_no_update')
    assert d.interpretation is not None and d.outcome.status == 'mismatch'


@pytest.mark.parametrize('case', ['competing_on', 'stand_follow_drift'])
@pytest.mark.parametrize('capacity', [1, 8])
def test_trace_and_diagnostic_capacity_do_not_change_complete_causal_evidence(results, case, capacity):
    reference = results[case]
    small = demo.run_seeking_learning_v1(case, trace_capacity=capacity, diagnostic_capacity=capacity)
    assert small.review_status == 'PASS'
    assert small.evidence.cycles == reference.evidence.cycles
    assert small.evidence.local_steps == reference.evidence.local_steps
    assert small.evidence.physical_samples == reference.evidence.physical_samples
    assert small.reports() == reference.reports()
    assert len(small.retained_dispositions) <= capacity


def test_render_and_detached_export_do_not_rerun_or_change_rng(results, monkeypatch):
    result = results['competing_on']
    prior, rng = result.as_dict(), random.getstate()
    monkeypatch.setattr(MotorWorldV1, 'step', lambda *a, **k: pytest.fail('inspection stepped physics'))
    assert demo.render_seeking_learning_v1(result)
    assert demo.render_seeking_learning_v1(result, detail=True)
    changed = result.as_dict(); changed['cycles'].clear()
    assert result.as_dict() == prior and random.getstate() == rng


@pytest.mark.parametrize('field', ['cycles', 'local_steps', 'physical_samples', 'peak_counts', 'durable_after', 'handoff_consumptions'])
def test_tampered_or_missing_evidence_cannot_pass(results, field):
    result = results['nominal_on']
    value = 'changed' if field == 'durable_after' else -1 if field == 'handoff_consumptions' else ()
    altered = replace(result, evidence=replace(result.evidence, **{field: value}))
    assert altered.review_status == 'FAIL'


@pytest.mark.parametrize('bad', [None, True, 0, [], '', 'NOMINAL_ON', 'typo'])
def test_unknown_selector_refuses_before_construction(bad):
    with pytest.raises(ValueError):
        demo.create_seeking_learning_trial_v1(bad)


@pytest.mark.parametrize('bad', [None, 0, 1, 'yes'])
def test_display_option_is_boolean(results, bad):
    with pytest.raises(TypeError):
        demo.render_seeking_learning_v1(results['nominal_on'], detail=bad)


@pytest.mark.parametrize('case', ['nominal_on', 'competing_on', 'nonfocal', 'stand_follow_drift'])
def test_cli_outside_repo_returns_complete_shared_result(results, case, tmp_path):
    run = subprocess.run([sys.executable, str(ROOT / 'scripts/review_nca8_feeding.py'), '--seek-learning', '--case', case, '--json'],
                         cwd=tmp_path, text=True, capture_output=True, check=False)
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout) == json.loads(json.dumps([results[case].as_dict()]))


@pytest.mark.parametrize('arguments', [['--seek-learning', '--oral'], ['--seek-learning', '--seek-attention'],
                                        ['--seek-learning', '--case', 'nonsense']])
def test_invalid_cross_family_cli_fails(arguments):
    run = subprocess.run([sys.executable, str(ROOT / 'scripts/review_nca8_feeding.py'), *arguments],
                         text=True, capture_output=True, check=False)
    assert run.returncode != 0 and 'error:' in run.stderr


def test_menu_inspection_reuses_retained_results(results, monkeypatch):
    answers = iter(['6', '1', '6', ''])
    calls = []
    monkeypatch.setattr(demo.cca8_cli, 'read_menu_input_v1', lambda: next(answers))
    def run(case):
        calls.append(case); return results[case]
    monkeypatch.setattr(demo, 'run_seeking_learning_v1', run)
    demo.run_seeking_learning_menu_v1()
    assert calls == ['nominal_on', 'nominal_off', 'competing_on', 'competing_off', 'attention_off', 'comparison_off']


def test_parent_menu_routes_without_executing_old_trials(monkeypatch):
    answers = iter(['22', ''])
    calls = []
    monkeypatch.setattr(nca8_feeding_demo.cca8_cli, 'read_menu_input_v1', lambda: next(answers))
    monkeypatch.setattr(nca8_feeding_demo, 'run_seeking_learning_menu_v1', lambda: calls.append('F'))
    monkeypatch.setattr(nca8_feeding_demo, 'run_feeding_detail_v1', lambda *a: pytest.fail('ran old experiment'))
    nca8_feeding_demo.run_feeding_detail_menu_v1()
    assert calls == ['F']


def test_reset_closes_old_hook_and_replaces_all_pending_ownership():
    trial = demo.create_seeking_learning_trial_v1()
    trial.focal_step()
    old = trial.core.feeding_detail.learning_hook
    assert old.pending()
    trial.reset()
    assert not old.pending() and old._closed
    new = trial.core.feeding_detail.learning_hook
    assert new is not old and new.stream.generation == old.stream.generation + 1
    with pytest.raises(RuntimeError):
        old.reconcile(cycle_id=2, cutoff_tick=4)
    assert not new.pending()


@pytest.mark.parametrize('after_effect', [False, True])
def test_physical_fault_closes_hook_and_never_retries(monkeypatch, after_effect):
    trial = demo.create_seeking_learning_trial_v1()
    trial.focal_step()
    original = MotorWorldV1.step
    calls = []
    def fail(world, command):
        calls.append(command)
        if after_effect:
            original(world, command)
        raise RuntimeError('test physical fault')
    monkeypatch.setattr(MotorWorldV1, 'step', fail)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.core.feeding_detail.learning_hook._closed
    assert not trial.core.feeding_detail.learning_hook.pending()
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert len(calls) == 1


def test_hook_overflow_stops_before_fresh_installation(monkeypatch):
    trial = demo.create_seeking_learning_trial_v1()
    monkeypatch.setattr(SeekingLearningHookV1, 'reconcile', lambda *a, **k: (_ for _ in ()).throw(OverflowError('test')))
    with pytest.raises(OverflowError):
        trial.focal_step()
    assert trial.controller.installation_count == 0 and trial.tick == 0
    assert trial.core.feeding_detail.learning_hook._closed


def test_production_hook_imports_no_physics_controller_or_global_learning_writer():
    tree = ast.parse((ROOT / 'nca8_seek_learning.py').read_text())
    imports = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    assert not imports & {'cca8_support_world', 'nca8_hierarchy', 'nca8_sensorimotor', 'nca8_learning_registry', 'random'}
    assert not any(isinstance(node, ast.Attribute) and node.attr in {'_state', '_world', 'step', 'allocate', '_relevance'} for node in ast.walk(tree))


def test_registry_has_real_modules_without_new_behavioral_primitives():
    rows = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert rows['nca8_seek_learning'] == 'nca8_seek_learning'
    assert rows['nca8_seek_learning_demo'] == 'nca8_seek_learning_demo'
    assert len(cca8_run._cca8_component_rows()) == 115 and len(cca8_run.PRIMITIVES) == 8
