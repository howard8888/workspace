"""Finite causal contrasts and read-only menu/CLI for actual translation."""
from dataclasses import replace
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_translation_demo as demo
import nca8_visual_demo as preview
from nca8_translation_demo import TRANSLATION_CASES_V1, run_translation_v1
from nca8_sensorimotor_contracts import LocalTargetDispositionV1

ROOT=Path(__file__).resolve().parents[1]


@pytest.mark.parametrize('case', TRANSLATION_CASES_V1)
def test_every_profile_has_real_finite_history_and_unchanged_durable_owners(case):
    first = run_translation_v1(case)
    assert first.as_dict() == run_translation_v1(case).as_dict()
    assert len(first.local_steps) == len(first.physical_samples) == 12
    assert [x.calculation.cutoff_tick for x in first.cycles] == [0,4,8,12]
    assert first.bound_violations == () and first.durable_unchanged
    assert first.as_dict()['elapsed_seconds'] == pytest.approx(.6)
    assert first.as_dict()['durable_updates'] == 0
    assert first.as_dict()['task_outcome_consumer'] == 'not_implemented_for_visual'


def test_true_rotation_differs_from_coordinate_reexpression_in_consumed_drives():
    zero, ninety, rotated = [run_translation_v1(x) for x in ('heading_0','heading_90','rotated_coordinates')]
    d0=zero.local_steps[0].command.translation
    d90=ninety.local_steps[0].command.translation
    dr=rotated.local_steps[0].command.translation
    assert (d90.forward,d90.left)==pytest.approx((d0.left,-d0.forward))
    assert (dr.forward,dr.left)==pytest.approx((d0.forward,d0.left))
    for a,b,c in zip(zero.physical_samples,ninety.physical_samples,rotated.physical_samples):
        assert a.position == pytest.approx(b.position)
        assert c.position == pytest.approx((-a.position[1],a.position[0]))


def test_recognition_off_preserves_target_and_every_drive_not_merely_endpoint():
    on, off = run_translation_v1('heading_0'),run_translation_v1('recognition_off')
    assert on.cycles[0].visual_source.recognition and not off.cycles[0].visual_source.recognition
    assert on.cycles[0].visual_source.guidance == off.cycles[0].visual_source.guidance
    assert on.cycles[0].reservations == off.cycles[0].reservations
    assert [s.command for s in on.local_steps] == [s.command for s in off.local_steps]
    assert on.physical_samples == off.physical_samples


@pytest.mark.parametrize('case',['spatial_off','vision_missing','heading_missing','contact_unknown','capability_missing'])
def test_missing_evidence_or_capability_has_no_translation_command(case):
    result=run_translation_v1(case)
    assert all(s.command is None or s.command.translation is None for s in result.local_steps)
    assert result.physical_samples[-1].position == (0,0)


def test_fast_feedback_changes_drive_before_next_focal_call_with_same_target_and_forcing():
    on, off = run_translation_v1('disturbed'),run_translation_v1('feedback_slow')
    assert on.cycles[0].as_dict() == off.cycles[0].as_dict()
    assert on.physical_samples[:3] == off.physical_samples[:3]
    assert [s.command for s in on.local_steps[:3]] == [s.command for s in off.local_steps[:3]]
    assert on.local_steps[3].command != off.local_steps[3].command
    assert on.cycles[1].calculation.cutoff_tick == off.cycles[1].calculation.cutoff_tick == 4
    assert on.local_steps[-1].reports[0].disposition is LocalTargetDispositionV1.ACHIEVED
    assert off.local_steps[-1].reports[0].disposition is LocalTargetDispositionV1.EXPIRED


def test_local_prediction_off_preserves_reactive_motion_and_can_have_same_endpoint():
    on, off = run_translation_v1('disturbed'),run_translation_v1('prediction_off')
    assert on.cycles[0].reservations == off.cycles[0].reservations
    assert on.physical_samples[:3] == off.physical_samples[:3]
    assert on.local_steps[3].command != off.local_steps[3].command
    assert on.physical_samples[-1].position == off.physical_samples[-1].position
    assert any(step.predictions for step in off.local_steps)
    assert all(report.correction_count == 0 for step in off.local_steps for report in step.reports)


def test_real_obstacle_stops_pursuit_without_an_autonomous_detour():
    result=run_translation_v1('obstacle_contact')
    assert result.final_feedback.planar.obstacle_contact is True
    assert result.physical_samples[-1].position[0] < .14
    assert result.local_steps[-1].reports[0].reason == 'observed_obstacle_contact'
    assert all(s.command is None for s in result.local_steps[4:])
    assert sum(c.commitment.selected_primitive_id == 'fixture:translation' for c in result.cycles)==1


