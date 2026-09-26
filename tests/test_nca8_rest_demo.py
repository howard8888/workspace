"""Shared Rest walkthrough, complete evidence, exact stepping and read-only export."""
from dataclasses import replace
from functools import lru_cache
import importlib.util
import json
from pathlib import Path
import random
import subprocess
import sys

import pytest

import nca8_rest_demo as demo
import nca8_feeding_demo as parent
from nca8_outcomes import RightingIntervalEvidenceV1

ROOT=Path(__file__).resolve().parents[1]


@lru_cache(None)
def result(case='already_fed'):
    return demo.run_rest_v1(case)


@pytest.mark.parametrize('case',demo.REST_CASES_V1)
def test_each_declared_live_profile_has_complete_bounded_truthful_evidence(case):
    r=result(case)
    assert r.review_status=='PASS'
    assert len(r.local_steps)==320 and len(r.physical_samples)==321
    assert all(ok for _,ok in r.checks())
    assert r.as_dict()['B99']=='not_claimed'


@pytest.mark.parametrize('case',['nominal','already_recumbent','release_drift','post_rest_support_loss'])
def test_explicit_stepping_and_automatic_run_are_the_identical_trial_schedule(case):
    w=demo.RestWalkthroughV1(demo.rest_profile_v1(case))
    while not w.finished:
        before=w.trial.tick
        w.advance()
        assert w.trial.tick==min(before+w.profile.cadence,w.profile.horizon_ticks)
    assert w.snapshot().as_dict()==result(case).as_dict()
    with pytest.raises(ValueError): w.advance()


def test_inspect_export_and_browse_never_advance_reset_or_modify(tmp_path,monkeypatch):
    w=demo.RestWalkthroughV1(demo.rest_profile_v1('already_fed'))
    for _ in range(4): w.advance()
    before=w.snapshot().as_dict();tick=w.trial.tick;rng=random.getstate()
    def forbidden(*args,**kwargs): raise AssertionError('inspection attempted execution')
    monkeypatch.setattr(w.trial,'focal_step',forbidden);monkeypatch.setattr(w.trial,'advance_lower',forbidden)
    assert 'Cognitive cycle' in w.inspect() and 'EXTERNAL BODY' in w.inspect()
    assert 'Cognitive cycle 1' in w.inspect(0)
    path=tmp_path/'retained.txt';w.export(path)
    assert json.loads(path.read_text(encoding='utf-8'))==before
    with pytest.raises(FileExistsError): w.export(path)
    assert w.snapshot().as_dict()==before and w.trial.tick==tick and random.getstate()==rng


@pytest.mark.parametrize('bad',[None,True,'1',1.5])
def test_inspection_index_is_not_coerced(bad):
    w=demo.RestWalkthroughV1(demo.rest_profile_v1())
    with pytest.raises(TypeError): w.inspect(bad)
    assert w.trial.tick==0


def test_empty_or_out_of_range_inspection_performs_no_work():
    w=demo.RestWalkthroughV1(demo.rest_profile_v1())
    assert 'No retained cycle' in w.inspect()
    w.advance()
    with pytest.raises(IndexError): w.inspect(2)
    assert w.trial.tick==4


@pytest.mark.parametrize('case',['already_fed','attention_off','navigation_off'])
def test_reset_replaces_only_this_generation_and_preserves_declared_ablation(case):
    w=demo.RestWalkthroughV1(demo.rest_profile_v1(case));other=demo.RestWalkthroughV1(demo.rest_profile_v1('already_fed'))
    first=w.run_to_end();old=w.trial.core.rest;old_outcomes=w.trial.core.cognition.sensory.rest_outcomes
    before_other=other.trial.snapshot()
    w.reset()
    assert w.trial.tick==0 and not w.finished and w.snapshot().cycles==()
    assert w.trial.core.rest is not old and other.trial.snapshot()==before_other
    assert old_outcomes._closed
    second=w.run_to_end()
    assert second.metrics()==first.metrics()
    assert second.cycles[0].receipt.generation==first.cycles[0].receipt.generation+1


@pytest.mark.parametrize('field,value',[('horizon_ticks',0),('horizon_ticks',321),('horizon_ticks',True),('cadence',2),
    ('cadence',True),('cancel_tick',321),('cancel_tick',-1),('navigation_enabled',1),('attention_enabled',None),
    ('maternal_association_enabled','true'),('rest',None),('bearing',None)])
def test_review_limits_remain_separate_strict_explicit_configuration(field,value):
    with pytest.raises((ValueError,TypeError)): replace(demo.rest_profile_v1(),**{field:value})


@pytest.mark.parametrize('horizon',[1,3,9,13])
def test_nonmultiple_external_horizon_does_not_add_an_extra_physical_step(horizon):
    p=replace(demo.rest_profile_v1('already_fed'),horizon_ticks=horizon)
    w=demo.RestWalkthroughV1(p);r=w.run_to_end()
    assert w.trial.tick==horizon and len(r.local_steps)==horizon
    assert tuple(c.calculation.cutoff_tick for c in r.cycles)==tuple(range(0,horizon+1,4))
    assert dict(r.checks())['complete_declared_schedule']
    assert r.review_status=='FAIL'  # Insufficient horizon cannot establish nominal completion.


