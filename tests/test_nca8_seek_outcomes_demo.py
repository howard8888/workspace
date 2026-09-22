"""Causal, lifecycle, UI and exact retained-evidence tests for the D consumer."""

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
import nca8_menu
from nca8_runtime import Nca8SessionV1
import nca8_seek_nipple_demo as previous
import nca8_seek_outcomes_demo as demo
from nca8_seek_outcomes import SeekNippleIntervalEvidenceV1

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="module")
def results():
    return {case: demo.run_seek_nipple_outcome_v1(case) for case in demo.SEEK_NIPPLE_OUTCOME_CASES_V1}


def motion(result):
    return tuple(None if step.command is None else step.command.as_dict() for step in result.evidence.local_steps)


def sources(result):
    return tuple(c.feeding_detail_source.as_dict() if c.feeding_detail_source is not None else None for c in result.evidence.cycles)


@pytest.mark.parametrize("case", demo.SEEK_NIPPLE_OUTCOME_CASES_V1)
def test_each_declared_case_has_complete_finite_causal_evidence(results, case):
    result = results[case]
    assert result.review_status == "PASS", result.checks()
    assert len(result.checks()) == 15 and all(value for _, value in result.checks())
    assert result.evidence.physical_samples and not result.bound_violations
    assert result.evidence.durable_before == result.evidence.durable_after
    assert result.as_dict()["B99"] == "open"


def test_same_geometry_and_commands_do_not_manufacture_touch(results):
    present, absent = results["nominal"], results["no_surface"]
    assert motion(present) == motion(absent)
    assert present.outcomes()[0].status == absent.outcomes()[0].status == "matched"
    assert present.outcomes()[0].evidence.feedback.oral.contact is True
    assert absent.outcomes()[0].evidence.feedback.oral.contact is False
    assert present.evidence.metrics()["first_physical_touch_tick"] == 4
    assert absent.evidence.metrics()["first_physical_touch_tick"] is None
    assert dict(absent.outcomes()[0].residuals)["mouth_position"] == pytest.approx(0)


@pytest.mark.parametrize("enabled,disabled", [("nominal", "comparison_off"), ("endpoint_drift", "drift_comparison_off")])
def test_comparison_lesion_preserves_every_command_source_task_and_physical_sample(results, enabled, disabled):
    on, off = results[enabled], results[disabled]
    assert motion(on) == motion(off) and sources(on) == sources(off)
    assert on.evidence.physical_samples == off.evidence.physical_samples
    assert on.evidence.metrics() == off.evidence.metrics()
    assert tuple(c.seeking_task for c in on.evidence.cycles) == tuple(c.seeking_task for c in off.evidence.cycles)
    assert off.outcomes()[0].status == "comparison_disabled" and not off.outcomes()[0].relations
    assert on.outcomes()[0].command_intervals == off.outcomes()[0].command_intervals == 4


def test_original_endpoint_mismatch_is_not_repaired_by_local_achievement(results):
    outcome = results["endpoint_drift"].outcomes()[0]
    assert outcome.status == "mismatch" and dict(outcome.relations)["detail_anchor"] == "matched"
    assert dict(outcome.residuals)["mouth_position"] == pytest.approx(0.01)
    assert (outcome.claim.due_tick, outcome.evidence.feedback.event_tick, outcome.evidence.feedback.available_tick) == (8, 8, 9)
    assert outcome.evaluated_tick == 12
    earlier = next(s for s in results["endpoint_drift"].evidence.local_steps if s.tick == 5)
    assert earlier.reports[0].disposition.value == "achieved"
    assert outcome.as_dict()["causal_credit"] == "not_established"


def test_after_endpoint_change_cannot_replace_the_original_event_with_current_geometry(results):
    result = results["after_endpoint_drift"]
    first = result.outcomes()[0]
    assert first.status == "matched" and first.evidence.mouth_position.x == pytest.approx(0.1)
    later_cycle = next(c for c in result.evidence.cycles if c.calculation.cutoff_tick == first.evaluated_tick)
    assert later_cycle.feeding_detail_source.oral_feedback.event_tick == 11
    assert later_cycle.feeding_detail_source.oral_feedback.oral.extension_metres == pytest.approx(0.11)
    assert first.claim.preview.predicted_mouth.x == pytest.approx(0.1)