@pytest.mark.parametrize('case',['feedback_missing','feedback_delayed','motor_blocked','cancelled'])
def test_adverse_trial_does_not_fake_local_achievement(case):
    result=run_translation_v1(case)
    assert result.local_steps[-1].reports[0].disposition is not LocalTargetDispositionV1.ACHIEVED
    assert all(s.command is None for s in result.local_steps[8:])


@pytest.mark.parametrize('case',['heading_0','obstacle_contact','disturbed','feedback_missing','support_priority'])
def test_trace_retention_does_not_control_source_target_or_motion(case):
    assert run_translation_v1(case,trace_capacity=1).as_dict()['cycles'] == run_translation_v1(case).as_dict()['cycles']
    assert run_translation_v1(case,trace_capacity=1).physical_samples == run_translation_v1(case).physical_samples


def test_render_and_export_are_detached_without_rng_or_cognitive_effect():
    state=random.getstate()
    result=run_translation_v1()
    original=json.dumps(result.as_dict(),sort_keys=True)
    assert 'supplied' in demo.render_translation_v1(result).lower()
    assert 'lower tick=0' in demo.render_translation_v1(result,detail=True)
    exported=result.as_dict();exported['observer_physical_samples'][0]['position'][0]=500
    assert json.dumps(result.as_dict(),sort_keys=True)==original
    assert random.getstate()==state


def test_real_measured_bound_or_durable_change_is_not_hidden():
    result=run_translation_v1()
    assert replace(result,peak_counts=(('wnm',2),)).bound_violations==('wnm',)
    assert not replace(result,durable_after='changed').durable_unchanged


@pytest.mark.parametrize('case',['heading_90','obstacle_contact','disturbed'])
def test_script_runs_outside_repo_and_exports_actual_shared_results(case,tmp_path):
    process=subprocess.run([sys.executable,str(ROOT/'scripts/review_nca8_visual.py'),'--translation',case,'--json'],
                           cwd=tmp_path,capture_output=True,text=True,check=False)
    assert process.returncode==0,process.stderr
    assert json.loads(process.stdout)==json.loads(json.dumps([run_translation_v1(case).as_dict()]))
    assert list(tmp_path.iterdir())==[]


@pytest.mark.parametrize('arguments',[['--translation','bad'],['--translation','--case','heading_0']])
def test_cli_refuses_unknown_or_mixed_profiles(arguments):
    process=subprocess.run([sys.executable,str(ROOT/'scripts/review_nca8_visual.py'),*arguments],capture_output=True,text=True,check=False)
    assert process.returncode==2


def test_script_returns_nonzero_on_inspection_failure(monkeypatch,capsys):
    from scripts import review_nca8_visual as script
    result=replace(run_translation_v1(),durable_after='bad')
    monkeypatch.setattr(script,'run_translation_v1',lambda _case:result)
    assert script.main(['--translation','heading_0'])==1
    assert 'durable unchanged=False' in capsys.readouterr().out


def test_visual_menu_injects_translation_route_without_a_second_renderer_loop(monkeypatch):
    inputs=iter(['8',''])
    monkeypatch.setattr(preview.cca8_cli,'read_menu_input_v1',lambda:next(inputs))
    calls=[]
    preview.run_visual_preview_menu_v1(translation_review=lambda:calls.append('one'))
    assert calls==['one']


def test_opening_translation_menu_runs_no_trial(monkeypatch):
    monkeypatch.setattr(demo.cca8_cli,'read_menu_input_v1',lambda:'')
    monkeypatch.setattr(demo,'run_translation_v1',lambda *_a,**_k:pytest.fail('opening menu advanced world'))
    demo.run_translation_menu_v1()


def test_detail_menu_reuses_same_trial_function(monkeypatch):
    inputs=iter(['7',''])
    monkeypatch.setattr(demo.cca8_cli,'read_menu_input_v1',lambda:next(inputs))
    result=run_translation_v1()
    calls=[]
    monkeypatch.setattr(demo,'run_translation_v1',lambda c:(calls.append(c),result)[1])
    demo.run_translation_menu_v1()
    assert calls==['heading_0']


@pytest.mark.parametrize('case',[None,True,'','HEADING_0',3])
def test_bad_case_does_not_create_an_unrequested_body(case):
    with pytest.raises(ValueError):
        run_translation_v1(case)