@pytest.mark.parametrize('tamper',['cycles','steps','body','claims','outcomes','rest','durable','handoff','installations','dwell'])
def test_missing_or_corrupt_review_cannot_pass_by_omitting_inconvenient_evidence(tamper):
    r=result();cycles=list(r.cycles)
    if tamper=='cycles': r=replace(r,cycles=())
    elif tamper=='steps': r=replace(r,local_steps=r.local_steps[:-1])
    elif tamper=='body': r=replace(r,physical_samples=r.physical_samples[:-1])
    elif tamper=='durable': r=replace(r,durable_after='changed')
    elif tamper=='handoff': r=replace(r,handoff_consumptions=0)
    elif tamper=='installations': r=replace(r,installations=0)
    else:
        for i,c in enumerate(cycles):
            if tamper=='claims' and c.rest.registration: cycles[i]=replace(c,rest=replace(c.rest,registration=None));break
            if tamper=='outcomes' and c.rest.outcomes: cycles[i]=replace(c,rest=replace(c.rest,outcomes=()));break
            if tamper=='rest': cycles[i]=replace(c,rest=None);break
            if tamper=='dwell' and c.rest.current_safe_rest is True: cycles[i]=replace(c,rest=replace(c.rest,current_safe_rest=False));break
        r=replace(r,cycles=tuple(cycles))
    assert r.review_status=='FAIL'


@pytest.mark.parametrize('capacity',[1,4,16])
def test_trace_capacity_is_only_diagnostic_not_support_or_eligibility(capacity):
    small=demo.run_rest_v1('already_fed',trace_capacity=capacity)
    assert small.cycles==result().cycles
    assert small.local_steps==result().local_steps and small.physical_samples==result().physical_samples


@pytest.mark.parametrize('case',['release_drift','release_drift_route_off','release_drift_competing'])
def test_actual_delayed_relation_mismatch_not_a_fabricated_failure_flag(case):
    r=result(case);outcomes=[o for c in r.cycles for o in c.rest.outcomes]
    assert len(outcomes)==1 and outcomes[0].status=='mismatch'
    assert outcomes[0].evidence.oral_seal.closure==pytest.approx(.05)
    assert outcomes[0].claim.application.projection.predicted_coordinate==0
    allocations=[c.rest.allocation for c in r.cycles if c.rest.allocation and c.rest.allocation.kind=='interpretation']
    assert len(allocations)==int(case=='release_drift')
    assert r.metrics()['first_completed_tick'] is None
    f=[status for c in r.cycles if c.rest.learning for _,status in c.rest.learning.dispositions]
    assert ('accepted_no_update' in f)==(case=='release_drift')


def test_question_route_changes_focus_not_actual_original_evidence():
    on,off=result('release_drift'),result('release_drift_route_off')
    assert on.local_steps==off.local_steps and on.physical_samples==off.physical_samples
    a=next(c for c in on.cycles if c.rest.outcomes);b=next(c for c in off.cycles if c.rest.outcomes)
    assert a.rest.outcomes==b.rest.outcomes
    assert a.rest.allocation.kind=='interpretation' and b.rest.allocation.kind!='interpretation'
    assert a.commitment.selected_primitive_id is None


@pytest.mark.parametrize('case',['already_recumbent','release_drift'])
def test_script_from_outside_repository_matches_same_shared_export(tmp_path,case):
    run=subprocess.run([sys.executable,str(ROOT/'scripts/review_nca8_feeding.py'),'--rest','--case',case,'--json'],
                        cwd=tmp_path,text=True,capture_output=True,check=True)
    data=json.loads(run.stdout)
    assert data==[result(case).as_dict()]


@pytest.mark.parametrize('args',[['--rest','--sustained-feeding'],['--rest','--case','unknown']])
def test_invalid_cli_rejects_instead_of_selecting_another_case(args):
    run=subprocess.run([sys.executable,str(ROOT/'scripts/review_nca8_feeding.py'),*args],capture_output=True,text=True)
    assert run.returncode!=0


def test_menu_parent_routes_35_once_without_old_experiments(monkeypatch):
    choices=iter(['35','']);seen=[]
    monkeypatch.setattr(parent.cca8_cli,'read_menu_input_v1',lambda:next(choices))
    monkeypatch.setattr(parent,'run_rest_menu_v1',lambda:seen.append('rest'))
    parent.run_feeding_detail_menu_v1()
    assert seen==['rest']


def test_walkthrough_menu_inspection_is_readonly_and_explicit_step_once(monkeypatch,capsys):
    choices=iter(['4','1','2','4','5','1','0']);counts=[]
    real=demo.RestWalkthroughV1.advance
    def advance(self): counts.append(self.trial.tick);return real(self)
    monkeypatch.setattr(demo.RestWalkthroughV1,'advance',advance)
    monkeypatch.setattr(demo.cca8_cli,'read_menu_input_v1',lambda:next(choices))
    demo.run_rest_menu_v1()
    assert counts==[0]
    assert 'EXTERNAL BODY' in capsys.readouterr().out


@pytest.mark.parametrize('bad',[None,True,'nominal ',1,[]])
def test_unknown_case_cannot_silently_run_a_nominal_organism(bad):
    with pytest.raises(ValueError): demo.rest_profile_v1(bad)


def test_release_registry_lists_three_real_services_not_extra_legacy_primitives():
    import cca8_run
    names={name for name,*_ in cca8_run._cca8_component_rows()}
    assert {'nca8_rest','nca8_rest_outcomes','nca8_rest_demo'}<=names
    assert cca8_run.__version__=='0.30.46' and len(names)==126
    assert len(cca8_run.PRIMITIVES)==8