def test_narrowing_preserves_original_prediction_and_separately_scores_unchanged_anchor(results):
    result = results["narrowed"]
    first = result.outcomes()[0]
    assert result.as_dict()["oral_capability_maximum_step_metres"] == 0.04
    assert first.claim.preview.predicted_mouth.x == pytest.approx(0.1)
    assert first.claim.targets[0].target.endpoint == pytest.approx(0.04)
    assert first.status == "partly_matched"
    assert dict(first.relations) == {"mouth_position": "unevaluable_authorization", "detail_anchor": "matched",
                                     "separation": "unevaluable_authorization"}
    assert first.command_intervals == 2 and len(result.claims()) == 3


def test_registration_bank_lesion_preserves_original_handoff_claim_and_scoring(results):
    on, off = results["nominal"], results["pnm_registration_off"]
    assert motion(on) == motion(off) and on.evidence.physical_samples == off.evidence.physical_samples
    assert not off.evidence.registered_pnm_cycles and on.evidence.registered_pnm_cycles
    assert off.claims()[0].preview is off.evidence.cycles[0].receipt.dispatch.motor.projection
    assert off.outcomes()[0].status == "matched"


@pytest.mark.parametrize("case", ["seek_off", "stand_follow_seek_off"])
def test_no_selected_seeking_has_no_claim_or_oral_action(results, case):
    result = results[case]
    assert not result.claims() and not result.outcomes()
    assert not any(s.command is not None and s.command.oral_drive not in (None, 0.0) for s in result.evidence.local_steps)


@pytest.mark.parametrize("case", ["no_capability", "heading_90", "out_of_reach"])
def test_bodymap_veto_is_not_an_executed_prediction_failure(results, case):
    result = results[case]
    assert result.claims() and all(not c.targets for c in result.claims())
    assert all(o.status == "not_applied" and o.command_intervals == 0 and o.evidence is None for o in result.outcomes())
    assert result.evidence.installations == 0


def test_distinct_task_contributions_keep_distinct_original_claims(results):
    result = results["intermediate_target"]
    first, second = result.outcomes()
    assert first.claim.preview.task_id == second.claim.preview.task_id
    assert first.claim.preview.pnm.application_id != second.claim.preview.pnm.application_id
    assert (first.claim.due_tick, second.claim.due_tick) == (8, 16)
    assert (first.command_intervals, second.command_intervals) == (6, 6)
    assert first.claim.preview.basis.oral_feedback.oral.extension_metres == 0
    assert second.claim.preview.basis.oral_feedback.oral.extension_metres == pytest.approx(0.15)


def test_dropout_private_touch_is_not_a_corresponding_observed_result(results):
    result = results["dropout"]
    assert result.evidence.metrics()["first_physical_touch_tick"] is not None
    assert result.outcomes()[0].status == "interrupted" and result.outcomes()[0].evidence is None
    assert result.evidence.metrics()["first_reached_detail_tick"] is None


def test_continuous_run_does_not_attribute_support_or_translation_to_oral_claim(results):
    result = results["stand_follow"]
    assert result.evidence.metrics()["first_seeking_tick"] == 92
    assert next(c.calculation.cutoff_tick for c in result.evidence.cycles
                if c.maternal_task is not None and c.maternal_task.task is not None and c.maternal_task.task.status == "completed") == 100
    assert [o.claim.due_tick for o in result.outcomes()] == [100, 108]
    assert [o.command_intervals for o in result.outcomes()] == [6, 6]
    assert any(c.claim_registration is not None for c in result.evidence.cycles)
    assert any(c.maternal_correspondence is not None for c in result.evidence.cycles)
    assert all(c.seeking_correspondence.as_dict()["learning_route"] == "unimplemented_no_participation" for c in result.evidence.cycles)


def test_fast_focal_cadence_can_match_an_endpoint_without_completing_the_task(results):
    result = results["cadence_1"]
    assert result.outcomes()[0].status == "matched"
    assert result.evidence.metrics()["final_task_status"] == "budget_exhausted"
    assert len(result.evidence.local_steps) == len(results["cadence_8"].evidence.local_steps) == 64
    assert result.evidence.profile.seeking.as_dict()["maximum_physical_ticks"] == results["nominal"].evidence.profile.seeking.as_dict()["maximum_physical_ticks"]


@pytest.mark.parametrize("case", ["nominal", "endpoint_drift", "narrowed", "dropout", "stand_follow"])
@pytest.mark.parametrize("capacity", [1, 8])
def test_retention_changes_only_its_own_measured_diagnostic_count(results, case, capacity):
    small = demo.run_seek_nipple_outcome_v1(case, trace_capacity=capacity).as_dict()
    original = results[case].as_dict()
    differences = {key for key,value in small["peak_owner_counts"].items() if original["peak_owner_counts"].get(key) != value}
    assert differences == {"focal_trace"}
    assert small["peak_owner_counts"]["focal_trace"] == capacity
    # Only this intentionally changed diagnostic storage count is unequal.
    small["peak_owner_counts"]["focal_trace"] = original["peak_owner_counts"]["focal_trace"]
    assert small == original


def test_export_and_both_renderers_are_readonly(results, monkeypatch):
    result = results["endpoint_drift"]
    before, rng = result.as_dict(), random.getstate()
    monkeypatch.setattr(demo, "run_seek_nipple_outcome_v1", lambda *args, **kwargs: pytest.fail("inspection reran a trial"))
    assert "mismatch" in demo.render_seek_nipple_outcome_v1(result, detail=True)
    assert "PASS" in demo.render_seek_nipple_outcome_v1(result)
    changed = result.as_dict()
    changed["outcomes"][0]["relation_results"].clear()
    assert result.as_dict() == before and random.getstate() == rng


@pytest.mark.parametrize("change", ["no_cycles", "no_steps", "no_physics", "duplicate_outcome", "missing_claim", "wrong_exposure",
                                    "missing_count", "duplicate_count", "coerced_count", "over_count", "durable", "consumptions", "installations"])
def test_missing_or_tampered_evidence_cannot_pass(results, change):
    result = results["nominal"]
    raw = result.evidence
    if change == "no_cycles":
        raw = replace(raw, cycles=())
    elif change == "no_steps":
        raw = replace(raw, local_steps=())
    elif change == "no_physics":
        raw = replace(raw, physical_samples=())
    elif change in {"duplicate_outcome", "missing_claim", "wrong_exposure"}:
        cycles = list(raw.cycles)
        index = 0 if change == "missing_claim" else next(i for i,c in enumerate(cycles) if c.seeking_correspondence.outcomes)
        frame = cycles[index].seeking_correspondence
        if change == "missing_claim":
            frame = replace(frame, registration=None)
        elif change == "duplicate_outcome":
            frame = replace(frame, outcomes=frame.outcomes * 2)
        else:
            frame = replace(frame, outcomes=(replace(frame.outcomes[0], command_intervals=99),))
        cycles[index] = replace(cycles[index], seeking_correspondence=frame)
        raw = replace(raw, cycles=tuple(cycles))
    elif change == "missing_count":
        raw = replace(raw, peak_counts=tuple((k,v) for k,v in raw.peak_counts if k != "seeking_pending_claims"))
    elif change == "duplicate_count":
        raw = replace(raw, peak_counts=raw.peak_counts + (raw.peak_counts[0],))
    elif change in {"coerced_count", "over_count"}:
        raw = replace(raw, peak_counts=tuple((k, True if change == "coerced_count" else 99) if k == "seeking_pending_claims" else (k,v)
                                            for k,v in raw.peak_counts))
    elif change == "durable":
        raw = replace(raw, durable_after="changed")
    elif change == "consumptions":
        raw = replace(raw, handoff_consumptions=raw.handoff_consumptions + 1)
    else:
        raw = replace(raw, installations=raw.installations + 1)
    assert replace(result, evidence=raw).review_status == "FAIL"


@pytest.mark.parametrize("case", [None, True, 1, [], "", "NOMINAL", "typo"])
def test_unknown_selector_fails_before_constructing_any_trial(case):
    with pytest.raises(ValueError):
        demo.run_seek_nipple_outcome_v1(case)


@pytest.mark.parametrize("detail", [None, 0, 1, "yes"])
def test_render_option_is_boolean_not_truthy(results, detail):
    with pytest.raises(TypeError):
        demo.render_seek_nipple_outcome_v1(results["nominal"], detail=detail)


@pytest.mark.parametrize("capacity", [0, 4097, True, 1.5, "8"])
def test_retention_bounds_are_not_coerced(capacity):
    with pytest.raises((TypeError, ValueError)):
        demo.create_seek_nipple_outcome_trial_v1(trace_capacity=capacity)


@pytest.mark.parametrize("case", ["nominal", "endpoint_drift", "narrowed", "stand_follow"])
def test_cli_outside_repository_exports_identical_shared_evidence(results, case, tmp_path):
    output = subprocess.run([sys.executable, str(ROOT/'scripts/review_nca8_feeding.py'), '--seek-outcomes', '--case', case, '--json'],
                            cwd=tmp_path, capture_output=True, text=True, check=False)
    assert output.returncode == 0, output.stderr
    assert json.loads(output.stdout) == [json.loads(json.dumps(results[case].as_dict(), allow_nan=False))]


@pytest.mark.parametrize("args", [["--seek", "--seek-outcomes"], ["--oral", "--seek-outcomes"],
                                 ["--seek-outcomes", "--case", "wrong_parent_seed"], ["--seek-outcomes", "--case", "typo"]])
def test_cli_rejects_cross_family_and_unknown_cases(args):
    output = subprocess.run([sys.executable, str(ROOT/'scripts/review_nca8_feeding.py'), *args], capture_output=True, text=True, check=False)
    assert output.returncode == 2


@pytest.mark.parametrize("group,count", [("1",3), ("2",3), ("3",5), ("4",7), ("5",3), ("6",len(demo.SEEK_NIPPLE_OUTCOME_CASES_V1))])
def test_menu_uses_declared_shared_cases_and_retains_without_rerun(results, monkeypatch, capsys, group, count):
    answers, calls = iter(("7", "bad", group, "7", "")), []
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    def run(case):
        calls.append(case)
        return results[case]
    monkeypatch.setattr(demo, "run_seek_nipple_outcome_v1", run)
    demo.run_seek_nipple_outcome_menu_v1()
    assert len(calls) == count
    assert "No completed results" in capsys.readouterr().out


def test_parent_feeding_menu_delegates_without_new_run_or_reset(monkeypatch):
    answers, calls = iter(("20", "")), []
    monkeypatch.setattr(nca8_feeding_demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    monkeypatch.setattr(nca8_feeding_demo, "run_seek_nipple_outcome_menu_v1", lambda: calls.append("outcomes"))
    nca8_feeding_demo.run_feeding_detail_menu_v1()
    assert calls == ["outcomes"]


def test_full_nested_menu_preserves_existing_a0_session_and_rng(monkeypatch, capsys):
    session = Nca8SessionV1()
    before = session.status(), session.trace_snapshot(), random.getstate()
    answers = iter(("15", "20", "1", "7", "", "", ""))
    monkeypatch.setattr(demo.cca8_cli, "read_menu_input_v1", lambda: next(answers))
    assert nca8_menu.run_nca8_experimental_menu_v1(session) is session
    assert capsys.readouterr().out.count("P16-2C-D / nominal / SEEKING CORRESPONDENCE REVIEW: PASS") == 2
    assert (session.status(), session.trace_snapshot(), random.getstate()) == before


def test_new_consumer_cannot_read_private_world_select_tasks_or_write_learning():
    tree = ast.parse((ROOT/'nca8_seek_outcomes.py').read_text())
    modules = {node.module for node in ast.walk(tree) if isinstance(node, ast.ImportFrom)}
    attributes = {node.attr for node in ast.walk(tree) if isinstance(node, ast.Attribute)}
    assert not modules & {"cca8_support_world", "cca8_env", "nca8_hierarchy", "nca8_sensorimotor", "cca8_feeding", "nca8_learning"}
    assert not attributes & {"_world", "milestones", "reward", "observer_body", "observer_planar_body", "observer_oral_body", "commit", "apply"}


def test_d_collector_is_the_existing_c_collector_not_a_second_cognitive_loop(monkeypatch):
    calls = []
    original = previous.collect_seek_nipple_evidence_v1
    def collect(trial, profile):
        calls.append(profile.case)
        return original(trial, profile)
    monkeypatch.setattr(demo, 'collect_seek_nipple_evidence_v1', collect)
    assert demo.run_seek_nipple_outcome_v1().review_status == "PASS"
    assert calls == ["nominal"]


def test_reset_replaces_claim_owner_and_invalidates_old_installations():
    trial = demo.create_seek_nipple_outcome_trial_v1()
    first = trial.focal_step()
    trial.advance_lower()
    owner, claim = trial.core.seeking_outcomes, first.seeking_correspondence.registration
    trial.reset()
    assert owner is not trial.core.seeking_outcomes
    assert not trial.core.seeking_outcomes.pending() and not trial._seeking_intervals
    assert trial.tick == 0 and trial.core.cognition.stream.generation == 2
    with pytest.raises((ValueError, RuntimeError)):
        trial.core.seeking_outcomes.installed(claim, at_tick=0)
    assert trial.focal_step().seeking_correspondence.registration.preview.basis.stream.generation == 2


@pytest.mark.parametrize("after_effect", [False, True])
def test_fault_closes_pending_claim_as_unknown_and_never_retries(monkeypatch, after_effect):
    trial = demo.create_seek_nipple_outcome_trial_v1()
    trial.focal_step()
    original, calls = MotorWorldV1.step, []
    def fail(world, command):
        calls.append(command)
        if after_effect:
            original(world, command)
        raise RuntimeError("physical call failed")
    monkeypatch.setattr(MotorWorldV1, "step", fail)
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert trial.stopped and trial.tick == int(after_effect)
    assert trial.core.seeking_outcomes.history()[0].status == "unresolved_stopped"
    with pytest.raises(RuntimeError):
        trial.advance_lower()
    assert len(calls) == 1 and not trial.core.seeking_outcomes.pending()


def test_ingress_overflow_stops_before_an_extra_world_interval():
    trial = demo.create_seek_nipple_outcome_trial_v1()
    trial.focal_step()
    for _ in range(16):
        trial.advance_lower()
    before = trial.tick, trial.observer_oral_body
    with pytest.raises(OverflowError):
        trial.advance_lower()
    assert (trial.tick, trial.observer_oral_body) == before and trial.stopped
    assert trial.core.seeking_outcomes.history()[0].status == "unresolved_stopped"


def test_unknown_frozen_interval_type_stops_core_without_new_installation():
    trial = demo.create_seek_nipple_outcome_trial_v1()
    trial.focal_step()
    trial.advance_lower()
    interval = trial._seeking_intervals[0]
    assert isinstance(interval, SeekNippleIntervalEvidenceV1)
    trial._seeking_intervals[0] = "invented"
    count = trial.controller.installation_count
    with pytest.raises((TypeError, ValueError)):
        trial.focal_step()
    assert trial.stopped and trial.controller.installation_count == count


def test_registry_lists_two_real_components_without_new_host_behavioral_primitives():
    registry = dict(cca8_run._CCA8_COMPONENT_REGISTRY)
    assert registry['nca8_seek_outcomes'] == 'nca8_seek_outcomes'
    assert registry['nca8_seek_outcomes_demo'] == 'nca8_seek_outcomes_demo'
    assert len(cca8_run._cca8_component_rows()) == 101 and len(cca8_run.PRIMITIVES) == 8


def test_narrowing_reference_holds_cadence_provider_geometry_and_original_task_fixed(results):
    control, narrow = results["narrowing_control"], results["narrowed"]
    left, right = control.evidence.profile.as_dict(), narrow.evidence.profile.as_dict()
    assert left["cadence"] == right["cadence"] == 8
    # The case name identifies the intervention; all task/world profile fields agree.
    left["case"] = right["case"]
    assert left == right
    assert control.claims()[0].preview.as_dict() == narrow.claims()[0].preview.as_dict()
    assert control.claims()[0].request.as_dict() == narrow.claims()[0].request.as_dict()
    assert control.outcomes()[0].status == "matched" and narrow.outcomes()[0].status == "partly_matched"
    assert control.outcomes()[0].evaluated_tick == narrow.outcomes()[0].evaluated_tick == 16
    assert control.claims()[0].targets[0].target.endpoint == pytest.approx(0.1)
    assert narrow.claims()[0].targets[0].target.endpoint == pytest.approx(0.04)
